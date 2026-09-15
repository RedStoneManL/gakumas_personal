# 学マス 课程/考试卡牌引擎规则（レッスン／試験／コンテスト 共通）

> 2026-09-08更新：本页保留早期来源与推导；涉及集中／好印象强化、批次资格、开始后、费用事件、自动使用和状态寿命的当前实现，以 [行为契约](../ENGINE_RULE_CONTRACT.md) 为准。其余未验证细则仍保留证据等级，见 [采样清单](../RULE_ALIGNMENT_LOG_REQUESTS.md)。

> 目的：为 `engine/` 提供一份可直接实现、可写单元测试的数值规格。只覆盖所有剧本共享的通用规则；H.I.F 专属规则见 `docs/scenarios/hif.md`，master-data 字段总表见 schema atlas（本文只在规则映射到某表/字段时引用，不重复其结构）。
>
> 证据等级标注（每条规则后缀）：
> - `[確認:core <file>:<line>]` — kjirou/gakumas-core 源码（TypeScript，含本家实测视频链接的注释）。路径前缀 `ext/gakumas-core/src/`。
> - `[確認:engine <file>]` — surisuririsu/gakumas-tools `packages/gakumas-engine`（当前活跃维护、覆盖アノマリー与コンテスト）。
> - `[確認:master <Table>.<field>]` — vertesan/gakumasu-diff 中的官方 master data（`ext/gakumasu-diff/*.yaml`）。数值来自游戏客户端，最高可信度。
> - `[確認:web <URL>]` — 本次直接读取的网页。
> - `[転記:seesaawiki]` — seesaawiki.jp/gakumasu 的「レッスン・試験詳細」「最終プロデュース評価」页面。本会话中该域名被出口代理阻断，内容转记自 `docs/research/user_report_02_data_and_formulas.md`（上一轮已直接阅读该 wiki）以及 WebSearch 返回的页面摘要；标注为转记，不视为一手确认。
> - `[検索要約:<URL>]` — 仅通过 WebSearch 摘要获得（页面本身被阻断）。
> - `[推定]` — 由代码/数据推断或社区共识，尚未有一手证据；实现时应做成可配置项并写入待验证清单（§15）。
>
> 取整记号：`ceil(x)` 向上取整，`floor(x)` 向下取整。所有“每步取整”都指对中间结果立即取整后再进入下一步。

---

## 1. 全局常量（对局设定表 ExamSetting）

官方对局参数集中在 `ExamSetting.yaml`（当前所有 Produce 都引用 `p_exam_setting-1`）`[確認:master Produce.examSettingId]`。下表是引擎必须读取的字段及其语义（语义列由字段名 + 引擎实现 + 社区文档三方交叉推断，右列标明证据）。

| 字段 (ExamSetting) | 值 | 语义 | 证据 |
|---|---|---|---|
| `handLimit` | 5 | 手札（手牌）上限 5 张 | `[確認:master]` `[確認:core models.ts:39]` `[確認:engine CardManager.drawCard]` |
| `turnStartDistribute` | 3 | 每回合开始抽 3 张 | `[確認:master]` `[確認:core models.ts:36]` `[確認:engine TurnManager.startTurn]` |
| `holdLimit` | 2 | 保留（保留/hold）槽位上限 2 张 | `[確認:master]`；引擎 `heldCards` 未硬编码上限 `[推定]` |
| `examTurnEndRecoveryStamina` | 2 | スキップ（跳过回合）回复体力 2 | `[確認:master]` `[確認:core models.ts:42]` `[確認:engine TurnManager.endTurn]` |
| `examParameterBuffPermil` | 1500 | 好調倍率 ×1.5 | `[確認:master]` `[確認:core lesson-mutation.ts:686]` |
| `examParameterBuffMultiplePerTurnPermil` | 100 | 絶好調：每 1 回合好調 +10% | `[確認:master]` `[確認:core lesson-mutation.ts:686-690]` |
| `examStaminaConsumptionDownPermil` | 500 | 消費体力減少：费用 ×0.5 | `[確認:master]` `[確認:core models.ts:352]` |
| `examStaminaConsumptionAddPermil` | 1000 | 消費体力増加：费用 +100%（×2） | `[確認:master]` `[確認:core models.ts:351]` |
| `examStaminaConsumptionAddDownPermil` | 1250 | 増加与減少同时存在时的合成倍率 ×1.25？ | `[推定]`（两个模拟器都按 ×2×0.5=×1 处理，与该字段矛盾，见 §15） |
| `examStaminaConsumptionDownAddPermil` | 600 | 「消費体力減少効果増加」状态：減少变为 ×0.4？ | `[推定]` |
| `examBlockAddDownPermil` | 667 | 不安（元気增加量 ×0.667） | `[確認:master]` `[確認:engine resolvers.resolveGenki: ×0.67]` |
| `examGimmickParameterDebuffPermil` | 667 | 不調（分数 ×0.667） | `[確認:master]` `[確認:engine resolvers.resolveScore: ×0.67]` |
| `examConcentrationLessonValueMultiplePermil1/2` | 2000 / 2500 | 強気 1 段 ×2.0、2 段 ×2.5（master 中 “Concentration” = 強気） | `[確認:master]` `[確認:engine resolvers.resolveScore]` |
| `examConcentrationStaminaMultiplePermil1/2` | 2000 / 2000 | 強気时体力消耗 ×2 | `[確認:master]` `[確認:engine resolvers.resolveCost]` |
| `examConcentrationStaminaPenetrateReduce2` | 1 | 強気 2 段：每次出牌额外固定体力 −1（穿透元気） | `[確認:master]` `[確認:engine constants.DEFAULT_EFFECTS]` |
| `examPreservationLessonValueMultiplePermil1/2` | 500 / 250 | 温存 1 段 ×0.5、2 段 ×0.25 | `[確認:master]` `[確認:engine]` |
| `examPreservationStaminaMultiplePermil1/2` | 500 / 250 | 温存时体力消耗 ×0.5 / ×0.25 | `[確認:master]` `[確認:engine]` |
| `examOverPreservationLessonValueMultiplePermil` / `…StaminaMultiplePermil` | 0 / 0 | のんびり：分数 ×0、体力消耗 ×0 | `[確認:master]` `[確認:engine]` |
| `examFullPowerLessonValueMultiplePermil` | 3000 | 全力 ×3.0 | `[確認:master]` `[確認:engine]` |
| `fullPowerPlayableValueAdd` | 1 | 进入全力时 スキルカード使用数 +1 | `[確認:master]` `[確認:engine FULL_POWER_CHANGED_EFFECTS]` |
| `preservationReleasePlayableValueAdd1/2` | 1 / 1 | 温存解除时使用数 +1 | `[確認:master]` `[確認:engine STANCE_CHANGED_EFFECTS]` |
| `preservationReleaseBlockAdd1/2` | 0 / 5 | 温存 2 段解除时 固定元気 +5 | `[確認:master]` `[確認:engine]` |
| `preservationReleaseEnthusiastic1/2` | 5 / 8 | 温存 1/2 段解除时 熱意 +5 / +8 | `[確認:master]` `[確認:engine]` |
| `overPreservationReleasePlayableValueAdd / BlockAdd / Enthusiastic` | 1 / 5 / 10 | のんびり解除：使用数 +1、固定元気 +5、熱意 +10 | `[確認:master]` `[確認:engine]` |
| `overPreservationReleaseToFullPowerGrowEffectLessonAdd` | 10 | のんびり→全力：全部技能卡 成長 パラメータ+10 | `[確認:master]` `[確認:engine]` |
| `examLessonValueMultipleDependReviewOrAggressiveMultiplePermil` / `MaxPermil` | 20 / 500 | プライド：+2%×min(好印象, やる気)，上限 +50% | `[確認:master]` `[確認:engine resolvers.resolveScore prideTurns]` |
| `examBuffConsumptionDownPermil` / `AddPermil` | 500 / 1000 | 「強化状態コスト」的减半/翻倍 | `[確認:master]` 语义 `[推定]` |
| `produceExamPanicStaminaCandidates` | [1,2,3,4,5,6,7,7,8,8,9,9,10,11,12,13,14,15] | 気まぐれ（ExamPanic）随机体力消耗候选（等概率抽样） | `[確認:master]` 抽样方式 `[推定]` |
| `examAutoPlayEnableVersion` / `examAutoPlaySearchCommandLimit` | 2 / 5 | AutoPlay 版本与搜索深度 5 | `[確認:master]` |

