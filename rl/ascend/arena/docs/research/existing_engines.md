# 现有开源学マス引擎 / 模拟器 / RL 仓库调研

> 调研日期：2026-09-07。所有仓库均已 clone 到 `scratchpad/ext/`，本文的结论来自直接读源码、跑测试与冒烟脚本，而不是 README 转述。
> 我们的目标：Python 模拟器，数据源为 datamined master DB（`vertesan/gakumasu-diff` YAML；`ProduceCard` 行引用 `ProduceExamEffect` 行，效果由 `ProduceExamEffectType` 枚举分派）。最想知道的是：**有没有项目已经直接解释 master data 的效果枚举**，而不是手写卡牌定义。

## 0. 一句话结论

- **有，且只有一个**：`skyfsj/gakumas-rl`（Python，GPL-3.0，2026-04/05）直接读 `gakumasu-diff` 的 YAML，用 `effectType` 字符串分派 `ProduceExamEffectType_*`，同时解释 `ProduceExamTrigger` / `ProduceExamPhaseType` / `ProduceCardGrowEffect` / `ProduceExamStatusEnchant` / `ProduceEffect`（培育外循环）/ `ExamSetting`（各种 permil 常数）。它还自带 Gymnasium 环境、MaskablePPO + BC 自举训练流程和 242 个规则测试。**在今天（2026-09-04 版）的 master data 上跑：240 passed / 1 failed / 1 skipped**，NIA/初 Legend 的 exam 能完整跑通。
- 它覆盖了 master data 中实际出现的 108 个 `ProduceExamEffectType` 值里的 **99 个**；缺的 9 个全部是 2026-05 H.I.F 上线后新增的（`ExamStatusEnchantEncore`、`ExamGimmickEnthusiastic`、`ExamLessonDependStamina`、`ExamMultipleEnthusiasticLesson`、`ExamFullPowerLessonMultipleAdditive`、`ExamConcentrationLessonMultipleAdditive`、`ExamLessonBuffAdditiveFix`、`ExamAggressiveAdditiveFix`、`ExamForcePlayCardSearchWithCost`）。培育外循环的 `ProduceEffectType` 覆盖 57/66，缺的 9 个里 `StarAddition` / `StarPermilUp` / `ParameterLimitUp` 也是 H.I.F 专属。
- 其余所有引擎（`gakumas-core`、`gakumas-tools/gakumas-engine`、两个 contest simulator、`gakumastrain`、`lts129/Gakumas-RL`、`mihalinn/gakumasu`、`gakumasu-anomaly-sim` 等）都是**手写卡牌定义**（TS 对象 / CSV DSL / JS 数组 / YAML / xlsx），只有 `new_gakumas_contest_simulator` 借用了 master 表 `ProduceExamAutoEvaluation` 作为 AI 权重。
- 主要的负面因素：`gakumas-rl` 是 **GPL-3.0**，且 exam 的取整/相位实现是作者按「ヘルプ手册」自行推导的，没有任何实机录像对照测试；它只知道 `ProduceType_FirstStar` 和 `ProduceType_NextIdolAudition` 两种剧本，H.I.F 会被当成初来跑。

## 1. 仓库总表

星数来自 GitHub search API（2026-09-07）；"大小" 为不含 `.git` 的工作树。

