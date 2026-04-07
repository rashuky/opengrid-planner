"""TChannel: T-shaped cable channel with a flat rectangular junction, no rounded corners."""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainterPath

from constants import SMALL_CELL_PX, TILE_CELLS, TILE_PX
from elements.channels.base import Channel


class TChannel(Channel):
    """T-shaped cable channel.

    Three arms meet at a flat rectangular junction:
      - stem arm  (direction set by rotation)
      - left arm  (relative label; see rotation notes below)
      - right arm

    Junction dimensions:
      perpendicular to stem: stem_w  tiles
      along stem direction:  max(left_w, right_w)  tiles  (jh)

    Both bar arms snap to the outer edge of the junction (away from stem).
    The narrower arm therefore does not reach the inner (stem-side) edge.

    col/row: top-left of bounding box in small-cell coordinates.

    Rotations (stem direction):
      0 → stem down    (⊤)   left arm → west,  right arm → east
      1 → stem right   (⊣)   left arm → north, right arm → south
      2 → stem up      (⊥)   left arm → west,  right arm → east
      3 → stem left    (⊢)   left arm → north, right arm → south
    """

    def __init__(
        self,
        col: int, row: int,
        stem_len: int, stem_w: int,
        left_len: int, left_w: int,
        right_len: int, right_w: int,
        rotation: int,
    ):
        self.col = col
        self.row = row
        self.stem_len = stem_len
        self.stem_w = stem_w
        self.left_len = left_len
        self.left_w = left_w
        self.right_len = right_len
        self.right_w = right_w
        self.rotation = rotation % 4

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _jh(self) -> int:
        """Junction depth along the stem axis (tiles) = max(left_w, right_w)."""
        return max(self.left_w, self.right_w)

    def _rects_tiles(self):
        """Return [(x, y, w, h), ...] in tiles relative to bounding-box top-left.

        Always three rects: left arm, right arm, junction+stem combined.
        Zero-size rects are omitted by _shape_path() before rendering.

        rotation=0 (⊤, stem down):
            bbox W = left_len + stem_w + right_len
            bbox H = jh + stem_len
            Both bar arms snap to y=0 (outer/top edge).

        rotation=1 (⊣, stem right):
            bbox W = jh + stem_len
            bbox H = left_len + stem_w + right_len
            Both bar arms snap to x=0 (outer/left edge).

        rotation=2 (⊥, stem up):
            bbox W = left_len + stem_w + right_len
            bbox H = stem_len + jh
            Both bar arms snap to bottom (y = stem_len + jh).

        rotation=3 (⊢, stem left):
            bbox W = stem_len + jh
            bbox H = left_len + stem_w + right_len
            Both bar arms snap to right (x = stem_len + jh).
        """
        sl, sw = self.stem_len, self.stem_w
        ll, lw = self.left_len, self.left_w
        rl, rw = self.right_len, self.right_w
        jh = self._jh()
        r = self.rotation

        if r == 0:   # stem down  ⊤
            return [
                (0,       0,  ll, lw),           # left arm, snaps to top
                (ll + sw, 0,  rl, rw),           # right arm, snaps to top
                (ll,      0,  sw, jh + sl),      # junction + stem
            ]
        elif r == 1:  # stem right  ⊣
            return [
                (0,    0,       lw, ll),          # top arm, snaps to left
                (0,    ll + sw, rw, rl),          # bottom arm, snaps to left
                (0,    ll,      jh + sl, sw),     # junction + stem
            ]
        elif r == 2:  # stem up  ⊥
            th = sl + jh
            return [
                (0,       th - lw, ll, lw),       # left arm, snaps to bottom
                (ll + sw, th - rw, rl, rw),       # right arm, snaps to bottom
                (ll,      0,       sw, th),        # stem + junction
            ]
        else:         # r == 3, stem left  ⊢
            tw = sl + jh
            return [
                (tw - lw, 0,       lw, ll),       # top arm, snaps to right
                (tw - rw, ll + sw, rw, rl),       # bottom arm, snaps to right
                (0,       ll,      tw, sw),        # stem + junction
            ]

    def _bbox_wh_tiles(self):
        """Return (tile_w, tile_h) of the bounding box."""
        sl, sw = self.stem_len, self.stem_w
        ll = self.left_len
        rl = self.right_len
        jh = self._jh()
        if self.rotation in (0, 2):
            return ll + sw + rl, jh + sl
        else:
            return jh + sl, ll + sw + rl

    def _shape_path(self) -> QPainterPath:
        """QPainterPath outline of the T area (union of all arm rects)."""
        tc = self.col // TILE_CELLS
        tr = self.row // TILE_CELLS
        ox = tc * TILE_PX
        oy = tr * TILE_PX
        path = QPainterPath()
        for (x, y, w, h) in self._rects_tiles():
            if w > 0 and h > 0:
                path.addRect(QRectF(
                    ox + x * TILE_PX,
                    oy + y * TILE_PX,
                    w * TILE_PX,
                    h * TILE_PX,
                ))
        return path.simplified()

    # ------------------------------------------------------------------
    # Channel interface
    # ------------------------------------------------------------------

    def occupied_cells(self):
        tc = self.col // TILE_CELLS
        tr = self.row // TILE_CELLS
        seen = set()
        for (rx, ry, rw, rh) in self._rects_tiles():
            for dc in range(rw * TILE_CELLS):
                for dr in range(rh * TILE_CELLS):
                    c = (tc + rx) * TILE_CELLS + dc
                    r = (tr + ry) * TILE_CELLS + dr
                    if (c, r) not in seen:
                        seen.add((c, r))
                        yield c, r

    def bounding_box_px(self) -> tuple:
        tw, th = self._bbox_wh_tiles()
        return (
            self.col * SMALL_CELL_PX,
            self.row * SMALL_CELL_PX,
            tw * TILE_PX,
            th * TILE_PX,
        )

    def fill_path(self) -> QPainterPath:
        return self._shape_path()

    def wall_paths(self) -> list:
        return [self._shape_path()]

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "type":      "T",
            "col":       self.col,
            "row":       self.row,
            "stem_len":  self.stem_len,
            "stem_w":    self.stem_w,
            "left_len":  self.left_len,
            "left_w":    self.left_w,
            "right_len": self.right_len,
            "right_w":   self.right_w,
            "rotation":  self.rotation,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TChannel":
        return cls(
            d["col"], d["row"],
            d["stem_len"], d["stem_w"],
            d["left_len"], d["left_w"],
            d["right_len"], d["right_w"],
            d["rotation"],
        )
