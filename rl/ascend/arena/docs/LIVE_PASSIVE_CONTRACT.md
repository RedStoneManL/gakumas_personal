# HIF 实况被动状态契约

> 后续通用版本见 [LIVE_PASSIVE_GENERIC.md](LIVE_PASSIVE_GENERIC.md)：arena-passive/2 按机制与来源链校验，编码 arena-exam-observed/3。本页的 v1 六个 ID 集合保留用于已有 adapter/checkpoint 兼容。

2026-09-08。字段与最小结构先于代码交付，下述六种状态绑定和公共分类现已实现；
验证记录见 [ARENA_PASSIVE_UPDATE.md](ARENA_PASSIVE_UPDATE.md)。
沿用 arena-live/1、arena-session/1、arena-rules/2；考试编码升级 arena-exam-observed/2。
本文件中的历史证据不组成当前完整观察。最小 JSON 的其余事实是 synthetic，不是实机通过记录。

## 证据分类（ID 是候选，装备/副本另证）

下表路径均相对 gakumas 根目录。F=`third_party/MaaGakumasu-hif-dev/tests/fixtures/hif/`，
P=`design/arena-adapter/preparation-evidence.json`。主数据固定 571dbb62601e78998cddeacdbce3ea1bc672d7fc。

| 源文件 / JSON pointer | 可确认与主数据候选 | 来源与字段 | 不能推定的部分 |
|---|---|---|---|
| F/fresh_first_exam_initial_status.json `/pages/0/words/0/text`、`/pages/0/words/3/text`；F/selected_memory_abilities.json `/memory_details/9/top/16/text`、`/memory_details/9/top/18/text` | 成功への道筋使用后，追加使用数+1、抽牌；候选 `enchant-p_ef-hif_memory-p_card-01-men-2_041-enc01` | HIF 回忆，exam_enchants；能力定义见下方 069 | 当前回忆实例、此次考试剩余次数、装载时点需当前证据或连续历史 |
| F/fresh_first_exam_initial_status.json `/pages/0/words/4/text`、`/pages/0/words/2/text`；F/selected_memory_abilities.json `/memory_details/5/top/15/text`、`/memory_details/5/top/16/text`、`/memory_details/5/top/13/text` | シュプレヒコール使用后随机除外山札/弃牌中的眠気；候选 `enchant-p_ef-hif_memory-p_card-01-act-2_001-enc01` | HIF 回忆，exam_enchants；能力 003 | 截断字不能单独拼成全文；随机目标由结果快照确认，不能预选 |
| F/fresh_first_exam_initial_status.json `/pages/1/words/1/text`、`/pages/1/words/3/text`；F/selected_memory_abilities.json `/memory_details/3/top/16/text`、`/memory_details/3/top/15/text`、`/memory_details/3/top/17/text` | 精神統一使用后同类除外；候选 `enchant-p_ef-hif_memory-p_card-01-men-2_104-enc01` | HIF 回忆，exam_enchants；能力 034 | 与精神統一卡本身的抽牌/集中强化不是同一个状态 |
| F/selection1_full_status.json `/pages/1/words/3/text`、`/pages/1/words/1/text`；F/selected_memory_abilities.json `/memory_details/2/top/16/text`、`/memory_details/2/top/17/text`、`/memory_details/2/top/14/text` | 立ち位置チェック使用后追加使用数/抽牌；候选 `enchant-p_ef-hif_memory-p_card-01-act-2_059-enc01` | HIF 回忆，exam_enchants；能力 072 | 后一局选中索引改为 12，不能沿用旧索引 2 的能力 |
| F/selection1_full_status.json `/pages/2/words/6/text`、`/pages/2/words/18/text`、`/pages/2/words/12/text` | 願いの力+，主动卡使用时集中+1；候选 `enchant-p_card-01-men-2_038-enc01` | 已使用卡产生的场上触发，exam_enchants | 不是给当前手牌挂 card_status_enchant；来源卡实例与强化/自定义另核对 |
| P `/raw_evidence/idol_item_text` | 勇気の標，集中≥13时使用卡，使用数+1、集中+4、考试内1次；候选 `pitem_01-3-342-0` → `enchant-p_item_effect_01-3-342-0-enc01` | P 道具，inventories.items + exam_enchants | 不能把名称相似的 + 版本（集中+7）当实测；当前持有/剩余次数另证 |
| F/selection1_full_status.json `/pages/2/words/2/text`；F/selected_memory_abilities.json `/memory_details/3/top/13/text`、`/memory_details/3/top/12/text` | 回合开始抽牌；精神統一候选 `enchant-p_card-01-men-2_104-enc01`，センブリソーダ候选 `enchant-pdrink_00-2-010-enc01` | 卡或饮料产生的场上触发，exam_enchants | 状态页“剩1回合”不能唯一确定来源；主数据 StartPlay 在引擎同时用于出牌和回合开始，暂不绑定这两个状态，需修正相位语义 |
| F/selection1_full_status.json `/pages/1/words/5/text`、`/pages/1/words/10/text`、`/pages/1/words/15/text` | センブリソーダ `pdrink_00-2-010`，10%增幅候选 `e_effect-exam_lesson_value_multiple-0100-05` | 饮料，exam_effects：ExamLessonValueMultiple | 主数据初始5回合不是当前剩1回合；来源实例/应用时点另证；此饮料还生成抽牌 enchant，不能只保留倍率 |
| F/selection1_full_status.json `/pages/2/words/3/text`、`/pages/2/words/7/text` | 好调3回合，基础50%描述 | facts.parameter_buff=3；不是额外 enchant | 不把好调再放入 exam_effects 重复统计 |
| F/fresh_first_exam_initial_status.json `/pages/0/words/1/text`、`/pages/0/words/6/text`；F/selection1_full_status.json `/pages/0/words/4/text`、`/pages/0/words/7/text` | 集中基础描述，后一个历史页集中31 | facts.lesson_buff；不是“集中增长触发器” | 不将两局的0/31合并；没有证据证明独立被动触发 |
| F/fresh_first_exam_initial_status.json `/pages/0/words/5/text`；F/selection1_full_status.json `/pages/0/words/6/text`、`/pages/2/words/13/text` | 静かな意志+、深呼吸++、支援名等上下文 | 先保留原 OCR；卡变体归 EntityRef/ exam_card_state | 名称与邻行不能直接证明当前装备或某个 enchant 来源 |

