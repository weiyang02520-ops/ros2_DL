# VISION_INTEGRATION_PLAN：独立操作视觉详细实施规格

版本：V4，2026-10-14。状态：设计规格；尚未实现检测、深度定位或跟踪。

## 0. 当前授权与结论

本轮允许：修订本计划，并按用户最新授权将检查后的仓库上传 GitHub。上传不等于授权启动 Cursor 云端任务、V0、相机、推理、V1～V3 开发或机器人。上传默认使用独立私有仓库，不覆盖原 origin，不上传模型、凭据、运行产物或未经检查的历史。

视觉始终独立，不绑定机械臂。不修改 MODEL-1/2/3、Nav2/AMCL/SLAM、EKF/TF 所有权、cmd_vel、底盘、手机控制、旧感知模块、生产启动脚本、服务或全局设置。

可行性结论：CONDITIONALLY_FEASIBLE_BY_SOURCE_REVIEW。
- V0：结构与参数可以离线检查；Linux 构建和惰性节点运行尚未验证。
- V1：桌面瓶子/杯子二维检测有明确实施路线，模型、环境和真实数据仍需验证。
- V2：仅对取得可靠深度的可见表面提供三维位置，不承诺透明物体定位。
- V3：仅做单相机短期身份关联，不做跨相机/跨重启重识别。
- ARM_READY=NO。观测位置不是抓取位姿，不提供抓取方向、夹爪姿态、可达性、碰撞检查或运动授权。
- 此文的数值为初版工程默认值和内部验收目标，不是实测结果，也不是比赛指标。正式验收前将本版本、参数和数据集哈希写入验收协议；验收中不得为追求通过而改阈值。

用户已确认：桌面静止或慢动场景；第一版不要求透明瓶子/玻璃杯的可靠三维位置。其余默认边界由本规格确定：固定相机、室内光照、工作距离 0.5～1.5 m、目标速度不超过约 0.05 m/s、最多 20 个当前目标。超出边界的结果单独报告，不并入首版达标结论。系统没有材质分类能力，不能承诺自动识别并拒绝所有透明目标的背景深度。

## 1. 仓库真实边界

主仓库：dg202611_robot_integration。ROS 包在 src/ 下，由 colcon 发现；navigation/fusion/recovery 主要是 ylhb_base 内模块，不是仓库根目录下三个独立包。

| 既有组件 | 已核查内容 | 本模块处理方式 |
|---|---|---|
| ylhb_base | 三模型、硬件、导航、控制 | 不修改、不作为依赖、不启动 |
| ylhb_perception | 旧 TensorRT/CUDA 检测与 JSON 目标定位 | 保留原样，不复用其运行节点或强制构建依赖 |
| ylhb_interfaces | 任务/语音公共消息 | 不添加视觉消息，避免公共接口变更 |
| ZED wrapper | RGB、深度、CameraInfo、TF | 未来只订阅已有驱动，不打开 SDK、不改变其配置 |
| dg_hvs_bridge | RDK 事件相机 | 与本模块无运行依赖 |
| dg_synthetic_validation | 合成验证工具 | 仅参考打包和证据风格，不复用导航场景冒充视觉测试 |

已存在的两个新包：
- src/vision_perception：ament_python；setup.py/setup.cfg、resource、节点壳、launch、config。
- src/vision_perception_interfaces：ament_cmake/ROSIDL；当前只有 VisionObject、VisionObjectArray 两个草稿消息。

已检查包名无冲突、相关目录无忽略标记；未执行 colcon discovery、编译、消息生成或 ROS 启动。当前脚手架只创建 DiagnosticArray 状态发布者，没有图像订阅和目标输出。根目录 docs/evidence 不随 Python 包安装，发布包必须另外携带本计划和证据政策。

## 2. 已确定的处理路线与内部模块

~~~text
现有 ZED：RGB ──> 图像解码/预处理 ──> YOLO 框与目标轮廓
                          |                  |
                     来源/时序检查       2D 身份关联（仅 V3）
                          |                  |
注册深度 + CameraInfo ──> 配对/标定检查 ──> 轮廓内深度资格检查
                                             |
                               按观测编号和检测序号组合
                                             |
                          /dg/vision/objects + 诊断/证据
~~~

跟踪作用于二维检测，不因深度无效而必然中断。三维点不是跟踪的必需输入。V1 不运行跟踪或深度处理；V2 不运行跟踪；V3 将二维轨迹与当前帧的深度资格结果组合。不得把预测框或历史三维点重新标记成当前测量。

未来代码按以下职责划分，纯算法层不导入 rclpy：
- 数据类型/配置：不可变 FrameKey、Detection、DepthResult、Track、配置校验。
- 图像与模型：像素解码、letterbox、ONNX 后端、框/轮廓解码。
- 深度：输入契约、配对器、CameraInfo、深度选点和投影。
- 跟踪：同类别 IoU 关联和时间生命周期。
- 组合与映射：按 FrameKey/detection_index 合并，构造 ROS 消息。
- ROS 节点：订阅、单个工作线程、状态、发布；不包含机械臂或控制逻辑。
- 离线入口与评价器：文件/保留数据集输入、CSV/JSON、独立评价。

一个节点、一个推理工作线程；最多一个待处理任务。处理繁忙时用最新待处理帧替换旧待处理帧，记录丢弃数，不排长队。采集回调不执行推理。

## 3. 公共接口：当前草稿与未来定稿分开

### 3.1 V0 保持当前接口与代码不变

