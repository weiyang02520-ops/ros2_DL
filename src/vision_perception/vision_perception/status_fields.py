"""Diagnostic field helpers without rclpy (unit-testable).

Empty detections after a successful process are healthy for fake-image smoke:
status stays OK / V1_ROS_DEV_WEBCAM. Worker errors degrade; empty boxes do not.
No new input for longer than input_stale_sec → STALE (clears pending frames).

Humble diagnostic_msgs/DiagnosticStatus.level is a ``byte`` field: assignment
must be length-1 bytes (``b'\\x00'``), not a Python ``int``.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple, Union

# diagnostic_msgs/DiagnosticStatus level values as Humble expects (len==1 bytes)
LEVEL_OK = b"\x00"
LEVEL_WARN = b"\x01"
LEVEL_ERROR = b"\x02"
LEVEL_STALE = b"\x03"


def as_diagnostic_level_byte(level: Union[int, bytes, bytearray]) -> bytes:
    """Coerce a level to a length-1 bytes object for DiagnosticStatus.level."""
    if isinstance(level, (bytes, bytearray)):
        value = bytes(level)
        if len(value) != 1:
            raise ValueError(
                f"DiagnosticStatus.level must be length-1 bytes, got {value!r}"
            )
        return value
    if isinstance(level, int):
        if level < 0 or level > 255:
            raise ValueError(f"DiagnosticStatus.level int out of range: {level}")
        return bytes((level,))
    raise TypeError(
        f"DiagnosticStatus.level must be int or length-1 bytes, got {type(level)!r}"
    )


def is_input_stale(
    last_input_age_sec: Optional[float], input_stale_sec: float = 1.0
) -> bool:
    """True when age is known and exceeds the stale threshold."""
    if last_input_age_sec is None:
        return False
    return float(last_input_age_sec) > float(input_stale_sec)


def source_stamp_age_sec(
    stamp_sec: int,
    stamp_nanosec: int,
    *,
    now_sec: float,
) -> float:
    """Age of a message source stamp relative to ``now_sec`` (seconds)."""
    stamp = float(stamp_sec) + float(stamp_nanosec) * 1e-9
    return float(now_sec) - stamp


def is_observation_too_old(
    stamp_sec: int,
    stamp_nanosec: int,
    *,
    now_sec: float,
    max_observation_age_sec: float = 0.500,
) -> bool:
    """Plan §9: drop outputs whose source stamp age exceeds the gate."""
    return source_stamp_age_sec(
        stamp_sec, stamp_nanosec, now_sec=now_sec
    ) > float(max_observation_age_sec)


def compose_v1_ros_diagnostic(
    *,
    frames_received: int,
    frames_processed: int,
    frames_dropped: int,
    last_observation_id: int,
    last_detection_count: int,
    last_worker_error: str = "",
    camera_contract: str = "DEV_WEBCAM_ONLY / NOT_ZED",
    rgb_topic: str = "/dg/vision/webcam/image_raw",
    depth_topic: str = "",
    camera_info_topic: str = "",
    source_session_id: str = "",
    backend: str = "onnxruntime_cpu",
    source_kind: str = "LIVE_CAMERA",
    last_input_age_sec: Optional[float] = None,
    input_stale_sec: float = 1.0,
    publish_debug_image: bool = False,
    last_inference_ms: float = -1.0,
    calibration_id: str = "",
    enable_objects: bool = False,
    object_output_active: bool = False,
    enable_tracking: bool = False,
    tracking_active: bool = False,
    tracking_session_id: str = "",
    last_objects_count: int = 0,
    last_position_valid_count: int = 0,
    last_pair_reason: str = "",
    last_pair_skew_sec: Optional[float] = None,
    depth_frames_received: int = 0,
    camera_info_received: bool = False,
    observations_dropped_age: int = 0,
    max_observation_age_sec: float = 0.500,
) -> Tuple[bytes, str, Dict[str, str]]:
    """Return (level_byte, message, key/value fields) for v1_ros(+optional V2/V3) status."""
    error = (last_worker_error or "").strip()
    stale = is_input_stale(last_input_age_sec, input_stale_sec)

    if error:
        level = LEVEL_WARN
        message = "V1_ROS_DEGRADED"
    elif stale:
        level = LEVEL_STALE
        message = "STALE"
    elif enable_objects and not camera_info_received:
        # V2 enabled but no CameraInfo yet — degrade, do not invent 3D.
        level = LEVEL_WARN
        message = "V2_OBJECTS_NO_CALIBRATION"
    else:
        level = LEVEL_OK
        if enable_tracking:
            message = "V3_TRACKING_DEV"
        elif enable_objects:
            message = "V2_OBJECTS_DEV"
        else:
            message = "V1_ROS_DEV_WEBCAM"

    age_text = (
        f"{float(last_input_age_sec):.3f}" if last_input_age_sec is not None else ""
    )
    skew_text = (
        f"{float(last_pair_skew_sec):.6f}" if last_pair_skew_sec is not None else ""
    )
    tracking_on = bool(enable_tracking or tracking_active)
    fields = {
        "mode": "v1_ros",
        "implementation_status": message,
        "camera_subscriptions_active": "true",
        "camera_contract": camera_contract,
        "backend": backend,
        "source_kind": source_kind,
        "source_session_id": source_session_id,
        "calibration_id": calibration_id,
        "inference_active": "true",
        "tracking_active": "true" if tracking_on else "false",
        "tracking_session_id": str(tracking_session_id or "") if tracking_on else "",
        "object_output_active": "true" if object_output_active else "false",
        "enable_objects": "true" if enable_objects else "false",
        "enable_tracking": "true" if enable_tracking else "false",
        "control_output_active": "false",
        "arm_ready": "NO",
        "publish_debug_image": "true" if publish_debug_image else "false",
        "v1_detections_interface": "VisionDetectionArray",
        "v2_objects_interface": "VisionObjectArray",
        "frames_received": str(int(frames_received)),
        "frames_processed": str(int(frames_processed)),
        "frames_dropped": str(int(frames_dropped)),
        "depth_frames_received": str(int(depth_frames_received)),
        "camera_info_received": "true" if camera_info_received else "false",
        "last_observation_id": str(int(last_observation_id)),
        "last_detection_count": str(int(last_detection_count)),
        "last_objects_count": str(int(last_objects_count)),
        "last_position_valid_count": str(int(last_position_valid_count)),
        "last_pair_reason": last_pair_reason,
        "last_pair_skew_sec": skew_text,
        "last_input_age_sec": age_text,
        "input_stale_sec": f"{float(input_stale_sec):.3f}",
        "max_observation_age_sec": f"{float(max_observation_age_sec):.3f}",
        "observations_dropped_age": str(int(observations_dropped_age)),
        "last_inference_ms": (
            f"{float(last_inference_ms):.2f}" if last_inference_ms >= 0 else ""
        ),
        "empty_detections_healthy": "true",
        "last_worker_error": error,
        "rgb_topic": rgb_topic,
        "depth_topic": depth_topic,
        "camera_info_topic": camera_info_topic,
    }
    return as_diagnostic_level_byte(level), message, fields


def empty_detections_are_healthy(
    last_detection_count: int, last_worker_error: Optional[str] = None
) -> bool:
    """Fake solid-color frames often yield []; that must not mark the node unhealthy."""
    if (last_worker_error or "").strip():
        return False
    return int(last_detection_count) >= 0
