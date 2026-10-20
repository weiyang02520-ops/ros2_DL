"""V3 MultiObjectTracker behaviour (no ROS / no camera / no ONNX)."""

from __future__ import annotations

from vision_perception.objects_pipeline import (
    Object3D,
    ObjectBatch,
    apply_track_assignments,
)
from vision_perception.tracker import MultiObjectTracker
from vision_perception.types import BoundingBox2D, Detection, DetectionBatch, FrameKey


def _det(
    index: int,
    class_name: str,
    cx: float,
    cy: float,
    sx: float = 20.0,
    sy: float = 30.0,
    conf: float = 0.9,
) -> Detection:
    return Detection(
        detection_index=index,
        class_name=class_name,
        confidence=conf,
        bbox=BoundingBox2D(cx, cy, sx, sy),
    )


def test_confirm_hits_before_object_id():
    tracker = MultiObjectTracker(confirm_hits=3, match_iou=0.30)
    dets = [_det(0, "cup", 50, 50)]
    a1 = tracker.update(dets, stamp_sec=0.0)
    a2 = tracker.update(dets, stamp_sec=0.1)
    a3 = tracker.update(dets, stamp_sec=0.2)
    assert a1[0].tracking_valid is False and a1[0].object_id == ""
    assert a2[0].tracking_valid is False and a2[0].object_id == ""
    assert a3[0].tracking_valid is True and a3[0].object_id.startswith("trk_")
    oid = a3[0].object_id
    a4 = tracker.update(dets, stamp_sec=0.3)
    assert a4[0].object_id == oid


def test_cross_class_no_match_and_two_cups_cross():
    tracker = MultiObjectTracker(confirm_hits=2, match_iou=0.30)
    # Warm two cups to confirmed.
    left = _det(0, "cup", 40, 40)
    right = _det(1, "cup", 120, 40)
    tracker.update([left, right], stamp_sec=0.0)
    confirmed = tracker.update([left, right], stamp_sec=0.1)
    assert all(a.tracking_valid for a in confirmed)
    id_left = next(a.object_id for a in confirmed if a.detection_index == 0)
    id_right = next(a.object_id for a in confirmed if a.detection_index == 1)
    assert id_left != id_right
    # Swap positions (crossing): IoU may switch IDs; both stay valid + unique.
    swapped = tracker.update(
        [_det(0, "cup", 120, 40), _det(1, "cup", 40, 40)],
        stamp_sec=0.2,
    )
    ids = {a.object_id for a in swapped}
    assert len(ids) == 2
    assert all(a.tracking_valid for a in swapped)
    # Bottle must never steal a cup track.
    bottle_only = tracker.update([_det(0, "bottle", 40, 40)], stamp_sec=0.3)
    assert bottle_only[0].tracking_valid is False


def test_short_occlusion_keeps_id_then_timeout_drops():
    tracker = MultiObjectTracker(
        confirm_hits=2, match_iou=0.30, lost_timeout_sec=0.70
    )
    dets = [_det(0, "bottle", 80, 60)]
    tracker.update(dets, stamp_sec=0.0)
    confirmed = tracker.update(dets, stamp_sec=0.1)
    oid = confirmed[0].object_id
    assert oid
    # Miss within timeout — track retained as lost (no published prediction).
    empty = tracker.update([], stamp_sec=0.4)
    assert empty == ()
    # Reappear nearby → same ID.
    back = tracker.update(dets, stamp_sec=0.5)
    assert back[0].object_id == oid and back[0].tracking_valid is True
    # Miss beyond timeout → new ID after reconfirm.
    tracker.update([], stamp_sec=0.6)
    tracker.update([], stamp_sec=1.5)  # > 0.70 since last hit at 0.5
    again = tracker.update(dets, stamp_sec=1.6)
    assert again[0].tracking_valid is False
    again2 = tracker.update(dets, stamp_sec=1.7)
    assert again2[0].object_id != oid


def test_tentative_deleted_on_first_miss():
    tracker = MultiObjectTracker(confirm_hits=3)
    tracker.update([_det(0, "cup", 10, 10)], stamp_sec=0.0)
    assert tracker.active_track_count == 1
    tracker.update([], stamp_sec=0.1)
    assert tracker.active_track_count == 0


