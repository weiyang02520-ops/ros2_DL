"""Inert ROS2 shell: publish scaffold status, never fabricated observations."""

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class VisionPerceptionNode(Node):
    """Reserve configuration and expose an explicit non-operational status."""

    def __init__(self):
        super().__init__("vision_perception_node")
        defaults = {
            "mode": "skeleton",
            "rgb_topic": "/zed/zed_node/rgb/color/rect/image",
            "depth_topic": "/zed/zed_node/depth/depth_registered",
            "camera_info_topic": "/zed/zed_node/rgb/color/rect/camera_info",
            "detections_topic": "/dg/vision/detections_2d",
            "objects_topic": "/dg/vision/objects",
            "status_topic": "/dg/vision/status",
            "target_classes": ["bottle", "cup"],
            "backend": "unconfigured",
            "model_path": "",
            "detector_enabled": False,
            "tracking_enabled": False,
            "publish_debug_image": False,
            "output_frame_policy": "input_optical_header",
            "sync_tolerance_sec": 0.05,
            "min_depth_m": 0.2,
            "max_depth_m": 8.0,
        }
        for name, default in defaults.items():
            self.declare_parameter(name, default)

        if self.get_parameter("mode").value != "skeleton":
            raise ValueError("Only skeleton mode exists; V1/V2/V3 are not implemented")
        enabled = any(
            self.get_parameter(name).value
            for name in ("detector_enabled", "tracking_enabled", "publish_debug_image")
        )
        if enabled or self.get_parameter("backend").value != "unconfigured":
            raise ValueError("Inference, tracking and debug rendering are not implemented")
        status_topic = self.get_parameter("status_topic").value
        if not status_topic.startswith("/dg/vision/"):
            raise ValueError("Scaffold status must remain within /dg/vision/")

        self._status_publisher = self.create_publisher(DiagnosticArray, status_topic, 1)
        self._timer = self.create_timer(1.0, self._publish_status)
        self.get_logger().warning(
            "SKELETON_ONLY: no camera subscriptions, inference, object output or control"
        )

    def _publish_status(self):
        message = DiagnosticArray()
        message.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = "dg/vision/scaffold"
        status.level = DiagnosticStatus.WARN
        status.message = "SKELETON_ONLY"
        fields = {
            "mode": "skeleton",
            "implementation_status": "NOT_IMPLEMENTED",
            "camera_subscriptions_active": "false",
            "inference_active": "false",
            "tracking_active": "false",
            "object_output_active": "false",
            "control_output_active": "false",
        }
        status.values = [KeyValue(key=key, value=value) for key, value in fields.items()]
        message.status = [status]
        self._status_publisher.publish(message)


def main(args=None):
    """Run the status-only shell using the existing repository cleanup style."""
    rclpy.init(args=args)
    node = None
    try:
        node = VisionPerceptionNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
