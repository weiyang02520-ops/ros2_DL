# 仓库地图

核对日期：2026-10-15。描述当前工作树，不代表所有包已构建或已部署。

## 一、目录与责任

| 位置 | 内容 | 修改边界 |
| --- | --- | --- |
| `src/ylhb_base/` | 底盘、里程计、GNSS/UWB、导航配置与实验核心 | 方向、几何、控制和硬件接口属高风险区 |
| `src/ylhb_interfaces/` | 自定义消息、服务及任务接口 | 字段变化需检查所有生产者和消费者 |
| `src/ylhb_llm/` | 系统监督器、任务、语音、策略和 QML | 区分任务接收与物理完成 |
| `src/ylhb_mobile_bridge/` | HTTP/WebSocket、ROS 桥接、地图路线和上传 | 网络控制与文件写入边界 |
| `src/ylhb_perception/` | 既有视觉推理和模型目录 | 模型权重不随源码完整交付 |
| `src/ylhb_3d_mapping/` | 三维采集和重建 | SDK、磁盘及输出目录分别核对 |
| `src/dg_hvs_bridge/` | 事件视觉桥接 | 软件启动不代表检测到真实传感器 |
| `src/dg_synthetic_validation/` | 合成数据验证 | 不得作为实机功能完成证明 |
| `src/vision_perception/`、`src/vision_perception_interfaces/` | 已有未提交独立视觉实现与接口 | 本轮不改，不宣称已部署 |
| `src/hipnuc_imu/`、`src/rplidar_ros-ros2/` | IMU 与雷达驱动 | 不顺手整理或替换驱动 |
| `src/zed-ros2-wrapper/` | 上游 ZED 包装与组件 | 保留上游结构及专门说明 |
| `scripts/` | 构建、部署、采集、诊断和评估 | preflight、smoke 的名称不保证无副作用 |
| `maps/`、`scenarios/` | 地图资产和场景配置 | 文件存在不是现场执行证据 |
| `evidence/` | 按专题和日期保存的证据 | 保留来源，勿用生成数据替换 |
| `docs/architecture/` | 架构图与通信矩阵 | 拓扑说明不替代运行观测 |
| `docs/dg202611/` | 目标、核心模型、验收与历史交付 | 检查时间与证据适用范围 |
| `skills/` | 测试规范、ROS 实践和运动边界 | 修改测试、处理实机前遵守 |
| `tools/route_map_tool/` | 地图路线工具 | 离线合法不代表实地可通行 |
| `CAD/`、`记录照片/`、`官方通信协议/` | 结构、照片与协议参考 | 几何参数需追溯依据 |

## 二、按任务找入口

以下 Python 模块除另注外均在 `src/ylhb_mobile_bridge/ylhb_mobile_bridge/`。

| 任务 | 入口 |
| --- | --- |
| HTTP 路由和鉴权 | `mobile_bridge_server.py` |
| 平台部署与执行接口 | `platform_api.py`、`platform_store.py` |
| 请求字段与默认值 | `schemas.py` |
| ROS 话题与缓存 | `ros_bridge.py`；包内 `config/mobile_bridge.yaml` |
| 巡逻状态机和路线 | `patrol_executor_node.py`、`patrol_route_store.py` |
| 地图显示与文件管理 | `map_snapshot.py`、`map_manager.py` |
| 弱网与资产上传 | `map_upload.py`、`scene_upload.py`、`inspection_image_upload.py` |
| 构建 | `scripts/build_on_jetson.sh` |
| 发行包写入 | `scripts/deploy_release_from_windows.ps1`、`scripts/install_release_on_robot.sh` |
| 误差和重定位统计 | `scripts/position_error_evaluator.py`、`scripts/relocalization_evaluator.py` |
| 真实要求评估 | `scripts/teacher_requirements_evaluator.py` |

## 三、责任方向

~~~text
本体界面 / 移动端 / 云平台
    → 任务和系统命令 → 系统监督器 → 导航 / 巡逻执行
    ← 状态、事件、位姿 ← ROS 桥接和持久化

雷达 / IMU / 里程计 → 定位与导航 → 受控速度链 → 底盘
相机 → 图像和深度 → 推理或三维采集 → 快照和上传
真实采集 → 原始文件与清单 → 离线统计 → 要求评估
~~~

最终速度来源、TF 发布者和进程所有权必须按 [集成说明](INTEGRATION.md) 现场核对。

## 四、测试入口

