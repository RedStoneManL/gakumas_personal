# H.I.F 新增 `ProduceExamEffectType` 语义与实现说明

> 数据版本：`data/raw/gakumasu-diff`（2026-09-04 dump），翻译：`data/raw/GakumasTranslationData/local-files/masterTrans/*.json`。
> 目标：把 `docs/research/existing_engines.md` §3 列出的「主数据有、gakumas-rl 没有」的 9 个 `ProduceExamEffectType` 落地到 `gakumas_rl/simulation/exam/effects/`，并让效果器注册表不再静默吸收未知类型。
> 证据标注：`[主数据 表.字段]`、`[卡面 JP/ZH]`（`produceDescriptions` 原文与中文翻译）、`[类比 现有效果器]`、`[推定]`。
> 回归测试：`tests/gakumas_rl/test_hif_exam_effects.py`。

## 0. 总表

| effectType（去前缀） | 官方名（Label） | 主数据出现 | 引用方 | 实现位置 |
|---|---|---|---|---|
| `ExamStatusEnchantEncore` | 再演 | 5 行 | 5 张 H.I.F 偶像固有 SSR 卡 | `effects/encore.py` + `runtime._dispatch_phase` 绑定卡钩子 |
| `ExamGimmickEnthusiastic` | 熱意 | **0 行**（仅作 Label / 描述标签） | 卡面「熱意効果を n 倍適用」等 | `effects/enthusiastic.py`（预留） |
| `ExamLessonDependStamina` | — | 3 行 | 自然体の魅力（p_card-01-ido-3_213）| `effects/lesson_value.py` |
| `ExamMultipleEnthusiasticLesson` | — | 3 行 | 手を伸ばした先に（p_card-03-ido-3_197）| `effects/lesson_value.py` |
| `ExamFullPowerLessonMultipleAdditive` | 全力強化 | 3 行 | P アイテム 憧憬挑战 / 初星旗帜（紫）/ tour gimmick | `effects/timed.py` + `effects/stance_multiple.py` |
| `ExamConcentrationLessonMultipleAdditive` | 強気強化 | 2 行 | P アイテム 编织夏日的影子 | 同上 |
| `ExamLessonBuffAdditiveFix` | 集中増加量追加 | 2 行 | あなたがくれた夢 / 波間に揺れる光 | `effects/timed.py` + `runtime._apply_scalar_modifiers` |
| `ExamAggressiveAdditiveFix` | やる気増加量追加 | 1 行 | わたしを支える言葉 | 同上 |
| `ExamForcePlayCardSearchWithCost` | — | 1 行 | 高みへ羽ばたく一番星（L 卡）的持续效果 | `effects/card_operation.py` |

另外发现并一并补齐的新枚举值（不在 9 个之列）：

| 枚举 | 出现 | 处理 |
|---|---|---|
| `ProduceExamPhaseType_ExamAggressiveUpInterval` | 1 个触发器（わたしを支える言葉 的再演条件「直接効果でやる気が5回増加時」） | `ids.ExamPhase.AGGRESSIVE_UP_INTERVAL`；`effects/scalar_resource.py` 在卡牌/饮料带来的やる気增加后按次数分发 |
| `ProduceExamFieldStatusType_ConditionThresholdMultiple` | 2 个触发器 | 仅补常量 `ids.FieldStatus.CONDITION_THRESHOLD_MULTIPLE`；求值器（`triggers/`，非本次范围）未实现 |
| `Label_ExamFullPowerPointAdditiveFix` / `Label_ExamParameterBuffAdditiveFix` / `Label_ExamReviewAdditiveFix` | 只有 Label / 描述表，尚无效果行 | 已按同族语义预先注册为持续修饰（固定值加算） |

## 1. 逐类型语义与证据

### 1.1 `ExamStatusEnchantEncore`（再演）

