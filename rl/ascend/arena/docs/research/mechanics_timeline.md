# 学マス master data：数据时效性与机制/评分变更时间线

> 目的：审计 `data/raw/gakumasu-diff`（vertesan/gakumasu-diff 的 git clone）相对真实游戏的**新鲜度**，并从全部 git 历史中提取**机制与评分规则随时间的变化**，据此给出通用引擎必须具备的扩展点清单。
> 生成工具：`tools/masterdata/history_diff.py`（见 §B.0）。审计日期：2026-09-07。
> 相关文档：`docs/research/data_sources.md`（数据源）、`docs/research/existing_engines.md`（现有模拟器）、`docs/ARCHITECTURE.md` §8。

---

## Part A — 数据新鲜度

### A.1 dump 现状

| 项目 | 值 |
|---|---|
| 仓库 | `vertesan/gakumasu-diff`，本地 clone 已 `--unshallow`，**249 个 commit**，2024-05-18 → 2026-09-04 |
| 最新 commit | `5b8969e` 2026-09-04 11:03:33 UTC（=JST 20:03）；同日还有 `855a24f` 02:03 UTC（=JST 11:03） |
| 提交者 | 237/249 为 `vts-server`（自动化账号），其余 12 个是 2024-05～2025-04 间作者 `vertesan` 的手动提交（大版本当天补跑）；commit message 是 master DB 文件的 sha256，无人工描述 |
| `ForceAppVersion.yaml` | iOS / Android / DMM 均为 **3.3.0**（`PlatformType_Other` 仍是 1.10.1，为占位） |
| 表数量 | 286 个 YAML（初始 dump 195 → 现在 286；历史上删除过 9 个） |

### A.2 与真实游戏的对照

能核实到的官方/半官方事实（本环境的出口代理封锁了 `gakuen.idolmaster-official.jp`、`idolmaster-official.jp`、App Store、Google Play、X、seesaawiki、wikiwiki 等域名，只能通过搜索引擎摘要间接核实；下列结论已用多条独立搜索结果交叉确认）：

- **ver.3.3.0** 于 **2026-08-17 11:00 JST** 上线（内容之一：サポートイベントのスキルカードが強化済みで獲得可能、可在设置中开关）。搜索引擎摘要将其描述为「約 3 週間前」，与今天 2026-09-07 吻合。
- 搜索 `ver.3.3.1` / `ver.3.3.2` / `ver.3.4.0` 均无结果，说明截至 2026-09-07 **3.3.0 仍是最新版本**。
- 2026-08-26 16:40 JST 有一次「あさり先生のプロデュースゼミ」的紧急维护（修复メモリーアビリティ重复的 bug）；dump 同日 02:03 UTC 有 commit `10fd0cf`。
- 2026-09-04 11:00 JST 新剧情活动「さいごの文化祭」开始；dump 同日 02:03 UTC（=11:03 JST）即有 commit `855a24f`，20:03 JST 再次 commit。
- 第三方商店镜像（QooApp）曾记录 v3.2.3 更新于 2026-08-05；dump 的 `ForceAppVersion` 在 2026-08-10 变为 3.2.3、2026-08-21 变为 3.3.0，与「发布日 + 数日后强制更新」的官方惯例一致（官方 X 历史公告：ver.1.3.0 于 7/18 发布、7/22 强制更新；ver.1.4.0 于 8/28 发布、9/1 强制更新）。

**结论：dump 没有落后于线上。** 最新 commit 就是 2026-09-04 当天两次更新的 master data；`ForceAppVersion` 3.3.0 与线上最新版本一致。dump 的「滞后」上限就是 vts-server 的轮询周期（见 A.3），实际观测为**同一小时内**。

### A.3 vertesan/campus 的更新机制与节奏

- `vertesan/campus`（Go）是 `gakumasu-diff` 与 `gkms-webdata` 的后台 cronjob：用 Firebase 匿名认证登录游戏服务器、下载加密的 master DB（MasterMemory/MessagePack）与混淆的 AssetBundle，解密后把每张表写成一个 YAML 文件，再由 `push_master.sh` 推送到 gakumasu-diff。仓库含 `cronjob.sh`、Docker 封装。
- 观测到的节奏（249 commits / 840 天 ≈ **每 3.4 天一次**，每月 4–13 次）。commit 的 UTC 小时分布高度集中在 02 时（=JST 11 时，学マス的常规更新时刻）与 06–11 时之间，说明 cron 以小时级轮询、只有 master 变化时才 commit。
- 最长间隔 **13 天**（2026-01-27 → 02-09），其余均 ≤12 天；从未出现「几周没更新」的情况，因此不存在系统性滞后。
- 每次 commit 改动 25–130 个文件；**改动文件 ≥ 100 的 commit 与大版本对应**：2024-11-16 `cda4882`（1.5.0）、2024-12-20 `4bad77b`（1.6.x）、2024-12-26 `cb5768d`（1.7.0 / N.I.A）、2025-05-16 `be4e3b4`（2.0.0）、2025-12-26 `6edc27e`（2.7.0 / レジェンド）、2026-05-16 `f0dac51`（3.0.2 / H.I.F）。
- 一个可直接用作「版本↔日期」映射的副产品：`ForceAppVersion.yaml` 自 2024-12-20 出现以来每次变化都对应一次强制更新（见 §B.3.0 的版本表）。

### A.4 对引擎的含义

- 每次同步 dump 后先跑 `history_diff.py HEAD@{1} HEAD`，把「新表 / 新枚举值 / 配置行变化」作为**升级信号**；不要假设 master data 只是「加卡」。
- 机制变化和版本号并不总是同步：2025-10-31 的最終試験スコア上限属于**代码侧**改动，`ResultGradePattern` / `ProduceGrade` 表当天没有任何变化（见 §B.3）。因此引擎的评分规则需要带 `effective_from` 日期、而非只跟 dump commit 走。

---

## Part B — 机制时间线（来自 git 历史）

### B.0 方法与工具

`tools/masterdata/history_diff.py DUMP OLD NEW [--cache DIR] [--examples T:F] [--json OUT]`：

- **新表 / 删表**：`git ls-tree` 比较。
- **顶层字段增删、枚举值增删**（按 `(table, field-path)`）：对每个 commit 的每张表做**逐行文本扫描**（不做 YAML 解析，`- key: value` 布局是机器生成的，扫描结果与解析一致），每个 commit 约 13 s，结果 pickle 到 `--cache`；两个 commit 的 diff 本身瞬时完成。
- **配置表逐行 diff**（默认 `Produce, ProduceSetting, ExamSetting, ResultGradePattern, ProduceGrade, ProduceExamBattleScoreConfig, ProduceStepAuditionDifficulty, ProduceExamBattleConfig, ProduceLiveEvaluation, ProduceSeason, ProduceSeasonZeroGrade, ForceAppVersion`，可用 `--config-tables` 覆盖）：`CSafeLoader` 解析，行键 = `id`；当 `id` 不唯一（如 `ProduceStepAuditionDifficulty` 每个角色 4 行共用一个 id）或没有 `id`（`ResultGradePattern`、`ForceAppVersion`）时自动改用 `id + 所有 *Id/*Type 字段 + number/level/grade` 的复合键。
- `--examples ProduceExamEffect:effectType`：对每个新枚举值在 NEW 版本里找一行示例并打印其 `produceDescriptions[*].text`（日文说明）。
- 本文的数据来自：对全部 249 个 commit 建缓存后按时间顺序两两 diff（脚本 `history_diff.summarize` + 一个 30 行的驱动），以及对上述配置表在**每个触碰它的 commit** 上做逐行 diff（比「按月抽样」更精确：本文给出的首次出现日期都是精确到 commit 的）。

常用：

```bash
python tools/masterdata/history_diff.py data/raw/gakumasu-diff HEAD~1 HEAD --cache /tmp/hcache --examples ProduceExamEffect:effectType,ProduceExamTrigger:phaseTypes
python tools/masterdata/history_diff.py data/raw/gakumasu-diff 6edc27e f0dac51 --cache /tmp/hcache --tables '^Produce' --json legend_to_hif.json
```

注意事项：
- 初始 commit `6a55c6a`/`2621ae8`（2024-05-18）就是 1.0 上线时的全量数据，因此「首次出现 = 2024-05-18」的项目只表示「上线即有」。
- 2024-05-19 `7eeab79` 出现了大量 `*_Unknown` 值和空字段（`null -> ""`）——这是 vertesan 改了序列化方式（把 0 值/默认值也写出来），不是机制变化。同理 2025-01-20/22 `ca49096`/`94c6eb3` 把所有 `descriptions` 字段改名为 `produceDescriptions`（并删除了 `ProduceDescription*Type` 旧表）。**读历史时要区分「序列化变化」与「机制变化」**。
- `ExamSetting` 里的功能开关字段会**出现→翻转→消失**（`examShuffleFixed` 2024-08-10 出现 false→08-29 true→12-20 消失；`auditionSupportUpgradeAdded`、`examCardSelectEvaluationTriggerCoefficientEnable`、`examDrawCountLimitFixed`、`examDrinkTriggerFixed`、`examStanceChangeAssignmentCountEnable` 2024-12～2025-08 出现、2025-10-14 全部翻回 false、2025-10-21 消失）。这些是官方修 bug 时的灰度开关，消失即「行为固化为 true」。引擎不必实现开关本身，但要知道对应行为的生效日期（见 B.3.4）。

### B.1 枚举值时间线

每个家族只列**初始 dump 之后**新增的值（初始值见 `docs/research/master_data_enums.md` / `inspect_dump.py --enums`）。「值」列省略了家族前缀。


#### `ProduceExamEffectType`（`ProduceExamEffect.effectType`，试验内效果）

共 138 个值，其中 67 个在初始 dump（2024-05-18）之后出现。

