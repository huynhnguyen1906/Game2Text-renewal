from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


MIN_REGION_SIZE = 10


@dataclass
class ScreenRegion:
    id: str
    label: str
    x: int
    y: int
    width: int
    height: int
    monitor: int
    border_color: str = "red"
    capture_hotkey: str = "ctrl+q"
    select_hotkey: str = "ctrl+shift+q"
    enabled: bool = True
    show_region_border: bool = True

    @property
    def is_valid(self) -> bool:
        return self.width >= MIN_REGION_SIZE and self.height >= MIN_REGION_SIZE

    @classmethod
    def from_drag(
        cls,
        *,
        id: str,
        label: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        monitor: int,
        border_color: str = "red",
        capture_hotkey: str = "ctrl+q",
        select_hotkey: str = "ctrl+shift+q",
    ) -> "ScreenRegion":
        x = min(start_x, end_x)
        y = min(start_y, end_y)
        width = abs(end_x - start_x)
        height = abs(end_y - start_y)
        return cls(
            id=id,
            label=label,
            x=x,
            y=y,
            width=width,
            height=height,
            monitor=monitor,
            border_color=border_color,
            capture_hotkey=capture_hotkey,
            select_hotkey=select_hotkey,
        )


@dataclass
class FilterConfig:
    invertColor: bool = False
    dilate: bool = False
    blurImageRadius: int = 0
    binarizeThreshold: int | None = None
    activeProfile: str = ""

    @property
    def is_binarize_enabled(self) -> bool:
        return self.binarizeThreshold is not None


@dataclass
class LogEntry:
    id: str
    row_key: str
    folder: str
    source_text: str
    translated_text: str | None = None
    translation_pending: bool = False
    translation_status: str = "idle"
    translation_error: str | None = None
    created_at: datetime | None = None
    region_id: str = "1"


@dataclass
class WindowState:
    open: bool
    x: int
    y: int
    width: int
    height: int
    always_on_top: bool = False
