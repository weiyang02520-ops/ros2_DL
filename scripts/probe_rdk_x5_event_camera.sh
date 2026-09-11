#!/usr/bin/env bash
# Read-only hardware probe for EVS event cameras on D-Robotics RDK X5.
# This script does not configure MIPI, load firmware, change network settings,
# or publish ROS messages. It only records what the running image exposes.
set -u

output="${1:-rdk_x5_event_camera_probe_$(date +%Y%m%d_%H%M%S).txt}"
mkdir -p "$(dirname "$output")" 2>/dev/null || true

run() {
  echo
  echo "=== $1 ==="
  shift
  "$@" 2>&1 || echo "COMMAND_FAILED=$?"
}

{
  echo "DG-202611 RDK X5 event-camera read-only probe"
  echo "probe_started=$(date --iso-8601=seconds 2>/dev/null || date)"
  echo "probe_host=$(hostname 2>/dev/null || true)"
  run "kernel" uname -a
  run "os_release" cat /etc/os-release
  run "device_tree_model" bash -c 'tr -d "\\0" </proc/device-tree/model 2>/dev/null || true'
  run "board_release_files" bash -c 'for f in /etc/board* /etc/hobot* /etc/drobotics*; do [ -f "$f" ] && { echo "--- $f"; sed -n "1,120p" "$f"; }; done'
  run "usb_devices" lsusb
  run "video_media_nodes" bash -c 'for pattern in /dev/video* /dev/media* /dev/v4l-subdev* /dev/event* /dev/i2c-*; do compgen -G "$pattern" || true; done'
  run "video_sysfs" bash -c 'for node in /sys/class/video4linux/video*; do [ -e "$node" ] || continue; echo "--- $node"; readlink -f "$node"; cat "$node/name" 2>/dev/null || true; done'
  run "media_sysfs" bash -c 'for node in /sys/class/media/media*; do [ -e "$node" ] || continue; echo "--- $node"; readlink -f "$node"; cat "$node/name" 2>/dev/null || true; done'
  run "v4l2_devices" bash -c 'command -v v4l2-ctl >/dev/null && v4l2-ctl --list-devices || echo "v4l2-ctl unavailable"'
  run "media_graph" bash -c 'command -v media-ctl >/dev/null && media-ctl -p || echo "media-ctl unavailable"'
  run "gstreamer_camera_plugins" bash -c 'command -v gst-inspect-1.0 >/dev/null && gst-inspect-1.0 | grep -Ei "evs|event|v4l2|mipi|camera" || echo "gst-inspect unavailable"'
  run "kernel_camera_messages" bash -c 'dmesg --since "10 minutes ago" 2>&1 | grep -Ei "evs|event.?camera|mipi|csi|v4l2|video|camera" || true'
  run "loaded_camera_modules" bash -c 'lsmod 2>/dev/null | grep -Ei "evs|camera|v4l2|mipi|csi" || true'
  run "ros_environment" bash -c 'command -v ros2 >/dev/null && { ros2 doctor --report 2>&1 || true; ros2 topic list -t 2>&1 || true; } || echo "ros2 unavailable"'
  run "event_camera_processes" bash -c 'ps -ef 2>/dev/null | grep -Ei "evs|event.?camera|camera" | grep -v grep || true'
  echo
  echo "=== probe_end ==="
  echo "probe_finished=$(date --iso-8601=seconds 2>/dev/null || date)"
} | tee "$output"

echo "PROBE_OUTPUT=$output"