> 实现建议：把上表做成 `engine/config.py::ExamSetting` dataclass，从 master 表直接加载；不要把 1.5 / 0.5 / 3.0 写死。

---

## 2. 对局对象与牌堆

- 参与者状态：体力（体力 `stamina`，上限为アイドル最大体力），元気（元気 `genki`，初始 0），スコア/パラメータ（`score`，课程叫パラメータ、考试叫スコア `[確認:core types.ts Lesson.score]`），状態修正列表，Pアイテム列表（含每个道具的已发动次数），Pドリンク列表（对局内最多 3 个，可被效果提升到 4 `[確認:master ProduceSetting.produceDrinkPossessLimit=3, produceDrinkPossessMaxLimit=4]`）。
- 牌堆：山札（deck）、手札（hand，≤5）、捨札（discard）、除外（removed/lost）、保留（held，≤2）。`[確認:master ProduceDescriptionLabel: Label_ProduceCardPositionType_Hand/Grave/Lost/Hold/DeckFirst/DeckLast/DeckRandom]`
- 开局：把全部技能卡洗入山札 `[確認:core index.ts initializeGamePlay shuffleArray]`。「レッスン開始時手札に入る」（`innate`）的卡在第 1 回合抽牌前移到山札顶端 `[確認:core lesson-mutation.ts drawCardsOnTurnStart]`；gakumas-engine 的实现是回合 1 在抽 3 张后再检查山札顶最多 2 张 `isForceInitialHand` 追加抽入 `[確認:engine TurnManager.startTurn]`。持有 ≥6 张 innate 时溢出部分顺延到第 2 回合（6 张→T1 5 张 / T2 1 张；7 张→5/2；≥8 张行为未明）`[確認:core types.ts CardContentData.innate 注释, issue #37/#42]`。
- 山札耗尽时：把捨札洗牌后成为新山札；捨札也空则无法再抽 `[確認:core lesson-mutation.ts drawCardsFromDeck]` `[確認:engine CardManager.recycleDiscards]`。除外堆永不回收。
- 手牌满 5 张时继续抽到/生成的卡：gakumas-core 放入捨札，并注明本家实测是“堆到山札顶端”（TODO 注释引用视频）`[確認:core lesson-mutation.ts generateCard TODO]`；gakumas-engine 直接不抽（`if hand.length>=5 return`）`[確認:engine CardManager.drawCard]`。**实现选择：不抽/生成到山札顶（按本家）**，标记 `[推定]`。

---

## 3. 回合结构

### 3.1 回合数与回合属性
- 回合数由 stage 定义：课程 `ProduceStepLessonLevel.limitTurn`（通常 5–7，追い込み 9–12）`[確認:master]`；初 考试 `ProduceExamBattleConfig.turn`：中間 9 回合、最終 11 或 12 回合 `[確認:master p_exam_battle_config-*-produce-00X-1-*: turn 9; -2-*: turn 11/12]`。
- 每回合有一个属性（Vo/Da/Vi）。课程内全部回合同属性（Pアイテム文案「【ボーカルレッスン・ボーカルターンのみ】」）`[確認:core types.ts ReactiveEffectTrigger.idolParameterKind 注释]`。考试的回合属性序列由 `ProduceExamBattleConfig.vocal/dance/visual` 权重生成；gakumas-engine 的生成算法：第 1 回合按 `firstTurns` 概率分布抽，最后 3 回合固定为按审查比重升序（权重最高的属性排最后一回合），中间回合按各属性剩余数量随机洗牌 `[確認:engine TurnManager.generateTurnTypes]`。
- 「ターン追加+n」（ExamExtraTurn）增加剩余回合；追加回合复制原最终回合的属性 `[確認:core models.ts createActualTurns]`。「残りnターン以内」条件按含追加回合后的值判定 `[確認:core types.ts countRemainingTurns]`。

### 3.2 回合开始（ターン開始時）顺序
kjirou 实测（每条附视频）`[確認:core index.ts startTurn 注释]`：
1. 上回合开始时已存在的持续时间型状態修正 −1（见 §3.5）。
2. 行动点置 1（即每回合默认可出 1 张）。
3. 回合号 +1。
4. 応援/トラブル（Encouragement，考试的加油/干扰事件）发动。
5. Pアイテム「ターン開始時」触发（按道具获得顺序）。
6. Pアイテム「nターンごとに」触发（在 5 之后）。
7. 抽 3 张（若 Pアイテム 已使分数达 PERFECT 则不抽）。
8. 状態修正的「発動予約」：先 `パラメータ+n` → 再 `スキルカードを引く` → 再 `手札をレッスン中強化`。
9. 第 1 回合：メモリー アビリティ按概率发动。
10. 记录此刻的状態修正 id 列表（供下回合步骤 1 使用）。

gakumas-engine 的对应阶段（DSL `at:` 名）：`beforeStartOfTurn` → `startOfTurn` → 抽 3 张 → 进入全力时 `moveHeldCardsToHand` → `afterStartOfTurn` → `turn`(nターン後) → `everyTurn` `[確認:engine TurnManager.startTurn]`。全力判定在最前：若当前指針=全力先重置为 none；然后若 `lockStanceTurns==0 && fullPowerCharge>=10` → 全力値 −10 并进入全力 `[確認:engine constants.FULL_POWER_EFFECTS]`。

### 3.3 玩家行动
- 每回合基础出牌次数 1（`cardUsesRemaining=1`）`[確認:engine TurnManager.startTurn]` `[確認:core index.ts actionPoints=1]`。「スキルカード使用数追加+n」（ExamPlayableValueAdd）增加本回合可出牌数。消耗顺序：先消耗「使用数追加」，再消耗基础行动点 `[確認:core lesson-mutation.ts consumeRemainingCardUsageCount]`。出牌后若行动点为 0 且仍有使用数追加，则行动点回 1、追加 −1（本家 UI 可见）`[確認:core lesson-mutation.ts useCard 末尾]`。
- 「使用数追加」不跨回合：回合开始时已存在的会在回合结束时消失（`additionalCardUsageCount` 是 1 回合效果）`[確認:core types.ts additionalCardUsageCount 注释]` `[検索要約:https://zutapoke.com/1830/]`。
- Pドリンク使用不消耗出牌次数，可在任意出牌前后使用；每个只能用一次，用后从列表移除 `[確認:core lesson-mutation.ts useDrink]`。
- スキップ（Skip）：放弃本回合剩余出牌，体力 +2（不超过上限）`[確認:core index.ts skipTurn]`；gakumas-engine 中“出牌次数未用完就结束回合”即视为 skip，回复 2 并触发 `turnSkipped` 阶段 `[確認:engine TurnManager.endTurn]`。
- 出牌次数用尽时自动进入回合结束 `[確認:engine CardManager.useCard 末尾]`。

### 3.4 回合结束（ターン終了時）顺序
kjirou `[確認:core index.ts endTurn 注释]`：
1. Pアイテム「ターン終了時」。
2. 状態修正（持続効果）「ターン終了時」。
3. 弃掉未使用的手牌（进捨札）。
4. 好印象结算：`score += 好印象` 经完整分数管线（§5.4）。

