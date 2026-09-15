# H.I.F編（Hatsuboshi IDOL FESTIVAL）机制规格书

> 目的：为本地模拟器实现 H.I.F 剧本提供可编码的数值规格。
> 数据来源：
> - **(A) 主数据（master data）**：`gakumasu-diff` YAML dump（2026-09-04 版）。引用格式 `表名.字段`，视为权威。
> - **(B) 网络攻略**：game8 / wikiwiki / seesaawiki / note / appgamelog 等，本会话中大部分站点被出口代理拦截，只能通过搜索摘要获得内容；引用时标注 URL。
> 每个事实块末尾标注 **[确认: 表.字段]** 或 **[网络: URL]** 或 **[推断]**。凡标注 [推断] 的内容在实现时应做成可配置项。

---

## 0. 总览

| 项目 | 值 | 来源 |
|---|---|---|
| 剧本名 | Hatsuboshi IDOL FESTIVAL（H.I.F，ハツボシアイドルフェスティバル） | `ProduceGroup.name`（produce_group-003） |
| 类型枚举 | `ProduceType_HatsuboshiIdolFestival` | `ProduceGroup.type` |
| 实装日 | 2026-05-16（2周年） | [网络: famitsu 202605/74899 搜索摘要] |
| 结构 | **两个独立 Produce**：`produce-007`「選抜試験（选拔试验）」→ `produce-008`「本戦（本战）」；用 `produceSplitType` 区分 `ProduceSplitType_Selection` / `ProduceSplitType_Final`，互为 `splitPairProduceId` | `Produce.yaml` |
| 选拔试验步数 | `steps: 20`（20 天/周），`actionPointQuantity: 20` | `Produce.steps`（produce-007） |
| 本战步数 | `steps: 9`，`actionPointQuantity: 20` | `Produce.steps`（produce-008） |
| 属性成长上限 | `idolCardParameterGrowthLimit: 3000`（两阶段相同；初レジェンド也是 3000，NIA マスター 2600，初マスター 1800） | `Produce.idolCardParameterGrowthLimit` |
| 评价上限 | `limitGrade: ResultGrade_Sssss`（S5）；初=Ssss（S4），NIA=SssPlus（S3+） | `ProduceGroup.limitGrade` |
| 强制通用Live | `isForceLiveCommon: true`，`disableForceLiveCommonEndingLiveType: ProduceLiveType_TrueEnd` | `ProduceGroup` |
| 选拔试验的 Live | `ProduceLiveType_A`（10 位偶像各 1 行） | `ProduceLiveEvaluation`（produce-007） |
| 本战的 Live | `ProduceLiveType_TrueEnd` | `ProduceLiveEvaluation`（produce-008） |
| 舞台 | `env_3d_live_hifstage-00-00-noon`，曲目 `music-all-<idol>-016` | `ProduceGroupLiveCommon` |
| 剧本描述 | 『Hatsuboshi IDOL FESTIVAL』── 初星学園のトップをめぐる戦いの火蓋が切られる さぁ、目指せ！『一番星』を！ | `ProduceGroup.description` |

**核心玩法一句话**：选拔试验是一次 20 周、含 3 场对战式试验的常规育成（有独立的 ScheduleUI「公開レッスン（公开课）」，试验用卡组）；通关后生成「選抜試験メモリー（选拔试验回忆）」，用它进入 9 步的本战（1~6 天准备 + Round1 → インターバル（间歇）→ Round2）。本战 Round1×1.2 + Round2 的合计分数最高者成为「一番星」。新资源「スター性（明星性）」既提高试验分数加成，也直接计入最终评价。 [确认: Produce/ProduceGroup] [网络: seesaawiki H.I.F, game8 783836 摘要]

---

## 1. 解锁条件与可用偶像

### 1.1 剧本解锁

| 条件 | 值 | 来源 |
|---|---|---|
| 選抜試験 解锁 | 任意偶像 親愛度（亲密度）Lv ≥ 27（`ConditionType_DearnessLevel min=27`，描述「「H.I.F」に挑戦できる いずれかのアイドルの親愛度Lv27で解放」） | `ConditionSet cd-hif_selection_produce-unlock_open` |
| 本戦 解锁 | 任意偶像 親愛度 ≥ 33 **且** `produce-007` 通关次数 ≥ 1（`ConditionType_ProduceClearCount min=1`，描述「いずれかのアイドルで選抜試験突破」） | `ConditionSet cd-hif_final_produce-unlock_open` |
| 对比：NIA 解锁 | 親愛度 10 + P课题 35；NIA マスター 親愛度 20；初レジェンド PLv50 + 親愛度10 + 主线 60 | `ConditionSet cd-nia_*`, `cd-hajime_legend_*` |
| 推荐 PLv | `produceHatsuboshiIdolFestivalFinalTargetProducerLevel: 70`（本战推荐制作人等级 70） | `Setting.yaml` |

### 1.2 每个偶像的参加条件

| 偶像 | 選抜試験 | 本戦 | 来源 |
|---|---|---|---|
| amao/hmsz/hrnm/hski/hume/kcna/kllj/shro/ssmk/ttmr（10 人） | 该偶像親愛度 ≥ 27（`cd-dearness_level-<id>-27`） | 该偶像親愛度 ≥ 33（`cd-dearness_level-<id>-33`） | `ProduceCharacter`（produce-007 / produce-008） |
| atbm / fktn / jsna | `cd_close-hif`（TimeTerm 永久关闭，描述「順次実装予定」） | 同左 | `ProduceCharacter` |
| 分批开放（历史） | `cd_close-hif_kcna_shro`「5/26以降に挑戦可能」、`cd_close-hif_kllj_ssmk`「6/5以降に挑戦可能」（已过期，现在都可用） | | `ConditionSet` |

> 注：燕(atbm)、星南(jsna)、广、咲季等在本战中作为 **对手 NPC** 出现（见 §6.3）。

### 1.3 親愛度相关的 HIF 专用效果（`CharacterDearnessLevel` + `ProduceSkill`）

以 amao 为例（10 人结构相同）；Lv28 起新增「獲得するスター性を X% 増加」（`p_effect-star_permil_up`），Lv37 新增饮料上限：

| 親愛度Lv | 解锁条件文本 | 新增/变化效果 | 来源 |
|---|---|---|---|
| 27 | 親愛度Pt累计600+通关 | 相談リフレッシュ回数+1 | `CharacterDearnessLevel.produceSkills` |
| 28 | H.I.F選抜試験でプロデュースを開始する | 获得スター性 **+5%**（star_permil_up lv1） | 同上 |
| 29 | 選抜試験を進める | +10% | |
| 30 | 選抜試験第1回を突破 | +15% | |
| 31 | 第2回を突破 | +20% | |
| 32 | 第3回を突破 | +25% | |
| 33 | 選抜試験をクリア | +30% | |
| 34 | 本戦を進める | +35% | |
| 35 | 本戦を進める | +40% | |
| 36 | 本戦で優勝する | **+50%**（lv9，上限） | |
| 37 | 一番星になる | +50% 维持；**Pドリンク所持上限+1** | |
| （常驻 Lv20+） | | 試験・オーディション時のスコアボーナスを +50%（`audition_parameter_bonus_multiple` lv7）、初期Pポイント+30、最大体力+2、獲得スキルカード再抽選回数+3、スキルカード除去回数+1 | |

