#!/usr/bin/env python3
"""Plan or collect read-only navigation topic discovery evidence."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


CONTRACTS = (
    ("/scan", "sensor_msgs/msg/LaserScan"),
    ("/odom", "nav_msgs/msg/Odometry"),
    ("/amcl_pose", "geometry_msgs/msg/PoseWithCovarianceStamped"),
    ("/dg/lidar/quality", "diagnostic_msgs/msg/DiagnosticArray"),
    ("/dg/gnss/quality", "diagnostic_msgs/msg/DiagnosticArray"),
    ("/dg/relocalization/match_quality", "diagnostic_msgs/msg/DiagnosticArray"),
)


def bounded_timeout(value):
    seconds = float(value)
    if not math.isfinite(seconds) or not 0 < seconds <= 60:
        raise argparse.ArgumentTypeError("timeout must be finite and within (0, 60]")
    return seconds


def as_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def inspect_topic(ros2_path, topic, expected_type, timeout, environment):
    command = [ros2_path, "topic", "info", topic, "--verbose"]
    observation = {
        "topic": topic, "expected_type": expected_type, "command": command,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "NOT_OBSERVED",
    }
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, env=environment, check=False,
        )
    except subprocess.TimeoutExpired as error:
        observation.update(
            status="TIMEOUT", stdout=as_text(error.stdout),
            stderr=as_text(error.stderr), returncode=None,
        )
        return observation
    except OSError as error:
        observation.update(status="COMMAND_ERROR", stderr=str(error), returncode=None)
        return observation
    observation.update(stdout=result.stdout, stderr=result.stderr, returncode=result.returncode)
    if result.returncode != 0:
        observation["status"] = "COMMAND_ERROR"
        return observation
    type_match = re.search(r"^Type:\s*(\S+)\s*$", result.stdout, re.MULTILINE)
    publishers = re.search(r"^Publisher count:\s*(\d+)\s*$", result.stdout, re.MULTILINE)
    subscribers = re.search(r"^Subscription count:\s*(\d+)\s*$", result.stdout, re.MULTILINE)
    if not all((type_match, publishers, subscribers)):
        observation["status"] = "UNPARSED"
        return observation
    observation.update(
        observed_type=type_match.group(1),
        publisher_count=int(publishers.group(1)),
        subscription_count=int(subscribers.group(1)),
    )
    if observation["observed_type"] != expected_type:
        observation["status"] = "TYPE_MISMATCH"
    elif observation["publisher_count"] == 0:
        observation["status"] = "NO_PUBLISHER"
    elif observation["subscription_count"] == 0:
        observation["status"] = "NO_SUBSCRIBER"
    else:
        observation["status"] = "DISCOVERY_MATCH"
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="print plan only (default)")
    mode.add_argument("--capture", action="store_true", help="query an already running ROS graph")
    parser.add_argument("--timeout", type=bounded_timeout, default=5.0)
    parser.add_argument("--output", type=Path, help="new JSON file; never overwrite existing files")
    arguments = parser.parse_args()
    output_handle = None
    if arguments.output is not None:
        try:
            output_handle = arguments.output.open("x", encoding="utf-8", newline="\n")
        except OSError as error:
            parser.error(str(error))
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "mode": "CAPTURE" if arguments.capture else "PLAN",
        "scope": "TOPIC_DISCOVERY_ONLY",
        "hardware_acceptance": "NOT_PROVEN",
        "qos_compatibility": "NOT_EVALUATED",
        "message_freshness": "NOT_EVALUATED",
        "frame_and_timestamp": "NOT_EVALUATED",
        "motion_commands_sent": False,
        "environment": {
            name: os.environ.get(name)
            for name in ("ROS_DISTRO", "ROS_DOMAIN_ID", "ROS_LOCALHOST_ONLY", "RMW_IMPLEMENTATION")
        },
        "contracts": [
            {"topic": topic, "expected_type": expected_type,
             "command": ["ros2", "topic", "info", topic, "--verbose"]}
            for topic, expected_type in CONTRACTS
        ],
        "observations": [],
    }
    exit_code = 0
    if not arguments.capture:
        report["result"] = "PLAN_ONLY"
    else:
        ros2_path = shutil.which("ros2")
        if ros2_path is None:
            report["result"] = "ROS2_UNAVAILABLE"
            exit_code = 2
        else:
            environment = dict(os.environ, LANG="C", LC_ALL="C")
            report["observations"] = [
                inspect_topic(ros2_path, topic, expected_type, arguments.timeout, environment)
                for topic, expected_type in CONTRACTS
            ]
            matched = all(
                item["status"] == "DISCOVERY_MATCH" for item in report["observations"]
            )
            report["result"] = "DISCOVERY_MATCH_ONLY" if matched else "CONTRACT_GAP"
            exit_code = 0 if matched else 1
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if output_handle is not None:
        with output_handle:
            output_handle.write(serialized)
    else:
        sys.stdout.write(serialized)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
