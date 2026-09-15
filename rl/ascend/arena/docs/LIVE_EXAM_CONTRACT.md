# HIF センス考试实况契约

本轮在 `arena-live/1` 的 facts/inventories/Choice 内扩展，不改变奖励/咨询字段。
规则版本仍 `arena-rules/2`；考试编码当前使用 `arena-exam-observed/2`。
2026-09-08 非空被动、来源与计数语义见 [LIVE_PASSIVE_CONTRACT.md](LIVE_PASSIVE_CONTRACT.md)。
2026-09-07：下述出牌、饮料、固定选一张的检索/弃牌和会话恢复均已实现。
样例均标 synthetic，不是实机成功记录；验证和剩余工作见 [考试交付记录](ARENA_EXAM_UPDATE.md)。

## 每次观察的事实

每个字段沿用 `{status:"observed", value:..., evidence:[...]}`；未知为 unknown/null。
零和空数组也必须有证据，缺失不继承上一帧。

| facts 名称 | 类型/单位 | 要求 |
|---|---|---|
| exam_id | 非空字符串 | 每次考试尝试唯一，重试必须换 ID；同一 run 的 revision 继续递增 |
| exam_stage_type | 主数据 ProduceStepType 字符串 | 当前选拔/本战节点，须属于场景考试序列 |
| turn、max_turns、extra_turns | 非负整数/回合；turn 从 1 开始 | max_turns 为基础总回合；extra_turns 是尚未进入的追加回合，追加页另需 extra_turns_granted，见被动契约 |
| plays_used、plays_remaining | 非负整数/次 | 已完成卡使用次数含自动完整使用，不含仅效果重复；remaining 是玩家行动窗，见被动契约 |
| stamina、max_stamina、block | 非负整数/点 | 体力/最大体力/元气，max_stamina > 0 |
| lesson_buff | 非负整数/层 | 集中 |
| parameter_buff、parameter_buff_multiple_per_turn | 非负整数/剩余回合 | 好调、绝好调；折叠图标不能填 0 |
| current_turn_color | vocal/dance/visual | 当前回合属性 |
| exam_effects | 完整效果列表 | 额外持续状态，见下文；基本好调/绝好调由上面的事实单独表达，不重复列入 |
| exam_enchants | 完整场上触发列表 | 支持六种非空状态，具体结构、profile及来源见被动契约；不能漏掉 P 道具/预约 |
| forbidden_card_search_ids | 主数据 ID 数组 | 当前禁用卡的检索限制，空数组表示明确没有 |
| exam_card_state | instance_id → 动态卡状态对象 | 当前手牌，以及已提供其他区域里的卡；不能把“读到 +”当作已知成长 |
| score、target_score | 整数/分；score ≥ 0，target_score > 0 | 可选，用于编码分数差；未读则掩码为 0 |
| score_bonus_multiplier | 非负数/倍 | 可选，当前属性最终倍率，例如 1750% 填 17.5；不再乘局外默认加成 |
| review、aggressive、enthusiastic | 非负整数/层 | 通常可选；遇到对应费用/出牌条件时会成为必需字段 |
| exam_selection | `{effect_id: string}` | search/discard 必需，确切的主数据补选效果；普通 exam 不需要 |

动态卡状态对象明确给 `grow_effect_ids`（考试内追加成长，不含 EntityRef 的自定义）、
`transient_effect_ids`、`transient_trigger_ids`、`card_status_enchant_id`、`play_count_bonus`。
空值分别用 []、[]、[]、""、0。无法映射的临时变化必须 unknown，不能套基础卡。

额外持续状态每项：`effect_id`、`remaining_turns`（或 null 表示不限回合）、
`remaining_count`（或 null）、`applied_turn`。仅可使用实现白名单内的主数据效果。
不支持的效果或出牌条件返回 `arena.exam.effects.<id>` / `arena.exam.trigger.<id>`，不忽略。

当前额外持续效果白名单（以下省略 `ProduceExamEffectType_` 前缀）：
`ExamStaminaConsumptionDown`、`ExamStaminaConsumptionAdd`、`ExamStaminaConsumptionDownFix`、
`ExamStaminaConsumptionAddFix`、`ExamLessonValueMultiple`、`ExamLessonValueMultipleDown`、
`ExamLessonBuffMultiple`、`ExamParameterBuffAdditive`。
每项给出当前剩余回合/次数，不用效果主数据的初始持续时间代填。
例如体力消耗减半可传 `e_effect-exam_stamina_consumption_down-01`，remaining_turns=1、
remaining_count=null、applied_turn=1；这是字段示意，不能当作实机有此状态。

