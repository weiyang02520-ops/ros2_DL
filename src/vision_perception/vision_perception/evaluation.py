"""Offline V1 bbox evaluation (plan §10.1). No ROS / no camera / no weights.

Same-class IoU≥threshold one-to-one matching. Per-class precision/recall.
Denominator zero → metric marked non-computable (not 100%).
Empty GT images contribute FP when predictions appear; they do not inflate
precision denominators via background frame counts alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from vision_perception.postprocess import box_iou_xyxy
from vision_perception.types import ALLOWED_CLASSES


DEFAULT_IOU_THRESHOLD = 0.5


@dataclass(frozen=True)
class EvalBox:
    class_name: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def as_xyxy(self) -> Tuple[float, float, float, float]:
        return (self.x_min, self.y_min, self.x_max, self.y_max)


@dataclass
class ImageEvalCase:
    source_image_id: str
    ground_truth: List[EvalBox] = field(default_factory=list)
    predictions: List[EvalBox] = field(default_factory=list)


@dataclass(frozen=True)
class ClassCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, other: "ClassCounts") -> "ClassCounts":
        return ClassCounts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)


def _metric_or_none(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def bbox_from_detection_dict(det: Dict[str, Any]) -> EvalBox:
    bbox = det["bbox"]
    cx = float(bbox["center_x"])
    cy = float(bbox["center_y"])
    sx = float(bbox["size_x"])
    sy = float(bbox["size_y"])
    return EvalBox(
        class_name=str(det["class_name"]),
        x_min=cx - 0.5 * sx,
        y_min=cy - 0.5 * sy,
        x_max=cx + 0.5 * sx,
        y_max=cy + 0.5 * sy,
    )


def bbox_from_annotation_dict(item: Dict[str, Any]) -> EvalBox:
    if "bbox" in item and isinstance(item["bbox"], dict):
        return bbox_from_detection_dict(item)
    if all(k in item for k in ("x_min", "y_min", "x_max", "y_max")):
        return EvalBox(
            class_name=str(item["class_name"]),
            x_min=float(item["x_min"]),
            y_min=float(item["y_min"]),
            x_max=float(item["x_max"]),
            y_max=float(item["y_max"]),
        )
    raise ValueError(
        "annotation box needs class_name + xyxy or centre/size bbox dict"
    )


def match_same_class_iou(
    ground_truth: Sequence[EvalBox],
    predictions: Sequence[EvalBox],
    *,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
) -> ClassCounts:
    """Greedy one-to-one match within a single class list (already filtered)."""
    if not ground_truth and not predictions:
        return ClassCounts()
    if not ground_truth:
        return ClassCounts(fp=len(predictions))
    if not predictions:
        return ClassCounts(fn=len(ground_truth))

    pairs: List[Tuple[float, int, int]] = []
    for gi, gt in enumerate(ground_truth):
        for pi, pred in enumerate(predictions):
            iou = box_iou_xyxy(gt.as_xyxy(), pred.as_xyxy())
            if iou >= iou_threshold:
                pairs.append((iou, gi, pi))
    # Highest IoU first; ties by gt index then pred index for determinism.
    pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
    used_gt: set[int] = set()
    used_pred: set[int] = set()
    tp = 0
    for _iou, gi, pi in pairs:
        if gi in used_gt or pi in used_pred:
            continue
        used_gt.add(gi)
        used_pred.add(pi)
        tp += 1
    fp = len(predictions) - len(used_pred)
    fn = len(ground_truth) - len(used_gt)
    return ClassCounts(tp=tp, fp=fp, fn=fn)


def evaluate_image(
    case: ImageEvalCase, *, iou_threshold: float = DEFAULT_IOU_THRESHOLD
) -> Dict[str, ClassCounts]:
    by_class: Dict[str, ClassCounts] = {name: ClassCounts() for name in ALLOWED_CLASSES}
    for class_name in ALLOWED_CLASSES:
        gt = [b for b in case.ground_truth if b.class_name == class_name]
        pred = [b for b in case.predictions if b.class_name == class_name]
        by_class[class_name] = match_same_class_iou(
            gt, pred, iou_threshold=iou_threshold
        )
    # Predictions outside allowed classes count as FP against neither bottle/cup;
    # surface them under a synthetic bucket only if present.
    other = [b for b in case.predictions if b.class_name not in ALLOWED_CLASSES]
    if other:
        by_class["_other"] = ClassCounts(fp=len(other))
    return by_class


def evaluate_cases(
    cases: Sequence[ImageEvalCase],
    *,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
    classes: Sequence[str] = ALLOWED_CLASSES,
) -> Dict[str, Any]:
    totals = {name: ClassCounts() for name in classes}
    per_image: List[Dict[str, Any]] = []
    for case in cases:
        by_class = evaluate_image(case, iou_threshold=iou_threshold)
        image_entry: Dict[str, Any] = {
            "source_image_id": case.source_image_id,
            "counts": {},
        }
        for name in classes:
            counts = by_class.get(name, ClassCounts())
            totals[name] = totals[name].add(counts)
            image_entry["counts"][name] = {
                "tp": counts.tp,
                "fp": counts.fp,
                "fn": counts.fn,
            }
        per_image.append(image_entry)

    metrics: Dict[str, Any] = {
        "stage": "V1_OFFLINE_EVAL",
        "iou_threshold": float(iou_threshold),
        "score_note": "Caller must filter predictions at the operating score (default 0.35).",
        "per_class": {},
        "images": per_image,
        "arm_ready": "NO",
        "camera_contract": "NOT_RUN",
    }
    for name in classes:
        c = totals[name]
        precision = _metric_or_none(c.tp, c.tp + c.fp)
        recall = _metric_or_none(c.tp, c.tp + c.fn)
        metrics["per_class"][name] = {
            "tp": c.tp,
            "fp": c.fp,
            "fn": c.fn,
            "precision": precision,
            "recall": recall,
            "precision_computable": precision is not None,
            "recall_computable": recall is not None,
        }
    return metrics


def load_annotations_file(path: str) -> Dict[str, List[EvalBox]]:
    """Load annotations keyed by source_image_id.

    Accepted shapes:
      {"images":[{"source_image_id":"a.jpg","boxes":[...]}]}
      [{"source_image_id":"a.jpg","boxes":[...]}]
    """
    import json
    from pathlib import Path

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "images" in raw:
        entries = list(raw["images"])
    elif isinstance(raw, list):
        entries = raw
    else:
        raise ValueError("annotations must be a list or {images:[...]}")

    out: Dict[str, List[EvalBox]] = {}
    for entry in entries:
        image_id = str(entry.get("source_image_id") or entry.get("image_id") or "")
        if not image_id:
            raise ValueError("each annotation image needs source_image_id")
        boxes = [bbox_from_annotation_dict(item) for item in entry.get("boxes", [])]
        for box in boxes:
            if box.class_name not in ALLOWED_CLASSES:
                raise ValueError(
                    f"annotation class_name={box.class_name!r} not in {ALLOWED_CLASSES}"
                )
        out[image_id] = boxes
    return out


def cases_from_offline_batches(
    batches: Sequence[Dict[str, Any]],
    annotations_by_id: Dict[str, List[EvalBox]],
) -> List[ImageEvalCase]:
    """Pair offline detection batches with GT. Missing GT → empty GT (FP-only)."""
    cases: List[ImageEvalCase] = []
    seen: set[str] = set()
    for batch in batches:
        image_id = str(batch.get("source_image_id") or "")
        if not image_id:
            raise ValueError("detection batch missing source_image_id")
        seen.add(image_id)
        preds = [bbox_from_detection_dict(det) for det in batch.get("detections", [])]
        cases.append(
            ImageEvalCase(
                source_image_id=image_id,
                ground_truth=list(annotations_by_id.get(image_id, [])),
                predictions=preds,
            )
        )
    # GT-only images (no prediction batch) count as FN.
    for image_id, boxes in annotations_by_id.items():
        if image_id in seen:
            continue
        cases.append(
            ImageEvalCase(
                source_image_id=image_id,
                ground_truth=list(boxes),
                predictions=[],
            )
        )
    return cases


def evaluate_offline_payload(
    payload_or_batches: Any,
    annotations_path: str,
    *,
    iou_threshold: float = DEFAULT_IOU_THRESHOLD,
) -> Dict[str, Any]:
    if isinstance(payload_or_batches, dict) and "batches" in payload_or_batches:
        batches = list(payload_or_batches["batches"])
    elif isinstance(payload_or_batches, list):
        batches = list(payload_or_batches)
    else:
        raise ValueError("expected offline payload with batches or a batch list")
    annotations = load_annotations_file(annotations_path)
    cases = cases_from_offline_batches(batches, annotations)
    return evaluate_cases(cases, iou_threshold=iou_threshold)


def summarize_v2_object_coverage(
    object_batches: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Functional V2 coverage from ObjectBatch dicts (plan §10.2 scaffolding).

    Reports paired / position_valid rates only. Without independent surface-point
    ground truth, ``v2_accuracy`` stays ``BLOCKED`` and ``result`` is ``NOT_RUN``.
    Never invents a precision PASS from synthetic planes.
    """
    n_batches = 0
    n_paired = 0
    n_objects = 0
    n_position_valid = 0
    reasons: Dict[str, int] = {}
    for batch in object_batches:
        n_batches += 1
        if batch.get("depth_paired") or batch.get("pair_reason") == "OK":
            n_paired += 1
        for obj in batch.get("objects", []):
            n_objects += 1
            if obj.get("position_valid"):
                n_position_valid += 1
            reason = str(obj.get("invalid_reason") or "")
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
    return {
        "stage": "V2_POSITION_COVERAGE",
        "result": "NOT_RUN",
        "v2_accuracy": "BLOCKED",
        "arm_ready": "NO",
        "camera_contract": "NOT_RUN",
        "batches": int(n_batches),
        "batches_paired": int(n_paired),
        "pair_rate": _metric_or_none(n_paired, n_batches),
        "objects": int(n_objects),
        "position_valid": int(n_position_valid),
        "position_valid_rate": _metric_or_none(n_position_valid, n_objects),
        "invalid_reason_counts": reasons,
        "note": (
            "Coverage only. Independent surface-point truth required for "
            "V2_ACCURACY; synthetic depth must not be marked PASS."
        ),
    }