网络攻略把这个 +50% 称为「信頼度（信赖度）を上げることで最大+50%」，即同一件事。[网络: game8 785067 摘要]

`star_permil_up` 逐级取值：50/100/150/200/250/300/350/400/500‰。 [确认: `ProduceEffect p_effect-star_permil_up-*`]

---

## 2. Produce 设置差异（`ProduceSetting`）

| 字段 | p_setting-7（選抜） | p_setting-8（本戦） | p_setting-6（初レジェンド） | p_setting-5（NIAマスター） | 含义 |
|---|---|---|---|---|---|
| refreshStaminaRecoveryPermil | **500** | **500** | 700 | 700 | 「休む」体力回复 50%（其他剧本 70%） |
| beforeAuditionRefreshStaminaRecoveryPermil | 500 | 500 | 700 | 500 | 试验前休整回复 50% |
| stepSkipStaminaRecoveryPermil | 250 | 250 | 250 | 250 | 跳过回复 25% |
| produceDrinkPossessLimit / MaxLimit | 3 / 4 | 3 / 4 | 3 / 4 | 3 / 4 | 饮料上限 3（親愛度37 +1 → 4） |
| customizeProduceCardCount | 2 | 2 | 2 | 2 | 可自定义卡数 |
| stepIntervalUpgradeProduceCardCount | 1 | 1 | 1 | 1 | 间歇强化卡数 |
| stepIntervalCustomizeProduceCardCount | 2 | 2 | 2 | 2 | 间歇自定义卡数 |
| maxLegendProduceCardCount | 1 | 1 | 1 | 0 | 可带 1 张传说卡 |
| produceAuditionTrendAssessmentPermilUpper/Lower | 110/110 | 110/110 | 110/110 | 110/110 | 试验前「趋势评估」±11% |
| stepCustomizeStartAlertProducePointThreshold | 49 | 49 | 49 | 39 | |
| continueCount | 3 | 3 | 3 | 3 | 试验失败可续 3 次 |

[确认: `ProduceSetting.yaml` 全字段]

`Produce.maxRefreshCount: 0`（选拔/本战都没有 NIA 的「刷新」次数）、`baseStepLevel: 1`。[确认: `Produce`]

---

## 3. 周（日）程表

### 3.1 選抜試験（produce-007，20 步）

**试验固定位置**（由主数据的 3 个 stepType + 网络确认）：

| 日 | 类型 | 说明 | 来源 |
|---|---|---|---|
| 1 | 开场事件 | 『H.I.F』开幕，获得 **H.I.Fワッペン**（`pitem_00-3-265-0`） | `ProduceStepEventDetail event-detail-p_story-003-produce-007-opening-1`（produceEffect `produce_reward-...-pitem_00-3-265-0`） |
| 1~6 | 自由行动 | 授業事件池 `before_1st`（「获得卡」型） | `ProduceStepEventDetail school-*-produce_007-*-before_1st-*` |
| 7 | **選抜試験1**（`ProduceStepType_AuditionMid1`） | 通过后：随机删除 2 张「基本」卡 + 选择获得 1 个カスタムPアイテム | `event-detail-p_story-003-produce-007-after_audition_mid1-1`（`produce_card_delete-...-starter-random-02_02`, `produce_reward_set-p_rd-item_set-produce_007-customize_item-select-01_01`） |
| 8~12 | 自由行动 | 活動支給事件池 `before_2nd` | `event-detail-activity-003-produce_007-before_2nd-*` |
| 13 | **選抜試験2**（`AuditionMid2`） | 通过后：随机删除 2 张「基本」卡 + 选择升级カスタムPアイテム | `...after_audition_mid2-1`（`produce_customize_item_upgrade-select-01_01`） |
| 14~19 | 自由行动 | 授業池 `before_3rd`（「セレクトチェンジ」型）+ 活動支給池 `before_3rd` | 同上 |
| 20 | **選抜試験3**（`AuditionFinal`） | 通过后：选择升级カスタムPアイテム；生成選抜試験メモリー | `...after_audition_final-1` |

网络攻略（game8 推荐日程，[网络: game8 783836 搜索摘要]）给出的 20 日：
1 差し入れ / 2 レッスン / 3 授業 / 4 レッスン / 5 おでかけ(50P) / 6 授業 / **7 試験1（目标 15,000+）** / 8 おでかけ or 差し入れ / 9 レッスン / 10 授業 / 11 レッスン / 12 相談(或特別指導) / **13 試験2（目标 150,000+）** / 14 おでかけ or 差し入れ / 15 レッスン / 16 (14日未选的一项) / 17 授業 / 18 レッスン / 19 相談 / **20 試験3（目标 400,000+）**。
另有摘要称「HIF では 8 レッスン、6 授業」。[网络: 同上]

> [推断] 试验日 7/13/20 是确定的（3 段 6+6+7 步）。每个自由日提供哪些候选（レッスン×3 / 授業 / おでかけ / 差し入れ / 活動支給 / 相談 / 特別指導 / 休む）的**逐日菜单**在主数据里不是表驱动的（初/NIA 也一样，由客户端代码决定），模拟器应先按上表的推荐日程做成可配置的固定日程。主数据中 `ProduceWeekMotion` 只给出 HIF 使用 week number 11~20 的演出，`enableOpenLesson` 在 11/12 为 true，其余 false，这只是演出标记，不是日程。

### 3.2 本戦（produce-008，9 步）

| 步 | 类型 | 来源 |
|---|---|---|
| 1~6 | 准备（授業/レッスン/おでかけ/差し入れ/相談/特別指導/活動支給 等） | 授業池 `event-detail-school-*-produce_008-*`（无 before 前缀，只有 1 池）；活動支給池 `event-detail-activity-003-produce_008-01/02` |
| 7 | **Round1**（`ProduceStepType_AuditionMid1`，9 回合） | `ProduceStepAuditionDifficulty`（produce-008 Mid1）、`ProduceExamBattleConfig ...produce_008-01 turn=9` |
| 8 | **インターバル**（相談 + 特別指導 合体；Round1 结束事件 `after_audition_mid1` 发放道具集 `p_rd-item_set-produce_008-end_mid_audition-all`） | `HelpContent help-hif-produce-schedule-interval`; `event-detail-p_story-003-produce-008-after_audition_mid1-1`; [网络: game8] |
| 9 | **Round2**（`ProduceStepType_AuditionFinal`，12 回合） | `ProduceExamBattleConfig ...produce_008-02 turn=12` |

网络描述：「本戦は 9 プロシージャ構成、日1〜6 は準備活動、日7〜9 にラウンド1・2」「本戦はプレイヤーが選択できるスケジュールが3日目のおでかけまたは差し入れのみ」（即准备期大部分为固定行动，只有第 3 天可选おでかけ/差し入れ）。[网络: appmatch/game8 搜索摘要] [推断] 具体固定行动序列未取得，建议实现为可配置。

---

## 4. 自由行动与数值

### 4.1 レッスン = 公開レッスン（`ProduceStepOpenLesson`，**无卡牌小游戏，直接加数值**）