| 首次出现 | commit | 值 | 名称 / 示例说明（日文，取自 `produceDescriptions[*].text` 或 `ProduceDescription*`.name） | 示例行 |
|---|---|---|---|---|
| 2024-06-01 | `fc8c4c9` | `ExamBlockPerUseCardCount` | 元気+2（レッスン中に使用したスキルカード1枚につき、元気増加量+10） | `e_effect-exam_block_per_use_card_count-0002-0010` `effectValue1=2,effectValue2=10` |
| 2024-08-01 | `d2ff174` | `ExamLessonAddMultipleParameterBuff` | パラメータ+16（好調効果を1.5倍適用） | `e_effect-exam_lesson_add_multiple_parameter_buff-0016-0500-01` `effectValue1=16,effectValue2=500,effectCount=1` |
| 2024-08-01 | `d2ff174` | `ExamLessonDependParameterBuff` | 好調の100%分パラメータ上昇させ、好調を半分にする | `e_effect-exam_lesson_depend_parameter_buff-1000-0500-01` `effectValue1=1000,effectValue2=500,effectCount=1` |
| 2024-08-10 | `05469e1` | `ExamBlockDependExamReview` | 好印象の100%分元気増加 | `e_effect-exam_block_depend_exam_review-1000-01` `effectValue1=1000,effectCount=1` |
| 2024-08-22 | `2e0eccd` | `ExamLessonDependPlayCardCountSum` | パラメータ+20（レッスン中に使用したスキルカード1枚につき、パラメータ上昇量+10） | `e_effect-exam_lesson_depend_play_card_count_sum-0020-0010-01` `effectValue1=20,effectValue2=10,effectCount=1` |
| 2024-09-01 | `dbbca94` | `ExamBlockAddMultipleAggressive` | 元気+10（やる気効果を1.6倍適用） | `e_effect-exam_block_add_multiple_aggressive-0010-0600-01` `effectValue1=10,effectValue2=600,effectCount=1` |
| 2024-09-20 | `3421aa7` | `ExamAggressiveReduce` | やる気減少 / やる気減少1 | `e_effect-exam_aggressive_reduce-0001` `effectValue1=1` |
| 2024-09-20 | `3421aa7` | `ExamLessonBuffReduce` | 集中減少 / 集中減少1 | `e_effect-exam_lesson_buff_reduce-0001` `effectValue1=1` |
| 2024-09-20 | `3421aa7` | `ExamLessonValueMultipleDown` | パラメータ上昇量減少 （描述表无模板，游戏内显示回退文本）| `e_effect-exam_lesson_value_multiple_down-p_card_search-deck_all-all-0_0-g_effect-lesson_reduce-2` |
| 2024-09-20 | `3421aa7` | `ExamParameterBuffReduce` | 好調減少 / 好調減少1 | `e_effect-exam_parameter_buff_reduce-0001` `effectValue1=1` |
| 2024-09-20 | `3421aa7` | `ExamReviewReduce` | 好印象減少 / 好印象減少1 | `e_effect-exam_review_reduce-0001` `effectValue1=1` |
| 2024-10-08 | `6978853` | `ExamLessonDependStaminaConsumptionSum` | レッスン中に消費した体力の1000%分パラメータ上昇 | `e_effect-exam_lesson_depend_stamina_consumption_sum-10000-01` `effectValue1=10000,effectCount=1` |
| 2024-10-18 | `3e082a0` | `ExamReviewDependExamBlock` | 元気の100%分好印象増加させ、元気を0にする | `e_effect-exam_review_depend_exam_block-1000-1000-01` `effectValue1=1000,effectValue2=1000,effectCount=1` |
| 2024-10-25 | `8f45f8b` | `ExamAddGrowEffect` | 成長 （描述表无模板，游戏内显示回退文本）| `e_effect-exam_add_grow_effect-p_card_search-target_is_self-g_effect-lesson_add-8-g_effect-lesson_count_add-1-g_effect-cost_add-1` |
| 2024-10-25 | `8f45f8b` | `ExamStanceReset` | 指針解除 / 指針解除 | `e_effect-exam_stance_reset` |
| 2024-10-25 | `8f45f8b` | `StanceLock` | 指針固定 / 指針固定1ターン | `e_effect-stance_lock-01` `effectTurn=1` |
| 2024-10-28 | `6e35819` | `ExamLessonBuffDependParameterBuff` | 好調の100%分集中増加 | `e_effect-exam_lesson_buff_depend_parameter_buff-1000-01` `effectValue1=1000,effectCount=1` |
| 2024-11-16 | `cda4882` | `ExamForcePlayCardSearch` | 山札か捨札にあるスキルカードを1枚選択し、コストを消費せず使用 | `e_effect-exam_force_play_card_search-p_card_search-deck_grave-select-1_1` |
| 2024-11-16 | `cda4882` | `ExamFullPowerPointReduce` | 全力値減少 / 全力値減少1 | `e_effect-exam_full_power_point_reduce-0001` `effectValue1=1` |
| 2024-11-16 | `cda4882` | `ExamLessonFullPowerPoint` | パラメータ+10（累積全力値の100%分、パラメータ上昇量増加・2回） | `e_effect-exam_lesson_full_power_point-0010-1000-02` `effectValue1=10,effectValue2=1000,effectCount=2` |
| 2024-12-09 | `b83654c` | `ExamAggressiveValueMultiple` | やる気1.3倍 | `e_effect-exam_aggressive_value_multiple-0300` `effectValue1=300` |
| 2024-12-20 | `4bad77b` | `ExamDebuffRecover` | 低下状態回復 / 低下状態回復1 | `e_effect-exam_debuff_recover-0001` `effectValue1=1` |
| 2025-03-21 | `4ba70d5` | `ExamAggressiveAdditive` | やる気増加量増加 / やる気増加量増加+25%（3ターン） | `e_effect-exam_aggressive_additive-0250-03` `effectValue1=250,effectTurn=3` |
| 2025-03-21 | `4ba70d5` | `ExamConcentrationLessonMultipleAdditive` | 強気強化 / 強気強化+35% | `e_effect-exam_concentration_lesson_multiple_additive-0350-inf` `effectValue1=350,effectTurn=-1` |
| 2025-03-21 | `4ba70d5` | `ExamEnthusiasticAdditive` | 熱意追加 / 熱意追加+25（2ターン） | `e_effect-exam_enthusiastic_additive-0025-02` `effectValue1=25,effectTurn=2` |
| 2025-03-21 | `4ba70d5` | `ExamEnthusiasticMultiple` | 熱意増加 / 熱意増加+100%（3ターン） | `e_effect-exam_enthusiastic_multiple-1000-03` `effectValue1=1000,effectTurn=3` |
| 2025-03-21 | `4ba70d5` | `ExamFullPowerLessonMultipleAdditive` | 全力強化 / 全力強化+20%（4ターン） | `e_effect-exam_full_power_lesson_multiple_additive-0200-04` `effectValue1=200,effectTurn=4` |
| 2025-03-21 | `4ba70d5` | `ExamFullPowerPointAdditive` | 全力値増加量増加 / 全力値増加量増加+25%（1ターン） | `e_effect-exam_full_power_point_additive-0250-01` `effectValue1=250,effectTurn=1` |
| 2025-03-21 | `4ba70d5` | `ExamGrowEffectLessonAddAdditive` | パラメータ上昇値増加量増加 | `` |
| 2025-03-21 | `4ba70d5` | `ExamLessonBuffAdditive` | 集中増加量増加 / 集中増加量増加+100%（2ターン） | `e_effect-exam_lesson_buff_additive-1000-02` `effectValue1=1000,effectTurn=2` |
| 2025-03-21 | `4ba70d5` | `ExamLessonDependStamina` | 体力の1000%分パラメータ上昇 | `e_effect-exam_lesson_depend_stamina-10000-01` `effectValue1=10000,effectCount=1` |
| 2025-03-21 | `4ba70d5` | `ExamLessonValueMultipleDependReviewOrAggressive` | プライド / プライド（2ターン） | `e_effect-exam_lesson_value_multiple_depend_review_or_aggressive-02` `effectTurn=2` |
| 2025-03-21 | `4ba70d5` | `ExamOverPreservation` | のんびり / のんびりに変更 | `e_effect-exam_over_preservation` |
| 2025-03-21 | `4ba70d5` | `ExamParameterBuffAdditive` | 好調増加量増加 / 好調増加量増加+100%（3ターン） | `e_effect-exam_parameter_buff_additive-1000-03` `effectValue1=1000,effectTurn=3` |
| 2025-03-21 | `4ba70d5` | `ExamParameterBuffMultiplePerTurnReduce` | 絶好調減少 / 絶好調減少1 | `e_effect-exam_parameter_buff_multiple_per_turn_reduce-0001` `effectValue1=1` |
| 2025-03-21 | `4ba70d5` | `ExamReviewAdditive` | 好印象増加量増加 / 好印象増加量増加+100%（3ターン） | `e_effect-exam_review_additive-1000-03` `effectValue1=1000,effectTurn=3` |
| 2025-03-21 | `4ba70d5` | `ExamReviewDependExamCardPlayAggressive` | やる気の300%分好印象増加 | `e_effect-exam_review_depend_exam_card_play_aggressive-3000-01` `effectValue1=3000,effectCount=1` |
| 2025-03-21 | `4ba70d5` | `ExamReviewMultiple` | 好印象強化 / 好印象強化+100%（3ターン） | `e_effect-exam_review_multiple-1000-03` `effectValue1=1000,effectTurn=3` |
| 2025-03-24 | `0981177` | `ExamItemFireLimitAdd` | アイドル固有Pアイテムの発動回数+1 | `e_effect-exam_item_fire_limit_add-0001` `effectValue1=1` |
| 2025-04-21 | `a1d531d` | `ExamLessonDependAggressiveAndSearchCount` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-21 | `a1d531d` | `ExamLessonDependBlockAndSearchCount` | 除外にある私を超えて（翔）1枚につき、元気の20%分パラメータ上昇 | `e_effect-exam_lesson_depend_block_and_search_count-0200-01-p_card_search-lost-p_card-02-ido-3_190-all-0_0` `effectValue2=200,effectCount=1` |
| 2025-04-21 | `a1d531d` | `ExamLessonDependReviewAndSearchCount` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-22 | `3f61123` | `ExamAggressiveDependReview` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-22 | `3f61123` | `ExamAggressivePerSearchCount` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-22 | `3f61123` | `ExamBlockPerSearchCount` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-22 | `3f61123` | `ExamFullPowerPointPerSearchCount` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-22 | `3f61123` | `ExamLessonBuffPerSearchCount` | 除外にあるスキルカード2枚につき、集中+1 | `e_effect-exam_lesson_buff_per_search_count-0500-p_card_search-lost-all-0_0` `effectValue2=500` |
| 2025-04-22 | `3f61123` | `ExamMultipleConcentrationLesson` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-22 | `3f61123` | `ExamMultipleEnthusiasticLesson` | パラメータ+1（熱意効果を2倍適用） | `e_effect-exam_multiple_enthusiastic_lesson-0001-1000-01` `effectValue1=1,effectValue2=1000,effectCount=1` |
| 2025-04-22 | `3f61123` | `ExamMultipleFullPowerLesson` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-22 | `3f61123` | `ExamParameterBuffDependLessonBuff` | 集中の100%分好調増加させ、集中を半分にする | `e_effect-exam_parameter_buff_depend_lesson_buff-1000-0500-01` `effectValue1=1000,effectValue2=500,effectCount=1` |
| 2025-04-22 | `3f61123` | `ExamParameterBuffPerSearchCount` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2025-04-22 | `3f61123` | `ExamReviewPerSearchCount` | 山札か捨札にあるスキルカード1枚ごとに、好印象+1 | `e_effect-exam_review_per_search_count-1000-p_card_search-deck_grave` `effectValue2=1000` |
| 2025-12-26 | `6edc27e` | `ExamLessonDependBlockConsumptionSum` | レッスン中に消費した元気の100%分パラメータ上昇 | `e_effect-exam_lesson_depend_block_consumption_sum-1000-01` `effectValue1=1000,effectCount=1` |
| 2026-03-31 | `ff8795e` | `ExamBlockDependBlockConsumptionSum` | レッスン中に消費した元気の100%分元気増加 | `e_effect-exam_block_depend_block_consumption_sum-1000-01` `effectValue1=1000,effectCount=1` |
| 2026-03-31 | `ff8795e` | `ExamEnthusiasticTurnAdd` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2026-03-31 | `ff8795e` | `ExamReviewCountAdd` | 好印象追加発動 / 好印象追加発動+1（3ターン） | `e_effect-exam_review_count_add-0001-03` `effectValue1=1,effectTurn=3` |
| 2026-05-16 | `f0dac51` | `ExamForcePlayCardSearchWithCost` | 除外以外のスキルカードを1枚選択し、コストを消費して使用 | `e_effect-exam_force_play_card_search_with_cost-p_card_search-not_lost-select-1_1` |
| 2026-05-16 | `f0dac51` | `ExamStatusEnchantEncore` | 再演 / レッスン終了まで、スキルカード使用後、手札にある自然体の魅力が1枚以上の場合、自身を再使用（4回まで発動・ターン内1回まで）再演：スキルカード使用後、手札にある自然体の魅力が1枚以上の場合、自身を再使用（4回まで・ターン | `e_effect-exam_status_enchant_encore-0001-04-inf-enchant-p_card-01-ido-3_200-enc01` `effectValue1=1,effectCount=4,effectTurn=-1` |
| 2026-05-26 | `aba06dc` | `ExamAggressiveAdditiveFix` | やる気増加量追加 / やる気増加量追加+1（2ターン） | `e_effect-exam_aggressive_additive_fix-0001-02` `effectValue1=1,effectTurn=2` |
| 2026-05-26 | `aba06dc` | `ExamFullPowerPointAdditiveFix` | 全力値増加量追加 | `` |
| 2026-05-26 | `aba06dc` | `ExamLessonBuffAdditiveFix` | 集中増加量追加 / 集中増加量追加+1（4ターン） | `e_effect-exam_lesson_buff_additive_fix-0001-04` `effectValue1=1,effectTurn=4` |
| 2026-05-26 | `aba06dc` | `ExamParameterBuffAdditiveFix` | 好調増加量追加 | `` |
| 2026-05-26 | `aba06dc` | `ExamReviewAdditiveFix` | 好印象増加量追加 | `` |
| 2026-06-11 | `3d6c98c` | `ExamFullPowerPointDependFullPowerPointGetSum` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2026-06-11 | `3d6c98c` | `ExamLessonDependEnthusiasticGetSum` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |
| 2026-06-11 | `3d6c98c` | `ExamMoveGrowEffect` | （HEAD 中无示例行；仅在枚举/描述表出现） | `` |

#### `ProduceExamPhaseType`（`ProduceExamTrigger.phaseTypes[]`，触发相位）

共 30 个值，其中 18 个在初始 dump（2024-05-18）之后出现。

| 首次出现 | commit | 值 | 名称 / 示例说明（日文，取自 `produceDescriptions[*].text` 或 `ProduceDescription*`.name） | 示例行 |
|---|---|---|---|---|
| 2024-06-19 | `63cb6ba` | `ExamStaminaReduce` | 直接効果で体力が減少した時、の場合、使用可 | `e_trigger-exam_stamina_reduce` |
| 2024-06-24 | `9b0cc92` | `ExamCardMoveLost` | スキルカードが除外に移動した時、の場合、使用可 | `e_trigger-exam_card_move_lost-p_card_search-target` |
| 2024-06-24 | `9b0cc92` | `ExamPlayTurnCountInterval` | 好印象が6以上の場合、ターン内にスキルカードを2回使用するごとに、好印象が6以上の場合、使用可 | `e_trigger-exam_play_turn_count_interval-2-review_up-6-p_card_search-target` `phaseValues=[2]` |
| 2024-11-06 | `3d0028d` | `None` | 山札か捨札にあるトラブルカードが1枚以上の場合、山札か捨札にあるトラブルカードが1枚以上の場合、使用可 | `e_trigger-none-card_search_count_up-1-p_card_search-trouble-deck_grave` |
| 2024-11-16 | `cda4882` | `ExamCardMoveGrave` | 自身が捨て札に移動した時、の場合、使用可 | `e_trigger-exam_card_move_grave-p_card_search-target_is_self` |
| 2024-11-16 | `cda4882` | `ExamCardMoveHand` | 自身が手札に移動した時、の場合、使用可 | `e_trigger-exam_card_move_hand-p_card_search-target_is_self` |
| 2024-11-16 | `cda4882` | `ExamSearchCardPlay` | （描述表无模板，游戏内显示回退文本）| `e_trigger-exam_search_card_play-full_power_up-p_card_search-target_is_self-0_1` |
| 2024-11-16 | `cda4882` | `ExamStanceChangeConcentration` | 直接効果で強気になった時、このレッスン中の累計全力値が5以上の場合、このレッスン中の累計全力値が5以上の場合、使用可 | `e_trigger-exam_stance_change_concentration-full_power_point_get_sum_up-5` |
| 2024-11-16 | `cda4882` | `ExamStanceChangeCountInterval` | 直接効果で指針を2回変更するたび、の場合、使用可 | `e_trigger-exam_stance_change_count_interval-2` `phaseValues=[2]` |
| 2024-11-16 | `cda4882` | `ExamStanceChangeFullPower` | 全力になった時、強気になった回数が1回以上の場合、強気になった回数が1回以上の場合、使用可 | `e_trigger-exam_stance_change_full_power-concentration_change_count_up-1` |
| 2024-11-16 | `cda4882` | `ExamStanceChangePreservation` | 直接効果で温存になった時、の場合、使用可 | `e_trigger-exam_stance_change_preservation` |
| 2025-02-21 | `e65dc7e` | `ExamBuffConsume` | スキルカードコストで強化状態を消費した時、好調が3ターン以上の場合、好調が3ターン以上の場合、使用可 | `e_trigger-exam_buff_consume-parameter_buff_up-3` |
| 2025-03-24 | `0981177` | `ExamTurnSkip` | ターンスキップ時、絶好調状態の場合、絶好調状態の場合、使用可 | `e_trigger-exam_turn_skip-parameter_buff_multiple_per_turn_up-1` |
| 2025-06-09 | `28cf6f6` | `ExamEndTurnInterval` | 2ターンごとのターン終了時、除外にあるスキルカードが8枚以下の場合、除外にあるスキルカードが8枚以下の場合、使用可 | `e_trigger-exam_end_turn_interval-2-not-card_search_count_up-9-p_card_search-lost` `phaseValues=[2]` |
| 2025-08-12 | `f6ea7d0` | `ExamStanceChangeFromFullPower` | 全力を解除後、除外にあるでこれーとまじっくが1枚以上の場合、除外にあるでこれーとまじっくが1枚以上の場合、使用可 | `e_trigger-exam_stance_change_from_full_power-card_search_count_up-1-p_card_search-lost-p_card-03-ido-3_144` |
| 2026-02-19 | `374cf1a` | `ExamPlayCountIntervalAfter` | 好調が5ターン以上の場合、メンタルスキルカード使用後3回ごとに、好調が5ターン以上の場合、使用可 | `e_trigger-exam_play_count_interval_after-3-parameter_buff_up-5-p_card_search-mental_skill-target` `phaseValues=[3]` |
| 2026-03-09 | `8f2f3e2` | `ExamStanceChangeFromConcentration` | 直接効果で強気を解除後、全力の場合、全力の場合、使用可 | `e_trigger-exam_stance_change_from_concentration-full_power_up` |
| 2026-05-26 | `aba06dc` | `ExamAggressiveUpInterval` | 直接効果でやる気が5回増加時、の場合、使用可 | `e_trigger-exam_aggressive_up_interval-5-exam_card_play_aggressive` `phaseValues=[5]` |

