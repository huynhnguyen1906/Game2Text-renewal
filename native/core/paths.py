from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Return the editable runtime root.

    In source mode this is the newsource directory. In a packaged build this is
    the directory containing the executable.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_root() -> Path:
    """Return the read-only bundled resource root."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    return app_root()


def config_path() -> Path:
    return app_root() / "config.ini"


def logs_dir() -> Path:
    return app_root() / "logs"


def text_logs_dir() -> Path:
    return logs_dir() / "text"


def image_logs_dir() -> Path:
    return logs_dir() / "images"


def profiles_dir() -> Path:
    return app_root() / "profiles"


def resources_dir() -> Path:
    runtime_resources = app_root() / "resources"
    if runtime_resources.exists():
        return runtime_resources

    parent_resources = app_root().parent / "resources"
    if parent_resources.exists():
        return parent_resources

    return bundle_root() / "resources"


def public_dir() -> Path:
    runtime_public = app_root() / "public"
    if runtime_public.exists():
        return runtime_public
    return bundle_root() / "public"


def icon_path() -> Path:
    return public_dir() / "icon.ico"


def tesseract_dir() -> Path:
    return resources_dir() / "bin" / "win" / "tesseract"


def tesseract_exe_path() -> Path:
    return tesseract_dir() / "tesseract.exe"


def tessdata_dir() -> Path:
    return tesseract_dir() / "tessdata"