- 行：`e_effect-exam_status_enchant_encore-0001-{02,03,04}-inf-enchant-<card>-encXX`，`effectValue1=1`、`effectCount∈{2,3,4}`、`effectTurn=-1`、`produceExamStatusEnchantId=enchant-<card>-encXX` `[主数据 ProduceExamEffect]`。
- 卡面：「レッスン終了まで、〈条件〉、自身を再使用（N回まで発動・ターン内1回まで）」；ZH：「训练结束为止，〈条件〉，自身会再次使用（N次为限发动・回合内1次为限）」`[卡面 JP/ZH]`。
- Label 说明：「再演是，在训练中，仅限第一次使用自身时发动的效果。在之后的本次训练中，当满足指定条件时，每回合 1 次为限，自身会再次使用（**不消耗技能卡花费值**）」`[主数据 ProduceDescriptionLabel Label_ExamStatusEnchantEncore（ZH）]`。
- 被引用的附魔：5 个 `ProduceExamStatusEnchant` 行的效果都只有一条 `e_effect-exam_force_play_card_search-p_card_search-target_is_self-exam_status_enchant_encore-all-1_1`（`ExamForcePlayCardSearch`，检索 `p_card_search-target_is_self-exam_status_enchant_encore`：`cardPositionType=Target, isSelf=true`）`[主数据 ProduceExamStatusEnchant / ProduceCardSearch]`。
- 触发器（各卡不同）：
  - 3_197 手を伸ばした先に：`ExamEndTurn` + `RemainingTurn ≤ 3`（「残り3ターン以内」）；
  - 3_200 お姉さんの感覚：`ExamCardPlayAfter` + 手札里 自然体の魅力 ≥1（`CardSearchCountUp`）+ `produceCardSearchId=p_card_search-target`；
  - 3_202 わたしだけの思い出：`ExamTurnInterval 2` + `StaminaUpMultiple ≥ 800‰`；
  - 3_198 クールすぎるアイドル：`ExamCardPlayAfter` + `p_card_search-target-p_card-02-ido-3_211`（「燃え盛る青い炎使用後」）；
  - 3_201 わたしを支える言葉：`ExamAggressiveUpInterval 5` + `effectTypes=[ExamCardPlayAggressive]`。

**实现**（`effects/encore.py`）：把附魔挂成绑定到 **当前出牌卡** 的 `TriggeredEnchant`（新增字段 `bound_card_uid` / `once_per_turn` / `last_fired_turn`）：`effectCount` → `remaining_count`（N回まで）、`effectTurn=-1` → 永续、`effectValue1=1` → ターン内 1 回。没有出牌上下文（`current_card is None`）时忽略；同一张卡已挂有同 id 的绑定附魔时不再挂载（「仅限第一次使用自身时发动」——再使用时卡效果会再次走到本效果）。
`runtime._dispatch_phase` 对绑定型附魔：绑定卡不存在则跳过；同回合已发动则跳过；用 phase 事件里的行动卡做触发器匹配（`○○使用後`）；结算效果期间把绑定卡放进 `runtime.resolving_enchant_card`，`ExamForcePlayCardSearch` 效果器据此解析 `isSelf`/`Target` 检索并 **免费、不占用出牌窗口** 地再使用它（`_play_card(pay_cost=False, consume_play_window=False)`）。

### 1.2 `ExamGimmickEnthusiastic`（熱意）

- 当前 dump 里 **没有任何 `effectType` 等于它的效果行**（`existing_engines.md` 统计的 6 次全部是 `produceDescriptions[].examEffectType` 标签）；它只作为 `Label_ExamGimmickEnthusiastic_{Exam,Produce}` 和卡面「熱意」的类型标签存在 `[主数据 ProduceDescriptionLabel / ProduceCard.produceDescriptions]`。
- Label：「热意每有 1 点打分上升量增加 1；回合结束时热意变为 0」`[ZH]`——与运行时现有实现一致（`_apply_score_value_modifiers` 里 `+= enthusiastic`，`_end_turn` 清零）。热意的实际来源是温存解除奖励（`ExamSetting.preservationReleaseEnthusiastic{1,2}` / `overPreservationReleaseEnthusiastic`）。
- **实现**：`ids.ExamEffect.GIMMICK_ENTHUSIASTIC` + `effects/enthusiastic.py`：若将来出现「熱意+n」效果行，按 `effectValue1` 走 `_gain_enthusiastic`（套用 熱意追加/熱意増加 修饰）。

### 1.3 `ExamLessonDependStamina`

- 行：`e_effect-exam_lesson_depend_stamina-{8000,10000,12000}-01`，`effectValue1∈{8000,10000,12000}`（千分比）、`effectCount=1` `[主数据]`。
- 卡面：「体力の 800% 分パラメータ上昇」/ ZH「体力的 800% 数值变为打分上升」（自然体の魅力：集中消費5、好調12ターン以上で使用可、先「最大体力の10%分体力回復」再本效果）`[卡面 JP/ZH]`。
- **语义**：`ceil(当前体力 × effectValue1/1000)`，参照 **当前体力**（卡面写「体力の」而不是「最大体力の」；同卡的回复效果写的是「最大体力の」，二者措辞不同）。走 `ExamLesson*` 前缀打分管线（集中/熱意/好調/指针倍率照常）`[类比 ExamLessonDependBlock / ExamLessonDependExamReview：ceil(资源 × 千分比)]`。

