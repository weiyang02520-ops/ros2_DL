# DG-202611 一次性实机采集流程

本流程用于尽量一次收齐方案书需要的机器人数据。采集器只订阅 ROS 2 话题、读取
系统状态并记录 rosbag，不会发布运动命令。所有移动、遮挡和故障注入均由现场人员
明确执行。

## 开始前

1. 机器人上层和底盘电池均有电，急停按钮可立即使用。
2. 手机控制、UI、建图/导航和底盘单独验证正常。
3. `/home/nvidia/ros2_DL` 保持原样，三模型位于 `/home/nvidia/dg202611_ws`。
4. 在地面用卷尺标记起点、两个中间点和终点，记录相对坐标并拍照。
5. 每次实验前记下场景编号；不能在看完结果后修改阈值或删除失败trial。

## 采集命令

在一个独立终端运行：

```bash
cd /home/nvidia/dg202611_ws
./scripts/run_real_robot_capture.sh \
  --scenario EXP02_IDLE_REAL \
  --duration 180 \
  --operator peng \
  --hardware-notes "上下电池已供电；急停可用；底盘静止"
```

等待终端显示 `CAPTURE_READY:` 后再开始本场景动作。

结果默认保存在：

```text
/home/nvidia/dg202611_ws/results/real_robot/YYYYmmdd_HHMMSS_<scenario>/
```

每个目录自动包含 `metadata.json`、`result.json`、`rosbag/`、资源采样、节点/话题/
参数快照、CAN和手机桥接状态、日志及SHA256清单。`capture_status=COMPLETE`只表示
采集完整，不代表性能合格。

## 推荐顺序

| 顺序 | 场景编号 | 时长 | 现场动作 | 主要用途 |
|---:|---|---:|---|---|
| 1 | EXP02_IDLE_REAL | 180 s | 机器人静止 | 节点、频率、TF、CPU/GPU/内存基线 |
| 2 | EXP03_LIDAR_CLEAR | 120 s | 环境保持静态 | MODEL-2正常质量基线 |
| 3 | EXP03_LIDAR_PARTIAL | 120 s | 纸板遮挡约1/3雷达视场 | 局部遮挡检测与降级 |
| 4 | EXP03_LIDAR_BLOCKED | 60 s | 短时遮挡大部分视场后恢复 | 拒绝与恢复滞回 |
| 5 | EXP03_LIDAR_DYNAMIC | 120 s | 一人在机器人前方横向往返 | 动态目标与稳定特征 |
| 6 | EXP01_ROUTE_BASELINE_R1-R3 | 每次按路线结束 | 三次相同路线，三模型关闭 | 原系统轨迹基线 |
| 7 | EXP01_ROUTE_FUSION_R1-R3 | 每次按路线结束 | 三次相同路线，三模型旁路开启 | 融合输出对比 |
| 8 | EXP04_INVALID_CANDIDATE | 60 s | 机器人静止，运行预先冻结的错误候选注入 | 验证错误候选拒绝 |
| 9 | EXP04_ACTIVE_RECOVERY_R01-R20 | 每次最长60 s | 空旷区域，逐次执行冻结的定位异常场景 | 恢复成功率与时间 |
| 10 | EXP02_ENDURANCE | 600 s | 三模型同时运行并正常使用手机/UI | 稳定性和资源裕量 |

第8、9项涉及恢复状态和可能的旋转动作。开始前必须确认速度仲裁器所有权、周围空旷
和急停；采集器本身不会启动这些动作。

## UWB数据的使用

UWB硬件数据已经采完，不需要在上述流程中重新连接。分别回放三份已封存数据：

```bash
./scripts/run_dg_integration.sh \
  enable_uwb_replay:=true \
  uwb_replay_file:=$(ros2 pkg prefix --share ylhb_base)/data/uwb/20260905/static_raw_20260905_165208.csv
```

另外两份为 `move_raw_20260905_170425.csv` 和 `anchor_fault.csv`。每份回放时单独启动
一次采集，场景编号分别使用 `UWB_STATIC_REPLAY`、`UWB_MOVE_REPLAY` 和
`UWB_ANCHOR_FAULT_REPLAY`。

如果只验证软件消费链，可保持 `uwb_alignment_enabled:=false` 并记录 UWB质量话题；
如果要验证 MODEL-1 的 `UWB_AIDED`，必须先冻结 UWB到map的二维变换，再设置为true。

## 每次结束后的现场检查

```bash
session=$(ls -dt results/real_robot/* | head -n 1)
cat "$session/result.json"
test -f "$session/rosbag/metadata.yaml"
(cd "$session" && sha256sum -c manifest.sha256)
```

同时记录肉眼观察：机器人是否按预期动作、是否人工接管、是否碰撞/安全中止、UI和
手机是否掉线。任何失败trial都保留。

## 传回Windows

完成全部场景后，在 Windows PowerShell 执行：

```powershell
scp -r nvidia@<机器人当前IP>:/home/nvidia/dg202611_ws/results/real_robot "$env:USERPROFILE\Downloads\DG202611_real_robot_20260907"
```

传回后再次校验每个session的 `manifest.sha256`，再运行位置误差、特征重复率和重定位
评价器，生成第9章表格和图。原始rosbag、CSV和日志不做覆盖式修改。