#### `ProduceExamFieldStatusType`（`ProduceExamTrigger.fieldStatusTypes[]`，触发条件）

共 29 个值，其中 14 个在初始 dump（2024-05-18）之后出现。

| 首次出现 | commit | 值 | 名称 / 示例说明（日文，取自 `produceDescriptions[*].text` 或 `ProduceDescription*`.name） | 示例行 |
|---|---|---|---|---|
| 2024-06-24 | `9b0cc92` | `PlayCardLesson` | アクティブスキルカード使用時、直前にアクティブスキルカードを使用した状態の場合、直前にアクティブスキルカードを使用した状態の場合、使用可 | `e_trigger-exam_card_play-play_card_lesson-p_card_search-active_skill-playing-0_1` |
| 2024-06-24 | `9b0cc92` | `PlayCardSkill` | アクティブスキルカード使用時、直前にメンタルスキルカードを使用した状態の場合、直前にメンタルスキルカードを使用した状態の場合、使用可 | `e_trigger-exam_card_play-play_card_skill-p_card_search-active_skill-playing-0_1` |
| 2024-11-16 | `cda4882` | `ConcentrationChangeCountUp` | 【ダンスレッスン・ダンスターンのみ】ターン開始時、強気になった回数が3回以上の場合、強気になった回数が3回以上の場合、使用可 | `e_trigger-exam_start_turn-concentration_change_count_up-3-lesson_dance` `fieldStatusValues=[3]` |
| 2024-11-16 | `cda4882` | `ConcentrationUp` | 【ダンスレッスン・ダンスターンのみ】ターン開始後、強気の場合、強気の場合、使用可 | `e_trigger-start_play-concentration_up-lesson_dance` |
| 2024-11-16 | `cda4882` | `FullPowerChangeCountUp` | 全力になった時、全力になった回数が2回以上の場合、全力になった回数が2回以上の場合、使用可 | `e_trigger-exam_stance_change_full_power-full_power_change_count_up-2` `fieldStatusValues=[2]` |
| 2024-11-16 | `cda4882` | `FullPowerPointGetSumUp` | 直接効果で強気になった時、このレッスン中の累計全力値が5以上の場合、このレッスン中の累計全力値が5以上の場合、使用可 | `e_trigger-exam_stance_change_concentration-full_power_point_get_sum_up-5` `fieldStatusValues=[5]` |
| 2024-11-16 | `cda4882` | `FullPowerPointUp` | アイドル固有スキルカード使用後、全力値が9以下の場合、全力値が9以下の場合、使用可 | `e_trigger-exam_card_play_after-not-full_power_point_up-10-p_card_search-playing-idol-unique-0_1` `fieldStatusValues=[10]` |
| 2024-11-16 | `cda4882` | `FullPowerUp` | （描述表无模板，游戏内显示回退文本）| `e_trigger-exam_search_card_play-full_power_up-p_card_search-target_is_self-0_1` |
| 2024-11-16 | `cda4882` | `NoStance` | いずれかの指針の場合、強気効果のスキルカード使用後3回ごとに、いずれかの指針の場合、使用可 | `e_trigger-exam_play_count_interval_after-3-not-no_stance-p_card_search-target-effect_group-visible-exam_concentration-000` |
| 2024-11-16 | `cda4882` | `PreservationChangeCountUp` | 【ビジュアルレッスン・ビジュアルターンのみ】ターン開始時、温存になった回数が4回以上の場合、温存になった回数が4回以上の場合、使用可 | `e_trigger-exam_start_turn-preservation_change_count_up-4-lesson_visual` `fieldStatusValues=[4]` |
| 2024-11-16 | `cda4882` | `PreservationUp` | 【ビジュアルレッスン・ビジュアルターンのみ】ターン開始後、温存の場合、温存の場合、使用可 | `e_trigger-start_play-preservation_up-lesson_visual` |
| 2024-12-20 | `4de551b` | `StanceChangeCountUp` | 【ボーカルレッスン・ボーカルターンのみ】ターン開始時、指針を変更した回数が4回以上の場合、指針を変更した回数が4回以上の場合、使用可 | `e_trigger-exam_start_turn-stance_change_count_up-4-lesson_vocal` `fieldStatusValues=[4]` |
| 2025-01-09 | `8c8cd91` | `CardSearchCountUp` | 【ビジュアルレッスン・ビジュアルターンのみ】ターン開始時、除外にあるスキルカードが7枚以上の場合、除外にあるスキルカードが7枚以上の場合、使用可 | `e_trigger-exam_start_turn-card_search_count_up-7-p_card_search-lost-lesson_visual` `fieldStatusValues=[7]` |
| 2025-08-22 | `0fdb17b` | `ParameterBuffMultiplePerTurnUp` | スキルカード使用後、絶好調が5ターン以上の場合、絶好調が5ターン以上の場合、使用可 | `e_trigger-exam_card_play_after-parameter_buff_multiple_per_turn_up-5-p_card_search-target-0_1` `fieldStatusValues=[5]` |

#### `ProduceCardGrowEffectType`（`ProduceCardGrowEffect.effectType`，卡牌成长/カスタマイズ）

共 54 个值，其中 53 个在初始 dump（2024-05-18）之后出现。整个家族在 2024-10-25（アノマリー/成長 上线）才出现。

| 首次出现 | commit | 值 | 名称 / 示例说明（日文，取自 `produceDescriptions[*].text` 或 `ProduceDescription*`.name） | 示例行 |
|---|---|---|---|---|
| 2024-10-25 | `4eeeeea` | `AggressiveAdd` | やる気値増加 | `g_effect-aggressive_add-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `AggressiveReduce` | やる気値減少 | `` |
| 2024-10-25 | `8f45f8b` | `BlockAdd` | 元気値増加 | `g_effect-block_add-1` `value=1` |
| 2024-10-25 | `8f45f8b` | `BlockReduce` | 元気値減少 | `g_effect-block_reduce-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `CardDrawAdd` | ドロー枚数増加 | `` |
| 2024-10-25 | `4eeeeea` | `CardDrawReduce` | ドロー枚数減少 | `` |
| 2024-10-25 | `4eeeeea` | `CardStatusEnchantChange` | 成長変更 | `g_effect-card_status_enchant_change-card_enchant-e_trigger-exam_card_play_after-p_card_search-target-effect_group-visible-exam_concentration-000-0_1-2-g_effect-lesson_add-15-g_effect-lesson_count_add-1` |
| 2024-10-25 | `8f45f8b` | `CostAdd` | コスト値増加 | `g_effect-cost_add-1` `value=1` |
| 2024-10-25 | `8f45f8b` | `CostBuffAdd` | 強化状態コスト値増加 | `` |
| 2024-10-25 | `8f45f8b` | `CostBuffReduce` | 強化状態コスト値減少 | `` |
| 2024-10-25 | `8f45f8b` | `CostPenetrateAdd` | 体力消費コスト値増加 | `g_effect-cost_penetrate_add-1` `value=1` |
| 2024-10-25 | `8f45f8b` | `CostPenetrateReduce` | 体力消費コスト値減少 | `g_effect-cost_penetrate_reduce-1` `value=1` |
| 2024-10-25 | `8f45f8b` | `CostReduce` | コスト値減少 | `g_effect-cost_reduce-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `EffectAdd` | 効果追加 | `g_effect-effect_add-e_effect-exam_add_grow_effect-p_card_search-deck_all-all-0_0-g_effect-lesson_add-1` |
| 2024-10-25 | `4eeeeea` | `EffectChange` | 効果置換 | `g_effect-effect_change-e_effect-exam_block_per_use_card_count-0002-0008-e_effect-exam_status_enchant-02-inf-enchant-p_card-02-ido-3_067-enc01` |
| 2024-10-25 | `4eeeeea` | `EffectDelete` | 効果削除 | `` |
| 2024-10-25 | `8f45f8b` | `FullPowerPointAdd` | 全力値増加 | `g_effect-full_power_point_add-1` `value=1` |
| 2024-10-25 | `8f45f8b` | `FullPowerPointReduce` | 全力値減少 | `g_effect-full_power_point_reduce-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `InitialAdd` | 開始時手札効果付与 | `g_effect-initial_add` |
| 2024-10-25 | `8f45f8b` | `LessonAdd` | パラメータ値増加 | `g_effect-lesson_add-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `LessonBuffAdd` | 集中値増加 | `g_effect-lesson_buff_add-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `LessonBuffReduce` | 集中値減少 | `` |
| 2024-10-25 | `8f45f8b` | `LessonCountAdd` | パラメータ上昇回数増加 | `g_effect-lesson_count_add-1` `value=1` |
| 2024-10-25 | `8f45f8b` | `LessonCountReduce` | パラメータ上昇回数減少 | `g_effect-lesson_count_reduce-1` `value=1` |
| 2024-10-25 | `8f45f8b` | `LessonReduce` | パラメータ値減少 | `g_effect-lesson_reduce-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `ParameterBuffMultiplePerTurnAdd` | 絶好調値増加 | `g_effect-parameter_buff_multiple_per_turn_add-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `ParameterBuffMultiplePerTurnReduce` | 絶好調値減少 | `` |
| 2024-10-25 | `4eeeeea` | `ParameterBuffTurnAdd` | 好調値増加 | `g_effect-parameter_buff_turn_add-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `ParameterBuffTurnReduce` | 好調値減少 | `` |
| 2024-10-25 | `4eeeeea` | `PlayEffectTriggerChange` | 効果発動条件を置換 | `g_effect-play_effect_trigger_change-e_trigger-exam_card_play-card_play_aggressive_up-3` |
| 2024-10-25 | `4eeeeea` | `PlayMovePositionTypeChange` | 使用後移動先変更 | `g_effect-play_move_position_type_change-grave` |
| 2024-10-25 | `4eeeeea` | `PlayTriggerChange` | 使用可能条件を置換 | `g_effect-play_trigger_change-e_trigger-none-block_up-30-e_trigger-none-block_up-15` |
| 2024-10-25 | `4eeeeea` | `ReviewAdd` | 好印象値増加 | `g_effect-review_add-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `ReviewReduce` | 好印象値減少 | `` |
| 2024-10-25 | `4eeeeea` | `StaminaConsumptionAddTurnAdd` | 消費体力増加値減少 | `` |
| 2024-10-25 | `4eeeeea` | `StaminaConsumptionAddTurnReduce` | 消費体力増加値増加 | `` |
| 2024-10-25 | `4eeeeea` | `StaminaConsumptionDownTurnAdd` | 消費体力減少値増加 | `g_effect-stamina_consumption_down_turn_add-1` `value=1` |
| 2024-10-25 | `4eeeeea` | `StaminaConsumptionDownTurnReduce` | 消費体力減少値減少 | `` |
| 2024-12-20 | `4bad77b` | `CostAggressiveAdd` | やる気コスト値増加 | `g_effect-cost_aggressive_add-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostAggressiveReduce` | やる気コスト値減少 | `g_effect-cost_aggressive_reduce-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostFullPowerPointAdd` | 全力値コスト値増加 | `g_effect-cost_full_power_point_add-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostFullPowerPointReduce` | 全力値コスト値減少 | `g_effect-cost_full_power_point_reduce-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostLessonBuffAdd` | 集中コスト値増加 | `g_effect-cost_lesson_buff_add-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostLessonBuffReduce` | 集中コスト値減少 | `g_effect-cost_lesson_buff_reduce-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostParameterBuffAdd` | 好調コスト値増加 | `g_effect-cost_parameter_buff_add-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostParameterBuffReduce` | 好調コスト値減少 | `g_effect-cost_parameter_buff_reduce-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostReviewAdd` | 好印象コスト値増加 | `g_effect-cost_review_add-1` `value=1` |
| 2024-12-20 | `4bad77b` | `CostReviewReduce` | 好印象コスト値減少 | `g_effect-cost_review_reduce-1` `value=1` |
| 2024-12-20 | `4bad77b` | `LessonDependBlockAdd` | 元気分パラメータ倍率増加 | `g_effect-lesson_depend_block_add-100` `value=100` |
| 2024-12-20 | `4bad77b` | `LessonDependExamCardPlayAggressiveAdd` | やる気分パラメータ倍率増加 | `g_effect-lesson_depend_exam_card_play_aggressive_add-1000` `value=1000` |
| 2024-12-20 | `4bad77b` | `LessonDependExamReviewAdd` | 好印象分パラメータ倍率増加 | `g_effect-lesson_depend_exam_review_add-1000` `value=1000` |
| 2025-03-21 | `4ba70d5` | `CostParameterBuffMultiplePerTurnAdd` | 絶好調コスト値増加 | `` |
| 2025-03-21 | `4ba70d5` | `CostParameterBuffMultiplePerTurnReduce` | 絶好調コスト値減少 | `g_effect-cost_parameter_buff_multiple_per_turn_reduce-1` `value=1` |

