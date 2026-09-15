# 实况被动结构绑定与兼容迁移

新入口 `facts.exam_passive_version = observed("arena-passive/2")` 采用机制校验与真实来源链校验；不依赖六个固定 enchant ID。
v1、arena-live/1、arena-session/1、arena-issues/1、奖励／咨询接口继续可用。

## 字段

`ExamEnchantState` 的字段保持不变：state_id、exam_id、enchant_id、source、source_level、remaining_turns、remaining_count、applied_turn、applied_phase、last_fired_turn、bound_card_instance_id、once_per_turn。
仍须提供 exam_counter_semantics=arena-exam-counters/1 和 observed exam_scheduled_effects。未知不填零；没有状态要提供有证据的空数组。

最小迁移：复制 [live_passive_minimal.json](examples/live_passive_minimal.json)，仅将 exam_passive_version 改为 arena-passive/2；完整示例见 [live_passive_generic.json](examples/live_passive_generic.json)。示例都是合成数据，不是新实机证据。

## 支持判断

1. 根据来源实例找到真实卡牌变体、当前道具或已装备回忆能力及等级。
2. 追踪来源定义 → 效果 → 附魔 → 子效果，核对该来源是否确实产生目标 enchant。
3. 按 phase、fieldStatus、effectType、search 结构检查能力；新 ID 或不同数值不需要增加白名单。
4. 从来源应用效果读取最大持续时间／次数，核对观察中的剩余值和最近触发时点。不会从主数据推算“今天还剩几次”。
5. 直接建立 TriggeredEnchant；不执行开场效果，不抽牌，不消费资源。

当前可绑定的机制族包括基础资源增益、好调／绝好调、好印象、やる気、基础得分、体力增减、抽牌、追加行动、移牌以及少量持续修饰；时机支持考试／回合开始、回合结束、出牌时／后。
确切集合以 [capabilities.py](../gakumas_arena/content/capabilities.py) 的 LIVE_EFFECTS/LIVE_PHASES 和测试为准。这是**按机制的有限支持集**，不是宣称所有注册效果已经完成实况绑定。

仍明确返回 unsupported：StartPlay 的有歧义时序、需额外历史语义的触发、未绑定的预约／再演／卡绑定／每回合一次、同一来源的多次叠加实例，以及超过编码容量的状态。
来源或动态字段缺失为 observation；矛盾实例、跨考试状态和不可能的次数为 contract；submitted/uncertain 仍由原事务恢复流程处理为 resolution。
v2 不放宽基本考试局限：目前官方实况考试仍为 HIF センス；自创剧本执行通过 ContentSession，不能代替游戏观察。

## 编码版本

| 观察配置 | 编码版本 | 被动布局 |
|---|---|---|
| arena-passive/1 或旧空状态契约 | arena-exam-observed/2 | 保留六个 ID 的旧特征空间 |
| arena-passive/2 | arena-exam-observed/3 | 32 个被动槽、128 个效果槽，按机制结构编码 |

v3 保留原 global/action 特征，增加通用 passive_features、passive_effect_features 及各自 known_mask。
被动行包含次数、剩余时间、时机和条件；效果行包含父状态槽位、效果顺序、effectType、数值、次数和选择模式。复杂筛选定义还有固定长度结构摘要。
该摘要用于区分定义，不是可逆的完整规则描述，也不证明策略已经学会该筛选含义；完整定义仍在主数据库／内容包。
同类效果的新 ID 不增加张量维度。超容量或未知编码机制直接拒绝，绝不静默截断。
禁止硬编码维度；读取 manifest。当前测试样例为 32×77 和 128×133，具体以 manifest 为准。

训练复用相同入口：`ExamVisibilityWrapper(env, known_fields, structural_passives=True)`。
旧 checkpoint 不能静默当作 v3 模型使用；adapter/policy 必须验证版本与 manifest 摘要。
旧快照恢复仍恢复原命令，不会在恢复途中自动切换配置版本或产生新提案。

若宿主显式把自创内容仓库注入 live backend，masterdata_revision 附加 `:content:<digest>`，防止把修改过的目录冒充固定官方主数据版本。
这只用于本地合成联调，不会把自创卡牌安装到实际游戏中。
