"""W1–W4 contract regressions: source_kind, mask degrade, age helper (no ROS/hw)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from vision_perception.config import resolved_source_kind, vision_config_from_mapping
from vision_perception.depth_io import camera_calibration_from_pinhole, decode_depth_image
from vision_perception.objects_pipeline import build_object_batch
from vision_perception.source_qos import normalize_qos_reliability
from vision_perception.status_fields import is_observation_too_old
from vision_perception.types import (
    SOURCE_KIND_LIVE,
    SOURCE_KIND_SYNTHETIC,
    BoundingBox2D,
    Detection,
    DetectionBatch,
    FrameKey,
    resolve_observation_source_kind,
    topic_looks_synthetic,
)


def test_fake_topic_never_resolves_to_live_camera():
    assert topic_looks_synthetic("/dg/vision/fake/depth") is True
    assert (
        resolve_observation_source_kind(
            rgb_topic="/dg/vision/webcam/image_raw",
            input_profile="fake_dev",
        )
        == SOURCE_KIND_SYNTHETIC
    )
    assert (
        resolve_observation_source_kind(
            rgb_topic="/dg/vision/fake/image",
            input_profile="default",
        )
        == SOURCE_KIND_SYNTHETIC
    )
    assert (
        resolve_observation_source_kind(
            rgb_topic="/zed/zed_node/rgb/color/rect/image",
            input_profile="zed_subscribe",
        )
        == SOURCE_KIND_LIVE
    )


def test_v1_ros_zed_subscribe_contract_and_no_bbox_fallback(tmp_path: Path):
    cfg = vision_config_from_mapping(
        {
            "mode": "v1_ros",
            "backend": "onnxruntime_cpu",
            "model_path": str(tmp_path / "m.onnx"),
            "model_manifest_path": str(tmp_path / "m.json"),
            "detector_enabled": True,
            "camera_contract": "ZED_TOPIC_SUBSCRIBE_ONLY / NOT_START_SDK",
            "input_profile": "zed_subscribe",
            "rgb_topic": "/zed/zed_node/rgb/color/rect/image",
            "enable_objects": True,
            "allow_bbox_mask_fallback": False,
        }
    )
    assert resolved_source_kind(cfg) == SOURCE_KIND_LIVE
    assert cfg.allow_bbox_mask_fallback is False
    assert normalize_qos_reliability(cfg.image_qos_reliability) == "best_effort"


def test_post_inference_age_gate_still_uses_source_stamp():
    # Same helper is re-checked after inference in vision_node.
    assert (
        is_observation_too_old(100, 0, now_sec=100.2, max_observation_age_sec=0.5)
        is False
    )
    assert (
        is_observation_too_old(100, 0, now_sec=100.6, max_observation_age_sec=0.5)
        is True
    )


def _batch(detections, *, w=640, h=480) -> DetectionBatch:
    return DetectionBatch(
        key=FrameKey(
            source_session_id="s",
            observation_id=1,
            source_kind=SOURCE_KIND_LIVE,
            calibration_id="c",
            frame_id="optical",
            source_stamp_sec=1,
            source_stamp_nanosec=0,
        ),
        detections=tuple(detections),
        image_width=w,
        image_height=h,
    )


def test_mask_degraded_when_bbox_fallback_rejected():
    h, w = 480, 640
    depth_m = np.full((h, w), 1.0, dtype=np.float32)
    depth = decode_depth_image(
        depth_m.tobytes(),
        height=h,
        width=w,
        encoding="32FC1",
        stamp_sec=1,
        stamp_nanosec=0,
        frame_id="optical",
    )
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=500.0, fy=500.0, cx=320.0, cy=240.0, frame_id="optical"
    )
    det = Detection(0, "bottle", 0.9, BoundingBox2D(320, 240, 80, 120))
    objects = build_object_batch(
        _batch([det]),
        depth=depth,
        calibration=calib,
        pair_reason="OK",
        pair_skew_sec=0.0,
        allow_bbox_mask_fallback=False,
    )
    assert len(objects.objects) == 1
    obj = objects.objects[0]
    assert obj.position_valid is False
    assert obj.invalid_reason == "MASK_DEGRADED"
    assert all(math.isnan(v) for v in obj.position_xyz)
    assert objects.mask_degraded_count == 1


def test_rgb_depth_size_mismatch_marks_input_invalid():
    h, w = 480, 640
    depth_m = np.full((h, w), 1.0, dtype=np.float32)
    depth = decode_depth_image(
        depth_m.tobytes(),
        height=h,
        width=w,
        encoding="32FC1",
        frame_id="optical",
    )
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=500.0, fy=500.0, cx=320.0, cy=240.0, frame_id="optical"
    )
    det = Detection(0, "cup", 0.8, BoundingBox2D(100, 100, 40, 40))
    # RGB size disagrees with depth plane.
    objects = build_object_batch(
        _batch([det], w=320, h=240),
        depth=depth,
        calibration=calib,
        pair_reason="OK",
        require_rgb_depth_same_size=True,
    )
    assert objects.objects[0].invalid_reason == "INPUT_INVALID"
    assert objects.objects[0].position_valid is False
    assert objects.registration_reason == "INPUT_INVALID"


def test_zed_and_fake_profile_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "config" / "profiles" / "zed_subscribe.yaml").is_file()
    assert (root / "config" / "profiles" / "fake_dev.yaml").is_file()
    assert (root / "launch" / "vision_zed_subscribe.launch.py").is_file()
    assert (root / "requirements-arm64.txt").is_file()
    text = (root / "config" / "profiles" / "zed_subscribe.yaml").read_text(
        encoding="utf-8"
    )
    assert "allow_bbox_mask_fallback: false" in text
    assert "ZED_TOPIC_SUBSCRIBE_ONLY" in text
    assert "enable_tracking: false" in text