@dataclass(frozen=True)
class TrackedIdentity:
    """One predicted identity on a frame (for V3 scaffolding checks)."""

    frame_id: str
    detection_index: int
    object_id: str
    class_name: str = ""
    tracking_valid: bool = False


def count_same_frame_duplicate_ids(
    identities: Sequence[TrackedIdentity],
) -> int:
    """Count frames where the same non-empty object_id appears more than once."""
    by_frame: Dict[str, List[str]] = {}
    for item in identities:
        oid = str(item.object_id or "").strip()
        if not oid or not item.tracking_valid:
            continue
        by_frame.setdefault(str(item.frame_id), []).append(oid)
    duplicates = 0
    for ids in by_frame.values():
        seen: set[str] = set()
        for oid in ids:
            if oid in seen:
                duplicates += 1
            else:
                seen.add(oid)
    return duplicates


def count_id_switches(
    frame_order: Sequence[str],
    gt_id_by_frame_det: Mapping[Tuple[str, int], str],
    pred_id_by_frame_det: Mapping[Tuple[str, int], str],
) -> int:
    """Count identity switches along a GT identity timeline (synthetic scaffold).

    For each ground-truth identity, walk frames in order. When consecutive
    matched predictions disagree on object_id, count one switch. Missing
    identity annotations → caller must report NOT_RUN rather than IDF1 PASS.
    """
    # Invert GT: identity -> ordered (frame, det) appearances
    gt_timeline: Dict[str, List[Tuple[str, int]]] = {}
    for frame_id in frame_order:
        for (fid, det_idx), gt_id in gt_id_by_frame_det.items():
            if fid != frame_id:
                continue
            gt_timeline.setdefault(str(gt_id), []).append((fid, int(det_idx)))

    switches = 0
    for _gt_id, appearances in gt_timeline.items():
        prev_pred: Optional[str] = None
        for frame_id, det_idx in appearances:
            pred = str(pred_id_by_frame_det.get((frame_id, det_idx), "") or "")
            if not pred:
                prev_pred = None
                continue
            if prev_pred is not None and pred != prev_pred:
                switches += 1
            prev_pred = pred
    return switches


