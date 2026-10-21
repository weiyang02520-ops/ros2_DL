# vision_delivery（W7）

隔离部署 / 启停 / 短采集入口。**默认预览，显式 `--execute` / `-Execute` 才执行。没有 All 步骤。**

| 脚本 | 环境 |
|---|---|
| `Run-VisionStage.sh` | Jetson / Linux 隔离工作空间 |
| `Run-VisionStage.ps1` | 本机 Windows → SSH 到机器人 |

## 步骤

| Step | 作用 | 是否启 ZED |
|---|---|---|
| Deploy | 隔离目录说明 / 可选授权构建 | 否 |
| Perception | `vision_zed_subscribe.launch.py` | **否**（需已有相机流） |
| Transform | W5 转换（默认 disabled） | 否 |
| Subscriber | 只订阅打印 | 否 |
| Capture | 限时 `ros2 bag record` | 否 |
| StopOwn | 只停本脚本记录的 PID | 否 |

Camera 步骤**不在本脚本内**——必须使用已审阅的既有相机入口，并单独授权。

## 示例

```bash
# 预览
bash Run-VisionStage.sh Perception
# 执行（授权后）
bash Run-VisionStage.sh Perception --execute
bash Run-VisionStage.sh Capture --execute --duration=15
bash Run-VisionStage.sh StopOwn --execute
```

```powershell
& .\Run-VisionStage.ps1 -Step Perception
& .\Run-VisionStage.ps1 -Step Perception -Execute
```

硬约束：不改 `~/ros2_DL` 软链、不发 `cmd_vel`/导航/`/initialpose`、不发布正式 TF。
