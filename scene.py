"""GridScene: the QGraphicsScene that owns all canvas state and interactions."""
import logging

from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtGui import QPen, QColor, QBrush, QUndoStack, QPainterPath
from PySide6.QtCore import Qt, QRectF, Signal, QPointF

from constants import (
    SMALL_CELL_PX, TILE_CELLS, TILE_PX, CANVAS_TILES, CANVAS_PX,
    MODE_PAINT, MODE_ADD_GRID, MODE_ADD_CHANNEL, MODE_SELECT,
)
from elements.opengrid.region import GridRegion
from elements.channels.base import Channel
from elements.channels.i_channel import IChannel
from elements.channels.l_channel import LChannel
from elements.channels.registry import channel_from_dict
from commands import PlaceGridCommand, PlaceChannelCommand, PaintCommand, DeleteChannelCommand, EditChannelCommand


class GridScene(QGraphicsScene):
    # Signals for external observers (channel list panel, main window)
    channel_placed = Signal(object)      # Channel after _add_channel
    channel_erased = Signal(object)         # id(channel) after _remove_channel
    channel_selection_changed = Signal(object)  # Channel | None

    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, CANVAS_PX, CANVAS_PX)
        self._cells: dict = {}           # (col, row) -> QGraphicsRectItem
        self._regions: list = []         # list[GridRegion]
        self._region_items: dict = {}    # id(region) -> [QGraphicsItem, ...]
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
        self._channel_cells: set = set()
        self._ch_type = 'I'
        self._ch_length = 3
        self._ch_width = 1
        self._ch_orientation = 'H'
        self._ch_len_x = 3
        self._ch_len_y = 3
        self._ch_rotation = 0
        self._ch_ghost = None
        self._last_scene_pos = None
        # selection / editing state
        self._selected_ch = None
        self._selection_items: list = []
        self._editing: bool = False
        self._edit_source_ch = None
        self._edit_rotation: int = 0
        self._edit_orientation: str = 'H'

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def selected_channel(self):
        return self._selected_ch

    def set_color(self, color: QColor):
        self._current_color = color

    def set_pen_size(self, w: int, h: int):
        self._pen_w = max(1, w)
        self._pen_h = max(1, h)

    def set_mode(self, mode: str):
        self._cancel_edit()
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
        self._ch_len_x = max(0, params.get('len_x', 3))
        self._ch_len_y = max(0, params.get('len_y', 3))
        self._ch_rotation = params.get('rotation', 0)
        if self._mode == MODE_ADD_CHANNEL:
            self._update_ch_ghost(self._last_scene_pos)

    # ------------------------------------------------------------------
    # Region management
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Channel management
    # ------------------------------------------------------------------

    def _make_candidate_channel(self, col: int, row: int) -> Channel:
        """Instantiate the currently-configured channel type at (col, row)."""
        if self._ch_type == 'L':
            return LChannel(col, row, self._ch_len_x, self._ch_len_y,
                            self._ch_width, self._ch_rotation)
        return IChannel(col, row, self._ch_length, self._ch_width, self._ch_orientation)

    def _draw_channel(self, channel: Channel) -> list:
        """Draw any channel type polymorphically via fill_path() / wall_paths()."""
        wall_pen = QPen(QColor(44, 80, 120))
        wall_pen.setWidth(3)
        wall_pen.setCapStyle(Qt.RoundCap)
        wall_pen.setJoinStyle(Qt.RoundJoin)
        fill_brush = QBrush(QColor(100, 140, 180, 80))

        fill_item = self.addPath(channel.fill_path(), QPen(Qt.NoPen), fill_brush)
        fill_item.setData(0, id(channel))  # tag for hit-testing in select mode
        items = [fill_item]
        for path in channel.wall_paths():
            wall_item = self.addPath(path, wall_pen, QBrush(Qt.NoBrush))
            wall_item.setData(0, id(channel))
            items.append(wall_item)
        for item in items:
            item.setZValue(2)
        return items

    def _add_channel(self, channel: Channel):
        items = self._draw_channel(channel)
        self._channels.append(channel)
        self._channel_items[id(channel)] = items
        for cell in channel.occupied_cells():
            self._channel_cells.add(cell)
        self.channel_placed.emit(channel)

    def _remove_channel(self, channel: Channel, update_selection: bool = True):
        cid = id(channel)
        for item in self._channel_items.pop(cid, []):
            self.removeItem(item)
        if channel in self._channels:
            self._channels.remove(channel)
        for cell in channel.occupied_cells():
            self._channel_cells.discard(cell)
        if update_selection and self._selected_ch is channel:
            self._clear_selection_overlay()
            self._selected_ch = None
            self.channel_selection_changed.emit(None)
        self.channel_erased.emit(cid)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_channel(self, channel_id: int):
        """Select the channel with the given id(), draw highlight, emit signal."""
        self._clear_selection_overlay()
        ch = next((c for c in self._channels if id(c) == channel_id), None)
        self._selected_ch = ch
        if ch is not None:
            self._draw_selection_overlay(ch)
        self.channel_selection_changed.emit(ch)

    def deselect(self):
        self._cancel_edit()
        self._clear_selection_overlay()
        if self._selected_ch is not None:
            self._selected_ch = None
            self.channel_selection_changed.emit(None)

    def _draw_selection_overlay(self, channel: Channel):
        x, y, w, h = channel.bounding_box_px()
        sel_pen = QPen(QColor(255, 165, 0))
        sel_pen.setWidth(2)
        sel_pen.setStyle(Qt.DashLine)
        item = self.addRect(QRectF(x, y, w, h), sel_pen, QBrush(Qt.NoBrush))
        item.setZValue(5)
        self._selection_items = [item]

    def _clear_selection_overlay(self):
        for item in self._selection_items:
            self.removeItem(item)
        self._selection_items = []

    def _channel_at_pos(self, scene_pos):
        """Return the Channel whose graphic item is at scene_pos, or None."""
        for item in self.items(scene_pos):
            cid = item.data(0)
            if cid is not None:
                ch = next((c for c in self._channels if id(c) == cid), None)
                if ch is not None:
                    return ch
        return None

    # ------------------------------------------------------------------
    # Edit operations (move / rotate / delete / param change)
    # ------------------------------------------------------------------

    def rotate_selected(self):
        """Cycle rotation of the selected channel; enter move-ghost mode."""
        if self._selected_ch is None:
            return
        src = self._edit_source_ch if self._editing else self._selected_ch
        d = src.to_dict()
        if d['type'] == 'L':
            cur = self._edit_rotation if self._editing else d['rotation']
            self._edit_rotation = (cur + 1) % 4
            self._edit_orientation = 'H'
        else:
            cur = self._edit_orientation if self._editing else d['orientation']
            self._edit_orientation = 'V' if cur == 'H' else 'H'
            self._edit_rotation = 0
        if not self._editing:
            self._start_editing(self._selected_ch)
        else:
            self._update_edit_ghost(self._last_scene_pos)

    def delete_selected(self):
        """Delete the selected channel via an undoable command."""
        if self._selected_ch is None:
            return
        ch = self._selected_ch
        self._cancel_edit()
        self._undo_stack.push(DeleteChannelCommand(self, ch))

    def cancel_edit(self):
        """Public cancel: stop ghost-reposition mode without committing."""
        self._cancel_edit()

    def update_selected_channel_params(self, params: dict):
        """Apply param changes to the selected channel immediately."""
        if self._selected_ch is None or self._editing:
            return
        old = self._selected_ch
        d = old.to_dict()
        if d['type'] != params.get('type', d['type']):
            return  # type change not supported via panel
        if d['type'] == 'L':
            new_ch = LChannel(
                old.col, old.row,
                params.get('len_x', d['len_x']),
                params.get('len_y', d['len_y']),
                params.get('width', d['width']),
                params.get('rotation', d['rotation']),
            )
        else:
            new_ch = IChannel(
                old.col, old.row,
                params.get('length', d['length']),
                params.get('width', d['width']),
                params.get('orientation', d['orientation']),
            )
        self._undo_stack.push(EditChannelCommand(self, old, new_ch))
        # EditChannelCommand.redo() already called select_channel(id(new_ch))

    # ------------------------------------------------------------------
    # Internal edit-ghost helpers
    # ------------------------------------------------------------------

    def _start_editing(self, channel: Channel):
        self._edit_source_ch = channel
        self._editing = True
        pos = QPointF(channel.col * SMALL_CELL_PX, channel.row * SMALL_CELL_PX)
        self._last_scene_pos = pos
        self._update_edit_ghost(pos)

    def _cancel_edit(self):
        if self._editing:
            self._editing = False
            self._edit_source_ch = None
            if self._ch_ghost is not None:
                self._ch_ghost.setVisible(False)

    def _make_edit_candidate(self, col: int, row: int) -> Channel:
        d = self._edit_source_ch.to_dict()
        if d['type'] == 'L':
            return LChannel(col, row, d['len_x'], d['len_y'],
                            d['width'], self._edit_rotation)
        return IChannel(col, row, d['length'], d['width'], self._edit_orientation)

    def _channel_placement_valid_edit(self, col: int, row: int) -> bool:
        limit = CANVAS_TILES * TILE_CELLS
        exclude_cells = set(self._edit_source_ch.occupied_cells())
        for c, r in self._make_edit_candidate(col, row).occupied_cells():
            if not (0 <= c < limit and 0 <= r < limit):
                return False
            if not self._cell_in_any_region(c, r):
                return False
            if (c, r) in self._channel_cells and (c, r) not in exclude_cells:
                return False
        return True

    def _update_edit_ghost(self, scene_pos):
        cell = self._tile_cell_at(scene_pos)
        if cell is None:
            if self._ch_ghost is not None:
                self._ch_ghost.setVisible(False)
            return
        col, row = cell
        valid = self._channel_placement_valid_edit(col, row)
        pen_color  = QColor(0, 150, 0, 200) if valid else QColor(200, 0, 0, 220)
        fill_color = QColor(0, 200, 0, 40)  if valid else QColor(255, 0, 0, 50)
        ghost_pen = QPen(pen_color)
        ghost_pen.setWidth(1)
        ghost_pen.setStyle(Qt.DashLine)
        path = self._make_edit_candidate(col, row).fill_path()
        if self._ch_ghost is None:
            self._ch_ghost = self.addPath(path, ghost_pen, QBrush(fill_color))
            self._ch_ghost.setZValue(10)
        else:
            self._ch_ghost.setPath(path)
            self._ch_ghost.setPen(ghost_pen)
            self._ch_ghost.setBrush(QBrush(fill_color))
            self._ch_ghost.setVisible(True)

    def _channel_candidate_cells(self, col: int, row: int):
        """Yield cells a channel would occupy if its top-left is at (col, row)."""
        yield from self._make_candidate_channel(col, row).occupied_cells()

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

    def _tile_cell_at(self, scene_pos):
        """Return channel origin (col, row) snapped to tile grid, or None."""
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
        path = self._make_candidate_channel(col, row).fill_path()
        if self._ch_ghost is None:
            self._ch_ghost = self.addPath(path, ghost_pen, QBrush(fill_color))
            self._ch_ghost.setZValue(10)
        else:
            self._ch_ghost.setPath(path)
            self._ch_ghost.setPen(ghost_pen)
            self._ch_ghost.setBrush(QBrush(fill_color))
            self._ch_ghost.setVisible(True)

    # ------------------------------------------------------------------
    # Region ghost preview
    # ------------------------------------------------------------------

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
        pen_color  = QColor(200, 0, 0, 220) if collides else QColor(0, 150, 0, 200)
        fill_color = QColor(255, 0, 0, 50)  if collides else QColor(0, 200, 0, 40)
        ghost_pen = QPen(pen_color)
        ghost_pen.setWidth(2)
        ghost_pen.setStyle(Qt.DashLine)
        if self._ghost is None:
            self._ghost = self.addRect(rect, ghost_pen, QBrush(fill_color))
            self._ghost.setZValue(10)
        else:
            self._ghost.setPen(ghost_pen)
            self._ghost.setBrush(QBrush(fill_color))
            self._ghost.setRect(rect)
            self._ghost.setVisible(True)

    # ------------------------------------------------------------------
    # Cell operations
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Stroke helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

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
        self._cancel_edit()
        self._clear_selection_overlay()
        self._selected_ch = None
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
            self._add_channel(channel_from_dict(cd))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

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
                    channel = self._make_candidate_channel(*cell)
                    self._undo_stack.push(PlaceChannelCommand(self, channel))
                    logging.info("PLACE channel %s", channel.to_dict())
        elif self._mode == MODE_SELECT:
            if event.button() == Qt.LeftButton:
                if self._editing:
                    cell = self._tile_cell_at(event.scenePos())
                    if cell and self._channel_placement_valid_edit(*cell):
                        new_ch = self._make_edit_candidate(*cell)
                        src = self._edit_source_ch
                        self._cancel_edit()
                        self._undo_stack.push(EditChannelCommand(self, src, new_ch))
                        # EditChannelCommand.redo() selects new_ch automatically
                else:
                    ch = self._channel_at_pos(event.scenePos())
                    if ch is not None:
                        if ch is self._selected_ch:
                            # second click on selected channel → enter move mode
                            d = ch.to_dict()
                            self._edit_rotation = d.get('rotation', 0)
                            self._edit_orientation = d.get('orientation', 'H')
                            self._start_editing(ch)
                        else:
                            self.select_channel(id(ch))
                    else:
                        self.deselect()
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
        elif self._mode == MODE_SELECT:
            if self._editing:
                self._update_edit_ghost(event.scenePos())
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self._editing:
                self._cancel_edit()
            elif self._selected_ch is not None:
                self.deselect()
        super().keyPressEvent(event)
