"""Startup-only configuration helpers for the vision module.

Values mirror VISION_INTEGRATION_PLAN.md V4 defaults. Invalid config fails
loudly; nothing is silently corrected at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

from vision_perception.types import ALLOWED_CLASSES, ModelManifest


CAMERA_CONTRACT_NOT_RUN = "NOT_RUN"
CAMERA_CONTRACT_DEV_WEBCAM = "DEV_WEBCAM_ONLY"
CAMERA_CONTRACT_NOT_ZED = "NOT_ZED"


@dataclass(frozen=True)
class VisionConfig:
    mode: str = "skeleton"
    backend: str = "unconfigured"
    model_path: str = ""
    model_manifest_path: str = ""
    detector_enabled: bool = False
    # V2 gate: default false; true allowed only for mode=v1_ros (depth+/objects).
    enable_objects: bool = False
    # V3 gate: default false; true allowed only for mode=v1_ros (like enable_objects).
    enable_tracking: bool = False
    # Legacy synonym of enable_tracking (kept for existing YAML / tests).
    tracking_enabled: bool = False
    publish_debug_image: bool = False
    debug_image_topic: str = "/dg/vision/debug_image"
    debug_image_max_hz: float = 2.0
    input_stale_sec: float = 1.0
    status_topic: str = "/dg/vision/status"
    detections_topic: str = "/dg/vision/detections_2d"
    objects_topic: str = "/dg/vision/objects"
    # Dev default is local webcam topic; ZED names are reserved for a later stage.
    rgb_topic: str = "/dg/vision/webcam/image_raw"
    depth_topic: str = "/zed/zed_node/depth/depth_registered"
    camera_info_topic: str = "/zed/zed_node/rgb/color/rect/camera_info"
    target_classes: Tuple[str, ...] = ALLOWED_CLASSES
    inference_rate_hz: float = 5.0
    pending_frames: int = 1
    ort_threads: int = 2
    model_input_size: int = 640
    confidence_threshold: float = 0.35
    nms_iou_threshold: float = 0.45
    max_detections: int = 20
    mask_threshold: float = 0.5
    status_rate_hz: float = 1.0
    output_frame_policy: str = "input_optical_header"
    sync_tolerance_sec: float = 0.010
    # Plan §7.1: wait for depth after RGB before declaring DEPTH_UNPAIRED.
    sync_wait_sec: float = 0.100
    sync_queue_size: int = 10
    # Plan §9: drop outputs whose source stamp is older than this.
    max_observation_age_sec: float = 0.500
    min_depth_m: float = 0.5
    max_depth_m: float = 1.5
    # Plan §7.2 surface sampling (used when enable_objects=true).
    mask_erode_kernel: int = 3
    depth_patch_size: int = 7
    min_patch_pixels: int = 25
    min_valid_depth_fraction: float = 0.60
    max_depth_mad_m: float = 0.020
    max_depth_spread_m: float = 0.050
    # Plan §8 V3 tracker defaults (used only when enable_tracking=true).
    tracker_match_iou: float = 0.30
    tracker_confirm_hits: int = 3
    tracker_lost_timeout_sec: float = 0.70
    video_device: int = 0
    image_frame_id: str = "webcam_optical_frame"
    camera_contract: str = CAMERA_CONTRACT_NOT_RUN


DEFAULTS = VisionConfig()

# ROS vision_perception_node: skeleton (inert) or explicit v1_ros (RGB → detections).
# mode:=v1 (legacy) and offline remain rejected on the ROS node.
ROS_NODE_ALLOWED_MODES = frozenset({"skeleton", "v1_ros"})


def normalize_ros_node_mode(mode: Any) -> str:
    """Allow only skeleton / v1_ros for the ROS node; reject mode:=v1 and others."""
    normalized = str(mode).strip()
    if normalized not in ROS_NODE_ALLOWED_MODES:
        raise ValueError(
            f"Unsupported ROS mode={normalized!r}; allowed modes are "
            f"{sorted(ROS_NODE_ALLOWED_MODES)}. "
            "mode:='v1' is rejected. Offline files use vision_offline_detect."
        )
    return normalized


def require_ros_skeleton_mode(mode: Any) -> str:
    """Backward-compatible helper: accept skeleton only (used by older tests/docs)."""
    normalized = normalize_ros_node_mode(mode)
    if normalized != "skeleton":
        raise ValueError(
            f"Unsupported ROS mode={normalized!r}; only mode='skeleton' is allowed "
            "by this helper. Use normalize_ros_node_mode for v1_ros."
        )
    return normalized


def as_bool(value: Any) -> bool:
    """Coerce ROS/YAML/launch stringy bools; ``\"false\"`` is False."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


