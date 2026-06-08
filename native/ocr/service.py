from __future__ import annotations

from PIL import Image

from native.config.service import read_value
from native.ocr import tesseract_engine


TESSERACT_ENGINE_ALIASES = {
    "tesseract",
    "tesseract lstm",
    "tesseract-lstm",
}


def _normalize_engine_name(engine_name: str) -> str:
    return engine_name.strip().lower()


def image_to_text(image: Image.Image, text_orientation: str = "horizontal") -> str:
    """Run OCR on a PIL image using the configured OCR backend."""
    engine_name = _normalize_engine_name(read_value("OCRCONFIG", "engine", "Tesseract LSTM"))
    if engine_name in TESSERACT_ENGINE_ALIASES:
        return tesseract_engine.image_to_text(image, text_orientation)
    raise RuntimeError(f"OCR engine '{engine_name}' is not implemented.")
