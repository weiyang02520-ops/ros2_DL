"""ROS2 vision node: skeleton (default) or explicit v1_ros RGB detection.

skeleton: status only — no camera, no inference, no detections.
v1_ros: subscribe sensor_msgs/Image, run DetectionEngine, publish
        VisionDetectionArray on /dg/vision/detections_2d + status.
Optional enable_objects:=true (default false): subscribe depth + CameraInfo,
        wait up to sync_wait_sec then pair ≤ sync_tolerance_sec, publish
        VisionObjectArray on /dg/vision/objects.
Optional enable_tracking:=true (default false, v1_ros only): short-horizon
        2D IoU tracker; fills object_id / tracking_valid when objects on.
Optional debug_image (default off, ≤2 Hz). mode:=v1 (legacy) remains rejected.
camera_contract for v1_ros: DEV_WEBCAM_ONLY / NOT_ZED. ARM_READY=NO.
Does not start ZED SDK or publish grasp / cmd_vel.
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image

from vision_perception.config import (
    CAMERA_CONTRACT_NOT_RUN,
    as_bool,
    normalize_ros_node_mode,
    vision_config_from_mapping,
)
from vision_perception.debug_overlay import DebugPublishGate, draw_detections_rgb
from vision_perception.depth_io import (
    CameraCalibration,
    DepthFrame,
    camera_calibration_from_info_msg,
    decode_depth_msg,
)
from vision_perception.frame_pairing import DepthFrameBuffer, RgbDepthSyncGate, SyncedPair
from vision_perception.frame_worker import LatestFrameWorker
from vision_perception.message_mapping import (
    try_build_vision_detection_array_msg,
    try_build_vision_object_array_msg,
)
from vision_perception.objects_pipeline import apply_track_assignments, build_object_batch
from vision_perception.pipeline import DetectionEngine
from vision_perception.ros_image_bridge import (
    DecodedImage,
    decode_sensor_image_msg,
    encode_rgb8_image_fields,
)
from vision_perception.runtime_deps import check_numpy_opencv_compat, check_v1_runtime_imports
from vision_perception.status_fields import (
    as_diagnostic_level_byte,
    compose_v1_ros_diagnostic,
    is_input_stale,
    is_observation_too_old,
)
from vision_perception.tracker import MultiObjectTracker, stamp_sec_from_parts


@dataclass
class PendingRgbJob:
    """RGB frame plus optional pre-inference depth snapshot (V2)."""

    decoded: DecodedImage
    depth: Optional[DepthFrame]
    pair_skew_sec: Optional[float]
    pair_reason: str
    calibration: Optional[CameraCalibration]


def _fill_sensor_image_msg(msg: Image, fields: dict) -> Image:
    msg.height = int(fields["height"])
    msg.width = int(fields["width"])
    msg.encoding = str(fields["encoding"])
    msg.is_bigendian = int(fields.get("is_bigendian", 0))
    msg.step = int(fields["step"])
    msg.data = fields["data"]
    msg.header.frame_id = str(fields["header"]["frame_id"])
    msg.header.stamp.sec = int(fields["header"]["stamp"]["sec"])
    msg.header.stamp.nanosec = int(fields["header"]["stamp"]["nanosec"])
    return msg


class VisionPerceptionNode(Node):
    """Skeleton status shell, or v1_ros Image→detections (+ optional V2 objects)."""

    def __init__(self):
        super().__init__("vision_perception_node")
        defaults = {
            "mode": "skeleton",
            "rgb_topic": "/dg/vision/webcam/image_raw",
            "depth_topic": "/zed/zed_node/depth/depth_registered",
            "camera_info_topic": "/zed/zed_node/rgb/color/rect/camera_info",
            "detections_topic": "/dg/vision/detections_2d",
            "objects_topic": "/dg/vision/objects",
            "status_topic": "/dg/vision/status",
            "debug_image_topic": "/dg/vision/debug_image",
            "target_classes": ["bottle", "cup"],
            "backend": "unconfigured",
            "model_path": "",
            "model_manifest_path": "",
            "detector_enabled": False,
            "enable_objects": False,
            "enable_tracking": False,
            "tracking_enabled": False,
            "tracker_match_iou": 0.30,
            "tracker_confirm_hits": 3,
            "tracker_lost_timeout_sec": 0.70,
            "publish_debug_image": False,
            "debug_image_max_hz": 2.0,
            "input_stale_sec": 1.0,
            "output_frame_policy": "input_optical_header",
            "sync_tolerance_sec": 0.010,
            "sync_wait_sec": 0.100,
            "sync_queue_size": 10,
            "max_observation_age_sec": 0.500,
            "min_depth_m": 0.5,
            "max_depth_m": 1.5,
            "mask_erode_kernel": 3,
            "depth_patch_size": 7,
            "min_patch_pixels": 25,
            "min_valid_depth_fraction": 0.60,
            "max_depth_mad_m": 0.020,
            "max_depth_spread_m": 0.050,
            "inference_rate_hz": 5.0,
            "confidence_threshold": 0.35,
            "nms_iou_threshold": 0.45,
            "max_detections": 20,
            "ort_threads": 2,
            "model_input_size": 640,
            "status_rate_hz": 1.0,
            "video_device": 0,
            "image_frame_id": "webcam_optical_frame",
            "camera_contract": CAMERA_CONTRACT_NOT_RUN,
            "pending_frames": 1,
        }
        for name, default in defaults.items():
            self.declare_parameter(name, default)

        mode = normalize_ros_node_mode(self.get_parameter("mode").value)
        self._mode = mode
        self._engine: Optional[DetectionEngine] = None
        self._worker: Optional[LatestFrameWorker] = None
        self._detections_pub = None
        self._objects_pub = None
        self._debug_pub = None
        self._debug_gate: Optional[DebugPublishGate] = None
        self._image_sub = None
        self._depth_sub = None
        self._info_sub = None
        self._frames_received = 0
        self._depth_frames_received = 0
        self._last_observation_id = 0
        self._last_detection_count = 0
        self._last_objects_count = 0
        self._last_position_valid_count = 0
        self._last_pair_reason = ""
        self._last_pair_skew_sec: Optional[float] = None
        self._last_source_kind = "LIVE_CAMERA"
        self._last_calibration_id = ""
        self._last_inference_ms = -1.0
        self._backend_name = "unconfigured"
        self._publish_debug = False
        self._enable_objects = False
        self._object_output_active = False
        self._enable_tracking = False
        self._tracker: Optional[MultiObjectTracker] = None
        self._tracking_session_id = ""
        self._min_depth_m = 0.5
        self._max_depth_m = 1.5
        self._mask_erode_kernel = 3
        self._depth_patch_size = 7
        self._min_patch_pixels = 25
        self._min_valid_depth_fraction = 0.60
        self._max_depth_mad_m = 0.020
        self._max_depth_spread_m = 0.050
        self._sync_queue_size = 10
        self._max_observation_age_sec = 0.500
        self._observations_dropped_age = 0
        self._depth_topic = ""
        self._camera_info_topic = ""
        self._input_stale_sec = 1.0
        self._last_input_mono: Optional[float] = None
        self._started_mono = time.monotonic()
        self._stale_cleared = False
        self._implementation_status = "SKELETON_ONLY"
        self._camera_contract = CAMERA_CONTRACT_NOT_RUN
        self._inference_active = False
        self._camera_subscriptions_active = False
        self._depth_buffer: Optional[DepthFrameBuffer] = None
        self._sync_gate: Optional[RgbDepthSyncGate[DecodedImage]] = None
        self._sync_poll_timer = None
        self._calib_lock = threading.Lock()
        self._calibration: Optional[CameraCalibration] = None
        self._camera_info_received = False

        status_topic = self.get_parameter("status_topic").value
        if not status_topic.startswith("/dg/vision/"):
            raise ValueError("status_topic must remain within /dg/vision/")
        self._status_publisher = self.create_publisher(DiagnosticArray, status_topic, 1)

        if mode == "skeleton":
            self._init_skeleton()
        else:
            self._init_v1_ros()

        rate_hz = float(self.get_parameter("status_rate_hz").value)
        if rate_hz <= 0:
            raise ValueError("status_rate_hz must be > 0")
        self._timer = self.create_timer(1.0 / rate_hz, self._publish_status)

    def _param_map(self) -> dict:
        names = [
            "mode",
            "backend",
            "model_path",
            "model_manifest_path",
            "detector_enabled",
            "enable_objects",
            "enable_tracking",
            "tracking_enabled",
            "publish_debug_image",
            "debug_image_topic",
            "debug_image_max_hz",
            "input_stale_sec",
            "status_topic",
            "detections_topic",
            "objects_topic",
            "rgb_topic",
            "depth_topic",
            "camera_info_topic",
            "target_classes",
            "inference_rate_hz",
            "pending_frames",
            "ort_threads",
            "model_input_size",
            "confidence_threshold",
            "nms_iou_threshold",
            "max_detections",
            "status_rate_hz",
            "output_frame_policy",
            "sync_tolerance_sec",
            "sync_wait_sec",
            "sync_queue_size",
            "max_observation_age_sec",
            "min_depth_m",
            "max_depth_m",
            "mask_erode_kernel",
            "depth_patch_size",
            "min_patch_pixels",
            "min_valid_depth_fraction",
            "max_depth_mad_m",
            "max_depth_spread_m",
            "tracker_match_iou",
            "tracker_confirm_hits",
            "tracker_lost_timeout_sec",
            "video_device",
            "image_frame_id",
            "camera_contract",
        ]
        return {name: self.get_parameter(name).value for name in names}

    def _init_skeleton(self) -> None:
        enabled = any(
            as_bool(self.get_parameter(name).value)
            for name in (
                "detector_enabled",
                "enable_objects",
                "enable_tracking",
                "tracking_enabled",
                "publish_debug_image",
            )
        )
        if enabled or self.get_parameter("backend").value != "unconfigured":
            raise ValueError(
                "Inference, objects, tracking and debug rendering are not active "
                "in skeleton mode"
            )
        self._implementation_status = "SKELETON_ONLY"
        self._camera_contract = CAMERA_CONTRACT_NOT_RUN
        self.get_logger().warning(
            "SKELETON_ONLY: no camera subscriptions, inference, object output or control; "
            "use mode:=v1_ros for DEV webcam/Image detection; "
            "enable_objects:=true only with v1_ros for V2 /objects; "
            "enable_tracking:=true only with v1_ros for V3 2D tracker"
        )

    def _init_v1_ros(self) -> None:
        # Fail fast on NumPy 2.x / missing ORT before opening cameras or models.
        check_numpy_opencv_compat()
        notes = check_v1_runtime_imports(require_opencv=False)
        for line in notes:
            self.get_logger().info(f"runtime_dep: {line}")

        raw = self._param_map()
        # Force documented contract label for this stage.
        if not str(raw.get("camera_contract", "")).strip() or str(
            raw.get("camera_contract")
        ) == CAMERA_CONTRACT_NOT_RUN:
            raw["camera_contract"] = "DEV_WEBCAM_ONLY / NOT_ZED"
        if not raw.get("detector_enabled"):
            raw["detector_enabled"] = True
        if raw.get("backend") in ("", "unconfigured"):
            raw["backend"] = "onnxruntime_cpu"
        cfg = vision_config_from_mapping(raw)

        try:
            from vision_perception_interfaces.msg import VisionDetectionArray
        except ImportError as exc:
            raise RuntimeError(
                "vision_perception_interfaces is required for v1_ros detections publish"
            ) from exc

        detections_topic = cfg.detections_topic
        self._detections_pub = self.create_publisher(
            VisionDetectionArray, detections_topic, 10
        )
        self._enable_objects = bool(cfg.enable_objects)
        self._enable_tracking = bool(cfg.enable_tracking or cfg.tracking_enabled)
        self._min_depth_m = float(cfg.min_depth_m)
        self._max_depth_m = float(cfg.max_depth_m)
        self._mask_erode_kernel = int(cfg.mask_erode_kernel)
        self._depth_patch_size = int(cfg.depth_patch_size)
        self._min_patch_pixels = int(cfg.min_patch_pixels)
        self._min_valid_depth_fraction = float(cfg.min_valid_depth_fraction)
        self._max_depth_mad_m = float(cfg.max_depth_mad_m)
        self._max_depth_spread_m = float(cfg.max_depth_spread_m)
        self._sync_queue_size = int(cfg.sync_queue_size)
        self._max_observation_age_sec = float(cfg.max_observation_age_sec)
        self._depth_topic = str(cfg.depth_topic)
        self._camera_info_topic = str(cfg.camera_info_topic)

        if self._enable_tracking:
            self._tracker = MultiObjectTracker(
                match_iou=float(cfg.tracker_match_iou),
                confirm_hits=int(cfg.tracker_confirm_hits),
                lost_timeout_sec=float(cfg.tracker_lost_timeout_sec),
            )
            self._tracking_session_id = self._tracker.tracking_session_id
            self.get_logger().warning(
                "V3 enable_tracking: per-class IoU tracker active "
                f"(match_iou={cfg.tracker_match_iou}, "
                f"confirm_hits={cfg.tracker_confirm_hits}, "
                f"lost_timeout_sec={cfg.tracker_lost_timeout_sec}); "
                "object_id only after confirmed match; ARM_READY=NO; "
                "no ReID / no predicted boxes as measurements"
            )

        if self._enable_objects:
            try:
                from vision_perception_interfaces.msg import VisionObjectArray
            except ImportError as exc:
                raise RuntimeError(
                    "vision_perception_interfaces is required for enable_objects"
                ) from exc
            objects_topic = cfg.objects_topic
            if not objects_topic.startswith("/dg/vision/"):
                raise ValueError("objects_topic must remain within /dg/vision/")
            self._objects_pub = self.create_publisher(
                VisionObjectArray, objects_topic, 10
            )
            self._object_output_active = True
            self._depth_buffer = DepthFrameBuffer(
                tolerance_sec=float(cfg.sync_tolerance_sec),
                max_size=int(cfg.sync_queue_size),
            )
            self._sync_gate = RgbDepthSyncGate(
                self._depth_buffer,
                sync_wait_sec=float(cfg.sync_wait_sec),
            )
            self._depth_sub = self.create_subscription(
                Image, cfg.depth_topic, self._on_depth, 10
            )
            self._info_sub = self.create_subscription(
                CameraInfo, cfg.camera_info_topic, self._on_camera_info, 10
            )
            # Poll awaiting RGB timeouts without blocking the executor.
            poll_hz = 50.0
            self._sync_poll_timer = self.create_timer(
                1.0 / poll_hz, self._poll_sync_gate
            )
            self.get_logger().warning(
                f"V2 enable_objects: depth={cfg.depth_topic}, "
                f"camera_info={cfg.camera_info_topic}, "
                f"sync_wait_sec={cfg.sync_wait_sec}, "
                f"sync_tolerance_sec={cfg.sync_tolerance_sec}, "
                f"publish {objects_topic}; unpaired/missing calib → "
                "position_valid=false (no forged 3D); ARM_READY=NO; "
                "orientation_valid=false; no grasp"
            )

        self._publish_debug = bool(cfg.publish_debug_image)
        if self._publish_debug:
            topic = cfg.debug_image_topic
            if not topic.startswith("/dg/vision/"):
                raise ValueError("debug_image_topic must remain within /dg/vision/")
            self._debug_pub = self.create_publisher(Image, topic, 1)
            self._debug_gate = DebugPublishGate(cfg.debug_image_max_hz)
            self.get_logger().warning(
                f"debug_image enabled on {topic} (max {cfg.debug_image_max_hz} Hz)"
            )

        self._engine = DetectionEngine.from_config(cfg)
        self._backend_name = str(cfg.backend)
        self._input_stale_sec = float(cfg.input_stale_sec)
        min_interval = 1.0 / float(cfg.inference_rate_hz)
        self._worker = LatestFrameWorker(
            self._process_pending_frame,
            min_interval_sec=min_interval,
        )
        self._worker.start()
        self._image_sub = self.create_subscription(
            Image, cfg.rgb_topic, self._on_image, 10
        )
        if self._enable_tracking:
            self._implementation_status = "V3_TRACKING_DEV"
        elif self._enable_objects:
            self._implementation_status = "V2_OBJECTS_DEV"
        else:
            self._implementation_status = "V1_ROS_DEV_WEBCAM"
        self._camera_contract = str(cfg.camera_contract)
        self._inference_active = True
        self._camera_subscriptions_active = True
        objects_note = (
            f"; objects={cfg.objects_topic}" if self._enable_objects else "; no /objects"
        )
        tracking_note = "; tracking=on" if self._enable_tracking else "; tracking=off"
        self.get_logger().warning(
            f"v1_ros DEV_WEBCAM_ONLY / NOT_ZED: subscribing {cfg.rgb_topic}, "
            f"publishing {detections_topic}{objects_note}{tracking_note}; "
            "no ZED SDK start, no cmd_vel; "
            "empty detections=[] is healthy for blank fake frames; ARM_READY=NO"
        )

    def _on_depth(self, msg: Image) -> None:
        if self._sync_gate is None:
            return
        try:
            frame = decode_depth_msg(msg)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"depth decode failed: {exc}")
            return
        self._depth_frames_received += 1
        synced = self._sync_gate.on_depth(frame)
        if synced is not None:
            self._submit_synced(synced)

    def _on_camera_info(self, msg: CameraInfo) -> None:
        try:
            calib = camera_calibration_from_info_msg(msg)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"CameraInfo rejected: {exc}")
            return
        with self._calib_lock:
            prev = self._calibration
            if prev is not None and prev.calibration_id != calib.calibration_id:
                # Calibration change: clear depth pairing + tracker session.
                if self._depth_buffer is not None:
                    self._depth_buffer.clear()
                if self._sync_gate is not None:
                    self._sync_gate.clear()
                if self._tracker is not None:
                    self._tracking_session_id = self._tracker.reset_session(
                        reason="calibration_change"
                    )
                self.get_logger().warning(
                    "CameraInfo calibration_id changed; depth buffer and tracks cleared"
                )
            self._calibration = calib
            self._camera_info_received = True

    def _snapshot_calibration(self) -> Optional[CameraCalibration]:
        with self._calib_lock:
            return self._calibration

    def _submit_synced(self, synced: SyncedPair[DecodedImage]) -> None:
        if self._worker is None:
            return
        depth = synced.depth
        pair_reason = synced.pair_reason
        pair_skew = synced.pair_skew_sec
        calib = self._snapshot_calibration()
        if pair_reason == "OK" and calib is None:
            # Paired depth but no CameraInfo yet — do not forge XYZ.
            pair_reason = "DEPTH_UNPAIRED"
            depth = None
        self._worker.submit(
            PendingRgbJob(
                decoded=synced.payload,
                depth=depth,
                pair_skew_sec=pair_skew,
                pair_reason=pair_reason,
                calibration=calib,
            )
        )

    def _poll_sync_gate(self) -> None:
        if self._sync_gate is None:
            return
        synced = self._sync_gate.poll(time.monotonic())
        if synced is not None:
            self._submit_synced(synced)

    def _on_image(self, msg: Image) -> None:
        self._frames_received += 1
        self._last_input_mono = time.monotonic()
        self._stale_cleared = False
        if self._worker is None:
            return
        # Decode off the worker to keep invalid encodings out of the queue early.
        try:
            decoded = decode_sensor_image_msg(msg)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"image decode failed: {exc}")
            return

        if self._enable_objects and self._sync_gate is not None:
            # Hold RGB until matching depth arrives (or sync_wait_sec timeout).
            synced = self._sync_gate.on_rgb(
                decoded,
                stamp_sec=decoded.header.stamp_sec,
                stamp_nanosec=decoded.header.stamp_nanosec,
                now_mono=time.monotonic(),
            )
            if synced is not None:
                self._submit_synced(synced)
            return

        self._worker.submit(
            PendingRgbJob(
                decoded=decoded,
                depth=None,
                pair_skew_sec=None,
                pair_reason="DEPTH_UNPAIRED",
                calibration=None,
            )
        )

    def _process_pending_frame(self, job: Any) -> None:
        if self._engine is None or self._detections_pub is None:
            return
        if isinstance(job, PendingRgbJob):
            decoded = job.decoded
            depth = job.depth
            pair_skew = job.pair_skew_sec
            pair_reason = job.pair_reason
            calib = job.calibration
        else:
            # Backward-compatible if a bare DecodedImage is submitted.
            decoded = job
            depth = None
            pair_skew = None
            pair_reason = "DEPTH_UNPAIRED"
            calib = None

        # Plan §9: never publish observations older than max_observation_age_sec.
        now_sec = self.get_clock().now().nanoseconds * 1e-9
        if is_observation_too_old(
            decoded.header.stamp_sec,
            decoded.header.stamp_nanosec,
            now_sec=now_sec,
            max_observation_age_sec=self._max_observation_age_sec,
        ):
            self._observations_dropped_age += 1
            return

        calib_id = calib.calibration_id if calib is not None else ""
        t0 = time.monotonic()
        batch = self._engine.process_rgb_array(
            decoded.rgb,
            frame_id=decoded.header.frame_id,
            stamp_sec=decoded.header.stamp_sec,
            stamp_nanosec=decoded.header.stamp_nanosec,
            source_kind="LIVE_CAMERA",
            calibration_id=calib_id,
        )
        self._last_inference_ms = (time.monotonic() - t0) * 1000.0
        self._last_observation_id = int(batch.key.observation_id)
        self._last_detection_count = len(batch.detections)
        self._last_source_kind = batch.key.source_kind
        self._last_calibration_id = batch.key.calibration_id
        message = try_build_vision_detection_array_msg(batch)
        self._detections_pub.publish(message)
        self._maybe_publish_debug(decoded.rgb, batch)

        track_assignments = ()
        tracking_session_id = ""
        if self._enable_tracking and self._tracker is not None:
            stamp = stamp_sec_from_parts(
                batch.key.source_stamp_sec, batch.key.source_stamp_nanosec
            )
            track_assignments = self._tracker.update(
                batch.detections,
                stamp_sec=stamp,
                calibration_id=calib_id or batch.key.calibration_id,
            )
            tracking_session_id = self._tracker.tracking_session_id
            self._tracking_session_id = tracking_session_id

        if self._enable_objects and self._objects_pub is not None:
            objects = build_object_batch(
                batch,
                depth=depth,
                calibration=calib,
                pair_skew_sec=pair_skew,
                pair_reason=pair_reason,
                min_depth_m=self._min_depth_m,
                max_depth_m=self._max_depth_m,
                tracking_session_id=tracking_session_id,
                mask_erode_kernel=self._mask_erode_kernel,
                depth_patch_size=self._depth_patch_size,
                min_patch_pixels=self._min_patch_pixels,
                min_valid_depth_fraction=self._min_valid_depth_fraction,
                max_depth_mad_m=self._max_depth_mad_m,
                max_depth_spread_m=self._max_depth_spread_m,
            )
            if track_assignments:
                objects = apply_track_assignments(
                    objects,
                    track_assignments,
                    tracking_session_id=tracking_session_id,
                )
            self._last_objects_count = len(objects.objects)
            self._last_position_valid_count = sum(
                1 for o in objects.objects if o.position_valid
            )
            self._last_pair_reason = objects.pair_reason
            self._last_pair_skew_sec = objects.pair_skew_sec
            if objects.calibration_id:
                self._last_calibration_id = objects.calibration_id
            self._objects_pub.publish(try_build_vision_object_array_msg(objects))

    def _maybe_publish_debug(self, rgb, batch) -> None:
        if not self._publish_debug or self._debug_pub is None or self._debug_gate is None:
            return
        if not self._debug_gate.allow():
            return
        overlay = draw_detections_rgb(rgb, batch.detections)
        fields = encode_rgb8_image_fields(
            overlay,
            frame_id=batch.key.frame_id,
            stamp_sec=batch.key.source_stamp_sec,
            stamp_nanosec=batch.key.source_stamp_nanosec,
        )
        msg = Image()
        self._debug_pub.publish(_fill_sensor_image_msg(msg, fields))

    def _last_input_age_sec(self) -> float:
        if self._last_input_mono is None:
            return time.monotonic() - self._started_mono
        return time.monotonic() - self._last_input_mono

    def _publish_status(self):
        message = DiagnosticArray()
        message.header.stamp = self.get_clock().now().to_msg()
        status = DiagnosticStatus()
        status.name = "dg/vision/node"
        if self._mode == "skeleton":
            # Humble: DiagnosticStatus.level is byte → length-1 bytes, not int.
            status.level = as_diagnostic_level_byte(DiagnosticStatus.WARN)
            status.message = "SKELETON_ONLY"
            fields = {
                "mode": self._mode,
                "implementation_status": self._implementation_status,
                "camera_subscriptions_active": "false",
                "camera_contract": self._camera_contract,
                "backend": "unconfigured",
                "source_session_id": "",
                "inference_active": "false",
                "tracking_active": "false",
                "tracking_session_id": "",
                "object_output_active": "false",
                "enable_objects": "false",
                "enable_tracking": "false",
                "control_output_active": "false",
                "arm_ready": "NO",
                "publish_debug_image": "false",
                "v1_detections_interface": "VisionDetectionArray",
                "v2_objects_interface": "VisionObjectArray",
            }
        else:
            dropped = self._worker.dropped if self._worker is not None else 0
            processed = self._worker.processed if self._worker is not None else 0
            last_error = self._worker.last_error if self._worker is not None else ""
            age = self._last_input_age_sec()
            session_id = (
                self._engine.source_session_id if self._engine is not None else ""
            )
            # STALE: drop pending frames + tracks once; do not keep replaying old work.
            if (
                is_input_stale(age, self._input_stale_sec)
                and self._worker is not None
                and not self._stale_cleared
            ):
                self._worker.clear_pending()
                if self._tracker is not None:
                    self._tracking_session_id = self._tracker.reset_session(
                        reason="stale"
                    )
                self._stale_cleared = True
            level, msg, fields = compose_v1_ros_diagnostic(
                frames_received=self._frames_received,
                frames_processed=processed,
                frames_dropped=dropped,
                last_observation_id=self._last_observation_id,
                last_detection_count=self._last_detection_count,
                last_worker_error=last_error or "",
                camera_contract=self._camera_contract,
                rgb_topic=str(self.get_parameter("rgb_topic").value),
                depth_topic=self._depth_topic,
                camera_info_topic=self._camera_info_topic,
                source_session_id=session_id,
                backend=self._backend_name,
                source_kind=self._last_source_kind,
                last_input_age_sec=age,
                input_stale_sec=self._input_stale_sec,
                publish_debug_image=self._publish_debug,
                last_inference_ms=self._last_inference_ms,
                calibration_id=self._last_calibration_id,
                enable_objects=self._enable_objects,
                object_output_active=self._object_output_active,
                enable_tracking=self._enable_tracking,
                tracking_active=self._enable_tracking,
                tracking_session_id=self._tracking_session_id,
                last_objects_count=self._last_objects_count,
                last_position_valid_count=self._last_position_valid_count,
                last_pair_reason=self._last_pair_reason,
                last_pair_skew_sec=self._last_pair_skew_sec,
                depth_frames_received=self._depth_frames_received,
                camera_info_received=self._camera_info_received,
                observations_dropped_age=self._observations_dropped_age,
                max_observation_age_sec=self._max_observation_age_sec,
            )
            status.level = as_diagnostic_level_byte(level)
            status.message = msg
            self._implementation_status = msg
        status.values = [KeyValue(key=key, value=value) for key, value in fields.items()]
        message.status = [status]
        self._status_publisher.publish(message)

    def destroy_node(self):
        if self._sync_poll_timer is not None:
            self._sync_poll_timer.cancel()
            self._sync_poll_timer = None
        if self._sync_gate is not None:
            self._sync_gate.clear()
        if self._worker is not None:
            self._worker.clear_pending()
            self._worker.stop()
            self._worker = None
        if self._tracker is not None:
            self._tracker.clear()
            self._tracker = None
        if self._depth_buffer is not None:
            self._depth_buffer.clear()
        super().destroy_node()


def main(args=None):
    """Run skeleton or v1_ros; unsupported configuration exits non-zero."""
    rclpy.init(args=args)
    node = None
    exit_code = 0
    try:
        node = VisionPerceptionNode()
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    except (ValueError, RuntimeError, FileNotFoundError, OSError) as exc:
        hint = ""
        text = str(exc)
        if "model_path" in text or "model manifest" in text or "model file" in text:
            hint = (
                " Hint: v1_ros needs absolute local paths "
                "model_path:=/ABS/yolo11n-seg.onnx "
                "model_manifest_path:=/ABS/model_manifest.json "
                "(no auto-download; weights are not in git). "
                "See share/vision_perception/examples/model_manifest.template.json"
            )
        print(f"[vision_perception_node] FATAL: {exc}{hint}", file=sys.stderr)
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
