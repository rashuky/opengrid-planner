"""IChannel: straight (I-shaped) cable channel."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

from constants import SMALL_CELL_PX, TILE_CELLS, TILE_PX
from elements.channels.base import Channel


class IChannel(Channel):
    """Straight cable channel, either horizontal or vertical.

    col/row are top-left in small-cell coordinates.
    length and width are in tiles; orientation is 'H' or 'V'.
    Open ends (the two short sides) have no wall drawn.
    """

    def __init__(self, col: int, row: int, length: int, width: int, orientation: str):
        self.col = col
        self.row = row
        self.length = length        # tiles along the main axis
        self.width = width          # tiles across
        self.orientation = orientation  # 'H' or 'V'

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _pixel_rect(self) -> tuple:
        x = self.col * SMALL_CELL_PX
        y = self.row * SMALL_CELL_PX
        if self.orientation == 'H':
            return x, y, self.length * TILE_PX, self.width * TILE_PX
        return x, y, self.width * TILE_PX, self.length * TILE_PX

    # ------------------------------------------------------------------
    # Channel interface
    # ------------------------------------------------------------------

    def occupied_cells(self):
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

    def bounding_box_px(self) -> tuple:
        return self._pixel_rect()

    def fill_path(self) -> QPainterPath:
        x, y, w, h = self._pixel_rect()
        path = QPainterPath()
        path.addRect(QRectF(x, y, w, h))
        return path

    def wall_paths(self) -> list:
        """Two long-side walls; the short open ends are left undrawn."""
        x, y, w, h = self._pixel_rect()
        if self.orientation == 'H':
            p1 = QPainterPath(); p1.moveTo(x, y);     p1.lineTo(x + w, y)
            p2 = QPainterPath(); p2.moveTo(x, y + h); p2.lineTo(x + w, y + h)
        else:
            p1 = QPainterPath(); p1.moveTo(x,     y); p1.lineTo(x,     y + h)
            p2 = QPainterPath(); p2.moveTo(x + w, y); p2.lineTo(x + w, y + h)
        return [p1, p2]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "type": "I",
            "col": self.col,
            "row": self.row,
            "length": self.length,
            "width": self.width,
            "orientation": self.orientation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IChannel":
        return cls(d["col"], d["row"], d["length"], d["width"], d["orientation"])
