# 学マス 培育外循环规则（プロデュース：初 Hajime / N.I.A. 基线）

> 目的：为 `produce/` 与 `scenarios/*.yaml` 提供可实现的周程状态机、各行动的数值效果、参数上限、思い出生成与最終評価公式。H.I.F 专属规则见 `docs/scenarios/hif.md`；对局内规则见 `docs/rules/lesson_exam_engine.md`（下称 *engine 文档*）。
>
> 证据等级标注同 engine 文档：`[確認:master <Table>.<field>]`（vertesan/gakumasu-diff 官方 master data）、`[確認:code <repo> <file>]`、`[確認:web <URL>]`、`[転記:seesaawiki]`（转记自 `docs/research/user_report_02_data_and_formulas.md`，本会话 seesaawiki 被出口代理阻断）、`[検索要約:<URL>]`（仅 WebSearch 摘要）、`[推定]`。

---

## 1. 剧本 / 难度总表 `[確認:master Produce.yaml, ProduceGroup.yaml, ProduceSetting.yaml]`

| produceId | ProduceGroup | 名称 | 周数 `steps` | 参数上限 `idolCardParameterGrowthLimit` | 开始消耗 AP `actionPointQuantity` | `baseStepLevel` | 卡再抽选 `maxRefreshCount` | ProduceSetting |
|---|---|---|---|---|---|---|---|---|
| produce-001 | 001 定期公演『初』 | レギュラー | 13 | 1000 | 15 | 1 | 0 | p_setting-1 |
| produce-002 | 001 | プロ | 16 | 1500 | 20 | 5 | 0 | p_setting-2 |
| produce-003 | 001 | マスター | 18 | 1800 | 20 | 5 | 0 | p_setting-3 |
| produce-006 | 001 | レジェンド | 18 | 3000 | 20 | 5 | 4 | p_setting-6 |
| produce-004 | 002 NEXT IDOL AUDITION | プロ | 27 | 2000 | 20 | 1 | 4 | p_setting-4 |
| produce-005 | 002 | マスター | 26 | 2600 | 20 | 1 | 4 | p_setting-5 |
| produce-007/008 | 003 Hatsuboshi IDOL FESTIVAL | 選抜試験 / 本戦 | 20 / 9 | 3000 | 20 | 1 | — | p_setting-7/8 |

- 社区常引用的上限「レギュラー1000 / プロ1500 / マスター1800 / N.I.A 2000 / NIAマスター2300」`[転記:seesaawiki]` `[検索要約]` 中 NIA マスター 已被 master data 更新为 **2600**（gakumas-tools `nia.js MAX_PARAMS_BY_DIFFICULTY.master=2600` 同步）`[確認:master]` `[確認:code gakumas-tools utils/nia.js]`；レジェンド 上限 3000（gakumas-tools `produceRank.js`；gakumas-rl 旧移植为 2800）`[確認:code]`。
- 参数上限可被效果 `ProduceEffectType_ParameterLimitUp` 抬高 `[確認:master ProduceEffect]`。
- ProduceGroup 的 `limitGrade`（评价封顶）：初 = SSSS(26000)、NIA = SSS+(23000)、HIF = SSSSS(35000) `[確認:master ProduceGroup.limitGrade]`。
- `ProduceSetting` 关键字段 `[確認:master]`：

| 字段 | 初 (1/2/3) | レジェンド(6) | NIA プロ(4) | NIA マスター(5) | 语义 |
|---|---|---|---|---|---|
| `produceDrinkPossessLimit` / `MaxLimit` | 3 / 4 | 3 / 4 | 3 / 4 | 3 / 4 | Pドリンク 持有上限（可被 `ProduceDrinkPossessLimitUp` 提到 4） |
| `refreshStaminaRecoveryPermil` | 700 | 700 | 700 | 700 | 休む 回复 = 最大体力 × 70% |
| `beforeAuditionRefreshStaminaRecoveryPermil` | 700 | 700 | 500 | 500 | 試験/オーディション 前自动回复比例 |
| `stepSkipStaminaRecoveryPermil` | 250 | 250 | 250 | 250 | 跳过某步时回复 25% `[推定]` |
| `customizeProduceCardCount` | 1 | 2 | 1 | 2 | 可カスタマイズ 卡数 |
| `stepIntervalUpgradeProduceCardCount` / `CustomizeProduceCardCount` | 1 / 2 | 1 / 2 | 1 / 2 | 1 / 2 | 每步可强化 1 张 / カスタマイズ 2 张 `[推定]` |
| `continueCount` | 3 | 3 | 3 | 3 | 试验失败可コンティニュー次数 |
| `examStartAlertStaminaThreshold` | 10 | 10 | 10 | 10 | 试验前体力警告阈值 |

