# Vision examples (no model weights)

| File | Purpose |
|---|---|
| `model_manifest.template.json` | Fill SHA256 / license after a local YOLO11n-seg ONNX export |
| `smoke_rgb_hint.npy` | Tiny HxWx3 RGB format sample (crude blobs; YOLO often returns `[]`) |
| `make_smoke_rgb_npy.py` | Regenerate `smoke_rgb_hint.npy` |
| `golden_format_batch.json` | Offline JSON **format** sample (empty + one bottle); not a real ONNX golden |
| `eval_annotations.example.json` | Example V1 bbox GT for offline precision/recall CLI |
| `../evidence/templates/` | V1_OFFLINE / V1_ROS metadata shells (also in share/) |

Copy the manifest template next to your local ONNX (outside git), fill hashes:

```bash
model_path:=/home/YOU/vision_models/yolo11n-seg.onnx
model_manifest_path:=/home/YOU/vision_models/model_manifest.json
```

## Fake-image RGB source (`use_fake_image:=true`)

Launch argument: `fake_image_path:=/ABS/PATH` (aliases inside the node:
`image_path`, legacy `npy_path`).

Supported files: `.jpg` / `.jpeg` / `.png` (needs OpenCV), or HxWx3 `.npy`.

```bash
# Format-only sample (detections often empty — still a valid smoke):
SHARE=$(ros2 pkg prefix vision_perception)/share/vision_perception
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros use_fake_image:=true \
  fake_image_path:=$SHARE/examples/smoke_rgb_hint.npy \
  model_path:=$HOME/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=$HOME/vision_models/model_manifest.json

# Non-empty detections: feed a real bottle/cup photo
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros use_fake_image:=true \
  fake_image_path:=/home/YOU/Pictures/bottle_on_desk.jpg \
  model_path:=$HOME/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=$HOME/vision_models/model_manifest.json
```

Optional overlay (default off):

```bash
publish_debug_image:=true   # /dg/vision/debug_image ≤2 Hz; no GUI
```

See package `README.md` for Ubuntu103 shortest smoke commands and **未做项 (NOT_RUN)**.
