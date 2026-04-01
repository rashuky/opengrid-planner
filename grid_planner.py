import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QPushButton, QColorDialog, QLabel, QSpinBox, QHBoxLayout, QWidget,
    QFileDialog, QMessageBox,
)
from PySide6.QtGui import QPen, QColor, QBrush, QUndoStack, QUndoCommand, QKeySequence
from PySide6.QtCore import Qt, QRectF

LOG_PATH = Path(__file__).parent / "actions.log"
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

CELL_SIZE = 20
GRID_CELLS = 10
GRID_BLOCK = CELL_SIZE * GRID_CELLS

PALETTE = [
    ("#e74c3c", "Red"),
    ("#e67e22", "Orange"),
    ("#f1c40f", "Yellow"),
    ("#2ecc71", "Green"),
    ("#3498db", "Blue"),
    ("#9b59b6", "Purple"),
    ("#1abc9c", "Teal"),
    ("#ecf0f1", "White"),
]


class PaintCommand(QUndoCommand):
    """Single undoable stroke: maps each affected cell to (old_color, new_color).
    None means the cell was empty (no fill)."""

    def __init__(self, scene, changes: dict, label: str):
        super().__init__(label)
        self._scene = scene
        # changes: {(col, row): (old_color_hex_or_None, new_color_hex_or_None)}
        self._changes = changes
        self._first_redo = True   # changes already applied during the stroke

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        for (col, row), (_, new) in self._changes.items():
            if new is None:
                self._scene._remove_cell(col, row)
            else:
                self._scene._apply_cell(col, row, QColor(new))
        logging.info("REDO %s cells=%s", self.text(), json.dumps(list(self._changes.keys())))

    def undo(self):
        for (col, row), (old, _) in self._changes.items():
            if old is None:
                self._scene._remove_cell(col, row)
            else:
                self._scene._apply_cell(col, row, QColor(old))
        logging.info("UNDO %s cells=%s", self.text(), json.dumps(list(self._changes.keys())))


class GridScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, 800, 800)
        self._cells = {}          # (col, row) -> QGraphicsRectItem
        self._current_color = QColor("#3498db")
        self._pen_w = 1
        self._pen_h = 1
        self._undo_stack = QUndoStack(self)
        self._stroke_before: dict | None = None   # snapshot before current stroke
        self._stroke_cells: dict = {}             # changes accumulated this stroke
        self._draw_base_grid()

    # ------------------------------------------------------------------ public

    def set_color(self, color: QColor):
        self._current_color = color

    def set_pen_size(self, w: int, h: int):
        self._pen_w = max(1, w)
        self._pen_h = max(1, h)

    @property
    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    # ------------------------------------------------------------------ save/load

    def to_dict(self) -> dict:
        """Serialize the current canvas to a plain dictionary."""
        cells = []
        for (col, row), item in self._cells.items():
            cells.append({
                "col": col,
                "row": row,
                "color": item.brush().color().name(),
            })
        return {
            "version": 1,
            "cell_size": CELL_SIZE,
            "cells": cells,
        }

    def load_dict(self, data: dict):
        """Clear canvas and restore state from a dictionary."""
        if data.get("version") != 1:
            raise ValueError(f"Unsupported project version: {data.get('version')}")
        # Remove all painted cells
        for item in list(self._cells.values()):
            self.removeItem(item)
        self._cells.clear()
        self._stroke_cells.clear()
        self._undo_stack.clear()
        for entry in data.get("cells", []):
            self._apply_cell(entry["col"], entry["row"], QColor(entry["color"]))

    # ------------------------------------------------------------------ grid

    def _draw_base_grid(self):
        light_pen = QPen(QColor(200, 230, 200))
        light_pen.setWidth(1)
        medium_pen = QPen(QColor(120, 180, 120))
        medium_pen.setWidth(2)

        rows = int(self.height() / CELL_SIZE)
        cols = int(self.width() / CELL_SIZE)

        for r in range(rows):
            for c in range(cols):
                self.addRect(QRectF(c * CELL_SIZE, r * CELL_SIZE, CELL_SIZE, CELL_SIZE), light_pen)

        for r in range(0, rows, GRID_CELLS):
            for c in range(0, cols, GRID_CELLS):
                self.addRect(QRectF(c * CELL_SIZE, r * CELL_SIZE, GRID_BLOCK, GRID_BLOCK), medium_pen)

    # ------------------------------------------------------------------ low-level cell ops

    def _apply_cell(self, col: int, row: int, color: QColor):
        key = (col, row)
        if key in self._cells:
            self.removeItem(self._cells[key])
        item = self.addRect(
            QRectF(col * CELL_SIZE, row * CELL_SIZE, CELL_SIZE, CELL_SIZE),
            QPen(Qt.NoPen),
            QBrush(color),
        )
        item.setZValue(-1)
        self._cells[key] = item

    def _remove_cell(self, col: int, row: int):
        key = (col, row)
        if key in self._cells:
            self.removeItem(self._cells[key])
            del self._cells[key]

    # ------------------------------------------------------------------ stroke helpers

    def _cell_at(self, scene_pos):
        col = int(scene_pos.x() // CELL_SIZE)
        row = int(scene_pos.y() // CELL_SIZE)
        cols = int(self.width() / CELL_SIZE)
        rows = int(self.height() / CELL_SIZE)
        if 0 <= col < cols and 0 <= row < rows:
            return col, row
        return None

    def _affected_keys(self, col: int, row: int):
        max_col = int(self.width() / CELL_SIZE)
        max_row = int(self.height() / CELL_SIZE)
        for dc in range(self._pen_w):
            for dr in range(self._pen_h):
                c, r = col + dc, row + dr
                if 0 <= c < max_col and 0 <= r < max_row:
                    yield c, r

    def _snapshot_before(self, col: int, row: int):
        """Record old state of affected cells before they are changed."""
        for c, r in self._affected_keys(col, row):
            key = (c, r)
            if key not in self._stroke_cells:
                item = self._cells.get(key)
                old = item.brush().color().name() if item else None
                self._stroke_cells[key] = [old, old]   # [before, after]; after updated later

    def _paint_cells(self, col: int, row: int):
        self._snapshot_before(col, row)
        for c, r in self._affected_keys(col, row):
            self._apply_cell(c, r, self._current_color)
            self._stroke_cells[(c, r)][1] = self._current_color.name()

    def _erase_cells(self, col: int, row: int):
        self._snapshot_before(col, row)
        for c, r in self._affected_keys(col, row):
            self._remove_cell(c, r)
            self._stroke_cells[(c, r)][1] = None

    def _commit_stroke(self, label: str):
        changes = {k: (v[0], v[1]) for k, v in self._stroke_cells.items() if v[0] != v[1]}
        self._stroke_cells = {}
        if not changes:
            return
        cmd = PaintCommand(self, changes, label)
        self._undo_stack.push(cmd)
        logging.info(
            "COMMIT %s changed=%d cells=%s",
            label,
            len(changes),
            json.dumps([[c, r, v[0], v[1]] for (c, r), v in changes.items()]),
        )

    # ------------------------------------------------------------------ events

    def mousePressEvent(self, event):
        cell = self._cell_at(event.scenePos())
        if cell:
            if event.button() == Qt.RightButton:
                self._erase_cells(*cell)
            else:
                self._paint_cells(*cell)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        cell = self._cell_at(event.scenePos())
        if cell:
            if event.buttons() & Qt.LeftButton:
                self._paint_cells(*cell)
            elif event.buttons() & Qt.RightButton:
                self._erase_cells(*cell)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() in (Qt.LeftButton, Qt.RightButton):
            label = "erase" if event.button() == Qt.RightButton else "paint"
            self._commit_stroke(label)
        super().mouseReleaseEvent(event)


class GridView(QGraphicsView):
    """QGraphicsView with Ctrl+wheel zoom and keyboard +/- zoom."""

    ZOOM_FACTOR = 1.15

    def __init__(self, scene):
        super().__init__(scene)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = self.ZOOM_FACTOR if event.angleDelta().y() > 0 else 1 / self.ZOOM_FACTOR
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def zoom_in(self):
        self.scale(self.ZOOM_FACTOR, self.ZOOM_FACTOR)

    def zoom_out(self):
        self.scale(1 / self.ZOOM_FACTOR, 1 / self.ZOOM_FACTOR)

    def zoom_reset(self):
        self.resetTransform()


PROJECT_FILTER = "Grid Planner Project (*.gridplan);;All files (*)"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._current_path: Path | None = None
        self._update_title()

        self.scene = GridScene()
        self.view = GridView(self.scene)
        self.setCentralWidget(self.view)

        self._build_menu()
        self._build_toolbar()
        self._build_shortcuts()

        self.scene.undo_stack.cleanChanged.connect(self._update_title)

    def _update_title(self, clean: bool = True):
        name = self._current_path.name if getattr(self, '_current_path', None) else "Untitled"
        dirty = "" if clean else " ●"
        self.setWindowTitle(f"Grid Planner — {name}{dirty}")

    def _build_menu(self):
        file_menu = self.menuBar().addMenu("&File")

        new_act = file_menu.addAction("&New")
        new_act.setShortcut(QKeySequence.StandardKey.New)
        new_act.triggered.connect(self._new_project)

        open_act = file_menu.addAction("&Open…")
        open_act.setShortcut(QKeySequence.StandardKey.Open)
        open_act.triggered.connect(self._open_project)

        file_menu.addSeparator()

        save_act = file_menu.addAction("&Save")
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self._save_project)

        save_as_act = file_menu.addAction("Save &As…")
        save_as_act.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_act.triggered.connect(self._save_project_as)

        file_menu.addSeparator()

        quit_act = file_menu.addAction("&Quit")
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)

    # ------------------------------------------------------------------ file ops

    def _confirm_discard(self) -> bool:
        """Return True if it is safe to discard the current project."""
        if self.scene.undo_stack.isClean():
            return True
        reply = QMessageBox.question(
            self, "Unsaved changes",
            "The project has unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Discard

    def _new_project(self):
        if not self._confirm_discard():
            return
        self.scene.load_dict({"version": 1, "cell_size": CELL_SIZE, "cells": []})
        self._current_path = None
        self.scene.undo_stack.setClean()
        self._update_title()
        logging.info("NEW project")

    def _open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open project", "", PROJECT_FILTER)
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.scene.load_dict(data)
            self._current_path = Path(path)
            self.scene.undo_stack.setClean()
            self._update_title()
            logging.info("OPEN %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def _save_project(self):
        if self._current_path is None:
            self._save_project_as()
            return
        self._write_project(self._current_path)

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save project", "", PROJECT_FILTER)
        if not path:
            return
        if not path.endswith(".gridplan"):
            path += ".gridplan"
        self._current_path = Path(path)
        self._write_project(self._current_path)

    def _write_project(self, path: Path):
        try:
            path.write_text(json.dumps(self.scene.to_dict(), indent=2), encoding="utf-8")
            self.scene.undo_stack.setClean()
            self._update_title()
            logging.info("SAVE %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    def _build_shortcuts(self):
        undo_action = self.scene.undo_stack.createUndoAction(self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.addAction(undo_action)

        redo_action = self.scene.undo_stack.createRedoAction(self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.addAction(redo_action)

    def _build_toolbar(self):
        toolbar = self.addToolBar("Colors")
        toolbar.setMovable(False)

        for hex_color, name in PALETTE:
            btn = QPushButton()
            btn.setToolTip(name)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                f"background-color: {hex_color}; border: 2px solid #555; border-radius: 4px;"
            )
            color = QColor(hex_color)
            btn.clicked.connect(lambda checked=False, c=color: self.scene.set_color(c))
            toolbar.addWidget(btn)

        toolbar.addSeparator()

        custom_btn = QPushButton("Custom…")
        custom_btn.clicked.connect(self._pick_custom_color)
        toolbar.addWidget(custom_btn)

        toolbar.addSeparator()

        # Pen size: W × H spinboxes
        size_widget = QWidget()
        size_layout = QHBoxLayout(size_widget)
        size_layout.setContentsMargins(4, 0, 4, 0)
        size_layout.setSpacing(2)
        size_layout.addWidget(QLabel("Pen:"))

        self._spin_w = QSpinBox()
        self._spin_w.setRange(1, 20)
        self._spin_w.setValue(1)
        self._spin_w.setPrefix("W ")
        self._spin_w.setToolTip("Brush width in cells")
        self._spin_w.valueChanged.connect(self._update_pen_size)
        size_layout.addWidget(self._spin_w)

        self._spin_h = QSpinBox()
        self._spin_h.setRange(1, 20)
        self._spin_h.setValue(1)
        self._spin_h.setPrefix("H ")
        self._spin_h.setToolTip("Brush height in cells")
        self._spin_h.valueChanged.connect(self._update_pen_size)
        size_layout.addWidget(self._spin_h)

        toolbar.addWidget(size_widget)

        toolbar.addSeparator()

        # Undo / Redo buttons
        self._undo_btn = QPushButton("↩ Undo")
        self._undo_btn.setToolTip("Undo  (Ctrl+Z)")
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self.scene.undo_stack.undo)
        toolbar.addWidget(self._undo_btn)

        self._redo_btn = QPushButton("↪ Redo")
        self._redo_btn.setToolTip("Redo  (Ctrl+Shift+Z)")
        self._redo_btn.setEnabled(False)
        self._redo_btn.clicked.connect(self.scene.undo_stack.redo)
        toolbar.addWidget(self._redo_btn)

        self.scene.undo_stack.canUndoChanged.connect(self._undo_btn.setEnabled)
        self.scene.undo_stack.canRedoChanged.connect(self._redo_btn.setEnabled)

        toolbar.addSeparator()

        # Zoom controls
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setToolTip("Zoom in  (Ctrl+Scroll)")
        zoom_in_btn.setFixedSize(28, 28)
        zoom_in_btn.clicked.connect(self.view.zoom_in)
        toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setToolTip("Zoom out  (Ctrl+Scroll)")
        zoom_out_btn.setFixedSize(28, 28)
        zoom_out_btn.clicked.connect(self.view.zoom_out)
        toolbar.addWidget(zoom_out_btn)

        zoom_reset_btn = QPushButton("1:1")
        zoom_reset_btn.setToolTip("Reset zoom")
        zoom_reset_btn.setFixedSize(36, 28)
        zoom_reset_btn.clicked.connect(self.view.zoom_reset)
        toolbar.addWidget(zoom_reset_btn)

        toolbar.addSeparator()

        # Save / Open shortcuts in toolbar
        save_btn = QPushButton("💾 Save")
        save_btn.setToolTip("Save project  (Ctrl+S)")
        save_btn.clicked.connect(self._save_project)
        toolbar.addWidget(save_btn)

        open_btn = QPushButton("📂 Open")
        open_btn.setToolTip("Open project  (Ctrl+O)")
        open_btn.clicked.connect(self._open_project)
        toolbar.addWidget(open_btn)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("  Left: paint  |  Right: erase  |  Ctrl+Scroll: zoom"))

    def _update_pen_size(self):
        self.scene.set_pen_size(self._spin_w.value(), self._spin_h.value())

    def _pick_custom_color(self):
        color = QColorDialog.getColor(self.scene._current_color, self)
        if color.isValid():
            self.scene.set_color(color)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