gakumas-engine `[確認:engine TurnManager.endTurn]`：skip 判定/回复 → `endOfTurn` 阶段 → 好印象结算（重复 `1 + Σ好印象追加発動` 次）→ 持续时间型 buff −1（§3.5）→ 重置 `cardUsesRemaining/turnCardsUsed/turnCardsUpgraded/熱意=0` → 效果 `ttl/delay` 递减、清理过期 → 弃手牌 → `turnsElapsed++ / turnsRemaining--` → 下一回合。

> 两个实现的差异：kjirou 在**下回合开始**做 −1，engine 在**本回合结束**做 −1；只要都遵守“本回合新获得的不减”（§3.5），结果等价。

### 3.5 持续时间递减规则（重要）
- 本回合内新获得（或从 0 变为 >0）的持续时间型状态，本回合不递减；即“好調3ターン”在获得回合外还能再享受 3 个完整回合 `[確認:core types.ts Idol.modifierIdsAtTurnStart]` `[確認:engine BuffManager.freshBuffs]` `[検索要約:https://note.com/fit_bee8608/n/n41e766bde741]`。
- 递减对象（engine `EOT_DECREMENT_FIELDS`）：好調、絶好調、好印象、プライド、指針固定、消費体力減少、消費体力増加、元気増加無効、不調、アクティブ使用不可、メンタル使用不可、不安、カード使用不可 `[確認:engine constants.EOT_DECREMENT_FIELDS]`。kjirou 额外把 `doubleEffect`（有 duration 的「もう1回発動」）计入 `[確認:core lesson-mutation.ts decreaseEachModifierDurationOverTime]`。
- 「ターン開始時」由 Pアイテム/持続効果新付与的持续状态是否在当回合递减：kjirou 标注为不明 `[推定]`。

### 3.6 对局结束
- 剩余回合为 0 且回合结束；或课程分数达到 PERFECT 上限（达到后立即结束，不再抽牌/触发）`[確認:core index.ts isLessonEnded]` `[確認:core lesson-mutation.ts 各处 isScoreSatisfyingPerfect]`。
- 课程有 CLEAR/PERFECT 两阈值：`ProduceStepLessonLevel.successThreshold`（CLEAR）与 `resultTargetValueLimit`（PERFECT）`[確認:master]`，PERFECT 为含 CLEAR 的总分；超过 PERFECT 的分数被截断（`remainingIncrementableScore`）`[確認:core lesson-mutation.ts calculatePerformingScoreEffect]`。考试无 PERFECT 上限；中間试験有 `forceEndScore`（达到即强制结束：レギュラー 900、プロ 1700）`[確認:master ProduceStepAuditionDifficulty.forceEndScore]`。

---

## 4. 出牌合法性与费用

### 4.1 费用种类（ActionCost.kind）`[確認:core types.ts ActionCost]`
| 种类 | 原文 | 支付资源 |
|---|---|---|
| `normal` | 无标注（卡右下数字） | 元気优先，不足部分扣体力 |
| `life` | 体力消費n | 只扣体力（穿透元気）→ master `ExamStaminaReduceFix` |
| `focus` | 集中消費n | 扣集中 |
| `goodCondition` | 好調消費nターン | 扣好調回合数 |
| `motivation` | やる気消費n | 扣やる気 |
| `positiveImpression` | 好印象消費n | 扣好印象 |
| `fullPowerCharge` | 全力値消費n | 扣全力値（アノマリー）`[確認:engine constants.COST_FIELDS]` |

### 4.2 可出牌判定 `[確認:core lesson-mutation.ts canPlayCard/validateCostConsumution]` `[確認:engine CardManager.isCardUsable]`
1. 全局禁用：カード使用不可 / アクティブ使用不可 / メンタル使用不可 状态下对应卡不可用 `[確認:engine]`。
2. 使用条件（`conditions`）：如「3ターン目以降」「元気が0」「好調状態」「体力の50%以上」「レッスンCLEARの100%以下」等，按**出牌前**状态判定 `[確認:core types.ts CardUsageCondition]`。
3. 费用可支付性：`normal` 需 `元気 + 体力 ≥ 修正后费用`；`life` 需 `体力 ≥ 费用`；状态类费用需对应状态值 ≥ 费用。**体力不足时卡不可出**（不存在“扣到 0 仍可出”的规则）`[確認:core validateCostConsumution]` `[確認:engine isCardUsable: previewState[cost field] < 0 → false]`。
4. 百分比判定的取整：kjirou 用 `floor(体力×100/最大体力)` 与阈值比较（“以上”“以下”均用该整数）`[確認:core lesson-mutation.ts measureValue]`；本家取整未查明 `[推定]`。

### 4.3 费用修正与支付顺序
修正后费用（仅对**技能卡**费用生效；Pアイテム/Pドリンク 的费用不受消費体力減少/削減影响）`[確認:web https://github.com/kjirou/gakumas-core/issues/141]` `[確認:core models.ts calculateModifierEffectedActionCost]`：

```
kjirou:  cost' = max( ceil(cost × rate) − 消費体力削減, 0 ),  rate = (増加?2:1) / (減少?2:1)
engine:  cost' = floor→ 先乘 指針倍率(強気×2 / 温存×0.5 / 温存2×0.25 / のんびり×0)
                 再乘 減少×0.5、増加×2 → floor(向 0 取整) → +削減(costReduction) −追加(costIncrease) → clamp ≥ 0
```
`[確認:engine resolvers.resolveCost]`。两者的取整方向表面相反（kjirou 对费用 ceil、engine 对负数费用 floor），但 engine 的费用以负数表示，`Math.floor(-2.5) = -3`，即**消耗量向上取整**——与 CHANGELOG「Round stamina numbers down (i.e. round consumed stamina up)」一致 `[確認:engine CHANGELOG]`。因此规则：**费用减半时小数向上取整**（消費 5 → 3）`[確認:core types.ts halfLifeConsumption「端数は切り上げ」]`。

支付顺序：`normal` 费用先扣元気，元気归零后剩余扣体力 `[確認:core calculateCostConsumption]` `[確認:engine resolveCost]`。技能卡的费用在效果发动**之前**支付；Pアイテム的费用在其效果发动**之后**支付 `[確認:core activateEffectsOfProducerItem 注释+视频]`。

コスト0化（nullifyCostCards / nullifyCostActiveCards）：有体力费用的下一张卡（或下一张アクティブ）不支付费用并消耗 1 次 `[確認:engine CardManager.useCard]`。

### 4.4 「体力減少n」与「体力消費n」
Pアイテム/トラブル 的「体力減少」（ExamStaminaDamage）与费用「体力消費」（ExamStaminaReduceFix）不同：Pアイテム 即使体力不足也会发动 `[確認:core lesson-mutation.ts canActivateProducerItem 注释, issue #46]`。kjirou 把「体力減少」按 normal 费用（先扣元気）处理并标注 TODO `[推定]`。

---

## 5. 分数（パラメータ／スコア）计算

### 5.1 统一管线（推荐实现）
综合 seesaawiki 的“每步向上取整”描述与两套实现：

```
S0 = 卡面基础值 + 成長(g.score) [+ 参照値：好印象/やる気/元気 的百分比部分，各自 ceil 后加入]
S1 = ceil( S0 + 集中 × 集中適用倍率 × 集中強化倍率 + 熱意 × 熱意適用倍率 )          # engine
好調倍率 M1 = 1 + (0.5 + (絶好調 ? 0.1 × 好調残ターン : 0)) × 好調効果適用倍数   (好調なし → 1)
指針倍率 M2 = 強気 2.0(+強気強化) / 強気2 2.5(+強気強化) / 温存 0.5 / 温存2 0.25 / 全力 3.0(+全力強化) / のんびり 0 / なし 1
增减倍率 M3 = (1 + Σパラメータ上昇量増加% + プライド%) × max(1 − Σパラメータ上昇量減少%, 0) × (不調 ? 0.67 : 1)
S2 = ceil( S1 × M1 × M2 × M3 )
S3 = ceil( S2 × ターン属性倍率 )      # 考试: スコアボーナス%/100；课程: 1
score += S3   (课程再按 PERFECT 上限截断)
```
`[確認:engine resolvers.resolveScore]`（三次 ceil：S1、S2、S3）。