- `src/ylhb_base/test/`：几何、安全配置、传感器纯逻辑、误差与证据评估。
- `src/ylhb_mobile_bridge/test/`：地图、路线、网络、进程、请求和平台客户端。
- `src/ylhb_llm/test/`：任务、策略、监督器及界面语义绑定等。
- 本轮只增加离线统计测试和人工验收骨架，不增加默认硬件依赖。

## 五、已有改动保护

本轮开始前，地图管理实现及其测试已有改动；视觉目录、相关文档、导航话题审计脚本、状态文件和 `artifacts/` 已有未提交内容。本轮不清理、不覆盖、不提交这些内容。

发行前必须明确选择已提交快照还是当前工作树包。`git archive HEAD` 不包含未提交文件，不能直接当作本次完整交付。

## 六、本轮补充的结构和依赖清单

本节为本次增量梳理，不覆盖上轮已经存在的地图实现、测试和视觉文件。仓库包含 16 份 ROS 包声明；目录名与包名不一定相同，例如 rplidar_ros-ros2 声明为 rplidar_ros。以下是源码声明，不是已安装清单，也不是完整传递依赖锁文件。

### 6.1 一级目录补全

| 目录或文件组 | 职责与边界 |
| --- | --- |
| .git/ | 版本库元数据，不属于部署运行资产，本轮不改历史和远端 |
| .pytest_cache/、各 __pycache__/ | 本地检查缓存，不能作为验收证据或源码交付主体 |
| artifacts/ | 已有未提交生成产物，本轮保留，不擅自发布 |
| UI_sc/ | 界面素材和参考，运行 QML 入口仍在 ylhb_llm 包内 |
| 根目录状态报告 | GNSS、导航、预硬件等专题快照，按原日期解读，不作为当前整车状态 |
| docs/validation/ | 命令、验证结果和边界；历史记录不覆写成本轮结果 |
| docs/protocol/ | 外部平台协议及身份、部署、事件语义 |
| docs/superpowers/ | 历史方案和设计，不等于每条计划均已实施 |
| scenarios/ | 场景与实验输入，需区分合成样例和真实会话 |

### 6.2 包内职责细分

| 模块 | 重要子目录/入口 | 调用方向与依赖 |
| --- | --- | --- |
| ylhb_base | src/、include/ | C++ 底盘/定位设备驱动；ROS 消息、设备与 Linux 接口 |
| ylhb_base | scripts/ | 多源融合、导航监督、重定位、UWB 和速度仲裁，纯核心与 ROS 包装并存 |
| ylhb_base | launch/、config/、urdf/、behavior_trees/ | 启动、设备参数、坐标与几何、导航行为树，不应作为普通文档批量整理 |
| ylhb_base | data/、test/ | 历史数据及针对性测试，数据存在不代表新版本已采集 |
| ylhb_llm | ylhb_llm/system_supervisor_node.py | 系统模式、进程和运行条件监督 |
| ylhb_llm | inspection_agent_*、agent_policy.py、agent_tools.py | Agent 规格、运行与工具策略；任务级入口不替代底盘安全链 |
| ylhb_llm | ui_backend.py、ui_ros_bridge.py、qml/ | 界面与 ROS 状态/命令绑定；语音节点另行处理输入输出 |
| ylhb_mobile_bridge | ros_bridge.py、mobile_bridge_server.py | ROS 缓存/发布和 HTTP/WS 适配，不能把缓存状态当实时硬件确认 |
| ylhb_mobile_bridge | patrol_executor_node.py、patrol_route_store.py | 路线绑定、任务状态与 Nav2 action 执行 |
| ylhb_mobile_bridge | platform_api.py、platform_cloud_client.py、platform_store.py | 入站控制、主动云连接、部署及事件持久化，控制所有权需互斥 |
| ylhb_mobile_bridge | map_*、scene_upload.py、inspection_image_upload.py | 地图、不可变资产、上传队列与远端确认 |
| ylhb_3d_mapping | 包内 Python 节点、config/、launch/ | ZED 采集/重建，运行还依赖设备 SDK，不仅是 package.xml |
| ylhb_perception | src/、scripts/、模型相关目录 | 既有图像推理实现，模型和 GPU 运行条件独立验收 |
| vision_perception 及接口包 | Python 实现、config/、msg/ | 已有未提交独立视觉路径，保持隔离，不认作本轮已部署功能 |
| dg_hvs_bridge | src/、launch/、config/ | 事件视觉桥接，后端可用性与实际检测分开记录 |
| dg_synthetic_validation | Python 包、launch/、场景配置 | 合成测试与回放，只证明对应实验链 |
| hipnuc_imu、rplidar_ros | 驱动源码和配置 | 设备数据进入 ROS，保留第三方 SDK 维护边界 |
| zed_components、zed_wrapper | C++ 组件、launch/config | ZED 驱动组件及启动封装；zed_ros2 为聚合包，zed_debug 为调试包 |
| ylhb_interfaces、vision_perception_interfaces | msg/ | 接口生成优先于引用方构建；字段变更需要全部上下游同步 |

