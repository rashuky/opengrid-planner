"""QUndoCommand subclasses for all undoable actions."""
import logging

from PySide6.QtGui import QColor, QUndoCommand

from elements.opengrid.region import GridRegion
from elements.channels.base import Channel


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
        super().__init__("Place channel")
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
