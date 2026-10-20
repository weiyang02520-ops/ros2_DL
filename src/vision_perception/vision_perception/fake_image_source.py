"""Pure helpers for fake-image RGB sources (no rclpy)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from vision_perception.image_io import load_image_file_rgb


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


def load_fake_rgb(
    path: str = "",
    *,
    width: int = 640,
    height: int = 480,
) -> tuple[np.ndarray, str]:
    """Load file RGB or build the default colour-block frame.

    Returns (rgb_uint8, source_note).
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