### 6.3 依赖方向

~~~text
接口包 → 使用接口的节点
hipnuc_imu / rplidar_ros → ylhb_base 的 bringup 与定位导航
zed_components → zed_wrapper / zed_debug → zed_ros2 聚合
ylhb_mobile_bridge / ylhb_3d_mapping / ylhb_interfaces → ylhb_llm
vision_perception_interfaces → vision_perception
离线 scripts 评估器 → 真实要求评估器 → 定向离线检查入口
~~~

箭头表示前置依赖到使用者，不等同于全部 ROS 消息方向。跨包动态导入、launch 调用与外部 SDK 可能不完整体现在 manifest 中，目标机仍需 colcon/rosdep 和导入检查。不要把上表直接改成手写固定构建顺序。

### 6.4 全部包的显式依赖

仅列 depend、build_depend、exec_depend、buildtool_depend，去除注释与重复声明；不包含 test_depend、传递依赖和系统中预装 SDK。ROS 条件依赖以原 manifest 的 condition 为准，本表只展示名称并集。

| 包名 | 声明位置 | 显式依赖名称并集 |
| --- | --- | --- |
| `dg_hvs_bridge` | `src/dg_hvs_bridge/package.xml` | `ament_cmake`、`rclcpp`、`sensor_msgs`、`diagnostic_msgs`、`ament_index_python`、`launch`、`launch_ros`、`rclpy` |
| `dg_synthetic_validation` | `src/dg_synthetic_validation/package.xml` | `ament_python`、`rclpy`、`python3-numpy`、`visualization_msgs`、`tf2_ros`、`ament_index_python`、`diagnostic_msgs`、`geometry_msgs`、`nav_msgs`、`sensor_msgs`、`std_msgs`、`python3-yaml`、`rosbag2_transport`、`ros2cli` |
| `hipnuc_imu` | `src/hipnuc_imu/package.xml` | `ament_cmake`、`rclcpp`、`std_msgs`、`sensor_msgs` |
| `rplidar_ros` | `src/rplidar_ros-ros2/package.xml` | `ament_cmake_auto`、`ament_cmake_ros`、`rclcpp`、`sensor_msgs`、`std_srvs`、`rclcpp_components` |
| `vision_perception` | `src/vision_perception/package.xml` | `ament_python`、`rclpy`、`diagnostic_msgs`、`ament_index_python`、`launch`、`launch_ros`、`sensor_msgs`、`vision_msgs`、`vision_perception_interfaces` |
| `vision_perception_interfaces` | `src/vision_perception_interfaces/package.xml` | `ament_cmake`、`rosidl_default_generators`、`std_msgs`、`geometry_msgs`、`rosidl_default_runtime` |
| `ylhb_3d_mapping` | `src/ylhb_3d_mapping/package.xml` | `ament_python`、`rclpy`、`sensor_msgs`、`std_msgs`、`python3-yaml` |
| `ylhb_base` | `src/ylhb_base/package.xml` | `ament_cmake`、`rclcpp`、`std_msgs`、`sensor_msgs`、`nmea_msgs`、`diagnostic_msgs`、`geometry_msgs`、`nav_msgs`、`std_srvs`、`behaviortree_cpp_v3`、`robot_localization`、`hipnuc_imu`、`rplidar_ros`、`slam_toolbox`、`nav2_bringup`、`nav2_map_server`、`nonpersistent_voxel_layer`、`nav2_lifecycle_manager`、`robot_state_publisher`、`xacro`、`rclpy`、`python3-numpy`、`python3-serial`、`tf2`、`tf2_ros`、`tf2_geometry_msgs` |
| `ylhb_interfaces` | `src/ylhb_interfaces/package.xml` | `ament_cmake`、`rosidl_default_generators`、`std_msgs`、`rosidl_default_runtime` |
| `ylhb_llm` | `src/ylhb_llm/package.xml` | `ament_python`、`rclpy`、`std_msgs`、`std_srvs`、`geometry_msgs`、`diagnostic_msgs`、`lifecycle_msgs`、`tf2_ros`、`sensor_msgs`、`cv_bridge`、`python3-yaml`、`python3-pyqt5`、`python3-pyqt5.qtquick`、`python3-pil`、`qml-module-qtquick2`、`qml-module-qtquick-window2`、`qml-module-qtquick-controls2`、`qml-module-qtquick-layouts`、`qml-module-qtqml-models2`、`ylhb_interfaces`、`ylhb_mobile_bridge`、`ylhb_3d_mapping` |
| `ylhb_mobile_bridge` | `src/ylhb_mobile_bridge/package.xml` | `ament_python`、`rclpy`、`geometry_msgs`、`diagnostic_msgs`、`std_msgs`、`std_srvs`、`nav_msgs`、`sensor_msgs`、`nav2_msgs`、`action_msgs`、`python3-fastapi`、`python3-uvicorn`、`python3-pydantic`、`python3-multipart`、`python3-numpy`、`python3-pil`、`python3-yaml` |
| `ylhb_perception` | `src/ylhb_perception/package.xml` | `ament_cmake`、`rclcpp`、`sensor_msgs`、`std_msgs`、`cv_bridge`、`rclpy`、`geometry_msgs`、`vision_msgs` |
| `zed_components` | `src/zed-ros2-wrapper/zed_components/package.xml` | `ament_cmake`、`ament_cmake_auto`、`backward_ros`、`nlohmann-json-dev`、`zed_msgs`、`rclcpp`、`rclcpp_components`、`rcutils`、`builtin_interfaces`、`std_msgs`、`rosgraph_msgs`、`stereo_msgs`、`sensor_msgs`、`geometry_msgs`、`nav_msgs`、`nmea_msgs`、`geographic_msgs`、`tf2`、`tf2_ros`、`tf2_geometry_msgs`、`image_transport`、`std_srvs`、`diagnostic_msgs`、`diagnostic_updater`、`visualization_msgs`、`robot_localization`、`launch_ros`、`image_transport_plugins`、`compressed_image_transport`、`compressed_depth_image_transport`、`theora_image_transport` |
| `zed_debug` | `src/zed-ros2-wrapper/zed_debug/package.xml` | `ament_cmake`、`ament_cmake_auto`、`rclcpp`、`rclcpp_components`、`rcutils`、`zed_components`、`backward_ros` |
| `zed_ros2` | `src/zed-ros2-wrapper/zed_ros2/package.xml` | `ament_cmake`、`ament_cmake_auto`、`zed_msgs`、`zed_description`、`zed_components`、`zed_wrapper` |
| `zed_wrapper` | `src/zed-ros2-wrapper/zed_wrapper/package.xml` | `ament_cmake`、`ament_cmake_auto`、`zed_components`、`launch_ros`、`zed_description`、`xacro`、`image_transport_plugins`、`compressed_image_transport`、`compressed_depth_image_transport`、`theora_image_transport` |

