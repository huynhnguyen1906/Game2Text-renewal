from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QScrollArea, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, QTimer, QRect

from native.config.service import read_value, update_section
from native.ui.log_row_widget import LogRowWidget
from native.app.event_bus import global_bus
from native.core.models import LogEntry


MIN_LOG_FONT_SIZE = 14
MAX_LOG_FONT_SIZE = 36


class LogWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Game2Text Log")
        self.setStyleSheet("background-color: #2b2b2b; color: white;")
        self._shutdown_in_progress = False
        self._shutdown_restore_open = False
        self.log_font_size = self._load_initial_font_size()
        
        always_on_top = read_value("NATIVEAPP", "log_always_on_top", "true").lower() == "true"
        if always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
             
        # Layout
        self.central_widget = QWidget()
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.setCentralWidget(self.central_widget)

        # Top Control Bar
        self.toolbar_widget = QWidget()
        self.toolbar_widget.setStyleSheet("background-color: #1e1e1e; border-bottom: 1px solid #444;")
        self.toolbar_layout = QHBoxLayout(self.toolbar_widget)
        self.toolbar_layout.setContentsMargins(10, 8, 10, 8)
        self.toolbar_layout.setSpacing(8)

        self.font_label = QLabel("Font")
        self.font_label.setStyleSheet("color: #ddd; font-weight: bold;")
        self.font_size_value = QLabel("")
        self.font_size_value.setStyleSheet("color: #aaa; min-width: 42px;")
        self.btn_font_decrease = QPushButton("-")
        self.btn_font_increase = QPushButton("+")

        for button in (self.btn_font_decrease, self.btn_font_increase):
            button.setFixedSize(28, 28)
            button.setStyleSheet(
                "QPushButton { background-color: #333; color: white; border: 1px solid #555; }"
                "QPushButton:hover { background-color: #444; }"
            )

        self.toolbar_layout.addWidget(self.font_label)
        self.toolbar_layout.addWidget(self.btn_font_decrease)
        self.toolbar_layout.addWidget(self.btn_font_increase)
        self.toolbar_layout.addWidget(self.font_size_value)
        self.toolbar_layout.addStretch()
        self.layout.addWidget(self.toolbar_widget)
         
        # Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll_layout.setSpacing(8)
         
        self.scroll_area.setWidget(self.scroll_content)
        self.layout.addWidget(self.scroll_area)
         
        self.rows: dict[str, LogRowWidget] = {}
        
        # Connect Bus
        global_bus.log_entry_created.connect(self.on_log_created)
        global_bus.log_entry_updated.connect(self.on_log_updated)
        self.btn_font_decrease.clicked.connect(lambda: self.adjust_font_size(-1))
        self.btn_font_increase.clicked.connect(lambda: self.adjust_font_size(1))
        self.update_font_size_label()
        
        # Restore geometry
        x = int(read_value("NATIVEAPP", "log_window_x", "1200"))
        y = int(read_value("NATIVEAPP", "log_window_y", "120"))
        w = int(read_value("NATIVEAPP", "log_window_width", "400"))
        h = int(read_value("NATIVEAPP", "log_window_height", "600"))
        self.setGeometry(x, y, w, h)
        self._persisted_geometry = QRect(self.geometry())

    def _load_initial_font_size(self) -> int:
        raw_value = read_value("NATIVEAPP", "log_font_size", read_value("APPEARANCE", "fontsize", "23"))
        try:
            font_size = int(raw_value)
        except ValueError:
            font_size = 23
        return max(MIN_LOG_FONT_SIZE, min(MAX_LOG_FONT_SIZE, font_size))

    def prepare_for_app_shutdown(self, restore_open: bool) -> None:
        self._shutdown_in_progress = True
        self._shutdown_restore_open = restore_open

    def _capture_persistable_geometry(self) -> None:
        rect = self.normalGeometry() if self.isMaximized() else self.geometry()
        if rect.width() > 0 and rect.height() > 0:
            self._persisted_geometry = QRect(rect)

    def persist_state(self, open_state: bool | None = None) -> None:
        if open_state is None:
            open_state = self.isVisible()
        self._capture_persistable_geometry()
        update_section("NATIVEAPP", {
            "log_window_open": str(open_state).lower(),
            "log_window_width": str(self._persisted_geometry.width()),
            "log_window_height": str(self._persisted_geometry.height()),
            "log_window_x": str(self._persisted_geometry.x()),
            "log_window_y": str(self._persisted_geometry.y()),
            "log_font_size": str(self.log_font_size),
        })

    def update_font_size_label(self) -> None:
        self.font_size_value.setText(f"{self.log_font_size}px")
        self.btn_font_decrease.setEnabled(self.log_font_size > MIN_LOG_FONT_SIZE)
        self.btn_font_increase.setEnabled(self.log_font_size < MAX_LOG_FONT_SIZE)

    def adjust_font_size(self, delta: int) -> None:
        new_size = max(MIN_LOG_FONT_SIZE, min(MAX_LOG_FONT_SIZE, self.log_font_size + delta))
        if new_size == self.log_font_size:
            return
        self.log_font_size = new_size
        for row in self.rows.values():
            row.set_font_size(self.log_font_size)
        self.update_font_size_label()
        self.persist_state()
        self.scroll_to_bottom()

    def _set_scrollbar_to_bottom(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def scroll_to_bottom(self) -> None:
        # Run twice because translation updates can change row height after the
        # first layout pass, especially for long wrapped text.
        QTimer.singleShot(0, self._set_scrollbar_to_bottom)
        QTimer.singleShot(60, self._set_scrollbar_to_bottom)

    def on_log_created(self, entry: LogEntry) -> None:
        row = LogRowWidget(entry.id, entry.source_text, font_size=self.log_font_size)
        self.rows[entry.id] = row
        self.scroll_layout.addWidget(row)
        self.scroll_to_bottom()
         
        if entry.translation_status != "idle" and entry.translation_status != "pending":
            row.update_state({
                "translation_status": entry.translation_status,
                "translated_text": entry.translated_text,
                "translation_error": entry.translation_error
            })

    def on_log_updated(self, log_id: str, patch: dict[str, object]) -> None:
        row = self.rows.get(log_id)
        if row:
            row.update_state(patch)
            self.scroll_to_bottom()

    def showEvent(self, event) -> None:
        self._capture_persistable_geometry()
        self.persist_state(True)
        super().showEvent(event)

    def moveEvent(self, event) -> None:
        self._capture_persistable_geometry()
        super().moveEvent(event)

    def resizeEvent(self, event) -> None:
        self._capture_persistable_geometry()
        super().resizeEvent(event)

    def hideEvent(self, event) -> None:
        if not self._shutdown_in_progress:
            self.persist_state(False)
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._capture_persistable_geometry()
        open_state = self._shutdown_restore_open if self._shutdown_in_progress else False
        self.persist_state(open_state)
        super().closeEvent(event)
