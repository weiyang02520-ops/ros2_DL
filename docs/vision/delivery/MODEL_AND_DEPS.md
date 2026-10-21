# 模型与依赖说明（§11 交付）

| 项 | 内容 |
|---|---|
| 模型 | YOLO11n-seg ONNX（COCO bottle=39, cup=41） |
| 禁止 | 旧 yolo26.onnx/.engine 改名冒充 |
| Manifest 模板 | `examples/model_manifest.template.json` |
| 云端已填 SHA 示例 | `examples/model_manifest.cloud_export.example.json` |
| 导出复现 | [`MODEL_EXPORT_REPRO.md`](./MODEL_EXPORT_REPRO.md) |
| 运行时 | `requirements-runtime.txt` / `requirements-arm64.txt` |
| NumPy | `>=1.26.4,<2`（禁止 2.x） |
| ORT | `onnxruntime==1.20.1` CPU 首版（**aarch64 wheel 已在 QEMU 验证可装**） |
| 详细 | `docs/vision/ARM64_DEPENDENCY_PLAN.md` |

## 云端实测 SHA（2026-10-21）

| 文件 | SHA256 |
|---|---|
| `yolo11n-seg.pt` | `55ed65c56c91713d23e8402371c6c49a6fd84f257f7dce452e8d70e41dcbe152` |
| `yolo11n-seg.onnx` | `6e448a4d97b7da9a95cb36acad3c44c2ae704ce23c537e4b7a53b6bde3800978` |

权重与 ONNX **不进 git**。云端 artifacts：`/opt/cursor/artifacts/vision_models/`。本机按 `MODEL_EXPORT_REPRO.md` 复现同一 SHA 后放入 `$HOME/vision_models/`。
