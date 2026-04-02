"""Abstract base class for all cable channel types.

Every channel subclass must implement:
  - occupied_cells()     → geometry in small-cell coordinates
  - bounding_box_px()    → pixel-space bounding box
  - fill_path()          → QPainterPath for the filled body
  - wall_paths()         → list of open QPainterPaths for walls (stroked only)
  - to_dict() / from_dict()  → serialisation round-trip

The scene calls fill_path() and wall_paths() without any isinstance checks,
so adding a new channel type (T, Y, …) requires no changes to scene.py.
"""
from abc import ABC, abstractmethod

from PySide6.QtGui import QPainterPath


class Channel(ABC):
    """Abstract base for all channel shapes (I, L, T, Y, …)."""

    @abstractmethod
    def occupied_cells(self):
        """Yield (col, row) small-cell coordinates this channel covers."""

    @abstractmethod
    def bounding_box_px(self) -> tuple:
        """Return (x, y, w, h) pixel bounding box."""

    @abstractmethod
    def fill_path(self) -> QPainterPath:
        """QPainterPath for the solid body of the channel (filled, not stroked)."""

    @abstractmethod
    def wall_paths(self) -> list:
        """Open QPainterPaths for all wall segments (stroked, not filled).

        Return multiple paths when the wall is geometrically discontinuous
        (e.g. the two open ends of an I-channel, or outer-arch + inner-step
        for an L-channel).
        """

    @abstractmethod
    def to_dict(self) -> dict:
        """Serialise to a JSON-compatible dict.  Must include a 'type' key."""

    @classmethod
    @abstractmethod
    def from_dict(cls, d: dict) -> "Channel":
        """Deserialise from a dict produced by to_dict()."""