---

## 2. 周程（初）

### 2.1 步骤类型（`ProduceStepType_*`）`[確認:master]`
`LessonVocal/Dance/VisualNormal`（通常レッスン）、`…Sp`（SPレッスン）、`Refresh`（休む）、`EventActivity`（活動支給）、`EventSchool`（授業）、`Present`/`FanPresent`（プレゼント）、`AuditionMid1`/`AuditionMid2`/`AuditionFinal`（中間/最終試験，NIA 的一次/二次/最終オーディション）、`Business`（営業，NIA）、`SelfLesson…`（自主練，NIA）、`OpenLesson…(Star)`（HIF）。追い込みレッスン 在 master 里是 `ProduceStepLesson.name=追い込みレッスン` 且 level id 含 `hard` `[確認:master ProduceStepLesson]`。

### 2.2 各难度周表
标记：`L` 通常/SP レッスン 可选（括号内 通常/SP 的 PERFECT 值）、`H` 追い込みレッスン（PERFECT 总值；主/副属性）、`C` 授業（+主属性）、`O` おでかけ、`A` 活動支給、`S` 相談、`R` 休む（每周皆可）、`M` 中間試験、`F` 最終試験。

**レギュラー（13 周）**`[確認:code gakumas-tools utils/lessons.js regular]`：

| 周 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 内容 | L(50) | 自由 | L(50/80) | 自由 | H(300; 150/75) | M | 自由 | 自由 | L(80/140) | L(80/140) | 自由 | H(400; 200/100) | F |

**プロ（16 周）**`[確認:code lessons.js pro]`：

| 周 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 内容 | L(60) | 自由 | 自由 | L(60/90) | 自由 | H(360; 180/90) | M | 自由 | 自由 | L(110/170) | 自由 | L(120/200) | L(150/220) | 自由 | H(600; 310/145) | F |

**マスター（18 周）**`[確認:code gakumas-hajime-simulator schedule/Container.tsx hajime_m]` `[確認:code lessons.js master]`：

| 周 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 内容 | C(+50) | C(+50) | A/O | S/O | L(60/90) | A/O/S | H(360; 180/90) | M | A/O/S | C(+80)/O | L(110/170) | C(+110)/O | A/O | L(120/200) | L(150/220)/C(+110) | A/O/S | H(600; 310/145) | F |

「自由」周 = 休む/おでかけ/相談/活動支給/授業 中按周开放的子集 `[推定]`（レギュラー/プロ 的自由周构成未从 master 逐周核对；master 的 `ProduceStepTransition`/`ProduceStepEventDetail` 记录了每周可选项，schema atlas 负责）。

### 2.3 与 master `ProduceStepLessonLevel` 的对应 `[確認:master]`
| produce | 通常レッスン (turn, CLEAR/PERFECT) | SPレッスン | 追い込み | 授業(レッスン化) |
|---|---|---|---|---|
| 001 レギュラー | (5,25/50) (6,40/80) | (5,40/80) (6,70/140) | (9,75/300) (10,100/400) | — |
| 002 プロ / 003 マスター | (5–6,30/60) (6–7,55/110) (6–7,60/120) (6–7,75/150) | (5–6,45/90) (6–7,85/170) (6–7,100/200) (6–7,110/220) | (9,90/360) (11–12,165/600) | (6–7,45/90) |
| 006 レジェンド | (8, 60/120 → 90/160 → 155/240 → 245/380 → 395/630) | (8, 85/160 → 120/210 → 190/310 → 280/460 → 455/710) | — | — |

