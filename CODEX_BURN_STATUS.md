# DG-202611 本轮现状、缺口与执行记录

核对日期：2026-10-14。范围：本地阅读、独立脚本草稿、离线验证。没有连接机器人、部署、启动 ROS 业务节点、发布话题或调用执行器服务。

## 1. 现状与证据边界

已阅读 `README.md`、`NAVIGATION_INTEGRATION_NEXT.md`、`PREHARDWARE_CLOSURE_REPORT.md`、仓库 `AGENTS.md` 和工作区 `DG-202611_后续执行小计划.md`；核对 ROS2 实践优先、安全运动边界技能、好测试规范及现有预检/采集入口。知识库检索没有高相关结果，停止继续检索。

- README 描述底盘、导航、三模型、视觉、UI 和云连接的工程能力，不是本轮实机验收证明。
- 2026-09-03 的预硬件报告标记 COMPLETE，并报告历史测试、构建结果。本轮未复跑，不能沿用为当前全部功能通过。
- 导航后续文档仍列出运行话题契约、回放、候选交接、速度所有权、安全恢复与实机数据等缺口。“无软件工作剩余”仅代表预硬件报告当时范围，不代表项目闭环完成。
- 2026-09-07 后续小计划报告真实 UWB 数据、回放入口、采集器和部署包已准备，不能据此认定当前目标机已部署或 MODEL-1 已消费。
- 补充查看 `docs/dg202611/FINAL_EVIDENCE_INDEX.md`：2026-09-13 索引区分真实事件采集/跨板业务接收与待补的 MODEL-1 UWB、MODEL-3 闭环和实测毫米波证据。已有真实数据不能一律说成未验证，部分链路也不能等同完整系统通过。本轮未重新校验索引中所有原始文件。
- 工作树存在未跟踪的视觉包、视觉文档、视觉证据和 artifacts，本轮不改、不删除、不纳入交付结论。原地图、路线、配置、旧报告及 v2 文档保持不动。

本轮为 `LOCAL_ONLY`，没有 `TARGET_WRITTEN`、`TARGET_VERIFIED` 或 `REMOTE_VERIFIED` 证据。旧会话中的机器人状态只作背景，不能当作当前运行事实。

## 2. 缺口与优先级

| 优先级 | 缺口 | 当前判断与下一步 |
| --- | --- | --- |
| P0 | 导航/三模型运行话题契约未在本轮确认 | 检查类型、生产者、消费者与 QoS 原始信息，再采集消息时间、frame 与真实消费状态。 |
| P0 | 运动控制所有权及恢复安全交还 | 待核对不代表仲裁器不存在。当前有仲裁器代码及相关修改记录，但本轮不验证实机所有权、制动或交还，不启用主动感知/巡逻。 |
| P1 | UWB→MODEL-1、MODEL-2→MODEL-3 真实消费与 MODEL-3 闭环 | 保存接受、拒绝、降级、恢复、超时、人工接管的真实记录，合成场景不能替代。 |
| P1 | 可追溯评价指标 | 使用现有采集器和评价器保留原始日志、参数、时间、场景与哈希；缺少位置真值或完整试验记录时不填指标。 |
| P2 | 辅助传感器标定/融合消融与方案书 v3 | 根据实际设备/原始记录确认，不沿用旧文档“等待到货”作为当前事实；保留 v2 和备份，结果齐备后再制作副本。 |

选第一项 P0：它是后续真实消费/恢复验证的前置输入，可用只读脚本推进，不启动机器人、不改算法。安全所有权仍为并列 P0，不以本次查询代替其验收。

## 3. 本轮脚本草稿

新增 `scripts/audit_navigation_topic_contracts.py`，只依赖 Python 标准库，不加入默认 launch，不修改模型、Nav2、底盘或配置。

- 默认/`--plan`：输出六个话题的核对计划，不执行 ROS 命令。
- `--capture`：只对已运行的 ROS 图执行固定的 `ros2 topic info <topic> --verbose`，逐条超时，不用 shell、不启动业务节点、不设置参数、不发布消息或目标。ROS CLI 自身可能使用本地发现守护进程，不等于启动机器人功能。
- 检查 `/scan`、`/odom`、`/amcl_pose` 和三个质量话题。预期类型依据当前 `navigation_health_node.py` 订阅；话题被 remap 时报告差异，不修改配置。
- 保存查询命令、UTC 时间、原始 stdout/stderr、退出码、端点计数、ROS 环境和脚本 SHA-256。原始输出保留 QoS 供人工核对。
- 无 ROS、超时、解析失败、类型不符、缺少发布/订阅端均不判通过。输出文件独占创建，拒绝覆盖证据。
- 无订阅端可能只是消费者尚未运行，不等于传感器坏了。发现匹配不等于持续传数据，也不能证明订阅者身份正确。

