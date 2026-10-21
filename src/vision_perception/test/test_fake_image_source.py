"""Fake-image file source helpers (no ROS / no camera)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from vision_perception.fake_image_source import (
    load_fake_rgb,
    match_rgb_to_hw,
    resolve_fake_image_path,
)


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_resolve_prefers_image_path_then_aliases():
    assert resolve_fake_image_path("a.jpg", "b.jpg", "c.npy") == "a.jpg"
    assert resolve_fake_image_path("", "b.jpg", "c.npy") == "b.jpg"
    assert resolve_fake_image_path("", "", "c.npy") == "c.npy"
    assert resolve_fake_image_path("", "", "") == ""


def test_load_fake_rgb_default_colour_blocks():
    rgb, note = load_fake_rgb("", width=32, height=24)
    assert rgb.shape == (24, 32, 3)
    assert note == "synthetic_colour_blocks"
    assert rgb.dtype == np.uint8


def test_load_fake_rgb_from_committed_hint_npy():
    path = EXAMPLES / "smoke_rgb_hint.npy"
    assert path.is_file()
    rgb, note = load_fake_rgb(str(path))
    assert rgb.ndim == 3 and rgb.shape[2] == 3
    assert note.startswith("file:smoke_rgb_hint.npy")
    assert rgb.shape[0] >= 8 and rgb.shape[1] >= 8


def test_match_rgb_to_hw_resizes_native_file_to_fake_depth_plane():
    """COCO/native JPG vs fixed 640x480 fake depth must be matched for V2 size gate."""
    path = EXAMPLES / "smoke_rgb_hint.npy"
    rgb, _ = load_fake_rgb(str(path))
    assert rgb.shape[:2] != (480, 640)
    matched = match_rgb_to_hw(rgb, 480, 640)
    assert matched.shape == (480, 640, 3)
    assert matched.dtype == np.uint8
    same = match_rgb_to_hw(matched, 480, 640)
    assert same.shape == (480, 640, 3)


def test_launch_declares_fake_image_path():
    text = (
        Path(__file__).resolve().parents[1] / "launch" / "vision.launch.py"
    ).read_text(encoding="utf-8")
    assert 'DeclareLaunchArgument(\n            "fake_image_path"' in text or (
        '"fake_image_path"' in text and "LaunchConfiguration(\"fake_image_path\")" in text
    )
    assert "use_fake_depth" in text
    assert "enable_objects" in text
    assert "vision_fake_depth_publisher" in text
    assert "stamp_source_topic" in text
    assert 'rgb_topic": ""' in text or "rgb_topic\": \"\"" in text
    # Synthetic path must force RELIABLE so fake depth/RGB are not dropped.
    assert 'image_qos_reliability"] = "reliable"' in text or (
        '"image_qos_reliability": "reliable"' in text
    )