通常/SP 的 PERFECT = 2×CLEAR；追い込み PERFECT = CLEAR + 3×副属性值（165+3×145=600, 100+3×100=400, 75+3×75=300, 90+3×90=360）`[確認:master]`。

---

## 3. 各行动的数值效果

### 3.1 レッスン（通常 / SP）
- 对局：回合数 `limitTurn`，全部回合同属性（engine 文档 §3.1）。
- 属性上升（PERFECT 之内的得分即为基础上升量）`[転記:seesaawiki]` `[検索要約:https://note.com/suzu_hmjn/n/n87d2972f528d]`：
```
base   = min(score, PERFECT)                      # 通常/SP: PERFECT = 2×CLEAR
gain   = base + floor(base × レッスンボーナス% / 100)     # = floor(base × (1 + bonus/100))
```
  レッスンボーナス = 该属性的 サポカ「レッスンボーナス」合计（`ProduceEffectType_{Vocal,Dance,Visual}GrowthRateAddition`）+ Pアイテム/メモリー 的同类效果 `[確認:master ProduceEffect]`。取整：gakumasu-calc 与 涼鈴 转记均为 floor `[確認:code gakumasu-calc statusCalculation.applyParaBonus]`；gakumas-hajime-simulator 用 ceil（`calcLessonIncrease`）`[確認:code]` → 冲突，采用 floor 并列入 §10。
- 上升量封顶于参数上限（超出部分浪费）`[確認:code gakumas-hajime-simulator calcArrayMax(1800)]`。
- SPレッスン：数值更高（表 2.3），且附带 Pポイント増加・体力回復・レッスン開始時効果・Pドリンク獲得 `[検索要約:https://note.com/kagi296/…]`。出现概率：基础概率 + サポカ `LessonSpChangeRatePermilAddition`/`Lesson{Vocal,Dance,Visual}SpChangeRatePermilAddition` `[確認:master ProduceEffect]`；基础概率数值 `[推定]`（game8 提到出现在特定周 `[検索要約:https://game8.jp/gakuen-idolmaster/609972]`）。
- 体力：初 的课程无前置体力消耗，体力在对局内由出牌支付 `[推定]`；课程结束回复由 メモリー/サポカ「レッスン終了時体力回復」提供（`MemoryAbility` 例 `end_lesson-lesson_dance-stamina_recover_fix`）`[確認:master MemoryAbility]`。
- 课程结束附带获得 1 张技能卡（3 选 1）与 Pポイント `[推定]`（`ProduceEffectType_LessonPresentProducePointUp`/`LessonPresentProduceCardRewardCountUp` 存在 `[確認:master]`）。

### 3.2 追い込みレッスン（試験前）
```
excess = clamp(score − CLEAR, 0, PERFECT − CLEAR)
主属性  = CLEAR + floor(excess / 3)           # 最終前: 165 + floor(435/3) = 310
副属性  = floor(excess / 3)   (各)             # 145
除不尽时余数优先加给主属性（+1）
再各自套用 レッスンボーナス（同 3.1）
```
`[転記:seesaawiki/涼鈴]` `[確認:master successThreshold=165, resultTargetValueLimit=600]` `[確認:code lessons.js oikomi main 310 / sub 145]`。CLEAR 之后【〇〇ターンのみ】条件恒真（engine 文档 §5.3）。追い込み 不吃「上限+」类加成（hajime-simulator 中 `limitIncrease` 仅对通常课程）`[推定]`。

### 3.3 休む（Refresh）
体力回复 `floor(最大体力 × refreshStaminaRecoveryPermil/1000)` = 70% `[確認:master ProduceSetting]`（取整方向 `[推定]`）；社区表述“约 2/3” `[検索要約]`。触发 サポカ「休む選択時」事件（`SupportCardEvent*`）`[確認:code gakumasu-calc calculateWeekGain rest]`。

