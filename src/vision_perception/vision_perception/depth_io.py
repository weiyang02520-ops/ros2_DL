"""Depth image + CameraInfo helpers (no rclpy / no ZED SDK)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple

import numpy as np


@dataclass(frozen=True)
class CameraCalibration:
    """Pinhole optical camera from CameraInfo (fx, fy, cx, cy from P)."""

    frame_id: str
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float
    calibration_id: str
    # Raw fields kept for hashing / diagnostics.
    k: Tuple[float, ...] = ()
    d: Tuple[float, ...] = ()
    r: Tuple[float, ...] = ()
    p: Tuple[float, ...] = ()


@dataclass(frozen=True)
class DepthFrame:
    depth_m: np.ndarray  # HxW float32 metres; NaN/inf = invalid
    stamp_sec: int
    stamp_nanosec: int
    frame_id: str
    encoding: str


def stamp_to_ns(sec: int, nanosec: int) -> int:
    return int(sec) * 1_000_000_000 + int(nanosec)


def stamp_delta_sec(
    a_sec: int, a_nsec: int, b_sec: int, b_nsec: int
) -> float:
    return abs(stamp_to_ns(a_sec, a_nsec) - stamp_to_ns(b_sec, b_nsec)) * 1e-9


def decode_depth_image(
    data: bytes,
    *,
    height: int,
    width: int,
    encoding: str,
    step: Optional[int] = None,
    stamp_sec: int = 0,
    stamp_nanosec: int = 0,
    frame_id: str = "",
) -> DepthFrame:
    """Decode sensor_msgs/Image depth to float32 metres."""
    enc = encoding.strip().lower()
    h, w = int(height), int(width)
    if h <= 0 or w <= 0:
        raise ValueError("depth height/width must be positive")
    buf = np.frombuffer(data, dtype=np.uint8)
    if enc in {"32fc1", "32fc"}:
        expected = h * w * 4
        if step is None:
            step = w * 4
        if len(buf) < expected and len(buf) < h * int(step):
            raise ValueError("depth 32FC1 buffer too short")
        if int(step) == w * 4 and len(buf) >= expected:
            depth = np.frombuffer(buf[:expected], dtype=np.float32).reshape(h, w)
        else:
            row = int(step)
            depth = np.empty((h, w), dtype=np.float32)
            for y in range(h):
                start = y * row
                depth[y] = np.frombuffer(buf[start : start + w * 4], dtype=np.float32)
    elif enc in {"16uc1", "mono16"}:
        expected = h * w * 2
        if step is None:
            step = w * 2
        if int(step) == w * 2 and len(buf) >= expected:
            raw = np.frombuffer(buf[:expected], dtype=np.uint16).reshape(h, w)
        else:
            row = int(step)
            raw = np.empty((h, w), dtype=np.uint16)
            for y in range(h):
                start = y * row
                raw[y] = np.frombuffer(buf[start : start + w * 2], dtype=np.uint16)
        # Common ROS convention: millimetres in 16UC1.
        depth = raw.astype(np.float32) * 0.001
        depth[raw == 0] = np.nan
    else:
        raise ValueError(
            f"unsupported depth encoding={encoding!r}; expected 32FC1 or 16UC1"
        )
    depth = np.array(depth, dtype=np.float32, copy=True)
    depth[~np.isfinite(depth)] = np.nan
    depth[depth <= 0] = np.nan
    return DepthFrame(
        depth_m=depth,
        stamp_sec=int(stamp_sec),
        stamp_nanosec=int(stamp_nanosec),
        frame_id=str(frame_id),
        encoding=str(encoding),
    )


def decode_depth_msg(msg: Any) -> DepthFrame:
    stamp = msg.header.stamp
    return decode_depth_image(
        bytes(msg.data),
        height=int(msg.height),
        width=int(msg.width),
        encoding=str(msg.encoding),
        step=int(msg.step) if getattr(msg, "step", 0) else None,
        stamp_sec=int(stamp.sec),
        stamp_nanosec=int(stamp.nanosec),
        frame_id=str(msg.header.frame_id),
    )


def _as_float_tuple(values: Sequence[Any], expected: int) -> Tuple[float, ...]:
    items = tuple(float(v) for v in values)
    if len(items) < expected:
        raise ValueError(f"expected at least {expected} values, got {len(items)}")
    return items[:expected]


def calibration_id_from_fields(
    *,
    frame_id: str,
    width: int,
    height: int,
    k: Sequence[float],
    d: Sequence[float],
    r: Sequence[float],
    p: Sequence[float],
    binning_x: int = 0,
    binning_y: int = 0,
    roi: Optional[dict] = None,
) -> str:
    payload = {
        "frame_id": frame_id,
        "width": int(width),
        "height": int(height),
        "K": [float(x) for x in k],
        "D": [float(x) for x in d],
        "R": [float(x) for x in r],
        "P": [float(x) for x in p],
        "binning_x": int(binning_x),
        "binning_y": int(binning_y),
        "roi": roi or {},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def camera_calibration_from_info_msg(msg: Any) -> CameraCalibration:
    """Build CameraCalibration from sensor_msgs/CameraInfo (or duck type)."""
    frame_id = str(msg.header.frame_id)
    width = int(msg.width)
    height = int(msg.height)
    k = _as_float_tuple(msg.k, 9)
    d = tuple(float(x) for x in msg.d)
    r = _as_float_tuple(msg.r, 9)
    p = _as_float_tuple(msg.p, 12)
    # P: [fx 0 cx tx; 0 fy cy ty; 0 0 1 0]
    fx, fy, cx, cy = p[0], p[5], p[2], p[6]
    if fx <= 0 or fy <= 0:
        raise ValueError(f"invalid CameraInfo P fx/fy: fx={fx}, fy={fy}")
    roi = {}
    if hasattr(msg, "roi"):
        roi = {
            "x_offset": int(msg.roi.x_offset),
            "y_offset": int(msg.roi.y_offset),
            "height": int(msg.roi.height),
            "width": int(msg.roi.width),
            "do_rectify": bool(msg.roi.do_rectify),
        }
    calib_id = calibration_id_from_fields(
        frame_id=frame_id,
        width=width,
        height=height,
        k=k,
        d=d,
        r=r,
        p=p,
        binning_x=int(getattr(msg, "binning_x", 0) or 0),
        binning_y=int(getattr(msg, "binning_y", 0) or 0),
        roi=roi,
    )
    return CameraCalibration(
        frame_id=frame_id,
        width=width,
        height=height,
        fx=float(fx),
        fy=float(fy),
        cx=float(cx),
        cy=float(cy),
        calibration_id=calib_id,
        k=k,
        d=d,
        r=r,
        p=p,
    )


def camera_calibration_from_pinhole(
    *,
    width: int,
    height: int,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    frame_id: str = "fake_optical_frame",
) -> CameraCalibration:
    """Synthetic CameraInfo for unit tests / fake publisher."""
    k = (fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0)
    r = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    p = (fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0)
    calib_id = calibration_id_from_fields(
        frame_id=frame_id, width=width, height=height, k=k, d=(), r=r, p=p
    )
    return CameraCalibration(
        frame_id=frame_id,
        width=int(width),
        height=int(height),
        fx=float(fx),
        fy=float(fy),
        cx=float(cx),
        cy=float(cy),
        calibration_id=calib_id,
        k=k,
        d=(),
        r=r,
        p=p,
    )


def project_optical_xyz(
    u: float, v: float, z_m: float, calib: CameraCalibration
) -> Tuple[float, float, float]:
    """X=(u-cx)Z/fx, Y=(v-cy)Z/fy, Z=depth (optical metres)."""
    z = float(z_m)
    x = (float(u) - calib.cx) * z / calib.fx
    y = (float(v) - calib.cy) * z / calib.fy
    return (x, y, z)


def encode_depth_32fc1_fields(
    depth_m: np.ndarray,
    *,
    frame_id: str = "",
    stamp_sec: int = 0,
    stamp_nanosec: int = 0,
) -> dict:
    if depth_m.ndim != 2:
        raise ValueError("depth_m must be HxW")
    h, w = depth_m.shape
    contiguous = np.ascontiguousarray(depth_m, dtype=np.float32)
    return {
        "height": h,
        "width": w,
        "encoding": "32FC1",
        "is_bigendian": 0,
        "step": w * 4,
        "data": contiguous.tobytes(),
        "header": {
            "frame_id": frame_id,
            "stamp": {"sec": stamp_sec, "nanosec": stamp_nanosec},
        },
    }
