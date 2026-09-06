from pathlib import Path


def test_verified_motor_direction_transform_is_preserved():
    source = (
        Path(__file__).resolve().parents[1]
        / "ylhb_mobile_bridge"
        / "ros_bridge.py"
    ).read_text(encoding="utf-8")
    assert "msg.linear.x = -linear_x" in source
    assert "msg.angular.z = angular_z" in source
