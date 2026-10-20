"""RGB-primary depth pairing (plan §7.1). Pure Python / NumPy, no rclpy."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Generic, Optional, Tuple, TypeVar

from vision_perception.depth_io import DepthFrame, stamp_delta_sec, stamp_to_ns


T = TypeVar("T")


@dataclass
class PairResult:
    depth: Optional[DepthFrame]
    skew_sec: Optional[float]
    reason: str  # OK / DEPTH_UNPAIRED
    match_index: int = -1  # buffer index when reason==OK before consume


class DepthFrameBuffer:
    """Finite depth queue for RGB-primary pairing."""

    def __init__(
        self,
        *,
        tolerance_sec: float = 0.010,
        max_size: int = 10,
    ):
        if tolerance_sec <= 0:
            raise ValueError("tolerance_sec must be > 0")
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self.tolerance_sec = float(tolerance_sec)
        self.max_size = int(max_size)
        self._frames: Deque[DepthFrame] = deque()
        self.dropped_oldest = 0
        self.paired = 0
        self.unpaired = 0

    def push(self, frame: DepthFrame) -> None:
        self._frames.append(frame)
        while len(self._frames) > self.max_size:
            self._frames.popleft()
            self.dropped_oldest += 1

    def clear(self) -> None:
        self._frames.clear()

    def __len__(self) -> int:
        return len(self._frames)

    def find_match(self, stamp_sec: int, stamp_nanosec: int) -> PairResult:
        """Nearest depth within tolerance; does not consume or update counters."""
        if not self._frames:
            return PairResult(depth=None, skew_sec=None, reason="DEPTH_UNPAIRED")

        rgb_ns = stamp_to_ns(stamp_sec, stamp_nanosec)
        best_i = -1
        best_key: Optional[Tuple[int, int, int]] = None
        for i, frame in enumerate(self._frames):
            d_ns = stamp_to_ns(frame.stamp_sec, frame.stamp_nanosec)
            delta = abs(d_ns - rgb_ns)
            key = (delta, d_ns, i)  # earlier depth wins ties
            if best_key is None or key < best_key:
                best_key = key
                best_i = i

        assert best_i >= 0 and best_key is not None
        frame = self._frames[best_i]
        skew = stamp_delta_sec(
            stamp_sec, stamp_nanosec, frame.stamp_sec, frame.stamp_nanosec
        )
        if skew > self.tolerance_sec + 1e-12:
            return PairResult(
                depth=None, skew_sec=skew, reason="DEPTH_UNPAIRED", match_index=-1
            )
        return PairResult(
            depth=frame, skew_sec=skew, reason="OK", match_index=best_i
        )

    def consume_match(self, match_index: int) -> DepthFrame:
        frame = self._frames[match_index]
        del self._frames[match_index]
        self.paired += 1
        return frame

    def pair_for_rgb(
        self, stamp_sec: int, stamp_nanosec: int
    ) -> PairResult:
        """Find exact stamp match, else nearest unused depth within tolerance.

        On ties (equal |delta|), prefer the earlier depth stamp. Consumes the
        chosen depth so each depth pairs with at most one RGB.
        """
        found = self.find_match(stamp_sec, stamp_nanosec)
        if found.reason != "OK" or found.match_index < 0 or found.depth is None:
            self.unpaired += 1
            return PairResult(
                depth=None, skew_sec=found.skew_sec, reason="DEPTH_UNPAIRED"
            )
        self.consume_match(found.match_index)
        return PairResult(
            depth=found.depth, skew_sec=found.skew_sec, reason="OK"
        )


@dataclass
class SyncedPair(Generic[T]):
    """RGB payload plus depth pairing outcome (ready for inference)."""

    payload: T
    depth: Optional[DepthFrame]
    pair_skew_sec: Optional[float]
    pair_reason: str


@dataclass
class _Awaiting(Generic[T]):
    payload: T
    stamp_sec: int
    stamp_nanosec: int
    deadline_mono: float


class RgbDepthSyncGate(Generic[T]):
    """Hold RGB until a matching depth arrives or sync_wait_sec elapses.

    Fixes the fake-image→vision→fake-depth race where RGB is paired before the
    stamp-mirrored depth is published (skew ≈ 1/frame_rate).
    Compatible with single-threaded executors: never blocks inside callbacks.
    """

    def __init__(
        self,
        buffer: DepthFrameBuffer,
        *,
        sync_wait_sec: float = 0.100,
    ):
        if sync_wait_sec < 0:
            raise ValueError("sync_wait_sec must be >= 0")
        self.buffer = buffer
        self.sync_wait_sec = float(sync_wait_sec)
        self._awaiting: Optional[_Awaiting[T]] = None
        self.replaced_awaiting = 0
        self.timed_out = 0

    @property
    def has_awaiting(self) -> bool:
        return self._awaiting is not None

    def clear(self) -> None:
        self._awaiting = None

    def _try_finish(self, awaiting: _Awaiting[T]) -> Optional[SyncedPair[T]]:
        found = self.buffer.find_match(awaiting.stamp_sec, awaiting.stamp_nanosec)
        if found.reason != "OK" or found.match_index < 0 or found.depth is None:
            return None
        depth = self.buffer.consume_match(found.match_index)
        self._awaiting = None
        return SyncedPair(
            payload=awaiting.payload,
            depth=depth,
            pair_skew_sec=found.skew_sec,
            pair_reason="OK",
        )

    def on_rgb(
        self,
        payload: T,
        *,
        stamp_sec: int,
        stamp_nanosec: int,
        now_mono: float,
    ) -> Optional[SyncedPair[T]]:
        """Offer an RGB frame. Returns a ready pair, or None if waiting for depth."""
        if self._awaiting is not None:
            self.replaced_awaiting += 1
        awaiting = _Awaiting(
            payload=payload,
            stamp_sec=int(stamp_sec),
            stamp_nanosec=int(stamp_nanosec),
            deadline_mono=float(now_mono) + self.sync_wait_sec,
        )
        ready = self._try_finish(awaiting)
        if ready is not None:
            return ready
        if self.sync_wait_sec <= 0:
            self.buffer.unpaired += 1
            self._awaiting = None
            found = self.buffer.find_match(stamp_sec, stamp_nanosec)
            return SyncedPair(
                payload=payload,
                depth=None,
                pair_skew_sec=found.skew_sec,
                pair_reason="DEPTH_UNPAIRED",
            )
        self._awaiting = awaiting
        return None

    def on_depth(self, frame: DepthFrame) -> Optional[SyncedPair[T]]:
        self.buffer.push(frame)
        if self._awaiting is None:
            return None
        return self._try_finish(self._awaiting)

    def poll(self, now_mono: float) -> Optional[SyncedPair[T]]:
        """Finalize timed-out awaiting RGB as DEPTH_UNPAIRED."""
        awaiting = self._awaiting
        if awaiting is None:
            return None
        ready = self._try_finish(awaiting)
        if ready is not None:
            return ready
        if float(now_mono) < awaiting.deadline_mono:
            return None
        self._awaiting = None
        self.timed_out += 1
        self.buffer.unpaired += 1
        found = self.buffer.find_match(awaiting.stamp_sec, awaiting.stamp_nanosec)
        return SyncedPair(
            payload=awaiting.payload,
            depth=None,
            pair_skew_sec=found.skew_sec,
            pair_reason="DEPTH_UNPAIRED",
        )


def attach_any_payload(payload: Any) -> Any:
    """Typing helper placeholder for call sites; identity."""
    return payload
