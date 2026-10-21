# ARM64 QEMU 冒烟记录（≠ Jetson 实机）

**重要：** QEMU user-mode ≠ Jetson。无 JetPack、无 CUDA/TensorRT、无板级电源/热设计证据。仅验证 **aarch64 wheel 可装 + 两包可 colcon + pytest**。

## 环境

| 项 | 值 |
|---|---|
| 日期 | 2026-10-21 |
| 镜像 | `arm64v8/ros:humble-ros-base`（`linux/arm64`） |
| 模拟 | `tonistiigi/binfmt --install arm64`（需 `binfmt_misc` 已挂载） |
| 脚本 | `src/vision_perception/scripts/docker_arm64_qemu_smoke.sh` |
| 结果 | `ARM64_QEMU_SMOKE_OK` |

## 结果

| 步骤 | 结果 |
|---|---|
| `uname -m` | `aarch64` |
| `numpy>=1.26.4,<2` | OK 1.26.4（manylinux aarch64 wheel） |
| `opencv-python-headless==4.10.0.84` | OK |
| `onnxruntime==1.20.1` | OK（`cp310 manylinux aarch64` wheel 存在） |
| `colcon build` 两包 | OK（约 1min21s under QEMU） |
| `pytest` | **150 passed** |

## 卡点与修复（本轮）

1. 仅 `docker pull --platform linux/arm64 ros:humble-ros-base-jammy` 时易仍用本地 **amd64** 缓存 → `exec format error`。改用 **`arm64v8/ros:humble-ros-base`**。
2. 环境无 `binfmt_misc` 时需：`mount -t binfmt_misc …` 后再 `tonistiigi/binfmt --install arm64`。

## 仍 NOT_RUN（必须 Jetson）

板载 `pip`/`colcon`、CUDA EP、实测推理 Hz、温升与电池窗口。
