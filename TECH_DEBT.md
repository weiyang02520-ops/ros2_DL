# 技术债清单

扫描日期：2026-10-15。本文是当前工作树的静态检查和离线复现结果，不代表目标机健康检查。优先级按风险、影响与可验证成本排序；“有 TODO”不等于“现场已故障”，“没有 TODO”也不等于没有债务。

## 一、范围和方法

代码与配置扫描：src、scripts、tools；使用 rg 默认忽略规则，检查独立单词 TODO、FIXME、HACK，排除 SVG 和 lock 文件。忽略 .git、缓存、二进制、模型资产以及 Git 忽略项，不将 class_XXX 这样的标识误当作待办。本次命中 29 行，均位于第三方 rplidar 和 ZED 目录。原始命中清单见文末，包含上游注释成对标记，不能按行数计算独立缺陷。

可复现命令：

~~~bash
rg -n '\b(TODO|FIXME|HACK)\b' src scripts tools --glob '!*.svg' --glob '!*.lock'
~~~

另外人工检查包清单、桥接配置、速度仲裁、平台客户端、README 和特征评估器。以下非标记项明确区分源码事实、已复现问题与尚待现场核验的风险。未读取真实凭据，未修改系统设置，未进行网络或硬件探测。

## 二、按优先级排序

P0 表示已有证据表明必须停止使用的直接风险；P1 为发布前需解决或确认的风险；P2 为确定性维护与兼容性问题；P3 为可计划优化。此次未确认 P0，不意味着已排除实机安全风险。

| 优先级/编号 | 状态 | 问题与依据 | 处理与验收 |
| --- | --- | --- | --- |
| P1 D-01 | 未验证，发布门槛 | 当前 Windows 离线检查没有目标机、ROS 图、控制所有权及真实停车证据 | 由现场人员按 TEST_PLAN 补设备/TF/导航/任务/停止证据；不以 mock 放行 |
| P1 D-02 | 源码事实，部署待核对 | mobile_bridge.yaml 默认 host=0.0.0.0 且 require_token=false | 现场发布前核对可信网络与鉴权。不要将端口转发公网；本轮不改现有配置 |
| P1 D-03 | 源码注释，未复现现场故障 | rplidar Linux net_serial.cpp:248 标注使用非阻塞 I/O 的待办；发送循环依赖 write 的进展 | 在隔离设备环境评估短写/阻塞/取消，优先跟踪上游修复；不直接改驱动 |
| P1 D-04 | 未验证，依赖门槛 | CUDA、TensorRT、ZED SDK、事件视觉后端、ROS 消息与第三方包不由本次离线检查覆盖 | 目标机记录版本并构建所需包，执行真实数据验证；manifest 不能当安装证明 |
| P2 D-05 | 本轮已修复 | 单帧对 API 漏检负值、零、NaN、无穷大距离，能输出误导重复率 | 两个公开入口统一有限正值校验；新增案例修复前失败、修复后通过 |
| P2 D-06 | 本轮已修复 | 空间点和旧特征 ID 混用被退回旧 ID 路径，格式错误被算成零重复率 | 非空帧对格式不一致明确拒绝；双顺序与汇总/单对调用覆盖，保留合法旧格式 |
| P2 D-07 | 源码事实，仍需环境验证 | 工作路径默认 /home/nvidia/ros2_DL；平台和三维目录有各自覆盖入口 | 部署前核对最终参数及权限。集成规格已列来源，但没有迁移配置或自动发现设备 |
| P2 D-08 | 上游限制 | ZED GNSS 融合路径注明 loop closure/odometry 限制并强制关闭 Area Memory | 核对实际 SDK 版本和启用模式后验证定位行为，不直接删除保护分支 |
| P2 D-09 | 上游兼容待办 | ZED SDK workaround、SVO 版本检查、streaming 输入、人体跟踪支持等 | 先核对使用功能与上游版本；回放、真实帧、时间戳和导出结果分别验收 |
| P2 D-10 | 待维护 | 多份包声明和外部 SDK 不是传递依赖锁文件，ROS 条件依赖仍需目标解析 | 仓库地图保留声明来源；发布时附目标机依赖清单和构建输出 |
| P2 D-11 | 已识别，保留现状 | 开始前已有地图、误差评估、视觉、文档与产物的未提交改动 | 本轮不覆盖或清理。发布先审查完整 diff，不能把 git archive HEAD 视作工作树完整交付 |
| P3 D-12 | 上游优化 | ZED GPU 直接共享 TODO 与自定义检测配置示例 TODO | 只有实测瓶颈或启用定制模型时再处理，不能当必修运行故障 |
| P3 D-13 | 上游平台债务 | rplidar macOS/Windows I/O、定时器及 unpacker 注释 | 当前目标是 Linux/Jetson，按实际使用路径优先，保留完整索引便于上游比对 |

## 三、本轮修复边界

