# 2026-10-15 本地离线验证记录

验证范围：LOCAL_ONLY。无机器人连接、部署、运动或远端请求。本记录中的人工验收模板没有被计为测试通过。

## 一、环境

| 项目 | 实际环境 |
| --- | --- |
| 系统 | Windows，PowerShell |
| Python | 3.14.4，C:/Python314/python.exe |
| pytest | 9.1.1 |
| NumPy | 2.4.4 |
| Pillow | 11.3.0 |
| PyYAML | 6.0.3 |
| FastAPI | 0.115.6 |
| Pydantic | 2.13.4 |
| httpx | 0.28.1 |

以上是本轮离线环境，不是 Jetson 部署版本。没有安装、升级或卸载依赖。比较程序曾在另一工具的子进程中因用户依赖搜索路径不同而无法导入 NumPy；最终使用上述 Python 在正常 PowerShell 环境重跑成功，没有更改系统环境。

## 二、定向测试

从仓库根目录执行：

~~~text
python -m pytest -q -p no:cacheprovider src/ylhb_mobile_bridge/test/test_map_snapshot.py src/ylhb_base/test/test_position_error_evaluator.py src/ylhb_base/test/test_relocalization_evaluator.py src/ylhb_base/test/test_feature_repeatability_evaluator.py src/ylhb_base/test/test_teacher_requirements_evaluator.py
~~~

结果：33 passed，退出码 0。重构前原有定向基线为 22 passed；新增行为测试在旧实现上先得到 33 passed，再对重构后的实现运行相同集合。

保留 8 条 Pillow 弃用警告，来自 Image.fromarray 的显式 mode 参数；原始实现已有同类警告。本轮没有抑制测试警告、修改图像库或用减少断言换通过。

## 三、前后实现对照

对照脚本：[compare_offline_refactor.py](compare_offline_refactor.py)。基线源码标识：

~~~text
b4697c8c08480c9f8fe2e0452fb130f888f75880
~~~

复现命令：

~~~text
python docs/validation/compare_offline_refactor.py --reference b4697c8c08480c9f8fe2e0452fb130f888f75880
~~~

默认 reference 为 HEAD，仅在 HEAD 仍是重构前版本时可直接使用；提交后应使用记录中的基线标识。脚本从该 Git 对象读取原文件，在内存中加载两版实现，临时 CSV 使用系统临时目录，无 ROS 和网络操作。

| 对照对象 | 输入组数 | 结果 |
| --- | --- | --- |
| 地图快照 | 150 | 元数据与 PNG/Base64 完全一致 |
| 位置批次 | 120 | 每批同时比较水平和高程指标 |
| 位置 CSV | 10 | 正常、空白、非法、缺字段、非有限数等结果或异常类型一致 |
| 重定位批次 | 120 | 分类、成功率、耗时和失败原因一致 |
| 重定位 CSV | 6 | 有效事件与行处理结果一致 |
| 无效地图尺寸 | 3 | 异常类型一致，不制造像素 |

总计 409 组，固定随机种子 20261015，退出码 0。这是有限的回归对照，不是穷尽证明；异常只比较类型，不把警告文字当契约；对照没有证明实机、真实数据质量或性能。

## 四、已复现的接口阻塞

单独运行：

~~~text
python -m pytest -q -p no:cacheprovider src/ylhb_mobile_bridge/test/test_schemas.py
~~~

结果：收集阶段失败，退出码 2，未执行该文件中的测试。错误为 PydanticUserError：regex 已移除，应使用 pattern；触发点是 schemas.py 的 MappingSaveRequest 字段声明。

随后从重构前 Git 对象读取原版 schemas.py，在同一环境直接导入，也出现同样错误。因此这是已有的环境兼容问题，不是本轮数据处理重构引入。没有改 schemas、降级 Pydantic、安装 ROS 或迁移整个接口层。HTTP/WebSocket 实际运行仍未验证。

## 五、静态核对

- 已用 AST 核对本地及平台共 41 个路由声明，包括 WebSocket，均能在接口契约中找到。
- 已比较三个修改实现模块的全部公开函数参数 AST，签名与基线一致。
- 本轮 14 份 Markdown 文档通过 UTF-8 解码、无替换字符/空字节、结尾换行和无尾随空格检查。
- 41 个本地 Markdown 链接均能解析到现有文件或目录。
- 7 个修改或新增 Python 文件通过 AST 语法与无尾随空格检查，不生成或启动 ROS 节点。
- git diff --check 退出码 0。Git 提示部分原有 CRLF 文件未来会按仓库规则规范化为 LF，这不是测试失败；未为此修改全局 Git 配置。

## 六、未执行项目

未运行全仓库 pytest 或 colcon test，未构建 Jetson 包，未启动或改变 ROS 节点，未检查真实 TF、传感器、导航、巡逻和云上传。未执行安装器、预检、激活、服务重启或任何运动命令。

本地通过仅覆盖本轮所列数据处理行为。目标机、远端和现场任务仍需分别记录，不能把本报告作为整车验收。