### 1.4 `ExamMultipleEnthusiasticLesson`

- 行：`e_effect-exam_multiple_enthusiastic_lesson-{0001,0003,0005}-1000-01`，`effectValue1∈{1,3,5}`（基础值）、`effectValue2=1000`（千分比）`[主数据]`。
- 卡面：「パラメータ+n（熱意効果を 2 倍適用）」/ ZH「打分+n（热意效果会 2 倍生效）」`[卡面]`。
- **语义**：与 `ExamMultipleLessonBuffLesson`「パラメータ+n（集中効果を m 倍適用）」同构 `[类比]`：`value = n + ceil(熱意 × effectValue2/1000)`，之后打分主管线再加一次熱意，合计 熱意 × (1 + effectValue2/1000) = 2 倍。

### 1.5 `ExamFullPowerLessonMultipleAdditive`（全力強化）/ 1.6 `ExamConcentrationLessonMultipleAdditive`（強気強化）

- 行：`..._full_power_lesson_multiple_additive-{0200-04, 0250-inf, 0350-inf}`（+20% 4ターン / +25% / +35%）、`..._concentration_lesson_multiple_additive-{0350-inf, 0600-inf}`（+35% / +60%）；`effectValue1` 千分比，`effectTurn` 回合数或 -1 `[主数据]`。
- Label：「強気強化：强气所提供的打分上升量会增加」「全力強化：全力所提供的打分上升量会增加」`[ZH]`；`docs/rules/lesson_exam_engine.md` §8.1：強気 ×2.0/×2.5「+ 強気強化」，全力 ×3.0「+ 全力強化」`[確認:engine]`。
- 来源：P アイテム 憧憬挑战（`enchant-p_item_effect_03-3-317-*`，全力になった時、全力強化 +25%/+35%）、初星旗帜（紫）与 tour gimmick（全力になった時、全力強化+20%（4ターン）・全力効果カードのパラメータ値+8）、编织夏日的影子（強気効果のスキルカード使用時、強気2段階の場合、強気強化 +35%/+60%、次のターン温存）。
- **语义**：持续效果；对应指针的打分倍率改为 `基础倍率 + Σ加算`（例：全力 3.0 + 0.25 = 3.25，強気2段 2.5 + 0.35 = 2.85）；指针不匹配时无效。
- **实现**：`effects/timed.py` 挂载；`effects/stance_multiple.py` 计算 `(基础 + 加算) / 基础` 修正系数，由 `effects/lesson_value.py` 在 `apply_score_value_modifiers` 之后乘上（数学上等价于替换指针倍率，且不改动他人维护的 `ExamRuntime._apply_score_value_modifiers`）。**接入点提示**：若打分主管线后续加入取整或改写指针倍率，请把 `stance_lesson_multiple_additive(context)` 直接加进指针倍率并删除 `lesson_value.py` 里的后乘，避免双算。

### 1.7 `ExamLessonBuffAdditiveFix`（集中増加量追加）/ 1.8 `ExamAggressiveAdditiveFix`（やる気増加量追加）

- 行：`e_effect-exam_lesson_buff_additive_fix-{0001-04, 0002-02}`（+1 4ターン / +2 2ターン）、`e_effect-exam_aggressive_additive_fix-0001-02`（+1 2ターン）；`effectValue1` 为**固定值** `[主数据]`。
- 对照同族「増加量増加」：`e_effect-exam_lesson_buff_additive-0250-02`「集中増加量増加+25%」、`e_effect-exam_aggressive_additive-0500-03`「やる気増加量増加+50%」，`effectValue1` 为**千分比** `[主数据]`。Label ZH：「集中増加量追加：集中的增加量会追加（**加算**）」vs「集中増加量増加：…会增加」`[ZH]`。
- **语义**：每次获得 集中/やる気 时 `+固定值`；与百分比修饰同时存在时 `(基础 + Σ追加) × (1 + Σ増加%)` `[確認:engine resolveEnthusiasm: (v + Σbonus) × (1 + Σbuffs)；docs/rules/lesson_exam_engine.md §7]`。
- **实现**：`effects/timed.py` 挂载；`runtime._apply_scalar_modifiers` 增加 `*_ADDITIVE_FIX` 分支（固定值）；同时把原本被当作固定值相加的 `ExamLessonBuffAdditive` / `ExamAggressiveAdditive` / `ExamFullPowerPointAdditive` 改为千分比乘算（原实现会把 `+25%` 当成 `+250`）。

