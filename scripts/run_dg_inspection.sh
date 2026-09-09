#!/usr/bin/env bash
set -euo pipefail

integration_ws="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
base_ws="${DG_BASE_WS:-/home/nvidia/ros2_DL}"

if [ ! -x "${integration_ws}/install/ylhb_llm/lib/ylhb_llm/inspection_display_ui_node" ]; then
  echo "DG UI overlay is not built: ${integration_ws}/install/ylhb_llm" >&2
  exit 2
fi

existing_stack="$(pgrep -af '[i]nspection_display_ui_node|[s]ystem_supervisor_node' || true)"
if [ -n "${existing_stack}" ]; then
  echo "Refusing to start a second inspection UI/Supervisor stack." >&2
  echo "${existing_stack}" >&2
  exit 3
fi

# Keep the robot's maps, routes, credentials, media and hardware configuration
# rooted in the protected base workspace while resolving ROS packages from the
# versioned DG overlay last.
export WS_DIR="${base_ws}"
export YLHB_OVERLAY_WS="${integration_ws}"

exec "${integration_ws}/scripts/run_on_jetson.sh" inspection "$@"
