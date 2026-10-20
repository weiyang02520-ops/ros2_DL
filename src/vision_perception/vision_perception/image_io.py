"""Image buffer decode and letterbox preprocessing.

Uses NumPy only. Does not import cv_bridge or rclpy.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from vision_perception.types import LetterboxMeta


SUPPORTED_COLOR_ENCODINGS = ("rgb8", "bgr8", "rgba8", "bgra8")


def decode_color_image(
    data: bytes | bytearray | memoryview | np.ndarray,
    height: int,
    width: int,
    encoding: str,
    step: int | None = None,
) -> np.ndarray:
    """Decode a ROS-like Image buffer into contiguous RGB uint8 HxWx3."""
    encoding = encoding.lower()
    if encoding not in SUPPORTED_COLOR_ENCODINGS:
        raise ValueError(f"unsupported color encoding={encoding!r}")
    if height <= 0 or width <= 0:
        raise ValueError("height and width must be positive")

    channels = 4 if encoding.endswith("a8") else 3
    expected_step = width * channels
    row_step = expected_step if step is None else int(step)
    if row_step < expected_step:
        raise ValueError(f"step={row_step} smaller than width*channels={expected_step}")

    if isinstance(data, np.ndarray):
        raw = np.ascontiguousarray(data).reshape(-1).view(np.uint8)
    else:
        raw = np.frombuffer(data, dtype=np.uint8)
    needed = row_step * height
    if raw.size < needed:
        raise ValueError(f"image buffer too short: have {raw.size}, need {needed}")

    if row_step == expected_step:
        image = raw[:needed].reshape(height, width, channels)
    else:
        rows = []
        for row in range(height):
            start = row * row_step
            rows.append(raw[start : start + expected_step])
        image = np.stack(rows, axis=0).reshape(height, width, channels)

    if encoding == "rgb8":
        rgb = image
    elif encoding == "bgr8":
        rgb = image[:, :, ::-1]
    elif encoding == "rgba8":
        rgb = image[:, :, :3]
    else:  # bgra8
        rgb = image[:, :, 2::-1]
    return np.ascontiguousarray(rgb, dtype=np.uint8)


def _bilinear_resize(image: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Minimal bilinear resize for uint8 HxWxC images."""
    in_h, in_w, channels = image.shape
    if out_h <= 0 or out_w <= 0:
        raise ValueError("output size must be positive")
    if in_h == out_h and in_w == out_w:
        return np.ascontiguousarray(image)

    # Map output pixel centres to input coordinates.
    y_ratio = in_h / float(out_h)
    x_ratio = in_w / float(out_w)
    out = np.empty((out_h, out_w, channels), dtype=np.float32)
    for y in range(out_h):
        src_y = (y + 0.5) * y_ratio - 0.5
        y0 = int(np.floor(src_y))
        y1 = min(y0 + 1, in_h - 1)
        y0 = max(0, y0)
        wy = src_y - y0
        for x in range(out_w):
            src_x = (x + 0.5) * x_ratio - 0.5
            x0 = int(np.floor(src_x))
            x1 = min(x0 + 1, in_w - 1)
            x0 = max(0, x0)
            wx = src_x - x0
            top = (1.0 - wx) * image[y0, x0].astype(np.float32) + wx * image[y0, x1].astype(
                np.float32
            )
            bottom = (1.0 - wx) * image[y1, x0].astype(np.float32) + wx * image[y1, x1].astype(
                np.float32
            )
            out[y, x] = (1.0 - wy) * top + wy * bottom
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def _resize_rgb(image_rgb: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Prefer OpenCV bilinear resize; fall back to pure NumPy."""
    try:
        import cv2  # type: ignore

        # cv2 expects BGR channel order only for colour semantics of imread;
        # resizing channel-wise is order-agnostic for interleaved HxWx3.
        return cv2.resize(image_rgb, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
    except ImportError:
        return _bilinear_resize(image_rgb, out_h, out_w)


def letterbox_rgb(
    image_rgb: np.ndarray,
    model_size: int = 640,
    pad_value: int = 114,
) -> Tuple[np.ndarray, LetterboxMeta]:
    """Keep aspect ratio, resize, centre-pad to model_size x model_size."""
    if image_rgb.ndim != 3 or image_rgb.shape[2] != 3:
        raise ValueError("image_rgb must be HxWx3")
    source_h, source_w = image_rgb.shape[:2]
    if source_h <= 0 or source_w <= 0:
        raise ValueError("empty image")
    scale = min(model_size / float(source_w), model_size / float(source_h))
    new_w = max(1, int(round(source_w * scale)))
    new_h = max(1, int(round(source_h * scale)))
    resized = _resize_rgb(image_rgb, new_h, new_w)

    canvas = np.full((model_size, model_size, 3), pad_value, dtype=np.uint8)
    pad_left = (model_size - new_w) // 2
    pad_top = (model_size - new_h) // 2
    pad_right = model_size - new_w - pad_left
    pad_bottom = model_size - new_h - pad_top
    canvas[pad_top : pad_top + new_h, pad_left : pad_left + new_w] = resized
    meta = LetterboxMeta(
        scale=scale,
        pad_left=pad_left,
        pad_top=pad_top,
        pad_right=pad_right,
        pad_bottom=pad_bottom,
        source_width=source_w,
        source_height=source_h,
        model_size=model_size,
    )
    return canvas, meta


def letterbox_to_nchw_float32(canvas_rgb: np.ndarray) -> np.ndarray:
    """Convert padded RGB uint8 to NCHW FP32 in [0, 1], batch=1."""
    if canvas_rgb.dtype != np.uint8:
        raise ValueError("canvas must be uint8")
    chw = np.transpose(canvas_rgb.astype(np.float32) / 255.0, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


def restore_xyxy_from_letterbox(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    meta: LetterboxMeta,
) -> Tuple[float, float, float, float]:
    """Map model-space xyxy back to original image pixels."""
    x1 = (x1 - meta.pad_left) / meta.scale
    y1 = (y1 - meta.pad_top) / meta.scale
    x2 = (x2 - meta.pad_left) / meta.scale
    y2 = (y2 - meta.pad_top) / meta.scale
    return (x1, y1, x2, y2)


def load_image_file_rgb(path: str) -> np.ndarray:
    """Load a local image file as RGB uint8.

    Prefers OpenCV when available; otherwise accepts a raw .npy HxWx3 array.
    JPEG/PNG without OpenCV raises a clear environment error (no silent fake).
    """
    from pathlib import Path

    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(path)
    if file_path.suffix.lower() == ".npy":
        array = np.load(str(file_path))
        if array.ndim != 3 or array.shape[2] != 3:
            raise ValueError(f"npy image must be HxWx3, got {array.shape}")
        return np.ascontiguousarray(array, dtype=np.uint8)
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV (cv2) is required to load JPEG/PNG for offline detection; "
            "or provide a .npy HxWx3 RGB array"
        ) from exc
    bgr = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"failed to read image: {file_path}")
    return np.ascontiguousarray(bgr[:, :, ::-1])
