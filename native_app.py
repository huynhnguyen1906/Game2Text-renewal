from __future__ import annotations

import os
import sys
import signal
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from native.core.dpi import enable_dpi_awareness, set_windows_app_user_model_id
from native.core import paths
from native.core.startup import initialize_runtime
from native.config.service import load_region, read_value, save_region, update_section
from native.core.models import ScreenRegion
from native.app.app_controller import global_controller
from native.app.event_bus import global_bus
from native.app.workers import global_workers

from native.ui.game_overlay_window import GameOverlayWindow
from native.ui.game_overlay_editor_window import GameOverlayEditorWindow
from native.ui.log_window import LogWindow
from native.ui.preview_window import PreviewWindow
from native.ui.main_window import MainWindow

from native.capture.screen_capture import capture_region
from native.regions.border import RegionBorder
from native.regions.overlay import SelectionOverlay
from native.hotkeys.service import setup_hotkeys, teardown_hotkeys


def _apply_runtime_icon(app: QApplication, *windows) -> None:
    icon_file = paths.icon_path()
    if not icon_file.exists():
        return
    app_icon = QIcon(str(icon_file))
    if app_icon.isNull():
        return
    app.setWindowIcon(app_icon)
    for window in windows:
        window.setWindowIcon(app_icon)


def main() -> int:
    # Keep Ctrl+C working in the terminal while the Qt event loop is running.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    set_windows_app_user_model_id()
    enable_dpi_awareness()
    initialize_runtime()
    
    app = QApplication(sys.argv)
    app.setApplicationName("Game2Text")
    app.setDesktopFileName("Game2Text.Native")
    
    log_win = LogWindow()
    preview_win = PreviewWindow()
    main_win = MainWindow(log_win, preview_win)
    game_overlay_win = GameOverlayWindow()
    game_overlay_editor_win = GameOverlayEditorWindow(game_overlay_win, main_win)
    main_win.overlay_win = game_overlay_win
    _apply_runtime_icon(app, main_win, log_win, preview_win, game_overlay_win, game_overlay_editor_win)
    
    if read_value("NATIVEAPP", "main_window_open", "true").lower() == "true":
        main_win.show()
    
    if read_value("NATIVEAPP", "log_window_open", "false").lower() == "true":
        log_win.show()
        
    if read_value("NATIVEAPP", "preview_window_open", "false").lower() == "true":
        preview_win.show()
        
    # ---------- Region & Capture logic ----------
    
    border_win = RegionBorder()
    overlay_win = None
    current_region = None
    last_toggle_borders_at = 0.0

    def apply_loaded_region(region: ScreenRegion | None) -> None:
        nonlocal current_region
        current_region = region
        if current_region and current_region.is_valid:
            border_win.set_region(current_region)
            main_win.status_label.setText(f"Loaded region {current_region.width}x{current_region.height}")
        else:
            border_win.set_region(None)
            main_win.status_label.setText("No region selected. (Ctrl+Shift+Q)")

    def reload_runtime_config() -> None:
        apply_loaded_region(load_region())
        region_for_hotkeys = current_region or ScreenRegion(
            id="1",
            label="Region 1",
            x=0,
            y=0,
            width=0,
            height=0,
            monitor=1,
        )
        show_borders_hotkey = read_value("NATIVEAPP", "show_borders_hotkey", "ctrl+shift+1")
        toggle_game_overlay_hotkey = read_value("GAMEOVERLAY", "toggle_hotkey", "ctrl+shift+2")
        source_lang = read_value("TRANSLATIONCONFIG", "source_lang", "en")
        target_lang = read_value("TRANSLATIONCONFIG", "target_lang", "vi")
        provider = read_value("TRANSLATIONCONFIG", "translation_service", "openai")
        model = read_value("TRANSLATIONCONFIG", "model", "gpt-4.1-nano")
        main_win.update_hotkey_labels(
            capture_hotkey=region_for_hotkeys.capture_hotkey,
            select_hotkey=region_for_hotkeys.select_hotkey,
            toggle_borders_hotkey=show_borders_hotkey,
            toggle_game_overlay_hotkey=toggle_game_overlay_hotkey,
        )
        main_win.sync_translation_settings(
            source_lang=source_lang,
            target_lang=target_lang,
            provider=provider,
            model=model,
        )
        setup_hotkeys(
            region_for_hotkeys.capture_hotkey,
            region_for_hotkeys.select_hotkey,
            show_borders_hotkey,
            toggle_game_overlay_hotkey,
        )
        preview_win.filter_panel.reload_from_config()
        game_overlay_win.reload_from_config()

    reload_runtime_config()
    if read_value("GAMEOVERLAY", "visible", "false").lower() == "true":
        game_overlay_win.show_from_saved_state()

    def do_select_region():
        nonlocal overlay_win
        if overlay_win is None:
            overlay_win = SelectionOverlay()
            overlay_win.region_selected.connect(on_region_selected)
        # Ensure it shows at the top covering everything
        overlay_win.show()
        overlay_win.raise_()
        overlay_win.activateWindow()
        
    def do_capture():
        if not current_region or not current_region.is_valid:
            main_win.status_label.setText("Error: Select a region first!")
            return
            
        border_win.hide()
        QApplication.processEvents() # Flush paint hide events
        
        try:
            img = capture_region(current_region)
            global_bus.preview_image_updated.emit(img)
            global_controller.process_captured_image(img, current_region.id)
            main_win.status_label.setText(f"Captured: {img.width}x{img.height}")
        except Exception as e:
            main_win.status_label.setText(f"Capture failed: {e}")
        finally:
            if current_region.show_region_border:
                border_win.show()

    def on_region_selected(region: ScreenRegion):
        if current_region:
            region.capture_hotkey = current_region.capture_hotkey
            region.select_hotkey = current_region.select_hotkey
            region.border_color = current_region.border_color
            region.show_region_border = current_region.show_region_border
        apply_loaded_region(region)
        save_region(region)
        main_win.status_label.setText(f"New region set: {region.width}x{region.height}")
        if preview_win.isVisible():
            refresh_preview_capture()

    def toggle_border():
        if current_region:
            current_region.show_region_border = not border_win.isVisible()
            save_region(current_region)
            border_win.set_region(current_region)
            if current_region.show_region_border:
                main_win.status_label.setText("Region border shown.")
            else:
                main_win.status_label.setText("Region border hidden.")

    def toggle_all_borders() -> None:
        nonlocal last_toggle_borders_at
        if not current_region or not current_region.is_valid:
            main_win.status_label.setText("No region selected.")
            return
        now = time.monotonic()
        if now - last_toggle_borders_at < 0.25:
            return
        last_toggle_borders_at = now
        current_region.show_region_border = not current_region.show_region_border
        save_region(current_region)
        border_win.set_region(current_region)
        if current_region.show_region_border:
            main_win.status_label.setText("All region borders shown.")
        else:
            main_win.status_label.setText("All region borders hidden.")

    def refresh_preview_capture() -> None:
        if not current_region or not current_region.is_valid:
            main_win.status_label.setText("Error: Select a region first!")
            return
        try:
            img = capture_region(current_region)
            global_bus.preview_image_updated.emit(img)
            main_win.status_label.setText(f"Preview refreshed: {img.width}x{img.height}")
        except Exception as e:
            main_win.status_label.setText(f"Preview refresh failed: {e}")

    def toggle_game_overlay() -> None:
        if game_overlay_editor_win.isVisible() and game_overlay_win.isVisible():
            game_overlay_editor_win.close()
        is_visible = game_overlay_win.toggle_visibility()
        if is_visible:
            main_win.status_label.setText("Game overlay shown.")
        else:
            main_win.status_label.setText("Game overlay hidden.")

    def toggle_game_overlay_editor() -> None:
        if game_overlay_editor_win.isVisible():
            game_overlay_editor_win.close()
            main_win.status_label.setText("Game overlay editor closed.")
        else:
            game_overlay_editor_win.show()
            main_win.status_label.setText("Game overlay editor opened.")

    global_bus.trigger_capture.connect(do_capture)
    global_bus.trigger_select_region.connect(do_select_region)
    global_bus.trigger_show_borders.connect(toggle_all_borders)
    global_bus.trigger_toggle_game_overlay.connect(toggle_game_overlay)
    global_bus.overlay_text_updated.connect(game_overlay_win.handle_new_translation)
    global_bus.status_changed.connect(main_win.status_label.setText)
    global_bus.capture_failed.connect(lambda message: main_win.status_label.setText(f"Capture/OCR failed: {message}"))

    main_win.btn_capture.clicked.connect(do_capture)
    # Map selection button directly via global bus or connected slot
    main_win.btn_select_region.clicked.connect(do_select_region)
    main_win.btn_toggle_border.clicked.connect(toggle_border)

    def toggle_log_window() -> None:
        if log_win.isHidden():
            log_win.show()
        else:
            log_win.hide()

    def toggle_preview_window() -> None:
        if preview_win.isHidden():
            preview_win.show()
            refresh_preview_capture()
        else:
            preview_win.hide()

    def open_config_file() -> None:
        config_file = paths.config_path()
        if config_file.exists():
            os.startfile(str(config_file))
            main_win.status_label.setText(f"Opened config: {config_file.name}")
        else:
            main_win.status_label.setText("Config file not found.")

    def on_source_lang_changed(value: str) -> None:
        normalized = value.strip().lower()
        update_section("TRANSLATIONCONFIG", {"source_lang": normalized})
        reload_runtime_config()
        main_win.status_label.setText(f"Source language set to {normalized}.")

    def on_target_lang_changed(value: str) -> None:
        normalized = value.strip().lower()
        update_section("TRANSLATIONCONFIG", {"target_lang": normalized})
        reload_runtime_config()
        main_win.status_label.setText(f"Target language set to {normalized}.")

    def on_provider_changed(value: str) -> None:
        normalized = value.strip().lower()
        update_section("TRANSLATIONCONFIG", {"translation_service": normalized})
        reload_runtime_config()
        main_win.status_label.setText(f"Translation provider set to {normalized}.")

    def on_model_changed() -> None:
        model_value = main_win.model_input.text().strip()
        update_section("TRANSLATIONCONFIG", {"model": model_value})
        reload_runtime_config()
        main_win.status_label.setText(f"Translation model set to {model_value or '(empty)'}.")

    def on_set_api_key() -> None:
        api_key = main_win.prompt_for_api_key()
        if api_key is None:
            return
        update_section("TRANSLATIONCONFIG", {"api_key": api_key})
        reload_runtime_config()
        masked = "*" * min(len(api_key), 8) if api_key else "(empty)"
        main_win.status_label.setText(f"API key updated: {masked}")

    main_win.btn_toggle_log.clicked.connect(toggle_log_window)
    main_win.btn_toggle_preview.clicked.connect(toggle_preview_window)
    main_win.btn_toggle_game_overlay.clicked.connect(toggle_game_overlay)
    main_win.btn_game_overlay_editor.clicked.connect(toggle_game_overlay_editor)
    main_win.btn_open_config.clicked.connect(open_config_file)
    main_win.btn_reload_config.clicked.connect(reload_runtime_config)
    main_win.source_lang_combo.currentTextChanged.connect(on_source_lang_changed)
    main_win.target_lang_combo.currentTextChanged.connect(on_target_lang_changed)
    main_win.provider_combo.currentTextChanged.connect(on_provider_changed)
    main_win.model_input.editingFinished.connect(on_model_changed)
    main_win.btn_set_api_key.clicked.connect(on_set_api_key)
    preview_win.filter_panel.btn_reset.clicked.connect(refresh_preview_capture)

    try:
        return app.exec()
    finally:
        teardown_hotkeys()
        global_workers.shutdown()


if __name__ == "__main__":
    sys.exit(main())