#### `ProduceEffectType`（`ProduceEffect.produceEffectType`，培育外循环效果）

共 103 个值，其中 32 个在初始 dump（2024-05-18）之后出现。

| 首次出现 | commit | 值 | 名称 / 示例说明（日文，取自 `produceDescriptions[*].text` 或 `ProduceDescription*`.name） | 示例行 |
|---|---|---|---|---|
| 2024-09-20 | `3421aa7` | `AuditionNpcEnhance` | ライバルのスコア | `p_effect-audition_npc_enhance-0020_0020` |
| 2024-09-20 | `3421aa7` | `BeforeAuditionRefreshStaminaDown` | 試験前体力回復量減少 | `p_effect-before_audition_refresh_stamina_down-0250_0250` |
| 2024-09-20 | `3421aa7` | `BeforeAuditionRefreshStaminaUp` | 試験前体力回復量増加 | `p_effect-before_audition_refresh_stamina_up-0050_0050` |
| 2024-09-20 | `3421aa7` | `EventActivityProducePointDown` | お出かけの消費Pポイント減少 | `p_effect-event_activity_produce_point_down-0500_0500` |
| 2024-09-20 | `3421aa7` | `EventActivityProducePointUp` | お出かけの消費Pポイント増加 | `p_effect-event_activity_produce_point_up-0250_0250` |
| 2024-09-20 | `3421aa7` | `EventSchoolStaminaDown` | 授業の消費体力減少 | `p_effect-event_school_stamina_down-0500_0500` |
| 2024-09-20 | `3421aa7` | `EventSchoolStaminaUp` | 授業の消費体力増加 | `p_effect-event_school_stamina_up-0100_0100` |
| 2024-09-20 | `3421aa7` | `ExamTurnDown` | ターン数減少 | `p_effect-exam_turn_down-0001_0001` |
| 2024-09-20 | `3421aa7` | `ExamTurnUp` | ターン数増加 | `` |
| 2024-09-20 | `3421aa7` | `ShopPriceUpMultiple` | 相談の全項目を割増 | `p_effect-shop_price_up_multiple-0050_0050` |
| 2024-09-20 | `3421aa7` | `ShopProduceCardDeletePriceUpMultiple` | 相談のスキルカード削除を割増 | `` |
| 2024-09-20 | `3421aa7` | `ShopProduceCardPriceUpMultiple` | 相談のスキルカードを割増 | `` |
| 2024-09-20 | `3421aa7` | `ShopProduceCardUpgradePriceUpMultiple` | 相談のスキルカード強化を割増 | `` |
| 2024-09-20 | `3421aa7` | `ShopProduceDrinkPriceUpMultiple` | 相談のPドリンクを割増 | `` |
| 2024-12-26 | `cb5768d` | `AuditionVoteCountUp` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-audition_vote_count_up-0050_0050` |
| 2024-12-26 | `cb5768d` | `EventBusinessVoteCountUp` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-event_business_vote_count_up-0050_0050` |
| 2024-12-26 | `cb5768d` | `ProduceCardExcludeCountUp` | スキルカード除去 | `p_effect-produce_card_exclude_count_up-0001_0001` |
| 2024-12-26 | `cb5768d` | `VoteCountAddition` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-vote_count_addition-0800_0800` |
| 2025-03-21 | `4ba70d5` | `HighScoreGoldAddition` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-high_score_gold_addition-0020_0020` |
| 2025-05-16 | `be4e3b4` | `IdolCardProduceCardCustomizeEnable` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-idol_card_produce_card_customize_enable` |
| 2025-06-19 | `15272c3` | `ShopRerollCountUp` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-shop_reroll_count_up-0001_0001` |
| 2025-12-26 | `6edc27e` | `ExamPermanentAuditionStatusEnchant` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-exam_permanent_audition_status_enchant-enchant-customize_pitem-01-04-3-001_00-04-2-001_01-01-1-001_00-04-4-001-enc01` |
| 2025-12-26 | `6edc27e` | `ExamPermanentLessonStatusEnchant` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-exam_permanent_lesson_status_enchant-enchant-pitem_00-1-048-challenge-enc01` |
| 2026-03-31 | `ff8795e` | `AuditionNpcWeaken` | ライバルのスコア | `p_effect-audition_npc_weaken-0500_0500` |
| 2026-05-16 | `f0dac51` | `CustomizeProduceCardProducePointDownMultiple` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-customize_produce_card_produce_point_down_multiple-0200_0200` |
| 2026-05-16 | `f0dac51` | `ParameterLimitUp` | パラメータ上限増加 | `p_effect-parameter_limit_up-0050_0050` |
| 2026-05-16 | `f0dac51` | `ProduceCardChangeSelect` | セレクトチェンジ | `p_effect-produce_card_change_select-0001_0001-p_rd-produce_007-customizeitem-p_card_search-active_skill-mental_skill-deck_all-select-01_01` |
| 2026-05-16 | `f0dac51` | `ProduceCustomizeItemUpgrade` | （HEAD 中无示例行；仅在枚举/描述表出现） | `p_effect-produce_customize_item_upgrade-select-01_01` |
| 2026-05-16 | `f0dac51` | `ProduceDrinkPossessLimitUp` | Pドリンク所持上限増加 | `p_effect-produce_drink_possess_limit_up-0001_0001` |
| 2026-05-16 | `f0dac51` | `ShopProduceCardPriceDiscountMultiplePermanent` | 相談のスキルカードを割引 | `p_effect-shop_produce_card_price_discount_multiple_permanent-0050_0050-p_card_search-deck_all` |
| 2026-05-16 | `f0dac51` | `StarAddition` | スター性獲得 | `p_effect-star_addition-0010_0010` |
| 2026-05-16 | `f0dac51` | `StarPermilUp` | スター性獲得量増加 | `p_effect-star_permil_up-0050_0050` |

#### `ProducePhaseType`（`ProduceTrigger.phaseType`，培育相位）


**`ProducePhaseType`**：共 29 个值，初始之后新增 15 个。

- 2024-07-22 `4202981`：`BuyShopItemProduceDrink`
- 2024-12-26 `cb5768d`：`EndBeforeAuditionRefresh`, `StartAuditionFinal`, `StartAuditionMid1`, `StartAuditionMid2`, `StartCustomize`
- 2025-05-01 `117c736`：`ChangeProduceCard`
- 2025-05-19 `676438a`：`EndPresent`, `EndShop`, `EndStepEventBusiness`
- 2025-05-29 `87149c3`：`GetProduceDrink`
- 2025-06-09 `28cf6f6`：`CustomizeProduceCard`
- 2025-09-17 `ac884f1`：`GetProduceItem`
- 2025-12-26 `6edc27e`：`StartAudition`
- 2026-07-31 `6271031`：`BuyShopItemProduceCard`

#### `ProduceStepType`（步骤类型；出现在 `ProduceStepAuditionDifficulty.stepType`、`ProduceStepTransition` 等）


**`ProduceStepType`**：共 34 个值，初始之后新增 21 个。

- 2024-12-26 `cb5768d`：`AuditionMid2`, `Business`, `FanPresent`, `SelfLessonDanceNormal`, `SelfLessonDanceSp`, `SelfLessonVisualNormal`, `SelfLessonVisualSp`, `SelfLessonVocalNormal`, `SelfLessonVocalSp`
- 2026-05-16 `f0dac51`：`OpenLessonDanceNormal`, `OpenLessonDanceNormalStar`, `OpenLessonDanceSp`, `OpenLessonDanceSpStar`, `OpenLessonVisualNormal`, `OpenLessonVisualNormalStar`, `OpenLessonVisualSp`, `OpenLessonVisualSpStar`, `OpenLessonVocalNormal`, `OpenLessonVocalNormalStar`, `OpenLessonVocalSp`, `OpenLessonVocalSpStar`

#### `ProduceType` / `ProduceSplitType`（剧本族 / 分段）


**`ProduceType`**：共 4 个值，初始之后新增 2 个。

- 2024-12-26 `cb5768d`：`NextIdolAudition`
- 2026-05-16 `f0dac51`：`HatsuboshiIdolFestival`

**`ProduceSplitType`**：共 3 个值，初始之后新增 2 个。

- 2026-05-16 `f0dac51`：`Final`, `Selection`

#### `ProduceCardCategory` / `ProduceCardRarity` / `ProduceCardMovePositionType` / `ProduceCardPositionType` / `ProduceCardMoveEffectTriggerType` / `ProducePlanType` / `ExamCostType`


**`ProduceCardCategory`**：共 4 个值，初始之后新增 0 个。

- （无新增）

**`ProduceCardRarity`**：共 5 个值，初始之后新增 1 个。

- 2025-12-26 `6edc27e`：`Legend`

**`ProduceCardMovePositionType`**：共 8 个值，初始之后新增 2 个。

- 2024-06-24 `9b0cc92`：`DeckLast`
- 2024-11-16 `cda4882`：`Hold`

**`ProduceCardPositionType`**：共 10 个值，初始之后新增 4 个。

- 2024-06-24 `9b0cc92`：`Lost`
- 2024-11-16 `cda4882`：`DeckGrave`, `Hold`
- 2025-12-26 `6edc27e`：`NotLost`

**`ProduceCardMoveEffectTriggerType`**：共 3 个值，初始之后新增 2 个。

- 2025-12-26 `6edc27e`：`Hand`
- 2026-03-31 `ff8795e`：`Hold`

**`ProducePlanType`**：共 5 个值，初始之后新增 1 个。

- 2024-10-25 `8f45f8b`：`Plan3`

**`ExamCostType`**：共 7 个值，初始之后新增 2 个。

- 2024-11-16 `cda4882`：`ExamFullPowerPoint`
- 2026-03-09 `8f2f3e2`：`ExamParameterBuffMultiplePerTurn`

**`ProducePickRangeType`**：共 4 个值，初始之后新增 0 个。

- （无新增）

**`ProducePickCountType`**：共 2 个值，初始之后新增 1 个。

- 2026-05-16 `f0dac51`：`Shortage`

#### `ProduceStepAuditionType` / `ProduceStepBusinessType` / `ProduceStepLessonType`


**`ProduceStepAuditionType`**：共 11 个值，初始之后新增 10 个。

- 2024-12-26 `cb5768d`：`FinalEasy`, `FinalHard`, `FinalNormal`, `FinalVeryHard`, `Mid1Easy`, `Mid1Hard`, `Mid1Normal`, `Mid2Easy`, `Mid2Hard`, `Mid2Normal`

**`ProduceStepBusinessType`**：共 4 个值，初始之后新增 3 个。

- 2025-08-22 `0fdb17b`：`ProduceCard`, `ProduceDrink`, `ProducePoint`

**`ProduceStepLessonType`**：共 5 个值，初始之后新增 1 个。

- 2024-09-20 `3421aa7`：`LessonSp`

#### `ResultGrade` / `ResultGradeType` / `ProducerRankingGrade`


**`ResultGrade`**：共 20 个值，初始之后新增 6 个。

- 2025-05-19 `676438a`：`Sss`, `SssPlus`
- 2025-12-26 `6edc27e`：`Ssss`
- 2026-05-16 `f0dac51`：`SsssPlus`, `Sssss`, `SssssPlus`

**`ResultGradeType`**：共 6 个值，初始之后新增 2 个。

- 2024-12-26 `cb5768d`：`ProduceVoteCount`
- 2026-05-16 `f0dac51`：`ProduceStar`

**`ProducerRankingGrade`**：共 6 个值，初始之后新增 6 个。

- 2025-09-29 `26f0628`：`Bronze`, `Gold`, `Normal`, `Rainbow`, `RainbowPlus`, `Silver`

#### `ProduceExamAutoEvaluationType` / `ExamPlayType` / `ExamStatusEffectType`（官方 AutoPlay 与 コンテスト）


**`ProduceExamAutoEvaluationType`**：共 53 个值，初始之后新增 35 个。

- 2024-06-24 `9b0cc92`：`ExamExtraTurn`
- 2024-10-25 `4eeeeea`：`ExamConcentration`, `ExamConcentrationCount`, `ExamFullPower`, `ExamFullPowerCount`, `ExamFullPowerPointTotal`, `ExamPreservation`, `ExamPreservationCount`, `HoldCount`
- 2024-12-20 `4bad77b`：`DrawCardCount`, `ExamAntiDebuff`, `RemainTurn`
- 2025-03-21 `4ba70d5`：`ExamAggressiveAdditive`, `ExamBlockRestriction`, `ExamConcentrationLessonMultipleAdditive`, `ExamEnthusiasticAdditive`, `ExamEnthusiasticMultiple`, `ExamFullPowerLessonMultipleAdditive`, `ExamFullPowerPointAdditive`, `ExamGrowEffectLessonAddAdditive`, `ExamLessonBuffAdditive`, `ExamLessonValueMultiple`, `ExamLessonValueMultipleDependReviewOrAggressive`, `ExamParameterBuffAdditive`, `ExamReviewAdditive`, `ExamReviewMultiple`, `StanceLock`
- 2026-03-31 `ff8795e`：`ExamReviewCountAdd`, `StanceLockConcentration`, `StanceLockFullPower`, `StanceLockPreservation`
- 2026-05-12 `c344b6e`：`ExamBuffConsumptionAdd`, `ExamBuffConsumptionDown`, `ExamParameterBuffTurnEndReduceLock`, `ExamReviewTurnEndReduceLock`

**`ExamPlayType`**：共 5 个值，初始之后新增 1 个。

- 2025-11-14 `4e3a93c`：`AutoPlayCompetition`

**`ExamStatusEffectType`**：共 6 个值，初始之后新增 6 个。

- 2025-11-14 `4e3a93c`：`Aggressive`, `FullPowerPoint`, `LessonBuff`, `ParameterBuff`, `ParameterBuffMultiplePerTurn`, `Review`

#### `ProduceEventCharacterType` / `ProduceLiveType` / `ProduceResourceType` / `ProducerLevelUnlockType` / `IdolCardLevelLimitEffectType`


**`ProduceEventCharacterType`**：共 15 个值，初始之后新增 14 个。

- 2025-03-21 `4ba70d5`：`AfterAuditionFinal`, `AfterAuditionMid1`, `AfterAuditionMid2`, `AfterStep1`, `AfterStep2`, `BeforeAuditionFinal`, `BeforeAuditionMid1`, `BeforeAuditionMid2`, `Ending`, `Failure`, `Opening`
- 2026-05-16 `f0dac51`：`AfterStepBeforeAuditionFinal`, `AfterStepBeforeAuditionMid1`, `AfterStepBeforeAuditionMid2`

**`ProduceLiveType`**：共 7 个值，初始之后新增 1 个。

- 2026-05-12 `c344b6e`：`E`

**`ProduceResourceType`**：共 6 个值，初始之后新增 1 个。

- 2026-05-16 `f0dac51`：`ProduceCustomizeItem`

**`ProducerLevelUnlockType`**：共 7 个值，初始之后新增 2 个。

- 2025-03-21 `4ba70d5`：`ProduceCardExcludeCount`
- 2025-12-26 `6edc27e`：`ProduceCardConversion`

**`IdolCardLevelLimitEffectType`**：共 5 个值，初始之后新增 1 个。

- 2026-05-16 `f0dac51`：`SecondProduceCardUpgrade`

#### B.1 小结：枚举增长的节律

| 日期 | commit | 版本/内容 | 新枚举值（试验内） |
|---|---|---|---|
| 2024-06～10 | 多个 | 每期新 SSR 偶像卡带 1～2 个新 `ExamLessonDepend*` / `Exam*Reduce` 效果 | `ExamBlockPerUseCardCount`, `ExamLessonDependParameterBuff`, `ExamLessonDependPlayCardCountSum`, … |
| 2024-10-25 | `4eeeeea`/`8f45f8b` | 1.5.0 前置：**アノマリー**（Plan3）+ **成長（GrowEffect）** | `ProducePlanType_Plan3`, 整个 `ProduceCardGrowEffectType`(38), `ExamAddGrowEffect`, `StanceLock`, `ExamStanceReset` |
| 2024-11-16 | `cda4882` | 1.5.0：アノマリー正式上线（強気/温存/全力 指針） | `ExamCostType_ExamFullPowerPoint`, `ProduceCardMovePositionType_Hold`, 8 个 `ExamStanceChange*` 相位, 9 个 `FullPower*/Preservation*/Concentration*` 触发条件, `ExamForcePlayCardSearch`, `ExamLessonFullPowerPoint` |
| 2024-12-20/26 | `4bad77b`/`cb5768d` | 1.6.1/1.7.0：**カスタマイズ**、**N.I.A**（Mid2 试验、Business、SelfLesson、FanPresent、VoteCount） | `ProduceType_NextIdolAudition`, `ProduceStepType_AuditionMid2/Business/SelfLesson*/FanPresent`, 10 个 `ProduceStepAuditionType_*Easy/Normal/Hard/VeryHard`, `ResultGradeType_ProduceVoteCount`, `ExamDescriptionType_Customize*`, `ProducePhaseType_StartCustomize` |
| 2025-03-21 | `4ba70d5` | 1.10.x：**のんびり（OverPreservation）**、熱意、プライド 等 17 个新效果（アノマリー扩展 + ハイスコア活动） | `ExamOverPreservation`, `ExamEnthusiastic*`, `Exam*Additive`, `ExamLessonValueMultipleDependReviewOrAggressive`, `ProduceHighScoreEventType_Rush` |
| 2025-04-21/22 | `a1d531d`/`3f61123` | 1.11.0：`*PerSearchCount` / `*AndSearchCount` 系（按区域卡数计数） | 12 个 |
| 2025-05-16/19 | `be4e3b4`/`676438a` | 2.0.0：**N.I.A マスター**、SSS/SSS+ 评级 | `ResultGrade_Sss/SssPlus`, `ProducePhaseType_EndPresent/EndShop/EndStepEventBusiness` |
| 2025-08-18/22 | `e55755f`/`0fdb17b` | 2.3.0：`ProduceStepBusinessType`，`ParameterBuffMultiplePerTurnUp` 触发条件 | |
| 2025-09-29 | `26f0628` | 2.4.0：プロデューサーランキング / シーズン制 | `ProducerRankingGrade_*` |
| 2025-10-21 | `d1637c4` | 2.5.0 前置：**コンバージョン**、`ProduceLegendProduceCard`/`ProduceInitialDeck` 表（空）、`ProduceSelectScreenOrderType` | |
| 2025-11-14 | `4e3a93c` | 2.6.0：**コンテスト改版（Competition）**、`ExamPlayType_AutoPlayCompetition`、`ExamStatusEffectType` | |
| 2025-12-26 | `6edc27e` | 2.7.0：**初・レジェンド**（`produce-006`）、`ProduceCardRarity_Legend`、`ProduceCardPositionType_NotLost`、`ExamPermanent*StatusEnchant`、SSSS 评级 | `ExamLessonDependBlockConsumptionSum`, `ProduceCardMoveEffectTriggerType_Hand` |
| 2026-02-19～03-31 | `374cf1a`/`8f2f3e2`/`ff8795e` | 2.9～2.10：`pickCountType`、`chainProduceExamEffectIds`、`ExamCostType_ExamParameterBuffMultiplePerTurn`（绝好调作为费用）、`ExamReviewCountAdd`、`ExamEnthusiasticTurnAdd`、Easy 模式 | |
| 2026-05-12/16 | `c344b6e`/`f0dac51` | 3.0.x：**H.I.F**（`ProduceType_HatsuboshiIdolFestival`，`ProduceSplitType_Selection/Final`，`OpenLesson*Star` 步骤，`ResultGradeType_ProduceStar`，SSSS+/SSSSS/SSSSS+）、**プリマステラ**、**成長パネル**、**ユニット**、`ExamStatusEnchantEncore`（再演）、`ExamForcePlayCardSearchWithCost`、`ExamBuffConsumption*` | |
| 2026-05-26～06-11 | `aba06dc`/`3d6c98c` | 3.0.3/3.1.0：`Exam*AdditiveFix` 5 个、`ExamAggressiveUpInterval` 相位、`ExamMoveGrowEffect`、`Exam*GetSum` | |
| 2026-07～09 | | 没有新的试验内枚举值；只有 `ProducePhaseType_BuyShopItemProduceCard`（07-31） | |

结论：**平均每 1～2 个月出现一批新的 `ProduceExamEffectType`（2 年内 +67）**，大版本一次加 10～20 个；触发相位 `ProduceExamPhaseType`（+18）和触发条件 `ProduceExamFieldStatusType`（+15）也在持续增长。任何把效果类型写死为 switch/enum 的引擎在每个大版本后都会遇到未知值。

### B.2 新表时间线

初始 dump 有 195 张表；之后新增 100 张、删除 9 张。与 produce 模拟相关的新增表（其余为 Photo/Gasha/Home/Tour/Gvg 等 UI 与活动表，列表见 `git log --diff-filter=A --name-only`）：

| 首次出现 | commit | 表 | 说明（字段来自 HEAD 样本） |
|---|---|---|---|
| 2024-07-19 | `87cc008` | `ProduceExamAutoCardSelectEvaluation` | 官方 AutoPlay 的「选卡奖励」权重（`examEffectType, remainingTerm, evaluationType, evaluation`），Vibbit 逆向的 AI 表之一 |
| 2024-08-29 | `5107190` | `ProduceChallengeCharacter`, `ProduceChallengeSlot`, `ProduceItemChallengeGroup` | 「チャレンジPアイテム」槽位：`ProduceChallengeSlot(produceId, number) → ProduceItemChallengeGroup(produceItemId, lessonLimitUpScore, auditionParameterGrowthRatePermil)`，マスター难度的附加规则 |
| 2024-10-25 | `4eeeeea` | `ProduceExamAutoGrowEffectEvaluation` | AutoPlay 对「成長」效果的权重（アノマリー前置） |
| 2024-12-20 | `4bad77b` | `ProduceCardCustomize`, `ProduceCardCustomizeRarityEvaluation` | **カスタマイズ**：`ProduceCard.produceCardCustomizeIds[]` → `ProduceCardCustomize(customizeCount, produceCardGrowEffectIds[], producePoint, overwriteProduceCardGrowEffectType)`；稀有度→评价值 |
| 2024-12-20 | `4bad77b` | `ProduceDescription*`（9 张）, `ProduceCharacter`, `ProduceCharacterAdv`, `ProduceStoryGroup`, `ProduceGroupLiveCommon`, `ProduceStepSelfLesson(+Motion)`, `ProduceStepAuditionCharacter`, `ProduceStepFanPresentMotion`, `ForceAppVersion`, `ProduceExamAutoPlayCardEvaluation` | 描述模板体系重构；N.I.A 的自习（`ProduceStepSelfLesson: progressLevel, stamina, parameter`）、ファンプレゼント、试验对手角色（`ProduceStepAuditionCharacter: successNextIdolAuditionRank/failureNextIdolAuditionRank`）；AutoPlay 每张卡的固定权重表 |
| 2025-04-21 | `264c0c7` | `ProduceGrade`, `ProduceGuide*`（4 张） | **评级阈值改为按 `produceGroupId`**（`ProduceGrade(produceGroupId, grade, threshold)`），取代全局 `ResultGradePattern`；新手推荐牌组 |
| 2025-05-16 | `be4e3b4` | `ProduceCardPool`, `ProduceNextIdolAuditionMasterRankingSeason`, `SupportCardProduceSkillFilter` | 随机卡池（`produceCardRatios[{id, upgradeCount, ratio}]`，供 `ExamCardCreateSearch`）；NIA マスター ランキング赛季 |
| 2025-08-18 | `e55755f` | `ResearchMemoryRerollCost` | リサーチ（メモリー再抽）费用表 |
| 2025-09-29 | `26f0628` | `ProduceSeason`, `ProduceSeasonZeroGrade`, `ProducerRanking*`（5 张）, `Badge` | プロデューサーランキング：赛季（`ProduceSeason: startTime/endTime/fixRankTime`，シーズン0 = 2024-05-16～2025-09-29）、季前旧评级阈值快照 |
| 2025-10-21 | `d1637c4` | `ProduceCardConversion`, `ProduceInitialDeck`, `ProduceLegendProduceCard` | **コンバージョン**（`beforeProduceCardId → afterProduceCardId`, `conditionSetId`=プロデューサーLv 条件）；每个剧本按 `examEffectType`（=プラン代表 buff）的初始牌组 id；**レジェンドカード**候选（`produceId, examEffectType, produceCardIds[]`，2025-12-26 才填入 6 行，2026-03 两次扩充） |
| 2025-11-14 | `4e3a93c` | `CompetitionSeason`, `CompetitionStageSectionLock`, `CompetitionExamStatusEffectIcon`, `ExamContestEmbedProduceCard`, `ProduceExamAutoPlayProduceCardEvaluation` | コンテスト改版（`CompetitionGrade__1..8`, `CompetitionStageType__1..3`）；コンテスト嵌入卡；AutoPlay 按卡的负权重（-100000 = 禁用） |
| 2026-05-12 | `c344b6e` | `IdolCardPrimaStellaProduceSkill`, `ProduceGrowthPanel`, `ProduceGrowthPanelSheet`, `ProduceCustomizeItem`, `ProduceCustomizeItemRelationship`, `ProduceCharacterUnit`, `ProduceLiveEvaluation`, `ProduceSplitAdv`, `ProduceStepOpenLesson(+Motion)`, `ProduceStepAuditionRivalActor(+Motion)`, `ProduceStepAuditionCharacterBgm`, `ProduceStepAuditionCharacterUnitMotion`, `ExamUnitMotion`, `ProduceDescriptionProduceType` | **3.0 / H.I.F 全套**：プリマステラ（偶像卡新一档解放 → 追加 `ProduceSkill`，`IdolCard.idolCardPrimaStellaProduceSkillId/secondProduceCardId/...`）；**成長パネル**（`ProduceGrowthPanel(level, produceGrowthPanelSheetId, produceEffectIds[], unlockItemQuantity)`，按 `ProduceType` 的永久成长树，50 格）；**カスタマイズPアイテム**（`ProduceCustomizeItem: isBase/isTerminal, produceExamTriggerId, produceExamEffectIds, examEffectTurn/Count` + 父子关系树）；ユニット（REVERSI = kllj+ssmk）；H.I.F 的公開レッスン（`ProduceStepOpenLesson: mainParameter, subParameter, star`）；试验对手（`RivalActor`）；`ProduceLiveEvaluation(produceId, characterId, liveType)` 决定结局 live 种类 |

删除的表：`CostumeGroup`(2025-01-09)、`ProduceDescription`/`ProduceDescriptionProduce{CardGrowEffect,Effect,ExamEffect,Plan}Type`（2025-01-20，被 `ProduceDescription*` 新体系取代）、`ProduceLiveCommon`（→`ProduceGroupLiveCommon`）、`GashaAnimation`、`PhotoLookEffectorCharacter`（2026-08-17）。


### B.3 剧本（Produce）与评分规则的变化

#### B.3.0 版本 ↔ 日期（来自 `ForceAppVersion` 的每次变化；该表 2024-12-20 才出现，之前的版本按官方 X 公告）

| dump 日期 | 强制更新到 | 对应内容（同日/前几日的 master 变化） |
|---|---|---|
| 2024-07-22 | 1.3.0（官方：7/18 发布，7/22 强制） | — |
| 2024-09-01 | 1.4.0（官方：8/28 发布，9/1 强制） | マスター难度（9/20 入表） |
| 2024-11-16 | 1.5.0 | アノマリー |
| 2024-12-20 / 12-26 | 1.6.1 → 1.7.0 | カスタマイズ → N.I.A |
| 2025-01-22 / 02-21 / 03-24 | 1.8.0 / 1.9.0 / 1.10.1（+DMM 平台） | AutoPlay v1→v2；のんびり等 |
| 2025-04-22 / 04-24 | 1.11.0 / 1.11.1 | ProduceGrade 按剧本族评级 |
| 2025-05-16 | **2.0.0** | N.I.A マスター（05-19 入表）、SSS |
| 2025-06-19 / 07-17 / 08-22 / 09-29 | 2.1.0 / 2.2.0 / 2.3.0 / 2.4.0 | プライド、Business 类型、プロデューサーランキング |
| 2025-10-06 / 10-17 / 11-16 / 12-18 | 2.4.2 / 2.5.0 / 2.6.0 / 2.7.0 | コンバージョン、コンテスト改版、（12-26）レジェンド |
| 2026-01-22 / 02-19 / 03-16 / 04-15 | 2.8.0 / 2.9.0 / 2.10.2 / 2.11.0 | chain 效果、絶好調费用、Easy 模式 |
| 2026-05-16 | **3.0.2** | H.I.F、プリマステラ、成長パネル |
| 2026-06-05 / 06-15 / 07-21 / 08-10 / 08-21 | 3.0.3 / 3.1.0 / 3.2.0 / 3.2.3 / **3.3.0** | ユニット；`Exam*GetSum`；（3.3.0）サポイベ强化卡获取 |

#### B.3.1 `Produce.yaml`（HEAD，8 行）

| id | 名称 | 族 | 首次出现 | steps | AP | growthLimit | baseStepLevel | maxRefresh | produceSettingId | splitType / pair | unlock 条件 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `produce-001` | レギュラー | 初 | 2024-05-18 (1.0) | 13 | 15 | 1000 | 1 | 0 | `p_setting-1` | Unknown  | `-` |
| `produce-002` | プロ | 初 | 2024-05-18 (1.0) | 16 | 20 | 1500 | 5 | 0 | `p_setting-2` | Unknown  | `cd-task_clear-01-040` |
| `produce-003` | マスター | 初 | 2024-09-20 `3421aa7` (1.4.x) | 18 | 20 | 1800 | 5 | 0 | `p_setting-3` | Unknown  | `cd-master_produce-unlock_open` |
| `produce-004` | プロ | N.I.A | 2024-12-26 `cb5768d` (1.7.0) | 27 | 20 | 2000 | 1 | 4 | `p_setting-4` | Unknown  | `cd-nia_produce-unlock_open` |
| `produce-005` | マスター | N.I.A | 2025-05-19 `676438a` (2.0.0) | 26 | 20 | 2600 | 1 | 4 | `p_setting-5` | Unknown  | `cd-nia_master_produce-unlock_open` |
| `produce-006` | レジェンド | 初 | 2025-12-26 `6edc27e` (2.7.0) | 18 | 20 | 3000 | 5 | 4 | `p_setting-6` | Unknown  | `cd-hajime_legend_produce-unlock_open` |
| `produce-007` | 選抜試験 | H.I.F | 2026-05-16 `f0dac51` (3.0.2) | 20 | 20 | 3000 | 1 | 0 | `p_setting-7` | Selection / produce-008 | `cd-hif_selection_produce-unlock_open` |
| `produce-008` | 本戦 | H.I.F | 2026-05-16 `f0dac51` (3.0.2) | 9 | 20 | 3000 | 1 | 0 | `p_setting-8` | Final / produce-007 | `cd-hif_final_produce-unlock_open` |

行级变化史（`history_diff` 逐 commit）：
- 2024-09-20 `3421aa7`：+`produce-003` マスター（steps 18，growthLimit 1800）。2024-12-26 其 unlock 条件由 `cd-master_produce-view_open` 改为 `cd-master_produce-unlock_open`。
- 2024-12-26 `cb5768d`：+`produce-004`，当时 **name = "N.I.A"**，growthLimit 2000，steps 27，`maxRefreshCount 4`；2025-05-19 改名为「プロ」并换配色（因为加入了 NIA マスター `produce-005`：growthLimit 2300，steps 26）。
- 2025-12-26 `6edc27e`：+`produce-006` レジェンド（steps 18，growthLimit **2800**，`ProduceSelectScreenOrderType_Second`）；同 commit `produce-005` growthLimit **2300 → 2600**。
- 2026-03-31 `ff8795e`：Easy 模式字段（只有 `produce-004` 配了 `easyConditionSetId=cd-easy_mode` 与 `easyProduceItemIds=[pitem_00-3-330-0]`）。
- 2026-05-16 `f0dac51`：+`produce-007` 選抜試験（steps 20）/ `produce-008` 本戦（steps 9），`ProduceSplitType_Selection/Final` 互指，`selectionMemoryEmbedProduceCardId`；同 commit `produce-006` growthLimit **2800 → 3000**。
- `examSettingId` 八行**始终**都是 `p_exam_setting-1`：试验内常数是全局的，不按剧本区分；剧本差异全部在 `ProduceSetting`、`ProduceStepAuditionDifficulty`、`ProduceStep*`、`ProduceGrowthPanel`、`ProduceInitialDeck`、`ProduceLegendProduceCard` 等按 `produceId`/`produceType` 的表里。

#### B.3.2 `ProduceSetting`（HEAD，列 = `p_setting-1..8`）

| 字段 | `1` | `2` | `3` | `4` | `5` | `6` | `7` | `8` |
|---|---|---|---|---|---|---|---|---|
| `initialProducePoint` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `produceDrinkPossessLimit` | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| `produceDrinkPossessMaxLimit` | 4 | 4 | 4 | 4 | 4 | 4 | 4 | 4 |
| `refreshStaminaRecoveryPermil` | 700 | 700 | 700 | 700 | 700 | 700 | 500 | 500 |
| `beforeAuditionRefreshStaminaRecoveryPermil` | 700 | 700 | 700 | 500 | 500 | 700 | 500 | 500 |
| `stepSkipStaminaRecoveryPermil` | 250 | 250 | 250 | 250 | 250 | 250 | 250 | 250 |
| `customizeProduceCardCount` | 1 | 1 | 1 | 1 | 2 | 2 | 2 | 2 |
| `stepIntervalUpgradeProduceCardCount` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `stepIntervalCustomizeProduceCardCount` | 2 | 2 | 2 | 2 | 2 | 2 | 2 | 2 |
| `maxLegendProduceCardCount` | 0 | 0 | 0 | 0 | 0 | 1 | 1 | 1 |
| `selectionMemoryNeedProduceCardCount` | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 |
| `produceAuditionTrendAssessmentPermilUpper` | 200 | 200 | 200 | 200 | 110 | 110 | 110 | 110 |
| `produceAuditionTrendAssessmentPermilLower` | 200 | 200 | 200 | 200 | 110 | 110 | 110 | 110 |
| `continueCount` | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |

变化史：2024-12-20 加入 customize / 跳过步骤回体 / 试验前回体字段（`beforeAuditionRefreshStaminaRecoveryPermil` 初 700、NIA 500）；2025-05-19 NIA マスター `customizeProduceCardCount=2`、`produceAuditionTrendAssessmentPermil=110`（其余 200）；2025-08-18 该字段拆成 Upper/Lower、2025-09-29 旧字段删除；2025-10-21 `maxLegendProduceCardCount` 出现（先全 1，2025-12-26 改为只有 `p_setting-6` 为 1，其余 0）；2026-05-12/16 加入 `produceDrinkPossessMaxLimit=4`、`stepIntervalUpgradeProduceCardCount=1`、`stepIntervalCustomizeProduceCardCount=2`、`selectionMemoryNeedProduceCardCount=1`（全部剧本），H.I.F 两行 `refreshStaminaRecoveryPermil=500`。

#### B.3.3 `ExamSetting`（单行 `p_exam_setting-1`）的数值变化 —— 直接影响打牌结算

| 日期 | commit | 变化 | 含义 |
|---|---|---|---|
| 2024-06-24 | `9b0cc92` | `produceExamPanicStaminaCandidates` `[1,3,5,8,11,15]` → `[1,2,3,4,5,6,7,7,8,8,9,9,10,11,12,13,14,15]` | 気まぐれ（Panic）随机体力消耗的候选分布改变 |
| 2024-10-25 | `8f45f8b` | `examConcentrationLessonValueMultiplePermil1/2` 1500/2000 → **2000/2500**；`examConcentrationStaminaMultiplePermil1` 1500→2000；`fullPowerPlayableValueAdd` 2→1；`preservationReleaseBlockAdd1/2` 10/10→0/5；`preservationReleaseEnthusiastic1/2` 0/5→5/8；`preservationReleasePlayableValueAdd2` 5→1 | アノマリー上线前的指針数值重调（強気 1 段/2 段倍率、温存解除奖励） |
| 2024-10-25 | `4eeeeea` | +`examConcentrationStaminaPenetrateReduce1/2` = 0/1 | 強気对体力直接消耗的减免 |
| 2025-01-22 → 02-28 | | `examAutoPlayEnableVersion` 1 → 2，`examAutoPlaySearchCommandLimit` 1 → 5 | 官方 AutoPlay 改为带搜索的 v2 |
| 2025-03-21 | `4ba70d5` | +`overPreservationRelease{PlayableValueAdd,BlockAdd,Enthusiastic}`=1/5/10，`overPreservationReleaseToFullPowerGrowEffectLessonAdd`=10，`examOverPreservation*MultiplePermil`=0，`examAutoPlaySearchCommandPlanLimits`=[5,5,5] | のんびり（OverPreservation）指針 |
| 2025-06-17 | `4cd7c1e` | +`examLessonValueMultipleDependReviewOrAggressiveMultiplePermil`=**100** | プライド：每点好印象/やる気 +10% |
| 2025-11-07 | `8995439` | 同字段 **100 → 20** | プライド削弱为每点 +2% |
| 2025-11-14 | `4e3a93c` | +`examLessonValueMultipleDependReviewOrAggressiveMaxPermil`=**500** | プライド上限 +50% |
| 2026-02-19 | `374cf1a` | +`fixMoveCardShuffleDeckEnable`=true | 卡牌移动进山札后洗牌规则修正（固化） |
| 2026-05-12 | `c344b6e` | +`examBuffConsumptionAddPermil`=1000，`examBuffConsumptionDownPermil`=500 | H.I.F 的 buff 消费（`ExamBuffConsume` 相位）增减倍率 |

同样重要的是**没有变**的：`examStaminaConsumptionDownPermil/AddPermil`、`examBlockAddDownPermil=667`、`examParameterBuffPermil`、`examParameterBuffMultiplePerTurnPermil`、`holdLimit`、`handLimit`、`turnStartDistribute`、`examGimmickParameterDebuffPermil=667`、`examTurnEndRecoveryStamina` 自 1.0 起未改。

#### B.3.4 功能开关（出现→翻转→消失）的生效日期

| 开关 | 出现(false) | 翻 true | 消失（固化） | 含义（推测自字段名） |
|---|---|---|---|---|
| `examShuffleFixed` | 2024-08-10 | 2024-08-29 | 2024-12-20 | 洗牌算法修正 |
| `examCardSelectEvaluationTriggerCoefficientEnable` | 2024-12-20 | 2024-12-26 | 2025-10-21 | AutoPlay 选卡评价乘 trigger 系数 |
| `examDrawCountLimitFixed` | 2024-12-20 | 2024-12-26 | 2025-10-21 | 抽牌数上限修正 |
| `auditionSupportUpgradeAdded` | 2024-12-20 (true) | — | 2025-10-21 | 试验中サポート强化 |
| `examDrinkTriggerFixed` | 2025-05-16 | 2025-05-19 | 2025-10-21 | Pドリンク触发修正 |
| `examStanceChangeAssignmentCountEnable` | 2025-08-18 | 2025-08-22 | 2025-10-21 | 指針变更计数 |
| `examAutoPlayV2Enable` | 2024-12-20 | — | 2025-01-22（被 `examAutoPlayEnableVersion` 取代） | |

2025-10-14 `452bfc9` 曾把 5 个开关一起翻回 false 一周（2.4.2 热修复期），2025-10-21 一并删除。

#### B.3.5 评级阈值与评价值规则

- `ResultGradePattern`（全局，按 `ResultGradeType`）与 `ProduceGrade`（2025-04-21 起，按 `produceGroupId`）的 `ProduceScore` 阈值：F 0 / E 1000 / D 2000 / C 3000 / C+ 4500 / B 6000 / B+ 8000 / A 10000 / A+ 11500 / S 13000 / S+ 14500 / SS 16000 / SS+ 18000 —— **自 1.0 起从未修改**；只在顶部追加：SSS 20000 / SSS+ 23000（2025-05-19，先只给 NIA 族 `produce_group-002`；初族 2025-12-26 才加）、SSSS 26000（2025-12-26，初族）、SSSS+ 30000 / SSSSS 35000 / SSSSS+ 40000（2026-05-16；`ProduceGrade` 里 H.I.F 族 `produce_group-003` 到 SSSSS 为止，`ResultGradePattern` 另有 SSSSS+）。
- `ProduceGroup.limitGrade`（该族可达到的最高评级）：2025-05-19 初 = SS+，NIA = SSS+；2025-12-26 初 → **SSSS**（レジェンド）。
- 其他评级轴：`ResultGradeType_ProduceIdolCardParameter`（参数总和评级，SSS 3000 / SSS+ 3500）；`ProduceVoteCount`（NIA ファン投票数，E 3000 … SSS+ 160000，2024-12-26）；`ProduceStar`（H.I.F スター性，E 20 … S+ 1200，2026-05-16）。`MemoryEvaluation` 与 `ProduceAuditionLiveBattleScore` 两轴 2025-01-20 被删除。
- `ProduceSeasonZeroGrade`（2025-09-29）= プロデューサーランキング シーズン0 期间各族阈值的冻结快照（初族到 SSS+ 23000）——官方自己也在做「按赛季版本化的评级表」。
- **2025-10-31 最終試験スコア上限**：dump 当天 commit `8f5684e`（64 文件）只新增了 26 行 `ProduceStepAuditionDifficulty`（新偶像卡），`ResultGradePattern` / `ProduceGrade` / `ExamSetting` / `ProduceSetting` 均**无变化**——评价值公式（順位点 + 2.3×参数 + 分段折算的试验分，及其上限；レジェンド版 2.1 系数与中間試験项；H.I.F 的换算）**全部在客户端/服务端代码里，master data 不含**。公式本身见 `existing_engines.md` §6（`gakumas-tools/utils/produceRank.js`、`hif.js`）与 `user_report_02_data_and_formulas.md` §3。因此引擎的评价值模块必须自带 `effective_from`。

#### B.3.6 试验难度 / NPC 分数（`ProduceStepAuditionDifficulty`、`ProduceExamBattle*`）

结构：每行 = (`produceId`, `stepType` ∈ {AuditionMid1, AuditionMid2, AuditionFinal}, `auditionType`（NIA 的 Easy/Normal/Hard/VeryHard，其余 Unknown）, 角色或**偶像卡**)。`id` 不唯一（`p_step_audition_difficulty-amao` 4 行；`…-i_card-ttmr-3-001` 这种**按偶像卡覆盖**的行自 2024-05-22 起存在，2025-10-14 曾单独调低 ttmr/fktn SSR 的 baseScore）。字段：`rankThreshold`（合格名次：初 3、NIA 1、HIF 選抜 2、本戦 Final 1）、`parameterBaseLine`、`baseScore`、`forceEndScore`（提前结束分，只有 初 レギュラー/プロ Mid1 用）、`produceExamBattleNpcGroupId`（NPC 分数区间表）、`produceExamBattleConfigId`（NPC 的回合数与三维 → `ProduceExamBattleScoreConfig` 的 `parameter` + 三维 permil）、`produceExamGimmickEffectGroupId`（试验 gimmick 组，初/NIA/HIF 各 14/7/6 种）、NIA 的 `voteCount`/`voteCountBaseLine`/`dearnessLevel`、HIF 的 `starScoreBonusBaseLine`/`isStaticNpcScore`。

HEAD 各剧本的量级（baseScore 区间 / NPC `scoreMin..scoreMax`）：初 レギュラー Final 2450–2650 / NPC ≤2856；プロ 6950–7650 / ≤8215；マスター 8340–9180 / ≤15609；NIA プロ Final Easy 12.8k–13.6k … VeryHard 58k–62k / NPC ≤71.8k；NIA マスター Final VeryHard 93k–97k / ≤112.5k；**レジェンド Final 174k–176k / NPC 159k–202k**（rankThreshold 3）；H.I.F 選抜 Final 134k–136k、本戦 Mid1 400k–406k、**本戦 Final 600k–609k，NPC 固定（`isStaticNpcScore=true`）294k–640k**。

变化史（行内数值修改，非新增）：
- 2025-07-07 `b2f0762`：160 行 NIA 的 `dearnessLevel` 0 → 14（Hard）/ 17（VeryHard）：高难度需要親愛度。
- 2025-10-14 `452bfc9`：ttmr/fktn 偶像卡专属行 baseScore 下调（如 3250→2550、9700→7300）。
- **2025-12-26 `6edc27e`：NIA プロ（`produce-004`）全部 990 行 `baseScore` 下调 ×0.73–0.80**（Final Easy 16650–17650 → 12800–13550；FinalVeryHard 79700–84800 → 58150–61900；Mid2Normal ×0.733）。NIA マスター未动。这是 2.7.0 的难度重平衡，与 レジェンド 同日。
- 2026-05-12 `c344b6e`：全部 3248 行加 `isStaticNpcScore=false`、`starScoreBonusBaseLine=0`（H.I.F 前置）。
- 其余 80 次 commit 全是**新增行**（每张新偶像卡 +4/+26/+28 行，每个新剧本 +241～+750 行），即 NPC 难度是按偶像卡配置的，新卡 = 新行，引擎必须按 (produceId, stepType, auditionType, idolCard/character) 查表而不是按剧本给常数。
- `ProduceExamBattleScoreConfig` 164 → 4108 行、`ProduceExamBattleConfig` 39 → 655 行：新增来自 タワー（`tower_###-…-turn_#`，300 行）、コンテスト、セミナー、各剧本变体；数值修改只有 2024-07-01/07-22/08-01/08-22/11-16 五次对 `*Permil` 的个位数微调（±2～17‰）。