kjirou 的等价形式（两次 ceil）`[確認:core lesson-mutation.ts calculatePerformingScoreEffect]`：
```
base  = ceil( (value + 集中×focusMultiplier + boostPerCardUsed×使用枚数) × 好調倍率(整数/10) × (1+上昇量増加%/100) )
score = ceil( base × スコアボーナス% / 100 )
```
kjirou 注释：`0.1×1.4` 的浮点误差会改变结果，故好調倍率用整数（15/10、(15+好調)/10）计算 `[確認:core]`。**实现必须用整数/分数运算，禁止直接乘 0.1。**

seesaawiki 转记版 `[転記:seesaawiki]`：
```
最終基礎 = 基礎値 + 集中 × (1+絶好調?) × N          （乗算ごとに切り上げ）
最終パラメータ = 最終基礎 × 好調倍率 × (1+上昇割合加算) × (1+上昇量減少割合)   （毎ステップ切り上げ）
最終スコア = 最終パラメータ × スコアボーナス                                 （切り上げ）
最終元気 = 元気上昇 × 元気上昇率 + 加算 − 減少                               （切り捨て）
```
其中「集中N倍適用」与「好調X%分」是先合算再 ceil 还是各自 ceil，wiki 标注「検証の必要あり」`[転記:seesaawiki]` → §15。

### 5.2 回归测试向量（本家 v1.2.0 实测）`[確認:core lesson-mutation.ts 注释]`
| 状态 | 卡 | 结果 |
|---|---|---|
| 集中0 好調1 絶好調なし | アピールの基本 +9 | 9×1.5=13.5 → **14** |
| 集中4 好調6 絶好調あり | ハイタッチ +17（集中×1.5） | (17+6)×2.1=48.3 → **49** |
| 集中4 好調6 絶好調あり | ハイタッチ+ +23（集中×2.0） | (23+8)×2.1=65.1 → **66** |
| 集中4 好調6 絶好調あり | 初星水 +10 | (10+4)×2.1=29.4 → **30** |
| 集中11 好調あり | ハイタッチ +17（集中×1.5） | 集中分 16.5→17；(17+17)×1.5=**51** `[確認:core types.ts focusMultiplier 注释]` |
| 好調あり スコアボーナス175% | +9 | 13.5→14；14×1.75=24.5→**25**（两次 ceil）`[確認:core types.ts Idol.scoreBonus, issue #81]` |

### 5.3 ターン属性倍率／スコアボーナス
- 考试：每个属性有一个 スコアボーナス%（例 vocal 400 / dance 1400 / visual 1200 表示 ×4 / ×14 / ×12）`[確認:core index.ts 示例]`。数值由 `ProduceExamBattleScoreConfig`（parameter → permil 的分段线性表）按当前参数插值得到，显示值 = permil/10 %（例 produce-001 最終 vovi: parameter 446 → vocalPermil 4402 ≈ 440.2%）`[確認:master]` 插值方式 `[推定]`。
- コンテスト：gakumas-engine `typeMultipliers.js` 的分段函数（按赛季变化，属于コンテスト专属，此处略）。
- 课程：倍率 1（无属性倍率）；追い込みレッスン CLEAR 之后属性条件（【〇〇ターンのみ】）视为恒真 `[確認:core types.ts ignoreIdolParameterKindConditionAfterClearing]`。

### 5.4 好印象结算（ロジック）
回合结束时 `score += 好印象值` 经 §5.1 管线（含 好調/上昇量増加/スコアボーナス；集中也会被加进去——两个模拟器都如此，本家是否如此未验证 `[推定]`）`[確認:core obtainPositiveImpressionScoreOnTurnEnd]` `[確認:engine GOOD_IMPRESSION_EFFECTS]`。「好印象追加発動+n」使该结算重复 n 次 `[確認:engine TurnManager.endTurn]`。

### 5.5 元気计算（floor 方向）
```
元気增量 = value + やる気 × やる気適用倍率(默认 1) [+ boostPerCardUsed × 使用枚数]
         → 「元気増加無効」中为 0；不安中 ×0.67 ；固定元気(fixedGenki) 不受やる気/不安影响
```
kjirou 对 `やる気×倍率` 用 ceil（参照 focusMultiplier）`[確認:core calculatePerformingVitalityEffect]`；seesaawiki 说元気步骤「小数切り捨て」`[転記:seesaawiki]`；engine 不取整（浮点累加）`[確認:engine resolveGenki]`。**采用：分数向上、元気向下** `[転記:seesaawiki]`，倍率为 1 时无差异。

「元気の n% 分パラメータ上昇」：`ceil(元気 × n/100)` 作为基础值进入 §5.1 管线；「元気を半分/0にして」先 `floor(元気×0.5)`/全部 减少再计算 `[確認:core performLeveragingVitality]`。

---

## 6. センス（好調・絶好調・集中）

| 状态 | master 枚举 | 语义 |
|---|---|---|
| 集中 | `ExamLessonBuff` | 累积值；每次パラメータ上昇加算 `集中×倍率`（卡面「集中効果をn倍適用」= 倍率）；不自然衰减 `[確認:master Label_ExamLessonBuff_Produce=集中]` `[確認:core]` |
| 好調 | `ExamParameterBuff` | 回合数；>0 时倍率 1.5；每回合 −1 `[確認:master examParameterBuffPermil=1500]` |
| 絶好調 | `ExamParameterBuffMultiplePerTurn` | 回合数；与好調同时存在时倍率 = 1.5 + 0.1×好調残回合；单独存在无效 `[確認:master examParameterBuffMultiplePerTurnPermil=100]` `[確認:core]` |
| 好調n倍適用 | `goodConditionTurnsMultiplier`(engine) | 倍率 = 1 + (0.5 + 0.1×好調)×n；n=3 → 2.5(+0.3×好調) `[確認:engine resolveScore]` `[転記:seesaawiki]` |
| 集中強化 / 集中増加量増加 | `ExamLessonBuffMultiple` / `ExamLessonBuffAdditive` | 前者乘在集中的效果上，后者乘在集中的获得量上 `[確認:engine concentrationEffectBuffs/concentrationBuffs]` |
| 好調増加量増加 | `ExamParameterBuffAdditive` | 好調获得量 ×(1+Σ) `[確認:engine resolveGoodConditionTurns]` |
| 「好調の n% 分」 | — | `ceil(好調回合数 × n/100)` 作基础值 `[確認:core performLeveragingModifier]` |
| 「集中1.5倍」等 | `multiplyModifier` | `ceil(値×倍率)` `[確認:core multiplyModifier]` |

叠加：同种状态叠加为数值/回合数相加（好調3 + 好調2 = 5 回合）`[確認:core getModifier duration 累加]`。

---

## 7. ロジック（やる気・好印象・プライド）

