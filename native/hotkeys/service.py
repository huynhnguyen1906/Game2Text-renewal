from __future__ import annotations

import keyboard
from native.app.event_bus import global_bus

def setup_hotkeys(
    capture_hotkey: str = "ctrl+q",
    select_hotkey: str = "ctrl+shift+q",
    show_borders_hotkey: str = "ctrl+shift+1",
    toggle_game_overlay_hotkey: str = "ctrl+shift+2",
):
    """
    Registers global hotkeys using the `keyboard` package.
    It emits Qt signals into the main thread.
    """
    try:
        # Avoid double-registering if called multiple times or reloaded
        keyboard.unhook_all()
    except Exception:
        pass
        
    keyboard.add_hotkey(
        capture_hotkey,
        lambda: global_bus.trigger_capture.emit(),
        suppress=False,
        trigger_on_release=False,
    )
    keyboard.add_hotkey(
        select_hotkey,
        lambda: global_bus.trigger_select_region.emit(),
        suppress=False,
        trigger_on_release=False,
    )
    keyboard.add_hotkey(
        show_borders_hotkey,
        lambda: global_bus.trigger_show_borders.emit(),
        suppress=False,
        trigger_on_release=False,
    )
    keyboard.add_hotkey(
        toggle_game_overlay_hotkey,
        lambda: global_bus.trigger_toggle_game_overlay.emit(),
        suppress=False,
        trigger_on_release=False,
    )


def teardown_hotkeys():
    try:
        keyboard.unhook_all()
    except Exception:
        pass
