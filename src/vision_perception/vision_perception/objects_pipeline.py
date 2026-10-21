"""Build VisionObject batches from 2D detections + paired depth (V2).

Optional V3: apply_track_assignments fills object_id / tracking_valid.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import List, Mapping, Optional, Sequence, Tuple

import numpy as np

from vision_perception.depth_io import CameraCalibration, DepthFrame
from vision_perception.surface_sample import sample_visible_surface
from vision_perception.tracker import TrackAssignment, assignments_by_detection_index
from vision_perception.types import (
    POSITION_REFERENCE,
    Detection,
    DetectionBatch,
    detection_mask_or_none,
)


@dataclass(frozen=True)
class Object3D:
    detection_index: int
    class_name: str
    confidence: float
    bbox_center_x: float
    bbox_center_y: float
    bbox_size_x: float
    bbox_size_y: float
    bbox_theta: float
    position_xyz: Tuple[float, float, float]
    position_valid: bool
    position_reference: str
    invalid_reason: str
    reference_u: float
    reference_v: float
    valid_depth_fraction: float
    orientation_xyzw: Tuple[float, float, float, float]
    orientation_valid: bool
    tracking_valid: bool
    object_id: str
    mask_source: str


@dataclass(frozen=True)
class ObjectBatch:
    detection_batch: DetectionBatch
    objects: Tuple[Object3D, ...]
    tracking_session_id: str
    depth_paired: bool
    pair_skew_sec: Optional[float]
    pair_reason: str
    calibration_id: str
    mask_source: str = "bbox_fill"
    # Count of detections that fell back to bbox or were rejected for mask reasons.
    mask_degraded_count: int = 0
    registration_reason: str = "OK"


def _nan_quat() -> Tuple[float, float, float, float]:
    return (float("nan"), float("nan"), float("nan"), float("nan"))


def _nan_xyz() -> Tuple[float, float, float]:
    return (float("nan"), float("nan"), float("nan"))


def object_from_unpaired_detection(det: Detection) -> Object3D:
    return Object3D(
        detection_index=int(det.detection_index),
        class_name=det.class_name,
        confidence=float(det.confidence),
        bbox_center_x=float(det.bbox.center_x),
        bbox_center_y=float(det.bbox.center_y),
        bbox_size_x=float(det.bbox.size_x),
        bbox_size_y=float(det.bbox.size_y),
        bbox_theta=float(det.bbox.theta),
        position_xyz=_nan_xyz(),
        position_valid=False,
        position_reference=POSITION_REFERENCE,
        invalid_reason="DEPTH_UNPAIRED",
        reference_u=float("nan"),
        reference_v=float("nan"),
        valid_depth_fraction=0.0,
        orientation_xyzw=_nan_quat(),
        orientation_valid=False,
        tracking_valid=False,
        object_id="",
        mask_source="none",
    )


def _invalid_object(
    det: Detection,
    *,
    invalid_reason: str,
    mask_source: str,
) -> Object3D:
    return Object3D(
        detection_index=int(det.detection_index),
        class_name=det.class_name,
        confidence=float(det.confidence),
        bbox_center_x=float(det.bbox.center_x),
        bbox_center_y=float(det.bbox.center_y),
        bbox_size_x=float(det.bbox.size_x),
        bbox_size_y=float(det.bbox.size_y),
        bbox_theta=float(det.bbox.theta),
        position_xyz=_nan_xyz(),
        position_valid=False,
        position_reference=POSITION_REFERENCE,
        invalid_reason=invalid_reason,
        reference_u=float("nan"),
        reference_v=float("nan"),
        valid_depth_fraction=0.0,
        orientation_xyzw=_nan_quat(),
        orientation_valid=False,
        tracking_valid=False,
        object_id="",
        mask_source=mask_source,
    )


def _registration_failure_reason(
    detection_batch: DetectionBatch,
    depth: DepthFrame,
    calibration: CameraCalibration,
    *,
    require_rgb_depth_same_size: bool,
    require_depth_calib_same_frame: bool,
) -> Optional[str]:
    """Return invalid_reason when RGB/depth/CameraInfo are not registerable."""
    depth_h, depth_w = depth.depth_m.shape[:2]
    if (calibration.height, calibration.width) != (depth_h, depth_w):
        return "INPUT_INVALID"
    if require_rgb_depth_same_size:
        img_w = int(detection_batch.image_width)
        img_h = int(detection_batch.image_height)
        if img_w > 0 and img_h > 0 and (img_h, img_w) != (depth_h, depth_w):
            return "INPUT_INVALID"
    if require_depth_calib_same_frame:
        depth_frame = str(depth.frame_id or "").strip()
        calib_frame = str(calibration.frame_id or "").strip()
        if depth_frame and calib_frame and depth_frame != calib_frame:
            return "INPUT_INVALID"
    return None


def build_object_batch(
    detection_batch: DetectionBatch,
    *,
    depth: Optional[DepthFrame],
    calibration: Optional[CameraCalibration],
    pair_skew_sec: Optional[float] = None,
    pair_reason: str = "DEPTH_UNPAIRED",
    min_depth_m: float = 0.5,
    max_depth_m: float = 1.5,
    tracking_session_id: str = "",
    mask_erode_kernel: int = 3,
    depth_patch_size: int = 7,
    min_patch_pixels: int = 25,
    min_valid_depth_fraction: float = 0.60,
    max_depth_mad_m: float = 0.020,
    max_depth_spread_m: float = 0.050,
    allow_bbox_mask_fallback: bool = True,
    require_rgb_depth_same_size: bool = True,
    require_depth_calib_same_frame: bool = True,
) -> ObjectBatch:
    """One Object3D per retained 2D detection (including depth failures).

    Invalid detections are retained with NaN positions — never drop or zero-fill.
    When ``allow_bbox_mask_fallback`` is False, missing/mismatched instance masks
    yield ``MASK_DEGRADED`` (diagnosable) instead of silently sampling the bbox.
    """
    detections: Sequence[Detection] = detection_batch.detections
    if depth is None or calibration is None or pair_reason != "OK":
        objects = tuple(object_from_unpaired_detection(d) for d in detections)
        return ObjectBatch(
            detection_batch=detection_batch,
            objects=objects,
            tracking_session_id=tracking_session_id,
            depth_paired=False,
            pair_skew_sec=pair_skew_sec,
            pair_reason="DEPTH_UNPAIRED",
            calibration_id=calibration.calibration_id if calibration else "",
            mask_source="bbox_fill",
            mask_degraded_count=0,
            registration_reason="DEPTH_UNPAIRED",
        )

    reg_reason = _registration_failure_reason(
        detection_batch,
        depth,
        calibration,
        require_rgb_depth_same_size=require_rgb_depth_same_size,
        require_depth_calib_same_frame=require_depth_calib_same_frame,
    )
    if reg_reason is not None:
        objects = tuple(
            _invalid_object(d, invalid_reason=reg_reason, mask_source="none")
            for d in detections
        )
        return ObjectBatch(
            detection_batch=detection_batch,
            objects=objects,
            tracking_session_id=tracking_session_id,
            depth_paired=True,
            pair_skew_sec=pair_skew_sec,
            pair_reason=pair_reason,
            calibration_id=calibration.calibration_id,
            mask_source="none",
            mask_degraded_count=0,
            registration_reason=reg_reason,
        )

    built: List[Object3D] = []
    batch_mask_source = "yolo_seg"
    mask_degraded_count = 0
    for det in detections:
        inst_mask = detection_mask_or_none(det)
        mask_kw = {}
        used_source = "bbox_fill"
        degraded = False
        if inst_mask is not None and det.mask_source == "yolo_seg":
            if inst_mask.shape[:2] == depth.depth_m.shape[:2]:
                mask_kw = {"mask": inst_mask, "mask_source": "yolo_seg"}
                used_source = "yolo_seg"
            else:
                # Mask plane does not match registered depth — diagnosable degrade.
                degraded = True
                mask_degraded_count += 1
                if not allow_bbox_mask_fallback:
                    built.append(
                        _invalid_object(
                            det,
                            invalid_reason="MASK_DEGRADED",
                            mask_source="mask_size_mismatch",
                        )
                    )
                    continue
                used_source = "bbox_fill_after_mask_mismatch"
        else:
            # No usable instance mask.
            degraded = True
            mask_degraded_count += 1
            if not allow_bbox_mask_fallback:
                built.append(
                    _invalid_object(
                        det,
                        invalid_reason="MASK_DEGRADED",
                        mask_source="bbox_fallback_rejected",
                    )
                )
                continue
            used_source = "bbox_fill"

        if used_source != "yolo_seg":
            batch_mask_source = used_source if degraded else batch_mask_source
            if batch_mask_source == "yolo_seg":
                batch_mask_source = used_source

        sample = sample_visible_surface(
            depth.depth_m,
            det.bbox,
            calibration,
            min_depth_m=min_depth_m,
            max_depth_m=max_depth_m,
            mask_threshold_pixels=int(min_patch_pixels),
            mask_erode_kernel=int(mask_erode_kernel),
            patch_size=int(depth_patch_size),
            min_patch_pixels=int(min_patch_pixels),
            min_valid_depth_fraction=float(min_valid_depth_fraction),
            max_depth_mad_m=float(max_depth_mad_m),
            max_depth_spread_m=float(max_depth_spread_m),
            **mask_kw,
        )
        # Prefer the resolved source label (includes mismatch fallback tag).
        mask_source = used_source if used_source != "yolo_seg" else sample.mask_source
        built.append(
            Object3D(
                detection_index=int(det.detection_index),
                class_name=det.class_name,
                confidence=float(det.confidence),
                bbox_center_x=float(det.bbox.center_x),
                bbox_center_y=float(det.bbox.center_y),
                bbox_size_x=float(det.bbox.size_x),
                bbox_size_y=float(det.bbox.size_y),
                bbox_theta=float(det.bbox.theta),
                position_xyz=sample.xyz,
                position_valid=bool(sample.position_valid),
                position_reference=sample.position_reference,
                invalid_reason=sample.invalid_reason,
                reference_u=float(sample.reference_u),
                reference_v=float(sample.reference_v),
                valid_depth_fraction=float(sample.valid_depth_fraction),
                orientation_xyzw=_nan_quat(),
                orientation_valid=False,
                tracking_valid=False,
                object_id="",
                mask_source=mask_source,
            )
        )

    if not detections:
        batch_mask_source = "none"
        mask_degraded_count = 0
    elif mask_degraded_count == 0:
        batch_mask_source = "yolo_seg"
    elif mask_degraded_count == len(detections):
        # All degraded / rejected.
        if any(o.mask_source == "bbox_fallback_rejected" for o in built):
            batch_mask_source = "bbox_fallback_rejected"
        elif any(o.mask_source == "mask_size_mismatch" for o in built):
            batch_mask_source = "mask_size_mismatch"
        else:
            batch_mask_source = "bbox_fill"

    return ObjectBatch(
        detection_batch=detection_batch,
        objects=tuple(built),
        tracking_session_id=tracking_session_id,
        depth_paired=True,
        pair_skew_sec=pair_skew_sec,
        pair_reason=pair_reason,
        calibration_id=calibration.calibration_id,
        mask_source=batch_mask_source,
        mask_degraded_count=int(mask_degraded_count),
        registration_reason="OK",
    )


def apply_track_assignments(
    batch: ObjectBatch,
    assignments: Sequence[TrackAssignment],
    *,
    tracking_session_id: str,
) -> ObjectBatch:
    """Attach V3 identity fields to each Object3D (by detection_index).

    Unmatched / tentative detections keep empty object_id and tracking_valid=false.
    Does not invent historical boxes; only annotates current-frame objects.
    Never copies a previous valid XYZ onto a currently invalid observation.
    """
    by_index: Mapping[int, TrackAssignment] = assignments_by_detection_index(assignments)
    updated: List[Object3D] = []
    for obj in batch.objects:
        assignment = by_index.get(int(obj.detection_index))
        if assignment is None:
            updated.append(
                replace(obj, tracking_valid=False, object_id="")
            )
        else:
            updated.append(
                replace(
                    obj,
                    tracking_valid=bool(assignment.tracking_valid),
                    object_id=str(assignment.object_id or ""),
                )
            )
    return replace(
        batch,
        objects=tuple(updated),
        tracking_session_id=str(tracking_session_id or ""),
    )