V0 只生成当前两个消息并启动原惰性节点。不得在 V0 顺手增加下述字段或消息。当前消息定义可编译与否需实际验证，不能由本文替代。

### 3.2 V1 开始前的接口定稿步骤

在另行授权 V1 实现后，先更新新建的接口包并重新验证构建，再写业务处理。此处给出唯一拟定规格，不沿用靠数组下标的跨话题关联。

拟新增 VisionDetection2D 和 VisionDetectionArray；拟扩展既有 VisionObject、VisionObjectArray。新模块尚未发布真实目标，也未找到仓库内消费者；变更前仍需再查消费者。若发现消费者，暂停接口替换并报告，不静默破坏兼容性。

| 话题 | 拟定消息类型 | 首次启用 |
|---|---|---|
| /dg/vision/status | diagnostic_msgs/DiagnosticArray | 当前壳/V0 |
| /dg/vision/detections_2d | vision_perception_interfaces/VisionDetectionArray | V1 |
| /dg/vision/objects | vision_perception_interfaces/VisionObjectArray | V2 |
| /dg/vision/debug_image | sensor_msgs/Image，默认关闭 | V1 后显式调试 |

二维消息包含标准 vision_msgs/BoundingBox2D，而不是 Detection2D.results 中的 ObjectHypothesisWithPose。这样二维结果不携带未估计的六维位姿和零协方差。与上一草稿直接使用 Detection2DArray 的建议相比，这是有意的、尚未实施的接口修订。标准兼容转发器不在首版范围内。

共同观测键：
- source_session_id：节点建立输入会话时生成 UUID；重启、相机重置、时钟回退、标定改变后重新生成。
- observation_id：该会话内从 1 单调增加的 uint64；按接受的源帧分配，丢弃的序号不回收。
- detection_index：同一观测内从 0 连续编号；二维与三维结果显式携带它，不依赖数组顺序。
- header：原始 RGB stamp/frame，保持不变。批次和单目标若同时保留 header，其值必须一致。
- calibration_id：CameraInfo 的 frame、尺寸、K/D/R/P、ROI/binning 规范化后 SHA256；V1 无标定时为空，V2/V3 必须有值。
- source_kind：LIVE_CAMERA / RECORDED_CAMERA；普通离线图片只输出文件评价结果，不伪装成 ROS 实机观测。

拟定 VisionDetection2D：
~~~text
uint32 detection_index
string class_name
float32 confidence
vision_msgs/BoundingBox2D bbox
~~~

VisionDetectionArray：
~~~text
std_msgs/Header header
string source_session_id
uint64 observation_id
string calibration_id
string source_kind
VisionDetection2D[] detections
~~~

VisionObject 在当前字段上明确扩展以下内容：
~~~text
std_msgs/Header header
uint32 detection_index
string object_id
string class_name
float32 confidence
vision_msgs/BoundingBox2D bbox
geometry_msgs/Point position
bool position_valid
string position_reference
string invalid_reason
float64 reference_u
float64 reference_v
float32 valid_depth_fraction
geometry_msgs/Quaternion orientation
bool orientation_valid
bool tracking_valid
~~~

VisionObjectArray 包含共同观测键的全部批次字段，另加 tracking_session_id 和 VisionObject[] objects。orientation_valid 在 V1～V3 恒为 false；未来测量朝向是独立任务。

固定语义：
- class_name 只允许 bottle、cup；confidence 是类别分数，不是位置精度。
- position 单位为米，位于该 RGB/CameraInfo 的真实光学坐标系。
- position_reference 恒为 visible_surface_sample，不用它编码失败原因。
- invalid_reason 取 OK、DEPTH_UNPAIRED、MASK_TOO_SMALL、DEPTH_INSUFFICIENT、DEPTH_DISCONTINUITY、INPUT_INVALID、STALE。
- 无效位置存储 NaN，position_valid=false；未知朝向四个分量为 NaN，orientation_valid=false。ROS 浮点可以传递，JSON/CSV 导出时未知数值转 null/空值并保留标志，禁止把它显示为原点或单位朝向。
- V2 无跟踪：object_id、tracking_session_id 为空，tracking_valid=false。
- V3 只有已确认且本帧匹配的轨迹才有 object_id 和 tracking_valid=true；ID 只在 tracking_session_id 内有效。
- V2/V3 每个保留二维检测对应一个对象条目，包括无效深度。不能悄悄删去失败目标提高有效率。
- 数组最多 20 项；不是硬实时内存保证。原始 .msg 是否采用有界数组在首版保持不变，由应用限制长度。

所有接口都是观测，不是机械臂目标。即使未来变换到 arm_base，也仍缺抓取点、朝向和碰撞信息；position_valid=true 不构成运动授权。

## 4. ZED 输入契约与证据等级

默认名字有本地源码依据，但尚未验证当前设备：

| 项目 | 本地依据 | 待实机确认 |
|---|---|---|
| RGB | ylhb_perception 的 perception.launch.py、detector.yaml；ZED 的 publishRgbImages | 实际解析名、编码、尺寸、QoS、频率 |
| 深度 | ZED retrieveDepthMap、publishDepthMapWithInfo | 真实编码/单位、无效值、光学 Z 而非欧氏距离 |
| CameraInfo | 同组件共享左相机信息并填充 K/P/尺寸/frame | 当前标定、P、R、ROI/binning、与图像对应 |
| frame | setTFCoordFrameNames 使用 camera_name + _left_camera_frame_optical | 实际 header，不硬编码或改名 |
| 时间戳 | debug.use_pub_timestamps 可改变 stamp 来源 | 实际参数、SDK/ROS 时钟、回放方式 |
| 配准 | RGB 使用左图，深度/信息使用左光学 frame | 前景边缘在多个距离下是否真正逐像素对齐 |

