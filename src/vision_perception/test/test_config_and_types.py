"""Config validation and immutable type behaviour (no ROS / no hardware)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vision_perception.config import (
    load_model_manifest,
    normalize_ros_node_mode,
    require_ros_skeleton_mode,
    validate_manifest_shapes,
    validate_vision_config,
    vision_config_from_mapping,
)
from vision_perception.types import (
    BoundingBox2D,
    Detection,
    sort_detections_deterministic,
)


def test_skeleton_defaults_validate():
    cfg = vision_config_from_mapping(None)
    assert cfg.mode == "skeleton"
    assert cfg.backend == "unconfigured"
    assert cfg.max_detections == 20
    assert cfg.publish_debug_image is False
    assert cfg.enable_objects is False
    assert cfg.enable_tracking is False
    assert cfg.tracker_match_iou == 0.30
    assert cfg.tracker_confirm_hits == 3
    assert cfg.tracker_lost_timeout_sec == 0.70
    assert cfg.tracking_enabled is False
    assert cfg.debug_image_topic == "/dg/vision/debug_image"
    assert cfg.debug_image_max_hz == 2.0
    assert cfg.input_stale_sec == 1.0


def test_skeleton_rejects_enabled_detector():
    with pytest.raises(ValueError, match="skeleton"):
        vision_config_from_mapping({"detector_enabled": True})


def test_offline_requires_model_paths():
    with pytest.raises(ValueError, match="model_path"):
        vision_config_from_mapping(
            {"mode": "offline", "backend": "onnxruntime_cpu", "model_manifest_path": "x"}
        )


def test_offline_accepts_valid_mapping(tmp_path: Path):
    cfg = vision_config_from_mapping(
        {
            "mode": "offline",
            "backend": "onnxruntime_cpu",
            "model_path": str(tmp_path / "model.onnx"),
            "model_manifest_path": str(tmp_path / "manifest.json"),
        }
    )
    assert cfg.confidence_threshold == 0.35
    assert cfg.sync_tolerance_sec == 0.010


def test_status_topic_must_stay_under_dg_vision():
    with pytest.raises(ValueError, match="status_topic"):
        vision_config_from_mapping({"status_topic": "/cmd_vel"})


def test_sort_detections_is_deterministic():
    items = [
        Detection(0, "cup", 0.9, BoundingBox2D(10, 10, 4, 4)),
        Detection(0, "bottle", 0.9, BoundingBox2D(5, 5, 4, 4)),
        Detection(0, "bottle", 0.95, BoundingBox2D(1, 1, 2, 2)),
    ]
    ordered = sort_detections_deterministic(items)
    assert [d.class_name for d in ordered] == ["bottle", "bottle", "cup"]
    assert [d.detection_index for d in ordered] == [0, 1, 2]
    assert ordered[0].confidence == 0.95


def test_load_model_manifest_requires_coco_ids(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "source": "test",
                "onnx_sha256": "abc",
                "license": "test",
                "input_name": "images",
                "input_shape": [1, 3, 640, 640],
                "output0_shape": [1, 116, 8400],
                "output1_shape": [1, 32, 160, 160],
                "class_map": {"bottle": 1, "cup": 2},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="COCO"):
        load_model_manifest(str(path))


def test_load_model_manifest_ok(tmp_path: Path):
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "source": "test",
                "onnx_sha256": "abc",
                "license": "test",
                "input_name": "images",
                "input_shape": [1, 3, 640, 640],
                "output0_shape": [1, 116, 8400],
                "output1_shape": [1, 32, 160, 160],
                "class_map": {"bottle": 39, "cup": 41},
            }
        ),
        encoding="utf-8",
    )
    manifest = load_model_manifest(str(path))
    validate_manifest_shapes(manifest)
    assert manifest.class_id_to_name()[39] == "bottle"


def test_validate_rejects_mode_v1_for_shared_config():
    from vision_perception.config import VisionConfig

    # Shared helper allows only skeleton/offline. mode=v1 must not silently activate.
    with pytest.raises(ValueError, match="Unsupported mode"):
        validate_vision_config(VisionConfig(mode="v1"))


def test_ros_node_helper_rejects_v1_even_if_offline_config_exists():
    # ROS node path rejects legacy v1 and offline (CLI-only).
    with pytest.raises(ValueError, match="Unsupported ROS mode"):
        normalize_ros_node_mode("v1")
    with pytest.raises(ValueError, match="Unsupported ROS mode"):
        normalize_ros_node_mode("offline")
    with pytest.raises(ValueError):
        require_ros_skeleton_mode("v1_ros")


def test_v1_ros_config_requires_model_and_dev_webcam_contract(tmp_path: Path):
    cfg = vision_config_from_mapping(
        {
            "mode": "v1_ros",
            "backend": "onnxruntime_cpu",
            "model_path": str(tmp_path / "m.onnx"),
            "model_manifest_path": str(tmp_path / "m.json"),
            "detector_enabled": True,
            "camera_contract": "DEV_WEBCAM_ONLY / NOT_ZED",
            "rgb_topic": "/dg/vision/webcam/image_raw",
        }
    )
    assert cfg.mode == "v1_ros"
    with pytest.raises(ValueError, match="camera_contract"):
        vision_config_from_mapping(
            {
                "mode": "v1_ros",
                "backend": "onnxruntime_cpu",
                "model_path": str(tmp_path / "m.onnx"),
                "model_manifest_path": str(tmp_path / "m.json"),
                "detector_enabled": True,
                "camera_contract": "ZED_VERIFIED",
                "rgb_topic": "/dg/vision/webcam/image_raw",
            }
        )
