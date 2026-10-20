"""Visible-surface depth sampling inside a 2D target (plan §7.2).

V2 offline path uses a filled bbox mask (mask_source=bbox_fill) then 3×3 erode.
Full YOLO-seg mask reconstruction can replace bbox_fill later without changing
the sampling / projection contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

from vision_perception.depth_io import CameraCalibration, project_optical_xyz
from vision_perception.types import BoundingBox2D, POSITION_REFERENCE


@dataclass(frozen=True)
class SurfaceSampleResult:
    position_valid: bool
    invalid_reason: str
    position_reference: str
    reference_u: float
    reference_v: float
    valid_depth_fraction: float
    xyz: Tuple[float, float, float]  # NaN when invalid
    mask_source: str


def bbox_fill_mask(
    bbox: BoundingBox2D, height: int, width: int
) -> np.ndarray:
    """Binary HxW mask filled with the axis-aligned bbox (uint8 0/1)."""
    mask = np.zeros((height, width), dtype=np.uint8)
    x1 = int(max(0, min(width, np.floor(bbox.x_min))))
    y1 = int(max(0, min(height, np.floor(bbox.y_min))))
    x2 = int(max(0, min(width, np.ceil(bbox.x_max))))
    y2 = int(max(0, min(height, np.ceil(bbox.y_max))))
    if x2 > x1 and y2 > y1:
        mask[y1:y2, x1:x2] = 1
    return mask


def erode_mask_once(mask: np.ndarray, kernel: int = 3) -> np.ndarray:
    """Binary erode with a square kernel (OpenCV when available)."""
    if kernel < 1 or kernel % 2 == 0:
        raise ValueError("kernel must be odd and >= 1")
    binary = (mask > 0).astype(np.uint8)
    try:
        import cv2  # type: ignore

        k = np.ones((kernel, kernel), dtype=np.uint8)
        return (cv2.erode(binary, k, iterations=1) > 0).astype(np.uint8)
    except Exception:  # noqa: BLE001 - fall back for minimal test envs
        pad = kernel // 2
        padded = np.pad(binary, pad, mode="constant", constant_values=0)
        # Vectorised via 2D convolution with ones.
        from numpy.lib.stride_tricks import sliding_window_view

        windows = sliding_window_view(padded, (kernel, kernel))
        return (windows.sum(axis=(-1, -2)) == kernel * kernel).astype(np.uint8)


def _median_mad_spread(samples: np.ndarray) -> Tuple[float, float, float]:
    med = float(np.median(samples))
    mad = float(np.median(np.abs(samples - med)))
    p10 = float(np.percentile(samples, 10))
    p90 = float(np.percentile(samples, 90))
    return med, mad, p90 - p10


def sample_visible_surface(
    depth_m: np.ndarray,
    bbox: BoundingBox2D,
    calib: CameraCalibration,
    *,
    min_depth_m: float = 0.5,
    max_depth_m: float = 1.5,
    mask_threshold_pixels: int = 25,
    mask_erode_kernel: int = 3,
    patch_size: int = 7,
    min_patch_pixels: int = 25,
    min_valid_depth_fraction: float = 0.60,
    max_depth_mad_m: float = 0.020,
    max_depth_spread_m: float = 0.050,
    mask: Optional[np.ndarray] = None,
    mask_source: str = "bbox_fill",
) -> SurfaceSampleResult:
    """Pick a local visible-surface sample inside the target mask / bbox."""
    nan = (float("nan"), float("nan"), float("nan"))
    h, w = depth_m.shape[:2]
    if calib.width and calib.height and (calib.width != w or calib.height != h):
        return SurfaceSampleResult(
            False,
            "INPUT_INVALID",
            POSITION_REFERENCE,
            float("nan"),
            float("nan"),
            0.0,
            nan,
            mask_source,
        )

    if mask is None:
        mask = bbox_fill_mask(bbox, h, w)
        mask_source = "bbox_fill"
    eroded = erode_mask_once(mask, kernel=int(mask_erode_kernel))
    # Keep erode inside bbox.
    bbox_mask = bbox_fill_mask(bbox, h, w)
    eroded = eroded & bbox_mask

    if int(eroded.sum()) < mask_threshold_pixels:
        return SurfaceSampleResult(
            False,
            "MASK_TOO_SMALL",
            POSITION_REFERENCE,
            float("nan"),
            float("nan"),
            0.0,
            nan,
            mask_source,
        )

    ys, xs = np.where(eroded > 0)
    depth_vals = depth_m[ys, xs]
    finite = np.isfinite(depth_vals)
    in_range = finite & (depth_vals >= min_depth_m) & (depth_vals <= max_depth_m)
    if not np.any(in_range):
        return SurfaceSampleResult(
            False,
            "DEPTH_INSUFFICIENT",
            POSITION_REFERENCE,
            float("nan"),
            float("nan"),
            0.0,
            nan,
            mask_source,
        )

    cx, cy = float(bbox.center_x), float(bbox.center_y)
    cand_x = xs[in_range]
    cand_y = ys[in_range]
    dist2 = (cand_x - cx) ** 2 + (cand_y - cy) ** 2
    # Nearest to centre; ties by row then column.
    order = np.lexsort((cand_x, cand_y, dist2))
    ref_u = float(cand_x[order[0]])
    ref_v = float(cand_y[order[0]])

    half = patch_size // 2
    u0 = int(round(ref_u))
    v0 = int(round(ref_v))
    y1 = max(0, v0 - half)
    y2 = min(h, v0 + half + 1)
    x1 = max(0, u0 - half)
    x2 = min(w, u0 + half + 1)
    patch_erode = eroded[y1:y2, x1:x2] > 0
    patch_depth = depth_m[y1:y2, x1:x2]
    patch_vals = patch_depth[patch_erode]
    if patch_vals.size < min_patch_pixels:
        return SurfaceSampleResult(
            False,
            "DEPTH_INSUFFICIENT",
            POSITION_REFERENCE,
            ref_u,
            ref_v,
            0.0,
            nan,
            mask_source,
        )
    finite_patch = patch_vals[np.isfinite(patch_vals)]
    in_range_patch = finite_patch[
        (finite_patch >= min_depth_m) & (finite_patch <= max_depth_m)
    ]
    frac = float(in_range_patch.size) / float(patch_vals.size)
    if frac < min_valid_depth_fraction or in_range_patch.size < min_patch_pixels:
        return SurfaceSampleResult(
            False,
            "DEPTH_INSUFFICIENT",
            POSITION_REFERENCE,
            ref_u,
            ref_v,
            frac,
            nan,
            mask_source,
        )

    med, mad, spread = _median_mad_spread(in_range_patch)
    if mad > max_depth_mad_m or spread > max_depth_spread_m:
        return SurfaceSampleResult(
            False,
            "DEPTH_DISCONTINUITY",
            POSITION_REFERENCE,
            ref_u,
            ref_v,
            frac,
            nan,
            mask_source,
        )

    xyz = project_optical_xyz(ref_u, ref_v, med, calib)
    if not all(np.isfinite(xyz)):
        return SurfaceSampleResult(
            False,
            "INPUT_INVALID",
            POSITION_REFERENCE,
            ref_u,
            ref_v,
            frac,
            nan,
            mask_source,
        )
    if not (min_depth_m <= xyz[2] <= max_depth_m):
        return SurfaceSampleResult(
            False,
            "DEPTH_INSUFFICIENT",
            POSITION_REFERENCE,
            ref_u,
            ref_v,
            frac,
            nan,
            mask_source,
        )
    return SurfaceSampleResult(
        True,
        "OK",
        POSITION_REFERENCE,
        ref_u,
        ref_v,
        frac,
        xyz,
        mask_source,
    )
