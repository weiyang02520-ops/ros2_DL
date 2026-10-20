# 机器人集成规格

核对日期：2026-10-15。依据当前工作树的 package.xml、launch、配置和实现编写。状态：源码契约整理及 LOCAL_ONLY 验证；不是整车交付合格证。本文不新增运行接口，不改变 MODEL-1/2/3，不修改底盘、导航或系统配置。

## 1. 范围与依据

覆盖硬件数据入口、定位导航、任务控制、UI、手机桥接、云端和离线证据链。外部平台仅按仓库协议描述，不假定平台服务已经部署。历史运行结论以原始报告日期为准，不自动继承到本次改动。

主要依据：

- 包边界：各 src 子目录 package.xml；完整声明依赖见 [仓库地图](REPO_MAP.md)。
- 启动与底盘选择：src/ylhb_base/launch/bringup.launch.py。
- 速度所有权：src/ylhb_base/scripts/cmd_vel_arbiter_node.py、cmd_vel_arbiter_core.py。
- 坐标系：src/ylhb_base/config/ekf.yaml、URDF、导航和 SLAM 配置。
- 外部接口：src/ylhb_mobile_bridge/config/mobile_bridge.yaml、ylhb_mobile_bridge 下的 ros_bridge.py、mobile_bridge_server.py、platform_api.py、platform_cloud_client.py。
- 云协议：[机器人平台协议](protocol/robot-platform-v1.md)；详细消息类型和生产者见 [通信矩阵](architecture/05-通信接口矩阵.md)。

## 2. 分层与进程职责

| 层 | 责任 | 依赖与约束 |
| --- | --- | --- |
| 驱动 | CAN/串口底盘、雷达、IMU、GNSS、事件视觉与相机 | Linux、设备权限、硬件 SDK；不能用进程存活代替有效数据 |
| 状态估计 | 轮式里程计、IMU、EKF、AMCL/SLAM 与多源实验模块 | 时间戳和坐标一致；底盘后端互斥；同一 TF 边不能重复发布 |
| 导航和控制 | Nav2、巡逻执行、速度仲裁 | 有效定位、地图和安全边界；AI/HTTP 不可绕过控制所有权 |
| 任务与交互 | 系统监督器、Agent policy/toolpack、QML、语音 | 任务级请求与真实执行分离，状态反馈不能冒充终态 |
| 网络与持久化 | FastAPI、WebSocket、平台客户端、SQLite、资产上传 | 身份、鉴权、目录和内容摘要校验；局域网监听不等于公网安全 |
| 证据与评估 | 采集清单、CSV、误差和重复率、教师要求评估 | 真实来源、完整清单和预冻结协议；合成输入不构成实机证据 |

Windows 当前只用于源码和离线 Python 检查。ROS 2 Humble/Ubuntu/Jetson 是仓库声明的目标环境，不是本轮实际运行环境。CUDA、ZED SDK、TensorRT、CAN 与 ROS 消息生成须在匹配目标机验证。

## 3. 数据与命令流

~~~text
雷达 /scan ───────────┐
IMU /imu/data ──┐     ├→ SLAM 或 AMCL → map 定位与导航输入
轮式 /odom ─────┴→ EKF┘
                        ↓
Nav2 /cmd_vel_nav ──────┐
恢复 /cmd_vel_recovery ─┼→ 仲裁 → /cmd_vel → 互斥底盘后端
授权手动 /cmd_vel_manual┘

QML / 手机 / 云命令 → 校验与任务边界 → 系统监督 / 巡逻执行 → Nav2
                  ← 状态、事件、执行标识与真实终态 ←

ZED / 视觉输入 → 推理或三维采集 → 文件快照 → 上传队列 → 外部平台确认
真实采集 → 会话清单与原始数据 → 离线指标 → 证据完整性与要求评估
~~~

上图表示职责流，不表示所有模式同时启动。实际重映射、节点命名和是否启用仲裁须结合现场 launch 参数与 ROS 图核对。独立视觉不得因此自动绑定机械臂、Nav2 或最终速度输出。

### 3.1 消息契约

