from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from native.config.service import read_value, update_section
from native.ui.log_window import LogWindow
from native.ui.preview_window import PreviewWindow


class MainWindow(QMainWindow):
    LANGUAGE_OPTIONS = [
        "en",
        "vi",
        "ja",
        "zh",
        "ko",
        "fr",
        "de",
        "es",
        "it",
        "pt",
        "ru",
        "th",
        "id",
        "ar",
        "tr",
    ]

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
        self.status_label.setWordWrap(True)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setStyleSheet("padding: 8px 10px;")
        self.layout.addWidget(self._create_status_block())
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

    def _create_status_block(self) -> QWidget:
        block = QWidget()
        block.setMinimumHeight(96)
        block.setMaximumHeight(96)

        block_layout = QHBoxLayout(block)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(0)

        left_panel = QWidget()
        left_layout = QGridLayout(left_panel)
        left_layout.setContentsMargins(10, 8, 10, 8)
        left_layout.setHorizontalSpacing(12)
        left_layout.setVerticalSpacing(10)

        source_label = QLabel("Source lang")
        target_label = QLabel("Target lang")
        self.source_lang_combo = QComboBox()
        self.target_lang_combo = QComboBox()
        for combo in (self.source_lang_combo, self.target_lang_combo):
            combo.addItems(self.LANGUAGE_OPTIONS)
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        left_layout.addWidget(source_label, 0, 0)
        left_layout.addWidget(self.source_lang_combo, 0, 1)
        left_layout.addWidget(target_label, 1, 0)
        left_layout.addWidget(self.target_lang_combo, 1, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 8, 10, 8)
        right_layout.addWidget(self.status_label)

        block_layout.addWidget(left_panel, 1)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("color: #3a3a3a;")
        block_layout.addWidget(divider)
        block_layout.addWidget(right_panel, 1)
        return block

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

    def sync_translation_language_selectors(self, source_lang: str, target_lang: str) -> None:
        self._set_combo_value(self.source_lang_combo, source_lang)
        self._set_combo_value(self.target_lang_combo, target_lang)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        normalized = value.strip().lower()
        if not normalized:
            return
        index = combo.findText(normalized, Qt.MatchFlag.MatchFixedString)
        if index < 0:
            combo.addItem(normalized)
            index = combo.findText(normalized, Qt.MatchFlag.MatchFixedString)
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

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