### 1.9 `ExamForcePlayCardSearchWithCost`

- 行：`e_effect-exam_force_play_card_search_with_cost-p_card_search-not_lost-select-1_1`：检索 `p_card_search-not_lost`（`cardPositionType=NotLost` = 山札+手札+捨札+保留）、`pickRangeType=Select`、`pickCountMin=pickCountMax=1` `[主数据]`。
- 卡面：「除外以外のスキルカードを1枚選択し、コストを消費して使用」/ ZH「选择 1 张除外以外的技能卡，消耗花费值使用」（高みへ羽ばたく一番星：ターン開始時、全力の場合、1 回まで）`[卡面]`。
- 对照 `ExamForcePlayCardSearch` 的 8 行全部写「コストを消費せず使用」/「自身を再使用」`[主数据]`。
- **语义**：`WithCost` 支付所选卡的体力/资源费用（因此只从当前付得起的候选中选）；无 `WithCost` 免费。两者都由效果驱动，**不占用本回合スキルカード使用数**（否则 ターン開始時 触发会直接吃掉玩家唯一的出牌机会）`[推定：与 gakumas-core「効果による使用は使用数を消費しない」一致]`。
- **实现**：`effects/card_operation.py::apply_force_play`：`Select` 用运行时自动选卡评分取最高价值候选，`Random` 用运行时随机源；`context.force_play_card(card, pay_cost=…)` → `_play_card(pay_cost, consume_play_window=False)`（`_play_card` 新增两个关键字参数；旧实现的强制使用会扣费并占用窗口，已迁出 `runtime._apply_card_operation`）。

## 2. 注册表与严格模式

- `effects/registry.py`：`EffectHandlerRegistry.resolve()/is_registered()`；`GAKUMAS_STRICT_EFFECTS=1|true|yes|on` 时，没有精确/前缀效果器的类型抛 `UnknownExamEffectTypeError`（含 effect id 与来源），否则仍走兜底并对每种未知类型 `logging.warning` 一次，记录到 `effects/fallback.py::UNKNOWN_EFFECT_TYPES_SEEN`。
- `tests/gakumas_rl/test_hif_exam_effects.py::test_every_master_effect_type_has_a_real_handler` 扫描 `ProduceExamEffect.yaml` 全部 `effectType`，任何新类型落到兜底都会直接失败。
- `ExamReviewAdditive`（好印象増加量増加 +n%、千分比、带回合数）原被 `effects/review.py` 当作即时 +n 好印象；现改为持续修饰（与 `ExamLessonBuffAdditive` 同族）。

## 3. 已知未决 / 上游问题（未在本次修改，需要对应模块的维护者处理）

1. `triggers/field_status.py` 把 `ProduceExamFieldStatusType_RemainingTurn` 当作「≥ 阈值」判定，而卡面语义是「残り n ターン以内（≤）」——影响 3_197 的再演与其它「残りnターン以内」触发器。本次测试只在 remaining == 3 处断言。
2. `constants.LESSON_EFFECT_TYPES`（用于 `LessonCountAdd` 成长的重复次数）未包含 `ExamLessonDependStamina` / `ExamMultipleEnthusiasticLesson`（也不含基础 `ExamLesson`），卡面虽有 `Description_LessonCountAdd_CountSection`，重复上昇暂不适用于这两类。
3. `ExamCardMoveGrave/Hand/Lost` 三个 phase 在主数据触发器里出现但运行时未分发；`ProduceExamFieldStatusType_ConditionThresholdMultiple` 未求值。
4. 「直接効果」判定：`ExamAggressiveUpInterval` 只统计 `source∈{card, drink}` 的やる気增加（`STATUS_CHANGE_TRIGGER_ORIGINS`），未区分卡牌费用/移动等更细的直接效果来源。
5. `ExamLessonBuffMultiple`（集中強化）在上游实现里作用于集中的**获得量**，而 `docs/rules/lesson_exam_engine.md` §6 认为它作用于集中的**效果**；本次未改动。
