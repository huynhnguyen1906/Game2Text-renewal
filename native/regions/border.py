from __future__ import annotations

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget

from native.core.models import ScreenRegion


class RegionBorder(QWidget):
    """A transparent, frameless window that draws a border around the selected screen region."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._region: ScreenRegion | None = None

    def set_region(self, region: ScreenRegion | None):
        self._region = region
        if region and region.is_valid:
            self.setGeometry(region.x, region.y, region.width, region.height)
            self.update()
            if region.show_region_border:
                self.show()
            else:
                self.hide()
        else:
            self.hide()

    def paintEvent(self, event):
        if not self._region:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(self._region.border_color))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw border inside the widget bounds so it doesn't get clipped
        rect = self.rect()
        painter.drawRect(rect.adjusted(1, 1, -1, -1))
