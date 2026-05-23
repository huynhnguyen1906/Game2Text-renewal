from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt

class LogRowWidget(QWidget):
    def __init__(self, log_id: str, source_text: str, font_size: int = 23, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_id = log_id
        self.font_size = font_size
        self._status_mode = "pending"
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        # Source Text
        self.source_label = QLabel(source_text)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.source_label.setWordWrap(True)
        self.source_label.setStyleSheet("color: white; font-weight: bold;")
        
        # Divider
        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.Shape.HLine)
        self.divider.setFrameShadow(QFrame.Shadow.Sunken)
        self.divider.setStyleSheet("background-color: #555;")
        
        # Translation/Status Text
        self.status_label = QLabel("Đang dịch...")
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #aaa;")
        
        self.layout.addWidget(self.source_label)
        self.layout.addWidget(self.divider)
        self.layout.addWidget(self.status_label)
        self.apply_styles()

    def set_font_size(self, font_size: int) -> None:
        self.font_size = font_size
        self.apply_styles()

    def apply_styles(self) -> None:
        source_style = f"color: white; font-weight: bold; font-size: {self.font_size}px;"
        status_style = f"color: #aaa; font-size: {self.font_size}px;"

        self.divider.show()
        self.status_label.show()

        if self._status_mode == "done":
            status_style = f"color: #d8b4e2; font-style: italic; font-size: {self.font_size}px;"
        elif self._status_mode in {"error", "queue_full"}:
            status_style = f"color: #ff6666; font-size: {self.font_size}px;"
        elif self._status_mode == "ocr_error":
            source_style = f"color: #ff6666; font-weight: bold; font-size: {self.font_size}px;"
            self.status_label.hide()
            self.divider.hide()

        self.source_label.setStyleSheet(source_style)
        self.status_label.setStyleSheet(status_style)
         
    def update_state(self, patch: dict[str, object]) -> None:
        status = patch.get("translation_status")
        
        if status == "done":
            self._status_mode = "done"
            translated_text = str(patch.get("translated_text", ""))
            self.status_label.setText(translated_text)
        elif status == "error":
            self._status_mode = "error"
            error_msg = str(patch.get("translation_error", "Lỗi dịch thuật"))
            self.status_label.setText(error_msg)
        elif status == "queue_full":
            self._status_mode = "queue_full"
            error_msg = str(patch.get("translation_error", "Queue full"))
            self.status_label.setText(error_msg)
        elif status == "ocr_error":
            self._status_mode = "ocr_error"
        elif status == "pending":
            self._status_mode = "pending"
            self.status_label.setText("Đang dịch...")
        self.apply_styles()
