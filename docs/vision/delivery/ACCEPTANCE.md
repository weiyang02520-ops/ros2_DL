# 验收记录模板（W8 软件壳）

> 假数据 / 云端单测 **不得** 记为实机 PASS。未测项写 `NOT_RUN`。

| 字段 | 值 |
|---|---|
| 分支 / commit | |
| 模型 / SHA256 | |
| 相机合同 | ZED_TOPIC_SUBSCRIBE_ONLY / NOT_START_SDK |
| 材质路线 | A 不透明基线 / B 透明待定 |
| 记录人 / 日期 | |

## 状态标签（逐项）

| 标签 | 结果 | 证据路径 |
|---|---|---|
| SOURCE_ONLY | | |
| SOFTWARE_CHECKED | | |
| LIVE_CAMERA_OBSERVED | NOT_RUN | |
| CAMERA_POSITION_MEASURED | NOT_RUN | |
| TARGET_TRANSFORM_SOFTWARE_CHECKED | | |
| PEER_CALIBRATION_NOT_RUN | NOT_RUN | |

## 窗口 A 链路

| 检查 | 结果 | 备注 |
|---|---|---|
| RGB/Depth/Info 话题与编码 | NOT_RUN | |
| `source_kind=LIVE_CAMERA`（非 SYNTHETIC） | NOT_RUN | |
| detections_2d 有输出或空健康 | NOT_RUN | |
| objects 无效项 NaN+reason | NOT_RUN | |

## 窗口 B 精度 / 挪位

| 指标 | 门槛（建议） | 结果 |
|---|---|---|
| 检测率 | ≥90% | NOT_RUN |
| 有效三维率 | ≥90%（分母含失败） | NOT_RUN |
| 更新时效 95% | ≤0.5s | NOT_RUN |
| 三维误差 median/p95 | ≤20/30 mm | NOT_RUN |
| 透明路线 B | 单列 | NOT_RUN |

## 失败与边界

无目标、DEPTH_UNPAIRED、MASK_DEGRADED、错内参、缺 TF、过期——均不得伪造有效点。
