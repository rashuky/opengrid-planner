"""MainWindow: top-level application window with toolbar, menu, and docks."""
import json
import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QColorDialog, QLabel, QSpinBox,
    QHBoxLayout, QVBoxLayout, QWidget, QFileDialog, QMessageBox, QDockWidget,
)
from PySide6.QtGui import QKeySequence, QColor, QAction
from PySide6.QtCore import Qt

from constants import MODE_PAINT, MODE_ADD_GRID, MODE_ADD_CHANNEL, MODE_SELECT, PALETTE
from scene import GridScene
from view import GridView, PROJECT_FILTER
from channel_panel import ChannelPanel
from channel_list import ChannelListPanel


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
        self._build_channel_dock()
        self._build_channel_list_dock()
        self._build_shortcuts()

        self.scene.undo_stack.cleanChanged.connect(self._update_title)

    # ------------------------------------------------------------------
    # Title / state
    # ------------------------------------------------------------------

    def _update_title(self, clean: bool = True):
        name = self._current_path.name if getattr(self, '_current_path', None) else "Untitled"
        dirty = "" if clean else " ●"
        self.setWindowTitle(f"Grid Planner — {name}{dirty}")

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Shortcuts
    # ------------------------------------------------------------------

    def _build_shortcuts(self):
        undo_action = self.scene.undo_stack.createUndoAction(self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.addAction(undo_action)

        redo_action = self.scene.undo_stack.createRedoAction(self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.addAction(redo_action)

        rotate_act = QAction("Rotate selected channel", self)
        rotate_act.setShortcut(QKeySequence("Ctrl+R"))
        rotate_act.triggered.connect(self.scene.rotate_selected)
        self.addAction(rotate_act)

        delete_act = QAction("Delete selected channel", self)
        delete_act.setShortcut(QKeySequence.StandardKey.Delete)
        delete_act.triggered.connect(self.scene.delete_selected)
        self.addAction(delete_act)

        escape_act = QAction("Cancel / deselect", self)
        escape_act.setShortcut(QKeySequence("Escape"))
        escape_act.triggered.connect(self.scene.cancel_edit)
        self.addAction(escape_act)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------

    def _build_toolbar(self):
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        # Mode toggle
        self._paint_btn = QPushButton("🖌 Paint")
        self._paint_btn.setCheckable(True)
        self._paint_btn.setChecked(True)
        self._paint_btn.setToolTip("Paint mode: left=paint, right=erase")
        self._paint_btn.clicked.connect(lambda: self._set_mode(MODE_PAINT))
        toolbar.addWidget(self._paint_btn)

        self._add_grid_btn = QPushButton("⊞ Add Grid")
        self._add_grid_btn.setCheckable(True)
        self._add_grid_btn.setToolTip("Grid mode: click to place an openGrid tile array")
        self._add_grid_btn.clicked.connect(lambda: self._set_mode(MODE_ADD_GRID))
        toolbar.addWidget(self._add_grid_btn)

        self._add_channel_btn = QPushButton("⌯ Add Channel")
        self._add_channel_btn.setCheckable(True)
        self._add_channel_btn.setToolTip("Channel mode: click to place a cable channel")
        self._add_channel_btn.clicked.connect(lambda: self._set_mode(MODE_ADD_CHANNEL))
        toolbar.addWidget(self._add_channel_btn)

        self._select_btn = QPushButton("↖ Select")
        self._select_btn.setCheckable(True)
        self._select_btn.setToolTip(
            "Select mode: click channel to select · click again to move\n"
            "Ctrl+R: rotate · Del: delete · Esc: cancel / deselect"
        )
        self._select_btn.clicked.connect(lambda: self._set_mode(MODE_SELECT))
        toolbar.addWidget(self._select_btn)

        toolbar.addSeparator()

        # Grid size
        gs_widget = QWidget()
        gs_layout = QHBoxLayout(gs_widget)
        gs_layout.setContentsMargins(4, 0, 4, 0)
        gs_layout.setSpacing(2)
        gs_layout.addWidget(QLabel("Grid:"))

        self._spin_gw = QSpinBox()
        self._spin_gw.setRange(1, 30)
        self._spin_gw.setValue(4)
        self._spin_gw.setPrefix("N ")
        self._spin_gw.setToolTip("Grid width in openGrid tiles (28 mm each)")
        self._spin_gw.valueChanged.connect(self._update_grid_size)
        gs_layout.addWidget(self._spin_gw)

        self._spin_gh = QSpinBox()
        self._spin_gh.setRange(1, 30)
        self._spin_gh.setValue(4)
        self._spin_gh.setPrefix("M ")
        self._spin_gh.setToolTip("Grid height in openGrid tiles (28 mm each)")
        self._spin_gh.valueChanged.connect(self._update_grid_size)
        gs_layout.addWidget(self._spin_gh)

        toolbar.addWidget(gs_widget)

        toolbar.addSeparator()

        # Colour palette
        for hex_color, name in PALETTE:
            btn = QPushButton()
            btn.setToolTip(name)
            btn.setFixedSize(28, 28)
            btn.setStyleSheet(
                f"background-color: {hex_color}; border: 2px solid #555; border-radius: 4px;"
            )
            c = QColor(hex_color)
            btn.clicked.connect(lambda checked=False, col=c: self.scene.set_color(col))
            toolbar.addWidget(btn)

        custom_btn = QPushButton("Custom…")
        custom_btn.clicked.connect(self._pick_custom_color)
        toolbar.addWidget(custom_btn)

        toolbar.addSeparator()

        # Pen size
        pen_widget = QWidget()
        pen_layout = QHBoxLayout(pen_widget)
        pen_layout.setContentsMargins(4, 0, 4, 0)
        pen_layout.setSpacing(2)
        pen_layout.addWidget(QLabel("Pen:"))

        self._spin_w = QSpinBox()
        self._spin_w.setRange(1, 20)
        self._spin_w.setValue(1)
        self._spin_w.setPrefix("W ")
        self._spin_w.setToolTip("Brush width in small cells")
        self._spin_w.valueChanged.connect(self._update_pen_size)
        pen_layout.addWidget(self._spin_w)

        self._spin_h = QSpinBox()
        self._spin_h.setRange(1, 20)
        self._spin_h.setValue(1)
        self._spin_h.setPrefix("H ")
        self._spin_h.setToolTip("Brush height in small cells")
        self._spin_h.valueChanged.connect(self._update_pen_size)
        pen_layout.addWidget(self._spin_h)

        toolbar.addWidget(pen_widget)

        toolbar.addSeparator()

        # Undo / Redo
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

        # Zoom
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

        # Save / Open
        save_btn = QPushButton("💾 Save")
        save_btn.setToolTip("Save project  (Ctrl+S)")
        save_btn.clicked.connect(self._save_project)
        toolbar.addWidget(save_btn)

        open_btn = QPushButton("📂 Open")
        open_btn.setToolTip("Open project  (Ctrl+O)")
        open_btn.clicked.connect(self._open_project)
        toolbar.addWidget(open_btn)

    # ------------------------------------------------------------------
    # Toolbar callbacks
    # ------------------------------------------------------------------

    def _set_mode(self, mode: str):
        self.scene.set_mode(mode)
        self._paint_btn.setChecked(mode == MODE_PAINT)
        self._add_grid_btn.setChecked(mode == MODE_ADD_GRID)
        self._add_channel_btn.setChecked(mode == MODE_ADD_CHANNEL)
        self._select_btn.setChecked(mode == MODE_SELECT)
        # Channel settings dock: visible when adding OR when something is selected
        self._channel_dock.setVisible(
            mode == MODE_ADD_CHANNEL or
            (mode == MODE_SELECT and self.scene.selected_channel is not None)
        )

    def _update_grid_size(self):
        self.scene.set_grid_size(self._spin_gw.value(), self._spin_gh.value())

    def _update_pen_size(self):
        self.scene.set_pen_size(self._spin_w.value(), self._spin_h.value())

    # ------------------------------------------------------------------
    # Channel dock
    # ------------------------------------------------------------------

    def _build_channel_dock(self):
        self._channel_panel = ChannelPanel()
        self._channel_dock = QDockWidget("Channel Settings", self)
        self._channel_dock.setWidget(self._channel_panel)
        self._channel_dock.setAllowedAreas(Qt.RightDockWidgetArea)
        self._channel_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.RightDockWidgetArea, self._channel_dock)
        self._channel_dock.setVisible(False)
        self._channel_panel.params_changed.connect(self._update_channel_params)
        self.scene.set_channel_params(self._channel_panel.params)

    def _update_channel_params(self, params: dict):
        if self.scene.mode == MODE_SELECT and self.scene.selected_channel is not None:
            self.scene.update_selected_channel_params(params)
        else:
            self.scene.set_channel_params(params)

    # ------------------------------------------------------------------
    # Channel list / object tree dock
    # ------------------------------------------------------------------

    def _build_channel_list_dock(self):
        self._channel_list_panel = ChannelListPanel()
        dock = QDockWidget("Object Tree", self)
        dock.setWidget(self._channel_list_panel)
        dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable |
            QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.tabifyDockWidget(self._channel_dock, dock)

        # Scene → list
        self.scene.channel_placed.connect(self._channel_list_panel.add_channel)
        self.scene.channel_erased.connect(self._channel_list_panel.remove_channel)
        self.scene.channel_selection_changed.connect(self._on_channel_selection_changed)

        # List → scene
        self._channel_list_panel.channel_selected.connect(self._on_list_channel_selected)

    def _on_list_channel_selected(self, channel_id: int):
        if channel_id == -1:
            self.scene.deselect()
        else:
            self.scene.select_channel(channel_id)

    def _on_channel_selection_changed(self, channel):
        is_selected = channel is not None
        # Update channel settings dock visibility in select mode
        if self.scene.mode == MODE_SELECT:
            self._channel_dock.setVisible(is_selected)
        # Populate channel panel controls with selected channel's params
        if is_selected:
            self._channel_panel.set_params(channel.to_dict())
        # Sync highlight in list (list may already be in sync, but guard)
        if is_selected:
            self._channel_list_panel.select_channel(id(channel))
        else:
            self._channel_list_panel.deselect()

    # ------------------------------------------------------------------
    # Colour picker
    # ------------------------------------------------------------------

    def _pick_custom_color(self):
        color = QColorDialog.getColor(self.scene._current_color, self)
        if color.isValid():
            self.scene.set_color(color)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _confirm_discard(self) -> bool:
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
        self.scene.load_dict({"version": 2, "cells": [], "regions": []})
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
