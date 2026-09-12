# RDK X5 HVS 双流实测状态（2026-09-12）

## 设备边界

本次实测只在 RDK X5（`sunrise@192.168.43.13`）进行，未连接、未修改机器人 Jetson（`nvidia@192.168.43.12`）和 `/home/nvidia/ros2_DL`。

## 已通过：厂商底层双流

在 RDK 上运行：

```bash
timeout -s INT -k 10 60 stdbuf -oL -eL \
  /app/multimedia_samples/sample_apx003cc/sample_hvs/dual_vc_vin_src/dual_vc_vin \
  -c 1 -d 0
```

实测日志确认：

- `VC0/VC1 are ready`；
- APS 已创建 ISP 节点并持续取帧；
- EVS 约 `208.5–209.0 FPS`；
- APS 约 `29.79–29.85 FPS`；
- 程序持续运行 60 秒后由 `timeout` 结束，退出码 `124` 只表示到时停止。

证据目录：

```text
evidence/rdk_hvs_20260912_141259/
```

因此可以记录为：

```text
RDK_VENDOR_DUAL_STREAM_PASS
```

## 未通过：Toolkit ROS 桥双流

最新 `dg_hvs_bridge` 已在 RDK 上重新编译并安装，使用当前板端参数：

```yaml
sensor_index: 52
i2c_bus: 6
evs_fps: 240
```

ROS 话题均已创建，EVS 和 features 有持续输出，但质量诊断为：

```text
state=DEGRADED
evs_fresh=true
aps_fresh=false
aps_frames=0
aps_packets=0
aps_format=UNKNOWN
fused_frames=0
```

运行日志持续出现：

```text
MIPI-HVS: APS ISP getframe failed
```

将 `sensor_index` 试为 52、53、49 后，APS 仍未恢复；问题不是 ROS 话题、QoS、APS 解码格式或 sensor index 单项配置导致的。当前证据更接近：预编译 ShiMetaPi X5 `MipiHvs` 后端的 APS ISP 路径与本机 RDK 厂商 HBN 双流实现不一致。

因此当前不能标记：

```text
RDK_ROS_HVS_BRIDGE_PASS
```

## 当前结论

- APX003CC 硬件、RDK 镜像、MIPI、CSI 和 ISP 底层链路已被厂商程序证明可用；
- DG 桥接的 EVS、ROS 话题、features、质量诊断和“不发布 `/cmd_vel`”均正常；
- APS ROS 输出和融合图尚未通过；
- 机器人 Jetson 端三模型尚未进行跨板事件相机联调。

## 下一步

1. 保留本次底层双流证据；
2. 继续采用 RDK 厂商 HBN 双 VC 管线做 APS/EVS 采集适配，避免把当前 Toolkit `MipiHvs` APS 失败写成硬件故障；
3. 新适配先在 RDK 本地发布 APS、EVS、quality 和 features，再进行 RDK→Jetson 网络联调；
4. 在 APS 真正持续输出前，不启用事件相机对 MODEL-2 激光结果的软融合。
