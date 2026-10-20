#!/usr/bin/env bash
# Shortest bootstrap for an isolated workspace that only contains
#   src/vision_perception
#   src/vision_perception_interfaces
# (zip/SFTP sync without the full monorepo / root .gitattributes).
#
# Usage (from the isolated workspace root):
#   bash src/vision_perception/scripts/bootstrap_isolated_ws.sh
#   bash src/vision_perception/scripts/bootstrap_isolated_ws.sh --pytest-only
#   bash src/vision_perception/scripts/bootstrap_isolated_ws.sh --build
#
# Does NOT claim camera/ONNX PASS. Fake-image smoke commands are printed only.
set -euo pipefail

PYTEST_ONLY=0
DO_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --pytest-only) PYTEST_ONLY=1 ;;
    --build) DO_BUILD=1 ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Discover workspace root: prefer directory that contains both packages under src/.
WS_ROOT=""
for candidate in \
  "$(pwd)" \
  "${PKG_ROOT}/../.." \
  "${PKG_ROOT}/.."
do
  if [[ -d "${candidate}/src/vision_perception" && -d "${candidate}/src/vision_perception_interfaces" ]]; then
    WS_ROOT="$(cd "${candidate}" && pwd)"
    break
  fi
done

if [[ -z "${WS_ROOT}" ]]; then
  echo "FAIL: could not find workspace with src/vision_perception and src/vision_perception_interfaces" >&2
  exit 1
fi

echo "OK: workspace=${WS_ROOT}"
cd "${WS_ROOT}"

# 1) Restore +x (zip/SFTP often drops execute bits; symlink-install needs them).
bash "${PKG_ROOT}/scripts/ensure_scripts_executable.sh"

# 2) LF guard on libexec wrappers (no dependency on monorepo root .gitattributes).
python3 - <<'PY'
from pathlib import Path
root = Path("src/vision_perception")
attrs = root / ".gitattributes"
assert attrs.is_file(), "missing package-local .gitattributes"
text = attrs.read_text(encoding="utf-8")
assert "scripts/**" in text and "eol=lf" in text
for path in sorted((root / "scripts").iterdir()):
    if not path.is_file():
        continue
    data = path.read_bytes()
    assert b"\r" not in data, f"CRLF in {path}; convert to LF"
print("OK: package-local LF attributes + scripts have no CR")
PY

# Source ROS / colcon setup without nounset: Humble setup.bash references
# optional vars (e.g. AMENT_TRACE_SETUP_FILES) that are unbound under `set -u`.
source_ros_setup() {
  local setup_file="$1"
  if [[ ! -f "${setup_file}" ]]; then
    return 1
  fi
  set +u
  # shellcheck disable=SC1090
  source "${setup_file}"
  set -u
}

# Evidence templates are package-local (no monorepo evidence/ tree required).
# Checked before --pytest-only so isolated sync fails fast if templates missing.
test -f src/vision_perception/evidence/templates/V1_ROS/metadata.json.template
test -f src/vision_perception/evidence/templates/V1_OFFLINE/metadata.json.template
echo "OK: package-local V1 evidence templates present"

# 3) Prefer Humble ros2 over a broken ~/.local/bin/ros2
if [[ -f /opt/ros/humble/setup.bash ]]; then
  source_ros_setup /opt/ros/humble/setup.bash
  export PATH="/opt/ros/humble/bin:${PATH}"
  hash -r || true
fi

if [[ "${PYTEST_ONLY}" -eq 1 ]]; then
  PYTHONPATH=src/vision_perception python3 -m pytest src/vision_perception/test -q
  exit 0
fi

if [[ "${DO_BUILD}" -eq 1 ]]; then
  rm -rf build/vision_perception build/vision_perception_interfaces \
         install/vision_perception install/vision_perception_interfaces
  colcon build --symlink-install --packages-select \
    vision_perception_interfaces vision_perception
  source_ros_setup install/setup.bash
  bash src/vision_perception/scripts/ensure_scripts_executable.sh
  bash src/vision_perception/scripts/check_ament_prefix_hook.sh
fi

PYTHONPATH=src/vision_perception python3 -m pytest src/vision_perception/test -q

cat <<'EOF'

--- Fake-image smoke (needs local ONNX; NOT_RUN without weights/photo) ---
source /opt/ros/humble/setup.bash
source install/setup.bash
export PATH="/opt/ros/humble/bin:$PATH"; hash -r
python3 -m pip install --user -r src/vision_perception/requirements-runtime.txt
SHARE=$(ros2 pkg prefix vision_perception)/share/vision_perception
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros use_fake_image:=true \
  fake_image_path:=$SHARE/examples/smoke_rgb_hint.npy \
  model_path:=$HOME/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=$HOME/vision_models/model_manifest.json \
  camera_contract:="DEV_WEBCAM_ONLY / NOT_ZED"

# V1 evidence shells (package / share — no repo-root evidence/ needed):
#   src/vision_perception/evidence/templates/V1_ROS/
#   $SHARE/evidence/templates/V1_ROS/

# Offline eval (no ROS) after you have detections JSON + annotations:
#   ros2 run vision_perception vision_offline_detect -- \
#     --images /path/to/img.jpg --model ... --manifest ... \
#     --out-json /tmp/v1.json --eval-annotations /path/to/annotations.json \
#     --out-metrics /tmp/metrics.json
EOF
