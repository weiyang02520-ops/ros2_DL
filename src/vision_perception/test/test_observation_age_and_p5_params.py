"""§5 / §9 config defaults and observation-age gate (no ROS / camera)."""

from __future__ import annotations

import pytest

from vision_perception.config import vision_config_from_mapping
from vision_perception.status_fields import (
    is_observation_too_old,
    source_stamp_age_sec,
)


def test_section5_defaults_and_rejects():
    cfg = vision_config_from_mapping(None)
    assert cfg.sync_queue_size == 10
    assert cfg.max_observation_age_sec == 0.500
    assert cfg.mask_erode_kernel == 3
    assert cfg.depth_patch_size == 7
    assert cfg.min_patch_pixels == 25
    assert cfg.min_valid_depth_fraction == 0.60
    assert cfg.max_depth_mad_m == 0.020
    assert cfg.max_depth_spread_m == 0.050
    with pytest.raises(ValueError, match="sync_queue_size"):
        vision_config_from_mapping({"sync_queue_size": 0})
    with pytest.raises(ValueError, match="mask_erode_kernel"):
        vision_config_from_mapping({"mask_erode_kernel": 2})
    with pytest.raises(ValueError, match="max_observation_age_sec"):
        vision_config_from_mapping({"max_observation_age_sec": 0.0})


def test_observation_age_gate():
    assert source_stamp_age_sec(10, 0, now_sec=10.6) == pytest.approx(0.6)
    assert (
        is_observation_too_old(10, 0, now_sec=10.6, max_observation_age_sec=0.5)
        is True
    )
    assert (
        is_observation_too_old(10, 0, now_sec=10.4, max_observation_age_sec=0.5)
        is False
    )
    # Future stamps are not "too old".
    assert (
        is_observation_too_old(20, 0, now_sec=10.0, max_observation_age_sec=0.5)
        is False
    )
