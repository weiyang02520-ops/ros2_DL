"""Runtime pin contract + empty-detections healthy status (no ROS / no camera)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vision_perception.runtime_deps import (
    NUMPY_PIP,
    ONNXRUNTIME_PIP,
    OPENCV_PIP,
    PIP_INSTALL_ORDER,
    check_numpy_opencv_compat,
    numpy_major_version,
    pip_install_commands,
)
from vision_perception.status_fields import (
    LEVEL_OK,
    LEVEL_WARN,
    as_diagnostic_level_byte,
    compose_v1_ros_diagnostic,
    empty_detections_are_healthy,
)


ROOT = Path(__file__).resolve().parents[1]


def test_pip_order_is_numpy_then_opencv_then_ort():
    assert PIP_INSTALL_ORDER[0].startswith("numpy")
    assert "<2" in PIP_INSTALL_ORDER[0]
    assert "opencv" in PIP_INSTALL_ORDER[1]
    assert "onnxruntime" in PIP_INSTALL_ORDER[2]
    cmds = pip_install_commands()
    assert len(cmds) == 3
    assert "numpy" in cmds[0] and "opencv" in cmds[1] and "onnxruntime" in cmds[2]


def test_requirements_runtime_txt_matches_pins():
    text = (ROOT / "requirements-runtime.txt").read_text(encoding="utf-8")
    assert "numpy>=1.26.4,<2" in text
    assert OPENCV_PIP in text
    assert ONNXRUNTIME_PIP in text
    # Order: numpy line before opencv before onnxruntime in the pin list section.
    n = text.index("numpy>=")
    o = text.index("opencv-python-headless")
    r = text.index("onnxruntime==")
    assert n < o < r


def test_setup_py_pins_numpy_less_than_2():
    text = (ROOT / "setup.py").read_text(encoding="utf-8")
    assert "numpy>=1.26.4,<2" in text
    assert OPENCV_PIP in text
    assert ONNXRUNTIME_PIP in text


def test_package_xml_mentions_numpy_pin_and_opencv():
    text = (ROOT / "package.xml").read_text(encoding="utf-8")
    assert "python3-numpy" in text
    assert "python3-opencv" in text
    assert "numpy" in text and "_ARRAY_API" in text


def test_check_numpy_rejects_major_2():
    check_numpy_opencv_compat("1.26.4")
    with pytest.raises(RuntimeError, match="_ARRAY_API"):
        check_numpy_opencv_compat("2.0.0")
    assert numpy_major_version("1.26.4") == 1
    assert NUMPY_PIP.endswith("<2")


def test_empty_detections_keep_ok_status():
    level, message, fields = compose_v1_ros_diagnostic(
        frames_received=40,
        frames_processed=30,
        frames_dropped=5,
        last_observation_id=30,
        last_detection_count=0,
        last_worker_error="",
        source_session_id="sess-ok",
        backend="onnxruntime_cpu",
        last_input_age_sec=0.1,
    )
    assert level == LEVEL_OK == b"\x00"
    assert isinstance(level, bytes) and len(level) == 1
    assert message == "V1_ROS_DEV_WEBCAM"
    assert fields["last_detection_count"] == "0"
    assert fields["empty_detections_healthy"] == "true"
    assert fields["source_session_id"] == "sess-ok"
    assert fields["backend"] == "onnxruntime_cpu"
    assert fields["arm_ready"] == "NO"
    assert empty_detections_are_healthy(0, "") is True


def test_worker_error_degrades_status_not_empty_boxes():
    level, message, fields = compose_v1_ros_diagnostic(
        frames_received=10,
        frames_processed=1,
        frames_dropped=0,
        last_observation_id=1,
        last_detection_count=0,
        last_worker_error="onnx boom",
    )
    assert level == LEVEL_WARN == b"\x01"
    assert isinstance(level, bytes) and len(level) == 1
    assert message == "V1_ROS_DEGRADED"
    assert fields["last_worker_error"] == "onnx boom"
    assert empty_detections_are_healthy(0, "onnx boom") is False


def test_v2_status_marks_object_output_and_missing_calib():
    level, message, fields = compose_v1_ros_diagnostic(
        frames_received=3,
        frames_processed=2,
        frames_dropped=0,
        last_observation_id=2,
        last_detection_count=1,
        enable_objects=True,
        object_output_active=True,
        camera_info_received=False,
        last_input_age_sec=0.1,
        depth_topic="/dg/vision/fake/depth",
        camera_info_topic="/dg/vision/fake/camera_info",
    )
    assert level == LEVEL_WARN
    assert message == "V2_OBJECTS_NO_CALIBRATION"
    assert fields["object_output_active"] == "true"
    assert fields["enable_objects"] == "true"
    assert fields["arm_ready"] == "NO"
    assert fields["camera_info_received"] == "false"

    level2, message2, fields2 = compose_v1_ros_diagnostic(
        frames_received=3,
        frames_processed=2,
        frames_dropped=0,
        last_observation_id=2,
        last_detection_count=1,
        enable_objects=True,
        object_output_active=True,
        camera_info_received=True,
        last_input_age_sec=0.1,
        last_pair_reason="OK",
        last_position_valid_count=1,
    )
    assert level2 == LEVEL_OK
    assert message2 == "V2_OBJECTS_DEV"
    assert fields2["last_pair_reason"] == "OK"
    assert fields2["last_position_valid_count"] == "1"


def test_diagnostic_level_byte_accepts_int_and_rejects_bad_length():
    assert as_diagnostic_level_byte(0) == b"\x00"
    assert as_diagnostic_level_byte(1) == b"\x01"
    assert as_diagnostic_level_byte(b"\x02") == b"\x02"
    with pytest.raises(ValueError, match="length-1"):
        as_diagnostic_level_byte(b"\x00\x01")
    with pytest.raises(TypeError):
        as_diagnostic_level_byte("0")  # type: ignore[arg-type]
