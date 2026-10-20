"""Offline V3 tracking on a detection-sequence JSON (no ROS / camera / ONNX).

Runs MultiObjectTracker (deterministic greedy per-class IoU) over frames and
emits track rows + V3 scaffold metrics (idf1=BLOCKED without identity labels).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from vision_perception.evaluation import (
    TrackedIdentity,
    summarize_v3_tracking_scaffold,
)
from vision_perception.tracker import (
    DEFAULT_CONFIRM_HITS,
    DEFAULT_LOST_TIMEOUT_SEC,
    DEFAULT_MATCH_IOU,
    MultiObjectTracker,
    TrackAssignment,
)
from vision_perception.types import BoundingBox2D, Detection


def _bbox_from_dict(raw: Mapping[str, Any]) -> BoundingBox2D:
    if all(k in raw for k in ("center_x", "center_y", "size_x", "size_y")):
        return BoundingBox2D(
            center_x=float(raw["center_x"]),
            center_y=float(raw["center_y"]),
            size_x=float(raw["size_x"]),
            size_y=float(raw["size_y"]),
            theta=float(raw.get("theta", 0.0)),
        )
    if all(k in raw for k in ("x_min", "y_min", "x_max", "y_max")):
        return BoundingBox2D.from_xyxy(
            float(raw["x_min"]),
            float(raw["y_min"]),
            float(raw["x_max"]),
            float(raw["y_max"]),
        )
    raise ValueError(
        "detection bbox needs centre/size fields or x_min/y_min/x_max/y_max"
    )


def detection_from_dict(raw: Mapping[str, Any], *, fallback_index: int) -> Detection:
    index = int(raw.get("detection_index", fallback_index))
    class_name = str(raw.get("class_name", ""))
    if not class_name:
        raise ValueError("detection missing class_name")
    bbox_raw = raw.get("bbox")
    if not isinstance(bbox_raw, Mapping):
        raise ValueError("detection missing bbox object")
    return Detection(
        detection_index=index,
        class_name=class_name,
        confidence=float(raw.get("confidence", 0.0)),
        bbox=_bbox_from_dict(bbox_raw),
    )


def load_track_sequence(raw: Any) -> List[Dict[str, Any]]:
    """Normalize sequence payload to an ordered list of frame dicts."""
    if isinstance(raw, dict) and "frames" in raw:
        frames = list(raw["frames"])
    elif isinstance(raw, list):
        frames = list(raw)
    else:
        raise ValueError("sequence must be a list or {frames:[...]}")
    if not frames:
        raise ValueError("sequence has no frames")
    return frames


def run_tracker_on_frames(
    frames: Sequence[Mapping[str, Any]],
    *,
    match_iou: float = DEFAULT_MATCH_IOU,
    confirm_hits: int = DEFAULT_CONFIRM_HITS,
    lost_timeout_sec: float = DEFAULT_LOST_TIMEOUT_SEC,
    gt_id_by_frame_det: Optional[Mapping[Tuple[str, int], str]] = None,
) -> Dict[str, Any]:
    """Associate detections across frames; return tracks payload + scaffold metrics."""
    tracker = MultiObjectTracker(
        match_iou=float(match_iou),
        confirm_hits=int(confirm_hits),
        lost_timeout_sec=float(lost_timeout_sec),
    )
    rows: List[Dict[str, Any]] = []
    identities: List[TrackedIdentity] = []
    frame_order: List[str] = []

    for frame_i, frame in enumerate(frames):
        frame_id = str(frame.get("frame_id") or frame.get("source_image_id") or f"f{frame_i}")
        stamp_sec = float(frame.get("stamp_sec", float(frame_i) * 0.1))
        calibration_id = str(frame.get("calibration_id", ""))
        det_raws = list(frame.get("detections", []))
        detections = [
            detection_from_dict(item, fallback_index=idx)
            for idx, item in enumerate(det_raws)
        ]
        assignments: Tuple[TrackAssignment, ...] = tracker.update(
            detections,
            stamp_sec=stamp_sec,
            calibration_id=calibration_id,
        )
        frame_order.append(frame_id)
        session_id = tracker.tracking_session_id
        by_index = {int(a.detection_index): a for a in assignments}
        for det in detections:
            assignment = by_index.get(int(det.detection_index))
            object_id = assignment.object_id if assignment else ""
            tracking_valid = bool(assignment.tracking_valid) if assignment else False
            track_state = assignment.track_state if assignment else ""
            track_id = int(assignment.track_id) if assignment else 0
            rows.append(
                {
                    "frame_id": frame_id,
                    "stamp_sec": stamp_sec,
                    "detection_index": int(det.detection_index),
                    "class_name": det.class_name,
                    "confidence": float(det.confidence),
                    "bbox_center_x": float(det.bbox.center_x),
                    "bbox_center_y": float(det.bbox.center_y),
                    "bbox_size_x": float(det.bbox.size_x),
                    "bbox_size_y": float(det.bbox.size_y),
                    "object_id": object_id,
                    "tracking_valid": tracking_valid,
                    "track_id": track_id,
                    "track_state": track_state,
                    "tracking_session_id": session_id,
                }
            )
            identities.append(
                TrackedIdentity(
                    frame_id=frame_id,
                    detection_index=int(det.detection_index),
                    object_id=object_id,
                    class_name=det.class_name,
                    tracking_valid=tracking_valid,
                )
            )

    has_gt = bool(gt_id_by_frame_det)
    metrics = summarize_v3_tracking_scaffold(
        identities,
        frame_order=frame_order,
        gt_id_by_frame_det=gt_id_by_frame_det,
        has_identity_annotations=has_gt,
    )
    return {
        "stage": "V3_TRACKING_OFFLINE",
        "camera_contract": "NOT_RUN",
        "arm_ready": "NO",
        "matcher": "deterministic_greedy_per_class_iou",
        "tracker_match_iou": float(match_iou),
        "tracker_confirm_hits": int(confirm_hits),
        "tracker_lost_timeout_sec": float(lost_timeout_sec),
        "tracking_session_id": tracker.tracking_session_id,
        "frames": len(frames),
        "rows": rows,
        "metrics": metrics,
    }


def tracks_payload_to_identities(payload: Mapping[str, Any]) -> List[TrackedIdentity]:
    return [
        TrackedIdentity(
            frame_id=str(row["frame_id"]),
            detection_index=int(row["detection_index"]),
            object_id=str(row.get("object_id", "")),
            class_name=str(row.get("class_name", "")),
            tracking_valid=bool(row.get("tracking_valid", False)),
        )
        for row in payload.get("rows", [])
    ]
