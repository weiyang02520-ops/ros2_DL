"""Manifest template in examples/ must stay a fill-in JSON (no weights)."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "examples" / "model_manifest.template.json"
EXAMPLE = ROOT / "config" / "model_manifest.example.json"


def _assert_template(path: Path) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    for key in (
        "source",
        "onnx_sha256",
        "license",
        "input_name",
        "input_shape",
        "output0_shape",
        "output1_shape",
        "class_map",
    ):
        assert key in raw
    assert raw["input_name"] == "images"
    assert raw["input_shape"] == [1, 3, 640, 640]
    assert raw["output0_shape"] == [1, 116, 8400]
    assert raw["output1_shape"] == [1, 32, 160, 160]
    assert raw["class_map"]["bottle"] == 39
    assert raw["class_map"]["cup"] == 41
    assert "REPLACE" in raw["onnx_sha256"]
    assert "REPLACE" in raw["license"]


def test_examples_manifest_template_fields():
    _assert_template(TEMPLATE)


def test_config_example_manifest_matches_contract():
    _assert_template(EXAMPLE)


def test_node_fatal_hint_mentions_manifest_template():
    text = (ROOT / "vision_perception" / "vision_node.py").read_text(encoding="utf-8")
    assert "model_manifest.template.json" in text
    assert "no auto-download" in text
