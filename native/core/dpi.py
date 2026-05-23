from __future__ import annotations

import ctypes
import platform


def set_windows_app_user_model_id(app_id: str = "Game2Text.Native") -> bool:
    if platform.system() != "Windows":
        return False
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except (AttributeError, OSError):
        return False


def configure_overlay_window_chrome(hwnd: int, editor_mode: bool) -> bool:
    """Adjust Windows DWM chrome for frameless overlay windows.

    In non-editor mode, aggressively disable non-client rendering, rounded
    corners, and shadow-like chrome that Windows may add to transparent
    top-level windows. In editor mode, restore the default NC rendering policy.
    """
    if platform.system() != "Windows" or not hwnd:
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        user32 = ctypes.windll.user32
    except AttributeError:
        return False

    # DWM constants
    DWMWA_NCRENDERING_POLICY = 2
    DWMWA_WINDOW_CORNER_PREFERENCE = 33
    DWMNCRP_DISABLED = 1
    DWMNCRP_ENABLED = 2
    DWMWCP_DEFAULT = 0
    DWMWCP_DONOTROUND = 1

    policy = ctypes.c_int(DWMNCRP_ENABLED if editor_mode else DWMNCRP_DISABLED)
    corner_pref = ctypes.c_int(DWMWCP_DEFAULT if editor_mode else DWMWCP_DONOTROUND)

    try:
        dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            DWMWA_NCRENDERING_POLICY,
            ctypes.byref(policy),
            ctypes.sizeof(policy),
        )
    except OSError:
        pass

    try:
        dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(corner_pref),
            ctypes.sizeof(corner_pref),
        )
    except OSError:
        pass

    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_NOACTIVATE = 0x0010
    SWP_FRAMECHANGED = 0x0020
    user32.SetWindowPos(
        ctypes.c_void_p(hwnd),
        None,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
    )
    return True


def enable_dpi_awareness() -> bool:
    """Enable Windows DPI awareness before QApplication is created.

    Returns True when a DPI-awareness call was attempted successfully, False
    when the platform is not Windows or no supported API is available.
    """
    if platform.system() != "Windows":
        return False

    try:
        awareness_context_per_monitor_v2 = ctypes.c_void_p(-4)
        result = ctypes.windll.user32.SetProcessDpiAwarenessContext(
            awareness_context_per_monitor_v2
        )
        if result:
            return True
    except (AttributeError, OSError):
        pass

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return True
    except (AttributeError, OSError):
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return True
    except (AttributeError, OSError):
        return False
