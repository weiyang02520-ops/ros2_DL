"""Latest-frame worker and Image decode tests (no ROS / no camera)."""

from __future__ import annotations

import time

import numpy as np

from vision_perception.frame_worker import LatestFrameWorker
from vision_perception.ros_image_bridge import (
    _FakeImageMsg,
    decode_sensor_image_msg,
    encode_rgb8_image_fields,
)


def test_latest_frame_worker_drops_superseded_pending():
    seen = []

    def process(item):
        time.sleep(0.05)
        seen.append(item)

    worker = LatestFrameWorker(process, min_interval_sec=0.0)
    worker.start()
    try:
        worker.submit("a")
        time.sleep(0.01)
        worker.submit("b")
        worker.submit("c")
        deadline = time.time() + 2.0
        while worker.processed < 1 and time.time() < deadline:
            time.sleep(0.01)
        # Allow worker to drain the last pending item.
        deadline = time.time() + 2.0
        while worker.processed < 2 and time.time() < deadline:
            time.sleep(0.01)
        assert worker.dropped >= 1
        assert "c" in seen
        assert seen[-1] == "c"
    finally:
        worker.stop()


def test_decode_sensor_image_msg_rgb8_roundtrip():
    rgb = np.zeros((4, 5, 3), dtype=np.uint8)
    rgb[1, 2] = (10, 20, 30)
    fields = encode_rgb8_image_fields(
        rgb, frame_id="webcam_optical_frame", stamp_sec=1, stamp_nanosec=2
    )
    msg = _FakeImageMsg(fields)
    decoded = decode_sensor_image_msg(msg)
    assert decoded.header.frame_id == "webcam_optical_frame"
    assert decoded.header.stamp_sec == 1
    assert decoded.header.stamp_nanosec == 2
    assert decoded.rgb.shape == (4, 5, 3)
    assert tuple(decoded.rgb[1, 2]) == (10, 20, 30)