### 6.5 脚本按副作用分类

| 类别 | 代表入口 | 默认处理 |
| --- | --- | --- |
| 本轮离线回归 | scripts/run_offline_integration_checks.py | 只启动明确列出的 pytest，不连接硬件或网络 |
| 纯文件评估 | feature_repeatability_evaluator.py、teacher_requirements_evaluator.py | 输入来源须检查；输出写入也应选定位置，不覆写原始数据 |
| 数据采集与探测 | real_robot_capture.py、capture_serial_sensor_raw.py、probe_rdk_x5_event_camera.sh | 先审查设备、话题和副作用，不按名称假定只读 |
| 构建与发行 | build_on_jetson.sh、deploy_release_from_windows.ps1、install_release_on_robot.sh | 构建、写入、激活分别记录；本轮不执行 |
| 网络、驱动和服务配置 | configure_*、install_*、setup_* | 会改运行环境，非本轮修复范围 |
| 实机与巡逻启动 | run_dg_inspection.sh、run_patrol_low*、run_on_jetson.sh | 由现场人员执行，不由 Agent 代跑 |
| 版本发布 | git_publish.sh | 推送有外部副作用，本轮不执行 |

### 6.6 本轮交付入口

[集成规格](INTEGRATION_SPEC.md)、[测试计划](TEST_PLAN.md)、[ADR-001](ADR-001.md)、[ADR-002](ADR-002.md)、[ADR-003](ADR-003.md)、[技术债](../TECH_DEBT.md)、[变更草稿](../CHANGELOG_DRAFT.md)。本轮对旧文档采用增量补充，不把上轮结果冒充新测试。
