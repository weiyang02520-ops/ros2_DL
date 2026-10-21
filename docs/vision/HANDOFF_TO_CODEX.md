# 本机 Codex 唯一入口 — ZED 瓶杯视觉软件包

**先读本文，再动手。** 旧文档保留作链接，不再作为执行入口。

| 项 | 值 |
|---|---|
| 分支 | `codex/zed-bottle-w1-w4`（基线 `vision/v1-v3`） |
| Draft PR | → `vision/v1-v3`（**勿合并** `main` / 存档分支） |
| 范围 | W1–W7 软件 + §11 可云端交付物；**实机仍 NOT_RUN** |
| 硬约束 | 不改 ZED SDK/驱动、Nav2、底盘、机械臂、生产服务/软链；无运动/`/initialpose`/正式 TF 发布 |

姊妹文档：[`DELIVERY_SCOPE.md`](./DELIVERY_SCOPE.md) · [`ARM64_DEPENDENCY_PLAN.md`](./ARM64_DEPENDENCY_PLAN.md) · [`delivery/`](./delivery/) · 历史 [`W1_W4_HANDOFF.md`](./W1_W4_HANDOFF.md) · [`LOCAL_HANDOFF.md`](./LOCAL_HANDOFF.md)

---

## ① 全部改动与未完成项

### 已完成（软件）

**W1–W4（既有）** 来源/时效/QoS、配准与 `MASK_DEGRADED`、ZED 只订阅 profile、ARM64 依赖方案。

**W5 坐标转换**

| 文件 | 作用 |
|---|---|
| `vision_perception/object_transform.py` | 纯数学：`p'=R p+t`；无效保留；无单位矩阵兜底 |
| `vision_perception/object_transform_node.py` | ROS 节点；默认 `enabled:=false`；static / TF@stamp |
| `config/transform_config.yaml` | 默认关闭 |
| `config/profiles/peer_robot_template.yaml` | 对方空模板 |
| `config/profiles/current_robot.yaml` | 本机实采占位（待填） |
| `launch/vision_object_transform.launch.py` | 独立 launch |
| `scripts/vision_object_transform_node` | libexec |
| `test/test_object_transform.py` | 合同单测 |

**W6 只订阅**

| 文件 | 作用 |
|---|---|
| `examples/subscribe_vision_objects.py` | 打印 objects/status；无控制 |
| `scripts/vision_subscribe_objects` | `ros2 run` 入口 |
| `examples/README.md` | 用法 |

**W7 启停/采集**

| 文件 | 作用 |
|---|---|
| `scripts/vision_delivery/Run-VisionStage.sh` | Linux 阶段入口（默认预览） |
| `scripts/vision_delivery/Run-VisionStage.ps1` | PC→SSH 包装 |
| `scripts/vision_delivery/README.md` | 说明 |
| `scripts/docker_humble_smoke.sh` | 云端/PC Docker Humble 冒烟 |

**§11 交付包（云端可写）**

| 文件 | 作用 |
|---|---|
| `docs/vision/delivery/MIGRATION_GUIDE.md` | 迁移顺序 |
| `docs/vision/delivery/ACCEPTANCE.md` | 验收壳 |
| `docs/vision/delivery/RESULTS_TABLE_TEMPLATE.csv` | 结果表模板（勿填假数） |
| `docs/vision/delivery/MODEL_AND_DEPS.md` | 模型依赖索引 |
| `evidence/templates/W5_TRANSFORM/`、`ACCEPTANCE/` | 证据空壳 |

接口：`INTERFACE_CONTRACT.md` 已补 W5 `/dg/vision/objects_target` 语义。

### 未完成（必须本机/实机）

- 模型 ONNX 导出与 SHA 填入（权重不进 git）
- Jetson aarch64 真实 `pip`/`colcon`（Docker x86 ≠ ARM64 RUN）
- 真 ZED 流、话题/编码复核、窗口 A/B 测量
- W5 **实机**外参/TF 与 `/objects_target` 精度
- 透明路线 B 实测
- 填写 `current_robot.yaml` 实测字段与 ACCEPTANCE 真值表
- 合并 `main` / 生产部署（禁止，除非用户另批）

