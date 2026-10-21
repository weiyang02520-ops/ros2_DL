# 阶段 0 软件缺陷修复说明（SYNTHETIC / 本机 PC）

**标签：** `SOFTWARE_CHECKED` — 假流与 skeleton 修复；**不得**记实机 / `LIVE_CAMERA` PASS。  
**基线：** `181d1fd`（`codex/zed-bottle-w1-w4`）  
**关联：** 本机阶段 0 结果 `ready_for_window_a=false`（Perception 预览失败、skeleton SIGINT 异常、合成可靠 3D 未过）。

## 修了什么

| 缺陷 | 根因 | 修复 |
|---|---|---|
| Perception 预览 `COLCON_TRACE unbound variable` | `Run-VisionStage.sh` 在 `set -u` 下直接 `source install/setup.bash` | `source_ros_setup`：预置 `COLCON_TRACE` 等可选变量，`set +u` 再 source |
| skeleton timeout/SIGINT → 节点 exit -2 | `finally` 里 `destroy_node` / `rclpy.shutdown` 再抛 `KeyboardInterrupt` | 各 vision 节点 main 收尾吞掉 `KeyboardInterrupt` / `ExternalShutdownException` |
| 合成 e2e：检出 3 bottle，但 `/objects` 全 `DEPTH_UNPAIRED` / NaN | ① 假 RGB 原生分辨率 ≠ 假深度 640×480；② 合成仍用 BEST_EFFORT 易丢帧；③ stamp 已配对但 CameraInfo 跨话题未到时被立刻改写为 `DEPTH_UNPAIRED`；④ e2e `--once` 与 status 不同帧 | ① stamp-lock 时 `match_rgb_to_hw`；② fake launch 强制 `image_qos_reliability:=reliable`；③ 配对成功无 calib 时短 defer 等 CameraInfo（超时仍标无效，不伪造 XYZ）；④ e2e 多样本直到 `position_valid=true` |

**未放宽：** `require_rgb_depth_same_size`、深度有效性门槛、无效时仍 NaN + reason。配对失败仍必须 `position_valid=false`。

## 本机如何复验

隔离 ws 构建两包后：

```bash
# 1) Perception 预览（应打印命令，不再因 COLCON_TRACE 退出）
bash src/vision_perception/scripts/vision_delivery/Run-VisionStage.sh Perception

# 2) skeleton 限时（期望 timeout 124 或干净收尾；节点不应再因 destroy 抛 -2）
source /opt/ros/humble/setup.bash && source install/setup.bash
timeout 8 ros2 launch vision_perception vision.launch.py mode:=skeleton

# 3) 合成可靠 3D（真 ONNX + 假流；结果仅 SYNTHETIC）
export VISION_MODELS_DIR=$HOME/vision_models   # 或 artifacts 目录
bash src/vision_perception/scripts/docker_humble_e2e_synthetic_smoke.sh
# 期望日志含 E2E_SYNTHETIC_SMOKE_OK 与 E2E_SYNTHETIC_RELIABLE_3D_OK
```

包内单测：`PYTHONPATH=src/vision_perception python3 -m pytest src/vision_perception/test -q`

## 云端复验（本轮）

| 命令 | 结果 |
|---|---|
| `pytest src/vision_perception/test` | **153 passed** |
| `docker_humble_smoke.sh` | Perception 预览打印 OK（无 COLCON_TRACE）；`skeleton_launch_exit=124`；日志无 KeyboardInterrupt；`DOCKER_SMOKE_OK` |
| `docker_humble_e2e_synthetic_smoke.sh` | 首个 objects 样本即 3×`position_valid=true`（z≈1.0）；`E2E_SYNTHETIC_SMOKE_OK` + `E2E_SYNTHETIC_RELIABLE_3D_OK`（**SYNTHETIC**） |

本轮云端 ONNX SHA 与历史云端文档 SHA 可能不同字节（同源 PT）；冒烟用本地 artifacts manifest，**未提交权重**。

## `ready_for_window_a` 条件

软件侧建议全部满足后再向用户申请窗口 A：

1. Perception 预览在 `set -u` 下可 source setup（本修复覆盖）。
2. skeleton 限时启动可观察 `SKELETON_ONLY`，SIGINT/timeout 收尾无未捕获 `KeyboardInterrupt` 导致的节点 -2。
3. 合成假流上可复现至少一条 `position_valid=true`（仍标 **SYNTHETIC**，≠ 实机 PASS）。
4. Jetson 上电、已审相机、真 ZED 订阅、短采集仍需**用户另行授权**；未授权前保持 `ready_for_window_a=false`。
