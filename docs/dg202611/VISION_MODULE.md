# Independent Manipulation Vision Module

Date: 2026-10-13. Implementation status: SCAFFOLD_ONLY.

## Purpose and placement

`src/vision_perception` is an independent `ament_python` package for future
bottle/cup detection, depth-qualified positions and temporal tracking.
`src/vision_perception_interfaces` defines the arm-independent observation
contract. No arm code is present or required. Neither package depends on the
navigation/fusion/recovery modules or the legacy inspection detector.

Full design and feasibility gates:
[VISION_INTEGRATION_PLAN.md](VISION_INTEGRATION_PLAN.md).
Source review considers V1–V3 conditionally feasible for observations; no runtime,
performance or arm-grasp acceptance has passed. The next phase ends at V0 package
and shell verification, without detection implementation.

## Current executable behavior

`vision_perception_node` declares future interface parameters and publishes a
one-second diagnostic heartbeat on `/dg/vision/status`. It explicitly reports
`SKELETON_ONLY` and all processing/control flags false.

- No RGB/depth subscriptions or image processing.
- No model loading, inference, GPU access or tracking.
- No detection/object publisher, including empty arrays.
- No camera startup, TF publication, arm action or robot control.
- Unsupported mode or enabled detector/tracker settings are rejected at startup.
  No dynamic validation callback/read-only parameter descriptor exists: a later
  parameter update may store a value, but cannot activate processing. No hot reload
  or runtime feature activation is implemented.

The launch starts only this shell. It is not included in production bringup,
services or autostart. The existing ZED driver must remain separately managed.

## Future public contract

| Topic | Type | Stage |
|---|---|---|
| `/dg/vision/detections_2d` | `vision_msgs/Detection2DArray` | V1 |
| `/dg/vision/objects` | `vision_perception_interfaces/VisionObjectArray` | V2/V3 |
| `/dg/vision/status` | `diagnostic_msgs/DiagnosticArray` | scaffold onward |

Object fields include object_id, class_name, confidence, position xyz, source
Header (timestamp/frame), position validity/reference, orientation validity and
tracking validity. Unknown orientation is not a measured identity quaternion.
V2 is a visible-surface position estimate, not full object pose or grasp pose.
The planned V2 array retains one entry per filtered 2D detection in source order,
including invalid depth, so an empty object_id does not erase source association.
This is a future contract, not currently implemented publishing behavior.

Outputs initially remain in the actual camera optical frame: x right, y down,
z forward, metres. There is no assumed arm/base/map transform. Future consumers
must check validity and source timestamp, then apply their own calibrated
transform. No consumer is connected in this round.

## Configuration

Installed config: `share/vision_perception/config/vision.yaml`.
Input topic and default optical-frame names have local launch/config/component
source support but are not hardware-verified today. Namespace and deployed wrapper
version may differ. Sync/depth parameters are reserved; 50 ms is a provisional
value, not an accepted live pairing tolerance. The local OpenNI branch emits
mono16 millimetres; default float depth is in metres. Units must be verified against
the actual producer, not guessed from encoding alone.

Source headers are retained; whether their stamps are acquisition or publication
time depends on the upstream debug.use_pub_timestamps setting. Actual registration,
calibration, QoS and timestamp basis must be checked before V2. Runtime stays
backend=unconfigured with no model. The plan recommends ONNX Runtime CPU as the
first reference backend; target-native TensorRT is a later measured optimization.

## Planned milestones

- V1: annotated bottle/cup 2D detection, original-image bbox and source header.
- V2: synchronized RGB/depth/calibration, valid metric 3D surface positions;
  reject invalid/stale depth and preserve unknown orientation.
- V3: stable track IDs with reset session, occlusion policy and stale-track expiry.

All three remain NOT_IMPLEMENTED / NOT_VALIDATED. Acceptance protocols and
evidence layouts are in the integration plan. No navigation performance threshold
is reused as a manipulation-vision acceptance claim.

## Verification and remaining work

Local static checks passed for Python/XML/YAML, asset paths and additive scope.
Protected-source SHA256 comparison across 376 existing tracked files was unchanged.
Linux colcon build, ROSIDL generation, launch runtime, camera input and detection
performance have not been verified. Devices are offline; no runtime pass is
claimed. Evidence root: `evidence/vision/` currently contains policy only.

Future authorized Linux entry:

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select vision_perception_interfaces vision_perception
source install/setup.bash
ros2 launch vision_perception vision.launch.py
```

## Existing-module boundary

This addition does not edit MODEL-1/2/3, Nav2/AMCL/SLAM, EKF/TF, cmd_vel or
chassis control, existing perception/interfaces, deployment scripts or services.
It does not install dependencies or alter any machine/global configuration.
