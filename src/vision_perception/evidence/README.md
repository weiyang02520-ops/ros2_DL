# Vision evidence templates (package-local)

Canonical empty shells for isolated workspaces that only sync
`vision_perception` + `vision_perception_interfaces`.

| Path | Stage |
|---|---|
| `templates/V0_SHELL/` | Skeleton status-only (`mode:=skeleton`) |
| `templates/V1_OFFLINE/` | Offline 2D CLI |
| `templates/V1_ROS/` | `mode:=v1_ros` fake/webcam |
| `templates/V2_POSITION/` | Offline objects / fake-depth smoke (`enable_objects`) |
| `templates/V3_TRACKING/` | Offline track sequence / `enable_tracking` scaffold (`tracks.csv.template`, `session_reset_timeline.yaml.template`) |

Installed to: `share/vision_perception/evidence/templates/…`

```bash
# From source tree (isolated ws):
SHARE_SRC=src/vision_perception/evidence/templates/V3_TRACKING
# After colcon install:
SHARE=$(ros2 pkg prefix vision_perception)/share/vision_perception/evidence/templates/V3_TRACKING

RUN=evidence/vision/$(date +%Y%m%d)_V3_TRACKING_smoke01
mkdir -p "$RUN/logs"
cp "$SHARE"/* "$RUN/"
# rename *.template → final names, fill fields, attach tracks.csv / metrics
```

Filled run directories still belong under the workspace/repo
`evidence/vision/<date>_<stage>_<run>/` (never overwrite history).
`ARM_READY=NO`. Synthetic / fake depth must keep `v2_accuracy=BLOCKED`.
Without identity annotations keep `idf1=BLOCKED` / `result=NOT_RUN`.
Do not claim ZED acceptance from these shells.
