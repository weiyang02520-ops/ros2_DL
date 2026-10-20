"""CLI: offline RGB + depth → VisionObject-shaped JSON/CSV (V2 scaffolding).

Requires local ONNX + manifest. Never downloads weights. No ROS / ZED / arm.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "V2 offline objects: local RGB + depth .npy + synthetic pinhole. "
            "Does not claim LIVE_CAMERA or V2_ACCURACY PASS."
        )
    )
    parser.add_argument("--images", nargs="+", required=True, help="RGB paths")
    parser.add_argument(
        "--depths",
        nargs="+",
        required=True,
        help="Depth .npy paths (HxW float metres), same order as --images",
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-csv", default="", help="objects.csv")
    parser.add_argument(
        "--out-metrics",
        default="",
        help="Coverage metrics JSON (result=NOT_RUN / v2_accuracy=BLOCKED)",
    )
    parser.add_argument("--fx", type=float, default=500.0)
    parser.add_argument("--fy", type=float, default=500.0)
    parser.add_argument("--cx", type=float, default=-1.0, help="-1 → width/2")
    parser.add_argument("--cy", type=float, default=-1.0, help="-1 → height/2")
    parser.add_argument("--min-depth-m", type=float, default=0.5)
    parser.add_argument("--max-depth-m", type=float, default=1.5)
    parser.add_argument("--confidence", type=float, default=0.35)
    parser.add_argument("--nms-iou", type=float, default=0.45)
    parser.add_argument("--max-detections", type=int, default=20)
    parser.add_argument("--ort-threads", type=int, default=2)
    parser.add_argument("--mask-threshold", type=float, default=0.5)
    parser.add_argument(
        "--enable-tracking",
        action="store_true",
        help="Run MultiObjectTracker across the file sequence (fills object_id).",
    )
    parser.add_argument("--match-iou", type=float, default=0.30)
    parser.add_argument("--confirm-hits", type=int, default=3)
    parser.add_argument("--lost-timeout-sec", type=float, default=0.70)
    return parser.parse_args(argv)


def _nan_blank(value: float) -> str:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    return str(value)


def _write_objects_csv(path: str, entries: List[Dict[str, Any]]) -> None:
    fieldnames = [
        "source_session_id",
        "observation_id",
        "detection_index",
        "source_image_id",
        "class_name",
        "confidence",
        "position_valid",
        "invalid_reason",
        "position_x",
        "position_y",
        "position_z",
        "reference_u",
        "reference_v",
        "valid_depth_fraction",
        "mask_source",
        "orientation_valid",
        "tracking_valid",
        "object_id",
        "tracking_session_id",
        "pair_reason",
    ]
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            objects = entry["objects"]
            dets = entry["detections"]
            source_image_id = entry.get("source_image_id", "")
            objs = objects.get("objects", [])
            if not objs:
                writer.writerow(
                    {
                        "source_session_id": objects.get("source_session_id", ""),
                        "observation_id": objects.get("observation_id", ""),
                        "detection_index": "",
                        "source_image_id": source_image_id,
                        "class_name": "",
                        "confidence": "",
                        "position_valid": "",
                        "invalid_reason": "",
                        "position_x": "",
                        "position_y": "",
                        "position_z": "",
                        "reference_u": "",
                        "reference_v": "",
                        "valid_depth_fraction": "",
                        "mask_source": objects.get("mask_source", ""),
                        "orientation_valid": "false",
                        "tracking_valid": "false",
                        "object_id": "",
                        "tracking_session_id": objects.get("tracking_session_id", ""),
                        "pair_reason": objects.get("pair_reason", ""),
                    }
                )
                continue
            for obj in objs:
                pos = obj.get("position", {})
                writer.writerow(
                    {
                        "source_session_id": objects.get("source_session_id", ""),
                        "observation_id": objects.get("observation_id", ""),
                        "detection_index": obj.get("detection_index", ""),
                        "source_image_id": source_image_id,
                        "class_name": obj.get("class_name", ""),
                        "confidence": obj.get("confidence", ""),
                        "position_valid": obj.get("position_valid", False),
                        "invalid_reason": obj.get("invalid_reason", ""),
                        "position_x": _nan_blank(float(pos.get("x", float("nan")))),
                        "position_y": _nan_blank(float(pos.get("y", float("nan")))),
                        "position_z": _nan_blank(float(pos.get("z", float("nan")))),
                        "reference_u": _nan_blank(float(obj.get("reference_u", float("nan")))),
                        "reference_v": _nan_blank(float(obj.get("reference_v", float("nan")))),
                        "valid_depth_fraction": obj.get("valid_depth_fraction", ""),
                        "mask_source": obj.get("mask_source", ""),
                        "orientation_valid": False,
                        "tracking_valid": bool(obj.get("tracking_valid", False)),
                        "object_id": obj.get("object_id", ""),
                        "tracking_session_id": objects.get("tracking_session_id", ""),
                        "pair_reason": objects.get("pair_reason", ""),
                    }
                )
            _ = dets  # reserved for future joint CSV columns


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    from vision_perception.offline_objects import (
        run_offline_objects_on_paths,
        summarize_object_batches,
    )

    for path in list(args.images) + list(args.depths):
        if not Path(path).is_file():
            print(f"ERROR: missing file: {path}", file=sys.stderr)
            return 2
    if not Path(args.model).is_file():
        print(f"ERROR: model not found: {args.model}", file=sys.stderr)
        return 2
    if not Path(args.manifest).is_file():
        print(f"ERROR: manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    cx = None if args.cx < 0 else float(args.cx)
    cy = None if args.cy < 0 else float(args.cy)
    try:
        entries = run_offline_objects_on_paths(
            args.images,
            args.depths,
            model_path=args.model,
            manifest_path=args.manifest,
            fx=float(args.fx),
            fy=float(args.fy),
            cx=cx,
            cy=cy,
            min_depth_m=float(args.min_depth_m),
            max_depth_m=float(args.max_depth_m),
            confidence_threshold=float(args.confidence),
            nms_iou_threshold=float(args.nms_iou),
            max_detections=int(args.max_detections),
            ort_threads=int(args.ort_threads),
            mask_threshold=float(args.mask_threshold),
            enable_tracking=bool(args.enable_tracking),
            tracker_match_iou=float(args.match_iou),
            tracker_confirm_hits=int(args.confirm_hits),
            tracker_lost_timeout_sec=float(args.lost_timeout_sec),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: offline objects failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "stage": "V2_POSITION_OFFLINE",
        "camera_contract": "NOT_RUN",
        "arm_ready": "NO",
        "orientation_valid_policy": "always_false",
        "source_kind_note": (
            "OFFLINE_FILE + synthetic/fake depth; not LIVE_CAMERA / not ZED PASS"
        ),
        "entries": entries,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if args.out_csv:
        _write_objects_csv(args.out_csv, entries)

    coverage = summarize_object_batches(entries)
    metrics_text = json.dumps(coverage, indent=2, sort_keys=True)
    if args.out_metrics:
        mpath = Path(args.out_metrics)
        mpath.parent.mkdir(parents=True, exist_ok=True)
        mpath.write_text(metrics_text + "\n", encoding="utf-8")
    elif not args.out_json:
        print(metrics_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