### 3.4 おでかけ（Outing）
按消耗的 Pポイント 档位回复体力，档位越高回复越多并附带 Pドリンク/技能卡 `[検索要約:https://game8.jp/gakuen-idolmaster/609743]`；master 效果类型：`StaminaRecoverMultiple`、`ProduceReward`、`ProduceCardUpgrade` `[確認:code gakumas-rl ACTION_EFFECT_TYPES(outing)]` `[確認:master ProduceEffect]`。具体档位/概率 `[推定]`（需实测）。サポカ「おでかけ選択時」事件加成 `[確認:code gakumasu-calc]`。

### 3.5 相談（Consultation / ショップ）
- 商品槽：技能卡 ×4、Pドリンク ×4、強化 ×4、削除 ×4（gakumas-rl 的动作空间）`[確認:code gakumas-rl runtime SHOP_*_ACTION_TYPES]` 槽数 `[推定]`。
- 价格折扣效果：`ShopProduceCardPriceDiscountMultiple(Permanent)`、`ShopProduceDrinkPriceDiscountMultiple`、`ShopProduceCardUpgradePriceDiscountMultiple`、`ShopProduceCardDeletePriceDiscountMultiple`、`ShopPriceUpMultiple`、`ShopRerollCountUp` `[確認:master ProduceEffect]`。
- 削除回数 上限受 親愛度 影响 `[検索要約:https://game8.jp/gakuen-idolmaster/609573]`。基础价格表 `[推定]`（未取得）。
- サポカ「相談選択時」事件 `[確認:code gakumasu-calc]`。

### 3.6 授業（EventSchool）
マスター 周表中 +50/+50/+80/+110/+110（选定属性）`[確認:code gakumas-hajime-simulator Container.tsx cIncrease]`；授業有时以课程形式进行（master `school-event` 级别 6–7 回合 45/90）`[確認:master]` `[検索要約]`；`EventSchoolStaminaUp/Down` 影响其体力消耗 `[確認:master]`。

### 3.7 活動支給（EventActivity）
给予 Pドリンク（マスター 为 3 选 1）、技能卡（可能含 + 强化版）、Pポイント `[検索要約:https://www.4gamer.net/…20240924035/]`；效果类型 `ProduceReward`/`ProduceRewardSet`、`EventActivityProducePointUp/Down` `[確認:master]`。

### 3.8 試験（中間 / 最終）`[確認:master ProduceStepAuditionDifficulty]`
| produce | 中間: baseScore / forceEndScore / parameterBaseLine | 最終: baseScore / parameterBaseLine | 合格名次 `rankThreshold` |
|---|---|---|---|
| 001 レギュラー | 600 / 900 / 100 | 2500 / 200 | 3 |
| 002 プロ | 1150 / 1700 / 150 | 7150 / 450 | 3 |
| 003 マスター | 1380 / 0 / 150 | 8580 / 450 | 3 |

- 回合数：中間 9、最終 11–12（engine 文档 §3.1）`[確認:master ProduceExamBattleConfig]`。
- 対戦 NPC 分数由 `produceExamBattleNpcGroupId` 决定；`baseScore` 为 NPC 基准 `[推定]`。
- 试验前自动回复：`beforeAuditionRefreshStaminaRecoveryPermil`（初 70%）`[確認:master]`；可被 `BeforeAuditionRefreshStaminaUp/Down` 调整 `[確認:master]`。
- 最終試験名次 → 全参数加成：1 位 +30、2 位 +20、3 位 +10、4 位以下 0（レジェンド：+160/+80/+40）`[確認:code gakumas-tools utils/produceRank.js PARAM_BONUS_BY_PLACE(_LEGEND)]` `[転記:seesaawiki]`；加成后仍受上限封顶 `[確認:code produceRank.js Math.min(cur+bonus, maxParams)]`。中間試験 1 位 +20 `[推定]`（gakumas-hajime-simulator 的 `test increase 20/30` 合计 +50）。
- スコアボーナス%：由参数经 `ProduceExamBattleScoreConfig` 曲线得到（engine 文档 §5.3）。親愛度 提升试验スコアボーナス（`audition_parameter_bonus_multiple`）`[確認:master CharacterDearnessLevel.produceSkills]`。