四个 HIF 能力 ID 使用前缀
`memory_ability-p_memory_skill-common-hatsuboshi_idol_festival-p_trigger-start_audition-for_hif_memory-exam_status_enchant-exam_turn_timer-exam_status_enchant-01-`
后接 `003-001` / `034-001` / `069-001` / `072-001`，level=1。
主数据链是 MemoryAbility → ProduceSkill → ProduceEffect → enc02 开场计时器 → enc01 已就绪触发。
当前稳定页只绑定已就绪 enc01，不重放 enc02 开场效果，不从持有回忆自动激活。
`isUniqueActivation` 禁止同种 HIF 能力重复发动；重复 OCR 行不能生成第二个状态。

原始 SHA256、JSON pointer 和未改写片段在 [历史证据摘录](examples/live_passive_evidence.json)。
`python scripts/audit_passive_evidence.py` 校验 adapter 索引的哈希和片段是否与原文件一致；不读取 runs。
历史标签/来源对应仍是待核验项，哈希只证明选用了哪份资料，不证明今天仍装备同样能力。

## 字段和最小结构

非空 `facts.exam_enchants.value` 为 ExamEnchantState 数组，配套
`facts.exam_passive_version="arena-passive/1"` 与 `facts.exam_counter_semantics="arena-exam-counters/1"`。
全部仍用 ObservedValue 包装并给证据。旧明确空数组仍可接受，不自动补建被动。
新 profile 还要求 facts.exam_scheduled_effects 为已观察列表；本阶段仅支持明确 []。
非空预约列表返回 unsupported.exam.scheduled_effects，不能把它移入普通已就绪 enchant 或忽略。
预约后续结构需要 effect_id、fire_turn、次数、来源/目标和状态身份；目前不解释/执行非空 payload。