出牌条件只覆盖依赖上述已知资源、行动计数、剩余回合和センス无姿态的条件。
依赖历史次数、未知状态或其他卡检索的出牌条件返回 Inspect。场上被动可按新契约提供非空列表，
卡自身 card_status_enchant 仍暂不支持。预约、再演和其他超出白名单的状态明确 unsupported；
不能为了让示例可执行而省略实机已有效果。
这些要求目前对 exam/search/discard 整帧统一检查，即使只想 end_turn 也不能绕过缺失状态。

## 区域和动作

`hand` 是完整当前手牌，实体数组顺序只描述当前可见顺序。`deck` 在考试页面特指剩余山札多重集，
与规划页面的整副牌组区分；`discard` 是弃牌，`hold` 保留区，`lost` 除外区，`playing` 正在结算的卡。
除 hand 必需 complete 外，其他区域可 unknown/partial；普通出牌不会由它们推算隐藏牌序。
提供 complete 区域时必须有具体实例和完整动态卡状态。同一实例不可同时在两个区域出现。

| pending_decision.kind | Choice.action_type | targets |
|---|---|---|
| exam | card | 一个当前 hand 实体，按 instance_id 绑定，不传内部 uid |
| exam | end_turn | 空 |
| exam | drink | 一个完整 drinks 区域中的当前饮料实例 |
| search / discard | card_select | 一个符合 exam_selection 检索规则的具体卡实例 |

`Choice.parameters` 普通出牌为空，仍核验整个 Choice。UI 可用性和引擎合法性共同决定动作掩码。
相同名字、不同副本/强化/自定义分开；换槽不换 ID。状态变化不从命令推算，只接受更晚的实际绝对快照。
新观察可以是 exam、search/discard 等选择页，不能在一次 card 命令中隐含选择后续目标。

饮料使用复用 `ExamRuntime.can_use_drink`：剩余出牌窗口为零时不可使用；不减少 plays_remaining。
是否消耗饮料只看确认后新快照。当前最多接收场景默认饮料容量，超出返回 `arena.exam.encoder_capacity`；
`drink_overflow` 页面返回 `arena.exam.binding.drink_overflow`。

补选仅支持主数据 `ExamCardMove + Select + 固定 1 张`，目的区为 hand/hold/grave，
不支持随机、动态张数、多选、自身定位或随机排序。目的 grave 对应 discard，其余对应 search。
每个补选必须新 observation_id/revision/decision_id 和独立 command，不再支付出牌费用，
plays_remaining=0 时仍可补选。源区域必须 complete；例如 deck_grave 要求 deck 和 discard 都完整。
合法目标复用引擎检索区域和过滤器，提供全部匹配目标，不按默认价值排序代选。

已验证的两个效果：

- 检索饮料 `pdrink_01-3-012` → `e_effect-exam_card_move-p_card_search-deck_grave-hand-select-1_1`。
- 弃一张手牌 → `e_effect-exam_card_move-p_card_search-hand-1-grave-select-1_1`。

完整往返见 [饮料/选择 JSON](examples/live_exam_choices.json)。其中弃牌是独立合成补选页，
未声称识别或重放了真实的前置出牌动画。

## 支持边界

当前针对 produce-007/008、センス流派、已结算且稳定的玩家决策点。复用 ExamRuntime 的费用、条件和
GakumasExamEnv 的特征编码；不调用 reset/step，不生成实机随机结果。
缺失掩码与 manifest 是公共考试编码的一部分，只有声明支持局部观察的策略可用。
旧完整状态策略及 checkpoint 不能静默接入。

内部 UID 由 run_id / exam_id / instance_id 确定；换槽保持 UID，新考试/重试换 exam_id。
每帧重新装配已知状态，不保留上次考试的 buff、计数或隐藏牌序；revision 始终在 run 内单调递增。
`observation_only` runtime 显式拒绝 reset/step；也不建立随机初始牌组或饮料。
卡效果只用于共用规则/特征识别，后续伤害、抽牌、触发和移牌结果均由 adapter 读回。

模拟侧提供 `card_selection_boundary(runtime, effect_id)` 与 `resolve_card_selection(runtime, effect_id, uid)`，
用于已经处于补选边界的显式枚举/移牌。**旧 seeded simulator 的宏动作尚未改成通用可暂停续跑器**，
仍可能自动完成内部补选；不能用该旧路径冒充本契约的交互轨迹。实况不调用该路径，也不自动执行后续补选。

## 共用考试编码

公共入口在 `gakumas_rl.simulation.exam.observed_encoding`：

