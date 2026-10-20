# vision_perception

Independent manipulation-vision ROS2 package (arm-independent).

## Current behaviour

| Path | Status |
|---|---|
| ROS `mode:=skeleton` (default) | `/dg/vision/status` only (`SKELETON_ONLY`). No image sub, no inference, no detections. |
| ROS `mode:=v1_ros` (explicit) | Subscribe `sensor_msgs/Image` on configurable `rgb_topic`, run ONNX bottle/cup detector, publish `VisionDetectionArray` on `/dg/vision/detections_2d` + status (`source_session_id` / `backend` / STALE). |
| Optional `publish_debug_image:=true` | Annotated `sensor_msgs/Image` on `/dg/vision/debug_image` (≤2 Hz). **Default off.** |
| Optional `vision_webcam_publisher` | V4L2/OpenCV → Image. Started only with `use_webcam:=true`. |
| Optional `vision_fake_image_publisher` | Synthetic/file RGB for no-camera smoke tests (`use_fake_image:=true`). |
| Optional `vision_fake_depth_publisher` | Constant 32FC1 depth + synthetic CameraInfo (`use_fake_depth:=true`). Mirrors RGB stamps. |
| Optional `enable_objects:=true` (v1_ros only) | V2: pair depth+CameraInfo, publish `VisionObjectArray` on `/dg/vision/objects`. **Default false.** |
| Optional `enable_tracking:=true` (v1_ros only) | V3: short-horizon per-class IoU tracker (**deterministic greedy**, not Hungarian). **Default false.** Confirmed matches fill `object_id` / `tracking_valid` on objects. |
| Offline CLI `vision_offline_detect` | File → JSON/CSV. No ROS camera claim. |
| Offline CLI `vision_offline_objects` | RGB + depth `.npy` + synthetic pinhole → objects JSON/CSV (coverage only). |
| Offline CLI `vision_offline_track` | Detection-sequence JSON → tracks JSON/CSV + V3 scaffold metrics (`--identity-annotations` can compute numeric IDF1; `result` stays `NOT_RUN`). |
| `object_id` publish path | Only on `/dg/vision/objects` when `enable_objects` + tracking (or offline_objects `--enable-tracking`). Tracking-only does not extend `VisionDetection2D`. |
| V2 mask | YOLO-seg contour when `output1` present; else `bbox_fill` fallback. |
| Legacy `mode:=v1` | **Rejected** (non-zero exit). |
| ZED / production camera contract | **Not authorized here.** `camera_contract=DEV_WEBCAM_ONLY / NOT_ZED` for v1_ros. Node may *subscribe* to ZED topic names but never starts the SDK. |
| Arm / grasp | **Not authorized.** `ARM_READY=NO`. `orientation_valid` stays false through V3. |

### Module stages (V0–V3)

| Stage | Gate | Core modules | Default |
|---|---|---|---|
| V0 skeleton | `mode:=skeleton` | status only | on |
| V1 detect | `mode:=v1_ros` / offline CLI | image_io, onnx_backend, postprocess, message_mapping | explicit |
| V2 objects | `enable_objects:=true` | frame_pairing, surface_sample, objects_pipeline | **false** |
| V3 track | `enable_tracking:=true` | tracker (+ objects fields when V2 on) | **false** |

Real ZED / V2 accuracy / V3 IDF1 remain **NOT_RUN** (no PASS from synthetic smoke).

### 未做项（NOT_RUN — 勿记 PASS）

| Item | Why blocked |
|---|---|
| 实时相机 / 瓶杯图冒烟验收 | Needs Ubuntu103 + local ONNX + real bottle/cup photo or `/dev/video*` |
| 导航 / 底盘 / `cmd_vel` / MODEL bringup | Out of scope; must not change |
| 实机 ZED 深度配准 / 透明物体三维 | Needs real ZED stream + fixture ground truth; fake depth only checks plumbing |
| V2 三维精度验收（median≤30 mm 等） | Needs independent surface-point truth (plan §10.2); synthetic plane ≠ PASS |
| V3 IDF1 / 身份标注验收 | Needs identity-annotated sequences; scaffold reports `result=NOT_RUN` / `idf1=BLOCKED` |
| 真 ONNX 黄金样例比对 | Weights stay out of git; synthetic postprocess goldens cover format only |