默认输入：
- /zed/zed_node/rgb/color/rect/image，sensor_msgs/Image。
- /zed/zed_node/depth/depth_registered，sensor_msgs/Image。
- /zed/zed_node/rgb/color/rect/camera_info，sensor_msgs/CameraInfo。

源码位置前缀：
- ZED_WRAPPER = src/zed-ros2-wrapper/zed_wrapper。
- ZED_STEREO = src/zed-ros2-wrapper/zed_components/src/zed_camera。
- 话题构造：ZED_WRAPPER/launch/zed_camera.launch.py，ZED_STEREO/src/zed_camera_component_video_depth.cpp。
- frame：ZED_STEREO/src/zed_camera_component_main.cpp。
- 编码：zed_components/src/tools/src/sl_tools.cpp。
- 默认单位/时间戳：ZED_WRAPPER/config/common_stereo.yaml。

证据等级严格区分：SOURCE_SUPPORTED、DEPLOYED_VERSION_VERIFIED、INPUT_MEASURED、METRIC_VALIDATED。默认话题、相同 frame 字符串、同尺寸、相近时间戳均不单独证明配准正确。

编码约定：
- 彩色支持 rgb8、bgr8、rgba8、bgra8，明确转成模型 RGB。名字含 rgb 不代表 encoding=rgb8。
- 深度接受 32FC1 米；本地 OpenNI 分支实际为 mono16 毫米。16UC1 只有在生产者契约确认毫米后才接受。
- 尊重 step、endianness；零、NaN、Inf、超量程和生产者特殊无效码都不作为有效深度。
- 首版只支持已配准的左目校正图；P[3]、P[7] 非零或 R/ROI/binning 不在确认契约内时拒绝，不猜测换算。
- 光学轴：x 向右、y 向下、z 向前。输出不冒充 map/base_link，也不发布 TF。
- 新模块不启动相机、不重写 SDK 参数、不争夺相机所有权。新增深度订阅可能增加 GPU 负担，未来采集前需记录基线资源。

时间与来源：
- live 需要已确认采集时间基础；若只知发布时间，允许记录二维诊断，但不通过 live 新鲜度/同步验收，V2 无有效位置输出。
- header 不改成推理完成时间。源时间回退、重复或零时间戳进入输入异常；不可用回调到达时间冒充拍摄时间。
- 普通 JPEG/PNG 使用 source_image_id；没有采集时间和 frame 就不生成“实机 ROS header”，文件 mtime 不作为采集时间。
- RECORDED_CAMERA 使用原记录时间与匹配回放时钟，显式标记来源。源时间新鲜度和本机单调时间接收年龄分别检查；回放暂停不能让旧目标永久“新鲜”。
- CameraInfo 缓存标定内容，不强求静态 info stamp 与每帧相等。frame/尺寸/标定改变时清理配对和轨迹，停止有效 3D，重新确认契约后开始新会话。

## 5. 默认参数与配置规则

下表是未来 V1～V3 的实现默认值，当前 V0 配置不修改。

| 参数 | 默认 | 语义 |
|---|---:|---|
| inference_rate_hz | 5.0 | 上限，不保证达到 |
| pending_frames | 1 | 忙时保留最新任务 |
| ort_threads | 2 | 禁止默认占满 CPU |
| model_input_size | 640×640 | batch=1、FP32 |
| confidence_threshold | 0.35 | 单标签类别分数 |
| nms_iou_threshold | 0.45 | 按类别 NMS |
| max_detections | 20 | 目标输出上限 |
| mask_threshold | 0.5 | 目标轮廓二值化 |
| sync_tolerance_sec | 0.010 | 非精确戳配对的最大差 |
| sync_wait_sec | 0.100 | 等待深度的上限 |
| sync_queue_size | 10 | 各输入有限缓存 |
| max_observation_age_sec | 0.500 | 源时间及接收年龄检查 |
| input_stale_sec | 1.0 | 无新输入进入 STALE |
| min_depth_m / max_depth_m | 0.5 / 1.5 | 首版工作距离 |
| mask_erode_kernel | 3×3，1 次 | 缩小边界污染 |
| depth_patch_size | 7×7 | 候选像素附近 |
| min_patch_pixels | 25 | 轮廓内最少采样数 |
| min_valid_depth_fraction | 0.60 | 对轮廓内采样计分 |
| max_depth_mad_m | 0.020 | 局部深度稳定性门槛 |
| max_depth_spread_m | 0.050 | P90-P10 上限 |
| tracker_match_iou | 0.30 | 同类别关联下限 |
| tracker_confirm_hits | 3 | 连续观测确认轨迹 |
| tracker_lost_timeout_sec | 0.70 | 最后一次测量后的保留时间 |
| publish_debug_image | false | 不默认渲染/发布 |
| status_rate_hz | 1.0 | 独立健康状态 |

所有影响模型、输入、坐标或发布路径的参数只在启动时读取，未来实现应标记只读；不提供运行时热切换模式。此要求尚未写入当前节点壳。配置不合法则启动失败，不静默修正或自动换后端。

## 6. V1 实现规格：二维检测

### 6.1 模型与依赖

