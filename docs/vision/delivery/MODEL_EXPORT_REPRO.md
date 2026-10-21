# YOLO11n-seg ONNX 导出复现（云端 2026-10-21）

权重 / ONNX **不进 git**（仓库公开）。产物保存在本机/云端 artifacts，按下方命令复现同一 SHA。

## 本次云端实测结果（SYNTHETIC / SOFTWARE_CHECKED）

| 项 | 值 |
|---|---|
| 日期 | 2026-10-21 |
| Ultralytics | 8.4.183 |
| Torch | 2.14.1+cu130（导出用 CPU） |
| ONNX | 1.23.2 |
| Opset | 17 |
| 导出选项 | `imgsz=640 dynamic=False simplify=True` |
| `weights_sha256`（`yolo11n-seg.pt`） | `55ed65c56c91713d23e8402371c6c49a6fd84f257f7dce452e8d70e41dcbe152` |
| `onnx_sha256`（`yolo11n-seg.onnx`） | `6e448a4d97b7da9a95cb36acad3c44c2ae704ce23c537e4b7a53b6bde3800978` |
| 输入 | `images` `(1,3,640,640)` |
| 输出 | `output0 (1,116,8400)` + `output1 (1,32,160,160)` |
| 许可备注 | Ultralytics 预训练权重多为 AGPL-3.0；**未提交进公库**；再分发前自行审 license |
| Artifacts 路径（本云端） | `/opt/cursor/artifacts/vision_models/` |

若本机复现得到**不同** `onnx_sha256`：核对 ultralytics/torch/onnx/onnxslim 版本与 `simplify` 开关；以本机实测 SHA 更新 manifest，勿强行沿用旧哈希。

## 本机复现命令

```bash
python3 -m pip install --user 'ultralytics==8.4.183' 'onnx==1.23.2' onnxslim \
  'numpy>=1.26.4,<2' 'onnxruntime==1.20.1'
mkdir -p "$HOME/vision_models" && cd /tmp && rm -f yolo11n-seg.pt yolo11n-seg.onnx
python3 - <<'PY'
from pathlib import Path
import hashlib, shutil
from ultralytics import YOLO
model = YOLO('yolo11n-seg.pt')
path = Path(model.export(format='onnx', imgsz=640, dynamic=False, simplify=True, opset=17))
dst = Path.home() / 'vision_models' / 'yolo11n-seg.onnx'
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(path, dst)
h = hashlib.sha256(dst.read_bytes()).hexdigest()
print(dst, h)
assert h == '6e448a4d97b7da9a95cb36acad3c44c2ae704ce23c537e4b7a53b6bde3800978', h
PY
# 复制仓库内已填 SHA 的示例 manifest，或从 template 填写：
cp src/vision_perception/examples/model_manifest.cloud_export.example.json \
  "$HOME/vision_models/model_manifest.json"
```

合同字段见 `examples/model_manifest.template.json` / `MODEL_AND_DEPS.md`。