| 仓库 | 语言 | 许可 | 最后提交 | ★ | 大小 | 类别 |
|---|---|---|---|---|---|---|
| [skyfsj/gakumas-rl](https://github.com/skyfsj/gakumas-rl) | Python | GPL-3.0 | 2026-05-17 | 0 | 3.8M | **master-data 驱动**的 exam+produce 引擎 + Gym env + RL |
| [lts129/Gakumas-RL](https://github.com/lts129/Gakumas-RL) | Python | 无 | 2026-04-26 | 6 | 23M | 手写(xlsx)センス打牌引擎 + PPO/BC + OCR 实机部署 |
| [lts129/Gakumas-CalCardDeck](https://github.com/lts129/Gakumas-CalCardDeck) | Python | 无 | 2026-05-04 | 0 | 36M | 支援卡编成优化（xlsx），非模拟器 |
| [lirichar/gakumastrain](https://github.com/lirichar/gakumastrain) | Python | 无 | 2026-06-29 | 1 | 472K | clean-room 粗粒度全流程模拟 + 表格 Q-learning |
| [kjirou/gakumas-core](https://github.com/kjirou/gakumas-core) | TypeScript | MIT | 2024-09-22 | 14 | 1.3M | 手写 lesson/exam 引擎（センス/ロジック，2024-09 停更） |
| [kjirou/gakumas-lesson-simulator](https://github.com/kjirou/gakumas-lesson-simulator) | TypeScript | — | 2024-09-22 | 2 | 1.8M | gakumas-core 的 Gatsby UI |
| [surisuririsu/gakumas-tools](https://github.com/surisuririsu/gakumas-tools) | JavaScript | BSD-3 | 2026-09-05 | 79 | 201M | contest 引擎（CSV DSL）+ 数据包 + 网站 |
| [katabami83/gakumas_contest_simulator](https://github.com/katabami83/gakumas_contest_simulator) | JavaScript | 无 | 2025-01-01 | 9 | 1.5M | contest 引擎（手写 JS），seeded LCG，深度搜索 AI |
| [kanon511/new_gakumas_contest_simulator](https://github.com/kanon511/new_gakumas_contest_simulator) | JavaScript | 无 | 2024-12-14 | 15 | 1.1M | contest 引擎（手写 JS）+ 官方 AutoEvaluation 权重 |
| [mihalinn/gakumasu](https://github.com/mihalinn/gakumasu) | TypeScript | 无 | 2026-01-24 | 0 | 49M | 最终试验 UI 模拟器（ロジック，CSV→JSON 卡牌） |
| [happyMilleFeuille/gakumas](https://github.com/happyMilleFeuille/gakumas) | JavaScript | 无 | 2026-09-05 | 1 | 1.2G | 韩文站：ガシャ模拟 + 支援卡属性期望计算 + 评价值计算（含 HIF） |
| [tyuukiti/gakumasu-calc](https://github.com/tyuukiti/gakumasu-calc) | TS + C# | 无 | 2026-08-31 | 3 | 5.1M | 支援卡编成→属性理论值（初Legend/NIA/HIF），TS/C# 双实现 |
| [tyuukiti/gakumasu-anomaly-sim](https://github.com/tyuukiti/gakumasu-anomaly-sim) | TS + Python | MIT | 2026-05-15 | 0 | 1.5M | アノマリー最终回合全探索（wiki 爬取 YAML 卡牌） |
| [huraru7/gakumas_HIF_Rating_Calculation](https://github.com/huraru7/gakumas_HIF_Rating_Calculation) | JS | 无 | 2026-06-14 | ? | 32K | HIF 评价值计算器（公式见 §6） |
| [kjirou/gakumas-final-score](https://github.com/kjirou/gakumas-final-score) | TypeScript | — | 2024-10-16 | 2 | 1.6M | 初 评价值计算 |
| [Kantouzin/gkmas-rank-calculator](https://github.com/Kantouzin/gkmas-rank-calculator) | Svelte | — | 2025-01-04 | 8 | 1008K | 初 评价值计算 |
| [KagamiChan/gakumas.moe](https://github.com/KagamiChan/gakumas.moe) | TypeScript | MIT | 2026-01-05 | 2 | 392K | 初/NIA 评价值计算 |
| [Anthoooooooony/gakumas-calculator](https://github.com/Anthoooooooony/gakumas-calculator) | TypeScript | — | 2026-06-11 | 7 (archived) | 924K | 评价值计算 |
| [shunya200426/gakumasu-discord-bot](https://github.com/shunya200426/gakumasu-discord-bot) | Python | — | 2026-08-20 | 0 | 16M | 初/NIA 评价值 + OCR Discord bot（NIA fan/きらめき 换算） |
| [yuuhi1315/Gakumas-Simulator](https://github.com/yuuhi1315/Gakumas-Simulator) | JS | — | 2026-03-09 | 0 | 72K | ガシャ天井概率模拟，与打牌无关 |
| [sameta-gakmas/gakumas-exam-simulator](https://github.com/sameta-gakmas/gakumas-exam-simulator) | — | — | 2026-08-18 | 0 | 8K | 只有 README，无代码 |
| [gyeolls/gakumas-contest](https://github.com/gyeolls/gakumas-contest) | HTML | — | 2026-08-21 | 0 | 5.0M | 单文件 contest checker 页面 |
| [mafu176/gakumas-contest-tracker](https://github.com/mafu176/gakumas-contest-tracker) | JS (Next) | — | 2026-09-04 | 0 | 250M | contest 战绩记录/OCR，无引擎 |
| [Taka499/gakumas-hajime-lesson](https://github.com/Taka499/gakumas-hajime-lesson) | TypeScript | — | 2026-02-14 | 0 | 420K | 初Legend 周程参数计算器（含 2.1 系数评价公式） |
| [kakris704/gakumas-hajime-simulator](https://github.com/kakris704/gakumas-hajime-simulator) | TS/JS | — | 2026-06-12 | 0 | 828K | 初 周程参数计算器（CRA） |
| [ummmm300/gakumas-solo-simulator](https://github.com/ummmm300/gakumas-solo-simulator) | JS | — | 2026-07-20 | 0 | 480K | 单卡打分公式小工具 |
| [tp6m4t/gakumas_go](https://github.com/tp6m4t/gakumas_go) | Go | — | 2025-05-26 | 0 | 248K | 半成品 TUI 打牌，4 张卡 |
| [vertesan/gakumasu-diff](https://github.com/vertesan/gakumasu-diff) | YAML | — | 2026-09-04 | 65 | 198M | master DB dump（我们的数据源） |
| [vertesan/hatsuboshi-library](https://github.com/vertesan/hatsuboshi-library) | TypeScript | AGPL-3.0 | 2026-08-02 | 31 | 2.0M | 图鉴站；`app/types/proto/penum.ts` 含**完整枚举**（`ProduceExamEffectType` 169 项） |
| [imas-tools/gakumas-master-translation](https://github.com/imas-tools/gakumas-master-translation) | Python/JSON | — | 2026-09-04 | 7 | 153M | gakumasu-diff→JSON→汉化；含 `ProduceDescriptionProduceExamEffectType.json` |
| [kotonebot/kaa-game-data](https://github.com/kotonebot/kaa-game-data) | Python | GPL-3.0 | 2026-08-11 | 0 | 716K | gakumasu-diff→SQLite `game.db` 构建管线 |
| [AllenHeartcore/GkmasObjectManager](https://github.com/AllenHeartcore/GkmasObjectManager) | Python | GPL-3.0 | 2026-08-18 | 40 | 22M | 资源 manifest/解密/下载，非规则 |
| [DreamGallery/HatsuboshiToolkit](https://github.com/DreamGallery/HatsuboshiToolkit) | Python | — | 2025-06-24 | 16 | 76K | octocache 解密/更新，非规则 |
| [hatsuboshi-app/backend](https://github.com/hatsuboshi-app/backend) | TypeScript | GPL-3.0 | 2026-08-25 | 1 | 2.0M | REST API，静态数据 |
| [hatsuboshi-app/types](https://github.com/hatsuboshi-app/types) | TypeScript | MIT | 2026-08-25 | 1 | 744K | 手写枚举/类型（14 个 enum，无 `ProduceExamEffectType`） |
| [Xilorole/gakumas-data](https://github.com/Xilorole/gakumas-data) | JSON/TS | — | 2026-08-19 | 0 | 1.4M | コミュ台词转写，与规则无关 |

## 2. 核心仓库详解

### 2.1 skyfsj/gakumas-rl —— 唯一直接解释 master data 枚举的引擎

- **origin**：`https://github.com/skyfsj/gakumas-rl`；6 个 commit，作者 `fsj`（同一作者维护 `skyfsj/gakumas-assistant` OCR 自动化）；99 个 `.py`、37k 行；`AGENTS.md` 是给 Codex/LLM 的协作规范（简中注释、`dataclass`、禁止 LLM 参与训练等）。
- **建模范围**：lesson（通常/SP/追い込み）、中間/最終試験（含 rival NPC 计分与排名、回合颜色、NIA fan vote）、以及**完整培育外循环**：授業/おでかけ/活動支給/相談(shop 买卡/买饮料/强化/删卡)/営業/自主レッスン/customize/audition 选择/试验前 continue 等。剧本：`build_scenario()` 只区分 `ProduceType_NextIdolAudition` → `nia` 与其它 → `first_star`（`src/repository/master_data.py:1060-1135`）；produce-001~006（初 Regular/Pro/Master、NIA Pro/Master、初 Legend）按主数据 `Produce.steps` 装配。**H.I.F（produce-007 選抜試験、produce-008 本戦）会被当作 first_star 跑**：exam 能跑通（冒烟脚本验证），但没有 star quality、两轮制、本戦上限增加面板等机制。三种 plan（センス/ロジック/アノマリー）都由数据驱动：stance（`concentration` / `preservation` / `full_power`）、全力值、熱意、温存解除等都实现了（`ExamSetting` 的 `examPreservationReleaseBlockAdd1/2`、`fullPowerPlayableValueAdd` 等常数直接读表）。
- **数据源**：submodule `assets/gakumasu-diff`（我把它软链到我们 clone 的最新版做验证）+ `assets/GakumasTranslationData`（仅用于名字）。`MasterDataRepository.load_table()` 读 YAML 并做 pickle 磁盘缓存（首次 ~50 s，之后毫秒级）。用到的表（`src/repository/master_data.py:394-535` 与 `ExamRuntime.__init__`）：
  `ProduceCard, ProduceDrink, ProduceItem, ProduceDrinkEffect, ProduceExamEffect, ProduceExamStatusEnchant, ProduceExamTrigger, EffectGroup, ProduceEffect, Setting, ExamSetting, Produce, ProduceGroup, ProduceSetting, SupportCard, SupportCardLevel, SupportCardLevelLimit, SupportCardProduceSkillLevel{Vocal,Dance,Visual,Assist}, SupportCardProduceSkillFilter, ProduceEventSupportCard, ProduceStepEventDetail, ProduceStepEventSuggestion, ProduceInitialDeck, ExamInitialDeck, ProduceStepAuditionDifficulty, ProduceExamBattleConfig, ProduceExamBattleScoreConfig, ProduceExamBattleNpcGroup, ProduceExamAutoEvaluation, ProduceExamAutoTriggerEvaluation, ProduceExamAutoPlayCardEvaluation, ProduceStepLessonLevel, ProduceStepLesson, ProduceCardSearch, ProduceCardGrowEffect, ProduceCardStatusEnchant, ProduceExamGimmickEffectGroup, ProduceCardRandomPool, ProduceCardPool`。
- **效果分派**（关键）：
  - 入口 `ExamRuntime._apply_exam_effect()` → `src/simulation/exam/effects/registry.py:apply_exam_effect()`：`EffectHandlerRegistry.dispatch()` 按 `effect['effectType']` 字符串**精确匹配 → 前缀匹配（`ProduceExamEffectType_ExamLesson*` 统一走打分）→ fallback（当作计时效果挂起）**。
  - 枚举常量集中在 `src/simulation/exam/ids.py`（`ExamEffect`、`GrowEffect`、`ExamPhase`、`FieldStatus`、`TriggerCheck`）。
  - handler 分组（`src/simulation/exam/effects/*.py`）：
    - `timed.py`（挂成 `TimedExamEffect`，按 `effectTurn`/`effectCount` 衰减）：`ExamAggressiveAdditive, ExamAggressiveValueMultiple, ExamBlockAddDown, ExamBlockRestriction, ExamBlockValueMultiple, ExamCardSearchEffectPlayCountBuff, ExamEnthusiasticAdditive, ExamEnthusiasticMultiple, ExamFullPowerPointAdditive, ExamLessonBuffAdditive, ExamLessonBuffMultiple, ExamLessonValueMultiple, ExamLessonValueMultipleDependReviewOrAggressive, ExamLessonValueMultipleDown, ExamParameterBuffAdditive, ExamParameterBuffMultiplePerTurn, ExamPlayableValueAdd, ExamReviewCountAdd, ExamReviewMultiple, ExamSearchPlayCardStaminaConsumptionChange, StanceLock, ExamStaminaConsumptionAdd/AddFix/Down/DownFix, ExamStaminaRecoverRestriction`
    - `lesson_value.py` + `lesson_score.py`（前缀 `ExamLesson*` 与 `ExamMultipleLessonBuffLesson`）：`ExamLesson, ExamLessonFix, ExamLessonDependExamReview, ExamLessonDependExamCardPlayAggressive, ExamLessonDependBlock, ExamLessonDependParameterBuff, ExamLessonDependPlayCardCountSum, ExamLessonDependStaminaConsumptionSum, ExamLessonDependBlockConsumptionSum, ExamLessonDependBlockAndSearchCount, ExamLessonPerSearchCount, ExamLessonFullPowerPoint, ExamLessonAddMultipleLessonBuff, ExamLessonAddMultipleParameterBuff, ExamMultipleLessonBuffLesson`
    - `simple.py`：`ExamConcentration, ExamPreservation, ExamOverPreservation, ExamCardDraw, ExamFullPower, ExamStanceReset, ExamExtraTurn, ExamAntiDebuff, ExamDebuffRecover, ExamFullPowerPointReduce, ExamHandGraveCountCardDraw`
    - `stamina.py`：`ExamStaminaDamage, ExamStaminaReduce, ExamStaminaReduceFix, ExamStaminaRecover, ExamStaminaRecoverFix, ExamStaminaRecoverMultiple`
    - `block.py`：`ExamBlock, ExamBlockFix, ExamBlockDependBlockConsumptionSum, ExamBlockAddMultipleAggressive, ExamBlockDown, ExamBlockPerUseCardCount, ExamBlockDependExamReview`
    - `review.py`：`ExamReviewAdditive, ExamReviewDependExamCardPlayAggressive, ExamReviewDependExamBlock, ExamReviewPerSearchCount, ExamReviewReduce, ExamReviewValueMultiple`
    - `parameter_buff.py` / `lesson_buff.py` / `aggressive.py`：`ExamParameterBuffReduce, ExamParameterBuffMultiplePerTurnReduce, ExamParameterBuffDependLessonBuff, ExamLessonBuffReduce, ExamLessonBuffDependParameterBuff, ExamLessonBuffPerSearchCount, ExamAggressiveReduce`
    - `scalar_resource.py` / `duration_resource.py`（`ExamReview, ExamCardPlayAggressive, ExamParameterBuff, ExamLessonBuff, ExamFullPowerPoint` 这类"基础资源"型，集合定义在 `runtime.py` 顶部常量里）
    - `card_operation.py` → `ExamRuntime._apply_card_operation()`：`ExamCardCreateId, ExamCardCreateSearch, ExamCardDuplicate, ExamCardMove, ExamCardUpgrade, ExamForcePlayCardSearch`（`pickRangeType`/`pickCountType`/`movePositionType` 字段驱动；作者自评为"部分实现"）
    - `gimmick.py`：`ExamGimmickPlayCardLimit, ExamGimmickStartTurnCardDrawDown, ExamGimmickSleepy, ExamGimmickSlump, ExamGimmickParameterDebuff, ExamGimmickLessonDebuff, ExamPanic`（先消费 `anti_debuff` 层数）
    - `status_enchant.py` → `_apply_status_enchant()`（`ProduceExamStatusEnchant` 行 = trigger + effect ids 挂成 `TriggeredEnchant`）、`delayed_effect.py` → `_schedule_effect()`（`ExamEffectTimer`，"次のターン…"）、`grow_effect.py` → `_add_grow_effect()`（`ExamAddGrowEffect` → `ProduceCardGrowEffect` 行附着到卡上，`GrowEffect.*` 40 种在 `ids.py`）、`item_fire_limit.py`（`ExamItemFireLimitAdd`）。
  - 触发器：`src/simulation/exam/triggers/evaluator.py:trigger_matches()` 按 `ProduceExamTrigger` 的 `phaseTypes/phaseValues/fieldStatus*/produceCardSearchId/effectTypes/lessonType` 逐字段判定；`ExamRuntime._dispatch_phase()`（`runtime.py:2947`）在每个 `ProduceExamPhaseType_*` 下遍历 `active_enchants`（P アイテム / status enchant）和所有区域卡的 `produceCardStatusEnchantId`。间隔型 phase（`ExamTurnInterval`、`ExamPlayCountInterval`…）由 `_dispatch_interval_phase()` 用主数据里出现过的 `phaseValues` 取模。
  - 值语义：`effectValue1` 直接值，`_ratio_value()` 把 permil 转比例（`runtime.py:4221`），`_count_value()` 取 `effectCount`（`:4227`）。
- **回合相位与顺序**（`runtime.py`）：
  - `_start_turn()`（:2390）：turn++ → 重置 play_limit（`ExamSetting.turnStartDistribute`、`handLimit`）→ 回合颜色抽样（`_roll_turn_color` 按三维比例）→ rival 计分/排名 → **好印象、パラメータ強化各 -1** → `_decay_turn_effects()`（本回合新挂的效果不减，"ターン経過減免"）→ 全力解除 / 全力值≥阈值进入全力 → gimmick（按 `priority` 升序）→ phase `ExamStartTurn` → `ExamTurnTimer` → `ExamTurnInterval` → 抽牌 → `_fire_scheduled_effects()` → 支援卡"サポート"升级。
  - `_play_card()`（:2673）：算体力（`_card_stamina_components` :2806，含 grow cost、`ExamStaminaConsumption*` 倍率/固定值、Panic、stance 倍率 `examConcentrationStaminaMultiplePermil1/2`、`examPreservationStaminaMultiplePermil1/2`、`examOverPreservationStaminaMultiplePermil`、貫通 `examConcentrationStaminaPenetrateReduce`）→ `_spend_stamina()`（元気先吸收）→ phase `ExamStaminaReduceCard` → `ExamBuffConsume` → 扣资源型 cost → `StartExamPlay` → `StartPlay` → `ExamCardPlay` → 逐条 `playEffects`（带 `trigger_id` 的先判 trigger）× 重复次数（`LessonCountAdd/Reduce` grow）→ `ExamPlayTurnCountInterval` → `ExamPlayCountInterval` → `ExamSearchCardPlay` → `ExamCardPlayAfter` → `ExamPlayCountIntervalAfter` → 移到 `playMovePositionType` 指定区域。
  - `_end_turn()`（:2778）：`ExamTurnSkip`（若 skip）→ 好印象结算 `score += modifiers(review) × (1 + ExamReviewCountAdd)` → `ExamEndTurn` → `ExamEndTurnInterval` → 弃手牌 → 熱意清零 → `examTurnEndRecoveryStamina`（exam 或 skip 时）。
  - **打分公式** `_apply_score_value_modifiers()`（:3940）：`v = max(base,0) + lesson_buff(好調?) + enthusiastic` → 依次乘 `ExamLessonValueMultiple`(1+r) / `Down`(1−r) / `DependReviewOrAggressive`（`min(review,aggressive)×examLessonValueMultipleDependReviewOrAggressiveMultiplePermil`，上限 `MaxPermil`）→ 减 `GimmickLessonDebuff` → 乘 `GimmickParameterDebuff`（`examGimmickParameterDebuffPermil`）→ Slump 归零 → 乘 `examParameterBuffPermil`(1500=1.5) 与 `MultiplePerTurn` → 乘 stance 倍率（`examConcentrationLessonValueMultiplePermil{1,2}`、`examPreservation…{1,2}`、`examOverPreservation…`、`examFullPowerLessonValueMultiplePermil`）→ `_score_gain()` 再乘 `score_bonus_multiplier`（审査基准 / 回合颜色）。
  - **取整**：`_ceil_positive()`（:2241，`ceil(x − 1e-9)`）用于所有"参照值"型收益（好印象分/やる気分/元気分/検索数分…）；计数型用 `int(round())`；**分数本身保持 float 累加，没有 ceil**——这与 seesaawiki/gakumas-core 的 "スコアは切り上げ" 不一致，是移植时必须改的点。集中的加法（`+ concentration × 倍率`）也没在这个函数里，需核对 `_direct_value()` 路径。
- **RNG**：`ExamRuntime(seed=…)` → `np.random.default_rng(seed)`；洗牌、回合颜色、随机 card variant、drink 库存都走 `self.np_random`；`GakumasExamEnv.reset(seed=)` 用 gym 的 `np_random` 派生 `runtime_seed`。`ProduceRuntime(seed=…)` 同理。**完全可复现**。
- **测试**：`tests/test_rules.py` 242 个（6.8k 行），全部是"按手册规则构造小场景断言"，**没有实机录像对照**；`tests/test_manual_exam_setups.py` + `src/manual_exam_setups.py` 支持从 jsonl 载入"真实局面的 deck/drink/item"，但仓库里没有带样本。`scripts/fetch_help_content_pages.py` 拉官方 help 页面作为规则依据。在 2026-09-04 数据上：`240 passed, 1 failed (test_exam_runtime_weak_slump_and_panic_follow_game_labels: 手牌里找不到 0 费卡，数据漂移), 1 skipped`。
- **RL 部分**（`src/simulation/envs.py`, `src/training/*`）：
  - `GakumasExamEnv(gym.Env)`：`action_space = Discrete(max_actions)`（手牌槽 + 饮料槽 + end_turn），`observation_space = Dict{global: Box(-20,20,(global_dim,)), action_features: Box(...,(max_actions, feat_dim)), action_mask: Box(0,1,(max_actions,))}`。global 向量（`_global_observation` :1483）≈ 48 维基础（回合比例、分数/目标比、体力比、各区域牌数、13 种资源、stance one-hot、三维权重、fan vote、gimmick 剩余、battle 类型）+ 回合颜色 one-hot + stage 类型 + loadout 上下文 + 可选 deck 组成。每个动作特征 = 静态前缀（`EffectTaxonomy` 对卡的 `ProduceExamEffectType` 多热、trigger phase 多热、category/rarity/costType one-hot）+ 14 个数值（体力/貫通/资源 cost、`evaluation`、可用、强化次数、grow 数、customized、分数差比、三资源、槽位）。
  - `GakumasPlanningEnv`：培育外循环，动作 = `legal_actions()` 的候选列表（lesson/refresh/授業/おでかけ/shop_buy_card_1..4/…），同样 mask。`GakumasUnifiedBattleEnv` 复用 exam env。
  - 训练：SB3 `MaskablePPO`（`src/training/backends.py`），RLlib 备选；`autopilot.py` 课程 `初中间 → 初最终 → NIA中间 → NIA最终 → NIA选拔 → 初 Regular 全流程 → 初 Master → NIA Pro → NIA Master`，每阶段 `RL 探索 → 固定 seed 轨迹选优 → masked BC 自蒸馏 → RL 微调`。reward 有 `score`/`clear`/potential-based（`_phi_goal/_phi_eval/_phi_archetype/_phi_risk/_phi_efficiency`）三套。**仓库没有公布任何训练结果数字**。`src/demo_exam.py` 输出 HTML 回放；`src/interfaces/api.py` 是 FastAPI（列剧本/解析 loadout/跑 exam）。
- **其它可复用点**：`ProduceExamAutoEvaluation` 三张表被读入（`auto_evaluations()` 等）作为 `exam_effect_priors()`；`src/idol_config.py:build_initial_exam_deck()` 用 `ExamInitialDeck`+`ProduceCardPool` 组初始牌；支援卡 `SupportCardProduceSkill*` 的 lesson support 升级逻辑（`_apply_support_card_support`）；`scripts/generate_effect_coverage_matrix.py` 自动生成 P アイテム/饮料/挑战道具的覆盖矩阵（`docs/` 目录未随仓库提交）。

### 2.2 lts129/Gakumas-RL（+ Gakumas-CalCardDeck）

> 2026-09-10 复核补充：见[固定提交审计](reference_repositories_review_20260910.md)。该项目与本地 vendored 的 skyfsj/gakumas-rl 不同；以下终局奖励旧摘要已更正。

- 目标是**实机 OCR 部署**（`use/Use.py` 识别窗口、手牌），训练在自写环境 `envs/card_game_env_base.py`：`CardGameEnv(gym.Env)`，`action_space = Discrete(max_hand+1)`，obs = `dense_obs(136=18+5×22)` + `allcard_dense_obs(1080=40×27)` + `hand_sparse_obs(30)` + `allcard_sparse_obs(240)`；`reset(seed)` 可指定 seed。
- 数据源：`卡牌属性.xlsx`（sheet「基础词条类型」等，pandas 读入），卡 = `Card{name, card_type, cost_type, keywords:[Keyword{check_condition, check_value, keyword_type, value1, value2}]}`（`envs/cal_function/define_card.py`）——完全手写中文"词条"，**只支持センス**，角色卡/支援卡/道具不全，场地效果只有一个。
- 公式：`function_cal.py` 的 `cal_base/cal_jizhong/cal_juehaotiao` 均 `math.ceil`。奖励是项目自己的训练设计。2026-09-10 核对提交 `fe57c6235bda44393de998f1b43ed08477ede525`：`card_game_env_base.py` 终局实际为 `4·log10(score+1) + score/2000`；此前摘要 `8·log10(总分)`有误，不能作为当前实现或游戏评分公式使用。
- 算法：`MaskablePPO` + 专家数据 BC 正则（`ppo_trainer_withbc.py:fine_tune_with_bc`），`Record.py` 按 seed 搜最优动作序列做专家数据，`train_bc.py` 纯 BC；自定义 `CardEmbeddingExtractor`。提供 5 个预训练 `.zip`。无公开成绩。无许可证。
- `Gakumas-CalCardDeck`：支援卡最优编成 + SP 概率（xlsx），非模拟器。

### 2.3 lirichar/gakumastrain

- 自称 clean-room，**明确不用解包数据**、不复制 lts129 代码。`src/gakumas_sim/data/content.json`（20 KB：3 scenarios × 难度、34 张卡、20 道具、12 事件）+ `generated_cards.json/generated_items.json`（从 lts129 工作簿/Game8 导入，标 `exact:false`）。
- 剧本：初 Regular/Pro/Master/Legend、NIA Pro/Master、**H.I.F 20 日选拔 + 9 行程本战**（周程结构对，但数值是近似）；三 plan 只有 Sense 集中/好調、Logic 干劲/好印象。
- 引擎 `engine.py:GameEngine`：打分 `score = int(base × stat/50) + focus; ×1.5 if 好調`——是**玩具级近似**，不能作为规则参考。`env.py:IdolTrainingEnv(seed)`，动作固定 0..511 + `legal_actions()`，`state_key()` 离散化，`agent.py:QLearningAgent` 表格 Q-learning；README 报告 HIF 本战 sense：固定评估集均值 7186 vs 随机 7084。另有 MaaGakumasu 实时建议桥。
- 价值：H.I.F 周程/选拔结构与 `train-converge` 评估流程可参考；引擎本身不可移植。

### 2.4 kjirou/gakumas-core

- MIT，TypeScript，34k 行（含 15k 行测试），2024-09-22 停更（作者声明不再追新卡）。只做 lesson/exam 打牌，**不含培育**；センス/ロジック；无アノマリー；无 コンテスト。
- 卡牌手写在 `src/data/cards.ts`（168 张，`effects: [{kind:"getModifier"|"perform"|"performLeveragingModifier"|"drawCards"|"delayedEffect"|"reactiveEffect"|…}]`），P アイテム/饮料/偶像同理。
- 生命周期 `getNextPhase → startTurn → playCard/skipTurn/useDrink → endTurn`（`src/index.ts`），不可变状态，`diffUpdates` 逐步记录。
- **RNG**：`initializeGamePlay({getRandom})` 可注入（默认 `Math.random`），洗牌 `utils.ts:shuffle(getRandom)`——可 seed。
- **取整**（`src/lesson-mutation.ts:680-760`）：`baseScore = ceil((value + focus×focusMultiplier + boostPerCardUsed×uses) × goodConditionMultiplier/10 × mightyPerformance)`，其中 `goodConditionMultiplier = (好調?15:10) + (絶好調 ? 好調残ターン : 0)` **用整数算避免 0.1×1.4 浮点误差**；`score = ceil(baseScore × scoreBonus/100)`；元気 `ceil(value + motivation×mult + …)`；体力消耗 `ceil(cost×rate) − reduction`（`models.ts:355`）；元気分スコア `ceil(vitality×pct/100)`；元気減少 `floor(vitality×rate)`。这是社区"スコア切り上げ、元気減少切り捨て"共识最干净的代码化。
- **实机对照测试**：`src/e2e-tests/{kuramotochina-ssr-1,kuramotochina-ssr-2,fujitakotone-ssr-1,arimuramao-ssr-2}.test.ts` 共 9 个 test，每个按 YouTube 录像逐回合复现（注释附视频链接），是**唯一带真实录像对照的固定夹**——可直接翻成我们的 Python 回归用例（卡 id 需映射到 master id）。
- TODO（README）：コンテスト专属 P アイテム、アイドルの道 応援/トラブル、レッスンサポート发动率未知、コンテスト AI 未知。

### 2.5 surisuririsu/gakumas-tools（packages/gakumas-data + gakumas-engine）

- BSD-3，79★，2026-09-05 仍活跃（changelog 至 2026-08-28）。**只建模コンテスト**（`stages.csv` 的 `type ∈ {contest 153, event 24, linkContest 3}`），无 lesson/exam 的 clear/perfect、无培育。三 plan 都有（卡 206 sense / 222 logic / 170 anomaly / 36 free；870 行 `skill_cards.csv`、484 行 `p_items.csv`、111 行 `customizations.csv`）。
- **数据源是手写 CSV DSL**（见 §5），`pnpm validate:data` 编译期校验。
- 引擎 `packages/gakumas-engine/engine/`：`StageEngine`（状态机）+ `TurnManager`（`generateTurnTypes` 抽回合颜色、`startTurn/endTurn`）+ `BuffManager` + `EffectManager` + `CardManager`（区域移动/targeting）+ `Executor`（DSL 动作执行，`resolvers.js` 里 `score`/`genki`/`stamina`… 各字段 resolver）+ `Evaluator` + `StageLogger`；策略 `HeuristicStrategy`（启发式浅搜）/`ManualStrategy`/`PlayerStrategy`。
- **RNG**：`utils.js` mulberry32，`resetRand(seed)`、`getRandCallCount()`，README 明言确定性。
- **取整**：`Executor/index.js:461` 对字段赋值 `Math.ceil(v.toFixed(2))`；`resolvers.js:69` cost `Math.floor`，`:294` stamina `Math.floor`。
- 测试：`tests/suite.jsonl` 524 个 loadout 的**引擎快照**（不是实机分数，`note:"random"`），`rehearsalScores.jsonl` 8 条是 OCR 测试。无实机夹具。
- `gakumas-tools/utils/hif.js`、`produceRank.js`：HIF 与 初/Legend 评价值公式（§6）。

### 2.6 katabami83/gakumas_contest_simulator 与 kanon511/new_gakumas_contest_simulator

- 两者都是**コンテスト**手写 JS 引擎（Vue/纯 JS），三 plan 卡表手写为 `{id, name, type, plan, cost:{type,value}, condition:'', effects:[{type:'score',value:9}], limit, ...}`（katabami 13k 行数据；kanon511 18k 行含 UI），2024-12/2025-01 停更（覆盖到 フェス 2 弾）。
- katabami：`Player` 持 `RandomGenerator(seed)`（LCG `a=1664525,c=1013904223`）→ **可复现**；`ai/ContestAI.js` 是深度 `depth` 的全动作枚举搜索 + `EvaluationCalculator`（好印象等差数列期望、集中/やる気按剩余回合倍率×1.2、好調 log 曲线）；`ParameterCalculator.js:21` 的属性→倍率 `ceil(floor(ceil(status×coef×criterion×(1−penalty)+100)×(1+supportBonus)×10)…)`。无许可证。
- kanon511：`Math.random`（不可 seed）；`AutoContest.select()` 取手牌 `card.evaluation` 最大者，权重来自 **master 表 `ProduceExamAutoEvaluation`**（`scripts/simulator/data/ProduceExamAutoEvaluation.js`：`{maxRemainingTerm:7, "ProduceExamEffectType_ExamParameterBuff": {evaluations: {"1": {ProduceExamAutoEvaluationType_Parameter: {evaluation, examStatusEnchantCoefficientPermil}, ...}}}}`）——这是官方自动打牌权重的唯一 JS 落地，和 gakumas-rl 的 `auto_evaluations()` 一样可作 baseline policy。`Calculator.js` 各处 `Math.ceil`。无许可证。

### 2.7 其它模拟器 / 小工具

- **mihalinn/gakumasu**：React 最终试验 UI，**ロジック限定**（logic.json 249 张 + free 24 + trouble 1，其余 json 为空），效果由 CSV "略称" 经 `scripts/update_cards.js:parseEffectString` 转成 `EffectType`（`CARD_EFFECT_REFERENCE.md`：`genki:5`、`score_impression:1`、`gate:[motivation>=3]:genki:5`、`turn_start:gate=[…]&effect=…`）。`effectResolver.ts` 打分用 `Math.floor`（与共识相反），`Math.random` 不可 seed，`comparison_report.md` 显示 262 卡有 29 处转换不一致。仅供 UI 参考。
- **tyuukiti/gakumasu-anomaly-sim**：MIT。アノマリー最终回合**全探索**（含抽牌分支期望）；卡从 wiki 爬成 YAML（`Data/AnomalyCards/*.yaml`：`variants[{level, cost:{hp,full_power}, effects:[{kind:'param'|'state_change'|…, value, note}], raw_effect_text, unparsed_lines}]`）——数据本身是"半解析 + 原文"。`effectExecutor.ts` 实现了 wiki 版熱意公式：`ceil((熱意追加 + N) × (1 + 熱意増加%/100))`，N=温存1段=5/2段=8；强気 1段 +100% / 2段 +150%；param 用 `floor(base×mult)`。`moveSearch.ts` 的期望搜索可借鉴做 MCTS 对照。
- **tyuukiti/gakumasu-calc**：支援卡编成→属性理论值，剧本 **初 Legend / NIA Master / H.I.F（选拔 Day1-20 + 本战 Day21-29，HIF ボーナスパネル Lv、本战上限增加）**；`web/src/services/statusCalculation.ts` + C# 双实现且有 55+48 个交叉一致性测试。对我们的**培育外循环参数增长（lesson/授業/おでかけ/支援卡事件触发次数）**是最完整的数值参考；数据在 `Data/SupportCards`、`Data/Plans`（YAML）。
- **happyMilleFeuille/gakumas**：韩文站，`calcLogic.js` 有 初/NIA/HIF 三剧本的周程动作与授業/おでかけ/差入 收益表（`hajimeLessonStats`、`niaLessonStats`、`hifLessonStats.byWeek`）、`producedata.js`（3.4k 行 P アイドル/道具/卡 描述，韩日双语手写）、`calcModals.js` 的 HIF 评价值（§6）与"強化 (isKyouka)" 分支：`floor(sum×0.72 + v4×8.8888)`，v4 上限 610。1.2 GB 主要是 webp/mp4 资源。
- **Taka499/gakumas-hajime-lesson**、**kakris704/gakumas-hajime-simulator**：初 Legend / 初 的周程参数计算（`LEGEND_LESSON_VALUES` 周 4/7/12/14/16 = +140/180/260/370/570，非选属性 +55/60/70/90/115；`calcLessonIncrease = ceil((base+limitIncrease)×(1+lessonBonus%))`，试验一位 +50，上限 1800）。`_docs/GAME_MECHANICS.md` 是 wiki 摘要。
- **ummmm300/gakumas-solo-simulator**：单卡分数 `ceil((basePower+other)×scoreMultiplier×extra)`，玩具。
- **tp6m4t/gakumas_go**：Go TUI，4 张卡，事件驱动 buff，半成品。
- **yuuhi1315/Gakumas-Simulator**：ガシャ天井概率，无关。**sameta-gakmas/gakumas-exam-simulator**：空仓库。**gyeolls/gakumas-contest**：单 HTML。**mafu176/gakumas-contest-tracker**：战绩记录 + OCR，无引擎。

### 2.8 数据 / 工具链仓库（非引擎）

- **vertesan/gakumasu-diff**：我们的数据源。`ProduceExamEffect.yaml` 73 万行；`Produce.yaml` 8 个 produce（001 レギュラー13步 / 002 プロ16 / 003 マスター18 / 004 NIA プロ27 / 005 NIA マスター26 / 006 レジェンド18 / 007 HIF 選抜試験20 / 008 HIF 本戦9），`ProduceGroup.yaml` 三种 `ProduceType_{FirstStar, NextIdolAudition, HatsuboshiIdolFestival}`；`ExamSetting.yaml` 含全部 permil 常数（`examParameterBuffPermil`, `examConcentrationLessonValueMultiplePermil1/2`, `examPreservationReleaseBlockAdd1/2`, `overPreservationRelease*`, `fullPowerPlayableValueAdd`, `handLimit`, `holdLimit`, `turnStartDistribute`, `examTurnEndRecoveryStamina`, `produceExamPanicStaminaCandidates`…）；`ProduceStepAuditionDifficulty.yaml` 4259 行（每偶像×produce×step 的 `baseScore/forceEndScore/parameterBaseLine/produceExamBattleConfigId/produceExamGimmickEffectGroupId/voteCountBaseLine/starScoreBonusBaseLine`）。**`ProduceExamEffectType` 枚举本身不在 YAML 里**（只以字符串出现），完整枚举见下一条。
- **vertesan/hatsuboshi-library**（AGPL）：`app/types/proto/penum.ts` 是从 proto 生成的**全量枚举**：`ProduceExamEffectType` 169 项（含 Unknown；master data 实际用到 108 项，另有 60 项如 `ExamChainEffect`、`ExamForecast`、`ExamUplifting`、`ExamThresholdDown`、`ExamStanceLock{Concentration,FullPower,Preservation}` 等从未在数据出现）、`ProduceExamPhaseType` 58 项、共 214 个 enum。`app/components/media/effectDescription.tsx` 展示 `produceDescriptions` 段落的渲染逻辑。**这是我们 `ProduceExamEffectType` 字典最好的起点**（枚举是数据结构不是代码，AGPL 风险可忽略；我们只需要名字列表）。
- **imas-tools/gakumas-master-translation**：`scripts/gakumasu_diff_to_json.py` 把 YAML 转 JSON（112 表），`data/ProduceDescriptionProduceExamEffectType.json` 等是**带中文翻译的效果类型描述表**（结构 `{rules, data}`），可作枚举语义字典的第二来源。
- **kotonebot/kaa-game-data**（GPL）：`kaa-data schema` 把 gakumasu-diff YAML 灌进 SQLite `game.db`——若我们想要 SQL 查询而不是 YAML 解析，可借鉴其 `src/schema`。
- **GkmasObjectManager / HatsuboshiToolkit / hatsuboshi-app backend+types / Xilorole/gakumas-data**：资源解密、REST、手写类型、コミュ转写；对规则引擎无直接价值（`hatsuboshi-app/types` 只有 14 个手写 enum，无 `ProduceExamEffectType`）。

## 3. `ProduceExamEffectType` 覆盖对照

统计口径：`gakumasu-diff/ProduceExamEffect.yaml`（2026-09-04）中出现的 `effectType` 值（不含 `Unknown`）共 **108** 个；`hatsuboshi-library/penum.ts` 枚举共 169 个。

| | 数量 | 说明 |
|---|---|---|
| master data 使用 | 108 | 出现频次 top：`ExamLesson 1698, ExamBlock 740, ExamStatusEnchant 448, ExamLessonBuff 440, ExamReview 384, ExamParameterBuff 301, ExamCardPlayAggressive 210, ExamFullPowerPoint 203, ExamLessonValueMultiple 196, ExamPlayableValueAdd 175, ExamAddGrowEffect 160, ExamEffectTimer 138` |
| gakumas-rl `ids.py` 声明 | 100 | 其中 `ExamStaminaRecover` 数据里没有 |
| gakumas-rl 覆盖 ∩ 数据 | 99 | |
| **数据有、gakumas-rl 没有** | 9 | `ExamAggressiveAdditiveFix(3), ExamConcentrationLessonMultipleAdditive(6), ExamForcePlayCardSearchWithCost(1), ExamFullPowerLessonMultipleAdditive(11), ExamGimmickEnthusiastic(6), ExamLessonBuffAdditiveFix(6), ExamLessonDependStamina(3), ExamMultipleEnthusiasticLesson(3), ExamStatusEnchantEncore(10)`（括号为出现次数；`ExamLessonDependStamina`/`ExamMultipleEnthusiasticLesson` 会落到前缀 handler，其余落到 fallback 当作计时效果——即静默错误） |
| 枚举有、数据从未用 | 60 | 可以先不管 |

`ProduceEffectType`（培育外循环）：数据 66 个，gakumas-rl 处理 57 个；缺 `CustomizeProduceCardProducePointDownMultiple, EventActivityProducePointDown, ParameterLimitUp, ProduceCardChangeSelect, ProduceCustomizeItemUpgrade, ProduceDrinkPossessLimitUp, ShopProduceCardPriceDiscountMultiplePermanent, StarAddition, StarPermilUp`。

## 4. 各引擎的 RNG / 相位 / 取整一览

| 引擎 | seed | 相位/触发模型 | 取整 |
|---|---|---|---|
| gakumas-rl | `np.random.default_rng(seed)` | master `ProduceExamPhaseType` 全量 dispatch（`_dispatch_phase`），trigger 按主数据字段匹配 | 参照值 `ceil`，分数 **float 不取整**（需改），计数 `round` |
| gakumas-core | `getRandom` 注入 | 固定 `startTurn/playCard/endTurn`，`reactiveEffect`/`delayedEffect` 手写 | 分数/元気/体力 `ceil`；元気減少 `floor`；好調倍率整数化 |
| gakumas-tools engine | mulberry32 `resetRand(seed)` | DSL `at:phase`（32 种）+ `group` 排序 | 字段赋值 `ceil(toFixed(2))`，cost/stamina `floor` |
| katabami83 | LCG seed | 手写 `Effective/PreEffect/PassiveStatusEffect` | `Math.ceil`（属性倍率有 `ceil(floor(ceil(...)))` 链） |
| kanon511 | `Math.random` | 手写 | `Math.ceil` |
| mihalinn | `Math.random` | 手写 | `Math.floor`（存疑） |
| anomaly-sim | 无（全枚举） | 单回合 | param `floor`、熱意 `ceil` |
| gakumastrain | `seed` | 无相位 | `int()` 近似 |

## 5. gakumas-tools `Effects.md` DSL 语法摘要

`packages/gakumas-data/Effects.md`（`csv/skill_cards.csv` 的 `conditions/cost/actions/effects` 列、`p_items.csv`/`stages.csv` 的 `effects`、`p_drinks.csv` 的 `actions`、`customizations.csv` 的 patch 列）：

- **结构**：`at:<phase>[<filter>]? { if:<cond> { target:<expr> { <action>… } } limit:N ttl:N delay:N group:N line:N }`；效果以空白或 `;` 分隔；裸赋值 `score+=5` 就是 action（`do:` 可省）。
- **phase**（`at:`）32 种：`startOfStage, afterStartOfStage, prestage, beforeStartOfTurn, startOfTurn, afterStartOfTurn, turn, everyTurn, endOfTurn, turnSkipped, cardUsed, activeCardUsed, mentalCardUsed, afterCardUsed, afterActiveCardUsed, afterMentalCardUsed, processCard, processCost, checkCost, cardMovedToHand, cardMovedToHeld, cardRemoved, buffCostConsumed, stanceChanged, stanceValueChanged, staminaDecreased, genkiIncreased, goodConditionTurnsIncreased, concentrationIncreased, goodImpressionTurnsIncreased, motivationIncreased, fullPowerChargeIncreased`；`at:cardUsed[active & !removed]` 是 target-rule 过滤。
- **条件**（`if:`）：比较运算 + `& | !` + 括号；引用状态变量、resolver（`isVocalTurn, isStrength, isPreservation, isFullPower, isDirectEffect, stanceChangedTimes, usedCardId, cardHasEffect(name), countCards[expr], effectCounter(name)`…）、字符串字面量（`strength`, `SSR`）。
- **动作**：赋值 `= += -= *= /= %=`；特殊动作 `drawCard(n), upgradeHand, exchangeHand, addCardToHand(id), moveRandomToHand[expr](n), moveSelectedToHand, moveAllToTopOfDeck, holdRandom/holdAll/holdThis, useRandomFree/useAllFree/useSelectedFree, removeAll, moveHeldCardsToHand, removeDebuffs(n), setStance(s), decreaseFullPowerCharge(n), setScoreBuff(amount, turns?), setScoreDebuff, setGoodImpressionTurnsBuff/EffectBuff/TimesBuff, setMotivationBuff, setGoodConditionTurnsBuff, setConcentrationBuff/EffectBuff, setEnthusiasmBuff/Bonus, setFullPowerChargeBuff/EffectBuff, setStrengthEffectBuff`。
- **target 表达式**：`this, hand, deck, discarded, held, removed, all, active, mental, trouble, basic, pIdol, T/N/R/SR/SSR/L`，函数 `effect(name), baseId(n), id(n)`，可 `& | !` 组合。
- **growth 字段**（`g.*`，持久附着在卡上）：`g.score, g.scoreTimes, g.cost, g.typedCost, g.genki, g.goodConditionTurns, g.perfectConditionTurns, g.concentration, g.goodImpressionTurns, g.motivation, g.fullPowerCharge, g.halfCostTurns, g.scoreByGoodImpressionTurns, g.scoreByMotivation, g.scoreByGenki, g.stanceLevel`。
- **状态变量**（约 60 个）：`turnsElapsed, turnsRemaining, cardUsesRemaining, stamina, fixedStamina, genki, fixedGenki, cost, score, scoreTimes, cardsUsed, activeCardsUsed, turnCardsUsed, goodConditionTurns, perfectConditionTurns, concentration, goodImpressionTurns, motivation, prideTurns, stance, prevStance, lockStanceTurns, fullPowerCharge, cumulativeFullPowerCharge, enthusiasm, strengthTimes, preservationTimes, leisureTimes, fullPowerTimes, halfCostTurns, doubleCostTurns, costReduction, costIncrease, doubleCardEffectCards, nullifyCostCards, nullifyGenkiTurns, nullifyDebuff, noActiveTurns, noMentalTurns, noCardUseTurns, poorConditionTurns, uneaseTurns, concentrationMultiplier, enthusiasmMultiplier, motivationMultiplier, goodConditionTurnsMultiplier, *Delta…`。
- **customization patch**：`@anchor` 标注效果或单个 action，`level:N { @foo score+=10 }` 分级覆盖，`+ <effect>` 追加。

对我们的意义：这套 DSL 是对"人类可读效果语言"最成熟的设计（状态变量名、phase 名、target 代数），我们的 JSON DSL 可以直接借用其命名；但它与 master 枚举是**两套本体**，不能自动映射。

## 6. 评价值公式

### 6.1 H.I.F（`huraru7/gakumas_HIF_Rating_Calculation/js/formulas.js`，与 `gakumas-tools/utils/hif.js`、`happyMilleFeuille/gakumas/calcModals.js` 三方一致）

```
输入：paramTotal = Vo+Da+Vi（各 ≤ 3200）, starQuality（本戦 R2 前スター性，≤ 1110）,
      r1Score（R1 实际分数）, r2Score（R2 分数）

starGainR2(s) = ceil( s ≤ 400000 : s × 0.0001875
                     s ≤ 600000 : 75  + (s − 400000) × 0.000225
                     s ≤ 1000000: 120 + (s − 600000) × 0.000075
                     else       : 150 )

r1Eval(s)  = floor( s ≤ 300000 : 0
                    s ≤ 700000 : (s − 300000) × 0.01
                    s ≤ 1000000: 4000 + (s − 700000) × 0.003
                    s ≤ 1200000: 4900 + (s − 1000000) × 0.002
                    s ≤ 1400000: 5300 + (s − 1200000) × 0.001
                    else       : 5500 )
      // gakumas-tools 版先 floor(r1Score/1.2) 再查表（R1 有 ×1.2 補正，MAX_ROUND1_SCORE=1680000）；
      // huraru7 版把 "実際のスコア" 直接查表，等价于 gakumas-tools 的 adjusted score。

r2Eval(s)  = floor( s ≤ 600000 : 0
                    s ≤ 900000 : (s − 600000) × 0.004
                    s ≤ 1500000: 1200 + (s − 900000) × 0.008
                    s ≤ 2000000: 6000 + (s − 1500000) × 0.002
                    s ≤ 2400000: 7000 + (s − 2000000) × 0.001
                    else       : 7400 )

r2StarGain = floor( starGainR2(r2Score) × 1.5 )
statStar   = floor( paramTotal × 2 + (r2StarGain + min(starQuality,1110)) × 7.5 )
評価値     = statStar + r1Eval(r1Score) + r2Eval(r2Score) − 2000

ランク：S5 ≥ 35000, S4+ ≥ 30000, S4 ≥ 26000, SSS+ ≥ 23000, SSS ≥ 20000, SS+ ≥ 18000, SS ≥ 16000,
       S+ ≥ 14500, S ≥ 13000, A+ ≥ 11500, A ≥ 10000, B+ ≥ 8000, B ≥ 6000, C+ ≥ 4500, C ≥ 3000
```

`happyMilleFeuille` 版把 スター性 上限设为 1335（把 R2 スター性获得并入输入），并有"強化"模式 `floor(sum × 0.72 + v4 × 8.8888)`（v4 ≤ 610）——这两个差异需实测确认。反算所需 R2 分数用二分（R2 同时影响 スター性）。

### 6.2 初 / 初 Legend（`gakumas-tools/utils/produceRank.js`，与 gakumas-final-score、gkmas-rank-calculator、discord-bot 一致）

```
順位点 = {1:1700, 2:900, 3:500, 4+:0}
パラメータ加算 = {1:+30, 2:+20, 3:+10}（Legend: {1:+160, 2:+80, 3:+40}），各属性 min(param+bonus, 上限)；上限 regular 1000 / pro 1500 / master 1800 / legend 3000
パラ評価 = floor( Σparam × 2.3 )（Legend: × 2.1）
最終試験分段（非 Legend，切り捨て）: ≤5000:0.30 | ≤10000:0.15 | ≤20000:0.08 | ≤30000:0.04 | ≤40000:0.02 | >40000:0.01
Legend 最終: ≤300000:0.015 | ≤500000:0.01 | ≤600000:0.008 | ≤2000000:0.001 | >2000000:0
Legend 中間: ≤10000:0.11 | ≤20000:0.08 | ≤30000:0.05 | ≤40000:0.008 | ≤50000:0.003 | ≤60000:0.002 | ≤200000:0.001 | >:0
評価値 = 順位点 + パラ評価 + 中間評価(Legend) + 最終評価
```

NIA：`gakumasu-discord-bot/scenarios/nia_scenario.py` 有 fan 换算（`(auditionScore − 減衰ライン) × coef + const`，master ×1.5）与きらめき，参数表在 `config/nia_settings.py`。

## 7. 排名推荐

### (a) 效果解释器（`ProduceExamEffectType` → 状态变更）

1. **移植 `gakumas-rl/src/simulation/exam/{ids.py, effects/*.py, triggers/*.py}` 的结构与语义**（registry + 按枚举分组的 handler + trigger 逐字段匹配），配合 `hatsuboshi-library/penum.ts` 的 169 项全枚举和 `gakumas-master-translation` 的描述表补齐语义字典。补上 9 个 HIF 新枚举。**注意 GPL-3.0**：如果逐行移植代码，我们的仓库需要兼容 GPL；如果只借用"分组/字段语义"重写，风险可控。建议：把它当**规格文档 + 差分测试对照**，重写而非复制。
2. 取整规则以 `gakumas-core/src/lesson-mutation.ts` 为准（分数 ceil、好調倍率整数化），覆盖 gakumas-rl 的 float 累加。
3. `gakumas-tools/Effects.md` 只借命名，不借本体。

### (b) 回合引擎（相位、区域、stance、体力）

1. `gakumas-rl/src/simulation/exam/runtime.py` 的 `_start_turn / _play_card / _end_turn / _dispatch_phase / _card_stamina_components / _apply_score_value_modifiers`——它是唯一把 `ProduceExamPhaseType` 58 个相位与 `ExamSetting` 常数接起来的实现；顺序（好印象/パラ強化衰减 → 全力 → gimmick → StartTurn → TurnTimer → 抽牌 → scheduled）可直接作为我们的相位表。
2. `gakumas-core` 的 e2e 录像用例（9 个）作为回归夹具；`gakumas-tools` 的 `HeuristicStrategy` 与 kanon511 的 `AutoContest`（官方 `ProduceExamAutoEvaluation` 权重）作 baseline policy。
3. アノマリー细节（熱意/温存解除数值）交叉验证 `gakumasu-anomaly-sim/effectExecutor.ts` 与 `ExamSetting.preservationReleaseEnthusiastic1/2, overPreservationReleaseEnthusiastic`。

### (c) 培育外循环

1. `gakumas-rl/src/simulation/produce/{runtime.py, items.py}`（4.8k 行）：周程/checkpoint、shop、customize、audition 选择、支援卡事件、`ProduceEffectType` 57 种、`ProduceItemInterpreter`（P アイテム trigger 解析）。同样按规格重写；缺 H.I.F 路线（选拔 20 日 + 本战 9 行程、star quality、`ParameterLimitUp` 面板、`StarAddition/StarPermilUp`）。
2. 数值对照：`tyuukiti/gakumasu-calc`（HIF/初Legend/NIA 的 lesson/授業/おでかけ/支援卡触发收益，TS+C# 双实现有测试）、`happyMilleFeuille/gakumas/calcLogic.js`（`hifLessonStats.byWeek`）、`gakumas-hajime-lesson`（Legend lesson 表）。
3. `gakumastrain/content.json` 的 HIF 周程骨架只做结构参考。

### (d) 评价值

直接实现 §6：HIF 用 huraru7 / gakumas-tools 版（三方一致），初/Legend 用 `produceRank.js`，NIA 用 discord-bot 的 fan/きらめき 参数；对照 master 表 `ResultGradePattern` / `ProduceExamBattleScoreConfig`（我们已确认）做单元测试。

### (e) RL 环境

1. `gakumas-rl/src/simulation/envs.py` 的观测/动作设计（`Dict{global, action_features, action_mask}` + `Discrete` 槽位动作，卡特征 = 枚举多热 + 数值）和 `src/repository/master_data.py:EffectTaxonomy` 的固定索引编码——这是与"数据驱动效果"天然匹配的编码方式，建议照搬设计。训练流程（MaskablePPO → 固定 seed 轨迹选优 → masked BC → 微调）与 `AGENTS.md` 里的可复现要求也值得沿用。
2. `lts129/Gakumas-RL` 的 PPO+BC 交替与 `CardEmbeddingExtractor` 是次选参考；其 xlsx 数据不用。
3. `katabami83` 的深度枚举搜索 + 期望评估、`gakumasu-anomaly-sim` 的抽牌分支期望，可作 MCTS 基线。

## 8. 缺口清单

1. **H.I.F 全套**：无任何仓库用 master data 实现 HIF 打牌规则（`ExamStatusEnchantEncore`、`ExamGimmickEnthusiastic`、`ExamLessonDependStamina`、`ExamMultipleEnthusiasticLesson`、`Exam{FullPower,Concentration}LessonMultipleAdditive`、`Exam{LessonBuff,Aggressive}AdditiveFix`、`ExamForcePlayCardSearchWithCost`）与培育规则（`StarAddition/StarPermilUp/ParameterLimitUp`、`ProduceType_HatsuboshiIdolFestival` 的 20+9 步周程、两轮制本戦、スター性→評価値）。只有评价值公式（§6.1）和参数增长表（gakumasu-calc / happyMilleFeuille）是现成的。
2. **实机对照数据**：只有 gakumas-core 的 9 段录像用例（2024 年，センス/ロジック），无 アノマリー、无 NIA/HIF、无培育全流程录像；gakumas-tools 的 524 条是引擎快照。需要自建录像→jsonl 的采集流程（gakumas-rl 的 `manual_exam_setups.py` 格式可直接用）。
3. **取整/相位的权威性**：gakumas-rl 按 help 页推导，分数不取整、集中加法路径需核对；gakumas-core 有录像背书但停在 2024-09。两者合并后仍需实测（尤其 `examLessonValueMultipleDependReviewOrAggressive`、`ParameterBuffMultiplePerTurn`、温存解除）。
4. **`ExamCardMove / ExamCardCreateSearch / ExamForcePlayCardSearch / ExamSearchPlayCardStaminaConsumptionChange`**：gakumas-rl 自评"部分实现"（`pickRangeType/pickCountType` 组合未穷尽）。
5. **枚举语义字典**：169 项枚举无人给出完整的自然语言定义；只能从 `ProduceDescription*` 表 + `gakumas-master-translation` 的描述 + 主数据出现上下文反推。60 个未使用枚举可延后。
6. **官方 AutoPlay**：`ProduceExamAutoEvaluation` 三表已有两处落地（gakumas-rl、kanon511），但 `examAutoPlaySearchCommandLimit/PlanLimits` 的搜索算法无人实现。
7. **许可**：最有价值的 gakumas-rl 是 GPL-3.0；gakumas-core MIT、gakumas-tools BSD-3、anomaly-sim MIT 可放心引用；katabami83 / kanon511 / lts129 / mihalinn / gakumastrain / gakumasu-calc 无许可证（只能当参考读物）。
8. **隐藏概率**：SP レッスン概率、事件权重、shop 刷新、回合颜色分布（gakumas-rl 用三维比例近似）、`ProduceCardRandomPool` 权重——所有仓库都是猜测或近似，需实测拟合。