---

## 4. 体力（Stamina）
- 最大体力 = キャラ基础 + True End 奖励 + サポカ `MaxStaminaAddition` − `MaxStaminaReduceFix` `[確認:master ProduceEffect]` `[確認:code gakumas-core types.ts CharacterData.maxLife 注释]`。
- 消耗：对局内出牌（engine 文档 §4）；NIA 自主練 前置 6/8 `[確認:master ProduceStepSelfLesson.stamina]`。
- 回复：休む 70%、试验前 70%/50%、おでかけ 档位、SP レッスン/授業/メモリー 的固定回复 `StaminaRecoverFix`、倍率 `StaminaRecoverMultiple` `[確認:master]`。
- 「最大体力上升会提高 休む/おでかけ/试验前 的回复量」`[検索要約]`（与百分比规则一致）。

---

## 5. 初始参数与サポートカード效果类别
- 初始参数 = Pアイドル 卡面初始值（`IdolCard*` 表，schema atlas）+ サポカ 初期パラメータ（`Vocal/Dance/VisualAddition`，produce_start 触发）+ 持ち込みメモリー 的固定加成 `[確認:code gakumasu-calc calculate: baseStatus + character bonus + memoryFlat + equipBonus]`。
- サポカ/Pアイドル 培育技能效果类别（`ProduceEffectType_*`，按 master 出现频次）`[確認:master ProduceEffect]`：
  - 参数：`Vocal/Dance/VisualAddition`（固定 +，用于初期/事件）、`…GrowthRateAddition`（レッスンボーナス %）、`ParameterLimitUp`。
  - 课程：`LessonSpChangeRatePermilAddition`、`Lesson{Vo,Da,Vi}SpChangeRatePermilAddition`（SP 出现率）、`LessonPresentProducePointUp`、`LessonPresentProduceCardRewardCountUp`。
  - 体力：`StaminaRecoverFix/Multiple`、`StaminaReduceFix`、`MaxStaminaAddition`、`MaxStaminaReduceFix`、`BeforeAuditionRefreshStaminaUp/Down`、`EventSchoolStaminaUp/Down`。
  - Pポイント/商店：`ProducePointAddition(DisableTrigger)`、`ProducePointReduceFix`、`Shop*Discount*`、`ShopRerollCountUp`、`CustomizeProduceCardProducePointDownMultiple`。
  - 卡牌：`SupportCardProduceCardUpgradeProbabilityUp`（レッスン後強化確率）、`ProduceCardChange/ChangeUpgrade/ChangeSelect`（チェンジ）、`ProduceCardUpgrade/Delete/Duplicate`、`ProduceCardSelectRerollCountUp`、`ProduceCardExcludeCountUp`、`IdolCardProduceCardCustomizeEnable`。
  - 对局内：`ExamStatusEnchant`（レッスン開始時 付与状态）、`ExamPermanentAuditionStatusEnchant` / `ExamPermanentLessonStatusEnchant`（试验/课程永続状态）、`ExamTurnDown`。
  - 试验/NIA：`AuditionParameterBonusMultiple`、`AuditionNpcEnhance/Weaken`、`VoteCountAddition`、`AuditionVoteCountUp`、`EventBusinessVoteCountUp`、`StarPermilUp`/`StarAddition`（HIF）。
  - 事件加成：`SupportCardEventParameterAdditionValueUp`、`SupportCardEventProducePointAdditionValueUp`、`SupportCardEventStaminaRecoverUp`。
  - 奖励：`ProduceReward/RewardSet`、`HighScoreGoldAddition`、`ProduceDrinkPossessLimitUp`。
- gakumas-hajime-simulator 对サポカ事件的分类（用于回归对拍）：`lesson / spLesson / mSkillUpgrade / skillUpgrade / selectSoudan / getDrink / selectRest / selectGoOut / getMSkill / getASkill / getSkill / lessonBonus / endTest / selectProvide / selectClass / limitIncrease / baseParams` `[確認:code supportSlice.js]`。