HIF 的レッスン走 `ProduceStepType_OpenLesson{Vocal,Dance,Visual}{Normal,Sp}[Star]` 12 种 stepType（`ProduceStepTransition` 中仅对 produce-007/008 定义）。每次公开课要选：主属性（Vo/Da/Vi）、副属性（另两项之一，id 中的 `sub_da/sub_vi/sub_vo`）、以及「パラメータ型」或「スター型（☆标记）」。SP 随机出现（基础发生率 + HIF ボーナス最多 +5%）。

| 阶段（id 段） | 型 | 体力 | 主属性 | 副属性 | スター性 |
|---|---|---|---|---|---|
| produce_007-01（试验1前） | parameter 通常 | 6 | +60 | +20 | +5 |
| | parameter SP | 8 | +80 | +50 | +10 |
| | star 通常 | 6 | +50 | +10 | +20 |
| | star SP | 8 | +60 | +20 | +30 |
| produce_007-02（试验2前） | parameter 通常 / SP | 6 / 8 | 80 / 100 | 30 / 60 | 5 / 10 |
| | star 通常 / SP | 6 / 8 | 70 / 80 | 10 / 20 | 20 / 30 |
| produce_007-03（试验3前） | parameter 通常 / SP | 6 / 8 | 100 / 120 | 40 / 70 | 5 / 10 |
| | star 通常 / SP | 6 / 8 | 90 / 100 | 10 / 20 | 20 / 30 |
| produce_007-04（[推断] 本战准备期） | parameter 通常 / SP | 6 / 8 | 120 / 140 | 50 / 80 | 5 / 10 |
| | star 通常 / SP | 6 / 8 | 110 / 120 | 10 / 20 | 20 / 30 |

[确认: `ProduceStepOpenLesson.{stamina,mainParameter,subParameter,star}` 全 48 行]
- 网络确认「公開レッスンは SP で主+80/副+50、通常で主+60/副+20」「SPレッスン体力8、授業体力5」。[网络: game8 784794 / note 摘要]
- 表中数值是**基础值**，再乘以偶像成长率（`IdolCard.produce*GrowthRatePermil`、HIF ボーナス的パラメータボーナス%、TrueEnd ボーナス等）；スター性乘以 `star_permil_up`（親愛度）后**向下取整**（网络：「親愛度37で5日の通常レッスンを行うと獲得スター性が7となるため小数点以下は切り捨て」→ 5×1.5=7.5→7）。[网络: wikiwiki 摘要] [推断: 成长率是否作用于副属性同样适用]
- SP 发生率：`p_effect-lesson_sp_change_rate_permil_addition-00X0`（HIF ボーナス +1%~+5%）。[确认: `ProduceGrowthPanel`]
- HIF 没有 `追い込みレッスン`（`ProduceStepLesson` 的 hard 行只属于 001/002/produce_006 系列，HIF 使用 OpenLesson 表）。[确认: `ProduceStepLesson` id 前缀统计]

### 4.2 授業（`ProduceStepType_EventSchool`）

体力 5。三个选项（每个属性一套）：

| 阶段 | 选项 | 效果 | 来源 |
|---|---|---|---|
| 選抜 before_1st | plan 专属 ×2 | 主属性 **+120**，「集中/好調（センス）」「やる気/好印象（ロジック）」「強気/全力（アノマリー）」关系的技能卡 **选择获得** 1 张 | `ProduceStepEventSuggestion p_s_e_s-event-detail-produce_007-school-*-before_1st-plan*-get-*`（stamina 5） |
| | common | 主属性 +120，非トラブル卡 1 张セレクトチェンジ；附带获得 **眠気**（`produceCardId: p_card-00-acc-0_002`） | `...before_1st-common-change_select` |
| 選抜 before_3rd | plan 专属 ×2 | 主属性 **+150**，非トラブル卡 1 张 → 换成同流派关系卡（セレクトチェンジ） | `...before_3rd-plan*-change_select-*` |
| | common | +150，任意セレクトチェンジ + 眠気 | |
| 本戦 | plan 专属 ×2 / common | 主属性 **+180**，セレクトチェンジ（common 附带眠気） | `...produce_008-school-*` |

[确认: `ProduceStepEventSuggestion`/`ProduceStepEventDetail`] 注：主数据中没有 `before_2nd` 的授業池（试验1→试验2之间的授業若存在，则复用 before_3rd 池或由代码决定）[推断]。

### 4.3 活動支給（`ProduceStepType_EventActivity`）

三个选项（選抜 before_2nd / before_3rd、本戦各一套，内容一致）：

| 选项 | 代价 | 效果 | 来源 |
|---|---|---|---|
| 上 | **Pポイント 50** | 最大体力の 60% 回复 + 选择获得 Pドリンク + 选择获得 **强化済み**技能卡 + 选择获得技能卡（=2 张） | `p_s_e_s-event-detail-produce_007-activity-before_2nd-01`（producePoint 50） |
| 中 | 获得 **眠気** | 同上（2 张卡） | `...-02`（produceCardId 眠気） |
| 下 | 无 | 60% 体力 + 选择 Pドリンク + 选择获得技能卡 1 张 | `...-03` |

[确认: 同上] 网络：「おでかけの上段は 50P でスキルカード 2 枚獲得」「活動支給は HIF 中约 5 回」。[网络: note syato_monami 摘要]

### 4.4 おでかけ（Business）、差し入れ（FanPresent/Present）、休む（Refresh）

- `ProduceStepTransition` 中 HIF 定义了 `EventActivity`、`FanPresent`、`Refresh`；`Business`/`EventSchool`/`Present` 使用通用行（`produceIds: []`）。[确认]
- カスタムPアイテム触发器中存在「おでかけ終了時」「差し入れ終了時」「相談選択時」「レッスン終了時」四类，证明 HIF 中这四种行动都存在。[确认: `ProduceCustomizeItem.produceDescriptions`]
- 休む：体力回复 **50%**（`refreshStaminaRecoveryPermil: 500`）。[确认]
- おでかけ的具体奖励表：主数据中 business 事件表只有 produce_004/005（NIA）的 1728 行各一套（例：ボーカル+80 + 强化済み关系卡获得，附带ファン投票数），HIF 没有专属行 → [推断] HIF 复用 NIA 表（去掉投票数）或由代码生成；网络称「おでかけは体力回復もできる」「おでかけ、休む、特別指導、カスタマイズはクリア恩恵少なめ」。[网络: game8 摘要]
- 差し入れ：支援卡事件（`ProduceEventSupportCard`），网络推荐「差し入れ・ドリンク編成」。[网络: game8]

### 4.5 相談（商店）与 インターバル

