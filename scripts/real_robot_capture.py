#!/usr/bin/env python3
"""Capture traceable DG-202611 real-robot evidence without commanding motion."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Iterable, Sequence


DEFAULT_TOPICS = (
    "/scan",
    "/odom",
    "/odometry/filtered",
    "/amcl_pose",
    "/map",
    "/tf",
    "/tf_static",
    "/cmd_vel",
    "/zlac8015d/status",
    "/dg/lidar/quality",
    "/dg/gnss/quality",
    "/dg/uwb/pose",
    "/dg/uwb/quality",
    "/dg/fusion/odom",
    "/dg/fusion/pose",
    "/dg/fusion/status",
    "/dg/navigation/status",
    "/dg/relocalization/seed",
    "/dg/relocalization/match_quality",
    "/dg/relocalization/status",
    "/cmd_vel_recovery",
    "/cmd_vel_nav",
    "/dg/test_cmd_vel",
)


SNAPSHOT_COMMANDS = {
    "hostname.txt": ("hostname",),
    "uname.txt": ("uname", "-a"),
    "ip_addr.txt": ("ip", "-4", "-br", "addr"),
    "ros_nodes.txt": ("ros2", "node", "list"),
    "ros_topics.txt": ("ros2", "topic", "list", "-t"),
    "ros_services.txt": ("ros2", "service", "list", "-t"),
    "ros_actions.txt": ("ros2", "action", "list", "-t"),
    "tf_static_once.txt": ("ros2", "topic", "echo", "/tf_static", "--once"),
    "can1.txt": ("ip", "-details", "-statistics", "link", "show", "can1"),
    "mobile_bridge_service.txt": (
        "systemctl",
        "status",
        "ylhb-mobile-bridge.service",
        "--no-pager",
    ),
}

PARAMETER_NODES = (
    "/zlac8015d_canopen_controller",
    "/ekf_filter_node",
    "/mobile_bridge",
    "/dg_lidar_robust_node",
    "/dg_multisource_fusion_node",
    "/dg_active_relocalization_node",
    "/dg_navigation_health_node",
    "/dg_uwb_replay_node",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_label(value: str) -> str:
    label = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    label = label.strip("._-")
    if not label:
        raise ValueError("scenario must contain at least one safe filename character")
    return label[:80]


def unique_topics(values: Iterable[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        topic = str(value).strip()
        if not topic or not topic.startswith("/"):
            raise ValueError(f"invalid absolute ROS topic: {value!r}")
        if topic not in seen:
            seen.add(topic)
            ordered.append(topic)
    return tuple(ordered)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def git_snapshot(repository: Path) -> dict[str, object]:
    def git(*arguments: str) -> str | None:
        try:
            return subprocess.check_output(
                ("git", *arguments), cwd=repository, stderr=subprocess.DEVNULL, text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = git("status", "--porcelain=v1")
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "status_porcelain": status,
        "clean": status == "" if status is not None else None,
    }


def run_snapshot(command: Sequence[str], destination: Path, timeout: float = 15.0) -> int:
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        destination.write_text(completed.stdout or "", encoding="utf-8")
        return int(completed.returncode)
    except (OSError, subprocess.TimeoutExpired) as error:
        destination.write_text(f"SNAPSHOT_FAILED: {type(error).__name__}: {error}\n", encoding="utf-8")
        return 124 if isinstance(error, subprocess.TimeoutExpired) else 127


def read_proc_sample(previous_cpu: tuple[int, int] | None) -> tuple[dict[str, object], tuple[int, int] | None]:
    sample: dict[str, object] = {
        "utc": utc_now(),
        "monotonic_sec": time.monotonic(),
        "load1": None,
        "load5": None,
        "load15": None,
        "cpu_percent": None,
        "memory_total_kib": None,
        "memory_available_kib": None,
        "thermal_max_c": None,
    }
    try:
        sample["load1"], sample["load5"], sample["load15"] = os.getloadavg()
    except (AttributeError, OSError):
        pass

    current_cpu: tuple[int, int] | None = None
    try:
        fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()[1:]
        counters = [int(value) for value in fields]
        total = sum(counters)
        idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
        current_cpu = (total, idle)
        if previous_cpu is not None:
            total_delta = total - previous_cpu[0]
            idle_delta = idle - previous_cpu[1]
            if total_delta > 0:
                sample["cpu_percent"] = 100.0 * (1.0 - idle_delta / total_delta)
    except (OSError, ValueError, IndexError):
        pass

    try:
        meminfo: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, value = line.split(":", 1)
            meminfo[key] = int(value.strip().split()[0])
        sample["memory_total_kib"] = meminfo.get("MemTotal")
        sample["memory_available_kib"] = meminfo.get("MemAvailable")
    except (OSError, ValueError, IndexError):
        pass

    temperatures: list[float] = []
    for sensor in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            value = float(sensor.read_text(encoding="ascii").strip())
            temperatures.append(value / 1000.0 if value > 200.0 else value)
        except (OSError, ValueError):
            continue
    if temperatures:
        sample["thermal_max_c"] = max(temperatures)
    return sample, current_cpu


def terminate_process(process: subprocess.Popen[str] | None, timeout: float = 15.0) -> int | None:
    if process is None:
        return None
    if process.poll() is not None:
        return process.returncode
    try:
        os.killpg(process.pid, signal.SIGINT)
    except (AttributeError, OSError):
        process.send_signal(signal.SIGINT)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            return process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            process.kill()
            return process.wait(timeout=5.0)


def build_manifest(session: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(session.rglob("*")):
        if not path.is_file() or path.name in {"manifest.json", "manifest.sha256"}:
            continue
        entries.append(
            {
                "path": path.relative_to(session).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return entries


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record DG-202611 real-robot evidence. This tool never publishes commands."
    )
    parser.add_argument("--scenario", required=True, help="Frozen scenario or trial identifier")
    parser.add_argument("--duration", type=float, default=120.0, help="Seconds; 0 records until Ctrl-C")
    parser.add_argument("--output-root", default="results/real_robot")
    parser.add_argument("--operator", default=os.environ.get("USER", "unknown"))
    parser.add_argument("--hardware-notes", default="")
    parser.add_argument("--sample-period", type=float, default=1.0)
    parser.add_argument("--topic", action="append", default=[], help="Additional absolute ROS topic")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = create_parser().parse_args(argv)
    if arguments.duration < 0.0:
        raise SystemExit("--duration must be non-negative")
    if arguments.sample_period <= 0.0:
        raise SystemExit("--sample-period must be positive")
    if shutil.which("ros2") is None:
        print("ERROR: ros2 is unavailable; source the ROS 2 and integration workspaces first.", file=sys.stderr)
        return 2

    scenario = sanitize_label(arguments.scenario)
    topics = unique_topics((*DEFAULT_TOPICS, *arguments.topic))
    repository = Path(arguments.repo).expanduser().resolve()
    output_root = Path(arguments.output_root).expanduser().resolve()
    session = output_root / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{scenario}"
    logs = session / "logs"
    snapshots = session / "snapshots"
    logs.mkdir(parents=True, exist_ok=False)
    snapshots.mkdir(parents=True)

    created_utc = utc_now()
    metadata = {
        "schema_version": 1,
        "run_class": "REAL_ROBOT_CAPTURE",
        "evaluation_status": "NOT_EVALUATED",
        "experiment_id": session.name,
        "scenario": scenario,
        "operator": arguments.operator,
        "hardware_notes": arguments.hardware_notes,
        "created_utc": created_utc,
        "started_utc": None,
        "requested_duration_sec": arguments.duration,
        "sample_period_sec": arguments.sample_period,
        "hostname": platform.node(),
        "platform": platform.platform(),
        "ros_distro": os.environ.get("ROS_DISTRO"),
        "ros_domain_id": os.environ.get("ROS_DOMAIN_ID"),
        "rmw_implementation": os.environ.get("RMW_IMPLEMENTATION"),
        "repository": str(repository),
        "git": git_snapshot(repository),
        "topics": list(topics),
        "safety": {
            "publishes_motion_commands": False,
            "requires_human_supervision_for_motion": True,
            "motion_is_operator_controlled": True,
        },
    }
    write_json(session / "metadata.json", metadata)

    snapshot_results: dict[str, int] = {}
    for filename, command in SNAPSHOT_COMMANDS.items():
        snapshot_results[filename] = run_snapshot(command, snapshots / filename)
    parameter_dir = snapshots / "parameters"
    parameter_dir.mkdir()
    for node in PARAMETER_NODES:
        filename = f"{node.strip('/').replace('/', '_')}.yaml"
        snapshot_results[f"parameters/{filename}"] = run_snapshot(
            ("ros2", "param", "dump", node), parameter_dir / filename, timeout=10.0
        )

    bag_path = session / "rosbag"
    bag_log_handle = (logs / "rosbag.log").open("w", encoding="utf-8")
    recorder = subprocess.Popen(
        ("ros2", "bag", "record", "-o", str(bag_path), *topics),
        stdout=bag_log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )

    tegrastats_process: subprocess.Popen[str] | None = None
    tegrastats_log_handle = None
    if shutil.which("tegrastats") is not None:
        tegrastats_log_handle = (logs / "tegrastats.log").open("w", encoding="utf-8")
        tegrastats_process = subprocess.Popen(
            ("tegrastats", "--interval", str(max(100, int(arguments.sample_period * 1000)))),
            stdout=tegrastats_log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )

    resource_path = session / "resource_samples.csv"
    interrupted = False
    capture_error: str | None = None
    capture_ready = False
    previous_cpu: tuple[int, int] | None = None
    started_utc: str | None = None
    started_monotonic: float | None = None
    try:
        time.sleep(1.0)
        if recorder.poll() is not None:
            raise RuntimeError(f"ros2 bag recorder exited early with code {recorder.returncode}")
        started_utc = utc_now()
        started_monotonic = time.monotonic()
        metadata["started_utc"] = started_utc
        write_json(session / "metadata.json", metadata)
        capture_ready = True
        print(f"CAPTURE_READY: {session}", flush=True)
        with resource_path.open("w", newline="", encoding="utf-8") as resource_handle:
            writer: csv.DictWriter[str] | None = None
            while arguments.duration == 0.0 or time.monotonic() - started_monotonic < arguments.duration:
                sample, previous_cpu = read_proc_sample(previous_cpu)
                sample["elapsed_sec"] = time.monotonic() - started_monotonic
                if writer is None:
                    writer = csv.DictWriter(resource_handle, fieldnames=list(sample))
                    writer.writeheader()
                writer.writerow(sample)
                resource_handle.flush()
                if recorder.poll() is not None:
                    raise RuntimeError(f"ros2 bag recorder stopped with code {recorder.returncode}")
                time.sleep(arguments.sample_period)
    except KeyboardInterrupt:
        interrupted = True
    except Exception as error:  # Preserve the evidence directory on any runtime failure.
        capture_error = f"{type(error).__name__}: {error}"
    finally:
        recorder_code = terminate_process(recorder)
        tegrastats_code = terminate_process(tegrastats_process)
        bag_log_handle.close()
        if tegrastats_log_handle is not None:
            tegrastats_log_handle.close()

    ended_utc = utc_now()
    actual_duration = time.monotonic() - started_monotonic if started_monotonic is not None else 0.0
    snapshot_results["ros_nodes_after.txt"] = run_snapshot(
        ("ros2", "node", "list"), snapshots / "ros_nodes_after.txt"
    )
    snapshot_results["ros_topics_after.txt"] = run_snapshot(
        ("ros2", "topic", "list", "-t"), snapshots / "ros_topics_after.txt"
    )

    bag_metadata = bag_path / "metadata.yaml"
    result = {
        "schema_version": 1,
        "run_class": "REAL_ROBOT_CAPTURE",
        "evaluation_status": "NOT_EVALUATED",
        "capture_status": (
            "COMPLETE" if capture_ready and capture_error is None and bag_metadata.is_file() else "FAILED"
        ),
        "capture_ready": capture_ready,
        "experiment_id": session.name,
        "started_utc": started_utc,
        "ended_utc": ended_utc,
        "actual_duration_sec": actual_duration,
        "interrupted_by_operator": interrupted,
        "rosbag_return_code": recorder_code,
        "tegrastats_return_code": tegrastats_code,
        "rosbag_path": str(bag_path),
        "rosbag_present": bag_path.exists(),
        "rosbag_metadata_present": bag_metadata.is_file(),
        "snapshot_return_codes": snapshot_results,
        "error": capture_error,
        "claim_boundary": "Capture completion is not a performance result; evaluation is required.",
    }
    write_json(session / "result.json", result)
    entries = build_manifest(session)
    write_json(session / "manifest.json", {"files": entries})
    (session / "manifest.sha256").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in entries), encoding="ascii"
    )

    print(session)
    if result["capture_status"] != "COMPLETE":
        print(f"ERROR: capture failed: {capture_error or 'rosbag metadata is missing'}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
