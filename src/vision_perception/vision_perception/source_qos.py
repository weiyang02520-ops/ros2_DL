"""Subscription QoS helpers for RGB / depth / CameraInfo (no rclpy import at module load).

ZED and other sensor drivers commonly publish BEST_EFFORT + VOLATILE. Matching
that profile avoids silent zero-message subscriptions when RELIABLE is assumed.
"""

from __future__ import annotations

from typing import Any


ALLOWED_QOS_RELIABILITY = frozenset({"best_effort", "reliable"})


def normalize_qos_reliability(value: Any) -> str:
    text = str(value or "best_effort").strip().lower().replace("-", "_")
    if text not in ALLOWED_QOS_RELIABILITY:
        raise ValueError(
            f"image_qos_reliability must be one of {sorted(ALLOWED_QOS_RELIABILITY)}, "
            f"got {value!r}"
        )
    return text


def build_sensor_qos_profile(reliability: str = "best_effort", *, depth: int = 10):
    """Build an rclpy QoSProfile for camera Image / CameraInfo subscriptions."""
    from rclpy.qos import (
        DurabilityPolicy,
        HistoryPolicy,
        QoSProfile,
        ReliabilityPolicy,
    )

    rel = normalize_qos_reliability(reliability)
    policy = (
        ReliabilityPolicy.BEST_EFFORT
        if rel == "best_effort"
        else ReliabilityPolicy.RELIABLE
    )
    return QoSProfile(
        history=HistoryPolicy.KEEP_LAST,
        depth=int(depth),
        reliability=policy,
        durability=DurabilityPolicy.VOLATILE,
    )
