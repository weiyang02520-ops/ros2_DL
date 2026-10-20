#!/usr/bin/env python3
"""Run bounded offline regression checks without ROS, network or hardware access."""

from pathlib import Path
import subprocess
import sys


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    test_paths = [
        "src/ylhb_base/test/test_feature_repeatability_evaluator.py",
        "src/ylhb_base/test/test_teacher_requirements_evaluator.py",
    ]
    command = [sys.executable, "-m", "pytest", "-q", *test_paths]
    try:
        return subprocess.run(command, cwd=repo_root, check=False).returncode
    except OSError as error:
        print(f"Cannot run offline checks: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
