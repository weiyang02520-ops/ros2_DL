"""Map pure DetectionBatch / ObjectBatch to dicts / optional ROS messages.

ROS message imports are optional so unit tests run without a Humble install.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, TYPE_CHECKING

from vision_perception.types import (
    POSITION_REFERENCE,
    Detection,
    DetectionBatch,
)

if TYPE_CHECKING:
    from vision_perception.objects_pipeline import Object3D, ObjectBatch


def detection_to_dict(detection: Detection) -> Dict[str, Any]:
    return {
        "detection_index": int(detection.detection_index),
        "class_name": detection.class_name,
        "confidence": float(detection.confidence),
        "bbox": {
            "center_x": float(detection.bbox.center_x),
            "center_y": float(detection.bbox.center_y),
            "size_x": float(detection.bbox.size_x),
            "size_y": float(detection.bbox.size_y),
            "theta": float(detection.bbox.theta),
        },
    }


def detection_batch_to_dict(batch: DetectionBatch) -> Dict[str, Any]:
    key = batch.key
    return {
        "header": {
            "frame_id": key.frame_id,
            "stamp": {
                "sec": int(key.source_stamp_sec),
                "nanosec": int(key.source_stamp_nanosec),
            },
        },
        "source_session_id": key.source_session_id,
        "observation_id": int(key.observation_id),
        "calibration_id": key.calibration_id,
        "source_kind": key.source_kind,
        "source_image_id": key.source_image_id,
        "image_width": int(batch.image_width),
        "image_height": int(batch.image_height),
        "detections": [detection_to_dict(item) for item in batch.detections],
    }


def nan_point_dict() -> Dict[str, float]:
    return {"x": float("nan"), "y": float("nan"), "z": float("nan")}


def nan_quaternion_dict() -> Dict[str, float]:
    return {"x": float("nan"), "y": float("nan"), "z": float("nan"), "w": float("nan")}


def placeholder_object_dict_from_detection(
    detection: Detection,
    *,
    frame_id: str = "",
    stamp_sec: int = 0,
    stamp_nanosec: int = 0,
    invalid_reason: str = "DEPTH_UNPAIRED",
) -> Dict[str, Any]:
    """V2-shaped object stub from a 2D detection. Not published in V1."""
    return {
        "header": {
            "frame_id": frame_id,
            "stamp": {"sec": stamp_sec, "nanosec": stamp_nanosec},
        },
        "detection_index": int(detection.detection_index),
        "object_id": "",
        "class_name": detection.class_name,
        "confidence": float(detection.confidence),
        "bbox": detection_to_dict(detection)["bbox"],
        "position": nan_point_dict(),
        "position_valid": False,
        "position_reference": POSITION_REFERENCE,
        "invalid_reason": invalid_reason,
        "reference_u": float("nan"),
        "reference_v": float("nan"),
        "valid_depth_fraction": 0.0,
        "orientation": nan_quaternion_dict(),
        # Plan §3: orientation_valid is false for V1–V3.
        "orientation_valid": False,
        "tracking_valid": False,
    }


def placeholder_object_array_dict_from_batch(
    batch: DetectionBatch,
    *,
    tracking_session_id: str = "",
    invalid_reason: str = "DEPTH_UNPAIRED",
) -> Dict[str, Any]:
    """VisionObjectArray-shaped dict for contract tests. Never published by V1."""
    key = batch.key
    objects = [
        placeholder_object_dict_from_detection(
            det,
            frame_id=key.frame_id,
            stamp_sec=key.source_stamp_sec,
            stamp_nanosec=key.source_stamp_nanosec,
            invalid_reason=invalid_reason,
        )
        for det in batch.detections
    ]
    return {
        "header": {
            "frame_id": key.frame_id,
            "stamp": {
                "sec": int(key.source_stamp_sec),
                "nanosec": int(key.source_stamp_nanosec),
            },
        },
        "source_session_id": key.source_session_id,
        "observation_id": int(key.observation_id),
        "calibration_id": key.calibration_id,
        "source_kind": key.source_kind,
        "tracking_session_id": tracking_session_id,
        "objects": objects,
        # Not a .msg field — mirrors status contract for offline JSON only.
        "arm_ready": "NO",
    }


# Field names required on VisionObject / VisionObjectArray dict shapes (plan §3).
VISION_OBJECT_DICT_FIELDS = (
    "header",
    "detection_index",
    "object_id",
    "class_name",
    "confidence",
    "bbox",
    "position",
    "position_valid",
    "position_reference",
    "invalid_reason",
    "reference_u",
    "reference_v",
    "valid_depth_fraction",
    "orientation",
    "orientation_valid",
    "tracking_valid",
)

VISION_OBJECT_ARRAY_DICT_FIELDS = (
    "header",
    "source_session_id",
    "observation_id",
    "calibration_id",
    "source_kind",
    "tracking_session_id",
    "objects",
)


def try_build_vision_detection_array_msg(batch: DetectionBatch):
    """Build vision_perception_interfaces/VisionDetectionArray when ROS msgs exist."""
    try:
        from vision_msgs.msg import BoundingBox2D, Pose2D
        from vision_perception_interfaces.msg import (
            VisionDetection2D,
            VisionDetectionArray,
        )
    except ImportError as exc:
        raise RuntimeError(
            "ROS message packages are unavailable in this environment"
        ) from exc

    message = VisionDetectionArray()
    message.header.frame_id = batch.key.frame_id
    message.header.stamp.sec = int(batch.key.source_stamp_sec)
    message.header.stamp.nanosec = int(batch.key.source_stamp_nanosec)
    message.source_session_id = batch.key.source_session_id
    message.observation_id = int(batch.key.observation_id)
    message.calibration_id = batch.key.calibration_id
    message.source_kind = batch.key.source_kind

    detections: List[Any] = []
    for item in batch.detections:
        det = VisionDetection2D()
        det.detection_index = int(item.detection_index)
        det.class_name = item.class_name
        det.confidence = float(item.confidence)
        bbox = BoundingBox2D()
        centre = Pose2D()
        centre.x = float(item.bbox.center_x)
        centre.y = float(item.bbox.center_y)
        centre.theta = float(item.bbox.theta)
        bbox.center = centre
        bbox.size_x = float(item.bbox.size_x)
        bbox.size_y = float(item.bbox.size_y)
        det.bbox = bbox
        detections.append(det)
    message.detections = detections
    return message


def object3d_to_dict(
    obj: "Object3D",
    *,
    frame_id: str = "",
    stamp_sec: int = 0,
    stamp_nanosec: int = 0,
) -> Dict[str, Any]:
    """Serialisable VisionObject-shaped dict from Object3D."""
    ox, oy, oz = obj.position_xyz
    qx, qy, qz, qw = obj.orientation_xyzw
    return {
        "header": {
            "frame_id": frame_id,
            "stamp": {"sec": int(stamp_sec), "nanosec": int(stamp_nanosec)},
        },
        "detection_index": int(obj.detection_index),
        "object_id": obj.object_id,
        "class_name": obj.class_name,
        "confidence": float(obj.confidence),
        "bbox": {
            "center_x": float(obj.bbox_center_x),
            "center_y": float(obj.bbox_center_y),
            "size_x": float(obj.bbox_size_x),
            "size_y": float(obj.bbox_size_y),
            "theta": float(obj.bbox_theta),
        },
        "position": {"x": float(ox), "y": float(oy), "z": float(oz)},
        "position_valid": bool(obj.position_valid),
        "position_reference": obj.position_reference,
        "invalid_reason": obj.invalid_reason,
        "reference_u": float(obj.reference_u),
        "reference_v": float(obj.reference_v),
        "valid_depth_fraction": float(obj.valid_depth_fraction),
        "orientation": {
            "x": float(qx),
            "y": float(qy),
            "z": float(qz),
            "w": float(qw),
        },
        # Plan §3: orientation_valid stays false through V1–V3.
        "orientation_valid": False,
        "tracking_valid": bool(obj.tracking_valid),
    }


def object_batch_to_dict(batch: "ObjectBatch") -> Dict[str, Any]:
    """VisionObjectArray-shaped dict + offline-only arm_ready marker."""
    key = batch.detection_batch.key
    objects = [
        object3d_to_dict(
            obj,
            frame_id=key.frame_id,
            stamp_sec=key.source_stamp_sec,
            stamp_nanosec=key.source_stamp_nanosec,
        )
        for obj in batch.objects
    ]
    return {
        "header": {
            "frame_id": key.frame_id,
            "stamp": {
                "sec": int(key.source_stamp_sec),
                "nanosec": int(key.source_stamp_nanosec),
            },
        },
        "source_session_id": key.source_session_id,
        "observation_id": int(key.observation_id),
        "calibration_id": batch.calibration_id or key.calibration_id,
        "source_kind": key.source_kind,
        "tracking_session_id": batch.tracking_session_id,
        "objects": objects,
        "arm_ready": "NO",
        "depth_paired": bool(batch.depth_paired),
        "pair_reason": batch.pair_reason,
        "mask_source": batch.mask_source,
    }


def try_build_vision_object_array_msg(batch: "ObjectBatch"):
    """Build vision_perception_interfaces/VisionObjectArray when ROS msgs exist."""
    try:
        from geometry_msgs.msg import Point, Quaternion
        from vision_msgs.msg import BoundingBox2D, Pose2D
        from vision_perception_interfaces.msg import VisionObject, VisionObjectArray
    except ImportError as exc:
        raise RuntimeError(
            "ROS message packages are unavailable in this environment"
        ) from exc

    key = batch.detection_batch.key
    message = VisionObjectArray()
    message.header.frame_id = key.frame_id
    message.header.stamp.sec = int(key.source_stamp_sec)
    message.header.stamp.nanosec = int(key.source_stamp_nanosec)
    message.source_session_id = key.source_session_id
    message.observation_id = int(key.observation_id)
    message.calibration_id = batch.calibration_id or key.calibration_id
    message.source_kind = key.source_kind
    message.tracking_session_id = batch.tracking_session_id

    objects: List[Any] = []
    for item in batch.objects:
        obj = VisionObject()
        obj.header.frame_id = key.frame_id
        obj.header.stamp.sec = int(key.source_stamp_sec)
        obj.header.stamp.nanosec = int(key.source_stamp_nanosec)
        obj.detection_index = int(item.detection_index)
        obj.object_id = item.object_id
        obj.class_name = item.class_name
        obj.confidence = float(item.confidence)
        bbox = BoundingBox2D()
        centre = Pose2D()
        centre.x = float(item.bbox_center_x)
        centre.y = float(item.bbox_center_y)
        centre.theta = float(item.bbox_theta)
        bbox.center = centre
        bbox.size_x = float(item.bbox_size_x)
        bbox.size_y = float(item.bbox_size_y)
        obj.bbox = bbox
        px, py, pz = item.position_xyz
        obj.position = Point(x=float(px), y=float(py), z=float(pz))
        obj.position_valid = bool(item.position_valid)
        obj.position_reference = item.position_reference
        obj.invalid_reason = item.invalid_reason
        obj.reference_u = float(item.reference_u)
        obj.reference_v = float(item.reference_v)
        obj.valid_depth_fraction = float(item.valid_depth_fraction)
        qx, qy, qz, qw = item.orientation_xyzw
        obj.orientation = Quaternion(
            x=float(qx), y=float(qy), z=float(qz), w=float(qw)
        )
        obj.orientation_valid = False
        obj.tracking_valid = bool(item.tracking_valid)
        objects.append(obj)
    message.objects = objects
    return message


def is_nan_number(value: float) -> bool:
    return isinstance(value, float) and math.isnan(value)