每个状态必填：state_id、exam_id、enchant_id、source（EntityRef）、source_level、remaining_turns、
remaining_count、applied_turn、applied_phase、last_fired_turn、bound_card_instance_id、once_per_turn。
state_id 在本次考试内稳定且唯一；同次考试重复同一 enchant 不静默去重。新考试必须新 exam_id。

- source.kind=memory：definition_id 是 MemoryAbility.id，source_level 为等级，instance_id 对应 RunSetup.loadout.memories；必须匹配已声明能力/等级。
- source.kind=item：definition_id 是 ProduceItem.id，instance_id 对应 complete inventories.items；source_level=null。
- source.kind=card：完整卡变体和 instance_id 对应一个 complete 卡区域；source_level=null。可在 lost/discard，不能为补来源捏造当前手牌。
- remaining_turns/count：必须明确给出正整数或 null（确认没有这一类上限）；缺字段不等于不限。已耗尽状态不留 count=0，确认后从完整活跃列表移除。
- applied_turn 是真实应用回合（开场可0）；applied_phase=exam_start/turn_start/card_resolution/drink_resolution。引擎内部衰减标记按相位转换，不由 adapter 减一。
- last_fired_turn=null 表示有凭据确认尚未触发，不表示不知道；否则是真实最后触发回合。当前最小集合不支持 once_per_turn=true 或绑定再演目标。
- bound_card_instance_id 用于再演等具体目标，和来源实例分开；本阶段必须明确 null。预约、再演、每回合一次及动态 card_status_enchant 先如实表达并返回 unsupported，不能省略。

EntityRef.customize_ids 是永久自定义；exam_card_state.grow_effect_ids 是考试内新增成长，
transient_effect_ids / transient_trigger_ids 是临时变化；重复效果发次数 play_count_bonus 不等于额外行动窗口。
卡片附魔 card_status_enchant_id 是 ProduceCardStatusEnchant，对卡自身的触发，与场上 ProduceExamStatusEnchant 分开。

最小完整结构见 [live_passive_minimal.json](examples/live_passive_minimal.json)，只采用成功への道筋回忆被动，整帧 synthetic。
公共类型 `ExamEnchantState` 与 [生成 schema](schemas/arena-exam-enchant-state-v1.json) 定义相同字段。
最小集合是上表四个 HIF enc01、願いの力 enc01、勇気の標基础版 enc01；均无限回合，
HIF/道具只余1次且尚未发动，願いの力无次数上限。其他类型/重复叠加并未开放。
source 缺映射/证据返回 observation；已声明的来源与主数据/装备矛盾返回 contract；未知 enchant ID 返回 unsupported。
来源卡永久自定义仍复用既有卡解析器，不推断历史同名副本。

## 回合与行动记账

plays_used 对应 runtime.turn_counters.play_count：本回合已经完成的“卡使用”次数，含再演/强制使用等
再次走完整使用流程的自动使用；普通多段伤害或“效果再发动”循环不增加此计数。
plays_remaining 是玩家还能提交的卡使用窗口数量，自动使用不消耗玩家窗口；饮料和补选也不消耗。
因此 play_limit=plays_used+plays_remaining 是内部计算上限，不是玩家本回合最多点击次数。
一次 command 不保证只对应一个卡使用；不能用已确认命令条数代替 plays_used。
这是共用引擎的计数定义；本阶段没有用实机验证任意再演组合的计数，未绑定的再演仍返回 unsupported。

turn 从1计数；max_turns 是基础回合数；extra_turns 是引擎尚未进入的追加回合余额。
进入追加回合后，当前回合已从 extra_turns 扣除；剩余回合为 extra_turns+1。
在基础回合内，剩余回合为 max_turns-turn+1+extra_turns。
追加回合页需另给 facts.extra_turns_granted（本考试累计确认追加数），
满足 extra_turns_granted=(turn-max_turns)+extra_turns；只看“残りnターン”不能恢复这组值。

