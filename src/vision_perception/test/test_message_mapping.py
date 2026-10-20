"""DetectionBatch → dict mapping and interface .msg contract checks."""

from __future__ import annotations

from pathlib import Path

from vision_perception.message_mapping import (
    detection_batch_to_dict,
    placeholder_object_dict_from_detection,
)
from vision_perception.types import (
    BoundingBox2D,
    Detection,
    DetectionBatch,
    FrameKey,
)


ROOT = Path(__file__).resolve().parents[2]
IFACE_MSG = ROOT / "vision_perception_interfaces" / "msg"


def test_detection_batch_dict_carries_observation_keys():
    batch = DetectionBatch(
        key=FrameKey(
            source_session_id="sess-1",
            observation_id=7,
            source_kind="OFFLINE_FILE",
            calibration_id="",
            source_image_id="img_001.npy",
        ),
        detections=(
            Detection(
                detection_index=0,
                class_name="cup",
                confidence=0.77,
                bbox=BoundingBox2D(12.0, 20.0, 8.0, 10.0),
            ),
        ),
        image_width=100,
        image_height=80,
    )
    payload = detection_batch_to_dict(batch)
    assert payload["source_session_id"] == "sess-1"
    assert payload["observation_id"] == 7
    assert payload["detections"][0]["class_name"] == "cup"
    assert payload["detections"][0]["bbox"]["size_x"] == 8.0


def test_placeholder_object_uses_nan_and_invalid_flags():
    det = Detection(0, "bottle", 0.5, BoundingBox2D(1, 2, 3, 4))
    obj = placeholder_object_dict_from_detection(det)
    assert obj["position_valid"] is False
    assert obj["orientation_valid"] is False
    assert obj["tracking_valid"] is False
    assert obj["position_reference"] == "visible_surface_sample"
    assert obj["invalid_reason"] == "DEPTH_UNPAIRED"
    assert obj["position"]["x"] != obj["position"]["x"]  # NaN


def test_v1_msg_files_match_plan_fields():
    detection2d = (IFACE_MSG / "VisionDetection2D.msg").read_text(encoding="utf-8")
    detection_array = (IFACE_MSG / "VisionDetectionArray.msg").read_text(encoding="utf-8")
    vision_object = (IFACE_MSG / "VisionObject.msg").read_text(encoding="utf-8")
    object_array = (IFACE_MSG / "VisionObjectArray.msg").read_text(encoding="utf-8")

    for token in (
        "uint32 detection_index",
        "string class_name",
        "float32 confidence",
        "vision_msgs/BoundingBox2D bbox",
    ):
        assert token in detection2d

    for token in (
        "std_msgs/Header header",
        "string source_session_id",
        "uint64 observation_id",
        "string calibration_id",
        "string source_kind",
        "VisionDetection2D[] detections",
    ):
        assert token in detection_array

    for token in (
        "uint32 detection_index",
        "string invalid_reason",
        "float64 reference_u",
        "float64 reference_v",
        "float32 valid_depth_fraction",
        "vision_msgs/BoundingBox2D bbox",
    ):
        assert token in vision_object

    for token in (
        "string source_session_id",
        "uint64 observation_id",
        "string calibration_id",
        "string source_kind",
        "string tracking_session_id",
        "VisionObject[] objects",
    ):
        assert token in object_array
