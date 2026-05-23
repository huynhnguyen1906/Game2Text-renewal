from __future__ import annotations

import mss
from PIL import Image

from native.core.models import ScreenRegion


def capture_region(region: ScreenRegion) -> Image.Image:
    """Capture a screen region using mss and return a PIL Image."""
    with mss.mss() as sct:
        monitor = {
            "top": region.y,
            "left": region.x,
            "width": region.width,
            "height": region.height
        }
        sct_img = sct.grab(monitor)
        # Create PIL Image directly from mss output bytes
        return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
