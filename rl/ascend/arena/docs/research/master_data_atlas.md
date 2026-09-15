# 学マス master data 图谱（Master Data Atlas）

> 数据源：datamined master DB 的 YAML dump（`vertesan/gakumasu-diff`，commit `5b8969e`，286 张表，每表一个文件、每文件一个 row dict 列表）。
> 字段类型来自 `pmaster.proto` / `pcommon.proto`（574 个 message，一表一 message），枚举全集来自 `penum.proto`。
> 生成方式：`python tools/masterdata/build_docs.py --cache md.pkl --proto-dir <proto> --out-dir docs/research`；数据统计由 `tools/masterdata/inspect_dump.py` 提供，中文注释在 `tools/masterdata/atlas_annotations*.py`。
> 姊妹文档：`master_data_enums.md`（全部枚举取值 + 效果类型逐值语义）。

## 0. 读前须知

### 0.1 dump 的物理形态与读取

- 每张表一个 `Table.yaml`，顶层是 list，每个元素是一行 dict；嵌套 list-of-dict（`produceDescriptions`、`playEffects`、`rewards`、`stages`…）就是 proto 里的 `repeated message`。
- 整个 dump 约 209 MB YAML（ProduceCard 38 MB、ProduceExamEffect 28 MB、ProduceExamStatusEnchant 25 MB、ProduceExamGimmickEffectGroup 21 MB、ProduceItem 16 MB）。**必须用 libyaml 的 `yaml.CSafeLoader`**（PyPI 的 PyYAML wheel 自带；Debian 的 python3-yaml 没有），全量解析约 2.5 分钟，之后请走 pickle/JSON 缓存。
- 两个文件不是合法 YAML：`Localization.yaml`（块标量 `|` 后紧跟 `\r` 与正文）和 `Rule.yaml`（含 `\x0b` 控制字符）。`inspect_dump.py` 里有修复回退；二者与模拟无关。
- 枚举值序列化为 `EnumName_Value` 字符串；`EnumName_Unknown`（proto 编号 0）是“未设置”，在筛选/统计时应视为空。
- 千分比字段以 `Permil` 结尾（1000 = 100%），万分比 `Permyriad`；时间是 Unix 毫秒的**字符串**（`"1715824800000"`，`"0"` = 无）。
- 主键：多数表是 `id`；`ProduceCard` 是 `(id, upgradeCount)`；`ProduceSkill` 是 `(id, level)`；`ProduceExamGimmickEffectGroup`、`ProduceCardPool/RandomPool`、`ProduceExamBattleNpcGroup`、`ProduceExamBattleScoreConfig`、`ConditionSet`、`ConsumptionSet`、`IdolCardLevelLimit`、`IdolCardPotential`、`ProduceGrowthPanel` 等是“同一 id 多行”的分组表（用 `number`/`priority`/`level`/`parameter` 区分）。
- **id 本身携带大量语义**（如 `e_effect-exam_lesson-0009-01` = ExamLesson v1=9 count=1；`p_trigger-end_lesson-lesson_dance-dance-0400_0000` = 舞蹈课结束且 Dance≥400）。`ProduceTrigger` 表甚至**只有 id + phaseType**，条件只存在于 id 里，实现时需要解析 id 或依赖描述文本。

### 0.2 描述文本是最好的文档

自 2025-01-20 起独立的 `ProduceDescription` 表被删除，描述以 `produceDescriptions[]`（`pcommon.ProduceDescriptionSegment`）内联在每一行上。片段的 `text` 已是渲染后的文本，顺序拼接即游戏内说明。§2 说明其结构与 `ProduceDescription*` 模板表的映射规则；`master_data_enums.md` §2.1 给出了每个 ProduceExamEffectType 的日文说明文与示例文本。

### 0.3 三层效果模型（实现引擎时的心智图）

```
培育外循环                                   考试内（レッスン/試験/コンテスト）
ProduceSkill / ProduceItem / ProduceCustomizeItem / 事件 / 成长面板
   └─ ProduceTrigger(时机) + ProduceEffect(原子效果)
         ├─ 三维/体力/P点/商店/卡牌操作/奖励
         └─ ExamStatusEnchant / ExamPermanent*StatusEnchant ──► ProduceExamStatusEnchant（持续效果）
                                                                    = ProduceExamTrigger(时机+条件) + ProduceExamEffect[]（原子效果）
ProduceCard.playProduceExamTriggerId（使用条件）
ProduceCard.playEffects[] ──► ProduceExamEffect（可各带 ProduceExamTrigger 附加条件）
ProduceCard.produceCardStatusEnchantId ──► ProduceCardStatusEnchant（成长：ProduceExamTrigger + ProduceCardGrowEffect[]）
ProduceDrink ──► ProduceDrinkEffect ──► ProduceExamEffect
试炼 gimmick ──► ProduceExamGimmickEffectGroup（startTurn + 条件 + ProduceExamEffect）
对象/条件计数统一用 ProduceCardSearch；效果分组用 EffectGroup。
```

### 0.4 已知空表 / 缺失

- 空表：`ProduceCardStatusEffect`、`ExamSimulation`、`ProduceCardSimulation(Group)`、`ProduceItemSimulation(Group)`、`IdolCardSimulation`、`SupportCardSimulation(Group)`、`ProduceExamAutoResourceEvaluation`、`TowerLayer*`、`CompetitionSeason` 等。
- `ProduceRewardSet` 引用的“奖励集合 → 候选卡/道具”表不在 dump 中（集合 id 只出现在 `ProduceEffect.id` 的 `p_rd-…` 片段里）。
- 课程/事件在周程中的出现概率、SP 课程基础概率、商店刷新规则等**流程参数不在 master 里**（在服务端逻辑），需从别处确认。

## 1. 表总览

dump 共 286 张表；本图谱详述 120 张。全部表的行数：

| 表 | 行数 | 本文分组 |
|---|---|---|
| Achievement | 1206 |  |
| AchievementProgress | 2096 |  |
| AppReview | 2 |  |
| AssetDownload | 3967 |  |
| Badge | 273 |  |
| Bgm | 2 |  |
| Character | 24 | F. 偶像卡 / 角色 / 支援卡 |
| CharacterActorLookEffector | 1 |  |
| CharacterAdv | 25 |  |
| CharacterColor | 27 |  |
| CharacterDearnessLevel | 451 | F. 偶像卡 / 角色 / 支援卡 |
| CharacterDearnessStoryGashaCampaign | 0 |  |
| CharacterDetail | 181 |  |
| CharacterProduceStory | 39 |  |
| CharacterPushMessage | 169 |  |
| CharacterTrueEndAchievement | 36 |  |
| CharacterTrueEndBonus | 36 | F. 偶像卡 / 角色 / 支援卡 |
| CoinGashaButton | 36 |  |
| CompetitionExamStatusEffectIcon | 6 | J. 其他相关（备注级） |
| CompetitionSeason | 0 |  |
| CompetitionStageSectionLock | 24 |  |
| ConditionSet | 5084 | I. 通用条件/消耗 |
| ConsumptionSet | 814 | I. 通用条件/消耗 |
| Costume | 547 |  |
| CostumeColorGroup | 307 |  |
| CostumeHead | 393 |  |
| CostumeMotion | 98 |  |
| CostumePhotoGroup | 15 |  |
| CostumeWaitMotion | 40 |  |
| DearnessBackground | 208 |  |
| DearnessBgm | 13 |  |
| DearnessBoostBgm | 13 |  |
| DearnessMotion | 3972 |  |
| DearnessStoryCampaign | 0 |  |
| DeepLinkTransition | 14 |  |
| EffectGroup | 67 | D. 考试（レッスン/試験）效果引擎 |
| EventLabel | 13 |  |
| EventStoryCampaign | 0 |  |
| ExamContestEmbedProduceCard | 24 | C. 技能卡 |
| ExamInitialDeck | 46 | C. 技能卡 |
| ExamMotion | 2213 |  |
| ExamOutGameMotion | 780 |  |
| ExamSetting | 1 | A. 剧本与全局设定 |
| ExamSimulation | 0 | D. 考试（レッスン/試験）效果引擎 |
| ExamUnitMotion | 6 |  |
| ExchangeItemCategory | 6 |  |
| FeatureLock | 13 |  |
| ForceAppVersion | 4 |  |
| GashaAnimationStep | 143 |  |
| GashaButton | 103 |  |
| GuildDonationItem | 9 |  |
| GuildReaction | 44 |  |
| GvgRaid | 1 |  |
| GvgRaidStageLoop | 0 |  |
| HelpCategory | 36 |  |
| HelpContent | 273 |  |
| HelpInfo | 297 |  |
| HomeBackground | 22 |  |
| HomeBackgroundPrefabGroup | 153 |  |
| HomeBoard | 28 |  |
| HomeMonitor | 4 |  |
| HomeMotion | 1789 |  |
| HomeTime | 4 |  |
| IdolCard | 151 | F. 偶像卡 / 角色 / 支援卡 |
| IdolCardLevelLimit | 171 | F. 偶像卡 / 角色 / 支援卡 |
| IdolCardLevelLimitProduceSkill | 44 | F. 偶像卡 / 角色 / 支援卡 |
| IdolCardLevelLimitStatusUp | 38 | F. 偶像卡 / 角色 / 支援卡 |
| IdolCardPiece | 151 |  |
| IdolCardPieceQuantity | 3 |  |
| IdolCardPotential | 604 | F. 偶像卡 / 角色 / 支援卡 |
| IdolCardPotentialProduceSkill | 250 | F. 偶像卡 / 角色 / 支援卡 |
| IdolCardPrimaStellaProduceSkill | 10 | F. 偶像卡 / 角色 / 支援卡 |
| IdolCardSimulation | 0 | F. 偶像卡 / 角色 / 支援卡 |
| IdolCardSkin | 291 |  |
| IdolCardSkinSelectReward | 12 |  |
| IdolCardSkinUnit | 5 |  |
| InvitationMission | 4 |  |
| InvitationPointReward | 11 |  |
| Item | 352 |  |
| JewelConsumptionCount | 3 |  |
| LimitItem | 23 |  |
| Localization | 95 |  |
| LoginBonusMotion | 32 |  |
| MainStoryChapter | 4 |  |
| MainStoryPart | 1 |  |
| MainTask | 310 |  |
| MainTaskGroup | 4 |  |
| MainTaskIcon | 127 |  |
| Media | 222 |  |
| MediaExternalLink | 6 |  |
| MeishiBaseAsset | 299 |  |
| MeishiBaseColor | 15 |  |
| MeishiIllustrationAsset | 699 |  |
| MeishiTextColor | 37 |  |
| MemoryAbility | 575 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| MemoryExchangeItem | 3 |  |
| MemoryExchangeItemQuantity | 18 |  |
| MemoryGift | 21 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| MemoryTag | 24 |  |
| Mission | 3367 |  |
| MissionDailyRelease | 163 |  |
| MissionDailyReleaseGroup | 31 |  |
| MissionGroup | 266 |  |
| MissionPanelSheet | 44 |  |
| MissionPanelSheetGroup | 36 |  |
| MissionPass | 29 |  |
| MissionPassPoint | 1 |  |
| MissionPassProgress | 601 |  |
| MissionPoint | 35 |  |
| MissionPointRewardSet | 129 |  |
| MissionProgress | 3318 |  |
| Money | 80 |  |
| Music | 416 |  |
| MusicHot | 2203 |  |
| MusicSinger | 395 |  |
| PhotoBackground | 8 |  |
| PhotoFacialLookTarget | 0 |  |
| PhotoFacialMotionGroup | 4 |  |
| PhotoLookTargetVoiceCharacter | 13 |  |
| PhotoPose | 1040 |  |
| PhotoReactionVoiceGroup | 436 |  |
| PhotoWaitVoiceCharacter | 65 |  |
| PhotoWaitVoiceGroup | 117 |  |
| Produce | 8 | A. 剧本与全局设定 |
| ProduceAdv | 32 | J. 其他相关（备注级） |
| ProduceCard | 1714 | C. 技能卡 |
| ProduceCardConversion | 21 | C. 技能卡 |
| ProduceCardCustomize | 343 | C. 技能卡 |
| ProduceCardCustomizeRarityEvaluation | 4 | C. 技能卡 |
| ProduceCardGrowEffect | 453 | C. 技能卡 |
| ProduceCardPool | 10 | C. 技能卡 |
| ProduceCardRandomPool | 313 | C. 技能卡 |
| ProduceCardSearch | 280 | C. 技能卡 |
| ProduceCardSimulation | 0 |  |
| ProduceCardSimulationGroup | 0 |  |
| ProduceCardStatusEffect | 0 | C. 技能卡 |
| ProduceCardStatusEnchant | 77 | C. 技能卡 |
| ProduceCardTag | 3 | C. 技能卡 |
| ProduceChallengeCharacter | 39 | A. 剧本与全局设定 |
| ProduceChallengeSlot | 54 | A. 剧本与全局设定 |
| ProduceCharacter | 104 | A. 剧本与全局设定 |
| ProduceCharacterAdv | 10 |  |
| ProduceCharacterUnit | 2 | A. 剧本与全局设定 |
| ProduceCustomizeItem | 180 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceCustomizeItemRelationship | 171 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceDescriptionExamEffect | 88 | H. 描述模板系统 |
| ProduceDescriptionLabel | 226 | H. 描述模板系统 |
| ProduceDescriptionProduceCardGrowEffect | 53 | H. 描述模板系统 |
| ProduceDescriptionProduceCardMovePosition | 7 | H. 描述模板系统 |
| ProduceDescriptionProduceEffect | 92 | H. 描述模板系统 |
| ProduceDescriptionProducePlan | 4 | H. 描述模板系统 |
| ProduceDescriptionProduceStep | 2 | H. 描述模板系统 |
| ProduceDescriptionProduceType | 5 | H. 描述模板系统 |
| ProduceDescriptionSwap | 78 | H. 描述模板系统 |
| ProduceDrink | 29 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceDrinkEffect | 45 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceEffect | 2114 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceEffectIcon | 98 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceEventCharacterGrowth | 39 | B. 周程：课程 / 试炼 / 事件 |
| ProduceEventSupportCard | 511 | B. 周程：课程 / 试炼 / 事件 |
| ProduceExamAutoCardSelectEvaluation | 210 | G. 自动打牌评估 |
| ProduceExamAutoEvaluation | 11130 | G. 自动打牌评估 |
| ProduceExamAutoGrowEffectEvaluation | 3710 | G. 自动打牌评估 |
| ProduceExamAutoPlayCardEvaluation | 3066 | G. 自动打牌评估 |
| ProduceExamAutoPlayProduceCardEvaluation | 840 | G. 自动打牌评估 |
| ProduceExamAutoResourceEvaluation | 0 | G. 自动打牌评估 |
| ProduceExamAutoTriggerEvaluation | 315 | G. 自动打牌评估 |
| ProduceExamBattleConfig | 655 | B. 周程：课程 / 试炼 / 事件 |
| ProduceExamBattleNpcGroup | 11879 | B. 周程：课程 / 试炼 / 事件 |
| ProduceExamBattleNpcMob | 62 | B. 周程：课程 / 试炼 / 事件 |
| ProduceExamBattleScoreConfig | 4108 | B. 周程：课程 / 试炼 / 事件 |
| ProduceExamEffect | 2070 | D. 考试（レッスン/試験）效果引擎 |
| ProduceExamGimmickEffectGroup | 3707 | B. 周程：课程 / 试炼 / 事件 |
| ProduceExamStatusEnchant | 2003 | D. 考试（レッスン/試験）效果引擎 |
| ProduceExamTrigger | 676 | D. 考试（レッスン/試験）效果引擎 |
| ProduceGrade | 49 | A. 剧本与全局设定 |
| ProduceGroup | 3 | A. 剧本与全局设定 |
| ProduceGroupLiveCommon | 101 | J. 其他相关（备注级） |
| ProduceGrowthPanel | 50 | A. 剧本与全局设定 |
| ProduceGrowthPanelSheet | 1 | A. 剧本与全局设定 |
| ProduceGuide | 302 | J. 其他相关（备注级） |
| ProduceGuideProduceCardCategory | 67 |  |
| ProduceGuideProduceCardCategoryGroup | 16 |  |
| ProduceGuideProduceCardSampleDeckCategory | 65 |  |
| ProduceGuideProduceCardSampleDeckCategoryGroup | 16 |  |
| ProduceHighScore | 19 | A. 剧本与全局设定 |
| ProduceInitialDeck | 48 | C. 技能卡 |
| ProduceItem | 1038 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceItemChallengeGroup | 390 | A. 剧本与全局设定 |
| ProduceItemEffect | 931 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceItemSimulation | 0 |  |
| ProduceItemSimulationGroup | 0 |  |
| ProduceLegendProduceCard | 6 | A. 剧本与全局设定 |
| ProduceLive | 316 | A. 剧本与全局设定 |
| ProduceLiveEvaluation | 410 | A. 剧本与全局设定 |
| ProduceNavigation | 352 | A. 剧本与全局设定 |
| ProduceNextIdolAuditionMasterRankingSeason | 3 | A. 剧本与全局设定 |
| ProduceResultMotion | 314 |  |
| ProduceScheduleBackground | 15 |  |
| ProduceScheduleMotion | 1066 |  |
| ProduceSeason | 2 | A. 剧本与全局设定 |
| ProduceSeasonZeroGrade | 30 | A. 剧本与全局设定 |
| ProduceSetting | 8 | A. 剧本与全局设定 |
| ProduceSkill | 1488 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceSplitAdv | 24 | J. 其他相关（备注级） |
| ProduceStartMotion | 39 |  |
| ProduceStepAuditionCharacter | 130 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepAuditionCharacterBgm | 44 |  |
| ProduceStepAuditionCharacterUnitMotion | 66 |  |
| ProduceStepAuditionDifficulty | 4259 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepAuditionMotion | 866 |  |
| ProduceStepAuditionRivalActor | 10 |  |
| ProduceStepAuditionRivalActorMotion | 2 |  |
| ProduceStepEventDetail | 6888 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepEventSuggestion | 3066 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepFanPresentMotion | 39 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepLesson | 955 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepLessonLevel | 174 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepOpenLesson | 48 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepOpenLessonMotion | 424 |  |
| ProduceStepSelfLesson | 6 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStepSelfLessonMotion | 416 |  |
| ProduceStepTransition | 3228 | B. 周程：课程 / 试炼 / 事件 |
| ProduceStory | 3341 | J. 其他相关（备注级） |
| ProduceStoryGroup | 1856 | J. 其他相关（备注级） |
| ProduceTrigger | 176 | E. 培育外循环效果：技能 / 道具 / 饮料 |
| ProduceWeekMotion | 230 |  |
| ProducerLevel | 80 |  |
| ProducerRanking | 4 |  |
| ProducerRankingCharacter | 13 |  |
| ProducerRankingProduce | 12 |  |
| ProducerRankingRankGrade | 24 |  |
| ProducerRankingTower | 51 |  |
| PvpRateCommonProduceCard | 3 | C. 技能卡 |
| PvpRateConfig | 51 | J. 其他相关（备注级） |
| PvpRateMotion | 52 |  |
| PvpRateUnitSlotUnlock | 8 |  |
| ResearchMemoryRerollCost | 55 |  |
| ResultGradePattern | 60 | A. 剧本与全局设定 |
| Rule | 23 |  |
| SeminarExamTransition | 12 | J. 其他相关（备注级） |
| Setting | 1 |  |
| Shop | 5 |  |
| ShopItem | 280 |  |
| ShopProduct | 14 |  |
| Story | 268 |  |
| StoryEvent | 34 |  |
| StoryGroup | 96 |  |
| SupportCard | 201 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardBonus | 15 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardFlavor | 562 |  |
| SupportCardLevel | 150 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardLevelLimit | 15 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardProduceSkillFilter | 44 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardProduceSkillLevelAssist | 307 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardProduceSkillLevelDance | 4764 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardProduceSkillLevelVisual | 5091 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardProduceSkillLevelVocal | 5109 | F. 偶像卡 / 角色 / 支援卡 |
| SupportCardSimulation | 0 |  |
| SupportCardSimulationGroup | 0 |  |
| Terms | 3 |  |
| Tips | 30 |  |
| TitleAsset | 6 |  |
| TitleVoice | 17 |  |
| Tour | 4 |  |
| TourMotion | 28 |  |
| TourStageTimeline | 12 |  |
| Tower | 13 | J. 其他相关（备注级） |
| TowerLayer | 0 |  |
| TowerLayerExam | 0 |  |
| TowerLayerRank | 0 |  |
| TowerReset | 1700 |  |
| TowerTotalClearRankReward | 97 |  |
| Tutorial | 216 |  |
| TutorialCharacterVoice | 21 |  |
| TutorialProduce | 3 | J. 其他相关（备注级） |
| TutorialProduceStep | 12 | J. 其他相关（备注级） |
| Voice | 39 |  |
| VoiceGroup | 3439 |  |
| VoiceRoster | 1915 |  |
| Work | 2 |  |
| WorkLevel | 24 |  |
| WorkLevelReward | 2736 |  |
| WorkMotion | 78 |  |
| WorkSkip | 5 |  |
| WorkTime | 6 |  |

## 2. 通用嵌套结构

### 2.1 produceDescriptions[]（pcommon.ProduceDescriptionSegment）

几乎所有效果表都带 `produceDescriptions`（2025-01-20 起独立的 ProduceDescription 表被删除，描述改为内联到各行）。每个片段是一段“模板 token”，**`text` 字段已经是渲染后的文本**（数值、卡名、标签名都已填入），因此把片段的 text 顺序拼接（空 PlainText 视为换行，去掉 `<nobr>`）就能得到游戏内显示的完整效果说明。只有 `Exam` 型且 `examDescriptionType` 为 ExamValue/ExamTurn/ExamCount/… 的片段 text 为空——它们是 **Label 模板**里留给运行时填充的槽。

| 片段字段 | proto 类型 | 含义 |
|---|---|---|
| `produceDescriptionType` | ProduceDescriptionType | ProduceDescriptionType：片段类型（PlainText=纯文本 / Exam=数值槽 / ProduceExamEffectType=效果名标签 / ProduceCard=卡名 / ProduceDescriptionName=引用 Label / DiffText=强化差异高亮 / ProduceCardCategory / ProduceCardGrowEffectType / ProduceDescription / ProduceItem / ProduceDrink / ProduceStepBusinessType）。 |
| `examDescriptionType` | ExamDescriptionType | ExamDescriptionType：数值槽种类（CustomizeEffectValue1/2、CustomizeEffectValuePercent1/2、CustomizeTurn、CustomizeEffectCount、CustomizeCostValue、CustomizeLessonCountAdd、CustomizeInitialAdd、CustomizePlayMovePositionLost、CustomizeEffectAdd、ExamValue/ExamValue2/ExamTurn/ExamCount/ExamTurnTimer=运行时填充的槽）。 |
| `examEffectType` | ProduceExamEffectType | 当片段是效果名标签时，指明是哪种 ProduceExamEffectType。 |
| `produceCardGrowEffectType` | ProduceCardGrowEffectType | 当片段是成长效果名标签时的 ProduceCardGrowEffectType。 |
| `produceCardCategory` | ProduceCardCategory | 当片段是卡牌类别标签时的 ProduceCardCategory。 |
| `produceCardMovePositionType` | ProduceCardMovePositionType | 当片段描述移动位置时的 ProduceCardMovePositionType。 |
| `produceStepType` | ProduceStepType | 片段引用的 ProduceStepType（例如“学園活動”）。 |
| `produceStepBusinessType` | ProduceStepBusinessType | 片段引用的 ProduceStepBusinessType（营业种类）。 |
| `text` | string | **已渲染的文本**（大多数片段都直接带最终文字；空字符串的 PlainText = 换行）。 |
| `targetId` | string | 片段引用对象：Label_*/Description_*/Convert_*（→ ProduceDescriptionLabel）或 ProduceCard/ProduceItem 的 id。 |
| `targetLevel` | int32 | 引用对象的等级/强化段（几乎全 0）。 |
| `effectValue1` | int32 | 槽位对应的原始数值（如 permil 值 200 渲染成 “20%”）。 |
| `effectValue2` | int32 | 第二数值。 |
| `effectCount` | int32 | 次数。 |
| `turn` | int32 | 回合数。 |
| `costValue` | int32 | 费用值。 |
| `produceDescriptionSwapId` | string | → ProduceDescriptionSwap：文本按 レッスン/試験(オーディション) 场景替换（パラメータ↔スコア 等）。 |
| `originProduceExamTriggerId` | string | 该片段来源的 ProduceExamTrigger。 |
| `originProduceExamEffectId` | string | 该片段来源的 ProduceExamEffect。 |
| `originProduceCardStatusEnchantId` | string | 该片段来源的 ProduceCardStatusEnchant。 |
| `isCost` | bool | 该片段属于费用说明。 |
| `isOnlyOutGame` | bool | 只在培育外（图鉴/编成）显示，考试内不显示（例如“重複不可”）。 |
| `changeColor` | bool | 变色高亮。 |

**模板→文本的映射规则**（由 ProduceDescription* 表定义）：

1. `ProduceDescriptionType_ProduceExamEffectType` 片段：`examEffectType` → `ProduceDescriptionExamEffect.name`（如 ExamParameterBuff→好調），`targetId` 指向其说明 Label。
2. `ProduceDescriptionType_ProduceDescriptionName`/`ProduceDescription` 片段：`targetId`=Label_*/Convert_* → `ProduceDescriptionLabel.name`；若 Label 带 `produceDescriptionSwapId`，按场景（レッスン/試験）用 `ProduceDescriptionSwap.text` 替换（パラメータ↔スコア、レッスン↔試験・ステージ）。
3. `ProduceDescriptionType_Exam` 片段：按 `examDescriptionType` 从所属效果行取 effectValue1/2/effectCount/turn/costValue 格式化（Percent 型除以 10 显示为 %）。
4. `ProduceCard`/`ProduceItem`/`ProduceDrink` 片段：`targetId`→对应表 name。
5. `ProduceCardGrowEffectType` 片段 → `ProduceDescriptionProduceCardGrowEffect.name`；`ProduceCardCategory` → Label_ActiveSkillCard 等。
6. Label 的 `produceDescriptions` 本身也是片段列表，可递归引用；其中 `Exam(ExamValue/ExamTurn…)` 槽由效果行的数值填充——这就是 **Label 模板** 与 **效果行** 的连接方式。

### 2.2 playEffects[]（ProduceCard）

| 字段 | 含义 |
|---|---|
| `produceExamTriggerId` | 该条效果的附加发动条件（空=无条件）。 |
| `produceExamEffectId` | → ProduceExamEffect。 |
| `hideIcon` | 不显示效果图标。 |
| `isOncePlayEffect` | 每场只发动一次的效果（用于 再演 ExamStatusEnchantEncore 等）。 |

### 2.3 rewards[] / produceRewards[]

`{resourceType, resourceId, quantity|resourceLevel}`，resourceId 按 resourceType 多态。

## 3. A. 剧本与全局设定

### Produce（8 行）

培育剧本/难度的顶层定义。8 行 = 『初』レギュラー/プロ/マスター/レジェンド(produce-001/002/003/006)、N.I.A プロ/マスター(004/005)、H.I.F 選抜試験/本戦(007/008)。每行决定周数(steps)、参数成长上限、试炼配置等；通过 produceSettingId / examSettingId 挂接数值设定。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "produce-001", "produce-002" |
| `name` | string | 100% | 显示名（日文）。 | "レギュラー", "プロ" |
| `baseStepLevel` | int32 | 100% | 起始 step level（决定课程强度表 ProduceStepLessonLevel 的 progressLevel 起点；初 プロ/マスター=5）。 | 1, 5 |
| `maxRefreshCount` | int32 | 38% | 可“休息(Refresh)”的最大次数（N.I.A / レジェンド=4，其他 0=不限）。 | 0, 4 |
| `produceSelectScreenOrderType` | ProduceSelectScreenOrderType | 100% | 选择界面分页（First/Second，レジェンド在第二页）。 | "ProduceSelectScreenOrderType_First", "ProduceSelectScreenOrderType_Second" |
| `challengeViewConditionSetId` | string | 38% | → ConditionSet，チャレンジPアイテム 栏位显示条件。 | "cd-master_produce-view_open", "cd-nia_produce-unlock_open" |
| `viewConditionSetId` | string | 38% | → ConditionSet，显示条件。 | "cd-pro_produce-view_open", "cd-master_produce-view_open" |
| `unlockConditionSetId` | string | 88% | → ConditionSet，解锁条件。 | "cd-task_clear-01-040", "cd-master_produce-unlock_open" |
| `examSettingId` | string | 100% | → ExamSetting（全库唯一 p_exam_setting-1）。 | "p_exam_setting-1" |
| `produceSettingId` | string | 100% | → ProduceSetting，每个剧本一份。 | "p_setting-1", "p_setting-2" |
| `idolCardParameterGrowthLimit` | int32 | 100% | 三维参数成长上限（初 1000/1500/1800/3000，NIA 2000/2600，HIF 3000）。 | 1000, 1500 |
| `maxProduceEventCharacterGrowthNumber` | int32 | 38% | 角色成长事件（CharacterGrowth）最多触发次数（仅『初』2/3）。 | 2, 3 |
| `steps` | int32 | 100% | 总周数（初 13/16/18，NIA 27/26，HIF 選抜 20 + 本戦 9）。 | 13, 16 |
| `actionPointQuantity` | int32 | 100% | 消耗 AP（15/20）。 | 15, 20 |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "produce-1", "produce-2" |
| `produceNavigationNormalId` | string | 100% | → ProduceNavigation，普通导航台词组。 | "p_navi-produce_group-001-normal", "p_navi-produce_group-002-normal" |
| `produceNavigationAuditionId` | string | 100% | → ProduceNavigation，试炼前导航台词组。 | "p_navi-produce_group-001-audition", "p_navi-produce_group-002-audition" |
| `produceNavigationLoseId` | string | 100% | → ProduceNavigation，失败导航台词组。 | "p_navi-produce_group-001-lose", "p_navi-produce_group-002-lose" |
| `gradientColor1` | string | 100% | UI 渐变色。 | "FFD731", "72B8FF" |
| `gradientColor2` | string | 100% | UI 渐变色。 | "FF9538", "EA74FF" |
| `easyProduceItemIds` | repeated string | 12% | → ProduceItem，简单模式(イージー)附赠道具（仅 NIA プロ）。 | ["pitem_00-3-330-0"] |
| `easyConditionSetId` | string | 12% | → ConditionSet，简单模式可选条件（亲爱度 1..18）。 | "cd-easy_mode" |
| `easyProduceConditionSetId` | string | 12% | 简单模式限制条件（id 以 p-cd- 开头，不在 ConditionSet 中）。 | "p-cd-easy_mode-ng-02" |
| `produceSplitType` | ProduceSplitType | 100% | ProduceSplitType：H.I.F 把一次培育拆成 Selection(選抜試験, produce-007) 与 Final(本戦, produce-008) 两半；Unknown=不区分。 | "ProduceSplitType_Unknown", "ProduceSplitType_Selection" |
| `splitPairProduceId` | string | 25% | → Produce，H.I.F 的另一半（007↔008）。 | "produce-008", "produce-007" |
| `selectionMemoryEmbedProduceCardId` | string | 25% | → ExamContestEmbedProduceCard，H.I.F 選抜メモリー生成时嵌入的卡池。 | "exam_contest_embed_produce_card-produce…" |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 2, 3 |

外键（按 id 连接验证）：
- `challengeViewConditionSetId` → **ConditionSet** (2/2 命中)
- `viewConditionSetId` → **ConditionSet** (2/2 命中)
- `unlockConditionSetId` → **ConditionSet** (7/7 命中)
- `examSettingId` → **ExamSetting** (1/1 命中)
- `produceSettingId` → **ProduceSetting** (8/8 命中)
- `produceNavigationNormalId` → **ProduceNavigation** (3/3 命中)
- `produceNavigationAuditionId` → **ProduceNavigation** (3/3 命中)
- `produceNavigationLoseId` → **ProduceNavigation** (3/3 命中)
- `easyProduceItemIds` → **ProduceItem** (1/1 命中)
- `easyConditionSetId` → **ConditionSet** (1/1 命中)
- `splitPairProduceId` → **Produce** (2/2 命中)
- `selectionMemoryEmbedProduceCardId` → **ExamContestEmbedProduceCard** (1/1 命中)

代表行：
```json
{"id": "produce-001", "name": "レギュラー", "baseStepLevel": 1, "produceSelectScreenOrderType": "ProduceSelectScreenOrderType_First", "examSettingId": "p_exam_setting-1", "produceSettingId": "p_setting-1", "idolCardParameterGrowthLimit": 1000, "maxProduceEventCharacterGrowthNumber": 2, "steps": 13, "actionPointQuantity": 15, "assetId": "produce-1", "produceNavigationNormalId": "p_navi-produce_group-001-normal", "produceNavigationAuditionId": "p_navi-produce_group-001-audition", "produceNavigationLoseId": "p_navi-produce_group-001-lose", "gradientColor1": "FFD731", "gradientColor2": "FF9538", "order": 2}
{"id": "produce-005", "name": "マスター", "baseStepLevel": 1, "maxRefreshCount": 4, "produceSelectScreenOrderType": "ProduceSelectScreenOrderType_First", "challengeViewConditionSetId": "cd-nia_produce-unlock_open", "unlockConditionSetId": "cd-nia_master_produce-unlock_open", "examSettingId": "p_exam_setting-1", "produceSettingId": "p_setting-5", "idolCardParameterGrowthLimit": 2600, "steps": 26, "actionPointQuantity": 20, "assetId": "produce-nia-2", "produceNavigationNormalId": "p_navi-produce_group-002-normal", "produceNavigationAuditionId": "p_navi-produce_group-002-audition", "produceNavigationLoseId": "p_navi-produce_group-002-lose", "gradientColor1": "FF1C7E", "gradientColor2": "FFC436", "order": 2}
```

### ProduceGroup（3 行）

剧本系列。3 行：定期公演『初』(FirstStar) / NEXT IDOL AUDITION / Hatsuboshi IDOL FESTIVAL。挂 Produce 列表、评价上限、通用 Live 设置。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "produce_group-001", "produce_group-002" |
| `name` | string | 100% | 显示名（日文）。 | "定期公演『初』", "NEXT IDOL AUDITION" |
| `type` | ProduceType | 100% | ProduceType。 | "ProduceType_FirstStar", "ProduceType_NextIdolAudition" |
| `produceIds` | repeated string | 100% | → Produce。 | ["produce-001", "produce-002", "produce-003", "produce-006"], ["produce-004", "produce-005"] |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "produce-group-1", "produce-group-2" |
| `viewConditionSetId` | string | 0% | → ConditionSet，显示条件。 |  |
| `unlockConditionSetId` | string | 67% | → ConditionSet，解锁条件。 | "cd-nia_produce-unlock_open", "cd-hif_selection_produce-unlock_open" |
| `failedProduceMemoryAssetId` | string | 100% | 培育失败时的メモリー图。 | "img_general_memory_all-produce-failure-…", "img_general_memory_all-produce-failure-…" |
| `description` | string | 100% | 说明文（日文）。 | "定期公演『初』──それは、初星学園アイドル科の\n成績上位者のみ立つことができる…", "『NEXT IDOL AUDITION』──通称『N.I.A』\n次代を担うアイ…" |
| `isForceLiveCommon` | bool | 67% | 结束 Live 是否强制使用通用曲目（NIA/HIF=true）。 | false, true |
| `disableForceLiveCommonEndingLiveType` | ProduceLiveType | 100% | 例外：该 ProduceLiveType 不强制通用（TrueEnd）。 | "ProduceLiveType_Unknown", "ProduceLiveType_TrueEnd" |
| `limitGrade` | ResultGrade | 100% | 该系列可达到的最高评价（初 Ssss / NIA SssPlus / HIF Sssss）。 | "ResultGrade_Ssss", "ResultGrade_SssPlus" |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 1, 2 |

外键（按 id 连接验证）：
- `produceIds` → **Produce** (8/8 命中)
- `unlockConditionSetId` → **ConditionSet** (2/2 命中)

代表行：
```json
{"id": "produce_group-001", "name": "定期公演『初』", "type": "ProduceType_FirstStar", "produceIds": ["produce-001", "produce-002", "produce-003", "produce-006"], "assetId": "produce-group-1", "failedProduceMemoryAssetId": "img_general_memory_all-produce-failure-001", "description": "定期公演『初』──それは、初星学園アイドル科の\n成績上位者のみ立つことができるステージ\n自分を磨き、今、彼女たちは輝きはじめる──", "limitGrade": "ResultGrade_Ssss", "order": 1}
{"id": "produce_group-002", "name": "NEXT IDOL AUDITION", "type": "ProduceType_NextIdolAudition", "produceIds": ["produce-004", "produce-005"], "assetId": "produce-group-2", "unlockConditionSetId": "cd-nia_produce-unlock_open", "failedProduceMemoryAssetId": "img_general_memory_all-produce-failure-002", "description": "『NEXT IDOL AUDITION』──通称『N.I.A』\n次代を担うアイドルの頂点を決める戦いが開幕！\nファンを集めて、今、栄光のステージへ──", "isForceLiveCommon": true, "disableForceLiveCommonEndingLiveType": "ProduceLiveType_TrueEnd", "limitGrade": "ResultGrade_SssPlus", "order": 2}
```

### ProduceSetting（8 行）

每剧本一份的培育数值设定（休息回复比例、饮料上限、定制次数等）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_setting-1", "p_setting-2" |
| `initialProducePoint` | int32 | 0% | 初始 P ポイント（全 0）。 | 0 |
| `produceDrinkPossessLimit` | int32 | 100% | P饮料默认持有上限 3。 | 3 |
| `refreshStaminaRecoveryPermil` | int32 | 100% | “休む”回复最大体力的千分比（700 / HIF 500）。 | 700, 500 |
| `customizeProduceCardCount` | int32 | 100% | 特别指导(カスタマイズ)一次可定制卡数（1 或 2）。 | 1, 2 |
| `stepSkipStaminaRecoveryPermil` | int32 | 100% | 跳过周程的体力回复千分比 250。 | 250 |
| `beforeAuditionRefreshStaminaRecoveryPermil` | int32 | 100% | 试炼前自动回复千分比（700 / NIA・HIF 500）。 | 700, 500 |
| `stepCustomizeStartAlertProducePointThreshold` | int32 | 100% | 进入定制时 P点低于该值弹提示。 | 49, 39 |
| `examStartAlertStaminaThreshold` | int32 | 100% | 考试前体力低于 10 弹提示。 | 10 |
| `continueCount` | int32 | 100% | 可コンティニュー次数 3。 | 3 |
| `produceAuditionTrendAssessmentPermilUpper` | int32 | 100% | 试炼“合格趋势”评估上界千分比（200 或 110）。 | 200, 110 |
| `produceAuditionTrendAssessmentPermilLower` | int32 | 100% | 同上下界。 | 200, 110 |
| `maxLegendProduceCardCount` | int32 | 38% | 可持有的 Legend 卡数（レジェンド/HIF=1）。 | 0, 1 |
| `stepIntervalUpgradeProduceCardCount` | int32 | 100% | 每次强化周程可强化卡数 1。 | 1 |
| `stepIntervalCustomizeProduceCardCount` | int32 | 100% | 每次定制周程可定制卡数 2。 | 2 |
| `selectionMemoryNeedProduceCardCount` | int32 | 100% | H.I.F 選抜メモリー需要卡数 1。 | 1 |
| `produceDrinkPossessMaxLimit` | int32 | 100% | 饮料持有硬上限 4（含上限+1 技能）。 | 4 |

代表行：
```json
{"id": "p_setting-1", "produceDrinkPossessLimit": 3, "refreshStaminaRecoveryPermil": 700, "customizeProduceCardCount": 1, "stepSkipStaminaRecoveryPermil": 250, "beforeAuditionRefreshStaminaRecoveryPermil": 700, "stepCustomizeStartAlertProducePointThreshold": 49, "examStartAlertStaminaThreshold": 10, "continueCount": 3, "produceAuditionTrendAssessmentPermilUpper": 200, "produceAuditionTrendAssessmentPermilLower": 200, "stepIntervalUpgradeProduceCardCount": 1, "stepIntervalCustomizeProduceCardCount": 2, "selectionMemoryNeedProduceCardCount": 1, "produceDrinkPossessMaxLimit": 4}
{"id": "p_setting-5", "produceDrinkPossessLimit": 3, "refreshStaminaRecoveryPermil": 700, "customizeProduceCardCount": 2, "stepSkipStaminaRecoveryPermil": 250, "beforeAuditionRefreshStaminaRecoveryPermil": 500, "stepCustomizeStartAlertProducePointThreshold": 39, "examStartAlertStaminaThreshold": 10, "continueCount": 3, "produceAuditionTrendAssessmentPermilUpper": 110, "produceAuditionTrendAssessmentPermilLower": 110, "stepIntervalUpgradeProduceCardCount": 1, "stepIntervalCustomizeProduceCardCount": 2, "selectionMemoryNeedProduceCardCount": 1, "produceDrinkPossessMaxLimit": 4}
```

### ExamSetting（1 行）

考试（レッスン/試験）引擎的全局常量，全库仅 1 行 p_exam_setting-1；Produce/PvpRateConfig/Tour/GvgRaid/TutorialProduce 全部指向它。**实现引擎必须逐字段读取**。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_exam_setting-1" |
| `examStaminaConsumptionDownPermil` | int32 | 100% | 消費体力減少 状态：消耗×50%。 | 500 |
| `examStaminaConsumptionAddPermil` | int32 | 100% | 消費体力増加 状态：消耗+100%。 | 1000 |
| `examBlockAddDownPermil` | int32 | 100% | 不安：元気获得×66.7%（即 -33%）。 | 667 |
| `examStaminaConsumptionAddDownPermil` | int32 | 100% | 消費体力増加効果減少（1250）：增加效果被削到 50%（未使用效果）。 | 1250 |
| `examStaminaReduceChange` | int32 | 100% | 体力消費軽減 常量 1（未使用）。 | 1 |
| `examStaminaConsumptionDownAddPermil` | int32 | 100% | 消費体力減少効果増加：减少效果改为 60%（未使用）。 | 600 |
| `examConcentrationLessonValueMultiplePermil` | int32 | 100% | 強気 参数倍率 2000（旧字段，被 ...Permil1/2 取代）。 | 2000 |
| `fullPowerPlayableValueAdd` | int32 | 100% | 进入全力时 追加使用次数 +1。 | 1 |
| `examFullPowerLessonValueMultiplePermil` | int32 | 100% | 全力 参数倍率 3000（=+200%）。 | 3000 |
| `holdLimit` | int32 | 100% | 保留(ホールド)区上限 2。 | 2 |
| `handLimit` | int32 | 100% | 手牌上限 5。 | 5 |
| `turnStartDistribute` | int32 | 100% | 每回合开始发牌 3 张。 | 3 |
| `examGimmickParameterDebuffPermil` | int32 | 100% | 不調：参数×66.7%。 | 667 |
| `examParameterBuffPermil` | int32 | 100% | 好調：参数×150%。 | 1500 |
| `examTurnEndRecoveryStamina` | int32 | 100% | 回合结束回复体力 2（试炼特有规则）。 | 2 |
| `produceExamPanicStaminaCandidates` | repeated int32 | 100% | 気まぐれ 随机消耗体力候选值列表（1..15）。 | [1, 2, 3, 4, 5, "…(+13)"] |
| `examParameterBuffMultiplePerTurnPermil` | int32 | 100% | 絶好調：每剩余 1 回合好調 +10%。 | 100 |
| `preservationReleasePlayableValueAdd1` | int32 | 100% | 温存1段 解除时 使用次数+1。 | 1 |
| `preservationReleasePlayableValueAdd2` | int32 | 100% | 温存2段 解除时 使用次数+1。 | 1 |
| `preservationReleaseBlockAdd1` | int32 | 0% | 温存1段 解除时 固定元気 +0。 | 0 |
| `preservationReleaseBlockAdd2` | int32 | 100% | 温存2段 解除时 固定元気 +5。 | 5 |
| `preservationReleaseEnthusiastic1` | int32 | 100% | 温存1段 解除时 熱意 +5。 | 5 |
| `preservationReleaseEnthusiastic2` | int32 | 100% | 温存2段 解除时 熱意 +8。 | 8 |
| `examConcentrationLessonValueMultiplePermil1` | int32 | 100% | 強気1段 参数 +100%。 | 2000 |
| `examConcentrationLessonValueMultiplePermil2` | int32 | 100% | 強気2段 参数 +150%。 | 2500 |
| `examPreservationLessonValueMultiplePermil1` | int32 | 100% | 温存1段 参数×50%。 | 500 |
| `examPreservationLessonValueMultiplePermil2` | int32 | 100% | 温存2段 参数×25%。 | 250 |
| `examConcentrationStaminaMultiplePermil1` | int32 | 100% | 強気1段 消耗体力×200%。 | 2000 |
| `examConcentrationStaminaMultiplePermil2` | int32 | 100% | 強気2段 消耗体力×200%。 | 2000 |
| `examPreservationStaminaMultiplePermil1` | int32 | 100% | 温存1段 消耗×50%。 | 500 |
| `examPreservationStaminaMultiplePermil2` | int32 | 100% | 温存2段 消耗×25%。 | 250 |
| `examConcentrationStaminaPenetrateReduce1` | int32 | 0% | 強気1段 每用一张卡额外 体力消費(无视元気) 0。 | 0 |
| `examConcentrationStaminaPenetrateReduce2` | int32 | 100% | 強気2段 每用一张卡额外 体力消費 1。 | 1 |
| `examAutoPlayEnableVersion` | int32 | 100% | 自动打牌算法版本 2。 | 2 |
| `examAutoPlaySearchCommandLimit` | int32 | 100% | 自动打牌搜索深度 5。 | 5 |
| `overPreservationReleasePlayableValueAdd` | int32 | 100% | のんびり 解除 使用次数+1。 | 1 |
| `overPreservationReleaseBlockAdd` | int32 | 100% | のんびり 解除 固定元気+5。 | 5 |
| `overPreservationReleaseEnthusiastic` | int32 | 100% | のんびり→強気 熱意+10。 | 10 |
| `examOverPreservationLessonValueMultiplePermil` | int32 | 0% | のんびり 参数×0%。 | 0 |
| `examOverPreservationStaminaMultiplePermil` | int32 | 0% | のんびり 消耗×0%。 | 0 |
| `overPreservationReleaseToFullPowerGrowEffectLessonAdd` | int32 | 100% | のんびり→全力 时全卡 パラメータ値増加+10。 | 10 |
| `examAutoPlaySearchCommandPlanLimits` | repeated int32 | 100% | 各プラン自动打牌搜索深度 [5,5,5]。 | [5, 5, 5] |
| `examLessonValueMultipleDependReviewOrAggressiveMultiplePermil` | int32 | 100% | プライド：min(好印象,やる気) 每 1 点 +2%。 | 20 |
| `examLessonValueMultipleDependReviewOrAggressiveMaxPermil` | int32 | 100% | プライド 上限 +50%。 | 500 |
| `fixMoveCardShuffleDeckEnable` | bool | 100% | 移动卡到牌库指定位置后是否保持洗牌规则 true。 | true |
| `examBuffConsumptionDownPermil` | int32 | 100% | 強化状態コスト減少 ×50%（未使用效果）。 | 500 |
| `examBuffConsumptionAddPermil` | int32 | 100% | 強化状態コスト増加 +100%。 | 1000 |

代表行：
```json
{"id": "p_exam_setting-1", "examStaminaConsumptionDownPermil": 500, "examStaminaConsumptionAddPermil": 1000, "examBlockAddDownPermil": 667, "examStaminaConsumptionAddDownPermil": 1250, "examStaminaReduceChange": 1, "examStaminaConsumptionDownAddPermil": 600, "examConcentrationLessonValueMultiplePermil": 2000, "fullPowerPlayableValueAdd": 1, "examFullPowerLessonValueMultiplePermil": 3000, "holdLimit": 2, "handLimit": 5, "turnStartDistribute": 3, "examGimmickParameterDebuffPermil": 667, "examParameterBuffPermil": 1500, "examTurnEndRecoveryStamina": 2, "produceExamPanicStaminaCandidates": [1, 2, 3, 4, 5, "…(+13)"], "examParameterBuffMultiplePerTurnPermil": 100, "preservationReleasePlayableValueAdd1": 1, "preservationReleasePlayableValueAdd2": 1, "preservationReleaseBlockAdd2": 5, "preservationReleaseEnthusiastic1": 5, "preservationReleaseEnthusiastic2": 8, "examConcentrationLessonValueMultiplePermil1": 2000, "examConcentrationLessonValueMultiplePermil2": 2500, "examPreservationLessonValueMultiplePermil1": 500, "examPreservationLessonValueMultiplePermil2": 250, "examConcentrationStaminaMultiplePermil1": 2000, "examConcentrationStaminaMultiplePermil2": 2000, "examPreservationStaminaMultiplePermil1": 500, "examPreservationStaminaMultiplePermil2": 250, "examConcentrationStaminaPenetrateReduce2": 1, "examAutoPlayEnableVersion": 2, "examAutoPlaySearchCommandLimit": 5, "overPreservationReleasePlayableValueAdd": 1, "overPreservationReleaseBlockAdd": 5, "overPreservationReleaseEnthusiastic": 10, "overPreservationReleaseToFullPowerGrowEffectLessonAdd": 10, "examAutoPlaySearchCommandPlanLimits": [5, 5, 5], "examLessonValueMultipleDependReviewOrAggressiveMultiplePermil": 20, "examLessonValueMultipleDependReviewOrAggressiveMaxPermil": 500, "fixMoveCardShuffleDeckEnable": true, "examBuffConsumptionDownPermil": 500, "examBuffConsumptionAddPermil": 1000}
```

### ProduceSeason（2 行）

培育赛季（シーズン0/1）的时间窗，用于评价/榜单结算。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "produce_season-00", "produce_season-01" |
| `name` | string | 100% | 显示名（日文）。 | "シーズン0", "シーズン1" |
| `startTime` | int64 | 100% | 开始时间（Unix ms 字符串）。 | "1715824800000", "1759111200000" |
| `endTime` | int64 | 100% | 结束时间（Unix ms 字符串，0=无）。 | "1759107600000", "0" |
| `fixRankTime` | int64 | 100% | 排名锁定时间（Unix ms 字符串）。 | "1759370400000", "0" |

代表行：
```json
{"id": "produce_season-00", "name": "シーズン0", "startTime": "1715824800000", "endTime": "1759107600000", "fixRankTime": "1759370400000"}
{"id": "produce_season-01", "name": "シーズン1", "startTime": "1759111200000", "endTime": "0", "fixRankTime": "0"}
```

### ProduceSeasonZeroGrade（30 行）

シーズン0 期间各剧本系列的评价(ResultGrade)分数阈值（已被 ProduceGrade 取代）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceGroupId` | string | 100% | → ProduceGroup（剧本系列：初 / N.I.A / H.I.F）。 | "produce_group-001", "produce_group-002" |
| `grade` | ResultGrade | 100% | ResultGrade。 | "ResultGrade_F", "ResultGrade_E" |
| `threshold` | int32 | 93% | 达到该评价所需 培育评分。 | 0, 1000 |

外键（按 id 连接验证）：
- `produceGroupId` → **ProduceGroup** (2/2 命中)

代表行：
```json
{"produceGroupId": "produce_group-001", "grade": "ResultGrade_F"}
{"produceGroupId": "produce_group-002", "grade": "ResultGrade_F"}
```

### ProduceGrade（49 行）

当前各剧本系列的最终评价阈值：F=0,E=1000,D=2000,C=3000,C+=4500,B=6000,B+=8000,A=10000,A+=11500,S=13000,S+=14500,SS=16000,SS+=18000,SSS=20000,SSS+=23000,SSSS=26000(初/HIF),SSSS+=30000,SSSSS=35000(仅 HIF)。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceGroupId` | string | 100% | → ProduceGroup（剧本系列：初 / N.I.A / H.I.F）。 | "produce_group-001", "produce_group-002" |
| `grade` | ResultGrade | 100% | ResultGrade。 | "ResultGrade_F", "ResultGrade_E" |
| `threshold` | int32 | 94% | 培育评分阈值。 | 0, 1000 |

外键（按 id 连接验证）：
- `produceGroupId` → **ProduceGroup** (3/3 命中)

代表行：
```json
{"produceGroupId": "produce_group-001", "grade": "ResultGrade_F"}
{"produceGroupId": "produce_group-002", "grade": "ResultGrade_APlus", "threshold": 11500}
```

### ResultGradePattern（60 行）

四类结果评价的通用阈值表：ProduceScore(评分, 到 SSSSS+=40000)、ProduceIdolCardParameter(参数, E=100…SSS+=3500)、ProduceVoteCount(NIA 投票数, E=3000…SSS+=160000)、ProduceStar(HIF スター性, E=20…S+=1200)。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ResultGradeType | 100% | ResultGradeType。 | "ResultGradeType_ProduceScore", "ResultGradeType_ProduceIdolCardParameter" |
| `grade` | ResultGrade | 100% | ResultGrade。 | "ResultGrade_F", "ResultGrade_E" |
| `threshold` | int32 | 93% | 阈值。 | 0, 1000 |

代表行：
```json
{"type": "ResultGradeType_ProduceScore", "grade": "ResultGrade_F"}
{"type": "ResultGradeType_ProduceIdolCardParameter", "grade": "ResultGrade_Ss", "threshold": 2100}
```

### ProduceHighScore（19 行）

高分活动（ハイスコアイベント / 十王邦夫のアイドル強化月間）定义，Normal/Rush 两种；与 ProduceItem.isHighScoreRush、ProduceEffectType_HighScoreGoldAddition 关联。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "highscore-event-001", "highscore-event-002" |
| `name` | string | 100% | 显示名（日文）。 | "十王邦夫のアイドル強化月間", "ハイスコアイベント" |
| `produceHighScoreEventType` | ProduceHighScoreEventType | 100% | Normal / Rush。 | "ProduceHighScoreEventType_Normal", "ProduceHighScoreEventType_Rush" |
| `bannerAssetId` | string | 100% | 横幅图。 | "img_general_event_highscore-event_highs…", "img_general_event_highscore-event_highs…" |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 1 |

代表行：
```json
{"id": "highscore-event-001", "name": "十王邦夫のアイドル強化月間", "produceHighScoreEventType": "ProduceHighScoreEventType_Normal", "bannerAssetId": "img_general_event_highscore-event_highscore-event-001-banner", "order": 1}
{"id": "highscorerush-event-006", "name": "十王邦夫のアイドル強化月間〜星々のきらめき〜", "produceHighScoreEventType": "ProduceHighScoreEventType_Rush", "bannerAssetId": "img_general_event_highscorerush_highscorerush-event-006-banner", "order": 1}
```

### ProduceLegendProduceCard（6 行）

『初』レジェンド(produce-006) 每个流派(examEffectType)可选的 Legend 稀有度卡列表（每流派 5 张，共 15 张）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceId` | string | 100% | → Produce（剧本/难度）。 | "produce-006" |
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_ExamParameterBuff", "ProduceExamEffectType_ExamLessonBuff" |
| `produceCardIds` | repeated string | 100% | → ProduceCard（rarity=Legend）。 | ["p_card-01-act-100_003", "p_card-01-act-100_004", "p_card-01-act-100_006", "p_card-01-men-100_001", "p_card-01-men-100_005"], ["p_card-02-act-100_009", "p_card-02-act-100_010", "p_card-02-men-100_007", "p_card-02-men-100_008", "p_card-02-men-100_011"] |

外键（按 id 连接验证）：
- `produceId` → **Produce** (1/1 命中)
- `produceCardIds` → **ProduceCard** (15/15 命中)

代表行：
```json
{"produceId": "produce-006", "examEffectType": "ProduceExamEffectType_ExamParameterBuff", "produceCardIds": ["p_card-01-act-100_003", "p_card-01-act-100_004", "p_card-01-act-100_006", "p_card-01-men-100_001", "p_card-01-men-100_005"]}
{"produceId": "produce-006", "examEffectType": "ProduceExamEffectType_ExamCardPlayAggressive", "produceCardIds": ["p_card-02-act-100_009", "p_card-02-act-100_010", "p_card-02-men-100_007", "p_card-02-men-100_008", "p_card-02-men-100_011"]}
```

### ProduceCharacter（104 行）

剧本 × 角色 的开放关系（哪个角色可在哪个剧本培育，及解锁条件）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceId` | string | 100% | → Produce（剧本/难度）。 | "produce-001", "produce-002" |
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `forceLiveCommonIdolCardId` | string | 25% | → IdolCard，通用 Live 时使用的形象卡。 | "i_card-amao-3-007", "i_card-atbm-3-012" |
| `unlockConditionSetId` | string | 100% | → ConditionSet，解锁条件。 | "cd_time_24_0516_produce-character-open", "cd_time_atbm_produce-character-open" |

外键（按 id 连接验证）：
- `produceId` → **Produce** (8/8 命中)
- `characterId` → **Character** (13/13 命中)
- `forceLiveCommonIdolCardId` → **IdolCard** (13/13 命中)
- `unlockConditionSetId` → **ConditionSet** (49/49 命中)

代表行：
```json
{"produceId": "produce-001", "characterId": "amao", "unlockConditionSetId": "cd_time_24_0516_produce-character-open"}
{"produceId": "produce-005", "characterId": "amao", "forceLiveCommonIdolCardId": "i_card-amao-3-007", "unlockConditionSetId": "cd-dearness_level-amao-20"}
```

### ProduceCharacterUnit（2 行）

H.I.F 的双人 unit（REVERSI：kllj↔ssmk）定义，仅影响演出。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "reversi" |
| `produceGroupId` | string | 100% | → ProduceGroup（剧本系列：初 / N.I.A / H.I.F）。 | "produce_group-003" |
| `targetCharacterId` | string | 100% | 本人。 | "kllj", "ssmk" |
| `unitCharacterId` | string | 100% | 搭档。 | "ssmk", "kllj" |
| `name` | string | 100% | 显示名（日文）。 | "REVERSI" |
| `liveCostumeId` | string | 0% | 外键/引用 id（见 FK）。 |  |
| `liveCostumeHeadId` | string | 0% | 外键/引用 id（见 FK）。 |  |

外键（按 id 连接验证）：
- `produceGroupId` → **ProduceGroup** (1/1 命中)
- `targetCharacterId` → **Character** (2/2 命中)
- `unitCharacterId` → **Character** (2/2 命中)

代表行：
```json
{"id": "reversi", "produceGroupId": "produce_group-003", "targetCharacterId": "kllj", "unitCharacterId": "ssmk", "name": "REVERSI"}
{"id": "reversi", "produceGroupId": "produce_group-003", "targetCharacterId": "ssmk", "unitCharacterId": "kllj", "name": "REVERSI"}
```

### ProduceChallengeSlot（54 行）

チャレンジPアイテム 槽位：剧本(003/005/006) × 流派 × 槽序号 → ProduceItemChallengeGroup。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "challenge_slot-exam_card_play_aggressive", "challenge_slot-exam_concentration" |
| `produceId` | string | 100% | → Produce（剧本/难度）。 | "produce-003", "produce-005" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `produceItemChallengeGroupId` | string | 100% | → ProduceItemChallengeGroup。 | "challenge_slot-exam_card_play_aggressiv…", "challenge_slot-exam_card_play_aggressiv…" |
| `unlockDescription` | string | 22% | 解锁条件说明。 | "「初」：マスターの最終試験で1位になる", "「初」：マスターでプロデュース評価Sを獲得する" |

外键（按 id 连接验证）：
- `produceId` → **Produce** (3/3 命中)
- `produceItemChallengeGroupId` → **ProduceItemChallengeGroup** (54/54 命中)

代表行：
```json
{"id": "challenge_slot-exam_card_play_aggressive", "produceId": "produce-003", "number": 1, "produceItemChallengeGroupId": "challenge_slot-exam_card_play_aggressive-produce_003-group_001"}
{"id": "challenge_slot-exam_lesson_buff", "produceId": "produce-003", "number": 1, "produceItemChallengeGroupId": "challenge_slot-exam_lesson_buff-produce_003-group_001"}
```

### ProduceChallengeCharacter（39 行）

チャレンジ 模式按角色的解锁条件（亲爱度 10 等）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceId` | string | 100% | → Produce（剧本/难度）。 | "produce-003", "produce-005" |
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `unlockConditionSetId` | string | 100% | → ConditionSet，解锁条件。 | "cd-dearness_level-amao-10", "cd-dearness_level-atbm-10" |

外键（按 id 连接验证）：
- `produceId` → **Produce** (3/3 命中)
- `characterId` → **Character** (13/13 命中)
- `unlockConditionSetId` → **ConditionSet** (27/27 命中)

代表行：
```json
{"produceId": "produce-003", "characterId": "amao", "unlockConditionSetId": "cd-dearness_level-amao-10"}
{"produceId": "produce-005", "characterId": "hume", "unlockConditionSetId": "cd-dearness_level-hume-20"}
```

### ProduceItemChallengeGroup（390 行）

チャレンジPアイテム 分组：一组里多件道具，附带课程上限分加成与试炼参数成长率。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "challenge_slot-exam_card_play_aggressiv…", "challenge_slot-exam_card_play_aggressiv…" |
| `produceItemId` | string | 100% | → ProduceItem（isChallenge=true 的道具）。 | "pitem_00-1-025-challenge", "pitem_00-1-026-challenge" |
| `lessonLimitUpScore` | int32 | 62% | 课程 CLEAR 上限提升。 | 5, 10 |
| `auditionParameterGrowthRatePermil` | int32 | 38% | 试炼参数成长率千分比。 | 0, 50 |

外键（按 id 连接验证）：
- `produceItemId` → **ProduceItem** (237/237 命中)

代表行：
```json
{"id": "challenge_slot-exam_card_play_aggressive-produce_003-group_001", "produceItemId": "pitem_00-1-025-challenge", "lessonLimitUpScore": 5}
{"id": "challenge_slot-exam_lesson_buff-produce_003-group_001", "produceItemId": "pitem_00-1-025-challenge", "lessonLimitUpScore": 5}
```

### ProduceNextIdolAuditionMasterRankingSeason（3 行）

N.I.A マスター 排行赛季时间窗。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "next_idol_audition_master_rank_season-1", "next_idol_audition_master_rank_season-2" |
| `produceId` | string | 100% | → Produce（剧本/难度）。 | "produce-005" |
| `startTime` | int64 | 100% | 开始时间（Unix ms 字符串）。 | "1747620000000", "1751248800000" |
| `endTime` | int64 | 100% | 结束时间（Unix ms 字符串，0=无）。 | "1750795200000", "1754424000000" |
| `fixRankTime` | int64 | 100% | 排名锁定时间。 | "1751227200000", "1754942400000" |

外键（按 id 连接验证）：
- `produceId` → **Produce** (1/1 命中)

代表行：
```json
{"id": "next_idol_audition_master_rank_season-1", "produceId": "produce-005", "startTime": "1747620000000", "endTime": "1750795200000", "fixRankTime": "1751227200000"}
{"id": "next_idol_audition_master_rank_season-2", "produceId": "produce-005", "startTime": "1751248800000", "endTime": "1754424000000", "fixRankTime": "1754942400000"}
```

### ProduceGrowthPanelSheet（1 行）

成长面板（H.I.F 专属“育成パネル”）表头：解锁道具、任务组、成就。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "produce_growth_panel_sheet-hif" |
| `produceType` | ProduceType | 100% | ProduceType：FirstStar=定期公演『初』 / NextIdolAudition=N.I.A / HatsuboshiIdolFestival=H.I.F。 | "ProduceType_HatsuboshiIdolFestival" |
| `unlockItemId` | string | 100% | → Item，面板点数道具。 | "item-produce-produce_growth_panel_sheet…" |
| `missionGroupId` | string | 100% | → MissionGroup。 | "mission-group-mission_HIF_clear_1" |
| `achievementId` | string | 100% | → Achievement。 | "achieve-o_028" |

外键（按 id 连接验证）：
- `unlockItemId` → **Item** (1/1 命中)
- `missionGroupId` → **MissionGroup** (1/1 命中)
- `achievementId` → **Achievement** (1/1 命中)

代表行：
```json
{"id": "produce_growth_panel_sheet-hif", "produceType": "ProduceType_HatsuboshiIdolFestival", "unlockItemId": "item-produce-produce_growth_panel_sheet_point-hif", "missionGroupId": "mission-group-mission_HIF_clear_1", "achievementId": "achieve-o_028"}
```

### ProduceGrowthPanel（50 行）

成长面板的每格：9 个面板(id) × 最多 6 级(level)，每级消耗 unlockItemQuantity 点数，给予永久 ProduceEffect（三维加成、成长率、SP率、上限+、商店折扣等）。produceSplitType 指明只在 選抜/本戦 生效。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "produce_growth_panel_sheet-hif-01", "produce_growth_panel_sheet-hif-02" |
| `level` | int32 | 100% | 等级。 | 1, 2 |
| `produceGrowthPanelSheetId` | string | 100% | 外键/引用 id（见 FK）。 | "produce_growth_panel_sheet-hif" |
| `produceSplitType` | ProduceSplitType | 100% | ProduceSplitType：H.I.F 把一次培育拆成 Selection(選抜試験, produce-007) 与 Final(本戦, produce-008) 两半；Unknown=不区分。 | "ProduceSplitType_Unknown", "ProduceSplitType_Final" |
| `name` | string | 0% | 显示名（日文）。 |  |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) ボーカル上昇+20 / ボーカルパラメータボーナス+2%", "(渲染) ボーカル上昇+40 / ボーカルパラメータボーナス+4%" |
| `unlockConditionSetId` | string | 0% | → ConditionSet，解锁条件。 |  |
| `unlockItemQuantity` | int32 | 100% | 解锁所需点数。 | 10, 20 |
| `isUnlockRecommended` | bool | 0% | 推荐标记。 | false |
| `produceEffectIds` | repeated string | 100% | → ProduceEffect 列表。 | ["p_effect-vocal_addition-0020_0020", "p_effect-vocal_growth_rate_addition-002…"], ["p_effect-vocal_addition-0040_0040", "p_effect-vocal_growth_rate_addition-004…"] |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 1, 2 |

外键（按 id 连接验证）：
- `produceGrowthPanelSheetId` → **ProduceGrowthPanelSheet** (1/1 命中)
- `produceDescriptions.targetId` → **ProduceDescriptionLabel** (1/1 命中)
- `produceEffectIds` → **ProduceEffect** (59/59 命中)

代表行：
```json
{"id": "produce_growth_panel_sheet-hif-01", "level": 1, "produceGrowthPanelSheetId": "produce_growth_panel_sheet-hif", "produceDescriptions": "(渲染) ボーカル上昇+20 / ボーカルパラメータボーナス+2%", "unlockItemQuantity": 10, "produceEffectIds": ["p_effect-vocal_addition-0020_0020", "p_effect-vocal_growth_rate_addition-0020_0020"], "order": 1}
{"id": "produce_growth_panel_sheet-hif-05", "level": 6, "produceGrowthPanelSheetId": "produce_growth_panel_sheet-hif", "produceDescriptions": "(渲染) 試験前の体力回復量を15%増加", "unlockItemQuantity": 60, "produceEffectIds": ["p_effect-before_audition_refresh_stamina_up-0150_0150"], "order": 5}
```

### ProduceLive（316 行）

结束 Live 曲目/舞台资源表（musicId × ProduceLiveType）。与模拟无关，仅备注。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `musicId` | string | 100% | → Music。 | "music-all-amao-001", "music-all-amao-002" |
| `type` | ProduceLiveType | 100% | ProduceLiveType（A/B/C/D/E/TrueEnd）。 | "ProduceLiveType_TrueEnd", "ProduceLiveType_A" |
| `forceUnlockConditionSetId` | string | 1% | 外键/引用 id（见 FK）。 | "cd-view-music-all-nasr-008-release", "cd-view-music-all-nasr-010-02" |
| `unlockConditionSetId` | string | 0% | → ConditionSet，解锁条件。 | "cd-view-music-all-nasr-008-01" |
| `thumbnailAssetId` | string | 98% | 外键/引用 id（见 FK）。 | "img_general_live_music-all-amao-001_tru…", "img_general_live_music-all-amao-002_tru…" |
| `environmentAssetId` | string | 100% | 外键/引用 id（见 FK）。 | "env_3d_live_all001-00-noon", "env_3d_live_all002-00-noon" |
| `timelineAssetId` | string | 100% | 外键/引用 id（见 FK）。 | "tln_live_all-001", "tln_live_all-002" |
| `beforeAdvAssetId` | string | 16% | 外键/引用 id（见 FK）。 | "adv_live_amao_001_start-01-01", "adv_live_amao_001_start-02-01" |
| `afterAdvAssetId` | string | 16% | 外键/引用 id（见 FK）。 | "adv_live_amao_001_end-01-01", "adv_live_amao_001_end-02-01" |
| `liveMusicAssetId` | string | 76% | 外键/引用 id（见 FK）。 | "sud_music_live_all-001-amao_true-001", "sud_music_live_all-002-amao_true-001" |
| `motionAssetIds` | repeated string | 67% | 外键/引用 id（见 FK）。 | ["mot_live_chr_amao_all-001_00_in"], ["mot_live_chr_amao_all-002_00_in"] |
| `unitLiveThumbnailAssetCharacterIds` | repeated string | 2% | 外键/引用 id（见 FK）。 | ["amao", "hrnm"], ["hume", "hmsz", "jsna"] |
| `unitLiveThumbnailAssetIds` | repeated string | 2% | 外键/引用 id（见 FK）。 | ["img_general_live_music-unit-amao-004_tr…", "img_general_live_music-unit-hrnm-004_tr…"], ["img_general_live_music-unit-hume-002_tr…", "img_general_live_music-unit-hmsz-002_tr…", "img_general_live_music-unit-jsna-002_tr…"] |
| `liveOverrideAssetId` | string | 0% | 外键/引用 id（见 FK）。 |  |
| `additionalActorAssetIds` | repeated string | 9% | 外键/引用 id（见 FK）。 | ["mdl_chr_amao-spcs-0000_body", "mdl_chr_amao-spcs-0000_face", "mdl_chr_amao-spcs-0000_hair"], ["mdl_chr_amao-cstm-0176_body", "mdl_chr_amao-base-0000_face", "mdl_chr_amao-cstm-0000_hair"] |
| `costumeId` | string | 0% | 外键/引用 id（见 FK）。 | "nasr-cstm-0119" |
| `costumeHeadId` | string | 0% | 外键/引用 id（见 FK）。 |  |

外键（按 id 连接验证）：
- `musicId` → **Music** (264/264 命中)
- `forceUnlockConditionSetId` → **ConditionSet** (2/2 命中)
- `unlockConditionSetId` → **ConditionSet** (1/1 命中)
- `environmentAssetId` → AssetDownload? (3/65 = 5%，多态或部分引用)
- `timelineAssetId` → AssetDownload? (1/113 = 1%，多态或部分引用)
- `liveMusicAssetId` → AssetDownload? (3/239 = 1%，多态或部分引用)
- `motionAssetIds` → AssetDownload? (4/92 = 4%，多态或部分引用)
- `unitLiveThumbnailAssetCharacterIds` → **Character** (12/12 命中)
- `additionalActorAssetIds` → AssetDownload? (16/80 = 20%，多态或部分引用)
- `costumeId` → **Costume** (1/1 命中)

代表行：
```json
{"musicId": "music-all-amao-001", "type": "ProduceLiveType_TrueEnd", "thumbnailAssetId": "img_general_live_music-all-amao-001_true-end", "environmentAssetId": "env_3d_live_all001-00-noon", "timelineAssetId": "tln_live_all-001", "liveMusicAssetId": "sud_music_live_all-001-amao_true-001", "motionAssetIds": ["mot_live_chr_amao_all-001_00_in"]}
{"musicId": "music-all-kllj-009", "type": "ProduceLiveType_TrueEnd", "thumbnailAssetId": "img_general_live_music-all-kllj-009_true-end", "environmentAssetId": "env_3d_live_all009-00-noon", "timelineAssetId": "tln_live_all-009", "liveMusicAssetId": "sud_music_live_all-009-kllj_true-001", "motionAssetIds": ["mot_live_chr_cmmn_all-009_00_in"]}
```

### ProduceLiveEvaluation（410 行）

剧本 × 角色 × 可出现的 Live 类型（评价等级 → Live 分支）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceId` | string | 100% | → Produce（剧本/难度）。 | "produce-001", "produce-002" |
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `liveType` | ProduceLiveType | 100% | ProduceLiveType。 | "ProduceLiveType_TrueEnd", "ProduceLiveType_A" |

外键（按 id 连接验证）：
- `produceId` → **Produce** (8/8 命中)
- `characterId` → **Character** (13/13 命中)

代表行：
```json
{"produceId": "produce-001", "characterId": "amao", "liveType": "ProduceLiveType_TrueEnd"}
{"produceId": "produce-003", "characterId": "kcna", "liveType": "ProduceLiveType_A"}
```

### ProduceNavigation（352 行）

（仅备注）培育中导航角色台词：id=台词组，number=序号，description=台词（含 <COLOR_VOCAL> 富文本）。与模拟无关。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_navi-produce_group-001-audition", "p_navi-produce_group-001-lose" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `description` | string | 99% | 台词文本。 | "試験に合格する実力は十分なようですね！", "ボーカルが少し足りないみたいですね\n<COLOR_VOCAL>ボーカル</co…" |

代表行：
```json
{"id": "p_navi-produce_group-001-audition", "number": 1, "description": "試験に合格する実力は十分なようですね！"}
{"id": "p_navi-produce_group-002-lose", "number": 5, "description": "ビジュアルに僅かな差があったみたいです\n<COLOR_VISUAL>ビジュアル</color>レッスンで強化しましょう"}
```

## 4. B. 周程：课程 / 试炼 / 事件

### ProduceStepLesson（955 行）

课程(レッスン)实例表。id 编码：`p_step_lesson_level-{produce序号}-{角色}-{hard|normal|sp}-{vo|da|vi}-{序号}`（初）或 `p_step_lesson-produce_00X-{流派}-{normal|sp}-{序号}`（レジェンド/HIF）。name 是课程档位名（通常レッスンA..E / SPレッスンA..D / 追い込みレッスン / 追加レッスン / レジェンドレッスン / チュートリアル）。真正的数值在 produceStepLessonLevelId。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_step_lesson_level-001-amao-hard-da-001", "p_step_lesson_level-001-amao-hard-da-002" |
| `name` | string | 100% | 显示名（日文）。 | "追い込みレッスン", "通常レッスンA" |
| `produceStepLessonLevelId` | string | 100% | → ProduceStepLessonLevel（回合数、CLEAR 线、PERFECT 线）。 | "p_step_lesson_level-001-plan1-hard-001", "p_step_lesson_level-001-plan1-hard-002" |

外键（按 id 连接验证）：
- `produceStepLessonLevelId` → **ProduceStepLessonLevel** (174/174 命中)

代表行：
```json
{"id": "p_step_lesson_level-001-amao-hard-da-001", "name": "追い込みレッスン", "produceStepLessonLevelId": "p_step_lesson_level-001-plan1-hard-001"}
{"id": "p_step_lesson_level-002-shro-normal-da-003", "name": "通常レッスンC", "produceStepLessonLevelId": "p_step_lesson_level-002-plan2-aggressive-normal-003"}
```

课程与周次的绑定规则（第几周出现哪个档位）**不在 master 里**，需从游戏/攻略确认；这里只提供档位数值池。

### ProduceStepLessonLevel（174 行）

课程数值档位。id 编码 `p_step_lesson_level-{produce}-{planN}-{hard|normal|sp}-{序号}`。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_step_lesson_level-001-plan1-hard-001", "p_step_lesson_level-001-plan1-hard-002" |
| `progressLevel` | int32 | 100% | 进度等级（全 1）。 | 1 |
| `limitTurn` | int32 | 100% | 回合数（normal 5/6，sp 5/6，hard 9/10，legend 更长）。 | 9, 10 |
| `successThreshold` | int32 | 100% | CLEAR 目标分。 | 75, 100 |
| `resultTargetValueLimit` | int32 | 100% | PERFECT 目标分（超过后停止计分/满分线）。 | 300, 400 |

代表行：
```json
{"id": "p_step_lesson_level-001-plan1-hard-001", "progressLevel": 1, "limitTurn": 9, "successThreshold": 75, "resultTargetValueLimit": 300}
{"id": "p_step_lesson_level-002-plan2-normal-003", "progressLevel": 1, "limitTurn": 7, "successThreshold": 55, "resultTargetValueLimit": 110}
```

### ProduceStepSelfLesson（6 行）

自主レッスン（N.I.A produce-004）：固定消耗体力与固定参数收益（无打牌）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "self_lesson-produce_004-01-normal", "self_lesson-produce_004-01-sp" |
| `progressLevel` | int32 | 100% | 进度等级（全 1）。 | 1 |
| `stamina` | int32 | 100% | 消耗体力。 | 6, 8 |
| `parameter` | int32 | 100% | 参数收益。 | 80, 100 |

代表行：
```json
{"id": "self_lesson-produce_004-01-normal", "progressLevel": 1, "stamina": 6, "parameter": 80}
{"id": "self_lesson-produce_004-02-sp", "progressLevel": 1, "stamina": 8, "parameter": 120}
```

### ProduceStepOpenLesson（48 行）

公開レッスン（H.I.F produce-007 選抜試験）：消耗体力，主参数+mainParameter，副参数(subParameterType)+subParameter，获得 star（スター性）。id 里含 parameter/star 与 sp 标记。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_step_open_lesson-produce_007-01-param…", "p_step_open_lesson-produce_007-01-param…" |
| `stamina` | int32 | 100% | 消耗体力。 | 8, 6 |
| `subParameterType` | ProduceParameterType | 100% | 副参数种类。 | "ProduceParameterType_Dance", "ProduceParameterType_Visual" |
| `mainParameter` | int32 | 100% | 主参数收益。 | 80, 60 |
| `subParameter` | int32 | 100% | 副参数收益。 | 50, 20 |
| `star` | int32 | 100% | スター性收益。 | 10, 5 |

代表行：
```json
{"id": "p_step_open_lesson-produce_007-01-parameter-sp-sub_da", "stamina": 8, "subParameterType": "ProduceParameterType_Dance", "mainParameter": 80, "subParameter": 50, "star": 10}
{"id": "p_step_open_lesson-produce_007-03-parameter-sp-sub_da", "stamina": 8, "subParameterType": "ProduceParameterType_Dance", "mainParameter": 120, "subParameter": 70, "star": 10}
```

### ProduceStepAuditionDifficulty（4259 行）

试炼(中間/最終試験、オーディション)难度表：id=难度组（按角色 `p_step_audition_difficulty-{chr}` 或按偶像卡 `-i_card-...`，IdolCard.produceStepAuditionDifficultyId 指向），行 = (id, produceId, stepType, number)。给出参数基准线、基础分、NPC 组、战斗配置(回合/参数)、gimmick 组、票数基准等。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_step_audition_difficulty-amao", "p_step_audition_difficulty-fktn" |
| `produceId` | string | 100% | → Produce（剧本/难度）。 | "produce-001", "produce-002" |
| `stepType` | ProduceStepType | 100% | ProduceStepType（周程类型：LessonXxx / AuditionMid1/Mid2/Final / EventXxx / Present / Refresh / OpenLesson / SelfLesson ...）。 | "ProduceStepType_AuditionMid1", "ProduceStepType_AuditionFinal" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `rankThreshold` | int32 | 100% | 合格名次（初=3 名以内，NIA/HIF 最终=1 位）。 | 3, 1 |
| `parameterBaseLine` | int32 | 100% | 参数基准（用于评分换算/合格趋势）。 | 100, 200 |
| `baseScore` | int32 | 100% | 基础目标分（试炼合格线的基准）。 | 600, 2500 |
| `forceEndScore` | int32 | 6% | 达到即强制结束（仅『初』中間，如 900）。 | 900, 0 |
| `produceExamBattleNpcGroupId` | string | 100% | → ProduceExamBattleNpcGroup（对手 NPC 分数区间）。 | "p_npc_group-amao-produce-001-1-04", "p_npc_group-amao-produce-001-2-04" |
| `produceExamBattleConfigId` | string | 100% | → ProduceExamBattleConfig（回合数、评分用参数与分数曲线）。 | "p_exam_battle_config-vovi-04-produce-00…", "p_exam_battle_config-vovi-04-produce-00…" |
| `produceExamGimmickEffectGroupId` | string | 91% | → ProduceExamGimmickEffectGroup（试炼场地效果时间表）。 | "p_exam_gimmick-produce-001-exam_paramet…", "p_exam_gimmick-produce-002-exam_paramet…" |
| `auditionType` | ProduceStepAuditionType | 100% | ProduceStepAuditionType（NIA 的 Mid1Easy..FinalVeryHard 难度分级）。 | "ProduceStepAuditionType_Unknown", "ProduceStepAuditionType_Mid1Easy" |
| `isUnlockAnimation` | bool | 6% | 解锁演出。 | false, true |
| `voteCountBaseLine` | int32 | 62% | NIA 投票数基准。 | 0, 4968 |
| `isStaticNpcScore` | bool | 5% | NPC 分数固定（HIF 本戦 border 用）。 | false, true |
| `dearnessLevel` | int32 | 12% | 需要的亲爱度（NIA FinalHard/VeryHard 14/17）。 | 0, 14 |
| `voteCount` | int32 | 44% | NIA 合格所需票数。 | 0, 4000 |
| `starScoreBonusBaseLine` | int32 | 13% | HIF スター性 分数加成基准。 | 0, 50 |

外键（按 id 连接验证）：
- `produceId` → **Produce** (8/8 命中)
- `produceExamBattleNpcGroupId` → **ProduceExamBattleNpcGroup** (420/420 命中)
- `produceExamBattleConfigId` → **ProduceExamBattleConfig** (338/338 命中)
- `produceExamGimmickEffectGroupId` → **ProduceExamGimmickEffectGroup** (226/226 命中)

代表行：
```json
{"id": "p_step_audition_difficulty-amao", "produceId": "produce-001", "stepType": "ProduceStepType_AuditionMid1", "number": 1, "rankThreshold": 3, "parameterBaseLine": 100, "baseScore": 600, "forceEndScore": 900, "produceExamBattleNpcGroupId": "p_npc_group-amao-produce-001-1-04", "produceExamBattleConfigId": "p_exam_battle_config-vovi-04-produce-001-1-1"}
{"id": "p_step_audition_difficulty-i_card-hume-3-016", "produceId": "produce-006", "stepType": "ProduceStepType_AuditionMid1", "number": 1, "rankThreshold": 3, "parameterBaseLine": 300, "baseScore": 12450, "produceExamBattleNpcGroupId": "p_npc_group-hume-produce_006_mid", "produceExamBattleConfigId": "p_exam_battle_config-davo-03-produce_006_mid", "produceExamGimmickEffectGroupId": "p_exam_gimmick-produce_006_mid-lesson_buff"}
```

### ProduceStepAuditionCharacter（130 行）

N.I.A 各角色每次试炼的合格/失败后排名（successNextIdolAuditionRank / failure...）与选择画面剪影。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `stepType` | ProduceStepType | 100% | ProduceStepType（周程类型：LessonXxx / AuditionMid1/Mid2/Final / EventXxx / Present / Refresh / OpenLesson / SelfLesson ...）。 | "ProduceStepType_AuditionMid1", "ProduceStepType_AuditionMid2" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `successNextIdolAuditionRank` | int32 | 100% | 合格后的 NIA 排名。 | 61, 58 |
| `failureNextIdolAuditionRank` | int32 | 100% | 失败后的排名。 | 63, 40 |
| `auditionSelectHeaderSilhouetteAssetId` | string | 10% | 剪影角色。 | "sgka", "ttmr" |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `auditionSelectHeaderSilhouetteAssetId` → **Character** (8/8 命中)

代表行：
```json
{"characterId": "amao", "stepType": "ProduceStepType_AuditionMid1", "number": 1, "successNextIdolAuditionRank": 61, "failureNextIdolAuditionRank": 63}
{"characterId": "hume", "stepType": "ProduceStepType_AuditionMid2", "number": 3, "successNextIdolAuditionRank": 52, "failureNextIdolAuditionRank": 67}
```

### ProduceExamBattleConfig（655 行）

试炼/竞赛的战斗配置：回合数、评分基准三维(vocal/dance/visual)、评分曲线 id；Excellent/Bad 是 NIA 高低分档参数。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_exam_battle_config-competition_pre_st…", "p_exam_battle_config-competition_pre_st…" |
| `turn` | int32 | 100% | 回合数。 | 12, 9 |
| `vocal` | int32 | 100% | 基准 Vocal。 | 1069, 802 |
| `dance` | int32 | 100% | 基准 Dance。 | 535, 1337 |
| `visual` | int32 | 100% | 基准 Visual。 | 1069, 535 |
| `produceExamBattleScoreConfigId` | string | 100% | → ProduceExamBattleScoreConfig。 | "p_exam_battle_score_config-competition-…", "p_exam_battle_score_config-competition-…" |
| `vocalExcellent` | int32 | 46% | 高分档参数。 | 0, 1173 |
| `danceExcellent` | int32 | 46% | 同。 | 0, 1434 |
| `visualExcellent` | int32 | 46% | 同。 | 0, 1737 |
| `vocalBad` | int32 | 46% | 低分档参数。 | 0, 914 |
| `danceBad` | int32 | 46% | 同。 | 0, 1139 |
| `visualBad` | int32 | 46% | 同。 | 0, 1402 |

外键（按 id 连接验证）：
- `produceExamBattleScoreConfigId` → **ProduceExamBattleScoreConfig** (407/407 命中)

代表行：
```json
{"id": "p_exam_battle_config-competition_pre_stage1", "turn": 12, "vocal": 1069, "dance": 535, "visual": 1069, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-competition-pre-stage_1"}
{"id": "p_exam_battle_config-tower_001-352_288_426-1084_887_1314-turn_12", "turn": 12, "vocal": 352, "dance": 288, "visual": 426, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-tower_001-352_288_426-1084_887_1314", "vocalExcellent": 1084, "danceExcellent": 887, "visualExcellent": 1314, "vocalBad": 252, "danceBad": 188, "visualBad": 326}
```

### ProduceExamBattleScoreConfig（4108 行）

试炼评分曲线：同一 id 多行，按 parameter（偶像该维参数）分段，给出每维的 permil 系数（分数 = 卡牌スコア × 系数/1000 之类的分段线性插值）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_exam_battle_score_config-april_stage_1", "p_exam_battle_score_config-competition-…" |
| `parameter` | int32 | 88% | 分段起点（参数值）。 | 0, 50 |
| `vocalPermil` | int32 | 100% | Vocal 回合系数。 | 1, 57035 |
| `dancePermil` | int32 | 100% | Dance 回合系数。 | 1, 57035 |
| `visualPermil` | int32 | 100% | Visual 回合系数。 | 1, 57035 |

代表行：
```json
{"id": "p_exam_battle_score_config-april_stage_1", "vocalPermil": 1, "dancePermil": 1, "visualPermil": 1}
{"id": "p_exam_battle_score_config-tower_001-1806_2188_1477-1965_2382_1608", "parameter": 1965, "vocalPermil": 16382, "dancePermil": 17569, "visualPermil": 11354}
```

### ProduceExamBattleNpcGroup（11879 行）

试炼对手组：每组 number 个对手（角色或 mob），分数区间 scoreMin..scoreMax、三维占比、开场/中段/终盘得分分配（op/mid/ed Permil）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_npc_group-amao-produce_004-1-1", "p_npc_group-amao-produce_004-1-2" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `characterId` | string | 4% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "hrnm", "ttmr" |
| `produceExamBattleNpcMobId` | string | 96% | → ProduceExamBattleNpcMob（路人/边界线 NPC）。 | "npc_nia_20", "npc_nia_18" |
| `scoreMin` | int32 | 100% | 最终分下限。 | 931, 535 |
| `scoreMax` | int32 | 100% | 上限。 | 1138, 802 |
| `vocalPermil` | int32 | 100% | 分数三维占比。 | 334, 330 |
| `dancePermil` | int32 | 100% | 。 | 333, 330 |
| `visualPermil` | int32 | 100% | 。 | 333, 340 |
| `opScorePermil` | int32 | 100% | 前段得分比例。 | 200, 300 |
| `midScorePermil` | int32 | 100% | 中段。 | 250, 300 |
| `edScorePermil` | int32 | 100% | 后段。 | 550, 400 |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `produceExamBattleNpcMobId` → **ProduceExamBattleNpcMob** (61/61 命中)

代表行：
```json
{"id": "p_npc_group-amao-produce_004-1-1", "number": 1, "produceExamBattleNpcMobId": "npc_nia_20", "scoreMin": 931, "scoreMax": 1138, "vocalPermil": 334, "dancePermil": 333, "visualPermil": 333, "opScorePermil": 200, "midScorePermil": 250, "edScorePermil": 550}
{"id": "p_npc_group-tower_001-hski-exam_concentration-stage_024", "number": 3, "produceExamBattleNpcMobId": "npc_rare-mob-vo-1", "scoreMin": 38278, "scoreMax": 40278, "vocalPermil": 400, "dancePermil": 300, "visualPermil": 300, "opScorePermil": 100, "midScorePermil": 200, "edScorePermil": 700}
```

### ProduceExamBattleNpcMob（62 行）

路人 NPC 定义（含 HIF 的 border=合格线虚拟对手 isBorder）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "npc_andk", "npc_atbm" |
| `name` | string | 100% | 显示名（日文）。 | "藍井 撫子", "雨夜 燕" |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "exam-audition_andk", "exam-audition_atbm" |
| `isBorder` | bool | 2% | 是否为“合格线”虚拟对手。 | false, true |

代表行：
```json
{"id": "npc_andk", "name": "藍井 撫子", "assetId": "exam-audition_andk"}
{"id": "npc_nia_08", "name": "有馬 りおん", "assetId": "exam-audition_mob_03"}
```

### ProduceExamGimmickEffectGroup（3707 行）

试炼场地效果（ギミック）时间表：同一 id 多行，priority 排序，startTurn 起生效，可带 fieldStatus 条件（如“元気≤5 时体力-2”），效果为 produceExamEffectId；isPositive 区分正/负面。PvpRateConfig.stages 与 ProduceStepAuditionDifficulty 引用。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_e_gim-exam_card_play_aggressive-0-pro…", "p_e_gim-exam_card_play_aggressive-0-pro…" |
| `priority` | int32 | 100% | 同组排序。 | 1, 2 |
| `remainingTurnPermil` | int32 | 0% | 未使用(0)。 | 0 |
| `startTurn` | int32 | 100% | 生效起始回合。 | 2, 4 |
| `remainingTurn` | int32 | 0% | 未使用(0)。 | 0 |
| `fieldStatusType` | ProduceExamFieldStatusType | 100% | ProduceExamFieldStatusType 条件。 | "ProduceExamFieldStatusType_Unknown", "ProduceExamFieldStatusType_BlockUp" |
| `fieldStatusValue` | int32 | 67% | 条件阈值。 | 0, 6 |
| `fieldStatusCheckType` | ProduceExamTriggerCheckType | 100% | Not=取反。 | "ProduceExamTriggerCheckType_Unknown", "ProduceExamTriggerCheckType_Not" |
| `produceExamEffectId` | string | 100% | → ProduceExamEffect（考试内原子效果）。 | "e_effect-exam_card_play_aggressive-0001", "e_effect-exam_stamina_damage-0002" |
| `fieldStatusProduceCardSearchId` | string | 0% | 未使用。 |  |
| `isPositive` | bool | 76% | 正面效果标记。 | true, false |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) やる気+1", "(渲染) 元気が5以下の場合、体力減少2" |

外键（按 id 连接验证）：
- `produceExamEffectId` → **ProduceExamEffect** (428/428 命中)
- `produceDescriptions.targetId` → **ProduceDescriptionLabel** (57/58 命中)
- `produceDescriptions.originProduceExamEffectId` → **ProduceExamEffect** (428/428 命中)

代表行：
```json
{"id": "p_e_gim-exam_card_play_aggressive-0-produce-001-da-hard-final", "priority": 1, "startTurn": 2, "produceExamEffectId": "e_effect-exam_card_play_aggressive-0001", "isPositive": true, "produceDescriptions": "(渲染) やる気+1"}
{"id": "p_exam_gimmick-produce-001-exam_card_play_aggressive_01-lesson_sp-after_mid", "priority": 4, "startTurn": 6, "fieldStatusType": "ProduceExamFieldStatusType_BlockUp", "fieldStatusValue": 20, "produceExamEffectId": "e_effect-exam_block-0004", "isPositive": true, "produceDescriptions": "(渲染) 元気が20以上の場合、元気+4"}
```

### ProduceStepEventDetail（6888 行）

周程事件（6888）：角色事件(Character/CharacterGrowth/IdolCard/SupportCard) 与 学園活動事件(School/Business/Activity)。id 编码含来源；effect 直接给 produceEffectIds，或给出选项列表 produceStepEventSuggestionIds（お出かけ/授業/営业的选择肢）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "event-detail-001-p_story-001-after-audi…", "event-detail-001-p_story-001-after-audi…" |
| `suggestionType` | ProduceEventSuggestionType | 100% | 全 Primary。 | "ProduceEventSuggestionType_Primary" |
| `produceStoryId` | string | 43% | → ProduceStory（角色事件对应的具体剧情）。 | "p_story-001-amao-after-audition-final-f…", "p_story-001-amao-after-audition-final-n…" |
| `produceStoryGroupId` | string | 57% | → ProduceStoryGroup（按角色展开的剧情组）。 | "p_story-001-after-audition-final-failur…", "p_story-001-after-audition-mid-failure-…" |
| `produceEffectIds` | repeated string | 63% | → ProduceEffect 列表。 | ["p_effect-vocal_addition-0030_0030", "p_effect-dance_addition-0030_0030", "p_effect-visual_addition-0030_0030"], ["p_effect-vocal_addition-0020_0020", "p_effect-dance_addition-0020_0020", "p_effect-visual_addition-0020_0020"] |
| `produceStepEventSuggestionIds` | repeated string | 76% | → ProduceStepEventSuggestion（选项）。 | ["p_s_e_s-event-detail-001-p_story-001-am…", "p_s_e_s-event-detail-001-p_story-001-am…"], ["p_s_e_s-event-detail-001-p_story-001-am…", "p_s_e_s-event-detail-001-p_story-001-am…"] |
| `supportCardId` | string | 7% | → SupportCard。 | "s_card-1-0000", "s_card-1-0001" |
| `eventType` | ProduceEventType | 100% | ProduceEventType。 | "ProduceEventType_Character", "ProduceEventType_CharacterGrowth" |
| `eventCharacterType` | ProduceEventCharacterType | 100% | ProduceEventCharacterType（Opening/AfterStep1/AfterAuditionMid1/Ending/Failure…触发时机）。 | "ProduceEventCharacterType_Failure", "ProduceEventCharacterType_AfterStep1" |
| `isBusinessExcellent` | bool | 25% | 营业(Business)事件的“大成功”版本标记。 | false, true |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 63% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) ボーカル上昇+30 / ダンス上昇+30 / ビジュアル上昇+30", "(渲染) ボーカル上昇+20 / ダンス上昇+20 / ビジュアル上昇+20" |

外键（按 id 连接验证）：
- `produceStoryId` → **ProduceStory** (1874/1874 命中)
- `produceStoryGroupId` → **ProduceStoryGroup** (151/151 命中)
- `produceEffectIds` → **ProduceEffect** (257/257 命中)
- `produceStepEventSuggestionIds` → **ProduceStepEventSuggestion** (3048/3048 命中)
- `supportCardId` → **SupportCard** (201/201 命中)
- `produceDescriptions.targetId` → ProduceItem? (134/195 = 69%，多态或部分引用)

代表行：
```json
{"id": "event-detail-001-p_story-001-after-audition-final-failure-01", "suggestionType": "ProduceEventSuggestionType_Primary", "produceStoryGroupId": "p_story-001-after-audition-final-failure-01", "eventType": "ProduceEventType_Character", "eventCharacterType": "ProduceEventCharacterType_Failure"}
{"id": "event-detail-business-produce_005-plan1-produce_point-before_1st-02-073", "suggestionType": "ProduceEventSuggestionType_Primary", "produceStoryGroupId": "p_story-event-002_business-2-2-1", "produceEffectIds": ["p_effect-vote_count_addition-2400_2400"], "produceStepEventSuggestionIds": ["p_s_e_s-event-detail-business-produce_005-before_1st-produce_point-plan1-vocal-parameter_…", "p_s_e_s-event-detail-business-produce_005-before_1st-produce_point-plan1-dance-lesson_buff", "p_s_e_s-event-detail-business-produce_005-before_1st-produce_point-plan1-visual-active"], "eventType": "ProduceEventType_Business", "produceDescriptions": "(渲染) ファン投票数+2400"}
```

### ProduceStepEventSuggestion（3066 行）

事件选项：消耗 P点/体力，给予 produceEffectIds；可带成功率 successProbabilityPermyriad（万分比）与成功/失败分支效果及后续事件(successStepId)。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_s_e_s-event-detail-001-p_story-001-am…", "p_s_e_s-event-detail-001-p_story-001-am…" |
| `producePoint` | int32 | 14% | 消耗 P点。 | 0, 100 |
| `stamina` | int32 | 18% | 消耗体力。 | 0, 5 |
| `produceCardId` | string | 8% | → ProduceCard（注意 ProduceCard 主键是 (id, upgradeCount)）。 | "p_card-00-acc-0_002" |
| `produceCardUpgradeCount` | int32 | 0% | 赠卡强化段。 | 0 |
| `produceEffectIds` | repeated string | 83% | → ProduceEffect 列表。 | ["p_effect-produce_reward_set-p_rd-drink_…"], ["p_effect-produce_reward_set-p_rd-produc…"] |
| `stepType` | ProduceStepType | 100% | 后续周程类型。 | "ProduceStepType_Unknown", "ProduceStepType_EventActivity" |
| `stepId` | string | 13% | 后续周程/事件 id（多为 event-detail-activity-*，少数 exam-*）。 | "event-detail-activity-produce_004-05-17…", "event-detail-activity-produce_004-06-17…" |
| `successProbabilityPermyriad` | int32 | 3% | 成功率（万分比，0=无判定）。 | 0, 10000 |
| `successProduceEffectIds` | repeated string | 3% | 成功效果。 | ["p_effect-produce_card_upgrade-0001_0001…"], ["p_effect-produce_reward_set-p_rd-produc…"] |
| `successStepType` | ProduceStepType | 100% | 成功后周程类型。 | "ProduceStepType_Unknown", "ProduceStepType_EventActivity" |
| `successStepId` | string | 1% | → ProduceStepEventDetail 成功后事件。 | "event-detail-activity-001-atbm-017-1", "event-detail-activity-001-hmsz-017-1" |
| `failProduceEffectIds` | repeated string | 2% | 失败效果。 | ["p_effect-produce_reward-0001_0001-produ…"], ["p_effect-vocal_addition-0040_0040"] |
| `failStepType` | ProduceStepType | 100% | 未使用。 | "ProduceStepType_Unknown" |
| `failStepId` | string | 0% | 未使用。 |  |
| `alwaysSuccessful` | bool | 97% | 无判定=true。 | true, false |
| `produceEffectFireStep` | int32 | 0% | 未使用(0)。 | 0 |
| `isCampaign` | bool | 0% | 未使用(false)。 | false |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) 特定のPドリンクを選択して獲得", "(渲染) スキルカードを選択して獲得" |

外键（按 id 连接验证）：
- `produceCardId` → **ProduceCard** (1/1 命中)
- `produceEffectIds` → **ProduceEffect** (229/229 命中)
- `stepId` → ProduceStepEventDetail? (2/45 = 4%，多态或部分引用)
- `successProduceEffectIds` → **ProduceEffect** (5/5 命中)
- `successStepId` → **ProduceStepEventDetail** (26/26 命中)
- `failProduceEffectIds` → **ProduceEffect** (7/7 命中)
- `produceDescriptions.targetId` → ProduceDescriptionLabel? (6/7 = 86%，多态或部分引用)

代表行：
```json
{"id": "p_s_e_s-event-detail-001-p_story-001-amao-opening-true-01-01", "produceEffectIds": ["p_effect-produce_reward_set-p_rd-drink_set-produce_start-r-select-01_01"], "alwaysSuccessful": true, "produceDescriptions": "(渲染) 特定のPドリンクを選択して獲得"}
{"id": "p_s_e_s-event-detail-business-produce_005-before_3rd-produce_card-plan3-dance-concentrati…", "produceEffectIds": ["p_effect-dance_addition-0130_0130", "p_effect-produce_reward_set-p_rd-produce-004-business-before_3rd-exam_concentration-upgra…"], "alwaysSuccessful": true, "produceDescriptions": "(渲染) ダンス上昇+130 / 強気・温存関係の強化済みスキルカードを選択して獲得"}
```

### ProduceEventCharacterGrowth（39 行）

角色成长事件（每角色 3 个）：达到某维参数阈值(vocal/dance/visual)后触发 produceStepEventDetailId。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `title` | string | 100% | 标题。 | "新しい自分", "成長できる証" |
| `description` | string | 100% | 说明文（日文）。 | "ビジュアル300以上", "ボーカル450以上" |
| `vocal` | int32 | 36% | 触发阈值。 | 0, 450 |
| `dance` | int32 | 36% | 。 | 0, 1000 |
| `visual` | int32 | 28% | 。 | 300, 0 |
| `produceStepEventDetailId` | string | 100% | → ProduceStepEventDetail。 | "event-detail-001-p_story-001-amao-fb-01", "event-detail-001-p_story-001-amao-fb-02" |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `produceStepEventDetailId` → **ProduceStepEventDetail** (39/39 命中)

代表行：
```json
{"characterId": "amao", "number": 1, "title": "新しい自分", "description": "ビジュアル300以上", "visual": 300, "produceStepEventDetailId": "event-detail-001-p_story-001-amao-fb-01"}
{"characterId": "hume", "number": 2, "title": "底知れぬ才能", "description": "ボーカル450以上", "vocal": 450, "produceStepEventDetailId": "event-detail-001-p_story-001-hume-fb-02"}
```

### ProduceEventSupportCard（511 行）

支援卡事件：每张支援卡 3 个事件，需要 supportCardLevel(1/20/40) 才解锁。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `supportCardId` | string | 100% | → SupportCard。 | "s_card-1-0000", "s_card-1-0001" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `supportCardLevel` | int32 | 100% | 解锁等级。 | 1, 20 |
| `produceStepEventDetailId` | string | 100% | → ProduceStepEventDetail。 | "event-detail-s_card-1-0000-01", "event-detail-s_card-1-0000-02" |

外键（按 id 连接验证）：
- `supportCardId` → **SupportCard** (201/201 命中)
- `produceStepEventDetailId` → **ProduceStepEventDetail** (511/511 命中)

代表行：
```json
{"supportCardId": "s_card-1-0000", "number": 1, "supportCardLevel": 1, "produceStepEventDetailId": "event-detail-s_card-1-0000-01"}
{"supportCardId": "s_card-3-0023", "number": 3, "supportCardLevel": 40, "produceStepEventDetailId": "event-detail-s_card-3-0023-03"}
```

### ProduceStepTransition（3228 行）

（备注）周程前后过场：角色 × stepType × Before/After 的 ADV/语音/服装。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `stepType` | ProduceStepType | 100% | ProduceStepType（周程类型：LessonXxx / AuditionMid1/Mid2/Final / EventXxx / Present / Refresh / OpenLesson / SelfLesson ...）。 | "ProduceStepType_LessonVocalNormal", "ProduceStepType_LessonVocalSp" |
| `stepPhaseType` | ProduceStepPhaseType | 100% | Before/After。 | "ProduceStepPhaseType_Before", "ProduceStepPhaseType_After" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `costumeHeadId` | string | 43% | 外键/引用 id（见 FK）。 | "costume_head_amao-casl-0000", "costume_head_atbm-schl-0000" |
| `costumeId` | string | 43% | 外键/引用 id（见 FK）。 | "amao-casl-0000", "amao-trng-0000" |
| `advAssetId` | string | 100% | ADV。 | "adv_pstep_001_cmmn_before-lesson-01-c", "adv_pstep_001_cmmn_before-lesson-04-c" |
| `voiceAssetId` | string | 100% | 语音资源 id。 | "sud_vo_system_pstep_amao_before-lesson-…", "sud_vo_system_pstep_amao_before-lesson-…" |
| `produceGroupId` | string | 0% | → ProduceGroup（剧本系列：初 / N.I.A / H.I.F）。 |  |
| `produceIds` | repeated string | 39% | 外键/引用 id（见 FK）。 | ["produce-007", "produce-008"] |
| `unitCharacterIds` | repeated string | 1% | 外键/引用 id（见 FK）。 | ["ssmk"], ["kllj"] |
| `unitCharacterCostumeHeadIds` | repeated string | 1% | 外键/引用 id（见 FK）。 | ["costume_head_ssmk-schl-0000"], ["costume_head_kllj-schl-0000"] |
| `unitCharacterCostumeIds` | repeated string | 1% | 外键/引用 id（见 FK）。 | ["ssmk-schl-0000"], ["kllj-schl-0000"] |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `costumeHeadId` → **CostumeHead** (13/13 命中)
- `costumeId` → **Costume** (21/21 命中)
- `produceIds` → **Produce** (2/2 命中)
- `unitCharacterIds` → **Character** (2/2 命中)
- `unitCharacterCostumeHeadIds` → **CostumeHead** (2/2 命中)
- `unitCharacterCostumeIds` → **Costume** (2/2 命中)

代表行：
```json
{"characterId": "amao", "stepType": "ProduceStepType_LessonVocalNormal", "stepPhaseType": "ProduceStepPhaseType_Before", "number": 1, "costumeHeadId": "costume_head_amao-casl-0000", "costumeId": "amao-casl-0000", "advAssetId": "adv_pstep_001_cmmn_before-lesson-01-c", "voiceAssetId": "sud_vo_system_pstep_amao_before-lesson-01"}
{"characterId": "hume", "stepType": "ProduceStepType_OpenLessonVocalSp", "stepPhaseType": "ProduceStepPhaseType_After", "number": 3, "costumeHeadId": "costume_head_hume-schl-0000", "costumeId": "hume-schl-0000", "advAssetId": "adv_pstep_003_cmmn_after-lesson-param-02-b", "voiceAssetId": "sud_vo_system_pstep_hume_after-lesson-03", "produceIds": ["produce-007", "produce-008"]}
```

### ProduceStepFanPresentMotion（39 行）

（仅备注）粉丝礼物周程的角色动作。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `motionType` | ProduceStepFanPresentMotionType | 100% | Reaction/Wait。 | "ProduceStepFanPresentMotionType_Reaction", "ProduceStepFanPresentMotionType_Wait" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `facialAssetIds` | repeated string | 15% | 外键/引用 id（见 FK）。 | ["mot_all_chr_cmmn_facial-all-ikari1-egao…"], ["mot_all_chr_cmmn_facial-all-jiai1-egao1…"] |
| `bodyAssetIds` | repeated string | 100% | 外键/引用 id（见 FK）。 | ["mot_all_chr_amao_glad-001_in"], ["mot_all_chr_amao_glad-003_in"] |
| `voiceAssetId` | string | 67% | 语音资源 id。 | "sud_vo_system_amao_produce_fanpresent-01", "sud_vo_system_amao_produce_fanpresent-02" |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `facialAssetIds` → AssetDownload? (2/4 = 50%，多态或部分引用)
- `bodyAssetIds` → AssetDownload? (16/38 = 42%，多态或部分引用)

代表行：
```json
{"characterId": "amao", "motionType": "ProduceStepFanPresentMotionType_Reaction", "number": 1, "bodyAssetIds": ["mot_all_chr_amao_glad-001_in"], "voiceAssetId": "sud_vo_system_amao_produce_fanpresent-01"}
{"characterId": "hume", "motionType": "ProduceStepFanPresentMotionType_Reaction", "number": 2, "bodyAssetIds": ["mot_all_chr_cmmn_tereru-b-002_in"], "voiceAssetId": "sud_vo_system_hume_produce_fanpresent-02"}
```

## 5. C. 技能卡

### ProduceCard（1714 行）

技能卡（スキルカード）。主键 (id, upgradeCount)：同一 id 有 0/1（部分 legend 到 2/3）多行，name 带 '+'。id 编码 `p_card-{00共通|01センス|02ロジック|03アノマリー}-{act|men|acc(トラブル)|sup(支援卡来源)|ido(偶像固有)}-{稀有度 0N/1R/2SR/3SSR/100Legend}_{序号}`。打牌语义 = playProduceExamTriggerId（使用条件）+ playEffects（按序结算的 ProduceExamEffect，可各带附加条件）+ playMovePositionType（用后去向）+ 成长(produceCardStatusEnchantId)。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_card-00-acc-0_002", "p_card-00-act-0_001" |
| `upgradeCount` | int32 | 74% | 强化段数（0=未强化，1=+，2/3 见 legend 卡）。 | 0, 1 |
| `name` | string | 100% | 显示名（日文）。 | "眠気", "アピールの基本" |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "img_general_skillcard_acc-0_002", "img_general_skillcard_act-0_001" |
| `isCharacterAsset` | bool | 29% | 使用角色专属立绘。 | false, true |
| `voiceAssetId` | string | 0% | 语音资源 id。 | "sud_vo_system_cidol-jsna-3-015_produce_…", "sud_vo_system_cidol-hrnm-3-013_produce_…" |
| `rarity` | ProduceCardRarity | 100% | 稀有度枚举。 | "ProduceCardRarity_N", "ProduceCardRarity_Sr" |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Common", "ProducePlanType_Plan1" |
| `category` | ProduceCardCategory | 100% | ProduceCardCategory：ActiveSkill / MentalSkill / Trouble。 | "ProduceCardCategory_Trouble", "ProduceCardCategory_ActiveSkill" |
| `stamina` | int32 | 67% | 体力消耗（受元気抵扣、消費体力減少/増加 影响）。 | 0, 4 |
| `forceStamina` | int32 | 12% | 体力消費(无视元気)：直接扣体力的费用。 | 0, 1 |
| `costType` | ExamCostType | 100% | ExamCostType：非体力费用种类（好調/集中/好印象/やる気/全力値/絶好調）。 | "ExamCostType_Unknown", "ExamCostType_ExamLessonBuff" |
| `costValue` | int32 | 9% | 非体力费用数值。 | 0, 5 |
| `playProduceExamTriggerId` | string | 13% | → ProduceExamTrigger，使用条件（例：元気 0、好調中、強気2段）。 | "e_trigger-exam_start_turn-condition_thr…", "e_trigger-exam_start_turn-no_block" |
| `playEffects` | repeated PlayEffect | 100% | 效果列表（结构见 §2）。 | [{"produceExamTriggerId": "", "produceExamEffectId": "e_effect-exam_lesson-0009-01", "hideIcon": false, "isOncePlayEffect": false}], [{"produceExamTriggerId": "", "produceExamEffectId": "e_effect-exam_lesson-0014-01", "hideIcon": false, "isOncePlayEffect": false}] |
| `playMovePositionType` | ProduceCardMovePositionType | 100% | 用后去向：Grave=弃牌堆 / Lost=除外（レッスン中1回）。 | "ProduceCardMovePositionType_Lost", "ProduceCardMovePositionType_Grave" |
| `moveEffectTriggerType` | ProduceCardMoveEffectTriggerType | 100% | ProduceCardMoveEffectTriggerType：移动到 Hand/Hold 时触发 moveProduceExamEffectIds。 | "ProduceCardMoveEffectTriggerType_Unknown", "ProduceCardMoveEffectTriggerType_Hand" |
| `moveProduceExamEffectIds` | repeated string | 0% | 移动时效果。 | ["e_effect-exam_block-0005"], ["e_effect-exam_card_play_aggressive-0003"] |
| `isEndTurnLost` | bool | 0% | 未使用(false)。 | false |
| `isInitial` | bool | 5% | レッスン開始時手札に入る。 | false, true |
| `isRestrict` | bool | 0% | 未使用(false)。 | false |
| `produceCardStatusEnchantId` | string | 3% | → ProduceCardStatusEnchant，成长(成長)规则。 | "card_enchant-e_trigger-exam_stance_chan…", "card_enchant-e_trigger-exam_stance_chan…" |
| `searchTag` | string | 46% | 标签：starter / idol-unique（ProduceCardSearch.cardSearchTag 用）。 | "starter", "idol-unique" |
| `libraryHidden` | bool | 1% | 图鉴（ピクチャーブック）中隐藏。 | false, true |
| `noDeckDuplication` | bool | 72% | 重複不可（卡组内只能一张）。 | false, true |
| `isReward` | bool | 0% | 未使用。 | false |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) レッスン中1回", "(渲染) パラメータ+9" |
| `unlockProducerLevel` | int32 | 28% | 解锁所需 P 等级。 | 0, 3 |
| `rentalUnlockProducerLevel` | int32 | 28% | 租借解锁等级。 | 0, 1 |
| `evaluation` | int32 | 46% | 评价分：用于メモリー/编成强度评估（越高越强）。 | 5, 0 |
| `originIdolCardId` | string | 36% | → IdolCard，偶像固有卡来源。 | "i_card-hski-1-000", "i_card-ttmr-1-000" |
| `originSupportCardId` | string | 13% | → SupportCard，支援卡来源（sup 卡）。 | "s_card-2-0000", "s_card-2-0002" |
| `isInitialDeckProduceCard` | bool | 14% | 初始卡组卡（アピールの基本 等）。 | false, true |
| `effectGroupIds` | repeated string | 100% | → EffectGroup。把效果归入“xx效果”组，用于筛选（例如“好調効果のスキルカード”这类条件就是按 effectGroup 匹配）。 | ["effect_group-visible-exam_lesson-000"], ["effect_group-visible-exam_lesson-000", "effect_group-visible-exam_block-000"] |
| `produceCardCustomizeIds` | repeated string | 41% | → ProduceCardCustomize，可选定制方案。 | ["p_card_custom-040_070-g_effect-block_ad…", "p_card_custom-100-g_effect-lesson_count…", "p_card_custom-040_070-g_effect-lesson_a…"], ["p_card_custom-040_040_070-g_effect-bloc…", "p_card_custom-040_040_070-g_effect-stam…", "p_card_custom-070-g_effect-initial_add"] |
| `maxCustomizeCount` | int32 | 41% | 最大定制次数（2/3）。 | 0, 2 |
| `isConversion` | bool | 5% | 由 ProduceCardConversion 转换得到的卡。 | false, true |
| `moveProduceExamTriggerIds` | repeated string | 0% | 未使用。 |  |
| `originCharacterId` | string | 1% | → Character（nasr 专属卡）。 | "nasr" |
| `originPrimaStellaIdolCardId` | string | 1% | → IdolCard，プリマステラ(H.I.F 一番星) 专属卡来源。 | "i_card-amao-3-015", "i_card-ssmk-3-012" |
| `viewStartTime` | int64 | 100% | 可见起始时间，Unix 毫秒字符串；"0" 表示一直可见。 | "0", "1716339600000" |
| `isLimited` | bool | 0% | 限定标记（全库均为 false）。 | false |
| `order` | int64 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | "13000010000002", "11000010000001" |
| &nbsp;&nbsp;↳ `produceExamTriggerId` | string | 8% | 该条效果的附加发动条件（空=无条件）。 | "e_trigger-exam_card_play-stamina_up_mul…", "e_trigger-none-stamina_up_multiple-500" |
| &nbsp;&nbsp;↳ `produceExamEffectId` | string | 100% | → ProduceExamEffect。 | "e_effect-exam_lesson-0009-01", "e_effect-exam_lesson-0014-01" |
| &nbsp;&nbsp;↳ `hideIcon` | bool | 0% | 不显示效果图标。 | false, true |
| &nbsp;&nbsp;↳ `isOncePlayEffect` | bool | 0% | 每场只发动一次的效果（用于 再演 ExamStatusEnchantEncore 等）。 | false, true |

外键（按 id 连接验证）：
- `assetId` → AssetDownload? (92/448 = 21%，多态或部分引用)
- `playProduceExamTriggerId` → **ProduceExamTrigger** (39/39 命中)
- `moveProduceExamEffectIds` → **ProduceExamEffect** (5/5 命中)
- `produceCardStatusEnchantId` → **ProduceCardStatusEnchant** (21/21 命中)
- `produceDescriptions.targetId` → ProduceDescriptionLabel? (74/83 = 89%，多态或部分引用)
- `produceDescriptions.originProduceExamTriggerId` → **ProduceExamTrigger** (66/66 命中)
- `produceDescriptions.originProduceExamEffectId` → **ProduceExamEffect** (679/679 命中)
- `produceDescriptions.originProduceCardStatusEnchantId` → **ProduceCardStatusEnchant** (21/21 命中)
- `originIdolCardId` → **IdolCard** (151/151 命中)
- `originSupportCardId` → **SupportCard** (57/57 命中)
- `effectGroupIds` → **EffectGroup** (34/34 命中)
- `produceCardCustomizeIds` → **ProduceCardCustomize** (241/241 命中)
- `originCharacterId` → **Character** (1/1 命中)
- `originPrimaStellaIdolCardId` → **IdolCard** (10/10 命中)
- `playEffects.produceExamTriggerId` → **ProduceExamTrigger** (43/43 命中)
- `playEffects.produceExamEffectId` → **ProduceExamEffect** (678/678 命中)

代表行：
```json
{"id": "p_card-00-acc-0_002", "name": "眠気", "assetId": "img_general_skillcard_acc-0_002", "rarity": "ProduceCardRarity_N", "planType": "ProducePlanType_Common", "category": "ProduceCardCategory_Trouble", "playMovePositionType": "ProduceCardMovePositionType_Lost", "produceDescriptions": "(渲染) レッスン中1回", "evaluation": 5, "viewStartTime": "0", "order": "13000010000002"}
{"id": "p_card-02-ido-2_107", "upgradeCount": 3, "name": "紫電一閃+++", "assetId": "img_general_skillcard_ido-2_107", "rarity": "ProduceCardRarity_Sr", "planType": "ProducePlanType_Plan2", "category": "ProduceCardCategory_ActiveSkill", "stamina": 4, "playEffects": [{"produceExamTriggerId": "", "produceExamEffectId": "e_effect-exam_review-0004", "hideIcon": false, "isOncePlayEffect": false}, {"produceExamTriggerId": "", "produceExamEffectId": "e_effect-exam_status_enchant-04-inf-enchant-p_card-02-ido-2_107-enc01", "hideIcon": false, "isOncePlayEffect": false}], "playMovePositionType": "ProduceCardMovePositionType_Lost", "searchTag": "idol-unique", "noDeckDuplication": true, "produceDescriptions": "(渲染) 好印象+4 / 以降4回まで、ターン終了時、やる気が6以上の場合、好印象の80%分パラメータ上昇 / 重複不可 レッスン中1回", "originIdolCardId": "i_card-atbm-2-000", "effectGroupIds": ["effect_group-visible-exam_lesson_depend_exam_review-000", "effect_group-visible-exam_lesson-000", "effect_group-visible-exam_status_enchant-000", "effect_group-visible-exam_review-000"], "viewStartTime": "1763258400000", "order": "38020010630107"}
```

### ProduceCardTag（3 行）

卡牌标签字典：idol-unique / starter / strike（レッスンメニュー）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "idol-unique", "starter" |
| `name` | string | 100% | 显示名（日文）。 | "アイドル固有スキルカード", "スタータースキルカード" |

代表行：
```json
{"id": "idol-unique", "name": "アイドル固有スキルカード"}
{"id": "starter", "name": "スタータースキルカード"}
```

### ProduceCardSearch（280 行）

**卡牌筛选器**（280）：几乎所有“对象选择/条件计数”都通过它表达：位置(cardPositionType)、类别、稀有度、指定卡 id、标签、effectGroup、体力区间、随机池；isSelf=自身。produceDescriptions 给出人读描述（如“手札のアクティブスキルカード”）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_card_search-active_skill-deck_all", "p_card_search-active_skill-deck_all-eff…" |
| `cardRarities` | repeated ProduceCardRarity | 6% | 稀有度过滤。 | ["ProduceCardRarity_N", "ProduceCardRarity_R", "ProduceCardRarity_Sr", "ProduceCardRarity_Ssr"], ["ProduceCardRarity_Sr"] |
| `produceCardIds` | repeated string | 60% | → ProduceCard 列表（可重复表示多张）。 | ["p_card-00-act-0_001"], ["p_card-00-act-0_001", "p_card-01-act-0_023"] |
| `upgradeCounts` | repeated int32 | 0% | 强化段过滤。 | [1] |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Unknown", "ProducePlanType_Plan1" |
| `cardCategories` | repeated ProduceCardCategory | 8% | 类别过滤。 | ["ProduceCardCategory_ActiveSkill"], ["ProduceCardCategory_ActiveSkill", "ProduceCardCategory_MentalSkill"] |
| `cardStatusType` | ProduceCardSearchStatusType | 100% | 未使用。 | "ProduceCardSearchStatusType_Unknown" |
| `orderType` | ProduceCardOrderType | 100% | ProduceCardOrderType：First=按顺序取 / Random。 | "ProduceCardOrderType_Unknown", "ProduceCardOrderType_First" |
| `cardPositionType` | ProduceCardPositionType | 100% | ProduceCardPositionType：Deck/DeckAll/DeckGrave/Hand/Hold/Lost/NotLost/Playing(正在使用的卡)/Target(效果目标)/RandomPool。 | "ProduceCardPositionType_DeckAll", "ProduceCardPositionType_DeckGrave" |
| `cardSearchTag` | string | 2% | → ProduceCardTag。 | "idol-unique", "starter" |
| `produceCardRandomPoolId` | string | 4% | → ProduceCardPool/RandomPool（生成随机卡用）。 | "p_random_pool-all-upgrade_1", "p_random_pool-produce_007-create_set-ca…" |
| `limitCount` | int32 | 20% | 数量上限（如“1枚”）。 | 0, 3 |
| `staminaMinMaxType` | ConditionMinMaxType | 100% | 体力费用区间判定类型。 | "ConditionMinMaxType_Unknown", "ConditionMinMaxType_MinMax" |
| `staminaMin` | int32 | 1% | 。 | 0, 4 |
| `staminaMax` | int32 | 1% | 。 | 0, 99 |
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_Unknown" |
| `effectGroupIds` | repeated string | 12% | → EffectGroup。把效果归入“xx效果”组，用于筛选（例如“好調効果のスキルカード”这类条件就是按 effectGroup 匹配）。 | ["effect_group-visible-exam_full_power-000"], ["effect_group-visible-exam_block-000"] |
| `isSelf` | bool | 1% | 对象=自身。 | false, true |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) アクティブスキルカード", "(渲染) 全力効果のアクティブスキルカード" |
| `produceCardPoolId` | string | 4% | → ProduceCardPool。 | "p_random_pool-all-upgrade_1", "p_random_pool-produce_007-create_set-ca…" |
| `costType` | ExamCostType | 100% | 未使用。 | "ExamCostType_Unknown" |
| `isCustomized` | bool | 0% | 未使用。 | false |

外键（按 id 连接验证）：
- `produceCardIds` → **ProduceCard** (133/133 命中)
- `produceCardRandomPoolId` → **ProduceCardPool** (10/10 命中)
- `effectGroupIds` → **EffectGroup** (11/11 命中)
- `produceDescriptions.targetId` → ProduceCard? (133/152 = 88%，多态或部分引用)
- `produceCardPoolId` → **ProduceCardPool** (10/10 命中)

代表行：
```json
{"id": "p_card_search-active_skill-deck_all", "cardCategories": ["ProduceCardCategory_ActiveSkill"], "cardPositionType": "ProduceCardPositionType_DeckAll", "produceDescriptions": "(渲染) アクティブスキルカード"}
{"id": "p_card_search-ssr-random-deck_grave-3", "cardRarities": ["ProduceCardRarity_Ssr"], "orderType": "ProduceCardOrderType_Random", "cardPositionType": "ProduceCardPositionType_DeckGrave", "limitCount": 3, "produceDescriptions": "(渲染) ランダムな山札か捨札にあるスキルカード（SSR）3枚"}
```

### ProduceCardPool（10 行）

随机卡池（嵌套 produceCardRatios：卡 id、强化段、权重）。与 ProduceCardRandomPool 内容相同（一个是嵌套形式一个是展开行）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_random_pool-all-upgrade_1", "p_random_pool-produce_007-create_set-ca…" |
| `produceCardRatios` | repeated ProduceCardRatio | 100% | 权重列表。 | [{"id": "p_card-00-men-1_007", "upgradeCount": 1, "ratio": 1}, {"id": "p_card-00-men-1_005", "upgradeCount": 1, "ratio": 1}, {"id": "p_card-00-act-2_009", "upgradeCount": 1, "ratio": 1}, {"id": "p_card-00-men-2_012", "upgradeCount": 1, "ratio": 1}, {"id": "p_card-00-men-2_014", "upgradeCount": 1, "ratio": 1}, "…(+159)"], [{"id": "p_card-02-act-0_037", "upgradeCount": 0, "ratio": 25}, {"id": "p_card-02-act-0_038", "upgradeCount": 0, "ratio": 25}, {"id": "p_card-02-men-0_039", "upgradeCount": 0, "ratio": 75}, {"id": "p_card-02-men-0_041", "upgradeCount": 0, "ratio": 25}] |
| &nbsp;&nbsp;↳ `id` | string | 100% | → ProduceCard。 | "p_card-00-men-1_007", "p_card-00-men-1_005" |
| &nbsp;&nbsp;↳ `upgradeCount` | int32 | 91% | 强化段。 | 1, 0 |
| &nbsp;&nbsp;↳ `ratio` | int32 | 100% | 权重。 | 1, 25 |

代表行：
```json
{"id": "p_random_pool-all-upgrade_1", "produceCardRatios": [{"id": "p_card-00-men-1_007", "upgradeCount": 1, "ratio": 1}, {"id": "p_card-00-men-1_005", "upgradeCount": 1, "ratio": 1}, {"id": "p_card-00-act-2_009", "upgradeCount": 1, "ratio": 1}, {"id": "p_card-00-men-2_012", "upgradeCount": 1, "ratio": 1}, {"id": "p_card-00-men-2_014", "upgradeCount": 1, "ratio": 1}, "…(+159)"]}
{"id": "p_random_pool-produce_007-create_set-review", "produceCardRatios": [{"id": "p_card-02-men-0_035", "upgradeCount": 0, "ratio": 25}, {"id": "p_card-02-act-0_032", "upgradeCount": 0, "ratio": 50}, {"id": "p_card-02-men-0_034", "upgradeCount": 0, "ratio": 50}, {"id": "p_card-02-men-0_036", "upgradeCount": 0, "ratio": 25}]}
```

### ProduceCardRandomPool（313 行）

随机卡池展开行形式（id=池，每行一张卡+权重）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_random_pool-all-upgrade_1", "p_random_pool-produce_007-create_set-ca…" |
| `produceCardId` | string | 100% | → ProduceCard（注意 ProduceCard 主键是 (id, upgradeCount)）。 | "p_card-00-act-2_009", "p_card-00-men-1_005" |
| `upgradeCount` | int32 | 92% | 强化段数（0=未强化，1=+，2/3 见 legend 卡）。 | 1, 0 |
| `ratio` | int32 | 100% | 权重。 | 1, 3 |

外键（按 id 连接验证）：
- `produceCardId` → **ProduceCard** (253/253 命中)

代表行：
```json
{"id": "p_random_pool-all-upgrade_1", "produceCardId": "p_card-00-act-2_009", "upgradeCount": 1, "ratio": 1}
{"id": "p_random_pool-produce_007-create_set-card_play_aggressive", "produceCardId": "p_card-02-men-0_039", "ratio": 3}
```

### ProduceCardConversion（21 行）

卡牌转换（P 等级解锁后 before→after 的替换，例如 R 卡换成新版本）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `beforeProduceCardId` | string | 100% | → ProduceCard。 | "p_card-01-act-1_019", "p_card-01-act-2_002" |
| `afterProduceCardId` | string | 100% | → ProduceCard。 | "p_card-01-act-1_069", "p_card-01-men-2_110" |
| `conditionSetId` | string | 100% | → ConditionSet（P等级）。 | "cd_producer_level-052", "cd_producer_level-056" |
| `isNotReward` | bool | 100% | 全 true。 | true |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 2101052, 3101056 |

外键（按 id 连接验证）：
- `beforeProduceCardId` → **ProduceCard** (21/21 命中)
- `afterProduceCardId` → **ProduceCard** (21/21 命中)
- `conditionSetId` → **ConditionSet** (13/13 命中)

代表行：
```json
{"beforeProduceCardId": "p_card-01-act-1_019", "afterProduceCardId": "p_card-01-act-1_069", "conditionSetId": "cd_producer_level-052", "isNotReward": true, "order": 2101052}
{"beforeProduceCardId": "p_card-02-act-3_001", "afterProduceCardId": "p_card-02-act-3_187", "conditionSetId": "cd_producer_level-079", "isNotReward": true, "order": 4102079}
```

### ProduceCardCustomize（343 行）

卡牌定制方案：customizeCount 段（1..3）分别给一组成长效果(produceCardGrowEffectIds)，花费 producePoint；overwriteProduceCardGrowEffectType 用于显示成“成長追加”等。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_card_custom-020-g_effect-cost_penetra…", "p_card_custom-020-g_effect-cost_reduce-2" |
| `customizeCount` | int32 | 100% | 定制段数。 | 1, 2 |
| `overwriteProduceCardGrowEffectType` | ProduceCardGrowEffectType | 100% | 显示用覆盖类型。 | "ProduceCardGrowEffectType_Unknown", "ProduceCardGrowEffectType_CardStatusEnc…" |
| `description` | string | 38% | 说明文（日文）。 | "成長追加", "成長+" |
| `produceCardGrowEffectIds` | repeated string | 100% | 外键/引用 id（见 FK）。 | ["g_effect-cost_penetrate_reduce-1"], ["g_effect-cost_reduce-2"] |
| `producePoint` | int32 | 100% | P点费用（20/40/70/100…）。 | 20, 40 |

外键（按 id 连接验证）：
- `produceCardGrowEffectIds` → **ProduceCardGrowEffect** (157/157 命中)

代表行：
```json
{"id": "p_card_custom-020-g_effect-cost_penetrate_reduce-1", "customizeCount": 1, "produceCardGrowEffectIds": ["g_effect-cost_penetrate_reduce-1"], "producePoint": 20}
{"id": "p_card_custom-p_card-01-ido-3_017-1", "customizeCount": 1, "produceCardGrowEffectIds": ["g_effect-effect_change-e_effect-exam_lesson_buff-0005-e_effect-exam_status_enchant-inf-en…"], "producePoint": 100}
```

### ProduceCardCustomizeRarityEvaluation（4 行）

定制后评价加成（每稀有度 +12）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `rarity` | ProduceCardRarity | 100% | 稀有度枚举。 | "ProduceCardRarity_N", "ProduceCardRarity_R" |
| `evaluation` | int32 | 100% | 评价分：用于メモリー/编成强度评估（越高越强）。 | 12 |

代表行：
```json
{"rarity": "ProduceCardRarity_N", "evaluation": 12}
{"rarity": "ProduceCardRarity_Sr", "evaluation": 12}
```

### ProduceCardGrowEffect（453 行）

卡牌成长/定制的原子效果（453）：effectType + value（数值型：LessonAdd 等），或结构型：EffectAdd/EffectChange(替换 targetPlayProduceExamEffectIds→playProduceExamEffectId)、PlayTriggerChange/PlayEffectTriggerChange(替换触发)、CardStatusEnchantChange(换成长规则)、PlayMovePositionTypeChange。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "g_effect-aggressive_add-1", "g_effect-aggressive_add-2" |
| `effectType` | ProduceCardGrowEffectType | 100% | ProduceCardGrowEffectType。 | "ProduceCardGrowEffectType_AggressiveAdd", "ProduceCardGrowEffectType_BlockAdd" |
| `costType` | ExamCostType | 100% | 未使用。 | "ExamCostType_Unknown" |
| `value` | int32 | 77% | 数值（LessonDepend* 为千分比）。 | 1, 2 |
| `playProduceExamTriggerId` | string | 1% | PlayTriggerChange 的新使用条件。 | "e_trigger-none-block_up-15", "e_trigger-none-parameter_buff_up-4" |
| `playEffectProduceExamTriggerId` | string | 1% | PlayEffectTriggerChange 的新效果条件。 | "e_trigger-none-lesson_buff_up-10", "e_trigger-none-parameter_buff_up-8" |
| `targetPlayEffectProduceExamTriggerIds` | repeated string | 2% | 被替换的旧触发。 | ["e_trigger-exam_turn_timer-1"], ["e_trigger-exam_card_play-card_play_aggr…"] |
| `playProduceExamEffectId` | string | 17% | EffectAdd/EffectChange 加入的新效果。 | "e_effect-exam_add_grow_effect-p_card_se…", "e_effect-exam_add_grow_effect-p_card_se…" |
| `targetPlayProduceExamEffectIds` | repeated string | 5% | EffectChange 被替换的旧效果。 | ["e_effect-exam_block_per_use_card_count-…"], ["e_effect-exam_block_per_use_card_count-…"] |
| `produceCardStatusEnchantId` | string | 4% | CardStatusEnchantChange 的新成长规则。 | "card_enchant-e_trigger-exam_card_play_a…", "card_enchant-e_trigger-exam_stance_chan…" |
| `playMovePositionType` | ProduceCardMovePositionType | 100% | PlayMovePositionTypeChange 的新去向。 | "ProduceCardMovePositionType_Unknown", "ProduceCardMovePositionType_Grave" |
| `effectGroupIds` | repeated string | 16% | → EffectGroup。把效果归入“xx效果”组，用于筛选（例如“好調効果のスキルカード”这类条件就是按 effectGroup 匹配）。 | ["effect_group-visible-exam_add_grow_effe…"], ["effect_group-visible-exam_block-000"] |

外键（按 id 连接验证）：
- `playProduceExamTriggerId` → **ProduceExamTrigger** (4/4 命中)
- `playEffectProduceExamTriggerId` → **ProduceExamTrigger** (3/3 命中)
- `targetPlayEffectProduceExamTriggerIds` → **ProduceExamTrigger** (9/9 命中)
- `playProduceExamEffectId` → **ProduceExamEffect** (73/73 命中)
- `targetPlayProduceExamEffectIds` → **ProduceExamEffect** (22/22 命中)
- `produceCardStatusEnchantId` → **ProduceCardStatusEnchant** (16/16 命中)
- `effectGroupIds` → **EffectGroup** (21/21 命中)

代表行：
```json
{"id": "g_effect-aggressive_add-1", "effectType": "ProduceCardGrowEffectType_AggressiveAdd", "value": 1}
{"id": "g_effect-lesson_add-24", "effectType": "ProduceCardGrowEffectType_LessonAdd", "value": 24}
```

### ProduceCardStatusEnchant（77 行）

卡牌成长规则（成長）：produceExamTriggerId 满足时对自身应用 produceCardGrowEffectIds，最多 triggerCount 次（0=无限）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "card_enchant-e_trigger-exam_card_play_a…", "card_enchant-e_trigger-exam_card_play_a…" |
| `produceExamTriggerId` | string | 100% | → ProduceExamTrigger（考试内触发/条件）。 | "e_trigger-exam_card_play_after-full_pow…", "e_trigger-exam_card_play_after-p_card_s…" |
| `produceCardGrowEffectIds` | repeated string | 100% | → ProduceCardGrowEffect。 | ["g_effect-lesson_add-3", "g_effect-cost_full_power_point_add-1"], ["g_effect-lesson_add-5", "g_effect-cost_full_power_point_add-1"] |
| `triggerCount` | int32 | 53% | 最多触发次数。 | 4, 0 |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) 成長：自身使用後、全力の場合、自身のパラメータ値増加+3・全力値コスト値増加+1（4回まで）", "(渲染) 成長：自身使用後、全力の場合、自身のパラメータ値増加+5・全力値コスト値増加+1（4回まで）" |
| `effectGroupIds` | repeated string | 0% | → EffectGroup。把效果归入“xx效果”组，用于筛选（例如“好調効果のスキルカード”这类条件就是按 effectGroup 匹配）。 |  |

外键（按 id 连接验证）：
- `produceExamTriggerId` → **ProduceExamTrigger** (15/15 命中)
- `produceCardGrowEffectIds` → **ProduceCardGrowEffect** (28/28 命中)
- `produceDescriptions.targetId` → **ProduceDescriptionLabel** (20/20 命中)
- `produceDescriptions.originProduceCardStatusEnchantId` → **ProduceCardStatusEnchant** (77/77 命中)

代表行：
```json
{"id": "card_enchant-e_trigger-exam_card_play_after-full_power_up-p_card_search-target_is_self-0_…", "produceExamTriggerId": "e_trigger-exam_card_play_after-full_power_up-p_card_search-target_is_self-0_1", "produceCardGrowEffectIds": ["g_effect-lesson_add-3", "g_effect-cost_full_power_point_add-1"], "triggerCount": 4, "produceDescriptions": "(渲染) 成長：自身使用後、全力の場合、自身のパラメータ値増加+3・全力値コスト値増加+1（4回まで）"}
{"id": "card_enchant-e_trigger-exam_stance_change_count_interval-1-4-g_effect-lesson_add-15", "produceExamTriggerId": "e_trigger-exam_stance_change_count_interval-1", "produceCardGrowEffectIds": ["g_effect-lesson_add-15"], "triggerCount": 4, "produceDescriptions": "(渲染) 成長：直接効果で指針を変更するたび、自身のパラメータ値増加+15（4回まで）"}
```

### ProduceCardStatusEffect（0 行）

空表（0 行）。

### ExamInitialDeck（46 行）

初始卡组定义：produce_default-{流派}（8 张基础卡）、produce_006/007-{流派}、contest-{偶像卡}（竞赛用 4 张）、以及流派 2 张组。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "initial_deck-aggressive", "initial_deck-concentration" |
| `produceCardIds` | repeated string | 100% | → ProduceCard 列表（可重复表示多张）。 | ["p_card-02-men-0_012", "p_card-02-act-0_037"], ["p_card-03-men-0_015", "p_card-03-act-0_042"] |
| `produceCardUpgradeCounts` | repeated int32 | 26% | 对应各卡的强化段（空=全 0）。 | [0, 0, 0, 0, 0, "…(+1)"], [0, 0, 0, 0, 0, "…(+2)"] |

外键（按 id 连接验证）：
- `produceCardIds` → **ProduceCard** (62/62 命中)

代表行：
```json
{"id": "initial_deck-aggressive", "produceCardIds": ["p_card-02-men-0_012", "p_card-02-act-0_037"]}
{"id": "initial_deck-contest-i_card-ttmr-1-001", "produceCardIds": ["p_card-02-ido-1_057", "p_card-02-men-0_011", "p_card-02-men-0_011", "p_card-00-act-0_001"]}
```

### ProduceInitialDeck（48 行）

剧本 × 流派 → ExamInitialDeck（初/NIA 用 produce_default，レジェンド用 produce_006，HIF 用 produce_007）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceId` | string | 100% | → Produce（剧本/难度）。 | "produce-001", "produce-002" |
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_ExamParameterBuff", "ProduceExamEffectType_ExamLessonBuff" |
| `examInitialDeckId` | string | 100% | → ExamInitialDeck。 | "initial_deck-produce_default-parameter_…", "initial_deck-produce_default-lesson_buff" |

外键（按 id 连接验证）：
- `produceId` → **Produce** (8/8 命中)
- `examInitialDeckId` → **ExamInitialDeck** (18/18 命中)

代表行：
```json
{"produceId": "produce-001", "examEffectType": "ProduceExamEffectType_ExamParameterBuff", "examInitialDeckId": "initial_deck-produce_default-parameter_buff"}
{"produceId": "produce-005", "examEffectType": "ProduceExamEffectType_ExamParameterBuff", "examInitialDeckId": "initial_deck-produce_default-parameter_buff"}
```

### ExamContestEmbedProduceCard（24 行）

コンテスト/H.I.F 選抜メモリー 生成时按流派嵌入的卡池（每流派 18 张）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "exam_aprilfool_embed_produce_card-01", "exam_contest_embed_produce_card-01" |
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_ExamParameterBuff", "ProduceExamEffectType_ExamLessonBuff" |
| `produceCardIds` | repeated string | 100% | → ProduceCard 列表（可重复表示多张）。 | ["p_card-01-men-0_024", "p_card-01-men-0_025", "p_card-01-men-0_029", "p_card-01-act-0_023", "p_card-01-act-1_002", "…(+13)"], ["p_card-01-act-1_022", "p_card-01-act-2_003", "p_card-01-men-0_025", "p_card-01-men-0_029", "p_card-01-act-0_023", "…(+13)"] |

外键（按 id 连接验证）：
- `produceCardIds` → **ProduceCard** (53/53 命中)

代表行：
```json
{"id": "exam_aprilfool_embed_produce_card-01", "examEffectType": "ProduceExamEffectType_ExamParameterBuff", "produceCardIds": ["p_card-01-men-0_024", "p_card-01-men-0_025", "p_card-01-men-0_029", "p_card-01-act-0_023", "p_card-01-act-1_002", "…(+13)"]}
{"id": "exam_contest_embed_produce_card-produce_008", "examEffectType": "ProduceExamEffectType_ExamParameterBuff", "produceCardIds": ["p_card-01-act-0_022", "p_card-01-act-0_023", "p_card-01-act-0_023", "p_card-01-men-0_024", "p_card-01-men-0_025", "…(+1)"]}
```

### PvpRateCommonProduceCard（3 行）

（备注）コンテスト(PvpRate) 各プラン的公共卡。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "pvp_live_battle_1" |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Plan1", "ProducePlanType_Plan2" |
| `produceCards` | repeated ProduceCard | 100% | 公共卡列表（id/upgradeCount/customizes）。 | [{"id": "p_card-01-men-0_007", "upgradeCount": 0, "customizes": []}, {"id": "p_card-01-men-0_007", "upgradeCount": 0, "customizes": []}, {"id": "p_card-01-men-0_008", "upgradeCount": 0, "customizes": []}, {"id": "p_card-01-men-0_008", "upgradeCount": 0, "customizes": []}, {"id": "p_card-01-act-0_005", "upgradeCount": 0, "customizes": []}, "…(+3)"], [{"id": "p_card-02-men-0_011", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-0_011", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-0_012", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-0_012", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-0_009", "upgradeCount": 0, "customizes": []}, "…(+3)"] |
| &nbsp;&nbsp;↳ `id` | string | 100% | → ProduceCard。 | "p_card-01-men-0_007", "p_card-01-men-0_008" |
| &nbsp;&nbsp;↳ `upgradeCount` | int32 | 0% | 强化段。 | 0 |
| &nbsp;&nbsp;↳ `customizes` | repeated ProduceCardCustomize | 0% | 定制（空）。 |  |

代表行：
```json
{"id": "pvp_live_battle_1", "planType": "ProducePlanType_Plan1", "produceCards": [{"id": "p_card-01-men-0_007", "upgradeCount": 0, "customizes": []}, {"id": "p_card-01-men-0_007", "upgradeCount": 0, "customizes": []}, {"id": "p_card-01-men-0_008", "upgradeCount": 0, "customizes": []}, {"id": "p_card-01-men-0_008", "upgradeCount": 0, "customizes": []}, {"id": "p_card-01-act-0_005", "upgradeCount": 0, "customizes": []}, "…(+3)"]}
{"id": "pvp_live_battle_1", "planType": "ProducePlanType_Plan2", "produceCards": [{"id": "p_card-02-men-0_011", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-0_011", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-0_012", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-0_012", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-0_009", "upgradeCount": 0, "customizes": []}, "…(+3)"]}
```

## 6. D. 考试（レッスン/試験）效果引擎

### ProduceExamEffect（2070 行）

**考试内原子效果**（2070 行，107 种 effectType）。数值槽：effectValue1/2、effectCount、effectTurn(-1=无限)；对象槽：produceCardSearchId + pickRangeType/pickCountMin/Max + movePositionType；链式：chainProduceExamEffectId(s)（ExamEffectTimer 延迟发动的目标）；结构引用：produceExamStatusEnchantId（ExamStatusEnchant 挂载的持续效果）、produceCardGrowEffectIds（ExamAddGrowEffect 附加的成长）。每种 effectType 使用哪些槽见 master_data_enums.md §ProduceExamEffectType。id 编码 `e_effect-{snake_type}-{value...}`。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "e_effect-exam_add_grow_effect-p_card_se…", "e_effect-exam_add_grow_effect-p_card_se…" |
| `effectType` | ProduceExamEffectType | 100% | ProduceExamEffectType。 | "ProduceExamEffectType_ExamAddGrowEffect", "ProduceExamEffectType_ExamAggressiveAdd…" |
| `effectValue1` | int32 | 60% | 主数值（整数或千分比，视类型）。 | 0, 1 |
| `effectValue2` | int32 | 15% | 副数值（倍率千分比等）。 | 0, 400 |
| `effectCount` | int32 | 44% | 次数（参数上升次数 / 生效次数）。 | 0, 1 |
| `effectTurn` | int32 | 39% | 持续回合，-1=永久（レッスン終了まで）。 | 0, 2 |
| `targetProduceCardId` | string | 1% | → ProduceCard（ExamCardCreateId 生成的卡）。 | "p_card-00-acc-0_002", "p_card-01-act-2_003" |
| `targetUpgradeCount` | int32 | 0% | 生成卡的强化段。 | 0, 1 |
| `targetExamEffectType` | ProduceExamEffectType | 100% | 未使用。 | "ProduceExamEffectType_Unknown" |
| `produceCardSearchId` | string | 14% | → ProduceCardSearch，卡牌筛选器（决定作用对象/统计对象）。 | "p_card_search-active_skill-deck_all", "p_card_search-active_skill-deck_all-eff…" |
| `movePositionType` | ProduceCardMovePositionType | 100% | ProduceCardMovePositionType（移动/生成的目的地）。 | "ProduceCardMovePositionType_Unknown", "ProduceCardMovePositionType_DeckFirst" |
| `pickRangeType` | ProducePickRangeType | 100% | ProducePickRangeType：All=全部命中对象 / Random=随机抽取 / Select=玩家选择 / Unknown=不适用。 | "ProducePickRangeType_All", "ProducePickRangeType_Unknown" |
| `pickCountReferenceProduceCardSearchId` | string | 0% | Shortage 模式下参考的筛选器（“使山札达到 N 张”）。 | "p_card_search-deck" |
| `pickCountType` | ProducePickCountType | 100% | ProducePickCountType：Shortage=补足到 N。 | "ProducePickCountType_Unknown", "ProducePickCountType_Shortage" |
| `pickCountMin` | int32 | 3% | 选取数量下限。 | 0, 1 |
| `pickCountMax` | int32 | 3% | 选取数量上限。 | 0, 1 |
| `produceCardSearchId2` | string | 0% | 未使用。 |  |
| `pickRangeType2` | ProducePickRangeType | 100% | 未使用。 | "ProducePickRangeType_Unknown" |
| `pickCountReferenceProduceCardSearchId2` | string | 0% | 未使用。 |  |
| `pickCountType2` | ProducePickCountType | 100% | 未使用。 | "ProducePickCountType_Unknown" |
| `pickCountMin2` | int32 | 0% | 未使用。 | 0 |
| `pickCountMax2` | int32 | 0% | 未使用。 | 0 |
| `chainProduceExamEffectId` | string | 6% | → ProduceExamEffect，延迟/链式目标。 | "e_effect-exam_add_grow_effect-p_card_se…", "e_effect-exam_add_grow_effect-p_card_se…" |
| `chainProduceExamEffectIds` | repeated string | 0% | 多个链式目标。 | ["e_effect-exam_card_draw-0001", "e_effect-exam_block-0002"], ["e_effect-exam_card_draw-0001", "e_effect-exam_playable_value_add-01"] |
| `produceExamStatusEnchantId` | string | 22% | → ProduceExamStatusEnchant（持续效果 = 触发器 + 效果列表）。 | "enchant-p_card-01-ido-3_202-enc02", "enchant-p_card-02-ido-3_198-enc01" |
| `produceCardStatusEnchantId` | string | 0% | 未使用。 |  |
| `produceCardGrowEffectIds` | repeated string | 8% | → ProduceCardGrowEffect（ExamAddGrowEffect/ExamLessonValueMultipleDown 用）。 | ["g_effect-lesson_add-10"], ["g_effect-lesson_add-13", "g_effect-cost_add-1"] |
| `effectGroupIds` | repeated string | 92% | → EffectGroup。把效果归入“xx效果”组，用于筛选（例如“好調効果のスキルカード”这类条件就是按 effectGroup 匹配）。 | ["effect_group-visible-exam_add_grow_effe…"], ["effect_group-visible-exam_card_play_agg…"] |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) アクティブスキルカードのパラメータ値増加+10", "(渲染) アクティブスキルカードのパラメータ値増加+13・コスト値増加+1" |
| `customizeProduceDescriptions` | repeated ProduceDescriptionSegment | 100% | 卡牌定制（カスタマイズ）界面用的描述片段：与 produceDescriptions 相同，只是在开头多一个 `Label_StyleDot`（项目符号）。 | "(渲染) アクティブスキルカードのパラメータ値増加+10", "(渲染) アクティブスキルカードのパラメータ値増加+13・コスト値増加+1" |

外键（按 id 连接验证）：
- `targetProduceCardId` → **ProduceCard** (11/11 命中)
- `produceCardSearchId` → **ProduceCardSearch** (75/75 命中)
- `pickCountReferenceProduceCardSearchId` → **ProduceCardSearch** (1/1 命中)
- `chainProduceExamEffectId` → **ProduceExamEffect** (121/121 命中)
- `chainProduceExamEffectIds` → **ProduceExamEffect** (6/6 命中)
- `produceExamStatusEnchantId` → **ProduceExamStatusEnchant** (439/439 命中)
- `produceCardGrowEffectIds` → **ProduceCardGrowEffect** (71/71 命中)
- `effectGroupIds` → **EffectGroup** (42/42 命中)
- `produceDescriptions.targetId` → ProduceCard? (121/210 = 58%，多态或部分引用)
- `produceDescriptions.originProduceExamEffectId` → **ProduceExamEffect** (2070/2070 命中)
- `customizeProduceDescriptions.targetId` → ProduceCard? (121/212 = 57%，多态或部分引用)
- `customizeProduceDescriptions.originProduceExamEffectId` → **ProduceExamEffect** (2070/2070 命中)

代表行：
```json
{"id": "e_effect-exam_add_grow_effect-p_card_search-active_skill-deck_all-all-0_0-g_effect-lesson…", "effectType": "ProduceExamEffectType_ExamAddGrowEffect", "produceCardSearchId": "p_card_search-active_skill-deck_all", "pickRangeType": "ProducePickRangeType_All", "produceCardGrowEffectIds": ["g_effect-lesson_add-10"], "effectGroupIds": ["effect_group-visible-exam_add_grow_effect-000"], "produceDescriptions": "(渲染) アクティブスキルカードのパラメータ値増加+10", "customizeProduceDescriptions": "(渲染) アクティブスキルカードのパラメータ値増加+10"}
{"id": "e_effect-exam_lesson_depend_stamina-12000-01", "effectType": "ProduceExamEffectType_ExamLessonDependStamina", "effectValue1": 12000, "effectCount": 1, "effectGroupIds": ["effect_group-visible-exam_lesson-000"], "produceDescriptions": "(渲染) 体力の1200%分パラメータ上昇", "customizeProduceDescriptions": "(渲染) 体力の1200%分パラメータ上昇"}
```

### ProduceExamTrigger（676 行）

**考试内触发/条件**（676）：phaseTypes=时机（ProduceExamPhaseType），phaseValues=时机参数（每 N 次/第 N 回合），fieldStatusTypes/Values(+CheckTypes Not)=场上状态条件，produceCardSearchId + lower/upperSearchCount=对象卡条件（如“使用的是アクティブ卡”），effectTypes=ExamStatusChange/AggressiveUpInterval 关注的效果种类，lessonType=仅某属性课程/回合。三组描述：produceDescriptions=作为持续效果条件时的文案；playProduceDescriptions=作为使用条件时（…の場合、使用可）；playEffectProduceDescriptions=作为效果附加条件时。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "e_trigger-exam_aggressive_up_interval-5…", "e_trigger-exam_buff_consume" |
| `phaseTypes` | repeated ProduceExamPhaseType | 100% | ProduceExamPhaseType 列表（None=纯条件，无时机）。 | ["ProduceExamPhaseType_ExamAggressiveUpIn…"], ["ProduceExamPhaseType_ExamBuffConsume"] |
| `phaseValues` | repeated int32 | 13% | 时机参数。 | [5], [0] |
| `fieldStatusCheckTypes` | repeated ProduceExamTriggerCheckType | 5% | Not=取反（“以下”“非…状態”）。 | ["ProduceExamTriggerCheckType_Not"] |
| `fieldStatusTypes` | repeated ProduceExamFieldStatusType | 62% | ProduceExamFieldStatusType 列表。 | ["ProduceExamFieldStatusType_LessonBuffUp"], ["ProduceExamFieldStatusType_ParameterBuf…"] |
| `fieldStatusValues` | repeated int32 | 51% | 阈值（≥；Not 时为 <）。 | [13], [3] |
| `fieldStatusProduceCardSearchIds` | repeated string | 3% | CardSearchCountUp 计数用的筛选器。 | ["p_card_search-hand-p_card-01-ido-3_213"], ["p_card_search-hold"] |
| `produceCardSearchId` | string | 42% | → ProduceCardSearch，卡牌筛选器（决定作用对象/统计对象）。 | "p_card_search-target_is_self", "p_card_search-target" |
| `upperSearchCount` | int32 | 0% | 未使用(0)。 | 0 |
| `lowerSearchCount` | int32 | 38% | 命中卡数下限（1=“使用的卡满足筛选”）。 | 0, 1 |
| `cardMovePositionType` | ProduceCardMovePositionType | 100% | 未使用。 | "ProduceCardMovePositionType_Unknown" |
| `effectTypes` | repeated ProduceExamEffectType | 4% | 关注的效果类型。 | ["ProduceExamEffectType_ExamCardPlayAggre…"], ["ProduceExamEffectType_ExamBlock"] |
| `lessonType` | ProduceStepLessonType | 100% | ProduceStepLessonType 限定。 | "ProduceStepLessonType_Unknown", "ProduceStepLessonType_LessonDance" |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) 直接効果でやる気が5回増加時、", "(渲染) スキルカードコストで強化状態を消費した時、" |
| `playProduceDescriptions` | repeated ProduceDescriptionSegment | 100% | 使用条件文案。 | "(渲染) の場合、使用可", "(渲染) の場合、使用可" |
| `playEffectProduceDescriptions` | repeated ProduceDescriptionSegment | 100% | 效果条件文案。 | "(渲染) の場合、", "(渲染) の場合、" |

外键（按 id 连接验证）：
- `fieldStatusProduceCardSearchIds` → **ProduceCardSearch** (9/9 命中)
- `produceCardSearchId` → **ProduceCardSearch** (173/173 命中)
- `produceDescriptions.targetId` → ProduceCard? (115/146 = 79%，多态或部分引用)
- `produceDescriptions.originProduceExamTriggerId` → **ProduceExamTrigger** (674/674 命中)
- `playProduceDescriptions.targetId` → **ProduceDescriptionLabel** (21/23 命中)
- `playProduceDescriptions.originProduceExamTriggerId` → **ProduceExamTrigger** (676/676 命中)
- `playEffectProduceDescriptions.targetId` → **ProduceDescriptionLabel** (21/23 命中)
- `playEffectProduceDescriptions.originProduceExamTriggerId` → **ProduceExamTrigger** (676/676 命中)

代表行：
```json
{"id": "e_trigger-exam_aggressive_up_interval-5-exam_card_play_aggressive", "phaseTypes": ["ProduceExamPhaseType_ExamAggressiveUpInterval"], "phaseValues": [5], "effectTypes": ["ProduceExamEffectType_ExamCardPlayAggressive"], "produceDescriptions": "(渲染) 直接効果でやる気が5回増加時、", "playProduceDescriptions": "(渲染) の場合、使用可", "playEffectProduceDescriptions": "(渲染) の場合、"}
{"id": "e_trigger-exam_end_turn-review_up-10", "phaseTypes": ["ProduceExamPhaseType_ExamEndTurn"], "fieldStatusTypes": ["ProduceExamFieldStatusType_ReviewUp"], "fieldStatusValues": [10], "produceDescriptions": "(渲染) ターン終了時、好印象が10以上の場合、", "playProduceDescriptions": "(渲染) 好印象が10以上の場合、使用可", "playEffectProduceDescriptions": "(渲染) 好印象が10以上の場合、"}
```

### ProduceExamStatusEnchant（2003 行）

**持续效果**（2003）：= 一个触发器 + 效果列表，由 ProduceExamEffect(ExamStatusEnchant)/ProduceItemEffect/ProduceEffect 挂到场上，回合/次数限制由挂载方给出（effectTurn/effectCount）。id 前缀表明来源：p_item_effect_*(P道具)、p_card-*(卡)、p_ef-hif_memory-*(HIF メモリー技能)、customize_pitem-*、tower*、p_exam_gimmick-*、bullet_point-*(多条效果的列表式描述)。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "enchant-bullet_point-p_card-01-men-100_…", "enchant-bullet_point-p_exam_gimmick-tou…" |
| `assetId` | string | 0% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 |  |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) 次のターン、パラメータ上昇量増加110%（1ターン）・スキルカード使用数追加+1・スキルカードを2枚引く", "(渲染) アイドル固有スキルカード使用時、好調が10ターン以上の場合、好調4ターン・最大体力の5%分体力回復" |
| `produceExamTriggerId` | string | 100% | → ProduceExamTrigger（考试内触发/条件）。 | "e_trigger-start_play-p_card-01-men-100_…", "e_trigger-exam_card_play-parameter_buff…" |
| `produceExamEffectIds` | repeated string | 100% | → ProduceExamEffect，触发时依次结算。 | ["e_effect-exam_lesson_value_multiple-110…", "e_effect-exam_playable_value_add-01", "e_effect-exam_card_draw-0002"], ["e_effect-exam_parameter_buff-04", "e_effect-exam_stamina_recover_multiple-…"] |

外键（按 id 连接验证）：
- `produceDescriptions.targetId` → ProduceCard? (121/211 = 57%，多态或部分引用)
- `produceDescriptions.originProduceExamTriggerId` → **ProduceExamTrigger** (415/415 命中)
- `produceDescriptions.originProduceExamEffectId` → **ProduceExamEffect** (620/620 命中)
- `produceExamTriggerId` → **ProduceExamTrigger** (417/417 命中)
- `produceExamEffectIds` → **ProduceExamEffect** (620/620 命中)

代表行：
```json
{"id": "enchant-bullet_point-p_card-01-men-100_005-enc01", "produceDescriptions": "(渲染) 次のターン、パラメータ上昇量増加110%（1ターン）・スキルカード使用数追加+1・スキルカードを2枚引く", "produceExamTriggerId": "e_trigger-start_play-p_card-01-men-100_005", "produceExamEffectIds": ["e_effect-exam_lesson_value_multiple-1100-01", "e_effect-exam_playable_value_add-01", "e_effect-exam_card_draw-0002"]}
{"id": "enchant-p_item_effect_tower_001-exam_card_play_aggressive-2-stage_020-enc01", "produceDescriptions": "(渲染) アクティブスキルカード使用時、直前にメンタルスキルカードを使用した状態の場合、 / ターン追加+1", "produceExamTriggerId": "e_trigger-exam_card_play-play_card_skill-p_card_search-active_skill-playing-0_1", "produceExamEffectIds": ["e_effect-exam_extra_turn"]}
```

### EffectGroup（67 行）

效果分组字典（67）：把 ProduceExamEffectType / ProduceEffectType 的多个具体类型归为“xx效果”，用于卡牌/道具筛选和图鉴过滤（hiddenFilter=不在筛选 UI 里显示）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "effect_group-hidden-stamina_reduce_fix-…", "effect_group-visible-audition_npc_enhan…" |
| `name` | string | 97% | 显示名（日文）。 | "体力減少", "ライバルのスコア" |
| `examEffectType` | ProduceExamEffectType | 100% | 主考试效果类型。 | "ProduceExamEffectType_Unknown", "ProduceExamEffectType_ExamAddGrowEffect" |
| `produceEffectType` | ProduceEffectType | 100% | 主培育效果类型。 | "ProduceEffectType_StaminaReduceFix", "ProduceEffectType_AuditionNpcEnhance" |
| `examEffectTypes` | repeated ProduceExamEffectType | 63% | 归入本组的全部考试效果类型。 | ["ProduceExamEffectType_ExamStaminaDamage", "ProduceExamEffectType_ExamStaminaReduce", "ProduceExamEffectType_ExamStaminaReduce…"], ["ProduceExamEffectType_ExamAddGrowEffect", "ProduceExamEffectType_ExamGrowEffectLes…", "ProduceExamEffectType_ExamMoveGrowEffect"] |
| `produceEffectTypes` | repeated ProduceEffectType | 42% | 归入本组的培育效果类型。 | ["ProduceEffectType_StaminaReduceFix", "ProduceEffectType_StaminaReduceMultiple"], ["ProduceEffectType_AuditionNpcEnhance"] |
| `hiddenFilter` | bool | 30% | 筛选 UI 隐藏。 | true, false |
| `produceCardGrowEffectTypes` | repeated ProduceCardGrowEffectType | 0% | 未使用。 |  |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 210008, 210009 |

代表行：
```json
{"id": "effect_group-hidden-stamina_reduce_fix-000", "name": "体力減少", "produceEffectType": "ProduceEffectType_StaminaReduceFix", "examEffectTypes": ["ProduceExamEffectType_ExamStaminaDamage", "ProduceExamEffectType_ExamStaminaReduce", "ProduceExamEffectType_ExamStaminaReduceFix"], "produceEffectTypes": ["ProduceEffectType_StaminaReduceFix", "ProduceEffectType_StaminaReduceMultiple"], "hiddenFilter": true, "order": 210008}
{"id": "effect_group-visible-exam_parameter_buff_multiple_per_turn-000", "name": "絶好調", "examEffectType": "ProduceExamEffectType_ExamParameterBuffMultiplePerTurn", "examEffectTypes": ["ProduceExamEffectType_ExamParameterBuffMultiplePerTurn"], "order": 110002}
```

### ExamSimulation（0 行）

空表（0 行）。

## 7. E. 培育外循环效果：技能 / 道具 / 饮料

### ProduceEffect（2114 行）

**培育外循环原子效果**（2114，66 种 produceEffectType）：三维加成、成长率、体力/P点、商店折扣、卡牌操作(強化/削除/チェンジ/コピー)、报酬(ProduceReward/RewardSet)、挂考试持续效果(ExamStatusEnchant/ExamPermanent*)。数值 effectValueMin..Max（几乎全部 Min=Max；千分比或整数视类型）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_effect-audition_npc_enhance-0020_0020", "p_effect-audition_npc_enhance-0030_0030" |
| `produceEffectType` | ProduceEffectType | 100% | ProduceEffectType。 | "ProduceEffectType_AuditionNpcEnhance", "ProduceEffectType_AuditionNpcWeaken" |
| `effectValueMin` | int32 | 78% | 数值下限。 | 20, 30 |
| `effectValueMax` | int32 | 78% | 数值上限。 | 20, 30 |
| `produceResourceType` | ProduceResourceType | 100% | ProduceResourceType（RewardSet/ProduceCardChange 的资源种类）。 | "ProduceResourceType_Unknown", "ProduceResourceType_ProduceCard" |
| `produceRewards` | repeated ProduceReward | 10% | ProduceReward 的具体奖励列表。 | [{"resourceType": "ProduceResourceType_ProduceCard", "resourceId": "p_card-00-acc-0_002", "resourceLevel": 0}], [{"resourceType": "ProduceResourceType_ProduceCard", "resourceId": "p_card-00-sup-2_025", "resourceLevel": 0}] |
| `produceCardSearchId` | string | 6% | → ProduceCardSearch，卡牌筛选器（决定作用对象/统计对象）。 | "p_card_search-active_skill-mental_skill…", "p_card_search-deck_all" |
| `produceExamStatusEnchantId` | string | 12% | → ProduceExamStatusEnchant（持续效果 = 触发器 + 效果列表）。 | "enchant-customize_pitem-01-04-3-001_00-…", "enchant-customize_pitem-01-04-3-001_00-…" |
| `produceStepEventDetailId` | string | 0% | 未使用。 |  |
| `pickRangeType` | ProducePickRangeType | 100% | ProducePickRangeType：All=全部命中对象 / Random=随机抽取 / Select=玩家选择 / Unknown=不适用。 | "ProducePickRangeType_Unknown", "ProducePickRangeType_Select" |
| `pickCountMin` | int32 | 14% | 选取数量下限。 | 0, 1 |
| `pickCountMax` | int32 | 14% | 选取数量上限。 | 0, 1 |
| `isResearch` | bool | 0% | リサーチ活动用。 | false, true |
| &nbsp;&nbsp;↳ `resourceType` | ProduceResourceType | 100% | ProduceResourceType。 | "ProduceResourceType_ProduceCard", "ProduceResourceType_ProduceDrink" |
| &nbsp;&nbsp;↳ `resourceId` | string | 100% | → ProduceCard/ProduceDrink/ProduceItem。 | "p_card-00-acc-0_002", "p_card-00-sup-2_025" |
| &nbsp;&nbsp;↳ `resourceLevel` | int32 | 0% | 强化段。 | 0, 1 |

外键（按 id 连接验证）：
- `produceCardSearchId` → **ProduceCardSearch** (27/27 命中)
- `produceExamStatusEnchantId` → **ProduceExamStatusEnchant** (259/259 命中)
- `produceRewards.resourceId` → ProduceItem? (136/207 = 66%，多态或部分引用)
- ProduceRewardSet 的奖励集合 id 只出现在 ProduceEffect.id 里（`p_rd-...`），对应的“集合→候选卡”表**不在 dump 中**。

代表行：
```json
{"id": "p_effect-audition_npc_enhance-0020_0020", "produceEffectType": "ProduceEffectType_AuditionNpcEnhance", "effectValueMin": 20, "effectValueMax": 20}
{"id": "p_effect-produce_reward_set-p_rd-produce-event_activity-drink-ssr-random-02_02", "produceEffectType": "ProduceEffectType_ProduceRewardSet", "produceResourceType": "ProduceResourceType_ProduceDrink", "pickRangeType": "ProducePickRangeType_Random", "pickCountMin": 2, "pickCountMax": 2}
```

### ProduceTrigger（176 行）

培育外循环触发时机（176）。**注意：dump 中该表只有 id 与 phaseType 两个字段**，附加条件（如 `vocal-0400_0000`=Vocal≥400、`stamina_ratio-0500_0000`=体力≥50%、`produce_card_count-0020_0000`=持卡≥20、`for_nia_master` 等）只能从 id 字符串解析，或从 ProduceSkill/ProduceItem 的 produceDescriptions 文本反推。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_trigger-buy_shop_item_produce_card", "p_trigger-buy_shop_item_produce_drink" |
| `phaseType` | ProducePhaseType | 100% | ProducePhaseType（ProduceStart/StartLesson/EndLesson/StartAudition/EndAudition/StartShop/GetProduceCard/…）。 | "ProducePhaseType_BuyShopItemProduceCard", "ProducePhaseType_BuyShopItemProduceDrink" |

代表行：
```json
{"id": "p_trigger-buy_shop_item_produce_card", "phaseType": "ProducePhaseType_BuyShopItemProduceCard"}
{"id": "p_trigger-get_produce_card-0000_0000-p_card_search-deck_all-effect_group-visible-exam_ful…", "phaseType": "ProducePhaseType_GetProduceCard"}
```

### ProduceSkill（1488 行）

培育技能（1488 = 684 个 skill × level）：id 前缀 p_support_skill(支援卡技能 1066) / p_memory_skill(メモリーアビリティ 340) / p_dearness_skill(亲爱度技能 45) / p_idol_skill(偶像卡潜能/上限技能 27) / p_primastella_skill(HIF 一番星 10)。一条技能 = produceTriggerId1 + produceEffectId1 (+ activationRatePermil1 概率) ，activationCount=培育中最多发动次数；2/3 槽位未使用。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_dearness_skill-common-p_trigger-produ…", "p_dearness_skill-common-p_trigger-produ…" |
| `level` | int32 | 100% | 技能等级（同 id 多行）。 | 1, 2 |
| `rarity` | SkillRarity | 100% | SkillRarity。 | "SkillRarity_Ssr", "SkillRarity_R" |
| `tag` | string | 100% | 全 'tag'。 | "tag" |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Common", "ProducePlanType_Plan1" |
| `produceType` | ProduceType | 100% | ProduceType：FirstStar=定期公演『初』 / NextIdolAudition=N.I.A / HatsuboshiIdolFestival=H.I.F。 | "ProduceType_Unknown", "ProduceType_HatsuboshiIdolFestival" |
| `produceSplitType` | ProduceSplitType | 100% | ProduceSplitType：H.I.F 把一次培育拆成 Selection(選抜試験, produce-007) 与 Final(本戦, produce-008) 两半；Unknown=不区分。 | "ProduceSplitType_Unknown", "ProduceSplitType_Final" |
| `activationCount` | int32 | 51% | 培育中最多发动次数（0=不限）。 | 1, 0 |
| `produceEffectId1` | string | 100% | → ProduceEffect。 | "p_effect-produce_point_addition_disable…", "p_effect-produce_point_addition_disable…" |
| `produceTriggerId1` | string | 100% | → ProduceTrigger。 | "p_trigger-produce_start-initial", "p_trigger-produce_start-no_description" |
| `activationRatePermil1` | int32 | 14% | 发动概率千分比（0=100%）。 | 0, 300 |
| `produceEffectId2` | string | 0% | 未使用。 |  |
| `produceTriggerId2` | string | 0% | 未使用。 |  |
| `activationRatePermil2` | int32 | 0% | 未使用。 | 0 |
| `produceEffectId3` | string | 0% | 未使用。 |  |
| `produceTriggerId3` | string | 0% | 未使用。 |  |
| `activationRatePermil3` | int32 | 0% | 未使用。 | 0 |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) 初期Pポイント+10", "(渲染) 初期Pポイント+20" |

外键（按 id 连接验证）：
- `produceDescriptions.targetId` → ProduceCard? (124/149 = 83%，多态或部分引用)
- `produceDescriptions.originProduceExamEffectId` → **ProduceExamEffect** (121/121 命中)

代表行：
```json
{"id": "p_dearness_skill-common-p_trigger-produce_start-initial-produce_point_addition_disable_tr…", "level": 1, "rarity": "SkillRarity_Ssr", "tag": "tag", "planType": "ProducePlanType_Common", "activationCount": 1, "produceEffectId1": "p_effect-produce_point_addition_disable_trigger-0010_0010", "produceTriggerId1": "p_trigger-produce_start-initial", "produceDescriptions": "(渲染) 初期Pポイント+10"}
{"id": "p_support_skill-common-p_trigger-get_produce_card-0000_0000-p_card_search-active_skill-de…", "level": 3, "rarity": "SkillRarity_Ssr", "tag": "tag", "planType": "ProducePlanType_Common", "produceEffectId1": "p_effect-vocal_addition-0003_0003", "produceTriggerId1": "p_trigger-get_produce_card-0000_0000-p_card_search-active_skill-deck_all", "produceDescriptions": "(渲染) アクティブスキルカード獲得時、ボーカル上昇+3"}
```

### ProduceItem（1038 行）

P道具（1038）。id 编码 `pitem_{00共通|01|02|03}-{稀有度}-{序号}-{0|1强化}[-000 竞赛变体]`、`pitem_..-challenge[-流派]`、`pitem_tower_*`。两类：isExamEffect=true 的考试内道具（skills → ProduceItemEffect(ExamStatusEnchant)）与培育外道具（produceTriggerId + skills → ProduceItemEffect(ProduceEffect)），fireLimit/fireInterval 控制次数/间隔。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "pitem_00-0-004-0-000", "pitem_00-0-004-0-001" |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "img_general_pitem_0-004", "img_general_pitem_0-008" |
| `rarity` | ProduceItemRarity | 100% | 稀有度枚举。 | "ProduceItemRarity_N", "ProduceItemRarity_R" |
| `name` | string | 100% | 显示名（日文）。 | "初星バッチ（赤）", "初星バッチ（紫）" |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Common", "ProducePlanType_Plan1" |
| `fireLimit` | int32 | 27% | 培育中发动次数上限（0=不限）。 | 0, 1 |
| `fireInterval` | int32 | 1% | 发动间隔。 | 0, 2 |
| `produceTriggerId` | string | 33% | → ProduceTrigger（培育外循环触发时机）。 | "p_trigger-start_shop", "p_trigger-end_audition" |
| `produceTriggerIds` | repeated string | 0% | 未使用。 |  |
| `produceItemEffectIds` | repeated string | 100% | → ProduceItemEffect。 | ["p_item_effect-exam_status_enchant-inf-0…"], ["p_item_effect-exam_status_enchant-inf-0…"] |
| `skills` | repeated Skill | 100% | 效果列表（每项 produceItemEffectId，produceTriggerId 均空）。 | [{"produceTriggerId": "", "produceItemEffectId": "p_item_effect-exam_status_enchant-inf-0…"}], [{"produceTriggerId": "", "produceItemEffectId": "p_item_effect-exam_status_enchant-inf-0…"}] |
| &nbsp;&nbsp;↳ `produceTriggerId` | string | 0% | 未使用。 |  |
| &nbsp;&nbsp;↳ `produceItemEffectId` | string | 100% | → ProduceItemEffect。 | "p_item_effect-exam_status_enchant-inf-0…", "p_item_effect-exam_status_enchant-inf-0…" |
| `libraryHidden` | bool | 55% | 图鉴（ピクチャーブック）中隐藏。 | true, false |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) 8ターン目開始時、 / パラメータ+15 / 元気+15 / （レッスン内1回）", "(渲染) ターン開始時、消費体力減少状態の場合、 / パラメータ上昇量増加15%" |
| `evaluation` | int32 | 42% | 评价分：用于メモリー/编成强度评估（越高越强）。 | 0, 50 |
| `isExamEffect` | bool | 67% | 考试内生效的道具。 | true, false |
| `originIdolCardId` | string | 29% | → IdolCard 固有道具来源。 | "i_card-hski-1-000", "i_card-ttmr-1-000" |
| `originSupportCardId` | string | 13% | → SupportCard 来源。 | "s_card-2-0001", "s_card-2-0003" |
| `isUpgraded` | bool | 15% | 强化版（+）。 | false, true |
| `effectGroupIds` | repeated string | 93% | → EffectGroup。把效果归入“xx效果”组，用于筛选（例如“好調効果のスキルカード”这类条件就是按 effectGroup 匹配）。 | ["effect_group-visible-exam_lesson-000", "effect_group-visible-exam_block-000"], ["effect_group-visible-exam_lesson_value_…"] |
| `isChallenge` | bool | 23% | チャレンジPアイテム。 | false, true |
| `isHighScoreRush` | bool | 2% | 高分 Rush 活动道具。 | false, true |
| `isResearch` | bool | 1% | リサーチ活动道具。 | false, true |
| `isEasy` | bool | 0% | 简单模式道具。 | false, true |
| `viewStartTime` | int64 | 100% | 可见起始时间，Unix 毫秒字符串；"0" 表示一直可见。 | "0", "1716339600000" |
| `isLimited` | bool | 0% | 限定标记（全库均为 false）。 | false |
| `order` | int64 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | "1", "1003400130" |

外键（按 id 连接验证）：
- `assetId` → AssetDownload? (125/517 = 24%，多态或部分引用)
- `produceTriggerId` → **ProduceTrigger** (103/103 命中)
- `produceItemEffectIds` → **ProduceItemEffect** (919/919 命中)
- `skills.produceItemEffectId` → **ProduceItemEffect** (919/919 命中)
- `produceDescriptions.targetId` → ProduceDescriptionLabel? (95/127 = 75%，多态或部分引用)
- `produceDescriptions.originProduceExamTriggerId` → **ProduceExamTrigger** (253/253 命中)
- `produceDescriptions.originProduceExamEffectId` → ProduceExamEffect? (412/645 = 64%，多态或部分引用)
- `originIdolCardId` → **IdolCard** (151/151 命中)
- `originSupportCardId` → **SupportCard** (131/131 命中)
- `effectGroupIds` → **EffectGroup** (54/54 命中)

代表行：
```json
{"id": "pitem_00-0-004-0-000", "assetId": "img_general_pitem_0-004", "rarity": "ProduceItemRarity_N", "name": "初星バッチ（赤）", "planType": "ProducePlanType_Common", "produceItemEffectIds": ["p_item_effect-exam_status_enchant-inf-01-enchant-pitem_00-0-004-0-000-enc01"], "skills": [{"produceTriggerId": "", "produceItemEffectId": "p_item_effect-exam_status_enchant-inf-01-enchant-pitem_00-0-004-0-000-enc01"}], "libraryHidden": true, "produceDescriptions": "(渲染) 8ターン目開始時、 / パラメータ+15 / 元気+15 / （レッスン内1回）", "isExamEffect": true, "effectGroupIds": ["effect_group-visible-exam_lesson-000", "effect_group-visible-exam_block-000"], "viewStartTime": "0", "order": "1"}
{"id": "pitem_02-1-032-challenge", "assetId": "img_general_pitem_1-032", "rarity": "ProduceItemRarity_R", "name": "強化グリッパー（赤）", "planType": "ProducePlanType_Plan2", "fireLimit": 2, "produceTriggerId": "p_trigger-start_present", "produceItemEffectIds": ["p_item_effect-produce_effect-p_effect-audition_npc_enhance-0050_0050", "p_item_effect-produce_effect-p_effect-exam_status_enchant-enchant-pitem_02-1-031-challeng…"], "skills": [{"produceTriggerId": "", "produceItemEffectId": "p_item_effect-produce_effect-p_effect-audition_npc_enhance-0050_0050"}, {"produceTriggerId": "", "produceItemEffectId": "p_item_effect-produce_effect-p_effect-exam_status_enchant-enchant-pitem_02-1-031-challeng…"}], "libraryHidden": true, "produceDescriptions": "(渲染) 活動支給・差し入れ選択時、 / ライバルのスコアが5%増加 / 次のレッスン開始時、やる気+2 / 好印象+2 / 消費体力追加1 / （プロデュース中2回）", "effectGroupIds": ["effect_group-visible-exam_stamina_consumption_add_fix-000", "effect_group-visible-exam_review-000", "effect_group-visible-exam_card_play_aggressive-000", "effect_group-visible-audition_npc_enhance-000"], "isChallenge": true, "viewStartTime": "0", "order": "28200100320"}
```

### ProduceItemEffect（931 行）

P道具效果：ExamStatusEnchant（挂 produceExamStatusEnchantId，effectTurn -1=整场，effectCount=每场次数）或 ProduceEffect（produceEffectId）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_item_effect-exam_status_enchant-07-en…", "p_item_effect-exam_status_enchant-07-en…" |
| `effectType` | ProduceItemEffectType | 100% | ProduceItemEffectType。 | "ProduceItemEffectType_ExamStatusEnchant", "ProduceItemEffectType_ProduceEffect" |
| `effectTurn` | int32 | 74% | 持续回合（-1 无限）。 | 7, -1 |
| `effectCount` | int32 | 58% | 每场次数。 | 0, 1 |
| `produceEffectId` | string | 26% | → ProduceEffect（培育外循环效果）。 | "p_effect-audition_npc_enhance-0020_0020", "p_effect-audition_npc_enhance-0030_0030" |
| `produceExamStatusEnchantId` | string | 74% | → ProduceExamStatusEnchant（持续效果 = 触发器 + 效果列表）。 | "enchant-p_item_effect_tower_001-exam_ca…", "enchant-p_item_effect_tower_001-exam_le…" |

外键（按 id 连接验证）：
- `produceEffectId` → **ProduceEffect** (238/238 命中)
- `produceExamStatusEnchantId` → **ProduceExamStatusEnchant** (681/681 命中)

代表行：
```json
{"id": "p_item_effect-exam_status_enchant-07-enchant-pitem_tower_001-exam_card_play_aggressive-1-…", "effectType": "ProduceItemEffectType_ExamStatusEnchant", "effectTurn": 7, "produceExamStatusEnchantId": "enchant-p_item_effect_tower_001-exam_card_play_aggressive-1-stage_010-enc01"}
{"id": "p_item_effect-exam_status_enchant-inf-04-enchant-pitem_02-3-033-1-enc01", "effectType": "ProduceItemEffectType_ExamStatusEnchant", "effectTurn": -1, "effectCount": 4, "produceExamStatusEnchantId": "enchant-p_item_effect_02-3-033-1-enc01"}
```

### ProduceDrink（29 行）

P饮料（29）：效果直接是 ProduceDrinkEffect → ProduceExamEffect（即时效果，无触发）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "pdrink_00-1-001", "pdrink_00-1-004" |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "img_general_pdrink_1-001", "img_general_pdrink_1-004" |
| `name` | string | 100% | 显示名（日文）。 | "初星水", "烏龍茶" |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Common", "ProducePlanType_Plan1" |
| `produceDrinkEffectIds` | repeated string | 100% | → ProduceDrinkEffect。 | ["p_drink_effect-e_effect-exam_lesson-001…"], ["p_drink_effect-e_effect-exam_block-0007"] |
| `rarity` | ProduceDrinkRarity | 100% | 稀有度枚举。 | "ProduceDrinkRarity_R", "ProduceDrinkRarity_Sr" |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) パラメータ+10", "(渲染) 元気+7" |
| `unlockProducerLevel` | int32 | 62% | 解锁 P 等级。 | 0, 8 |
| `effectGroupIds` | repeated string | 93% | → EffectGroup。把效果归入“xx效果”组，用于筛选（例如“好調効果のスキルカード”这类条件就是按 effectGroup 匹配）。 | ["effect_group-visible-exam_lesson-000"], ["effect_group-visible-exam_block-000"] |
| `originSupportCardId` | string | 0% | 未使用。 |  |
| `libraryHidden` | bool | 3% | 图鉴（ピクチャーブック）中隐藏。 | false, true |
| `viewStartTime` | int64 | 100% | 可见起始时间，Unix 毫秒字符串；"0" 表示一直可见。 | "0" |
| `order` | int64 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | "100010000001", "100010000004" |

外键（按 id 连接验证）：
- `assetId` → AssetDownload? (17/29 = 59%，多态或部分引用)
- `produceDrinkEffectIds` → **ProduceDrinkEffect** (43/43 命中)
- `produceDescriptions.targetId` → **ProduceDescriptionLabel** (23/23 命中)
- `produceDescriptions.originProduceExamEffectId` → **ProduceExamEffect** (43/43 命中)
- `effectGroupIds` → **EffectGroup** (24/24 命中)

代表行：
```json
{"id": "pdrink_00-1-001", "assetId": "img_general_pdrink_1-001", "name": "初星水", "planType": "ProducePlanType_Common", "produceDrinkEffectIds": ["p_drink_effect-e_effect-exam_lesson-0010-01"], "rarity": "ProduceDrinkRarity_R", "produceDescriptions": "(渲染) パラメータ+10", "effectGroupIds": ["effect_group-visible-exam_lesson-000"], "viewStartTime": "0", "order": "100010000001"}
{"id": "pdrink_01-3-002", "assetId": "img_general_pdrink_3-002", "name": "厳選初星マキアート", "planType": "ProducePlanType_Plan1", "produceDrinkEffectIds": ["p_drink_effect-e_effect-exam_status_enchant-inf-enchant-pdrink_01-3-002-enc01"], "rarity": "ProduceDrinkRarity_Ssr", "produceDescriptions": "(渲染) 以降、ターン終了時、集中+1", "unlockProducerLevel": 27, "effectGroupIds": ["effect_group-visible-exam_status_enchant-000", "effect_group-visible-exam_lesson_buff-000"], "viewStartTime": "0", "order": "310010000002"}
```

### ProduceDrinkEffect（45 行）

饮料效果行：仅 produceExamEffectId 有值。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_drink_effect-e_effect-exam_block-0003", "p_drink_effect-e_effect-exam_block-0007" |
| `produceEffectId` | string | 0% | 未使用。 |  |
| `produceExamEffectId` | string | 100% | → ProduceExamEffect（考试内原子效果）。 | "e_effect-exam_block-0003", "e_effect-exam_block-0007" |

外键（按 id 连接验证）：
- `produceExamEffectId` → **ProduceExamEffect** (45/45 命中)

代表行：
```json
{"id": "p_drink_effect-e_effect-exam_block-0003", "produceExamEffectId": "e_effect-exam_block-0003"}
{"id": "p_drink_effect-e_effect-exam_lesson_value_multiple-0100-05", "produceExamEffectId": "e_effect-exam_lesson_value_multiple-0100-05"}
```

### ProduceCustomizeItem（180 行）

N.I.A マスター 的“カスタマイズPアイテム”树（180）：isBase 根节点 → ProduceCustomizeItemRelationship 子节点，每个节点 = produceTriggerId + produceEffectIds（含挂持续效果），produceEffectTriggerCount=培育中次数。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "customize_pitem-01-04-3-001", "customize_pitem-01-04-3-001_00-04-2-001…" |
| `name` | string | 100% | 显示名（日文）。 | "ポーチ（赤）", "くま（赤）" |
| `effectType` | ProduceItemEffectType | 100% | 全 ProduceEffect。 | "ProduceItemEffectType_ProduceEffect" |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Plan1", "ProducePlanType_Plan2" |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 100% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) レッスン終了時、 / 体力回復6 / 次の試験開始時、集中+2・好調2ターン / （プロデュース中2回）", "(渲染) レッスン終了時、 / 体力回復6 / ランダムなPドリンクを獲得 / 次の試験開始時、集中+3・好調3ターン / （プロデュース中2回）" |
| `assetId1` | string | 100% | 外观层 1。 | "img_general_cstm-pitem_01-1-001", "img_general_cstm-pitem_02-1-001" |
| `assetId2` | string | 95% | 层 2。 | "img_general_cstm-pitem_04-2-001", "img_general_cstm-pitem_04-2-002" |
| `assetId3` | string | 100% | 层 3。 | "img_general_cstm-pitem_04-3-001", "img_general_cstm-pitem_04-3-002" |
| `assetId4` | string | 75% | 层 4。 | "img_general_cstm-pitem_04-4-001", "img_general_cstm-pitem_04-4-002" |
| `assetId5` | string | 0% | 未使用。 |  |
| `isBase` | bool | 5% | 根节点。 | true, false |
| `isTerminal` | bool | 75% | 叶节点。 | false, true |
| `examEffectTurn` | int32 | 0% | 未使用。 | 0 |
| `examEffectCount` | int32 | 0% | 未使用。 | 0 |
| `produceExamTriggerId` | string | 0% | 未使用。 |  |
| `produceExamEffectIds` | repeated string | 0% | 未使用。 |  |
| `produceEffectTriggerCount` | int32 | 100% | 培育中发动次数。 | 2, 1 |
| `produceEffectTriggerInterval` | int32 | 0% | 未使用。 | 0 |
| `produceTriggerId` | string | 100% | → ProduceTrigger（培育外循环触发时机）。 | "p_trigger-end_lesson-lesson", "p_trigger-start_shop" |
| `produceEffectIds` | repeated string | 100% | → ProduceEffect 列表。 | ["p_effect-stamina_recover_fix-0006_0006", "p_effect-exam_status_enchant-enchant-cu…"], ["p_effect-stamina_recover_fix-0006_0006", "p_effect-produce_reward_set-p_rd-drink_…", "p_effect-exam_status_enchant-enchant-cu…"] |
| `effectGroupIds` | repeated string | 100% | → EffectGroup。把效果归入“xx效果”组，用于筛选（例如“好調効果のスキルカード”这类条件就是按 effectGroup 匹配）。 | ["effect_group-visible-exam_parameter_buf…", "effect_group-visible-exam_lesson_buff-0…", "effect_group-visible-stamina_recover_fi…"], ["effect_group-visible-exam_parameter_buf…", "effect_group-visible-exam_lesson_buff-0…", "effect_group-visible-stamina_recover_fi…", "effect_group-visible-produce_point_addi…"] |

外键（按 id 连接验证）：
- `produceDescriptions.targetId` → **ProduceDescriptionLabel** (12/12 命中)
- `produceDescriptions.originProduceExamTriggerId` → **ProduceExamTrigger** (2/2 命中)
- `produceDescriptions.originProduceExamEffectId` → ProduceEffect? (44/60 = 73%，多态或部分引用)
- `produceTriggerId` → **ProduceTrigger** (4/4 命中)
- `produceEffectIds` → **ProduceEffect** (44/44 命中)
- `effectGroupIds` → **EffectGroup** (14/14 命中)

代表行：
```json
{"id": "customize_pitem-01-04-3-001", "name": "ポーチ（赤）", "effectType": "ProduceItemEffectType_ProduceEffect", "planType": "ProducePlanType_Plan1", "produceDescriptions": "(渲染) レッスン終了時、 / 体力回復6 / 次の試験開始時、集中+2・好調2ターン / （プロデュース中2回）", "assetId1": "img_general_cstm-pitem_01-1-001", "assetId3": "img_general_cstm-pitem_04-3-001", "isBase": true, "produceEffectTriggerCount": 2, "produceTriggerId": "p_trigger-end_lesson-lesson", "produceEffectIds": ["p_effect-stamina_recover_fix-0006_0006", "p_effect-exam_status_enchant-enchant-customize_pitem-01-04-3-001-enc01"], "effectGroupIds": ["effect_group-visible-exam_parameter_buff-000", "effect_group-visible-exam_lesson_buff-000", "effect_group-visible-stamina_recover_fix-000"]}
{"id": "customize_pitem-02-04-3-002_00-04-2-002_02-02-1-001_00-04-4-004", "name": "羽人形（緑）", "effectType": "ProduceItemEffectType_ProduceEffect", "planType": "ProducePlanType_Plan2", "produceDescriptions": "(渲染) おでかけ終了時、 / Pポイント+60 / スキルカードを選択して削除 / 以降の試験開始時、好印象+6・やる気+6 / （プロデュース中1回）", "assetId1": "img_general_cstm-pitem_02-1-001", "assetId2": "img_general_cstm-pitem_04-2-002", "assetId3": "img_general_cstm-pitem_04-3-002", "assetId4": "img_general_cstm-pitem_04-4-004", "isTerminal": true, "produceEffectTriggerCount": 1, "produceTriggerId": "p_trigger-end_step_event_activity", "produceEffectIds": ["p_effect-produce_point_addition-0060_0060", "p_effect-produce_card_delete-p_card_search-deck_all-select-01_01", "p_effect-exam_permanent_audition_status_enchant-enchant-customize_pitem-02-04-3-001_00-04…"], "effectGroupIds": ["effect_group-visible-exam_review-000", "effect_group-visible-exam_card_play_aggressive-000", "effect_group-visible-produce_card_delete-000", "effect_group-visible-produce_point_addition-000"]}
```

### ProduceCustomizeItemRelationship（171 行）

定制道具树的父子边。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `parentProduceCustomizeItemId` | string | 100% | → ProduceCustomizeItem。 | "customize_pitem-01-04-3-001", "customize_pitem-01-04-3-001_00-04-2-001…" |
| `childProduceCustomizeItemId` | string | 100% | → ProduceCustomizeItem。 | "customize_pitem-01-04-3-001_00-04-2-001…", "customize_pitem-01-04-3-001_00-04-2-002…" |

外键（按 id 连接验证）：
- `parentProduceCustomizeItemId` → **ProduceCustomizeItem** (45/45 命中)
- `childProduceCustomizeItemId` → **ProduceCustomizeItem** (171/171 命中)

代表行：
```json
{"parentProduceCustomizeItemId": "customize_pitem-01-04-3-001", "childProduceCustomizeItemId": "customize_pitem-01-04-3-001_00-04-2-001_01-01-1-001"}
{"parentProduceCustomizeItemId": "customize_pitem-02-04-3-002_00-04-2-002_02-02-1-001", "childProduceCustomizeItemId": "customize_pitem-02-04-3-002_00-04-2-002_02-02-1-001_00-04-4-002"}
```

### MemoryAbility（575 行）

メモリー的アビリティ（575）：指向 ProduceSkill(p_memory_skill)，带评价分与可用剧本系列；isUniqueActivation=重複発動不可。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "ability-001-p_memory_skill-common-p_tri…", "ability-001-p_memory_skill-common-p_tri…" |
| `level` | int32 | 100% | 等级。 | 1 |
| `skillId` | string | 100% | → ProduceSkill。 | "p_memory_skill-common-p_trigger-end_les…", "p_memory_skill-common-p_trigger-end_les…" |
| `evaluation` | int32 | 100% | 评价分：用于メモリー/编成强度评估（越高越强）。 | 18, 27 |
| `rarity` | SkillRarity | 100% | 稀有度枚举。 | "SkillRarity_Unknown" |
| `produceGroupIds` | repeated string | 87% | → ProduceGroup 可用系列。 | ["produce_group-001"], ["produce_group-002"] |
| `isUniqueActivation` | bool | 18% | 同名只发动一次。 | false, true |

外键（按 id 连接验证）：
- `skillId` → **ProduceSkill** (340/340 命中)
- `produceGroupIds` → **ProduceGroup** (3/3 命中)

代表行：
```json
{"id": "ability-001-p_memory_skill-common-p_trigger-end_lesson-lesson_dance-stamina_recover_fix-0…", "level": 1, "skillId": "p_memory_skill-common-p_trigger-end_lesson-lesson_dance-stamina_recover_fix-01-001", "evaluation": 18}
{"id": "memory_ability-p_memory_skill-common-hatsuboshi_idol_festival-p_trigger-start_audition-fo…", "level": 1, "skillId": "p_memory_skill-common-hatsuboshi_idol_festival-p_trigger-start_audition-for_hif_memory-ex…", "evaluation": 3, "produceGroupIds": ["produce_group-003"], "isUniqueActivation": true}
```

### MemoryGift（21 行）

（备注）赠送的固定メモリー（新手/活动），含卡、アビリティ、三维。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "memory_gift-20251116-kcna", "memory_gift-20251116-shro" |
| `name` | string | 100% | 显示名（日文）。 | "メモリー「学園生活 倉本千奈 」", "メモリー「学園生活 篠澤広」" |
| `description` | string | 0% | 说明文（日文）。 |  |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "img_general_memory_linkcontest-002", "img_general_memory_linkcontest-001" |
| `grade` | ResultGrade | 100% | ResultGrade（メモリー评价）。 | "ResultGrade_D", "ResultGrade_F" |
| `idolCardId` | string | 100% | → IdolCard。 | "i_card-kcna-1-000", "i_card-shro-1-000" |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Unknown" |
| &nbsp;&nbsp;↳ `id` | string | 100% | → ProduceCard。 | "p_card-02-act-1_028", "p_card-02-men-1_031" |
| &nbsp;&nbsp;↳ `upgradeCount` | int32 | 48% | 强化段。 | 0, 1 |
| &nbsp;&nbsp;↳ `customizes` | repeated ProduceCardCustomize | 10% | 定制列表。 | [{"id": "p_card_custom-wrapper-p_card-03-men-1_0…", "customizeCount": 1}], [{"id": "p_card_custom-100-g_effect-lesson_count…", "customizeCount": 1}] |
| `produceCardPhaseType` | ProduceMemoryProduceCardPhaseType | 100% | ProduceMemoryProduceCardPhaseType：该卡在 ProduceStart 还是 EndAuditionMid 时进入卡组。 | "ProduceMemoryProduceCardPhaseType_EndAu…", "ProduceMemoryProduceCardPhaseType_Produ…" |
| `memoryAbilities` | repeated MemoryAbility | 100% | → MemoryAbility 列表。 | [{"id": "ability-001-p_memory_skill-common-p_tri…", "level": 1}, {"id": "ability-001-p_memory_skill-common-p_tri…", "level": 1}, {"id": "ability-001-p_memory_skill-common-p_tri…", "level": 1}], [{"id": "ability-p_cd-memory-vocal-450-001-p_mem…", "level": 1}, {"id": "ability-p_cd-memory-dance-450-001-p_mem…", "level": 1}, {"id": "ability-p_cd-memory-visual-450-001-p_me…", "level": 1}] |
| &nbsp;&nbsp;↳ `id` | string | 100% | → MemoryAbility。 | "ability-001-p_memory_skill-common-p_tri…", "ability-001-p_memory_skill-common-p_tri…" |
| &nbsp;&nbsp;↳ `level` | int32 | 100% | 等级。 | 1 |
| `vocal` | int32 | 100% | メモリー三维。 | 200, 400 |
| `dance` | int32 | 100% | 。 | 400, 300 |
| `visual` | int32 | 100% | 。 | 300, 200 |
| `stamina` | int32 | 100% | 体力。 | 25 |
| `examBattleProduceCards` | repeated ProduceCard | 100% | コンテスト用卡组。 | [{"id": "p_card-02-ido-1_018", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-1_028", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-1_004", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-2_045", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-2_047", "upgradeCount": 0, "customizes": []}], [{"id": "p_card-02-ido-1_015", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-1_031", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-1_006", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-2_053", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-2_047", "upgradeCount": 0, "customizes": []}] |
| &nbsp;&nbsp;↳ `id` | string | 100% | → ProduceCard。 | "p_card-02-ido-1_018", "p_card-02-act-1_028" |
| &nbsp;&nbsp;↳ `upgradeCount` | int32 | 0% | 强化段。 | 0 |
| &nbsp;&nbsp;↳ `customizes` | repeated ProduceCardCustomize | 0% | 定制。 |  |
| `examBattleProduceItemIds` | repeated string | 100% | → ProduceItem コンテスト用道具。 | ["pitem_00-1-009-0"], ["pitem_00-1-006-0"] |
| &nbsp;&nbsp;↳ `id` | string | 100% | → ProduceCardCustomize。 | "p_card_custom-wrapper-p_card-03-men-1_0…", "p_card_custom-100-g_effect-lesson_count…" |
| &nbsp;&nbsp;↳ `customizeCount` | int32 | 100% | 段数。 | 1 |

外键（按 id 连接验证）：
- `idolCardId` → **IdolCard** (8/8 命中)
- `examBattleProduceItemIds` → **ProduceItem** (8/8 命中)

代表行：
```json
{"id": "memory_gift-20251116-kcna", "name": "メモリー「学園生活 倉本千奈 」", "assetId": "img_general_memory_linkcontest-002", "grade": "ResultGrade_D", "idolCardId": "i_card-kcna-1-000", "produceCard": {"id": "p_card-02-act-1_028", "upgradeCount": 0, "customizes": []}, "produceCardPhaseType": "ProduceMemoryProduceCardPhaseType_EndAuditionMid", "memoryAbilities": [{"id": "ability-001-p_memory_skill-common-p_trigger-produce_start-initial-vocal_addition-01-001", "level": 1}, {"id": "ability-001-p_memory_skill-common-p_trigger-produce_start-initial-dance_addition-01-001", "level": 1}, {"id": "ability-001-p_memory_skill-common-p_trigger-produce_start-initial-visual_addition-01-001", "level": 1}], "vocal": 200, "dance": 400, "visual": 300, "stamina": 25, "examBattleProduceCards": [{"id": "p_card-02-ido-1_018", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-1_028", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-1_004", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-2_045", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-2_047", "upgradeCount": 0, "customizes": []}], "examBattleProduceItemIds": ["pitem_00-1-009-0"]}
{"id": "memory_gift-20260516-hif-plan2-1", "name": "H.I.F応援メモリー（みんな大好き＋）", "assetId": "img_general_memory_hif-gift-003", "grade": "ResultGrade_Sss", "idolCardId": "i_card-fktn-1-000", "produceCard": {"id": "p_card-02-act-2_049", "upgradeCount": 1, "customizes": []}, "produceCardPhaseType": "ProduceMemoryProduceCardPhaseType_ProduceStart", "memoryAbilities": [{"id": "ability-p_cd-memory-vocal-450-001-p_memory_skill-common-p_trigger-produce_start-initial-v…", "level": 1}, {"id": "ability-p_cd-memory-dance-450-001-p_memory_skill-common-p_trigger-produce_start-initial-d…", "level": 1}, {"id": "ability-p_cd-memory-visual-450-001-p_memory_skill-common-p_trigger-produce_start-initial-…", "level": 1}], "vocal": 200, "dance": 400, "visual": 300, "stamina": 25, "examBattleProduceCards": [{"id": "p_card-02-ido-1_012", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-1_030", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-men-2_055", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-1_027", "upgradeCount": 0, "customizes": []}, {"id": "p_card-02-act-2_046", "upgradeCount": 0, "customizes": []}], "examBattleProduceItemIds": ["pitem_00-1-003-0"]}
```

### ProduceEffectIcon（98 行）

（备注）ProduceEffectType → 图标资源。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ProduceEffectType | 100% | ProduceEffectType。 | "ProduceEffectType_VocalAddition", "ProduceEffectType_DanceAddition" |
| `resourceType` | ProduceResourceType | 100% | ResourceType/ProduceResourceType 枚举。 | "ProduceResourceType_Unknown", "ProduceResourceType_ProduceCard" |
| `iconAssetId` | string | 100% | 图标。 | "img_general_icon_produce-effect_pict-vo…", "img_general_icon_produce-effect_pict-da…" |
| `backgroundAssetId` | string | 100% | 背景。 | "img_general_icon_produce-effect_bg-vocal", "img_general_icon_produce-effect_bg-dance" |
| `order` | int64 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | "1010000", "1010010" |

外键（按 id 连接验证）：
- `iconAssetId` → AssetDownload? (3/46 = 7%，多态或部分引用)
- `backgroundAssetId` → AssetDownload? (3/7 = 43%，多态或部分引用)

代表行：
```json
{"type": "ProduceEffectType_VocalAddition", "iconAssetId": "img_general_icon_produce-effect_pict-vocal", "backgroundAssetId": "img_general_icon_produce-effect_bg-vocal", "order": "1010000"}
{"type": "ProduceEffectType_ProduceRewardSet", "resourceType": "ProduceResourceType_ProducePoint", "iconAssetId": "img_general_icon_produce-effect_pict-producerewardpoint", "backgroundAssetId": "img_general_icon_produce-effect_bg-positive", "order": "1330000"}
```

## 8. F. 偶像卡 / 角色 / 支援卡

### IdolCard（151 行）

偶像卡（プロデュースアイドル，151）。培育起点：三维初始值 produceVocal/Dance/Visual、成长率 permil、体力、固有卡 produceCardId、固有道具 before/afterProduceItemId（+ 版）、流派 examEffectType、试炼难度组、初始卡组、潜能/上限/一番星 技能表。id 编码 `i_card-{chr}-{1R|2SR|3SSR}-{序号}`。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "i_card-amao-1-000", "i_card-amao-1-001" |
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `originalIdolCardSkinId` | string | 100% | → IdolCardSkin 默认皮肤。 | "i_card-skin-amao-1-000", "i_card-skin-amao-1-001" |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "cidol-amao-1-000", "cidol-amao-1-001" |
| `name` | string | 100% | 显示名（日文）。 | "学園生活", "初恋" |
| `rarity` | IdolCardRarity | 100% | 稀有度枚举。 | "IdolCardRarity_R", "IdolCardRarity_Sr" |
| `isLimited` | bool | 0% | 限定标记（全库均为 false）。 | false |
| `anotherCostumeHeadId` | string | 50% | → CostumeHead。 | "costume_head_amao-cstm-0016", "costume_head_amao-cstm-0054" |
| `anotherCostumeId` | string | 66% | → Costume。 | "amao-cstm-0016", "amao-cstm-0036" |
| `idolCardPotentialId` | string | 100% | → IdolCardPotential（潜能 4 段）。 | "idol_card_potential-amao-r-01", "idol_card_potential-i_card-amao-1-001" |
| `idolCardPotentialProduceSkillId` | string | 100% | → IdolCardPotentialProduceSkill。 | "idol_card_potential_produce_skill_001", "idol_card_potential_produce_skill-i_car…" |
| `idolCardLevelLimitId` | string | 100% | → IdolCardLevelLimit（突破消耗）。 | "idol_card_level_limit-r-plan1-vo-vi", "idol_card_level_limit-r-plan2-vo-vi" |
| `idolCardLevelLimitProduceSkillId` | string | 100% | → IdolCardLevelLimitProduceSkill（突破解锁技能）。 | "idol_card_level_limit_produce_skill_001", "idol_card_level_limit_produce_skill_005" |
| `maxIdolCardLevelLimitRank` | IdolCardLevelLimitRank | 100% | 最大突破段（6 或 7）。 | "IdolCardLevelLimitRank__6", "IdolCardLevelLimitRank__7" |
| `additionalAnotherCostumeHeadIds` | repeated string | 3% | 额外服装。 | ["costume_head_hmsz-cstm-0174"], ["costume_head_jsna-hair-0017"] |
| `additionalAnotherCostumeIds` | repeated string | 1% | 额外服装。 | ["hmsz-cstm-0174"], ["ttmr-cstm-0174"] |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Plan1", "ProducePlanType_Plan2" |
| `idolCardLevelLimitStatusUpId` | string | 100% | → IdolCardLevelLimitStatusUp（突破加三维）。 | "level_limit_status_up-001", "level_limit_status_up-003" |
| `produceVocal` | int32 | 100% | 初始 Vocal。 | 65, 70 |
| `produceDance` | int32 | 100% | 初始 Dance。 | 55, 60 |
| `produceVisual` | int32 | 100% | 初始 Visual。 | 45, 50 |
| `produceVocalGrowthRatePermil` | int32 | 100% | Vocal 成长率千分比（课程/试炼参数加成）。 | 200, 210 |
| `produceDanceGrowthRatePermil` | int32 | 100% | 。 | 40, 50 |
| `produceVisualGrowthRatePermil` | int32 | 100% | 。 | 180, 100 |
| `produceStamina` | int32 | 100% | 初始最大体力。 | 31, 27 |
| `produceStepAuditionDifficultyId` | string | 100% | → ProduceStepAuditionDifficulty 难度组。 | "p_step_audition_difficulty-amao", "p_step_audition_difficulty-i_card-amao-…" |
| `examInitialDeckId` | string | 100% | → ExamInitialDeck（流派 2 张组：initial_deck-parameter_buff 等，用于表示卡的流派/教程）。 | "initial_deck-parameter_buff", "initial_deck-review" |
| `produceCardId` | string | 100% | → ProduceCard（注意 ProduceCard 主键是 (id, upgradeCount)）。 | "p_card-01-ido-1_013", "p_card-02-ido-1_059" |
| `beforeProduceItemId` | string | 100% | → ProduceItem 固有道具。 | "pitem_00-1-004-0", "pitem_02-1-016-0" |
| `afterProduceItemId` | string | 100% | → ProduceItem 固有道具+。 | "pitem_00-1-004-1", "pitem_02-1-016-1" |
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_ExamParameterBuff", "ProduceExamEffectType_ExamReview" |
| `produceChallengeSlotId` | string | 100% | → ProduceChallengeSlot。 | "challenge_slot-exam_parameter_buff", "challenge_slot-exam_review" |
| `showExamEffectType` | ProduceExamEffectType | 100% | 图鉴额外显示的流派（温存）。 | "ProduceExamEffectType_Unknown", "ProduceExamEffectType_ExamPreservation" |
| `secondProduceCardId` | string | 3% | → ProduceCard 第二固有卡（部分 SSR）。 | "p_card-01-ido-3_213", "p_card-03-ido-3_210" |
| `beforeLevelLimitProduceItemId` | string | 0% | 未使用。 |  |
| `afterLevelLimitProduceItemId` | string | 0% | 未使用。 |  |
| `primaStellaConsumptionSetId` | string | 7% | → ConsumptionSet，プリマステラ 解放消耗。 | "cs-idol_card_prima_stella-i_card-amao-3…", "cs-idol_card_prima_stella-i_card-hmsz-3…" |
| `idolCardPrimaStellaProduceSkillId` | string | 7% | → IdolCardPrimaStellaProduceSkill。 | "prima_stella_produce_skill-i_card-amao-…", "prima_stella_produce_skill-i_card-hmsz-…" |
| `primaStellaAchievementId` | string | 7% | → Achievement。 | "achieve-p_idol-amao-025", "achieve-p_idol-hmsz-025" |
| `potentialRankVoiceAssetId` | string | 100% | 语音。 | "sud_vo_system_cidol-amao-1-000_idol_pot…", "sud_vo_system_cidol-amao-1-001_idol_pot…" |
| `produceSelectVoiceAssetId` | string | 100% | 语音。 | "sud_vo_system_cidol-amao-1-000_produce_…", "sud_vo_system_cidol-amao-1-001_produce_…" |
| `produceScheduleFrontVoiceGroupId` | string | 75% | → VoiceGroup。 | "voice_group-cidol-amao-3-000-produce_sc…", "voice_group-cidol-amao-3-001-produce_sc…" |
| `produceScheduleBackVoiceGroupId` | string | 0% | 未使用。 |  |
| `useProduceCardVoiceAssetId` | string | 100% | 语音。 | "sud_vo_system_cidol-amao-1-000_produce_…", "sud_vo_system_cidol-amao-1-001_produce_…" |
| `useSecondProduceCardVoiceAssetId` | string | 3% | 语音。 | "sud_vo_system_cidol-hrnm-3-017_produce_…", "sud_vo_system_cidol-hski-3-018_produce_…" |
| `usePrimaStellaProduceCardVoiceAssetId` | string | 7% | 语音。 | "sud_vo_system_cidol-amao-3-015_produce_…", "sud_vo_system_cidol-hmsz-3-016_produce_…" |
| `primaStellaVoiceAssetId` | string | 7% | 语音。 | "sud_vo_system_cidol-amao-3-015_idol_det…", "sud_vo_system_cidol-hmsz-3-016_idol_det…" |
| `viewStartTime` | int64 | 100% | 可见起始时间，Unix 毫秒字符串；"0" 表示一直可见。 | "0", "1728871200000" |
| `order` | int64 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | "3999900109999", "3997950109998" |
| `produceStoryIds` | repeated string | 75% | → ProduceStory 偶像卡剧情。 | ["p_story-i_card-amao-3-000-01", "p_story-i_card-amao-3-000-02", "p_story-i_card-amao-3-000-03"], ["p_story-i_card-amao-3-001-01", "p_story-i_card-amao-3-001-02", "p_story-i_card-amao-3-001-03"] |
| `achievementIds` | repeated string | 83% | → Achievement。 | ["achieve-i_card-amao-2-000-04", "achieve-i_card-amao-2-000-05", "achieve-i_card-amao-2-000-06", "achieve-p_idol-card-amao-002-1", "achieve-p_idol-card-amao-002-2", "…(+1)"], ["achieve-i_card-amao-3-000-04", "achieve-i_card-amao-3-000-05", "achieve-i_card-amao-3-000-06", "achieve-p_idol-card-amao-003-1", "achieve-p_idol-card-amao-003-2", "…(+1)"] |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `originalIdolCardSkinId` → **IdolCardSkin** (151/151 命中)
- `anotherCostumeHeadId` → **CostumeHead** (76/76 命中)
- `anotherCostumeId` → **Costume** (100/100 命中)
- `idolCardPotentialId` → **IdolCardPotential** (151/151 命中)
- `idolCardPotentialProduceSkillId` → **IdolCardPotentialProduceSkill** (125/125 命中)
- `idolCardLevelLimitId` → **IdolCardLevelLimit** (23/23 命中)
- `idolCardLevelLimitProduceSkillId` → **IdolCardLevelLimitProduceSkill** (15/15 命中)
- `additionalAnotherCostumeHeadIds` → **CostumeHead** (4/4 命中)
- `additionalAnotherCostumeIds` → **Costume** (2/2 命中)
- `idolCardLevelLimitStatusUpId` → **IdolCardLevelLimitStatusUp** (6/6 命中)
- `produceStepAuditionDifficultyId` → **ProduceStepAuditionDifficulty** (133/133 命中)
- `examInitialDeckId` → **ExamInitialDeck** (6/6 命中)
- `produceCardId` → **ProduceCard** (151/151 命中)
- `beforeProduceItemId` → **ProduceItem** (151/151 命中)
- `afterProduceItemId` → **ProduceItem** (151/151 命中)
- `produceChallengeSlotId` → **ProduceChallengeSlot** (6/6 命中)
- `secondProduceCardId` → **ProduceCard** (5/5 命中)
- `primaStellaConsumptionSetId` → **ConsumptionSet** (10/10 命中)
- `idolCardPrimaStellaProduceSkillId` → **IdolCardPrimaStellaProduceSkill** (10/10 命中)
- `primaStellaAchievementId` → **Achievement** (10/10 命中)
- `produceScheduleFrontVoiceGroupId` → **VoiceGroup** (113/113 命中)
- `produceStoryIds` → **ProduceStory** (339/339 命中)
- `achievementIds` → **Achievement** (756/756 命中)

代表行：
```json
{"id": "i_card-amao-1-000", "characterId": "amao", "originalIdolCardSkinId": "i_card-skin-amao-1-000", "assetId": "cidol-amao-1-000", "name": "学園生活", "rarity": "IdolCardRarity_R", "idolCardPotentialId": "idol_card_potential-amao-r-01", "idolCardPotentialProduceSkillId": "idol_card_potential_produce_skill_001", "idolCardLevelLimitId": "idol_card_level_limit-r-plan1-vo-vi", "idolCardLevelLimitProduceSkillId": "idol_card_level_limit_produce_skill_001", "maxIdolCardLevelLimitRank": "IdolCardLevelLimitRank__6", "planType": "ProducePlanType_Plan1", "idolCardLevelLimitStatusUpId": "level_limit_status_up-001", "produceVocal": 65, "produceDance": 55, "produceVisual": 45, "produceVocalGrowthRatePermil": 200, "produceDanceGrowthRatePermil": 40, "produceVisualGrowthRatePermil": 180, "produceStamina": 31, "produceStepAuditionDifficultyId": "p_step_audition_difficulty-amao", "examInitialDeckId": "initial_deck-parameter_buff", "produceCardId": "p_card-01-ido-1_013", "beforeProduceItemId": "pitem_00-1-004-0", "afterProduceItemId": "pitem_00-1-004-1", "examEffectType": "ProduceExamEffectType_ExamParameterBuff", "produceChallengeSlotId": "challenge_slot-exam_parameter_buff", "potentialRankVoiceAssetId": "sud_vo_system_cidol-amao-1-000_idol_potential-01", "produceSelectVoiceAssetId": "sud_vo_system_cidol-amao-1-000_produce_start-01", "useProduceCardVoiceAssetId": "sud_vo_system_cidol-amao-1-000_produce_skillcard-01", "viewStartTime": "0", "order": "3999900109999"}
{"id": "i_card-hume-3-017", "characterId": "hume", "originalIdolCardSkinId": "i_card-skin-hume-3-017", "assetId": "cidol-hume-3-017", "name": "真っ白いページと水彩の主人公", "rarity": "IdolCardRarity_Ssr", "anotherCostumeHeadId": "costume_head_hume-cstm-0101", "anotherCostumeId": "hume-cstm-0101", "idolCardPotentialId": "idol_card_potential-i_card-hume-3-017", "idolCardPotentialProduceSkillId": "idol_card_potential_produce_skill-i_card-hume-3-017", "idolCardLevelLimitId": "idol_card_level_limit-ssr-plan2-vo-da", "idolCardLevelLimitProduceSkillId": "idol_card_level_limit_produce_skill_001", "maxIdolCardLevelLimitRank": "IdolCardLevelLimitRank__6", "planType": "ProducePlanType_Plan2", "idolCardLevelLimitStatusUpId": "level_limit_status_up-001", "produceVocal": 50, "produceDance": 60, "produceVisual": 60, "produceVocalGrowthRatePermil": 170, "produceDanceGrowthRatePermil": 200, "produceVisualGrowthRatePermil": 120, "produceStamina": 30, "produceStepAuditionDifficultyId": "p_step_audition_difficulty-i_card-hume-3-017", "examInitialDeckId": "initial_deck-aggressive", "produceCardId": "p_card-02-ido-3_176", "beforeProduceItemId": "pitem_02-3-302-0", "afterProduceItemId": "pitem_02-3-302-1", "examEffectType": "ProduceExamEffectType_ExamCardPlayAggressive", "produceChallengeSlotId": "challenge_slot-exam_card_play_aggressive", "primaStellaConsumptionSetId": "cs-idol_card_prima_stella-i_card-hume-3-017", "idolCardPrimaStellaProduceSkillId": "prima_stella_produce_skill-i_card-hume-3-017", "primaStellaAchievementId": "achieve-p_idol-hume-025", "potentialRankVoiceAssetId": "sud_vo_system_cidol-hume-3-017_idol_potential-01", "produceSelectVoiceAssetId": "sud_vo_system_cidol-hume-3-017_produce_start-01", "produceScheduleFrontVoiceGroupId": "voice_group-cidol-hume-3-017-produce_schedule", "useProduceCardVoiceAssetId": "sud_vo_system_cidol-hume-3-017_produce_skillcard-01", "usePrimaStellaProduceCardVoiceAssetId": "sud_vo_system_cidol-hume-3-017_produce_skillcard-02", "primaStellaVoiceAssetId": "sud_vo_system_cidol-hume-3-017_idol_details-03", "viewStartTime": "1775786400000", "order": "1991700809982", "produceStoryIds": ["p_story-i_card-hume-3-017-01", "p_story-i_card-hume-3-017-02", "p_story-i_card-hume-3-017-03"], "achievementIds": ["achieve-i_card-hume-3-017-01", "achieve-i_card-hume-3-017-02", "achieve-i_card-hume-3-017-03", "achieve-i_card-hume-3-017-04", "achieve-i_card-hume-3-017-05", "…(+1)"]}
```

### IdolCardLevelLimit（171 行）

突破(レベル上限解放)消耗：id=按稀有度/プラン/主属性的模板，每段 rank 一行 → ConsumptionSet。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "idol_card_level_limit-r-plan1-vi-da", "idol_card_level_limit-r-plan1-vo-da" |
| `rank` | IdolCardLevelLimitRank | 100% | IdolCardLevelLimitRank(_1.._7)。 | "IdolCardLevelLimitRank__1", "IdolCardLevelLimitRank__2" |
| `consumptionSetId` | string | 100% | → ConsumptionSet。 | "cs-idol_card_level_limit-r-plan1-vi-da-1", "cs-idol_card_level_limit-r-plan1-vi-da-2" |

外键（按 id 连接验证）：
- `consumptionSetId` → **ConsumptionSet** (171/171 命中)

代表行：
```json
{"id": "idol_card_level_limit-r-plan1-vi-da", "rank": "IdolCardLevelLimitRank__1", "consumptionSetId": "cs-idol_card_level_limit-r-plan1-vi-da-1"}
{"id": "idol_card_level_limit-sr-plan2-vo-vi", "rank": "IdolCardLevelLimitRank__2", "consumptionSetId": "cs-idol_card_level_limit-sr-plan2-vo-vi-2"}
```

### IdolCardLevelLimitProduceSkill（44 行）

突破到 rank 时解锁/升级的 ProduceSkill(p_idol_skill)。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "idol_card_level_limit_produce_skill_001", "idol_card_level_limit_produce_skill_002" |
| `produceSkillId` | string | 100% | → ProduceSkill。 | "p_idol_skill-common-p_trigger-produce_s…", "p_idol_skill-common-p_trigger-produce_s…" |
| `produceSkillLevel` | int32 | 100% | 技能等级。 | 1, 2 |
| `rank` | IdolCardLevelLimitRank | 100% | 突破段。 | "IdolCardLevelLimitRank__7", "IdolCardLevelLimitRank__2" |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 2, 1 |

外键（按 id 连接验证）：
- `produceSkillId` → **ProduceSkill** (16/16 命中)

代表行：
```json
{"id": "idol_card_level_limit_produce_skill_001", "produceSkillId": "p_idol_skill-common-p_trigger-produce_start-no_description-idol_card_produce_card_customi…", "produceSkillLevel": 1, "rank": "IdolCardLevelLimitRank__7", "order": 2}
{"id": "idol_card_level_limit_produce_skill_008", "produceSkillId": "p_idol_skill-common-p_trigger-produce_start-no_description-lesson_sp_change_rate_permil_a…", "produceSkillLevel": 2, "rank": "IdolCardLevelLimitRank__6", "order": 2}
```

### IdolCardLevelLimitStatusUp（38 行）

突破各段的效果：ProduceVoDaVi(+三维)/ProduceSkill/ProduceCardUpgrade(固有卡强化)/ProduceStamina/SecondProduceCardUpgrade。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "level_limit_status_up-001", "level_limit_status_up-002" |
| `rank` | IdolCardLevelLimitRank | 100% | 突破段。 | "IdolCardLevelLimitRank__1", "IdolCardLevelLimitRank__2" |
| `effectTypes` | repeated IdolCardLevelLimitEffectType | 100% | IdolCardLevelLimitEffectType。 | ["IdolCardLevelLimitEffectType_ProduceVoD…"], ["IdolCardLevelLimitEffectType_ProduceSki…"] |
| `effectValue` | int32 | 24% | 数值（体力+3 等）。 | 0, 3 |
| `produceVocal` | int32 | 24% | +Vocal。 | 10, 0 |
| `produceDance` | int32 | 24% | 。 | 10, 0 |
| `produceVisual` | int32 | 24% | 。 | 10, 0 |
| `isIllustrationChange` | bool | 16% | 换立绘。 | false, true |

代表行：
```json
{"id": "level_limit_status_up-001", "rank": "IdolCardLevelLimitRank__1", "effectTypes": ["IdolCardLevelLimitEffectType_ProduceVoDaVi"], "produceVocal": 10, "produceDance": 10, "produceVisual": 10}
{"id": "level_limit_status_up-003", "rank": "IdolCardLevelLimitRank__6", "effectTypes": ["IdolCardLevelLimitEffectType_ProduceSkill"]}
```

### IdolCardPotential（604 行）

潜能(ポテンシャル) 4 段：每段效果类型（ProduceSkill/InitialProduceItemChange/ProduceStamina/ProduceVoDaViGrowthRatePermil）、成长率加成、消耗碎片。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "idol_card_potential-amao-r-01", "idol_card_potential-amao-sr-01" |
| `rank` | IdolCardPotentialRank | 100% | IdolCardPotentialRank。 | "IdolCardPotentialRank__1", "IdolCardPotentialRank__2" |
| `effectTypes` | repeated IdolCardPotentialEffectType | 100% | IdolCardPotentialEffectType。 | ["IdolCardPotentialEffectType_ProduceSkill"], ["IdolCardPotentialEffectType_InitialProd…"] |
| `effectValue` | int32 | 25% | 体力等数值。 | 0, 3 |
| `produceVocalGrowthRatePermil` | int32 | 15% | 成长率+。 | 0, 10 |
| `produceDanceGrowthRatePermil` | int32 | 20% | 。 | 0, 10 |
| `produceVisualGrowthRatePermil` | int32 | 18% | 。 | 0, 10 |
| `anotherCostumeProvide` | bool | 22% | 赠服装。 | false, true |
| `consumptionPiece` | int32 | 100% | 消耗碎片数。 | 25, 50 |

代表行：
```json
{"id": "idol_card_potential-amao-r-01", "rank": "IdolCardPotentialRank__1", "effectTypes": ["IdolCardPotentialEffectType_ProduceSkill"], "consumptionPiece": 25}
{"id": "idol_card_potential-i_card-hume-3-017", "rank": "IdolCardPotentialRank__3", "effectTypes": ["IdolCardPotentialEffectType_ProduceVoDaViGrowthRatePermil"], "produceVocalGrowthRatePermil": 30, "produceDanceGrowthRatePermil": 50, "consumptionPiece": 150}
```

### IdolCardPotentialProduceSkill（250 行）

潜能段解锁的 ProduceSkill。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "idol_card_potential_produce_skill_001", "idol_card_potential_produce_skill-i_car…" |
| `produceSkillId` | string | 100% | → ProduceSkill。 | "p_idol_skill-common-p_trigger-produce_s…", "p_idol_skill-common-p_trigger-produce_s…" |
| `produceSkillLevel` | int32 | 100% | 等级。 | 1, 2 |
| `rank` | IdolCardPotentialRank | 100% | 潜能段。 | "IdolCardPotentialRank__4", "IdolCardPotentialRank__1" |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 2, 1 |

外键（按 id 连接验证）：
- `produceSkillId` → **ProduceSkill** (6/6 命中)

代表行：
```json
{"id": "idol_card_potential_produce_skill_001", "produceSkillId": "p_idol_skill-common-p_trigger-produce_start-no_description-produce_card_select_reroll_cou…", "produceSkillLevel": 1, "rank": "IdolCardPotentialRank__4", "order": 2}
{"id": "idol_card_potential_produce_skill-i_card-hume-3-012", "produceSkillId": "p_idol_skill-common-p_trigger-produce_start-no_description-produce_card_select_reroll_cou…", "produceSkillLevel": 1, "rank": "IdolCardPotentialRank__4", "order": 2}
```

### IdolCardPrimaStellaProduceSkill（10 行）

プリマステラ（H.I.F 一番星称号）解放后获得的技能：培育开始时获得专属 Legend 卡（p_card-xx-ido-100_0xx）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "prima_stella_produce_skill-i_card-amao-…", "prima_stella_produce_skill-i_card-hmsz-…" |
| `produceSkillId` | string | 100% | → ProduceSkill。 | "p_primastella_skill-common-hatsuboshi_i…", "p_primastella_skill-common-hatsuboshi_i…" |
| `produceSkillLevel` | int32 | 100% | 技能等级（全 1）。 | 1 |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 1 |

外键（按 id 连接验证）：
- `produceSkillId` → **ProduceSkill** (10/10 命中)

代表行：
```json
{"id": "prima_stella_produce_skill-i_card-amao-3-015", "produceSkillId": "p_primastella_skill-common-hatsuboshi_idol_festival-final-p_trigger-produce_start-produce…", "produceSkillLevel": 1, "order": 1}
{"id": "prima_stella_produce_skill-i_card-kcna-3-014", "produceSkillId": "p_primastella_skill-common-hatsuboshi_idol_festival-final-p_trigger-produce_start-produce…", "produceSkillLevel": 1, "order": 1}
```

### IdolCardSimulation（0 行）

空表。

### Character（24 行）

角色（24，isPlayable 13 位可培育偶像 + NPC）。含服装、亲爱度任务组、真结局加成等引用。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "amao", "andk" |
| `lastName` | string | 100% | 姓。 | "有村", "藍井" |
| `firstName` | string | 100% | 名。 | "麻央", "撫子" |
| `alphabetLastName` | string | 100% | 罗马字姓。 | "ARIMURA", "AOI" |
| `alphabetFirstName` | string | 100% | 罗马字名。 | "MAO", "NADESHIKO" |
| `isPlayable` | bool | 54% | 可培育。 | true, false |
| `personalityType` | CharacterPersonalityType | 100% | CharacterPersonalityType。 | "CharacterPersonalityType_C", "CharacterPersonalityType_Unknown" |
| `characterTrueEndBonusId` | string | 54% | → CharacterTrueEndBonus。 | "character_true_end_bonus-amao", "character_true_end_bonus-atbm" |
| `achievementIds` | repeated string | 54% | → Achievement。 | ["achieve-m_amao-001", "achieve-p_idol-amao-000", "achieve-p_idol-amao-000-1", "achieve-p_idol-amao-000-2", "achieve-p_idol-amao-001", "…(+26)"], ["achieve-m_atbm-001", "achieve-p_idol-atbm-000", "achieve-p_idol-atbm-000-1", "achieve-p_idol-atbm-001", "achieve-p_idol-atbm-002", "…(+22)"] |
| `masterAchievementId` | string | 54% | → Achievement。 | "achieve-m_amao-001", "achieve-m_atbm-001" |
| `idolCardIds` | repeated string | 54% | → IdolCard。 | ["i_card-amao-1-000", "i_card-amao-1-001", "i_card-amao-2-000", "i_card-amao-3-000", "i_card-amao-3-001", "…(+7)"], ["i_card-atbm-1-000", "i_card-atbm-2-000", "i_card-atbm-3-000", "i_card-atbm-3-012", "i_card-atbm-3-018"] |
| `supportCardIds` | repeated string | 58% | → SupportCard。 | ["s_card-1-0003", "s_card-1-0012", "s_card-2-0002", "s_card-2-0003", "s_card-2-0013", "…(+34)"], ["s_card-1-0012", "s_card-2-0049", "s_card-2-0051", "s_card-2-0056", "s_card-2-0066", "…(+21)"] |
| `changeCostumeConditionSetId` | string | 4% | → ConditionSet。 | "cd-view-costume-nasr-2026" |
| `viewConditionSetId` | string | 0% | → ConditionSet，显示条件。 |  |
| `normalCostumeHeadId` | string | 58% | 服装。 | "costume_head_amao-casl-0000", "costume_head_atbm-schl-0000" |
| `trainingCostumeHeadId` | string | 58% | 。 | "costume_head_amao-casl-0000", "costume_head_atbm-schl-0000" |
| `liveCostumeHeadId` | string | 58% | 。 | "costume_head_amao-casl-0000", "costume_head_atbm-cstm-0000" |
| `normalCostumeId` | string | 58% | 。 | "amao-casl-0000", "atbm-schl-0000" |
| `trainingCostumeId` | string | 58% | 。 | "amao-trng-0000", "atbm-trng-0000" |
| `liveCostumeId` | string | 58% | 。 | "amao-cstm-0000", "atbm-cstm-0000" |
| `dearnessMissionGroupId` | string | 54% | → MissionGroup。 | "dearness_normal-mission_amao_01", "dearness_normal-mission_atbm_01" |
| `dearnessStoryUnlockItemId` | string | 54% | → Item。 | "item-dearness-unlock-amao", "item-dearness-unlock-atbm" |
| `produceCardIds` | repeated string | 4% | → ProduceCard（nasr 专属）。 | ["p_card-02-ido-3_192", "p_card-03-ido-3_193", "p_card-01-ido-3_191"] |
| `otherStoryIds` | repeated string | 54% | → Story。 | ["story_2025_bd-01_amao-01", "story-2024_p-bd-01_amao-01"], ["story-2025_p-bd-01_atbm-01", "story-2026_bd-01_atbm-01"] |
| `potentialRank1VoiceAssetId` | string | 54% | 语音。 | "sud_vo_system_amao_idol_potential-01", "sud_vo_system_atbm_idol_potential-01" |
| `potentialRank3VoiceAssetId` | string | 54% | 语音。 | "sud_vo_system_amao_idol_potential-01", "sud_vo_system_atbm_idol_potential-01" |
| `potentialRank4VoiceAssetId` | string | 54% | 语音。 | "sud_vo_system_amao_idol_potential-02", "sud_vo_system_atbm_idol_potential-02" |
| `useProduceCardVoiceAssetId` | string | 4% | 语音。 | "sud_vo_system_nasr_produce_skillcard-01" |
| `standingListPositionX` | float | 0% | UI。 | 0 |
| `standingListPositionY` | float | 4% | UI。 | 0, 20 |
| `rosterDetailPositionX` | float | 8% | UI。 | 0, -19 |
| `rosterDetailPositionY` | float | 4% | UI。 | 0, 20 |
| `storyPositionX` | float | 33% | UI。 | 30, 0 |
| `storyPositionY` | float | 38% | UI。 | 40, 0 |
| `produceHighScorePositionX` | float | 12% | UI。 | 8, 0 |
| `produceHighScorePositionY` | float | 4% | UI。 | 0, 186 |
| `produceHighScoreRushPositionX` | float | 54% | UI。 | -8, 0 |
| `produceHighScoreRushPositionY` | float | 54% | UI。 | 219, 0 |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 40, 9999 |

外键（按 id 连接验证）：
- `characterTrueEndBonusId` → **CharacterTrueEndBonus** (13/13 命中)
- `achievementIds` → **Achievement** (392/392 命中)
- `masterAchievementId` → **Achievement** (13/13 命中)
- `idolCardIds` → **IdolCard** (151/151 命中)
- `supportCardIds` → **SupportCard** (200/200 命中)
- `changeCostumeConditionSetId` → **ConditionSet** (1/1 命中)
- `normalCostumeHeadId` → **CostumeHead** (14/14 命中)
- `trainingCostumeHeadId` → **CostumeHead** (14/14 命中)
- `liveCostumeHeadId` → **CostumeHead** (14/14 命中)
- `normalCostumeId` → **Costume** (14/14 命中)
- `trainingCostumeId` → **Costume** (14/14 命中)
- `liveCostumeId` → **Costume** (14/14 命中)
- `dearnessMissionGroupId` → **MissionGroup** (13/13 命中)
- `dearnessStoryUnlockItemId` → **Item** (13/13 命中)
- `produceCardIds` → **ProduceCard** (3/3 命中)
- `otherStoryIds` → **Story** (26/26 命中)

代表行：
```json
{"id": "amao", "lastName": "有村", "firstName": "麻央", "alphabetLastName": "ARIMURA", "alphabetFirstName": "MAO", "isPlayable": true, "personalityType": "CharacterPersonalityType_C", "characterTrueEndBonusId": "character_true_end_bonus-amao", "achievementIds": ["achieve-m_amao-001", "achieve-p_idol-amao-000", "achieve-p_idol-amao-000-1", "achieve-p_idol-amao-000-2", "achieve-p_idol-amao-001", "…(+26)"], "masterAchievementId": "achieve-m_amao-001", "idolCardIds": ["i_card-amao-1-000", "i_card-amao-1-001", "i_card-amao-2-000", "i_card-amao-3-000", "i_card-amao-3-001", "…(+7)"], "supportCardIds": ["s_card-1-0003", "s_card-1-0012", "s_card-2-0002", "s_card-2-0003", "s_card-2-0013", "…(+34)"], "normalCostumeHeadId": "costume_head_amao-casl-0000", "trainingCostumeHeadId": "costume_head_amao-casl-0000", "liveCostumeHeadId": "costume_head_amao-casl-0000", "normalCostumeId": "amao-casl-0000", "trainingCostumeId": "amao-trng-0000", "liveCostumeId": "amao-cstm-0000", "dearnessMissionGroupId": "dearness_normal-mission_amao_01", "dearnessStoryUnlockItemId": "item-dearness-unlock-amao", "otherStoryIds": ["story_2025_bd-01_amao-01", "story-2024_p-bd-01_amao-01"], "potentialRank1VoiceAssetId": "sud_vo_system_amao_idol_potential-01", "potentialRank3VoiceAssetId": "sud_vo_system_amao_idol_potential-01", "potentialRank4VoiceAssetId": "sud_vo_system_amao_idol_potential-02", "storyPositionX": 30, "storyPositionY": 40, "produceHighScorePositionX": 8, "produceHighScoreRushPositionX": -8, "produceHighScoreRushPositionY": 219, "order": 40}
{"id": "krnh", "lastName": "賀陽", "firstName": "燐羽", "alphabetLastName": "KAYA", "alphabetFirstName": "RINHA", "order": 9999}
```

### CharacterDearnessLevel（451 行）

亲爱度等级表（每角色 1..37 级）：每级的培育条件、**获得的 ProduceSkill(p_dearness_skill) 及等级**、真结局目标等级标记。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `dearnessLevel` | int32 | 100% | 亲爱度等级。 | 1, 2 |
| `advAssetId` | string | 100% | 剧情 ADV。 | "adv_dear_amao_001", "adv_dear_amao_002" |
| `storyId` | string | 0% | 未使用。 |  |
| `produceConditionDescription` | string | 97% | 升级所需培育条件说明。 | "プロデュース中にレッスンを1回以上完了する", "プロデュース中に中間試験を合格後1週経過する" |
| `produceConditionAchievementId` | string | 3% | → Achievement。 | "achieve-p_idol-amao-001", "achieve-p_idol-atbm-002" |
| `produceConditionAchievementThreshold` | int32 | 3% | 成就阈值。 | 0, 250 |
| `produceSkills` | repeated ProduceSkill | 97% | 该级获得的技能列表。 | [{"id": "p_dearness_skill-common-p_trigger-produ…", "level": 1}], [{"id": "p_dearness_skill-common-p_trigger-produ…", "level": 2}] |
| `rewards` | repeated Reward | 0% | 奖励。 | [{"resourceType": "ResourceType_Costume", "resourceId": "amao-casl-0001", "quantity": 1}, {"resourceType": "ResourceType_CostumeHead", "resourceId": "costume_head_amao-casl-0001", "quantity": 1}, {"resourceType": "ResourceType_CostumeHead", "resourceId": "costume_head_amao-hair-0000", "quantity": 1}] |
| `ignoreReport` | bool | 74% | 不出报告。 | false, true |
| `itemUnlockConditionSetId` | string | 20% | → ConditionSet。 | "cd-ralease_dearness-story-amao", "cd-ralease_dearness-story-atbm" |
| `isStepThresholdLevel` | bool | 11% | 阶段门槛级。 | false, true |
| `isTargetLevel` | bool | 11% | 真结局目标级（最終試験1位/FINALE優勝/一番星）。 | false, true |
| `targetDescription` | string | 8% | 目标说明。 | "最終試験1位", "FINALEで優勝" |
| `trueEndAchievementProduceType` | ProduceType | 100% | 对应剧本系列。 | "ProduceType_Unknown", "ProduceType_FirstStar" |
| `dearnessPointThreshold` | int32 | 20% | 所需亲爱度点。 | 0, 20 |
| `storyGroupOrder` | int32 | 100% | 排序。 | 10, 20 |
| &nbsp;&nbsp;↳ `id` | string | 100% | → ProduceSkill。 | "p_dearness_skill-common-p_trigger-produ…", "p_dearness_skill-common-p_trigger-produ…" |
| &nbsp;&nbsp;↳ `level` | int32 | 100% | 技能等级。 | 1, 2 |
| &nbsp;&nbsp;↳ `resourceType` | ResourceType | 100% | 。 | "ResourceType_Costume", "ResourceType_CostumeHead" |
| &nbsp;&nbsp;↳ `resourceId` | string | 100% | 。 | "amao-casl-0001", "costume_head_amao-casl-0001" |
| &nbsp;&nbsp;↳ `quantity` | int32 | 100% | 。 | 1 |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `produceConditionAchievementId` → **Achievement** (13/13 命中)
- `itemUnlockConditionSetId` → **ConditionSet** (13/13 命中)
- `rewards.resourceId` → CostumeHead? (2/3 = 67%，多态或部分引用)

代表行：
```json
{"characterId": "amao", "dearnessLevel": 1, "advAssetId": "adv_dear_amao_001", "storyGroupOrder": 10}
{"characterId": "hume", "dearnessLevel": 24, "advAssetId": "adv_dear_hume_024", "produceConditionDescription": "親愛度Ptを累計300獲得して最終試験/最終オーディションクリア", "produceSkills": [{"id": "p_dearness_skill-common-p_trigger-produce_start-no_description-audition_parameter_bonus_m…", "level": 7}, {"id": "p_dearness_skill-common-p_trigger-produce_start-no_description-produce_card_select_reroll…", "level": 3}, {"id": "p_dearness_skill-common-p_trigger-produce_start-no_description-event_business_vote_count_…", "level": 9}, {"id": "p_dearness_skill-common-p_trigger-produce_start-no_description-audition_vote_count_up-03-…", "level": 9}, {"id": "p_dearness_skill-common-p_trigger-produce_start-no_description-produce_card_exclude_count…", "level": 1}, "…(+2)"], "ignoreReport": true, "itemUnlockConditionSetId": "cd-ralease_dearness-story-hume", "dearnessPointThreshold": 300, "storyGroupOrder": 240}
```

### CharacterTrueEndBonus（36 行）

真结局(トゥルーエンド)达成后的永久培育加成：按剧本系列给三维/成长率/体力。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "character_true_end_bonus-amao", "character_true_end_bonus-atbm" |
| `produceType` | ProduceType | 100% | ProduceType：FirstStar=定期公演『初』 / NextIdolAudition=N.I.A / HatsuboshiIdolFestival=H.I.F。 | "ProduceType_FirstStar", "ProduceType_NextIdolAudition" |
| `produceVocal` | int32 | 50% | +Vocal。 | 10, 15 |
| `produceDance` | int32 | 56% | 。 | 0, 20 |
| `produceVisual` | int32 | 67% | 。 | 10, 15 |
| `produceVocalGrowthRatePermil` | int32 | 50% | 成长率+。 | 0, 10 |
| `produceDanceGrowthRatePermil` | int32 | 56% | 。 | 0, 20 |
| `produceVisualGrowthRatePermil` | int32 | 61% | 。 | 50, 0 |
| `produceStamina` | int32 | 19% | +体力。 | 0, 4 |

代表行：
```json
{"id": "character_true_end_bonus-amao", "produceType": "ProduceType_FirstStar", "produceVocal": 10, "produceVisual": 10, "produceVisualGrowthRatePermil": 50}
{"id": "character_true_end_bonus-hume", "produceType": "ProduceType_HatsuboshiIdolFestival", "produceVocal": 25, "produceDance": 25, "produceVisual": 25, "produceVisualGrowthRatePermil": 30}
```

### SupportCard（201 行）

支援卡（201）：type(Vocal/Dance/Visual/Assist)、プラン、稀有度、等级表、突破表、剧情、**课程中强化手牌概率 produceCardUpgradePermil**（レッスンサポート）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "s_card-1-0000", "s_card-1-0001" |
| `characterIds` | repeated string | 100% | 登场角色。 | ["hski", "kcna", "shro"], ["ttmr", "hski"] |
| `name` | string | 100% | 显示名（日文）。 | "念入りにストレッチ", "全力、その後" |
| `type` | SupportCardType | 100% | SupportCardType。 | "SupportCardType_Visual", "SupportCardType_Vocal" |
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Common", "ProducePlanType_Plan2" |
| `rarity` | SupportCardRarity | 100% | 稀有度枚举。 | "SupportCardRarity_R", "SupportCardRarity_Sr" |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "csprt-1-0000", "csprt-1-0001" |
| `supportCardLevelId` | string | 100% | → SupportCardLevel。 | "support_card_level-1-001", "support_card_level-2-001" |
| `supportCardLevelLimitId` | string | 100% | → SupportCardLevelLimit。 | "support_card_level_limit-1-001", "support_card_level_limit-2-001" |
| `produceStoryIds` | repeated string | 100% | → ProduceStory。 | ["p_story-s_card-1-0000-01", "p_story-s_card-1-0000-02"], ["p_story-s_card-1-0001-01", "p_story-s_card-1-0001-02"] |
| `displayPositionX` | float | 0% | UI。 | 0 |
| `displayPositionY` | float | 0% | UI。 | 0 |
| `displayScale` | float | 56% | UI。 | 1, 0 |
| &nbsp;&nbsp;↳ `resourceType` | ResourceType | 100% | 分解奖励。 | "ResourceType_Item" |
| &nbsp;&nbsp;↳ `resourceId` | string | 100% | 。 | "item-support_card-exchange-1" |
| &nbsp;&nbsp;↳ `quantity` | int32 | 100% | 。 | 1, 5 |
| `isLimited` | bool | 0% | 限定标记（全库均为 false）。 | false |
| `produceCardUpgradePermil` | int32 | 100% | レッスンサポート 发生率千分比（每张卡基础值；技能 SupportCardProduceCardUpgradeProbabilityUp 叠加）。 | 19, 28 |
| `upgradeProduceCardSearchId` | string | 100% | → ProduceCardSearch（手札）。 | "p_card_search-hand" |
| `produceCardUpgradeLessonParameterType` | ProduceParameterType | 100% | 只在该属性课程中发生。 | "ProduceParameterType_Visual", "ProduceParameterType_Vocal" |
| `gashaSupportAnimationNumber` | int32 | 9% | 抽卡演出。 | 0, 1 |
| `upgradeProduceCardProduceDescriptions` | repeated ProduceDescriptionSegment | 100% | サポート发生率描述（確率小/中/大）。 | "(渲染) / 確率小", "(渲染) / 確率中" |
| `viewStartTime` | int64 | 100% | 可见起始时间，Unix 毫秒字符串；"0" 表示一直可见。 | "0", "1716339600000" |
| `order` | int64 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | "3999900001", "3999900002" |

外键（按 id 连接验证）：
- `characterIds` → **Character** (14/14 命中)
- `supportCardLevelId` → **SupportCardLevel** (3/3 命中)
- `supportCardLevelLimitId` → **SupportCardLevelLimit** (3/3 命中)
- `produceStoryIds` → **ProduceStory** (511/511 命中)
- `exchangeReward.resourceId` → **Item** (1/1 命中)
- `upgradeProduceCardSearchId` → **ProduceCardSearch** (1/1 命中)

代表行：
```json
{"id": "s_card-1-0000", "characterIds": ["hski", "kcna", "shro"], "name": "念入りにストレッチ", "type": "SupportCardType_Visual", "planType": "ProducePlanType_Common", "rarity": "SupportCardRarity_R", "assetId": "csprt-1-0000", "supportCardLevelId": "support_card_level-1-001", "supportCardLevelLimitId": "support_card_level_limit-1-001", "produceStoryIds": ["p_story-s_card-1-0000-01", "p_story-s_card-1-0000-02"], "displayScale": 1, "exchangeReward": {"resourceType": "ResourceType_Item", "resourceId": "item-support_card-exchange-1", "quantity": 1}, "produceCardUpgradePermil": 19, "upgradeProduceCardSearchId": "p_card_search-hand", "produceCardUpgradeLessonParameterType": "ProduceParameterType_Visual", "upgradeProduceCardProduceDescriptions": "(渲染) / 確率小", "viewStartTime": "0", "order": "3999900001"}
{"id": "s_card-3-0008", "characterIds": ["kllj", "ssmk"], "name": "おいしい顔、いただき～！", "type": "SupportCardType_Dance", "planType": "ProducePlanType_Common", "rarity": "SupportCardRarity_Ssr", "assetId": "csprt-3-0008", "supportCardLevelId": "support_card_level-3-001", "supportCardLevelLimitId": "support_card_level_limit-3-001", "produceStoryIds": ["p_story-s_card-3-0008-01", "p_story-s_card-3-0008-02", "p_story-s_card-3-0008-03"], "displayScale": 1, "exchangeReward": {"resourceType": "ResourceType_Item", "resourceId": "item-support_card-exchange-1", "quantity": 50}, "produceCardUpgradePermil": 37, "upgradeProduceCardSearchId": "p_card_search-hand", "produceCardUpgradeLessonParameterType": "ProduceParameterType_Dance", "upgradeProduceCardProduceDescriptions": "(渲染) / 確率大", "viewStartTime": "0", "order": "1999900008"}
```

### SupportCardBonus（15 行）

支援卡等级里程碑加成（rarity × level → bonusPermyriad，万分比）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `rarity` | SupportCardRarity | 100% | 稀有度枚举。 | "SupportCardRarity_R", "SupportCardRarity_Sr" |
| `level` | int32 | 100% | 等级。 | 10, 20 |
| `bonusPermyriad` | int32 | 100% | 加成万分比。 | 1, 2 |

代表行：
```json
{"rarity": "SupportCardRarity_R", "level": 10, "bonusPermyriad": 1}
{"rarity": "SupportCardRarity_Sr", "level": 40, "bonusPermyriad": 6}
```

### SupportCardLevel（150 行）

支援卡经验表（3 种稀有度 × 等级 → totalExp）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "support_card_level-1-001", "support_card_level-2-001" |
| `level` | int32 | 100% | 等级。 | 1, 2 |
| `totalExp` | int32 | 98% | 累计经验。 | 0, 32 |

代表行：
```json
{"id": "support_card_level-1-001", "level": 1}
{"id": "support_card_level-2-001", "level": 36, "totalExp": 35004}
```

### SupportCardLevelLimit（15 行）

支援卡突破段 → 等级上限。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "support_card_level_limit-1-001", "support_card_level_limit-2-001" |
| `rank` | SupportCardLevelLimitRank | 100% | SupportCardLevelLimitRank。 | "SupportCardLevelLimitRank_Unknown", "SupportCardLevelLimitRank__1" |
| `levelLimit` | int32 | 100% | 等级上限。 | 20, 25 |

代表行：
```json
{"id": "support_card_level_limit-1-001", "levelLimit": 20}
{"id": "support_card_level_limit-2-001", "rank": "SupportCardLevelLimitRank__2", "levelLimit": 40}
```

### SupportCardProduceSkillLevelVocal（5109 行）

Vocal 支援卡在各等级解锁/升级的 ProduceSkill(p_support_skill)：(supportCardId, produceSkillId, produceSkillLevel) 于 supportCardLevel 生效。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `supportCardId` | string | 100% | → SupportCard。 | "s_card-1-0001", "s_card-1-0003" |
| `produceSkillId` | string | 100% | → ProduceSkill。 | "p_support_skill-common-p_trigger-end_le…", "p_support_skill-common-p_trigger-produc…" |
| `produceSkillLevel` | int32 | 100% | 技能等级。 | 1, 2 |
| `supportCardLevel` | int32 | 100% | 支援卡等级。 | 5, 36 |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 2, 4 |

外键（按 id 连接验证）：
- `supportCardId` → **SupportCard** (67/67 命中)
- `produceSkillId` → **ProduceSkill** (79/79 命中)

代表行：
```json
{"supportCardId": "s_card-1-0001", "produceSkillId": "p_support_skill-common-p_trigger-end_lesson-lesson_vocal-vocal_addition-01-001", "produceSkillLevel": 1, "supportCardLevel": 5, "order": 2}
{"supportCardId": "s_card-3-0016", "produceSkillId": "p_support_skill-common-p_trigger-produce_start-no_description-support_card_produce_card_u…", "produceSkillLevel": 12, "supportCardLevel": 13, "order": 6}
```

### SupportCardProduceSkillLevelDance（4764 行）

同上，Dance 支援卡。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `supportCardId` | string | 100% | → SupportCard。 | "s_card-1-0002", "s_card-1-0007" |
| `produceSkillId` | string | 100% | → ProduceSkill。 | "p_support_skill-common-p_trigger-end_le…", "p_support_skill-common-p_trigger-produc…" |
| `produceSkillLevel` | int32 | 100% | 技能等级。 | 1, 2 |
| `supportCardLevel` | int32 | 100% | 支援卡等级。 | 5, 36 |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 2, 1 |

外键（按 id 连接验证）：
- `supportCardId` → **SupportCard** (63/63 命中)
- `produceSkillId` → **ProduceSkill** (72/72 命中)

代表行：
```json
{"supportCardId": "s_card-1-0002", "produceSkillId": "p_support_skill-common-p_trigger-end_lesson-lesson_dance-dance_addition-01-001", "produceSkillLevel": 1, "supportCardLevel": 5, "order": 2}
{"supportCardId": "s_card-3-0017", "produceSkillId": "p_support_skill-common-p_trigger-produce_start-no_description-support_card_produce_card_u…", "produceSkillLevel": 15, "supportCardLevel": 16, "order": 6}
```

### SupportCardProduceSkillLevelVisual（5091 行）

同上，Visual 支援卡。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `supportCardId` | string | 100% | → SupportCard。 | "s_card-1-0000", "s_card-1-0004" |
| `produceSkillId` | string | 100% | → ProduceSkill。 | "p_support_skill-common-p_trigger-end_le…", "p_support_skill-common-p_trigger-produc…" |
| `produceSkillLevel` | int32 | 100% | 技能等级。 | 1, 2 |
| `supportCardLevel` | int32 | 100% | 支援卡等级。 | 5, 36 |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 2, 4 |

外键（按 id 连接验证）：
- `supportCardId` → **SupportCard** (67/67 命中)
- `produceSkillId` → **ProduceSkill** (83/83 命中)

代表行：
```json
{"supportCardId": "s_card-1-0000", "produceSkillId": "p_support_skill-common-p_trigger-end_lesson-lesson_visual-visual_addition-01-001", "produceSkillLevel": 1, "supportCardLevel": 5, "order": 2}
{"supportCardId": "s_card-3-0015", "produceSkillId": "p_support_skill-common-p_trigger-produce_start-no_description-support_card_produce_card_u…", "produceSkillLevel": 13, "supportCardLevel": 14, "order": 6}
```

### SupportCardProduceSkillLevelAssist（307 行）

同上，Assist 支援卡。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `supportCardId` | string | 100% | → SupportCard。 | "s_card-2-0014", "s_card-3-0019" |
| `produceSkillId` | string | 100% | → ProduceSkill。 | "p_support_skill-common-p_trigger-end_le…", "p_support_skill-common-p_trigger-produc…" |
| `produceSkillLevel` | int32 | 100% | 技能等级。 | 1, 2 |
| `supportCardLevel` | int32 | 100% | 支援卡等级。 | 10, 41 |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 3, 1 |

外键（按 id 连接验证）：
- `supportCardId` → **SupportCard** (4/4 命中)
- `produceSkillId` → **ProduceSkill** (19/19 命中)

代表行：
```json
{"supportCardId": "s_card-2-0014", "produceSkillId": "p_support_skill-common-p_trigger-end_lesson_before_present-lesson-lesson_present_produce_…", "produceSkillLevel": 1, "supportCardLevel": 10, "order": 3}
{"supportCardId": "s_card-3-0020", "produceSkillId": "p_support_skill-common-p_trigger-produce_start-no_description-lesson_sp_change_rate_permi…", "produceSkillLevel": 2, "supportCardLevel": 15, "order": 4}
```

### SupportCardProduceSkillFilter（44 行）

支援卡技能筛选 UI 分类（title → ProduceEffectType 列表 + ProduceTrigger 列表）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "s_card_p_skill_filter-lessonpresentprod…", "s_card_p_skill_filter-lessonvocalspchan…" |
| `title` | string | 100% | 标题。 | "Pポイント獲得量増加", "SPレッスン発生率+" |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 36, 3 |
| `produceEffectTypes` | repeated ProduceEffectType | 100% | 。 | ["ProduceEffectType_LessonPresentProduceP…"], ["ProduceEffectType_LessonVocalSpChangeRa…", "ProduceEffectType_LessonSpChangeRatePer…", "ProduceEffectType_LessonDanceSpChangeRa…", "ProduceEffectType_LessonSpChangeRatePer…", "ProduceEffectType_LessonVisualSpChangeR…", "…(+1)"] |
| `produceTriggerIds` | repeated string | 100% | → ProduceTrigger。 | ["p_trigger-end_lesson_before_present-les…", "p_trigger-end_lesson_before_present-les…", "p_trigger-end_lesson_before_present-les…", "p_trigger-end_lesson_before_present-les…", "p_trigger-end_lesson_before_present-les…", "…(+2)"], ["p_trigger-produce_start-no_description"] |

外键（按 id 连接验证）：
- `produceTriggerIds` → **ProduceTrigger** (51/51 命中)

代表行：
```json
{"id": "s_card_p_skill_filter-lessonpresentproducepointup-p_trigger-end_lesson_before_present-les…", "title": "Pポイント獲得量増加", "order": 36, "produceEffectTypes": ["ProduceEffectType_LessonPresentProducePointUp"], "produceTriggerIds": ["p_trigger-end_lesson_before_present-lesson", "p_trigger-end_lesson_before_present-lesson_dance_sp", "p_trigger-end_lesson_before_present-lesson_dance", "p_trigger-end_lesson_before_present-lesson_visual_sp", "p_trigger-end_lesson_before_present-lesson_visual", "…(+2)"]}
{"id": "s_card_p_skill_filter-vocaladdition-p_trigger-get_produce_card-0000_0000-p_card_search-de…", "title": "スキルカード獲得時パラメータ上昇", "order": 14, "produceEffectTypes": ["ProduceEffectType_VocalAddition", "ProduceEffectType_DanceAddition", "ProduceEffectType_VisualAddition"], "produceTriggerIds": ["p_trigger-get_produce_card-0000_0000-p_card_search-deck_all"]}
```

## 9. G. 自动打牌评估

### ProduceExamAutoEvaluation（11130 行）

自动打牌(オート)的启发式权重表（11130 = 5 ExamPlayType × 6 流派 × 7 remainingTerm × 53 evaluationType）：对每个状态量 evaluationType 给出权重 evaluation，以及持续效果系数 examStatusEnchantCoefficientPermil。可作为我们 baseline agent 的价值函数参考。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ExamPlayType | 100% | ExamPlayType（AutoPlay/AutoPlayCompetition/ManualPlayLesson/ManualPlayLessonHard/ManualPlayAudition）。 | "ExamPlayType_AutoPlay", "ExamPlayType_ManualPlayLesson" |
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_ExamParameterBuff", "ProduceExamEffectType_ExamLessonBuff" |
| `remainingTerm` | int32 | 100% | 剩余回合分档 1..7（7=7 回合以上）。 | 1, 2 |
| `evaluationType` | ProduceExamAutoEvaluationType | 100% | ProduceExamAutoEvaluationType。 | "ProduceExamAutoEvaluationType_Parameter", "ProduceExamAutoEvaluationType_Block" |
| `evaluation` | int32 | 93% | 评价分：用于メモリー/编成强度评估（越高越强）。 | 162, 0 |
| `examStatusEnchantCoefficientPermil` | int32 | 91% | 持续效果的折算系数。 | 0, 1 |

代表行：
```json
{"type": "ExamPlayType_AutoPlay", "examEffectType": "ProduceExamEffectType_ExamParameterBuff", "remainingTerm": 1, "evaluationType": "ProduceExamAutoEvaluationType_Parameter", "evaluation": 162}
{"type": "ExamPlayType_ManualPlayLessonHard", "examEffectType": "ProduceExamEffectType_ExamCardPlayAggressive", "remainingTerm": 1, "evaluationType": "ProduceExamAutoEvaluationType_Parameter", "evaluation": 162}
```

### ProduceExamAutoTriggerEvaluation（315 行）

自动打牌对持续效果触发器的估值系数（coefficientPermil）与预计触发次数(count)。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ExamPlayType | 100% | ExamPlayType。 | "ExamPlayType_AutoPlay", "ExamPlayType_ManualPlayLesson" |
| `examStatusEnchantProduceExamTriggerId` | string | 100% | → ProduceExamTrigger。 | "e_trigger-exam_aggressive_up_interval-5…", "e_trigger-exam_buff_consume" |
| `coefficientPermil` | int32 | 97% | 系数。 | 330, 650 |
| `count` | int32 | 10% | 预计次数。 | 2, 0 |

外键（按 id 连接验证）：
- `examStatusEnchantProduceExamTriggerId` → **ProduceExamTrigger** (63/63 命中)

代表行：
```json
{"type": "ExamPlayType_AutoPlay", "examStatusEnchantProduceExamTriggerId": "e_trigger-exam_aggressive_up_interval-5-exam_card_play_aggressive", "coefficientPermil": 330, "count": 2}
{"type": "ExamPlayType_ManualPlayLessonHard", "examStatusEnchantProduceExamTriggerId": "e_trigger-exam_play_count_interval-3-p_card_search-target-effect_group-visible-exam_revie…", "coefficientPermil": 500}
```

### ProduceExamAutoPlayCardEvaluation（3066 行）

特定卡在剩余回合分档下的固定评价（-100000=不要打，1000000=必打）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceCardId` | string | 100% | → ProduceCard（注意 ProduceCard 主键是 (id, upgradeCount)）。 | "p_card-00-acc-0_002", "p_card-00-act-0_001" |
| `remainingTerm` | int32 | 100% | 剩余回合分档。 | 1, 2 |
| `evaluation` | int32 | 19% | 评价分：用于メモリー/编成强度评估（越高越强）。 | 0, -100000 |

外键（按 id 连接验证）：
- `produceCardId` → **ProduceCard** (438/438 命中)

代表行：
```json
{"produceCardId": "p_card-00-acc-0_002", "remainingTerm": 1}
{"produceCardId": "p_card-02-ido-2_021", "remainingTerm": 1}
```

### ProduceExamAutoPlayProduceCardEvaluation（840 行）

同上，按 ExamPlayType 区分。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ExamPlayType | 100% | ExamPlayType。 | "ExamPlayType_AutoPlay", "ExamPlayType_AutoPlayCompetition" |
| `produceCardId` | string | 100% | → ProduceCard（注意 ProduceCard 主键是 (id, upgradeCount)）。 | "p_card-00-sup-2_092", "p_card-00-sup-3_046" |
| `remainingTerm` | int32 | 100% | 分档。 | 4, 5 |
| `evaluation` | int32 | 100% | 评价分：用于メモリー/编成强度评估（越高越强）。 | -100000, 1000000 |

外键（按 id 连接验证）：
- `produceCardId` → **ProduceCard** (131/131 命中)

代表行：
```json
{"type": "ExamPlayType_AutoPlay", "produceCardId": "p_card-00-sup-2_092", "remainingTerm": 4, "evaluation": -100000}
{"type": "ExamPlayType_AutoPlay", "produceCardId": "p_card-02-ido-3_140", "remainingTerm": 4, "evaluation": -100000}
```

### ProduceExamAutoCardSelectEvaluation（210 行）

アノマリー(強気/全力)下自动选卡系数（LessonCoefficient / FullPowerPointCoefficient / FullPowerPointValue2Coefficient）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ExamPlayType | 100% | ExamPlayType。 | "ExamPlayType_AutoPlay", "ExamPlayType_ManualPlayLesson" |
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_ExamConcentration", "ProduceExamEffectType_ExamFullPower" |
| `remainingTerm` | int32 | 100% | 分档。 | 1, 2 |
| `evaluationType` | ProduceExamAutoCardSelectEvaluationType | 100% | ProduceExamAutoCardSelectEvaluationType。 | "ProduceExamAutoCardSelectEvaluationType…", "ProduceExamAutoCardSelectEvaluationType…" |
| `evaluation` | int32 | 86% | 评价分：用于メモリー/编成强度评估（越高越强）。 | 0, 1059 |

代表行：
```json
{"type": "ExamPlayType_AutoPlay", "examEffectType": "ProduceExamEffectType_ExamConcentration", "remainingTerm": 1, "evaluationType": "ProduceExamAutoCardSelectEvaluationType_LessonCoefficient"}
{"type": "ExamPlayType_ManualPlayLessonHard", "examEffectType": "ProduceExamEffectType_ExamFullPower", "remainingTerm": 1, "evaluationType": "ProduceExamAutoCardSelectEvaluationType_LessonCoefficient"}
```

### ProduceExamAutoResourceEvaluation（0 行）

空表。

### ProduceExamAutoGrowEffectEvaluation（3710 行）

アノマリー下各成长效果类型的估值。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ExamPlayType | 100% | ExamPlayType。 | "ExamPlayType_AutoPlay", "ExamPlayType_ManualPlayLesson" |
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_ExamConcentration", "ProduceExamEffectType_ExamFullPower" |
| `remainingTerm` | int32 | 100% | 分档。 | 1, 2 |
| `growEffectType` | ProduceCardGrowEffectType | 100% | ProduceCardGrowEffectType。 | "ProduceCardGrowEffectType_LessonAdd", "ProduceCardGrowEffectType_LessonReduce" |
| `evaluation` | int32 | 98% | 评价分：用于メモリー/编成强度评估（越高越强）。 | 0, 1 |
| `examStatusEnchantCoefficientPermil` | int32 | 98% | 系数。 | 0, 1 |

代表行：
```json
{"type": "ExamPlayType_AutoPlay", "examEffectType": "ProduceExamEffectType_ExamConcentration", "remainingTerm": 1, "growEffectType": "ProduceCardGrowEffectType_LessonAdd"}
{"type": "ExamPlayType_ManualPlayLessonHard", "examEffectType": "ProduceExamEffectType_ExamFullPower", "remainingTerm": 1, "growEffectType": "ProduceCardGrowEffectType_LessonAdd"}
```

## 10. H. 描述模板系统

### ProduceDescriptionExamEffect（88 行）

ProduceExamEffectType → 显示名(name)与说明标签的映射（88 种有 UI 名称的效果）：produceDescriptionLabelId=培育外说明，examProduceDescriptionLabelId=考试内说明（部分类型两者不同，如 集中 _Produce/_Exam）；mainBuffMinThresholds=主 buff 图标分级阈值（好調 [3,5]、集中/好印象/やる気/全力値 [5,10]）；noIcon/noReference=不显示图标/不可点击引用。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ProduceExamEffectType | 100% | ProduceExamEffectType。 | "ProduceExamEffectType_ExamLesson", "ProduceExamEffectType_ExamParameterBuff" |
| `name` | string | 100% | 显示名（日文）。 | "パラメータ", "好調" |
| `produceDescriptionSwapId` | string | 10% | → ProduceDescriptionSwap（レッスン/試験 用词替换）。 | "Swap_Label_ExamLesson", "Swap_Label_ExamCardUpgrade" |
| `produceDescriptionLabelId` | string | 100% | → ProduceDescriptionLabel。 | "Label_ExamLesson", "Label_ExamParameterBuff" |
| `examProduceDescriptionLabelId` | string | 100% | → ProduceDescriptionLabel。 | "Label_ExamLesson", "Label_ExamParameterBuff" |
| `mainBuffMinThresholds` | repeated int32 | 8% | 图标分级阈值。 | [3, 5], [5, 10] |
| `noIcon` | bool | 1% | 无图标。 | true, false |
| `noReference` | bool | 8% | 不可引用。 | true, false |

外键（按 id 连接验证）：
- `produceDescriptionSwapId` → **ProduceDescriptionSwap** (9/9 命中)
- `produceDescriptionLabelId` → **ProduceDescriptionLabel** (88/88 命中)
- `examProduceDescriptionLabelId` → **ProduceDescriptionLabel** (88/88 命中)

代表行：
```json
{"type": "ProduceExamEffectType_ExamLesson", "name": "パラメータ", "produceDescriptionSwapId": "Swap_Label_ExamLesson", "produceDescriptionLabelId": "Label_ExamLesson", "examProduceDescriptionLabelId": "Label_ExamLesson", "noIcon": true, "noReference": true}
{"type": "ProduceExamEffectType_ExamStaminaConsumptionDownAdd", "name": "消費体力減少効果増加", "produceDescriptionLabelId": "Label_ExamStaminaConsumptionDownAdd", "examProduceDescriptionLabelId": "Label_ExamStaminaConsumptionDownAdd"}
```

### ProduceDescriptionLabel（226 行）

术语/标签字典（226）：Label_*（效果/概念名 + 其说明片段）、Description_*（可复用的描述片段，如 Description_ProduceCardIsInitial）、Convert_*（受场景替换的词，如 レッスン↔試験・ステージ）。produceDescriptions 是该术语的说明文本（本身也是片段列表，可嵌套引用其他 Label）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "Convert_001", "Convert_002" |
| `name` | string | 99% | 显示名（日文）。 | "レッスン", "レッスンCLEARの" |
| `produceDescriptionSwapId` | string | 17% | 外键/引用 id（见 FK）。 | "Swap_Convert_001", "Swap_Convert_002" |
| `iconAssetId` | string | 1% | 图标（style-dot=项目符号）。 | "produce-card-move-effect-trigger", "style-dot" |
| `produceDescriptions` | repeated ProduceDescriptionSegment | 87% | 描述模板片段列表（结构见 §2），渲染后即游戏内效果文本。**这是效果语义最可靠的说明**。 | "(渲染) （回）", "(渲染) レッスン開始時手札に入る" |

外键（按 id 连接验证）：
- `produceDescriptionSwapId` → **ProduceDescriptionSwap** (39/39 命中)
- `produceDescriptions.targetId` → **ProduceDescriptionLabel** (7/7 命中)
- `produceDescriptions.produceDescriptionSwapId` → **ProduceDescriptionSwap** (11/11 命中)

代表行：
```json
{"id": "Convert_001", "name": "レッスン", "produceDescriptionSwapId": "Swap_Convert_001"}
{"id": "Label_ExamLessonFix", "name": "固定パラメータ", "produceDescriptionSwapId": "Swap_Label_ExamLessonFix", "produceDescriptions": "(渲染) 固定パラメータパラメータを増加させる"}
```

### ProduceDescriptionSwap（78 行）

场景替换词表：id × swapType(Lesson/Audition) → text。例如 Swap_Label_ExamLesson: Lesson=パラメータ / Audition=スコア；Swap_Convert_002: レッスン / 試験・ステージ。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "Swap_Convert_001", "Swap_Convert_002" |
| `swapType` | ProduceDescriptionSwapType | 100% | ProduceDescriptionSwapType。 | "ProduceDescriptionSwapType_Lesson", "ProduceDescriptionSwapType_Audition" |
| `text` | string | 100% | 替换后文本。 | "レッスン", "ターン" |

代表行：
```json
{"id": "Swap_Convert_001", "swapType": "ProduceDescriptionSwapType_Lesson", "text": "レッスン"}
{"id": "Swap_Label_ExamLessonValueMultipleDown", "swapType": "ProduceDescriptionSwapType_Audition", "text": "スコア上昇量減少"}
```

### ProduceDescriptionProduceCardGrowEffect（53 行）

ProduceCardGrowEffectType → 名称、说明标签、定制界面短文案（例：LessonAdd → パラメータ値増加 / パラメータ+）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ProduceCardGrowEffectType | 100% | ProduceCardGrowEffectType。 | "ProduceCardGrowEffectType_LessonAdd", "ProduceCardGrowEffectType_LessonReduce" |
| `name` | string | 100% | 显示名（日文）。 | "パラメータ値増加", "パラメータ値減少" |
| `noIcon` | bool | 0% | 。 | false |
| `noReference` | bool | 0% | 。 | false |
| `produceDescriptionLabelId` | string | 100% | 外键/引用 id（见 FK）。 | "Label_LessonAdd", "Label_LessonReduce" |
| `produceCardCustomizeDescription` | string | 100% | 定制界面短文案。 | "パラメータ+", "パラメータ-" |

外键（按 id 连接验证）：
- `produceDescriptionLabelId` → **ProduceDescriptionLabel** (53/53 命中)

代表行：
```json
{"type": "ProduceCardGrowEffectType_LessonAdd", "name": "パラメータ値増加", "produceDescriptionLabelId": "Label_LessonAdd", "produceCardCustomizeDescription": "パラメータ+"}
{"type": "ProduceCardGrowEffectType_StaminaConsumptionDownTurnAdd", "name": "消費体力減少値増加", "produceDescriptionLabelId": "Label_StaminaConsumptionDownTurnAdd", "produceCardCustomizeDescription": "消費体力減少+"}
```

### ProduceDescriptionProduceCardMovePosition（7 行）

ProduceCardMovePositionType → 位置名标签（山札の一番上 / 手札 / 除外…），Lost 额外有卡面用标签 レッスン中1回。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ProduceCardMovePositionType | 100% | ProduceCardMovePositionType。 | "ProduceCardMovePositionType_Hand", "ProduceCardMovePositionType_DeckFirst" |
| `produceDescriptionLabelId` | string | 100% | 外键/引用 id（见 FK）。 | "Label_ProduceCardPositionType_Hand", "Label_ProduceCardPositionType_DeckFirst" |
| `produceCardProduceDescriptionLabelId` | string | 14% | 卡面用标签。 | "Label_ProduceCardMovePositionType_Lost" |

外键（按 id 连接验证）：
- `produceDescriptionLabelId` → **ProduceDescriptionLabel** (7/7 命中)
- `produceCardProduceDescriptionLabelId` → **ProduceDescriptionLabel** (1/1 命中)

代表行：
```json
{"type": "ProduceCardMovePositionType_Hand", "produceDescriptionLabelId": "Label_ProduceCardPositionType_Hand"}
{"type": "ProduceCardMovePositionType_DeckRandom", "produceDescriptionLabelId": "Label_ProduceCardPositionType_DeckRandom"}
```

### ProduceDescriptionProduceEffect（92 行）

ProduceEffectType → 显示名（92），少数带说明标签。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ProduceEffectType | 100% | ProduceEffectType。 | "ProduceEffectType_VocalAddition", "ProduceEffectType_DanceAddition" |
| `name` | string | 100% | 显示名（日文）。 | "ボーカル上昇", "ダンス上昇" |
| `produceDescriptionLabelId` | string | 11% | 外键/引用 id（见 FK）。 | "Label_ProduceCardUpgrade", "Label_ProduceCardDuplicate" |

外键（按 id 连接验证）：
- `produceDescriptionLabelId` → **ProduceDescriptionLabel** (9/9 命中)

代表行：
```json
{"type": "ProduceEffectType_VocalAddition", "name": "ボーカル上昇"}
{"type": "ProduceEffectType_LessonVocalSpChangeRatePermilAddition", "name": "ボーカルSPレッスン発生率増加"}
```

### ProduceDescriptionProducePlan（4 行）

ProducePlanType → 名称/标签（共通、【センス専用】…）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ProducePlanType | 100% | ProducePlanType。 | "ProducePlanType_Common", "ProducePlanType_Plan1" |
| `name` | string | 100% | 显示名（日文）。 | "共通", "【センス専用】" |
| `produceDescriptionLabelId` | string | 100% | 外键/引用 id（见 FK）。 | "Label_ProducePlanType0", "Label_ProduceSkillPlanType1" |
| `planDetailProduceDescriptionLabelId` | string | 100% | 详细说明标签。 | "Label_ProducePlanType0", "Label_ProducePlanType1" |

外键（按 id 连接验证）：
- `produceDescriptionLabelId` → **ProduceDescriptionLabel** (4/4 命中)
- `planDetailProduceDescriptionLabelId` → **ProduceDescriptionLabel** (4/4 命中)

代表行：
```json
{"type": "ProducePlanType_Common", "name": "共通", "produceDescriptionLabelId": "Label_ProducePlanType0", "planDetailProduceDescriptionLabelId": "Label_ProducePlanType0"}
{"type": "ProducePlanType_Plan2", "name": "【ロジック専用】", "produceDescriptionLabelId": "Label_ProduceSkillPlanType2", "planDetailProduceDescriptionLabelId": "Label_ProducePlanType2"}
```

### ProduceDescriptionProduceStep（2 行）

ProduceStepType → 名称标签（学園活動、プレゼント）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `type` | ProduceStepType | 100% | ProduceStepType。 | "ProduceStepType_EventSchool", "ProduceStepType_Present" |
| `name` | string | 100% | 显示名（日文）。 | "学園活動", "プレゼント" |
| `produceDescriptionLabelId` | string | 100% | 外键/引用 id（见 FK）。 | "Label_ProduceStepType_EventSchool", "Label_ProduceStepType_Present" |

外键（按 id 连接验证）：
- `produceDescriptionLabelId` → **ProduceDescriptionLabel** (2/2 命中)

代表行：
```json
{"type": "ProduceStepType_EventSchool", "name": "学園活動", "produceDescriptionLabelId": "Label_ProduceStepType_EventSchool"}
{"type": "ProduceStepType_Present", "name": "プレゼント", "produceDescriptionLabelId": "Label_ProduceStepType_Present"}
```

### ProduceDescriptionProduceType（5 行）

ProduceType × ProduceSplitType → 专用标记文本模板（{Label_ProduceType_...}）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceType` | ProduceType | 100% | ProduceType：FirstStar=定期公演『初』 / NextIdolAudition=N.I.A / HatsuboshiIdolFestival=H.I.F。 | "ProduceType_FirstStar", "ProduceType_NextIdolAudition" |
| `produceSplitType` | ProduceSplitType | 100% | ProduceSplitType：H.I.F 把一次培育拆成 Selection(選抜試験, produce-007) 与 Final(本戦, produce-008) 两半；Unknown=不区分。 | "ProduceSplitType_Unknown", "ProduceSplitType_Selection" |
| `name` | string | 100% | 显示名（日文）。 | "初専用　", "N.I.A専用　" |
| `template` | string | 100% | 模板串。 | "{Label_ProduceType_FirstStar}", "{Label_ProduceType_NextIdolAudition}" |

代表行：
```json
{"produceType": "ProduceType_FirstStar", "name": "初専用　", "template": "{Label_ProduceType_FirstStar}"}
{"produceType": "ProduceType_HatsuboshiIdolFestival", "name": "H.I.F専用　", "template": "{Label_ProduceType_HatsuboshiIdolFestival}"}
```

## 11. I. 通用条件/消耗

### ConditionSet（5084 行）

通用条件集（5084 行 / 3725 个 id）：同一 id 多行按 number 排序，用 conditionOperatorType(And/Or) 组合；conditionType 决定 resourceId1/2 与 min/max 的含义（DearnessLevel / ProducerLevel / MainTaskCompleted / TimeTerm / ItemCount…）。培育相关：剧本解锁、卡牌转换、チャレンジ 角色解锁。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "cd_achieve-o_014", "cd_achieve-o_015" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `conditionOperatorType` | ConditionOperatorType | 100% | And/Or。 | "ConditionOperatorType_Or", "ConditionOperatorType_And" |
| `conditionType` | ConditionType | 100% | ConditionType。 | "ConditionType_MissionCompleted", "ConditionType_MainTaskCompleted" |
| `resourceId1` | string | 66% | 条件对象 1（多态，如 characterId/main task id）。 | "hidden_mission-achieve-o_014_001", "hidden_mission-achieve-o_014_002" |
| `resourceId2` | string | 4% | 条件对象 2。 | "produce_group-002", "shop_pack_item-0001" |
| `minMaxType` | ConditionMinMaxType | 100% | ConditionMinMaxType（Min/Max/MinMax/Unknown）。 | "ConditionMinMaxType_Unknown", "ConditionMinMaxType_Min" |
| `min` | int64 | 100% | 下限（字符串）。 | "1", "0" |
| `max` | int64 | 100% | 上限。 | "0", "1" |
| `beforeTime` | int64 | 100% | 时间上界(ms)。 | "0", "1722456000000" |
| `afterTime` | int64 | 100% | 时间下界(ms)。 | "0", "1738353599000" |
| `description` | string | 17% | 说明文（日文）。 | "順次実装予定", "5/26以降に挑戦可能" |

代表行：
```json
{"id": "cd_achieve-o_014", "number": 1, "conditionOperatorType": "ConditionOperatorType_Or", "conditionType": "ConditionType_MissionCompleted", "resourceId1": "hidden_mission-achieve-o_014_001", "min": "1", "max": "0", "beforeTime": "0", "afterTime": "0"}
{"id": "cd-dearness-top_motion_hume_dearness_level-10-20", "number": 1, "conditionOperatorType": "ConditionOperatorType_And", "conditionType": "ConditionType_DearnessLevel", "resourceId1": "hume", "minMaxType": "ConditionMinMaxType_MinMax", "min": "10", "max": "20", "beforeTime": "0", "afterTime": "0"}
```

### ConsumptionSet（814 行）

消耗集（突破/プリマステラ 等）：id 多行 → resourceType/resourceId/quantity。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "cs-idol_card_level_limit-r-plan1-vi-da-1", "cs-idol_card_level_limit-r-plan1-vi-da-2" |
| `number` | int32 | 100% | 组内序号。 | 1, 2 |
| `resourceType` | ResourceType | 100% | ResourceType/ProduceResourceType 枚举。 | "ResourceType_Item", "ResourceType_JewelPaidOnly" |
| `resourceId` | string | 99% | 资源 id，按 resourceType 多态指向 Item/ProduceCard/ProduceItem/ProduceDrink/...。 | "item-limitovermaterial-1", "item-money" |
| `quantity` | int32 | 100% | 数量。 | 120, 2000 |

外键（按 id 连接验证）：
- `resourceId` → **Item** (25/25 命中)

代表行：
```json
{"id": "cs-idol_card_level_limit-r-plan1-vi-da-1", "number": 1, "resourceType": "ResourceType_Item", "resourceId": "item-limitovermaterial-1", "quantity": 120}
{"id": "cs-idol_card_level_limit-sr-plan3-vi-da-5", "number": 6, "resourceType": "ResourceType_Item", "resourceId": "item-money", "quantity": 60000}
```

## 12. J. 其他相关（备注级）

### PvpRateConfig（51 行）

コンテスト(PvpRate) 赛季配置：三维基准、评分曲线、3 个 stage（回合数、P道具、gimmick 组）。复用考试引擎（AutoPlayCompetition）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "pvp_rate_config-1", "pvp_rate_config-10" |
| `description` | string | 100% | 说明文（日文）。 | "初めてのコンテスト", "S10" |
| `vocal` | int32 | 82% | 赛季基准 Vocal。 | 353, 446 |
| `dance` | int32 | 82% | 。 | 238, 356 |
| `visual` | int32 | 82% | 。 | 291, 89 |
| `examSettingId` | string | 100% | 外键/引用 id（见 FK）。 | "p_exam_setting-1" |
| `produceExamBattleScoreConfigId` | string | 82% | 外键/引用 id（见 FK）。 | "p_exam_battle_score_config-contest-seas…", "p_exam_battle_score_config-contest-seas…" |
| `examBattleFirstRankBonusPermil` | int32 | 100% | 第一名分数加成千分比（200）。 | 200 |
| `pvpRateCommonProduceCardId` | string | 100% | 外键/引用 id（见 FK）。 | "pvp_live_battle_1" |
| `winTimelineAssetId` | string | 100% | 演出。 | "tln_cont_vovi-001_totalresult_win", "tln_cont_voda-001_totalresult_win" |
| `loseTimelineAssetId` | string | 100% | 演出。 | "tln_cont_vovi-001_totalresult_lose", "tln_cont_voda-001_totalresult_lose" |
| `startTimelineInitialTimePermil` | int32 | 100% | 演出时间参数。 | 5033 |
| `topAssetId` | string | 100% | UI。 | "contest-top-vovi", "contest-top-voda" |
| `stages` | repeated Stage | 100% | 阶段列表。 | [{"stageType": "PvpRateStageType__1", "planType": "ProducePlanType_Common", "turn": 12, "produceItemId": "pitem_00-0-004-0-000", "produceItemIds": ["pitem_00-0-004-0-000"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_vovi-001_start", "examTimelineAssetId": "tln_cont_vovi-001_battle", "vocal": 353, "dance": 238, "visual": 291, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-seas…"}, {"stageType": "PvpRateStageType__2", "planType": "ProducePlanType_Plan1", "turn": 8, "produceItemId": "pitem_01-0-005-0-000", "produceItemIds": ["pitem_01-0-005-0-000"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_vovi-001_start", "examTimelineAssetId": "tln_cont_vovi-001_battle", "vocal": 353, "dance": 238, "visual": 291, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-seas…"}, {"stageType": "PvpRateStageType__3", "planType": "ProducePlanType_Plan2", "turn": 8, "produceItemId": "pitem_02-0-002-0-000", "produceItemIds": ["pitem_02-0-002-0-000"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_vovi-001_start", "examTimelineAssetId": "tln_cont_vovi-001_battle", "vocal": 353, "dance": 238, "visual": 291, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-seas…"}], [{"stageType": "PvpRateStageType__1", "planType": "ProducePlanType_Common", "turn": 10, "produceItemId": "pitem_00-0-004-0-006", "produceItemIds": ["pitem_00-0-004-0-006"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_voda-001_start", "examTimelineAssetId": "tln_cont_voda-001_battle", "vocal": 446, "dance": 356, "visual": 89, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-seas…"}, {"stageType": "PvpRateStageType__2", "planType": "ProducePlanType_Plan1", "turn": 12, "produceItemId": "pitem_01-0-005-0-006", "produceItemIds": ["pitem_01-0-005-0-006"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_voda-001_start", "examTimelineAssetId": "tln_cont_voda-001_battle", "vocal": 446, "dance": 356, "visual": 89, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-seas…"}, {"stageType": "PvpRateStageType__3", "planType": "ProducePlanType_Plan2", "turn": 8, "produceItemId": "pitem_02-0-006-0-007", "produceItemIds": ["pitem_02-0-006-0-007"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_voda-001_start", "examTimelineAssetId": "tln_cont_voda-001_battle", "vocal": 446, "dance": 356, "visual": 89, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-seas…"}] |
| &nbsp;&nbsp;↳ `stageType` | PvpRateStageType | 100% | PvpRateStageType（_1/_2/_3）。 | "PvpRateStageType__1", "PvpRateStageType__2" |
| &nbsp;&nbsp;↳ `planType` | ProducePlanType | 100% | 该阶段プラン。 | "ProducePlanType_Common", "ProducePlanType_Plan1" |
| &nbsp;&nbsp;↳ `turn` | int32 | 100% | 回合数。 | 12, 8 |
| &nbsp;&nbsp;↳ `produceItemId` | string | 82% | → ProduceItem 阶段道具。 | "pitem_00-0-004-0-000", "pitem_01-0-005-0-000" |
| &nbsp;&nbsp;↳ `produceItemIds` | repeated string | 100% | → ProduceItem。 | ["pitem_00-0-004-0-000"], ["pitem_01-0-005-0-000"] |
| &nbsp;&nbsp;↳ `produceExamGimmickEffectGroupId` | string | 12% | → ProduceExamGimmickEffectGroup。 | "p_exam_gimmick-contest-season_017-stage3", "p_exam_gimmick-contest-season_019-stage3" |
| &nbsp;&nbsp;↳ `bgmAssetId` | string | 100% | BGM。 | "sud_bgm_produce_audition-04" |
| &nbsp;&nbsp;↳ `startTimelineAssetId` | string | 100% | 演出。 | "tln_cont_vovi-001_start", "tln_cont_voda-001_start" |
| &nbsp;&nbsp;↳ `examTimelineAssetId` | string | 100% | 演出。 | "tln_cont_vovi-001_battle", "tln_cont_voda-001_battle" |
| &nbsp;&nbsp;↳ `vocal` | int32 | 100% | 阶段基准 Vocal。 | 353, 446 |
| &nbsp;&nbsp;↳ `dance` | int32 | 100% | 。 | 238, 356 |
| &nbsp;&nbsp;↳ `visual` | int32 | 100% | 。 | 291, 89 |
| &nbsp;&nbsp;↳ `produceExamBattleScoreConfigId` | string | 100% | → ProduceExamBattleScoreConfig。 | "p_exam_battle_score_config-contest-seas…", "p_exam_battle_score_config-contest-seas…" |

外键（按 id 连接验证）：
- `examSettingId` → **ExamSetting** (1/1 命中)
- `produceExamBattleScoreConfigId` → **ProduceExamBattleScoreConfig** (42/42 命中)
- `pvpRateCommonProduceCardId` → **PvpRateCommonProduceCard** (1/1 命中)
- `winTimelineAssetId` → AssetDownload? (3/7 = 43%，多态或部分引用)
- `loseTimelineAssetId` → AssetDownload? (3/7 = 43%，多态或部分引用)
- `stages.produceItemId` → **ProduceItem** (124/124 命中)
- `stages.produceItemIds` → **ProduceItem** (151/151 命中)
- `stages.produceExamGimmickEffectGroupId` → **ProduceExamGimmickEffectGroup** (17/17 命中)
- `stages.startTimelineAssetId` → AssetDownload? (3/7 = 43%，多态或部分引用)
- `stages.examTimelineAssetId` → AssetDownload? (3/7 = 43%，多态或部分引用)
- `stages.produceExamBattleScoreConfigId` → **ProduceExamBattleScoreConfig** (69/69 命中)

代表行：
```json
{"id": "pvp_rate_config-1", "description": "初めてのコンテスト", "vocal": 353, "dance": 238, "visual": 291, "examSettingId": "p_exam_setting-1", "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-season_001", "examBattleFirstRankBonusPermil": 200, "pvpRateCommonProduceCardId": "pvp_live_battle_1", "winTimelineAssetId": "tln_cont_vovi-001_totalresult_win", "loseTimelineAssetId": "tln_cont_vovi-001_totalresult_lose", "startTimelineInitialTimePermil": 5033, "topAssetId": "contest-top-vovi", "stages": [{"stageType": "PvpRateStageType__1", "planType": "ProducePlanType_Common", "turn": 12, "produceItemId": "pitem_00-0-004-0-000", "produceItemIds": ["pitem_00-0-004-0-000"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_vovi-001_start", "examTimelineAssetId": "tln_cont_vovi-001_battle", "vocal": 353, "dance": 238, "visual": 291, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-season_001"}, {"stageType": "PvpRateStageType__2", "planType": "ProducePlanType_Plan1", "turn": 8, "produceItemId": "pitem_01-0-005-0-000", "produceItemIds": ["pitem_01-0-005-0-000"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_vovi-001_start", "examTimelineAssetId": "tln_cont_vovi-001_battle", "vocal": 353, "dance": 238, "visual": 291, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-season_001"}, {"stageType": "PvpRateStageType__3", "planType": "ProducePlanType_Plan2", "turn": 8, "produceItemId": "pitem_02-0-002-0-000", "produceItemIds": ["pitem_02-0-002-0-000"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_vovi-001_start", "examTimelineAssetId": "tln_cont_vovi-001_battle", "vocal": 353, "dance": 238, "visual": 291, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-season_001"}]}
{"id": "pvp_rate_config-32", "description": "S32", "vocal": 178, "dance": 356, "visual": 356, "examSettingId": "p_exam_setting-1", "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-season_032", "examBattleFirstRankBonusPermil": 200, "pvpRateCommonProduceCardId": "pvp_live_battle_1", "winTimelineAssetId": "tln_cont_davi-001_totalresult_win", "loseTimelineAssetId": "tln_cont_davi-001_totalresult_lose", "startTimelineInitialTimePermil": 5033, "topAssetId": "contest-top-davi", "stages": [{"stageType": "PvpRateStageType__1", "planType": "ProducePlanType_Plan1", "turn": 12, "produceItemId": "pitem_01-0-005-0-015", "produceItemIds": ["pitem_01-0-005-0-015"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_davi-001_start", "examTimelineAssetId": "tln_cont_davi-001_battle", "vocal": 178, "dance": 356, "visual": 356, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-season_032"}, {"stageType": "PvpRateStageType__2", "planType": "ProducePlanType_Plan2", "turn": 8, "produceItemId": "pitem_02-0-002-0-011", "produceItemIds": ["pitem_02-0-002-0-011"], "produceExamGimmickEffectGroupId": "p_exam_gimmick-contest-season_032-stage2", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_davi-001_start", "examTimelineAssetId": "tln_cont_davi-001_battle", "vocal": 178, "dance": 356, "visual": 356, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-season_032"}, {"stageType": "PvpRateStageType__3", "planType": "ProducePlanType_Plan3", "turn": 10, "produceItemId": "pitem_03-0-003-0-008", "produceItemIds": ["pitem_03-0-003-0-008"], "produceExamGimmickEffectGroupId": "", "bgmAssetId": "sud_bgm_produce_audition-04", "startTimelineAssetId": "tln_cont_davi-001_start", "examTimelineAssetId": "tln_cont_davi-001_battle", "vocal": 178, "dance": 356, "visual": 356, "produceExamBattleScoreConfigId": "p_exam_battle_score_config-contest-season_032"}]}
```

### Tower（13 行）

（备注）“アイドルへの道”塔模式表头；TowerLayer/TowerLayerExam/TowerLayerRank 为空表，塔层数据不在 dump 中（ProduceItem 的 pitem_tower_* 与 ProduceExamStatusEnchant tower* 是其道具）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "tower_001-amao", "tower_001-atbm" |
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `title` | string | 100% | 标题。 | "有村麻央のアイドルへの道", "雨夜燕のアイドルへの道" |
| `viewConditionSetId` | string | 38% | → ConditionSet，显示条件。 | "cd_time_25_1226-1100", "cd_time_25_0616-1100" |
| `unlockConditionSetId` | string | 100% | → ConditionSet，解锁条件。 | "cd_tower_open_amao", "cd_tower_open_atbm" |
| `achievementId` | string | 100% | 外键/引用 id（见 FK）。 | "achieve-p_idol-amao-015", "achieve-p_idol-atbm-015" |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 10010, 10007 |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `viewConditionSetId` → **ConditionSet** (4/4 命中)
- `unlockConditionSetId` → **ConditionSet** (13/13 命中)
- `achievementId` → **Achievement** (13/13 命中)

代表行：
```json
{"id": "tower_001-amao", "characterId": "amao", "title": "有村麻央のアイドルへの道", "unlockConditionSetId": "cd_tower_open_amao", "achievementId": "achieve-p_idol-amao-015", "order": 10010}
{"id": "tower_001-hume", "characterId": "hume", "title": "花海佑芽のアイドルへの道", "viewConditionSetId": "cd_time_24_0813-1100", "unlockConditionSetId": "cd_tower_open_hume", "achievementId": "achieve-p_idol-hume-015", "order": 10080}
```

### CompetitionExamStatusEffectIcon（6 行）

コンテスト状态图标顺序（planType × ExamStatusEffectType）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `planType` | ProducePlanType | 100% | ProducePlanType：Common=全プラン通用 / Plan1=センス / Plan2=ロジック / Plan3=アノマリー。 | "ProducePlanType_Plan1", "ProducePlanType_Plan2" |
| `examStatusEffectType` | ExamStatusEffectType | 100% | ExamStatusEffectType。 | "ExamStatusEffectType_ParameterBuff", "ExamStatusEffectType_LessonBuff" |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 2, 1 |

代表行：
```json
{"planType": "ProducePlanType_Plan1", "examStatusEffectType": "ExamStatusEffectType_ParameterBuff", "order": 2}
{"planType": "ProducePlanType_Plan2", "examStatusEffectType": "ExamStatusEffectType_Review", "order": 2}
```

### ProduceGuide（302 行）

（备注）新手推荐卡组指南（偶像卡 × P等级 → 分类组）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `idolCardId` | string | 100% | → IdolCard。 | "i_card-amao-1-000", "i_card-amao-1-001" |
| `producerLevel` | int32 | 100% | 适用 P 等级（20/35）。 | 20, 35 |
| `produceGuideProduceCardCategoryGroupId` | string | 100% | → ProduceGuideProduceCardCategoryGroup。 | "ParameterBuff_group_20", "ParameterBuff_group_35" |
| `produceGuideProduceCardSampleDeckCategoryGroupId` | string | 100% | → ProduceGuideProduceCardSampleDeckCategoryGroup。 | "ParameterBuff_group_20", "ParameterBuff_group_35" |

外键（按 id 连接验证）：
- `idolCardId` → **IdolCard** (151/151 命中)
- `produceGuideProduceCardCategoryGroupId` → **ProduceGuideProduceCardCategoryGroup** (16/16 命中)
- `produceGuideProduceCardSampleDeckCategoryGroupId` → **ProduceGuideProduceCardCategoryGroup** (16/16 命中)

代表行：
```json
{"idolCardId": "i_card-amao-1-000", "producerLevel": 20, "produceGuideProduceCardCategoryGroupId": "ParameterBuff_group_20", "produceGuideProduceCardSampleDeckCategoryGroupId": "ParameterBuff_group_20"}
{"idolCardId": "i_card-hume-3-017", "producerLevel": 35, "produceGuideProduceCardCategoryGroupId": "CardPlayAggressive_group_35", "produceGuideProduceCardSampleDeckCategoryGroupId": "CardPlayAggressive_group_35"}
```

### ProduceStory（3341 行）

培育中剧情条目（3341）：类型 Character/CharacterGrowth/IdolCard/SupportCard/Step*Event；produceEventHintProduceConditionDescriptions 是“事件出现条件”的人读提示。仅备注。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_story_002_amao_after-audition-a-norma…", "p_story_002_amao_after-audition-a-norma…" |
| `type` | ProduceStoryType | 100% | ProduceStoryType。 | "ProduceStoryType_Character", "ProduceStoryType_CharacterGrowth" |
| `title` | string | 100% | 标题。 | "まだまだここから！", "まだまだこれから" |
| `advAssetId` | string | 100% | ADV。 | "adv_pstory_002_amao_after-audition-a-no…", "adv_pstory_002_amao_after-audition-a-no…" |
| `produceEventHintProduceConditionDescriptions` | repeated string | 11% | 触发条件提示文本。 | ["１次オーディションで「メロBang!」を選択し合格する"], ["２次オーディションで「GALAXYミュージック」を選択し合格する"] |
| `viewConditionSetId` | string | 0% | → ConditionSet，显示条件。 | "cd_close" |
| `unlockConditionSetId` | string | 0% | → ConditionSet，解锁条件。 |  |
| `isBusinessExcellent` | bool | 9% | 营业(Business)事件的“大成功”版本标记。 | false, true |
| `order` | int32 | 100% | 客户端排序键（字符串或整数，纯展示用）。 | 39, 38 |

外键（按 id 连接验证）：
- `viewConditionSetId` → **ConditionSet** (1/1 命中)

代表行：
```json
{"id": "p_story_002_amao_after-audition-a-normal-02", "type": "ProduceStoryType_Character", "title": "まだまだここから！", "advAssetId": "adv_pstory_002_amao_after-audition-a-normal-02", "produceEventHintProduceConditionDescriptions": ["１次オーディションで「メロBang!」を選択し合格する"], "order": 39}
{"id": "p_story-event-002_jsna_business-1-5", "title": "試飲販売", "advAssetId": "adv_pevent_002_jsna_sales_1-005-01", "order": 5}
```

### ProduceStoryGroup（1856 行）

剧情组 → 角色 → 具体剧情 的映射（同一组每个角色一条）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `id` | string | 100% | 主键。绝大多数表的 id 本身就是“可读的编码”（见各表说明），很多语义只在 id 里出现。 | "p_story-001-after-audition-final-failur…", "p_story-001-after-audition-final-normal…" |
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `produceStoryId` | string | 100% | → ProduceStory。 | "p_story-001-amao-after-audition-final-f…", "p_story-001-atbm-after-audition-final-f…" |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `produceStoryId` → **ProduceStory** (1856/1856 命中)

代表行：
```json
{"id": "p_story-001-after-audition-final-failure-01", "characterId": "amao", "produceStoryId": "p_story-001-amao-after-audition-final-failure-01"}
{"id": "p_story-event-002_business-1-4-2", "characterId": "hski", "produceStoryId": "p_story-event-002_hski_business-1-4-2"}
```

### ProduceAdv（32 行）

（备注）『初』/N.I.A 的固定剧情 ADV（试炼前夜、结果等）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceType` | ProduceType | 100% | ProduceType：FirstStar=定期公演『初』 / NextIdolAudition=N.I.A / HatsuboshiIdolFestival=H.I.F。 | "ProduceType_FirstStar", "ProduceType_NextIdolAudition" |
| `type` | ProduceAdvType | 100% | ProduceAdvType。 | "ProduceAdvType_BeforeFinalLessonHard", "ProduceAdvType_BeforeMid1LessonHard" |
| `title` | string | 100% | 标题。 | "追い込みレッスン開始！", "最終試験前日" |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "adv_pstory_001_cmmn_before-hard-final-n…", "adv_pstory_001_cmmn_before-hard-mid-nor…" |

代表行：
```json
{"produceType": "ProduceType_FirstStar", "type": "ProduceAdvType_BeforeFinalLessonHard", "title": "追い込みレッスン開始！", "assetId": "adv_pstory_001_cmmn_before-hard-final-normal-01"}
{"produceType": "ProduceType_NextIdolAudition", "type": "ProduceAdvType_BeforeMid2LessonHard", "title": "追い込みレッスン開始！", "assetId": "adv_pstory_001_cmmn_before-hard-mid-normal-01"}
```

### ProduceSplitAdv（24 行）

（备注）H.I.F 的固定剧情 ADV，按 Selection/Final 与目标角色分。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `produceType` | ProduceType | 100% | ProduceType：FirstStar=定期公演『初』 / NextIdolAudition=N.I.A / HatsuboshiIdolFestival=H.I.F。 | "ProduceType_HatsuboshiIdolFestival" |
| `type` | ProduceAdvType | 100% | ProduceAdvType。 | "ProduceAdvType_BeforeFinalAuditionRefre…", "ProduceAdvType_BeforeMid1AuditionRefresh" |
| `produceSplitTypes` | ProduceSplitType | 100% | 适用的 ProduceSplitType。 | "ProduceSplitType_Selection", "ProduceSplitType_Final" |
| `targetCharacterId` | string | 17% | → Character。 | "hski", "kllj" |
| `title` | string | 100% | 标题。 | "第3回『選抜試験』前", "『本戦』ラウンド2前" |
| `assetId` | string | 100% | 美术/预制体资源 id（非外键；AssetDownload 里只登记了一部分）。 | "adv_produce-refresh_003_selection_03", "adv_produce-refresh_003_final_02" |

外键（按 id 连接验证）：
- `targetCharacterId` → **Character** (3/3 命中)

代表行：
```json
{"produceType": "ProduceType_HatsuboshiIdolFestival", "type": "ProduceAdvType_BeforeFinalAuditionRefresh", "produceSplitTypes": "ProduceSplitType_Selection", "title": "第3回『選抜試験』前", "assetId": "adv_produce-refresh_003_selection_03"}
{"produceType": "ProduceType_HatsuboshiIdolFestival", "type": "ProduceAdvType_ProduceResultTrueEnd", "produceSplitTypes": "ProduceSplitType_Final", "title": "『H.I.F』本戦の結果は……", "assetId": "adv_presult_003_final-true"}
```

### ProduceGroupLiveCommon（101 行）

（备注）各剧本系列通用 Live 的资源。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `characterId` | string | 100% | → Character（4 字母缩写，如 amao=有村麻央、hski=花海咲季）。 | "amao", "atbm" |
| `produceGroupId` | string | 100% | → ProduceGroup（剧本系列：初 / N.I.A / H.I.F）。 | "produce_group-001", "produce_group-002" |
| `type` | ProduceLiveType | 100% | ProduceLiveType。 | "ProduceLiveType_TrueEnd", "ProduceLiveType_A" |
| `musicId` | string | 100% | → Music。 | "music-all-amao-001", "music-all-amao-002" |
| `needForceLiveCommonIdolCard` | bool | 13% | 需要指定形象卡。 | false, true |
| `unlockConditionSetId` | string | 2% | → ConditionSet，解锁条件。 | "cd_time_25_0630-1100" |
| `thumbnailAssetId` | string | 100% | 外键/引用 id（见 FK）。 | "img_general_live_music-all-amao-001_tru…", "img_general_live_music-all-amao-001_a" |
| `environmentAssetId` | string | 100% | 外键/引用 id（见 FK）。 | "env_3d_live_all001-00-noon", "env_3d_live_courtyard-00-00-noon" |
| `timelineAssetId` | string | 100% | 外键/引用 id（见 FK）。 | "tln_live_all-001", "tln_live_cmmn_all-001-normal-001" |
| `motionAssetIds` | repeated string | 61% | 外键/引用 id（见 FK）。 | ["mot_live_chr_amao_all-001_00_in"], ["mot_live_chr_amao_all-001-amao-normal-0…"] |
| `liveMusicAssetId` | string | 61% | 外键/引用 id（见 FK）。 | "sud_music_live_all-001-amao_true-001", "sud_music_live_all-001-amao_normal-001" |
| `beforeAdvAssetId` | string | 51% | 外键/引用 id（见 FK）。 | "adv_live_amao_001_start-01-01", "adv_live_amao_001_start-02-01" |
| `afterAdvAssetId` | string | 51% | 外键/引用 id（见 FK）。 | "adv_live_amao_001_end-01-01", "adv_live_amao_001_end-02-01" |
| `liveOverrideAssetId` | string | 0% | 外键/引用 id（见 FK）。 |  |
| `additionalActorAssetIds` | repeated string | 0% | 外键/引用 id（见 FK）。 |  |

外键（按 id 连接验证）：
- `characterId` → **Character** (13/13 命中)
- `produceGroupId` → **ProduceGroup** (3/3 命中)
- `musicId` → **Music** (36/36 命中)
- `unlockConditionSetId` → **ConditionSet** (1/1 命中)
- `environmentAssetId` → AssetDownload? (3/8 = 38%，多态或部分引用)
- `timelineAssetId` → AssetDownload? (4/44 = 9%，多态或部分引用)
- `motionAssetIds` → AssetDownload? (3/62 = 5%，多态或部分引用)
- `liveMusicAssetId` → AssetDownload? (3/62 = 5%，多态或部分引用)

代表行：
```json
{"characterId": "amao", "produceGroupId": "produce_group-001", "type": "ProduceLiveType_TrueEnd", "musicId": "music-all-amao-001", "thumbnailAssetId": "img_general_live_music-all-amao-001_true-end", "environmentAssetId": "env_3d_live_all001-00-noon", "timelineAssetId": "tln_live_all-001", "motionAssetIds": ["mot_live_chr_amao_all-001_00_in"], "liveMusicAssetId": "sud_music_live_all-001-amao_true-001"}
{"characterId": "hume", "produceGroupId": "produce_group-001", "type": "ProduceLiveType_D", "musicId": "music-all-hume-001", "thumbnailAssetId": "img_general_live_music-all-hume-001_d", "environmentAssetId": "env_3d_lesson_danceroom-00-00-noon", "timelineAssetId": "tln_live_hume_all-001-normal-004", "beforeAdvAssetId": "adv_live_hume_001_start-04-01", "afterAdvAssetId": "adv_live_hume_001_end-04-01"}
```

### SeminarExamTransition（12 行）

（备注）試験研修/基礎研修 教学考试列表（仅 produce-001）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `examEffectType` | ProduceExamEffectType | 100% | ProduceExamEffectType；在“按プラン/主 buff 分流”的表里表示 6 大流派之一（ExamParameterBuff=好調系 / ExamLessonBuff=集中系 / ExamReview=好印象系 / ExamCardPlayAggressive=やる気系 / ExamConcentration=強気(アノマリー) / ExamFullPower=全力(アノマリー)）。 | "ProduceExamEffectType_ExamParameterBuff", "ProduceExamEffectType_ExamLessonBuff" |
| `isLessonInt` | int32 | 50% | 1=课程型研修。 | 0, 1 |
| `description` | string | 100% | 说明文（日文）。 | "目標値に少し届きませんでしたね。好調は、パラメ\nータの上昇量をあげる効果があり…", "目標値に少し届きませんでしたね。好調は、パラメ\nータの上昇量をあげる効果があり…" |
| `seminarExamGroupId` | string | 100% | 研修组 id（不在 dump 中）。 | "seminar_gruop-03", "seminar_gruop-01" |
| `seminarExamId` | string | 100% | 研修 id（不在 dump 中）。 | "seminar_gruop-03_01", "seminar_gruop-01_01" |
| `seminarExamGroupName` | string | 100% | 研修组名。 | "試験研修", "基礎研修" |
| `seminarExamName` | string | 100% | 研修名。 | "【試験研修１】好調", "【基礎１】好調" |
| `produceIds` | repeated string | 100% | 外键/引用 id（见 FK）。 | ["produce-001"] |
| `rewards` | repeated Reward | 100% | 奖励。 | [{"resourceType": "ResourceType_JewelTotal", "resourceId": "", "quantity": 50}] |
| &nbsp;&nbsp;↳ `resourceType` | ResourceType | 100% | 。 | "ResourceType_JewelTotal" |
| &nbsp;&nbsp;↳ `resourceId` | string | 0% | 。 |  |
| &nbsp;&nbsp;↳ `quantity` | int32 | 100% | 。 | 50 |

外键（按 id 连接验证）：
- `produceIds` → **Produce** (1/1 命中)

代表行：
```json
{"examEffectType": "ProduceExamEffectType_ExamParameterBuff", "description": "目標値に少し届きませんでしたね。好調は、パラメ\nータの上昇量をあげる効果があります。試験研修で\n上手に使うコツを学んでみましょう！", "seminarExamGroupId": "seminar_gruop-03", "seminarExamId": "seminar_gruop-03_01", "seminarExamGroupName": "試験研修", "seminarExamName": "【試験研修１】好調", "produceIds": ["produce-001"], "rewards": [{"resourceType": "ResourceType_JewelTotal", "resourceId": "", "quantity": 50}]}
{"examEffectType": "ProduceExamEffectType_ExamCardPlayAggressive", "description": "目標値に少し届きませんでしたね。やる気は、値の\n分だけ元気の増加値をあげる効果があります。試験\n研修で上手に使うコツを学んでみましょう！", "seminarExamGroupId": "seminar_gruop-03", "seminarExamId": "seminar_gruop-03_04", "seminarExamGroupName": "試験研修", "seminarExamName": "【試験研修４】やる気", "produceIds": ["produce-001"], "rewards": [{"resourceType": "ResourceType_JewelTotal", "resourceId": "", "quantity": 50}]}
```

### TutorialProduce（3 行）

（备注）新手教程培育设定（3 个初始偶像）。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `tutorialType` | TutorialType | 100% | TutorialType。 | "TutorialType_GameStart" |
| `idolCardId` | string | 100% | → IdolCard。 | "i_card-fktn-1-000", "i_card-hski-1-000" |
| `produceCardIds` | repeated string | 100% | → ProduceCard 列表（可重复表示多张）。 | ["p_card-02-act-1_027", "p_card-00-act-0_001", "p_card-00-act-0_002", "p_card-02-men-1_030", "p_card-00-men-0_003", "…(+4)"], ["p_card-01-act-1_001", "p_card-00-act-0_001", "p_card-00-act-0_002", "p_card-01-act-1_019", "p_card-00-men-0_003", "…(+4)"] |
| `examSettingId` | string | 100% | 外键/引用 id（见 FK）。 | "p_exam_setting-1" |
| `produceSettingId` | string | 100% | 外键/引用 id（见 FK）。 | "p_setting-1" |
| `idolCardParameterGrowthLimit` | int32 | 100% | 参数上限 1200。 | 1200 |
| `produceNavigationNormalId` | string | 100% | 外键/引用 id（见 FK）。 | "p_navi-produce_group-001-tutorial" |
| `produceNavigationAuditionId` | string | 100% | 外键/引用 id（见 FK）。 | "p_navi-produce_group-001-tutorial-audit…" |
| `musicId` | string | 100% | → Music。 | "music-all-fktn-001", "music-all-hski-001" |
| `environmentAssetId` | string | 100% | 外键/引用 id（见 FK）。 | "env_3d_live_schoolgarden-00-00-noon" |
| `timelineAssetId` | string | 100% | 外键/引用 id（见 FK）。 | "tln_live_fktn_all-001-normal-003", "tln_live_hski_all-001-normal-003" |
| `memoryGiftId` | string | 100% | → MemoryGift。 | "memory_gift-fktn", "memory_gift-hski" |

外键（按 id 连接验证）：
- `idolCardId` → **IdolCard** (3/3 命中)
- `produceCardIds` → **ProduceCard** (12/12 命中)
- `examSettingId` → **ExamSetting** (1/1 命中)
- `produceSettingId` → **ProduceSetting** (1/1 命中)
- `produceNavigationNormalId` → **ProduceNavigation** (1/1 命中)
- `produceNavigationAuditionId` → **ProduceNavigation** (1/1 命中)
- `musicId` → **Music** (3/3 命中)
- `environmentAssetId` → **AssetDownload** (1/1 命中)
- `timelineAssetId` → **AssetDownload** (3/3 命中)
- `memoryGiftId` → **MemoryGift** (3/3 命中)

代表行：
```json
{"tutorialType": "TutorialType_GameStart", "idolCardId": "i_card-fktn-1-000", "produceCardIds": ["p_card-02-act-1_027", "p_card-00-act-0_001", "p_card-00-act-0_002", "p_card-02-men-1_030", "p_card-00-men-0_003", "…(+4)"], "examSettingId": "p_exam_setting-1", "produceSettingId": "p_setting-1", "idolCardParameterGrowthLimit": 1200, "produceNavigationNormalId": "p_navi-produce_group-001-tutorial", "produceNavigationAuditionId": "p_navi-produce_group-001-tutorial-audition", "musicId": "music-all-fktn-001", "environmentAssetId": "env_3d_live_schoolgarden-00-00-noon", "timelineAssetId": "tln_live_fktn_all-001-normal-003", "memoryGiftId": "memory_gift-fktn"}
{"tutorialType": "TutorialType_GameStart", "idolCardId": "i_card-hski-1-000", "produceCardIds": ["p_card-01-act-1_001", "p_card-00-act-0_001", "p_card-00-act-0_002", "p_card-01-act-1_019", "p_card-00-men-0_003", "…(+4)"], "examSettingId": "p_exam_setting-1", "produceSettingId": "p_setting-1", "idolCardParameterGrowthLimit": 1200, "produceNavigationNormalId": "p_navi-produce_group-001-tutorial", "produceNavigationAuditionId": "p_navi-produce_group-001-tutorial-audition", "musicId": "music-all-hski-001", "environmentAssetId": "env_3d_live_schoolgarden-00-00-noon", "timelineAssetId": "tln_live_hski_all-001-normal-003", "memoryGiftId": "memory_gift-hski"}
```

### TutorialProduceStep（12 行）

（备注）教程周程脚本。

| 字段 | proto 类型 | 非空率 | 含义 | 示例值 |
|---|---|---|---|---|
| `tutorialType` | TutorialType | 100% | TutorialType。 | "TutorialType_GameStart" |
| `idolCardId` | string | 100% | → IdolCard。 | "i_card-fktn-1-000", "i_card-hski-1-000" |
| `stepNumber` | int32 | 100% | 周序号。 | 1, 2 |
| `tutorialStep` | int32 | 100% | 教程步骤号。 | 5, 8 |
| `stepType` | ProduceStepType | 100% | ProduceStepType（周程类型：LessonXxx / AuditionMid1/Mid2/Final / EventXxx / Present / Refresh / OpenLesson / SelfLesson ...）。 | "ProduceStepType_LessonVisualNormal", "ProduceStepType_LessonDanceNormal" |
| `name` | string | 100% | 显示名（日文）。 | "ビジュアルレッスン", "ダンスレッスン" |
| `produceStepRefresh` | bool | 25% | 是否休息。 | false, true |
| `produceStepLessonId` | string | 50% | → ProduceStepLesson。 | "p_step_lesson_level-001-tutorial-fktn-0…", "p_step_lesson_level-001-tutorial-fktn-0…" |
| `progressLevel` | int32 | 50% | 进度等级。 | 1, 0 |
| `produceNavigationNumber` | int32 | 75% | 导航台词序号。 | 3, 2 |
| `rankThreshold` | int32 | 25% | 合格名次。 | 0, 3 |
| `parameterBaseLine` | int32 | 25% | 参数基准。 | 0, 100 |
| `baseScore` | int32 | 25% | 基础分。 | 0, 200 |
| `forceEndScore` | int32 | 0% | 强制结束分。 | 0 |
| `produceExamBattleNpcGroupId` | string | 25% | → ProduceExamBattleNpcGroup。 | "p_npc_group-tutorial-fktn", "p_npc_group-tutorial-hski" |
| `produceExamBattleConfigId` | string | 25% | → ProduceExamBattleConfig。 | "p_exam_battle_config-tutorial_fktn", "p_exam_battle_config-tutorial_hski" |
| `produceExamGimmickEffectGroupId` | string | 0% | → ProduceExamGimmickEffectGroup。 |  |

外键（按 id 连接验证）：
- `idolCardId` → **IdolCard** (3/3 命中)
- `produceStepLessonId` → **ProduceStepLesson** (6/6 命中)
- `produceExamBattleNpcGroupId` → **ProduceExamBattleNpcGroup** (3/3 命中)
- `produceExamBattleConfigId` → **ProduceExamBattleConfig** (3/3 命中)

代表行：
```json
{"tutorialType": "TutorialType_GameStart", "idolCardId": "i_card-fktn-1-000", "stepNumber": 1, "tutorialStep": 5, "stepType": "ProduceStepType_LessonVisualNormal", "name": "ビジュアルレッスン", "produceStepLessonId": "p_step_lesson_level-001-tutorial-fktn-001", "progressLevel": 1, "produceNavigationNumber": 3}
{"tutorialType": "TutorialType_GameStart", "idolCardId": "i_card-hski-1-000", "stepNumber": 3, "tutorialStep": 10, "stepType": "ProduceStepType_Refresh", "name": "休む", "produceStepRefresh": true, "produceNavigationNumber": 4}
```

## 13. 关键关系链（供建模）

以下关系全部经 id 连接验证（命中率见各表“外键”小节）。

**剧本 → 数值设定**

- `ProduceGroup.produceIds` → `Produce`；`Produce.produceSettingId` → `ProduceSetting`；`Produce.examSettingId` → `ExamSetting`（唯一）。
- `ProduceGrade.produceGroupId`、`ProduceInitialDeck.produceId` → `ExamInitialDeck.produceCardIds` → `ProduceCard`。
- `ProduceStepAuditionDifficulty(id=IdolCard.produceStepAuditionDifficultyId, produceId, stepType, number)` → `ProduceExamBattleConfig` → `ProduceExamBattleScoreConfig`；→ `ProduceExamBattleNpcGroup` → `ProduceExamBattleNpcMob`；→ `ProduceExamGimmickEffectGroup` → `ProduceExamEffect`。
- `ProduceStepLesson.produceStepLessonLevelId` → `ProduceStepLessonLevel`。

**偶像 → 培育起点**

- `IdolCard` → `ProduceCard`(produceCardId / secondProduceCardId)、`ProduceItem`(before/afterProduceItemId)、`ExamInitialDeck`、`ProduceStepAuditionDifficulty`、`IdolCardPotential(+ProduceSkill)`、`IdolCardLevelLimit(+ProduceSkill/+StatusUp)`、`IdolCardPrimaStellaProduceSkill` → `ProduceSkill`。
- `Character` → `IdolCard`、`SupportCard`、`CharacterTrueEndBonus`；`CharacterDearnessLevel.produceSkills[].id` → `ProduceSkill(p_dearness_skill)`。
- `SupportCard` → `SupportCardProduceSkillLevel{Vocal,Dance,Visual,Assist}` → `ProduceSkill(p_support_skill)`；`SupportCard.produceStoryIds` → `ProduceStory`；`ProduceEventSupportCard` → `ProduceStepEventDetail`。
- `MemoryAbility.skillId` → `ProduceSkill(p_memory_skill)`。

**培育外循环效果**

- `ProduceSkill.produceTriggerId1` → `ProduceTrigger`；`.produceEffectId1` → `ProduceEffect`。
- `ProduceItem.skills[].produceItemEffectId` → `ProduceItemEffect` → (`ProduceEffect` | `ProduceExamStatusEnchant`)；`ProduceItem.produceTriggerId` → `ProduceTrigger`。
- `ProduceCustomizeItem.produceEffectIds` → `ProduceEffect`；`ProduceCustomizeItemRelationship` 父子边。
- `ProduceStepEventDetail.produceEffectIds` / `.produceStepEventSuggestionIds` → `ProduceStepEventSuggestion.produceEffectIds|successProduceEffectIds|failProduceEffectIds` → `ProduceEffect`。
- `ProduceGrowthPanel.produceEffectIds` → `ProduceEffect`。
- `ProduceEffect.produceExamStatusEnchantId` → `ProduceExamStatusEnchant`；`.produceCardSearchId` → `ProduceCardSearch`；`.produceRewards[].resourceId` → `ProduceCard|ProduceDrink|ProduceItem`。

**考试内效果**

- `ProduceCard.playEffects[].produceExamEffectId` → `ProduceExamEffect`；`.playEffects[].produceExamTriggerId` / `.playProduceExamTriggerId` → `ProduceExamTrigger`；`.moveProduceExamEffectIds` → `ProduceExamEffect`；`.produceCardStatusEnchantId` → `ProduceCardStatusEnchant`；`.produceCardCustomizeIds` → `ProduceCardCustomize` → `ProduceCardGrowEffect`。
- `ProduceExamEffect.produceExamStatusEnchantId` → `ProduceExamStatusEnchant` → (`ProduceExamTrigger`, `ProduceExamEffect[]`)（可递归）。
- `ProduceExamEffect.chainProduceExamEffectId(s)` → `ProduceExamEffect`（ExamEffectTimer 延迟目标）；`.produceCardGrowEffectIds` → `ProduceCardGrowEffect`；`.produceCardSearchId` → `ProduceCardSearch`；`.targetProduceCardId` → `ProduceCard`。
- `ProduceExamTrigger.produceCardSearchId` / `.fieldStatusProduceCardSearchIds` → `ProduceCardSearch`。
- `ProduceCardStatusEnchant.produceExamTriggerId` → `ProduceExamTrigger`；`.produceCardGrowEffectIds` → `ProduceCardGrowEffect`；`ProduceCardGrowEffect.playProduceExamEffectId` → `ProduceExamEffect`、`.produceCardStatusEnchantId` → `ProduceCardStatusEnchant`、`.playProduceExamTriggerId` → `ProduceExamTrigger`。
- `ProduceCardSearch.produceCardIds` → `ProduceCard`；`.produceCardRandomPoolId|produceCardPoolId` → `ProduceCardPool`（=`ProduceCardRandomPool.id`）；`.effectGroupIds` → `EffectGroup`；`.cardSearchTag` → `ProduceCardTag`。
- `ProduceDrink.produceDrinkEffectIds` → `ProduceDrinkEffect.produceExamEffectId` → `ProduceExamEffect`。
- `ProduceExamAutoTriggerEvaluation.examStatusEnchantProduceExamTriggerId` → `ProduceExamTrigger`；`ProduceExamAutoPlay(Produce)CardEvaluation.produceCardId` → `ProduceCard`。

**描述模板**

- `ProduceDescriptionExamEffect.type`(ProduceExamEffectType) → `produceDescriptionLabelId`/`examProduceDescriptionLabelId` → `ProduceDescriptionLabel` → `produceDescriptionSwapId` → `ProduceDescriptionSwap`。
- 任意行的 `produceDescriptions[].targetId` → `ProduceDescriptionLabel`(Label_/Description_/Convert_) 或 `ProduceCard`/`ProduceItem`；`[].originProduceExamEffectId|originProduceExamTriggerId|originProduceCardStatusEnchantId` 回指来源行。

**条件**

- `Produce/ProduceGroup/ProduceCharacter/ProduceChallengeCharacter/ProduceCardConversion.*ConditionSetId` → `ConditionSet`（DearnessLevel / MainTaskCompleted / ProducerLevel / TimeTerm…）。
- `IdolCardLevelLimit.consumptionSetId`、`IdolCard.primaStellaConsumptionSetId` → `ConsumptionSet` → `Item`。

## 14. 未详述但与培育/考试相关的其他表

- **CharacterActorLookEffector**（1 行）：字段 characterId, jointLimitAssetId
- **CharacterAdv**（25 行）：字段 characterId, name, regexp, notIdol
- **CharacterColor**（27 行）：字段 characterId, mainColor, gradientColor1, gradientColor2, textColor, labelTextColor, transitionGradientColor1, transitionGradientColor2, decorationMainGradientColor1, decorationMainGradientColor2
- **CharacterDearnessStoryGashaCampaign**（0 行）：字段 
- **CharacterDetail**（181 行）：字段 characterId, type, content, order
- **CharacterProduceStory**（39 行）：字段 characterId, produceGroupId, eventCharacterProduceStoryIds, eventCharacterGrowthProduceStoryIds, eventCampaignProduceStoryIds, eventActivityProduceStoryIds, eventSchoolProduceStoryIds, eventBusinessProduceStoryIds
- **CharacterPushMessage**（169 行）：字段 characterId, type, number, title, message
- **CharacterTrueEndAchievement**（36 行）：字段 characterId, produceType, targetAchievements
- **CompetitionSeason**（0 行）：字段 
- **CompetitionStageSectionLock**（24 行）：字段 grade, stageType, sectionTypes
- **ExamMotion**（2213 行）：字段 characterId, type, motionType, number, facialMotionId, bodyMotionId, voiceAssetId, sceneLayoutId, cameraId, targetIds, targetStepTypes
- **ExamOutGameMotion**（780 行）：字段 characterId, type, motionType, number, facialAssetIds, bodyAssetIds, voiceAssetId, sceneLayoutId, cameraId
- **ExamUnitMotion**（6 行）：字段 produceCharacterUnitId, unitCharacterId, motionType, number, bodyMotionId, facialMotionId, targetIds, targetStepTypes
- **GvgRaid**（1 行）：字段 id, name, titleAssetId, bannerAssetId, storyGroupId, examSettingId, order
- **GvgRaidStageLoop**（0 行）：字段 
- **IdolCardPiece**（151 行）：字段 idolCardId, itemId, releaseConsumptionQuantity
- **IdolCardPieceQuantity**（3 行）：字段 rarity, quantity
- **IdolCardSkin**（291 行）：字段 id, idolCardId, name, assetId, costumeHeadId, costumeId, musicId, idolCardSsrAnimationStartMilliseconds, additionalCostumeHeadIds, additionalCostumeIds, homeVoiceGroupId, detailVoiceGroupId, beforeLevelLimitRankVoiceAssetId, afterLevelLimitRankVoiceAssetId, produceSelectVoiceAssetId, produceSelectFa
- **IdolCardSkinSelectReward**（12 行）：字段 id, idolCardSkinId, movieAssetId, difficultyType, order
- **IdolCardSkinUnit**（5 行）：字段 id, idolCardSkinIds, unitCharacters, liveOrderCharacterIds
- **MemoryExchangeItem**（3 行）：字段 planType, itemId
- **MemoryExchangeItemQuantity**（18 行）：字段 grade, quantity
- **MemoryTag**（24 行）：字段 id, defaultName, assetId, order
- **PhotoLookTargetVoiceCharacter**（13 行）：字段 characterId, number, voiceAssetId
- **PhotoWaitVoiceCharacter**（65 行）：字段 characterId, number, voiceAssetId
- **ProduceCardSimulation**（0 行）：字段 
- **ProduceCardSimulationGroup**（0 行）：字段 
- **ProduceCharacterAdv**（10 行）：字段 produceType, type, characterId, title, assetId
- **ProduceGuideProduceCardCategory**（67 行）：字段 id, label, produceCardCount, effectGroupIds, produceCardIds
- **ProduceGuideProduceCardCategoryGroup**（16 行）：字段 id, description, produceGuideProduceCardCategoryIds
- **ProduceGuideProduceCardSampleDeckCategory**（65 行）：字段 id, label, produceCardIds
- **ProduceGuideProduceCardSampleDeckCategoryGroup**（16 行）：字段 id, produceGuideProduceCardSampleDeckCategoryIds
- **ProduceItemSimulation**（0 行）：字段 
- **ProduceItemSimulationGroup**（0 行）：字段 
- **ProduceResultMotion**（314 行）：字段 characterId, liveType, number, motionAssetId, facialAssetId, voiceAssetId, produceGroupIds, produceIds
- **ProduceScheduleBackground**（15 行）：字段 locationType, backgroundAssetId, sceneLayoutId, monitorMovieId, produceGroupIds
- **ProduceScheduleMotion**（1066 行）：字段 characterId, locationType, staminaMotionType, motionType, number, facialAssetIds, bodyAssetIds, voiceAssetId
- **ProduceStartMotion**（39 行）：字段 characterId, motionType, number, motionAssetId, facialAssetId, voiceAssetId
- **ProduceStepAuditionCharacterBgm**（44 行）：字段 characterId, produceId, stepType, bgmAssetId
- **ProduceStepAuditionCharacterUnitMotion**（66 行）：字段 produceCharacterUnitId, characterId, targetCharacterId, stepType, motionType, number, facialAssetId, bodyAssetId, voiceAssetId, produceIds, motionSeAssetId, motionSeStartMilliseconds
- **ProduceStepAuditionMotion**（866 行）：字段 characterId, stepType, motionType, number, facialAssetId, bodyAssetId, voiceAssetId, sceneLayoutId, cameraId, produceGroupIds, auditionType, produceIds, motionSeAssetId, motionSeStartMilliseconds
- **ProduceStepAuditionRivalActor**（10 行）：字段 id, produceCharacterId, stepType, number, actorAssetIds, produceIds
- **ProduceStepAuditionRivalActorMotion**（2 行）：字段 rivalActorId, motionType, number, bodyAssetId, facialAssetId
- **ProduceStepOpenLessonMotion**（424 行）：字段 characterId, stepType, number, advId, voiceAssetId1, voiceAssetId2, seAssetId, bgmAssetId
- **ProduceStepSelfLessonMotion**（416 行）：字段 characterId, stepType, number, motionAssetId, voiceAssetId, bgmAssetId, sceneLayoutId, cameraId, propAssetIds, disableLipSync
- **ProduceWeekMotion**（230 行）：字段 characterId, number, costumeHeadId, costumeId, advAssetId, voiceAssetId, produceIds, enableOpenLesson
- **ProducerLevel**（80 行）：字段 level, totalExp, unlockTargets, bonusRewards
- **ProducerRanking**（4 行）：字段 id, name, characterIds, hasCharacterRankingReward, hasOverallRankingReward, producerRankingRankGradeId, producerRankingProduceId, producerRankingTowerId, startTime, endTime, fixRankTime
- **ProducerRankingCharacter**（13 行）：字段 characterId, characterTopPositionX, characterTopPositionY
- **ProducerRankingProduce**（12 行）：字段 id, produceId
- **ProducerRankingRankGrade**（24 行）：字段 id, upperLimitRank, grade
- **ProducerRankingTower**（51 行）：字段 id, towerId, layerNumbers
- **PvpRateMotion**（52 行）：字段 characterId, motionType, number, facialAssetId, bodyAssetId, voiceAssetId, sceneLayoutId, cameraId
- **PvpRateUnitSlotUnlock**（8 行）：字段 grade, slotCountPerStage
- **ResearchMemoryRerollCost**（55 行）：字段 lockCount, rerollCount, quantity
- **SupportCardFlavor**（562 行）：字段 supportCardId, number, characterIds, text, voiceAssetId
- **SupportCardSimulation**（0 行）：字段 
- **SupportCardSimulationGroup**（0 行）：字段 
- **Tour**（4 行）：字段 id, name, titleAssetId, bannerAssetId, storyGroupId, examSettingId, tourStageTimelineId, tourMotionId, aprilFoolAssetIds, order
- **TourMotion**（28 行）：字段 id, characterId, number, facialAssetId, bodyAssetId, voiceAssetId, sceneLayoutId, cameraId
- **TourStageTimeline**（12 行）：字段 id, stageNumber, startTimelineAssetId, examTimelineAssetId, resultTimelineAssetId, examBgmAssetId, timelineBackgroundAssetId, liveOverrideAssetId
- **TowerLayer**（0 行）：字段 
- **TowerLayerExam**（0 行）：字段 
- **TowerLayerRank**（0 行）：字段 
- **TowerReset**（1700 行）：字段 towerId, layerNumber, number
- **TowerTotalClearRankReward**（97 行）：字段 rank, isFeature
- **TutorialCharacterVoice**（21 行）：字段 characterId, type, number, assetId

