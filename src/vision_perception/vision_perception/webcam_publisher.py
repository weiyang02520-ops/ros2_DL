"""Optional V4L2/OpenCV webcam → sensor_msgs/Image publisher.

Not started from skeleton mode. Requires explicit launch (use_webcam:=true).
This is DEV_WEBCAM_ONLY / NOT_ZED — it does not open the ZED SDK.
"""

from __future__ import annotations

import sys

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import Image


class WebcamPublisherNode(Node):
    def __init__(self):
        super().__init__("vision_webcam_publisher")
        self.declare_parameter("video_device", 0)
        self.declare_parameter("image_topic", "/dg/vision/webcam/image_raw")
        self.declare_parameter("frame_id", "webcam_optical_frame")
        self.declare_parameter("frame_rate_hz", 15.0)
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)

        topic = str(self.get_parameter("image_topic").value)
        if not topic.startswith("/"):
            raise ValueError("image_topic must be absolute")
        self._frame_id = str(self.get_parameter("frame_id").value)
        rate = float(self.get_parameter("frame_rate_hz").value)
        if rate <= 0:
            raise ValueError("frame_rate_hz must be > 0")

        from vision_perception.runtime_deps import (
            OPENCV_PIP,
            NUMPY_PIP,
            check_numpy_opencv_compat,
        )

        check_numpy_opencv_compat()
        try:
            import cv2  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "OpenCV (cv2) is required for vision_webcam_publisher. "
                f"Install after {NUMPY_PIP}: pip install --user '{OPENCV_PIP}'"
            ) from exc

        device = int(self.get_parameter("video_device").value)
        self._cv2 = cv2
        self._cap = cv2.VideoCapture(device)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"Failed to open V4L2/OpenCV device index={device}. "
                "Check /dev/video* or use use_webcam:=false with an external Image topic."
            )
        width = int(self.get_parameter("width").value)
        height = int(self.get_parameter("height").value)
        if width > 0:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height > 0:
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self._pub = self.create_publisher(Image, topic, 10)
        self._timer = self.create_timer(1.0 / rate, self._tick)
        self.get_logger().warning(
            f"DEV_WEBCAM_ONLY / NOT_ZED: publishing {topic} from video_device={device}"
        )

    def _tick(self):
        ok, bgr = self._cap.read()
        if not ok or bgr is None:
            self.get_logger().error("webcam frame grab failed")
            return
        rgb = self._cv2.cvtColor(bgr, self._cv2.COLOR_BGR2RGB)
        msg = Image()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._frame_id
        msg.height = int(rgb.shape[0])
        msg.width = int(rgb.shape[1])
        msg.encoding = "rgb8"
        msg.is_bigendian = 0
        msg.step = int(msg.width * 3)
        msg.data = rgb.tobytes()
        self._pub.publish(msg)

    def destroy_node(self):
        try:
            if getattr(self, "_cap", None) is not None:
                self._cap.release()
        finally:
            super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    exit_code = 0
    try:
        node = WebcamPublisherNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (ValueError, RuntimeError) as exc:
        print(f"[vision_webcam_publisher] FATAL: {exc}", file=sys.stderr)
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
