"""GridRegion: a rectangular array of openGrid tiles placed on the canvas."""
from constants import TILE_CELLS


class GridRegion:
    """One placed openGrid tile array: n_w × n_h tiles at (tile_col, tile_row).

    Each openGrid tile = TILE_CELLS × TILE_CELLS small paintable cells (28 mm real).
    """

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
        """Return True if this region's tile rectangle intersects other's."""
        return not (
            self.tile_col + self.n_w <= other.tile_col or
            other.tile_col + other.n_w <= self.tile_col or
            self.tile_row + self.n_h <= other.tile_row or
            other.tile_row + other.n_h <= self.tile_row
        )

    def to_dict(self) -> dict:
        return {
            "tile_col": self.tile_col,
            "tile_row": self.tile_row,
            "n_w": self.n_w,
            "n_h": self.n_h,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GridRegion":
        return cls(d["tile_col"], d["tile_row"], d["n_w"], d["n_h"])
