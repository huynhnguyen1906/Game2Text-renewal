from __future__ import annotations

import shutil
from configparser import ConfigParser
from pathlib import Path

from native.core import paths
from native.core.models import FilterConfig, ScreenRegion


REGION_COMPAT_SECTION = "REGIONCONFIG"
REGION_SECTION = "REGION_1"
NATIVE_APP_SECTION = "NATIVEAPP"
FILTER_SECTION = "FILTERCONFIG"
GAME_OVERLAY_SECTION = "GAMEOVERLAY"


DEFAULT_CONFIG: dict[str, dict[str, str]] = {
    "APPEARANCE": {
        "fontsize": "23",
        "darktheme": "true",
        "selection_color": "hotpink",
        "selection_line_width": "1",
    },
    "OCRCONFIG": {
        "engine": "Tesseract LSTM",
        "tesseract_language": "eng",
        "ocr_space_language": "eng",
        "oem": "1",
        "extra_options": (
            '"-c chop_enable=T -c use_new_state_cost=F -c segment_segcost_rating=F '
            '-c textord_force_make_prop_words=F -c edges_max_children_per_outline=40"'
        ),
    },
    "TRANSLATIONCONFIG": {
        "translation_service": "Google Translate",
        "source_lang": "en",
        "target_lang": "vi",
        "openai_model": "gpt-4.1-nano",
        "openai_api_key": "",
    },
    "LOGCONFIG": {
        "launchlogwindow": "false",
        "currentsessionmaxlogsize": "30",
        "lastsessionmaxlogsize": "15",
        "logimages": "false",
        "logimagetype": "jpg",
        "logimagequality": "1.0",
        "resize_screenshot": "false",
        "resize_screenshot_max_width": "1280",
        "resize_screenshot_max_height": "720",
        "gamescriptfile": "",
    },
    "WINDOWS_HOTKEYS": {
        "refresh_ocr": "ctrl+q",
        "add_to_anki": "<shift>+e",
    },
}


EXISTING_SECTION_DEFAULTS: dict[str, dict[str, str]] = {
    "TRANSLATIONCONFIG": {
        "openai_model": "gpt-4.1-nano",
    },
}


NATIVE_DEFAULTS: dict[str, dict[str, str]] = {
    REGION_SECTION: {
        "label": "Region 1",
        "x": "100",
        "y": "200",
        "width": "900",
        "height": "180",
        "monitor": "1",
        "border_color": "red",
        "capture_hotkey": "ctrl+q",
        "select_hotkey": "ctrl+shift+q",
        "enabled": "true",
        "show_region_border": "true",
    },
    NATIVE_APP_SECTION: {
        "translation_queue_limit": "5",
        "show_borders_hotkey": "ctrl+shift+1",
        "main_window_open": "true",
        "main_window_x": "100",
        "main_window_y": "100",
        "main_window_width": "420",
        "main_window_height": "360",
        "log_window_open": "false",
        "log_window_x": "1200",
        "log_window_y": "120",
        "log_window_width": "700",
        "log_window_height": "900",
        "log_always_on_top": "true",
        "preview_window_open": "false",
        "preview_window_x": "900",
        "preview_window_y": "120",
        "preview_window_width": "900",
        "preview_window_height": "700",
    },
    FILTER_SECTION: {
        "invertColor": "false",
        "dilate": "false",
        "blurImageRadius": "0",
        "binarizeEnabled": "false",
        "binarizeThreshold": "50",
        "activeProfile": "",
    },
    GAME_OVERLAY_SECTION: {
        "visible": "false",
        "x": "320",
        "y": "820",
        "width": "900",
        "height": "120",
        "font_size": "28",
        "text_opacity": "1.0",
        "outline_opacity": "0.7",
        "background_opacity": "0.7",
        "overlay_opacity": "1.0",
        "auto_hide_seconds": "15",
        "use_text_background": "false",
        "toggle_hotkey": "ctrl+shift+2",
    },
}


