"""Immutable observation types shared by offline and future ROS adapters.

Pure-Python / NumPy only. Do not import rclpy here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np


ALLOWED_CLASSES = ("bottle", "cup")
SOURCE_KIND_LIVE = "LIVE_CAMERA"
SOURCE_KIND_RECORDED = "RECORDED_CAMERA"
SOURCE_KIND_FILE = "OFFLINE_FILE"

INVALID_REASONS = (
    "OK",
    "DEPTH_UNPAIRED",
    "MASK_TOO_SMALL",
    "DEPTH_INSUFFICIENT",
    "DEPTH_DISCONTINUITY",
    "INPUT_INVALID",
    "STALE",
)

POSITION_REFERENCE = "visible_surface_sample"


@dataclass(frozen=True)
class BoundingBox2D:
    """Axis-aligned box in original image pixels (centre + size)."""

    center_x: float
    center_y: float
    size_x: float
    size_y: float
    theta: float = 0.0

    @property
    def x_min(self) -> float:
        return self.center_x - 0.5 * self.size_x

    @property
    def y_min(self) -> float:
        return self.center_y - 0.5 * self.size_y

    @property
    def x_max(self) -> float:
        return self.center_x + 0.5 * self.size_x

    @property
    def y_max(self) -> float:
        return self.center_y + 0.5 * self.size_y

    def as_xyxy(self) -> Tuple[float, float, float, float]:
        return (self.x_min, self.y_min, self.x_max, self.y_max)

    @classmethod
    def from_xyxy(cls, x1: float, y1: float, x2: float, y2: float) -> "BoundingBox2D":
        size_x = max(0.0, x2 - x1)
        size_y = max(0.0, y2 - y1)
        return cls(
            center_x=x1 + 0.5 * size_x,
            center_y=y1 + 0.5 * size_y,
            size_x=size_x,
            size_y=size_y,
        )


@dataclass(frozen=True)
class Detection:
    """One filtered 2D detection before ROS message mapping.

    Optional ``mask`` is HxW uint8 (0/1) in original image coordinates when
    YOLO-seg reconstruction succeeded; otherwise None and surface sampling
    falls back to bbox_fill.
    """

    detection_index: int
    class_name: str
    confidence: float
    bbox: BoundingBox2D
    mask: Optional[Any] = None  # np.ndarray | None; Any avoids dataclass hash issues
    mask_source: str = ""


@dataclass(frozen=True)
class LetterboxMeta:
    """Scale and padding needed to map model coordinates back to the source image."""

    scale: float
    pad_left: int
    pad_top: int
    pad_right: int
    pad_bottom: int
    source_width: int
    source_height: int
    model_size: int = 640


@dataclass(frozen=True)
class FrameKey:
    """Shared observation key for 2D/3D association (no array-index coupling)."""

    source_session_id: str
    observation_id: int
    source_kind: str
    calibration_id: str = ""
    frame_id: str = ""
    source_stamp_sec: int = 0
    source_stamp_nanosec: int = 0
    source_image_id: str = ""


@dataclass(frozen=True)
class DetectionBatch:
    """One processed observation of 2D detections."""

    key: FrameKey
    detections: Tuple[Detection, ...] = field(default_factory=tuple)
    image_width: int = 0
    image_height: int = 0

    def sorted_detections(self) -> List[Detection]:
        return list(self.detections)


@dataclass(frozen=True)
class ModelManifest:
    """Validated local ONNX contract. Weights are never auto-downloaded."""

    source: str
    onnx_sha256: str
    license: str
    input_name: str
    input_shape: Tuple[int, ...]
    output0_shape: Tuple[int, ...]
    output1_shape: Tuple[int, ...]
    class_map: dict
    weights_sha256: str = ""
    export_tool_versions: Optional[dict] = None

    def class_id_to_name(self) -> dict:
        return {int(v): str(k) for k, v in self.class_map.items()}


def clip_box_to_image(
    x1: float, y1: float, x2: float, y2: float, width: int, height: int
) -> Optional[Tuple[float, float, float, float]]:
    """Clip an xyxy box to image bounds; return None if degenerate after clip."""
    x1 = max(0.0, min(float(width), x1))
    y1 = max(0.0, min(float(height), y1))
    x2 = max(0.0, min(float(width), x2))
    y2 = max(0.0, min(float(height), y2))
    if x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def validate_class_name(class_name: str) -> str:
    if class_name not in ALLOWED_CLASSES:
        raise ValueError(f"Unsupported class_name={class_name!r}; allowed={ALLOWED_CLASSES}")
    return class_name


def sort_detections_deterministic(items: Sequence[Detection]) -> List[Detection]:
    """Score desc, then class_name, then original-image geometry; reassign indices."""
    ordered = sorted(
        items,
        key=lambda d: (
            -float(d.confidence),
            d.class_name,
            float(d.bbox.center_x),
            float(d.bbox.center_y),
            float(d.bbox.size_x),
            float(d.bbox.size_y),
        ),
    )
    return [
        Detection(
            detection_index=index,
            class_name=item.class_name,
            confidence=item.confidence,
            bbox=item.bbox,
            mask=item.mask,
            mask_source=item.mask_source,
        )
        for index, item in enumerate(ordered)
    ]


def detection_mask_or_none(detection: Detection) -> Optional[np.ndarray]:
    """Return a contiguous uint8 HxW mask when present and non-empty."""
    mask = detection.mask
    if mask is None:
        return None
    array = np.asarray(mask)
    if array.ndim != 2 or array.size == 0:
        return None
    return np.ascontiguousarray((array > 0).astype(np.uint8))