- 相談：与初/NIA 相同的购买/强化/删除。HIF ボーナス可使「相談のスキルカード」最多 **30% 折扣**；亲密度27+「相談リフレッシュ回数+1」。[确认: `ProduceGrowthPanel` sheet-hif-09; `CharacterDearnessLevel`]
- カスタムPアイテム的「人形」系提供「相談のPドリンク 50% 割引」「スキルカード強化 50% 割引」「削除 50% 割引」「スキルカード 50% 割引」。[确认: `ProduceCustomizeItem`]
- **インターバル（本战 Round1 与 Round2 之间）**：`HelpInfo.type ScheduleInterval`；网络：「相談＋特別指導が組み合わさった内容、強化やドリンクの補充ができるが **削除はできない**」「右下の回復から Pポイント10 で体力2 回復」「ラウンド1 前の相談で P ポイントを温存」。Round1 结束事件发放 `p_rd-item_set-produce_008-end_mid_audition-all`（pickRange All）。[确认: `ProduceEffect`] [网络: note 摘要]
- Localization 有 `produce.interval.reroll_sheet`、`setting.produce.exit_interval_confirm/reroll_interval_confirm`，说明间歇有「リフレッシュ（重抽）」与「終了」操作。[确认: `Localization.yaml`]

### 4.6 カスタムPアイテム（HIF 专用）

结构（每个プラン一套，`ProduceCustomizeItem` 共 180 行）：

| 层 | 名称 | 触发 | 效果 | 试验开始时效果 |
|---|---|---|---|---|
| 1（base，试验1通过后选 1） | ポーチ（赤/緑/黄） | レッスン終了時 | 赤: 体力回復6 / 緑: Pポイント+30 / 黄: ランダムな特定のPドリンク | センス: 集中+2・好調2ターン（×2 回）；ロジック: 好印象+2・やる気+2；アノマリー: 全カードパラメータ値+4 |
| 2（试验2通过后升级） | くま/人形/ロボ/もじゃ/インコ/うさぎ … | レッスン終了時 / 相談選択時 / 差し入れ終了時 / おでかけ終了時 | 例：人形（赤）「相談選択時 体力回復12・Pポイント+40」、ロボ（赤）「差し入れ終了時 体力12・セレクトチェンジ」 | 集中+3・好調3T（×2）或 集中+6・好調6T（×1） |
| 3（试验3通过后升级，isTerminal） | 花/リボン/メダル/羽 ＋ 上记 | 同上 | 例：花人形（赤）「相談のPドリンク 50%割引」、羽くま（赤）「スキルカード（高確率でSSR）を選択して獲得」、リボンもじゃ「スキルカードをコピー」 | 「以降の試験開始時」集中+6・好調6T（・固定元気+6） |

[确认: `ProduceCustomizeItem.{name,produceDescriptions,isBase,isTerminal}`；升级事件 `p_effect-produce_customize_item_upgrade-select-01_01`]

### 4.7 H.I.F 専用 P アイテム

| id | 名称 | 效果 | 来源 |
|---|---|---|---|
| pitem_00-3-265-0 | **H.I.Fワッペン** | スキルカード獲得時、スター性+10（プロデュース中 **20 回**） | `ProduceItem`（fireLimit 20, trigger `p_trigger-get_produce_card`, effect `p_effect-star_addition-0010_0010`） |
| pitem_01-3-266/267（センス）、02-3-268/269（ロジック）、03-3-270/271（アノマリー） | **H.I.F応援棒（紫/緑/黄/赤/青/桃）** | 試験開始時、山札のスキルカードが **22 枚** になるように「基本」を含むカードを山札のランダムな位置に生成 | `ProduceItem`, `ProduceExamEffect e_effect-exam_card_create_search-...-22_22`, 生成池 `ProduceCardPool p_random_pool-produce_007-create_set-*` |

生成池内容（例）：parameter_buff 池 = `p_card-01-act-0_022`(20) / `01-act-0_023`(40) / `01-men-0_024`(20) / `01-men-0_025`(20) / `01-men-0_029`(20)；review 池 = `02-men-0_035`(25)/`02-act-0_032`(50)/`02-men-0_034`(50)/`02-men-0_036`(25)；其余见 `ProduceCardPool`。[确认]
网络：「HIFワッペンは 20 回発動、選抜+本戦合計で 20 枚獲得を目指す」「残りのバッジ回数は本戦に持ち越す」。[网络: game8 785067]

---

## 5. スター性（明星性）系统

| 项目 | 值 | 来源 |
|---|---|---|
| 资源类型 | `ProduceEffectType_StarAddition`（加算）、`ProduceEffectType_StarPermilUp`（获得量倍率） | `ProduceEffect` |
| 获得途径 | ① 公開レッスン（5/10/20/30，见 §4.1）② H.I.Fワッペン（每获得 1 张卡 +10，20 次）③ 试验分数换算（见 §6.4 `starScoreBonusBaseLine`）④ 支援卡/事件（略） | `ProduceStepOpenLesson.star`, `ProduceItem`, `ProduceStepAuditionDifficulty.starScoreBonusBaseLine` |
| 获得倍率 | 親愛度 28~36：+5%…+50%（`star_permil_up`），取整向下 | `CharacterDearnessLevel` |
| 作用 | 「スター性が高いほどスコアボーナスの値も高くなります」（试验内的スコアボーナス随スター性上升） + 直接计入最终评价（×7.5，[推断]） | `ProduceNavigation p_navi-produce_group-003-lose #1`; [网络] |
| 上限 | 网络：獲得できるスター性の上限 **1335**；親愛度37 时 Round2 前最大 **1110**，Round2 后最多再 **+225** → 1335 | [网络: game8 785067; 知恵袋摘要] |
| 目标 | 選抜終了時 700+（低于 700 说明ワッペン使用不足）；本战 1300+ | [网络: game8 785067] |

试验分数→スター性 上限（网络实测）：試験1 ≈14,000~15,000 分封顶、試験2 150,000、試験3 390,000~400,000；Round1 50 万分 ≈ +180 スター性、Round2 35 万分 ≈ +100。[网络: x.com/TimeMagicWitch 摘要; note fit_bee8608 摘要]

[推断] 对照主数据 `starScoreBonusBaseLine` = 50/200/400（選抜1/2/3）、600/800（本战 R1/R2），与 `baseScore` = 6,050/49,800/136,350、406,150/608,800：封顶分数约为 baseScore 的 2.3~3.0 倍。建议实现：
`star_gain = floor( starScoreBonusBaseLine × clamp(score / cap, 0, 1) × (1 + star_permil_up/1000) )`，cap 取上表实测值（14,000 / 150,000 / 390,000 / R1、R2 待定），其中 starScoreBonusBaseLine 与实测「R1 +180 @ 50万」的比例（600×0.5M/1.4M≈214，×1.5 亲密度倍率不符）表明真实公式可能不是线性或 baseline 含义不同——**列为开放问题**。

---

## 6. 试验（選抜試験 / 本戦）规则

### 6.1 通用引擎参数（与初/NIA 相同）

`ExamSetting p_exam_setting-1`（所有 Produce 共用）：handLimit 5、turnStartDistribute 3（每回合发 3 张）、holdLimit 2、examTurnEndRecoveryStamina 2、examParameterBuffPermil 1500（好調 +50%）、examConcentrationLessonValueMultiplePermil 2000、examFullPowerLessonValueMultiplePermil 3000、examStaminaConsumptionDownPermil 500、examBlockAddDownPermil 667 等。[确认: `ExamSetting`]

### 6.2 各场试验的难度参数（`ProduceStepAuditionDifficulty`，产出 `produceId ∈ {produce-007, produce-008}`）

