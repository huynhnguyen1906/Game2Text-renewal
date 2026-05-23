from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QSlider, QComboBox, QPushButton, QHBoxLayout, QFileDialog
from PySide6.QtCore import Qt, Signal

from native.config.service import load_filter_config, save_filter_config
from native.core import paths
from native.core.models import FilterConfig
from native.filters.profiles import export_profile, import_profile, load_profiles

class FilterPanel(QWidget):
    config_changed = Signal(object)
    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._suppress_events = False
        self._loaded_profiles: dict[str, FilterConfig] = {}
        self.layout = QVBoxLayout(self)
        
        # Profiles
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.btn_import = QPushButton("Import")
        self.btn_export = QPushButton("Export")
        self.btn_reset = QPushButton("Reset")
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addWidget(self.btn_import)
        profile_layout.addWidget(self.btn_export)
        profile_layout.addWidget(self.btn_reset)
        
        # Binarize
        binarize_layout = QHBoxLayout()
        self.chk_binarize = QCheckBox("Binarize")
        self.slider_threshold = QSlider(Qt.Orientation.Horizontal)
        self.slider_threshold.setRange(0, 100)
        self.slider_threshold.setValue(50)
        self.slider_threshold.setEnabled(False)
        binarize_layout.addWidget(self.chk_binarize)
        binarize_layout.addWidget(self.slider_threshold)
        
        self.chk_binarize.toggled.connect(self.slider_threshold.setEnabled)
        
        # Blur
        blur_layout = QHBoxLayout()
        blur_layout.addWidget(QLabel("Gaussian Blur"))
        self.slider_blur = QSlider(Qt.Orientation.Horizontal)
        self.slider_blur.setRange(0, 100)
        self.slider_blur.setValue(0)
        blur_layout.addWidget(self.slider_blur)
        
        # Toggles
        self.chk_dilate = QCheckBox("Dilate")
        self.chk_invert = QCheckBox("Invert Color")
        
        self.layout.addLayout(profile_layout)
        self.layout.addLayout(binarize_layout)
        self.layout.addLayout(blur_layout)
        self.layout.addWidget(self.chk_dilate)
        self.layout.addWidget(self.chk_invert)
        self.layout.addStretch()

        self.profile_combo.currentTextChanged.connect(self.on_profile_selected)
        self.chk_binarize.toggled.connect(self.on_control_changed)
        self.slider_threshold.valueChanged.connect(self.on_control_changed)
        self.slider_blur.valueChanged.connect(self.on_control_changed)
        self.chk_dilate.toggled.connect(self.on_control_changed)
        self.chk_invert.toggled.connect(self.on_control_changed)
        self.btn_import.clicked.connect(self.import_profile_from_dialog)
        self.btn_export.clicked.connect(self.export_current_profile)
        self.btn_reset.clicked.connect(self.refresh_requested.emit)

        self.reload_from_config()

    def reload_from_config(self) -> None:
        self._suppress_events = True
        self.profile_combo.clear()
        self.profile_combo.addItem("(Custom)")
        self._loaded_profiles.clear()

        current_config = load_filter_config()
        profiles = sorted(load_profiles(paths.profiles_dir()), key=lambda item: str(item.get("name", "")).lower())
        for profile in profiles:
            name = str(profile.get("name", "")).strip()
            if name:
                self.profile_combo.addItem(name)
                self._loaded_profiles[name] = import_profile(paths.profiles_dir() / f"{name}.yaml")

        self.set_filter_config(current_config)
        self._suppress_events = False

    def current_filter_config(self) -> FilterConfig:
        active_profile = self.profile_combo.currentText()
        if active_profile == "(Custom)":
            active_profile = ""
        return FilterConfig(
            invertColor=self.chk_invert.isChecked(),
            dilate=self.chk_dilate.isChecked(),
            blurImageRadius=self.slider_blur.value(),
            binarizeThreshold=self.slider_threshold.value() if self.chk_binarize.isChecked() else None,
            activeProfile=active_profile,
        )

    def set_filter_config(self, config: FilterConfig) -> None:
        self.chk_binarize.setChecked(config.is_binarize_enabled)
        self.slider_threshold.setValue(config.binarizeThreshold if config.binarizeThreshold is not None else 50)
        self.slider_threshold.setEnabled(config.is_binarize_enabled)
        self.slider_blur.setValue(config.blurImageRadius)
        self.chk_dilate.setChecked(config.dilate)
        self.chk_invert.setChecked(config.invertColor)

        if config.activeProfile:
            index = self.profile_combo.findText(config.activeProfile)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
            else:
                self.profile_combo.addItem(config.activeProfile)
                self.profile_combo.setCurrentIndex(self.profile_combo.count() - 1)
        else:
            self.profile_combo.setCurrentIndex(0)

    def on_profile_selected(self, profile_name: str) -> None:
        if self._suppress_events:
            return
        profile_name = profile_name.strip()
        if not profile_name or profile_name == "(Custom)":
            config = self.current_filter_config()
            config.activeProfile = ""
            save_filter_config(config)
            self.config_changed.emit(config)
            return

        config = self._loaded_profiles.get(profile_name)
        if not config:
            return

        self._suppress_events = True
        applied = FilterConfig(
            invertColor=config.invertColor,
            dilate=config.dilate,
            blurImageRadius=config.blurImageRadius,
            binarizeThreshold=config.binarizeThreshold,
            activeProfile=profile_name,
        )
        self.set_filter_config(applied)
        self._suppress_events = False
        save_filter_config(applied)
        self.config_changed.emit(applied)

    def on_control_changed(self, *_args) -> None:
        if self._suppress_events:
            return
        config = self.current_filter_config()
        if config.activeProfile and config.activeProfile in self._loaded_profiles:
            config.activeProfile = ""
            self._suppress_events = True
            self.profile_combo.setCurrentIndex(0)
            self._suppress_events = False
        save_filter_config(config)
        self.config_changed.emit(config)

    def import_profile_from_dialog(self) -> None:
        source_file, _ = QFileDialog.getOpenFileName(
            self,
            "Import Filter Profile",
            str(paths.profiles_dir()),
            "YAML Files (*.yaml *.yml)",
        )
        if not source_file:
            return

        source_path = Path(source_file)
        target_path = paths.profiles_dir() / source_path.name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() != target_path.resolve():
            shutil.copy2(source_path, target_path)

        config = import_profile(target_path)
        config.activeProfile = target_path.stem
        save_filter_config(config)
        self.reload_from_config()
        self.config_changed.emit(config)

    def export_current_profile(self) -> None:
        current_config = self.current_filter_config()
        suggested_name = current_config.activeProfile or "custom-filter"
        target_file, _ = QFileDialog.getSaveFileName(
            self,
            "Export Filter Profile",
            str(paths.profiles_dir() / f"{suggested_name}.yaml"),
            "YAML Files (*.yaml)",
        )
        if not target_file:
            return
        export_path = Path(target_file)
        export_profile(export_path, current_config)

        if export_path.parent.resolve() == paths.profiles_dir().resolve():
            updated_config = FilterConfig(
                invertColor=current_config.invertColor,
                dilate=current_config.dilate,
                blurImageRadius=current_config.blurImageRadius,
                binarizeThreshold=current_config.binarizeThreshold,
                activeProfile=export_path.stem,
            )
            save_filter_config(updated_config)
            self.reload_from_config()
            self.config_changed.emit(updated_config)