选用 YOLO11n-seg 的 COCO 预训练权重，原因是 V2 需要目标轮廓；V1 只输出框，不发布轮廓或三维点。类别映射固定以模型 manifest 核对，标准 COCO 为 bottle=39、cup=41。不能根据文件名或旧工程 class_names 猜测。

基准导出路线：Ultralytics 8.3.0，PyTorch 2.4.1、torchvision 0.19.1、ONNX 1.16.2；Python 3.10 的独立导出环境。导出设置：FP32、640、batch=1、dynamic=false、simplify=false、opset=17，不把后处理 NMS 嵌入 ONNX。导出和模型获取都在未来单独获准后执行，不触碰系统环境。

部署基准：ONNX Runtime CPU 1.20.1、NumPy 1.26.4、OpenCV headless 4.10.0.84；V3 再加 SciPy 1.11.4。Linux ROS 使用与 Humble 相符的 Python 3.10 隔离环境，核对生成脚本解释器及 rclpy 导入路径；不升级全局 Python/NumPy。图像按 Image 数据和 NumPy 解码，首版不引入 cv_bridge 的二进制版本耦合。缺 wheel/ABI 不兼容时报告环境阻塞，不自动升级 CUDA/JetPack。

推理进程不导入 Ultralytics/PyTorch，不调用自动下载；只读显式提供的本地 ONNX 和 model_manifest.json。manifest 必填来源、权重/ONNX SHA256、许可、导出工具版本、输入输出布局及类别表。上游模型许可与仓库自身许可分开保留；许可条件未确认时停止模型导入，不擅自购买许可或把权重公开打包。

TensorRT 不进入首版实现。只有 CPU 参考结果正确、实际 Jetson 未满足资源/时延门槛时，才另开优化任务：同一 ONNX、目标 JetPack/TensorRT 原地编译独立 engine，并比较输出。Windows engine 不假定可在 Jetson 运行；禁止 CPU/GPU 静默回退。

### 6.2 预处理与后处理

1. 按 encoding 解码，转 RGB；验证尺寸、step、数据长度。
2. 保持比例缩放至 640×640，双线性插值、居中 padding=114；记录真实 scale 与四边 padding。
3. 转 CHW、FP32、除以 255、batch=1。不得重复交换颜色或归一化。
4. ONNX 输入名 images，预期两个输出：output0=[1,116,8400]、output1=[1,32,160,160]。前者是 4 个 xywh、80 类分数和 32 个轮廓系数，后者是轮廓原型。实际导出必须验证；布局不符就停止，不自动猜维度。
5. 单框取最大类分数，保留 bottle/cup 且 score≥0.35 的项。分数已是概率形式，不再次 sigmoid。
6. 按类别做 IoU=0.45 的 NMS；移除退化框、恢复到原图坐标并裁到图像边界。
7. 保留最多 20 项；按 score 降序、class_name、原图 x/y/宽/高确定性排序，再分配 detection_index。
8. V1 发布 VisionDetectionArray；不发布 /objects，不启动深度配对和跟踪。空结果仅代表一次真实处理帧没有合格目标。

V2 所需轮廓按同一候选的系数与原型重建，sigmoid 后逆 letterbox、裁回 bbox，并阈值化。实现时使用固定版本上游结果作黄金参考；本计划不复制或重新许可其源码。

## 7. V2 实现规格：表面选点与三维位置

### 7.1 RGB/深度配对

RGB 为主序列。先找完全相同采集 stamp；否则在有效契约下选择尚未使用、差值≤10 ms 的最近深度。平局取较早深度，每份深度只配一份 RGB。

RGB 等待最多 100 ms，队列最多 10；超时仍可做二维检测，但对应 /objects 条目为 DEPTH_UNPAIRED。队列溢出丢最旧未配对项并记数。超过新鲜度、未知时钟、错误 frame/尺寸/标定为全局输入错误，不输出有效三维点。

推理前固定该观测的 RGB、depth、CameraInfo 快照；推理结束后再次检查年龄。不得将推理期间到达的“最新深度”拼到旧框上。旧稿 50 ms 参数只属于现有惰性壳的保留值，不用于 V2。

### 7.2 目标轮廓内选点

对每个目标：
1. 重建原图轮廓，做一次 3×3 腐蚀，边界不跨出 bbox。
2. 腐蚀后总像素不足 25，返回 MASK_TOO_SMALL。
3. 在轮廓内有效深度像素中，选择距离 bbox 中心最近的像素；同距按行、列排序，记为 reference_u/v。无可选像素则 DEPTH_INSUFFICIENT。
4. 取该像素附近 7×7 与腐蚀轮廓的交集；交集不足 25，或有限且在范围内的深度比例低于 0.60，返回 DEPTH_INSUFFICIENT。
5. 在有效样本上计算 median、MAD、P90-P10。MAD>20 mm 或 spread>50 mm，返回 DEPTH_DISCONTINUITY。
6. 以该局部 median 估计选中像素的光学 Z。按确认的校正左相机 P 计算 X=(u-cx)Z/fx、Y=(v-cy)Z/fy、Z=depth。
7. xyz 有限且满足范围后 position_valid=true、invalid_reason=OK；否则保留条目并返回失败原因。

这里估计的是选中可见表面的局部点，不是物体中心，也不是抓取点。轮廓仍可能错误，深度仍可能看穿透明表面；有效标志不等于绝对正确。评价必须把错误背景选点计为失败。不得把透明目标从报告中隐藏，但透明目标不计入不透明首版的达标承诺。

