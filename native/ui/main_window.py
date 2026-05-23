from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QFrame
from PySide6.QtCore import Qt

from native.config.service import read_value, update_section
from native.ui.log_window import LogWindow
from native.ui.preview_window import PreviewWindow


class MainWindow(QMainWindow):
    def __init__(self, log_window: LogWindow, preview_window: PreviewWindow, overlay_window: QWidget | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Game2Text Control")
        
        self.log_win = log_window
        self.preview_win = preview_window
        self.overlay_win = overlay_window
        
        # UI Elements
        self.central_widget = QWidget()
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(0)
        self.setCentralWidget(self.central_widget)

        # Status Block
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(72)
        self.status_label.setMaximumHeight(72)
        self.status_label.setStyleSheet("padding: 8px 4px;")
        self.layout.addWidget(self.status_label)
        self.layout.addSpacing(8)
        self.layout.addWidget(self._create_separator())
        self.layout.addSpacing(12)

        # Capture / Border Block
        self.btn_capture = QPushButton("Capture Now")
        self.btn_toggle_border = QPushButton("Toggle Border Show/Hide")
        self.layout.addWidget(self._create_button_block([self.btn_capture, self.btn_toggle_border]))
        self.layout.addStretch(1)
        self.layout.addWidget(self._create_separator())
        self.layout.addSpacing(12)

        # Region Selection Block
        self.btn_select_region = QPushButton("Select Region")
        self.layout.addWidget(self._create_button_block([self.btn_select_region]))
        self.layout.addStretch(1)
        self.layout.addWidget(self._create_separator())
        self.layout.addSpacing(12)

        # Window Toggles
        self.btn_toggle_log = QPushButton("Open Log Window")
        self.btn_toggle_preview = QPushButton("Open Preview Window")
        self.layout.addWidget(self._create_button_block([self.btn_toggle_log, self.btn_toggle_preview]))
        self.layout.addStretch(1)
        self.layout.addWidget(self._create_separator())
        self.layout.addSpacing(12)

        # Future Overlay Block
        self.btn_toggle_game_overlay = QPushButton("Show/Hide Game Overlay")
        self.btn_game_overlay_editor = QPushButton("Game Overlay Editor")
        self.layout.addWidget(self._create_button_block([self.btn_toggle_game_overlay, self.btn_game_overlay_editor]))
        self.layout.addStretch(1)
        self.layout.addWidget(self._create_separator())
        self.layout.addSpacing(12)

        # Config Block
        self.btn_open_config = QPushButton("Open Config")
        self.btn_reload_config = QPushButton("Reload Config")
        self.layout.addWidget(self._create_button_block([self.btn_open_config, self.btn_reload_config]))
        
        # Restore Main Window Position
        x = int(read_value("NATIVEAPP", "main_window_x", "100"))
        y = int(read_value("NATIVEAPP", "main_window_y", "100"))
        w = int(read_value("NATIVEAPP", "main_window_width", "420"))
        h = int(read_value("NATIVEAPP", "main_window_height", "360"))
        self.setGeometry(x, y, w, h)

    def _create_separator(self) -> QFrame:
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #3a3a3a;")
        return separator

    def _create_button_block(self, buttons: list[QPushButton]) -> QWidget:
        block = QWidget()
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(8)
        for button in buttons:
            block_layout.addWidget(button)
        return block

    def update_hotkey_labels(
        self,
        *,
        capture_hotkey: str,
        select_hotkey: str,
        toggle_borders_hotkey: str,
        toggle_game_overlay_hotkey: str,
    ) -> None:
        self.btn_capture.setText(self._format_button_text("Capture Now", capture_hotkey))
        self.btn_select_region.setText(self._format_button_text("Select Region", select_hotkey))
        self.btn_toggle_border.setText(self._format_button_text("Toggle Border Show/Hide", toggle_borders_hotkey))
        self.btn_toggle_game_overlay.setText(
            self._format_button_text("Show/Hide Game Overlay", toggle_game_overlay_hotkey)
        )

    @staticmethod
    def _format_button_text(label: str, hotkey: str) -> str:
        normalized = hotkey.strip()
        if not normalized:
            return label
        pretty_hotkey = "+".join(part.capitalize() for part in normalized.split("+"))
        return f"{label} ({pretty_hotkey})"

    def closeEvent(self, event) -> None:
        log_open = not self.log_win.isHidden()
        preview_open = not self.preview_win.isHidden()
        overlay_open = bool(
            self.overlay_win
            and getattr(self.overlay_win, "manual_visible", not self.overlay_win.isHidden())
        )
        self.log_win.prepare_for_app_shutdown(log_open)
        self.preview_win.prepare_for_app_shutdown(preview_open)
        if self.overlay_win and hasattr(self.overlay_win, "prepare_for_app_shutdown"):
            self.overlay_win.prepare_for_app_shutdown(overlay_open)
        update_section("NATIVEAPP", {
            "main_window_open": "true",
            "main_window_width": str(self.width()),
            "main_window_height": str(self.height()),
            "main_window_x": str(self.x()),
            "main_window_y": str(self.y()),
            "log_window_open": str(log_open).lower(),
            "preview_window_open": str(preview_open).lower(),
        })
        self.log_win.close()
        self.preview_win.close()
        if self.overlay_win:
            self.overlay_win.close()
        super().closeEvent(event)
