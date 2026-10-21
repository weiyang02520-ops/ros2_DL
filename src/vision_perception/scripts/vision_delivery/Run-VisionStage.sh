#!/usr/bin/env bash
# W7: 隔离视觉阶段入口（Linux / Jetson）。默认只预览；加 --execute 才执行。
# 不改生产软链、不启 ZED SDK、不发运动。一步一步跑，没有 All。
set -euo pipefail

STEP="${1:-}"
shift || true
EXECUTE=0
DURATION_SEC=20
WS="${VISION_ISOLATED_WS:-$HOME/vision_isolated_ws}"
REPO="${VISION_REPO:-}"
MODEL_PATH="${VISION_MODEL_PATH:-$HOME/vision_models/yolo11n-seg.onnx}"
MANIFEST_PATH="${VISION_MANIFEST_PATH:-$HOME/vision_models/model_manifest.json}"
LOG_DIR="${VISION_LOG_DIR:-$HOME/vision_logs}"
PID_FILE="${VISION_PID_FILE:-$LOG_DIR/vision_stage.pids}"

for arg in "$@"; do
  case "$arg" in
    --execute|-Execute) EXECUTE=1 ;;
    --duration=*) DURATION_SEC="${arg#*=}" ;;
    --ws=*) WS="${arg#*=}" ;;
    --repo=*) REPO="${arg#*=}" ;;
  esac
done

usage() {
  cat <<'EOF'
Usage: Run-VisionStage.sh <Step> [--execute] [--duration=20] [--ws=DIR] [--repo=DIR]

Steps:
  Deploy       仅准备/校验隔离包说明（不自动 start）
  Perception   启动 v1_ros ZED-subscribe 感知（需已有相机流；本脚本不启 ZED）
  Transform    启动 W5 转换（默认 disabled；需显式环境变量启用）
  Subscriber   只订阅打印 objects/status
  Capture      限时 ros2 bag 录准许话题
  StopOwn      仅停止本脚本记录的 PID
  Help

Default is preview. Pass --execute to run. No All step.
EOF
}

# Humble/colcon setup.bash references optional vars (COLCON_TRACE,
# AMENT_TRACE_SETUP_FILES, …) that trip `set -u`. Source with nounset off.
source_ros_setup() {
  local setup_file="$1"
  if [[ ! -f "${setup_file}" ]]; then
    return 1
  fi
  # Pre-define common optional vars so nested scripts stay safe under nounset.
  export COLCON_TRACE="${COLCON_TRACE:-}"
  export AMENT_TRACE_SETUP_FILES="${AMENT_TRACE_SETUP_FILES:-}"
  export AMENT_PYTHON_EXECUTABLE="${AMENT_PYTHON_EXECUTABLE:-}"
  set +u
  # shellcheck disable=SC1090
  source "${setup_file}"
  set -u
}

need_ros() {
  if [[ -z "${ROS_DISTRO:-}" ]]; then
    source_ros_setup /opt/ros/humble/setup.bash
  fi
  if [[ -f "$WS/install/setup.bash" ]]; then
    source_ros_setup "$WS/install/setup.bash"
  fi
}

preview() {
  echo "[PREVIEW] $*"
}

run_or_preview() {
  if [[ "$EXECUTE" -eq 1 ]]; then
    echo "[EXECUTE] $*"
    eval "$@"
  else
    preview "$*"
  fi
}

track_pid() {
  mkdir -p "$(dirname "$PID_FILE")"
  echo "$1" >>"$PID_FILE"
}

case "$STEP" in
  ""|Help|-h|--help)
    usage
    exit 0
    ;;
  Deploy)
    preview "Ensure isolated ws at $WS (production ~/ros2_DL read-only)"
    preview "colcon build --symlink-install --packages-select vision_perception_interfaces vision_perception"
    preview "Models: $MODEL_PATH + $MANIFEST_PATH"
    if [[ "$EXECUTE" -eq 1 ]]; then
      mkdir -p "$LOG_DIR" "$WS/src"
      if [[ -n "$REPO" ]]; then
        echo "[EXECUTE] sync note: copy vision packages into $WS/src from $REPO (manual/authorized)"
      fi
      echo "[EXECUTE] Deploy does not build automatically unless VISION_DEPLOY_BUILD=1"
      if [[ "${VISION_DEPLOY_BUILD:-0}" == "1" ]]; then
        need_ros
        (cd "$WS" && colcon build --symlink-install --packages-select vision_perception_interfaces vision_perception)
      fi
    fi
    ;;
  Perception)
    need_ros
    CMD="ros2 launch vision_perception vision_zed_subscribe.launch.py mode:=v1_ros enable_objects:=true enable_tracking:=false model_path:=$MODEL_PATH model_manifest_path:=$MANIFEST_PATH"
    if [[ "$EXECUTE" -eq 1 ]]; then
      mkdir -p "$LOG_DIR"
      # shellcheck disable=SC2086
      nohup bash -lc "$CMD" >"$LOG_DIR/perception.log" 2>&1 &
      track_pid $!
      echo "started perception pid $!; log $LOG_DIR/perception.log"
    else
      preview "$CMD"
    fi
    ;;
  Transform)
    need_ros
    EN="${VISION_TRANSFORM_ENABLED:-false}"
    CMD="ros2 launch vision_perception vision_object_transform.launch.py enabled:=$EN"
    if [[ "$EXECUTE" -eq 1 ]]; then
      mkdir -p "$LOG_DIR"
      nohup bash -lc "$CMD" >"$LOG_DIR/transform.log" 2>&1 &
      track_pid $!
      echo "started transform pid $!; enabled=$EN"
    else
      preview "$CMD  # default enabled:=false; set VISION_TRANSFORM_ENABLED=true only with real extrinsics"
    fi
    ;;
  Subscriber)
    need_ros
    CMD="ros2 run vision_perception vision_subscribe_objects --ros-args"
    # Prefer module CLI:
    CMD="ros2 run vision_perception vision_subscribe_objects"
    if [[ "$EXECUTE" -eq 1 ]]; then
      run_or_preview "$CMD"
    else
      preview "$CMD"
    fi
    ;;
  Capture)
    need_ros
    mkdir -p "$LOG_DIR"
    OUT="$LOG_DIR/bag_$(date +%Y%m%d_%H%M%S)"
    TOPICS="/dg/vision/objects /dg/vision/detections_2d /dg/vision/status /dg/vision/objects_target /dg/vision/transform_status"
    CMD="ros2 bag record -o $OUT $TOPICS --max-bag-duration $DURATION_SEC"
    if [[ "$EXECUTE" -eq 1 ]]; then
      # shellcheck disable=SC2086
      timeout "${DURATION_SEC}" ros2 bag record -o "$OUT" $TOPICS || true
      echo "bag dir: $OUT (duration<=${DURATION_SEC}s)"
    else
      preview "$CMD"
    fi
    ;;
  StopOwn)
    if [[ ! -f "$PID_FILE" ]]; then
      echo "No pid file $PID_FILE"
      exit 0
    fi
    if [[ "$EXECUTE" -eq 1 ]]; then
      while read -r pid; do
        [[ -z "$pid" ]] && continue
        if kill -0 "$pid" 2>/dev/null; then
          echo "stopping $pid"
          kill "$pid" || true
        fi
      done <"$PID_FILE"
      : >"$PID_FILE"
    else
      preview "kill PIDs listed in $PID_FILE only"
      cat "$PID_FILE" || true
    fi
    ;;
  *)
    echo "Unknown step: $STEP" >&2
    usage
    exit 2
    ;;
esac
