# 接口契约

核对日期：2026-10-15。依据当前 `mobile_bridge_server.py`、`platform_api.py`、`schemas.py`、`ros_bridge.py` 和桥接 YAML。本文不新增接口或改变权限。

## 一、协议和鉴权

默认监听为 `0.0.0.0:8000`，是监听设置，不是可公开访问的安全承诺。本地接口没有统一版本路径；状态数据额外包含 `apiVersion="1.1"`、`robotId`、`bridgeInstanceId`。平台路径使用 `/api/platform/v1`，不能把两个版本值混用。

| 范围 | 当前鉴权 | 注意事项 |
| --- | --- | --- |
| 普通 `/api/` | `require_token=true` 时接受 `X-API-Token` 或 Bearer | YAML 默认 false，不代表部署安全 |
| `/ws/status`、`/ws/map` | 启用鉴权时通过 `?token=` | 错误令牌关闭码 1008，查询串需从日志脱敏 |
| `/api/platform/v1/*` | 始终要求平台 Bearer，空平台令牌拒绝 | 外层普通鉴权开启后也要满足外层检查 |

平台令牌来源优先为 `YLHB_PLATFORM_API_TOKEN`，其次为同名用途参数。若本地与平台令牌不同，平台 Bearer 配合本地 `X-API-Token`，不能只提供其中之一。关闭本地 APP 还有独立的路由门控，不能仅凭令牌判断可达性。

## 二、本地响应

~~~json
{"ok":true,"message":"status","data":{},"error":null,"timestamp":0.0}
~~~

`timestamp` 为服务器生成的 Unix 秒数。普通错误有两类：捕获后返回 `ok=false` 的业务失败，可能仍为 HTTP 200；显式异常处理产生的 401、404、422 和地图操作错误等。客户端必须同时检查 HTTP 状态和 `ok`，不能只检查 200。

请求校验错误为 422，`error=validation_error`，错误详情在 `data.detail`。常见业务错误有 `invalid_request`、`process_error`、`no_map`、`supervisor_unavailable` 和 `ros_unavailable`。展示消息不是稳定的机器判定字段。

## 三、本地 HTTP 路由清单

“状态读取”仍可能读取缓存或文件，不代表数据一定新鲜；所有控制入口均禁止由 Agent 为验收直接调用。

