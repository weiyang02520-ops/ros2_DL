# 合成端到端冒烟记录（非实机）

**标签：** `SOFTWARE_CHECKED` + `SYNTHETIC` — **不得**记 `LIVE_CAMERA_OBSERVED` / 实机 PASS。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-10-21 |
| 方式 | Docker `ros:humble-ros-base-jammy`（x86_64） |
| 脚本 | `src/vision_perception/scripts/docker_humble_e2e_synthetic_smoke.sh` |
| 模型 | artifacts `yolo11n-seg.onnx` SHA `6e448a4d…0978` |
| 样例图 | COCO val `000000007574.jpg`（多 bottle）；存为 `sample_bottle_cup.jpg` |
| 结果摘要 | `E2E_SYNTHETIC_SMOKE_OK` |

## 观测

| 检查 | 结果 |
|---|---|
| `source_kind` | `SYNTHETIC_DEV`（非 LIVE_CAMERA） |
| `/dg/vision/detections_2d` | 3× `bottle`（conf≈0.66/0.61/0.40） |
| `/dg/vision/objects` | 历史：曾出现 3 条 `DEPTH_UNPAIRED`（原生 RGB 尺寸≠假深度、BEST_EFFORT 丢帧、CameraInfo 竞态、`--once` 不同帧）。阶段 0 修复后应对齐 HxW + reliable QoS + CameraInfo defer + 多样本，期望 `position_valid=true`（仍 SYNTHETIC） |
| Pose2D 发布 | 曾失败（vision_msgs 4.1 `position.x`）；已修 `_fill_vision_pose2d` 兼容 |
| 阶段 0 修复 | 见 [`../STAGE0_FIX_NOTES.md`](../STAGE0_FIX_NOTES.md)；脚本现断言 `E2E_SYNTHETIC_RELIABLE_3D_OK` |

## Artifacts（不进 git）

`/opt/cursor/artifacts/vision_models/`：`yolo11n-seg.onnx`、`.pt`、`model_manifest.json`、样例图、本日志副本。
