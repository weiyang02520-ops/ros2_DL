"""CLI: detection-sequence JSON → tracks JSON/CSV (V3 scaffolding).

No ROS / camera / ONNX / ZED. Does not claim IDF1 PASS without identity labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence


TRACK_CSV_FIELDS = [
    "frame_id",
    "stamp_sec",
    "detection_index",
    "class_name",
    "confidence",
    "bbox_center_x",
    "bbox_center_y",
    "bbox_size_x",
    "bbox_size_y",
    "object_id",
    "tracking_valid",
    "track_id",
    "track_state",
    "tracking_session_id",
]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "V3 offline track: detection-sequence JSON → tracks. "
            "Deterministic greedy per-class IoU (not Hungarian). "
            "Does not claim LIVE_CAMERA or IDF1 PASS."
        )
    )
    parser.add_argument(
        "--sequence",
        required=True,
        help="JSON path: {frames:[...]} or a list of frames",
    )
    parser.add_argument("--out-json", default="", help="tracks.json payload")
    parser.add_argument("--out-csv", default="", help="tracks.csv")
    parser.add_argument(
        "--out-metrics",
        default="",
        help="Scaffold metrics JSON (result=NOT_RUN / idf1=BLOCKED)",
    )
    parser.add_argument("--match-iou", type=float, default=0.30)
    parser.add_argument("--confirm-hits", type=int, default=3)
    parser.add_argument("--lost-timeout-sec", type=float, default=0.70)
    parser.add_argument(
        "--identity-annotations",
        default="",
        help=(
            "Optional identity labels JSON for IDF1 scaffold numbers. "
            "result stays NOT_RUN (never auto PASS)."
        ),
    )
    return parser.parse_args(argv)


def _write_tracks_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACK_CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in TRACK_CSV_FIELDS})


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    from vision_perception.evaluation import load_identity_annotations_file
    from vision_perception.offline_track import load_track_sequence, run_tracker_on_frames

    seq_path = Path(args.sequence)
    if not seq_path.is_file():
        print(f"ERROR: sequence not found: {seq_path}", file=sys.stderr)
        return 2
    gt_map = None
    if args.identity_annotations:
        ann_path = Path(args.identity_annotations)
        if not ann_path.is_file():
            print(f"ERROR: identity annotations not found: {ann_path}", file=sys.stderr)
            return 2
        try:
            gt_map = load_identity_annotations_file(str(ann_path))
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: bad identity annotations: {exc}", file=sys.stderr)
            return 1
    try:
        raw = json.loads(seq_path.read_text(encoding="utf-8"))
        frames = load_track_sequence(raw)
        payload = run_tracker_on_frames(
            frames,
            match_iou=float(args.match_iou),
            confirm_hits=int(args.confirm_hits),
            lost_timeout_sec=float(args.lost_timeout_sec),
            gt_id_by_frame_det=gt_map,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: offline track failed: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    if args.out_csv:
        _write_tracks_csv(args.out_csv, list(payload.get("rows", [])))

    metrics = payload.get("metrics", {})
    metrics_text = json.dumps(metrics, indent=2, sort_keys=True)
    if args.out_metrics:
        mpath = Path(args.out_metrics)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        mpath.write_text(metrics_text + "\n", encoding="utf-8")
    elif not args.out_json:
        print(metrics_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