---

## 6. 親愛度（Dearness）
- 每级有解锁条件 `produceConditionDescription`（例：Lv2 「プロデュース中にレッスンを1回以上完了」、Lv3 「中間試験を合格後1週経過」、Lv4 「プロデュース2週目」、Lv5 「中間試験を1位通過」）与培育技能 `produceSkills`（例 `audition_parameter_bonus_multiple-03` level 1→3 递增）`[確認:master CharacterDearnessLevel]`。
- 汇总效果（社区）：试验スコアボーナス、相談 削除回数、Pドリンク 獲得上限、お仕事報酬、技能卡一次再抽选、コミュ `[検索要約:https://game8.jp/gakuen-idolmaster/609573]` `[転記:seesaawiki]`。
- NIA：投票数 ×(1 + 0.05×(親愛度−10)) `[確認:code gakumas-tools utils/nia.js calculateGainedVotes]`；`ProduceStepAuditionDifficulty.dearnessLevel`（14/17）标记高難度 FINALE 行所需亲密度 `[確認:master]` 语义 `[推定]`。
- True End：`CharacterTrueEndBonus`（最大体力等）`[確認:master 表名]`。

---

## 7. 思い出（メモリー）
- 生成：培育结束时生成 1 个メモリー，携带 アビリティ（最多 3 个？）与可继承技能卡；アビリティ 稀有度受最终评价与参数影响：评价 A 以上、各参数 ≥1000 时进入 SSR（虹）抽取表；“三项 1000 比单项 1500 更易出虹”`[検索要約:https://game8.jp/gakuen-idolmaster/613860, gutidere-niwaka.com]`；继承技能卡从本次培育中获得过的卡里抽 `[検索要約]`；虹技能卡独占且评价 ≤C+ 时被替换为「表現の基本」`[検索要約]`。精确概率 `[推定]`。
- `MemoryAbility`：每个 ability 有 `level`、`evaluation`（例 体力回復系 18/27/36）、`rarity`、`isUniqueActivation`（重複発動不可）`[確認:master]`；`MemoryTag`/`MemoryGift`/`ResearchMemoryRerollCost` 相关（schema atlas）。
- 对局内发动：每个 ability 按 `probability%` 在第 1 回合开始发动，后发动者受先发动者影响（やる気 → 元気）`[確認:code gakumas-core activateMemoryEffect, types.ts MemoryEffect]`。
- 参数贡献：持ち込みメモリー 的参数按 `floor(value × multiplier)` 计入（コンテスト/初期）`[確認:code gakumas-tools utils/stamina.js getMemoryParamContribution]`。

---

## 8. 最終プロデュース評価

### 8.1 初（レギュラー/プロ/マスター）`[転記:seesaawiki]` `[確認:code gakumas-tools produceRank.js]` `[確認:code gkmas-rank-calculator calculator.js]` `[確認:code gakumas-final-score utils.ts]`
```
P_i'  = min(P_i + 順位パラメータ加算, 上限)          # 加算: 1位30 / 2位20 / 3位10
評価  = 順位点 + floor(2.3 × ΣP_i') + floor(α(最終試験スコア))
順位点 = 1位 1700 / 2位 900 / 3位 500 / 4位以下 0
α(S) 分段（各段边际系数，按段累计后 floor）：
   0–5,000: 0.30 | 5,001–10,000: 0.15 | 10,001–20,000: 0.08 | 20,001–30,000: 0.04
   30,001–40,000: 0.02 | 40,001–200,000: 0.01 | 200,001+: 0   (2025/10/31 11:00 起封顶)
   ⇒ 段末累计值: 1500 / 2250 / 3050 / 3450 / 3650 / 5250(封顶)
```
`gkmas-rank-calculator` 用 Big.js 精确小数并 `roundDown`；`gakumas-final-score` 用整数百分比避免浮点误差 `[確認:code]`。**实现用整数运算**。经验校验：参数合计 3100、最終 1 位 15000 分 → 1700 + 7130 + 2650 = 11480（A+ 差 20）`[転記:seesaawiki 早見表]`。

