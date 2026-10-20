"""离线重定位统计回归，不依赖 ROS 或实际运动。"""

import csv
from pathlib import Path
import sys

import pytest


SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from relocalization_evaluator import (
    RelocalizationEvent,
    compute_metrics,
    read_csv,
)


def event(attempt_id, outcome, duration=None, reason=None):
    return RelocalizationEvent(
        timestamp=float(attempt_id),
        attempt_id=attempt_id,
        outcome=outcome,
        time_to_recovery=duration,
        failure_reason=reason,
    )


def test_empty_events_do_not_claim_recovery():
    assert compute_metrics([]) is None


def test_manual_and_failed_attempts_are_not_autonomous_success():
    metrics = compute_metrics([
        event(1, "RECOVERED", 2.0),
        event(2, "FAILED", 100.0, "定位无效"),
        event(3, "MANUAL_REQUIRED", 80.0, "定位无效"),
        event(4, "RECOVERED"),
    ])

    assert metrics.total_attempts == 4
    assert (metrics.successes, metrics.failures, metrics.manual_required) == (2, 1, 1)
    assert metrics.success_rate == pytest.approx(0.5)
    assert metrics.mean_time_to_recovery == pytest.approx(2.0)
    assert metrics.median_time_to_recovery == pytest.approx(2.0)
    assert metrics.failure_reasons == {"定位无效": 2}


def test_no_successful_duration_stays_unknown_instead_of_zero():
    metrics = compute_metrics([
        event(1, "RECOVERED"),
        event(2, "FAILED", 5.0),
    ])

    assert metrics.mean_time_to_recovery is None
    assert metrics.median_time_to_recovery is None
    assert metrics.failure_reasons == {}


def test_even_sample_median_preserves_existing_upper_middle_convention():
    metrics = compute_metrics([
        event(1, "RECOVERED", 8.0),
        event(2, "RECOVERED", 2.0),
    ])

    assert metrics.mean_time_to_recovery == pytest.approx(5.0)
    assert metrics.median_time_to_recovery == pytest.approx(8.0)


def test_csv_skips_invalid_rows_and_preserves_optional_fields(tmp_path, capsys):
    path = tmp_path / "relocalization.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "timestamp", "attempt_id", "outcome",
            "time_to_recovery", "failure_reason",
        ])
        writer.writerow([1, 1, " RECOVERED ", "2.5", "None"])
        writer.writerow([2, 2, "MANUAL_REQUIRED", "", "operator"])
        writer.writerow([3, 3, "UNKNOWN", "", ""])
        writer.writerow([4, "invalid", "FAILED", "", ""])
        writer.writerow([5, 5, "FAILED", "None", "None"])

    events = read_csv(str(path))

    assert [entry.outcome for entry in events] == [
        "RECOVERED", "MANUAL_REQUIRED", "FAILED",
    ]
    assert events[0].time_to_recovery == pytest.approx(2.5)
    assert events[0].failure_reason is None
    assert events[1].time_to_recovery is None
    assert events[2].time_to_recovery is None
    assert events[2].failure_reason is None
    assert capsys.readouterr().err