每个当前二维目标都发布对象条目。正常无目标帧发布空数组；相机断流/未知输入只发布不可用诊断，不把它伪装为成功的空场景。

## 8. V3 实现规格：短时二维身份关联

首版采用同类别 IoU 与匈牙利分配，不引入外观重识别网络、额外模型或未经测量的三维运动预测。

- 输入为当前真实二维检测，深度有效与否不影响关联。
- 每类独立匹配，IoU≥0.30 才允许关联，代价为 1-IoU；不可配对代价设为大值，使用虚拟新建/失踪项，禁止强行匹配。
- 轨迹按内部 ID、检测按 detection_index 排序后分配，保证给定输入和版本下结果可复现。
- 新检测建立 tentative 轨迹，连续 3 次真实匹配后 confirmed。未确认时不发布稳定 object_id。
- confirmed 轨迹失踪后保留 0.70 s 的关联状态，本帧不发布其历史位置或预测观测；超时删除。未确认轨迹首次漏检即删除。
- 短时失踪后只有满足同类/IoU 门槛才沿用 ID；完整遮挡后不承诺重识别，无法关联就分配新 ID。
- 新会话/时钟回退/相机或标定改变清空所有轨迹，生成新的 tracking_session_id。已过期 ID 不复用。
- tracking_valid 表示本帧真实检测匹配到 confirmed 轨迹；与 position_valid 分开。
- 人为排列两个相同杯子交叉的试验可能发生 ID 切换，必须统计，不能宣称身份永久正确。

## 9. 时序、状态和运行行为

未来实现状态：SKELETON_ONLY、STARTING、READY、DEGRADED、STALE、ERROR。当前壳只实现 SKELETON_ONLY。

- 模型缺失/哈希或类别表错误/输出布局错误：启动 ERROR、非零退出，不自动下载或切换模型。
- 当前输入无效：记录原因，必要时保持二维输出，但 suppress 有效 3D；每目标失败不要求进程退出。
- 最后新输入超过 1 s：STALE；清理过期待处理帧和轨迹，不反复发布旧 objects。
- 输出前分别检查源时钟年龄及单调时钟接收年龄≤0.5 s。未知源时钟不能据此宣称采集时延。
- 参数只读、话题输出白名单明确；status 只能 /dg/vision/status、DiagnosticArray。不得通过 remap 在 /objects 发布诊断。
- Debug 图默认关闭；启用时最多 2 Hz，不默认打开 GUI，不强依赖 RViz。
- 正常关闭停止接受帧、清空待处理任务、等待工作线程退出并销毁节点；只清理自己创建的进程。
- 不存在机械臂选择、动作服务、导航目标或速度命令的分支。

状态中记录 mode、source_kind、source_session_id、实际 backend/provider、已处理/丢弃/无效计数、最后输入和输出时间、推理时长、配对偏差、标定 ID。显示当前有效参数，不把未启用功能写成 READY。

## 10. 评价数据、公式与初版门槛

这些是内部初版默认验收目标，不是用户已实测的能力或官方比赛要求。数据标注、配置和本规格必须在运行前保存哈希。若不接受这些默认门槛，应在试验开始前修订；不得验收后放宽。

### 10.1 V1

独立测试集至少 300 张：瓶子/杯子各至少 100 个标注实例，至少 100 张无目标图；每类至少 3 个实物，覆盖混合、多目标、局部遮挡和不同背景。相邻视频帧不能冒充独立场景；开发集与验收集按场景分离。

同类别 bbox IoU≥0.5 做一对一最大匹配，固定 score=0.35：
- precision=TP/(TP+FP)，recall=TP/(TP+FN)，分别按类计算。
- 默认目标：两类各 precision≥0.90、recall≥0.85。
- 背景误报计 FP；不能把背景帧数直接加到 precision 分母。
- 分母为零时指标标记不可计算，不能记为 100%。

文件实验输出 source_image_id，不生成虚假传感器时间。离线通过不等于 ROS 实机通过。

### 10.2 V2

试验覆盖 0.5/1.0/1.5 m 和图像左/中/右区域，每格至少 20 个独立观测，不用相邻静止帧伪造样本独立性。记录不透明测试群和透明挑战群。

默认内部目标：
- 在匹配、有效且有独立真值的点上，三维欧氏误差 median≤30 mm、P95≤50 mm。
- 不透明测试群的端到端有效位置覆盖率≥0.80。
- 无效深度/错误标定/过期样本不得产生 position_valid=true；错误前景取点计失败。

必须区分：
- depth_coverage：有效三维的正确二维匹配项 / 全部正确二维匹配项。
- end_to_end_coverage：有效三维的正确二维匹配项 / 全部标注目标实例。
- position_error：有独立同点真值的有效匹配项误差；同时报告样本数和无效/漏检比例。
- accuracy_success_rate：正确匹配且误差≤50 mm 的项 / 全部标注目标实例。缺真值时不能计算。

真值必须针对同一个 reference_u/v 对应的表面点，位于同一光学坐标系，测量不确定度≤10 mm。由独立测量的刚性夹具/外部测量记录提供已知表面几何及坐标变换；评价器读取已配准真值，不使用 ZED 深度、AMCL 或融合输出当自身真值。真值记录需包含方法、仪器、精度、基准和像素关联。

测量夹具和外部真值尚未具备。没有合格真值时可以报告投影功能与有效率，V2_ACCURACY=BLOCKED，不能改用物体中心坐标去比较本模块的表面选点。纯平面或合成点仅验证深度/投影子功能，不能替代瓶子杯子的端到端精度。

