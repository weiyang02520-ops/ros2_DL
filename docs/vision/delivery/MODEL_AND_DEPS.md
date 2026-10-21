# 模型与依赖说明（§11 交付）

| 项 | 内容 |
|---|---|
| 模型 | YOLO11n-seg ONNX（COCO bottle=39, cup=41） |
| 禁止 | 旧 yolo26.onnx/.engine 改名冒充 |
| Manifest | `examples/model_manifest.template.json` |
| 运行时 | `requirements-runtime.txt` / `requirements-arm64.txt` |
| NumPy | `>=1.26.4,<2`（禁止 2.x） |
| ORT | `onnxruntime==1.20.1` CPU 首版 |
| 详细 | `docs/vision/ARM64_DEPENDENCY_PLAN.md` |

权重与 SHA **不进 git**；部署记录填写本机绝对路径与实测 SHA。