| 状态 | master 枚举 | 语义 |
|---|---|---|
| やる気 | `ExamCardPlayAggressive`（注意：master 命名里 “Aggressive” = やる気） | 累积值；每次元気上昇加算 `やる気×倍率`；不衰减 `[確認:master Label_ExamCardPlayAggressive_Produce=やる気]` `[確認:core]` |
| 好印象 | `ExamReview` | 累积值；回合结束按 §5.4 产分；**每回合 −1**（kjirou 按 amount −1 处理）`[確認:core decreaseEachModifierDurationOverTime positiveImpression]` `[確認:engine EOT_DECREMENT_FIELDS]` |
| 好印象強化 / 好印象増加量増加 / 好印象追加発動 | `ExamReviewMultiple` / `ExamReviewAdditive` / `ExamReviewCountAdd` | 分别乘在 好印象产分、好印象获得量、结算次数上 `[確認:engine goodImpressionTurnsEffectBuffs/…Buffs/…TimesBuffs]` |
| やる気増加量増加 / 追加 | `ExamAggressiveAdditive` / `ExamAggressiveAdditiveFix` | 获得量 ×(1+Σ) / +Σ `[確認:engine resolveMotivation]` |
| プライド | `ExamLessonValueMultipleDependReviewOrAggressive` | 回合数；分数 +min(2%×min(好印象,やる気), 50%) `[確認:master 20/500 permil]` `[確認:engine prideTurns]` |
| 「やる気の n% 分」「好印象の n% 分」 | — | `ceil(値×n/100)` 作基础值 `[確認:core]` |
| 「やる気効果を n 倍適用」 | `motivationMultiplier` | 元気增量中 やる気×n `[確認:core VitalityUpdateQuery.motivationMultiplier]` |

---

## 8. アノマリー（指針・全力値・熱意）

### 8.1 指針（Stance）状态机 `[確認:engine BuffManager.setStance, constants.STANCES]`
状态：`none / strength(強気1) / strength2(強気2) / preservation(温存1) / preservation2(温存2) / leisure(のんびり) / fullPower(全力)`。

| 指針 | 分数倍率 | 体力消耗倍率 | 其他 |
|---|---|---|---|
| 強気1 | ×2.0 + 強気強化 | ×2 | `[確認:master 2000‰]` |
| 強気2 | ×2.5 + 強気強化 | ×2，且每次出牌固定体力 −1 | `[確認:master 2500‰, PenetrateReduce2=1]` |
| 温存1 | ×0.5 | ×0.5 | |
| 温存2 | ×0.25 | ×0.25 | |
| のんびり | ×0 | ×0 | 温存已 2 段时再温存不进入のんびり（engine：leisure 由卡直接设置；处于 leisure 时对 preservation 的 set 被忽略）`[確認:engine setStance]` |
| 全力 | ×3.0 + 全力強化 | ×1 | 进入时 使用数+1、保留卡全部回手 `[確認:engine FULL_POWER_CHANGED_EFFECTS]` |

转移规则 `[確認:engine setStance]`：
- 同系再施加 → 升到 2 段（強気→強気2，温存→温存2）；升段不算「指針変更」但触发 `stanceValueChanged`。
- 全力中只能被 `setStance(none)` 解除；指針固定（`lockStanceTurns>0`）期间任何变更无效。
- 从温存/のんびり离开（且目标不是のんびり）时的“解除奖励”：温存1 → 熱意+5、使用数+1；温存2 → 熱意+8、固定元気+5、使用数+1；のんびり → 固定元気+5、使用数+1，且目标≠全力时 熱意+10，目标=全力时 全卡 成長 パラメータ+10 `[確認:master ExamSetting preservationRelease*/overPreservationRelease*]` `[確認:engine STANCE_CHANGED_EFFECTS]`。
- 熱意获得公式（含增幅）：`熱意 += ceil((基礎N + Σ熱意追加) × (1 + Σ熱意増加%))`，N = 5/8/10 `[確認:ext/gakumasu-anomaly-sim README「Wiki 準拠の熱意モデル」]` `[確認:engine resolveEnthusiasm: (v + Σbonus) × (1+Σbuffs)]`。
- 熱意（ExamGimmickEnthusiastic）只在当回合有效，回合结束清零；每次出分把 `熱意×熱意適用倍率` 加进 S1 `[確認:engine TurnManager.endTurn enthusiasm=0; resolveScore]`。
- 「直接効果」（isDirectEffect）：由技能卡效果/费用、卡移动到手札/保留、技能卡发起的発動予約、或进入全力 引起的指針变更算“直接”，用于 `if:isDirectEffect` 条件 `[確認:engine BuffManager.variableResolvers.isDirectEffect]`。

### 8.2 全力値 `[確認:engine constants.FULL_POWER_EFFECTS, resolveFullPowerCharge]`
- 累积值（`fullPowerCharge`），获得时 ×(1+Σ全力値増加量増加%)；同时累计 `cumulativeFullPowerCharge`。
- 回合开始：若已是全力 → 先解除；然后若 `未指針固定 && 全力値 ≥ 10` → 全力値 −10、进入全力（因此全力回合内再攒到 10，下回合可连续全力）`[検索要約:note.com たちばな]`。
- 「全力値減少」(`decreaseFullPowerCharge`) 视为低下状態（可被 低下状態無効 挡）`[確認:engine CHANGELOG 2025-12-08]`。

### 8.3 回归线索
- 「Fix full power effect activation order」(2026-07-31)、「changed order of card discard/removal vs afterCardUsed effect activation」(2026-05-09) `[確認:engine CHANGELOG]` — 表明这些顺序在近期被校正过；实现时对照 engine 当前版本。

---

## 9. 状态效果目录（状態／強化状態／低下状態）

官方名称来自 `ProduceDescriptionLabel.name`，枚举为 `ProduceExamEffectType_*`（`ExamStatusEnchant.produceDescriptions[].targetId = Label_*`）`[確認:master]`。“类型”列：`stack` 累积值、`turns` 回合数（§3.5 递减）、`count` 次数、`flag`。语义列证据为引擎实现。