Evidence empty shells (package-local, works in isolated two-package sync):
`src/vision_perception/evidence/templates/{V1_OFFLINE,V1_ROS,V2_POSITION,V3_TRACKING}/`
(also installed under `share/vision_perception/evidence/templates/`).

**Hard rules:** the node never auto-downloads weights; `.onnx` / `.pt` must stay out of git (see root `.gitignore`). License of upstream YOLO/COCO weights is separate from this repo — review before use; do not publish or redistribute weights until cleared.

## Build (Humble)

`vision_perception` is **ament_cmake + ament_cmake_python** (not pure
`ament_python`) so `ament_package()` writes `ament_prefix_path` hooks into
`package.dsv`. Pure setuptools installs on Ubuntu103 left only `pythonpath`
hooks, which broke `ros2 pkg prefix` after `source install/setup.bash`.

```bash
source /opt/ros/humble/setup.bash
# Clean rebuild required after packaging-type change:
rm -rf build/vision_perception install/vision_perception
colcon build --symlink-install --packages-select vision_perception_interfaces vision_perception
source install/setup.bash

# Must work WITHOUT manually exporting AMENT_PREFIX_PATH:
ros2 pkg list | grep vision_perception
ros2 pkg prefix vision_perception
# prefix wiring may be local_setup.dsv -> environment/ament_prefix_path.sh
ls "$(ros2 pkg prefix vision_perception)/share/vision_perception/environment"
ros2 pkg executables vision_perception
# expect libexec scripts under install/vision_perception/lib/vision_perception/
bash src/vision_perception/scripts/check_ament_prefix_hook.sh
ros2 launch vision_perception vision.launch.py --show-args
```

Executables are installed from `scripts/` via CMake `install(PROGRAMS ... DESTINATION lib/vision_perception)`.
`ament_python_install_package` does not honor setuptools `entry_points`.

**Line endings:** package-local `src/vision_perception/.gitattributes` forces LF on
`scripts/**` (works even when the monorepo root `.gitattributes` is absent after a
two-package zip/SFTP sync). CRLF shebangs become `python3\r` and fail with exit 127.

**Execute bit:** zip/SFTP often drops `+x`. With `colcon --symlink-install`, libexec
entries are symlinks to `scripts/vision_*`, so a missing source bit breaks launch.
CMake `install(PROGRAMS … PERMISSIONS …)` plus a post-install `chmod a+x` repairs
install space (and the symlink target). After any non-git sync, still prefer:

```bash
bash src/vision_perception/scripts/ensure_scripts_executable.sh
# or full isolated bootstrap:
bash src/vision_perception/scripts/bootstrap_isolated_ws.sh
```

## Runtime Python pins (NumPy &lt; 2 — required)

`v1_ros` / webcam / offline need:

| Package | Pin |
|---|---|
| NumPy | `>=1.26.4,<2` |
| OpenCV | `opencv-python-headless==4.10.0.84` (full `opencv-python` also OK if same major) |
| ONNX Runtime | `onnxruntime==1.20.1` (CPU) |

**Install order matters.** NumPy 2.x breaks many OpenCV wheels (`_ARRAY_API not found` / `numpy.core.multiarray failed to import`). Observed on Ubuntu103 when NumPy 2 was present with an older cv2.

```bash
# Preferred one-shot (after workspace source, from repo or install share):
python3 -m pip install --user -r src/vision_perception/requirements-runtime.txt
# same file also installed as:
#   share/vision_perception/requirements-runtime.txt

# Or strictly in this order:
python3 -m pip install --user 'numpy>=1.26.4,<2'
python3 -m pip install --user 'opencv-python-headless==4.10.0.84'
python3 -m pip install --user 'onnxruntime==1.20.1'

# Verify (must show numpy 1.x)
python3 -c "import numpy,cv2,onnxruntime as o; print(numpy.__version__, cv2.__version__, o.__version__)"
```

