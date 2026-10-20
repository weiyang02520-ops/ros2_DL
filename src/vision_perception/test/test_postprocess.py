"""Synthetic YOLO11-seg box decode and NMS tests (no ONNX / no camera)."""

from __future__ import annotations

import numpy as np

from vision_perception.pipeline import process_array_with_synthetic_output0
from vision_perception.postprocess import box_iou_xyxy, nms_per_class
from vision_perception.types import LetterboxMeta
from vision_perception.postprocess import decode_yolo11_seg_boxes


def _empty_output0(num_preds: int = 8400) -> np.ndarray:
    return np.zeros((1, 116, num_preds), dtype=np.float32)


def test_box_iou_identical_is_one():
    assert box_iou_xyxy((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0


def test_nms_keeps_highest_per_class():
    boxes = np.array(
        [
            [0, 0, 10, 10],
            [1, 1, 11, 11],
            [50, 50, 60, 60],
        ],
        dtype=np.float32,
    )
    scores = np.array([0.9, 0.8, 0.7], dtype=np.float32)
    class_ids = np.array([39, 39, 41], dtype=np.int32)
    keep = nms_per_class(boxes, scores, class_ids, iou_threshold=0.45)
    assert 0 in keep
    assert 1 not in keep
    assert 2 in keep


def test_decode_filters_to_bottle_cup_and_threshold():
    output0 = _empty_output0(4)
    # Candidate 0: bottle high score, xywh in model space around centre.
    output0[0, 0:4, 0] = np.array([320, 320, 40, 60], dtype=np.float32)
    output0[0, 4 + 39, 0] = 0.91
    # Candidate 1: person (class 0) — must be dropped.
    output0[0, 0:4, 1] = np.array([100, 100, 20, 20], dtype=np.float32)
    output0[0, 4 + 0, 1] = 0.99
    # Candidate 2: cup below threshold.
    output0[0, 0:4, 2] = np.array([200, 200, 30, 30], dtype=np.float32)
    output0[0, 4 + 41, 2] = 0.10
    # Candidate 3: cup above threshold.
    output0[0, 0:4, 3] = np.array([400, 300, 25, 25], dtype=np.float32)
    output0[0, 4 + 41, 3] = 0.80

    meta = LetterboxMeta(
        scale=1.0,
        pad_left=0,
        pad_top=0,
        pad_right=0,
        pad_bottom=0,
        source_width=640,
        source_height=640,
    )
    detections = decode_yolo11_seg_boxes(
        output0,
        meta,
        class_id_to_name={39: "bottle", 41: "cup"},
        confidence_threshold=0.35,
        nms_iou_threshold=0.45,
        max_detections=20,
    )
    names = [d.class_name for d in detections]
    assert names == ["bottle", "cup"]
    assert detections[0].detection_index == 0
    assert detections[1].detection_index == 1
    assert detections[0].confidence >= 0.9


def test_pipeline_synthetic_path_on_small_image():
    image = np.zeros((80, 120, 3), dtype=np.uint8)
    image[20:60, 40:80] = (200, 30, 30)
    output0 = _empty_output0(1)
    # After letterbox, geometry mapping still yields a clipped box in source space.
    output0[0, 0:4, 0] = np.array([320, 320, 80, 80], dtype=np.float32)
    output0[0, 4 + 39, 0] = 0.88
    batch = process_array_with_synthetic_output0(image, output0)
    assert batch.key.source_kind == "OFFLINE_FILE"
    assert batch.image_width == 120
    assert batch.image_height == 80
    assert len(batch.detections) == 1
    assert batch.detections[0].class_name == "bottle"


def test_empty_output_means_no_targets_not_error():
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    batch = process_array_with_synthetic_output0(image, _empty_output0(8))
    assert batch.detections == ()