### B.4 行级 schema 增长（表明新卡牌机制）

（首次出现日期为**字段**首次出现；2024-05-19 的一批是序列化变化，2025-01-22 的 `descriptions → produceDescriptions` 是改名。）

| 表 | 日期 | 新字段 | 机制 |
|---|---|---|---|
| `ProduceCard` | 2024-10-25 | `isReward` | 报酬卡 |
| | 2024-12-20 | `produceCardCustomizeIds[]`, `maxCustomizeCount` | **カスタマイズ**（→`ProduceCardCustomize`） |
| | 2025-10-21 | `isConversion`, `moveProduceExamTriggerIds[]` | **コンバージョン**（→`ProduceCardConversion`）；移动触发改为多触发器 |
| | 2025-12-26 | `rarity=Legend`（值） | **レジェンドカード**（25 张，`p_card-0X-…-100_NNN`） |
| | 2026-03-31 | `originCharacterId`, `voiceAssetId` | 角色固有卡溯源 |
| | 2026-05-12 | `originPrimaStellaIdolCardId` | **プリマステラ**第二固有卡 |
| `ProduceExamEffect` | 2024-08-29→10-25 | `produceCardGrowEffectId` → `produceCardGrowEffectIds[]` | 成長效果 |
| | 2024-12-20 | `effectGroupIds[]`, `customizeProduceDescriptions` | 效果分组（描述/图标/AI 用），カスタマイズ后的描述 |
| | 2026-02-19 | `pickCountType`, `pickCountReferenceProduceCardSearchId` | 生成数量按另一搜索的数量决定（`Shortage` = 补足到 N 张，2026-05-16） |
| | 2026-03-31 | `chainProduceExamEffectIds[]`（原单值 `chainProduceExamEffectId`） | 链式效果多目标 |
| | 2026-05-12 | `produceCardSearchId2`, `pickRangeType2`, `pickCountType2`, `pickCountMin2/Max2`, `pickCountReferenceProduceCardSearchId2` | 双搜索效果（`ExamMoveGrowEffect` 等：从 A 搬成長到 B） |
| `ProduceExamTrigger` | 2025-01-22 | `playProduceDescriptions`, `playEffectProduceDescriptions` | 触发器分「使用条件」「效果发动条件」两种描述 |
| `ProduceItem` | 2024-08-29 | `isChallenge` | チャレンジPアイテム（マスター） |
| | 2025-03-21 | `isHighScoreRush` | ハイスコア Rush 活动 |
| | 2025-05-16 | `fireInterval` | 每 N 次触发 |
| | 2025-08-18 | `isResearch` | リサーチ |
| | 2026-03-31 | `isEasy` | Easy 模式专用 |
| `ProduceSkill`（偶像/サポ技能） | 2026-05-12 | `produceType`, `produceSplitType` | 技能按剧本族/分段生效（プリマステラ技能只在 HIF 本戦） |
| `IdolCard` | 2025-05-16 | `maxIdolCardLevelLimitRank`, `showExamEffectType` | 突破上限 7、展示 buff |
| | 2026-05-12 | `idolCardPrimaStellaProduceSkillId`, `secondProduceCardId`, `before/afterLevelLimitProduceItemId`, `primaStella*` | **プリマステラ**：第二固有卡、突破前后不同 P アイテム |
| `ProduceCardSearch` | 2025-03-21 / 05-16 / 10-21 | `cardRarities`, `produceCardPoolId`, `costType`, `isCustomized` | 搜索条件扩展（按稀有度/卡池/费用类型/是否已カスタマイズ） |
| `ProduceStepAuditionDifficulty` | 2024-12-20 / 2026-05-12 | 见 B.3.6 | |
| `ProduceExamGimmickEffectGroup` | 2025-10-21 | `fieldStatusProduceCardSearchId` | gimmick 条件可引用卡搜索 |
| `MemoryAbility` | 2026-05-12 | `isUniqueActivation` | メモリーアビリティ 去重（2026-08-26 紧急维护修的就是它） |
| `ProduceCardGrowEffect` / `ProduceCardStatusEnchant` | 2024-11-16 | 整表（`effectType, value, costType, playProduceExamTriggerId, playMovePositionType, targetPlay*`…） | 成長 / 卡牌自身的持续效果 |