### 8.2 初 レジェンド `[確認:code produceRank.js]`
```
評価 = 順位点 + floor(2.1 × Σ min(P_i + {160,80,40,0}[順位], 3000)) + floor(β(中間スコア)) + floor(γ(最終スコア))
β 边际: 0–10k 0.11 | –20k 0.08 | –30k 0.05 | –40k 0.008 | –50k 0.003 | –60k 0.002 | –200k 0.001 | 200k+ 0
γ 边际: 0–300k 0.015 | –500k 0.01 | –600k 0.008 | –2,000k 0.001 | 2,000k+ 0   (段末累计 4500/6500/7300/8700)
```
gakumas-rl 旧移植为 加算 120/60/30、上限 2800 `[確認:code gakumas-rl produce_score.py]` → 以 gakumas-tools 当前值为准 `[推定]`。gakumas-hajime-lesson 的另一简化版「(参数×2.1) + 中間 + 最終」`[確認:code gakumas-hajime-lesson exam.ts]` 不含分段，不采用。

### 8.3 评价等级阈值（`ResultGradePattern`, `type=ProduceScore`）`[確認:master]`
| 等级 | F | E | D | C | C+ | B | B+ | A | A+ | S | S+ | SS | SS+ | SSS | SSS+ | SSSS | SSSS+ | SSSSS | SSSSS+ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 阈值 | 0 | 1000 | 2000 | 3000 | 4500 | 6000 | 8000 | 10000 | 11500 | 13000 | 14500 | 16000 | 18000 | 20000 | 23000 | 26000 | 30000 | 35000 | 40000 |

`ProduceGrade` 按 produceGroup 复刻同一表并以 `limitGrade` 封顶（初 SSSS、NIA SSS+、HIF SSSSS）`[確認:master ProduceGrade, ProduceGroup]`。`ResultGradeType_ProduceIdolCardParameter`（单项参数评级）阈值 0/100/200/300/450/600/800/1000/… `[確認:master]`。

### 8.4 N.I.A. `[確認:code gakumas-tools utils/nia.js]` `[検索要約:https://note.com/d_a_don/n/n6b94cf317fc9]`
```
評価 = floor(2.3 × ΣP_i) + ファン評価点
ファン評価点 = base[rank] + floor(votes × mult[rank])
  votes ≥ 20,001 A: 300+0.085v | ≥40,001 A+: 900+0.07v | ≥60,001 S: 1200+0.065v | ≥80,001 S+: 1600+0.06v
  ≥100,000 SS: 2600+0.05v | ≥120,000 SS+: 3800+0.04v | ≥140,000 SSS: 5200+0.03v
```
（社区表述的分段 ×0.1/0.085/0.07/0.065/0.06/0.055 `[検索要約]` 与上表结构一致，以代码为准。）

---

