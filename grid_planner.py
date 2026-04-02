import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QGraphicsView, QGraphicsScene,
    QPushButton, QColorDialog, QLabel, QSpinBox, QHBoxLayout, QVBoxLayout,
    QWidget, QFileDialog, QMessageBox, QDockWidget, QButtonGroup,
    QGraphicsPathItem,
)
from PySide6.QtGui import QPen, QColor, QBrush, QUndoStack, QUndoCommand, QKeySequence, QPainterPath
from PySide6.QtCore import Qt, QRectF, Signal

LOG_PATH = Path(__file__).parent / "actions.log"
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# --- Layout constants ---
SMALL_CELL_PX = 20        # pixels per small (paintable) cell
TILE_CELLS    = 10        # small cells per openGrid unit (28 mm real-world)
TILE_PX       = SMALL_CELL_PX * TILE_CELLS   # 200 px / openGrid tile
CANVAS_TILES  = 80        # canvas size in openGrid tiles (~2240 mm per side)
CANVAS_PX     = CANVAS_TILES * TILE_PX

MODE_PAINT        = "paint"
MODE_ADD_GRID     = "add_grid"
MODE_ADD_CHANNEL  = "add_channel"

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


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class GridRegion:
    """One placed openGrid tile array: n_w × n_h tiles at (tile_col, tile_row).
    Each openGrid tile = TILE_CELLS × TILE_CELLS small paintable cells = 28 mm real."""

    def __init__(self, tile_col: int, tile_row: int, n_w: int, n_h: int):
        self.tile_col = tile_col
        self.tile_row = tile_row
        self.n_w = n_w
        self.n_h = n_h

    def contains_small_cell(self, col: int, row: int) -> bool:
        sc = self.tile_col * TILE_CELLS
        sr = self.tile_row * TILE_CELLS
        return (sc <= col < sc + self.n_w * TILE_CELLS and
                sr <= row < sr + self.n_h * TILE_CELLS)

    def overlaps(self, other: "GridRegion") -> bool:
        """True if this region's tile rectangle intersects other's."""
        return not (
            self.tile_col + self.n_w <= other.tile_col or
            other.tile_col + other.n_w <= self.tile_col or
            self.tile_row + self.n_h <= other.tile_row or
            other.tile_row + other.n_h <= self.tile_row
        )

    def to_dict(self) -> dict:
        return {"tile_col": self.tile_col, "tile_row": self.tile_row,
                "n_w": self.n_w, "n_h": self.n_h}

    @classmethod
    def from_dict(cls, d: dict) -> "GridRegion":
        return cls(d["tile_col"], d["tile_row"], d["n_w"], d["n_h"])