当前稳定页能读的资源、行动窗、剩余次数/回合、动态变化以当前页为准。
身份、应用时点、累计追加数和已用次数可来自同 run/exam、完整无断档且区分自动使用/效果重复的确认历史。
点击、计划、预测或只确认手牌少一张不是完整计数凭据。遇到日志断档、uncertain、跨考试、映射歧义，
不得自行模拟余额或触发次数；需要补读或解决原事务。LiveSession 仍只消费绝对快照，事件只审计。
空列表需要同一稳定节点完整状态列表（顶/底或等价凭据）及来源覆盖；没看见图标不是不存在。

## 缺项分类

公共 classify_issue / classify_issues 在不改变 Decision/SessionReport wire 字段的前提下提供分类：
observation（补读或补完整证据）、unsupported（引擎能力不足，停止重截）、resolution（原未决命令）、
contract（版本、结构或身份矛盾）。分类结果也有版本 arena-issues/1，可单独 JSON 序列化。
`classify_issues(report_or_decision_or_exception, command_state=session.command_state)` 返回 LiveIssue 元组，
每项有 version/category/path/next_action；也接受路径列表和 MissingFields。ProtocolError 和 Pydantic
ValidationError 分为 contract；submitted/uncertain 优先分为 resolution，不被新页面缺项覆盖。

```python
from gakumas_arena.live import classify_issues
issues_json = [issue.model_dump(mode='json') for issue in
               classify_issues(report, command_state=session.command_state)]
```

聚合范围：基础11个数值缺值，当前属性、额外效果、禁用检索、动态卡状态缺值，以及每条 passive 的
结构/来源/次数/时间/作用域问题。握手、exam_id/stage 校验优先；旧费用、额外持续效果、卡触发器、
逐卡动态解析和区域检查仍可能首错即停，尚非整帧穷尽诊断。`unsupported` 等待实现更新；
`observation` 是补可靠证据（也可查连续日志），不等于无条件重截图。

## 编码与恢复兼容性

考试编码升级 **arena-exam-observed/2**，即使传空被动也使用新 manifest。
原 global/action_features/decision_kind/exam_context 顺序和数值保持，新增 `passive_features` 和
`passive_features_known_mask`，形状6×8。行按 manifest.passive_ids 排序，列为 presence、剩余回合、
无限回合标志、剩余次数、无限次数标志、引擎应用时点标记、末次触发回合、尚未触发标志。
计数仍按 x/(x+10)；applied_turn_marker 是相位转换后的引擎标记，区别于 wire 的真实应用回合。
完整活跃列表为空时 presence=0 且 mask=1；列表未知时全部值和 mask=0。
训练 wrapper 和实况调用同一入口，已知的非白名单或重复状态不能进入编码。

既有 v1 考试 checkpoint 必须拒绝/重新导出，不能补零伪装成新模型；manifest SHA256 已变化。
奖励/咨询编码 arena-planning-observed/2 不变。wire 和 session schema 不变，新类型通过额外 schema 发布。
旧明确空列表帧仍可用；接入非空状态需传 profile、计数语义版本及预约完整列表。
旧调用若把 plays_used 当点击次数，必须先校正导出逻辑；Arena 不从旧记录自动猜测迁移。

snapshot/restore 保存原始 payload、command_id、观察版本、结果/事件去重记录，恢复不调用策略或执行效果。
示例 [live_passive_recovery.json](examples/live_passive_recovery.json) 展示保留原非空状态直到补交确认快照，
而后明确从列表移除已耗尽回忆能力；重复确认不重复消费。运行 `python scripts/demo_live_passive.py`。
本阶段绑定的是可观察决策状态，不提供被动触发后的预测器；旧 seeded 模拟器的完整被动分发/宏动作续跑
不作为本次实况验收范围，也不能据绑定通过声称全部回忆模拟已校准。