数值按**试验配置类型**（偶像卡的 examEffectType/属性倾向 → `vovi/vida/davo/davi/voda` 等 BattleConfig）略有差异；下表给出两组代表值（`vovi-01`/`davi-01` 组 与 `vida-03`/`davo-03`/`voda-03` 组）：

| 试验 | stepType | rankThreshold（通过名次） | parameterBaseLine | baseScore（vovi/davi 组） | baseScore（vida/davo/voda-03 组） | isStaticNpcScore | starScoreBonusBaseLine |
|---|---|---|---|---|---|---|---|
| 選抜1 | AuditionMid1 | **2** | 150 | 6,050 | 5,950 | false | 50 |
| 選抜2 | AuditionMid2 | **2** | 300 | 49,800 | 49,150 | false | 200 |
| 選抜3 | AuditionFinal | **2** | 550 / 500 | 136,350 | 134,500 | false | 400 |
| 本戦 R1 | AuditionMid1 | **3** | 1000 / 950 | 406,150 | 400,450 | **true** | 600 |
| 本戦 R2 | AuditionFinal | **1** | 1000 / 950 | 608,800 | 600,250 | **true** | 800 |

[确认: `ProduceStepAuditionDifficulty`（每偶像/每偶像卡 107 行 × 5 步）] `forceEndScore=0`、`voteCount=0`、`auditionType=Unknown`、`dearnessLevel=0`（无 NIA 式难度分级）。

对照：初レジェンド 中间 rank3/baseScore 12,600、最终 rank3/176,350；NIA マスター Final VeryHard rank1/97,000（有投票数）。[确认]

**通过条件**（结合主数据）：
- 選抜1~3：名次 ≤ 2（`rankThreshold 2`），即分数 ≥ 「border」NPC。Localization：「ライバルとパフォーマンスで対決します。突破ライン超えると選抜試験突破となります。」[确认: `Localization produce.hif.audition.qualify.description`]
- 本战 R1：名次 ≤ 3（3 人赛，等于不淘汰；[推断] R1 只影响合计分）；R2：**名次 1**（合计分第一 = 一番星 = True End）。网络：「ラウンド1とラウンド2の合計値が最も高かったアイドルが1位、一番星」「ラウンド1は9ターン、総スコアを **1.2倍**（小数点以下切り捨て）してラウンド1獲得点として登録、ラウンド2は12ターンでそのまま」。[网络: wikiwiki HIF/基本情報 摘要]
- 失败：`ProduceSplitAdv ProduceAdvType_ProduceResultFailedMid1/Mid2/Final`（选拔任一场失败即 Produce 失败）；本战有 `FailedMid1`/`FailedFinal`。[确认: `ProduceSplitAdv`]

### 6.3 对手 NPC（`ProduceExamBattleNpcGroup` / `ProduceExamBattleNpcMob`）

每组 NPC 行字段：`scoreMin/scoreMax`（终分区间）、`vocal/dance/visualPermil`（分数按属性分配）、`op/mid/edScorePermil`（前/中/后段回合的分数分布）。

**選抜試験（5 人赛）**，以 amao 为例：

| 试验 | #1（顶尖） | #2 = **border**（`npc_hif_border`, isBorder=true） | #3~#5 |
|---|---|---|---|
| 1 | 風宮すずな 6,035 固定 (op/mid/ed 200/250/550) | 6,035 固定 (340/330/330) | 四谷リリ 1,963~2,963；荻野なのか 1,763~3,163；キャンディ・リズミカ 2,263~2,663 |
| 2 | Nebula Note 49,806 固定 | 49,806 | 8,519~18,519 / 6,519~20,519 ×2 |
| 3 | PRINCESS DOMINION 136,347 固定 | 136,347 | 31,843~43,843 / 33,843~41,843 / 27,843~47,843 |

其他偶像 border：5,963 / 49,168 / 134,524（vida/davo/voda 组，例 hrnm、hski、hume、kllj、shro）；6,035 / 49,806 / 136,347（vovi/davi 组，例 amao、hmsz、kcna、ssmk、ttmr）。选拔 3 的 #1 有时是 **命名角色**（atbm 燕、shro 広、hski 咲季）。[确认: `ProduceExamBattleNpcGroup` p_npc_group-<idol>-produce_007-0X]

→ 实现：border 与 #1 分数相同且固定；玩家分数 ≥ border 即名次 ≤ 2 → 通过（[推断] 平分判定按 ≥）。**通过线 = baseScore 附近（6,050 vs 6,035）**，因此 `baseScore` 可视为「突破ライン」。

**本戦（3 人赛，isStaticNpcScore=true，命名对手）**：

| 玩家偶像 | R1 #1 | R1 #2 | R2 #1 | R2 #2 |
|---|---|---|---|---|
| amao | 十王星南(jsna) 403,161~409,161 | 姫崎莉波(hrnm) 301,182~316,182 | jsna 598,779~618,779 | hrnm 437,672~487,672 |
| hmsz | jsna 同上 | 月村手毬(ttmr) 301,182~316,182 | jsna 同上 | ttmr 437,672~477,672 |
| hrnm | jsna 397,457~403,457 | amao 299,847~308,847 | jsna 590,229~610,229 | amao 441,174~471,174 |
| hski | **花海佑芽(hume)** 388,457~412,457 | jsna 301,347~307,347 | hume 560,229~640,229 | jsna 446,174~466,174 |
| hume | jsna 397,457~403,457 | hski 299,847~308,847 | jsna 590,229~610,229 | hski 441,174~471,174 |
| kcna | jsna 403,161~409,161 | 篠澤広(shro) 295,182~322,182 | jsna 598,779~618,779 | shro 417,672~507,672 |
| kllj | jsna 397,457~403,457 | hski 299,847~308,847 | jsna 590,229~610,229 | hski 441,174~471,174 |
| shro | jsna 397,457~403,457 | kcna 293,847~314,847 | jsna 590,229~610,229 | kcna 421,174~491,174 |
| ssmk | jsna 403,161~409,161 | 雨夜燕(atbm) 304,182~313,182 | jsna 598,779~618,779 | atbm 447,672~477,672 |
| ttmr | jsna 403,161~409,161 | hmsz 304,182~313,182 | jsna 598,779~618,779 | hmsz 447,672~477,672 |

[确认: `ProduceExamBattleNpcGroup` p_npc_group-<idol>-produce_008-01/02] 对手属性配比示例：jsna 350/350/300、op/mid/ed 330/330/340；hume 340/340/320、200/200/600（后段爆发）；shro 400/330/270、100/200/700。
网络：「星南は 2 ラウンド合計でおおよそ 110 万」（≈ 405k×1.2 + 610k = 1.096M，与主数据吻合）。[网络: wikiwiki 摘要]
`ProduceStepAuditionRivalActor`：本战 Final 的 3D 对手模型为 jsna（hski 时为 hume）。[确认]

### 6.4 回合数与属性→分数换算（`ProduceExamBattleConfig` / `ProduceExamBattleScoreConfig`）

| 试验 | turn | vocal/dance/visual 基准（vovi-01 组，Vo 主） | （davi-01 组，Da 主） |
|---|---|---|---|
| 選抜1 | **10** | 311 / 173 / 207 | 173 / 311 / 207 |
| 選抜2 | **12** | 613 / 341 / 409 | 341 / 613 / 409 |
| 選抜3 | **12** | 1,035 / 575 / 690 | 575 / 1,035 / 690 |
| 本戦 R1 | **9** | 1,960 / 1,089 / 1,307 | 1,089 / 1,960 / 1,307 |
| 本戦 R2 | **12** | 1,960 / 1,089 / 1,307 | 同上 |