Do **not** `pip install -U numpy` afterward. `setup.py` / `runtime_deps.py` encode the same pins; `mode:=v1_ros` refuses to start on NumPy ≥ 2.

## Local ONNX + manifest (required for v1_ros / offline)

Pipeline expects **YOLO11n-seg** COCO layout (V4 plan):

| Item | Required value |
|---|---|
| Input name | `images` |
| Input shape | `[1, 3, 640, 640]` FP32, values in `[0,1]` after `/255` |
| `output0` | `[1, 116, 8400]` = 4 xywh + 80 class scores + 32 mask coeffs |
| `output1` | `[1, 32, 160, 160]` mask prototypes (V1 publishes boxes only) |
| Classes used | COCO `bottle=39`, `cup=41` only |
| Export | FP32, imgsz=640, batch=1, `dynamic=false`, `simplify=false`, opset=17, **NMS not embedded** |

### Manifest template (JSON only, no weights in repo)

- Source template: `examples/model_manifest.template.json` (also installed under `share/vision_perception/examples/`)
- Copy beside your local ONNX, fill hashes/license:

```bash
# Example local layout (outside git / gitignored)
mkdir -p "$HOME/vision_models"
cp src/vision_perception/examples/model_manifest.template.json \
  "$HOME/vision_models/model_manifest.json"
# After export:
#   $HOME/vision_models/yolo11n-seg.onnx
#   edit model_manifest.json → onnx_sha256 / weights_sha256 / license
sha256sum "$HOME/vision_models/yolo11n-seg.onnx"
```

Required JSON fields: `source`, `onnx_sha256`, `license`, `input_name`, `input_shape`,
`output0_shape`, `output1_shape`, `class_map` (`bottle`→39, `cup`→41). Optional:
`weights_sha256`, `export_tool_versions`.

### How to obtain / export (isolated env — do not touch robot global Python)

Plan baseline: Ultralytics **8.3.0**, PyTorch **2.4.1**, torchvision **0.19.1**, ONNX **1.16.2**, Python 3.10 venv. Export is a **manual owner step**; this package will not download.

```bash
# On Ubuntu or WSL2 — separate venv (example only; pin versions you review)
python3.10 -m venv "$HOME/yolo11_export_venv"
source "$HOME/yolo11_export_venv/bin/activate"
pip install 'ultralytics==8.3.0' 'torch==2.4.1' 'torchvision==0.19.1' 'onnx==1.16.2'

# Ultralytics may fetch pretrained weights into its cache when you first load the name.
# That is outside this ROS package. Review upstream license before use.
python - <<'PY'
from ultralytics import YOLO
model = YOLO("yolo11n-seg.pt")  # local path preferred if you already have the file
model.export(
    format="onnx",
    imgsz=640,
    batch=1,
    dynamic=False,
    simplify=False,
    opset=17,
)
print("Move the produced .onnx next to your filled model_manifest.json")
PY
deactivate

# Deploy runtime (Humble side) needs onnxruntime CPU, e.g.:
#   pip install --user 'onnxruntime==1.20.1'   # or apt/wheel policy you choose
# Inference process must NOT import ultralytics/torch.
```

After export, verify ONNX I/O names/shapes match the table, fill `onnx_sha256`, set `license` only after review.

## Skeleton (default — safe)

```bash
ros2 launch vision_perception vision.launch.py
# Must still reject:
ros2 launch vision_perception vision.launch.py mode:=v1
ros2 run vision_perception vision_perception_node --ros-args -p mode:=v1
```

## Ubuntu103 shortest smoke (fake image + local ONNX)

Default remains **skeleton** (safe). Explicit `mode:=v1_ros` only.

**PATH note:** after `pip install --user ...`, `~/.local/bin` can shadow Humble
`ros2` with a broken/partial install. Prefer:

