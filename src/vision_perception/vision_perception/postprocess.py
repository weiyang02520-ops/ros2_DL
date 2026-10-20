"""YOLO11-seg box decode, optional mask reconstruct, class filter and NMS.

Operates on NumPy tensors only. Does not import Ultralytics or rclpy.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from vision_perception.image_io import restore_xyxy_from_letterbox
from vision_perception.mask_decode import reconstruct_instance_mask
from vision_perception.types import (
    ALLOWED_CLASSES,
    BoundingBox2D,
    Detection,
    LetterboxMeta,
    clip_box_to_image,
    sort_detections_deterministic,
    validate_class_name,
)


def box_iou_xyxy(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    if inter <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    denom = area_a + area_b - inter
    if denom <= 0.0:
        return 0.0
    return float(inter / denom)


def nms_per_class(
    boxes_xyxy: np.ndarray,
    scores: np.ndarray,
    class_ids: np.ndarray,
    iou_threshold: float,
) -> List[int]:
    """Greedy per-class NMS. Returns kept indices into the input arrays."""
    if boxes_xyxy.size == 0:
        return []
    keep: List[int] = []
    for class_id in sorted(set(int(x) for x in class_ids.tolist())):
        idxs = np.where(class_ids == class_id)[0]
        order = idxs[np.argsort(-scores[idxs])]
        selected: List[int] = []
        while order.size > 0:
            current = int(order[0])
            selected.append(current)
            if order.size == 1:
                break
            rest = order[1:]
            ious = np.array(
                [box_iou_xyxy(boxes_xyxy[current], boxes_xyxy[other]) for other in rest],
                dtype=np.float32,
            )
            order = rest[ious <= iou_threshold]
        keep.extend(selected)
    return sorted(keep)


def xywh_to_xyxy(xywh: np.ndarray) -> np.ndarray:
    x, y, w, h = xywh[..., 0], xywh[..., 1], xywh[..., 2], xywh[..., 3]
    return np.stack([x - w * 0.5, y - h * 0.5, x + w * 0.5, y + h * 0.5], axis=-1)


def decode_yolo11_seg_boxes(
    output0: np.ndarray,
    letterbox: LetterboxMeta,
    class_id_to_name: Dict[int, str],
    confidence_threshold: float = 0.35,
    nms_iou_threshold: float = 0.45,
    max_detections: int = 20,
    allowed_classes: Iterable[str] = ALLOWED_CLASSES,
    output1: Optional[np.ndarray] = None,
    mask_threshold: float = 0.5,
) -> List[Detection]:
    """Decode YOLO11n-seg output0=[1,116,8400] into original-image detections.

    Scores are treated as probabilities (no extra sigmoid). When ``output1``
    (mask prototypes) is provided, each kept detection may carry a binary
    instance mask (``mask_source=yolo_seg``); otherwise masks are omitted and
    V2 surface sampling falls back to bbox_fill.
    """
    if output0.ndim != 3:
        raise ValueError(f"output0 must be 3D, got shape={output0.shape}")
    if output0.shape[0] != 1 or output0.shape[1] != 116:
        raise ValueError(
            f"unexpected output0 layout {output0.shape}; expected (1, 116, N)"
        )

    # [1, 116, N] -> [N, 116]
    preds = np.transpose(output0[0], (1, 0))
    boxes_xywh = preds[:, 0:4]
    class_scores = preds[:, 4:84]
    mask_coeffs = preds[:, 84:116]

    class_ids = np.argmax(class_scores, axis=1).astype(np.int32)
    scores = class_scores[np.arange(class_scores.shape[0]), class_ids].astype(np.float32)

    allowed = set(allowed_classes)
    allowed_ids = {
        class_id
        for class_id, name in class_id_to_name.items()
        if name in allowed
    }
    if not allowed_ids:
        raise ValueError("class_id_to_name does not contain any allowed target class")

    keep_mask = (scores >= confidence_threshold) & np.isin(class_ids, list(allowed_ids))
    if not np.any(keep_mask):
        return []

    boxes_xywh = boxes_xywh[keep_mask]
    scores = scores[keep_mask]
    class_ids = class_ids[keep_mask]
    mask_coeffs = mask_coeffs[keep_mask]
    boxes_xyxy = xywh_to_xyxy(boxes_xywh)

    keep = nms_per_class(boxes_xyxy, scores, class_ids, nms_iou_threshold)
    detections: List[Detection] = []
    for index in keep:
        class_name = class_id_to_name[int(class_ids[index])]
        validate_class_name(class_name)
        x1, y1, x2, y2 = restore_xyxy_from_letterbox(
            float(boxes_xyxy[index, 0]),
            float(boxes_xyxy[index, 1]),
            float(boxes_xyxy[index, 2]),
            float(boxes_xyxy[index, 3]),
            letterbox,
        )
        clipped = clip_box_to_image(
            x1, y1, x2, y2, letterbox.source_width, letterbox.source_height
        )
        if clipped is None:
            continue
        bbox = BoundingBox2D.from_xyxy(*clipped)
        inst_mask = None
        mask_source = ""
        if output1 is not None:
            inst_mask, mask_source = reconstruct_instance_mask(
                mask_coeffs[index],
                output1,
                letterbox,
                bbox,
                mask_threshold=mask_threshold,
            )
            if inst_mask is None:
                mask_source = ""
        detections.append(
            Detection(
                detection_index=0,
                class_name=class_name,
                confidence=float(scores[index]),
                bbox=bbox,
                mask=inst_mask,
                mask_source=mask_source,
            )
        )

    ordered = sort_detections_deterministic(detections)
    return ordered[: max(0, int(max_detections))]
