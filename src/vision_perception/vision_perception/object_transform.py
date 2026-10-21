"""Camera→target frame transform for VisionObject batches (W5, pure math).

Contract (delivery plan §4.5):
  p_target = R_target_from_source @ p_source + t_target_from_source  (metres)

- Does not publish TF, cmd_vel, or arm goals.
- Invalid source positions stay invalid (same reason, NaN).
- Missing / expired transform → keep object, position_valid=false, INPUT_INVALID.
- orientation_valid always false (extrinsics rotation is NOT object orientation).
- bbox / reference_u/v remain source-image pixels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from vision_perception.objects_pipeline import Object3D, ObjectBatch
from vision_perception.types import DetectionBatch, FrameKey


NAN_XYZ = (float("nan"), float("nan"), float("nan"))
NAN_QUAT = (float("nan"), float("nan"), float("nan"), float("nan"))


@dataclass(frozen=True)
class RigidTransform:
    """Rigid transform: p_target = R @ p_source + t (metres)."""

    rotation: Tuple[Tuple[float, float, float], ...]  # 3x3 row-major
    translation: Tuple[float, float, float]
    source_frame: str
    target_frame: str
    extrinsics_id: str = ""
    source_note: str = ""
    calibration_date: str = ""

    def as_matrix(self) -> np.ndarray:
        r = np.asarray(self.rotation, dtype=np.float64)
        if r.shape != (3, 3):
            raise ValueError(f"rotation must be 3x3, got {r.shape}")
        return r

    def apply(self, xyz: Sequence[float]) -> Tuple[float, float, float]:
        p = np.asarray(xyz, dtype=np.float64).reshape(3)
        if not np.all(np.isfinite(p)):
            return NAN_XYZ
        out = self.as_matrix() @ p + np.asarray(self.translation, dtype=np.float64)
        return (float(out[0]), float(out[1]), float(out[2]))


def quat_xyzw_to_rotation_matrix(
    x: float, y: float, z: float, w: float
) -> Tuple[Tuple[float, float, float], ...]:
    """Unit quaternion (x,y,z,w) → 3x3 rotation (active, p' = R p)."""
    n = math.sqrt(x * x + y * y + z * z + w * w)
    if n < 1e-12:
        raise ValueError("quaternion norm too small")
    x, y, z, w = x / n, y / n, z / n, w / n
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return (
        (1.0 - 2.0 * (yy + zz), 2.0 * (xy - wz), 2.0 * (xz + wy)),
        (2.0 * (xy + wz), 1.0 - 2.0 * (xx + zz), 2.0 * (yz - wx)),
        (2.0 * (xz - wy), 2.0 * (yz + wx), 1.0 - 2.0 * (xx + yy)),
    )


def rotation_matrix_from_rpy_xyz(
    roll: float, pitch: float, yaw: float
) -> Tuple[Tuple[float, float, float], ...]:
    """Intrinsic XYZ (roll-pitch-yaw) radians → R such that p' = R p."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    # R = Rz(yaw) @ Ry(pitch) @ Rx(roll)
    r00 = cy * cp
    r01 = cy * sp * sr - sy * cr
    r02 = cy * sp * cr + sy * sr
    r10 = sy * cp
    r11 = sy * sp * sr + cy * cr
    r12 = sy * sp * cr - cy * sr
    r20 = -sp
    r21 = cp * sr
    r22 = cp * cr
    return (
        (r00, r01, r02),
        (r10, r11, r12),
        (r20, r21, r22),
    )


def rigid_transform_from_mapping(raw: Mapping[str, Any]) -> RigidTransform:
    """Build RigidTransform from YAML-like mapping. No unit-matrix default."""
    source_frame = str(raw.get("source_frame", "")).strip()
    target_frame = str(raw.get("target_frame", "")).strip()
    if not source_frame or not target_frame:
        raise ValueError("source_frame and target_frame are required")
    if source_frame == target_frame:
        raise ValueError("source_frame and target_frame must differ")

    t_raw = raw.get("translation_m")
    if t_raw is None:
        raise ValueError("translation_m [x,y,z] metres is required (no default)")
    t = tuple(float(v) for v in t_raw)
    if len(t) != 3:
        raise ValueError("translation_m must have 3 elements")

    rot = raw.get("rotation")
    if rot is None:
        raise ValueError(
            "rotation is required: either rotation.matrix 3x3 or "
            "rotation.quaternion_xyzw [x,y,z,w] or rotation.rpy_xyz_rad [r,p,y]"
        )
    if not isinstance(rot, Mapping):
        raise ValueError("rotation must be a mapping")

    if "matrix" in rot:
        mat = rot["matrix"]
        rows = tuple(tuple(float(c) for c in row) for row in mat)
        if len(rows) != 3 or any(len(r) != 3 for r in rows):
            raise ValueError("rotation.matrix must be 3x3")
        # Orthogonality soft-check
        r = np.asarray(rows, dtype=np.float64)
        if abs(abs(np.linalg.det(r)) - 1.0) > 1e-3:
            raise ValueError("rotation.matrix determinant must be ±1")
    elif "quaternion_xyzw" in rot:
        q = tuple(float(v) for v in rot["quaternion_xyzw"])
        if len(q) != 4:
            raise ValueError("quaternion_xyzw must have 4 elements")
        rows = quat_xyzw_to_rotation_matrix(*q)
    elif "rpy_xyz_rad" in rot:
        rpy = tuple(float(v) for v in rot["rpy_xyz_rad"])
        if len(rpy) != 3:
            raise ValueError("rpy_xyz_rad must have 3 elements")
        rows = rotation_matrix_from_rpy_xyz(*rpy)
    else:
        raise ValueError(
            "rotation needs matrix | quaternion_xyzw | rpy_xyz_rad "
            "(identity / missing extrinsics are rejected)"
        )

    return RigidTransform(
        rotation=rows,
        translation=t,
        source_frame=source_frame,
        target_frame=target_frame,
        extrinsics_id=str(raw.get("extrinsics_id", "")),
        source_note=str(raw.get("source_note", "")),
        calibration_date=str(raw.get("calibration_date", "")),
    )


@dataclass(frozen=True)
class TransformOutcome:
    """Per-batch transform result metadata (for diagnostics)."""

    ok: bool
    reason: str  # OK / TRANSFORM_DISABLED / TRANSFORM_MISSING / INPUT_INVALID / ...
    target_frame: str
    source_frame: str
    extrinsics_id: str = ""


def _invalidate(
    obj: Object3D, *, reason: str
) -> Object3D:
    return replace(
        obj,
        position_xyz=NAN_XYZ,
        position_valid=False,
        invalid_reason=reason,
        orientation_xyzw=NAN_QUAT,
        orientation_valid=False,
    )


def transform_object3d(
    obj: Object3D,
    rigid: RigidTransform,
    *,
    transform_available: bool,
    transform_fail_reason: str = "INPUT_INVALID",
) -> Object3D:
    """Transform one object. Never forges validity from a failed source."""
    if not obj.position_valid:
        # Keep original invalid reason and NaN; do not flip valid via TF.
        return replace(
            obj,
            orientation_xyzw=NAN_QUAT,
            orientation_valid=False,
        )
    if not transform_available:
        return _invalidate(obj, reason=transform_fail_reason or "INPUT_INVALID")
    xyz = rigid.apply(obj.position_xyz)
    if not all(math.isfinite(v) for v in xyz):
        return _invalidate(obj, reason="INPUT_INVALID")
    return replace(
        obj,
        position_xyz=xyz,
        position_valid=True,
        invalid_reason="OK",
        orientation_xyzw=NAN_QUAT,
        orientation_valid=False,
    )


def transform_object_batch(
    batch: ObjectBatch,
    *,
    rigid: Optional[RigidTransform],
    enabled: bool,
    transform_available: bool,
    transform_fail_reason: str = "INPUT_INVALID",
    expected_source_frame: str = "",
) -> Tuple[ObjectBatch, TransformOutcome]:
    """Return a new ObjectBatch in target_frame (or invalidated copy).

    Camera /objects topic is never modified here — caller publishes separately.
    """
    if not enabled:
        # Disabled: return empty-like invalid markers without claiming success.
        objects = tuple(
            _invalidate(o, reason="INPUT_INVALID") if o.position_valid else o
            for o in batch.objects
        )
        return (
            replace(batch, objects=objects),
            TransformOutcome(
                ok=False,
                reason="TRANSFORM_DISABLED",
                target_frame="",
                source_frame="",
            ),
        )

    if rigid is None:
        objects = tuple(
            _invalidate(o, reason=transform_fail_reason or "INPUT_INVALID")
            if o.position_valid
            else replace(o, orientation_valid=False, orientation_xyzw=NAN_QUAT)
            for o in batch.objects
        )
        return (
            replace(batch, objects=objects),
            TransformOutcome(
                ok=False,
                reason="TRANSFORM_MISSING",
                target_frame="",
                source_frame=expected_source_frame,
            ),
        )

    src_key = batch.detection_batch.key
    if expected_source_frame and src_key.frame_id:
        if src_key.frame_id != expected_source_frame and src_key.frame_id != rigid.source_frame:
            objects = tuple(
                _invalidate(o, reason="INPUT_INVALID")
                if o.position_valid
                else replace(o, orientation_valid=False, orientation_xyzw=NAN_QUAT)
                for o in batch.objects
            )
            return (
                replace(batch, objects=objects),
                TransformOutcome(
                    ok=False,
                    reason="INPUT_INVALID",
                    target_frame=rigid.target_frame,
                    source_frame=src_key.frame_id,
                    extrinsics_id=rigid.extrinsics_id,
                ),
            )

    # Prefer configured source_frame on the rigid for header rewrite.
    source_frame = rigid.source_frame or src_key.frame_id
    new_key = FrameKey(
        source_session_id=src_key.source_session_id,
        observation_id=src_key.observation_id,
        source_kind=src_key.source_kind,
        calibration_id=src_key.calibration_id,
        frame_id=rigid.target_frame,
        source_stamp_sec=src_key.source_stamp_sec,
        source_stamp_nanosec=src_key.source_stamp_nanosec,
        source_image_id=src_key.source_image_id,
    )
    new_det_batch = DetectionBatch(
        key=new_key,
        detections=batch.detection_batch.detections,
        image_width=batch.detection_batch.image_width,
        image_height=batch.detection_batch.image_height,
    )
    objects = tuple(
        transform_object3d(
            o,
            rigid,
            transform_available=transform_available,
            transform_fail_reason=transform_fail_reason,
        )
        for o in batch.objects
    )
    outcome = TransformOutcome(
        ok=bool(transform_available),
        reason="OK" if transform_available else (transform_fail_reason or "INPUT_INVALID"),
        target_frame=rigid.target_frame,
        source_frame=source_frame,
        extrinsics_id=rigid.extrinsics_id,
    )
    return (
        replace(batch, detection_batch=new_det_batch, objects=objects),
        outcome,
    )


def object_batch_from_vision_object_array_dict(
    payload: Mapping[str, Any],
) -> ObjectBatch:
    """Rebuild a minimal ObjectBatch from a VisionObjectArray-shaped dict (tests)."""
    from vision_perception.objects_pipeline import Object3D as O3
    from vision_perception.types import DetectionBatch, FrameKey

    header = payload.get("header", {})
    stamp = header.get("stamp", {})
    key = FrameKey(
        source_session_id=str(payload.get("source_session_id", "")),
        observation_id=int(payload.get("observation_id", 0)),
        source_kind=str(payload.get("source_kind", "")),
        calibration_id=str(payload.get("calibration_id", "")),
        frame_id=str(header.get("frame_id", "")),
        source_stamp_sec=int(stamp.get("sec", 0)),
        source_stamp_nanosec=int(stamp.get("nanosec", 0)),
    )
    objects: List[O3] = []
    for item in payload.get("objects", []):
        pos = item.get("position", {})
        ori = item.get("orientation", {})
        bbox = item.get("bbox", {})
        objects.append(
            O3(
                detection_index=int(item.get("detection_index", 0)),
                class_name=str(item.get("class_name", "")),
                confidence=float(item.get("confidence", 0.0)),
                bbox_center_x=float(bbox.get("center_x", 0.0)),
                bbox_center_y=float(bbox.get("center_y", 0.0)),
                bbox_size_x=float(bbox.get("size_x", 0.0)),
                bbox_size_y=float(bbox.get("size_y", 0.0)),
                bbox_theta=float(bbox.get("theta", 0.0)),
                position_xyz=(
                    float(pos.get("x", float("nan"))),
                    float(pos.get("y", float("nan"))),
                    float(pos.get("z", float("nan"))),
                ),
                position_valid=bool(item.get("position_valid", False)),
                position_reference=str(item.get("position_reference", "")),
                invalid_reason=str(item.get("invalid_reason", "")),
                reference_u=float(item.get("reference_u", float("nan"))),
                reference_v=float(item.get("reference_v", float("nan"))),
                valid_depth_fraction=float(item.get("valid_depth_fraction", 0.0)),
                orientation_xyzw=(
                    float(ori.get("x", float("nan"))),
                    float(ori.get("y", float("nan"))),
                    float(ori.get("z", float("nan"))),
                    float(ori.get("w", float("nan"))),
                ),
                orientation_valid=False,
                tracking_valid=bool(item.get("tracking_valid", False)),
                object_id=str(item.get("object_id", "")),
                mask_source=str(item.get("mask_source", "")),
            )
        )
    det_batch = DetectionBatch(key=key, detections=(), image_width=0, image_height=0)
    return ObjectBatch(
        detection_batch=det_batch,
        objects=tuple(objects),
        tracking_session_id=str(payload.get("tracking_session_id", "")),
        depth_paired=True,
        pair_skew_sec=None,
        pair_reason="OK",
        calibration_id=str(payload.get("calibration_id", "")),
    )


def example_static_extrinsics_dict() -> Dict[str, Any]:
    """Documented example — NOT a real robot calibration. Do not use as default."""
    return {
        "enabled": False,
        "mode": "static_extrinsics",
        "source_frame": "zed_left_camera_optical_frame",
        "target_frame": "peer_arm_base",
        "extrinsics_id": "EXAMPLE_ONLY_NOT_CALIBRATED",
        "calibration_date": "YYYY-MM-DD",
        "source_note": (
            "p_target = R_target_from_source * p_source + t; "
            "quaternion_xyzw is target←source orientation; "
            "translation_m is origin_source expressed in target frame."
        ),
        "translation_m": [0.0, 0.0, 0.0],
        "rotation": {
            # Identity shown only as format example; enabled must stay false
            # until peer fills a real calibration.
            "quaternion_xyzw": [0.0, 0.0, 0.0, 1.0],
        },
        "tf_timeout_sec": 0.05,
        "objects_input_topic": "/dg/vision/objects",
        "objects_target_topic": "/dg/vision/objects_target",
        "status_topic": "/dg/vision/transform_status",
    }