```bash
source /opt/ros/humble/setup.bash
source /path/to/ws/install/setup.bash
hash -r
type -a ros2
# first hit should be /opt/ros/humble/bin/ros2 (or the underlay), NOT a stale ~/.local copy
# If ~/.local wins:  export PATH="/opt/ros/humble/bin:$PATH"  and hash -r again
```

### A) Colour-block / format sample (detections often `[]` — still healthy)

```bash
SHARE=$(ros2 pkg prefix vision_perception)/share/vision_perception
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros \
  use_fake_image:=true \
  fake_image_path:=$SHARE/examples/smoke_rgb_hint.npy \
  model_path:=/home/weiyang/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=/home/weiyang/vision_models/model_manifest.json \
  camera_contract:="DEV_WEBCAM_ONLY / NOT_ZED"
```

### B) Non-empty detections — feed a real bottle/cup photo

```bash
# Put any local JPG/PNG of a bottle or cup on disk, then:
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros \
  use_fake_image:=true \
  fake_image_path:=/home/weiyang/Pictures/bottle_or_cup.jpg \
  model_path:=/home/weiyang/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=/home/weiyang/vision_models/model_manifest.json \
  camera_contract:="DEV_WEBCAM_ONLY / NOT_ZED"

ros2 topic echo /dg/vision/status --once
ros2 topic echo /dg/vision/detections_2d --once
```

Expect status `V1_ROS_DEV_WEBCAM` with `empty_detections_healthy=true`. With a clear
bottle/cup photo, `detections_2d` should sometimes be non-empty. Solid colour
blocks / `smoke_rgb_hint.npy` often stay `[]` (valid smoke).

Node aliases for the file: launch `fake_image_path`, or node params `image_path` /
legacy `npy_path`.

## Shortest webcam trial (Ubuntu / WSL2 + `/dev/video*`)

WSL2 needs USB camera attached to WSL (`usbipd` on Windows) so that `ls /dev/video*` works inside the Linux distro that runs Humble. Native Ubuntu: built-in laptop camera is usually `/dev/video0` (index `0`).

### Expected FATAL without model (by design)

```bash
ros2 launch vision_perception vision.launch.py mode:=v1_ros use_webcam:=true
# → non-zero exit, stderr like:
# [vision_perception_node] FATAL: v1_ros mode requires model_path
#   Hint: v1_ros needs absolute local paths model_path:=... model_manifest_path:=...
```

Same if `model_path` is set but the file/manifest is missing or SHA256 mismatches.

### With local model + front camera

```bash
ls -l /dev/video*          # must exist for use_webcam:=true
source /opt/ros/humble/setup.bash
source install/setup.bash  # your colcon workspace

ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros \
  use_webcam:=true \
  video_device:=0 \
  rgb_topic:=/dg/vision/webcam/image_raw \
  model_path:=$HOME/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=$HOME/vision_models/model_manifest.json \
  camera_contract:="DEV_WEBCAM_ONLY / NOT_ZED"
```

Watch:

```bash
ros2 topic echo /dg/vision/status --once
ros2 topic echo /dg/vision/detections_2d --once
ros2 topic hz /dg/vision/detections_2d
```

If `use_webcam:=true` but no device: webcam publisher FATALS with “Failed to open V4L2/OpenCV device”.

### No `/dev/video` — see “Ubuntu103 shortest smoke” above

Do **not** combine `use_webcam:=true` and `use_fake_image:=true`.

### Optional debug image (default off)

```bash
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros use_fake_image:=true \
  fake_image_path:=$SHARE/examples/smoke_rgb_hint.npy \
  model_path:=$HOME/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=$HOME/vision_models/model_manifest.json \
  publish_debug_image:=true
# → /dg/vision/debug_image at ≤2 Hz when frames are processed
```

## V2 offline smoke (fake RGB + fake depth → `/dg/vision/objects`)

Defaults stay safe: `enable_objects:=false` (no `/objects`). Explicit opt-in only.