| 方法与路径 | 输入 | 语义与风险 |
| --- | --- | --- |
| GET `/api/status` | 无 | 状态读取，附版本及实例标识 |
| POST `/api/cmd_vel` | 速度请求 | 运动控制，高风险 |
| POST `/api/text_command` | `text` | 进入任务解释链，可能有控制副作用 |
| POST `/api/task` | 任务请求 | 转文本发布，不表示任务完成 |
| POST `/api/stop` | 无 | 调用停止链；不是物理急停保证 |
| GET `/api/debug/status` | 无 | 调试状态 |
| POST `/api/debug/chassis/test` | 底盘测试请求 | 会影响运动，禁止自动测试 |
| POST `/api/debug/chassis/stop` | 无 | 停止底盘测试 |
| GET `/api/debug/mapping/status` | 无 | 建图状态 |
| GET `/api/debug/maps` | 无 | 地图列表 |
| GET `/api/debug/maps/{map_name}/preview` | `max_size_px=1024`，1～4096 | 文件地图预览 |
| POST `/api/debug/maps/{map_name}/confirm_default` | 无 | 替换默认地图并尝试创建上传任务 |
| POST `/api/debug/maps/{map_name}/rename` | `new_name` | 改名，有文件副作用 |
| DELETE `/api/debug/maps/{map_name}` | 无 | 删除，有文件副作用 |
| GET `/api/debug/mapping/map_snapshot` | `downsample=1`，1～16 | 当前地图快照，无地图返回业务错误 |
| POST `/api/debug/mapping/start` | 无 | 启动建图进程，有运行副作用 |
| POST `/api/debug/mapping/save` | `map_name` | 保存当前 SLAM 地图，无当前图拒绝 |
| POST `/api/debug/mapping/stop` | 无 | 停止建图并重置桥接地图缓存 |
| GET `/api/debug/navigation/status` | 无 | 导航状态 |
| POST `/api/debug/navigation/start` | 无 | 导航启动，高风险 |
| GET `/api/debug/system/status` | 无 | 系统与进程状态 |
| POST `/api/debug/system/start/{mode}` | mode 为 bringup 或 mapping | 发送系统启动命令 |
| POST `/api/debug/system/stop/{mode}` | 同上 | 发送系统停止命令 |
| GET `/api/debug/patrol/status` | 无 | 巡逻状态及执行器可用性 |
| POST `/api/debug/patrol/start` | 无 | 发送 start，可能实际运动 |
| POST `/api/debug/patrol/pause` | 无 | 发送 pause，需等待反馈 |
| POST `/api/debug/patrol/resume` | 无 | 发送 resume，可能实际运动 |
| POST `/api/debug/patrol/cancel` | 无 | 发送 cancel，需等待反馈 |
| POST `/api/debug/patrol/reload` | 无 | 发送 reload，有执行状态副作用 |
| POST `/api/debug/patrol/initialize` | 无 | 发送 initialize，不作为只读检查 |
| POST `/api/debug/navigation/set_initial_pose` | x、y、yaw | 发布初始位姿，改变定位状态 |
| POST `/api/debug/navigation/goal` | x、y、yaw、可选 label | 返回 `data.accepted`，不表示到达 |
| POST `/api/debug/navigation/cancel` | 无 | 返回取消请求结果，不表示车辆已停稳 |

确认默认地图后即使上传任务创建失败，也可能已经应用地图。客户端分别检查 `default_applied` 与 `upload.task_created`，不得把上传失败解释成地图未变。

## 四、请求字段

| 请求 | 字段和当前约束 |
| --- | --- |
| 速度 | `linear_x`、`angular_z` 默认 0；`duration_ms` 默认 300，50～3000 |
| 底盘测试 | 继承速度字段，另要求字符串 `mode` |
| 文本 | 必填字符串 `text` |
| 任务 | 可选 `command/text/task_id/route_id/checkpoint_id`，`metadata` 默认独立空字典 |
| 保存地图 | `map_name` 默认 my_map，仅字母、数字、下划线、连字符 |
| 改名 | `new_name` 必填，同上字符约束 |
| 位姿 | `x/y/yaw` 必填浮点数，位置按地图坐标米、角度弧度约定 |
| 导航目标 | 同位姿，另有可选 `label`；当前发送调用只传 x、y、yaw |

速度字段的业务限制来自 ROS 桥接层，不能把请求模型未声明幅度范围解释成不限速。YAML 当前上限为线速度 0.30、角速度 0.55，本轮未改也未现场验证。任务对象当前优先使用非空 text，其次把 command 转为文本，其他字段不自动变成结构化导航指令。

## 五、WebSocket 与地图数据

| 路径 | 默认节奏 | 消息 |
| --- | --- | --- |
| `/ws/status` | 配置 2 Hz | 普通响应包裹的状态 |
| `/ws/map` | 配置 1 Hz | 普通响应包裹的快照或 no_map |

这是服务端目标推送节奏，不是实测频率。`/ws/map` 的 downsample 查询参数限制到 1～16，无法解析时回到 1。客户端需处理断线、无地图和重新连接，不能无限沿用旧数据。

快照数据包含 `map_meta` 和 `png_base64`。元数据包括 frame_id、时间戳、原始分辨率、宽高、原点位置及四元数；PNG 为 RGB 编码显示图。缩小只影响 PNG，不修改元数据。灰度语义及纵向翻转见 [集成说明](INTEGRATION.md)。

## 六、平台 v1

平台成功响应不是普通 ApiResponse。平台存储错误格式为 `{code,message,requestId,details?}`；未知 HTTP 路由等仍可能经过外层 HTTP 异常处理，不能假定所有错误同构。

