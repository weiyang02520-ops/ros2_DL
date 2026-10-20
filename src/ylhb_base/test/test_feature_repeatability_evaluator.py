from pathlib import Path
import csv
import json
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from feature_repeatability_evaluator import (  # noqa: E402
    FrameFeatures,
    compute_frame_pair_repeatability,
    compute_metrics,
    main,
)


def frame(
    frame_id: int,
    points: list[tuple[float, float]],
    coordinate_frame: str = "laser",
) -> FrameFeatures:
    return FrameFeatures(
        frame_id=frame_id,
        timestamp=float(frame_id),
        feature_ids=[],
        valid_feature_count=len(points),
        feature_points=points,
        coordinate_frame=coordinate_frame,
    )


def test_spatial_matching_is_one_to_one_and_symmetric():
    first = frame(1, [(0.0, 0.0), (0.05, 0.0)])
    second = frame(2, [(0.02, 0.0)])

    assert compute_frame_pair_repeatability(first, second, 0.12) == pytest.approx(2.0 / 3.0)
    assert compute_frame_pair_repeatability(second, first, 0.12) == pytest.approx(2.0 / 3.0)


def test_zero_feature_pair_is_reported_and_never_counted_as_perfect():
    metrics = compute_metrics(
        [
            frame(1, []),
            frame(2, [(0.0, 0.0)]),
            frame(3, [(0.01, 0.0)]),
        ],
        0.12,
    )

    assert metrics is not None
    assert metrics.zero_feature_pair_count == 1
    assert metrics.total_pairs == 1
    assert metrics.overall_repeatability == pytest.approx(1.0)


def test_frame_change_is_rejected_instead_of_mixing_coordinates():
    with pytest.raises(ValueError, match="coordinate frame changed"):
        compute_metrics(
            [frame(1, [(0.0, 0.0)], "laser"), frame(2, [(0.0, 0.0)], "base_link")]
        )


def test_pool_mean_and_min_are_distinct_and_reproducible():
    metrics = compute_metrics(
        [
            frame(1, [(0.0, 0.0), (1.0, 0.0)]),
            frame(2, [(0.01, 0.0), (1.01, 0.0)]),
            frame(3, [(0.02, 0.0), (3.0, 0.0)]),
        ],
        0.12,
    )

    assert metrics is not None
    assert metrics.per_frame_repeatability == pytest.approx([1.0, 0.5])
    assert metrics.mean_per_frame == pytest.approx(0.75)
    assert metrics.min_repeatability == pytest.approx(0.5)
    assert metrics.overall_repeatability == pytest.approx(0.75)


@pytest.mark.parametrize("match_distance", [-0.12, 0.0, float("nan"), float("inf")])
def test_pair_api_rejects_invalid_matching_distance(match_distance):
    with pytest.raises(ValueError, match="finite and positive"):
        compute_frame_pair_repeatability(
            frame(1, [(0.0, 0.0)]), frame(2, [(0.01, 0.0)]), match_distance
        )


def test_mixed_feature_formats_are_rejected_by_pair_and_aggregate_apis():
    spatial = frame(1, [(0.0, 0.0)])
    legacy = FrameFeatures(2, 2.0, [1], 1)
    for first, second in ((spatial, legacy), (legacy, spatial)):
        with pytest.raises(ValueError, match="feature formats"):
            compute_frame_pair_repeatability(first, second)
        with pytest.raises(ValueError, match="feature formats"):
            compute_metrics([first, second])


def test_legacy_id_frames_remain_supported():
    frames = [FrameFeatures(1, 1.0, [10, 20], 2), FrameFeatures(2, 2.0, [20], 1)]
    assert compute_frame_pair_repeatability(*frames) == pytest.approx(2.0 / 3.0)
    metrics = compute_metrics(frames)
    assert metrics is not None
    assert metrics.matching_method == "LEGACY_ID"
    assert metrics.overall_repeatability == pytest.approx(2.0 / 3.0)


def test_invalid_distance_is_rejected_even_when_no_pair_is_available():
    with pytest.raises(ValueError, match="finite and positive"):
        compute_metrics([], -0.12)
    with pytest.raises(ValueError, match="finite and positive"):
        compute_frame_pair_repeatability(frame(1, []), frame(2, []), -0.12)


def test_csv_cli_produces_metrics_and_rejects_invalid_distance(tmp_path, capsys):
    csv_path = tmp_path / "features.csv"
    output_path = tmp_path / "metrics.json"
    fieldnames = [
        "frame_id", "timestamp", "valid_feature_count",
        "feature_points", "coordinate_frame",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for frame_id in (1, 2):
            writer.writerow({
                "frame_id": frame_id,
                "timestamp": frame_id,
                "valid_feature_count": 1,
                "feature_points": json.dumps([[0.0, 0.0]]),
                "coordinate_frame": "laser",
            })
    assert main([str(csv_path), "--output-json", str(output_path)]) == 0
    metrics = json.loads(output_path.read_text(encoding="utf-8"))
    assert metrics["matching_method"] == "SPATIAL_2D"
    assert metrics["total_pairs"] == 1
    assert metrics["overall_repeatability"] == pytest.approx(1.0)
    assert main([str(csv_path), "--match-distance", "-0.12"]) == 1
    assert "finite and positive" in capsys.readouterr().err
