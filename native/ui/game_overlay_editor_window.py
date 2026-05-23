from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from native.config.service import GAME_OVERLAY_SECTION, read_value, update_section
from native.ui.game_overlay_window import GameOverlayWindow


class GameOverlayEditorWindow(QWidget):
    def __init__(self, overlay_window: GameOverlayWindow, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.overlay_window = overlay_window
        self._suppress_events = False

        self.setWindowTitle("Game Overlay Editor")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(360, 260)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        info_label = QLabel("Mo editor de keo va resize cua so overlay truc tiep tren man hinh.")
        info_label.setWordWrap(True)
        root_layout.addWidget(info_label)

        self.font_size_label = QLabel()
        self.font_size_slider = self._create_slider(12, 96)
        root_layout.addLayout(self._create_row("Font Size", self.font_size_label, self.font_size_slider))

        self.overlay_opacity_label = QLabel()
        self.overlay_opacity_slider = self._create_slider(10, 100)
        root_layout.addLayout(self._create_row("Overlay Opacity", self.overlay_opacity_label, self.overlay_opacity_slider))

        self.text_opacity_label = QLabel()
        self.text_opacity_slider = self._create_slider(0, 100)
        root_layout.addLayout(self._create_row("Text Opacity", self.text_opacity_label, self.text_opacity_slider))

        self.outline_opacity_label = QLabel()
        self.outline_opacity_slider = self._create_slider(0, 100)
        root_layout.addLayout(self._create_row("Outline Opacity", self.outline_opacity_label, self.outline_opacity_slider))

        self.chk_text_background = QCheckBox("Use Text Background")
        root_layout.addWidget(self.chk_text_background)

        self.background_opacity_label = QLabel()
        self.background_opacity_slider = self._create_slider(0, 100)
        root_layout.addLayout(self._create_row("Background Opacity", self.background_opacity_label, self.background_opacity_slider))

        self.btn_done = QPushButton("Done")
        root_layout.addStretch()
        root_layout.addWidget(self.btn_done)

        self.font_size_slider.valueChanged.connect(self._on_controls_changed)
        self.overlay_opacity_slider.valueChanged.connect(self._on_controls_changed)
        self.text_opacity_slider.valueChanged.connect(self._on_controls_changed)
        self.outline_opacity_slider.valueChanged.connect(self._on_controls_changed)
        self.background_opacity_slider.valueChanged.connect(self._on_controls_changed)
        self.chk_text_background.toggled.connect(self._on_controls_changed)
        self.btn_done.clicked.connect(self.close)

        self.reload_from_config()

    def _create_slider(self, minimum: int, maximum: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(minimum, maximum)
        return slider

    def _create_row(self, title: str, value_label: QLabel, slider: QSlider) -> QVBoxLayout:
        layout = QVBoxLayout()
        header = QHBoxLayout()
        title_label = QLabel(title)
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(title_label)
        header.addStretch()
        header.addWidget(value_label)
        layout.addLayout(header)
        layout.addWidget(slider)
        return layout

    def reload_from_config(self) -> None:
        self._suppress_events = True
        font_size = int(read_value(GAME_OVERLAY_SECTION, "font_size", "28"))
        overlay_opacity = self._read_slider_value("overlay_opacity", 1.0, minimum=10)
        text_opacity = self._read_slider_value("text_opacity", 1.0)
        outline_opacity = self._read_slider_value("outline_opacity", 0.7)
        background_opacity = self._read_slider_value("background_opacity", 0.7)
        use_text_background = read_value(GAME_OVERLAY_SECTION, "use_text_background", "false").lower() == "true"

        self.font_size_slider.setValue(font_size)
        self.overlay_opacity_slider.setValue(overlay_opacity)
        self.text_opacity_slider.setValue(text_opacity)
        self.outline_opacity_slider.setValue(outline_opacity)
        self.chk_text_background.setChecked(use_text_background)
        self.background_opacity_slider.setValue(background_opacity)
        self.background_opacity_slider.setEnabled(use_text_background)
        self._refresh_value_labels()
        self._suppress_events = False

    def _read_slider_value(self, key: str, fallback: float, minimum: int = 0) -> int:
        raw_value = read_value(GAME_OVERLAY_SECTION, key, str(fallback))
        try:
            value = float(raw_value)
        except ValueError:
            value = fallback
        value = max(0.0, min(1.0, value))
        return max(minimum, int(round(value * 100)))

    def _refresh_value_labels(self) -> None:
        self.font_size_label.setText(f"{self.font_size_slider.value()} px")
        self.overlay_opacity_label.setText(f"{self.overlay_opacity_slider.value()}%")
        self.text_opacity_label.setText(f"{self.text_opacity_slider.value()}%")
        self.outline_opacity_label.setText(f"{self.outline_opacity_slider.value()}%")
        self.background_opacity_label.setText(f"{self.background_opacity_slider.value()}%")

    def _on_controls_changed(self, *_args) -> None:
        self._refresh_value_labels()
        if self._suppress_events:
            return
        use_text_background = self.chk_text_background.isChecked()
        self.background_opacity_slider.setEnabled(use_text_background)
        update_section(
            GAME_OVERLAY_SECTION,
            {
                "font_size": self.font_size_slider.value(),
                "overlay_opacity": f"{self.overlay_opacity_slider.value() / 100:.2f}",
                "text_opacity": f"{self.text_opacity_slider.value() / 100:.2f}",
                "outline_opacity": f"{self.outline_opacity_slider.value() / 100:.2f}",
                "background_opacity": f"{self.background_opacity_slider.value() / 100:.2f}",
                "use_text_background": str(use_text_background).lower(),
            },
        )
        self.overlay_window.reload_style_from_config()

    def showEvent(self, event) -> None:
        self.reload_from_config()
        self.overlay_window.reload_style_from_config()
        self.overlay_window.show_for_editor()
        self.overlay_window.set_editor_mode(True)
        super().showEvent(event)

    def closeEvent(self, event) -> None:
        self.overlay_window.set_editor_mode(False)
        self.overlay_window.reload_style_from_config()
        self.overlay_window.restore_after_editor()
        super().closeEvent(event)
