# 跨板事件相机验收证据（2026-09-13）

- `rdk_bridge_status.txt`：RDK X5 本地桥运行状态、HBN 二进制 SHA-256、环境变量和 `quality`/`feature_quality` 样本。
- `nvidia_receive.txt`：NVIDIA 端在 `2026-09-13T05:40:35Z` 发现事件相机业务话题并读取质量与特征质量消息，同时记录 `/dg/event_camera/features` 的接收频率。
- `manifest.sha256`：本目录证据文件清单。

结论：RDK → NVIDIA 的事件相机业务话题已完成一次跨板接收验证。样本中 `quality=GOOD`、`pair_valid=true`、`feature_quality.repeatability_status=COMPARED`，事件特征接收约 9–10 Hz。该验证使用独立观察命令；NVIDIA 当前运行的旧部署尚未启动 `auxiliary_transport_monitor` 和完整新版本 MODEL-2，因此 `model2_event_assist_observable` 仍需在新版本部署/启动后确认。

RDK 桥启动时需要先设置 Toolkit 和系统库路径，例如：

```bash
export LD_LIBRARY_PATH=/home/sunrise/dg202611_hvs_toolkit_20260912/shimetapi_hybrid_vision_toolkit-main/lib/x5:/usr/hobot/lib:/app/multimedia_samples/sample_apx003cc/sample_hvs/dual_vc_vin_src/lib:${LD_LIBRARY_PATH:-}
```

本次验证未启动底盘、未发布 `/cmd_vel`，也未修改机器人基础工作区或备份。