| 接口 | 类型/表达 | 方向与含义 |
| --- | --- | --- |
| /scan | sensor_msgs/LaserScan | 雷达到定位、地图、导航；检查 frame_id、频率和时间 |
| /imu/data | sensor_msgs/Imu | IMU 到融合；检查安装方向和协方差 |
| /odom | nav_msgs/Odometry | 轮式反馈到融合及状态桥接，不等于全局定位 |
| /map | nav_msgs/OccupancyGrid | 地图源到导航和地图快照；未知区域不能伪装为空闲 |
| /amcl_pose | geometry_msgs/PoseWithCovarianceStamped | AMCL 定位反馈；存在消息不等于定位可信 |
| /cmd_vel_nav、/cmd_vel_recovery、/cmd_vel_manual、/cmd_vel | geometry_msgs/Twist | 输入源分离；最终输出按启用模式核对唯一发布者 |
| /dg/control/manual_authorized | std_msgs/Bool | 手动授权信号；还须由运行路径验证新鲜度和锁 |
| /patrol/command、/patrol/status、/patrol/event | std_msgs/String，结构化负载 | 巡逻命令、运行状态、事件；字段以实现和接口文档为准 |
| /inspection_ai/system_command、/inspection_ai/system_status | std_msgs/String，结构化负载 | 系统模式命令与监督反馈，不能仅凭发送动作标完成 |
| HTTP /api/status、WebSocket /ws/status、/ws/map | JSON/地图帧，具体封装见契约 | 聚合状态与显示，不是物理安全回路 |

### 3.2 坐标、时间与模式

EKF 配置声明 world_frame=odom、base_link_frame=base_footprint，并发布对应 TF；base_link 与传感器安装关系从 URDF 获取。AMCL 或建图模式提供 map 到 odom 的关系。不能另造一条静态 map 到 odom 掩盖定位缺失。

同一时间只允许预定模式拥有建图或定位链。检查实际启动选择、时间源、传感器时间戳和 TF 连续性；历史报告中的 base_link 简写不能覆盖当前配置的 base_footprint。仿真/回放启用模拟时间时，需要所有相关节点与时钟来源一致。

## 4. 命令与执行生命周期

以下是验收阶段划分，不是新增枚举或对现有 JSON 字段的重命名：请求校验 → 持久化/接收确认 → 等待执行前提 → 执行中 → 成功、失败或取消。HTTP 202、云 ACK、上传入队均只对应中间阶段。

平台命令、deployment 与 execution 使用协议已有标识关联。重复投递不得创建冲突内容；地图与路线应验证身份和摘要；同一部署标识的冲突由存储层拒绝。前端必须继续观察状态和事件，不把请求返回成功解释成机器人已到达。

具体巡逻状态字段、开始/暂停/继续/取消入口和失败原因见 patrol_executor_node.py 与 [接口契约](API_CONTRACT.md)。字段随代码调整时，同步修改契约和行为测试，不在本文发明新状态。

## 5. 错误处理与恢复边界

| 条件 | 现有机制/处理要求 | 恢复与验收 |
| --- | --- | --- |
| 非法字段或范围 | HTTP 校验失败，保留明确错误 | 修正请求；不得改成默认成功 |
| 本地令牌无效 | 鉴权启用时拒绝，平台鉴权独立检查 | 核对两层设置，不在日志打印令牌 |
| 本地 APP 被停用 | 返回不可用，不转发控制 | 由授权人员恢复配置，不绕过开关 |
| 云连接与入站控制冲突 | platform_api 默认拒绝冲突入站控制 | 保持唯一控制入口，按现有开关处理 |
| 地图/路线/部署不一致 | 存储或管理层拒绝冲突 | 核对绑定、YAML/PGM 与摘要，不跳过校验 |
| 数据过期或所有权切换 | 仲裁核心提供过期判断和切换零速度保护 | 本轮未验证实际停车，须现场确认 |
| 驱动失联 | 配置存在速度超时和退出停车 | 不是物理急停替代品，现场验证停止效果 |
| 网络超时/临时失败 | 上传和平台客户端有队列/退避机制 | 按模块区分可重试错误与凭据阻塞；不无限重试鉴权失败 |
| 进程退出、磁盘满 | 保留失败原因与已有持久化任务 | 诊断日志、目录权限与队列，再按部署流程恢复 |
| 离线输入不兼容 | 两种特征格式混用或非法距离明确报错 | 调用者修正输入；不把不可比较数据记为零重复率 |

HTTP 的精确状态码和错误载荷以 mobile_bridge_server.py/platform_api.py 为准；不能把不同子系统的错误一律包装为同一个字段。当前常见拒绝包括 401、404、409、422、503，但并非每条路由都实现全部状态。

## 6. 配置目录与默认值

### 6.1 ROS 与设备

| 来源 | 配置项 | 当前源码默认/含义 |
| --- | --- | --- |
| bringup.launch.py | base_backend | zlac；另有 stm32 条件分支，不能同时控制底盘 |
| 同上 | enable_cmd_vel_arbiter | true；关闭需要单独审查控制来源，不是排障捷径 |
| cmd_vel_arbiter_node.py | source_timeout / switch_guard_duration / status_timeout | 0.5 / 0.2 / 1.0 秒，表示接收超时、切换保护和状态超时 |
| ekf.yaml | use_sim_time / publish_tf / frequency | false / true / 30.0 Hz；目标环境须核对 |
| zlac8015d.yaml | cmd_timeout_sec / stop_on_exit / fault_reset_on_start | 0.5 秒 / true / false；本轮不修改 |
| base_kinematics.yaml、URDF | 几何和安装关系 | 需追溯 CAD/实测依据，不能用软件假设充当标定 |
| nav2_params*.yaml、slam_toolbox_params.yaml | footprint、scan、未知区域、规划和建图 | 安全与地图语义红线，改动须目标机复验 |

