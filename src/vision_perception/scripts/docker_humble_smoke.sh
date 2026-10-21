#!/usr/bin/env bash
# 云端 / PC：用官方 ros:humble 镜像做两包 colcon + launch 解析 + skeleton/假流冒烟。
# 假数据结果不得记实机 PASS。需要本机已安装并可访问的 Docker。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
IMAGE="${VISION_DOCKER_IMAGE:-ros:humble-ros-base-jammy}"
WS_IN_DOCKER=/ws

echo "[docker_humble_smoke] root=$ROOT image=$IMAGE"

sudo docker run --rm \
  -v "$ROOT:$WS_IN_DOCKER" \
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
  ros-humble-cv-bridge
set +u
source /opt/ros/humble/setup.bash
set -u
python3 -m pip install --no-cache-dir -q "numpy>=1.26.4,<2" \
  "opencv-python-headless==4.10.0.84" "onnxruntime==1.20.1" pytest
rm -rf /tmp/vp_ws
mkdir -p /tmp/vp_ws/src
cp -a '"$WS_IN_DOCKER"'/src/vision_perception /tmp/vp_ws/src/
cp -a '"$WS_IN_DOCKER"'/src/vision_perception_interfaces /tmp/vp_ws/src/
# drop local __pycache__ noise
find /tmp/vp_ws/src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
cd /tmp/vp_ws
colcon build --symlink-install --packages-select vision_perception_interfaces vision_perception
set +u
source install/setup.bash
set -u
bash src/vision_perception/scripts/check_ament_prefix_hook.sh
ros2 launch vision_perception vision.launch.py --show-args | head -40
ros2 launch vision_perception vision_zed_subscribe.launch.py --show-args | head -20
ros2 launch vision_perception vision_object_transform.launch.py --show-args | head -20
# skeleton smoke (no camera / no model)
set +e
timeout 8 ros2 launch vision_perception vision.launch.py mode:=skeleton
SMOKE_EC=$?
set -e
echo "skeleton_launch_exit=$SMOKE_EC"
cd '"$WS_IN_DOCKER"'/src/vision_perception && python3 -m pytest test/ -q --tb=line
echo DOCKER_SMOKE_OK
'
