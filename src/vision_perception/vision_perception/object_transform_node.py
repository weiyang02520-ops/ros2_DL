"""W5: independent VisionObjectArray camera→target transform adapter.

Default disabled. Consumes /dg/vision/objects; optionally publishes
/dg/vision/objects_target. Never starts ZED, never publishes TF / cmd_vel /
nav goals /initialpose. Extrinsics must be provided (static YAML or TF at
the observation stamp) — no identity fallback.
"""

from __future__ import annotations

import math
import sys
import time
from typing import Any, Optional

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.time import Time

from vision_perception.object_transform import (
    RigidTransform,
    rigid_transform_from_mapping,
    transform_object_batch,
)
from vision_perception.objects_pipeline import Object3D, ObjectBatch
from vision_perception.status_fields import as_diagnostic_level_byte
from vision_perception.types import DetectionBatch, FrameKey, POSITION_REFERENCE


def _nan_xyz():
    return (float("nan"), float("nan"), float("nan"))


def _nan_quat():
    return (float("nan"), float("nan"), float("nan"), float("nan"))


def _object_batch_from_msg(msg) -> ObjectBatch:
    key = FrameKey(
        source_session_id=str(msg.source_session_id),
        observation_id=int(msg.observation_id),
        source_kind=str(msg.source_kind),
        calibration_id=str(msg.calibration_id),
        frame_id=str(msg.header.frame_id),
        source_stamp_sec=int(msg.header.stamp.sec),
        source_stamp_nanosec=int(msg.header.stamp.nanosec),
    )
    objects = []
    for item in msg.objects:
        objects.append(
            Object3D(
                detection_index=int(item.detection_index),
                class_name=str(item.class_name),
                confidence=float(item.confidence),
                bbox_center_x=float(item.bbox.center.x),
                bbox_center_y=float(item.bbox.center.y),
                bbox_size_x=float(item.bbox.size_x),
                bbox_size_y=float(item.bbox.size_y),
                bbox_theta=float(item.bbox.center.theta),
                position_xyz=(
                    float(item.position.x),
                    float(item.position.y),
                    float(item.position.z),
                ),
                position_valid=bool(item.position_valid),
                position_reference=str(item.position_reference or POSITION_REFERENCE),
                invalid_reason=str(item.invalid_reason),
                reference_u=float(item.reference_u),
                reference_v=float(item.reference_v),
                valid_depth_fraction=float(item.valid_depth_fraction),
                orientation_xyzw=(
                    float(item.orientation.x),
                    float(item.orientation.y),
                    float(item.orientation.z),
                    float(item.orientation.w),
                ),
                orientation_valid=False,
                tracking_valid=bool(item.tracking_valid),
                object_id=str(item.object_id),
                mask_source="",
            )
        )
    return ObjectBatch(
        detection_batch=DetectionBatch(key=key, detections=()),
        objects=tuple(objects),
        tracking_session_id=str(msg.tracking_session_id),
        depth_paired=True,
        pair_skew_sec=None,
        pair_reason="OK",
        calibration_id=str(msg.calibration_id),
    )


