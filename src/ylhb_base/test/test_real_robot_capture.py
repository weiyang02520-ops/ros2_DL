import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from real_robot_capture import (  # noqa: E402
    DEFAULT_TOPICS,
    build_manifest,
    sanitize_label,
    unique_topics,
    write_json,
)


def test_capture_topics_cover_all_three_models_and_uwb():
    required = {
        "/scan",
        "/odom",
        "/dg/lidar/quality",
        "/dg/uwb/pose",
        "/dg/uwb/quality",
        "/dg/fusion/status",
        "/dg/relocalization/status",
    }
    assert required.issubset(DEFAULT_TOPICS)


def test_unique_topics_preserves_order_and_rejects_relative_names():
    assert unique_topics(("/scan", "/odom", "/scan")) == ("/scan", "/odom")
    try:
        unique_topics(("cmd_vel",))
    except ValueError as error:
        assert "absolute ROS topic" in str(error)
    else:
        raise AssertionError("relative topic should be rejected")


def test_sanitize_label_blocks_path_traversal():
    assert sanitize_label("EXP-02 idle/real") == "EXP-02_idle_real"
    assert "/" not in sanitize_label("../../trial")


def test_manifest_is_deterministic_and_excludes_itself(tmp_path):
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "manifest.json").write_text("old", encoding="utf-8")
    entries = build_manifest(tmp_path)
    assert [item["path"] for item in entries] == ["a.txt", "b.txt"]
    assert all(len(str(item["sha256"])) == 64 for item in entries)


def test_write_json_replaces_atomically(tmp_path):
    target = tmp_path / "metadata.json"
    write_json(target, {"status": "first"})
    write_json(target, {"status": "second", "中文": "保留"})
    assert json.loads(target.read_text(encoding="utf-8")) == {
        "status": "second",
        "中文": "保留",
    }
    assert not target.with_suffix(".json.tmp").exists()


def test_capture_script_has_no_ros_motion_publish_command():
    source = (SCRIPTS / "real_robot_capture.py").read_text(encoding="utf-8")
    assert "ros2 topic pub" not in source
    assert '("ros2", "topic", "pub"' not in source
