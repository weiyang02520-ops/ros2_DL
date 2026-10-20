"""Optional debug RGB overlay (boxes only). No GUI; rate-limited by the node.

publish_debug_image defaults false. When enabled, callers must cap publish ≤2 Hz.
"""

from __future__ import annotations

import time
from typing import Iterable, Optional, Sequence, Tuple

import numpy as np

from vision_perception.types import Detection


# BGR-ish colours stored as RGB for rgb8 overlays.
_CLASS_COLORS = {
    "bottle": (40, 200, 80),
    "cup": (220, 160, 40),
}
_DEFAULT_COLOR = (200, 200, 200)


def draw_detections_rgb(
    image_rgb: np.ndarray,
    detections: Sequence[Detection],
    *,
    thickness: int = 2,
) -> np.ndarray:
    """Return a copy of ``image_rgb`` with axis-aligned boxes drawn (uint8 HxWx3)."""
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError("image_rgb must be HxWx3")
    canvas = np.ascontiguousarray(image_rgb, dtype=np.uint8).copy()
    height, width = canvas.shape[:2]
    for det in detections:
        color = _CLASS_COLORS.get(det.class_name, _DEFAULT_COLOR)
        x1 = int(max(0, min(width - 1, round(det.bbox.x_min))))
        y1 = int(max(0, min(height - 1, round(det.bbox.y_min))))
        x2 = int(max(0, min(width - 1, round(det.bbox.x_max))))
        y2 = int(max(0, min(height - 1, round(det.bbox.y_max))))
        if x2 <= x1 or y2 <= y1:
            continue
        _draw_rect(canvas, x1, y1, x2, y2, color, max(1, int(thickness)))
        label = f"{det.class_name}:{det.confidence:.2f}"
        _draw_label(canvas, x1, max(0, y1 - 1), label, color)
    return canvas


def _draw_rect(
    canvas: np.ndarray,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: Tuple[int, int, int],
    thickness: int,
) -> None:
    # Top / bottom
    canvas[y1 : y1 + thickness, x1 : x2 + 1] = color
    canvas[max(0, y2 - thickness + 1) : y2 + 1, x1 : x2 + 1] = color
    # Left / right
    canvas[y1 : y2 + 1, x1 : x1 + thickness] = color
    canvas[y1 : y2 + 1, max(0, x2 - thickness + 1) : x2 + 1] = color


def _draw_label(
    canvas: np.ndarray,
    x: int,
    y: int,
    text: str,
    color: Tuple[int, int, int],
) -> None:
    """Tiny block label (no FreeType dependency): a coloured bar under short text width."""
    # Approximate 6 px per character for a 10 px tall bar; keeps overlay dependency-free.
    bar_h = 10
    bar_w = min(canvas.shape[1] - x, max(12, 6 * len(text)))
    y0 = max(0, y - bar_h)
    canvas[y0:y, x : x + bar_w] = color


class DebugPublishGate:
    """Allow at most ``max_hz`` publishes (default 2.0 Hz per V4 plan §9)."""

    def __init__(self, max_hz: float = 2.0):
        if max_hz <= 0:
            raise ValueError("max_hz must be > 0")
        self._min_interval = 1.0 / float(max_hz)
        self._last_mono: Optional[float] = None

    def allow(self, now: Optional[float] = None) -> bool:
        t = time.monotonic() if now is None else float(now)
        if self._last_mono is None or (t - self._last_mono) >= self._min_interval:
            self._last_mono = t
            return True
        return False


def detections_have_only_allowed_classes(
    detections: Iterable[Detection], allowed: Sequence[str] = ("bottle", "cup")
) -> bool:
    allowed_set = set(allowed)
    return all(d.class_name in allowed_set for d in detections)