[确认: `ProduceExamBattleConfig` 30 行；`vocalExcellent/Bad` 全 0]。对照：NIA マスター Final VeryHard 12 回合 1,627/618/1,008；初レジェンド Final 12 回合 1,913/1,063/1,276。

回合的 Vo/Da/Vi 分配（每回合属性）与 NIA 一致由 BattleConfig 名（vovi/vida/davo…）的顺序与比例决定 [推断: 具体逐回合序列由客户端生成，沿用 NIA 实现]。

**分数换算表**（`ProduceExamBattleScoreConfig`，每行 parameter 断点→千分比，线性插值，和 NIA 结构一致）例 `vovi-01-produce_007-01`：

| parameter | vocalPermil | dancePermil | visualPermil |
|---|---|---|---|
| 0 | 536 | 36 | 268 |
| 173 | 1,112 | 612 | 845 |
| 207 | 1,226 | 689 | 958 |
| 311 | 1,572 | 922 | 1,191 |
| 10000 | 23,321 | 22,671 | 22,940 |

`vovi-01-produce_008-01/02`：0→536/36/268；1,089→4,166/3,666/3,898；1,307→4,892/4,155/4,625；1,960→7,069/5,621/6,090；10000→25,116/23,668/24,137。[确认] 对照 `produce_006_final`：0→964/64/482 … 10000→45,117/42,551/43,387（初レジェンド系数约为 HIF 的 1.8 倍，说明 HIF 的高分主要靠回合数/加成而非系数）。

### 6.5 试验内的固定 Gimmick

所有 HIF 试验的 `produceExamGimmickEffectGroupId` = `p_exam_gimmick-produce_00X-0Y-<style>`，内容全部只有 1 条：`startTurn 99`, `e_effect-exam_block-0001`「元気+1」（priority 1）→ **实质上无 Gimmick**（startTurn 99 永不触发）。对照初レジェンド/NIA 有「好調が N ターン以上の場合…」的分段 buff。[确认: `ProduceExamGimmickEffectGroup`]

### 6.6 スコアボーナス（分数加成）

- 親愛度 20+ 常驻：「試験・オーディション時のスコアボーナスを 50% 増加」。[确认: `CharacterDearnessLevel` → `audition_parameter_bonus_multiple` lv7]
- NIA 式「パラメータボーナス」在 HIF 中被「スター性」补充：`p_navi-...-lose #1`「スター性が高いほどスコアボーナスの値も高くなります」。具体公式未在主数据中（可能在代码）。[推断] 建议：`scoreBonus% = f(parameter) + g(star)`，g 单调递增，g(1335) 为上限；实现为可调表。

---

## 7. 最终评价（評価値）与等级

### 7.1 等级阈值（`ProduceGrade`，produce_group-003）

| 等级 | 阈值 | 等级 | 阈值 |
|---|---|---|---|
| F | 0 | S | 13,000 |
| E | 1,000 | S+ | 14,500 |
| D | 2,000 | SS | 16,000 |
| C | 3,000 | SS+ | 18,000 |
| C+ | 4,500 | SSS | 20,000 |
| B | 6,000 | SSS+ | 23,000 |
| B+ | 8,000 | **SSSS (S4)** | **26,000** |
| A | 10,000 | **SSSS+ (S4+)** | **30,000** |
| A+ | 11,500 | **SSSSS (S5)** | **35,000** |

[确认: `ProduceGrade`] 与 produce_group-001（初）到 S4=26,000 完全相同，HIF 额外追加 S4+ 30,000 与 S5 35,000；NIA 到 SSS+ 23,000。

### 7.2 評価値 计算（社区推定，主数据未包含）

社区推定公式 [网络: note fit_bee8608 / 知恵袋 q10328370305 搜索摘要]：

```
評価値 = 合計パラメータ × 2 + スター性 × 7.5 + 本戦スコア換算値 − 2000
本戦スコア換算値:
  Round1: スコア 30万～70万 → (score − 300,000) × 0.01   （例: 50万 → +2,000）
          70万(減衰開始)～140万(上限)  係数逓減（具体未取得）
  Round2: スコア 0～60万 → 0
          60万～150万 → (score − 600,000) × 0.01 [推断]
          150万(減衰)～240万(上限)
  選抜試験 3 回のスコアは評価値に直接寄与しない（スター性経由のみ）[网络: 知恵袋 q12328749712 摘要]
```
校核：SSS 目安「合計パラ 6,000、スター性 1,100、R1 50万、R2 35万」→ 12,000 + 8,250 + 2,000 + 0 − 2,000 = 20,250 ≈ 20,000 ✓。S4+ 目安「合計 6,000、スター性 1,335、R1 70万、R2 150万」→ 12,000 + 10,012 + 4,000 + 9,000 − 2,000 = 33,012 ≥ 30,000 ✓（若 R2 系数 0.01）。[推断: R2 段斜率与减衰区间为本文推算]

另一说（game8 784794）：S4+ 目安 = 選抜1 15,000 / 選抜2 150,000 / 選抜3 400,000 / 本戦1 700,000 / 本戦2 1,500,000 / 最終ステータス合計 6000 / スター性 1335。[网络]

### 7.3 结局与 True End

- `ProduceLiveEvaluation`: produce-008 全员 `ProduceLiveType_TrueEnd`（本战优胜 → TrueEnd 演出 `adv_presult_003_final-true`）。选拔通关 = `ProduceLiveType_A`（`adv_presult_003_selection-true`）。[确认]
- Achievement「True End : H.I.F をみる」= `achieve-p_idol-<idol>-000-2`（isTrueEndAchievement）。[确认: `Achievement`]
- `CharacterTrueEndBonus`（produceType HIF）：达成后该偶像在 HIF 中获得初始属性/成长率加成，例 amao Vi+15、Vo/Da/Vi 成长率 +1%/+3%/+1%；hski Vo+20 Da+25 Vi+30、体力+1；hume 三围各 +25、Vi 成长 +3%。[确认: `CharacterTrueEndBonus`]

---

## 8. メモリー与 H.I.F 専用アビリティ