class Channel:
    """An I-shaped cable channel placed on small-cell grid coordinates."""

    def __init__(self, col: int, row: int, length: int, width: int, orientation: str):
        self.col = col              # top-left small cell column
        self.row = row              # top-left small cell row
        self.length = length        # cells along the channel's main axis
        self.width = width          # cells across the channel
        self.orientation = orientation  # 'H' (horizontal) or 'V' (vertical)

    def occupied_cells(self):
        """Yield all (col, row) small cells this channel covers."""
        len_cells = self.length * TILE_CELLS
        wid_cells = self.width * TILE_CELLS
        if self.orientation == 'H':
            for dc in range(len_cells):
                for dr in range(wid_cells):
                    yield self.col + dc, self.row + dr
        else:
            for dc in range(wid_cells):
                for dr in range(len_cells):
                    yield self.col + dc, self.row + dr

    def to_dict(self) -> dict:
        return {
            "type": "I",
            "col": self.col, "row": self.row,
            "length": self.length, "width": self.width,
            "orientation": self.orientation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Channel":
        if d.get("type") == "L":
            return LChannel.from_dict(d)
        return cls(d["col"], d["row"], d["length"], d["width"], d["orientation"])


class LChannel:
    """An L-shaped cable channel placed on tile-snapped coordinates.

    The L consists of:
      - a horizontal arm of len_x tiles long × width tiles wide
      - a vertical arm of len_y tiles long × width tiles wide
    They share a corner tile depending on rotation:
      rotation 0: corner at top-left  → H arm goes right, V arm goes down
      rotation 1: corner at top-right → H arm goes left,  V arm goes down
      rotation 2: corner at bottom-left  → H arm goes right, V arm goes up
      rotation 3: corner at bottom-right → H arm goes left,  V arm goes up
    col, row are always the top-left of the bounding box.
    """

    def __init__(self, col: int, row: int,
                 len_x: int, len_y: int, width: int, rotation: int):
        self.col = col
        self.row = row
        self.len_x = len_x      # horizontal arm length in tiles
        self.len_y = len_y      # vertical arm length in tiles
        self.width = width      # arm width in tiles (same for both arms)
        self.rotation = rotation  # 0/1/2/3

    def _arm_rects_tiles(self):
        """Return (h_rect, v_rect) as (tc, tr, w, h) in tile coordinates."""
        lx, ly, w = self.len_x, self.len_y, self.width
        tc, tr = self.col // TILE_CELLS, self.row // TILE_CELLS
        r = self.rotation
        if r == 0:   # corner TL: H goes right from (tc,tr), V goes down from (tc,tr)
            h_rect = (tc, tr, lx, w)
            v_rect = (tc, tr, w, ly)
        elif r == 1: # corner TR: H goes left to (tc+lx-1,tr), V goes down from (tc+lx-w,tr)
            h_rect = (tc, tr, lx, w)
            v_rect = (tc + lx - w, tr, w, ly)
        elif r == 2: # corner BL: H goes right from (tc,tr+ly-w), V goes up to (tc,tr+ly-1)
            h_rect = (tc, tr + ly - w, lx, w)
            v_rect = (tc, tr, w, ly)
        else:        # corner BR: H goes left, V goes up
            h_rect = (tc, tr + ly - w, lx, w)
            v_rect = (tc + lx - w, tr, w, ly)
        return h_rect, v_rect

    def occupied_cells(self):
        """Yield all (col, row) small cells this channel covers."""
        seen = set()
        for (tc, tr, tw, th) in self._arm_rects_tiles():
            for dc in range(tw * TILE_CELLS):
                for dr in range(th * TILE_CELLS):
                    c = tc * TILE_CELLS + dc
                    r = tr * TILE_CELLS + dr
                    if (c, r) not in seen:
                        seen.add((c, r))
                        yield c, r

    def bounding_box_px(self):
        """Return (x, y, w, h) pixel bounding box."""
        lx, ly = self.len_x, self.len_y
        return (self.col * SMALL_CELL_PX,
                self.row * SMALL_CELL_PX,
                lx * TILE_PX,
                ly * TILE_PX)

    def to_dict(self) -> dict:
        return {
            "type": "L",
            "col": self.col, "row": self.row,
            "len_x": self.len_x, "len_y": self.len_y,
            "width": self.width, "rotation": self.rotation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LChannel":
        return cls(d["col"], d["row"], d["len_x"], d["len_y"],
                   d["width"], d["rotation"])



class PlaceGridCommand(QUndoCommand):
    """Undo/redo placing a GridRegion on the canvas."""

    def __init__(self, scene, region: GridRegion):
        super().__init__(f"Place {region.n_w}\u00d7{region.n_h} grid")
        self._scene = scene
        self._region = region

    def redo(self):
        self._scene._add_region(self._region)
        logging.info("REDO place-grid %s", self._region.to_dict())

    def undo(self):
        self._scene._remove_region(self._region)
        logging.info("UNDO place-grid %s", self._region.to_dict())


class PlaceChannelCommand(QUndoCommand):
    """Undo/redo placing a Channel on the canvas."""

    def __init__(self, scene, channel: Channel):
        super().__init__("Place I channel")
        self._scene = scene
        self._channel = channel

    def redo(self):
        self._scene._add_channel(self._channel)
        logging.info("REDO place-channel %s", self._channel.to_dict())

    def undo(self):
        self._scene._remove_channel(self._channel)
        logging.info("UNDO place-channel %s", self._channel.to_dict())


class PaintCommand(QUndoCommand):
    """Single undoable paint/erase stroke."""

    def __init__(self, scene, changes: dict, label: str):
        super().__init__(label)
        self._scene = scene
        self._changes = changes   # {(col, row): (old_hex|None, new_hex|None)}
        self._first_redo = True

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            return
        for (col, row), (_, new) in self._changes.items():
            if new is None:
                self._scene._remove_cell(col, row)
            else:
                self._scene._apply_cell(col, row, QColor(new))
        logging.info("REDO %s cells=%s", self.text(), list(self._changes.keys()))

    def undo(self):
        for (col, row), (old, _) in self._changes.items():
            if old is None:
                self._scene._remove_cell(col, row)
            else:
                self._scene._apply_cell(col, row, QColor(old))
        logging.info("UNDO %s cells=%s", self.text(), list(self._changes.keys()))


class GridScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, CANVAS_PX, CANVAS_PX)
        self._cells: dict = {}            # (col, row) -> QGraphicsRectItem
        self._regions: list = []          # list[GridRegion]
        self._region_items: dict = {}     # id(region) -> [QGraphicsItem, ...]
        self._current_color = QColor("#3498db")
        self._pen_w = 1
        self._pen_h = 1
        self._mode = MODE_PAINT
        self._grid_n_w = 4
        self._grid_n_h = 4
        self._undo_stack = QUndoStack(self)
        self._stroke_cells: dict = {}
        self._ghost = None
        # channel tracking
        self._channels: list = []
        self._channel_items: dict = {}  # id(channel) -> [QGraphicsItem, ...]
        self._channel_cells: set = set()  # (col, row) cells occupied by channels
        self._ch_type = 'I'
        self._ch_length = 3
        self._ch_width = 1
        self._ch_orientation = 'H'
        self._ch_len_x = 3
        self._ch_len_y = 3
        self._ch_rotation = 0
        self._ch_ghost = None
        self._last_scene_pos = None

    # ------------------------------------------------------------------ public

    @property
    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    def set_color(self, color: QColor):
        self._current_color = color

    def set_pen_size(self, w: int, h: int):
        self._pen_w = max(1, w)
        self._pen_h = max(1, h)

    def set_mode(self, mode: str):
        self._mode = mode
        if mode != MODE_ADD_GRID and self._ghost is not None:
            self.removeItem(self._ghost)
            self._ghost = None
        if mode != MODE_ADD_CHANNEL and self._ch_ghost is not None:
            self.removeItem(self._ch_ghost)
            self._ch_ghost = None

    def set_grid_size(self, n_w: int, n_h: int):
        self._grid_n_w = max(1, n_w)
        self._grid_n_h = max(1, n_h)
        if self._ghost is not None:
            r = self._ghost.rect()
            self._ghost.setRect(QRectF(r.x(), r.y(),
                                       self._grid_n_w * TILE_PX,
                                       self._grid_n_h * TILE_PX))

    def set_channel_params(self, params: dict):
        self._ch_type = params.get('type', 'I')
        self._ch_length = max(1, params.get('length', 3))
        self._ch_width = max(1, params.get('width', 1))
        self._ch_orientation = params.get('orientation', 'H')
        self._ch_len_x = max(1, params.get('len_x', 3))
        self._ch_len_y = max(1, params.get('len_y', 3))
        self._ch_rotation = params.get('rotation', 0)
        if self._mode == MODE_ADD_CHANNEL:
            self._update_ch_ghost(self._last_scene_pos)

    # ------------------------------------------------------------------ region management

    def _draw_region(self, region: GridRegion) -> list:
        items = []
        x0 = region.tile_col * TILE_PX
        y0 = region.tile_row * TILE_PX
        w  = region.n_w * TILE_PX
        h  = region.n_h * TILE_PX

        bg = self.addRect(QRectF(x0, y0, w, h),
                          QPen(Qt.NoPen), QBrush(QColor(245, 255, 245)))
        bg.setZValue(-3)
        items.append(bg)

        light_pen = QPen(QColor(200, 230, 200))
        light_pen.setWidth(1)
        for i in range(region.n_w * TILE_CELLS + 1):
            x = x0 + i * SMALL_CELL_PX
            items.append(self.addLine(x, y0, x, y0 + h, light_pen))
        for i in range(region.n_h * TILE_CELLS + 1):
            y = y0 + i * SMALL_CELL_PX
            items.append(self.addLine(x0, y, x0 + w, y, light_pen))

        medium_pen = QPen(QColor(120, 180, 120))
        medium_pen.setWidth(2)
        for i in range(region.n_w + 1):
            x = x0 + i * TILE_PX
            items.append(self.addLine(x, y0, x, y0 + h, medium_pen))
        for i in range(region.n_h + 1):
            y = y0 + i * TILE_PX
            items.append(self.addLine(x0, y, x0 + w, y, medium_pen))

        border_pen = QPen(QColor(0, 100, 0))
        border_pen.setWidth(3)
        border = self.addRect(QRectF(x0, y0, w, h), border_pen, QBrush(Qt.NoBrush))
        border.setZValue(1)
        items.append(border)
        return items

    def _add_region(self, region: GridRegion):
        items = self._draw_region(region)
        self._regions.append(region)
        self._region_items[id(region)] = items

    def _remove_region(self, region: GridRegion):
        for item in self._region_items.pop(id(region), []):
            self.removeItem(item)
        if region in self._regions:
            self._regions.remove(region)
        to_del = [k for k in self._cells if region.contains_small_cell(*k)]
        for k in to_del:
            self.removeItem(self._cells.pop(k))

    def _cell_in_any_region(self, col: int, row: int) -> bool:
        return any(r.contains_small_cell(col, row) for r in self._regions)

    # ------------------------------------------------------------------ channel management

    @staticmethod
    def _l_channel_path(ch: "LChannel") -> QPainterPath:
        """Build the filled L-shaped QPainterPath for an LChannel."""
        hr, vr = ch._arm_rects_tiles()
        path = QPainterPath()
        for (tc, tr, tw, th) in (hr, vr):
            path.addRect(QRectF(tc * TILE_PX, tr * TILE_PX, tw * TILE_PX, th * TILE_PX))
        return path.simplified()

    @staticmethod
    def _l_channel_outer_wall_path(ch: "LChannel") -> QPainterPath:
        """Open QPainterPath for the two long outer walls joined by a rounded arch at the corner."""
        hr, vr = ch._arm_rects_tiles()
        htc, htr, htw, hth = hr
        vtc, vtr, vtw, vth = vr
        hx1 = htc * TILE_PX;  hy1 = htr * TILE_PX
        hx2 = (htc + htw) * TILE_PX;  hy2 = (htr + hth) * TILE_PX
        vx1 = vtc * TILE_PX;  vy1 = vtr * TILE_PX
        vx2 = (vtc + vtw) * TILE_PX;  vy2 = (vtr + vth) * TILE_PX
        R = ch.width * TILE_PX          # outer corner radius = full arm width
        path = QPainterPath()
        r = ch.rotation
        if r == 0:   # corner TL: H-top → arch → V-left
            path.moveTo(hx2, hy1)
            path.lineTo(hx1 + R, hy1)
            path.arcTo(hx1, hy1, 2 * R, 2 * R, 90, 90)
            path.lineTo(vx1, vy2)
        elif r == 1: # corner TR: H-top → arch → V+H-right
            path.moveTo(hx1, hy1)
            path.lineTo(hx2 - R, hy1)
            path.arcTo(hx2 - 2 * R, hy1, 2 * R, 2 * R, 90, -90)
            path.lineTo(hx2, vy2)
        elif r == 2: # corner BL: V-left → arch → H-bottom
            path.moveTo(vx1, vy1)
            path.lineTo(hx1, hy2 - R)
            path.arcTo(hx1, hy2 - 2 * R, 2 * R, 2 * R, 180, 90)
            path.lineTo(hx2, hy2)
        else:        # corner BR: H-bottom → arch → H+V-right
            path.moveTo(hx1, hy2)
            path.lineTo(hx2 - R, hy2)
            path.arcTo(hx2 - 2 * R, hy2 - 2 * R, 2 * R, 2 * R, 270, 90)
            path.lineTo(hx2, vy1)
        return path

    @staticmethod
    def _l_channel_inner_step_path(ch: "LChannel") -> QPainterPath:
        """QPainterPath for the inner step (two right-angle segments at the concave corner)."""
        hr, vr = ch._arm_rects_tiles()
        htc, htr, htw, hth = hr
        vtc, vtr, vtw, vth = vr
        hx1 = htc * TILE_PX;  hy1 = htr * TILE_PX
        hx2 = (htc + htw) * TILE_PX;  hy2 = (htr + hth) * TILE_PX
        vx1 = vtc * TILE_PX;  vy1 = vtr * TILE_PX
        vx2 = (vtc + vtw) * TILE_PX;  vy2 = (vtr + vth) * TILE_PX
        path = QPainterPath()
        r = ch.rotation
        if r == 0:
            path.moveTo(hx2, hy2); path.lineTo(vx2, hy2); path.lineTo(vx2, vy2)
        elif r == 1:
            path.moveTo(vx1, vy2); path.lineTo(vx1, hy2); path.lineTo(hx1, hy2)
        elif r == 2:
            path.moveTo(hx2, hy1); path.lineTo(vx2, hy1); path.lineTo(vx2, vy1)
        else:
            path.moveTo(vx1, vy1); path.lineTo(vx1, hy1); path.lineTo(hx1, hy1)
        return path

    def _draw_channel(self, channel) -> list:
        items = []
        wall_pen = QPen(QColor(44, 80, 120))
        wall_pen.setWidth(3)
        wall_pen.setCapStyle(Qt.RoundCap)
        wall_pen.setJoinStyle(Qt.RoundJoin)
        fill_brush = QBrush(QColor(100, 140, 180, 80))

        if isinstance(channel, LChannel):
            body = self.addPath(self._l_channel_path(channel), QPen(Qt.NoPen), fill_brush)
            items.append(body)
            outer = self.addPath(self._l_channel_outer_wall_path(channel),
                                 wall_pen, QBrush(Qt.NoBrush))
            items.append(outer)
            inner = self.addPath(self._l_channel_inner_step_path(channel),
                                 wall_pen, QBrush(Qt.NoBrush))
            items.append(inner)
        else:
            if channel.orientation == 'H':
                x, y = channel.col * SMALL_CELL_PX, channel.row * SMALL_CELL_PX
                w, h = channel.length * TILE_PX, channel.width * TILE_PX
            else:
                x, y = channel.col * SMALL_CELL_PX, channel.row * SMALL_CELL_PX
                w, h = channel.width * TILE_PX, channel.length * TILE_PX
            body = self.addRect(QRectF(x, y, w, h), QPen(Qt.NoPen), fill_brush)
            items.append(body)
            if channel.orientation == 'H':
                items.append(self.addLine(x, y,     x + w, y,     wall_pen))
                items.append(self.addLine(x, y + h, x + w, y + h, wall_pen))
            else:
                items.append(self.addLine(x,     y, x,     y + h, wall_pen))
                items.append(self.addLine(x + w, y, x + w, y + h, wall_pen))

        for item in items:
            item.setZValue(2)
        return items

    def _add_channel(self, channel: Channel):
        items = self._draw_channel(channel)
        self._channels.append(channel)
        self._channel_items[id(channel)] = items
        for cell in channel.occupied_cells():
            self._channel_cells.add(cell)

    def _remove_channel(self, channel: Channel):
        for item in self._channel_items.pop(id(channel), []):
            self.removeItem(item)
        if channel in self._channels:
            self._channels.remove(channel)
        for cell in channel.occupied_cells():
            self._channel_cells.discard(cell)

    def _channel_candidate_cells(self, col: int, row: int):
        """Yield cells a channel would occupy if its top-left is at (col, row)."""
        if self._ch_type == 'L':
            tmp = LChannel(col, row, self._ch_len_x, self._ch_len_y,
                           self._ch_width, self._ch_rotation)
            yield from tmp.occupied_cells()
            return
        len_cells = self._ch_length * TILE_CELLS
        wid_cells = self._ch_width * TILE_CELLS
        if self._ch_orientation == 'H':
            for dc in range(len_cells):
                for dr in range(wid_cells):
                    yield col + dc, row + dr
        else:
            for dc in range(wid_cells):
                for dr in range(len_cells):
                    yield col + dc, row + dr

    def _channel_placement_valid(self, col: int, row: int) -> bool:
        limit = CANVAS_TILES * TILE_CELLS
        for c, r in self._channel_candidate_cells(col, row):
            if not (0 <= c < limit and 0 <= r < limit):
                return False
            if not self._cell_in_any_region(c, r):
                return False
            if (c, r) in self._channel_cells:
                return False
        return True

    def _ch_ghost_rect(self, col: int, row: int) -> QRectF:
        """Bounding box for the ghost regardless of channel type."""
        x, y = col * SMALL_CELL_PX, row * SMALL_CELL_PX
        if self._ch_type == 'L':
            return QRectF(x, y, self._ch_len_x * TILE_PX, self._ch_len_y * TILE_PX)
        if self._ch_orientation == 'H':
            return QRectF(x, y, self._ch_length * TILE_PX, self._ch_width * TILE_PX)
        return QRectF(x, y, self._ch_width * TILE_PX, self._ch_length * TILE_PX)

    def _tile_cell_at(self, scene_pos):
        """Return channel origin (col, row) in small-cell coords snapped to tile grid,
        or None if out of canvas bounds."""
        if scene_pos is None:
            return None
        tc = int(scene_pos.x() // TILE_PX)
        tr = int(scene_pos.y() // TILE_PX)
        if 0 <= tc < CANVAS_TILES and 0 <= tr < CANVAS_TILES:
            return tc * TILE_CELLS, tr * TILE_CELLS
        return None

    def _update_ch_ghost(self, scene_pos):
        cell = self._tile_cell_at(scene_pos)
        if cell is None:
            if self._ch_ghost is not None:
                self._ch_ghost.setVisible(False)
            return
        col, row = cell
        valid = self._channel_placement_valid(col, row)
        pen_color  = QColor(0, 150, 0, 200) if valid else QColor(200, 0, 0, 220)
        fill_color = QColor(0, 200, 0, 40)  if valid else QColor(255, 0, 0, 50)
        ghost_pen = QPen(pen_color)
        ghost_pen.setWidth(1)
        ghost_pen.setStyle(Qt.DashLine)
        if self._ch_type == 'L':
            tmp = LChannel(col, row, self._ch_len_x, self._ch_len_y,
                           self._ch_width, self._ch_rotation)
            path = self._l_channel_path(tmp)
            if self._ch_ghost is None or not isinstance(self._ch_ghost, QGraphicsPathItem):
                if self._ch_ghost is not None:
                    self.removeItem(self._ch_ghost)
                self._ch_ghost = self.addPath(path, ghost_pen, QBrush(fill_color))
                self._ch_ghost.setZValue(10)
            else:
                self._ch_ghost.setPath(path)
                self._ch_ghost.setPen(ghost_pen)
                self._ch_ghost.setBrush(QBrush(fill_color))
                self._ch_ghost.setVisible(True)
        else:
            rect = self._ch_ghost_rect(col, row)
            if self._ch_ghost is None or isinstance(self._ch_ghost, QGraphicsPathItem):
                if self._ch_ghost is not None:
                    self.removeItem(self._ch_ghost)
                self._ch_ghost = self.addRect(rect, ghost_pen, QBrush(fill_color))
                self._ch_ghost.setZValue(10)
            else:
                self._ch_ghost.setPen(ghost_pen)
                self._ch_ghost.setBrush(QBrush(fill_color))
                self._ch_ghost.setRect(rect)
                self._ch_ghost.setVisible(True)

    # ------------------------------------------------------------------ ghost preview

    def _tile_at_pos(self, scene_pos):
        tc = int(scene_pos.x() // TILE_PX)
        tr = int(scene_pos.y() // TILE_PX)
        max_tc = CANVAS_TILES - self._grid_n_w
        max_tr = CANVAS_TILES - self._grid_n_h
        if 0 <= tc <= max_tc and 0 <= tr <= max_tr:
            return tc, tr
        return None

    def _region_collides(self, tc: int, tr: int) -> bool:
        """Return True if a candidate region at (tc, tr) would overlap any existing region."""
        candidate = GridRegion(tc, tr, self._grid_n_w, self._grid_n_h)
        return any(candidate.overlaps(r) for r in self._regions)

    def _update_ghost(self, scene_pos):
        tile = self._tile_at_pos(scene_pos) if scene_pos else None
        if tile is None:
            if self._ghost is not None:
                self._ghost.setVisible(False)
            return
        tc, tr = tile
        rect = QRectF(tc * TILE_PX, tr * TILE_PX,
                      self._grid_n_w * TILE_PX, self._grid_n_h * TILE_PX)
        collides = self._region_collides(tc, tr)
        pen_color   = QColor(200, 0, 0, 220) if collides else QColor(0, 150, 0, 200)
        fill_color  = QColor(255, 0, 0, 50)  if collides else QColor(0, 200, 0, 40)
        if self._ghost is None:
            ghost_pen = QPen(pen_color)
            ghost_pen.setWidth(2)
            ghost_pen.setStyle(Qt.DashLine)
            self._ghost = self.addRect(rect, ghost_pen, QBrush(fill_color))
            self._ghost.setZValue(10)
        else:
            ghost_pen = QPen(pen_color)
            ghost_pen.setWidth(2)
            ghost_pen.setStyle(Qt.DashLine)
            self._ghost.setPen(ghost_pen)
            self._ghost.setBrush(QBrush(fill_color))
            self._ghost.setRect(rect)
            self._ghost.setVisible(True)

    # ------------------------------------------------------------------ low-level cell ops

    def _cell_at(self, scene_pos):
        col = int(scene_pos.x() // SMALL_CELL_PX)
        row = int(scene_pos.y() // SMALL_CELL_PX)
        if 0 <= col < CANVAS_TILES * TILE_CELLS and 0 <= row < CANVAS_TILES * TILE_CELLS:
            return col, row
        return None

    def _apply_cell(self, col: int, row: int, color: QColor):
        key = (col, row)
        if key in self._cells:
            self.removeItem(self._cells[key])
        item = self.addRect(
            QRectF(col * SMALL_CELL_PX, row * SMALL_CELL_PX, SMALL_CELL_PX, SMALL_CELL_PX),
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

    def _affected_keys(self, col: int, row: int):
        limit = CANVAS_TILES * TILE_CELLS
        for dc in range(self._pen_w):
            for dr in range(self._pen_h):
                c, r = col + dc, row + dr
                if 0 <= c < limit and 0 <= r < limit:
                    yield c, r

    def _snapshot_before(self, col: int, row: int):
        for c, r in self._affected_keys(col, row):
            key = (c, r)
            if key not in self._stroke_cells:
                item = self._cells.get(key)
                old = item.brush().color().name() if item else None
                self._stroke_cells[key] = [old, old]

    def _paint_cells(self, col: int, row: int):
        self._snapshot_before(col, row)
        for c, r in self._affected_keys(col, row):
            if not self._cell_in_any_region(c, r):
                continue
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
        self._undo_stack.push(PaintCommand(self, changes, label))
        logging.info("COMMIT %s changed=%d", label, len(changes))

    # ------------------------------------------------------------------ serialisation

    def to_dict(self) -> dict:
        return {
            "version": 3,
            "cells": [
                {"col": col, "row": row, "color": item.brush().color().name()}
                for (col, row), item in self._cells.items()
            ],
            "regions": [r.to_dict() for r in self._regions],
            "channels": [c.to_dict() for c in self._channels],
        }

    def load_dict(self, data: dict):
        if data.get("version") not in (1, 2, 3):
            raise ValueError(f"Unsupported project version: {data.get('version')}")
        for item in list(self._cells.values()):
            self.removeItem(item)
        self._cells.clear()
        self._stroke_cells.clear()
        for region in list(self._regions):
            self._remove_region(region)
        for channel in list(self._channels):
            self._remove_channel(channel)
        self._undo_stack.clear()
        for rd in data.get("regions", []):
            self._add_region(GridRegion.from_dict(rd))
        for entry in data.get("cells", []):
            self._apply_cell(entry["col"], entry["row"], QColor(entry["color"]))
        for cd in data.get("channels", []):
            self._add_channel(Channel.from_dict(cd))

    # ------------------------------------------------------------------ events

    def mousePressEvent(self, event):
        if self._mode == MODE_ADD_GRID:
            if event.button() == Qt.LeftButton:
                tile = self._tile_at_pos(event.scenePos())
                if tile and not self._region_collides(*tile):
                    region = GridRegion(tile[0], tile[1], self._grid_n_w, self._grid_n_h)
                    self._undo_stack.push(PlaceGridCommand(self, region))
                    logging.info("PLACE grid %s", region.to_dict())
        elif self._mode == MODE_ADD_CHANNEL:
            if event.button() == Qt.LeftButton:
                cell = self._tile_cell_at(event.scenePos())
                if cell and self._channel_placement_valid(*cell):
                    if self._ch_type == 'L':
                        channel = LChannel(cell[0], cell[1],
                                           self._ch_len_x, self._ch_len_y,
                                           self._ch_width, self._ch_rotation)
                    else:
                        channel = Channel(cell[0], cell[1],
                                          self._ch_length, self._ch_width, self._ch_orientation)
                    self._undo_stack.push(PlaceChannelCommand(self, channel))
                    logging.info("PLACE channel %s", channel.to_dict())
        else:
            cell = self._cell_at(event.scenePos())
            if cell and self._cell_in_any_region(*cell):
                if event.button() == Qt.RightButton:
                    self._erase_cells(*cell)
                else:
                    self._paint_cells(*cell)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self._last_scene_pos = event.scenePos()
        if self._mode == MODE_ADD_GRID:
            self._update_ghost(event.scenePos())
        elif self._mode == MODE_ADD_CHANNEL:
            self._update_ch_ghost(event.scenePos())
        else:
            cell = self._cell_at(event.scenePos())
            if cell and self._cell_in_any_region(*cell):
                if event.buttons() & Qt.LeftButton:
                    self._paint_cells(*cell)
                elif event.buttons() & Qt.RightButton:
                    self._erase_cells(*cell)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._mode == MODE_PAINT and event.button() in (Qt.LeftButton, Qt.RightButton):
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


class ChannelPanel(QWidget):
    """Right-side panel for configuring channel placement."""

    params_changed = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel("<b>Channel Type</b>"))
        type_widget = QWidget()
        type_layout = QHBoxLayout(type_widget)
        type_layout.setContentsMargins(0, 0, 0, 0)
        type_layout.setSpacing(4)
        self._btn_i = QPushButton("▬  I")
        self._btn_i.setCheckable(True)
        self._btn_i.setChecked(True)
        self._btn_l = QPushButton("⌐  L")
        self._btn_l.setCheckable(True)
        self._type_group = QButtonGroup(self)
        self._type_group.addButton(self._btn_i)
        self._type_group.addButton(self._btn_l)
        self._type_group.setExclusive(True)
        type_layout.addWidget(self._btn_i)
        type_layout.addWidget(self._btn_l)
        layout.addWidget(type_widget)

        layout.addSpacing(6)

        # --- I channel params ---
        self._i_widget = QWidget()
        i_layout = QVBoxLayout(self._i_widget)
        i_layout.setContentsMargins(0, 0, 0, 0)
        i_layout.setSpacing(4)

        i_layout.addWidget(QLabel("Length (tiles):"))
        self._spin_len = QSpinBox()
        self._spin_len.setRange(1, 40)
        self._spin_len.setValue(3)
        i_layout.addWidget(self._spin_len)

        i_layout.addWidget(QLabel("Width (tiles):"))
        self._spin_w = QSpinBox()
        self._spin_w.setRange(1, 10)
        self._spin_w.setValue(1)
        i_layout.addWidget(self._spin_w)

        i_layout.addWidget(QLabel("Orientation:"))
        orient_widget = QWidget()
        orient_layout = QHBoxLayout(orient_widget)
        orient_layout.setContentsMargins(0, 0, 0, 0)
        orient_layout.setSpacing(4)
        self._btn_h = QPushButton("— H")
        self._btn_h.setCheckable(True)
        self._btn_h.setChecked(True)
        self._btn_v = QPushButton("| V")
        self._btn_v.setCheckable(True)
        self._orient_group = QButtonGroup(self)
        self._orient_group.addButton(self._btn_h)
        self._orient_group.addButton(self._btn_v)
        self._orient_group.setExclusive(True)
        orient_layout.addWidget(self._btn_h)
        orient_layout.addWidget(self._btn_v)
        i_layout.addWidget(orient_widget)

        layout.addWidget(self._i_widget)

        # --- L channel params ---
        self._l_widget = QWidget()
        l_layout = QVBoxLayout(self._l_widget)
        l_layout.setContentsMargins(0, 0, 0, 0)
        l_layout.setSpacing(4)

        l_layout.addWidget(QLabel("X length (tiles):"))
        self._spin_lx = QSpinBox()
        self._spin_lx.setRange(2, 40)
        self._spin_lx.setValue(4)
        l_layout.addWidget(self._spin_lx)

        l_layout.addWidget(QLabel("Y length (tiles):"))
        self._spin_ly = QSpinBox()
        self._spin_ly.setRange(2, 40)
        self._spin_ly.setValue(4)
        l_layout.addWidget(self._spin_ly)

        l_layout.addWidget(QLabel("Width (tiles):"))
        self._spin_lw = QSpinBox()
        self._spin_lw.setRange(1, 10)
        self._spin_lw.setValue(1)
        l_layout.addWidget(self._spin_lw)

        l_layout.addWidget(QLabel("Corner (rotation):"))
        rot_widget = QWidget()
        rot_layout = QHBoxLayout(rot_widget)
        rot_layout.setContentsMargins(0, 0, 0, 0)
        rot_layout.setSpacing(2)
        self._rot_btns = []
        self._rot_group = QButtonGroup(self)
        # symbol shows where the open "notch" / inner corner is
        # rot 0: corner TL → shape looks like ⌐ (top-right open area)
        # rot 1: corner TR → shape looks like Γ (top-left open)
        # rot 2: corner BL → shape looks like L (bottom-right open)
        # rot 3: corner BR → shape looks like J (bottom-left open)
        for i, (lbl, tip) in enumerate([
            ("⌐", "Corner top-left"),
            ("Γ", "Corner top-right"),
            ("L", "Corner bottom-left"),
            ("J", "Corner bottom-right"),
        ]):
            btn = QPushButton(lbl)
            btn.setCheckable(True)
            btn.setFixedSize(32, 28)
            btn.setToolTip(tip)
            self._rot_group.addButton(btn, i)
            rot_layout.addWidget(btn)
            self._rot_btns.append(btn)
        self._rot_btns[0].setChecked(True)
        l_layout.addWidget(rot_widget)

        self._l_widget.setVisible(False)
        layout.addWidget(self._l_widget)

        layout.addStretch()

        # connect all
        self._type_group.buttonClicked.connect(self._on_type_changed)
        self._spin_len.valueChanged.connect(self._emit)
        self._spin_w.valueChanged.connect(self._emit)
        self._orient_group.buttonClicked.connect(self._emit)
        self._spin_lx.valueChanged.connect(self._emit)
        self._spin_ly.valueChanged.connect(self._emit)
        self._spin_lw.valueChanged.connect(self._emit)
        self._rot_group.buttonClicked.connect(self._emit)

    def _on_type_changed(self, *_):
        is_l = self._btn_l.isChecked()
        self._i_widget.setVisible(not is_l)
        self._l_widget.setVisible(is_l)
        self._emit()

    def _emit(self, *_):
        self.params_changed.emit(self._params())

    def _params(self) -> dict:
        if self._btn_l.isChecked():
            return {
                'type': 'L',
                'len_x': self._spin_lx.value(),
                'len_y': self._spin_ly.value(),
                'width': self._spin_lw.value(),
                'rotation': self._rot_group.checkedId(),
            }
        return {
            'type': 'I',
            'length': self._spin_len.value(),
            'width': self._spin_w.value(),
            'orientation': 'H' if self._btn_h.isChecked() else 'V',
        }

    @property
    def params(self) -> dict:
        return self._params()




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

    def _build_shortcuts(self):
        undo_action = self.scene.undo_stack.createUndoAction(self)
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.addAction(undo_action)

        redo_action = self.scene.undo_stack.createRedoAction(self)
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.addAction(redo_action)

    def _build_toolbar(self):
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        # --- Mode toggle ---
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
        self._add_channel_btn.setToolTip("Channel mode: click to place a cable channel on the grid")
        self._add_channel_btn.clicked.connect(lambda: self._set_mode(MODE_ADD_CHANNEL))
        toolbar.addWidget(self._add_channel_btn)

        toolbar.addSeparator()

        # --- Grid size (N×M openGrid tiles) ---
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

        # --- Color palette ---
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

        custom_btn = QPushButton("Custom…")
        custom_btn.clicked.connect(self._pick_custom_color)
        toolbar.addWidget(custom_btn)

        toolbar.addSeparator()

        # --- Pen size (W×H small cells) ---
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

        # --- Undo / Redo ---
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

        # --- Zoom ---
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

        # --- Save / Open ---
        save_btn = QPushButton("💾 Save")
        save_btn.setToolTip("Save project  (Ctrl+S)")
        save_btn.clicked.connect(self._save_project)
        toolbar.addWidget(save_btn)

        open_btn = QPushButton("📂 Open")
        open_btn.setToolTip("Open project  (Ctrl+O)")
        open_btn.clicked.connect(self._open_project)
        toolbar.addWidget(open_btn)

    # ------------------------------------------------------------------ toolbar callbacks

    def _set_mode(self, mode: str):
        self.scene.set_mode(mode)
        self._paint_btn.setChecked(mode == MODE_PAINT)
        self._add_grid_btn.setChecked(mode == MODE_ADD_GRID)
        self._add_channel_btn.setChecked(mode == MODE_ADD_CHANNEL)
        self._channel_dock.setVisible(mode == MODE_ADD_CHANNEL)

    def _update_grid_size(self):
        self.scene.set_grid_size(self._spin_gw.value(), self._spin_gh.value())

    def _update_pen_size(self):
        self.scene.set_pen_size(self._spin_w.value(), self._spin_h.value())

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
        # push defaults to scene
        self.scene.set_channel_params(self._channel_panel.params)

    def _update_channel_params(self, params: dict):
        self.scene.set_channel_params(params)

    def _pick_custom_color(self):
        color = QColorDialog.getColor(self.scene._current_color, self)
        if color.isValid():
            self.scene.set_color(color)

    # ------------------------------------------------------------------ file ops

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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
