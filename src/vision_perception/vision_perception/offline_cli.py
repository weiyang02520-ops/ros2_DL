"""Offline bottle/cup detection CLI for local images.

Does not start cameras, ROS publishers, or robot control. Plain image files
produce JSON/CSV evaluation output with source_image_id; they are not claimed
to be LIVE_CAMERA ROS observations.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List, Sequence


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "V1 offline 2D detection for bottle/cup images. "
            "Requires a local ONNX model and model_manifest.json; never downloads weights."
        )
    )
    parser.add_argument(
        "--images",
        nargs="+",
        required=True,
        help="Image paths (.jpg/.png via OpenCV, or HxWx3 .npy)",
    )
    parser.add_argument("--model", required=True, help="Local YOLO11n-seg ONNX path")
    parser.add_argument(
        "--manifest",
        required=True,
        help="model_manifest.json with SHA256, layout and COCO class_map",
    )
    parser.add_argument("--out-json", default="", help="Optional JSON results path")
    parser.add_argument("--out-csv", default="", help="Optional detections.csv path")
    parser.add_argument(
        "--eval-annotations",
        default="",
        help="Optional V1 bbox annotations JSON for offline precision/recall metrics",
    )
    parser.add_argument(
        "--out-metrics",
        default="",
        help="Optional metrics.json path (requires --eval-annotations)",
    )
    parser.add_argument(
        "--eval-iou",
        type=float,
        default=0.5,
        help="IoU threshold for V1 matching (plan default 0.5)",
    )
    parser.add_argument("--confidence", type=float, default=0.35)
    parser.add_argument("--nms-iou", type=float, default=0.45)
    parser.add_argument("--max-detections", type=int, default=20)
    parser.add_argument("--ort-threads", type=int, default=2)
    return parser.parse_args(argv)


def _write_csv(path: str, batches: List[dict]) -> None:
    fieldnames = [
        "source_session_id",
        "observation_id",
        "detection_index",
        "source_image_id",
        "class_name",
        "confidence",
        "center_x",
        "center_y",
        "size_x",
        "size_y",
    ]
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for batch in batches:
            if not batch["detections"]:
                writer.writerow(
                    {
                        "source_session_id": batch["source_session_id"],
                        "observation_id": batch["observation_id"],
                        "detection_index": "",
                        "source_image_id": batch.get("source_image_id", ""),
                        "class_name": "",
                        "confidence": "",
                        "center_x": "",
                        "center_y": "",
                        "size_x": "",
                        "size_y": "",
                    }
                )
                continue
            for det in batch["detections"]:
                bbox = det["bbox"]
                writer.writerow(
                    {
                        "source_session_id": batch["source_session_id"],
                        "observation_id": batch["observation_id"],
                        "detection_index": det["detection_index"],
                        "source_image_id": batch.get("source_image_id", ""),
                        "class_name": det["class_name"],
                        "confidence": det["confidence"],
                        "center_x": bbox["center_x"],
                        "center_y": bbox["center_y"],
                        "size_x": bbox["size_x"],
                        "size_y": bbox["size_y"],
                    }
                )


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    # Import here so --help works even when optional deps are missing.
    from vision_perception.pipeline import run_offline_on_paths

    missing = [path for path in args.images if not Path(path).is_file()]
    if missing:
        print(f"ERROR: missing image files: {missing}", file=sys.stderr)
        return 2
    if not Path(args.model).is_file():
        print(f"ERROR: model not found: {args.model}", file=sys.stderr)
        return 2
    if not Path(args.manifest).is_file():
        print(f"ERROR: manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    try:
        batches = run_offline_on_paths(
            args.images,
            model_path=args.model,
            manifest_path=args.manifest,
            confidence_threshold=args.confidence,
            nms_iou_threshold=args.nms_iou,
            max_detections=args.max_detections,
            ort_threads=args.ort_threads,
        )
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"ERROR: offline detection failed: {exc}", file=sys.stderr)
        return 1

    payload = {
        "stage": "V1_OFFLINE",
        "camera_contract": "NOT_RUN",
        "arm_ready": "NO",
        "source_kind_note": (
            "OFFLINE_FILE results are file evaluation outputs, "
            "not LIVE_CAMERA ROS observations"
        ),
        "batches": batches,
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if args.out_csv:
        _write_csv(args.out_csv, batches)

    if args.out_metrics and not args.eval_annotations:
        print("ERROR: --out-metrics requires --eval-annotations", file=sys.stderr)
        return 2
    if args.eval_annotations:
        from vision_perception.evaluation import evaluate_offline_payload

        if not Path(args.eval_annotations).is_file():
            print(
                f"ERROR: annotations not found: {args.eval_annotations}",
                file=sys.stderr,
            )
            return 2
        try:
            metrics = evaluate_offline_payload(
                payload,
                args.eval_annotations,
                iou_threshold=float(args.eval_iou),
            )
        except Exception as exc:  # noqa: BLE001 - CLI boundary
            print(f"ERROR: evaluation failed: {exc}", file=sys.stderr)
            return 1
        metrics_text = json.dumps(metrics, indent=2, sort_keys=True)
        if args.out_metrics:
            mpath = Path(args.out_metrics)
            mpath.parent.mkdir(parents=True, exist_ok=True)
            mpath.write_text(metrics_text + "\n", encoding="utf-8")
        else:
            print(metrics_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
