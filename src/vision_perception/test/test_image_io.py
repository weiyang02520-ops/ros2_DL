"""Image decode and letterbox round-trip checks (NumPy only)."""

from __future__ import annotations

import numpy as np

from vision_perception.image_io import (
    decode_color_image,
    letterbox_rgb,
    letterbox_to_nchw_float32,
    restore_xyxy_from_letterbox,
)


def test_decode_rgb8_and_bgr8():
    rgb = np.zeros((2, 3, 3), dtype=np.uint8)
    rgb[0, 0] = (10, 20, 30)
    decoded = decode_color_image(rgb.tobytes(), 2, 3, "rgb8")
    assert decoded.shape == (2, 3, 3)
    assert tuple(decoded[0, 0]) == (10, 20, 30)

    bgr = rgb[:, :, ::-1].copy()
    decoded_bgr = decode_color_image(bgr.tobytes(), 2, 3, "bgr8")
    assert tuple(decoded_bgr[0, 0]) == (10, 20, 30)


def test_decode_rejects_bad_step():
    data = bytes([0] * (2 * 2 * 3))
    try:
        decode_color_image(data, 2, 2, "rgb8", step=4)
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "step" in str(exc)


def test_letterbox_preserves_aspect_and_padding():
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    image[:, :] = (40, 80, 120)
    canvas, meta = letterbox_rgb(image, model_size=640, pad_value=114)
    assert canvas.shape == (640, 640, 3)
    assert meta.source_width == 200
    assert meta.source_height == 100
    assert meta.pad_top == meta.pad_bottom
    # Non-padded centre region should not be only pad_value.
    centre = canvas[320, 320]
    assert not np.array_equal(centre, np.array([114, 114, 114], dtype=np.uint8))


def test_letterbox_to_nchw_range():
    canvas = np.full((640, 640, 3), 255, dtype=np.uint8)
    tensor = letterbox_to_nchw_float32(canvas)
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert float(tensor.max()) == 1.0


def test_restore_xyxy_roundtrip_identity_when_no_pad_needed():
    image = np.zeros((640, 640, 3), dtype=np.uint8)
    _canvas, meta = letterbox_rgb(image, model_size=640)
    assert meta.scale == 1.0
    assert meta.pad_left == 0 and meta.pad_top == 0
    restored = restore_xyxy_from_letterbox(10, 20, 30, 40, meta)
    assert restored == (10.0, 20.0, 30.0, 40.0)
