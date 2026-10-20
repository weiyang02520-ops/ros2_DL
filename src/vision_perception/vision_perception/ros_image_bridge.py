"""Decode ROS sensor_msgs/Image-like buffers without importing rclpy/cv_bridge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from vision_perception.image_io import decode_color_image


@dataclass(frozen=True)
class ImageHeader:
    frame_id: str
    stamp_sec: int
    stamp_nanosec: int


@dataclass(frozen=True)
class DecodedImage:
    rgb: np.ndarray
    header: ImageHeader
    encoding: str


def header_from_msg(msg: Any) -> ImageHeader:
    stamp = msg.header.stamp
    return ImageHeader(
        frame_id=str(msg.header.frame_id),
        stamp_sec=int(stamp.sec),
        stamp_nanosec=int(stamp.nanosec),
    )


def decode_sensor_image_msg(msg: Any) -> DecodedImage:
    """Decode a sensor_msgs/Image message (or duck-typed equivalent) to RGB uint8."""
    rgb = decode_color_image(
        data=msg.data,
        height=int(msg.height),
        width=int(msg.width),
        encoding=str(msg.encoding),
        step=int(msg.step) if getattr(msg, "step", 0) else None,
    )
    return DecodedImage(rgb=rgb, header=header_from_msg(msg), encoding=str(msg.encoding))


def encode_rgb8_image_fields(
    rgb: np.ndarray,
    *,
    frame_id: str = "",
    stamp_sec: int = 0,
    stamp_nanosec: int = 0,
) -> dict:
    """Build field dict matching sensor_msgs/Image for tests / publishers."""
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("rgb must be HxWx3")
    height, width = rgb.shape[:2]
    contiguous = np.ascontiguousarray(rgb, dtype=np.uint8)
    return {
        "height": height,
        "width": width,
        "encoding": "rgb8",
        "is_bigendian": 0,
        "step": width * 3,
        "data": contiguous.tobytes(),
        "header": {
            "frame_id": frame_id,
            "stamp": {"sec": stamp_sec, "nanosec": stamp_nanosec},
        },
    }


class _FakeImageMsg:
    """Minimal duck-typed sensor_msgs/Image for unit tests."""

    def __init__(self, fields: dict):
        self.height = fields["height"]
        self.width = fields["width"]
        self.encoding = fields["encoding"]
        self.is_bigendian = fields.get("is_bigendian", 0)
        self.step = fields["step"]
        self.data = fields["data"]

        class _Stamp:
            def __init__(self, sec, nanosec):
                self.sec = sec
                self.nanosec = nanosec

        class _Header:
            def __init__(self, frame_id, stamp):
                self.frame_id = frame_id
                self.stamp = stamp

        hdr = fields["header"]
        self.header = _Header(
            hdr.get("frame_id", ""),
            _Stamp(hdr["stamp"]["sec"], hdr["stamp"]["nanosec"]),
        )
