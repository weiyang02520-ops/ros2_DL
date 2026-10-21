#!/usr/bin/env bash
# 真 ONNX + 假流端到端冒烟（Docker Humble）。结果仅 SYNTHETIC，不得记实机 PASS。
# 需要：/opt/cursor/artifacts/vision_models/{yolo11n-seg.onnx,model_manifest.json,sample_bottle_cup.jpg}
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
IMAGE="${VISION_DOCKER_IMAGE:-ros:humble-ros-base-jammy}"
ART="${VISION_MODELS_DIR:-/opt/cursor/artifacts/vision_models}"
WS_IN_DOCKER=/ws
ART_IN_DOCKER=/models

test -f "$ART/yolo11n-seg.onnx"
test -f "$ART/model_manifest.json"
test -f "$ART/sample_bottle_cup.jpg"

echo "[e2e_synthetic] root=$ROOT art=$ART"

sudo docker run --rm \
  -v "$ROOT:$WS_IN_DOCKER" \
  -v "$ART:$ART_IN_DOCKER:ro" \
  -w "$WS_IN_DOCKER" \
  "$IMAGE" \
  bash -lc '
set -eo pipefail
export DEBIAN_FRONTEND=noninteractive
export AMENT_TRACE_SETUP_FILES=
apt-get update -qq
apt-get install -y -qq \
  python3-pip python3-colcon-common-extensions \
  ros-humble-vision-msgs ros-humble-diagnostic-msgs \
  ros-humble-tf2-ros ros-humble-launch-ros \
  ros-humble-cv-bridge >/dev/null
set +u
source /opt/ros/humble/setup.bash
set -u
python3 -m pip install --no-cache-dir -q "numpy>=1.26.4,<2" \
  "opencv-python-headless==4.10.0.84" "onnxruntime==1.20.1"
rm -rf /tmp/vp_ws
mkdir -p /tmp/vp_ws/src
cp -a '"$WS_IN_DOCKER"'/src/vision_perception /tmp/vp_ws/src/
cp -a '"$WS_IN_DOCKER"'/src/vision_perception_interfaces /tmp/vp_ws/src/
find /tmp/vp_ws/src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
cd /tmp/vp_ws
colcon build --symlink-install --packages-select vision_perception_interfaces vision_perception
set +u
source install/setup.bash
set -u

MODEL='"$ART_IN_DOCKER"'/yolo11n-seg.onnx
MAN='"$ART_IN_DOCKER"'/model_manifest.json
IMG='"$ART_IN_DOCKER"'/sample_bottle_cup.jpg

# background launch: fake RGB+depth + V2 objects
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros \
  use_fake_image:=true \
  use_fake_depth:=true \
  enable_objects:=true \
  enable_tracking:=false \
  fake_image_path:=$IMG \
  fake_depth_m:=1.0 \
  model_path:=$MODEL \
  model_manifest_path:=$MAN \
  camera_contract:="DEV_WEBCAM_ONLY / NOT_ZED" \
  >/tmp/e2e_launch.log 2>&1 &
LPID=$!
cleanup() { kill $LPID 2>/dev/null || true; wait $LPID 2>/dev/null || true; }
trap cleanup EXIT

# wait for topics
for i in $(seq 1 40); do
  if ros2 topic list 2>/dev/null | grep -q /dg/vision/objects; then
    break
  fi
  sleep 1
done

echo "=== topic list (vision) ==="
ros2 topic list | grep /dg/vision || true

echo "=== status once ==="
timeout 10 ros2 topic echo /dg/vision/status --once 2>/dev/null | tee /tmp/e2e_status.txt || true

echo "=== detections_2d once ==="
timeout 15 ros2 topic echo /dg/vision/detections_2d --once 2>/dev/null | tee /tmp/e2e_det.txt || true

echo "=== objects once ==="
timeout 15 ros2 topic echo /dg/vision/objects --once 2>/dev/null | tee /tmp/e2e_obj.txt || true

python3 - <<'"'"'PY'"'"'
from pathlib import Path
status=Path("/tmp/e2e_status.txt").read_text(errors="replace")
det=Path("/tmp/e2e_det.txt").read_text(errors="replace")
obj=Path("/tmp/e2e_obj.txt").read_text(errors="replace")
print("CHECK source_kind_SYNTHETIC", "SYNTHETIC_DEV" in status or "SYNTHETIC_DEV" in det or "SYNTHETIC_DEV" in obj)
print("CHECK not_LIVE_as_only", "LIVE_CAMERA" not in det.split("source_kind")[-1][:40] if "source_kind" in det else "n/a")
print("CHECK has_detections_field", "detections:" in det or "class_name:" in det)
print("CHECK has_objects_field", "objects:" in obj or "position_valid:" in obj)
# soft asserts for pipeline plumbing
assert "SYNTHETIC_DEV" in status or "SYNTHETIC_DEV" in det or "SYNTHETIC_DEV" in obj, "expected SYNTHETIC_DEV"
assert "LIVE_CAMERA" not in (det+obj) or "SYNTHETIC_DEV" in (det+obj), "fake must not claim LIVE alone"
print("E2E_SYNTHETIC_SMOKE_OK")
PY
'
