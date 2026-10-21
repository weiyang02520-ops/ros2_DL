# W1–W4 软件准备交接（给本机 Codex / 现场）

**分支：** `codex/zed-bottle-w1-w4`（基线 `vision/v1-v3` @ `adcd2d8`；本包提交见分支 tip）  
**范围：** 总计划第 12 节 — 只做 W1–W4；**不含 W5 坐标转换**。  
**硬约束：** 不改 ZED SDK/驱动、Nav2、底盘、机械臂、三模型、生产服务/软链；不发运动/导航/`/initialpose`/正式 TF。  
**材质：** 不透明基线（路线 A）+ 透明待定（路线 B）；**不承诺透明瓶杯深度可靠**。

---

## 1. 改了哪些文件 / 哪些没完成

### 1.1 已改文件（逐个）

| 文件 | 改动摘要 |
|---|---|
| `src/vision_perception/vision_perception/types.py` | 新增 `SYNTHETIC_DEV`、`MASK_DEGRADED`；`resolve_observation_source_kind` / `topic_looks_synthetic` |
| `src/vision_perception/vision_perception/source_qos.py` | **新建** BEST_EFFORT/RELIABLE 传感器订阅 QoS |
| `src/vision_perception/vision_perception/config.py` | `input_profile`、`source_kind`、`image_qos_reliability`、`allow_bbox_mask_fallback`、配准开关；允许 `ZED_TOPIC_SUBSCRIBE_ONLY / NOT_START_SDK` |
| `src/vision_perception/vision_perception/pipeline.py` | v1_ros 默认 `source_kind` 走解析，假流不再写死 LIVE |
| `src/vision_perception/vision_perception/vision_node.py` | 假流≠LIVE；推理前后双次时效门控；传感器 QoS；mask/配准参数下传；status 诊断字段 |
| `src/vision_perception/vision_perception/objects_pipeline.py` | RGB/深度/内参尺寸与 frame 硬拒绝；mask 退化可诊断；`allow_bbox_mask_fallback=false` → `MASK_DEGRADED`+NaN；保留无效目标 |
| `src/vision_perception/vision_perception/message_mapping.py` | 导出 `mask_degraded_count` / `registration_reason` |
| `src/vision_perception/vision_perception/status_fields.py` | 增加 post-infer 丢帧、profile/QoS/mask 诊断键 |
| `src/vision_perception/config/vision.yaml` | 新参数默认值与注释 |
| `src/vision_perception/config/profiles/zed_subscribe.yaml` | **新建** ZED 只订阅 profile（tracking 关、bbox 退化关） |
| `src/vision_perception/config/profiles/fake_dev.yaml` | **新建** 假流 profile（`SYNTHETIC_DEV`） |
| `src/vision_perception/launch/vision.launch.py` | 假流自动 `SYNTHETIC_DEV` |
| `src/vision_perception/launch/vision_zed_subscribe.launch.py` | **新建** 只启视觉节点、不启 ZED |
| `src/vision_perception/requirements-arm64.txt` | **新建** Jetson 隔离依赖清单 |
| `src/vision_perception/CMakeLists.txt` | 安装 `requirements-arm64.txt` |
| `src/vision_perception/test/test_w1_w4_source_mask_age.py` | **新建** W1–W4 回归用例 |
| `src/vision_perception_interfaces/msg/VisionObject.msg` | 注释补充 `MASK_DEGRADED` |
| `src/vision_perception_interfaces/msg/VisionObjectArray.msg` | 注释补充 `SYNTHETIC_DEV` |
| `src/vision_perception_interfaces/INTERFACE_CONTRACT.md` | 来源/时效/mask/QoS/profile 合同更新 |
| `docs/vision/DELIVERY_SCOPE.md` | **新建** 交付范围（相机点 vs 目标转换、A/B 材质、状态标签） |
| `docs/vision/ARM64_DEPENDENCY_PLAN.md` | **新建** 模型+ARM64 隔离方案 |
| `docs/vision/LOCAL_HANDOFF.md` / `CLOUD_HANDOFF.md` | 指向本分支与本交接 |
| `docs/vision/W1_W4_HANDOFF.md` | **本文件** |

