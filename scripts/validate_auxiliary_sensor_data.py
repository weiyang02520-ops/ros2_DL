#!/usr/bin/env python3
"""Validate measured event-camera or normalized mmWave data before ROS replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_DIR = REPOSITORY_ROOT / "src" / "ylhb_base" / "scripts"
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from auxiliary_sensor_data import (  # noqa: E402
    iter_event_packets,
    iter_mmwave_frames,
    summarize_event_packet,
    summarize_mmwave_frame,
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Validate auxiliary sensor measured data")
    result.add_argument("kind", choices=("event_camera", "mmwave"))
    result.add_argument("input_file")
    result.add_argument("--output")
    result.add_argument("--event-window-us", type=int, default=20_000)
    result.add_argument("--moving-speed-threshold", type=float, default=0.15)
    return result


def validate_event(path: Path, window_us: int) -> dict[str, object]:
    packets = 0
    events = 0
    positives = 0
    first_timestamp: int | None = None
    last_timestamp: int | None = None
    for packet in iter_event_packets(path, window_us=window_us):
        summary = summarize_event_packet(packet)
        packets += 1
        events += int(summary["event_count"])
        positives += sum(sample.polarity for sample in packet.samples)
        if packet.samples:
            first_timestamp = (
                packet.samples[0].timestamp_us if first_timestamp is None else first_timestamp
            )
            last_timestamp = packet.samples[-1].timestamp_us
    return {
        "packet_count": packets,
        "event_count": events,
        "first_timestamp_us": first_timestamp,
        "last_timestamp_us": last_timestamp,
        "duration_sec": (
            (last_timestamp - first_timestamp) / 1_000_000.0
            if first_timestamp is not None and last_timestamp is not None
            else 0.0
        ),
        "positive_fraction": positives / events if events else 0.0,
        "event_window_us": window_us,
    }


def validate_mmwave(path: Path, moving_speed_threshold: float) -> dict[str, object]:
    frames = 0
    detections = 0
    moving = 0
    tracks: set[int] = set()
    first_timestamp: int | None = None
    last_timestamp: int | None = None
    for frame in iter_mmwave_frames(path):
        summary = summarize_mmwave_frame(
            frame, moving_speed_threshold=moving_speed_threshold
        )
        frames += 1
        detections += int(summary["detection_count"])
        moving += int(summary["moving_detection_count"])
        tracks.update(item.track_id for item in frame.detections)
        first_timestamp = frame.timestamp_us if first_timestamp is None else first_timestamp
        last_timestamp = frame.timestamp_us
    return {
        "frame_count": frames,
        "detection_count": detections,
        "moving_detection_count": moving,
        "unique_track_count": len(tracks),
        "first_timestamp_us": first_timestamp,
        "last_timestamp_us": last_timestamp,
        "duration_sec": (
            (last_timestamp - first_timestamp) / 1_000_000.0
            if first_timestamp is not None and last_timestamp is not None
            else 0.0
        ),
        "moving_speed_threshold": moving_speed_threshold,
    }


def main() -> int:
    arguments = parser().parse_args()
    path = Path(arguments.input_file).expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"input file does not exist: {path}")
    try:
        if arguments.kind == "event_camera":
            metrics = validate_event(path, arguments.event_window_us)
            count = int(metrics["event_count"])
            schema = "SHIMETA_EVT2_CSV"
        else:
            metrics = validate_mmwave(path, arguments.moving_speed_threshold)
            count = int(metrics["detection_count"])
            schema = "DG_MMWAVE_NORMALIZED_CSV_V1"
    except (OSError, ValueError) as exc:
        raise SystemExit(f"validation failed: {exc}") from exc
    report = {
        "schema_version": 1,
        "validation": "PASS" if count > 0 else "EMPTY",
        "sensor_kind": arguments.kind,
        "input_file": str(path),
        "input_size_bytes": path.stat().st_size,
        "input_sha256": file_sha256(path),
        "input_schema": schema,
        "metrics": metrics,
        "hardware_runtime_verified": False,
        "navigation_effect": "OBSERVATION_ONLY",
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(encoded, end="")
    if arguments.output:
        output = Path(arguments.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    return 0 if count > 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
