from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OcrResult:
    text: str
    context_labels: tuple[str, ...] = ()
