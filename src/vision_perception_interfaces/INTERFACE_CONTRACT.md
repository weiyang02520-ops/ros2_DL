# vision_perception_interfaces — frozen observation contract (plan §3)

| Topic | Message | First publish stage |
|---|---|---|
| `/dg/vision/detections_2d` | `VisionDetectionArray` | V1 |
| `/dg/vision/objects` | `VisionObjectArray` | **V2** (`enable_objects:=true` only) |
| `/dg/vision/status` | `diagnostic_msgs/DiagnosticArray` | V0+ |
| `/dg/vision/debug_image` | `sensor_msgs/Image` | V1 optional, default off |

## Observation keys (shared)

`source_session_id`, `observation_id`, `detection_index`, `header`, `calibration_id`, `source_kind`.

## Hard semantics

- `orientation_valid` is **always false** through V1–V3; orientation components are NaN when unknown.
- `position_valid=true` is **not** arm authorization. `ARM_READY` is a status diagnostic field only (`NO` until an arm stage is authorized).
- Default runtime keeps `enable_objects:=false` (V1 path: detections only, no `/objects`).
- With `mode:=v1_ros` and `enable_objects:=true`, the node may publish `/dg/vision/objects` after depth + CameraInfo pairing. Missing depth/calibration → `position_valid=false` / `DEPTH_UNPAIRED` (or status degrade); never forge 3D.
- V2 (tracking off): `object_id` and `tracking_session_id` empty; `tracking_valid=false`.
- V3 (`enable_tracking:=true`, `mode:=v1_ros` only): confirmed matches get non-empty
  `object_id` and `tracking_valid=true` within `tracking_session_id` on
  **`VisionObject` / `/objects`** (requires `enable_objects` to publish IDs).
  `VisionDetection2D` does not carry `object_id`. Tentative / unmatched stay empty
  + false. STALE / calibration change / clock rollback mint a new session; expired
  IDs are never reused. Matcher: deterministic greedy per-class IoU (not Hungarian).
  No ReID / cross-restart identity.
- Consumers of legacy `/perception/localized_objects` are out of scope; this package does not replace them silently.

## Runtime gates (vision_perception package)

- `enable_objects` defaults **false**; `true` allowed only for `mode:=v1_ros` (subscribes configurable `depth_topic` + `camera_info_topic`).
- `enable_tracking` defaults **false**; `true` allowed only for `mode:=v1_ros`
  (skeleton / offline reject). Tracker params: `tracker_match_iou` (0.30),
  `tracker_confirm_hits` (3), `tracker_lost_timeout_sec` (0.70).
- Default topic names (configurable; ZED names are subscription targets only — this package does **not** start the ZED SDK or edit ZED launch):
  - depth: `/zed/zed_node/depth/depth_registered`
  - camera_info: `/zed/zed_node/rgb/color/rect/camera_info`
  - Fake smoke: `/dg/vision/fake/depth` + `/dg/vision/fake/camera_info` via `use_fake_depth:=true`.
    Depth timer is stamp master; fake RGB copies depth stamps (`stamp_source_topic`).
    Node waits up to `sync_wait_sec` (default 0.100) for a match (`sync_tolerance_sec` 0.010).

## Evidence shells

Empty metadata templates ship inside `vision_perception` (not this interfaces
package): `src/vision_perception/evidence/templates/{V1_OFFLINE,V1_ROS,V2_POSITION,V3_TRACKING}/`
→ `share/vision_perception/evidence/templates/`. Isolated two-package syncs do
not need the monorepo `evidence/` tree.

## Consumers audit (this repo)

No in-repo subscriber to `vision_perception_interfaces/VisionObject*` was found
when this contract was finalized. If one appears before V2, pause and
re-authorize interface changes.
