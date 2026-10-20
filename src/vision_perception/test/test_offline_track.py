"""Offline V3 track CLI / sequence runner (no ROS / camera / ONNX)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from vision_perception.offline_track import load_track_sequence, run_tracker_on_frames
from vision_perception.offline_track_cli import TRACK_CSV_FIELDS, main as track_cli_main


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _crossing_frames():
    return [
        {
            "frame_id": "f0",
            "stamp_sec": 0.0,
            "detections": [
                {
                    "detection_index": 0,
                    "class_name": "cup",
                    "confidence": 0.9,
                    "bbox": {
                        "center_x": 40,
                        "center_y": 40,
                        "size_x": 20,
                        "size_y": 28,
                    },
                },
                {
                    "detection_index": 1,
                    "class_name": "cup",
                    "confidence": 0.9,
                    "bbox": {
                        "center_x": 120,
                        "center_y": 40,
                        "size_x": 20,
                        "size_y": 28,
                    },
                },
            ],
        },
        {
            "frame_id": "f1",
            "stamp_sec": 0.1,
            "detections": [
                {
                    "detection_index": 0,
                    "class_name": "cup",
                    "confidence": 0.9,
                    "bbox": {
                        "center_x": 41,
                        "center_y": 40,
                        "size_x": 20,
                        "size_y": 28,
                    },
                },
                {
                    "detection_index": 1,
                    "class_name": "cup",
                    "confidence": 0.9,
                    "bbox": {
                        "center_x": 119,
                        "center_y": 40,
                        "size_x": 20,
                        "size_y": 28,
                    },
                },
            ],
        },
        {
            "frame_id": "f2",
            "stamp_sec": 0.2,
            "detections": [
                {
                    "detection_index": 0,
                    "class_name": "cup",
                    "confidence": 0.9,
                    "bbox": {
                        "center_x": 42,
                        "center_y": 40,
                        "size_x": 20,
                        "size_y": 28,
                    },
                },
                {
                    "detection_index": 1,
                    "class_name": "cup",
                    "confidence": 0.9,
                    "bbox": {
                        "center_x": 118,
                        "center_y": 40,
                        "size_x": 20,
                        "size_y": 28,
                    },
                },
            ],
        },
    ]


def test_confirm_hits_before_id_and_session_field():
    payload = run_tracker_on_frames(_crossing_frames(), confirm_hits=3)
    rows = payload["rows"]
    f0 = [r for r in rows if r["frame_id"] == "f0"]
    f1 = [r for r in rows if r["frame_id"] == "f1"]
    f2 = [r for r in rows if r["frame_id"] == "f2"]
    assert all(not r["tracking_valid"] and r["object_id"] == "" for r in f0)
    assert all(not r["tracking_valid"] and r["object_id"] == "" for r in f1)
    assert all(r["tracking_valid"] and r["object_id"].startswith("trk_") for r in f2)
    assert len({r["object_id"] for r in f2}) == 2
    assert payload["tracking_session_id"]
    assert all(r["tracking_session_id"] == payload["tracking_session_id"] for r in rows)
    assert payload["matcher"] == "deterministic_greedy_per_class_iou"
    assert payload["metrics"]["result"] == "NOT_RUN"
    assert payload["metrics"]["idf1"] == "BLOCKED"
    assert payload["arm_ready"] == "NO"


def test_example_sequence_loads_and_runs():
    raw = json.loads(
        (EXAMPLES / "track_sequence.example.json").read_text(encoding="utf-8")
    )
    frames = load_track_sequence(raw)
    assert len(frames) == 3
    payload = run_tracker_on_frames(frames, confirm_hits=3)
    assert payload["frames"] == 3
    assert payload["metrics"]["has_identity_annotations"] is False


def test_cli_writes_json_csv_metrics(tmp_path: Path):
    seq = tmp_path / "seq.json"
    seq.write_text(
        json.dumps({"frames": _crossing_frames()}, indent=2) + "\n",
        encoding="utf-8",
    )
    out_json = tmp_path / "tracks.json"
    out_csv = tmp_path / "tracks.csv"
    out_metrics = tmp_path / "metrics.json"
    rc = track_cli_main(
        [
            "--sequence",
            str(seq),
            "--out-json",
            str(out_json),
            "--out-csv",
            str(out_csv),
            "--out-metrics",
            str(out_metrics),
            "--confirm-hits",
            "3",
        ]
    )
    assert rc == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["stage"] == "V3_TRACKING_OFFLINE"
    metrics = json.loads(out_metrics.read_text(encoding="utf-8"))
    assert metrics["result"] == "NOT_RUN"
    assert metrics["idf1"] == "BLOCKED"
    with out_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == TRACK_CSV_FIELDS
        csv_rows = list(reader)
    assert len(csv_rows) == len(payload["rows"])
    assert any(row["tracking_valid"] in {"True", "true", True} or row["object_id"] for row in csv_rows)


def test_cli_missing_sequence_exits_2(tmp_path: Path):
    rc = track_cli_main(["--sequence", str(tmp_path / "missing.json")])
    assert rc == 2
