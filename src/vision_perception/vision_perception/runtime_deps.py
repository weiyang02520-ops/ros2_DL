"""Pinned runtime dependency contract for v1_ros / webcam / offline paths.

NumPy 2.x is rejected: it commonly breaks OpenCV binary wheels with
``numpy.core.multiarray failed to import`` / ``_ARRAY_API not found``.
"""

from __future__ import annotations

from typing import List, Tuple

# setup.py / requirements-runtime.txt must stay aligned with these strings.
NUMPY_PIP = "numpy>=1.26.4,<2"
OPENCV_PIP = "opencv-python-headless==4.10.0.84"
ONNXRUNTIME_PIP = "onnxruntime==1.20.1"

PIP_INSTALL_ORDER = (NUMPY_PIP, OPENCV_PIP, ONNXRUNTIME_PIP)


def numpy_major_version(version: str) -> int:
    return int(str(version).split(".")[0])


def check_numpy_opencv_compat(numpy_version: str | None = None) -> None:
    """Raise RuntimeError if NumPy major version is unsafe for typical cv2 wheels."""
    if numpy_version is None:
        import numpy as np

        numpy_version = np.__version__
    if numpy_major_version(numpy_version) >= 2:
        raise RuntimeError(
            f"Incompatible NumPy {numpy_version}: vision_perception requires "
            f"{NUMPY_PIP}. NumPy 2.x breaks many OpenCV builds (_ARRAY_API). "
            "Fix order: pip install --user "
            f"'{NUMPY_PIP}' then '{OPENCV_PIP}' then '{ONNXRUNTIME_PIP}'. "
            "Do not upgrade numpy to 2.x afterward."
        )


def check_v1_runtime_imports(*, require_opencv: bool = False) -> List[str]:
    """Import-check pinned stack. Returns human-readable OK lines; raises on failure."""
    notes: List[str] = []
    check_numpy_opencv_compat()
    import numpy as np

    notes.append(f"numpy=={np.__version__} (pinned {NUMPY_PIP})")

    if require_opencv:
        try:
            import cv2  # type: ignore
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "OpenCV (cv2) import failed. Install headless pin after numpy<2: "
                f"pip install --user '{OPENCV_PIP}'. Underlying error: {exc}"
            ) from exc
        notes.append(f"cv2=={getattr(cv2, '__version__', '?')} (pin {OPENCV_PIP})")

    try:
        import onnxruntime as ort  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "onnxruntime import failed. After numpy<2: "
            f"pip install --user '{ONNXRUNTIME_PIP}'. Underlying error: {exc}"
        ) from exc
    notes.append(
        f"onnxruntime=={getattr(ort, '__version__', '?')} (pin {ONNXRUNTIME_PIP})"
    )
    return notes


def pip_install_commands() -> Tuple[str, ...]:
    return tuple(f"python3 -m pip install --user '{spec}'" for spec in PIP_INSTALL_ORDER)
