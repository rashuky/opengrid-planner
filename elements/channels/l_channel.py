"""LChannel: L-shaped cable channel with a rounded outer corner."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

from constants import TILE_CELLS, TILE_PX
from elements.channels.base import Channel


class LChannel(Channel):
    """L-shaped cable channel.

    The L consists of a horizontal arm (len_x × width tiles) and a vertical
    arm (len_y × width tiles) that share one corner tile.  The outer corner
    of the bend is drawn as a quarter-circle arc (radius = arm width).

    col/row are the top-left of the overall bounding box in small-cell coords.

    Rotations (which corner the two arms meet at):
      0 → top-left   (⌐)   H arm goes right,  V arm goes down
      1 → top-right  (Γ)   H arm goes left,   V arm goes down
      2 → bottom-left (L)  H arm goes right,  V arm goes up
      3 → bottom-right (J) H arm goes left,   V arm goes up
    """

    def __init__(
        self,
        col: int,
        row: int,
        len_x: int,
        len_y: int,
        width: int,
        rotation: int,
    ):
        self.col = col
        self.row = row
        self.len_x = len_x
        self.len_y = len_y
        self.width = width
        self.rotation = rotation

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _arm_rects_tiles(self):
        """Return (h_rect, v_rect) as (tc, tr, w, h) in tile coordinates."""
        lx, ly, w = self.len_x, self.len_y, self.width
        tc, tr = self.col // TILE_CELLS, self.row // TILE_CELLS
        r = self.rotation
        if r == 0:
            return (tc, tr, lx, w), (tc, tr, w, ly)
        elif r == 1:
            return (tc, tr, lx, w), (tc + lx - w, tr, w, ly)
        elif r == 2:
            return (tc, tr + ly - w, lx, w), (tc, tr, w, ly)
        else:
            return (tc, tr + ly - w, lx, w), (tc + lx - w, tr, w, ly)

    def _arm_px(self):
        """Return pixel bounds for both arms: (hx1,hy1,hx2,hy2, vx1,vy1,vx2,vy2)."""
        (htc, htr, htw, hth), (vtc, vtr, vtw, vth) = self._arm_rects_tiles()
        hx1, hy1 = htc * TILE_PX, htr * TILE_PX
        hx2, hy2 = (htc + htw) * TILE_PX, (htr + hth) * TILE_PX
        vx1, vy1 = vtc * TILE_PX, vtr * TILE_PX
        vx2, vy2 = (vtc + vtw) * TILE_PX, (vtr + vth) * TILE_PX
        return hx1, hy1, hx2, hy2, vx1, vy1, vx2, vy2

    # ------------------------------------------------------------------
    # Channel interface
    # ------------------------------------------------------------------

    def occupied_cells(self):
        seen = set()
        for (tc, tr, tw, th) in self._arm_rects_tiles():
            for dc in range(tw * TILE_CELLS):
                for dr in range(th * TILE_CELLS):
                    c = tc * TILE_CELLS + dc
                    r = tr * TILE_CELLS + dr
                    if (c, r) not in seen:
                        seen.add((c, r))
                        yield c, r

    def bounding_box_px(self) -> tuple:
        from constants import SMALL_CELL_PX
        return (
            self.col * SMALL_CELL_PX,
            self.row * SMALL_CELL_PX,
            self.len_x * TILE_PX,
            self.len_y * TILE_PX,
        )

    def fill_path(self) -> QPainterPath:
        """Union of the two arm rectangles."""
        path = QPainterPath()
        for (tc, tr, tw, th) in self._arm_rects_tiles():
            path.addRect(QRectF(tc * TILE_PX, tr * TILE_PX, tw * TILE_PX, th * TILE_PX))
        return path.simplified()

    def wall_paths(self) -> list:
        """Two paths: outer wall with rounded arch, and inner concave step."""
        return [self._outer_wall_path(), self._inner_step_path()]

    def _outer_wall_path(self) -> QPainterPath:
        """Outer wall: two straight runs joined by a quarter-circle arch."""
        hx1, hy1, hx2, hy2, vx1, vy1, vx2, vy2 = self._arm_px()
        R = self.width * TILE_PX
        path = QPainterPath()
        r = self.rotation
        if r == 0:   # corner TL
            path.moveTo(hx2, hy1)
            path.lineTo(hx1 + R, hy1)
            path.arcTo(hx1, hy1, 2 * R, 2 * R, 90, 90)
            path.lineTo(vx1, vy2)
        elif r == 1: # corner TR
            path.moveTo(hx1, hy1)
            path.lineTo(hx2 - R, hy1)
            path.arcTo(hx2 - 2 * R, hy1, 2 * R, 2 * R, 90, -90)
            path.lineTo(hx2, vy2)
        elif r == 2: # corner BL
            path.moveTo(vx1, vy1)
            path.lineTo(hx1, hy2 - R)
            path.arcTo(hx1, hy2 - 2 * R, 2 * R, 2 * R, 180, 90)
            path.lineTo(hx2, hy2)
        else:        # corner BR
            path.moveTo(hx1, hy2)
            path.lineTo(hx2 - R, hy2)
            path.arcTo(hx2 - 2 * R, hy2 - 2 * R, 2 * R, 2 * R, 270, 90)
            path.lineTo(hx2, vy1)
        return path

    def _inner_step_path(self) -> QPainterPath:
        """Inner concave corner: two right-angle segments at the step."""
        hx1, hy1, hx2, hy2, vx1, vy1, vx2, vy2 = self._arm_px()
        path = QPainterPath()
        r = self.rotation
        if r == 0:
            path.moveTo(hx2, hy2); path.lineTo(vx2, hy2); path.lineTo(vx2, vy2)
        elif r == 1:
            path.moveTo(vx1, vy2); path.lineTo(vx1, hy2); path.lineTo(hx1, hy2)
        elif r == 2:
            path.moveTo(hx2, hy1); path.lineTo(vx2, hy1); path.lineTo(vx2, vy1)
        else:
            path.moveTo(vx1, vy1); path.lineTo(vx1, hy1); path.lineTo(hx1, hy1)
        return path

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "type": "L",
            "col": self.col,
            "row": self.row,
            "len_x": self.len_x,
            "len_y": self.len_y,
            "width": self.width,
            "rotation": self.rotation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LChannel":
        return cls(
            d["col"], d["row"],
            d["len_x"], d["len_y"],
            d["width"], d["rotation"],
        )