| 官方名 (JP) | 枚举 (去前缀) | 类型 | 语义 / 数值 | 低下? |
|---|---|---|---|---|
| パラメータ | ExamLesson | — | 出分动作 | |
| 元気 | ExamBlock | stack | 先于体力承担 normal 费用 | |
| 固定元気 | ExamBlockFix | — | 不经やる気/不安 的元気增量 | |
| 体力回復 / 体力消費 / 体力減少 | ExamStaminaRecoverFix / ExamStaminaReduceFix / ExamStaminaDamage | — | 回复（不超上限）/ 费用（穿透元気）/ 伤害 | |
| 好調 / 絶好調 | ExamParameterBuff / ExamParameterBuffMultiplePerTurn | turns | §6 | |
| 集中 | ExamLessonBuff | stack | §6 | |
| やる気 | ExamCardPlayAggressive | stack | §7 | |
| 好印象 | ExamReview | stack(每回合−1) | §7 | |
| プライド | ExamLessonValueMultipleDependReviewOrAggressive | turns | +2%×min(好印象,やる気) ≤50% | |
| 温存 / のんびり / 強気 / 全力 / 全力値 / 熱意 | ExamPreservation / ExamOverPreservation / ExamConcentration / ExamFullPower / ExamFullPowerPoint / ExamGimmickEnthusiastic | stance / stack | §8 | |
| 指針固定 | StanceLock | turns | 期间指針不可变更；全力判定被跳过 | 低下 `[確認:engine DEBUFF_FIELDS]` |
| 指針解除 | ExamStanceReset | — | 指針→none | |
| スキルカード使用数追加 | ExamPlayableValueAdd | count(1回合) | §3.3 | |
| スキルカード追加発動 | ExamCardSearchEffectPlayCountBuff | count | 下一张(指定类型)卡效果发动 2 次；同时持有多个也只重复 1 次；对 L(レジェンド) 卡无效 `[確認:core useCard 注释+视频]` `[確認:engine useCard rarity!=="L"]` | |
| 発動予約 | ExamEffectTimer | delay | 「次のターン/nターン後、…」；回合开始按 §3.2 步骤 8 顺序发动；技能卡/Pドリンク 的発動予約自 2025/6/19 起被归为「直接効果」`[転記:seesaawiki]` `[確認:engine EffectManager.setEffects type=reservation]` | |
| 持続効果 | ExamStatusEnchant | — | 「以降、〜時、〜」类反应型效果（Pアイテム/応援/トラブル 的才是真持続効果）`[転記:seesaawiki]` | |
| 再演 | ExamStatusEnchantEncore | — | 再次发动一个持續効果 `[推定]` | |
| ターン追加 | ExamExtraTurn | — | 剩余回合 +n，复制末回合属性 | |
| パラメータ上昇量増加 / 減少 | ExamLessonValueMultiple / ExamLessonValueMultipleDown | turns（也有永続） | M3 中 ±% 加总 `[確認:engine scoreBuffs/scoreDebuffs]`；kjirou 按百分比分组合并回合数（本家未明）`[確認:core mightyPerformance 注释 issue #110]` | 減少=低下 |
| 消費体力減少 / 増加 | ExamStaminaConsumptionDown / Add | turns | ×0.5 / ×2（§4.3） | 増加=低下 |
| 消費体力削減 / 追加 | ExamStaminaConsumptionDownFix / AddFix | stack | 费用 −n / +n（乘算后加减） | 追加=低下 |
| 消費体力増加無効 / 消費体力減少効果増加 | ExamStaminaThresholdAddRestriction / ExamStaminaConsumptionDownAdd | — | 语义按名 | |
| 元気増加無効 | ExamBlockRestriction | turns | 元気增量为 0（固定元気除外?）`[確認:engine nullifyGenkiTurns]` | 低下 |
| 不安 | ExamBlockAddDown | turns | 元気增量 ×0.67 | 低下 |
| 不調 | ExamGimmickParameterDebuff | turns | 分数 ×0.67 | 低下 |
| 緊張 | ExamGimmickLessonDebuff | turns | パラメータ上昇量減少 类（engine setScoreDebuff）`[推定]` | 低下 |
| 弱気 | ExamGimmickSleepy | turns | アクティブ/メンタル使用不可 类 `[推定]` | 低下 |
| スランプ | ExamGimmickSlump | turns | 语义待查 `[推定]` | 低下 |
| 手札減少 | ExamGimmickStartTurnCardDrawDown | turns | 回合开始少抽 | 低下 |
| スキルカード使用不可 | ExamGimmickPlayCardLimit | turns | 全部/アクティブ/メンタル 不可用 `[確認:engine noCardUseTurns/noActiveTurns/noMentalTurns]` | 低下 |
| 気まぐれ | ExamPanic | — | 随机体力消耗（候选表见 §1） | 低下 |
| 疲労 | ExamGimmickTiredFix | — | 语义待查 | 低下 |
| 低下状態無効 | ExamAntiDebuff | count | 每挡下一个低下状態消耗 1 次；kjirou 实现为“阻止付与”`[確認:core getModifier debuffProtection]`；engine 的 `removeDebuffs(n)` 是「低下状態回復」清除已存在的 n 种 `[確認:engine BuffManager.removeDebuffs]` | |
| 低下状態回復 | ExamDebuffRecover | — | 清除 n 种低下状態 | |
| 体力回復無効 | ExamStaminaRecoverRestriction | turns | | 低下 |
| 高揚 | ExamUplifting | — | 语义待查 `[推定]` | |
| レッスン中強化 | ExamCardUpgrade | — | 手牌/指定卡在本对局内升 1 级（与プロデュース中強化互斥，最多 3 段 +）`[確認:core types.ts Card.enhancements]` | |
| 生成 / 複製 | ExamCardCreateId / ExamCardDuplicate | — | 生成指定卡/随机强化卡到手札（无视重複不可）`[確認:core generateCard]` | |
| 成長 | ExamAddGrowEffect | — | 对目标卡永久（本对局）改写 `g.*` 字段（パラメータ値増加/上昇回数増加/コスト値減少/…）`[確認:engine Effects.md Growth]` | |
| 直接効果 | Label_OnHitEffect | — | 见 §8.1 | |

低下状態集合（engine `DEBUFF_FIELDS`）：消費体力増加、消費体力追加、元気増加無効、アクティブ使用不可、メンタル使用不可、不安、不調、指針固定、カード使用不可；特殊动作 `setScoreDebuff`、`decreaseFullPowerCharge` 也视为低下 `[確認:engine constants]`。

---

## 10. 技能卡（スキルカード）规则

- 分类：`アクティブ`（有パラメータ上昇）/ `メンタル` / `トラブル`（眠気 等）`[確認:core types.ts CardSummaryKind]`；プラン：共通(free) / センス / ロジック / アノマリー `[確認:master Label_ProducePlanType0-3]`；稀有度 N/R/SR/SSR + L（レジェンド）+ T（トラブル）`[確認:engine constants.RARITIES]`。
- 强化：プロデュース中強化（+）与レッスン中強化互斥，各自最多使卡到 `+`；加上レッスンサポート（サポカ临时强化，蓝色 +）总强化数 ≤3；卡数据的 `contents[0..3]` 对应 +0…+3 `[確認:core types.ts CardData.contents, Card.enhancements]`。カスタマイズ：按 level 块打补丁（同一时刻只有一个 level 生效）`[確認:engine Effects.md Customization]`。
- 「レッスン中1回」：使用后进除外堆（不回收）；否则进捨札 `[確認:core useCard usableOncePerLesson]` `[確認:engine useCard skillCard.limit]`。カスタマイズ可把 limit 改为 0（可重复）`[確認:engine]`。
- 「重複不可」（`nonDuplicative`）：デッキ中不能持有 2 张；生成效果无视此限制 `[確認:core types.ts]`；engine 对 unique 卡去重只保留最强化的一张（L/T 除外）`[確認:engine IdolConfig.getDedupedCards]`。
- 「レッスン開始時手札に入る」：§2。
- 「保留」：把卡移到保留区（≤2）；进入全力时全部回手 `[確認:engine hold*/moveHeldCardsToHand]`。
- 效果结算：卡内效果按行顺序发动，后行受前行影响；但每行的**条件**按出牌前状态判定（例：楽観的 在无好調时集中+1 不发动）`[確認:core activateEffectsOnCardPlay, issue #95]`。
- 「レッスン中に使用したスキルカードn枚ごとに」计数包含当前这张 `[確認:core issue #203]`。
- 固有卡：Pアイドル 固有卡（特訓 Lv≥3 时为强化版）、Pアイテム 固有（才能開花 Lv≥2 强化）`[確認:core index.ts specialTrainingLevel/talentAwakeningLevel]`。
- 初始牌组：`ProduceInitialDeck` / `ExamInitialDeck`（master）；コンテスト默认卡组按プラン固定 8 张 `[確認:engine IdolStageConfig CONTEST_DEFAULT_CARD_IDS_BY_PLAN]`。

### 10.1 出牌时序（技能卡使用一次的内部顺序）`[確認:core index.ts playCard 注释, 全部附视频]`
```
1 手札から消費（除外 or 捨札）        ※engine 把 弃/除外 放在主效果之后、afterCardUsed 之前 (2026-05-09 校正)
2 コスト消費
3 [「もう1回発動」があれば 3 全体を 2 回]
  3-a もう1回発動 を 1 つ消費
  3-b Pアイテム「スキルカード使用時」(before)
  3-c 持続効果「〜使用時」(before)          ※3-b > 3-c 实测
  3-d Pアイテム「n回使用するごとに」
  3-e 主効果
  3-f Pアイテム「〜使用後」
  3-g 持続効果「〜使用後」                  ※3-f/3-g 顺序不明（无法同时持有）
  3-h Pアイテム「〇〇が増加後」            ※只对主効果引起的增加触发，Pドリンク/持続効果引起的增加不触发
  3-i Pアイテム「体力が減少した時」
4 使用数追加の繰り上げ処理 (§3.3)
```
engine 阶段名：`beforeCardUsed → processCost → cardUsed/activeCardUsed/mentalCardUsed → processCard(主効果, 追加発動时 2 次) → 弃/除外(cardRemoved) → buffCostConsumed → afterCardUsed/after{Active,Mental}CardUsed` `[確認:engine CardManager.useCard]`。

