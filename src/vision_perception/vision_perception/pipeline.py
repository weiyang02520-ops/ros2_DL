"""Compose preprocess → ONNX → postprocess for offline / v1_ros detection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from vision_perception.config import VisionConfig, vision_config_from_mapping
from vision_perception.image_io import (
    letterbox_rgb,
    letterbox_to_nchw_float32,
    load_image_file_rgb,
)
from vision_perception.message_mapping import detection_batch_to_dict
from vision_perception.onnx_backend import OnnxSession, create_onnx_session, run_onnx
from vision_perception.postprocess import decode_yolo11_seg_boxes
from vision_perception.types import (
    SOURCE_KIND_FILE,
    SOURCE_KIND_LIVE,
    DetectionBatch,
    FrameKey,
)


@dataclass
class DetectionEngine:
    """Shared engine for offline files and v1_ros Image subscription path."""

    config: VisionConfig
    session: OnnxSession
    source_session_id: str
    default_source_kind: str
    _next_observation_id: int = 1

    @classmethod
    def from_config(cls, config: VisionConfig) -> "DetectionEngine":
        if config.mode not in {"offline", "v1_ros"}:
            raise ValueError("DetectionEngine requires mode=offline or mode=v1_ros")
        session = create_onnx_session(
            model_path=config.model_path,
            manifest_path=config.model_manifest_path,
            ort_threads=config.ort_threads,
        )
        source_kind = SOURCE_KIND_FILE if config.mode == "offline" else SOURCE_KIND_LIVE
        return cls(
            config=config,
            session=session,
            source_session_id=str(uuid.uuid4()),
            default_source_kind=source_kind,
        )

    def process_rgb_array(
        self,
        image_rgb: np.ndarray,
        *,
        source_image_id: str = "",
        frame_id: str = "",
        source_kind: Optional[str] = None,
        stamp_sec: int = 0,
        stamp_nanosec: int = 0,
        calibration_id: str = "",
    ) -> DetectionBatch:
        canvas, meta = letterbox_rgb(image_rgb, model_size=self.config.model_input_size)
        tensor = letterbox_to_nchw_float32(canvas)
        output0, output1 = run_onnx(self.session, tensor)
        class_id_to_name = self.session.manifest.class_id_to_name()
        detections = decode_yolo11_seg_boxes(
            output0=output0,
            letterbox=meta,
            class_id_to_name=class_id_to_name,
            confidence_threshold=self.config.confidence_threshold,
            nms_iou_threshold=self.config.nms_iou_threshold,
            max_detections=self.config.max_detections,
            allowed_classes=self.config.target_classes,
            output1=output1,
            mask_threshold=self.config.mask_threshold,
        )
        observation_id = self._next_observation_id
        self._next_observation_id += 1
        key = FrameKey(
            source_session_id=self.source_session_id,
            observation_id=observation_id,
            source_kind=source_kind or self.default_source_kind,
            calibration_id=calibration_id,
            frame_id=frame_id,
            source_stamp_sec=int(stamp_sec),
            source_stamp_nanosec=int(stamp_nanosec),
            source_image_id=source_image_id,
        )
        return DetectionBatch(
            key=key,
            detections=tuple(detections),
            image_width=int(image_rgb.shape[1]),
            image_height=int(image_rgb.shape[0]),
        )

    def process_image_file(self, path: str) -> DetectionBatch:
        image = load_image_file_rgb(path)
        return self.process_rgb_array(
            image,
            source_image_id=str(Path(path).name),
            frame_id="",
            source_kind=SOURCE_KIND_FILE,
        )


# Backward-compatible alias used by older offline CLI imports.
OfflineEngine = DetectionEngine


def run_offline_on_paths(
    image_paths: Sequence[str],
    *,
    model_path: str,
    manifest_path: str,
    confidence_threshold: float = 0.35,
    nms_iou_threshold: float = 0.45,
    max_detections: int = 20,
    ort_threads: int = 2,
) -> List[dict]:
    """Convenience helper used by the CLI."""
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
            "detector_enabled": True,
        }
    )
    engine = DetectionEngine.from_config(config)
    results = []
    for path in image_paths:
        batch = engine.process_image_file(path)
        results.append(detection_batch_to_dict(batch))
    return results


def process_array_with_synthetic_output0(
    image_rgb: np.ndarray,
    output0: np.ndarray,
    *,
    class_id_to_name: Optional[dict] = None,
    confidence_threshold: float = 0.35,
    nms_iou_threshold: float = 0.45,
    max_detections: int = 20,
    source_image_id: str = "synthetic",
    source_kind: str = SOURCE_KIND_FILE,
    stamp_sec: int = 0,
    stamp_nanosec: int = 0,
    frame_id: str = "",
    output1: Optional[np.ndarray] = None,
    mask_threshold: float = 0.5,
) -> DetectionBatch:
    """Detection-path postprocess using a caller-provided model tensor (no ORT)."""
    _canvas, meta = letterbox_rgb(image_rgb, model_size=640)
    mapping = class_id_to_name or {39: "bottle", 41: "cup"}
    detections = decode_yolo11_seg_boxes(
        output0=output0,
        letterbox=meta,
        class_id_to_name=mapping,
        confidence_threshold=confidence_threshold,
        nms_iou_threshold=nms_iou_threshold,
        max_detections=max_detections,
        output1=output1,
        mask_threshold=mask_threshold,
    )
    key = FrameKey(
        source_session_id="synthetic-session",
        observation_id=1,
        source_kind=source_kind,
        source_image_id=source_image_id,
        frame_id=frame_id,
        source_stamp_sec=stamp_sec,
        source_stamp_nanosec=stamp_nanosec,
    )
    return DetectionBatch(
        key=key,
        detections=tuple(detections),
        image_width=int(image_rgb.shape[1]),
        image_height=int(image_rgb.shape[0]),
    )
