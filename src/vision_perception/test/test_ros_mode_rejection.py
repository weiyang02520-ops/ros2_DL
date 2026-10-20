"""ROS mode allowlist: skeleton + v1_ros; legacy mode:=v1 must still fail."""

from __future__ import annotations

from pathlib import Path

import pytest

from vision_perception.config import normalize_ros_node_mode, require_ros_skeleton_mode


LAUNCH_PATH = Path(__file__).resolve().parents[1] / "launch" / "vision.launch.py"
NODE_PATH = Path(__file__).resolve().parents[1] / "vision_perception" / "vision_node.py"


@pytest.mark.parametrize("mode", ["v1", "offline", "V1", "ready", "", "detect"])
def test_normalize_rejects_legacy_and_unknown_modes(mode: str):
    with pytest.raises(ValueError, match="Unsupported ROS mode"):
        normalize_ros_node_mode(mode)


def test_normalize_accepts_skeleton_and_v1_ros():
    assert normalize_ros_node_mode("skeleton") == "skeleton"
    assert normalize_ros_node_mode(" v1_ros ") == "v1_ros"


def test_require_ros_skeleton_mode_still_skeleton_only():
    assert require_ros_skeleton_mode("skeleton") == "skeleton"
    with pytest.raises(ValueError):
        require_ros_skeleton_mode("v1_ros")
    with pytest.raises(ValueError, match="Unsupported ROS mode"):
        require_ros_skeleton_mode("v1")


def test_launch_declares_and_forwards_mode_and_webcam_args():
    text = LAUNCH_PATH.read_text(encoding="utf-8")
    assert "DeclareLaunchArgument" in text
    assert '"mode"' in text
    assert '"mode": LaunchConfiguration("mode")' in text
    assert "use_webcam" in text
    assert "use_fake_image" in text
    assert "publish_debug_image" in text
    assert "enable_objects" in text
    assert "enable_tracking" in text
    assert 'LaunchConfiguration("enable_tracking")' in text
    assert "ParameterValue" in text
    assert "vision_webcam_publisher" in text
    assert "default_value=\"skeleton\"" in text or "default_value='skeleton'" in text


def test_node_uses_normalize_and_exits_nonzero_on_value_error():
    text = NODE_PATH.read_text(encoding="utf-8")
    assert "normalize_ros_node_mode" in text
    assert "sys.exit(exit_code)" in text
    assert "except (ValueError, RuntimeError, FileNotFoundError, OSError)" in text
    assert "v1_ros" in text
    assert "DEV_WEBCAM_ONLY" in text
