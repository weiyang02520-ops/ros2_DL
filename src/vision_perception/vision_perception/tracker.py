"""Short-horizon 2D identity association (V3). Pure algorithm — no rclpy.

Plan §8: per-class IoU matching, tentative→confirmed lifecycle, lost timeout.
Tracking does not depend on depth / position_valid. Never republishes predicted
boxes as current measurements.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from vision_perception.postprocess import box_iou_xyxy
from vision_perception.types import BoundingBox2D, Detection


DEFAULT_MATCH_IOU = 0.30
DEFAULT_CONFIRM_HITS = 3
DEFAULT_LOST_TIMEOUT_SEC = 0.70


class TrackState(str, Enum):
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    LOST = "lost"


@dataclass(frozen=True)
class TrackAssignment:
    """Per-detection tracking result for the current frame only."""

    detection_index: int
    object_id: str
    tracking_valid: bool
    track_id: int = 0
    track_state: str = ""


@dataclass
class _Track:
    track_id: int
    class_name: str
    bbox: BoundingBox2D
    hits: int
    state: TrackState
    last_stamp_sec: float
    object_id: str

    def as_xyxy(self) -> Tuple[float, float, float, float]:
        return self.bbox.as_xyxy()


def _new_session_id() -> str:
    return str(uuid.uuid4())


def _object_id_for(track_id: int) -> str:
    return f"trk_{int(track_id):04d}"


def match_tracks_greedy(
    tracks: Sequence[_Track],
    detections: Sequence[Detection],
    *,
    match_iou: float,
) -> List[Tuple[_Track, Detection, float]]:
    """Deterministic per-class greedy matching (cost = 1-IoU, gate IoU≥match_iou).

    Tracks sorted by track_id; detections by detection_index. Candidate pairs
    ordered by descending IoU, then track_id, then detection_index so results
    are reproducible for a given input and version.
    """
    by_class_tracks: Dict[str, List[_Track]] = {}
    for track in sorted(tracks, key=lambda t: int(t.track_id)):
        by_class_tracks.setdefault(track.class_name, []).append(track)

    by_class_dets: Dict[str, List[Detection]] = {}
    for det in sorted(detections, key=lambda d: int(d.detection_index)):
        by_class_dets.setdefault(det.class_name, []).append(det)

    matches: List[Tuple[_Track, Detection, float]] = []
    class_names = sorted(set(by_class_tracks) | set(by_class_dets))
    for class_name in class_names:
        class_tracks = by_class_tracks.get(class_name, [])
        class_dets = by_class_dets.get(class_name, [])
        if not class_tracks or not class_dets:
            continue
        pairs: List[Tuple[float, int, int, _Track, Detection]] = []
        for track in class_tracks:
            for det in class_dets:
                iou = box_iou_xyxy(track.as_xyxy(), det.bbox.as_xyxy())
                if iou >= float(match_iou):
                    pairs.append(
                        (float(iou), int(track.track_id), int(det.detection_index), track, det)
                    )
        pairs.sort(key=lambda item: (-item[0], item[1], item[2]))
        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        for iou, tid, did, track, det in pairs:
            if tid in used_tracks or did in used_dets:
                continue
            used_tracks.add(tid)
            used_dets.add(did)
            matches.append((track, det, iou))
    return matches


class MultiObjectTracker:
    """Single-camera short-horizon tracker (no ReID, no cross-restart IDs)."""

    def __init__(
        self,
        *,
        match_iou: float = DEFAULT_MATCH_IOU,
        confirm_hits: int = DEFAULT_CONFIRM_HITS,
        lost_timeout_sec: float = DEFAULT_LOST_TIMEOUT_SEC,
    ) -> None:
        if not (0.0 < float(match_iou) <= 1.0):
            raise ValueError("match_iou must be in (0, 1]")
        if int(confirm_hits) < 1:
            raise ValueError("confirm_hits must be >= 1")
        if float(lost_timeout_sec) <= 0:
            raise ValueError("lost_timeout_sec must be > 0")
        self.match_iou = float(match_iou)
        self.confirm_hits = int(confirm_hits)
        self.lost_timeout_sec = float(lost_timeout_sec)
        self._tracks: Dict[int, _Track] = {}
        self._next_track_id = 1
        self._tracking_session_id = _new_session_id()
        self._last_stamp_sec: Optional[float] = None
        self._last_calibration_id: str = ""

    @property
    def tracking_session_id(self) -> str:
        return self._tracking_session_id

    @property
    def active_track_count(self) -> int:
        return len(self._tracks)

    def reset_session(self, *, reason: str = "") -> str:
        """Clear all tracks and mint a new tracking_session_id (IDs never reuse)."""
        del reason  # retained for call-site clarity / future logging
        self._tracks.clear()
        # Never reuse track_id values across sessions in the same process.
        self._tracking_session_id = _new_session_id()
        self._last_stamp_sec = None
        self._last_calibration_id = ""
        return self._tracking_session_id

    def clear(self) -> None:
        """Alias for STALE / shutdown: drop tracks and start a new session."""
        self.reset_session(reason="clear")

    def update(
        self,
        detections: Sequence[Detection],
        *,
        stamp_sec: float,
        calibration_id: str = "",
    ) -> Tuple[TrackAssignment, ...]:
        """Associate current-frame detections; return one assignment per detection.

        Only confirmed matches receive a non-empty ``object_id`` and
        ``tracking_valid=True``. Tentative / new tracks keep empty id + false.
        Unmatched confirmed tracks are kept (lost) until timeout; tentative
        misses are deleted immediately. No predicted boxes are emitted.
        """
        stamp = float(stamp_sec)
        calib = str(calibration_id or "")

        # Clock rollback or calibration change → new session (plan §8).
        if self._last_stamp_sec is not None and stamp < self._last_stamp_sec:
            self.reset_session(reason="clock_rollback")
        elif (
            calib
            and self._last_calibration_id
            and calib != self._last_calibration_id
        ):
            self.reset_session(reason="calibration_change")

        if calib:
            self._last_calibration_id = calib
        self._last_stamp_sec = stamp

        live_tracks = list(self._tracks.values())
        matches = match_tracks_greedy(
            live_tracks, detections, match_iou=self.match_iou
        )
        touched_track_ids: set[int] = set()
        matched_det_indices = {int(d.detection_index) for _t, d, _iou in matches}

        assignments_by_index: Dict[int, TrackAssignment] = {}

        for track, det, _iou in matches:
            track.bbox = det.bbox
            track.hits = int(track.hits) + 1
            track.last_stamp_sec = stamp
            if track.state == TrackState.LOST:
                track.state = TrackState.CONFIRMED
            if track.hits >= self.confirm_hits:
                track.state = TrackState.CONFIRMED
                if not track.object_id:
                    track.object_id = _object_id_for(track.track_id)
            touched_track_ids.add(int(track.track_id))
            if track.state == TrackState.CONFIRMED:
                assignments_by_index[int(det.detection_index)] = TrackAssignment(
                    detection_index=int(det.detection_index),
                    object_id=track.object_id,
                    tracking_valid=True,
                    track_id=int(track.track_id),
                    track_state=track.state.value,
                )
            else:
                assignments_by_index[int(det.detection_index)] = TrackAssignment(
                    detection_index=int(det.detection_index),
                    object_id="",
                    tracking_valid=False,
                    track_id=int(track.track_id),
                    track_state=track.state.value,
                )

        # Unmatched detections → new tentative tracks (no published ID yet).
        for det in sorted(detections, key=lambda d: int(d.detection_index)):
            if int(det.detection_index) in matched_det_indices:
                continue
            tid = self._next_track_id
            self._next_track_id += 1
            new_track = _Track(
                track_id=tid,
                class_name=det.class_name,
                bbox=det.bbox,
                hits=1,
                state=TrackState.TENTATIVE,
                last_stamp_sec=stamp,
                object_id="",
            )
            if new_track.hits >= self.confirm_hits:
                new_track.state = TrackState.CONFIRMED
                new_track.object_id = _object_id_for(tid)
            self._tracks[tid] = new_track
            touched_track_ids.add(tid)
            if new_track.state == TrackState.CONFIRMED:
                assignments_by_index[int(det.detection_index)] = TrackAssignment(
                    detection_index=int(det.detection_index),
                    object_id=new_track.object_id,
                    tracking_valid=True,
                    track_id=tid,
                    track_state=new_track.state.value,
                )
            else:
                assignments_by_index[int(det.detection_index)] = TrackAssignment(
                    detection_index=int(det.detection_index),
                    object_id="",
                    tracking_valid=False,
                    track_id=tid,
                    track_state=new_track.state.value,
                )

        # Untouched tracks: tentative delete; confirmed → lost / timeout.
        to_delete: List[int] = []
        for tid, track in self._tracks.items():
            if tid in touched_track_ids:
                continue
            if track.state == TrackState.TENTATIVE:
                to_delete.append(tid)
                continue
            age = stamp - float(track.last_stamp_sec)
            if age > self.lost_timeout_sec:
                to_delete.append(tid)
            else:
                track.state = TrackState.LOST
        for tid in to_delete:
            self._tracks.pop(tid, None)

        # Ensure every input detection has an assignment (stable order).
        ordered = sorted(detections, key=lambda d: int(d.detection_index))
        result: List[TrackAssignment] = []
        for det in ordered:
            idx = int(det.detection_index)
            assignment = assignments_by_index.get(idx)
            if assignment is None:
                assignment = TrackAssignment(
                    detection_index=idx,
                    object_id="",
                    tracking_valid=False,
                )
            result.append(assignment)
        return tuple(result)


def assignments_by_detection_index(
    assignments: Sequence[TrackAssignment],
) -> Dict[int, TrackAssignment]:
    return {int(a.detection_index): a for a in assignments}


def stamp_sec_from_parts(stamp_sec: int, stamp_nanosec: int) -> float:
    return float(stamp_sec) + float(stamp_nanosec) * 1e-9
