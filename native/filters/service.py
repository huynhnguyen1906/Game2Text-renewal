from __future__ import annotations

import cv2
import numpy as np
from PIL import Image

from native.core.models import FilterConfig


def blur_kernel_from_slider(value: int) -> int:
    if value <= 0:
        return 0
    # Approximate current web behavior.
    radius = max(1, min(248, int((value / 100) * 3.5)))
    kernel = radius * 2 + 1
    return kernel


def apply_luminance_dilate(rgb: np.ndarray) -> np.ndarray:
    """Implement compatible 4-neighbor luminance dilate (JS compatible)."""
    # Create luminance array (77 * R + 151 * G + 28 * B)
    # rgb shape is (H, W, 3) where channels are R, G, B
    lum = (
        77 * rgb[..., 0].astype(np.uint32)
        + 151 * rgb[..., 1].astype(np.uint32)
        + 28 * rgb[..., 2].astype(np.uint32)
    )

    out_rgb = rgb.copy()

    # Fast path with numpy shifting
    lum_left = np.pad(lum[:, :-1], ((0, 0), (1, 0)), mode="edge")
    lum_right = np.pad(lum[:, 1:], ((0, 0), (0, 1)), mode="edge")
    lum_up = np.pad(lum[:-1, :], ((1, 0), (0, 0)), mode="edge")
    lum_down = np.pad(lum[1:, :], ((0, 1), (0, 0)), mode="edge")

    # Stack luminances to find the argmax (meaning which direction has max luminance)
    # indices: 0: center, 1: left, 2: right, 3: up, 4: down
    lum_stack = np.stack([lum, lum_left, lum_right, lum_up, lum_down], axis=-1)
    max_idx = np.argmax(lum_stack, axis=-1)

    rgb_left = np.pad(rgb[:, :-1, :], ((0, 0), (1, 0), (0, 0)), mode="edge")
    rgb_right = np.pad(rgb[:, 1:, :], ((0, 0), (0, 1), (0, 0)), mode="edge")
    rgb_up = np.pad(rgb[:-1, :, :], ((1, 0), (0, 0), (0, 0)), mode="edge")
    rgb_down = np.pad(rgb[1:, :, :], ((0, 1), (0, 0), (0, 0)), mode="edge")

    # Apply masks based on which neighbor had max luminance
    mask = max_idx == 1
    out_rgb[mask] = rgb_left[mask]

    mask = max_idx == 2
    out_rgb[mask] = rgb_right[mask]

    mask = max_idx == 3
    out_rgb[mask] = rgb_up[mask]

    mask = max_idx == 4
    out_rgb[mask] = rgb_down[mask]

    return out_rgb


def apply_invert(rgb: np.ndarray) -> np.ndarray:
    return 255 - rgb


def apply_threshold(rgb: np.ndarray, threshold: int) -> np.ndarray:
    thresh = int((threshold / 100) * 255)
    gray = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    bw = np.where(gray >= thresh, 255, 0).astype(np.uint8)
    return np.stack([bw, bw, bw], axis=-1)


def apply_filters(image: Image.Image, config: FilterConfig) -> Image.Image:
    """Apply the filter pipeline to a PIL Image without mutating the original.
    Order must be: blur -> dilate -> invert -> threshold
    """
    # Convert image to RGB numpy array
    rgb = np.array(image.convert("RGB"))

    # 1. Blur
    kernel = blur_kernel_from_slider(config.blurImageRadius)
    if kernel > 0:
        rgb = cv2.GaussianBlur(rgb, (kernel, kernel), 0)

    # 2. Dilate
    if config.dilate:
        rgb = apply_luminance_dilate(rgb)

    # 3. Invert Color
    if config.invertColor:
        rgb = apply_invert(rgb)

    # 4. Threshold (Binarize)
    if config.is_binarize_enabled and config.binarizeThreshold is not None:
        rgb = apply_threshold(rgb, config.binarizeThreshold)

    return Image.fromarray(rgb, mode="RGB")
