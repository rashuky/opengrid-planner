"""Grid Planner — entry point.

Run with:
    python grid_planner.py
"""
import sys

from PySide6.QtWidgets import QApplication

# Import constants so logging is configured before anything else runs
import constants  # noqa: F401
from main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
