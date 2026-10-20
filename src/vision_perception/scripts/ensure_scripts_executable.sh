#!/usr/bin/env bash
# Restore +x on vision libexec wrappers after zip/SFTP (mode bits often lost).
# Safe to re-run. Prefer running this BEFORE colcon --symlink-install so the
# install-space symlinks already point at executable sources; CMake also chmods
# at install time as a second line of defence.
#
# Usage (from package root or workspace):
#   bash src/vision_perception/scripts/ensure_scripts_executable.sh
#   # or after install:
#   bash "$(ros2 pkg prefix vision_perception)/share/vision_perception/scripts/ensure_scripts_executable.sh"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# When invoked from source tree: SCRIPT_DIR == .../scripts
# When invoked from install share: SCRIPT_DIR == .../share/vision_perception/scripts
PKG_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

LIBEXEC_WRAPPERS=(
  vision_perception_node
  vision_offline_detect
  vision_offline_objects
  vision_offline_track
  vision_webcam_publisher
  vision_fake_image_publisher
  vision_fake_depth_publisher
)
HELPER_SCRIPTS=(
  check_ament_prefix_hook.sh
  bootstrap_isolated_ws.sh
  ensure_scripts_executable.sh
)

chmod_list() {
  local dir="$1"
  shift
  local name path
  for name in "$@"; do
    path="${dir}/${name}"
    if [[ -e "${path}" ]]; then
      chmod a+x "${path}"
      # Symlink install: also chmod the ultimate target when possible.
      if [[ -L "${path}" ]]; then
        local target
        target="$(readlink -f "${path}" 2>/dev/null || true)"
        if [[ -n "${target}" && -e "${target}" ]]; then
          chmod a+x "${target}" || true
        fi
      fi
      echo "OK: chmod a+x ${path}"
    else
      echo "WARN: missing ${path}" >&2
    fi
  done
}

# Source-tree scripts/ (when this file lives in package scripts/).
if [[ -d "${SCRIPT_DIR}" ]]; then
  chmod_list "${SCRIPT_DIR}" "${LIBEXEC_WRAPPERS[@]}" "${HELPER_SCRIPTS[@]}"
fi

# Install-space libexec if ROS env already knows the package.
if command -v ros2 >/dev/null 2>&1; then
  if PREFIX="$(ros2 pkg prefix vision_perception 2>/dev/null)"; then
    if [[ -d "${PREFIX}/lib/vision_perception" ]]; then
      chmod_list "${PREFIX}/lib/vision_perception" "${LIBEXEC_WRAPPERS[@]}"
    fi
  fi
fi

# Common colcon layout relative to package: ../../install/vision_perception/lib/...
CANDIDATE_LIBEXEC="${PKG_ROOT}/../../install/vision_perception/lib/vision_perception"
if [[ -d "${CANDIDATE_LIBEXEC}" ]]; then
  chmod_list "$(cd "${CANDIDATE_LIBEXEC}" && pwd)" "${LIBEXEC_WRAPPERS[@]}"
fi

echo "OK: vision_perception script execute bits ensured"
