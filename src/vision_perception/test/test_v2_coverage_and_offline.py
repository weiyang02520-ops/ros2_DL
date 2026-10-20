"""V2 coverage metrics + objects_pipeline mask wiring (no ORT / no ROS)."""

from __future__ import annotations

import math

import numpy as np

from vision_perception.depth_io import (
    camera_calibration_from_pinhole,
    decode_depth_image,
)
from vision_perception.evaluation import summarize_v2_object_coverage
from vision_perception.message_mapping import object_batch_to_dict
from vision_perception.objects_pipeline import build_object_batch
from vision_perception.types import BoundingBox2D, Detection, DetectionBatch, FrameKey


def test_summarize_v2_coverage_blocked_without_truth():
    payload = summarize_v2_object_coverage(
        [
            {
                "depth_paired": True,
                "pair_reason": "OK",
                "objects": [
                    {"position_valid": True, "invalid_reason": "OK"},
                    {"position_valid": False, "invalid_reason": "DEPTH_INSUFFICIENT"},
                ],
            },
            {
                "depth_paired": False,
                "pair_reason": "DEPTH_UNPAIRED",
                "objects": [
                    {"position_valid": False, "invalid_reason": "DEPTH_UNPAIRED"},
                ],
            },
        ]
    )
    assert payload["result"] == "NOT_RUN"
    assert payload["v2_accuracy"] == "BLOCKED"
    assert payload["arm_ready"] == "NO"
    assert payload["batches"] == 2
    assert payload["batches_paired"] == 1
    assert payload["objects"] == 3
    assert payload["position_valid"] == 1
    assert payload["invalid_reason_counts"]["OK"] == 1


def test_objects_pipeline_uses_yolo_seg_mask_when_present():
    h, w = 120, 160
    depth = np.full((h, w), 1.0, dtype=np.float32)
    # Seg mask: only a small central disk — still large enough after erode.
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[40:80, 50:110] = 1
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=200.0, fy=200.0, cx=w / 2.0, cy=h / 2.0
    )
    batch = DetectionBatch(
        key=FrameKey(
            source_session_id="s",
            observation_id=1,
            source_kind="OFFLINE_FILE",
            calibration_id=calib.calibration_id,
            frame_id="f",
        ),
        detections=(
            Detection(
                0,
                "bottle",
                0.9,
                BoundingBox2D(80, 60, 80, 60),
                mask=mask,
                mask_source="yolo_seg",
            ),
        ),
        image_width=w,
        image_height=h,
    )
    depth_frame = decode_depth_image(
        depth.tobytes(),
        height=h,
        width=w,
        encoding="32FC1",
    )
    objects = build_object_batch(
        batch,
        depth=depth_frame,
        calibration=calib,
        pair_skew_sec=0.0,
        pair_reason="OK",
    )
    assert objects.mask_source == "yolo_seg"
    assert objects.objects[0].mask_source == "yolo_seg"
    assert objects.objects[0].position_valid is True
    assert abs(objects.objects[0].position_xyz[2] - 1.0) < 1e-4
    payload = object_batch_to_dict(objects)
    assert payload["arm_ready"] == "NO"
    assert payload["objects"][0]["orientation_valid"] is False


def test_yolo_seg_mask_too_small_reports_mask_too_small():
    h, w = 100, 100
    depth = np.full((h, w), 1.0, dtype=np.float32)
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[48:52, 48:52] = 1  # tiny → erode → MASK_TOO_SMALL
    calib = camera_calibration_from_pinhole(
        width=w, height=h, fx=100.0, fy=100.0, cx=50.0, cy=50.0
    )
    batch = DetectionBatch(
        key=FrameKey(
            source_session_id="s",
            observation_id=2,
            source_kind="OFFLINE_FILE",
            calibration_id=calib.calibration_id,
        ),
        detections=(
            Detection(
                0,
                "cup",
                0.8,
                BoundingBox2D(50, 50, 40, 40),
                mask=mask,
                mask_source="yolo_seg",
            ),
        ),
        image_width=w,
        image_height=h,
    )
    depth_frame = decode_depth_image(
        depth.tobytes(), height=h, width=w, encoding="32FC1"
    )
    objects = build_object_batch(
        batch,
        depth=depth_frame,
        calibration=calib,
        pair_reason="OK",
        pair_skew_sec=0.0,
    )
    assert objects.objects[0].position_valid is False
    assert objects.objects[0].invalid_reason == "MASK_TOO_SMALL"
    assert all(math.isnan(v) for v in objects.objects[0].position_xyz)