---

## Part C — 引擎扩展点清单

原则（与 `ARCHITECTURE.md` §8 一致）：**数据驱动 + 注册表 + 未知即报错 + 规则版本化**。下面每一项给出「为什么（来自 A/B 的证据）」和「驱动它的表/字段」。

### C.1 必须具备的扩展点

| # | 扩展点 | 证据 | 驱动表 / 字段 |
|---|---|---|---|
| 1 | **效果类型注册表**（`ProduceExamEffectType` → handler），未注册值抛 `UnsupportedMechanic`，并有覆盖率报告 | 2 年 +67 个值、几乎每个大版本 +10～20；HEAD 用到 107 个 | `ProduceExamEffect.effectType` + `effectValue1/2, effectCount, effectTurn, targetExamEffectType, produceCardSearchId(2), pickRangeType(2), pickCountType(2), pickCountMin/Max(2), pickCountReferenceProduceCardSearchId(2), movePositionType, chainProduceExamEffectIds, produceExamStatusEnchantId, produceCardStatusEnchantId, produceCardGrowEffectIds, effectGroupIds` |
| 2 | **触发器解释器**：相位注册表（`ProduceExamPhaseType`，30）× 条件注册表（`ProduceExamFieldStatusType`，29，含 `Not` 取反 `fieldStatusCheckTypes`）× 卡搜索 | 相位 +18、条件 +15；新相位常与新剧本同时出现（`ExamBuffConsume` 2025-02、`ExamAggressiveUpInterval` 2026-05） | `ProduceExamTrigger.phaseTypes[]/phaseValues[]/fieldStatusTypes[]/fieldStatusValues[]/fieldStatusCheckTypes[]/fieldStatusProduceCardSearchIds[]/produceCardSearchId/upperSearchCount/lowerSearchCount/lessonType/effectTypes[]`；`ProduceTrigger.phaseType`（培育相位，29） |
| 3 | **状态附魔目录**（持续效果实体）：`ProduceExamStatusEnchant`（2003 行）= trigger + effects 的组合，带 `ExamStatusEnchantEncore`（再演，2026-05）与 `ExamPermanent*StatusEnchant`（跨试验永久，2025-12） | 448 个 `ExamStatusEnchant` 效果引用它；HIF 的「再演」复制附魔 | `ProduceExamStatusEnchant(id, produceExamTriggerId, produceExamEffectIds[])`, `ProduceCardStatusEnchant(triggerCount, produceCardGrowEffectIds[])`, `ProduceItemEffect.produceExamStatusEnchantId`, `ProduceEffectType_ExamPermanent{Lesson,Audition}StatusEnchant` |
| 4 | **卡搜索 DSL**（`ProduceCardSearch`）作为独立模块 | 效果/触发/成長/gimmick 全部通过它选目标；字段 2025 年三次扩展（稀有度、卡池、费用类型、`isCustomized`） | `ProduceCardSearch.*`（`cardStatusType, examEffectType, planType, cardRarities, produceCardPoolId, costType, isCustomized, staminaMin/Max, upgradeCounts, isSelf, produceCardIds`）；`ProduceCardPool.produceCardRatios[]`；`ProducePickCountType_Shortage` |
| 5 | **卡牌成长层**（`ProduceCardGrowEffect`，54 种 `effectType`）：运行时叠加到卡牌定义上（値/コスト/効果追加・削除・置換/触发替换/移动位置替换），是 カスタマイズ、成長、レッスン中強化、ExamMoveGrowEffect 的共同基础 | 2024-10-25 整表出现，之后成为 160 个 `ExamAddGrowEffect` 效果与 343 行 `ProduceCardCustomize` 的载体 | `ProduceCardGrowEffect(effectType, value, costType, playProduceExamTriggerId, playProduceExamEffectId, playMovePositionType, targetPlay*Ids)`；`ProduceCardCustomize(customizeCount, produceCardGrowEffectIds, producePoint, overwriteProduceCardGrowEffectType)`；`ProduceCard.produceCardCustomizeIds/maxCustomizeCount` |
| 6 | **费用类型注册表**（`ExamCostType`，7）：体力/元気/好印象/やる気/集中/全力値/絶好調 | 2024-11 +全力値、2026-03 +絶好調 | `ProduceCard.costType/costValue/stamina/forceStamina`；`ExamSetting.exam*Consumption*Permil` |
| 7 | **卡牌区域与移动**：Deck/Hand/Grave/Lost/Hold 五区 + `DeckFirst/DeckLast/DeckRandom`；`Hold`（手札持ち越し，2024-11）与 `NotLost` 位置集合（2025-12）；`moveEffectTriggerType`（进入 Hand/Hold 时触发，2025-12/2026-03） | `ProduceCardMovePositionType` +3、`ProduceCardPositionType` +4 | `ProduceCard.playMovePositionType/moveEffectTriggerType/moveProduceExamEffectIds/moveProduceExamTriggerIds/isEndTurnLost`；`ExamSetting.holdLimit/handLimit/fixMoveCardShuffleDeckEnable` |
| 8 | **指針（Stance）状态机**：強気 1/2 段、温存 1/2 段、全力、のんびり（OverPreservation）、`StanceLock`；解除奖励常数 | アノマリー 2024-11 + のんびり 2025-03 两次扩展，且 `ExamSetting` 常数在 2024-10-25 重调 | `ExamSetting.{examConcentration*, examPreservation*, preservationRelease*, overPreservationRelease*, fullPowerPlayableValueAdd, examFullPowerLessonValueMultiplePermil}`；相位 `ExamStanceChange*`；条件 `*ChangeCountUp/NoStance/FullPowerPointGetSumUp` |
| 9 | **剧本配置以 `Produce.id` 为键**，剧本族以 `ProduceGroup.type`（`ProduceType`）为键，分段以 `ProduceSplitType` 为键；新剧本 = 新配置 + 可选 plugin | 8 个 Produce 行、3 个族；HIF 是「两个 Produce 行拼成一次培育」（`splitPairProduceId`、`selectionMemoryEmbedProduceCardId`） | `Produce.*`, `ProduceSetting.*`, `ProduceGroup(type, produceIds, limitGrade)`, `ProduceInitialDeck(produceId, examEffectType→examInitialDeckId)`, `ProduceLegendProduceCard`, `ProduceStepTransition`, `ProduceStep*`, `ProduceSkill.produceType/produceSplitType`, `ProduceGrowthPanelSheet.produceType` |
| 10 | **步骤类型注册表**（`ProduceStepType`，34）：Lesson/SpLesson/Audition(Mid1/Mid2/Final)/EventSchool/Activity/Business/SelfLesson*/FanPresent/OpenLesson*(Star) | NIA +9、HIF +12 | `ProduceStepTransition`, `ProduceStepLesson(+Level)`, `ProduceStepSelfLesson`, `ProduceStepOpenLesson(mainParameter, subParameter, star)`, `ProduceStepEventDetail/Suggestion`, `ProduceStepBusinessType` |
| 11 | **试验难度/NPC 查表**：按 (produceId, stepType, auditionType, character/idolCard)；NPC 分数由 `NpcGroup` 区间 + op/mid/ed permil 分段生成，或 `isStaticNpcScore` 固定；`ProduceExamBattleConfig` 给 NPC 三维与回合数 → `ScoreConfig` 换算 | 83 次 commit 几乎全是新偶像卡加行；2025-12-26 NIA 全量 ×0.78 | `ProduceStepAuditionDifficulty.*`, `ProduceExamBattleNpcGroup(scoreMin/Max, op/mid/edScorePermil, vocal/dance/visualPermil)`, `ProduceExamBattleNpcMob`, `ProduceExamBattleConfig(turn, vocal, dance, visual, *Excellent/*Bad)`, `ProduceExamBattleScoreConfig(parameter, *Permil)`, `ProduceExamGimmickEffectGroup` |
| 12 | **试验 gimmick**（本番の状況）：按 `priority/startTurn/remainingTurn(Permil)/fieldStatus*` 触发的效果组 | 3707 行，初/NIA/HIF 各自的组 | `ProduceExamGimmickEffectGroup.*`, `ExamSetting.examGimmick*` |
| 13 | **评价值/评级模块版本化**：阈值表来自 master（按 `produceGroupId`），公式来自 `rules/scoring/*.yaml`，带 `effective_from`（至少：2024-05-16 初版；2025-05-19 NIA SSS；2025-10-31 最終試験分上限；2025-12-26 レジェンド 2.1 系数 + 中間試験项；2026-05-16 HIF 換算与 スター性） | B.3.5：2025-10-31 无任何 master 变化 | `ProduceGrade`, `ResultGradePattern`, `ProduceSeasonZeroGrade`, `ProduceGroup.limitGrade`, `ProduceSeason`, `ResultGradeType_{ProduceVoteCount,ProduceStar,ProduceIdolCardParameter}` |
| 14 | **`ExamSetting` 常数随 dump 版本加载**（不要硬编码 permil），并把每次变化记入 changelog | B.3.3：プライド 100→20 (+cap 500)，強気倍率 1500/2000→2000/2500 | `ExamSetting.*`（46 字段） |
| 15 | **培育外循环效果注册表**（`ProduceEffectType`，103；HEAD 用 66）+ 培育触发相位（`ProducePhaseType`） | +32；HIF 新增 スター性/上限/ドリンク上限/永久折扣等 | `ProduceEffect(produceEffectType, value1/2, …)`, `ProduceItem/ProduceItemEffect`, `ProduceSkill(produceEffectId1..3, produceTriggerId1..3, activationRatePermil1..3)`, `ProduceDrink/ProduceDrinkEffect`, `ProduceGrowthPanel.produceEffectIds[]`, `ProduceCustomizeItem` |
| 16 | **卡牌来源/变体层**：コンバージョン（`before→after` 按 プロデューサーLv 条件）、レジェンドカード（按剧本+代表 buff 的候选池，`maxLegendProduceCardCount`）、プリマステラ第二固有卡、初始牌组（`ProduceInitialDeck`/`ExamInitialDeck`）、報酬卡/限定卡 | 2025-10 → 2026-05 三次新增 | `ProduceCardConversion`, `ProduceLegendProduceCard`, `IdolCard.secondProduceCardId/idolCardPrimaStellaProduceSkillId`, `IdolCardPrimaStellaProduceSkill`, `ProduceInitialDeck`, `ProduceCard.isConversion/isReward/isLimited/originIdolCardId/originSupportCardId/originPrimaStellaIdolCardId` |
| 17 | **成長パネル / カスタマイズPアイテム**（永久成长树与可组装 P アイテム）作为「培育前」配置层 | 2026-05 新表 | `ProduceGrowthPanel(level, produceEffectIds, unlockItemQuantity, produceSplitType)`, `ProduceGrowthPanelSheet(produceType)`, `ProduceCustomizeItem(isBase/isTerminal, produceExamTriggerId, produceExamEffectIds, examEffectTurn/Count, planType)`, `ProduceCustomizeItemRelationship` |
| 18 | **ライブ/结局层**（只影响评价展示与 TrueEnd 判定，不影响分数）：`ProduceLiveEvaluation(produceId, characterId, liveType)`、ユニット | 可延后，但要有占位 | `ProduceLive`, `ProduceLiveEvaluation`, `ProduceGroupLiveCommon`, `ProduceCharacterUnit` |
| 19 | **官方 AutoPlay 策略**（作为 baseline 策略插件，非核心）：v2 搜索（`examAutoPlaySearchCommandLimit/PlanLimits`）+ 四张权重表 | `ExamPlayType_AutoPlayCompetition` 2025-11 新增 | `ProduceExamAutoEvaluation`, `ProduceExamAutoTriggerEvaluation`, `ProduceExamAutoCardSelectEvaluation`, `ProduceExamAutoGrowEffectEvaluation`, `ProduceExamAutoPlayCardEvaluation`, `ProduceExamAutoPlayProduceCardEvaluation`, `ExamSetting.examAutoPlay*` |
| 20 | **描述模板层**（用于 UI/调试/校验，不参与结算）：`ProduceDescription*` 9 张表 + `produceDescriptions[]`（`ProduceDescriptionType`, `ExamDescriptionType`） | 2025-01 改名过一次；可拿来做「效果 → 日文文本」的回归校验 | `ProduceDescriptionExamEffect`, `ProduceDescriptionProduceEffect`, `ProduceDescriptionProduceCardGrowEffect`, `ProduceDescriptionLabel/Swap`, `ProduceDescriptionProduceType` |
| 21 | **数据版本元信息 + 升级流程**：记录 dump commit/日期；每次更新跑 `history_diff.py`，将「新枚举值/新表/配置行变化」变成 issue；固定 seed 回归 | Part A：dump 与线上同步，滞后 <1 天，新机制 1～2 月一批 | `ForceAppVersion`（版本号）、git 元数据 |

