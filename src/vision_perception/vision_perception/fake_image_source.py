"""Pure helpers for fake-image RGB sources (no rclpy)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from vision_perception.image_io import _resize_rgb, load_image_file_rgb


def resolve_fake_image_path(
    image_path: str = "",
    fake_image_path: str = "",
    npy_path: str = "",
) -> str:
    """Prefer image_path, then fake_image_path, then legacy npy_path."""
    for value in (image_path, fake_image_path, npy_path):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def match_rgb_to_hw(rgb: np.ndarray, height: int, width: int) -> np.ndarray:
    """Resize RGB to depth/CameraInfo HxW so require_rgb_depth_same_size can pass.

    Synthetic smoke often loads a native-resolution JPG while fake depth is a
    fixed 640x480 plane; without matching, paired stamps still yield
    INPUT_INVALID / no reliable 3D. Unpaired failure paths stay invalid.
    """
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("rgb must be HxWx3")
    out_h = int(height)
    out_w = int(width)
    if out_h <= 0 or out_w <= 0:
        raise ValueError("height/width must be positive")
    if int(rgb.shape[0]) == out_h and int(rgb.shape[1]) == out_w:
        return np.ascontiguousarray(rgb, dtype=np.uint8)
    return _resize_rgb(np.ascontiguousarray(rgb, dtype=np.uint8), out_h, out_w)


def load_fake_rgb(
    path: str = "",
    *,
    width: int = 640,
    height: int = 480,
) -> tuple[np.ndarray, str]:
    """Load file RGB or build the default colour-block frame.

    Returns (rgb_uint8, source_note). File sources keep native resolution;
    callers that stamp-lock to fake depth should ``match_rgb_to_hw``.
    """
    path = (path or "").strip()
    if path:
        rgb = load_image_file_rgb(path)
        return rgb, f"file:{Path(path).name}"
    w = max(8, int(width))
    h = max(8, int(height))
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    rgb[:, : w // 2, 0] = 200
    rgb[:, w // 2 :, 2] = 200
    return rgb, "synthetic_colour_blocks"