### 10.3 V3

至少 6 段身份标注视频：3 段连续多目标、3 段同类交叉/局部遮挡；另测消失、帧丢失、重启和时钟回退。
- 对当前二维观测按 IoU≥0.5 匹配标注身份。
- 默认 IDF1≥0.85；报告 ID switches、fragmentation 和确认前未跟踪帧，不能删掉前 2 帧提高分数。
- 同时出现的目标不得共享同一 object_id。
- 消失目标不再输出测量；超时、重启后的旧 ID 不得恢复使用。
- 3D 无效但 2D 连续可见时，不应仅因深度无效更换已确认 ID。
- 完全遮挡重识别不纳入通过承诺，但失败记录保留。

### 10.4 ROS/Jetson 性能

默认限速 5 Hz；实机内部最低吞吐 2 Hz，处理延迟 P95≤400 ms，超 500 ms 旧观测不得发布。单进程峰值 RSS 初版预算 1 GiB；记录实际 CPU/GPU/RAM/温度。与同配置无新模块基线相比，原传感器话题频率不得持续下降超过 10%。不满足时本轮性能 FAIL，另开优化任务，不修改原导航参数或伪报实时。

必须记录设备、模式、分辨率、时钟、模型/配置和热状态。Windows/VM 的 FPS 不能替代 Jetson 测量。

## 11. 证据与失败保存

目录：evidence/vision/<date>_<stage>_<run>/，禁止覆盖历史。stage 使用 V0_SHELL、V1_OFFLINE、V1_ROS、V2_POSITION、V3_TRACKING。

最低公共文件：
- metadata.json：实际环境、source_kind、source/session、代码提交及 dirty/未跟踪源码快照、阶段、PASS/FAIL/BLOCKED/NOT_RUN。
- parameters.yaml、source_hash.txt、manifest.sha256。
- acceptance_protocol.yaml：运行前冻结的数据集/标注/阈值/统计公式。
- logs/；原始 inputs/或 rosbag/按实际来源保留，不只保存截图。

V0 的 source_kind=NONE_NOT_APPLICABLE，不写 REAL_CAMERA 或相机测试通过。
V1 增加 detections.csv、标签、带框图、模型 manifest。
V2 增加 objects.csv、paired_frames.csv、rejected-input.csv、CameraInfo/标定契约和独立真值。
V3 增加 tracks.csv、身份标签和重置/失踪时间线。
实际运行增加 latency.csv、resources.csv、metrics.json。

CSV 共同关联字段：source_session_id、observation_id、detection_index、source_stamp、frame_id、source_image_id（按来源适用）。objects 记录 position_valid、invalid_reason、reference_u/v、xyz、depth fraction、track/session。缺失数值为空，不用 0 伪装。指标 JSON 不能省略漏检/无效的分母。

所有失败和原始数据保持可追溯。模型/大数据可能被 Git 忽略，要记录其实际保存位置和哈希；仅有哈希不等于文件已保存。合成算术测试、真实图片和实机结果分别标注。

## 12. 下一轮唯一允许执行的 V0

### 12.1 前置条件与复制策略

还需独立的 V0 执行授权和可用 Linux Humble。首选原 Ubuntu103 虚拟机。源码使用 Windows 当前两个新包的审阅快照，复制到独立 review/src；不把整个机器人仓库构建或覆盖生产 overlay。

默认 Linux scratch：/home/weiyang/vision_review_ws/<run_id>/，包含 src/build/install/log。路径已存在则换新 run_id，禁止删除或重置旧目录。对 Windows、复制后目标和执行前后的源码分别计算哈希；传输成功不等于目标副本正确。

清洁环境检查 PATH、PYTHONPATH、PYTHONHOME、VIRTUAL_ENV、AMENT_PREFIX_PATH、COLCON_PREFIX_PATH、CMAKE_PREFIX_PATH、LD_LIBRARY_PATH、Python 可执行文件、ROS_DISTRO。仅当前临时进程 source /opt/ros/humble 和 review/install，不修改 .bashrc/全局设置。

只读检查所需 rclpy、diagnostic_msgs、vision_msgs、std_msgs、geometry_msgs、ROSIDL 和 ament/launch 依赖。缺失就 BLOCKED，本轮不 apt/pip 安装。新 bash 仍可能继承环境，不能单凭 --noprofile 宣称隔离。

ROS_LOCALHOST_ONLY=1。ROS_DOMAIN_ID 从 61 开始，以不使用 daemon 的局部发现检查确认；已有未知节点就试 62、63，仍有冲突则 BLOCKED。只变更临时进程环境，不更改机器人设置，不查询/停止别人 daemon。发现时排除并记录本轮自己的 CLI 观察节点。

### 12.2 当前真实配置

V0 检查的参数名必须与现有节点一致：
~~~yaml
mode: skeleton
backend: unconfigured
model_path: ""
detector_enabled: false
tracking_enabled: false
publish_debug_image: false
status_topic: /dg/vision/status
~~~

detector、tracker、debug、object_output 不是当前配置参数，不能用它们替代真实字段。object_output_active 是诊断值，应为 false，不是可写配置。当前 sync_tolerance_sec=0.05、深度 0.2～8.0 只是未使用的保留参数，V0 不将它解释成 V2 实现。

当前代码只有 /dg/vision/ 前缀检查，没有精确话题锁定和动态参数回调。V0 使用审阅后的原配置，不重映射、不尝试非法 status_topic。端点检查是外部验收，不虚构代码已实现精确拒绝。

