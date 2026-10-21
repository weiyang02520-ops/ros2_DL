"""W5 transform math contract (no ROS / no TF / no hardware)."""

from __future__ import annotations

import math

import pytest

from vision_perception.object_transform import (
    RigidTransform,
    quat_xyzw_to_rotation_matrix,
    rigid_transform_from_mapping,
    transform_object_batch,
    transform_object3d,
)
from vision_perception.objects_pipeline import Object3D, ObjectBatch
from vision_perception.types import DetectionBatch, FrameKey, POSITION_REFERENCE


def _obj(**kwargs) -> Object3D:
    base = dict(
        detection_index=0,
        class_name="bottle",
        confidence=0.9,
        bbox_center_x=10.0,
        bbox_center_y=20.0,
        bbox_size_x=30.0,
        bbox_size_y=40.0,
        bbox_theta=0.0,
        position_xyz=(1.0, 0.0, 2.0),
        position_valid=True,
        position_reference=POSITION_REFERENCE,
        invalid_reason="OK",
        reference_u=10.0,
        reference_v=20.0,
        valid_depth_fraction=1.0,
        orientation_xyzw=(float("nan"),) * 4,
        orientation_valid=False,
        tracking_valid=False,
        object_id="",
        mask_source="yolo_seg",
    )
    base.update(kwargs)
    return Object3D(**base)


def _batch(objects) -> ObjectBatch:
    key = FrameKey(
        source_session_id="s",
        observation_id=1,
        source_kind="LIVE_CAMERA",
        calibration_id="c",
        frame_id="cam_optical",
        source_stamp_sec=1,
        source_stamp_nanosec=0,
    )
    return ObjectBatch(
        detection_batch=DetectionBatch(key=key, detections=()),
        objects=tuple(objects),
        tracking_session_id="",
        depth_paired=True,
        pair_skew_sec=0.0,
        pair_reason="OK",
        calibration_id="c",
    )


def test_identity_quat_translation_only():
    rigid = rigid_transform_from_mapping(
        {
            "source_frame": "cam",
            "target_frame": "arm",
            "translation_m": [0.1, -0.2, 0.3],
            "rotation": {"quaternion_xyzw": [0.0, 0.0, 0.0, 1.0]},
        }
    )
    out = transform_object3d(
        _obj(position_xyz=(1.0, 0.0, 0.0)), rigid, transform_available=True
    )
    assert out.position_valid is True
    assert out.position_xyz == pytest.approx((1.1, -0.2, 0.3), abs=1e-9)
    assert out.orientation_valid is False
    assert out.bbox_center_x == 10.0  # pixels unchanged


def test_invalid_source_stays_invalid_even_with_tf():
    rigid = RigidTransform(
        rotation=quat_xyzw_to_rotation_matrix(0, 0, 0, 1),
        translation=(1.0, 0.0, 0.0),
        source_frame="cam",
        target_frame="arm",
    )
    src = _obj(
        position_valid=False,
        invalid_reason="DEPTH_UNPAIRED",
        position_xyz=(float("nan"), float("nan"), float("nan")),
    )
    out = transform_object3d(src, rigid, transform_available=True)
    assert out.position_valid is False
    assert out.invalid_reason == "DEPTH_UNPAIRED"
    assert all(math.isnan(v) for v in out.position_xyz)


def test_missing_transform_invalidates_without_zero_fill():
    out, outcome = transform_object_batch(
        _batch([_obj()]),
        rigid=None,
        enabled=True,
        transform_available=False,
        transform_fail_reason="INPUT_INVALID",
    )
    assert outcome.reason == "TRANSFORM_MISSING"
    assert out.objects[0].position_valid is False
    assert out.objects[0].invalid_reason == "INPUT_INVALID"
    assert all(math.isnan(v) for v in out.objects[0].position_xyz)


def test_disabled_does_not_claim_success():
    rigid = rigid_transform_from_mapping(
        {
            "source_frame": "cam",
            "target_frame": "arm",
            "translation_m": [0, 0, 0],
            "rotation": {"quaternion_xyzw": [0, 0, 0, 1]},
        }
    )
    out, outcome = transform_object_batch(
        _batch([_obj()]),
        rigid=rigid,
        enabled=False,
        transform_available=True,
    )
    assert outcome.reason == "TRANSFORM_DISABLED"
    assert out.objects[0].position_valid is False


def test_rejects_missing_extrinsics_mapping():
    with pytest.raises(ValueError, match="translation_m"):
        rigid_transform_from_mapping(
            {
                "source_frame": "a",
                "target_frame": "b",
                "rotation": {"quaternion_xyzw": [0, 0, 0, 1]},
            }
        )


def test_batch_rewrites_frame_keeps_pixels():
    rigid = rigid_transform_from_mapping(
        {
            "source_frame": "cam_optical",
            "target_frame": "peer_arm_base",
            "translation_m": [0.0, 0.0, 0.5],
            "rotation": {"quaternion_xyzw": [0, 0, 0, 1]},
            "extrinsics_id": "test",
        }
    )
    out, outcome = transform_object_batch(
        _batch([_obj(reference_u=123.0, reference_v=45.0)]),
        rigid=rigid,
        enabled=True,
        transform_available=True,
    )
    assert outcome.ok is True
    assert out.detection_batch.key.frame_id == "peer_arm_base"
    assert out.objects[0].reference_u == 123.0
    assert out.objects[0].reference_v == 45.0
    assert out.objects[0].position_xyz[2] == pytest.approx(2.5)
