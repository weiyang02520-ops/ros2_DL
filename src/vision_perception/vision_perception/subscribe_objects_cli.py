"""CLI entry for W6 subscribe-only example."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def main(argv=None) -> int:
    # Prefer installed share/examples copy when present; else repo relative.
    candidates = []
    try:
        from ament_index_python.packages import get_package_share_directory

        share = Path(get_package_share_directory("vision_perception"))
        candidates.append(share / "examples" / "subscribe_vision_objects.py")
    except Exception:  # noqa: BLE001
        pass
    here = Path(__file__).resolve().parents[1] / "examples" / "subscribe_vision_objects.py"
    candidates.append(here)
    for path in candidates:
        if path.is_file():
            sys.argv = [str(path), *(argv if argv is not None else sys.argv[1:])]
            runpy.run_path(str(path), run_name="__main__")
            return 0
    print("subscribe_vision_objects.py not found", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
