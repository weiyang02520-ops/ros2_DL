# 本地 Cursor 接手文档（实机 / SSH 线）

> **读者：** 在**本地 PC** 新开 Cursor 对话、且能 SSH 到机器人 `nvidia@192.168.43.12` 的会话。  
> **云端：** 曾连不上该局域网 IP（ping/ssh 超时）；实机备份与联调由本线接手。  
> **分支：** `cursor/vision-v1-offline-1fcf`（[PR #1](https://github.com/weiyang02520-ops/dg202611_robot_integration/pull/1)，**勿合并**，直至用户明确要求）。  
> **姊妹文档：** 根目录 `CLOUD_HANDOFF.md`（仓库发布与云端边界；内容偏早期，以本文 + `src/vision_perception/README.md` + `docs/dg202611/VISION_INTEGRATION_PLAN.md` 为准）。

---

## 1) 项目目标与阶段现状

**目标：** 在机械臂无关的 `vision_perception` 包上完成 V0–V3 框架（检测 → 深度三维 → 短时跟踪），再与机上**已有**双目/ZED 话题只读订阅联调；不接管导航/底盘/机械臂。

| 阶段 | 已实现（云端/单测可证） | 默认开关 | 实机/精度仍 NOT_RUN |
|---|---|---|---|
| **V0** | `mode:=skeleton`：只发 `/dg/vision/status`（`SKELETON_ONLY`） | 默认 `skeleton` | — |
| **V1** | `mode:=v1_ros`：订 RGB → YOLO11n-seg ONNX CPU → `/dg/vision/detections_2d`；离线 CLI `vision_offline_detect` | 须显式 `v1_ros` | 实机相机/瓶杯图冒烟；真 ONNX 黄金比对（权重不进 git） |
| **V2** | `enable_objects:=true`：RGB–深度配对、表面采样 → `/dg/vision/objects`；假深度/离线 `vision_offline_objects` 仅通管道 | **默认 false** | 实机 ZED 配准深度、透明物、三维精度（median≤30mm 等） |
| **V3** | `enable_tracking:=true`：确定性**贪心**按类 IoU（非匈牙利）；`object_id` / `tracking_session_id`；离线 `vision_offline_track` + IDF1 脚手架 | **默认 false** | 身份标注序列上的 IDF1 验收；`result` 脚手架恒为 `NOT_RUN` |

**包：** `src/vision_perception`（ament_cmake + ament_python）、`src/vision_perception_interfaces`。  
**云端已齐：** §5/§9 参数接线、IDF1 脚手架、evidence 空壳模板、pytest 全绿（约 137）。  
**合成冒烟 ≠ PASS：** fake depth / 假图只证明 plumbing；不得记 ZED / V2 精度 / V3 IDF1 PASS。

---

## 2) 安全边界（硬规则）

- **不改：** ZED SDK、已有 ZED/双目 launch、Nav2/AMCL/SLAM、EKF/TF 归属、底盘/`ylhb_*`、MODEL-1/2/3 生产 bringup。  
- **不发：** `/cmd_vel` 或任何会使底盘/导航进入可执行态的 goal/service/lifecycle。  
- **`ARM_READY=NO`**；`orientation_valid` 全阶段保持 false（不授权抓取）。  
- **`camera_contract:="DEV_WEBCAM_ONLY / NOT_ZED"`**（v1_ros 冒烟与首轮实机联调均用此合同；节点可*订阅* ZED 话题名，但**绝不**启动 ZED SDK/驱动）。  
- 实机运动与巡逻由**用户现场**执行；Agent 仅做只读诊断（`ros2 topic/node/hz/echo`、日志）。详见 `skills/robot-motion-test-boundary/SKILL.md`、`skills/ros2-practice-first/SKILL.md`。

---

## 3) 用户定的实机顺序（必须遵守）

用户原话要点：**机上代码很乱；先整仓原样上传备份，再摸清结构；修整听用户说。** 用户记得机上有 **`res_ds`**（底盘与多元件原库）——须纳入备份并查清路径/git 关系，**不得擅自整理**。

```text
SSH 通 → ① 整仓原样备份上传 → ② 只读摸结构（含 res_ds）→ ③ 修整等口令
       → ④（口令后）拉视觉分支并只 build 两视觉包 → ⑤ 用户启现有双目 → V1 再 V2 冒烟
```

### ① 整仓原样备份（第一步，优先于任何修整/合并）

- 主机：`nvidia@192.168.43.12`（密码由用户当面提供；勿写入仓库）。  
- 找到机上真实工作空间 / git 根（可能很乱，多份目录并存）。  
- 推备份分支名：`robot/pre-vision-backup-YYYYMMDD`（按当天日期）。  
- **不改不删**、脏文件先 commit 进备份分支亦可；**不 force-push `main`**。  
- 备份完成再报告分支 URL，作回滚点。

### ② 只读摸结构

- 目录树、`git remote`/`status`/当前 commit、是否 dirty。  
- **`res_ds`：** 绝对路径、是否独立 git、与视觉/导航工作空间的关系。  
- 记下已有双目/ZED 启动方式与话题名（只记录，不改 launch）。

### ③ 修整

- **严格等用户口令**；未点名的目录/包不要“帮忙清理”。

### ④ 部署视觉（仅在用户明确同意备份完成之后）

- 在备份基础上开工作分支（如 `robot/vision-bringup-YYYYMMDD`），fetch/merge `cursor/vision-v1-offline-1fcf`。  
- **只** `colcon build --packages-select vision_perception_interfaces vision_perception`（勿整仓乱编无关包，除非用户要求）。  
- 权重与 manifest 放机上本地路径（见 §4），**不进 git**。

### ⑤ 双目结合冒烟（只订阅）

用户现场先启动**已有**双目/ZED 驱动。默认话题（YAML，可按实机改参）：

| 参数 | 默认名 |
|---|---|
| `rgb_topic` | 常为 `/zed/zed_node/rgb/color/rect/image`（以机上为准） |
| `depth_topic` | `/zed/zed_node/depth/depth_registered` |
| `camera_info_topic` | `/zed/zed_node/rgb/color/rect/camera_info` |

1. **首轮 V1：** `mode:=v1_ros`，`enable_objects:=false`，`enable_tracking:=false`，`camera_contract:="DEV_WEBCAM_ONLY / NOT_ZED"`，`rgb_topic` 指实机 RGB。  
2. **次轮 V2：** 再开 `enable_objects:=true`，接上 depth + camera_info。  
3. **tracking 默认关**；另开需用户再说。  
4. 验收只读：`/dg/vision/status` 非 FATAL、`arm_ready=NO`；V1 有 `/detections_2d`；V2 有 `/objects`（无深度时 `position_valid=false` 可接受）。结果记 **NOT_RUN**，不写精度 PASS。

---

## 4) 本地操作清单

### 4.1 克隆与检出本分支

```bash
git clone https://github.com/weiyang02520-ops/dg202611_robot_integration.git
cd dg202611_robot_integration
git fetch origin cursor/vision-v1-offline-1fcf
git checkout cursor/vision-v1-offline-1fcf
git pull --ff-only origin cursor/vision-v1-offline-1fcf
```

必读：`LOCAL_HANDOFF.md`（本文）、`src/vision_perception/README.md`、`docs/dg202611/VISION_INTEGRATION_PLAN.md`。

### 4.2 ONNX 与 model_manifest（权重不进 git）

推荐路径（机上/Ubuntu103 曾用类似布局）：

```text
$HOME/vision_models/yolo11n-seg.onnx
$HOME/vision_models/model_manifest.json   # 从 examples 模板复制后填 SHA256/许可
```

```bash
mkdir -p "$HOME/vision_models"
cp src/vision_perception/examples/model_manifest.template.json \
  "$HOME/vision_models/model_manifest.json"
# 放入本地导出的 yolo11n-seg.onnx，编辑 manifest 的 onnx_sha256 / weights_sha256 / license
sha256sum "$HOME/vision_models/yolo11n-seg.onnx"
```

根 `.gitignore` 已忽略 `.onnx` / `.pt`。节点**不**自动下载权重；`v1_ros` 缺绝对路径或 SHA 不匹配会 FATAL。

### 4.3 依赖版本（Ubuntu103 已验证思路）与 bootstrap

| 包 | 钉死版本 |
|---|---|
| NumPy | `>=1.26.4,<2`（**禁止 NumPy 2.x**） |
| OpenCV | `opencv-python-headless==4.10.0.84` |
| ONNX Runtime | `onnxruntime==1.20.1`（CPU） |
| ROS | Humble；推理进程不引 Ultralytics/PyTorch |

**安装顺序：** 先 NumPy 再 OpenCV，再 onnxruntime。一键：

```bash
source /opt/ros/humble/setup.bash
export PATH="/opt/ros/humble/bin:$PATH"; hash -r   # 防 ~/.local/bin/ros2 抢 PATH
python3 -m pip install --user -r src/vision_perception/requirements-runtime.txt
```

构建（只两包）：

```bash
bash src/vision_perception/scripts/ensure_scripts_executable.sh
rm -rf build/vision_perception build/vision_perception_interfaces \
       install/vision_perception install/vision_perception_interfaces
colcon build --symlink-install --packages-select \
  vision_perception_interfaces vision_perception
source install/setup.bash
bash src/vision_perception/scripts/check_ament_prefix_hook.sh
```

仅两包 zip/SFTP 同步到孤立工作空间时：

```bash
bash src/vision_perception/scripts/bootstrap_isolated_ws.sh --build
```

单测（无相机）：`PYTHONPATH=src/vision_perception python3 -m pytest src/vision_perception/test -q`

---

## 5) 已踩过的坑与修法摘要

| 坑 | 现象 / 原因 | 修法 |
|---|---|---|
| **NumPy 2.x** | OpenCV `_ARRAY_API not found` / `numpy.core.multiarray failed to import`（Ubuntu103 实踩） | 钉 `numpy<2`；先装 NumPy 再装 cv2；`v1_ros` 遇 NumPy≥2 拒绝启动 |
| **纯 ament_python** | `package.dsv` 只有 pythonpath，`ros2 pkg prefix` 在 source 后失效 | 改为 **ament_cmake + ament_cmake_python**，写 `ament_prefix_path` hook |
| **CRLF shebang** | `python3\r`，脚本 exit 127 | `scripts/**` LF（包内 `.gitattributes`）；`sed` 去 `\r`；测 `test_script_line_endings` |
| **zip/SFTP 丢 +x** | symlink-install 后 launch 找不到可执行 | `ensure_scripts_executable.sh` / bootstrap；CMake `install(PROGRAMS … PERMISSIONS)` |
| **`~/.local/bin/ros2` 抢 PATH** | pip --user 后 Humble `ros2` 被坏副本盖住 | `export PATH="/opt/ros/humble/bin:$PATH"; hash -r` |
| **假 RGB/深度双定时器** | stamp 偏斜 ≈0.20s → `DEPTH_UNPAIRED` | fake depth 作 stamp master；RGB 跟 depth stamp；`sync_wait_sec` 默认 0.100 |
| **`mode:=v1`** | 旧别名 | **拒绝**，须用 `v1_ros` |
| **无 model_path** | `v1_ros` FATAL（设计如此） | 传绝对 `model_path` + `model_manifest_path` |
| **云端 SSH 局域网机器人** | `192.168.43.12` ping/ssh 超时 | **改本地 Cursor** 接手（本文场景） |
| **误记精度 PASS** | 合成冒烟当 ZED/IDF1 通过 | evidence/`result` 保持 **NOT_RUN**；无独立真值不写 PASS |

---

## 6) 给本地 Cursor 新会话的开场提示语（复制即用）

```
你是本地 Cursor 会话，接手 DG-202611 视觉实机线。先读仓库根目录 LOCAL_HANDOFF.md（完整记忆），再读 src/vision_perception/README.md。

当前分支：cursor/vision-v1-offline-1fcf（PR #1，勿合并）。云端已完成 V0–V3 框架与单测；实机仍 NOT_RUN。

机器人 SSH：nvidia@192.168.43.12（密码当面给，勿写入仓库）。云端连不上该 IP，由你在本地执行。

强制顺序：
1) SSH 通后先把机上整仓原样备份上传到 GitHub 分支 robot/pre-vision-backup-YYYYMMDD（不改不删，不 force-push main）；用户说机上代码乱，且有 res_ds（底盘/元件原库）——必须摸清路径与 git 关系并纳入备份。
2) 只读摸清结构；任何修整严格等我口令，禁止擅自整理。
3) 我同意后再拉/合并视觉分支；只 colcon build vision_perception_interfaces 与 vision_perception；权重放 $HOME/vision_models/（不进 git）。
4) 双目由我现场启动；你只订阅现有话题：先 V1（enable_objects/tracking=false），再 V2（enable_objects=true）。camera_contract="DEV_WEBCAM_ONLY / NOT_ZED"。不改 ZED SDK/launch、Nav2、底盘；不发 cmd_vel；ARM_READY=NO。

遵守 skills/robot-motion-test-boundary 与 ros2-practice-first。先确认能 SSH，然后从整仓备份开始，每步回报。
```

---

## 快速链接

| 资源 | 路径 / URL |
|---|---|
| 本文 | `/LOCAL_HANDOFF.md` |
| 云端交接（早期） | `/CLOUD_HANDOFF.md` |
| 包 README | `src/vision_perception/README.md` |
| V4 计划 | `docs/dg202611/VISION_INTEGRATION_PLAN.md` |
| PR | https://github.com/weiyang02520-ops/dg202611_robot_integration/pull/1 |
| 运行时钉 | `src/vision_perception/requirements-runtime.txt` |
| manifest 模板 | `src/vision_perception/examples/model_manifest.template.json` |