REGION_COMPAT_KEY_MAP = {
    "x": "x",
    "y": "y",
    "width": "width",
    "height": "height",
    "monitor": "monitor",
    "show_region_border": "show_region_border",
    "border_color": "border_color",
}


def create_parser() -> ConfigParser:
    parser = ConfigParser()
    parser.optionxform = str
    return parser


def load_config(config_path: Path | None = None) -> ConfigParser:
    config_path = config_path or paths.config_path()
    parser = create_parser()
    parser.read(config_path, encoding="utf-8")
    return parser


def write_config(parser: ConfigParser, config_path: Path | None = None) -> None:
    config_path = config_path or paths.config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        parser.write(handle)


def read_value(section: str, key: str, fallback: str = "", config_path: Path | None = None) -> str:
    parser = load_config(config_path)
    if not parser.has_section(section):
        return fallback
    return parser.get(section, key, fallback=fallback)


def read_section(section: str, config_path: Path | None = None) -> dict[str, str]:
    parser = load_config(config_path)
    if not parser.has_section(section):
        return {}
    return dict(parser.items(section))


def update_section(
    section: str,
    values: dict[str, object],
    config_path: Path | None = None,
) -> None:
    config_path = config_path or paths.config_path()
    parser = load_config(config_path)
    if not parser.has_section(section):
        parser.add_section(section)
    for key, value in values.items():
        parser.set(section, key, str(value))
    write_config(parser, config_path)


def save_value(section: str, key: str, value: str, config_path: Path | None = None) -> None:
    update_section(section, {key: value}, config_path)


def read_bool(section: str, key: str, fallback: bool = False, config_path: Path | None = None) -> bool:
    value = read_value(section, key, str(fallback).lower(), config_path).strip().lower()
    return value in {"1", "true", "yes", "on"}