### 12.3 顺序与判定

| 编号 | 执行动作 | 保留证据 | 不满足时 |
|---|---|---|---|
| V0-01 | 确认授权、源/目标哈希、环境、路径和局部 domain | metadata/source_hash/env | BLOCKED，停止 |
| V0-02 | colcon list 仅发现两个预期源包；检查依赖 | colcon_list/dependencies | 缺环境 BLOCKED，包异常 FAIL |
| V0-03 | 独立 build/install/log 构建两包 | build.log | 编译失败 FAIL，不修 |
| V0-04 | interface show；Python 导入并记录 __file__；pkg prefix/安装资产 | interface_show/import_paths | 错包/导入失败 FAIL |
| V0-05 | 启动原 shell，读取实际参数、node info、话题类型及状态 | parameters/node_info/status | 越界端点或虚假 active 为 FAIL |
| V0-06 | 观察 10 s，检查正常关闭，仅清理自己启动的进程 | shutdown/processes | 残留/异常关闭 FAIL |
| V0-07 | 单独以 mode:=v1 启动，最多 10 s | rejection.log/exit status | 没有拒绝非骨架模式为 FAIL |
| V0-08 | 核对源码未变、保存清单与结论 | checklist/manifest | 证据缺失不可记 PASS |

未来命令顺序是：设置临时环境 → 只针对两包 colcon list → 带独立 log/build/install 路径的 colcon build → source review install → interface show/import/prefix → ros2 launch。所有路径先解析为绝对路径，禁止使用生产 install。本计划不在当前回合执行这些命令。

观察使用 ros2 node info --no-daemon --spin-time 2；诊断读取有 10 s 外层 timeout。无消息时不能无限等待，timeout=124 记超时，不当成功。接口上只有 /dg/vision/status 的 DiagnosticArray 是应用输出；rosout、parameter_events、参数服务是允许的 ROS 基础设施。禁止任何相机/目标/控制应用端点。若 /objects 出现 DiagnosticArray，立即 FAIL。

V0_REJ 是唯一允许的“非默认参数”测试：单独的 mode:=v1 拒绝测试，不是运行中开功能。记录实际退出码，不预设数字。

V0_FROZEN 结论只说明包与壳，不说明视觉能力。为保留既有回传习惯，总结字段使用：
- V0_PACKAGE_AND_SHELL_VERIFIED：所有实际执行的必需项通过。
- V0_RUNTIME_BLOCKED：缺环境或有失败未完成；同时必须用 check_status=FAIL/BLOCKED 区分软件失败与环境缺失，不把代码错误说成机器没开。

每份总结还必须有 camera_contract=NOT_RUN，V1/V2/V3=NOT_IMPLEMENTED，ARM_READY=NO。

### 12.4 V0-FIX

V0 中只记录失败，不同轮顺手改源码、配置、消息或装依赖。修复需另获 V0-FIX 授权，只修对应壳/接口/打包问题，不加入 YOLO、相机或目标输出。修复后重新获准运行 V0，仍不自动进入 V1。

Linux 不可用时，只做静态检查及元数据，报告 V0_RUNTIME_BLOCKED。不要等待旧 IP，不因锁屏或网页审阅不可用卡住，不搭 WSL/Docker/仿真来绕过范围。

## 13. 后续按此填代码的任务分解

以下均为未来参考规格，不代表当前执行授权。每阶段先拿到对应开发任务，再实施；结束时报告产物、检查和未验证部分。

| 顺序 | 实现任务 | 交付与退出条件 |
|---|---|---|
| 1 | V0 | 仅当前两包/当前消息/原 shell；按第 12 节停止 |
| 2 | V1-A 接口与纯数据层 | 在新接口包定稿第 3 节，构建并验证生成类型；补配置/数据类型/序号和消息映射检查；无真实模型运行 |
| 3 | V1-B 模型契约与离线引擎 | 提供获准本地模型和 manifest；实现预后处理/CPU ONNX；用固定黄金样例比较框和轮廓；无 ROS 相机/机械臂 |
| 4 | V1-C ROS 适配与二维验收 | 有限队列、工作线程、状态、真实编码和时间；先保留图像回放，再有权限接现有相机；执行 V1 指标 |
| 5 | V2-A 配对/标定/投影 | 先纯数组合成算术与错误输入检查，不作为相机成绩；实现第 7 节 |
| 6 | V2-B 真实位置验收 | 使用保留的注册深度/信息和独立真值；缺真值只验功能，不给精度 PASS |
| 7 | V3 | 同类 IoU/时间生命周期、显式关联键；身份标注序列和丢帧/重启验收 |
| 8 | Jetson 共存/优化 | 只测新增模块资源与既有话题基线；CPU 不达标才另开 TensorRT 优化，不调导航 |

代码组织建议采用 config/types、image_io、onnx_backend、postprocess、frame_pairing、depth_projection、tracker、message_mapping、pipeline、vision_node、offline_cli、evaluation 几组职责，不按单个函数跨包散放。launch/config 只服务新节点。新增测试只验证真实输入/输出、失败行为和接口，不用“文件含有某字符串”代表功能。

