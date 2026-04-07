"""Application-wide constants and logging configuration."""
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Pixel / geometry constants
# ---------------------------------------------------------------------------

SMALL_CELL_PX = 20                          # pixels per small (paintable) cell
TILE_CELLS    = 10                          # small cells per openGrid unit (28 mm)
TILE_PX       = SMALL_CELL_PX * TILE_CELLS  # 200 px / openGrid tile
CANVAS_TILES  = 80                          # canvas size in openGrid tiles
CANVAS_PX     = CANVAS_TILES * TILE_PX

# ---------------------------------------------------------------------------
# Application modes
# ---------------------------------------------------------------------------

MODE_PAINT       = "paint"
MODE_ADD_GRID    = "add_grid"
MODE_ADD_CHANNEL = "add_channel"
MODE_SELECT      = "select"

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

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
# Logging
# ---------------------------------------------------------------------------

LOG_PATH = Path(__file__).parent / "actions.log"
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
