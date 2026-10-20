"""YOLO11-seg mask reconstruction (plan §6.2 / §7.2).

Pure NumPy (+ optional OpenCV resize). No Ultralytics / rclpy.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

from vision_perception.types import BoundingBox2D, LetterboxMeta


def sigmoid(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-x))


def _resize_2d(mask: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Bilinear resize of a 2D float mask to out_h x out_w."""
    if mask.ndim != 2:
        raise ValueError("mask must be 2D")
    if out_h <= 0 or out_w <= 0:
        raise ValueError("output size must be positive")
    in_h, in_w = mask.shape
    if in_h == out_h and in_w == out_w:
        return np.ascontiguousarray(mask, dtype=np.float32)
    try:
        import cv2  # type: ignore

        return cv2.resize(
            mask.astype(np.float32), (out_w, out_h), interpolation=cv2.INTER_LINEAR
        )
    except ImportError:
        # Nearest-neighbour fallback for minimal test envs without OpenCV.
        ys = (np.arange(out_h) + 0.5) * in_h / out_h - 0.5
        xs = (np.arange(out_w) + 0.5) * in_w / out_w - 0.5
        ys = np.clip(np.rint(ys).astype(np.int32), 0, in_h - 1)
        xs = np.clip(np.rint(xs).astype(np.int32), 0, in_w - 1)
        return mask[ys][:, xs].astype(np.float32)


def combine_mask_coefficients(
    coefficients: np.ndarray, prototypes: np.ndarray
) -> np.ndarray:
    """coeffs[32] · protos[32,H,W] → float HxW (pre-sigmoid linear)."""
    coeffs = np.asarray(coefficients, dtype=np.float32).reshape(-1)
    protos = np.asarray(prototypes, dtype=np.float32)
    if protos.ndim == 4:
        if protos.shape[0] != 1:
            raise ValueError(f"prototypes batch must be 1, got {protos.shape}")
        protos = protos[0]
    if protos.ndim != 3:
        raise ValueError(f"prototypes must be [32,H,W] or [1,32,H,W], got {protos.shape}")
    n_proto, mh, mw = protos.shape
    if coeffs.size != n_proto:
        raise ValueError(
            f"coefficient length {coeffs.size} != prototype channels {n_proto}"
        )
    flat = protos.reshape(n_proto, -1)
    return (coeffs @ flat).reshape(mh, mw)


def invert_letterbox_mask(
    mask_model: np.ndarray, letterbox: LetterboxMeta
) -> np.ndarray:
    """Map a model-canvas mask (model_size×model_size) back to source HxW float."""
    if mask_model.ndim != 2:
        raise ValueError("mask_model must be 2D")
    size = int(letterbox.model_size)
    if mask_model.shape != (size, size):
        mask_model = _resize_2d(mask_model, size, size)
    y0 = int(letterbox.pad_top)
    x0 = int(letterbox.pad_left)
    y1 = size - int(letterbox.pad_bottom)
    x1 = size - int(letterbox.pad_right)
    if y1 <= y0 or x1 <= x0:
        return np.zeros(
            (letterbox.source_height, letterbox.source_width), dtype=np.float32
        )
    cropped = mask_model[y0:y1, x0:x1]
    return _resize_2d(cropped, letterbox.source_height, letterbox.source_width)


def crop_mask_to_bbox(
    mask: np.ndarray, bbox: BoundingBox2D, *, soft: bool = True
) -> np.ndarray:
    """Zero mask outside the axis-aligned bbox (keeps HxW)."""
    out = np.array(mask, dtype=np.float32, copy=True)
    h, w = out.shape
    x1 = int(max(0, min(w, np.floor(bbox.x_min))))
    y1 = int(max(0, min(h, np.floor(bbox.y_min))))
    x2 = int(max(0, min(w, np.ceil(bbox.x_max))))
    y2 = int(max(0, min(h, np.ceil(bbox.y_max))))
    cleared = np.zeros_like(out)
    if x2 > x1 and y2 > y1:
        cleared[y1:y2, x1:x2] = out[y1:y2, x1:x2]
    if not soft:
        return cleared
    return cleared


def reconstruct_instance_mask(
    coefficients: np.ndarray,
    prototypes: np.ndarray,
    letterbox: LetterboxMeta,
    bbox: BoundingBox2D,
    *,
    mask_threshold: float = 0.5,
) -> Tuple[Optional[np.ndarray], str]:
    """Build binary HxW mask in source image coords.

    Returns (mask_uint8_or_None, mask_source). On failure returns (None, "bbox_fill")
    so callers can fall back without forging a contour.
    """
    try:
        if not (0.0 < float(mask_threshold) < 1.0):
            return None, "bbox_fill"
        linear = combine_mask_coefficients(coefficients, prototypes)
        # Degenerate / empty coeffs·protos → sigmoid≈0.5 everywhere; not a contour.
        if float(np.max(np.abs(linear))) < 1e-6:
            return None, "bbox_fill"
        # Prototypes are typically 160×160; upsample to letterbox canvas then invert.
        canvas = _resize_2d(sigmoid(linear), letterbox.model_size, letterbox.model_size)
        source = invert_letterbox_mask(canvas, letterbox)
        source = crop_mask_to_bbox(source, bbox)
        binary = (source >= float(mask_threshold)).astype(np.uint8)
        if int(binary.sum()) <= 0:
            return None, "bbox_fill"
        return binary, "yolo_seg"
    except (ValueError, TypeError):
        return None, "bbox_fill"