必须覆盖的检查：
- 图像颜色/步长/端序、letterbox 往返、框和轮廓对齐。
- 模型哈希、类别和 tensor 布局错误拒绝；不静默下载。
- 精确/近似/乱序/重复/超时配对，标定变化和时钟回退。
- 空/零/NaN/Inf/错误单位深度；轮廓过小/深度不连续/背景误取。
- 当前观测、无目标、无输入、过期目标严格区分。
- 2D/3D key 一致、无效值不变原点；跟踪不依赖有效深度。
- 多同类目标、短失踪、长遮挡、新会话和 ID 生命周期。
- 新节点没有控制应用端点，参数来源和关闭行为真实检查。

纯算法测试可用明确标记的合成数组，但只证明算法子功能；模型和实机测试必须分别保留真实来源。没有足够数据时如实 BLOCKED，不能由单元测试推断真实传感器效果。

## 14. 平台与云端交接

| 环境 | 允许证明的内容 | 不能替代 |
|---|---|---|
| 当前 Windows | 文档/源码/配置/哈希；未来获准后的离线图片算法 | Humble ROS 运行、真实相机或 Jetson 性能 |
| Ubuntu22/Humble VM | V0；未来录制 ROS 数据的接口/行为 | ZED GPU/SDK 与目标机资源共存 |
| Cursor 云端 | 仓库审阅；环境满足时经授权做独立 V0/离线检查 | 自动访问家庭局域网 VM、Jetson、USB 相机；真实硬件验证 |
| 实际 Jetson + 已有 ZED | 部署输入契约、共存、真实图像/深度及目标机性能 | 独立真值、抓取安全和比赛指标 |

GitHub 上传只能让云端读取代码，不能自动赋予 Cursor GitHub App 的私有仓库权限，也不授权花费云端额度。若 App 尚不能访问，用户在 GitHub/Cursor 授权该私有仓库。不得为省事改成公开。云端缺 Humble/依赖时记 BLOCKED；本次上传不附带自动云端任务、PR、依赖安装或设备登录。

云端第一次接管只 READ/VERIFY/REPORT：读本计划、核对两包与新旧接口、声明真实环境和执行范围。不要把未来第 6～10 节误读为当前 V1 开工授权。

## 15. 尚缺的外部条件与结论

这些是实施前的输入或实测门槛，不留给实现者凭空猜：
- V0 授权与可用 Linux Humble、已存在依赖、独立目录。
- 合法可用的指定模型、实际模型哈希和可复现导出。
- 当前 ZED 部署版本、采集时钟、RGB/深度/CameraInfo 和像素配准证据。
- 标注图片/身份视频；V2 同表面点的独立三维真值及测量不确定度。
- Jetson 实际资源基线及本模块运行测量。

不得伪造这些条件。架构与算法初值已确定，不需要实现者再选检测器、决定消息关联方式或猜深度策略；缺外部证据时停止相关验收，不修改现有导航补偿。当前总体状态仍是设计有条件可行，运行与性能均未验证。

## 16. 依据与修订说明

本版整合并替代此前三版中的重复设计段落，保留 V0 与 V0-FIX 边界。主要纠正：
- 当前参数名使用 detector_enabled/tracking_enabled/publish_debug_image，而非不存在的 detector/tracker/debug。
- 2D 先关联身份，再与深度结果按 key 组合，不是先删去无深度目标再跟踪。
- 采用仅含二维字段的新消息，消除 Detection2D 中未估计六维 pose 的含糊语义。
- 不靠数组下标跨话题关联；位置参考与 invalid_reason 分离。
- 模型轮廓用于降低背景污染，仍保留错误前景率和透明物体边界。
- 明确公式、默认阈值、目标距离、队列/时序、证据分母和缺真值状态。
- GitHub/云端可读取源码，不等于可做设备实测或自动获准 V1。

本轮只修改本文件；未改消息、配置、代码或运行功能。现有 README/VISION_MODULE 的阶段草稿在未来实现对应阶段时再同步；当前 V0 以实际脚手架和第 12 节为准，未来 V1～V3 以本详细规格为准。

官方/一手依据（用于合同和实现参考，不构成当前运行证明）：
- [Ultralytics YOLO11 模型](https://docs.ultralytics.com/models/yolo11/)：存在 nano 分割模型；本文性能目标不是上游宣传成绩。
- [固定 v8.3.0 导出实现](https://raw.githubusercontent.com/ultralytics/ultralytics/v8.3.0/ultralytics/engine/exporter.py)与[头部实现](https://raw.githubusercontent.com/ultralytics/ultralytics/v8.3.0/ultralytics/nn/modules/head.py)：640 分割输出布局参考，实际模型须验证。
- [COCO 类别表](https://raw.githubusercontent.com/ultralytics/ultralytics/v8.3.0/ultralytics/cfg/datasets/coco.yaml)。
- [ROS Humble BoundingBox2D](https://raw.githubusercontent.com/ros-perception/vision_msgs/humble/vision_msgs/msg/BoundingBox2D.msg)、[CameraInfo](https://raw.githubusercontent.com/ros2/common_interfaces/humble/sensor_msgs/msg/CameraInfo.msg)、[Image](https://raw.githubusercontent.com/ros2/common_interfaces/humble/sensor_msgs/msg/Image.msg)。
- [ONNX Runtime Python](https://onnxruntime.ai/docs/api/python/api_summary.html)、[TensorRT provider](https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html)、[NVIDIA 兼容矩阵](https://docs.nvidia.com/deeplearning/tensorrt/latest/getting-started/support-matrix.html)。
- [colcon discovery](https://colcon.readthedocs.io/en/released/reference/discovery-arguments.html)、[build 参数](https://colcon.readthedocs.io/en/released/reference/verb/build.html)。