def compute_idf1_from_aligned_ids(
    gt_id_by_frame_det: Mapping[Tuple[str, int], str],
    pred_id_by_frame_det: Mapping[Tuple[str, int], str],
) -> Dict[str, Any]:
    """Clear-MOT-style IDF1 scaffold on already-aligned (frame, det) keys.

    Builds a greedy GT↔pred identity assignment from co-occurrence counts.
    Returns numeric idtp/idfp/idfn/idp/idr/idf1. Never sets acceptance PASS.
    """
    cooccur: Dict[Tuple[str, str], int] = {}
    gt_count: Dict[str, int] = {}
    pred_count: Dict[str, int] = {}
    keys = set(gt_id_by_frame_det) | set(pred_id_by_frame_det)
    for key in keys:
        gt = str(gt_id_by_frame_det.get(key, "") or "").strip()
        pred = str(pred_id_by_frame_det.get(key, "") or "").strip()
        if gt:
            gt_count[gt] = gt_count.get(gt, 0) + 1
        if pred:
            pred_count[pred] = pred_count.get(pred, 0) + 1
        if gt and pred:
            pair = (gt, pred)
            cooccur[pair] = cooccur.get(pair, 0) + 1

    pairs = sorted(
        ((count, gt, pred) for (gt, pred), count in cooccur.items()),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    used_gt: set[str] = set()
    used_pred: set[str] = set()
    idtp = 0
    for count, gt, pred in pairs:
        if gt in used_gt or pred in used_pred:
            continue
        used_gt.add(gt)
        used_pred.add(pred)
        idtp += int(count)

    n_gt = sum(gt_count.values())
    n_pred = sum(pred_count.values())
    idfn = max(0, n_gt - idtp)
    idfp = max(0, n_pred - idtp)
    idp = _metric_or_none(idtp, idtp + idfp)
    idr = _metric_or_none(idtp, idtp + idfn)
    if idp is None or idr is None or (idp + idr) <= 0:
        idf1: Optional[float] = None
    else:
        idf1 = 2.0 * idp * idr / (idp + idr)
    return {
        "idtp": int(idtp),
        "idfp": int(idfp),
        "idfn": int(idfn),
        "idp": idp,
        "idr": idr,
        "idf1": idf1,
        "idf1_computable": idf1 is not None,
    }


def load_identity_annotations_file(path: str) -> Dict[Tuple[str, int], str]:
    """Load identity annotations keyed by (frame_id, detection_index).

    Accepted shapes:
      {"frames":[{"frame_id":"f0","identities":[{"detection_index":0,"gt_id":"a"}]}]}
      [{"frame_id":"f0","detection_index":0,"gt_id":"a"}]
    """
    import json
    from pathlib import Path

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: Dict[Tuple[str, int], str] = {}
    if isinstance(raw, dict) and "frames" in raw:
        for frame in raw["frames"]:
            frame_id = str(frame.get("frame_id") or frame.get("source_image_id") or "")
            if not frame_id:
                raise ValueError("identity frame missing frame_id")
            for item in frame.get("identities", frame.get("boxes", [])):
                det_idx = int(item["detection_index"])
                gt_id = str(item.get("gt_id") or item.get("identity_id") or "")
                if not gt_id:
                    raise ValueError("identity entry missing gt_id")
                out[(frame_id, det_idx)] = gt_id
    elif isinstance(raw, list):
        for item in raw:
            frame_id = str(item.get("frame_id") or item.get("source_image_id") or "")
            if not frame_id:
                raise ValueError("identity row missing frame_id")
            det_idx = int(item["detection_index"])
            gt_id = str(item.get("gt_id") or item.get("identity_id") or "")
            if not gt_id:
                raise ValueError("identity row missing gt_id")
            out[(frame_id, det_idx)] = gt_id
    else:
        raise ValueError("identity annotations must be a list or {frames:[...]}")
    return out


def summarize_v3_tracking_scaffold(
    identities: Sequence[TrackedIdentity],
    *,
    frame_order: Optional[Sequence[str]] = None,
    gt_id_by_frame_det: Optional[Mapping[Tuple[str, int], str]] = None,
    has_identity_annotations: bool = False,
) -> Dict[str, Any]:
    """V3 tracking scaffold (plan §10.3). Never auto-marks IDF1 PASS.

    Without identity annotations ``idf1`` stays blocked and ``result=NOT_RUN``.
    With annotations, numeric IDF1 is reported but ``result`` remains ``NOT_RUN``
    (formal acceptance is a separate evidence protocol).
    """
    n = len(identities)
    n_valid = sum(1 for i in identities if i.tracking_valid and i.object_id)
    duplicate_ids = count_same_frame_duplicate_ids(identities)
    switches = 0
    idf1_block: Any = "BLOCKED"
    id_metrics: Optional[Dict[str, Any]] = None
    if (
        has_identity_annotations
        and frame_order is not None
        and gt_id_by_frame_det is not None
    ):
        pred_map = {
            (str(i.frame_id), int(i.detection_index)): str(i.object_id)
            for i in identities
            if i.tracking_valid and i.object_id
        }
        switches = count_id_switches(frame_order, gt_id_by_frame_det, pred_map)
        id_metrics = compute_idf1_from_aligned_ids(gt_id_by_frame_det, pred_map)
        idf1_block = id_metrics.get("idf1")

    return {
        "stage": "V3_TRACKING_SCAFFOLD",
        "result": "NOT_RUN",
        "idf1": idf1_block,
        "idp": None if id_metrics is None else id_metrics.get("idp"),
        "idr": None if id_metrics is None else id_metrics.get("idr"),
        "idtp": None if id_metrics is None else id_metrics.get("idtp"),
        "idfp": None if id_metrics is None else id_metrics.get("idfp"),
        "idfn": None if id_metrics is None else id_metrics.get("idfn"),
        "arm_ready": "NO",
        "camera_contract": "NOT_RUN",
        "identities": int(n),
        "tracking_valid_with_id": int(n_valid),
        "same_frame_duplicate_ids": int(duplicate_ids),
        "id_switches": int(switches) if has_identity_annotations else None,
        "has_identity_annotations": bool(has_identity_annotations),
        "note": (
            "Scaffold only. Numeric IDF1 with labels is still result=NOT_RUN; "
            "formal PASS requires the acceptance protocol and owner sign-off."
        ),
    }
