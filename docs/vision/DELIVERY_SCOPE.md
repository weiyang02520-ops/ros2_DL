# DG202611 ZED 瓶杯视觉 — 交付范围（W1 文档）

编制对齐：`DG202611_ZED瓶杯视觉交付总计划_20261021` 第 0/3/5/12 节。  
状态：软件准备（P1 / W1–W4）；实机项一律 **NOT_RUN**。

## 1. 本次交付什么

| 层 | 内容 | 完成判据 |
|---|---|---|
| A. 当前机器人相机坐标 | 真实 ZED RGB + 配准深度 → bottle/cup 可见表面点 | 实机测量后才可标 `CAMERA_POSITION_MEASURED` |
| B. 目标坐标转换 | 独立适配器（W5，本包不做） | 对方提供外参/TF；无外参不得输出有效 target |

本包（W1–W4）只做软件准备：来源/时效/QoS、配准与质量合同、ZED 订阅 profile、模型/ARM64 隔离方案。

## 2. 明确不做

- 不改 ZED SDK/驱动、Nav2、底盘、机械臂、三模型、生产服务或软链
- 不发 `cmd_vel`、导航目标、`/initialpose`，不发布正式 TF
- 不把表面点当抓取点；不承诺瓶盖/杯口/6D 姿态
- 不切换到旧 `yolo26` 后端；继续 YOLO11n-seg ONNX
- 跟踪（V3）默认关闭；坐标转换（W5）不在本包

## 3. 材质双路线

| 路线 | 实物 | 允许结论 |
|---|---|---|
| A 不透明/有纹理基线 | 明确列出的瓶/杯 | 仅声明这些条件通过 |
| B 透明/反光待定 | 原状透明杯/瓶（空/装水分记） | 2D 与 3D 分判；不得把检测成功当深度可靠 |

有限且稳定的深度数值 **不是** 表面归属证据。

## 4. 完成状态标签（禁止用单个 PASS 覆盖）

- `SOURCE_ONLY` — 实现存在
- `SOFTWARE_CHECKED` — 限定软件检查通过（云端单测/假流）
- `LIVE_CAMERA_OBSERVED` — 真实输入看到（未授权 → NOT_RUN）
- `CAMERA_POSITION_MEASURED` — 相机点位实测（NOT_RUN）
- `TARGET_TRANSFORM_SOFTWARE_CHECKED` — W5（未做）
- `PEER_CALIBRATION_NOT_RUN` — 对方标定

假数据冒烟 ≠ 实机 PASS。

## 5. 接口要点

- 话题：`/dg/vision/detections_2d`、`/dg/vision/objects`、`/dg/vision/status`
- 字段合同：`src/vision_perception_interfaces/INTERFACE_CONTRACT.md`
- 假流 `source_kind=SYNTHETIC_DEV`；真相机 `LIVE_CAMERA`
- 无效目标保留 + NaN + `invalid_reason`；禁用 0/旧点兜底
- `MASK_DEGRADED`：mask 不可用且禁止 bbox 退化时

## 6. 对方职责

另一台机：确认 ZED/话题/坐标系、完成相机→臂基座标定、决定抓取。本机只保证相机光学坐标合同与已测范围。
