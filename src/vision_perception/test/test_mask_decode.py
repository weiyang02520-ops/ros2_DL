"""YOLO-seg mask reconstruction unit tests (synthetic coeffs/protos)."""

from __future__ import annotations

import numpy as np

from vision_perception.mask_decode import (
    combine_mask_coefficients,
    reconstruct_instance_mask,
    sigmoid,
)
from vision_perception.postprocess import decode_yolo11_seg_boxes
from vision_perception.types import BoundingBox2D, LetterboxMeta


def test_sigmoid_bounds():
    out = sigmoid(np.array([-100.0, 0.0, 100.0], dtype=np.float32))
    assert out[0] < 1e-6
    assert abs(out[1] - 0.5) < 1e-5
    assert out[2] > 1.0 - 1e-6


def test_combine_and_reconstruct_yolo_seg_mask():
    # Strong positive coeff on first prototype channel → filled centre blob.
    protos = np.zeros((1, 32, 160, 160), dtype=np.float32)
    protos[0, 0, 40:120, 40:120] = 10.0
    coeffs = np.zeros(32, dtype=np.float32)
    coeffs[0] = 1.0
    linear = combine_mask_coefficients(coeffs, protos)
    assert linear.shape == (160, 160)
    assert float(linear[80, 80]) > 1.0

    letterbox = LetterboxMeta(
        scale=1.0,
        pad_left=0,
        pad_top=0,
        pad_right=0,
        pad_bottom=0,
        source_width=640,
        source_height=640,
        model_size=640,
    )
    bbox = BoundingBox2D(320, 320, 200, 200)
    mask, source = reconstruct_instance_mask(
        coeffs, protos, letterbox, bbox, mask_threshold=0.5
    )
    assert source == "yolo_seg"
    assert mask is not None
    assert mask.shape == (640, 640)
    assert int(mask.sum()) > 100
    # Outside bbox must be zero.
    assert int(mask[0:10, 0:10].sum()) == 0


def test_all_zero_prototypes_fall_back_to_bbox_fill_marker():
    protos = np.zeros((32, 160, 160), dtype=np.float32)
    coeffs = np.zeros(32, dtype=np.float32)
    letterbox = LetterboxMeta(
        scale=1.0,
        pad_left=0,
        pad_top=0,
        pad_right=0,
        pad_bottom=0,
        source_width=320,
        source_height=240,
        model_size=640,
    )
    bbox = BoundingBox2D(160, 120, 80, 80)
    mask, source = reconstruct_instance_mask(coeffs, protos, letterbox, bbox)
    assert mask is None
    assert source == "bbox_fill"


def test_decode_with_output1_attaches_mask_when_possible():
    # Build a tiny synthetic output0 with one bottle candidate at image centre.
    n = 8400
    output0 = np.zeros((1, 116, n), dtype=np.float32)
    # letterbox coords for centre of 80x60 → padded 640 canvas.
    # Use a box covering much of the letterboxed content.
    output0[0, 0, 0] = 320.0  # cx
    output0[0, 1, 0] = 240.0  # cy
    output0[0, 2, 0] = 100.0  # w
    output0[0, 3, 0] = 120.0  # h
    output0[0, 4 + 39, 0] = 0.95  # bottle class score
    output0[0, 84, 0] = 1.0  # mask coeff 0

    protos = np.zeros((1, 32, 160, 160), dtype=np.float32)
    protos[0, 0, :, :] = 8.0

    letterbox = LetterboxMeta(
        scale=1.0,
        pad_left=0,
        pad_top=0,
        pad_right=0,
        pad_bottom=0,
        source_width=640,
        source_height=480,
        model_size=640,
    )
    dets = decode_yolo11_seg_boxes(
        output0,
        letterbox,
        {39: "bottle", 41: "cup"},
        output1=protos,
        mask_threshold=0.5,
    )
    assert len(dets) == 1
    assert dets[0].class_name == "bottle"
    assert dets[0].mask is not None
    assert dets[0].mask_source == "yolo_seg"
    assert dets[0].mask.shape == (480, 640)


def test_decode_without_output1_leaves_mask_empty():
    n = 8400
    output0 = np.zeros((1, 116, n), dtype=np.float32)
    output0[0, 0, 0] = 100.0
    output0[0, 1, 0] = 80.0
    output0[0, 2, 0] = 40.0
    output0[0, 3, 0] = 50.0
    output0[0, 4 + 41, 0] = 0.9
    letterbox = LetterboxMeta(
        scale=1.0,
        pad_left=0,
        pad_top=0,
        pad_right=0,
        pad_bottom=0,
        source_width=200,
        source_height=160,
        model_size=640,
    )
    dets = decode_yolo11_seg_boxes(
        output0, letterbox, {39: "bottle", 41: "cup"}, output1=None
    )
    assert len(dets) == 1
    assert dets[0].mask is None
    assert dets[0].mask_source == ""
