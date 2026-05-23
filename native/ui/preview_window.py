from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from native.config.service import load_filter_config, read_value, update_section
from native.filters.service import apply_filters
from native.ui.filter_panel import FilterPanel
from native.app.event_bus import global_bus


class PreviewWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Filter & Preview")
        self._shutdown_in_progress = False
        self._shutdown_restore_open = False
        self._source_preview_image = None
        self._current_preview_qimage = None
        
        # Root
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QHBoxLayout(central_widget)
        
        # Preview Setup
        self.preview_label = QLabel("No preview image")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background-color: black; color: white;")
        self.preview_label.setMinimumSize(0, 0)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        
        self.layout.addWidget(self.preview_label, 2)
        
        # Controls
        self.filter_panel = FilterPanel()
        self.filter_panel.setMaximumWidth(320)
        self.filter_panel.setMinimumWidth(280)
        self.layout.addWidget(self.filter_panel, 1)

        global_bus.preview_image_updated.connect(self.on_preview_image_updated)
        self.filter_panel.config_changed.connect(self.on_filter_config_changed)
        self.filter_panel.refresh_requested.connect(self.render_preview)

        # Restore
        x = int(read_value("NATIVEAPP", "preview_window_x", "900"))
        y = int(read_value("NATIVEAPP", "preview_window_y", "120"))
        w = int(read_value("NATIVEAPP", "preview_window_width", "900"))
        h = int(read_value("NATIVEAPP", "preview_window_height", "700"))
        self.setGeometry(x, y, w, h)

    def prepare_for_app_shutdown(self, restore_open: bool) -> None:
        self._shutdown_in_progress = True
        self._shutdown_restore_open = restore_open

    def persist_state(self, open_state: bool | None = None) -> None:
        if open_state is None:
            open_state = self.isVisible()
        update_section("NATIVEAPP", {
            "preview_window_open": str(open_state).lower(),
            "preview_window_width": str(self.width()),
            "preview_window_height": str(self.height()),
            "preview_window_x": str(self.x()),
            "preview_window_y": str(self.y()),
        })

    def on_preview_image_updated(self, image) -> None:
        self._source_preview_image = image.copy()
        self.render_preview()

    def on_filter_config_changed(self, _config) -> None:
        self.render_preview()

    def render_preview(self) -> None:
        if self._source_preview_image is None:
            self.preview_label.setText("No preview image")
            self.preview_label.setPixmap(QPixmap())
            return
        filtered_image = apply_filters(self._source_preview_image.copy(), load_filter_config())
        rgba_image = filtered_image.convert("RGBA")
        raw_bytes = rgba_image.tobytes("raw", "RGBA")
        qimage = QImage(raw_bytes, rgba_image.width, rgba_image.height, rgba_image.width * 4, QImage.Format.Format_RGBA8888)
        self._current_preview_qimage = qimage.copy()
        if self._current_preview_qimage is None:
            return
        available_size = self.preview_label.contentsRect().size()
        if available_size.width() <= 0 or available_size.height() <= 0:
            return
        pixmap = QPixmap.fromImage(self._current_preview_qimage)
        scaled = pixmap.scaled(
            available_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def showEvent(self, event) -> None:
        self.persist_state(True)
        self.render_preview()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        if not self._shutdown_in_progress:
            self.persist_state(False)
        super().hideEvent(event)

    def resizeEvent(self, event) -> None:
        self.render_preview()
        super().resizeEvent(event)

    def closeEvent(self, event) -> None:
        open_state = self._shutdown_restore_open if self._shutdown_in_progress else False
        self.persist_state(open_state)
        super().closeEvent(event)
