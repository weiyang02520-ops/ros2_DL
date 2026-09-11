# 北斗短报文实机全面扫描记录（2026-09-11）

## 结论

本次对机器人当前系统、源码仓库、Git 全历史、系统服务、ROS 2 图、串口设备、历史备份和本机 AI 会话记录进行了只读扫描。能够确认的北斗相关能力是 **WTRTK980 GNSS/RTK 定位**；没有发现可以发送或接收北斗短报文的节点、话题、服务、协议解析器或启动入口。

当前状态必须记为：

```text
GNSS/RTK positioning: PRESENT
BeiDou short-message terminal: NOT IDENTIFIED
Short-message send/receive code: NOT FOUND
Outdoor end-to-end verification: NOT RUN
```

这不等于证明学长从未写过代码，只表示代码不在本次可访问的机器人系统、仓库历史或备份中，或者学长所说的是现有 RTK 代码。

## 扫描范围

- `/home/nvidia/ros2_DL` 当前工作树、远端和全部 Git 历史；
- `/home/nvidia/ros2_ws`；
- `/home/nvidia/PC_WJ/Intelligent-Power-Inspection`；
- `/home/nvidia/PC_WJ/ylhb-robot-mobile`；
- `/home/nvidia/dg202611_ws*` 及其源码副本；
- 2026-09-04、09-05、09-06 的基线、控制器、回滚、源码和完整运行时备份；
- `/etc/systemd/system`、运行进程、ROS 2 节点/话题/服务；
- `/root`、`/opt`、`/usr/local`、`/srv` 中的相关文件名和文本；
- USB 设备、udev 别名及 `/dev/ttyACM*` 的只读输出；
- Shell 历史及机器人本机可访问的 AI 会话记录。

扫描期间没有修改 `/home/nvidia/ros2_DL`，没有发送运动命令，也没有向串口发送配置指令。

2026-09-11 14:50 的复核扫描还确认：机器人运行的是 Jetson Orin Nano、Ubuntu 22.04；`dg202611-models.service` 与 `ylhb-mobile-bridge.service` 均为 active。扫描时基础 bringup 未启动，因此 `/gps/fix` 和 `/gps/rtk_status` 都只有订阅者、没有发布者，这只能说明当时 GNSS 节点未启动，不能当作硬件故障。

原始扫描报告保存在 Windows：

```text
artifacts/robot_scans/robot_full_scan_20260911_145108.txt
SHA256 AE63C183E98BC1BD63E64964974016F0535B9DC1EA63B53A598AAF30B1A95CF9

artifacts/robot_scans/beidou_deep_scan_20260911_145243.txt
SHA256 414E960A5C6A4B2F2D9FFC14FF67105622587A67F390E80E9DEDFF0E207405D9
```

## 已确认的真实链路

### WTRTK980 定位链路

`wtrtk980_nmea_node.cpp` 的行为是：

1. 只读打开 `/dev/rtk_4g`；
2. 解析 NMEA GGA；
3. 发布 `/gps/fix`、`/gps/nmea_sentence`、`/gps/rtk_status`；
4. 不包含短报文发送、接收、确认或重试逻辑。

### AirM2M 设备

机器人识别到 AirM2M 复合 USB 设备和多个 CDC ACM 串口。其中一个端口输出 NMEA，另一个端口显示蜂窝网络/LuatOS 状态。该证据支持“RTK/GNSS + 4G/NTRIP”链路，不能证明存在北斗短报文终端。

## 为什么不能直接补一段软件

北斗短报文能力首先取决于模块本身是否支持卫星短报文、是否开通服务、是否有对应天线和账号/卡号，然后才是串口协议和上层程序。普通 GNSS/RTK 板、4G 模块、NTRIP 链路不能通过修改 Python 或 ROS 2 代码变成北斗短报文终端。

## 唯一需要外部补齐的信息

向学长确认：

> 学长，已经写好的北斗短报文代码具体在哪个路径，用什么命令启动？对应的北斗模块型号、串口设备、ROS 2 节点和话题分别是什么？室外测试时消息发到哪个接收端？

向商家确认：

> 当前购买的北斗模块是否原生支持北斗短报文收发？请提供完整型号、短报文协议手册、串口参数、天线要求、服务开通方式、发送频率/长度限制和配套接收端说明。

拿到型号和协议后，代码工作包括协议适配、ROS 2 收发接口、发送队列、回执/超时/重试、日志留证和室外端到端验证。在此之前不能把占位文件 `scripts/beidou_short_message_interface.py` 当作实现。