def load_region(section: str = REGION_SECTION, config_path: Path | None = None) -> ScreenRegion | None:
    parser = load_config(config_path)
    section_name = section if parser.has_section(section) else REGION_COMPAT_SECTION
    if not parser.has_section(section_name):
        return None

    values = dict(parser.items(section_name))

    def _to_int(key: str, default: int) -> int:
        try:
            return int(values.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    return ScreenRegion(
        id="1",
        label=values.get("label", "Region 1"),
        x=_to_int("x", 0),
        y=_to_int("y", 0),
        width=_to_int("width", 0),
        height=_to_int("height", 0),
        monitor=_to_int("monitor", 1),
        border_color=values.get("border_color", "red"),
        capture_hotkey=values.get("capture_hotkey", "ctrl+q"),
        select_hotkey=values.get("select_hotkey", "ctrl+shift+q"),
        enabled=values.get("enabled", "true").lower() == "true",
        show_region_border=values.get("show_region_border", "true").lower() == "true",
    )


def save_region(region: ScreenRegion, config_path: Path | None = None) -> None:
    values = {
        "label": region.label,
        "x": region.x,
        "y": region.y,
        "width": region.width,
        "height": region.height,
        "monitor": region.monitor,
        "border_color": region.border_color,
        "capture_hotkey": region.capture_hotkey,
        "select_hotkey": region.select_hotkey,
        "enabled": str(region.enabled).lower(),
        "show_region_border": str(region.show_region_border).lower(),
    }
    update_section(REGION_SECTION, values, config_path)

    parser = load_config(config_path)
    if parser.has_section(REGION_COMPAT_SECTION):
        compat_values = {
            "x": region.x,
            "y": region.y,
            "width": region.width,
            "height": region.height,
            "monitor": region.monitor,
            "border_color": region.border_color,
            "show_region_border": str(region.show_region_border).lower(),
        }
        update_section(REGION_COMPAT_SECTION, compat_values, config_path)


def load_filter_config(config_path: Path | None = None) -> FilterConfig:
    parser = load_config(config_path)
    values = dict(parser.items(FILTER_SECTION)) if parser.has_section(FILTER_SECTION) else {}
    binarize_enabled = values.get("binarizeEnabled", "false").lower() == "true"

    def _to_int(key: str, default: int) -> int:
        try:
            return int(values.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    return FilterConfig(
        invertColor=values.get("invertColor", "false").lower() == "true",
        dilate=values.get("dilate", "false").lower() == "true",
        blurImageRadius=_to_int("blurImageRadius", 0),
        binarizeThreshold=_to_int("binarizeThreshold", 50) if binarize_enabled else None,
        activeProfile=values.get("activeProfile", ""),
    )


def save_filter_config(config: FilterConfig, config_path: Path | None = None) -> None:
    values: dict[str, object] = {
        "invertColor": str(config.invertColor).lower(),
        "dilate": str(config.dilate).lower(),
        "blurImageRadius": config.blurImageRadius,
        "binarizeEnabled": str(config.is_binarize_enabled).lower(),
        "binarizeThreshold": config.binarizeThreshold if config.binarizeThreshold is not None else 50,
        "activeProfile": config.activeProfile,
    }
    update_section(FILTER_SECTION, values, config_path)


def ensure_config_exists(config_path: Path | None = None) -> bool:
    """Ensure a config exists.

    Returns True when the file was created.
    """
    config_path = config_path or paths.config_path()
    if config_path.exists():
        return False

    config_path.parent.mkdir(parents=True, exist_ok=True)
    source_config = _find_source_config(config_path)
    if source_config:
        shutil.copy2(source_config, config_path)
        return True

    parser = create_parser()
    for section, values in DEFAULT_CONFIG.items():
        parser[section] = values
    write_config(parser, config_path)
    return True


def ensure_native_config(config_path: Path | None = None) -> bool:
    """Add native config sections and keys without deleting existing data.

    Returns True when the file changed.
    """
    config_path = config_path or paths.config_path()
    created = ensure_config_exists(config_path)
    parser = load_config(config_path)
    changed = created
    needs_backup = False

    if _apply_region_compat(parser):
        changed = True
        needs_backup = True

    for section, defaults in EXISTING_SECTION_DEFAULTS.items():
        if not parser.has_section(section):
            parser.add_section(section)
            changed = True
            needs_backup = True
        for key, value in defaults.items():
            if not parser.has_option(section, key):
                parser.set(section, key, value)
                changed = True
                needs_backup = True

    for section, defaults in NATIVE_DEFAULTS.items():
        if not parser.has_section(section):
            parser.add_section(section)
            changed = True
            needs_backup = True
        for key, value in defaults.items():
            if not parser.has_option(section, key):
                parser.set(section, key, value)
                changed = True
                needs_backup = True

    if changed:
        if needs_backup:
            backup_config_once(config_path)
        write_config(parser, config_path)
    return changed


def backup_config_once(config_path: Path | None = None) -> Path | None:
    config_path = config_path or paths.config_path()
    if not config_path.exists():
        return None
    backup_path = config_path.with_name(f"{config_path.name}.bak-native-first-run")
    if backup_path.exists():
        return backup_path
    shutil.copy2(config_path, backup_path)
    return backup_path


def _apply_region_compat(parser: ConfigParser) -> bool:
    if not parser.has_section(REGION_COMPAT_SECTION):
        return False
    if not parser.has_section(REGION_SECTION):
        parser.add_section(REGION_SECTION)

    changed = False
    for old_key, new_key in REGION_COMPAT_KEY_MAP.items():
        if parser.has_option(REGION_COMPAT_SECTION, old_key) and not parser.has_option(
            REGION_SECTION, new_key
        ):
            parser.set(REGION_SECTION, new_key, parser.get(REGION_COMPAT_SECTION, old_key))
            changed = True
    return changed


def _find_source_config(target_path: Path) -> Path | None:
    candidates = [
        paths.app_root() / "config.template.ini",
        paths.app_root().parent / "config.ini",
        paths.bundle_root() / "config.ini",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.resolve() != target_path.resolve():
            return candidate
    return None