### 10.2 效果动词 / 条件 词汇（DSL 设计输入）
gakumas-engine `Effects.md` 是目前最完整的可执行词表；建议 `engine/effects.py` 的 op 集合以它为超集，并映射到 master 枚举：

- **阶段（at:）**：startOfStage, afterStartOfStage, prestage, beforeStartOfTurn, startOfTurn, afterStartOfTurn, turn(nターン後), everyTurn(nターンごと), endOfTurn, turnSkipped, cardUsed/activeCardUsed/mentalCardUsed, afterCardUsed/…, processCard, processCost, checkCost, cardMovedToHand, cardMovedToHeld, cardRemoved, buffCostConsumed, stanceChanged, stanceValueChanged, staminaDecreased, genkiIncreased, goodConditionTurnsIncreased, concentrationIncreased, goodImpressionTurnsIncreased, motivationIncreased, fullPowerChargeIncreased `[確認:engine Effects.md]`。对应 master `ProduceExamPhaseType_*`：ExamStartExam, StartPlay, ExamStartTurn, ExamEndTurn, ExamCardPlay, ExamCardPlayAfter, ExamPlayCountInterval(After), ExamTurnInterval, ExamTurnTimer, ExamStatusChange, ExamBuffConsume, ExamStanceChange{Concentration,Preservation,FullPower,FromFullPower,FromConcentration,CountInterval}, ExamTurnSkip, ExamStaminaReduce(Card), ExamCardMove{Hand,Grave,Lost}, ExamSearchCardPlay, ExamAggressiveUpInterval `[確認:master ProduceExamTrigger.phaseTypes]`。
- **动作**：`score/genki/stamina/fixedGenki/fixedStamina/goodConditionTurns/perfectConditionTurns/concentration/goodImpressionTurns/motivation/prideTurns/fullPowerCharge/enthusiasm/cardUsesRemaining/turnsRemaining ± n`、`drawCard(n)`、`upgradeHand`、`exchangeHand`、`addCardToHand/Deck/TopOfDeck(id)`、`moveRandom/Selected/AllToHand[...]`、`moveAllToTopOfDeck/Deck[...]`、`holdRandom/All/This`、`useRandom/All/SelectedFree[...]`、`removeAll[...]`、`moveHeldCardsToHand`、`removeDebuffs(n)`、`setStance(x)`、`decreaseFullPowerCharge(n)`、`setScoreBuff/Debuff`、`setGoodImpressionTurns{Buff,EffectBuff,TimesBuff}`、`setMotivationBuff`、`setGoodConditionTurnsBuff`、`setConcentration{Buff,EffectBuff}`、`setEnthusiasm{Buff,Bonus}`、`setFullPowerCharge{Buff}`、`setFullPowerEffectBuff`、`setStrengthEffectBuff`、成長 `g.score/g.scoreTimes/g.cost/g.typedCost/g.genki/g.goodConditionTurns/g.perfectConditionTurns/g.concentration/g.goodImpressionTurns/g.motivation/g.fullPowerCharge/g.halfCostTurns/g.scoreBy{GoodImpressionTurns,Motivation,Genki}/g.stanceLevel` `[確認:engine Effects.md]`。
- **条件变量**：turnsElapsed/turnsRemaining/cardUsesRemaining/stamina/maxStamina/genki/score/cardsUsed/activeCardsUsed/turnCardsUsed/各 buff 值/stance/prevStance/isVocalTurn…/isStrength/isPreservation/isFullPower/isDirectEffect/stanceChangedTimes/usedCardId/lastUsedCardType/cardHasEffect(x)/cardSourceType/cardRarity/countCards[target]/effectCounter/各 *Delta `[確認:engine Effects.md]`。
- **kjirou 的抽象（更贴近原文语法）**：效果 kind = drainLife / drainModifier / drawCards / enhanceHand / exchangeHand / generateCard / generateTroubleCard / increaseRemainingTurns / getModifier / multiplyModifier / perform{score{value,times,focusMultiplier,boostPerCardUsed},vitality{value,fixedValue,motivationMultiplier,boostPerCardUsed}} / performLeveragingModifier{modifierKind,valueKind,percentage} / performLeveragingVitality{reductionKind,percentage} / recoverLife；条件 kind = countModifier{range} / countRemainingTurns{max} / countVitality{range} / measureValue{life|score, ≥/≤, %}；使用条件 = countTurnNumber / countVitalityZero / hasGoodCondition / measureValue `[確認:core types.ts]`。
- 修饰：`limit:N`（对局内最多发动 N 次）、`ttl:N`、`delay:N`、`group:N`（同阶段发动顺序，小者先）`[確認:engine Effects.md]`。

---

## 11. Pアイテム / Pドリンク

### 11.1 Pアイテム
- 触发类别（kjirou `ReactiveEffectTrigger.kind`）：lessonStart / turnStart / turnStartEveryNTurns / turnEnd / beforeCardEffectActivation(〜使用時) / afterCardEffectActivation(〜使用後，可限定「元気効果の」「好印象効果の」) / beforeCardEffectActivationEveryNTimes(n回使用するごとに) / modifierIncrease(〜が増加後) / lifeDecrease(体力が減少した時)，可附加「【〇〇レッスン・〇〇ターンのみ】」属性限定 `[確認:core types.ts ReactiveEffectTrigger]`。
- 发动次数「（レッスン内n回）」：`ProducerItemContentData.times`，剩余 = times − 已发动 `[確認:core models.ts getRemainingProducerItemTimes]`；engine 用 `limit:N` `[確認:engine]`。
- 发动条件（1 行目）对整个道具生效；条件判定用当前状态；费用在效果后支付（§4.3）。
- 同一触发点多个道具按**获得顺序**（列表顺序）发动；每发动一个后重新检查 PERFECT，达到即停止 `[確認:core activateProducerItemEffectsOnTurnStart]`。
- 「〇〇が増加後」只对技能卡主效果造成的增加触发（持続効果/Pドリンク 造成的不触发）`[確認:core types.ts modifierIncrease 注释+视频]`。
- 强化版（才能開花）用 `enhanced` 内容替换 `[確認:core]`。

### 11.2 Pドリンク
- 持有上限 3（可提升到 4）`[確認:master ProduceSetting]`；使用不耗出牌次数、无使用条件（只需能支付其费用）；顺序：移除饮料 → 支付费用 → 按行发动效果 `[確認:core useDrink]`。饮料效果引起的增加不触发「増加後」道具（§11.1）。
- 效果集合与技能卡相同（含「もう1回発動」「パラメータ上昇量増加」「消費体力減少」等）`[確認:core types.ts DrinkData 例]`。

### 11.3 応援 / トラブル（考试事件）
- 在指定回合开始时（§3.2 步骤 4）发动一个效果（可带条件）`[確認:core types.ts Encouragement]`；コンテスト的更复杂形式不在本文范围。

---

## 12. 随机性 vs 确定性

| 随机源 | 说明 |
|---|---|
| 山札洗牌（开局、捨札回收） | 唯一系统性随机；seeded RNG 必须覆盖 `[確認:core utils.shuffleArray]` |
| 考试回合属性序列 | 首回合按分布、中段洗牌、末 3 回合固定（§3.1） |
| 「ランダムな〜」效果 | 随机生成卡（SSR 强化随机）、随机移动/保留卡、眠気插入山札随机位置 `[確認:core generateCard/generateTroubleCard]` |
| メモリー アビリティ | 每个 ability 有发动概率 % `[確認:core activateMemoryEffect]` |
| 気まぐれ | 体力消耗从候选表抽样（§1） |
| Pアイテム/Pドリンク/状态效果本身 | 确定性（无隐藏概率） |
| 分数/费用计算 | 完全确定性（整数运算） |

