#!/usr/bin/env bash
# QEMU user-mode arm64 smoke（≠ Jetson；无 CUDA/JetPack）。
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# Prefer explicit arm64v8 tag — multi-arch tags often reuse local amd64 cache.
IMAGE="${VISION_ARM64_IMAGE:-arm64v8/ros:humble-ros-base}"
WS_IN_DOCKER=/ws
echo "[arm64_qemu] root=$ROOT image=$IMAGE platform=linux/arm64"
echo "[arm64_qemu] NOTE: QEMU ≠ Jetson (no CUDA/JetPack)"

# binfmt_misc must be mounted for user-mode emulation in this VM class.
if [[ ! -d /proc/sys/fs/binfmt_misc ]] || [[ ! -f /proc/sys/fs/binfmt_misc/status ]]; then
  sudo mkdir -p /proc/sys/fs/binfmt_misc
  sudo mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc || true
fi
sudo docker run --privileged --rm tonistiigi/binfmt --install arm64 \
  >/tmp/binfmt_install.log 2>&1 || cat /tmp/binfmt_install.log || true

echo "[arm64_qemu] pulling..."
if ! sudo docker pull --platform linux/arm64 "$IMAGE"; then
  echo "ARM64_PULL_FAIL image=$IMAGE"
  exit 3
fi

sudo docker run --rm --platform linux/arm64 \
  -v "$ROOT:$WS_IN_DOCKER" \
  -w "$WS_IN_DOCKER" \
  "$IMAGE" \
  bash -lc "
set -eo pipefail
export DEBIAN_FRONTEND=noninteractive
export AMENT_TRACE_SETUP_FILES=
echo uname=\$(uname -m)
apt-get update -qq
apt-get install -y -qq python3-pip python3-colcon-common-extensions \
  ros-humble-vision-msgs ros-humble-diagnostic-msgs \
  ros-humble-tf2-ros ros-humble-launch-ros
set +u
source /opt/ros/humble/setup.bash
set -u
set +e
python3 -m pip install --no-cache-dir 'numpy>=1.26.4,<2'; echo pip_numpy=\$?
python3 -m pip install --no-cache-dir 'opencv-python-headless==4.10.0.84'; echo pip_opencv=\$?
python3 -m pip install --no-cache-dir 'onnxruntime==1.20.1'; echo pip_ort=\$?
set -e
python3 - <<'PY'
import sys
print('python', sys.version)
for name in ('numpy','cv2','onnxruntime'):
    try:
        m=__import__(name if name!='cv2' else 'cv2')
        ver=getattr(m,'__version__', '?')
        print(name, 'OK', ver)
    except Exception as e:
        print(name, 'FAIL', e)
PY
rm -rf /tmp/vp_ws
mkdir -p /tmp/vp_ws/src
cp -a $WS_IN_DOCKER/src/vision_perception /tmp/vp_ws/src/
cp -a $WS_IN_DOCKER/src/vision_perception_interfaces /tmp/vp_ws/src/
find /tmp/vp_ws/src -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
cd /tmp/vp_ws
colcon build --symlink-install --packages-select vision_perception_interfaces vision_perception
set +u
source install/setup.bash
set -u
bash src/vision_perception/scripts/check_ament_prefix_hook.sh
python3 -m pip install --no-cache-dir -q pytest
cd $WS_IN_DOCKER/src/vision_perception
python3 -m pytest test/ -q --tb=line
echo ARM64_QEMU_SMOKE_OK
"