---

## ② 实际跑过 vs 未验证

### 已跑（云端）

| 命令 | 结果 | 标签 |
|---|---|---|
| `pytest`（`src/vision_perception/test`） | **149 passed** | SOFTWARE_CHECKED |
| `bash scripts/docker_humble_smoke.sh`（`ros:humble-ros-base-jammy`） | `colcon build` 两包成功；三 launch `--show-args` OK；`mode:=skeleton` 限时启动（timeout 124=预期）；容器内 pytest 149 passed；`DOCKER_SMOKE_OK` | SOFTWARE_CHECKED |
| Docker 假流 + 真 ONNX 端到端 | **未跑**（无权重） | NOT_RUN |
| 真相机 / Jetson ARM64 RUN | **未跑** | NOT_RUN |

**假数据 / skeleton / Docker x86 ≠ 实机 PASS，不得记 `LIVE_CAMERA_OBSERVED`。**

### 未验证清单

`colcon` 在 Jetson 本机、假流+ONNX 冒烟、真 ZED、精度、挪位、透明 B、W5 实机 TF、对方标定。

---

## ③ 本机/实机步骤（唯一执行清单）

> 默认**预览**；加 `--execute` / `-Execute` 才跑。电池窗口短，按序、可砍项已标明。  
> **每步标注是否需用户单独授权。**

### 阶段 0 — 关机准备（可不连机器人）

| 序 | 动作 | 预计 | 通过 | 失败 | 授权 |
|---|---|---|---|---|---|
| 0.1 | `git fetch && git checkout codex/zed-bottle-w1-w4` | 2 min | tip 与 PR 一致 | 停 | 否 |
| 0.2 | 导出 YOLO11n-seg ONNX + 填 manifest SHA（见 `delivery/MODEL_AND_DEPS.md`） | 10–30 min | 文件在 `$HOME/vision_models/` | 无模型不开机 | 否 |
| 0.3 | 隔离目录：`pip install -r requirements-arm64.txt`；只 build 两包 | 视机 | import ORT OK；`ros2 pkg prefix` | 不改生产软链 | **建议用户确认隔离路径** |
| 0.4 | （可选）PC 再跑 `docker_humble_smoke.sh` | 5–15 min | DOCKER_SMOKE_OK | 记日志 | 否 |
| 0.5 | 预览：`bash Run-VisionStage.sh Perception`（无 `--execute`） | 1 min | 打印命令 | — | 否 |

回退：删隔离 ws；`git checkout vision/v1-v3`。

---

### 阶段 1 — 窗口 A：真相机链路（约 8–12 min）

**需用户授权：上电、启已审相机、短采集。**

| 序 | 动作 | 预计 | 通过 | 失败 | 授权 |
|---|---|---|---|---|---|
| A0 | 电量/静止/急停/范围确认 | 开机前 | 未就绪不开机 | — | 用户 |
| A1 | 上电 + PC 连热点 | 1–2 min | SSH 通 | 结束 | 用户 |
| A2 | `Run-ReadOnly.ps1 -Step 01/02 -Execute` | 0.5–1.5 min | 状态可记；未知危险任务则中止 | 停 | 用户（既有只读） |
| A3 | **已审入口**启 ZED（本包脚本不启驱动） | 0.5–1 min | 仅批准相机进程 | 关机改方案 | **用户单独授权** |
| A4 | `Run-ReadOnly.ps1 -Step 03 -Execute` ~15s | 0.5 min | RGB/Depth/Info 齐；填 `current_robot.yaml` | 话题不符→改 profile | 用户 |
| A5 | `Run-VisionStage.sh Perception --execute` | 0.5–1 min | status 非 FATAL；`source_kind=LIVE_CAMERA` | 存日志关机 | **用户授权感知** |
| A6 | `Subscriber` + 短 `Capture --duration=20`；摆 1 瓶/杯两位置 | 1–2 min | 有观测；无效 NaN+reason | 只记链路 | 用户摆物 |
| A7 | `StopOwn --execute`；日志回 PC | 0.5–1 min | 无悬挂本次 PID | 勿 pkill 整机 | 用户 |
| A8 | 正常停机 | ≥2 min | 留余量 | — | 用户 |