## 9. N.I.A. 基线细则
- 周程：27 步（プロ）/26 步（マスター）；オーディション 在第 9 / 18 / 27 周（プロ）`[検索要約:https://game8.jp/gakuen-idolmaster/661665]`；每场必须第 1 名（`rankThreshold=1`），否则培育结束 `[確認:master ProduceStepAuditionDifficulty]`。
- 三场：一次（メロBang!，`AuditionMid1`）、二次（GALAXY，`AuditionMid2`）、最終（QUARTET / FINALE，`AuditionFinal`）；FINALE 需累计票数 ≥57,000 才开放 `[確認:code nia.js MIN_VOTES_BY_STAGE {melobang 9000, galaxy 25000, quartet 40000, finale 57000}]`。
- master 行示例（按角色/档位）：Mid1 `baseScore 1050/1700/2250, voteCountBaseLine 4968/5700/10134`；Mid2 `6750/10850/20600, vote 12233/20514/28544`；Final `13550/21650/34600/61900, vote 21300/36194/53210/67037`，最高两档要求 `dearnessLevel 14/17` `[確認:master]`。回合数：一次 9、二次/最終 12 `[確認:master ProduceExamBattleConfig produce_004-1/2/3: 9/12/12]`。
- 自主練（SelfLesson）：通常 体力 6 / パラメータ +80→100→120（按阶段），SP 体力 8 / +100→120→150 `[確認:master ProduceStepSelfLesson produce_004]`；体力不足时不可选 `[検索要約]`。
- 営業（Business）：获得票数（`EventBusinessVoteCountUp`），场地类型 商業施設/企業イベント会場/自治体イベント会場/リゾート施設 `[確認:master Label_Business*]`。
- オーディション 得分 → 参数上升：按角色的属性优先序（`PARAM_ORDER_BY_IDOL`）与平衡型（flat/skew），每项分数经分段函数 `gain = floor(score × mult + const)`（减衰起点：一次 1300/1060/870，二次 12400/10200/8400，最終 38400/31800/26000；上限点 2550/2050/1600 …）`[確認:code nia.js PARAM_REGIMES_BY_DIFF_STAGE_BALANCE_ORDER]` `[検索要約]`；再套 パラメータボーナス `floor(gain × bonus%)` 与 チャレンジ加成，封顶于上限 `[確認:code nia.js calculateBonusParams/calculatePostAuditionParams]`。
- 票数：`votes = floor(ceil(total × mult + const) × (1 + 0.05×(親愛度−10)))`，分段（プロ 最終：0–200k 0.1067045+2165 → 200k–798k 0.0032025+22783 → 798k+ 封顶 25334）`[確認:code nia.js VOTE_REGIMES_BY_DIFF_STAGE]`；seesaawiki 转记的 `ROUND(素点×2.20005/2.26673/2.23333)` 与 親密度20→`ROUNDUP(×1.5)` 为同一关系的另一种拟合 `[転記:seesaawiki]`。

---

## 10. 周循环状态机（实现草案）
```
init: params = idol_base + support_initial + memory_flat; stamina = max_stamina; deck = ProduceInitialDeck; drinks=[]; p_points = ProduceSetting.initialProducePoint(0)
for week in 1..steps:
    options = ScenarioConfig.week[week].actions   # 由 ProduceStepTransition 派生
    if option is Lesson/SP/Hard: run engine (turns=limitTurn, clear/perfect) → gain by §3.1/3.2 → card reward → support "lesson" triggers
    elif Refresh: stamina += floor(max × 0.7); support "rest" triggers
    elif Outing/Activity/School/Consult: apply ProduceEffect list; support triggers
    elif AuditionMid/Final: stamina = min(max, stamina + max × beforeAuditionRefresh‰); run engine with scoreBonus from ProduceExamBattleScoreConfig; rank vs NPC; fail → continue(≤3) or end; Final → place bonus
    after each step: cap params at limit; ProduceCardUpgrade interval; drinks cap 3/4
end: evaluation §8 → grade §8.3 → memory §7
```
サポカ 事件触发点（gakumasu-calc 的 trigger 名）：`lesson, sp_lesson, rest, outing, consultation, class, exam_end`（含次数上限 `triggerCounters`）`[確認:code gakumasu-calc calculateWeekGain/fireTrigger]`。

---

## 11. 未决 / 待实测
1. レッスンボーナス 取整（floor 多数 vs hajime-simulator ceil）。
2. 中間試験 名次参数加成（+20?）与レジェンド 加成（160/80/40 vs 120/60/30）。
3. レギュラー/プロ 自由周的可选行动集合（应从 `ProduceStepTransition` 解析）。
4. おでかけ 各档 Pポイント 消耗与回复量；相談 价格表；活動支給 掉落表；SP レッスン 基础概率；课程结束卡牌奖励规则。
5. 休む/试验前回复的取整方向。
6. `stepSkipStaminaRecoveryPermil`、`stepIntervalUpgrade/CustomizeProduceCardCount` 的确切语义。
7. メモリー アビリティ 稀有度抽取表与概率。
8. NIA 自主練 之外的步骤（営業 票数、ファンプレゼント）数值。