---

## 13. 基线策略（AutoPlay 复刻 + 启发式）

### 13.1 官方 AutoPlay（ProduceExamAutoEvaluation）
- 表结构：`ProduceExamAutoEvaluation {type: ExamPlayType, examEffectType, remainingTerm, evaluationType: ProduceExamAutoEvaluationType, evaluation(int), examStatusEnchantCoefficientPermil}`，共 11130 行 = 5 种 ExamPlayType（AutoPlay / ManualPlayLesson / ManualPlayLessonHard / ManualPlayAudition / AutoPlayCompetition）× 2226 `[確認:master]`。`ProduceExamAutoTriggerEvaluation {type, examStatusEnchantProduceExamTriggerId, coefficientPermil}` 用于持续/延迟效果。
- 算法（Vibbit 逆向 `Campus.InGame.Exam.ExamRuleCalculator.Evaluate`，转记自 research doc；原页 blog.vibbit.me 本会话被阻断）：对每张可出牌模拟出牌，计算 `evaluation = Σ_n floor(v_n × w_n)`，v1=分数、v2=元気、v3=体力、v4=集中、v5=好印象、v6=やる気、v7=min(好調,残ターン)、v8=好調ターン … v18=追加ターン；v1.4.0 共 19 项，r19 = Σ floor(m1×m2+0.0001)，m1 = coefficientPermil/1000 × 残回合；审查战 r1 = round(v1×3000/(dance+vocal+visual permil), 6)；无匹配 coefficientPermil 的卡默认权重 1（导致 AI 几乎不出「輝くキミへ」）`[転記:docs/research/user_report_02 ← blog.vibbit.me 2024/09, 2024/11]`。
- 可直接读表的权重示例（type=AutoPlay, remainingTerm=1）`[確認:master]`：examEffectType=強気(ExamConcentration)：Parameter 353、PlayableValueAdd 5118；好印象(ExamReview)：Parameter 162、PlayableValueAdd 568、ExamExtraTurn 47432；Vibbit 样例：やる気卡的 ExamStaminaConsumptionAdd 权重 −585。evaluationType 全集（53 种）：Parameter, Block, Stamina, RemainTurn, HoldCount, DrawCardCount, PlayableValueAdd, ExamLessonBuff, ExamReview, ExamCardPlayAggressive, ExamParameterBuff, ParameterBuffMultiplePerTurn, ParameterBuffOverTurn, ExamConcentration(Count), ExamPreservation(Count), ExamFullPower(Count), ExamFullPowerPointTotal/Additive, ExamEnthusiastic{Additive,Multiple}, ExamLessonValueMultiple(+DependReviewOrAggressive), ExamStaminaConsumption{Add,Down,DownFix}, ExamAntiDebuff, ExamBlockAddDown, ExamBlockRestriction, ExamBuffConsumption{Add,Down}, ExamGimmick{LessonDebuff,ParameterDebuff,Sleepy,Slump}, ExamGrowEffectLessonAddAdditive, ExamLessonBuffAdditive, ExamParameterBuffAdditive, ExamParameterBuffTurnEndReduceLock, ExamReview{Additive,CountAdd,Multiple,TurnEndReduceLock}, ExamAggressiveAdditive, ExamExtraTurn, ExamConcentrationLessonMultipleAdditive, ExamFullPowerLessonMultipleAdditive, StanceLock{,Concentration,FullPower,Preservation} `[確認:master]`。
- 搜索深度 `examAutoPlaySearchCommandLimit=5` `[確認:master ExamSetting]`。
- 实现建议：`agents/autoplay.py` 读表构造 `w[examEffectType][evaluationType][remainingTerm]`，对候选动作（出牌/饮料/结束）做 1 步模拟并按上式打分，作为 baseline。

### 13.2 gakumas-engine HeuristicStrategy（可作第二基线）`[確認:engine strategies/HeuristicStrategy.js]`
深度优先枚举本回合所有出牌序列（`MAX_DEPTH`），叶子状态价值 = 加权和：手牌×3、已用卡×8、体力×残回合×0.05、元気×tanh(残/3)×0.7×やる気系数、好調 min(好調,残)×1.6×系数、絶好調 min(絶,残)×好調×1.5×系数、集中×残×系数(推奨効果=集中时 3)、好印象×残×系数(3.5)、やる気×残×0.45×系数(5.5)、プライド×残×0.2、scoreBuffs×8、消費体力減少 min(,残)×6、増加×−6、削減×残×0.5、追加発動×50、使用数追加×50、元気増加無効×−9、レッスン中強化×20、アノマリー：強気回数×40、温存/のんびり/全力回数×80、熱意×5、累計全力値×3、成長×0.2×残；乘 平均属性倍率 后再按推奨効果加 `score × {好調0.4, 集中0.6, 好印象1.1, やる気0.6, 強気0.65}`。

---

## 14. 与 master data 的映射速查
| 规则 | 表 / 字段 |
|---|---|
| 手牌/抽牌/保留/skip 回复/各倍率 | `ExamSetting.*`（§1） |
| 课程回合数、CLEAR、PERFECT | `ProduceStepLessonLevel.limitTurn / successThreshold / resultTargetValueLimit` |
| 考试回合数、属性权重、スコアボーナス曲线 | `ProduceExamBattleConfig.turn/vocal/dance/visual` → `ProduceExamBattleScoreConfig` |
| 考试合格名次、基准分、强制结束分 | `ProduceStepAuditionDifficulty.rankThreshold / baseScore / forceEndScore / parameterBaseLine` |
| 效果语义 | `ProduceExamEffect.effectType(ProduceExamEffectType_*) + effectValue1/2/effectCount/effectTurn` |
| 触发时机 | `ProduceExamTrigger.phaseTypes(ProduceExamPhaseType_*) + phaseValues + fieldStatusCheckTypes` |
| 状态名称/图标 | `ProduceExamStatusEnchant` → `ProduceDescriptionLabel` |
| 卡牌位置 | `ProduceCardMovePositionType_*` / `Label_ProduceCardPositionType_*` |
| AutoPlay 权重 | `ProduceExamAutoEvaluation`, `ProduceExamAutoTriggerEvaluation` |
| 饮料上限 | `ProduceSetting.produceDrinkPossessLimit / MaxLimit` |

---

## 15. 未决 / 待验证清单（实现为可配置开关 + 对拍用例）
1. 集中倍率与好調百分比的 ceil 先后（seesaawiki「検証の必要あり」）。
2. 好印象结算是否吃 集中 / 好調（两模拟器均吃，本家未验证）。
3. 消費体力減少+増加 共存的合成倍率：×1（模拟器）vs ×1.25（`examStaminaConsumptionAddDownPermil=1250` 暗示）。
4. `examStaminaConsumptionDownAddPermil=600`、`examStaminaReduceChange=1`、`examBuffConsumption*` 的精确语义。
5. 手牌满 5 时生成/抽到的卡去向（山札顶 vs 捨札）；innate ≥8 张的分配。
6. 「ターン開始時」新付与的持续状态是否当回合递减。
7. 3-f 与 3-g、3-f 与 3-h 的先后（无法同时持有，实现上可任选并记录）。
8. 「低下状態無効」是阻止付与还是移除已有；对哪些效果生效（消費体力増加 已确认）。
9. 百分比条件（体力 50% 以上/以下）的取整方向。
10. 緊張 / 弱気 / スランプ / 高揚 / 疲労 / 再演 的精确数值语义（可从 `ProduceExamEffect` 对应行的 effectValue 读出，需逐条核对）。
11. 考试回合属性序列生成算法是否与本家一致（engine 的“末 3 回合固定”是コンテスト观察）。
12. Pアイテム「体力減少」是否先扣元気。
