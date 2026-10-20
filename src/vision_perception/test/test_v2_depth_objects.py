"""V2 offline unit tests: depth decode, pairing, surface sample, object batch."""

from __future__ import annotations

import math

import numpy as np
import pytest

from vision_perception.config import vision_config_from_mapping
from vision_perception.depth_io import (
    camera_calibration_from_pinhole,
    decode_depth_image,
    encode_depth_32fc1_fields,
    project_optical_xyz,
)
from vision_perception.frame_pairing import DepthFrameBuffer, RgbDepthSyncGate
from vision_perception.message_mapping import (
    VISION_OBJECT_ARRAY_DICT_FIELDS,
    VISION_OBJECT_DICT_FIELDS,
    is_nan_number,
    object_batch_to_dict,
)
from vision_perception.objects_pipeline import build_object_batch
from vision_perception.surface_sample import bbox_fill_mask, sample_visible_surface
from vision_perception.types import BoundingBox2D, Detection, DetectionBatch, FrameKey


def _batch_with_box(
    *,
    cx: float = 320.0,
    cy: float = 240.0,
    sx: float = 80.0,
    sy: float = 100.0,
    w: int = 640,
    h: int = 480,
) -> DetectionBatch:
    return DetectionBatch(
        key=FrameKey(
            source_session_id="sess-v2",
            observation_id=1,
            source_kind="LIVE_CAMERA",
            calibration_id="",
            frame_id="fake_optical",
            source_stamp_sec=10,
            source_stamp_nanosec=0,
        ),
        detections=(
            Detection(0, "bottle", 0.91, BoundingBox2D(cx, cy, sx, sy)),
        ),
        image_width=w,
        image_height=h,
    )


def test_decode_depth_32fc1_roundtrip():
    depth = np.full((4, 5), 1.25, dtype=np.float32)
    depth[0, 0] = np.nan
    fields = encode_depth_32fc1_fields(depth, frame_id="f", stamp_sec=1, stamp_nanosec=2)
    frame = decode_depth_image(
        fields["data"],
        height=fields["height"],
        width=fields["width"],
        encoding=fields["encoding"],
        step=fields["step"],
        stamp_sec=1,
        stamp_nanosec=2,
        frame_id="f",
    )
    assert frame.depth_m.shape == (4, 5)
    assert math.isnan(frame.depth_m[0, 0])
    assert abs(frame.depth_m[1, 1] - 1.25) < 1e-6


def test_decode_depth_16uc1_millimetres():
    raw = np.zeros((2, 3), dtype=np.uint16)
    raw[0, 0] = 1000  # 1.0 m
    raw[0, 1] = 0  # invalid
    frame = decode_depth_image(
        raw.tobytes(),
        height=2,
        width=3,
        encoding="16UC1",
        step=6,
    )
    assert abs(frame.depth_m[0, 0] - 1.0) < 1e-6
    assert math.isnan(frame.depth_m[0, 1])


def test_project_optical_xyz_pinhole():
    calib = camera_calibration_from_pinhole(
        width=640, height=480, fx=500.0, fy=500.0, cx=320.0, cy=240.0
    )
    x, y, z = project_optical_xyz(320.0, 240.0, 1.0, calib)
    assert abs(x) < 1e-9 and abs(y) < 1e-9 and abs(z - 1.0) < 1e-9
    x2, y2, z2 = project_optical_xyz(420.0, 240.0, 1.0, calib)
    assert abs(x2 - 0.2) < 1e-6 and abs(y2) < 1e-9 and abs(z2 - 1.0) < 1e-9


def test_depth_pairing_exact_and_tolerance_and_consume():
    buf = DepthFrameBuffer(tolerance_sec=0.010, max_size=10)
    d0 = decode_depth_image(
        np.ones((2, 2), dtype=np.float32).tobytes(),
        height=2,
        width=2,
        encoding="32FC1",
        stamp_sec=1,
        stamp_nanosec=0,
    )
    d1 = decode_depth_image(
        np.ones((2, 2), dtype=np.float32).tobytes(),
        height=2,
        width=2,
        encoding="32FC1",
        stamp_sec=1,
        stamp_nanosec=5_000_000,  # +5 ms
    )
    buf.push(d0)
    buf.push(d1)
    exact = buf.pair_for_rgb(1, 0)
    assert exact.reason == "OK"
    assert exact.depth is not None
    assert exact.depth.stamp_nanosec == 0
    # Consumed — second pair uses the remaining +5 ms depth for RGB at +4 ms.
    near = buf.pair_for_rgb(1, 4_000_000)
    assert near.reason == "OK"
    assert near.skew_sec is not None and near.skew_sec < 0.010
    empty = buf.pair_for_rgb(1, 0)
    assert empty.reason == "DEPTH_UNPAIRED"
    assert empty.depth is None


