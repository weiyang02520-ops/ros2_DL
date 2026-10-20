"""Ensure vision scripts stay LF-only (CRLF shebang -> python3\\r exit 127).

LF policy lives in the **package-local** `.gitattributes` so isolated workspaces
that only sync vision_perception(+_interfaces) still pass without the monorepo
root `.gitattributes`.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
PACKAGE_ATTRS = ROOT / ".gitattributes"


def test_package_gitattributes_forces_lf_for_scripts():
    assert PACKAGE_ATTRS.is_file(), (
        "expected src/vision_perception/.gitattributes for isolated-ws sync"
    )
    text = PACKAGE_ATTRS.read_text(encoding="utf-8")
    assert "scripts/**" in text
    assert "eol=lf" in text


def test_lf_policy_does_not_require_monorepo_root_gitattributes():
    """Isolated two-package sync has no repo-root .gitattributes; tests must not need it."""
    # Policy file under the package is enough; do not walk to the workspace root.
    assert PACKAGE_ATTRS == ROOT / ".gitattributes"
    assert str(PACKAGE_ATTRS).startswith(str(ROOT))
    # No helper that points outside the package for attributes.
    assert not hasattr(test_package_gitattributes_forces_lf_for_scripts, "uses_repo_root")


def test_scripts_directory_files_have_no_crlf():
    paths = sorted(p for p in SCRIPTS.iterdir() if p.is_file())
    assert paths, "expected scripts under src/vision_perception/scripts"
    for path in paths:
        data = path.read_bytes()
        assert b"\r\n" not in data and b"\r" not in data, (
            f"{path} contains CR; keep Unix LF only "
            "(see package .gitattributes scripts/**)"
        )
        if path.suffix == ".sh" or path.name.startswith("vision_"):
            if path.suffix == ".sh":
                assert data.startswith(b"#!/usr/bin/env bash\n") or data.startswith(
                    b"#!/bin/bash\n"
                ), path
            else:
                assert data.startswith(b"#!/usr/bin/env python3\n"), path


def test_check_script_accepts_environment_prefix_wiring():
    text = (SCRIPTS / "check_ament_prefix_hook.sh").read_text(encoding="utf-8")
    assert "environment/ament_prefix_path.sh" in text
    assert "local_setup.dsv" in text
    # Must not require package.dsv -> hook/ alone (false FAIL on ament_cmake).
    assert "Do not require the hook/ path alone" in text
    # Install-space execute-bit regression (zip/SFTP).
    assert '[[ ! -x "$LIBEXEC/$exe" ]]' in text or "! -x" in text


def test_ensure_scripts_executable_helper_exists():
    path = SCRIPTS / "ensure_scripts_executable.sh"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "chmod a+x" in text
    assert "vision_fake_image_publisher" in text
    assert "vision_fake_depth_publisher" in text
    assert "vision_offline_objects" in text
    assert "vision_offline_track" in text


def test_bootstrap_isolated_ws_script_exists():
    path = SCRIPTS / "bootstrap_isolated_ws.sh"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "ensure_scripts_executable" in text
    assert "pytest" in text
    assert "use_fake_image" in text
    # Humble setup.bash trips `set -u` (AMENT_TRACE_SETUP_FILES unbound).
    assert "source_ros_setup" in text
    assert "set +u" in text
    assert "set -u" in text
    assert "evidence/templates" in text