感知命令备忘：

```bash
source /opt/ros/humble/setup.bash
source $HOME/vision_isolated_ws/install/setup.bash
ros2 launch vision_perception vision_zed_subscribe.launch.py \
  mode:=v1_ros enable_objects:=true enable_tracking:=false \
  model_path:=$HOME/vision_models/yolo11n-seg.onnx \
  model_manifest_path:=$HOME/vision_models/model_manifest.json
```

---

### 阶段 2 — 窗口 B：挪位与精度（约 12–18 min）

**需用户单独授权实机验收。** 门槛见总计划 §8 / `delivery/ACCEPTANCE.md`。透明 B 可砍。无独立真值则绝对 XYZ 标 NOT_RUN。

| 序 | 动作 | 授权 |
|---|---|---|
| B1 | 上电 + Camera + Perception（复用 A profile） | 用户 |
| B2 | 瓶+杯各 5 位置采样填 RESULTS 表 | 用户摆测 |
| B3 | 每类 ≥3 次挪位；遮挡/失效 | 用户 |
| B4 | ≥3 min 连续（可与 B2/3 重叠） | 用户 |
| B5 | 可选透明短取样 | 可砍 |
| B6 | StopOwn + 停机 | 用户 |

---

### 阶段 3 — W5 实测（可与 A 后并行软件检，实机另窗）

| 序 | 动作 | 预计 | 通过 | 授权 |
|---|---|---|---|---|
| T0 | 无外参时保持 `enabled:=false`；可 Docker/隔离测 disabled 状态 | 5 min | status=`TRANSFORM_DISABLED` | 否 |
| T1 | 对方/本机填 `peer_robot_template` 真外参（禁 identity） | — | extrinsics_id 非空非 EXAMPLE | **用户/对方** |
| T2 | `Run-VisionStage.sh Transform --execute` 且 `VISION_TRANSFORM_ENABLED=true` + 参数 | 1 min | `/objects_target` frame=target；无效源仍无效 | **用户授权** |
| T3 | 已知点独立测量核对方向单位 | — | 记误差；失败则关 enabled | 用户 |

```bash
ros2 launch vision_perception vision_object_transform.launch.py enabled:=true \
  mode:=static_extrinsics \
  source_frame:=<实测光学frame> \
  target_frame:=<对方frame> \
  extrinsics_id:=PEER_CALIB_YYYYMMDD
# translation / quaternion 写入 params 文件，勿命令行猜
```

---

### 阶段 4 — 交付打包（关机后 PC）

| 序 | 动作 | 授权 |
|---|---|---|
| D1 | 填 ACCEPTANCE / RESULTS（真假来源分明；未测 NOT_RUN） | 否（文书） |
| D2 | 打包：分支 tip、模型 SHA、`current_robot.yaml` 实测、bag/日志路径、迁移指南 | 否 |
| D3 | 交给机械臂同学；说明表面点≠抓取点；对方标定仍 PEER_CALIBRATION_NOT_RUN | 用户发送 |

---

### 回退（一键回原版视觉基线）

```bash
# 只停本次 PID
bash Run-VisionStage.sh StopOwn --execute
# 代码
git fetch origin && git checkout vision/v1-v3
# 或机上备份
# git checkout robot/pre-vision-backup-20261020
# 删除隔离 install 目录；不动 ~/ros2_DL 生产软链
```

---

## 快速索引

| 需求 | 路径 |
|---|---|
| ZED 只订阅 | `launch/vision_zed_subscribe.launch.py` |
| 假流开发 | `vision.launch.py` + `use_fake_*` → `SYNTHETIC_DEV` |
| 转换 | `launch/vision_object_transform.launch.py`（默认关） |
| 订阅打印 | `ros2 run vision_perception vision_subscribe_objects` |
| 阶段脚本 | `scripts/vision_delivery/` |
| Docker 冒烟 | `scripts/docker_humble_smoke.sh` |
