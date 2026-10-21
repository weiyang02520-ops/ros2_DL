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
- Invalid detections are **retained** with NaN positions and an `invalid_reason`. Do not drop failures, do not write `0` or a previous XYZ as a successful fallback.
- V2 (tracking off): `object_id` and `tracking_session_id` empty; `tracking_valid=false`.
- V3 (`enable_tracking:=true`, `mode:=v1_ros` only): confirmed matches get non-empty
  `object_id` and `tracking_valid=true` within `tracking_session_id` on
  **`VisionObject` / `/objects`** (requires `enable_objects` to publish IDs).
  `VisionDetection2D` does not carry `object_id`. Tentative / unmatched stay empty
  + false. STALE / calibration change / clock rollback mint a new session; expired
  IDs are never reused. Matcher: deterministic greedy per-class IoU (not Hungarian).
  No ReID / cross-restart identity. Tracking must **not** copy an old valid XYZ onto
  a currently unpaired/invalid observation.
- Consumers of legacy `/perception/localized_objects` are out of scope; this package does not replace them silently.

## `source_kind` (W1)

| Value | Meaning |
|---|---|
| `LIVE_CAMERA` | Real camera stream (e.g. ZED subscribe profile) |
| `RECORDED_CAMERA` | Bag / recorded replay |
| `SYNTHETIC_DEV` | Fake / synthetic publishers (`/dg/vision/fake/...`, `input_profile:=fake_dev`) |
| `OFFLINE_FILE` | Offline CLI file input |

Fake streams **must not** be labeled `LIVE_CAMERA`. Auto-resolution uses `input_profile` and `rgb_topic`; explicit `source_kind` overrides when set.

## Freshness (W1)

- `max_observation_age_sec` (default 0.500) is applied to the **source RGB stamp**.
- Age is checked **before inference** and again **after inference**, before publish.
- Over-age observations are dropped (counted in status `observations_dropped_age` /
  `observations_dropped_age_post_infer`); they are not published as fresh.

## Mask / depth quality (W2)

`invalid_reason` values (keep at least):

`OK`, `DEPTH_UNPAIRED`, `MASK_TOO_SMALL`, `MASK_DEGRADED`, `DEPTH_INSUFFICIENT`,
`DEPTH_DISCONTINUITY`, `INPUT_INVALID`, `STALE`.

- `MASK_DEGRADED`: instance mask missing or size-mismatched, and
  `allow_bbox_mask_fallback:=false` (ZED delivery profile default).
- When fallback is allowed (fake_dev), bbox sampling may proceed but status exposes
  `last_mask_source` / `last_mask_degraded_count`.
- RGB / depth / CameraInfo size or frame mismatches → `INPUT_INVALID` (no forged XYZ).
- Transparent / reflective bottle-cup depth is **not** promised; treat as route B
  (opaque baseline vs transparent pending). Detection ≠ reliable surface depth.

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
- Sensor subscriptions default to **BEST_EFFORT** QoS (`image_qos_reliability`).
- Profiles:
  - `config/profiles/zed_subscribe.yaml` + `vision_zed_subscribe.launch.py`
  - `config/profiles/fake_dev.yaml` (SYNTHETIC_DEV)

## Evidence shells

Empty metadata templates ship inside `vision_perception` (not this interfaces
package): `src/vision_perception/evidence/templates/{V1_OFFLINE,V1_ROS,V2_POSITION,V3_TRACKING}/`
→ `share/vision_perception/evidence/templates/`. Isolated two-package syncs do
not need the monorepo `evidence/` tree.

## Consumers audit (this repo)

No in-repo subscriber to `vision_perception_interfaces/VisionObject*` was found
when this contract was finalized. If one appears before V2, pause and
re-authorize interface changes.

## Out of scope for W1–W4

Coordinate transform adapter (`/dg/vision/objects_target`, W5), motion commands,
Nav2 goals, `/initialpose`, and formal TF publish remain unauthorized.
