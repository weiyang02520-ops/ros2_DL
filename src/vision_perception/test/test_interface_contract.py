"""Plan §3 message-shape contract (no ROS codegen / no depth / no tracking)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vision_perception.config import vision_config_from_mapping
from vision_perception.message_mapping import (
    VISION_OBJECT_ARRAY_DICT_FIELDS,
    VISION_OBJECT_DICT_FIELDS,
    is_nan_number,
    placeholder_object_array_dict_from_batch,
    placeholder_object_dict_from_detection,
)
from vision_perception.types import (
    INVALID_REASONS,
    BoundingBox2D,
    Detection,
    DetectionBatch,
    FrameKey,
)


IFACE = Path(__file__).resolve().parents[2] / "vision_perception_interfaces"
MSG = IFACE / "msg"


def _field_lines(msg_text: str) -> list[str]:
    lines = []
    for raw in msg_text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def test_vision_detection_msgs_match_plan_section_3():
    d2d = _field_lines((MSG / "VisionDetection2D.msg").read_text(encoding="utf-8"))
    arr = _field_lines((MSG / "VisionDetectionArray.msg").read_text(encoding="utf-8"))
    assert d2d == [
        "uint32 detection_index",
        "string class_name",
        "float32 confidence",
        "vision_msgs/BoundingBox2D bbox",
    ]
    assert arr == [
        "std_msgs/Header header",
        "string source_session_id",
        "uint64 observation_id",
        "string calibration_id",
        "string source_kind",
        "VisionDetection2D[] detections",
    ]


def test_vision_object_msgs_match_plan_section_3():
    obj = _field_lines((MSG / "VisionObject.msg").read_text(encoding="utf-8"))
    arr = _field_lines((MSG / "VisionObjectArray.msg").read_text(encoding="utf-8"))
    assert obj == [
        "std_msgs/Header header",
        "uint32 detection_index",
        "string object_id",
        "string class_name",
        "float32 confidence",
        "vision_msgs/BoundingBox2D bbox",
        "geometry_msgs/Point position",
        "bool position_valid",
        "string position_reference",
        "string invalid_reason",
        "float64 reference_u",
        "float64 reference_v",
        "float32 valid_depth_fraction",
        "geometry_msgs/Quaternion orientation",
        "bool orientation_valid",
        "bool tracking_valid",
    ]
    assert arr == [
        "std_msgs/Header header",
        "string source_session_id",
        "uint64 observation_id",
        "string calibration_id",
        "string source_kind",
        "string tracking_session_id",
        "VisionObject[] objects",
    ]


def test_interface_contract_doc_exists_and_documents_v2_gate():
    text = (IFACE / "INTERFACE_CONTRACT.md").read_text(encoding="utf-8")
    assert "/dg/vision/objects" in text
    assert "VisionObjectArray" in text
    assert "orientation_valid" in text
    assert "ARM_READY" in text
    assert "enable_objects" in text
    assert "enable_tracking:=false" in text or "enable_tracking" in text
    assert "vision_perception/evidence/templates" in text
    assert (IFACE / "README.md").is_file()


def test_placeholder_object_shape_and_orientation_always_false():
    det = Detection(0, "bottle", 0.9, BoundingBox2D(10, 20, 4, 6))
    obj = placeholder_object_dict_from_detection(det)
    for key in VISION_OBJECT_DICT_FIELDS:
        assert key in obj
    assert obj["orientation_valid"] is False
    assert obj["tracking_valid"] is False
    assert obj["position_valid"] is False
    assert obj["object_id"] == ""
    assert is_nan_number(obj["orientation"]["w"])
    assert is_nan_number(obj["position"]["x"])
    assert obj["invalid_reason"] in INVALID_REASONS


def test_placeholder_object_array_observation_keys_and_arm_ready_no():
    batch = DetectionBatch(
        key=FrameKey(
            source_session_id="sess-x",
            observation_id=3,
            source_kind="LIVE_CAMERA",
            calibration_id="calib-hash",
            frame_id="cam_optical",
            source_stamp_sec=1,
            source_stamp_nanosec=2,
        ),
        detections=(Detection(0, "cup", 0.8, BoundingBox2D(1, 2, 3, 4)),),
    )
    payload = placeholder_object_array_dict_from_batch(batch)
    for key in VISION_OBJECT_ARRAY_DICT_FIELDS:
        assert key in payload
    assert payload["source_session_id"] == "sess-x"
    assert payload["observation_id"] == 3
    assert payload["tracking_session_id"] == ""
    assert payload["arm_ready"] == "NO"
    assert payload["objects"][0]["orientation_valid"] is False
    assert payload["objects"][0]["detection_index"] == 0


def test_enable_objects_and_tracking_default_false_and_reject_outside_v1_ros():
    cfg = vision_config_from_mapping(None)
    assert cfg.enable_objects is False
    assert cfg.enable_tracking is False
    assert cfg.tracking_enabled is False
    assert cfg.tracker_match_iou == 0.30
    assert cfg.tracker_confirm_hits == 3
    assert cfg.tracker_lost_timeout_sec == 0.70
    # Without mode=v1_ros, enable_objects/tracking=true are rejected (skeleton default).
    with pytest.raises(ValueError, match="enable_objects"):
        vision_config_from_mapping({"enable_objects": True})
    with pytest.raises(ValueError, match="enable_tracking"):
        vision_config_from_mapping({"enable_tracking": True})
    with pytest.raises(ValueError, match="enable_tracking"):
        vision_config_from_mapping({"tracking_enabled": True})


def test_enable_tracking_alias_disagrees_raises():
    with pytest.raises(ValueError, match="disagree"):
        vision_config_from_mapping(
            {"enable_tracking": False, "tracking_enabled": True}
        )


def test_v1_ros_allows_enable_objects_and_tracking_default_still_false(tmp_path: Path):
    base = {
        "mode": "v1_ros",
        "backend": "onnxruntime_cpu",
        "model_path": str(tmp_path / "m.onnx"),
        "model_manifest_path": str(tmp_path / "m.json"),
        "detector_enabled": True,
        "camera_contract": "DEV_WEBCAM_ONLY / NOT_ZED",
    }
    cfg = vision_config_from_mapping(base)
    assert cfg.enable_objects is False
    assert cfg.enable_tracking is False
    cfg2 = vision_config_from_mapping({**base, "enable_objects": True})
    assert cfg2.enable_objects is True
    assert cfg2.objects_topic == "/dg/vision/objects"
    cfg3 = vision_config_from_mapping({**base, "enable_tracking": True})
    assert cfg3.enable_tracking is True
    assert cfg3.tracking_enabled is True
    cfg4 = vision_config_from_mapping(
        {**base, "enable_objects": True, "enable_tracking": True}
    )
    assert cfg4.enable_objects is True and cfg4.enable_tracking is True


def test_v1_evidence_templates_exist():
    """Templates live inside the package so isolated two-package sync still passes."""
    root = Path(__file__).resolve().parents[1] / "evidence" / "templates"
    assert root.is_dir(), (
        "expected src/vision_perception/evidence/templates "
        "(not the monorepo evidence/vision/ tree)"
    )
    for stage in ("V1_OFFLINE", "V1_ROS"):
        base = root / stage
        assert (base / "metadata.json.template").is_file()
        assert (base / "parameters.yaml.template").is_file()
        assert (base / "acceptance_protocol.yaml.template").is_file()
        meta = (base / "metadata.json.template").read_text(encoding="utf-8")
        assert '"arm_ready": "NO"' in meta
        assert '"result": "NOT_RUN"' in meta
        params = (base / "parameters.yaml.template").read_text(encoding="utf-8")
        assert "enable_objects: false" in params
        assert "enable_tracking: false" in params


def test_v2_position_evidence_templates_exist():
    root = Path(__file__).resolve().parents[1] / "evidence" / "templates" / "V2_POSITION"
    assert root.is_dir()
    meta = (root / "metadata.json.template").read_text(encoding="utf-8")
    params = (root / "parameters.yaml.template").read_text(encoding="utf-8")
    protocol = (root / "acceptance_protocol.yaml.template").read_text(encoding="utf-8")
    assert '"result": "NOT_RUN"' in meta
    assert '"v2_accuracy": "BLOCKED"' in meta
    assert '"arm_ready": "NO"' in meta
    assert "enable_objects: true" in params
    assert "enable_tracking: false" in params
    assert "sync_wait_sec" in params
    assert "BLOCKED" in protocol
    assert "independent_surface" in protocol


def test_v3_tracking_evidence_templates_exist():
    root = Path(__file__).resolve().parents[1] / "evidence" / "templates" / "V3_TRACKING"
    assert root.is_dir()
    meta = (root / "metadata.json.template").read_text(encoding="utf-8")
    params = (root / "parameters.yaml.template").read_text(encoding="utf-8")
    protocol = (root / "acceptance_protocol.yaml.template").read_text(encoding="utf-8")
    tracks = (root / "tracks.csv.template").read_text(encoding="utf-8")
    timeline = (root / "session_reset_timeline.yaml.template").read_text(encoding="utf-8")
    assert '"result": "NOT_RUN"' in meta
    assert '"idf1": "BLOCKED"' in meta
    assert '"arm_ready": "NO"' in meta
    assert "enable_tracking: true" in params
    assert "tracker_match_iou: 0.30" in params
    assert "tracker_confirm_hits: 3" in params
    assert "NOT_RUN" in protocol
    assert "identity_annotations_required" in protocol
    assert "object_id" in tracks and "tracking_session_id" in tracks
    assert "session_start" in timeline or "events:" in timeline


def test_v0_shell_evidence_templates_exist():
    root = Path(__file__).resolve().parents[1] / "evidence" / "templates" / "V0_SHELL"
    assert root.is_dir()
    meta = (root / "metadata.json.template").read_text(encoding="utf-8")
    params = (root / "parameters.yaml.template").read_text(encoding="utf-8")
    assert '"result": "NOT_RUN"' in meta
    assert '"arm_ready": "NO"' in meta
    assert "NONE_NOT_APPLICABLE" in meta
    assert "mode: skeleton" in params
    assert "enable_tracking: false" in params