def test_depth_pairing_rejects_beyond_tolerance():
    buf = DepthFrameBuffer(tolerance_sec=0.010, max_size=4)
    d = decode_depth_image(
        np.ones((2, 2), dtype=np.float32).tobytes(),
        height=2,
        width=2,
        encoding="32FC1",
        stamp_sec=1,
        stamp_nanosec=0,
    )
    buf.push(d)
    bad = buf.pair_for_rgb(1, 20_000_000)  # 20 ms
    assert bad.reason == "DEPTH_UNPAIRED"
    assert bad.depth is None
    # Depth not consumed when unpaired.
    assert len(buf) == 1


def _depth_at(sec: int, nsec: int) -> object:
    return decode_depth_image(
        np.ones((2, 2), dtype=np.float32).tobytes(),
        height=2,
        width=2,
        encoding="32FC1",
        stamp_sec=sec,
        stamp_nanosec=nsec,
    )


def test_sync_gate_rgb_then_matching_depth_pairs_ok():
    """Ubuntu103 race: RGB arrives before stamp-mirrored depth (~0.2s skew)."""
    buf = DepthFrameBuffer(tolerance_sec=0.010, max_size=10)
    gate = RgbDepthSyncGate(buf, sync_wait_sec=0.100)
    # Immediate pair fails (empty buffer) → await.
    assert gate.on_rgb("rgb-A", stamp_sec=5, stamp_nanosec=0, now_mono=1.0) is None
    assert gate.has_awaiting is True
    # Matching depth arrives within wait window.
    ready = gate.on_depth(_depth_at(5, 0))
    assert ready is not None
    assert ready.pair_reason == "OK"
    assert ready.payload == "rgb-A"
    assert ready.depth is not None
    assert ready.pair_skew_sec == 0.0
    assert gate.has_awaiting is False


def test_sync_gate_depth_first_then_rgb_immediate_ok():
    buf = DepthFrameBuffer(tolerance_sec=0.010, max_size=10)
    gate = RgbDepthSyncGate(buf, sync_wait_sec=0.100)
    assert gate.on_depth(_depth_at(7, 0)) is None
    ready = gate.on_rgb("rgb-B", stamp_sec=7, stamp_nanosec=0, now_mono=2.0)
    assert ready is not None
    assert ready.pair_reason == "OK"
    assert ready.payload == "rgb-B"


def test_sync_gate_timeout_unpaired_keeps_skew_from_stale_depth():
    buf = DepthFrameBuffer(tolerance_sec=0.010, max_size=10)
    gate = RgbDepthSyncGate(buf, sync_wait_sec=0.100)
    buf.push(_depth_at(1, 0))  # 200 ms earlier than RGB below
    assert gate.on_rgb("rgb-C", stamp_sec=1, stamp_nanosec=200_000_000, now_mono=10.0) is None
    assert gate.poll(10.05) is None  # still waiting
    timed = gate.poll(10.11)
    assert timed is not None
    assert timed.pair_reason == "DEPTH_UNPAIRED"
    assert timed.depth is None
    assert timed.pair_skew_sec is not None
    assert timed.pair_skew_sec > 0.01


