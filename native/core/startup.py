from __future__ import annotations

from pathlib import Path

from native.core import paths
from native.core.dpi import enable_dpi_awareness
from native.config.service import ensure_native_config


def ensure_runtime_directories() -> None:
    for directory in (
        paths.text_logs_dir(),
        paths.image_logs_dir(),
        paths.profiles_dir(),
    ):
        directory.mkdir(parents=True, exist_ok=True)


def initialize_runtime() -> None:
    ensure_runtime_directories()
    ensure_native_config(paths.config_path())


def get_startup_diagnostics() -> dict[str, str]:
    """Return lightweight diagnostics for the Phase 0 skeleton."""
    initialize_runtime()
    return {
        "config_path": str(paths.config_path()),
        "config_exists": str(paths.config_path().exists()),
        "logs_dir": str(paths.logs_dir()),
        "text_logs_dir": str(paths.text_logs_dir()),
        "profiles_dir": str(paths.profiles_dir()),
        "tesseract_exe": str(paths.tesseract_exe_path()),
        "tessdata_dir": str(paths.tessdata_dir()),
        "dpi_awareness_attempted": str(enable_dpi_awareness()),
    }


def is_standalone_layout(root: Path | None = None) -> bool:
    root = root or paths.app_root()
    return (root / "native_app.py").exists() and (root / "native").is_dir()