### 6.2 桥接、地图和上传

来源：src/ylhb_mobile_bridge/config/mobile_bridge.yaml。

| 配置项 | 当前默认 | 使用边界 |
| --- | --- | --- |
| host / port | 0.0.0.0 / 8000 | 监听所有网卡，不应直接暴露公网 |
| require_token / api_token | false / 空 | 默认不是已加固配置，投入现场前单独配置和验证 |
| platform_api_token / robot_id | 空 / 空 | 平台身份与本地令牌不是同一概念 |
| status_rate_hz / map_stream_rate_hz | 2.0 / 1.0 | 状态与地图显示频率，不是控制频率 |
| map_max_size_px | 1024 | 缩略图限制；不能覆盖原图坐标元数据 |
| gps_stale_timeout_sec | 3.0 | GNSS 状态新鲜度阈值，不是精度保证 |
| max_linear_speed / max_angular_speed | 0.30 m/s / 0.55 rad/s | 桥接入口限制，不代表整个底盘全局唯一限速 |
| default_cmd_duration_ms | 300 | 单次手动请求默认持续时间 |
| platform_storage_dir | ~/.local/share/ylhb/platform | 运行数据位置，不是源码目录 |
| workspace_dir / default_map_path | /home/nvidia/ros2_DL / 该目录下 maps/my_map | 目标路径默认值，安装到别处必须核对 |
| scene_upload_allowed_root | /home/nvidia/ros2_DL/runs/3d_reconstruct | 三维资产允许根目录，禁止越界文件上传 |

### 6.3 云环境变量

来源：platform_cloud_client.py。凭据只在授权运行环境注入，本轮不读取或写入真实令牌。

| 环境变量 | 默认或用途 |
| --- | --- |
| YLHB_CLOUD_ENABLED | false；是否默认启用云连接 |
| YLHB_CLOUD_BASE_URL | 空；平台服务根地址 |
| YLHB_CLOUD_ROBOT_TOKEN | 空；机器人 Bearer 凭据，禁止提交 |
| YLHB_CLOUD_REQUEST_TIMEOUT_SEC | 10 秒 |
| YLHB_CLOUD_IDLE_HEARTBEAT_SEC / YLHB_CLOUD_ACTIVE_HEARTBEAT_SEC | 3 / 1 秒 |
| YLHB_CLOUD_MAX_BACKOFF_SEC | 30 秒 |
| YLHB_CLOUD_LOCAL_CONFIRM_TIMEOUT_SEC | 默认 1800 秒，代码还有边界处理 |
| YLHB_CLOUD_CA_FILE | 可选 CA 文件 |
| YLHB_SOFTWARE_VERSION | unknown；心跳软件版本标识 |

配置优先级不能统一猜成“环境变量覆盖所有 YAML”。云客户端明确读取环境，ROS 参数按节点声明和 launch 传入生效，业务模块还可能有独立配置。发布时记录最终生效值及其来源，敏感值只记录是否配置。

## 7. 离线评估接口与本轮兼容性

feature_repeatability_evaluator.py 使用 CSV 输入，输出文本及可选 JSON。空间点匹配计算 2M/(N1+N2)，空特征帧对不当作完美匹配。旧 feature_ids 格式保留，但同一非空帧对不能一帧空间点、一帧旧 ID。该组合原先被当作旧 ID 比较，容易把格式错误记成真实性能退化。

单帧对和汇总入口现在都要求匹配距离有限且大于零。非法参数在数据不足时也会先被拒绝；有效距离的空间匹配、旧 ID 匹配、聚合公式和 JSON 字段不变。CLI 对此类 ValueError 返回 1，不生成一次新的成功报告。调用者不得因异常而沿用旧结果。

## 8. 验收和明确未验证项

离线入口：在仓库根目录执行 python scripts/run_offline_integration_checks.py。它只运行列明的两个测试文件，不启动 ROS、不连接网络、不触碰机器人。完整测试分类与现场交接见 [测试计划](TEST_PLAN.md)。

本轮没有进行 Jetson 构建、真实设备采集、ROS 图观察、地图路线实跑或云端往返。所有这些结论保持 NOT_PROVEN。现场人员执行运动测试，Agent 不能启动实机 bringup、发布速度或发送导航目标。交付前按 [ADR-001](ADR-001.md)、[ADR-002](ADR-002.md)、[ADR-003](ADR-003.md) 分别审核边界、配置和证据。