只修改 scripts/feature_repeatability_evaluator.py 的纯数据处理边界，补充已有测试文件，并新增定向检查脚本。匹配算法、聚合公式、JSON 字段、有效空间点和合法旧 ID 行为不作替换。

对非法参数采取显式拒绝，因此调用者可能新增收到 ValueError。混合格式应在采集或导入时修正，不能吞异常后回填零值。没有批量删除 TODO，没有替换上游 SDK，没有调整 CAN、串口、几何、速度、Nav2、MODEL-1/2/3 或系统服务。

## 四、全部代码与配置标记索引

以下保留命中文本，便于追溯；同一注释的起止标记并非两个独立问题。

~~~text
src/rplidar_ros-ros2/sdk/src/arch/linux/net_serial.cpp:248:// FIXME: non-block io should be used
src/rplidar_ros-ros2/sdk/src/arch/linux/timer.h:49:// TODO: the highest timer interface should be clock_gettime
src/rplidar_ros-ros2/sdk/src/arch/macOS/net_serial.cpp:143:// FIXME: non-block io should be used
src/rplidar_ros-ros2/sdk/src/arch/macOS/timer.h:49:// TODO: the highest timer interface should be clock_gettime
src/rplidar_ros-ros2/sdk/src/arch/win32/net_serial.cpp:280:            // FIXME: may cause problem here
src/rplidar_ros-ros2/sdk/src/dataunpacker/unpacker/handler_capsules.cpp:274:    // FIXME: to eval
src/rplidar_ros-ros2/sdk/src/dataunpacker/unpacker/handler_capsules.cpp:57:    // FIXME: to eval
src/rplidar_ros-ros2/sdk/src/dataunpacker/unpacker/handler_capsules.cpp:588:    // FIXME: to eval
src/rplidar_ros-ros2/sdk/src/dataunpacker/unpacker/handler_capsules.cpp:798:    // FIXME: to eval
src/rplidar_ros-ros2/sdk/src/dataunpacker/unpacker/handler_hqnode.cpp:56:    // FIXME: to eval
src/rplidar_ros-ros2/sdk/src/sl_lidar_driver.cpp:1385:            // FIXME: stupid implementation here
src/rplidar_ros-ros2/sdk/src/sl_lidar_driver.cpp:1545:            //FIXME: will be changed in future releases
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_bodytrk.cpp:406:    // TODO(Walter) Add support for
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_main.cpp:1213:  // TODO(walter) ADD SVO SAVE COMPRESSION PARAMETERS
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_main.cpp:1704:    // TODO(Walter) Fix this as soon as the `sl::Fusion` module will support loop
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_main.cpp:2945:    // TODO(Walter) Check SVO version when it's available
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_main.cpp:2963:    // TODO(Walter) Check SVO version when it's available
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_main.cpp:3665:      // TODO(Walter) Modify when support for streaming input is added in the
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:1228:  // ----> TODO(Walter) Remove this check when fixed in ZED SDK
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:1235:  // <---- TODO(Walter) Remove this check when fixed in ZED SDK
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:1332:  // ----> TODO(Walter) Remove this check when fixed in ZED SDK
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:1339:  // <---- TODO(Walter) Remove this check when fixed in ZED SDK
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:1378:  // ----> TODO(Walter) Remove this check when fixed in ZED SDK
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:1385:  // <---- TODO(Walter) Remove this check when fixed in ZED SDK
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:2325:      //.WithGpuData(img.getPtr<sl::uchar4>(sl::MEM::GPU)) // TODO: Enable direct GPU memory sharing when supported by Isaac ROS.
src/zed-ros2-wrapper/zed_components/src/zed_camera/src/zed_camera_component_video_depth.cpp:2436:        //.WithGpuData(depth.getPtr<sl::float1>(sl::MEM::GPU)) // TODO: Enable direct GPU memory sharing when supported by Isaac ROS.
src/zed-ros2-wrapper/zed_components/src/zed_camera_one/src/zed_camera_one_component_video.cpp:695:      //.WithGpuData(img.getPtr<sl::uchar4>(sl::MEM::GPU)) // TODO: Enable direct GPU memory sharing when supported by Isaac ROS.
src/zed-ros2-wrapper/zed_debug/config/custom_object_detection.yaml:20:          # TODO: Add one instance of each class to the list below
src/zed-ros2-wrapper/zed_wrapper/config/custom_object_detection.yaml:20:          # TODO: Add one instance of each class to the list below
~~~

## 五、关闭技术债所需证据

已修复项需包含同输入复现、失败前后对照、合法数据兼容性和退出码。现场项需记录设备、环境、日期、执行者、真实日志和中止条件。外部平台项需远端确认与本地任务身份对应；上传入队不够。上游 TODO 的关闭应关联实际版本差异与对应验收，不可只删除注释。

本轮结果见 [验证记录](docs/validation/20261015_INTEGRATION_REFRESH.md)。未执行项保持 NOT_PROVEN。
