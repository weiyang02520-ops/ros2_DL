"""Publish synthetic depth + CameraInfo for offline V2 smoke (no ZED SDK).

Default smoke mode (launch ``use_fake_depth``): **timer is the stamp master**.
Publishes depth + CameraInfo with a shared ``now()`` stamp; fake_image should
set ``stamp_source_topic`` to this depth topic so RGB copies the same stamp
*after* depth/info are out (pairing succeeds).

Optional ``rgb_topic`` mirror mode remains for experiments; prefer timer+mirror
RGB for the default smoke path (avoids vision seeing RGB before depth).
"""

from __future__ import annotations

import sys

import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image

from vision_perception.depth_io import (
    camera_calibration_from_pinhole,
    encode_depth_32fc1_fields,
)


class FakeDepthPublisherNode(Node):
    def __init__(self):
        super().__init__("vision_fake_depth_publisher")
        self.declare_parameter("depth_topic", "/dg/vision/fake/depth")
        self.declare_parameter("camera_info_topic", "/dg/vision/fake/camera_info")
        # Empty = do not mirror RGB (timer master). Non-empty = copy RGB stamps.
        self.declare_parameter("rgb_topic", "")
        self.declare_parameter("frame_id", "fake_webcam_optical_frame")
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("constant_depth_m", 1.0)
        self.declare_parameter("fx", 500.0)
        self.declare_parameter("fy", 500.0)
        self.declare_parameter("cx", 320.0)
        self.declare_parameter("cy", 240.0)
        self.declare_parameter("frame_rate_hz", 5.0)

        self._depth_topic = str(self.get_parameter("depth_topic").value)
        self._info_topic = str(self.get_parameter("camera_info_topic").value)
        self._frame_id = str(self.get_parameter("frame_id").value)
        self._width = int(self.get_parameter("width").value)
        self._height = int(self.get_parameter("height").value)
        self._depth_m = float(self.get_parameter("constant_depth_m").value)
        self._fx = float(self.get_parameter("fx").value)
        self._fy = float(self.get_parameter("fy").value)
        self._cx = float(self.get_parameter("cx").value)
        self._cy = float(self.get_parameter("cy").value)
        if self._width <= 0 or self._height <= 0:
            raise ValueError("width/height must be positive")
        if self._depth_m <= 0:
            raise ValueError("constant_depth_m must be > 0")

        self._calib = camera_calibration_from_pinhole(
            width=self._width,
            height=self._height,
            fx=self._fx,
            fy=self._fy,
            cx=self._cx,
            cy=self._cy,
            frame_id=self._frame_id,
        )
        self._depth_plane = np.full(
            (self._height, self._width), self._depth_m, dtype=np.float32
        )

        self._depth_pub = self.create_publisher(Image, self._depth_topic, 10)
        self._info_pub = self.create_publisher(CameraInfo, self._info_topic, 10)

        rgb_topic = str(self.get_parameter("rgb_topic").value).strip()
        rate = float(self.get_parameter("frame_rate_hz").value)
        self._rgb_sub = None
        self._timer = None
        if rgb_topic:
            self._rgb_sub = self.create_subscription(
                Image, rgb_topic, self._on_rgb, 10
            )
            self.get_logger().warning(
                f"DEV fake depth mirrors stamps from {rgb_topic} → "
                f"{self._depth_topic} + {self._info_topic} "
                f"(constant {self._depth_m} m). Prefer timer master + "
                "fake_image stamp_source_topic for default smoke."
            )
        if rate > 0:
            self._timer = self.create_timer(1.0 / rate, self._on_timer)
            self.get_logger().warning(
                f"DEV fake depth stamp-master timer {rate} Hz → "
                f"{self._depth_topic} + {self._info_topic} "
                f"(constant {self._depth_m} m, NOT_ZED, no SDK)"
            )
        if self._rgb_sub is None and self._timer is None:
            raise ValueError(
                "fake depth needs frame_rate_hz > 0 (stamp master) "
                "and/or rgb_topic (mirror mode)"
            )

    def _publish(self, stamp, frame_id: str) -> None:
        # Publish CameraInfo then depth so calib is cached before depth pairing.
        info = CameraInfo()
        info.header.stamp = stamp
        info.header.frame_id = frame_id or self._frame_id
        info.width = self._calib.width
        info.height = self._calib.height
        info.k = list(self._calib.k)
        info.d = list(self._calib.d)
        info.r = list(self._calib.r)
        info.p = list(self._calib.p)
        info.distortion_model = "plumb_bob"
        self._info_pub.publish(info)

        fields = encode_depth_32fc1_fields(
            self._depth_plane,
            frame_id=frame_id or self._frame_id,
            stamp_sec=int(stamp.sec),
            stamp_nanosec=int(stamp.nanosec),
        )
        depth_msg = Image()
        depth_msg.header.stamp = stamp
        depth_msg.header.frame_id = fields["header"]["frame_id"]
        depth_msg.height = int(fields["height"])
        depth_msg.width = int(fields["width"])
        depth_msg.encoding = str(fields["encoding"])
        depth_msg.is_bigendian = 0
        depth_msg.step = int(fields["step"])
        depth_msg.data = fields["data"]
        self._depth_pub.publish(depth_msg)

    def _on_rgb(self, msg: Image) -> None:
        h, w = int(msg.height), int(msg.width)
        if (h, w) != (self._height, self._width):
            self._height, self._width = h, w
            self._cx = w / 2.0
            self._cy = h / 2.0
            self._calib = camera_calibration_from_pinhole(
                width=w,
                height=h,
                fx=self._fx,
                fy=self._fy,
                cx=self._cx,
                cy=self._cy,
                frame_id=self._frame_id,
            )
            self._depth_plane = np.full((h, w), self._depth_m, dtype=np.float32)
        frame_id = str(msg.header.frame_id) or self._frame_id
        self._publish(msg.header.stamp, frame_id)

    def _on_timer(self) -> None:
        stamp = self.get_clock().now().to_msg()
        self._publish(stamp, self._frame_id)


def main(args=None):
    rclpy.init(args=args)
    node = None
    exit_code = 0
    try:
        node = FakeDepthPublisherNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"[vision_fake_depth_publisher] FATAL: {exc}", file=sys.stderr)
        exit_code = 1
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