退出码：计划为 0；采集六项发现匹配为 0；契约缺口为 1；无 ROS/参数或输出路径错误为 2。始终保留 `hardware_acceptance=NOT_PROVEN`；QoS 兼容、消息新鲜度、frame/时间戳均为未评价。

## 4. 本地如何验证

仓库根目录 PowerShell，无需 ROS2：

```powershell
python -c "from pathlib import Path; file=Path('scripts/audit_navigation_topic_contracts.py'); compile(file.read_text(encoding='utf-8'), str(file), 'exec')"
python scripts/audit_navigation_topic_contracts.py --plan
python scripts/audit_navigation_topic_contracts.py --help
```

预期语法无报错；计划为 `PLAN_ONLY`、六条固定查询、observations 为空、实机状态为 `NOT_PROVEN`。

当前 Windows 未发现 `ros2`，可验证缺失依赖不会误判：

```powershell
python scripts/audit_navigation_topic_contracts.py --capture
$LASTEXITCODE
```

预期 `ROS2_UNAVAILABLE`、退出码 2，不安装或启动任何组件。如果以后此电脑已有 ROS2，这会改为只读查询当前 ROS 图，不再是缺失依赖验证。

可指定 `--output <新文件.json>`，上级目录必须存在，已有文件会被拒绝。计划文件不是实机证据。非法超时如 `--timeout nan` 应被拒绝。

## 5. 后续只读 ROS2 验收（本轮未执行）

仅在现场人员已独立启动并确认安全的目标环境中，从实际仓库根目录执行。这里不提供启动/运动命令，不运行现有全量 preflight，因为它包含构建和测试，并非本轮只读任务。

```bash
python3 scripts/audit_navigation_topic_contracts.py --capture --timeout 5 \
  --output navigation_topic_contracts_$(date +%Y%m%d_%H%M%S).json
```

预期六项 `DISCOVERY_MATCH`；人工检查原始端点中生产者/消费者身份、reliability、durability 等 QoS。再使用现有采集器获取连续消息、时间戳、frame、MODEL-1 UWB 消费及 MODEL-3 恢复记录。端点计数不能证明 QoS 兼容、TF 正确、定位精度、避障或安全交还。

失败时保留 JSON，核对具体话题的消费者、remap、DDS domain 和发现环境；不得为让报告通过而启动底盘、导航或巡逻。收集真实节点/参数/日志后再做最小修复。

## 6. 本轮验证结果

2026-10-14 已实际执行下列本地检查：

| 检查 | 实际结果 | 证明范围 |
| --- | --- | --- |
| Python `compile()` | 无语法错误 | 本地解释器可解析，不证明目标 ROS2 环境可运行 |
| 默认入口、显式 `--plan`、`--help` | 正常退出；计划六项、无 observations、实机状态仍为 NOT_PROVEN | 本地 CLI/计划生成行为 |
| 当前无 ROS2 时执行 `--capture` | ROS2_UNAVAILABLE，退出码 2 | 缺失依赖不会误判通过；没有执行 ROS 查询 |
| 超时值 nan、inf、0、-1、61 | 均拒绝，退出码 2 | 非法参数不会进入采集 |
| 指定新输出文件 | JSON 可解析、LF 换行、脚本哈希一致 | 本地证据输出格式 |
| 指定已有证据文件 | 拒绝写入，原字节不变 | 不覆盖历史证据 |
| 受版本控制文件差异 | 无改动，diff 格式检查无错误 | 原有文件未修改；本轮只新增本文和脚本 |

本地验证使用独立临时文件，验证后已清理。第一次组合命令在验证结果全部输出后遇到工具总超时，随后单独重跑差异检查成功；不把命令总超时当作整组执行成功。

ROS2 verbose 输出解析分支尚未在真实 ROS2 CLI 上运行；QoS、连续消息、TF、三模型消费、恢复、性能和实机运动均未验证。没有新增测试文件、Mock/Fake 或模拟 ROS 启动，不运行全仓库 pytest/colcon test，不把静态检查说成实机通过。

DONE
