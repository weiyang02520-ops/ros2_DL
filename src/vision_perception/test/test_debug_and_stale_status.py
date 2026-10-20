"""Debug overlay + STALE status + V1 no-/objects contract (no ROS / no camera)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from vision_perception.debug_overlay import (
    DebugPublishGate,
    detections_have_only_allowed_classes,
    draw_detections_rgb,
)
from vision_perception.frame_worker import LatestFrameWorker
from vision_perception.message_mapping import detection_batch_to_dict
from vision_perception.pipeline import process_array_with_synthetic_output0
from vision_perception.status_fields import (
    LEVEL_OK,
    LEVEL_STALE,
    LEVEL_WARN,
    compose_v1_ros_diagnostic,
    is_input_stale,
)
from vision_perception.types import BoundingBox2D, Detection


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _empty_output0(num_preds: int = 8400) -> np.ndarray:
    return np.zeros((1, 116, num_preds), dtype=np.float32)


def test_draw_detections_marks_pixels_near_box():
    image = np.zeros((40, 60, 3), dtype=np.uint8)
    det = Detection(0, "bottle", 0.9, BoundingBox2D(30, 20, 20, 16))
    out = draw_detections_rgb(image, [det])
    assert out.shape == image.shape
    assert out is not image
    # Top edge of the box should be non-zero (green-ish bottle colour).
    assert int(out[12, 30].sum()) > 0
    assert detections_have_only_allowed_classes([det])


def test_debug_publish_gate_caps_at_two_hz():
    gate = DebugPublishGate(max_hz=2.0)
    assert gate.allow(now=0.0) is True
    assert gate.allow(now=0.1) is False
    assert gate.allow(now=0.5) is True
    assert gate.allow(now=0.6) is False


def test_stale_status_when_input_age_exceeds_threshold():
    assert is_input_stale(1.01, 1.0) is True
    assert is_input_stale(0.5, 1.0) is False
    level, message, fields = compose_v1_ros_diagnostic(
        frames_received=5,
        frames_processed=5,
        frames_dropped=0,
        last_observation_id=5,
        last_detection_count=0,
        source_session_id="sess-abc",
        backend="onnxruntime_cpu",
        last_input_age_sec=1.5,
        input_stale_sec=1.0,
    )
    assert level == LEVEL_STALE == b"\x03"
    assert message == "STALE"
    assert fields["source_session_id"] == "sess-abc"
    assert fields["backend"] == "onnxruntime_cpu"
    assert fields["arm_ready"] == "NO"
    assert fields["object_output_active"] == "false"
    assert fields["tracking_active"] == "false"
    assert fields["tracking_session_id"] == ""
    assert fields["enable_tracking"] == "false"


def test_tracking_active_status_fields_when_enabled():
    level, message, fields = compose_v1_ros_diagnostic(
        frames_received=2,
        frames_processed=2,
        frames_dropped=0,
        last_observation_id=2,
        last_detection_count=1,
        source_session_id="sess-trk",
        backend="onnxruntime_cpu",
        last_input_age_sec=0.1,
        input_stale_sec=1.0,
        enable_tracking=True,
        tracking_active=True,
        tracking_session_id="trk-session-1",
    )
    assert level == LEVEL_OK
    assert message == "V3_TRACKING_DEV"
    assert fields["tracking_active"] == "true"
    assert fields["enable_tracking"] == "true"
    assert fields["tracking_session_id"] == "trk-session-1"
    assert fields["arm_ready"] == "NO"


def test_worker_error_outranks_stale():
    level, message, fields = compose_v1_ros_diagnostic(
        frames_received=1,
        frames_processed=0,
        frames_dropped=0,
        last_observation_id=0,
        last_detection_count=0,
        last_worker_error="boom",
        last_input_age_sec=9.0,
        input_stale_sec=1.0,
    )
    assert level == LEVEL_WARN
    assert message == "V1_ROS_DEGRADED"
    assert fields["last_worker_error"] == "boom"


def test_fresh_input_keeps_ok_and_exposes_session_backend():
    level, message, fields = compose_v1_ros_diagnostic(
        frames_received=2,
        frames_processed=2,
        frames_dropped=0,
        last_observation_id=2,
        last_detection_count=1,
        source_session_id="s1",
        backend="onnxruntime_cpu",
        last_input_age_sec=0.2,
        input_stale_sec=1.0,
        publish_debug_image=False,
    )
    assert level == LEVEL_OK
    assert message == "V1_ROS_DEV_WEBCAM"
    assert fields["source_session_id"] == "s1"
    assert fields["backend"] == "onnxruntime_cpu"
    assert fields["publish_debug_image"] == "false"


def test_clear_pending_drops_waiting_frame():
    worker = LatestFrameWorker(lambda _item: None, min_interval_sec=0.0)
    worker.submit("pending")
    assert worker.clear_pending() == 1
    assert worker.clear_pending() == 0
    assert worker.dropped >= 1


def test_golden_format_sample_schema():
    raw = json.loads((EXAMPLES / "golden_format_batch.json").read_text(encoding="utf-8"))
    assert raw["stage"] == "V1_OFFLINE"
    assert raw["camera_contract"] == "NOT_RUN"
    assert raw["arm_ready"] == "NO"
    assert len(raw["batches"]) >= 2
    empty = raw["batches"][1]
    assert empty["detections"] == []
    nonempty = raw["batches"][0]
    assert nonempty["detections"][0]["class_name"] in {"bottle", "cup"}
    for key in (
        "source_session_id",
        "observation_id",
        "source_kind",
        "calibration_id",
        "detections",
    ):
        assert key in nonempty


def test_synthetic_golden_boxes_match_expected_geometry():
    """Deterministic postprocess golden (no ONNX weights)."""
    image = np.zeros((80, 120, 3), dtype=np.uint8)
    output0 = _empty_output0(1)
    output0[0, 0:4, 0] = np.array([320, 320, 80, 80], dtype=np.float32)
    output0[0, 4 + 39, 0] = 0.88
    batch = process_array_with_synthetic_output0(image, output0)
    payload = detection_batch_to_dict(batch)
    assert payload["source_kind"] == "OFFLINE_FILE"
    assert len(payload["detections"]) == 1
    det = payload["detections"][0]
    assert det["class_name"] == "bottle"
    assert det["detection_index"] == 0
    assert abs(det["confidence"] - 0.88) < 1e-5
    # Letterbox of 120x80 into 640 maps centre near image centre.
    assert 40.0 <= det["bbox"]["center_x"] <= 80.0
    assert 20.0 <= det["bbox"]["center_y"] <= 60.0


def test_vision_node_objects_publisher_gated_by_enable_objects():
    text = (ROOT / "vision_perception" / "vision_node.py").read_text(encoding="utf-8")
    assert "create_publisher" in text
    assert "objects_topic" in text
    assert "enable_objects" in text
    # Publisher created only inside the enable_objects branch.
    assert "if self._enable_objects:" in text
    assert "VisionObjectArray" in text
    assert "ARM_READY=NO" in text
    assert "orientation_valid=false" in text or "orientation_valid" in text
