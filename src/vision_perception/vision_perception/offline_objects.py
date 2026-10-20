"""Offline V2 objects path: RGB file + depth array + synthetic CameraInfo.

No ROS, no ZED SDK, no grasp. Used by vision_offline_objects CLI and unit tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from vision_perception.config import vision_config_from_mapping
from vision_perception.depth_io import (
    CameraCalibration,
    DepthFrame,
    camera_calibration_from_pinhole,
)
from vision_perception.image_io import load_image_file_rgb
from vision_perception.message_mapping import (
    detection_batch_to_dict,
    object_batch_to_dict,
)
from vision_perception.objects_pipeline import (
    ObjectBatch,
    apply_track_assignments,
    build_object_batch,
)
from vision_perception.pipeline import DetectionEngine
from vision_perception.tracker import (
    DEFAULT_CONFIRM_HITS,
    DEFAULT_LOST_TIMEOUT_SEC,
    DEFAULT_MATCH_IOU,
    MultiObjectTracker,
)


def load_depth_npy(path: str) -> np.ndarray:
    array = np.load(str(path))
    if array.ndim != 2:
        raise ValueError(f"depth npy must be HxW metres, got {array.shape}")
    depth = np.asarray(array, dtype=np.float32)
    depth[~np.isfinite(depth)] = np.nan
    depth[depth <= 0] = np.nan
    return depth


def make_synthetic_calibration(
    *,
    width: int,
    height: int,
    fx: float,
    fy: float,
    cx: Optional[float] = None,
    cy: Optional[float] = None,
    frame_id: str = "offline_optical_frame",
) -> CameraCalibration:
    return camera_calibration_from_pinhole(
        width=width,
        height=height,
        fx=fx,
        fy=fy,
        cx=float(width / 2.0 if cx is None else cx),
        cy=float(height / 2.0 if cy is None else cy),
        frame_id=frame_id,
    )


def run_offline_objects_on_paths(
    image_paths: Sequence[str],
    depth_paths: Sequence[str],
    *,
    model_path: str,
    manifest_path: str,
    fx: float = 500.0,
    fy: float = 500.0,
    cx: Optional[float] = None,
    cy: Optional[float] = None,
    min_depth_m: float = 0.5,
    max_depth_m: float = 1.5,
    confidence_threshold: float = 0.35,
    nms_iou_threshold: float = 0.45,
    max_detections: int = 20,
    ort_threads: int = 2,
    mask_threshold: float = 0.5,
    frame_id: str = "offline_optical_frame",
    enable_tracking: bool = False,
    tracker_match_iou: float = DEFAULT_MATCH_IOU,
    tracker_confirm_hits: int = DEFAULT_CONFIRM_HITS,
    tracker_lost_timeout_sec: float = DEFAULT_LOST_TIMEOUT_SEC,
    mask_erode_kernel: int = 3,
    depth_patch_size: int = 7,
    min_patch_pixels: int = 25,
    min_valid_depth_fraction: float = 0.60,
    max_depth_mad_m: float = 0.020,
    max_depth_spread_m: float = 0.050,
) -> List[Dict[str, Any]]:
    """Detect 2D then build ObjectBatch per (image, depth) pair.

    Optional ``enable_tracking`` runs the pure MultiObjectTracker across the
    file sequence (does not require ROS ``mode=v1_ros`` config gate).
    """
    if len(image_paths) != len(depth_paths):
        raise ValueError(
            f"image/depth count mismatch: {len(image_paths)} vs {len(depth_paths)}"
        )
    config = vision_config_from_mapping(
        {
            "mode": "offline",
            "backend": "onnxruntime_cpu",
            "model_path": model_path,
            "model_manifest_path": manifest_path,
            "confidence_threshold": confidence_threshold,
            "nms_iou_threshold": nms_iou_threshold,
            "max_detections": max_detections,
            "ort_threads": ort_threads,
            "mask_threshold": mask_threshold,
            "min_depth_m": min_depth_m,
            "max_depth_m": max_depth_m,
            "detector_enabled": True,
        }
    )
    engine = DetectionEngine.from_config(config)
    tracker: Optional[MultiObjectTracker] = None
    if enable_tracking:
        tracker = MultiObjectTracker(
            match_iou=float(tracker_match_iou),
            confirm_hits=int(tracker_confirm_hits),
            lost_timeout_sec=float(tracker_lost_timeout_sec),
        )
    results: List[Dict[str, Any]] = []
    for frame_i, (image_path, depth_path) in enumerate(zip(image_paths, depth_paths)):
        rgb = load_image_file_rgb(image_path)
        depth_m = load_depth_npy(depth_path)
        if depth_m.shape[:2] != rgb.shape[:2]:
            raise ValueError(
                f"depth shape {depth_m.shape} != rgb HxW {rgb.shape[:2]} "
                f"for {image_path}"
            )
        h, w = depth_m.shape[:2]
        calib = make_synthetic_calibration(
            width=w, height=h, fx=fx, fy=fy, cx=cx, cy=cy, frame_id=frame_id
        )
        batch = engine.process_rgb_array(
            rgb,
            source_image_id=str(Path(image_path).name),
            frame_id=frame_id,
            calibration_id=calib.calibration_id,
            stamp_sec=frame_i,
            stamp_nanosec=0,
        )
        depth_frame = DepthFrame(
            depth_m=depth_m,
            stamp_sec=frame_i,
            stamp_nanosec=0,
            frame_id=frame_id,
            encoding="32FC1",
        )
        tracking_session_id = ""
        track_assignments = ()
        if tracker is not None:
            track_assignments = tracker.update(
                batch.detections,
                stamp_sec=float(frame_i),
                calibration_id=calib.calibration_id,
            )
            tracking_session_id = tracker.tracking_session_id
        objects = build_object_batch(
            batch,
            depth=depth_frame,
            calibration=calib,
            pair_skew_sec=0.0,
            pair_reason="OK",
            min_depth_m=min_depth_m,
            max_depth_m=max_depth_m,
            tracking_session_id=tracking_session_id,
            mask_erode_kernel=mask_erode_kernel,
            depth_patch_size=depth_patch_size,
            min_patch_pixels=min_patch_pixels,
            min_valid_depth_fraction=min_valid_depth_fraction,
            max_depth_mad_m=max_depth_mad_m,
            max_depth_spread_m=max_depth_spread_m,
        )
        if track_assignments:
            objects = apply_track_assignments(
                objects,
                track_assignments,
                tracking_session_id=tracking_session_id,
            )
        results.append(
            {
                "detections": detection_batch_to_dict(batch),
                "objects": object_batch_to_dict(objects),
                "source_image_id": batch.key.source_image_id,
                "depth_path": str(Path(depth_path).name),
            }
        )
    return results


def summarize_object_batches(entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Functional coverage summary — never claims V2_ACCURACY PASS without GT."""
    from vision_perception.evaluation import summarize_v2_object_coverage

    object_dicts = [entry["objects"] for entry in entries]
    return summarize_v2_object_coverage(object_dicts)
