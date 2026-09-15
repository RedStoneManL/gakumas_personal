# HIF 回忆、P 道具与卡片触发状态交付

2026-09-08。在 `codex/arena-live-bridge`、基点 `ef2402958547b2050e873841b9ff5066a895b1a9`
继续，保留此前未提交成果。本阶段只修改 Arena；根目录和 Maa 资料只读，未操作游戏、管理器、PAUSE、
防休眠或 runs，未训练 RL、优化通关率、提交或推送。

## 先交给 adapter 的入口

- [字段、证据分类与计数契约](LIVE_PASSIVE_CONTRACT.md)，先于代码实现写出，再按实际支持范围补齐。
- [最小 synthetic JSON](examples/live_passive_minimal.json)，公共类型 `ExamEnchantState`。
- [原始历史片段摘录](examples/live_passive_evidence.json)，含源文件 SHA256 与 JSON pointer，明确不能初始化整帧。
- [完整 synthetic 恢复对话](examples/live_passive_recovery.json)。
- 公共 `classify_issue` / `classify_issues` / `LiveIssue`，可直接序列化为 JSON。
- [被动条目 schema](schemas/arena-exam-enchant-state-v1.json)、[缺项分类 schema](schemas/arena-issues-v1.json)。

## 实现与范围

| 代码入口 | 本阶段行为 |
|---|---|
| `gakumas_arena/live/passive.py` | 六种已就绪场上触发的绝对观察绑定；校验主数据链、能力等级/来源实例、作用域、次数和时点；不执行效果 |
| `gakumas_rl/simulation/exam/passive_catalog.py` | 固定四个 HIF 回忆 enc01、願いの力 enc01、勇気の標基础版 enc01；记录来源、触发器及确切结果效果 |
| `gakumas_arena/live/exam.py` | 基础字段与被动问题聚合；复用既有合法性/费用；追加回合余额校验，不再将 turn≤max+余额作为条件 |
| `gakumas_arena/live/issues.py` | observation / unsupported / resolution / contract 分类；支持既有 report/decision、MissingFields、协议/结构异常 |
| `gakumas_rl/simulation/exam/observed_encoding.py` | v2 增加6×8被动特征与已知掩码；实况和训练 wrapper 同入口；原特征顺序保持 |
| `scripts/audit_passive_evidence.py` | 只读任务列出的资料，校验 adapter 索引的哈希/片段，提取原文；不读取 runs 或做 OCR |
| `scripts/demo_live_passive.py` | synthetic 非空回忆 → submitted/uncertain 保存 → 新实例恢复原命令 → 手工填写确认快照 → 去重 |

记账语义：plays_used 是完成的卡使用数（自动完整使用计入，仅效果重复不计入）；plays_remaining 是
玩家行动窗，两者不能从命令条数倒算。extra_turns 是尚未进入的追加回合，追加回合页面需累计确认
extra_turns_granted 交叉核验；基础回合该累计字段可 unknown。应用 phase 由 Arena 转成内部衰减标记。
此处明确的是引擎字段语义，没有新做再演组合的实机验证。

活跃列表不根据持有的回忆/P 道具自动生成；完整证据才可声明空列表或无限次数。
来源与现有装备/卡实例匹配，已知来源矛盾归 contract，来源尚未知归 observation。
重复 state_id 或重复唯一 HIF 能力不叠加；跨考试残留状态被拒绝，新考试重新绑定。
卡片来源的场上状态与卡自身附魔分开，集中/好调的基础说明也不归入 enchant。

聚合覆盖基本11个数值缺项、四个结构事实缺项及全部被动条目的结构/来源/时点问题；
场景/版本/exam_id/stage 先检查，旧逐卡费用/规则检查仍可能首错即停，未声称全部缺项可一次穷尽。
遇到 unsupported，adapter 保存现有材料并停止同页重截；resolution 优先解决原 submitted/uncertain 命令。

## 版本和验证

wire `arena-live/1`、snapshot `arena-session/1`、规则 `arena-rules/2`、规划编码 `arena-planning-observed/2` 保持。
新增 profile `arena-passive/1`、计数说明 `arena-exam-counters/1`、分类 `arena-issues/1`。
考试编码改为 **arena-exam-observed/2**，新增被动张量；v1 模型必须明确拒绝或重新导出，不能补零伪装兼容。
旧空状态帧仍可调用新 backend，非空状态需补 profile、计数语义和预约完整列表。
本地 master 固定 `571dbb62601e78998cddeacdbce3ea1bc672d7fc`，未更新数据或改 Maa Python 环境。

