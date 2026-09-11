# RDK X5 事件相机启动与接入

## 当前结论（2026-09-11）

事件相机的软件接入路线可以继续，当前状态是：

- **DG 侧车软件已准备好**：能够校验事件字段、回放真实 CSV、提取事件特征并输出质量统计；
- **RDK X5 上已有 APX003CC 厂商栈**：存在传感器库、EVS 实时采集示例以及 RAW8、EVT2、CSV 转换工具；
- **真实事件流尚未取得**：当前没有 `/dev/video*`、`/dev/media*` 或 `/dev/v4l-subdev*`；
- **真正阻塞点是启动配置**：APX003CC overlay 当前没有生效，而且 CAM1 overlay 指向的 I2C 控制器与此前看到 `0x3c` 应答的控制器尚未对应上。

因此，不能再把问题写成“缺 APX003CC 驱动”，也不能把现在的状态写成事件相机实机通过。下一步要先确认 CAM1、Linux I2C 编号和 overlay 的真实对应关系，再备份并修改启动配置。

## 已确认的板端资源

当前板端为 RDK X5 V1.0、RDK OS 3.4.1、Ubuntu 22.04、Linux 6.1.83，TROS Humble 环境位于：

```bash
/opt/tros/humble/setup.bash
```

APX003CC 传感器库：

```text
/usr/hobot/lib/sensor/libapx003cc.so
/usr/hobot/lib/sensor/libapx003cc.so.1
/usr/hobot/lib/sensor/libapx003cc.so.1.0.0
```

厂商样例根目录：

```text
/app/multimedia_samples/sample_apx003cc
```

已经确认的关键程序和源码包括：

```text
sample_evs_release/evs_mode/01_evs_live_player/evs_live_player.RAW8
sample_evs_release/evs_mode/04_raw8_to_evt2/raw8_to_evt2.cpp
sample_evs_release/evs_mode/02_evt2_to_csv/evt2_to_csv
sample_hvs/
```

系统同时带有 CAM0 和 CAM1 的 APX003CC overlay。CAM1 overlay 描述的传感器地址是 `0x3c`，使用 4 条 CSI 数据通道，但该 overlay 当前未进入活动设备树。

## 已确认的事件数据契约

厂商工具最终使用 `Metavision::EventCD`：

```text
x          像素横坐标
y          像素纵坐标
p          极性，0 或 1
t          时间戳，单位为微秒
```

已确认的 EVS 有效尺寸为 `768 × 608`。厂商 RAW8 解析代码按每个 MIPI 包 `1,048,576` 字节处理，每包包含 32 个子帧；解析后可以转换成 EVT2。EVT2 事件使用 32 位字，随后可用厂商工具导出：

```text
x,y,polarity,timestamp
```

DG 侧车的 ROS 2 输入是 `sensor_msgs/msg/PointCloud2`，字段对应为：

```text
pixel_x,pixel_y,polarity,time_offset_us
```

其中 `time_offset_us` 是相对于该 ROS 消息头时间戳的微秒偏移。CSV 转 ROS 时必须保持时间顺序，并记录原始文件 SHA-256、采集时间和转换命令。

## DG 双机接入结构

```text
APX003CC + 厂商采集程序（RDK X5）
  -> RAW8 / EVT2 / x,y,polarity,timestamp CSV
  -> DG wrapper
  -> /dg/event_camera/events
  -> event_feature_node（RDK X5）
  -> /dg/event_camera/features
  -> /dg/event_camera/feature_quality
  -> 局域网 DDS
  -> Jetson 记录、显示并提供给后续模型验证
```

事件原始流和特征提取优先留在 RDK X5，Jetson 只接收低带宽特征和质量信息。两块板联调时使用相同的 `ROS_DOMAIN_ID`。该侧链不发布 `/cmd_vel`，不接管机器人底盘。

## 第一步：只读探测

进入侧车包解压目录后运行：

```bash
bash probe_rdk_x5_event_camera.sh ~/evs_probe_$(date +%Y%m%d_%H%M%S).txt
```

脚本会自动尝试加载 `/opt/tros/humble/setup.bash`，并记录：

- 视频、媒体、I2C 设备与活动设备树；
- APX003CC 传感器库和厂商 EVS 工具；
- CAM0/CAM1 overlay 的关键目标控制器、地址和 CSI 通道；
- 当前启动配置中已经启用的 overlay；
- TROS/ROS 2 环境、话题和相关进程。

该脚本不会运行 `i2cdetect`，不会加载模块，不会修改 `/boot`，不会重启，也不会发布 ROS 消息。

## 第二步：确认 CAM1 与 overlay 映射

当前证据需要解决一个具体矛盾：

- 之前看到设备地址 `0x3c` 应答的 Linux I2C 适配器对应活动控制器 `i2c@341d0000`；
- 当前 `dtoverlay_cam1_apx003cc.dts` 的目标控制器是 `i2c@340f0000`。

这不等于 overlay 一定错误，也不能仅凭接口丝印猜测 CAM0/CAM1。必须结合板端 `/sys/class/i2c-adapter`、活动设备树、板卡原理图/官方端口定义和实际排线位置确认映射。完成确认之前，不修改启动配置。

## 第三步：可回滚地启用相机

只有第二步确认后才执行：

1. 保存当前 `/boot/config.txt`、`/boot/config/config.txt`、活动设备树和文件 SHA-256；
2. 记录 SD 卡镜像版本，并准备可从 Windows 恢复启动分区的办法；
3. 只启用确认正确的 APX003CC overlay；
4. 重启后检查设备节点、内核日志和传感器识别结果；
5. 若设备没有出现或启动异常，立即按备份恢复。

这一步只能在地瓜派专用任务中按已确认的命令执行，不能试错式轮流启用 CAM0/CAM1。

## 第四步：采集一段真实事件数据

设备正常识别后，先运行厂商 `evs_live_player.RAW8` 的帮助或样例说明，确认参数和输出位置，再采集一段短 RAW8。随后按板端现有工具链完成：

```text
真实 RAW8 -> raw8_to_evt2 -> EVT2 -> evt2_to_csv -> 真实 CSV
```

至少保存：

- 原始 RAW8、EVT2、CSV；
- 三者 SHA-256；
- 相机型号、端口、镜像版本、overlay 配置；
- 采集开始/结束时间、场景和转换命令；
- 事件数量、频率、时间戳单调性、坐标范围和极性统计。

## 第五步：接入 DG 侧车

取得真实 CSV 后可先验证回放链路：

```bash
bash run_rdk_event_csv_replay.sh /data/events.csv 50.0 false
```

回放会标记为 `source_kind=MEASURED_REPLAY`。实时 wrapper 准备好后再运行：

```bash
bash run_rdk_event_feature_sidecar.sh
python3 inspect_event_topic.py --timeout-sec 10 --output-json event_topic_probe.json
```

验收时必须区分：

- `SOFTWARE_READY`：脚本、接口和回放链路可用；
- `MEASURED_REPLAY_PASS`：真实采集数据已成功回放；
- `LIVE_HARDWARE_PASS`：真实相机持续输出并经 ROS 2 实时处理。

当前状态是 `SOFTWARE_READY`，尚未达到后两项。
