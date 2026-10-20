# ros2_DL 仓库说明

这是 DG-202611 / 电力巡检机器人相关代码的**统一主库**。旧仓库都保留不删，但新开发、交接、Cursor 云端都以本库为准。

仓库地址：https://github.com/weiyang02520-ops/ros2_DL

## 分支怎么用

| 分支 | 含义 |
|---|---|
| `main` | 2026-10-20 机器人 Jetson 上 `~/ros2_DL` 真实运行代码的原样备份（`60c0e33`）。默认以它为整机基线，稳、不乱动。 |
| `robot/pre-vision-backup-20261020` | 与上述备份同提交，便于按名字找回。 |
| `upstream-main` | 原 `liaojingwu20041031/electric-power-inspection-robot` 的 main（`9d0ed34`，含 dg202611 并入）。 |
| `pc/codex-work-20261020` | 用户电脑 `工作区1/dg202611_robot_integration`（Codex 工作目录，含当时未提交改动）的快照分支。 |
| `vision/v1-v3` | 从 `weiyang02520-ops/dg202611_robot_integration` 的 `cursor/vision-v1-offline-1fcf` 导入的新独立视觉两包（`vision_perception` / `vision_perception_interfaces`）及交接文档。 |

更细的模块职责见 `docs/DG202611_仓库梳理_20261020.md`。

## 开发与同步顺序（已确认）

1. Cursor 云端对着本库的**功能分支**开发（例如视觉继续在 `vision/v1-v3`）。
2. 上机实测，确认没有问题。
3. **用户明确授权后**，再合并进 `main`（或再同步到机器人）。不会自动合，也不会没测就改主库/上机。

## 旧来源（保留，不删）

- https://github.com/weiyang02520-ops/dg202611_robot_integration （发布库 + 原视觉 PR #1）
- https://github.com/liaojingwu20041031/electric-power-inspection-robot （机器人原先 remote）
- 用户电脑 `工作区1/dg202611_robot_integration`（本地 Codex 工作区，原样保留）

## 不在本 Git 里、只在机器人上的东西

- `src/ylhb_perception/models/yolo26.onnx`、`yolo26.engine`，以及 `runs/`（体积大，被 ignore）
- 日志、旧快照 `~/dg202611_ws_11a3f8d` 里的 `evidence/`、`scenarios/`、`DEPLOYMENT_RECORD.json` 等
- 系统配置：开机服务（如 `dg202611-models`、`robot-hardware-guard`、`ylhb-mobile-bridge`、`ylhb-wifi-reconnect`）、`~/.config/ylhb/platform.env`、UI 自启动、`.bashrc`（含密钥，**禁止推公库**）
- 另库：`~/ros2_ws`（`ylhb-smart-retail-robot`，Foxglove bridge 用）

## 安全约定

- 公库禁止提交 API 密钥、token、密码、含密钥的 `.bashrc` / `.env`。
- 未经用户明确指示：不改 Nav2 / 底盘 / ZED SDK、不发 `cmd_vel`、不合并视觉进监督器、不做目录大清理。
- 机械臂：`arm_ready=NO`；新视觉默认 skeleton，`enable_objects` / `enable_tracking` 默认关；实机相机 / ZED / 精度验收未在本备份中宣称已通过。

交接时请先读本文件，再读 `docs/DG202611_仓库梳理_20261020.md`，再选对应分支。