### 1.2 未完成 / 不在本包

- **W5** 坐标转换适配器与 `/dg/vision/objects_target`
- **W6** 只订阅示例增强 / 三维 debug 标注
- **W7** `Run-VisionStage.ps1` 启停包装（拟新增，本包未交付可执行脚本）
- **W8** 实机 ACCEPTANCE 结果表
- 实机 ZED 流、话题名复核、精度测量、透明路线 B 实测
- Jetson aarch64 上真正 `pip`/`colcon`/`ros2 launch`（云端无 ROS / 无硬件）
- 模型权重下载与 SHA 填入（权重不进 git）
- 合并进 `main` / 生产部署（禁止）

---

## 2. 实际跑过什么 / 仍未验证

### 2.1 已跑（云端 VM）

| 命令 | 结果 | 状态标签 |
|---|---|---|
| `python3 -m pip install --user -r …`（numpy 已有；补装 pytest、opencv-headless、onnxruntime） | 成功 | SOFTWARE_CHECKED（依赖在本 VM） |
| `cd src/vision_perception && python3 -m pytest test/ -q` | **143 passed** in ~0.5s | SOFTWARE_CHECKED |
| `python3 -m py_compile` launch 与主要模块 | 语法 OK（在修复后） | SOURCE_ONLY |

假数据相关断言覆盖：source_kind 解析、MASK_DEGRADED、尺寸不匹配 INPUT_INVALID、ZED profile 文件存在。  
**不得**把上述结果写成实机 PASS / `LIVE_CAMERA_OBSERVED`。

### 2.2 未跑（一律 NOT_RUN）

| 项 | 原因 |
|---|---|
| `colcon build --packages-select vision_perception_interfaces vision_perception` | 云端无 `/opt/ros`、无 `colcon` |
| `ros2 launch …` 假流冒烟 | 无 ROS2 |
| 真 ZED / 实机话题 / 精度 / 挪位 / 透明杯 | 机器人关机且无局域网；未授权实机 |
| ARM64 Jetson 安装与推理 Hz | 无目标机 |

---

## 3. 后续部署 / 启动 / 实机验收清单（本机 Codex 照做）

> 机器人电池供电，开机时间有限。下列按顺序；**默认预览，显式执行才跑**。  
> 一键回退见 §3.5。

### 3.0 开机前（机器人保持关机可做）

| 步 | 动作 | 预计 | 通过标准 | 失败 |
|---|---|---|---|---|
| P0 | `git fetch` 并检出 `codex/zed-bottle-w1-w4`；读本文 + `DELIVERY_SCOPE.md` | 2–5 min | 提交与本文一致 | 停 |
| P1 | 准备 YOLO11n-seg ONNX + manifest 到 `$HOME/vision_models/`（见 `ARM64_DEPENDENCY_PLAN.md`） | 10–30 min | SHA 写入 manifest | 无模型不开机测 |
| P2 | 隔离目录：`pip install --user -r requirements-arm64.txt`；`colcon build` 只两包 | 视机 15–60+ min | `import onnxruntime` OK；`ros2 pkg prefix vision_perception` | 记 BUILT 失败；不改生产软链 |
| P3 | PC 预览 launch 参数（不连机器人） | 2 min | 命令可复制 | — |

### 3.1 窗口 A：真相机链路（约 8–12 min，需已 BUILT）