```bash
SHARE=$(ros2 pkg prefix vision_perception)/share/vision_perception
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros \
  use_fake_image:=true \
  use_fake_depth:=true \
  enable_objects:=true \
  fake_image_path:=$SHARE/examples/smoke_rgb_hint.npy \
  fake_depth_m:=1.0 \
  model_path:=$HOME/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=$HOME/vision_models/model_manifest.json \
  camera_contract:="DEV_WEBCAM_ONLY / NOT_ZED"
```

`use_fake_depth:=true` starts `vision_fake_depth_publisher` as the **stamp
master** (5 Hz timer): CameraInfo then 32FC1 depth on
`/dg/vision/fake/{camera_info,depth}` with a shared `now()` stamp. With
`use_fake_image:=true`, the fake RGB node sets
`stamp_source_topic:=/dg/vision/fake/depth` and republishes RGB with that same
stamp *after* depth/info — so pairing is not racing two independent timers
(earlier bug: skew ≈ 0.20 s → `DEPTH_UNPAIRED`).

The vision node also holds RGB up to `sync_wait_sec` (default 0.100) for a
matching depth (plan §7.1), which covers residual delivery reordering.

Watch:

```bash
ros2 topic echo /dg/vision/status --once
ros2 topic echo /dg/vision/detections_2d --once
ros2 topic echo /dg/vision/objects --once
```

Expect `object_output_active=true`, `arm_ready=NO`, `last_pair_reason=OK` when
depth+info are flowing (even if `detections=[]` / `objects=[]` — paired empty
scene, not `DEPTH_UNPAIRED`). Every object: `orientation_valid=false` /
`tracking_valid=false`. With constant fake depth and a large enough bbox after
erode, `position_valid` may be true (synthetic only — not a ZED accuracy PASS).
Missing depth/info after `sync_wait_sec` → `DEPTH_UNPAIRED` or status
`V2_OBJECTS_NO_CALIBRATION`, never invented XYZ.

Configured input names (YAML / launch; subscribe only, no ZED start):

| Param | Default |
|---|---|
| `depth_topic` | `/zed/zed_node/depth/depth_registered` (fake remap → `/dg/vision/fake/depth`) |
| `camera_info_topic` | `/zed/zed_node/rgb/color/rect/camera_info` (fake → `/dg/vision/fake/camera_info`) |
| `sync_tolerance_sec` | `0.010` |
| `sync_wait_sec` | `0.100` |
| `min_depth_m` / `max_depth_m` | `0.5` / `1.5` |

## Unit tests (no ROS / no camera)

```bash
PYTHONPATH=src/vision_perception python3 -m pytest src/vision_perception/test -q
```

## Offline file CLI

```bash
ros2 run vision_perception vision_offline_detect -- \
  --images /path/to/img.npy \
  --model $HOME/vision_models/yolo11n-seg.onnx \
  --manifest $HOME/vision_models/model_manifest.json \
  --out-json /tmp/v1_offline.json \
  --out-csv /tmp/detections.csv
```

### Offline V2 objects (synthetic / recorded depth `.npy`)

```bash
# depth.npy: HxW float32 metres, same size as the RGB image
ros2 run vision_perception vision_offline_objects -- \
  --images /path/to/img.npy \
  --depths /path/to/depth.npy \
  --model $HOME/vision_models/yolo11n-seg.onnx \
  --manifest $HOME/vision_models/model_manifest.json \
  --fx 500 --fy 500 \
  --out-json /tmp/v2_objects.json \
  --out-csv /tmp/objects.csv \
  --out-metrics /tmp/v2_coverage.json
```

`--out-metrics` reports pair/position_valid **coverage** with
`result=NOT_RUN` and `v2_accuracy=BLOCKED` (no independent surface truth →
never mark accuracy PASS). `orientation_valid` stays false; `arm_ready=NO`.

### Offline V3 track (detection-sequence JSON, no camera)

```bash
# Input: frames with stamp_sec + detections (bbox centre/size). No ONNX required.
ros2 run vision_perception vision_offline_track -- \
  --sequence examples/track_sequence.example.json \
  --out-json /tmp/tracks.json \
  --out-csv /tmp/tracks.csv \
  --out-metrics /tmp/v3_scaffold.json
```

