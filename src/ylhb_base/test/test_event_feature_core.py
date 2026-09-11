import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from event_feature_core import (  # noqa: E402
    EventFeature,
    EventFeatureConfig,
    EventObservation,
    extract_event_features,
    feature_repeatability,
)


def observation(x: int, y: int, polarity: int = 1, offset: int = 0) -> EventObservation:
    return EventObservation(x, y, polarity, offset)


def test_dense_cells_become_deterministic_features() -> None:
    config = EventFeatureConfig(
        width=64,
        height=48,
        cell_size_px=8,
        min_events_per_cell=3,
        min_unique_pixels=2,
        max_features=8,
    )
    samples = [
        observation(1, 1),
        observation(2, 1, 0),
        observation(2, 2),
        observation(17, 9),
        observation(18, 9),
        observation(18, 10, 0),
        observation(40, 40),
    ]
    features = extract_event_features(samples, config)
    assert len(features) == 2
    assert features[0].x == pytest.approx(5.0 / 3.0)
    assert features[0].positive_fraction == pytest.approx(2.0 / 3.0)
    assert features[1].unique_pixel_count == 3


def test_sparse_or_hot_single_pixel_activity_is_rejected() -> None:
    config = EventFeatureConfig(
        width=32,
        height=32,
        cell_size_px=8,
        min_events_per_cell=3,
        min_unique_pixels=2,
    )
    samples = [observation(3, 3, offset=index) for index in range(10)]
    assert extract_event_features(samples, config) == []


def test_repeatability_is_one_to_one_and_zero_feature_is_unknown() -> None:
    previous = [
        EventFeature(10.0, 10.0, 5, 3, 0.6),
        EventFeature(11.0, 10.0, 5, 3, 0.6),
    ]
    current = [EventFeature(10.5, 10.0, 6, 4, 0.5)]
    assert feature_repeatability(previous, current, 2.0) == pytest.approx(2.0 / 3.0)
    assert feature_repeatability([], current, 2.0) is None


def test_invalid_event_is_rejected() -> None:
    config = EventFeatureConfig(width=32, height=32)
    with pytest.raises(ValueError, match="outside"):
        extract_event_features([observation(40, 1)], config)