| 序 | 命令/动作 | 预计 | 通过 | 失败怎么办 |
|---|---|---|---|---|
| 0 | 确认电量、静止、急停；范围=只订阅+感知 | 开机前 | 未准备好就不开机 | — |
| 1 | 用户上电；PC 连热点 | 1–2 min | SSH 通且静止 | 结束 |
| 2 | `Run-ReadOnly.ps1 -Step 01/02 -Execute` | 0.5–1.5 min | 记录进程/话题；有未知危险任务则中止 | 停本阶段 |
| 3 | **用户/已审入口**启动既有 ZED（本包不启驱动） | 0.5–1 min | 仅批准的相机进程 | 无法隔离则关机改方案 |
| 4 | `Run-ReadOnly.ps1 -Step 03 -Execute` ~15s | 0.3–0.6 min | RGB/Depth/Info 尺寸编码时戳齐 | 话题名不符→改 profile 再来，不猜绑 |
| 5 | 感知（示例，路径按隔离 install）： | 0.5–1 min | status 非 FATAL；`source_kind=LIVE_CAMERA`；无 fake | 保存错误日志关机 |
| 6 | 短采 + 摆一个瓶/杯两位置 | 1–2 min | 有 detections/objects；无效项 NaN+reason | 只记链路，不宣称精度 PASS |
| 7 | 只停本次视觉 PID；日志回 PC | 0.5–1 min | 无悬挂采集 | 勿 `pkill -9` 整机 |
| 8 | 用户正常停机 | ≥2 min 预留 | 留关机余量 | — |

**感知命令模板（隔离 ws，预览后执行）：**

```bash
source /opt/ros/humble/setup.bash
source /PATH/TO/ISOLATED_WS/install/setup.bash
# V1 only
ros2 launch vision_perception vision_zed_subscribe.launch.py \
  mode:=v1_ros enable_objects:=false enable_tracking:=false \
  model_path:=$HOME/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=$HOME/vision_models/model_manifest.json
# 下一轮再开 V2（另一次授权窗口亦可）：
#   enable_objects:=true
```

只读检查：

```bash
ros2 topic echo /dg/vision/status --once
ros2 topic echo /dg/vision/detections_2d --once
# enable_objects 后：
ros2 topic echo /dg/vision/objects --once
# 确认：source_kind 非 SYNTHETIC_DEV；position 无效时为 NaN 且 position_valid=false
```

### 3.2 窗口 B：挪位与精度（约 12–18 min）

前提：窗口 A 真输入已通。透明杯单列，可砍。步骤见总计划 §9.4；本包不重复编造测量数字。绝对 XYZ 无独立真值时标 `CAMERA_POSITION_MEASURED=NOT_RUN`。

### 3.3 假流冒烟（PC/隔离机，无硬件；≠实机 PASS）

```bash
ros2 launch vision_perception vision.launch.py \
  mode:=v1_ros use_fake_image:=true use_fake_depth:=true \
  enable_objects:=true enable_tracking:=false \
  fake_image_path:=$SHARE/examples/smoke_rgb_hint.npy \
  model_path:=/ABS/yolo11n-seg.onnx \
  model_manifest_path:=/ABS/model_manifest.json
# 期望 status source_kind=SYNTHETIC_DEV（绝不是 LIVE_CAMERA）
```

### 3.4 通过 / 失败速查

| 现象 | 处理 |
|---|---|
| 订不到 ZED 图 | 核对 QoS（默认 best_effort）与话题名；改 `zed_subscribe.yaml` |
| `MASK_DEGRADED` 大量 | 检查 seg mask；临时仅假流可开 `allow_bbox_mask_fallback:=true`，实机合格三维保持 false |
| `observations_dropped_age_post_infer` 升 | 推理过慢；降分辨率/Hz 或另批 TensorRT（需授权） |
| 假流显示 LIVE_CAMERA | 回归失败；确认 launch 带 `use_fake_*` 或 `fake_dev` profile |

### 3.5 回退（一键回到原版视觉基线）

```bash
# 只停本次节点（示例）
ros2 node list | grep vision
# 结束对应 PID / Ctrl+C launch，不要动 ZED 驱动除非当次你启的

# 代码回退到导入视觉前的机上备份或 vision 基线：
git fetch origin
git checkout vision/v1-v3          # 或 robot/pre-vision-backup-20261020
# 隔离 ws：删除/停用本次 isol 目录即可，不动 ~/ros2_DL 生产软链
```

生产未改软链时，**删掉隔离 install + 停节点 = 回到原版**。

---

## 4. 给审阅者的一句话

W1–W4 已在功能分支落地：假流不再冒充 LIVE、推理后时效补门控、ZED 只订阅 profile、mask/深度错误可诊断且无效目标保留；云端 **143** 单测通过；实机构建与验收 **NOT_RUN**，透明深度不承诺。