# Backward-compatible private alias.
_as_bool = as_bool


def _as_tuple_str(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ALLOWED_CLASSES
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return tuple(parts) if parts else ALLOWED_CLASSES
    return tuple(str(item) for item in value)


def _resolve_enable_tracking(data: Mapping[str, Any]) -> bool:
    """Accept enable_tracking or legacy tracking_enabled; reject disagreement."""
    has_new = "enable_tracking" in data
    has_old = "tracking_enabled" in data
    if has_new and has_old:
        if as_bool(data["enable_tracking"]) != as_bool(data["tracking_enabled"]):
            raise ValueError("enable_tracking and tracking_enabled disagree")
    if has_new:
        return as_bool(data["enable_tracking"])
    if has_old:
        return as_bool(data["tracking_enabled"])
    return False


def vision_config_from_mapping(raw: Mapping[str, Any] | None = None) -> VisionConfig:
    data: Dict[str, Any] = {} if raw is None else dict(raw)
    enable_tracking = _resolve_enable_tracking(data)
    cfg = VisionConfig(
        mode=str(data.get("mode", DEFAULTS.mode)),
        backend=str(data.get("backend", DEFAULTS.backend)),
        model_path=str(data.get("model_path", DEFAULTS.model_path)),
        model_manifest_path=str(data.get("model_manifest_path", DEFAULTS.model_manifest_path)),
        detector_enabled=_as_bool(data.get("detector_enabled", DEFAULTS.detector_enabled)),
        enable_objects=_as_bool(data.get("enable_objects", DEFAULTS.enable_objects)),
        enable_tracking=enable_tracking,
        tracking_enabled=enable_tracking,
        publish_debug_image=_as_bool(
            data.get("publish_debug_image", DEFAULTS.publish_debug_image)
        ),
        debug_image_topic=str(
            data.get("debug_image_topic", DEFAULTS.debug_image_topic)
        ),
        debug_image_max_hz=float(
            data.get("debug_image_max_hz", DEFAULTS.debug_image_max_hz)
        ),
        input_stale_sec=float(data.get("input_stale_sec", DEFAULTS.input_stale_sec)),
        status_topic=str(data.get("status_topic", DEFAULTS.status_topic)),
        detections_topic=str(data.get("detections_topic", DEFAULTS.detections_topic)),
        objects_topic=str(data.get("objects_topic", DEFAULTS.objects_topic)),
        rgb_topic=str(data.get("rgb_topic", DEFAULTS.rgb_topic)),
        depth_topic=str(data.get("depth_topic", DEFAULTS.depth_topic)),
        camera_info_topic=str(data.get("camera_info_topic", DEFAULTS.camera_info_topic)),
        target_classes=_as_tuple_str(data.get("target_classes", DEFAULTS.target_classes)),
        inference_rate_hz=float(data.get("inference_rate_hz", DEFAULTS.inference_rate_hz)),
        pending_frames=int(data.get("pending_frames", DEFAULTS.pending_frames)),
        ort_threads=int(data.get("ort_threads", DEFAULTS.ort_threads)),
        model_input_size=int(data.get("model_input_size", DEFAULTS.model_input_size)),
        confidence_threshold=float(
            data.get("confidence_threshold", DEFAULTS.confidence_threshold)
        ),
        nms_iou_threshold=float(data.get("nms_iou_threshold", DEFAULTS.nms_iou_threshold)),
        max_detections=int(data.get("max_detections", DEFAULTS.max_detections)),
        mask_threshold=float(data.get("mask_threshold", DEFAULTS.mask_threshold)),
        status_rate_hz=float(data.get("status_rate_hz", DEFAULTS.status_rate_hz)),
        output_frame_policy=str(
            data.get("output_frame_policy", DEFAULTS.output_frame_policy)
        ),
        sync_tolerance_sec=float(
            data.get("sync_tolerance_sec", DEFAULTS.sync_tolerance_sec)
        ),
        sync_wait_sec=float(data.get("sync_wait_sec", DEFAULTS.sync_wait_sec)),
        sync_queue_size=int(data.get("sync_queue_size", DEFAULTS.sync_queue_size)),
        max_observation_age_sec=float(
            data.get("max_observation_age_sec", DEFAULTS.max_observation_age_sec)
        ),
        min_depth_m=float(data.get("min_depth_m", DEFAULTS.min_depth_m)),
        max_depth_m=float(data.get("max_depth_m", DEFAULTS.max_depth_m)),
        mask_erode_kernel=int(
            data.get("mask_erode_kernel", DEFAULTS.mask_erode_kernel)
        ),
        depth_patch_size=int(data.get("depth_patch_size", DEFAULTS.depth_patch_size)),
        min_patch_pixels=int(data.get("min_patch_pixels", DEFAULTS.min_patch_pixels)),
        min_valid_depth_fraction=float(
            data.get("min_valid_depth_fraction", DEFAULTS.min_valid_depth_fraction)
        ),
        max_depth_mad_m=float(data.get("max_depth_mad_m", DEFAULTS.max_depth_mad_m)),
        max_depth_spread_m=float(
            data.get("max_depth_spread_m", DEFAULTS.max_depth_spread_m)
        ),
        tracker_match_iou=float(
            data.get("tracker_match_iou", DEFAULTS.tracker_match_iou)
        ),
        tracker_confirm_hits=int(
            data.get("tracker_confirm_hits", DEFAULTS.tracker_confirm_hits)
        ),
        tracker_lost_timeout_sec=float(
            data.get("tracker_lost_timeout_sec", DEFAULTS.tracker_lost_timeout_sec)
        ),
        video_device=int(data.get("video_device", DEFAULTS.video_device)),
        image_frame_id=str(data.get("image_frame_id", DEFAULTS.image_frame_id)),
        camera_contract=str(data.get("camera_contract", DEFAULTS.camera_contract)),
    )
    validate_vision_config(cfg)
    return cfg


def validate_vision_config(cfg: VisionConfig) -> None:
    if cfg.mode not in {"skeleton", "offline", "v1_ros"}:
        raise ValueError(
            f"Unsupported mode={cfg.mode!r}; allowed modes are "
            "'skeleton', 'offline', 'v1_ros'"
        )
    if not cfg.status_topic.startswith("/dg/vision/"):
        raise ValueError("status_topic must remain within /dg/vision/")
    if not cfg.detections_topic.startswith("/dg/vision/"):
        raise ValueError("detections_topic must remain within /dg/vision/")
    if not cfg.objects_topic.startswith("/dg/vision/"):
        raise ValueError("objects_topic must remain within /dg/vision/")
    if not cfg.debug_image_topic.startswith("/dg/vision/"):
        raise ValueError("debug_image_topic must remain within /dg/vision/")
    if cfg.inference_rate_hz <= 0:
        raise ValueError("inference_rate_hz must be > 0")
    if cfg.debug_image_max_hz <= 0 or cfg.debug_image_max_hz > 2.0:
        raise ValueError("debug_image_max_hz must be in (0, 2]")
    if cfg.input_stale_sec <= 0:
        raise ValueError("input_stale_sec must be > 0")
    if cfg.pending_frames != 1:
        raise ValueError("pending_frames must be 1 in V1")
    if cfg.ort_threads < 1:
        raise ValueError("ort_threads must be >= 1")
    if cfg.model_input_size != 640:
        raise ValueError("model_input_size must be 640 in V1")
    if not (0.0 < cfg.confidence_threshold <= 1.0):
        raise ValueError("confidence_threshold must be in (0, 1]")
    if not (0.0 < cfg.nms_iou_threshold <= 1.0):
        raise ValueError("nms_iou_threshold must be in (0, 1]")
    if cfg.max_detections < 1 or cfg.max_detections > 20:
        raise ValueError("max_detections must be in [1, 20]")
    for name in cfg.target_classes:
        if name not in ALLOWED_CLASSES:
            raise ValueError(f"target_classes contains unsupported class {name!r}")
    if cfg.min_depth_m <= 0 or cfg.max_depth_m <= cfg.min_depth_m:
        raise ValueError("depth range must satisfy 0 < min_depth_m < max_depth_m")
    if cfg.sync_tolerance_sec <= 0:
        raise ValueError("sync_tolerance_sec must be > 0")
    if cfg.sync_wait_sec < 0:
        raise ValueError("sync_wait_sec must be >= 0")
    if cfg.sync_queue_size < 1:
        raise ValueError("sync_queue_size must be >= 1")
    if cfg.max_observation_age_sec <= 0:
        raise ValueError("max_observation_age_sec must be > 0")
    if cfg.mask_erode_kernel < 1 or cfg.mask_erode_kernel % 2 == 0:
        raise ValueError("mask_erode_kernel must be odd and >= 1")
    if cfg.depth_patch_size < 1 or cfg.depth_patch_size % 2 == 0:
        raise ValueError("depth_patch_size must be odd and >= 1")
    if cfg.min_patch_pixels < 1:
        raise ValueError("min_patch_pixels must be >= 1")
    if not (0.0 < cfg.min_valid_depth_fraction <= 1.0):
        raise ValueError("min_valid_depth_fraction must be in (0, 1]")
    if cfg.max_depth_mad_m <= 0:
        raise ValueError("max_depth_mad_m must be > 0")
    if cfg.max_depth_spread_m <= 0:
        raise ValueError("max_depth_spread_m must be > 0")
    if not (0.0 < cfg.tracker_match_iou <= 1.0):
        raise ValueError("tracker_match_iou must be in (0, 1]")
    if cfg.tracker_confirm_hits < 1:
        raise ValueError("tracker_confirm_hits must be >= 1")
    if cfg.tracker_lost_timeout_sec <= 0:
        raise ValueError("tracker_lost_timeout_sec must be > 0")
    if cfg.mode == "skeleton":
        if (
            cfg.detector_enabled
            or cfg.publish_debug_image
            or cfg.enable_objects
            or cfg.enable_tracking
            or cfg.tracking_enabled
        ):
            raise ValueError(
                "skeleton mode forbids enabling detector/debug/enable_objects/"
                "enable_tracking"
            )
        if cfg.backend != "unconfigured":
            raise ValueError("skeleton mode requires backend=unconfigured")
    if cfg.mode == "offline":
        if cfg.enable_objects:
            raise ValueError(
                "enable_objects=true is only allowed for mode=v1_ros "
                "(offline CLI stays 2D-only)"
            )
        if cfg.enable_tracking or cfg.tracking_enabled:
            raise ValueError(
                "enable_tracking=true is only allowed for mode=v1_ros "
                "(offline CLI stays 2D-only; use pure tracker helpers for sequences)"
            )
        if cfg.backend != "onnxruntime_cpu":
            raise ValueError("offline mode requires backend=onnxruntime_cpu")
        if not cfg.model_path:
            raise ValueError("offline mode requires model_path")
        if not cfg.model_manifest_path:
            raise ValueError("offline mode requires model_manifest_path")
    if cfg.mode == "v1_ros":
        if cfg.backend != "onnxruntime_cpu":
            raise ValueError("v1_ros mode requires backend=onnxruntime_cpu")
        if not cfg.model_path:
            raise ValueError("v1_ros mode requires model_path")
        if not cfg.model_manifest_path:
            raise ValueError("v1_ros mode requires model_manifest_path")
        if not cfg.detector_enabled:
            raise ValueError("v1_ros mode requires detector_enabled=true")
        if not cfg.rgb_topic:
            raise ValueError("v1_ros mode requires rgb_topic")
        if cfg.enable_objects:
            if not cfg.depth_topic:
                raise ValueError("enable_objects=true requires depth_topic")
            if not cfg.camera_info_topic:
                raise ValueError("enable_objects=true requires camera_info_topic")
        contract = cfg.camera_contract.upper()
        if "DEV_WEBCAM_ONLY" not in contract:
            raise ValueError(
                "v1_ros camera_contract must include DEV_WEBCAM_ONLY "
                "(ZED contract is not authorized in this stage)"
            )
        if "ZED" in contract and "NOT_ZED" not in contract and "NOT ZED" not in contract:
            raise ValueError(
                "v1_ros must not claim a ZED camera_contract; use DEV_WEBCAM_ONLY / NOT_ZED"
            )
    else:
        if cfg.enable_objects:
            raise ValueError(
                "enable_objects=true is only allowed for mode=v1_ros"
            )
        if cfg.enable_tracking or cfg.tracking_enabled:
            raise ValueError(
                "enable_tracking=true is only allowed for mode=v1_ros"
            )


def load_model_manifest(path: str) -> ModelManifest:
    """Load and validate model_manifest.json. Does not fetch weights."""
    import json
    from pathlib import Path

    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"model manifest not found: {manifest_path}")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = (
        "source",
        "onnx_sha256",
        "license",
        "input_name",
        "input_shape",
        "output0_shape",
        "output1_shape",
        "class_map",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"model manifest missing keys: {missing}")
    class_map = {str(k): int(v) for k, v in dict(raw["class_map"]).items()}
    for name in ALLOWED_CLASSES:
        if name not in class_map:
            raise ValueError(f"model manifest class_map missing required class {name!r}")
    if class_map["bottle"] != 39 or class_map["cup"] != 41:
        raise ValueError(
            "class_map must use COCO ids bottle=39 and cup=41 unless explicitly re-authorized"
        )
    return ModelManifest(
        source=str(raw["source"]),
        onnx_sha256=str(raw["onnx_sha256"]).lower(),
        license=str(raw["license"]),
        input_name=str(raw["input_name"]),
        input_shape=tuple(int(x) for x in raw["input_shape"]),
        output0_shape=tuple(int(x) for x in raw["output0_shape"]),
        output1_shape=tuple(int(x) for x in raw["output1_shape"]),
        class_map=class_map,
        weights_sha256=str(raw.get("weights_sha256", "")).lower(),
        export_tool_versions=dict(raw["export_tool_versions"])
        if raw.get("export_tool_versions")
        else None,
    )


def verify_file_sha256(path: str, expected: str) -> str:
    import hashlib
    from pathlib import Path

    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"model file not found: {file_path}")
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    actual = digest.hexdigest().lower()
    if expected and actual != expected.lower():
        raise ValueError(
            f"ONNX SHA256 mismatch for {file_path}: expected {expected}, got {actual}"
        )
    return actual


def validate_manifest_shapes(manifest: ModelManifest) -> None:
    if tuple(manifest.input_shape) != (1, 3, 640, 640):
        raise ValueError(f"unexpected input_shape={manifest.input_shape}")
    if tuple(manifest.output0_shape) != (1, 116, 8400):
        raise ValueError(
            f"unexpected output0_shape={manifest.output0_shape}; expected (1, 116, 8400)"
        )
    if tuple(manifest.output1_shape) != (1, 32, 160, 160):
        raise ValueError(
            f"unexpected output1_shape={manifest.output1_shape}; expected (1, 32, 160, 160)"
        )
    if manifest.input_name != "images":
        raise ValueError(f"unexpected input_name={manifest.input_name!r}; expected 'images'")
