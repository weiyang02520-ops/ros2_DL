# 模型与 ARM64（Jetson）隔离依赖方案（W4）

## 1. 模型合同（不得换成 yolo26）

| 项 | 要求 |
|---|---|
| 权重 | YOLO11n-seg ONNX（COCO 预训练可作起点；bottle=39, cup=41） |
| 输入 | `images`，形状 `(1, 3, 640, 640)` |
| 输出 | `output0 (1, 116, 8400)` + `output1 (1, 32, 160, 160)` |
| Manifest | `examples/model_manifest.template.json` → 本机绝对路径；填 SHA256/许可 |
| 禁止 | 把机上旧 `yolo26.onnx/.engine` 改名当 YOLO11n-seg；推理进程不引 Ultralytics/PyTorch |

导出（在 PC，示例）：

```bash
# 仅在已授权的本机 Python 环境；结果 scp 到隔离目录，不进 git
yolo export model=yolo11n-seg.pt format=onnx imgsz=640 simplify=True
sha256sum yolo11n-seg.onnx
cp src/vision_perception/examples/model_manifest.template.json \
  "$HOME/vision_models/model_manifest.json"
# 编辑 onnx_sha256 / license / source
```

## 2. 依赖钉死

| 包 | 版本 | 说明 |
|---|---|---|
| NumPy | `>=1.26.4,<2` | **禁止 NumPy 2.x** |
| OpenCV | `opencv-python-headless==4.10.0.84` | 先装 NumPy 再装 |
| ONNX Runtime | `onnxruntime==1.20.1`（CPU 首版） | aarch64 wheel 以目标机实测为准 |
| ROS | Humble | 只 build 两视觉包 |

文件：

- `src/vision_perception/requirements-runtime.txt`（通用）
- `src/vision_perception/requirements-arm64.txt`（Jetson 清单 + 状态分层说明）

## 3. 隔离原则

1. 生产 `~/ros2_DL` **只读**；新建独立视觉工作目录与 venv/用户 site-packages。
2. 不用生产 `build/install` 作为本次输出；不改 `~/dg202611_ws` 软链、`.bashrc`、systemd。
3. 不借生产 Python 升级系统包或 ZED SDK。
4. 旧全量 `build/preflight/release` 脚本不用于本次默认部署。
5. `bootstrap_isolated_ws.sh` 会清重建并默认跑 pytest——**不能当只读入口**，需授权再执行。

## 4. 三状态（必须分记）

| 状态 | 含义 | 本云端包 |
|---|---|---|
| PREPARED | 源码/清单/导出说明就绪 | 本包文档与代码 |
| BUILT | 目标 aarch64 import ORT + colcon 两包成功 | **NOT_RUN**（无 Jetson） |
| RUN | 真实节点在机上跑通 | **NOT_RUN** |

“依赖可下载” ≠ “ARM64 已运行”。

## 5. 目标机准备命令（本机 Codex 预览用）

```bash
# 在隔离目录，勿动生产软链
source /opt/ros/humble/setup.bash
python3 -m pip install --user -r src/vision_perception/requirements-arm64.txt
python3 - <<'PY'
import numpy, cv2, onnxruntime as ort
assert numpy.__version__.startswith("1.")
print("ORT", ort.__version__, "OK")
PY
bash src/vision_perception/scripts/ensure_scripts_executable.sh
colcon build --symlink-install --packages-select \
  vision_perception_interfaces vision_perception
source install/setup.bash
bash src/vision_perception/scripts/check_ament_prefix_hook.sh
```

性能：CPU/ONNX 实际 Hz 以 Jetson 测量为准；达不到 `max_observation_age_sec` 时先记瓶颈再审批优化（TensorRT 另立任务）。
