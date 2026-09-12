# DG-202611 最终融合技术报告

**版本**：2026-09-12 初版  
**开发分支**：`codex/dg-robot-integration`  
**工作区**：`dg202611_robot_integration`

## 1. 目标与边界

本阶段把三个模型、已采集的UWB数据、RDK X5事件相机接口和毫米波规范化接口整理成可验证的ROS 2侧链。学长基础系统 `/home/nvidia/ros2_DL`、机器人备份和RDK备份均不在本阶段修改范围内。

辅助传感器默认采用观察门控模式：先证明数据到达、质量判断和模型调用，再决定是否让传感器改变LiDAR结果。新节点不发布 `/cmd_vel`，不直接控制底盘。

UWB材料统一写成“3个物理基站、6路逻辑观测接口”。已有UWB数据用于回放和MODEL-1接口验证，不据此宣称机器人地图坐标的绝对定位精度。

## 2. 系统结构

```text
RDK X5事件相机 ──> HVS桥 ──> 事件质量/特征/掩码 ─┐
Windows毫米波 ──> 规范化CSV/回放 ─> points/quality ─┼─> MODEL-2
已有UWB记录 ───> UWB回放 ──> pose/quality ─────────┘       │
                                                           ├─> MODEL-1融合
LiDAR、IMU、轮速、GNSS、AMCL、scan-match ────────────────────┘
                                                           ↓
                                             MODEL-3重定位与恢复
```

核心话题：

- MODEL-2：`/dg/lidar/filtered_scan`、`/dg/lidar/stable_features`、`/dg/lidar/quality`；
- MODEL-1：`/dg/fusion/pose`、`/dg/fusion/odom`、`/dg/fusion/status`；
- MODEL-3：`/dg/relocalization/match_quality`、`/cmd_vel_recovery`；
- 事件相机：`/dg/event_camera/features`、`/dg/event_camera/quality`、`/dg/event_camera/motion_mask`、`/dg/event_camera/camera_info`；
- 毫米波：`/dg/mmwave/points`、`/dg/mmwave/quality`；
- 传输诊断：`/dg/auxiliary/transport_quality`。

## 3. 已完成的代码工作

- 三模型侧链启动入口已经具备UWB回放、事件相机观察、毫米波回放和传输监视器开关；
- RDK脚本支持通过 `DG_RDK_USER`、`DG_RDK_HOST`、`DG_RDK_WORKSPACE`、`DG_RDK_RECORD_DIR` 和 `DG_RDK_TROS_SETUP`配置，不再依赖固定登录目录；
- RDK HVS桥默认记录目录由运行用户的 `$HOME`推导，空参数时使用 `$HOME/dg202611_rdk_records`；
- 传输监视器新增消息头时间戳、ROS接收时刻、本机接收时刻、消息年龄和尽力估算延迟；
- 事件相机原始事件流继续在RDK本地保存，跨板优先传输特征、质量和CameraInfo；
- 毫米波保留规范化CSV回放接口，真实厂商协议未确认前不启用实时解码和动态激光掩码。

## 4. 证据状态

当前已有软件协议、UWB真实采集和RDK本地事件相机采集证据。以下事项仍需在Linux ROS 2或真实设备上完成：

- RDK到NVIDIA的DDS发现和持续接收；
- 当前 `root`账号和当前HBN配置下的30至60秒事件相机长测；
- Jetson端对事件数据的实际接收证据；
- UWB回放进入MODEL-1后的`UWB_AIDED`状态证据；
- 毫米波真实型号、固件、输出协议和真实数据；
- 三模型在真实ROS 2图中的完整状态闭环；
- 用户现场执行的静止和低速运动验收。

## 5. 安全与声明规则

- `enable_cmd_vel_arbiter`默认关闭；
- `enable_mmwave_dynamic_mask`默认关闭；
- 事件相机内参、LiDAR外参和运动补偿未完成前保持`DIAGNOSTIC_ONLY`；
- 毫米波资料存在型号和供电差异，首次上电使用独立稳定5V电源，具体参数以实物和厂商资料为准；
- 只有日志、rosbag、CSV和现场记录支持的结果才能写入正式指标；
- 软件预检、回放结果和机器人实机结果必须在报告中分开标注。

## 6. 当前结论

代码接口和观察链已经准备好，下一步是Linux/ROS 2构建、RDK跨板传输验证、UWB回放证据和毫米波真实数据回放。当前不能把事件相机或毫米波写成已经主动改变LiDAR结果，也不能把软件预检写成实机指标。
