# DG-202611 机器人融合准备说明

这份分支用于把 MODEL-1、MODEL-2、MODEL-3 和已经采集的真实 UWB 数据接到
现有机器人系统。它是独立开发副本，不替换保存好的机器人备份，也不加入现有开机
自启动。

## 已接好的链路

- MODEL-2：`/scan`、`/odom` -> `/dg/lidar/quality`。
- MODEL-1：里程计、GNSS、AMCL、scan-match、UWB pose/quality -> `/dg/fusion/*`。
- MODEL-3：定位健康、主动扫描、候选位姿验证、恢复状态 -> `/dg/relocalization/*`。
- UWB：保存的真实 CSV -> 六路逻辑观测 -> 三个物理源去重 -> 质量门控 ->
  `/dg/uwb/pose`、`/dg/uwb/quality` -> MODEL-1。

三个真实基站的坐标为 A2=`(0,0)`、A3=`(2.4,0)`、A4=`(1.2,1.8)`。六路逻辑接口
不会被当作六个独立物理基站。

## 安全部署步骤

在机器人独立工作区构建，不覆盖 `/home/nvidia/ros2_DL`：

```bash
cd /home/nvidia/dg202611_ws
source /opt/ros/humble/setup.bash
source /home/nvidia/ros2_DL/install/setup.bash
colcon build --symlink-install \
  --packages-select ylhb_base ylhb_mobile_bridge \
  --allow-overriding ylhb_base ylhb_mobile_bridge
source install/setup.bash
```

第一次只做旁路观察：

```bash
./scripts/run_dg_integration.sh
```

默认行为有三道隔离：不启动 Nav2、不启动 UWB 回放、不启动速度仲裁器。即使以后
显式启动仲裁器，默认输出也只是 `/dg/test_cmd_vel`，不会直接控制底盘。

回放真实 UWB 稳态数据，但先不让它参与地图融合：

```bash
./scripts/run_dg_integration.sh \
  enable_uwb_replay:=true
```

检查：

```bash
ros2 topic echo /dg/uwb/quality --once
ros2 topic echo /dg/uwb/pose --once
ros2 topic echo /dg/fusion/status --once
```

## UWB 与地图对齐

UWB 坐标系和机器人 `map` 坐标系还缺一个二维刚体变换。部署时在同一参考点记录
UWB `(x,y)` 和机器人地图 `(x,y)`，确认方向后设置：

```text
map_x = cos(yaw) * uwb_x - sin(yaw) * uwb_y + offset_x
map_y = sin(yaw) * uwb_x + cos(yaw) * uwb_y + offset_y
```

完成对齐后才启用 MODEL-1 的 UWB 更新：

```bash
./scripts/run_dg_integration.sh \
  enable_uwb_replay:=true \
  uwb_alignment_enabled:=true \
  uwb_to_map_yaw:=0.0 \
  uwb_to_map_offset_x:=0.0 \
  uwb_to_map_offset_y:=0.0
```

具体的三个变换值要用机器人现场地图参考点填写。缺少这一步时，程序会发布真实
UWB 质量和位置，但 MODEL-1 不会把它当作地图坐标更新。

## 实机运动边界

MODEL-1、MODEL-2 和 UWB 都可以在底盘不动时验证。MODEL-3 完整闭环需要机器人
转动，速度仲裁器也只有在现场有人看护、底盘驱动器供电正常、急停可用时才启用：

```bash
enable_cmd_vel_arbiter:=true cmd_vel_output_topic:=/cmd_vel
```

这两个参数不会写入默认配置或开机自启动。实机验证完成前，三模型输出保持在
`/dg/*` 旁路话题，不替换学长原系统的 `/odom`、TF 或手机控制链路。

## 保留的底盘方向修复

独立分支保留了已经在机器人上验证有效的手机控制方向修复：
`ylhb_mobile_bridge/ros_bridge.py` 发布时只反转 `linear.x`，不改变 `angular.z`，也
不修改 `base_kinematics.yaml`。
