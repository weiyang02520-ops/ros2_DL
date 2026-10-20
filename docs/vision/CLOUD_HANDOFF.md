# Cloud Development Handoff

> **本地实机 / SSH 接手：** 请先读根目录 [`LOCAL_HANDOFF.md`](./LOCAL_HANDOFF.md)（完整记忆：阶段现状、安全边界、机上整仓备份顺序、`res_ds`、开场提示语）。云端连不上机器人局域网时，由本地 Cursor 按该文档继续。

This private repository is a reviewed source snapshot for DG-202611, published on 2026-10-14 at the owner's request. It does not transfer the original repository's full Git history.

## Read first

- docs/dg202611/VISION_INTEGRATION_PLAN.md is the V4 detailed vision specification.
- src/vision_perception and src/vision_perception_interfaces are existing inert scaffolds.
- docs/dg202611/VISION_MODULE.md and evidence/vision/README.md describe the scaffold and evidence policy. Proposed V1/V2/V3 interface changes in V4 are NOT implemented.

## Current authorization

Publishing this repository is authorized. Starting paid cloud agents, opening a PR, installing packages, executing V0, starting ZED, implementing V1/V2/V3, or accessing hardware is NOT authorized by publication alone. Follow the owner's next task.

First takeover: READ / VERIFY / REPORT. Verify repository contents, inspect actual available environment, read the plan and report any differences. Do not manufacture a ROS or camera PASS.

If a separate task authorizes V0, it is limited to discovery/build of the two existing vision packages and the status-only shell. Missing Linux Humble/dependencies means BLOCKED. No same-round code fix or installation. Keep camera_contract=NOT_RUN and ARM_READY=NO.

## Scope boundaries

No changes to MODEL-1/2/3, Nav2/AMCL/SLAM, EKF/TF ownership, cmd_vel, chassis, manual/mobile control, existing perception, production launch or services. No arm dependency. Do not start the robot from an old README example.

Cloud Linux does not automatically have ROS2 Humble and cannot reach powered-off local VMs, private-LAN Jetson/RDK or USB cameras. GitHub access does not provide camera data or authorize hardware tests. Cursor's GitHub app may need the owner to grant access to this private repository; do not make it public to work around permissions.

## Provenance

SOURCE_SNAPSHOT.json records the original tracked-code base, working-tree additions and source file hashes. The vision files and updated plan were untracked in the original checkout and are included explicitly. Model weights, local build/install/log, untracked release archives and original .git history are excluded.

The source hashes describe verified working-tree copies before Git text normalization. Existing .gitattributes may normalize text line endings when committed. Published content identity is the new repository's Git commit/tree, not the old source HEAD alone. No runtime, model or camera validation was performed as part of publication.
