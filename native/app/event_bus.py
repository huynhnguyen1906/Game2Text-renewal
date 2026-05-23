from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AppEventBus(QObject):
    log_entry_created = Signal(object)  # native.core.models.LogEntry
    log_entry_updated = Signal(str, dict)  # log_id, patch_dict
    overlay_text_updated = Signal(str)
    status_changed = Signal(str)
    capture_failed = Signal(str)
    preview_image_updated = Signal(object)  # PIL.Image
    region_updated = Signal(object)  # native.core.models.ScreenRegion
    trigger_capture = Signal()
    trigger_select_region = Signal()
    trigger_show_borders = Signal()
    trigger_toggle_game_overlay = Signal()


global_bus = AppEventBus()
