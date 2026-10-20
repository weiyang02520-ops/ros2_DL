"""ONNX Runtime CPU backend for local YOLO11n-seg weights.

Never auto-downloads models. Ultralytics/PyTorch are not imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple

import numpy as np

from vision_perception.config import (
    load_model_manifest,
    validate_manifest_shapes,
    verify_file_sha256,
)
from vision_perception.types import ModelManifest


@dataclass
class OnnxSession:
    manifest: ModelManifest
    model_path: str
    session: Any
    input_name: str


def _import_ort():
    try:
        import onnxruntime as ort  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "onnxruntime is required for offline/v1_ros detection "
            "(pin onnxruntime==1.20.1 after numpy>=1.26.4,<2; "
            "see requirements-runtime.txt)"
        ) from exc
    return ort


def create_onnx_session(
    model_path: str,
    manifest_path: str,
    ort_threads: int = 2,
) -> OnnxSession:
    """Load local ONNX + manifest, verify hash and tensor layout, create CPU session."""
    if ort_threads < 1:
        raise ValueError("ort_threads must be >= 1")
    manifest = load_model_manifest(manifest_path)
    validate_manifest_shapes(manifest)
    verify_file_sha256(model_path, manifest.onnx_sha256)

    ort = _import_ort()
    options = ort.SessionOptions()
    options.intra_op_num_threads = int(ort_threads)
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(
        model_path,
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    inputs = session.get_inputs()
    if not inputs:
        raise ValueError("ONNX model has no inputs")
    input_name = inputs[0].name
    if input_name != manifest.input_name:
        raise ValueError(
            f"ONNX input name {input_name!r} != manifest {manifest.input_name!r}"
        )
    outputs = session.get_outputs()
    if len(outputs) < 1:
        raise ValueError("ONNX model has no outputs")
    # Layout is validated against actual run outputs in run_onnx.
    return OnnxSession(
        manifest=manifest,
        model_path=model_path,
        session=session,
        input_name=input_name,
    )


def run_onnx(session: OnnxSession, nchw_float32: np.ndarray) -> Tuple[np.ndarray, np.ndarray | None]:
    """Run one batch. Returns (output0, output1_or_None)."""
    if nchw_float32.shape != (1, 3, 640, 640):
        raise ValueError(f"unexpected input tensor shape {nchw_float32.shape}")
    if nchw_float32.dtype != np.float32:
        raise ValueError("input tensor must be float32")
    feeds: Dict[str, np.ndarray] = {session.input_name: nchw_float32}
    outputs = session.session.run(None, feeds)
    if not outputs:
        raise ValueError("ONNX session returned no outputs")
    output0 = np.asarray(outputs[0])
    if tuple(output0.shape) != tuple(session.manifest.output0_shape):
        raise ValueError(
            f"output0 shape {output0.shape} != manifest {session.manifest.output0_shape}"
        )
    output1 = None
    if len(outputs) > 1:
        output1 = np.asarray(outputs[1])
        if tuple(output1.shape) != tuple(session.manifest.output1_shape):
            raise ValueError(
                f"output1 shape {output1.shape} != manifest {session.manifest.output1_shape}"
            )
    return output0, output1
