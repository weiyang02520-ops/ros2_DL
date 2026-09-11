# RDK X5 事件相机启动准备

## 先确认硬件组合

RDK X5 只是运行事件相机驱动的计算板。EVS 模组、MIPI 排线和正确的系统镜像仍然是必需项；厂商的 RDK X5 适配页以 EVS_003 为例，默认接到靠近网口的 CAM1 接口。官方清单还列出 5V/3A 以上电源、32GB 以上 Class 10 SD 卡，HDMI 显示器用于现场观察。硬件连接前先断电，排线插入后再通电。

当前 DG 工作区已经准备好通用 ROS 2 侧链：

```text
EVS 原始事件流 -> /dg/event_camera/events -> event_feature_node
                                      -> /dg/event_camera/features
                                      -> /dg/event_camera/feature_quality
```

这个侧链要求输入 `PointCloud2` 的字段为 `pixel_x`、`pixel_y`、`polarity`、`time_offset_us`，坐标系默认是 `event_camera_optical_frame`。它只做观测和特征质量统计，不接管底盘，也不发布 `/cmd_vel`。

## 第一步：只读探测

在 RDK X5 上运行：

```bash
cd ~/dg202611_ws
bash scripts/probe_rdk_x5_event_camera.sh ~/evs_probe_$(date +%Y%m%d_%H%M%S).txt
```

把命令最后打印的 `PROBE_OUTPUT=...` 文件传回 Windows。重点看：

- `/dev/video*`、`/dev/media*`、`/dev/v4l-subdev*` 是否出现；
- `media-ctl -p` 是否能看到 MIPI/CSI 图；
- `dmesg` 是否出现 EVS、MIPI、CSI 或传感器识别信息；
- 当前系统镜像和 EVS 模组型号是否匹配；
- 是否已经有厂商事件流程序或 ROS 2 节点。

脚本是只读的，不改驱动、不改网络、不启动 ROS 运动命令。

## 第二步：确认厂商输出

探测到设备后，先不要把它接到机器人。需要记录以下信息：

1. EVS 模组完整型号和分辨率；
2. RDK X5 系统镜像版本；
3. 厂商采集程序或 ROS 2 驱动命令；
4. 原始事件字段、时间戳单位和坐标系；
5. 是否能导出 CSV/RAW/ROS bag。

如果厂商程序只提供专用事件格式，先写一个只读 wrapper，把数据转换为 DG 的四字段事件格式，再接 `event_feature_node`。不直接修改 `/home/nvidia/ros2_DL`。

## 当前判断

本地软件侧已经具备事件数据校验、分包、特征提取和相邻包重复率计算；真正还没完成的是 RDK X5 上的 EVS 驱动识别和一段真实事件数据。只有看到真实设备节点和真实事件包后，才能继续做 ROS 2 实时接入与 MODEL-2/MODEL-3 联调。

## 双机运行方式

推荐让原始事件流和特征提取都留在 RDK X5，仅把低带宽结果交给 Jetson：

```text
APX003CC + 厂商驱动（RDK X5）
  -> /dg/event_camera/events
  -> event_feature_node（RDK X5）
  -> /dg/event_camera/features + /dg/event_camera/feature_quality
  -> 同一 ROS_DOMAIN_ID / 局域网
  -> Jetson 记录、显示并参与后续验证
```

两块板使用同一个 `ROS_DOMAIN_ID`。Jetson 不订阅原始事件话题时，DDS 不会把整条高带宽事件流传给 Jetson；它只需要订阅特征和诊断。第一次联调不要启用 MODEL-3 运动或速度仲裁器。

本仓库可生成一个无需编译整套机器人系统的轻量包：

```powershell
.\scripts\build_rdk_event_sidecar_bundle.ps1
```

上传并解压到 RDK X5 后，厂商事件发布器启动成功时运行：

```bash
bash run_rdk_event_feature_sidecar.sh
```

先验证单个实时事件包：

```bash
python3 inspect_event_topic.py --timeout-sec 10 --output-json event_topic_probe.json
```

如果当前只能由厂商工具导出真实 `x,y,polarity,timestamp` CSV，可以先完成真实数据回放链路：

```bash
bash run_rdk_event_csv_replay.sh /data/events.csv 50.0 false
```

回放会明确标记 `source_kind=MEASURED_REPLAY`，不会冒充实时驱动。

## 2026-09-11 当前硬件结论

- 地瓜派：RDK X5 V1.0，RDK OS 3.4.1，Ubuntu 22.04，内核 6.1.83；
- 事件相机插在 CAM1，对应 `mipi_host0 / i2c-6`；
- `0x3c` 有 I2C 应答，说明排线、电源和设备应答链路已经出现；
- 镜像中存在 `dtoverlay_cam0_apx003cc.dtbo`，但当前内核模块目录中没有 APX003CC 驱动；
- `/dev/video*` 为空与“缺内核驱动”一致，当前不能开始真实事件采集。

`dtoverlay` 只负责把硬件描述交给内核，不能替代缺失的传感器驱动。现在不应先改 `/boot/config/config.txt` 或重启碰运气；应优先向事件相机厂商取得适用于 **RDK OS 3.4.1 / Linux 6.1.83 / APX003CC** 的内核驱动、SDK、安装步骤和事件格式说明。拿到驱动包后先保存原包和 SHA-256，再在地瓜派专用任务中做可回滚安装。
