# 全局培育能力审计

更新：2026-09-10。当前范围为 `create_hif_training_produce` / `hif-report3/2`。**可按版本化配置训练完整 HIF 两剧本；选拔三场 → 本战两轮已经接通并验证恢复。** 详细报告、机制冲突取舍与使用方法以 [Report 3 RL-ready 交付](HIF_REPORT3_RL_READY.md) 为准。

## 当前执行能力

| 能力 | 证据与边界 |
|---|---|
| 事件、课堂与外出 | Report 3 的 92 事件/72 选项与本地一致；费用/眠气头部、来源池、自选、失败概率单位和合法性已修正。见 [事件专项](HIF_REPORT3_EVENTS.md) |
| 支援技能、支援事件与普通 P 道具 | 基于编成/等级/前置的解锁和实际触发；511 个支援事件的两剧本×三计划共 3066 路径有实际结果断言，见 [闭包说明](HIF_EVENT_CLOSURE.md) |
| HIF 自定义 P 道具 | 180 配置、171 进化边、四触发、下一场/永久效果、自选操作、计数与继承。见 [特殊道具](HIF_REPORT3_PITEMS.md) |
| HIF 回忆 | 105/105 自动编译并实际安装原生监听器；13 项专项覆盖计数、身份、区域、首回合及两剧本入场。旧 0/105 结论已失效 |
| 应援棒 | 六组主数据权重，原生 RNG/插入；上游文件保持原字节；显式配置覆盖不混用旧权重 |
| 公开课、特别指导、咨询、中场 | 默认日程、30/50 P、主副成长、特殊服务、报告价表、独立次数、目标选择与消费已实现；R2 无自动回体 |
| 全局恢复 | `snapshot()` / `restore_snapshot()` 覆盖公共决策边界与 RNG、库存、事件/道具/支援计数；不序列化 Python 回调调用栈 |
| 选拔交接 | 完整牌实例/定制、被动计数、支援、成长面板、剩余重抽等继承；P 点、饮料与当前 HP 按本战初始化 |
| 考试与倍率 | 局内由 pinned gktools 执行；默认五场课程或完整自定义，包含研究公式、NPC 身份、各场奖励及评价，见 [课程说明](HIF_FIVE_EXAM_COURSES.md) |

## 已知模型范围

未知奖励池成员/权重、事件发生率、SP 联合分布、部分商店刷新细节与取整顺序采用显式规划配置。25% StepSkip 已实现为 opt-in 规划动作，默认 HIF 菜单不开放。最终回忆生成、票据再生成和资格检查已实现；公平搜索条件采样仍属于 RL 搜索层能力。完整差异见 [精度与模型差异清单](HIF_FULL_PRODUCE_GAPS.md)，不要求追加实机截图才能训练。

旧 `create_training_produce`、`make_produce_env` 保留兼容；使用旧入口的实验不会自动获得新版日程和经济规则。未知执行机制明确报错，不转换为正常低分；静态目录收录、执行桥接、专项测试与实机校验分别说明。

## 当前验收

- [上一版回归 XML](../build/hif_report3/pytest.xml)：`hif-report3/1` 为 **310 passed，0 failures**。本版新增机制的最终验收见 [完整交付](HIF_REPORT3_RL_READY.md#验证产物)，不累加重复专项计数。
- [3＋2 固定倍率示例](../build/hif_report3/demo/manifest.json)：两阶段全局快照恢复一致、五场考试快照恢复分数一致。
- [3＋2 研究换算示例](../build/hif_report3/research_formula/manifest.json)：每场实际入场三维/star → 研究模型 → golden，完整正常终止。回合顺序、零对手、全达标明确标为合成课程。
- [报告3原包](research/imports/hif_events_rl_report3_2026-09-09/README.md)：5 项文件 SHA-256 验证，原证据保留。

入口：[使用指南](PRODUCE_USAGE_GUIDE.md)、[Agent 文档](../AGENT_ENTRY.md)、[完整交付矩阵](HIF_REPORT3_RL_READY.md)。验证脚本不启动 RL 训练、游戏或 Maa。
