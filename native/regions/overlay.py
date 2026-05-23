from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget, QApplication

from native.core.models import ScreenRegion


class SelectionOverlay(QWidget):
    """Full-screen, transparent overlay for selecting a rectangular region across all monitors."""
    
    region_selected = Signal(object)  # ScreenRegion

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._start_pos_local = None
        self._current_pos_local = None
        self._start_pos_global = None
        self._is_dragging = False

        # Cover entire virtual desktop across all monitors
        desktop_rect = QRect()
        for screen in QApplication.screens():
            desktop_rect = desktop_rect.united(screen.geometry())
        self.setGeometry(desktop_rect)

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Fill whole screen with semi-transparent black
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._is_dragging and self._start_pos_local and self._current_pos_local:
            rect = QRect(self._start_pos_local, self._current_pos_local).normalized()
            
            # Clear the inner rect area so it's fully transparent
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(rect, Qt.GlobalColor.transparent)

            # Draw the active selection border (hotpink or configurable)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen = QPen(QColor("hotpink"))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos_local = event.position().toPoint()
            self._current_pos_local = self._start_pos_local
            self._start_pos_global = event.globalPosition().toPoint()
            self._is_dragging = True
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.close()

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self._current_pos_local = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            current_pos_global = event.globalPosition().toPoint()

            # Global geometry start_pos relative to desktop
            region = ScreenRegion.from_drag(
                id="1",
                label="Region 1",
                start_x=self._start_pos_global.x(),
                start_y=self._start_pos_global.y(),
                end_x=current_pos_global.x(),
                end_y=current_pos_global.y(),
                monitor=1  # Simplifying, MSS can still capture via global bounds
            )
            
            if region.is_valid:
                self.region_selected.emit(region)
                
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