- 選抜試験通关生成「選抜試験メモリー」，本战必须用它进入；`Produce.selectionMemoryEmbedProduceCardId = exam_contest_embed_produce_card-produce_008`、`ProduceSetting.selectionMemoryNeedProduceCardCount 1`。[确认]
- `ExamContestEmbedProduceCard exam_contest_embed_produce_card-produce_008`：按流派内嵌卡（例 ExamParameterBuff: `01-act-0_022, 01-act-0_023 ×2, 01-men-0_024, 01-men-0_025, 01-men-0_029`；ExamFullPower: `03-act-0_047, 03-act-0_048 ×2, 03-men-0_049 ×2, 03-men-0_050`）。[确认]
- **H.I.F 専用アビリティ**（`ProduceSkill p_memory_skill-common-hatsuboshi_idol_festival-...`，105 条，SkillRarity_R，evaluation 3）：三类模板，均「H.I.F専用 重複発動不可」：
  1. 「試験ごとに、以降 2 回まで、<卡名>使用後、スキルカード使用数追加+1」（银/低费卡，例 軽い足取り、深呼吸、ファンサ、きらきら紙吹雪 …）
  2. 「試験ごとに、以降 1 回まで、<卡名>使用後、スキルカード使用数追加+1・スキルカードを引く」（例 飛躍、精一杯、眼力、汗と成長、リズミカル …）
  3. 「試験ごとに、以降 1 回まで、<卡名>使用後、ランダムな山札か捨札の眠気を除外に移動」（例 ひと呼吸、ペース配分、願いの力、盛り上げ上手、モチベ …）
  [确认: `ProduceSkill`/`MemoryAbility`/`ProduceExamTrigger e_trigger-exam_card_play_after-...-for_hif_memory`] 网络：「H.I.F アビリティは対象スキルが等確率で抽選、対象は銀・金スキル、無料スキルと眠気生成スキルは含まれない」。[网络: note fit_bee8608 摘要]
- 网络：「本戦は選抜試験メモリーで挑む前提、選抜メモリーが弱いと優勝は極めて困難」「良いメモリーができたら本戦だけを繰り返せる」「本戦後にメモリー抽選（SSS 厳選）」。[网络: game8/appgamelog 摘要]
- 配布 `MemoryGift memory_gift-20260516-hif-plan1~3-*`「H.I.F応援メモリー（シュプレヒコール＋ 等）」grade SSS。[确认]

---

## 9. 一番星（プリマステラ, Prima Stella）

| 项目 | 值 | 来源 |
|---|---|---|
| 解锁条件 | `Setting.idolCardPrimaStellaLevelLimitRank: 6`（特訓 6 段）、`idolCardPrimaStellaDearnessLevel: 37` | `Setting.yaml` |
| 消耗 | `ConsumptionSet cs-idol_card_prima_stella-<card>`：プリマステラノート×1（`item-primastellamaterial-common-001`）+ 該当偶像の「一番星の光」×1（`item-primastellamaterial-idol_<id>-001`） | `ConsumptionSet`, `Item` |
| 「一番星の光」入手 | Achievement `achieve-p_idol-<id>-025`「H.I.F の最終試験に合格して評価 **S4+ 以上** を獲得」（threshold 1）或 `-026`「最終試験に **120 回** 合格」 | `AchievementProgress` |
| 网络综述 | 本戦優勝 + 親愛度37 + 特訓6段階 + HIF最終試験120回合格 + 評価S4以上（120 回は選抜・本戦どちらもカウント） | [网络: appgamelog gkmas-prima-stella-idol 摘要] |
| 效果 | `IdolCardPrimaStellaProduceSkill` → `p_primastella_skill-...-final-...`「プロデュース開始時、<固有名>一番星を獲得（H.I.F本戦専用）」，即本战开始时获得一张专属「一番星」卡（`p_card-0X-ido-100_0YY`） | `IdolCardPrimaStellaProduceSkill`, `ProduceSkill` |
| 对应卡（10 张） | amao 見て→舞台で輝く一番星(01-ido-100_040)；ssmk 背中を押す(100_044)；kcna 皆に愛される(100_045)；hski 先陣を切る(02-ido-100_037)；hrnm 笑顔を生み出す(100_041)；hume 証明し続ける(100_046)；ttmr 高みへ羽ばたく(03-ido-100_038)；shro 奇跡を起こした(100_042)；kllj 勇気を届ける(100_043)；hmsz 星々を見下ろす(100_047) | 同上 |
| 对象卡 | 每偶像 1 张 SSR：i_card-amao-3-015 / hmsz-3-016 / hrnm-3-013 / hski-3-017 / hume-3-017 / kcna-3-014 / kllj-3-015 / shro-3-012 / ssmk-3-012 / ttmr-3-016 | `IdolCard.idolCardPrimaStellaProduceSkillId` |
| 成就 | `achieve-p_common-032`「P科首席：『一番星』解放を N 人達成」阈值 1/4/6/9/13 | `AchievementProgress` |

---

## 10. H.I.F ボーナス（成长面板，`ProduceGrowthPanelSheet produce_growth_panel_sheet-hif`）

解锁道具 `item-produce-produce_growth_panel_sheet_point-hif`「H.I.FボーナスPt」，来源为 HIF クリアミッション（`mission-group-mission_HIF_clear_1`：選抜試験完了 1/3 回 各 60Pt；各偶像本戦完了 20Pt；各偶像親愛度 30/31/33 各 10Pt）。[确认: `Mission`/`MissionProgress`]

| # | 面板 | Lv1 → Lv5/6 | 适用 | 每级 Pt |
|---|---|---|---|---|
| 1~3 | ボーカル/ダンス/ビジュアル上昇 + パラメータボーナス | +20/+2% → +100/+10%（5 级） | 全阶段 | 10/20/30/40/50 |
| 4 | 全属性 SPレッスン発生率 | +1% → +5%（5 级） | 全阶段 | 同上 |
| 5 | 試験前の体力回復量 | +5% → +15%（6 级：5/7/9/11/13/15） | 全阶段 | 10..60 |
| 6 | 全属性上限値 | +50 → +200（6 级：50/80/110/140/170/200） | **本戦のみ**（`ProduceSplitType_Final`） | 10..60 |
| 7 | Pポイント（初期） | +50 → +200（6 级：50/80/110/140/170/200） | **選抜のみ** | 10..60 |
| 8 | Pポイント（初期） | 同上 | **本戦のみ** | 10..60 |
| 9 | 相談のスキルカード割引 | 5% → 30%（6 级） | 全阶段 | 10..60 |

[确认: `ProduceGrowthPanel.{level,unlockItemQuantity,produceSplitType,produceEffectIds}`] 网络推荐解锁顺序：パラメータ上昇 → Pポイント（本戦側優先）→ SPレッスン発生率 → 割引/回復；上限值面板可后置（初始上限已 3000）。[网络: game8 784495 摘要]

---

## 11. 与 初 / N.I.A. 的差异总表