| 方法与路径 | 必要输入 | 返回或约束 |
| --- | --- | --- |
| GET `/api/platform/v1/health` | 平台令牌 | robotId、bootId、state、mapPose、odomPose、online |
| PUT `/api/platform/v1/deployments/{deployment_id}` | multipart 文件 manifest、route、yaml、pgm | 安装地图和路线，manifest.robotId 必须匹配 |
| POST `/api/platform/v1/executions/{execution_id}/start` | JSON deploymentId、executorRouteId、requestId | 202，accepted 和 STARTING；任务尚未完成 |
| POST `/api/platform/v1/executions/{execution_id}/{action}` | requestId，可选 commandId | action 仅 pause/resume/takeover/cancel，返回 PENDING_ROS |
| GET `/api/platform/v1/executions/{execution_id}` | 执行标识 | 执行、部署、请求、机器人、启动标识、状态及位姿 |
| GET `/api/platform/v1/events` | afterSequence 默认 0，limit 默认 100 | events 列表，处理方按序列游标追踪 |

启动还支持 taskId、commandId、profile，当前 profile 默认 inspection。部署不存在、执行不存在、权限拒绝等分别核对 HTTP 状态和错误码。部署内容与哈希、路线字段及持久化幂等细节以 `platform_store.py` 和既有 [协议目录](protocol/) 为准，不凭 requestId 推断所有动作天然幂等。

同时配置 `YLHB_CLOUD_BASE_URL` 和 `YLHB_CLOUD_ROBOT_TOKEN` 后，入站部署、启动、控制默认拒绝，返回 `INBOUND_CONTROL_DISABLED`（409）。只有显式开启 `YLHB_ALLOW_INBOUND_PLATFORM_CONTROL` 才允许进入后续流程。不得为测试临时绕过这一边界。

## 七、ROS 边界

| 默认接口 | 类型 | 方向及约束 |
| --- | --- | --- |
| `/cmd_vel_manual` | geometry_msgs/Twist | 桥接发布，运动高风险 |
| `/dg/control/manual_authorized` | std_msgs/Bool | 桥接发布，控制授权有副作用 |
| `/inspection_ai/text_command` | std_msgs/String | 发布任务文本，可能触发控制 |
| `/inspection_ai/system_command` | std_msgs/String | 发布系统命令 |
| `/patrol/command` | std_msgs/String | 发布巡逻命令 |
| `/initialpose` | geometry_msgs/PoseWithCovarianceStamped | 改变定位状态 |
| `/odom`、`/scan`、`/map` | Odometry、LaserScan、OccupancyGrid | 桥接订阅；scan 使用传感器 QoS，map 使用专用 QoS |
| `/imu/data`、`/gps/fix` | Imu、NavSatFix | 传感器 QoS |
| `/gps/rtk_status` | diagnostic_msgs/DiagnosticArray | 质量状态，结合新鲜度 |
| `/amcl_pose` | PoseWithCovarianceStamped | 定位订阅 |
| `/patrol/status`、`/patrol/event` | std_msgs/String | 状态和事件订阅 |
| `navigate_to_pose` | nav2_msgs/action/NavigateToPose | 桥接为 Action 客户端，目标发送高风险 |

地图及状态 QoS 具体以 ros_bridge 引用的实现为准，不能把所有 String 话题统一当普通易失消息。完整来源和更多接口参见 [通信矩阵](architecture/05-通信接口矩阵.md)。

## 八、兼容性检查

上线前逐项核对路由、字段、默认值、鉴权叠加、业务错误及异步状态。现有 schemas 使用 Pydantic 的 regex 参数，在本机 Pydantic 2.13.4 上已复现模型导入失败；重构前 Git 源码也有同样错误。本轮不扩大范围迁移依赖，见 [变更说明](CHANGELOG_20261015.md)，不能用纯数据测试代替接口验证。
