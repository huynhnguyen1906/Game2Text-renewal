from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPoint, QPointF, QRect, QRectF, Qt, QPropertyAnimation, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QResizeEvent,
    QShowEvent,
    QTextLayout,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget

from native.config.service import GAME_OVERLAY_SECTION, read_value, update_section
from native.core.dpi import configure_overlay_window_chrome


RESIZE_MARGIN = 10
TEXT_PADDING_X = 16
TEXT_PADDING_Y = 12


@dataclass
class OverlayStyle:
    font_size: int
    text_opacity: float
    outline_opacity: float
    background_opacity: float
    overlay_opacity: float
    use_text_background: bool


class OverlayTextDisplay(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._text = "Ban dich moi nhat se hien o day."
        self._style = OverlayStyle(
            font_size=28,
            text_opacity=1.0,
            outline_opacity=0.7,
            background_opacity=0.7,
            overlay_opacity=1.0,
            use_text_background=False,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background: transparent; border: none;")

    def set_text(self, text: str) -> None:
        stripped = text.strip()
        if stripped:
            self._text = stripped
            self.update()

    def set_style(self, style: OverlayStyle) -> None:
        self._style = style
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        rect = self.rect().adjusted(TEXT_PADDING_X, TEXT_PADDING_Y, -TEXT_PADDING_X, -TEXT_PADDING_Y)
        font = QFont()
        font.setPixelSize(self._style.font_size)
        font.setBold(True)
        painter.setFont(font)

        line_layouts, block_height = self._layout_lines(font, rect)
        if not line_layouts:
            return

        block_top = rect.top() + max(0.0, (rect.height() - block_height) / 2.0)

        if self._style.use_text_background:
            bg_color = QColor(0, 0, 0, int(self._style.background_opacity * 255))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg_color)
            for line_text, line_rect, _baseline_y in line_layouts:
                if not line_text.strip():
                    continue
                bg_rect = line_rect.adjusted(-14, -8, 14, 8)
                painter.drawRoundedRect(bg_rect, 10, 10)
            painter.setPen(QColor(255, 255, 255, int(self._style.text_opacity * 255)))
            for line_text, _line_rect, baseline_y in line_layouts:
                if not line_text:
                    continue
                path = QPainterPath()
                path.addText(QPointF(_line_rect.left(), baseline_y), font, line_text)
                painter.fillPath(path, QColor(255, 255, 255, int(self._style.text_opacity * 255)))
            return

        outline_color = QColor(0, 0, 0, int(self._style.outline_opacity * 255))
        fill_color = QColor(255, 255, 255, int(self._style.text_opacity * 255))
        outline_pen = QPen(
            outline_color,
            max(2.0, self._style.font_size * 0.14),
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
        for line_text, line_rect, baseline_y in line_layouts:
            if not line_text:
                continue
            path = QPainterPath()
            path.addText(QPointF(line_rect.left(), baseline_y), font, line_text)
            painter.strokePath(path, outline_pen)
            painter.fillPath(path, fill_color)

    def _layout_lines(self, font: QFont, rect: QRect) -> tuple[list[tuple[str, QRectF, float]], float]:
        layout = QTextLayout(self._text, font)
        layout.beginLayout()

        wrapped_lines: list[tuple[str, QRectF, float]] = []
        y = 0.0
        max_width = 0.0

        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(max(1.0, float(rect.width())))
            line.setPosition(QPointF(0.0, y))

            start = line.textStart()
            length = line.textLength()
            line_text = self._text[start : start + length].rstrip("\n")
            line_width = line.naturalTextWidth()
            line_height = line.height()
            max_width = max(max_width, line_width)

            wrapped_lines.append((line_text, QRectF(0.0, y, line_width, line_height), line.ascent()))
            y += line_height

        layout.endLayout()

        if not wrapped_lines:
            return [], 0.0

        total_height = wrapped_lines[-1][1].bottom()
        centered_lines: list[tuple[str, QRectF, float]] = []
        block_top = rect.top() + max(0.0, (rect.height() - total_height) / 2.0)
        for line_text, raw_rect, ascent in wrapped_lines:
            line_left = rect.left() + max(0.0, (rect.width() - raw_rect.width()) / 2.0)
            line_top = block_top + raw_rect.top()
            line_rect = QRectF(line_left, line_top, raw_rect.width(), raw_rect.height())
            baseline_y = line_top + ascent
            centered_lines.append((line_text, line_rect, baseline_y))

        return centered_lines, total_height


class GameOverlayWindow(QWidget):
    FADE_OUT_DURATION_MS = 750

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shutdown_in_progress = False
        self._shutdown_restore_open = False
        self._display_text = "Ban dich moi nhat se hien o day."
        self._base_overlay_opacity = 1.0
        self._current_fade_duration_ms = self.FADE_OUT_DURATION_MS
        self._manual_visible = False
        self._auto_hidden = False
        self._editor_mode = False
        self._dragging = False
        self._resize_edges: set[str] = set()
        self._drag_start_global = QPoint()
        self._drag_start_geometry = QRect()
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.timeout.connect(self._handle_auto_hide_timeout)
        self._fade_out_timer = QTimer(self)
        self._fade_out_timer.setSingleShot(True)
        self._fade_out_timer.timeout.connect(self._start_fade_out)
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_animation.setDuration(self.FADE_OUT_DURATION_MS)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.Linear)
        self._fade_animation.finished.connect(self._finish_fade_out)

        self.setWindowTitle("Game2Text Overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background: transparent; border: none;")
        self._apply_window_mode_flags(editor_mode=False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.display_widget = OverlayTextDisplay(self)
        layout.addWidget(self.display_widget)

        self.reload_from_config()

    def prepare_for_app_shutdown(self, restore_open: bool) -> None:
        self._shutdown_in_progress = True
        self._shutdown_restore_open = restore_open

    @property
    def editor_mode(self) -> bool:
        return self._editor_mode

    @property
    def manual_visible(self) -> bool:
        return self._manual_visible

    def set_display_text(self, text: str) -> None:
        stripped = text.strip()
        if stripped:
            self._display_text = stripped
        self.display_widget.set_text(self._display_text)

    def handle_new_translation(self, text: str) -> None:
        self.set_display_text(text)
        if not self._manual_visible:
            return
        self._cancel_fade_out()
        self._auto_hidden = False
        if not self.isVisible():
            self.reload_geometry_from_config()
            self.show()
            self.raise_()
        self.setWindowOpacity(self._base_overlay_opacity)
        self._restart_auto_hide_timer()

    def set_editor_mode(self, enabled: bool) -> None:
        if self._editor_mode == enabled:
            return
        self._editor_mode = enabled
        was_visible = self.isVisible()
        self.hide()
        self._apply_window_mode_flags(editor_mode=enabled)
        if was_visible:
            self.show()
            self._apply_native_chrome()
            self.raise_()
            if enabled:
                self.activateWindow()
        if enabled:
            self._cancel_fade_out()
            self._auto_hide_timer.stop()
        elif self._manual_visible and self.isVisible():
            self.setWindowOpacity(self._base_overlay_opacity)
            self._restart_auto_hide_timer()
        self._update_cursor()
        self.update()

    def _apply_window_mode_flags(self, editor_mode: bool) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        if editor_mode:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        else:
            flags |= Qt.WindowType.WindowTransparentForInput | Qt.WindowType.NoDropShadowWindowHint
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowFlags(flags)

    def _apply_native_chrome(self) -> None:
        try:
            hwnd = int(self.winId())
        except (TypeError, ValueError):
            return
        configure_overlay_window_chrome(hwnd, self._editor_mode)

    def reload_from_config(self) -> None:
        self._manual_visible = read_value(GAME_OVERLAY_SECTION, "visible", "false").lower() == "true"
        self.reload_geometry_from_config()
        self.reload_style_from_config()

    def reload_geometry_from_config(self) -> None:
        x = int(read_value(GAME_OVERLAY_SECTION, "x", "320"))
        y = int(read_value(GAME_OVERLAY_SECTION, "y", "820"))
        width = max(320, int(read_value(GAME_OVERLAY_SECTION, "width", "900")))
        height = max(80, int(read_value(GAME_OVERLAY_SECTION, "height", "120")))
        self.setGeometry(x, y, width, height)

    def reload_style_from_config(self) -> None:
        font_size = max(12, min(96, int(read_value(GAME_OVERLAY_SECTION, "font_size", "28"))))
        text_opacity = self._read_opacity("text_opacity", 1.0)
        outline_opacity = self._read_opacity("outline_opacity", 0.7)
        background_opacity = self._read_opacity("background_opacity", 0.7)
        overlay_opacity = self._read_opacity("overlay_opacity", 1.0)
        use_text_background = read_value(GAME_OVERLAY_SECTION, "use_text_background", "false").lower() == "true"
        self._base_overlay_opacity = overlay_opacity

        self.display_widget.set_text(self._display_text)
        self.display_widget.set_style(
                OverlayStyle(
                    font_size=font_size,
                    text_opacity=text_opacity,
                    outline_opacity=outline_opacity,
                    background_opacity=background_opacity,
                    overlay_opacity=overlay_opacity,
                    use_text_background=use_text_background,
            )
        )
        self.setWindowOpacity(self._base_overlay_opacity)
        self.update()

    def _read_opacity(self, key: str, fallback: float) -> float:
        raw_value = read_value(GAME_OVERLAY_SECTION, key, str(fallback))
        try:
            value = float(raw_value)
        except ValueError:
            value = fallback
        return max(0.0, min(1.0, value))

    def persist_state(self, visible: bool | None = None) -> None:
        if visible is None:
            visible = self._manual_visible
        update_section(
            GAME_OVERLAY_SECTION,
            {
                "visible": str(visible).lower(),
                "x": self.x(),
                "y": self.y(),
                "width": self.width(),
                "height": self.height(),
            },
        )

    def toggle_visibility(self) -> bool:
        if not self._manual_visible:
            self._manual_visible = True
            self._auto_hidden = False
            self._cancel_fade_out()
            self.reload_geometry_from_config()
            self.persist_state(True)
            self.setWindowOpacity(self._base_overlay_opacity)
            self.show()
            self.raise_()
            self._restart_auto_hide_timer()
            return True

        if self._auto_hidden and not self.isVisible():
            self._auto_hidden = False
            self._cancel_fade_out()
            self.reload_geometry_from_config()
            self.setWindowOpacity(self._base_overlay_opacity)
            self.show()
            self.raise_()
            self._restart_auto_hide_timer()
            return True

        self._manual_visible = False
        self._auto_hidden = False
        self._cancel_fade_out()
        self._auto_hide_timer.stop()
        self.persist_state(False)
        self.hide()
        return False

    def show_from_saved_state(self) -> None:
        self.reload_from_config()
        if not self._manual_visible:
            return
        self._auto_hidden = False
        self._cancel_fade_out()
        self.setWindowOpacity(self._base_overlay_opacity)
        self.show()
        self.raise_()
        self._restart_auto_hide_timer()

    def show_for_editor(self) -> None:
        self._cancel_fade_out()
        self._auto_hide_timer.stop()
        if not self.isVisible():
            self.reload_geometry_from_config()
            self.setWindowOpacity(self._base_overlay_opacity)
            self.show()
            self.raise_()

    def restore_after_editor(self) -> None:
        if not self._manual_visible:
            self._cancel_fade_out()
            self.hide()
            return
        self._auto_hidden = False
        self._cancel_fade_out()
        if not self.isVisible():
            self.setWindowOpacity(self._base_overlay_opacity)
            self.show()
            self.raise_()
        self._restart_auto_hide_timer()

    def _read_auto_hide_seconds(self) -> float:
        raw_value = read_value(GAME_OVERLAY_SECTION, "auto_hide_seconds", "15").strip()
        try:
            seconds = float(raw_value)
        except ValueError:
            seconds = 15.0
        return max(0.0, seconds)

    def _restart_auto_hide_timer(self) -> None:
        self._auto_hide_timer.stop()
        self._fade_out_timer.stop()
        if self._editor_mode or not self._manual_visible:
            return
        seconds = self._read_auto_hide_seconds()
        if seconds <= 0:
            return
        self._current_fade_duration_ms = max(1, min(self.FADE_OUT_DURATION_MS, int(seconds * 1000)))
        self._fade_animation.setDuration(self._current_fade_duration_ms)
        fade_start_seconds = max(0.0, seconds - (self._current_fade_duration_ms / 1000.0))
        self._fade_out_timer.start(int(fade_start_seconds * 1000))
        self._auto_hide_timer.start(int(seconds * 1000))

    def _handle_auto_hide_timeout(self) -> None:
        if self._editor_mode or not self._manual_visible or not self.isVisible():
            return
        if self._fade_animation.state() == QAbstractAnimation.State.Running:
            self._fade_animation.stop()
        self._auto_hidden = True
        self.hide()
        self.setWindowOpacity(self._base_overlay_opacity)

    def _start_fade_out(self) -> None:
        if self._editor_mode or not self._manual_visible or not self.isVisible():
            return
        self._fade_animation.stop()
        self._fade_animation.setStartValue(self._base_overlay_opacity)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.start()

    def _finish_fade_out(self) -> None:
        if self._fade_animation.state() == QAbstractAnimation.State.Running:
            return
        if self._editor_mode or not self._manual_visible or self._auto_hidden:
            return
        self._auto_hidden = True
        self.hide()
        self.setWindowOpacity(self._base_overlay_opacity)

    def _cancel_fade_out(self) -> None:
        self._fade_out_timer.stop()
        if self._fade_animation.state() == QAbstractAnimation.State.Running:
            self._fade_animation.stop()
        self.setWindowOpacity(self._base_overlay_opacity)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if not self._editor_mode:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(80, 160, 255, 220), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 10, 10)

    def _hit_test_edges(self, pos: QPoint) -> set[str]:
        rect = self.rect()
        edges: set[str] = set()
        if pos.x() <= RESIZE_MARGIN:
            edges.add("left")
        elif pos.x() >= rect.width() - RESIZE_MARGIN:
            edges.add("right")
        if pos.y() <= RESIZE_MARGIN:
            edges.add("top")
        elif pos.y() >= rect.height() - RESIZE_MARGIN:
            edges.add("bottom")
        return edges

    def _cursor_for_edges(self, edges: set[str]) -> Qt.CursorShape:
        if {"top", "left"} == edges or {"bottom", "right"} == edges:
            return Qt.CursorShape.SizeFDiagCursor
        if {"top", "right"} == edges or {"bottom", "left"} == edges:
            return Qt.CursorShape.SizeBDiagCursor
        if "left" in edges or "right" in edges:
            return Qt.CursorShape.SizeHorCursor
        if "top" in edges or "bottom" in edges:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.SizeAllCursor if self._editor_mode else Qt.CursorShape.ArrowCursor

    def _update_cursor(self, pos: QPoint | None = None) -> None:
        if not self._editor_mode:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        edges = self._hit_test_edges(pos or self.mapFromGlobal(self.cursor().pos()))
        self.setCursor(self._cursor_for_edges(edges))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self._editor_mode or event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        self._dragging = True
        self._resize_edges = self._hit_test_edges(event.position().toPoint())
        self._drag_start_global = event.globalPosition().toPoint()
        self._drag_start_geometry = self.geometry()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._editor_mode:
            return super().mouseMoveEvent(event)

        local_pos = event.position().toPoint()
        if not self._dragging:
            self._update_cursor(local_pos)
            return

        delta = event.globalPosition().toPoint() - self._drag_start_global
        new_geometry = QRect(self._drag_start_geometry)

        if self._resize_edges:
            minimum_width = max(320, self.minimumWidth())
            minimum_height = max(80, self.minimumHeight())
            if "left" in self._resize_edges:
                new_left = min(new_geometry.right() - minimum_width, self._drag_start_geometry.left() + delta.x())
                new_geometry.setLeft(new_left)
            if "right" in self._resize_edges:
                new_geometry.setRight(max(new_geometry.left() + minimum_width, self._drag_start_geometry.right() + delta.x()))
            if "top" in self._resize_edges:
                new_top = min(new_geometry.bottom() - minimum_height, self._drag_start_geometry.top() + delta.y())
                new_geometry.setTop(new_top)
            if "bottom" in self._resize_edges:
                new_geometry.setBottom(max(new_geometry.top() + minimum_height, self._drag_start_geometry.bottom() + delta.y()))
        else:
            new_geometry.moveTopLeft(self._drag_start_geometry.topLeft() + delta)

        self.setGeometry(new_geometry)
        self.persist_state(True)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._editor_mode and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._resize_edges = set()
            self.persist_state(True)
            self._update_cursor(event.position().toPoint())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._apply_native_chrome()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        if self._editor_mode and self.isVisible():
            self.persist_state(self._manual_visible)
        super().resizeEvent(event)

    def moveEvent(self, event) -> None:
        if self._editor_mode and self.isVisible():
            self.persist_state(self._manual_visible)
        super().moveEvent(event)

    def closeEvent(self, event) -> None:
        visible = self._shutdown_restore_open if self._shutdown_in_progress else False
        self.persist_state(visible)
        super().closeEvent(event)