在 Arena 仓库运行：

```powershell
.venv/Scripts/python.exe scripts/audit_passive_evidence.py
.venv/Scripts/python.exe scripts/demo_live_passive.py
.venv/Scripts/python.exe scripts/demo_live_exam.py
.venv/Scripts/python.exe scripts/demo_live_exam_choices.py
.venv/Scripts/python.exe scripts/demo_live_bridge.py
.venv/Scripts/python.exe scripts/export_live_schema.py
.venv/Scripts/python.exe -m pytest tests -q -rs
```

末次完整回归：**505 passed / 3 skipped，51.10秒**，无 xfail。
两项跳过因为没有可选 SB3 依赖，另一项因为该 seed 没有考前准备动作；缺 torch/fastapi 的可选
训练/API 模块仍按原配置不收集，本结果不代表这些可选功能已验收。
奖励/咨询、card/end_turn/drink、单卡 search/discard、原命令恢复/去重与九段录像回归均通过。
本阶段模块 Ruff、`git diff --check`、交付链接/示例类型/快照校验通过。

示例 v2 manifest SHA256：`757f60675e7b4520c1e133cf57479ad2669d2f5ea3c3de7e10285eb1e270783d`，
实际接入仍以运行环境输出的完整 manifest 为准。

四个示例及 schema 导出已成功；wire 和 session schema 导出前后的 SHA256 分别保持完全一致。
真实摘录验证了原文件哈希与 pointer，仍标记 `ready_for_engine_initialization=false`。
新测试覆盖六种实际证据指向的定义绑定、P 道具阈值与主动卡条件、缺失次数/来源、未知效果、重复状态、
作用域与计时冲突、计数分离、训练/实况掩码一致、恢复原命令及确认去重。测试禁止 live 调用
reset/step/dispatch/apply_effect/draw，未把随机模拟结果当实际回执。

## 仍未支持及真正缺少的证据

以下均可在相关当前页面或后续自然出现时局部补齐，不要求重跑整局。

| 缺口 | 已有资料解决了什么 | 仍需资料 / 后续工作 |
|---|---|---|
| 当前装备与来源实例 | 已知四种历史 HIF 能力定义、勇気の標基础版文本；旧/新选中索引分别5/9/2/3和5/9/12/3 | 只核对当前槽位/实例与实际能力等级；历史索引不是永久实例，不重采已有完整静态详情 |
| 活跃触发次数及应用时点 | 已知回忆/该P道具仅1次；状态页有“1回”但分行与跨页 | 当前稳定节点的对应状态剩余次数，或同一考试完整激活/触发历史；可复用已存资料，不由点击条数推算 |
| 来源卡变体 | 願いの力+片段与基础触发语义可确认 | 来源具体副本、当前区域、自定义/成长；状态页名称不足以确认副本，不要求重新读所有同名卡 |
| Turn/追加数/自动使用 | 已核对引擎字段与追加余额规则 | 有缺口时只补考试入口锚点、追加回合获得凭据、当前行动窗；日志断档时不能从“剩余n回合”补造历史 |
| 回合开始抽牌 | 精神統一和センブリソーダ主数据均有此状态；剩1回合页无法唯一确定来源 | 先修正/核验模拟器 StartPlay 相位混用，这是代码缺口；必要时仅对照相关卡/饮料前后到下一回合，不需为该问题循环截图 |
| センブリソーダ持续倍率 | 已定位 `pdrink_00-2-010` 与 `e_effect-exam_lesson_value_multiple-0100-05` | 来源实例和当前剩余/应用时点；还须如实包含其抽牌 enchant，不能只保留倍率让整帧执行 |
| 预约、再演、每回合一次、卡自身附魔及多层叠加 | 现有资料没有目标实例/定时队列/逐次计数完整证明 | 先扩展对应规则与结构；相关状态自然出现时采集详情、来源/目标、次数、fire_turn/last_fired_turn，不为凑覆盖重跑 |

本次支持“观察绑定与绝对状态消费”，未提供被动结果预测或校准完整 seeded 被动分发。
历史 partial/preview 帧仍不能自动执行；完整可执行示例都是 synthetic，不声称实机端到端通过。
