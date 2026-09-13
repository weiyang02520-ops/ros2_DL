# DG-202611 最终证据索引

**更新时间**：2026-09-13<br>
**规则**：`READY`表示已有文件或已完成静态验证；`PENDING`表示必须在后续设备或ROS 2环境中补齐；`NOT_CLAIMED`表示不能作为正式指标。

| 编号 | 证据 | 来源 | 状态 | 用途 |
|---|---|---|---|---|
| E01 | 三模型核心测试 | `src/ylhb_base/test/` | READY | 保护确定性逻辑，不代表实机 |
| E02 | UWB真实原始日志和CSV | `src/ylhb_base/data/uwb/20260905/`、`evidence/uwb/20260905/` | READY | 回放、质量门控、3物理源/6逻辑接口 |
| E03 | RDK事件相机本地长测 | RDK历史记录目录及其哈希清单 | 历史READY/本次PENDING | 历史EVS/APS采集；本次设备尚未识别 |
| E04 | RDK↔NVIDIA DDS基础发现 | 两侧`/dg/link_test`双向收发 | READY（基础发现）/PENDING（业务话题） | 基础跨板连通；事件业务话题持续接收仍待完成 |
| E05 | 事件特征和质量到达Jetson | `/dg/event_camera/features`、`/dg/event_camera/quality` | PENDING | MODEL-2观察调用 |
| E06 | 传输时间审计 | `/dg/auxiliary/transport_quality` | READY（代码）/PENDING（实机） | 新鲜度和延迟记录 |
| E07 | UWB进入MODEL-1 | `/dg/uwb/quality`、`/dg/fusion/status` | PENDING | `UWB_AIDED`消费证据 |
| E08 | 毫米波真实协议和数据 | 上位机截图、原始串口、规范化CSV | PENDING | MODEL-2观察回放 |
| E09 | MODEL-3完整状态闭环 | 真实ROS 2日志和状态时间线 | PENDING | 重定位、候选拒绝、恢复 |
| E10 | 用户现场实机运动 | 现场日志、照片、rosbag | PENDING | 低速受控验证 |
| E11 | 双板现场只读核验 | `docs/dg202611/LIVE_INTEGRATION_AUDIT_20260913.md` | READY | 部署版本、服务、输入缺口和时钟状态 |
| E12 | 最终验收命令清单 | `docs/dg202611/FINAL_ACCEPTANCE_COMMANDS_20260913.md` | READY | 现场按顺序执行静态、回放和实机验收 |

## 现有文件清单

- `docs/dg202611/UWB_MEASURED_RESULTS.md`
- `docs/dg202611/RDK_HVS_BRIDGE_STATUS_20260912.md`
- `docs/dg202611/AUXILIARY_TRANSPORT_ONLY.md`
- `docs/dg202611/FINAL_ACCEPTANCE_COMMANDS_20260913.md`
- `src/ylhb_base/data/uwb/20260905/README.md`
- `src/dg_hvs_bridge/README.md`

## 归档要求

每次现场测试至少保存：

```text
测试时间
设备和账号（不含密码）
Git提交号
启动参数
ROS_DOMAIN_ID / RMW_IMPLEMENTATION
话题类型、QoS、频率
TF和frame_id
rosbag或原始CSV
节点日志
文件SHA-256
现场照片或截图
```

未经现场数据补齐的`PENDING`项目不能改为`READY`，也不能用于方案书正式指标。
