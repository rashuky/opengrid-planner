"""GridView: zooming QGraphicsView wrapper."""
from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt

PROJECT_FILTER = "Grid Planner Project (*.gridplan);;All files (*)"


class GridView(QGraphicsView):
    """QGraphicsView with Ctrl+wheel zoom."""

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