Matcher is **deterministic greedy per-class IoU** (not SciPy Hungarian).
Without `--identity-annotations`, metrics keep `idf1=BLOCKED`. With labels,
numeric IDF1 may be reported but **`result` stays `NOT_RUN`** (no auto PASS).

```bash
ros2 run vision_perception vision_offline_track -- \
  --sequence examples/track_sequence.example.json \
  --identity-annotations examples/track_identity_annotations.example.json \
  --out-metrics /tmp/v3_idf1_scaffold.json
```

`vision_offline_objects --enable-tracking` fills `object_id` / `tracking_session_id`
across a file sequence (CSV columns included even when tracking is off).

Startup-only §5/§9 knobs (defaults from the plan): `sync_queue_size`,
`max_observation_age_sec` (drop old source stamps), `mask_erode_kernel`,
`depth_patch_size`, `min_patch_pixels`, `min_valid_depth_fraction`,
`max_depth_mad_m`, `max_depth_spread_m`.

## Boundaries

No MODEL-1/2/3, Nav2/AMCL/SLAM, EKF/TF, cmd_vel, chassis, production bringup, `ylhb_*`, or ZED SDK/launch changes. `/dg/vision/objects` publishes only when `enable_objects:=true` (default false).

## Ubuntu103 sync (same PR branch / full git checkout)

```bash
cd /path/to/ws/src/<this-repo>
git fetch origin cursor/vision-v1-offline-1fcf
git checkout cursor/vision-v1-offline-1fcf
git pull --ff-only origin cursor/vision-v1-offline-1fcf

source /opt/ros/humble/setup.bash
# Prefer Humble ros2 over a broken ~/.local/bin/ros2:
export PATH="/opt/ros/humble/bin:$PATH"; hash -r

bash src/vision_perception/scripts/ensure_scripts_executable.sh
rm -rf build/vision_perception build/vision_perception_interfaces \
       install/vision_perception install/vision_perception_interfaces
colcon build --symlink-install --packages-select \
  vision_perception_interfaces vision_perception
source install/setup.bash
bash src/vision_perception/scripts/ensure_scripts_executable.sh
bash src/vision_perception/scripts/check_ament_prefix_hook.sh

python3 -m pip install --user -r src/vision_perception/requirements-runtime.txt
PYTHONPATH=src/vision_perception python3 -m pytest src/vision_perception/test -q
```

## Isolated workspace (only the two vision packages)

After zip/SFTP of `vision_perception` + `vision_perception_interfaces` into
`ws/src/` (no monorepo root `.gitattributes`):

```bash
cd /path/to/isolated_ws
bash src/vision_perception/scripts/bootstrap_isolated_ws.sh --build
# pytest-only (no colcon):
#   bash src/vision_perception/scripts/bootstrap_isolated_ws.sh --pytest-only
```

The bootstrap script: restores `+x`, checks package-local LF / evidence templates
(no monorepo `evidence/` needed), optionally builds (CMake `install(CODE)` chmod
for libexec), runs pytest, and prints fake-image smoke commands (NOT_RUN without
ONNX). Defaults keep `enable_objects` / `enable_tracking` false; see V2 fake-depth smoke above.

**You should not need a manual `chmod +x scripts/vision_*` after a normal colcon
install** — CMake post-install `chmod` (bracket-arg `install(CODE)`) covers it.
If launch still says “Permission denied” / not executable, re-run
`ensure_scripts_executable.sh` (zip edge cases).

## Offline V1 evaluation (no ROS)

```bash
ros2 run vision_perception vision_offline_detect -- \
  --images /path/to/img.jpg \
  --model $HOME/vision_models/yolo11n-seg.onnx \
  --manifest $HOME/vision_models/model_manifest.json \
  --out-json /tmp/v1_offline.json \
  --eval-annotations src/vision_perception/examples/eval_annotations.example.json \
  --out-metrics /tmp/v1_metrics.json
```

Annotation schema: `examples/eval_annotations.example.json`. Metrics follow plan
§10.1 (per-class precision/recall; zero denominators → non-computable, not 100%).