def test_paired_empty_detections_keep_ok_not_unpaired():
    """No 2D targets → empty objects with pair_reason OK (not DEPTH_UNPAIRED)."""
    h, w = 480, 640
    depth_m = np.full((h, w), 1.0, dtype=np.float32)
    depth = decode_depth_image(
        depth_m.tobytes(),
        height=h,
        width=w,
        encoding="32FC1",
        stamp_sec=10,
        stamp_nanosec=0,
    )
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=500.0, fy=500.0, cx=320.0, cy=240.0
    )
    empty = DetectionBatch(
        key=FrameKey(
            source_session_id="s",
            observation_id=9,
            source_kind="LIVE_CAMERA",
            calibration_id=calib.calibration_id,
            frame_id="f",
            source_stamp_sec=10,
            source_stamp_nanosec=0,
        ),
        detections=(),
        image_width=w,
        image_height=h,
    )
    objects = build_object_batch(
        empty,
        depth=depth,
        calibration=calib,
        pair_skew_sec=0.0,
        pair_reason="OK",
    )
    assert objects.depth_paired is True
    assert objects.pair_reason == "OK"
    assert objects.objects == ()
    payload = object_batch_to_dict(objects)
    assert payload["objects"] == []
    assert payload["arm_ready"] == "NO"


def test_surface_sample_valid_constant_depth():
    h, w = 120, 160
    depth = np.full((h, w), 1.0, dtype=np.float32)
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=200.0, fy=200.0, cx=w / 2.0, cy=h / 2.0
    )
    bbox = BoundingBox2D(w / 2.0, h / 2.0, 40.0, 50.0)
    result = sample_visible_surface(depth, bbox, calib)
    assert result.position_valid is True
    assert result.invalid_reason == "OK"
    assert result.mask_source == "bbox_fill"
    assert abs(result.xyz[2] - 1.0) < 1e-5


def test_surface_sample_mask_too_small():
    h, w = 80, 80
    depth = np.full((h, w), 1.0, dtype=np.float32)
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=100.0, fy=100.0, cx=40.0, cy=40.0
    )
    bbox = BoundingBox2D(40.0, 40.0, 4.0, 4.0)  # tiny after erode
    result = sample_visible_surface(depth, bbox, calib)
    assert result.position_valid is False
    assert result.invalid_reason == "MASK_TOO_SMALL"


def test_surface_sample_depth_insufficient_nan():
    h, w = 120, 160
    depth = np.full((h, w), np.nan, dtype=np.float32)
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=200.0, fy=200.0, cx=w / 2.0, cy=h / 2.0
    )
    bbox = BoundingBox2D(w / 2.0, h / 2.0, 40.0, 50.0)
    result = sample_visible_surface(depth, bbox, calib)
    assert result.position_valid is False
    assert result.invalid_reason == "DEPTH_INSUFFICIENT"


def test_bbox_fill_mask_bounds():
    mask = bbox_fill_mask(BoundingBox2D(5, 5, 6, 4), height=10, width=10)
    assert mask.shape == (10, 10)
    assert int(mask.sum()) == 6 * 4


def test_object_batch_unpaired_keeps_entries_with_nan():
    batch = _batch_with_box()
    objects = build_object_batch(
        batch, depth=None, calibration=None, pair_reason="DEPTH_UNPAIRED"
    )
    assert len(objects.objects) == 1
    obj = objects.objects[0]
    assert obj.position_valid is False
    assert obj.invalid_reason == "DEPTH_UNPAIRED"
    assert obj.orientation_valid is False
    assert obj.tracking_valid is False
    assert obj.object_id == ""
    assert all(math.isnan(v) for v in obj.position_xyz)
    assert all(math.isnan(v) for v in obj.orientation_xyzw)
    payload = object_batch_to_dict(objects)
    for key in VISION_OBJECT_ARRAY_DICT_FIELDS:
        assert key in payload
    for key in VISION_OBJECT_DICT_FIELDS:
        assert key in payload["objects"][0]
    assert payload["arm_ready"] == "NO"
    assert payload["tracking_session_id"] == ""
    assert payload["objects"][0]["orientation_valid"] is False
    assert is_nan_number(payload["objects"][0]["position"]["x"])


