#!/usr/bin/env python3
"""W6: 只订阅打印 VisionObjectArray / status — 不发布任何控制。

用法（需已 source 工作空间）::

  ros2 run vision_perception vision_subscribe_objects
  # 或
  python3 $(ros2 pkg prefix vision_perception)/share/vision_perception/examples/subscribe_vision_objects.py

可选参数：
  --topic /dg/vision/objects
  --target-topic /dg/vision/objects_target
  --status-topic /dg/vision/status
  --once
"""

from __future__ import annotations

import argparse
import math
import sys


def _fmt_xyz(p) -> str:
    if any(math.isnan(float(v)) for v in (p.x, p.y, p.z)):
        return "(NaN, NaN, NaN)"
    return f"({p.x:.4f}, {p.y:.4f}, {p.z:.4f})"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default="/dg/vision/objects")
    parser.add_argument("--target-topic", default="")
    parser.add_argument("--status-topic", default="/dg/vision/status")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)

    try:
        import rclpy
        from diagnostic_msgs.msg import DiagnosticArray
        from rclpy.node import Node
        from vision_perception_interfaces.msg import VisionObjectArray
    except ImportError as exc:
        print(f"ROS deps missing: {exc}", file=sys.stderr)
        return 2

    class Subscriber(Node):
        def __init__(self):
            super().__init__("vision_subscribe_objects_example")
            self._done = False
            self.create_subscription(
                VisionObjectArray, args.topic, self._on_objects, 10
            )
            if args.target_topic:
                self.create_subscription(
                    VisionObjectArray, args.target_topic, self._on_target, 10
                )
            if args.status_topic:
                self.create_subscription(
                    DiagnosticArray, args.status_topic, self._on_status, 10
                )
            self.get_logger().info(
                f"subscribe-only example: objects={args.topic} "
                f"target={args.target_topic or '(off)'} "
                f"status={args.status_topic or '(off)'}; "
                "NO cmd_vel / NO goals / NO TF publish"
            )

        def _print_array(self, label: str, msg: VisionObjectArray) -> None:
            stamp = msg.header.stamp
            print(
                f"[{label}] frame={msg.header.frame_id!r} "
                f"stamp={stamp.sec}.{stamp.nanosec:09d} "
                f"source_kind={msg.source_kind} "
                f"obs_id={msg.observation_id} "
                f"n={len(msg.objects)}"
            )
            for obj in msg.objects:
                print(
                    f"  idx={obj.detection_index} class={obj.class_name} "
                    f"conf={obj.confidence:.3f} "
                    f"valid={obj.position_valid} reason={obj.invalid_reason!r} "
                    f"xyz={_fmt_xyz(obj.position)} "
                    f"ref_uv=({obj.reference_u:.1f},{obj.reference_v:.1f}) "
                    f"orient_valid={obj.orientation_valid} "
                    f"track_valid={obj.tracking_valid} id={obj.object_id!r}"
                )
            if args.once:
                self._done = True

        def _on_objects(self, msg: VisionObjectArray) -> None:
            self._print_array("camera_objects", msg)

        def _on_target(self, msg: VisionObjectArray) -> None:
            self._print_array("target_objects", msg)

        def _on_status(self, msg: DiagnosticArray) -> None:
            for st in msg.status:
                print(f"[status] {st.name}: level={st.level!r} msg={st.message}")
                for kv in st.values:
                    if kv.key in {
                        "source_kind",
                        "arm_ready",
                        "enable_objects",
                        "last_pair_reason",
                        "last_mask_source",
                        "camera_contract",
                    }:
                        print(f"         {kv.key}={kv.value}")

    rclpy.init(args=None)
    node = Subscriber()
    try:
        while rclpy.ok() and not node._done:
            rclpy.spin_once(node, timeout_sec=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
