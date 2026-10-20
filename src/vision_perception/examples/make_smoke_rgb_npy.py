#!/usr/bin/env python3
"""Write a tiny HxWx3 uint8 .npy for fake-image format smoke (not a YOLO photo).

Usage:
  python3 examples/make_smoke_rgb_npy.py /tmp/smoke_rgb.npy

For non-empty bottle/cup detections under mode:=v1_ros, pass a real photo:
  fake_image_path:=/path/to/bottle_or_cup.jpg
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np


def build_hint_frame(height: int = 240, width: int = 320) -> np.ndarray:
    """Crude bottle + cup colour blobs (format sample only; YOLO may still return [])."""
    rgb = np.full((height, width, 3), 240, dtype=np.uint8)
    # Bottle-like vertical rectangle (greenish).
    rgb[40:200, 50:100] = (40, 140, 60)
    rgb[30:50, 65:85] = (40, 140, 60)
    # Cup-like trapezoid block (bluish).
    rgb[120:200, 180:250] = (50, 90, 200)
    rgb[110:120, 190:240] = (50, 90, 200)
    return rgb


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_npy", type=Path, help="Output .npy path (HxWx3 RGB)")
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--width", type=int, default=320)
    args = parser.parse_args(argv)
    frame = build_hint_frame(args.height, args.width)
    args.out_npy.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(args.out_npy), frame)
    print(
        f"wrote {args.out_npy} shape={frame.shape} "
        "(format sample; use a real bottle/cup JPG for non-empty detections)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