def test_session_reset_on_clock_rollback_and_calibration():
    tracker = MultiObjectTracker(confirm_hits=2)
    tracker.update([_det(0, "cup", 10, 10)], stamp_sec=1.0)
    tracker.update([_det(0, "cup", 10, 10)], stamp_sec=1.1)
    session_a = tracker.tracking_session_id
    oid_a = tracker.update([_det(0, "cup", 10, 10)], stamp_sec=1.2)[0].object_id
    # Clock rollback → new session; prior ID not reused as published identity.
    after_rollback = tracker.update([_det(0, "cup", 10, 10)], stamp_sec=0.5)
    assert tracker.tracking_session_id != session_a
    assert after_rollback[0].tracking_valid is False
    session_b = tracker.tracking_session_id
    tracker.update([_det(0, "cup", 10, 10)], stamp_sec=0.6)
    confirmed = tracker.update([_det(0, "cup", 10, 10)], stamp_sec=0.7)
    assert confirmed[0].object_id != oid_a
    # Calibration change also resets.
    tracker.update(
        [_det(0, "cup", 10, 10)], stamp_sec=0.8, calibration_id="calib-1"
    )
    tracker.update(
        [_det(0, "cup", 10, 10)], stamp_sec=0.9, calibration_id="calib-2"
    )
    assert tracker.tracking_session_id != session_b


def test_depth_invalid_does_not_break_id_via_objects_apply():
    """Tracking is 2D-only; applying IDs to unpaired objects still works."""
    tracker = MultiObjectTracker(confirm_hits=2)
    dets = (_det(0, "bottle", 30, 30),)
    tracker.update(dets, stamp_sec=0.0)
    assignments = tracker.update(dets, stamp_sec=0.1)
    assert assignments[0].tracking_valid is True
    key = FrameKey(
        source_session_id="s",
        observation_id=1,
        source_kind="OFFLINE_FILE",
    )
    det_batch = DetectionBatch(key=key, detections=dets)
    unpaired = Object3D(
        detection_index=0,
        class_name="bottle",
        confidence=0.9,
        bbox_center_x=30.0,
        bbox_center_y=30.0,
        bbox_size_x=20.0,
        bbox_size_y=30.0,
        bbox_theta=0.0,
        position_xyz=(float("nan"), float("nan"), float("nan")),
        position_valid=False,
        position_reference="visible_surface_sample",
        invalid_reason="DEPTH_UNPAIRED",
        reference_u=float("nan"),
        reference_v=float("nan"),
        valid_depth_fraction=0.0,
        orientation_xyzw=(float("nan"),) * 4,
        orientation_valid=False,
        tracking_valid=False,
        object_id="",
        mask_source="none",
    )
    batch = ObjectBatch(
        detection_batch=det_batch,
        objects=(unpaired,),
        tracking_session_id="",
        depth_paired=False,
        pair_skew_sec=None,
        pair_reason="DEPTH_UNPAIRED",
        calibration_id="",
    )
    filled = apply_track_assignments(
        batch, assignments, tracking_session_id=tracker.tracking_session_id
    )
    assert filled.objects[0].position_valid is False
    assert filled.objects[0].tracking_valid is True
    assert filled.objects[0].object_id == assignments[0].object_id
    assert filled.tracking_session_id == tracker.tracking_session_id


def test_deterministic_greedy_order():
    tracker = MultiObjectTracker(confirm_hits=1, match_iou=0.30)
    # Two overlapping cups; detection_index order must be stable.
    a = _det(0, "cup", 50, 50, 40, 40)
    b = _det(1, "cup", 55, 55, 40, 40)
    first = tracker.update([a, b], stamp_sec=0.0)
    tracker2 = MultiObjectTracker(confirm_hits=1, match_iou=0.30)
    second = tracker2.update([a, b], stamp_sec=0.0)
    assert [x.object_id for x in first] == [x.object_id for x in second]
    assert [x.track_id for x in first] == [x.track_id for x in second]