class ObjectTransformNode(Node):
    """Subscribe camera objects → optional target-frame VisionObjectArray."""

    def __init__(self):
        super().__init__("vision_object_transform_node")
        self.declare_parameter("enabled", False)
        self.declare_parameter("mode", "static_extrinsics")  # static_extrinsics | tf
        self.declare_parameter("source_frame", "")
        self.declare_parameter("target_frame", "")
        self.declare_parameter("extrinsics_id", "")
        self.declare_parameter("calibration_date", "")
        self.declare_parameter("source_note", "")
        self.declare_parameter("translation_m", [float("nan"), float("nan"), float("nan")])
        self.declare_parameter("quaternion_xyzw", [0.0, 0.0, 0.0, 1.0])
        self.declare_parameter("rotation_matrix", [])  # flat 9 or empty
        self.declare_parameter("tf_timeout_sec", 0.05)
        self.declare_parameter("objects_input_topic", "/dg/vision/objects")
        self.declare_parameter("objects_target_topic", "/dg/vision/objects_target")
        self.declare_parameter("status_topic", "/dg/vision/transform_status")
        self.declare_parameter("status_rate_hz", 1.0)

        self._enabled = bool(self.get_parameter("enabled").value)
        self._mode = str(self.get_parameter("mode").value).strip().lower()
        self._tf_timeout = float(self.get_parameter("tf_timeout_sec").value)
        self._input_topic = str(self.get_parameter("objects_input_topic").value)
        self._output_topic = str(self.get_parameter("objects_target_topic").value)
        status_topic = str(self.get_parameter("status_topic").value)
        if not self._output_topic.startswith("/dg/vision/"):
            raise ValueError("objects_target_topic must stay under /dg/vision/")
        if not status_topic.startswith("/dg/vision/"):
            raise ValueError("status_topic must stay under /dg/vision/")

        self._static_rigid: Optional[RigidTransform] = None
        self._tf_buffer = None
        self._tf_listener = None
        self._last_reason = "TRANSFORM_DISABLED" if not self._enabled else "WAITING"
        self._last_count = 0
        self._last_valid = 0
        self._frames_in = 0
        self._frames_out = 0
        self._started = time.monotonic()
        self._last_input_mono: Optional[float] = None

        from vision_perception_interfaces.msg import VisionObjectArray

        self._pub = self.create_publisher(VisionObjectArray, self._output_topic, 10)
        self._status_pub = self.create_publisher(DiagnosticArray, status_topic, 1)
        self._sub = self.create_subscription(
            VisionObjectArray, self._input_topic, self._on_objects, 10
        )

        if self._enabled:
            self._init_transform_backend()
        else:
            self.get_logger().warning(
                "W5 transform DISABLED (default): will not publish valid "
                f"target poses on {self._output_topic}; camera "
                f"{self._input_topic} is unchanged; no TF publish / no motion"
            )

        rate = float(self.get_parameter("status_rate_hz").value)
        if rate <= 0:
            raise ValueError("status_rate_hz must be > 0")
        self.create_timer(1.0 / rate, self._publish_status)

    def _init_transform_backend(self) -> None:
        if self._mode == "static_extrinsics":
            self._static_rigid = self._load_static_from_params()
            self.get_logger().warning(
                f"W5 static_extrinsics enabled: "
                f"{self._static_rigid.source_frame} → {self._static_rigid.target_frame} "
                f"extrinsics_id={self._static_rigid.extrinsics_id!r}; "
                "no TF publish; orientation_valid stays false"
            )
        elif self._mode == "tf":
            from tf2_ros import Buffer, TransformListener

            source = str(self.get_parameter("source_frame").value).strip()
            target = str(self.get_parameter("target_frame").value).strip()
            if not source or not target:
                raise ValueError("tf mode requires source_frame and target_frame")
            self._tf_source = source
            self._tf_target = target
            self._tf_buffer = Buffer()
            self._tf_listener = TransformListener(self._tf_buffer, self)
            self.get_logger().warning(
                f"W5 tf mode: lookup {source}→{target} at observation stamp "
                f"(timeout={self._tf_timeout}s); consumes TF only, does not publish TF"
            )
        else:
            raise ValueError(
                f"Unsupported transform mode={self._mode!r}; "
                "use static_extrinsics or tf"
            )

    def _load_static_from_params(self) -> RigidTransform:
        source = str(self.get_parameter("source_frame").value).strip()
        target = str(self.get_parameter("target_frame").value).strip()
        t = [float(v) for v in self.get_parameter("translation_m").value]
        if len(t) != 3 or any(not math.isfinite(v) for v in t):
            raise ValueError(
                "enabled static_extrinsics requires finite translation_m [x,y,z]; "
                "refusing NaN / missing extrinsics (no identity fallback)"
            )
        extrinsics_id = str(self.get_parameter("extrinsics_id").value).strip()
        if not extrinsics_id or extrinsics_id.upper().startswith("EXAMPLE"):
            raise ValueError(
                "enabled static_extrinsics requires a real extrinsics_id "
                "(refusing empty/EXAMPLE identity placeholders)"
            )
        flat = list(self.get_parameter("rotation_matrix").value)
        mapping: dict = {
            "source_frame": source,
            "target_frame": target,
            "translation_m": t,
            "extrinsics_id": str(self.get_parameter("extrinsics_id").value),
            "calibration_date": str(self.get_parameter("calibration_date").value),
            "source_note": str(self.get_parameter("source_note").value),
        }
        if flat and len(flat) == 9:
            mapping["rotation"] = {
                "matrix": [
                    [float(flat[0]), float(flat[1]), float(flat[2])],
                    [float(flat[3]), float(flat[4]), float(flat[5])],
                    [float(flat[6]), float(flat[7]), float(flat[8])],
                ]
            }
        else:
            q = [float(v) for v in self.get_parameter("quaternion_xyzw").value]
            mapping["rotation"] = {"quaternion_xyzw": q}
        return rigid_transform_from_mapping(mapping)

    def _lookup_tf_rigid(self, stamp_sec: int, stamp_nanosec: int) -> tuple:
        """Return (RigidTransform|None, fail_reason). Uses observation stamp."""
        assert self._tf_buffer is not None
        try:
            when = Time(seconds=int(stamp_sec), nanoseconds=int(stamp_nanosec))
            tf = self._tf_buffer.lookup_transform(
                self._tf_target,
                self._tf_source,
                when,
                timeout=rclpy.duration.Duration(seconds=self._tf_timeout),
            )
        except Exception as exc:  # noqa: BLE001 — tf2 exceptions vary
            return None, f"INPUT_INVALID:{type(exc).__name__}"
        t = tf.transform.translation
        q = tf.transform.rotation
        try:
            rigid = rigid_transform_from_mapping(
                {
                    "source_frame": self._tf_source,
                    "target_frame": self._tf_target,
                    "translation_m": [t.x, t.y, t.z],
                    "rotation": {
                        "quaternion_xyzw": [q.x, q.y, q.z, q.w]
                    },
                    "extrinsics_id": f"tf:{self._tf_source}->{self._tf_target}",
                }
            )
        except ValueError:
            return None, "INPUT_INVALID"
        return rigid, "OK"

    def _on_objects(self, msg) -> None:
        from vision_perception.message_mapping import try_build_vision_object_array_msg

        self._frames_in += 1
        self._last_input_mono = time.monotonic()
        batch = _object_batch_from_msg(msg)

        if not self._enabled:
            self._last_reason = "TRANSFORM_DISABLED"
            # Still publish invalidated copies so consumers see the gate, OR skip.
            # Contract: when disabled, do not emit "successful" target coords.
            # Prefer not publishing valid-looking traffic: publish empty-invalid batch
            # only if someone subscribed; keep reason in status.
            out, outcome = transform_object_batch(
                batch, rigid=None, enabled=False, transform_available=False
            )
            self._last_reason = outcome.reason
            self._last_count = len(out.objects)
            self._last_valid = 0
            return

        rigid: Optional[RigidTransform] = None
        fail = "INPUT_INVALID"
        available = False
        if self._mode == "static_extrinsics":
            rigid = self._static_rigid
            available = rigid is not None
            fail = "INPUT_INVALID" if not available else "OK"
        elif self._mode == "tf":
            rigid, fail = self._lookup_tf_rigid(
                batch.detection_batch.key.source_stamp_sec,
                batch.detection_batch.key.source_stamp_nanosec,
            )
            available = rigid is not None
            if not available and not fail.startswith("INPUT_INVALID"):
                fail = "INPUT_INVALID"

        out, outcome = transform_object_batch(
            batch,
            rigid=rigid,
            enabled=True,
            transform_available=available,
            transform_fail_reason="INPUT_INVALID",
            expected_source_frame=str(self.get_parameter("source_frame").value),
        )
        self._last_reason = outcome.reason if available else fail
        self._last_count = len(out.objects)
        self._last_valid = sum(1 for o in out.objects if o.position_valid)
        try:
            self._pub.publish(try_build_vision_object_array_msg(out))
            self._frames_out += 1
        except RuntimeError as exc:
            self.get_logger().error(f"failed to build target VisionObjectArray: {exc}")

    def _publish_status(self) -> None:
        msg = DiagnosticArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        st = DiagnosticStatus()
        st.name = "dg/vision/object_transform"
        age = (
            ""
            if self._last_input_mono is None
            else f"{time.monotonic() - self._last_input_mono:.3f}"
        )
        if not self._enabled:
            st.level = as_diagnostic_level_byte(1)  # WARN
            st.message = "TRANSFORM_DISABLED"
        elif self._last_reason not in {"OK", "WAITING"}:
            st.level = as_diagnostic_level_byte(1)
            st.message = self._last_reason
        else:
            st.level = as_diagnostic_level_byte(0)
            st.message = "TRANSFORM_ACTIVE"
        fields = {
            "enabled": "true" if self._enabled else "false",
            "mode": self._mode,
            "objects_input_topic": self._input_topic,
            "objects_target_topic": self._output_topic,
            "source_frame": str(self.get_parameter("source_frame").value),
            "target_frame": str(self.get_parameter("target_frame").value),
            "extrinsics_id": str(self.get_parameter("extrinsics_id").value),
            "last_reason": self._last_reason,
            "frames_in": str(self._frames_in),
            "frames_out": str(self._frames_out),
            "last_object_count": str(self._last_count),
            "last_position_valid_count": str(self._last_valid),
            "last_input_age_sec": age,
            "publishes_tf": "false",
            "control_output_active": "false",
            "arm_ready": "NO",
            "note": (
                "bbox/reference_u/v remain source-image pixels; "
                "orientation_valid always false"
            ),
        }
        st.values = [KeyValue(key=k, value=v) for k, v in fields.items()]
        msg.status = [st]
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = None
    code = 0
    try:
        node = ObjectTransformNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (ValueError, RuntimeError, FileNotFoundError, OSError) as exc:
        print(f"[vision_object_transform_node] FATAL: {exc}", file=sys.stderr)
        code = 1
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    if code:
        sys.exit(code)


if __name__ == "__main__":
    main()