### C.2 数据里有、现有开源实现（很可能）没有的机制

依据 `docs/research/existing_engines.md`（gakumas-core 2024-09-22 停更、只做 lesson/exam 且无アノマリー；gakumas-tools/gakumas-engine 只做 コンテスト、手写 CSV DSL；skyfsj/gakumas-rl 读 master data、覆盖 99/108 效果类型但只认识 初/NIA）与本文 B 部分：

| 机制 | 数据位置 | 参考实现状态 |
|---|---|---|
| **H.I.F 全套**：選抜/本戦 分段、公開レッスン（主副参数 + スター性）、`ResultGradeType_ProduceStar`、`isStaticNpcScore` 固定 NPC、`starScoreBonusBaseLine`、`ExamStatusEnchantEncore`（再演）、`ExamBuffConsume` 相位与 `examBuffConsumption*Permil`、`ExamForcePlayCardSearchWithCost`、`Exam*AdditiveFix`、`ExamMoveGrowEffect`、`Exam*GetSum` | `Produce 007/008`, `ProduceStepOpenLesson`, `ProduceStepAuditionDifficulty`, `ExamSetting`, 2026-05/06 新枚举 | **无**（gakumas-tools 只有 HIF 评价值换算 `hif.js`，无培育/打牌；gakumas-rl 缺全部 9 个 2026-05 后的效果类型） |
| プリマステラ（第二固有卡、突破前后 P アイテム、`ProduceSkill.produceType/produceSplitType`） | `IdolCard.*primaStella*`, `IdolCardPrimaStellaProduceSkill` | 无 |
| 成長パネル / カスタマイズPアイテム | `ProduceGrowthPanel*`, `ProduceCustomizeItem*` | 无 |
| レジェンドカード（`Rarity_Legend`、候选池、`maxLegendProduceCardCount`）与 初・レジェンド 剧本（NPC 17 万分级、2.1 系数评价） | `ProduceLegendProduceCard`, `Produce 006` | 评价值公式有（gakumas-tools `produceRank.js`）；剧本/卡池逻辑无；gakumas-rl 能跑 Legend 的 exam 但不含培育 |
| コンバージョン、`ProduceInitialDeck`、`ExamCostType_ExamParameterBuffMultiplePerTurn`（絶好調费用）、`chainProduceExamEffectIds`、`pickCountType=Shortage`、双搜索（`*2` 字段） | `ProduceCardConversion`, 2026-02～05 字段 | 无 / gakumas-rl 部分（`pickRangeType/pickCountType` 未穷尽） |
| N.I.A 培育循环：Business（`ProduceStepBusinessType`）、SelfLesson、FanPresent、投票数（`voteCount*`、`ResultGradeType_ProduceVoteCount`）、Easy/Normal/Hard/VeryHard 试验选择、`dearnessLevel` 门槛、Mid2 试验、`maxRefreshCount` | `ProduceStep*`, `ProduceStepAuditionDifficulty`, `ProduceEffectType_*VoteCount*` | 部分（gakumas-rl 认识 NIA 的 exam；培育循环各家都是手写/近似） |
| 试验 NPC 分数生成（`NpcGroup` 区间 + op/mid/ed 分段、`BattleConfig`/`ScoreConfig` 换算、`*Excellent/*Bad`）与 gimmick 组 | `ProduceExamBattle*`, `ProduceExamGimmickEffectGroup` | 无完整实现（各模拟器用固定目标分或简化） |
| 2024-10-25 之后的 `ExamSetting` 数值（強気 2000/2500、のんびり、プライド 20‰+cap 500‰、`fixMoveCardShuffleDeckEnable`） | `ExamSetting` | gakumas-core 停在旧值；gakumas-rl 读表但 2026-05 后字段未处理 |
| 功能开关固化后的行为（`examDrawCountLimitFixed`、`examDrinkTriggerFixed`、`examStanceChangeAssignmentCountEnable`…） | B.3.4 | 无人建模（属于「bug 修复前后行为」，只能靠实测） |
| コンテスト改版（`Competition*`，2025-11）、`ExamPlayType_AutoPlayCompetition`、`ExamContestEmbedProduceCard` | `CompetitionSeason`, `CompetitionStageSectionLock` | gakumas-tools engine 建模了 コンテスト 舞台，但基于手写 CSV，不读这些表 |
| チャレンジPアイテム（マスター）、ハイスコア Rush、リサーチ、Easy 模式 P アイテム、`fireInterval` | `ProduceChallengeSlot`, `ProduceItemChallengeGroup`, `ProduceItem.isChallenge/isHighScoreRush/isResearch/isEasy/fireInterval` | 无 |
| 官方 AutoPlay v2 搜索（`examAutoPlaySearchCommandLimit=5`, `PlanLimits=[5,5,5]`）与 `ProduceExamAutoPlayProduceCardEvaluation`（-100000 禁用表） | `ExamSetting.examAutoPlay*`, 6 张 Auto 表 | 权重表有两处落地（gakumas-rl、kanon511），搜索算法无 |
| `MemoryAbility.isUniqueActivation`、`ProduceSkill.activationRatePermil1..3` 三段技能 | `MemoryAbility`, `ProduceSkill` | 无 |

### C.3 建议的落地顺序

1. 先做 C.1 #1–#8、#14（试验内核心：效果/触发/附魔/搜索/成長/费用/区域/指針 + `ExamSetting` 读表），用 gakumas-core 的 9 段录像用例做 センス/ロジック 回归，再用 gakumas-rl 的 242 个规则测试做 アノマリー 对拍（注意 GPL）。
2. 再做 #9–#12（剧本配置、步骤、NPC、gimmick）——先 初（レギュラー/プロ/マスター），因为它的 `ProduceStepAuditionDifficulty` 与评级表两年没动过，是最稳定的校验基线。
3. #13 评价值版本化与 #21 升级流程同时上线：每个 dump 更新都要能回答「这次有没有新枚举/新表/配置变化」。
4. 最后 #15–#19（N.I.A → レジェンド → H.I.F 的培育外循环、成長パネル、プリマステラ、AutoPlay baseline），这些没有任何参考实现，需要实测数据（见 `existing_engines.md` §8 与 `data_sources.md` §3）。