| 项目 | 初（produce-006 レジェンド） | N.I.A.（produce-005 マスター） | H.I.F（007+008） | 来源 |
|---|---|---|---|---|
| 步数 | 18 | 26（マスター）/27（プロ） | 20 + 9 | `Produce.steps` |
| 试验次数 | 2（中间+最终） | 3（各 3~4 档难度） | 3 + 2 轮 | `ProduceStepAuditionDifficulty` |
| 试验回合 | 10 / 12 | 9 / 12 / 12 | 10 / 12 / 12 / 9 / 12 | `ProduceExamBattleConfig` |
| 通过条件 | 名次 ≤ 3 | 名次 1（投票数制） | ≤2 / ≤2 / ≤2 / ≤3 / 1 | `rankThreshold` |
| 对手 | 随机 mob | 固定 NPC + 投票 | 選抜: mob + border；本戦: 命名对手、静态分数 | `NpcGroup.isStaticNpcScore` |
| Gimmick | 好調累积型 | パラメータ buff 型 | 无（占位） | `ProduceExamGimmickEffectGroup` |
| レッスン | 卡牌小游戏（含追い込み） | 自動レッスン（`ProduceStepSelfLesson` 80~150） | 公開レッスン（主+副+スター性，`ProduceStepOpenLesson`） | 各表 |
| 属性上限 | 3000 | 2600 | 3000（+200 面板） | `idolCardParameterGrowthLimit` |
| 休む回复 | 70% | 70% | **50%** | `ProduceSetting` |
| 新资源 | — | ファン投票数 | **スター性** | |
| 传说卡 | 1 | 0 | 1 | `maxLegendProduceCardCount` |
| 评价上限 | S4 (26,000) | SSS+ (23,000) | S5 (35,000) | `ProduceGrade` |
| 回忆 | 通常 | 通常 | 選抜メモリー→本戦（H.I.F 専用アビリティ） | |
| 专用道具 | — | N.I.A キー等 | H.I.Fワッペン、応援棒、カスタムPアイテム | `ProduceItem`/`ProduceCustomizeItem` |
| 初始卡组 | 流派 initial_deck | 同 | `initial_deck-produce_007-<style>`（选拔与本战相同） | `ProduceInitialDeck` |

---

## 12. 各プラン基线策略（社区经验，[网络]）

通用（[网络: game8 783836/784794/785067, note 系列摘要]）：
1. 解锁 HIF ボーナス到至少全 Lv1，优先「パラメータ上昇」「初期Pポイント」「相談割引」。
2. 選抜：授業选最低属性；レッスン选「普通」属性并尽量 SP（SP 发生率比其他剧本高 5%）；☆公開レッスン 优先用于凑スター性；HIFワッペン 20 次要在選抜+本戦内用完（おでかけ/活動支給上段 50P 拿 2 张卡最高效）；選抜終了 时スター性 ≥ 700，卡组 ≥ 22 张（応援棒会把山札补到 22）。
3. 目标分：選抜1 15,000 / 選抜2 150,000 / 選抜3 400,000（既是 S4+ 目安也是スター性封顶线）。
4. 本戦：R1 前的相談保留 P 点给インターバル（间歇不能删卡，P10=体力2）；R1 ≥ 30 万否则考虑重打選抜；优胜线 ≈ 110 万（星南）；S4+ 线 R1 70 万 + R2 150 万、合计属性 ≥ 6000、スター性 1335。
5. 支援卡：差し入れ・ドリンク編成；カスタムPアイテム 选「相談割引」系（ドリンク/スキルカード 50% 割引）。

| プラン | 推荐流派 | 要点 | 来源 |
|---|---|---|---|
| センス | 集中 / 好調 | 選抜1 高分需要「絶好調」，絶好調ドリンク优先；集中流靠「眼力」「決めポーズ」类 H.I.F アビリティ（+1 使用数・引く）；応援棒（紫/緑）补基本卡 | [网络: morishimemo 38/39 摘要] |
| ロジック | 好印象 / やる気 | 好印象流：「ふれあい」「ハートの合図」等 +1 使用数アビリティ；やる気流 需要ドリンク供給（ふわワク・花ロボ(黄) 极强）；本战靠 R2 12 回合累积 | [网络: morishimemo 40/41; game8 784692] |
| アノマリー | 強気 / 全力 | 全力：火力 buff 少，配「頂点へ」「盛り上げ上手」，R 中后段用「リスキーチャンス」「モチベ」维持全力；強気：「熱意」buff 循环每回合火力 | [网络: morishimemo 42/43; game8 784695] |

---

## 13. 开放问题（实现时需可配置 / 待实测）

1. **逐日行动菜单**：选拔 20 日与本战 9 日每天的候选行动集合不在主数据中；本战「只有第 3 天可选」的说法待核实。
2. **スター性 → スコアボーナス 公式**（§6.6）与 **试验分数 → スター性 公式**（§5，`starScoreBonusBaseLine` 的真实语义）。
3. **評価値 公式**（§7.2）的 R1/R2 減衰区间与斜率；選抜分数是否完全不计入。
4. 公開レッスン的成长率是否同时作用于副属性；SP 基础发生率。
5. おでかけ（Business）在 HIF 中的奖励表（是否复用 produce_005 表）。
6. Round1 ×1.2 是「合计用」还是同时用于 R1 的スター性换算。
7. 本战对手分数是「静态区间内随机一次」还是固定值（`isStaticNpcScore=true` 但仍有 min/max 区间）。
8. 選抜試験 平分时的名次判定；`rankThreshold 3` 在 R1 是否真正不淘汰。

---

## 附录 A：主要主数据 id 速查

- Produce: `produce-007`（選抜）、`produce-008`（本戦）；Group `produce_group-003`
- Setting: `p_setting-7/8`；ExamSetting `p_exam_setting-1`
- 难度: `ProduceStepAuditionDifficulty` produceId=produce-007/008；NPC `p_npc_group-<idol>-produce_00{7,8}-0{1,2,3}`；Config `p_exam_battle_config-<style>-produce_00{7,8}-0X`；ScoreConfig 同名
- 公開レッスン: `p_step_open_lesson-produce_007-0{1..4}-{parameter,star}[-sp]-sub_{vo,da,vi}`
- 事件: `event-detail-{school,activity}-003-produce_00{7,8}-*`、`event-detail-p_story-003-produce-00{7,8}-*`
- 面板: `produce_growth_panel_sheet-hif-0{1..9}`
- 道具: `pitem_00-3-265-0`（ワッペン）、`pitem_0{1,2,3}-3-26{6..71}-0`（応援棒）、`customize_pitem-0{1,2,3}-*`
- 回忆: `exam_contest_embed_produce_card-produce_008`、`p_memory_skill-common-hatsuboshi_idol_festival-*`
- 一番星: `IdolCardPrimaStellaProduceSkill`, `item-primastellamaterial-*`, `achieve-p_idol-<id>-025/026`
- 帮助页（官方，需游戏内访问）: `HelpContent help-hif-produce{,-star,-selection,-finals,-schedule-interval,-open-lesson,-item-customize,-memory-ability}`, `help-hif-bonus`, `idol-primastella`

## 附录 B：本次引用的网络来源（多数仅能通过搜索摘要读取）

- game8: https://game8.jp/gakuen-idolmaster/783836 （HIF攻略）、/784794（S4+）、/785067（スター性）、/784495（HIFボーナス）、/784692、/784695、/784697、/784942
- wikiwiki: https://wikiwiki.jp/gakumas/HIF/基本情報
- seesaawiki: https://seesaawiki.jp/gakumasu/d/H.I.F
- appgamelog: https://appgamelog.com/hif-koryaku/ 、/gkmas-hif-schedule/ 、/gkmas-prima-stella-idol/
- note: syato_monami n3e6218f3c356、assolato25253 n61fbcbb6e664、mk_vignette1010 n7f2604ce4f03、fit_bee8608 nb81dfb724b1c / n182b6108d8c4、team_marine nc73aa506c6f3、azhan1024 n368cae06669f（中文）
- morishimemo: gakumasu-memo-38 ~ 43
- 知恵袋: q10328370305、q12328749712、q11328363676
- X: @TimeMagicWitch 2067235889949106509
- 官方: famitsu 202605/74899、idolmaster-official.jp/news/01_17315