def test_object_batch_paired_valid_position_and_calibration_id():
    h, w = 480, 640
    depth_m = np.full((h, w), 1.0, dtype=np.float32)
    depth = decode_depth_image(
        depth_m.tobytes(),
        height=h,
        width=w,
        encoding="32FC1",
        stamp_sec=10,
        stamp_nanosec=0,
        frame_id="fake_optical",
    )
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=500.0, fy=500.0, cx=320.0, cy=240.0, frame_id="fake_optical"
    )
    batch = _batch_with_box()
    objects = build_object_batch(
        batch,
        depth=depth,
        calibration=calib,
        pair_skew_sec=0.0,
        pair_reason="OK",
    )
    assert objects.depth_paired is True
    assert objects.calibration_id == calib.calibration_id
    assert len(objects.objects) == 1
    obj = objects.objects[0]
    assert obj.position_valid is True
    assert obj.invalid_reason == "OK"
    assert obj.orientation_valid is False
    assert abs(obj.position_xyz[2] - 1.0) < 1e-4
    payload = object_batch_to_dict(objects)
    assert payload["calibration_id"] == calib.calibration_id
    assert payload["objects"][0]["position_valid"] is True
    assert payload["objects"][0]["orientation_valid"] is False
    assert payload["arm_ready"] == "NO"


def test_object_batch_retains_failed_detections():
    """Every 2D detection gets an object entry even when depth fails."""
    batch = DetectionBatch(
        key=FrameKey(
            source_session_id="s",
            observation_id=2,
            source_kind="LIVE_CAMERA",
            calibration_id="c",
            frame_id="f",
            source_stamp_sec=1,
            source_stamp_nanosec=0,
        ),
        detections=(
            Detection(0, "bottle", 0.9, BoundingBox2D(50, 50, 40, 40)),
            Detection(1, "cup", 0.8, BoundingBox2D(100, 100, 30, 30)),
        ),
        image_width=200,
        image_height=200,
    )
    objects = build_object_batch(
        batch, depth=None, calibration=None, pair_reason="DEPTH_UNPAIRED"
    )
    assert [o.detection_index for o in objects.objects] == [0, 1]
    assert all(not o.position_valid for o in objects.objects)


def test_v1_ros_allows_enable_objects_when_topics_set(tmp_path):
    cfg = vision_config_from_mapping(
        {
            "mode": "v1_ros",
            "backend": "onnxruntime_cpu",
            "model_path": str(tmp_path / "m.onnx"),
            "model_manifest_path": str(tmp_path / "m.json"),
            "detector_enabled": True,
            "camera_contract": "DEV_WEBCAM_ONLY / NOT_ZED",
            "enable_objects": True,
            "depth_topic": "/dg/vision/fake/depth",
            "camera_info_topic": "/dg/vision/fake/camera_info",
        }
    )
    assert cfg.enable_objects is True
    assert cfg.enable_tracking is False


def test_enable_objects_still_rejected_outside_v1_ros():
    with pytest.raises(ValueError, match="enable_objects"):
        vision_config_from_mapping({"enable_objects": True})
    with pytest.raises(ValueError, match="enable_objects"):
        vision_config_from_mapping(
            {
                "mode": "offline",
                "backend": "onnxruntime_cpu",
                "model_path": "/tmp/m.onnx",
                "model_manifest_path": "/tmp/m.json",
                "enable_objects": True,
            }
        )


def test_enable_tracking_allowed_with_objects_on_v1_ros(tmp_path):
    cfg = vision_config_from_mapping(
        {
            "mode": "v1_ros",
            "backend": "onnxruntime_cpu",
            "model_path": str(tmp_path / "m.onnx"),
            "model_manifest_path": str(tmp_path / "m.json"),
            "detector_enabled": True,
            "camera_contract": "DEV_WEBCAM_ONLY / NOT_ZED",
            "enable_objects": True,
            "enable_tracking": True,
            "depth_topic": "/dg/vision/fake/depth",
            "camera_info_topic": "/dg/vision/fake/camera_info",
        }
    )
    assert cfg.enable_tracking is True
    assert cfg.enable_objects is True
    assert cfg.tracker_match_iou == 0.30


def test_enable_tracking_rejected_on_skeleton_and_offline():
    with pytest.raises(ValueError, match="enable_tracking"):
        vision_config_from_mapping({"enable_tracking": True})
    with pytest.raises(ValueError, match="enable_tracking"):
        vision_config_from_mapping(
            {
                "mode": "offline",
                "backend": "onnxruntime_cpu",
                "model_path": "/tmp/m.onnx",
                "model_manifest_path": "/tmp/m.json",
                "enable_tracking": True,
            }
        )
