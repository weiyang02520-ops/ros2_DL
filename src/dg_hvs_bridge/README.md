# dg_hvs_bridge

RDK X5 上的 APX003CC HVS 双流 ROS 2 桥。它只发布相机数据和诊断，不发布运动命令。

构建时必须把 `HV_TOOLKIT_ROOT` 指向官方 `shimetapi_hybrid_vision_toolkit` 根目录。RDK X5 当前没有 `colcon` 时，使用标准 CMake/ament 流程：

```bash
source /opt/tros/humble/setup.bash
export HV_TOOLKIT_ROOT=$HOME/shimetapi_hybrid_vision_toolkit
cmake -S src/dg_hvs_bridge -B build/dg_hvs_bridge \
  -DCMAKE_BUILD_TYPE=Release \
  -DHV_TOOLKIT_ROOT="$HV_TOOLKIT_ROOT"
cmake --build build/dg_hvs_bridge -j2
cmake --install build/dg_hvs_bridge --prefix "$HOME/dg202611_hvs_ws/install"
source "$HOME/dg202611_hvs_ws/install/setup.bash"
```

有完整 ROS 2 工作区时也可以用 `colcon build --packages-select dg_hvs_bridge --cmake-args -DHV_TOOLKIT_ROOT=$HV_TOOLKIT_ROOT`；两种方式得到的是同一个桥接目标。

默认参数保留当前板端已验证的 HVS 配置：`sensor_index=52`、`i2c_bus=6`、`evs_fps=240`。这里的索引是板端传感器配置索引，不等同于 EVS/APS 的 VC 编号；EVS/APS 的 VC1 配对由官方 `Backend::MipiHvs` 完成。官方文档中的 `0/1` 是通用默认值，不能在本板上未经验证直接替换已工作的配置。

桥接会记录 APS 的实际格式、尺寸和字节数，并输出 `aps_packets`、`aps_rate_per_sec`、`aps_decode_failures`、`get_frame_timeouts` 等诊断字段。这样可以区分“后端没有取到 APS”“取到了但格式未支持”和“已经有 APS 但融合配对未通过”。目前支持 NV12、Gray8、RAW8、BayerRG8、RGB888，以及明确的 16 位 unpacked RAW10；没有猜测 packed RAW10 的布局。

`recording_enabled:=true` 时在 RDK 本地保存 RAW8、EVT2、事件 CSV、APS PGM、融合 JPEG、配置和运行统计。结束后使用 `run_hvs_capture_session.sh` 生成 SHA-256 清单。


## features 话题

参数文件默认启用桥接内置的 `/dg/event_camera/features` 发布器。它使用与现有 `event_feature_node` 相同的 PointCloud2 字段：`pixel_x`、`pixel_y`、`event_count`、`positive_fraction`。如果仍运行 `run_rdk_event_feature_sidecar.sh`，请把桥接参数 `publish_features` 设为 `false`，避免两个节点同时发布同一 features 话题；需要相邻包重复率时使用 sidecar 的 `feature_quality` 诊断。
