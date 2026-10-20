#!/usr/bin/env bash
# Regression check after colcon install (run on Humble VM).
# Usage:
#   source /opt/ros/humble/setup.bash
#   source install/setup.bash
#   bash src/vision_perception/scripts/check_ament_prefix_hook.sh
#
# Note: ament_cmake may wire AMENT_PREFIX_PATH via
#   share/<pkg>/local_setup.dsv -> environment/ament_prefix_path.sh
# rather than share/<pkg>/package.dsv -> hook/ament_prefix_path.*.
# Do not require the hook/ path alone (false FAIL on working installs).
set -euo pipefail

PKG=vision_perception

if ! ros2 pkg prefix "$PKG" >/dev/null 2>&1; then
  echo "FAIL: ros2 pkg prefix $PKG failed (AMENT_PREFIX_PATH missing package?)"
  echo "AMENT_PREFIX_PATH=${AMENT_PREFIX_PATH:-<unset>}"
  exit 1
fi

PREFIX="$(ros2 pkg prefix "$PKG")"
SHARE="$PREFIX/share/$PKG"

case ":${AMENT_PREFIX_PATH}:" in
  *":${PREFIX}:"*) ;;
  *)
    echo "FAIL: AMENT_PREFIX_PATH does not contain $PREFIX"
    echo "AMENT_PREFIX_PATH=$AMENT_PREFIX_PATH"
    exit 1
    ;;
esac

# Accept either modern environment/ wiring or older hook/ wiring.
PREFIX_HOOK_FOUND=0
CANDIDATES=(
  "$SHARE/environment/ament_prefix_path.sh"
  "$SHARE/environment/ament_prefix_path.dsv"
  "$SHARE/local_setup.dsv"
  "$SHARE/hook/ament_prefix_path.sh"
  "$SHARE/hook/ament_prefix_path.dsv"
  "$SHARE/package.dsv"
)

for path in "${CANDIDATES[@]}"; do
  if [[ -f "$path" ]] && grep -Eq 'AMENT_PREFIX_PATH|ament_prefix_path' "$path"; then
    echo "OK: prefix wiring referenced in $path"
    PREFIX_HOOK_FOUND=1
  fi
done

if [[ "$PREFIX_HOOK_FOUND" -ne 1 ]]; then
  echo "FAIL: no ament_prefix_path / AMENT_PREFIX_PATH reference under $SHARE"
  echo "Looked for environment/, local_setup.dsv, hook/, package.dsv"
  ls -la "$SHARE" 2>/dev/null || true
  exit 1
fi

LIBEXEC="$PREFIX/lib/$PKG"
for exe in vision_perception_node vision_offline_detect vision_offline_objects vision_offline_track vision_webcam_publisher vision_fake_image_publisher vision_fake_depth_publisher; do
  if [[ ! -x "$LIBEXEC/$exe" ]]; then
    echo "FAIL: missing executable $LIBEXEC/$exe"
    ls -la "$LIBEXEC" 2>/dev/null || true
    exit 1
  fi
  # Guard against CRLF shebang surviving into install space.
  if head -n 1 "$LIBEXEC/$exe" | grep -q $'\r'; then
    echo "FAIL: CRLF shebang in $LIBEXEC/$exe (python3\\r). Force LF via .gitattributes."
    exit 1
  fi
done

echo "OK: $PKG prefix=$PREFIX"
echo "OK: AMENT_PREFIX_PATH contains package prefix"
echo "OK: libexec scripts present under $LIBEXEC (LF shebang)"
ros2 pkg executables "$PKG"
ros2 launch "$PKG" vision.launch.py --show-args >/dev/null
echo "OK: ros2 launch $PKG vision.launch.py --show-args"
