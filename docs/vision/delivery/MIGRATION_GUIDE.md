# 迁移指南（对方机器人 / 机械臂同学）

状态：软件合同就绪；对方实机标定 **PEER_CALIBRATION_NOT_RUN**。

## 1. 兼容确认

1. ZED 型号 / SDK / ROS 发行版 / CPU 架构（x86_64 vs aarch64）
2. 使用同一 `vision_perception_interfaces` 消息版本
3. 不依赖本仓库生产 Nav2/底盘包

## 2. 先跑相机坐标（A 层）

1. 填 `config/profiles/peer_robot_template.yaml` 中 RGB/Depth/CameraInfo 话题与 QoS
2. 隔离安装依赖（见 `docs/vision/ARM64_DEPENDENCY_PLAN.md`）
3. `ros2 launch vision_perception vision_zed_subscribe.launch.py`（只订阅，不启 SDK）
4. 用 `ros2 run vision_perception vision_subscribe_objects` 核对 `frame_id`、时间戳、`position_valid`

## 3. 标定与转换（B 层软件能力）

1. 完成相机光学系 → 目标 `target_frame` 标定（静态或动态 TF）
2. 填 `peer_robot_template.yaml`：`source_frame`、`target_frame`、`translation_m`、旋转、日期、`extrinsics_id`
3. **禁止**拷贝他机矩阵或使用单位矩阵冒充
4. `ros2 launch vision_perception vision_object_transform.launch.py enabled:=true …`
5. 订阅 `/dg/vision/objects_target`；注意 bbox/reference_u/v 仍是**源图像像素**
6. 独立测量若干已知点，核对方向与单位

## 4. 无效与安全

- `position_valid=false` + NaN + `invalid_reason` 必须保留
- 缺 TF / 过期：目标输出无效，相机 `/dg/vision/objects` 仍可独立保留
- `orientation_valid` 恒 false；表面点 ≠ 抓取点
- 视觉节点不输出动作；抓取由对方控制栈负责

## 5. 回退

停转换与感知节点即可；不改对方生产 TF 树。删除隔离工作空间不影响其它包。