```python
from gakumas_rl.simulation.exam.observed_encoding import (
    ExamVisibilityWrapper, encode_exam_observation, exam_encoder_manifest,
)
encoded = encode_exam_observation(env, known_fields)
manifest = exam_encoder_manifest(env)
# 仿真训练普通考试页：相同函数和缺失掩码，不改变底层规则。
wrapped = ExamVisibilityWrapper(env, known_fields)
```

`global`、`action_features` 来自现有 `GakumasExamEnv`；未知位置填 0 并分别配套
`global_known_mask`、`action_features_known_mask`，已知 0 的掩码仍为 1。
`action_mask` 是 UI 与引擎合法性的交集。`decision_kind` 按 exam/search/discard 三维 one-hot；
`exam_context` 依次为绝好调剩余回合、剩余出牌次数，统一按 x/(x+10) 编码，另有同形 known_mask。
补选的旧 card 动作 one-hot 清空，由 decision_kind 区分选目标和出牌，不改变奖励/咨询 taxonomy。
选择页由 backend 先建立目标 ActionView，再调用同一 encoder 的 decision_kind 参数；
wrapper 的默认普通考试页不负责生成暂停/续跑流程。

隐藏抽牌顺序从不编码；未提供的属性、未来 gimmick、分数/目标、局外默认加成都被遮罩。
当前 live 关闭 deck composition 特征；complete 山札只提供多重集与可观察数量，不提供抽牌序。
manifest 包含有序词表、维度、规则与编码版本及 SHA256。跨考试固定场景词表，只改变当前舞台的数值。
此示例为 global=69、动作槽=52、动作宽=252，**接入时读取 manifest，不能硬编码这些数字**。
v2 另有6×8被动特征及缺失掩码，详见被动契约；v1 考试 checkpoint 不静默兼容。
[示例 manifest](examples/live_exam_encoder_manifest.json) 随脚本重新生成。
策略必须声明 `supports_partial_observations=True`。旧 checkpoint 不具备该空间，需按 manifest 校验后接入；
本阶段无 RL 训练，示例 FirstLegalPolicy 只验收接线。

## 使用与公共恢复

```python
from gakumas_arena.live import LiveBackend, LiveSession, Observation, RunSetup

session = LiveSession(policy, LiveBackend())
session.initialize(RunSetup.model_validate(setup_json), Observation.model_validate(observation_json))
decision = session.decide()
# 提交/结果流程沿用 LIVE_CONTRACT.md；持久化由 adapter 完成。
saved_json = session.snapshot().model_dump_json()
restored = LiveSession.restore(saved_json, policy, LiveBackend())
original = restored.pending_command
state = restored.command_state
```

`snapshot()` 返回版本 `arena-session/1` 的 SessionSnapshot，包含 setup、观察、原命令和结果/事件去重账本。
restore 接受该对象、字典或 JSON 字符串，不调用 policy.act、不生成替代命令、不执行输入。
submitted 恢复后 decide 为 Wait；uncertain 为 Inspect。使用 pending_command 的原始 command_id、
observation_id/revision 补交 confirmed 或 not_applied 及较新快照，方可继续消费。
proposed 恢复后返回原提案，但 adapter 仍必须按当前画面验证旧提案是否过期，不能直接重发输入。
已完成、已失效的 command_id 也不得重用，默认采用 UUID；自定义计数器须持久化或使用新的唯一前缀。

快照 SHA256 用于检出损坏，不是来源认证。输入必须是 adapter 自己可信保存的完整账本；截断、版本不符、
命令/观察矛盾均明确拒绝，不猜测恢复。master/rules 仍按原 setup 核验，不静默迁移。
保存文件、崩溃时原子写入、最新 UI 补读由 adapter 负责；本接口不包含日志文件或 UI 执行器。

- [最小观察 JSON](examples/live_exam_minimal.json)
- [出牌与恢复完整 JSON](examples/live_exam_recovery.json)，可运行 `python scripts/demo_live_exam.py`
- [饮料、检索、弃牌完整 JSON](examples/live_exam_choices.json)，可运行 `python scripts/demo_live_exam_choices.py`
- [会话快照 schema](schemas/arena-session-v1.json)
- 结构化 fact.value 类型：[卡状态](schemas/arena-exam-card-state-v1.json)、[持续效果项](schemas/arena-exam-timed-effect-v1.json)、[补选](schemas/arena-exam-selection-v1.json)

所有 schema 由 `python scripts/export_live_schema.py` 从类型生成。既有 arena-live/1 的 wire schema 保持兼容；
facts.value 的结构化语义由上述附加 schema 和本表定义，运行时还核验主数据、区域与合法性。
