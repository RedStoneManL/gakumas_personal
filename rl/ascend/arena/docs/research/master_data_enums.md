# 学マス master data 枚举全集（Master Data Enums）

> 数据源：`gakumasu-diff` dump（commit `5b8969e`）+ `penum.proto`（枚举定义全集，含 dump 中尚未使用的值）。
> 生成：`tools/masterdata/build_docs.py`（统计来自 `inspect_dump.py`；中文语义注释在 `atlas_annotations_more.py::ENUM_NOTES`）。
> 计数口径：值在整个 dump 中出现的次数（包含嵌套的 `produceDescriptions[]` 片段字段，因此 `ProduceExamEffectType_ExamLesson` 之类的计数远大于 ProduceExamEffect 的行数）。§2.1 另给出 **ProduceExamEffect 表内按 effectType 的行数**。
> 标记：**(dump 中无)** = proto 定义了但当前 dump 没有任何行使用；**(不在 proto 中)** = dump 里出现但 proto 未定义（通常是被枚举正则误判的 id 片段，如 `Convert_*`、`CardPlayAggressive_group_20`）。

## 0. 速查：实现考试引擎需要的枚举

| 枚举 | 用途 | 详解位置 |
|---|---|---|
| ProduceExamEffectType | 原子效果类型（ProduceExamEffect.effectType）；138 个定义值，dump 使用 107 个 | §2.1 |
| ProduceExamPhaseType | 触发时机（ProduceExamTrigger.phaseTypes） | §2.2 |
| ProduceExamFieldStatusType / ProduceExamTriggerCheckType | 场上状态条件 / 取反 | §2.2 |
| ProduceCardPositionType / ProduceCardOrderType / ProducePickRangeType / ProducePickCountType | 卡牌筛选与选取 | §3 |
| ProduceCardMovePositionType / ProduceCardMoveEffectTriggerType | 卡去向 / 移动时效果 | §3 |
| ExamCostType | 非体力费用 | §3 |
| ProduceCardGrowEffectType | 成长/定制效果 | §3 |
| ProduceEffectType / ProducePhaseType | 培育外循环效果与时机 | §2.3, §3 |
| ExamDescriptionType / ProduceDescriptionType | 描述模板片段 | §3 |
| ProduceExamAutoEvaluationType / ExamPlayType | 官方自动打牌权重 | §3 |

## 1. 枚举总览（penum.proto 全部 214 个枚举）

| 枚举 | proto 值数 | dump 出现值数 | dump 总出现次数 | 主要字段 |
|---|---|---|---|---|
| AchievementCategory | 4 | 3 | 1206 | Achievement.category |
| AntiCheatFeatureType | 8 | 0 | 0 |  |
| AppReviewType | 5 | 2 | 2 | AppReview.type |
| AssetCopyRuleGroup | 5 | 0 | 0 |  |
| AssetCopyRuleType | 5 | 0 | 0 |  |
| AssetDownloadType | 3 | 2 | 3967 | AssetDownload.type |
| AssetKind | 3 | 0 | 0 |  |
| AuthProviderType | 3 | 0 | 0 |  |
| BadgeGrade | 11 | 5 | 273 | Badge.grade |
| BadgeType | 2 | 1 | 273 | Badge.type |
| CharacterDetailType | 15 | 14 | 181 | CharacterDetail.type |
| CharacterPersonalityType | 5 | 5 | 24 | Character.personalityType |
| CoinGashaBoxResetTypeType | 4 | 0 | 0 |  |
| CoinGashaType | 4 | 0 | 0 |  |
| CompetitionGrade | 9 | 8 | 24 | CompetitionStageSectionLock.grade |
| CompetitionPhaseType | 5 | 0 | 0 |  |
| CompetitionSeasonStatusType | 5 | 0 | 0 |  |
| CompetitionStageSectionType | 4 | 1 | 12 | CompetitionStageSectionLock.sectionTypes |
| CompetitionStageType | 4 | 3 | 24 | CompetitionStageSectionLock.stageType |
| ConditionMinMaxType | 4 | 4 | 5364 | ConditionSet.minMaxType; ProduceCardSearch.staminaMinMaxType |
| ConditionOperatorType | 3 | 2 | 5084 | ConditionSet.conditionOperatorType |
| ConditionType | 77 | 44 | 5084 | ConditionSet.conditionType |
| ConsentAgreementType | 4 | 0 | 0 |  |
| ConsentType | 6 | 0 | 0 |  |
| CostumeFeatureType | 5 | 4 | 38 | Costume.invalidCostumeFeatureTypes |
| CostumeMotionType | 5 | 4 | 98 | CostumeMotion.motionType |
| CostumeSetType | 5 | 0 | 0 |  |
| CountType | 20 | 0 | 0 |  |
| DearnessMotionType | 10 | 5 | 3972 | DearnessMotion.motionType |
| DeckRecommendType | 5 | 0 | 0 |  |
| ErrorCode | 68 | 0 | 0 |  |
| EventStoryFilterType | 5 | 5 | 96 | StoryGroup.eventStoryFilterType |
| EventType | 13 | 12 | 12 | EventLabel.eventType |
| ExamActionType | 5 | 0 | 0 |  |
| ExamAiModelType | 3 | 0 | 0 |  |
| ExamCommandType | 17 | 0 | 0 |  |
| ExamCostType | 7 | 7 | 2447 | ProduceCard.costType; ProduceCardGrowEffect.costType; ProduceCardSearch.costType |
| ExamDescriptionType | 22 | 19 | 351294 | ProduceCard.produceDescriptions; ProduceCard.produceDescriptions.examDescriptionType; ProduceExamStatusEnchant.produceDescriptions |
| ExamGameType | 7 | 0 | 0 |  |
| ExamIdolStatusType | 5 | 0 | 0 |  |
| ExamMotionTargetType | 10 | 9 | 2993 | ExamMotion.type; ExamOutGameMotion.type |
| ExamMotionType | 9 | 8 | 2219 | ExamMotion.motionType; ExamUnitMotion.motionType |
| ExamOutGameMotionType | 7 | 6 | 780 | ExamOutGameMotion.motionType |
| ExamPhaseType | 8 | 0 | 0 |  |
| ExamPlayType | 6 | 5 | 16205 | ProduceExamAutoEvaluation.type; ProduceExamAutoGrowEffectEvaluation.type; ProduceExamAutoPlayProduceCardEvaluation.type |
| ExamStatusEffectType | 73 | 6 | 6 | CompetitionExamStatusEffectIcon.examStatusEffectType |
| ExchangeItemCategoryType | 5 | 4 | 6 | ExchangeItemCategory.categoryType |
| ExchangeItemResetCheckStatus | 3 | 0 | 0 |  |
| ExchangeType | 4 | 4 | 352 | Item.exchangeType |
| FeatureMaintenanceType | 26 | 0 | 0 |  |
| FourPanelComicSeries | 3 | 2 | 222 | Media.fourPanelComicSeries |
| FriendStatusType | 5 | 0 | 0 |  |
| GashaAnimationRarity | 5 | 4 | 143 | GashaAnimationStep.rarity |
| GashaAnimationStepType | 12 | 9 | 286 | GashaAnimationStep.currentStepType; GashaAnimationStep.nextStepType |
| GashaButtonAppealType | 6 | 5 | 309 | GashaButton.appealType; GashaButton.highAppealType; GashaButton.bottomAppealType |
| GashaButtonType | 3 | 2 | 103 | GashaButton.type |
| GashaCardBonusType | 6 | 0 | 0 |  |
| GashaContinuousStepType | 5 | 0 | 0 |  |
| GashaLimitType | 6 | 5 | 206 | GashaButton.limitType; GashaButton.discountLimitType |
| GashaType | 5 | 0 | 0 |  |
| GiftFilterType | 8 | 0 | 0 |  |
| GuildActivityPolicyType | 7 | 0 | 0 |  |
| GuildJoinRequestRouteType | 4 | 0 | 0 |  |
| GuildJoinType | 3 | 0 | 0 |  |
| GuildMissionPhaseType | 5 | 0 | 0 |  |
| GuildNotificationType | 3 | 0 | 0 |  |
| GuildRoleType | 4 | 0 | 0 |  |
| GuildSearchMemberCountRangeType | 4 | 0 | 0 |  |
| GvgRaidStageIconSizeType | 4 | 0 | 0 |  |
| HomeLocationType | 6 | 5 | 1789 | HomeMotion.locationType |
| HomeMotionType | 9 | 8 | 1789 | HomeMotion.motionType |
| HomeTimeType | 5 | 4 | 4 | HomeTime.type |
| HomeType | 5 | 0 | 0 |  |
| IdolCardDifficultyType | 4 | 3 | 12 | IdolCardSkinSelectReward.difficultyType |
| IdolCardLevelLimitEffectType | 7 | 5 | 42 | IdolCardLevelLimitStatusUp.effectTypes |
| IdolCardLevelLimitRank | 10 | 7 | 404 | IdolCardLevelLimit.rank; IdolCard.maxIdolCardLevelLimitRank; IdolCardLevelLimitProduceSkill.rank |
| IdolCardPotentialEffectType | 5 | 4 | 755 | IdolCardPotential.effectTypes |
| IdolCardPotentialRank | 5 | 4 | 854 | IdolCardPotential.rank; IdolCardPotentialProduceSkill.rank |
| IdolCardRarity | 4 | 4 | 506 | Item.idolCardRarity; IdolCard.rarity; IdolCardPieceQuantity.rarity |
| IdolSkillPossessionType | 4 | 0 | 0 |  |
| ItemRarity | 5 | 4 | 352 | Item.rarity |
| ItemType | 24 | 24 | 381 | Item.type; LimitItem.type; ExchangeItemCategory.itemType |
| LangType | 4 | 0 | 0 |  |
| LinkType | 42 | 0 | 0 |  |
| LoginBonusType | 4 | 0 | 0 |  |
| MainTaskType | 6 | 2 | 4 | MainTaskGroup.mainTaskType |
| MediaMovieType | 3 | 3 | 211 | Media.mediaMovieType |
| MediaType | 6 | 4 | 222 | Media.mediaType |
| MeishiBaseAssetType | 5 | 4 | 299 | MeishiBaseAsset.meishiBaseAssetType |
| MeishiIllustrationType | 8 | 7 | 699 | MeishiIllustrationAsset.type |
| MeishiObjectType | 19 | 0 | 0 |  |
| MissionCategory | 8 | 7 | 3367 | Mission.category |
| MissionType | 127 | 126 | 4997 | Mission.type; Achievement.missionType; MainTask.missionType |
| MusicType | 4 | 3 | 416 | Music.type |
| MusicWishListRequesterType | 4 | 0 | 0 |  |
| NoticeCategory | 4 | 0 | 0 |  |
| NoticeType | 9 | 0 | 0 |  |
| PaymentPendingReceiptDialogTimingType | 2 | 0 | 0 |  |
| PhotoBackgroundCategory | 5 | 3 | 8 | PhotoBackground.category |
| PhotoBackgroundTimeType | 5 | 3 | 10 | PhotoBackground.timeTypes |
| PhotoButtonExecuteType | 4 | 0 | 0 |  |
| PhotoLookTargetType | 4 | 2 | 1040 | PhotoPose.lookTargetType |
| PhotoPoseMotionType | 3 | 2 | 1040 | PhotoPose.motionType |
| PlatformType | 6 | 4 | 27 | Rule.platformType; ForceAppVersion.platformType |
| PreferenceType | 4 | 0 | 0 |  |
| ProduceAdvType | 20 | 19 | 66 | ProduceAdv.type; ProduceSplitAdv.type; ProduceCharacterAdv.type |
| ProduceCampaignType | 9 | 0 | 0 |  |
| ProduceCardCategory | 4 | 4 | 353032 | ProduceCard.produceDescriptions; ProduceCard.produceDescriptions.produceCardCategory; ProduceExamStatusEnchant.produceDescriptions |
| ProduceCardGrowEffectType | 54 | 54 | 355853 | ProduceCard.produceDescriptions; ProduceCard.produceDescriptions.produceCardGrowEffectType; ProduceExamStatusEnchant.produceDescriptions |
| ProduceCardMoveEffectTriggerType | 6 | 3 | 1714 | ProduceCard.moveEffectTriggerType |
| ProduceCardMovePositionType | 8 | 8 | 356214 | ProduceCard.produceDescriptions; ProduceCard.produceDescriptions.produceCardMovePositionType; ProduceExamStatusEnchant.produceDescriptions |
| ProduceCardOrderType | 4 | 3 | 280 | ProduceCardSearch.orderType |
| ProduceCardPositionType | 15 | 10 | 280 | ProduceCardSearch.cardPositionType |
| ProduceCardRarity | 6 | 5 | 1750 | ProduceCard.rarity; ProduceCardSearch.cardRarities; ProduceCardCustomizeRarityEvaluation.rarity |
| ProduceCardSearchStatusType | 6 | 1 | 280 | ProduceCardSearch.cardStatusType |
| ProduceConditionType | 76 | 0 | 0 |  |
| ProduceDescriptionSwapType | 4 | 2 | 78 | ProduceDescriptionSwap.swapType |
| ProduceDescriptionType | 24 | 12 | 351294 | ProduceCard.produceDescriptions; ProduceCard.produceDescriptions.produceDescriptionType; ProduceExamStatusEnchant.produceDescriptions |
| ProduceDisplayType | 3 | 0 | 0 |  |
| ProduceDrinkRarity | 5 | 3 | 29 | ProduceDrink.rarity |
| ProduceEffectType | 119 | 103 | 2523 | ProduceEffect.produceEffectType; SupportCardProduceSkillFilter.produceEffectTypes; ProduceEffectIcon.type |
| ProduceEventCharacterType | 15 | 15 | 6888 | ProduceStepEventDetail.eventCharacterType |
| ProduceEventSuggestionType | 3 | 1 | 6888 | ProduceStepEventDetail.suggestionType |
| ProduceEventType | 8 | 8 | 6888 | ProduceStepEventDetail.eventType |
| ProduceExamAutoCardSelectEvaluationType | 4 | 3 | 210 | ProduceExamAutoCardSelectEvaluation.evaluationType |
| ProduceExamAutoEvaluationType | 54 | 53 | 11130 | ProduceExamAutoEvaluation.evaluationType |
| ProduceExamEffectType | 169 | 138 | 371454 | ProduceCard.produceDescriptions; ProduceCard.produceDescriptions.examEffectType; ProduceExamStatusEnchant.produceDescriptions |
| ProduceExamFieldStatusType | 42 | 29 | 4125 | ProduceExamGimmickEffectGroup.fieldStatusType; ProduceExamTrigger.fieldStatusTypes |
| ProduceExamPhaseType | 57 | 30 | 676 | ProduceExamTrigger.phaseTypes |
| ProduceExamResultType | 4 | 0 | 0 |  |
| ProduceExamTriggerCheckType | 2 | 2 | 3744 | ProduceExamGimmickEffectGroup.fieldStatusCheckType; ProduceExamTrigger.fieldStatusCheckTypes |
| ProduceHighScoreEventType | 3 | 2 | 19 | ProduceHighScore.produceHighScoreEventType |
| ProduceItemEffectType | 3 | 2 | 1111 | ProduceItemEffect.effectType; ProduceCustomizeItem.effectType |
| ProduceItemRarity | 5 | 4 | 1038 | ProduceItem.rarity |
| ProduceLiveType | 7 | 7 | 1144 | ProduceLiveEvaluation.liveType; ProduceLive.type; ProduceResultMotion.liveType |
| ProduceMemoryProduceCardPhaseType | 3 | 2 | 21 | MemoryGift.produceCardPhaseType |
| ProduceParameterType | 4 | 4 | 249 | SupportCard.produceCardUpgradeLessonParameterType; ProduceStepOpenLesson.subParameterType |
| ProducePhaseType | 44 | 29 | 176 | ProduceTrigger.phaseType |
| ProducePickCountType | 4 | 2 | 4140 | ProduceExamEffect.pickCountType; ProduceExamEffect.pickCountType2 |
| ProducePickRangeType | 4 | 4 | 6254 | ProduceEffect.pickRangeType; ProduceExamEffect.pickRangeType; ProduceExamEffect.pickRangeType2 |
| ProducePlanType | 5 | 5 | 5424 | ProduceCard.planType; ProduceSkill.planType; ProduceItem.planType |
| ProduceProgressAuditionStatusType | 5 | 0 | 0 |  |
| ProduceProgressConditionType | 12 | 0 | 0 |  |
| ProduceProgressStatus | 28 | 0 | 0 |  |
| ProduceResourceOriginType | 15 | 0 | 0 |  |
| ProduceResourceType | 18 | 6 | 2626 | ProduceEffect.produceResourceType; ProduceEffect.produceRewards; ProduceEffect.produceRewards.resourceType |
| ProduceRewardType | 3 | 0 | 0 |  |
| ProduceScheduleLocationType | 16 | 15 | 1081 | ProduceScheduleMotion.locationType; ProduceScheduleBackground.locationType |
| ProduceScheduleMotionType | 5 | 4 | 1066 | ProduceScheduleMotion.motionType |
| ProduceScheduleStaminaMotionType | 3 | 2 | 1066 | ProduceScheduleMotion.staminaMotionType |
| ProduceSelectScreenOrderType | 3 | 2 | 8 | Produce.produceSelectScreenOrderType |
| ProduceSkillEffectType | 10 | 0 | 0 |  |
| ProduceSplitType | 3 | 3 | 1575 | ProduceSkill.produceSplitType; ProduceGrowthPanel.produceSplitType; ProduceSplitAdv.produceSplitTypes |
| ProduceStartMotionType | 3 | 2 | 39 | ProduceStartMotion.motionType |
| ProduceStepAuditionMotionType | 7 | 6 | 934 | ProduceStepAuditionMotion.motionType; ProduceStepAuditionCharacterUnitMotion.motionType; ProduceStepAuditionRivalActorMotion.motionType |
| ProduceStepAuditionType | 11 | 11 | 5125 | ProduceStepAuditionDifficulty.auditionType; ProduceStepAuditionMotion.auditionType |
| ProduceStepBusinessType | 5 | 4 | 351294 | ProduceCard.produceDescriptions; ProduceCard.produceDescriptions.produceStepBusinessType; ProduceExamStatusEnchant.produceDescriptions |
| ProduceStepFanPresentMotionType | 3 | 2 | 39 | ProduceStepFanPresentMotion.motionType |
| ProduceStepLessonType | 17 | 5 | 676 | ProduceExamTrigger.lessonType |
| ProduceStepPhaseType | 3 | 2 | 3228 | ProduceStepTransition.stepPhaseType |
| ProduceStepType | 51 | 34 | 369979 | ProduceCard.produceDescriptions; ProduceCard.produceDescriptions.produceStepType; ProduceExamStatusEnchant.produceDescriptions |
| ProduceStoryType | 10 | 8 | 3341 | ProduceStory.type |
| ProduceTriggerOriginType | 12 | 0 | 0 |  |
| ProduceType | 4 | 4 | 2086 | ProduceSkill.produceType; CharacterDearnessLevel.trueEndAchievementProduceType; CharacterTrueEndAchievement.produceType |
| ProducerLevelUnlockType | 8 | 7 | 322 | ProducerLevel.unlockTargets; ProducerLevel.unlockTargets.type |
| ProducerRankingGrade | 7 | 6 | 24 | ProducerRankingRankGrade.grade |
| ProducerRankingPointType | 3 | 0 | 0 |  |
| PurchaseTransactionStatusType | 7 | 0 | 0 |  |
| PushType | 8 | 7 | 169 | CharacterPushMessage.type |
| PvpRateGrade | 9 | 8 | 8 | PvpRateUnitSlotUnlock.grade |
| PvpRateMotionType | 3 | 2 | 52 | PvpRateMotion.motionType |
| PvpRatePhaseType | 6 | 0 | 0 |  |
| PvpRateRivalType | 4 | 0 | 0 |  |
| PvpRateSeasonStatusType | 5 | 0 | 0 |  |
| PvpRateStageType | 4 | 3 | 306 | PvpRateConfig.stages; PvpRateConfig.stages.stageType |
| ResetTimingType | 5 | 4 | 320 | ShopItem.resetTimingType; MissionPoint.resetTimingType; Shop.resetTimingType |
| ResourceOriginType | 4 | 4 | 940 | Costume.resourceOriginType; CostumeHead.resourceOriginType |
| ResourceType | 30 | 18 | 23201 | AchievementProgress.rewards; AchievementProgress.rewards.resourceType; MissionProgress.rewards |
| ResultGrade | 20 | 19 | 181 | ResultGradePattern.grade; ProduceGrade.grade; ProduceSeasonZeroGrade.grade |
| ResultGradeType | 6 | 4 | 60 | ResultGradePattern.type |
| RewardProvideType | 6 | 0 | 0 |  |
| RewardSetType | 3 | 0 | 0 |  |
| RuleType | 5 | 4 | 23 | Rule.type |
| ServingStatus | 5 | 0 | 0 |  |
| ShopItemLabelType | 3 | 2 | 126 | ShopItem.labelTypes |
| ShopType | 6 | 5 | 5 | Shop.type |
| SkillRarity | 5 | 5 | 2063 | ProduceSkill.rarity; MemoryAbility.rarity |
| StartupNotificationDisplayType | 11 | 0 | 0 |  |
| StartupNotificationEffectType | 4 | 0 | 0 |  |
| StartupNotificationRemindType | 6 | 0 | 0 |  |
| StartupNotificationType | 13 | 0 | 0 |  |
| StoryCampaignType | 3 | 0 | 0 |  |
| StoryEventMotionType | 4 | 0 | 0 |  |
| StoryEventType | 5 | 5 | 130 | StoryGroup.storyEventType; StoryEvent.storyEventType |
| StoryType | 12 | 9 | 364 | Story.type; StoryGroup.storyType |
| SupportCardLevelLimitRank | 5 | 5 | 15 | SupportCardLevelLimit.rank |
| SupportCardRarity | 4 | 4 | 568 | Item.supportCardRarity; SupportCard.rarity; SupportCardBonus.rarity |
| SupportCardType | 5 | 4 | 201 | SupportCard.type |
| TermsType | 4 | 3 | 3 | Terms.type |
| TimeType | 10 | 0 | 0 |  |
| TipsType | 6 | 3 | 30 | Tips.type |
| TourProgressPhaseType | 3 | 0 | 0 |  |
| TourScoreGrade | 14 | 0 | 0 |  |
| TourStageIconSizeType | 4 | 0 | 0 |  |
| TutorialCharacterVoiceType | 3 | 2 | 21 | TutorialCharacterVoice.type |
| TutorialNavigationPositionType | 6 | 4 | 216 | Tutorial.navigationPositionType |
| TutorialNavigationType | 6 | 6 | 216 | Tutorial.navigationType |
| TutorialProduceCommandType | 9 | 9 | 216 | Tutorial.tutorialProduceCommandType |
| TutorialType | 90 | 78 | 548 | MainTask.unlockFeatureTutorialType; Tutorial.tutorialType; TutorialProduceStep.tutorialType |
| ViewAreaType | 3 | 3 | 30 | Tips.viewAreaType |
| VoicePlayScreenType | 5 | 3 | 1915 | VoiceRoster.type |
| Weekday | 8 | 2 | 285 | ShopItem.resetWeekday; Shop.resetWeekday |
| WorkMotionType | 7 | 6 | 78 | WorkMotion.motionType |
| WorkType | 3 | 2 | 2768 | WorkLevelReward.type; WorkLevel.type; WorkTime.type |

dump 中形似枚举但 proto 未定义的前缀（多为 id 噪声）：Convert

## 2. 核心枚举详解

### 2.1 ProduceExamEffectType（考试内效果类型）——效果解释器的实现清单

每个值给出：语义（中文）、UI 名称与说明文（来自 ProduceDescriptionExamEffect → ProduceDescriptionLabel）、ProduceExamEffect 中的行数与非零字段、取值范围、引用来源、示例行与渲染文本。`v1/v2` 指 effectValue1/2；‰ 表示千分比。

#### Unknown  — rows=0  （无 UI 名称行）

- 语义：占位/未指定。
- dump 中无 ProduceExamEffect 行。

#### ExamLesson  — rows=122  UI名=**パラメータ**

- 语义：パラメータ/スコア +v1，effectCount 次（“パラメータ+9（2回）”）。受 好調/集中/強気/全力/熱意 等倍率修正。
- swap=Swap_Label_ExamLesson，noIcon，noReference
- 非零字段：`effectValue1` 122/122, `effectCount` 122/122
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
  - effectCount 取值：[1, 2, 3, 4, 5, 6]
- 被谁引用：ProduceCard.playEffects=431, StatusEnchant=97, Gimmick=49, chain=19, GrowEffect=2, Drink=1
- 示例行：`{"id": "e_effect-exam_lesson-0001-01", "effectValue1": 1, "effectCount": 1}`
  - 文本：「パラメータ+1」
  - 另一例 `e_effect-exam_lesson-0023-01`：「パラメータ+23」

#### ExamParameterBuff  — rows=17  UI名=**好調**

- 语义：好調 +effectTurn 回合（参数 ×1.5，ExamSetting.examParameterBuffPermil）。
- 说明文（Label_ExamParameterBuff）：パラメータ上昇量を50%増加
- 图标阈值=[3, 5]
- 非零字段：`effectTurn` 17/17
  - effectTurn 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
- 被谁引用：Gimmick=194, ProduceCard.playEffects=154, StatusEnchant=148, chain=5, Drink=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_parameter_buff-01", "effectTurn": 1}`
  - 文本：「好調1ターン」
  - 另一例 `e_effect-exam_parameter_buff-09`：「好調9ターン」

#### ExamBlock  — rows=60  UI名=**元気**

- 语义：元気 +v1（受 やる気 加成、不安/弱気 减成）。
- 说明文（Label_ExamBlock）：スキルカードやトラブルによる体力減少時、体力の代わりに消費される
- 非零字段：`effectValue1` 60/60
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
- 被谁引用：ProduceCard.playEffects=480, Gimmick=454, StatusEnchant=187, chain=12, Drink=3, GrowEffect=2, ProduceCard.move=1
- 示例行：`{"id": "e_effect-exam_block-0001", "effectValue1": 1}`
  - 文本：「元気+1」
  - 另一例 `e_effect-exam_block-0031`：「元気+31」

#### ExamCardDraw  — rows=5  UI名=**スキルカードを引く**

- 语义：抽 v1 张牌。
- 说明文（Label_ExamCardDraw）：スキルカードを引く
- noReference
- 非零字段：`effectValue1` 5/5
  - effectValue1 取值：[1, 2, 3, 4, 5]
- 被谁引用：StatusEnchant=106, ProduceCard.playEffects=104, chain=6, ProduceCard.move=1, Drink=1
- 示例行：`{"id": "e_effect-exam_card_draw-0001", "effectValue1": 1}`
  - 文本：「スキルカードを引く」
  - 另一例 `e_effect-exam_card_draw-0003`：「スキルカードを3枚引く」

#### ExamStaminaConsumptionDown  — rows=8  UI名=**消費体力減少**

- 语义：消費体力減少 状态 effectTurn 回合（×50%）。
- 说明文（Label_ExamStaminaConsumptionDown）：消費体力を50%軽減
- 非零字段：`effectTurn` 8/8
  - effectTurn 取值：[-1, 1, 2, 3, 4, 5, 6, 7]
- 被谁引用：ProduceCard.playEffects=66, Gimmick=65, StatusEnchant=42, Drink=2, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_stamina_consumption_down-01", "effectTurn": 1}`
  - 文本：「消費体力減少1ターン」
  - 另一例 `e_effect-exam_stamina_consumption_down-05`：「消費体力減少5ターン」

#### ExamCardCreateId  — rows=15  UI名=**生成**

- 语义：生成指定卡 targetProduceCardId（targetUpgradeCount 段）pickCount 张到 movePositionType；レッスン結束后删除。
- 说明文（Label_ExamCardCreateId）：スキルカードを獲得する。獲得したスキルカードはレッスン終了時に削除される
- 非零字段：`targetProduceCardId` 15/15, `movePositionType` 15/15, `pickCountMin` 15/15, `pickCountMax` 15/15, `targetUpgradeCount` 5/15
  - movePositionType 取值：['DeckFirst', 'DeckRandom', 'Grave', 'Hand']
  - pickCountMin 取值：[1, 2, 5]
  - pickCountMax 取值：[1, 2, 5]
- 被谁引用：Gimmick=51, ProduceCard.playEffects=37, StatusEnchant=28
- 示例行：`{"id": "e_effect-exam_card_create_id-p_card-00-acc-0_002-0-deck_first-1_1", "targetProduceCardId": "p_card-00-acc-0_002", "movePositionType": "ProduceCardMovePositionType_DeckFirst", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本：「眠気を山札の一番上に生成」
  - 另一例 `e_effect-exam_card_create_id-p_card-01-men-1_008-0-deck_first-1_1`：「深呼吸を山札の一番上に生成」

#### ExamStaminaReduceFix  — rows=7  UI名=**体力消費**

- 语义：体力消費 v1（无视元気直接扣体力）。
- 说明文（Label_ExamStaminaReduceFix）：元気を無視して体力を消費
- 非零字段：`effectValue1` 7/7
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 10]
- 被谁引用：StatusEnchant=162, Gimmick=28, Drink=1
- 示例行：`{"id": "e_effect-exam_stamina_reduce_fix-0001", "effectValue1": 1}`
  - 文本：「体力消費1」
  - 另一例 `e_effect-exam_stamina_reduce_fix-0004`：「体力消費4」

#### ExamCardMove  — rows=44  （无 UI 名称行）

- 语义：移动筛选/选择的卡到 movePositionType（手札/山札/捨札/除外/保留）。
- 非零字段：`produceCardSearchId` 44/44, `movePositionType` 44/44, `pickRangeType` 44/44, `pickCountMax` 21/44, `pickCountMin` 20/44
  - pickRangeType 取值：['All', 'Random', 'Select']
  - movePositionType 取值：['DeckFirst', 'DeckLast', 'DeckRandom', 'Grave', 'Hand', 'Hold', 'Lost']
  - pickCountMin 取值：[1, 2, 3]
  - pickCountMax 取值：[1, 2, 3]
- 被谁引用：StatusEnchant=143, ProduceCard.playEffects=84, Gimmick=23, chain=4, Drink=3, GrowEffect=2, ProduceCard.move=1
- 示例行：`{"id": "e_effect-exam_card_move-p_card_search-active_skill-deck_grave-hand-random-1_1", "produceCardSearchId": "p_card_search-active_skill-deck_grave", "movePositionType": "ProduceCardMovePositionType_Hand", "pickRangeType": "ProducePickRangeType_Random", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本：「ランダムな山札か捨札のアクティブスキルカードを手札に移動」
  - 另一例 `e_effect-exam_card_move-p_card_search-hand-1-grave-select-1_1`：「手札のスキルカード1枚を選択し、捨札に移動」

#### ExamLessonBuff  — rows=20  UI名=**集中**

- 语义：集中 +v1（每点使 パラメータ +1）。
- 说明文（Label_ExamLessonBuff_Produce）：集中が1増加するごとに、パラメータ上昇量を1増加
- 考试内说明（Label_ExamLessonBuff_Exam）：パラメータ上昇量を増加
- 图标阈值=[5, 10]
- 非零字段：`effectValue1` 20/20
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
- 被谁引用：Gimmick=330, ProduceCard.playEffects=201, StatusEnchant=162, chain=4, Drink=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_lesson_buff-0001", "effectValue1": 1}`
  - 文本：「集中+1」
  - 另一例 `e_effect-exam_lesson_buff-0011`：「集中+11」

#### ExamCardUpgrade  — rows=13  UI名=**レッスン中強化**

- 语义：レッスン中強化：把筛选到的卡临时升级（pickRange/pickCount）。
- 说明文（Label_ExamCardUpgrade）：レッスン中強化終了までスキルカードを強化
- swap=Swap_Label_ExamCardUpgrade
- 非零字段：`produceCardSearchId` 13/13, `pickRangeType` 13/13, `pickCountMin` 7/13, `pickCountMax` 7/13
  - pickRangeType 取值：['All', 'Random', 'Select']
  - pickCountMin 取值：[1, 2, 3]
  - pickCountMax 取值：[1, 2, 3]
- 被谁引用：StatusEnchant=10, ProduceCard.playEffects=4, chain=2, Drink=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_card_upgrade-p_card_search-active_skill-deck_all-random-1_1", "produceCardSearchId": "p_card_search-active_skill-deck_all", "pickRangeType": "ProducePickRangeType_Random", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本：「ランダムなアクティブスキルカード1枚をレッスン中強化」
  - 另一例 `e_effect-exam_card_upgrade-p_card_search-deck-1-all-0_0`：「山札のスキルカード1枚をすべてレッスン中強化」

#### ExamBlockValueMultiple  — rows=8  （无 UI 名称行）

- 语义：元気 ×(1+v1‰)。
- 非零字段：`effectValue1` 8/8
  - effectValue1 取值：[200, 300, 400, 500, 600, 1000, 1500, 2000]
- 被谁引用：Gimmick=19, StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_block_value_multiple-0200", "effectValue1": 200}`
  - 文本：「元気1.2倍」
  - 另一例 `e_effect-exam_block_value_multiple-0600`：「元気1.6倍」

#### ExamPlayableValueAdd  — rows=3  UI名=**スキルカード使用数追加**

- 语义：スキルカード使用数追加 +effectCount（本回合额外出牌次数）。
- 说明文（Label_ExamPlayableValueAdd_Produce）：このターン、スキルカードを追加で使用できる
- 考试内说明（Label_ExamPlayableValueAdd_Exam）：スキルカードを追加で使用できる
- 非零字段：`effectCount` 3/3
  - effectCount 取值：[1, 2, 3]
- 被谁引用：ProduceCard.playEffects=335, StatusEnchant=156, Gimmick=133, chain=7, Drink=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_playable_value_add-01", "effectCount": 1}`
  - 文本：「スキルカード使用数追加+1」
  - 另一例 `e_effect-exam_playable_value_add-02`：「スキルカード使用数追加+2」

#### ExamLessonBuffMultiple  — rows=15  UI名=**集中強化**

- 语义：集中強化：集中带来的参数增量 ×(1+v1‰)，effectTurn 回合。
- 说明文（Label_ExamLessonBuffMultiple）：集中によるパラメータ上昇量を増加
- 非零字段：`effectValue1` 15/15, `effectTurn` 15/15
  - effectValue1 取值：[50, 150, 200, 250, 300, 500, 1000, 1300, 1500, 2000, 3000]
  - effectTurn 取值：[-1, 1, 2, 3, 4, 5]
- 被谁引用：ProduceCard.playEffects=12, StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_lesson_buff_multiple-0050-01", "effectValue1": 50, "effectTurn": 1}`
  - 文本：「集中強化5%（1ターン）」
  - 另一例 `e_effect-exam_lesson_buff_multiple-0300-04`：「集中強化30%（4ターン）」

#### ExamCardStaminaConsumptionChange  — rows=0  UI名=**消費体力変化**

- 语义：（proto/描述表定义，dump 无行）改变某卡消耗体力。
- 说明文（Label_ExamCardStaminaConsumptionChange）：exam_template利用
- dump 中无 ProduceExamEffect 行。

#### ExamBlockRestriction  — rows=5  UI名=**元気増加無効**

- 语义：元気増加無効 effectTurn 回合。
- 说明文（Label_ExamBlockRestriction）：元気が増加しない
- 非零字段：`effectTurn` 5/5
  - effectTurn 取值：[-1, 1, 2, 3, 7]
- 被谁引用：StatusEnchant=29, Gimmick=13, ProduceCard.playEffects=8
- 示例行：`{"id": "e_effect-exam_block_restriction-01", "effectTurn": 1}`
  - 文本：「元気増加無効1ターン」
  - 另一例 `e_effect-exam_block_restriction-03`：「元気増加無効3ターン」

#### ExamLessonDependBlock  — rows=83  （无 UI 名称行）

- 语义：元気 ×v1‰ 的パラメータ（v2 为附加倍率）。
- 非零字段：`effectValue1` 83/83, `effectCount` 83/83, `effectValue2` 37/83
  - effectValue1 取值：[200, 250, 300, 350, 400, 500, 550, 600, 650, 700, 750, 800, 900, 950]
  - effectValue2 取值：[250, 500, 1000]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=72, StatusEnchant=72, chain=14, Gimmick=3, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_lesson_depend_block-0200-01", "effectValue1": 200, "effectCount": 1}`
  - 文本：「元気の20%分パラメータ上昇」
  - 另一例 `e_effect-exam_lesson_depend_block-1700-01`：「元気の170%分パラメータ上昇」

#### ExamCardCreateSearch  — rows=8  （无 UI 名称行）

- 语义：生成 pickCount 张来自 produceCardSearch（随机池）的卡到 movePositionType；pickCountType=Shortage 时补足到 N 张。
- 非零字段：`effectValue1` 8/8, `produceCardSearchId` 8/8, `movePositionType` 8/8, `pickRangeType` 8/8, `pickCountMin` 8/8, `pickCountMax` 8/8, `pickCountReferenceProduceCardSearchId` 6/8, `pickCountType` 6/8
  - effectValue1 取值：[1]
  - pickRangeType 取值：['Random']
  - movePositionType 取值：['DeckRandom', 'Hand']
  - pickCountMin 取值：[1, 22]
  - pickCountMax 取值：[1, 22]
- 被谁引用：StatusEnchant=6, ProduceCard.playEffects=4, Drink=1
- 示例行：`{"id": "e_effect-exam_card_create_search-0001-p_card_search-random-random_pool-p_random_pool-all-…", "effectValue1": 1, "produceCardSearchId": "p_card_search-random-random_pool-p_random_pool-all-upgrade_1-1", "movePositionType": "ProduceCardMovePositionType_Hand", "pickRangeType": "ProducePickRangeType_Random", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本：「ランダムな強化済みスキルカードを、手札に生成」
  - 另一例 `e_effect-exam_card_create_search-0001-p_card_search-random-random_pool-p_random_pool-produce_007-create_set-parameter_buff-p_card_search-deck-deck_random-random_shortage-22_22`：「山札にあるスキルカードが22枚になるように、ランダムな名前に「基本」を含むスキルカードを、山札のランダムな位置に生成」

#### ExamStatusEnchant  — rows=448  UI名=**持続効果**

- 语义：挂载持续效果 produceExamStatusEnchantId，持续 effectTurn(-1=整场)，最多 effectCount 次；本身无数值。
- 说明文（Label_ExamStatusEnchant）：exam_template利用
- noReference
- 非零字段：`effectTurn` 447/448, `produceExamStatusEnchantId` 444/448, `effectCount` 142/448, `pickCountMin` 13/448, `pickCountMax` 13/448, `effectValue1` 2/448
  - effectValue1 取值：[5, 20]
  - effectCount 取值：[1, 2, 3, 4, 5]
  - effectTurn 取值：[-1, 1, 2, 3, 4, 5, 11]
  - pickCountMin 取值：[1]
  - pickCountMax 取值：[1]
- 被谁引用：Gimmick=414, ProduceCard.playEffects=284, StatusEnchant=130, GrowEffect=14, Drink=5
- 示例行：`{"id": "e_effect-exam_status_enchant"}`
  - 文本：「未定義のパターン(Type: ExamStatusEnchant, EffectValue1: 0, EffectValue2: 0, EffectCount: 0, EffectTurn: 0, ProduceCardSearchID: , PickRangeType: , PickCountMin: 0, PickCountMax: 0, PickCountType: , ProduceCardSearch2TemplateNumber: 0)」
  - 另一例 `e_effect-exam_status_enchant-inf-enchant-p_card-02-ido-3_078-enc01`：「レッスン終了まで、好印象効果のスキルカード使用後、好印象の30%分パラメータ上昇」

#### ExamMultipleLessonBuffLesson  — rows=104  （无 UI 名称行）

- 语义：パラメータ +v1，集中效果按 v2‰ 倍率适用。
- 非零字段：`effectValue1` 104/104, `effectValue2` 104/104, `effectCount` 104/104
  - effectValue1 取值：[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
  - effectValue2 取值：[500, 700, 1000, 1300, 1400, 1500, 1600, 2000, 2500, 3000, 4000, 4500, 5000, 5500]
  - effectCount 取值：[1, 3]
- 被谁引用：ProduceCard.playEffects=44, StatusEnchant=13, chain=9, GrowEffect=3
- 示例行：`{"id": "e_effect-exam_multiple_lesson_buff_lesson-0002-0500-01", "effectValue1": 2, "effectValue2": 500, "effectCount": 1}`
  - 文本：「パラメータ+2（集中効果を1.5倍適用）」
  - 另一例 `e_effect-exam_multiple_lesson_buff_lesson-0014-1500-01`：「パラメータ+14（集中効果を2.5倍適用）」

#### ExamForcePlayCardSearch  — rows=8  （无 UI 名称行）

- 语义：无视费用直接使用筛选到的卡。
- 非零字段：`produceCardSearchId` 8/8, `pickRangeType` 8/8, `pickCountMin` 5/8, `pickCountMax` 5/8, `movePositionType` 2/8
  - pickRangeType 取值：['All', 'Random', 'Select']
  - movePositionType 取值：['Hand']
  - pickCountMin 取值：[1]
  - pickCountMax 取值：[1]
- 被谁引用：ProduceCard.playEffects=14, StatusEnchant=6, Drink=2
- 示例行：`{"id": "e_effect-exam_force_play_card_search-p_card_search-active_skill-lost-random-1_1", "produceCardSearchId": "p_card_search-active_skill-lost", "pickRangeType": "ProducePickRangeType_Random", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本：「ランダムな除外にあるアクティブスキルカードを、コストを消費せず使用」
  - 另一例 `e_effect-exam_force_play_card_search-p_card_search-r-random-hand-2-all-0_0`：「ランダムな手札にあるスキルカード（R）2枚をコストを消費せず使用」

#### ExamCardStaminaConsumptionDownSpecify  — rows=0  UI名=**消費体力低下**

- 语义：（定义，dump 无行）指定卡消耗降低。
- 说明文（Label_ExamCardStaminaConsumptionDownSpecify）：exam_template利用
- dump 中无 ProduceExamEffect 行。

#### ExamStaminaDamage  — rows=11  UI名=**体力減少**

- 语义：体力減少 v1（试炼 gimmick 用，元気可抵挡）。
- swap=Swap_Label_ExamStaminaDamage，noReference
- 非零字段：`effectValue1` 11/11
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12]
- 被谁引用：Gimmick=480, StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_stamina_damage-0001", "effectValue1": 1}`
  - 文本：「体力減少1」
  - 另一例 `e_effect-exam_stamina_damage-0006`：「体力減少6」

#### ExamStaminaRecoverFix  — rows=25  UI名=**体力回復**

- 语义：体力回復 v1。
- swap=Swap_Label_ExamStaminaRecoverFix，noReference
- 非零字段：`effectValue1` 25/25
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
- 被谁引用：StatusEnchant=77, Gimmick=54, ProduceCard.playEffects=28, Drink=3, chain=3
- 示例行：`{"id": "e_effect-exam_stamina_recover_fix-0001", "effectValue1": 1}`
  - 文本：「体力回復1」
  - 另一例 `e_effect-exam_stamina_recover_fix-0013`：「体力回復13」

#### ExamLessonFix  — rows=14  UI名=**固定パラメータ**

- 语义：固定パラメータ +v1（不受强化/低下状态影响）。
- 说明文（Label_ExamLessonFix）：固定パラメータパラメータを増加させる
- swap=Swap_Label_ExamLessonFix
- 非零字段：`effectValue1` 14/14, `effectCount` 14/14
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=1
- 示例行：`{"id": "e_effect-exam_lesson_fix-0001-01", "effectValue1": 1, "effectCount": 1}`
  - 文本：「固定パラメータ+1」
  - 另一例 `e_effect-exam_lesson_fix-0008-01`：「固定パラメータ+8」

#### ExamCardDuplicate  — rows=1  UI名=**複製**

- 语义：複製：把筛选/选择的卡复制到 movePositionType。
- 说明文（Label_ExamCardDuplicate）：スキルカードの複製を獲得する。獲得したスキルカードはレッスン終了時に削除される
- 非零字段：`effectValue1` 1/1, `produceCardSearchId` 1/1, `movePositionType` 1/1, `pickRangeType` 1/1, `pickCountMax` 1/1
  - effectValue1 取值：[1]
  - pickRangeType 取值：['Select']
  - movePositionType 取值：['DeckLast']
  - pickCountMax 取值：[1]
- 被谁引用：StatusEnchant=12
- 示例行：`{"id": "e_effect-exam_card_duplicate-0001-p_card_search-hand-deck_last-select-0_1", "effectValue1": 1, "produceCardSearchId": "p_card_search-hand", "movePositionType": "ProduceCardMovePositionType_DeckLast", "pickRangeType": "ProducePickRangeType_Select", "pickCountMax": 1}`
  - 文本：「手札を1枚まで選択し、山札の一番下に複製」

#### ExamReview  — rows=18  UI名=**好印象**

- 语义：好印象 +v1（回合结束按好印象值加参数，回合开始 -1）。
- 说明文（Label_ExamReview_Produce）：ターン終了時、好印象1ごとにパラメータを1上昇。ターン開始時、好印象が1減少
- 考试内说明（Label_ExamReview_Exam）：ターン終了時、パラメータを上昇。ターン開始時、好印象が1減少
- 图标阈值=[5, 10]
- 非零字段：`effectValue1` 18/18
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
- 被谁引用：ProduceCard.playEffects=260, Gimmick=251, StatusEnchant=172, chain=3, Drink=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_review-0001", "effectValue1": 1}`
  - 文本：「好印象+1」
  - 另一例 `e_effect-exam_review-0010`：「好印象+10」

#### ExamLessonValueChangePerPlay  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamCardStaminaConsumptionReduce  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamReviewValueMultiple  — rows=8  （无 UI 名称行）

- 语义：好印象 ×(1+v1‰)。
- 非零字段：`effectValue1` 8/8
  - effectValue1 取值：[100, 200, 300, 500, 700, 1000, 1500, 2000]
- 被谁引用：Gimmick=51, StatusEnchant=11, ProduceCard.playEffects=8, chain=1
- 示例行：`{"id": "e_effect-exam_review_value_multiple-0100", "effectValue1": 100}`
  - 文本：「好印象1.1倍」
  - 另一例 `e_effect-exam_review_value_multiple-0700`：「好印象1.7倍」

#### ExamCardSearchEffectPlayCountBuff  — rows=8  UI名=**スキルカード追加発動**

- 语义：スキルカード追加発動：下 effectCount 张符合筛选的卡效果再发动 v1 次，effectTurn 回合内。
- 说明文（Label_ExamCardSearchEffectPlayCountBuff_Produce）：次に使用する対象のスキルカードの効果を複数回発動
- 考试内说明（Label_ExamCardSearchEffectPlayCountBuff）：の効果をもう回発動
- 非零字段：`effectValue1` 8/8, `effectCount` 8/8, `effectTurn` 8/8, `produceCardSearchId` 8/8, `pickRangeType` 8/8
  - effectValue1 取值：[1]
  - effectCount 取值：[1, 10]
  - effectTurn 取值：[-1, 1]
  - pickRangeType 取值：['All']
- 被谁引用：ProduceCard.playEffects=20, StatusEnchant=8, Drink=2, chain=1
- 示例行：`{"id": "e_effect-exam_card_search_effect_play_count_buff-0001-01-01-p_card_search-active_skill-de…", "effectValue1": 1, "effectCount": 1, "effectTurn": 1, "produceCardSearchId": "p_card_search-active_skill-deck_all", "pickRangeType": "ProducePickRangeType_All"}`
  - 文本：「次に使用するアクティブスキルカードの効果をもう1回発動（1回・1ターン）」
  - 另一例 `e_effect-exam_card_search_effect_play_count_buff-0001-01-01-p_card_search-mental_skill-playing-all-0_0`：「次に使用するメンタルスキルカードの効果をもう1回発動（1回・1ターン）」

#### ExamLessonValueMultiple  — rows=62  UI名=**パラメータ上昇量増加**

- 语义：パラメータ上昇量増加 +v1‰（含好印象带来的上升），effectTurn 回合。
- 说明文（Label_ExamLessonValueMultiple）：パラメータ上昇量増加上昇量を増加（好印象による上昇も含む）
- swap=Swap_Label_ExamLessonValueMultiple
- 非零字段：`effectValue1` 62/62, `effectTurn` 62/62
  - effectValue1 取值：[20, 30, 50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 800, 900]
  - effectTurn 取值：[-1, 1, 2, 3, 4, 5, 6, 8, 20]
- 被谁引用：Gimmick=293, StatusEnchant=135, ProduceCard.playEffects=12, Drink=2, chain=2
- 示例行：`{"id": "e_effect-exam_lesson_value_multiple-0020-inf", "effectValue1": 20, "effectTurn": -1}`
  - 文本：「パラメータ上昇量増加2%」
  - 另一例 `e_effect-exam_lesson_value_multiple-0700-03`：「パラメータ上昇量増加70%（3ターン）」

#### ExamCardPlayAggressive  — rows=16  UI名=**やる気**

- 语义：やる気 +v1（每点使 元気增量 +1）。
- 说明文（Label_ExamCardPlayAggressive_Produce）：やる気が1増加するごとに、元気の増加量を1増加
- 考试内说明（Label_ExamCardPlayAggressive_Exam）：元気の増加量を増加
- 图标阈值=[5, 10]
- 非零字段：`effectValue1` 16/16
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15]
- 被谁引用：Gimmick=209, ProduceCard.playEffects=200, StatusEnchant=157, ProduceCard.move=4, chain=3, Drink=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_card_play_aggressive-0001", "effectValue1": 1}`
  - 文本：「やる気+1」
  - 另一例 `e_effect-exam_card_play_aggressive-0009`：「やる気+9」

#### ExamConcentration  — rows=2  UI名=**強気**

- 语义：指針→強気（v1=段数 1/2）。
- 说明文（Label_ExamConcentration_Produce）：指針を強気に変更する / すでに強気の場合、2段階目になる /  / ▼1段階目 / パラメータ上昇量と消費体力を100%増加 /  / ▼2段階目 / パラメータ上昇量を150%増加・消費体力が100%増加 / スキルカードを使うごとに、体力消費1
- 考试内说明（Label_ExamConcentration_Exam）：▼1段階目 / パラメータ上昇量と消費体力を100%増加 /  / ▼2段階目 / パラメータ上昇量を150%増加・消費体力が100%増加 / スキルカードを使うごとに、体力消費1
- 图标阈值=[1]
- 非零字段：`effectValue1` 2/2
  - effectValue1 取值：[1, 2]
- 被谁引用：ProduceCard.playEffects=136, StatusEnchant=3, GrowEffect=3, chain=3, Drink=2
- 示例行：`{"id": "e_effect-exam_concentration-0001", "effectValue1": 1}`
  - 文本：「強気に変更」
  - 另一例 `e_effect-exam_concentration-0002`：「強気2段階目に変更」

#### ExamPreservation  — rows=2  UI名=**温存**

- 语义：指針→温存（v1=段数）。
- 说明文（Label_ExamPreservation_Produce）：指針を温存に変更する / すでに温存の場合、2段階目になる /  / ▼1段階目 / パラメータ上昇量と消費体力を50%減少 / 解除されたとき、熱意+5・スキルカード使用数追加+1 /  / ▼2段階目 / パラメータ上昇量と消費体力を75%減少 / 解除されたとき、熱意+8・固定元気+5・スキルカード使用数追加+1
- 考试内说明（Label_ExamPreservation_Exam）：▼1段階目 / パラメータ上昇量と消費体力を50%減少 / 解除されたとき、熱意+5・スキルカード使用数追加+1 /  / ▼2段階目 / パラメータ上昇量と消費体力を75%減少 / 解除されたとき、熱意+8・固定元気+5・スキルカード使用数追加+1
- 非零字段：`effectValue1` 2/2
  - effectValue1 取值：[1, 2]
- 被谁引用：ProduceCard.playEffects=114, StatusEnchant=48, Drink=2, GrowEffect=2, chain=2
- 示例行：`{"id": "e_effect-exam_preservation-0001", "effectValue1": 1}`
  - 文本：「温存に変更」
  - 另一例 `e_effect-exam_preservation-0002`：「温存2段階目に変更」

#### ExamFullPower  — rows=1  UI名=**全力**

- 语义：指針→全力。
- 说明文（Label_ExamFullPower）：全力に変更時、スキルカード使用数追加+1・保留にあるスキルカードを手札に移動 / 全力状態の時、パラメータ上昇量を200%増加 / 次のターン開始時に全力を解除 / 全力状態を解除するまで指針は変更できない
- 图标阈值=[1]
- 非零字段：
- 被谁引用：（无引用）
- 示例行：`{"id": "e_effect-exam_full_power"}`
  - 文本：「全力に変更」

#### ExamStanceReset  — rows=1  UI名=**指針解除**

- 语义：指針解除（解除温存/強気）。
- 说明文（Label_ExamStanceReset）：「温存」と「強気」を解除する
- 非零字段：
- 被谁引用：StatusEnchant=1
- 示例行：`{"id": "e_effect-exam_stance_reset"}`
  - 文本：「指針解除」

#### ExamFullPowerPoint  — rows=11  UI名=**全力値**

- 语义：全力値 +v1（回合末 ≥10 则下回合开始消费 10 进入全力）。
- 说明文（Label_ExamFullPowerPoint）：ターン終了時に全力値が10以上なら、次のターン開始時に全力値を10消費して、指針を全力に変更
- 图标阈值=[5, 10]
- 非零字段：`effectValue1` 11/11
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15]
- 被谁引用：ProduceCard.playEffects=185, StatusEnchant=47, Gimmick=30, chain=6, Drink=2, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_full_power_point-0001", "effectValue1": 1}`
  - 文本：「全力値+1」
  - 另一例 `e_effect-exam_full_power_point-0006`：「全力値+6」

#### ExamForecast  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamFullPowerPointReduce  — rows=3  UI名=**全力値減少**

- 语义：全力値 -v1。
- 说明文（Label_ExamFullPowerPointReduce）：全力値を減少させる
- 非零字段：`effectValue1` 3/3
  - effectValue1 取值：[1, 2, 3]
- 被谁引用：StatusEnchant=8
- 示例行：`{"id": "e_effect-exam_full_power_point_reduce-0001", "effectValue1": 1}`
  - 文本：「全力値減少1」
  - 另一例 `e_effect-exam_full_power_point_reduce-0002`：「全力値減少2」

#### ExamLessonAddBlock  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamLessonFullPowerPoint  — rows=55  （无 UI 名称行）

- 语义：パラメータ +v1（累计全力値 ×v2‰ 追加），effectCount 次。
- 非零字段：`effectValue2` 55/55, `effectCount` 55/55, `effectValue1` 43/55
  - effectValue1 取值：[2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16]
  - effectValue2 取值：[500, 600, 1000, 1200, 1400, 1500, 1600, 1700, 2000, 2700, 3000, 3500, 4000, 6500]
  - effectCount 取值：[1, 2, 3, 4]
- 被谁引用：ProduceCard.playEffects=18, StatusEnchant=14, Gimmick=2, chain=1
- 示例行：`{"id": "e_effect-exam_lesson_full_power_point-0002-1000-01", "effectValue1": 2, "effectValue2": 1000, "effectCount": 1}`
  - 文本：「パラメータ+2（累積全力値の100%分、パラメータ上昇量増加）」
  - 另一例 `e_effect-exam_lesson_full_power_point-0012-0500-01`：「パラメータ+12（累積全力値の50%分、パラメータ上昇量増加）」

#### ExamSearchPlayCardStaminaConsumptionChange  — rows=5  UI名=**消費体力変化**

- 语义：使用的符合筛选的卡消耗体力改为 0，effectCount 次，effectTurn(-1)。
- 说明文（Label_ExamSearchPlayCardStaminaConsumptionChange）：exam_template利用
- 非零字段：`effectCount` 5/5, `effectTurn` 5/5, `produceCardSearchId` 5/5, `pickRangeType` 5/5
  - effectCount 取值：[1, 2, 3, 5]
  - effectTurn 取值：[-1]
  - pickRangeType 取值：['All']
- 被谁引用：ProduceCard.playEffects=9, StatusEnchant=5, Drink=1
- 示例行：`{"id": "e_effect-exam_search_play_card_stamina_consumption_change-01-inf-p_card_search-active_ski…", "effectCount": 1, "effectTurn": -1, "produceCardSearchId": "p_card_search-active_skill-deck_all", "pickRangeType": "ProducePickRangeType_All"}`
  - 文本：「使用したアクティブスキルカードの消費体力を0にする（）」
  - 另一例 `e_effect-exam_search_play_card_stamina_consumption_change-02-inf-p_card_search-deck_all-all-0_0`：「使用したスキルカードの消費体力を0にする（）」

#### ExamStaminaReduce  — rows=5  （无 UI 名称行）

- 语义：最大体力 ×v1‰ 消耗（可为负=回复）。
- 非零字段：`effectValue1` 5/5
  - effectValue1 取值：[-30, 100, 150, 800, 1000]
- 被谁引用：StatusEnchant=8, ProduceCard.playEffects=1
- 示例行：`{"id": "e_effect-exam_stamina_reduce--0030", "effectValue1": -30}`
  - 文本：「最大体力の-3%分体力消費」
  - 另一例 `e_effect-exam_stamina_reduce-0150`：「最大体力の15%分体力消費」

#### ExamUplifting  — rows=0  UI名=**高揚**

- 语义：高揚（定义，dump 无行）：回合末按高揚值加元気。
- 说明文（Label_ExamUplifting_Produce）：ターン終了時、高揚1ごとに元気を1増加。体力減少時、高揚が1減少
- 考试内说明（Label_ExamUplifting_Exam）：ターン終了時、元気を増加。体力減少時、高揚が1減少
- dump 中无 ProduceExamEffect 行。

#### ExamExtraTurn  — rows=1  UI名=**ターン追加**

- 语义：ターン追加 +1。
- 说明文（Label_ExamExtraTurn）：レッスンの残りターンが増加
- 非零字段：
- 被谁引用：Gimmick=28, StatusEnchant=21, ProduceCard.playEffects=7, Drink=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_extra_turn"}`
  - 文本：「ターン追加+1」

#### ExamAntiDebuff  — rows=4  UI名=**低下状態無効**

- 语义：低下状態無効 effectCount 次。
- 说明文（Label_ExamAntiDebuff）：低下状態にならない
- 非零字段：`effectCount` 4/4
  - effectCount 取值：[1, 2, 3, 5]
- 被谁引用：StatusEnchant=20, Gimmick=14, ProduceCard.playEffects=12, chain=1
- 示例行：`{"id": "e_effect-exam_anti_debuff-01", "effectCount": 1}`
  - 文本：「低下状態無効1回」
  - 另一例 `e_effect-exam_anti_debuff-03`：「低下状態無効3回」

#### ExamStaminaConsumptionAdd  — rows=7  UI名=**消費体力増加**

- 语义：消費体力増加 effectTurn 回合（+100%）。
- 说明文（Label_ExamStaminaConsumptionAdd）：消費体力が100%増加
- 非零字段：`effectTurn` 7/7
  - effectTurn 取值：[-1, 1, 2, 3, 4, 5, 16]
- 被谁引用：Gimmick=62, StatusEnchant=28, ProduceCard.playEffects=24, Drink=1
- 示例行：`{"id": "e_effect-exam_stamina_consumption_add-01", "effectTurn": 1}`
  - 文本：「消費体力増加1ターン」
  - 另一例 `e_effect-exam_stamina_consumption_add-04`：「消費体力増加4ターン」

#### ExamThresholdDown  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamBlockAddDown  — rows=8  UI名=**不安**

- 语义：不安 effectTurn 回合（元気获得 -33%）。
- 说明文（Label_ExamBlockAddDown）：元気の増加量が33%減少
- 非零字段：`effectTurn` 8/8
  - effectTurn 取值：[-1, 1, 2, 3, 4, 5, 6, 20]
- 被谁引用：StatusEnchant=12, Gimmick=10, chain=1
- 示例行：`{"id": "e_effect-exam_block_add_down-01", "effectTurn": 1}`
  - 文本：「不安1ターン」
  - 另一例 `e_effect-exam_block_add_down-05`：「不安5ターン」

#### ExamBlockAddDownRestriction  — rows=0  UI名=**不安無効**

- 语义：不安無効（定义，无行）。
- 说明文（Label_ExamBlockAddDownRestriction）：不安状態にならない
- dump 中无 ProduceExamEffect 行。

#### ExamStaminaRecoverAdd  — rows=0  UI名=**体力回復効果増加**

- 语义：体力回復効果増加（定义，无行）。
- 说明文（Label_ExamStaminaRecoverAdd）：体力回復効果を増加
- dump 中无 ProduceExamEffect 行。

#### ExamStaminaReduceChange  — rows=0  UI名=**体力消費軽減**

- 语义：体力消費軽減（定义，无行）。
- 说明文（Label_ExamStaminaReduceChange）：以下の消費体力を1にする
- dump 中无 ProduceExamEffect 行。

#### ExamPanic  — rows=3  UI名=**気まぐれ**

- 语义：気まぐれ effectTurn 回合：手牌消耗体力随机（候选 ExamSetting.produceExamPanicStaminaCandidates）。
- 说明文（Label_ExamPanic）：手札の消費体力がランダムに変化
- 非零字段：`effectTurn` 3/3
  - effectTurn 取值：[1, 3, 4]
- 被谁引用：Gimmick=32, StatusEnchant=1
- 示例行：`{"id": "e_effect-exam_panic-01", "effectTurn": 1}`
  - 文本：「気まぐれ1ターン」
  - 另一例 `e_effect-exam_panic-03`：「気まぐれ3ターン」

#### ExamLessonChangeSpecifyLessThan  — rows=0  UI名=**パラメータ上昇値変更**

- 语义：パラメータ上昇値変更（定义，无行）。
- 说明文（Label_ExamLessonChangeSpecifyLessThan）：パラメータ上昇値変更パラメータ上昇値が以下ならにする
- swap=Swap_Label_ExamLessonChangeSpecifyLessThan
- dump 中无 ProduceExamEffect 行。

#### ExamHandHold  — rows=0  UI名=**手札持ち越し**

- 语义：手札持ち越し（定义，无行）。
- 说明文（Label_ExamHandHold）：ターン終了時に手札を捨てない
- dump 中无 ProduceExamEffect 行。

#### ExamStaminaConsumptionAddFix  — rows=4  UI名=**消費体力追加**

- 语义：消費体力追加 +v1（固定值），effectTurn(-1)。
- 说明文（Label_ExamStaminaConsumptionAddFix）：スキルカードの消費体力が増加
- 非零字段：`effectValue1` 4/4, `effectTurn` 4/4
  - effectValue1 取值：[1, 2, 3, 4]
  - effectTurn 取值：[-1]
- 被谁引用：StatusEnchant=45, Gimmick=19
- 示例行：`{"id": "e_effect-exam_stamina_consumption_add_fix-0001-inf", "effectValue1": 1, "effectTurn": -1}`
  - 文本：「消費体力追加1」
  - 另一例 `e_effect-exam_stamina_consumption_add_fix-0003-inf`：「消費体力追加3」

#### ExamStaminaConsumptionAddDown  — rows=0  UI名=**消費体力増加効果減少**

- 语义：（定义，无行）。
- 说明文（Label_ExamStaminaConsumptionAddDown）：消費体力増加の効果を50%に変更
- dump 中无 ProduceExamEffect 行。

#### ExamStaminaRecoverRestriction  — rows=1  UI名=**体力回復無効**

- 语义：体力回復無効，effectTurn。
- 说明文（Label_ExamStaminaRecoverRestriction）：体力が回復しない
- 非零字段：`effectTurn` 1/1
  - effectTurn 取值：[-1]
- 被谁引用：StatusEnchant=12
- 示例行：`{"id": "e_effect-exam_stamina_recover_restriction-inf", "effectTurn": -1}`
  - 文本：「体力回復無効」

#### ExamStaminaConsumptionDownAdd  — rows=0  UI名=**消費体力減少効果増加**

- 语义：（定义，无行）。
- 说明文（Label_ExamStaminaConsumptionDownAdd）：消費体力減少の効果を60%に変更
- dump 中无 ProduceExamEffect 行。

#### ExamGetCardUpgrade  — rows=0  UI名=**生成強化**

- 语义：生成強化（定义，无行）。
- 说明文（Label_ExamGetCardUpgrade）：レッスン中にスキルカードを生成する場合、レッスン中強化状態で生成
- dump 中无 ProduceExamEffect 行。

#### ExamStaminaConsumptionDownFix  — rows=4  UI名=**消費体力削減**

- 语义：消費体力削減 -v1（固定值），effectTurn(-1)。
- 说明文（Label_ExamStaminaConsumptionDownFix）：スキルカードの消費体力を減少
- 非零字段：`effectValue1` 4/4, `effectTurn` 4/4
  - effectValue1 取值：[1, 2, 3, 4]
  - effectTurn 取值：[-1]
- 被谁引用：StatusEnchant=46, ProduceCard.playEffects=28, Gimmick=8
- 示例行：`{"id": "e_effect-exam_stamina_consumption_down_fix-0001-inf", "effectValue1": 1, "effectTurn": -1}`
  - 文本：「消費体力削減1」
  - 另一例 `e_effect-exam_stamina_consumption_down_fix-0003-inf`：「消費体力削減3」

#### ExamHandGraveCountCardDraw  — rows=1  UI名=**手札を入れ替える**

- 语义：手札をすべて入れ替える（弃全部手牌并抽同数）。
- 说明文（Label_ExamHandGraveCountCardDraw）：手札を入れ替える
- noReference
- 非零字段：
- 被谁引用：ProduceCard.playEffects=16, Drink=1
- 示例行：`{"id": "e_effect-exam_hand_grave_count_card_draw"}`
  - 文本：「手札をすべて入れ替える」

#### ExamHandGraveCountCardAdd  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamEffectTimer  — rows=138  UI名=**発動予約**

- 语义：発動予約：v1 回合后（effectCount 次）发动 chainProduceExamEffectId(s)。“次のターン、…”。
- 说明文（Label_ExamEffectTimer）：、
- noReference
- 非零字段：`effectValue1` 138/138, `effectCount` 138/138, `chainProduceExamEffectId` 132/138, `chainProduceExamEffectIds` 5/138
  - effectValue1 取值：[1, 2, 3, 4, 6]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=282, StatusEnchant=129, Gimmick=9, GrowEffect=3
- 示例行：`{"id": "e_effect-exam_effect_timer-0001-01-e_effect-exam_add_grow_effect-p_card_search-hand-all-0…", "effectValue1": 1, "effectCount": 1, "chainProduceExamEffectId": "e_effect-exam_add_grow_effect-p_card_search-hand-all-0_0-g_effect-lesson_add-12"}`
  - 文本：「次のターン、手札のパラメータ値増加+12」
  - 另一例 `e_effect-exam_effect_timer-0001-01-e_effect-exam_multiple_lesson_buff_lesson-0014-1000-03`：「次のターン、パラメータ+14（3回・集中効果を2倍適用）」

#### ExamGimmickLessonDebuff  — rows=4  UI名=**緊張**

- 语义：緊張 v1（每点参数 -1），effectTurn。
- 说明文（Label_ExamGimmickLessonDebuff_Produce）：緊張が1増加するごとに、パラメータ上昇量が1減少
- 考试内说明（Label_ExamGimmickLessonDebuff_Exam）：パラメータ上昇量を減少
- 非零字段：`effectValue1` 4/4, `effectTurn` 4/4
  - effectValue1 取值：[5, 6, 7, 10]
  - effectTurn 取值：[-1]
- 被谁引用：StatusEnchant=12
- 示例行：`{"id": "e_effect-exam_gimmick_lesson_debuff-0005-inf", "effectValue1": 5, "effectTurn": -1}`
  - 文本：「緊張5」
  - 另一例 `e_effect-exam_gimmick_lesson_debuff-0007-inf`：「緊張7」

#### ExamGimmickParameterDebuff  — rows=10  UI名=**不調**

- 语义：不調 effectTurn 回合（参数 ×2/3）。
- 说明文（Label_ExamGimmickParameterDebuff）：パラメータ上昇量が33%減少
- 非零字段：`effectTurn` 10/10
  - effectTurn 取值：[-1, 1, 2, 3, 4, 5, 6, 8, 19, 20]
- 被谁引用：Gimmick=63, StatusEnchant=14, chain=1
- 示例行：`{"id": "e_effect-exam_gimmick_parameter_debuff-01", "effectTurn": 1}`
  - 文本：「不調1ターン」
  - 另一例 `e_effect-exam_gimmick_parameter_debuff-06`：「不調6ターン」

#### ExamGimmickSleepy  — rows=5  UI名=**弱気**

- 语义：弱気 v1（每点元気获得 -1）。
- 说明文（Label_ExamGimmickSleepy_Produce）：弱気が1増加するごとに、元気の増加量が1減少
- 考试内说明（Label_ExamGimmickSleepy_Exam）：元気の増加量が減少
- 非零字段：`effectValue1` 5/5, `effectTurn` 5/5
  - effectValue1 取值：[1, 2, 3, 4, 10]
  - effectTurn 取值：[-1]
- 被谁引用：StatusEnchant=12, Gimmick=10
- 示例行：`{"id": "e_effect-exam_gimmick_sleepy-0001-inf", "effectValue1": 1, "effectTurn": -1}`
  - 文本：「弱気1」
  - 另一例 `e_effect-exam_gimmick_sleepy-0003-inf`：「弱気3」

#### ExamGimmickEnthusiastic  — rows=0  UI名=**熱意**

- 语义：熱意（定义，直接行为 0；通过温存解除等产生）：每点参数 +1，回合末清零。
- 说明文（Label_ExamGimmickEnthusiastic_Produce）：熱意1につきパラメータ上昇量を1増加  / ターン終了時、熱意を0にする
- 考试内说明（Label_ExamGimmickEnthusiastic_Exam）：パラメータ上昇量を増加  / ターン終了時、熱意を0にする
- dump 中无 ProduceExamEffect 行。

#### ExamGimmickPlayCardLimit  — rows=26  UI名=**スキルカード使用不可**

- 语义：使用不可：筛选到的卡 effectTurn 回合不可用。
- 说明文（Label_ExamGimmickPlayCardLimit_Produce）：スキルカードが使用できない
- 考试内说明（Label_ExamGimmickPlayCardLimit_Exam）：使用不可
- 非零字段：`effectTurn` 26/26, `produceCardSearchId` 26/26, `pickRangeType` 13/26
  - effectTurn 取值：[-1, 1, 2, 3, 4, 5]
  - pickRangeType 取值：['All']
- 被谁引用：Gimmick=36, StatusEnchant=22, chain=3
- 示例行：`{"id": "e_effect-exam_gimmick_play_card_limit-01-p_card_search-active_skill-deck_all", "effectTurn": 1, "produceCardSearchId": "p_card_search-active_skill-deck_all"}`
  - 文本：「アクティブスキルカード使用不可（1ターン）」
  - 另一例 `e_effect-exam_gimmick_play_card_limit-03-p_card_search-deck_all-effect_group-visible-exam_full_power-000-all-0_0`：「全力効果のスキルカード使用不可（3ターン）」

#### ExamGimmickSlump  — rows=4  UI名=**スランプ**

- 语义：スランプ effectTurn 回合：参数不上升。
- 说明文（Label_ExamGimmickSlump）：パラメータが上昇しない
- 非零字段：`effectTurn` 4/4
  - effectTurn 取值：[-1, 1, 2, 3]
- 被谁引用：Gimmick=28, StatusEnchant=27
- 示例行：`{"id": "e_effect-exam_gimmick_slump-01", "effectTurn": 1}`
  - 文本：「スランプ1ターン」
  - 另一例 `e_effect-exam_gimmick_slump-03`：「スランプ3ターン」

#### ExamGimmickStartTurnCardDrawDown  — rows=3  UI名=**手札減少**

- 语义：手札減少 v1（回合开始少抽 v1 张），effectTurn。
- 说明文（Label_ExamGimmickStartTurnCardDrawDown_Produce）：手札減少が1増加するごとに、ターン開始時に引くスキルカードが1枚減少
- 考试内说明（Label_ExamGimmickStartTurnCardDrawDown_Exam）：ターン開始時に引くスキルカードが枚減少
- 非零字段：`effectValue1` 3/3, `effectTurn` 3/3
  - effectValue1 取值：[1, 2]
  - effectTurn 取值：[-1, 1, 3]
- 被谁引用：StatusEnchant=14, Gimmick=10
- 示例行：`{"id": "e_effect-exam_gimmick_start_turn_card_draw_down-0001-03", "effectValue1": 1, "effectTurn": 3}`
  - 文本：「手札減少1（3ターン）」
  - 另一例 `e_effect-exam_gimmick_start_turn_card_draw_down-0001-inf`：「手札減少1（∞ターン）」

#### ExamStaminaRecoverMultiple  — rows=4  （无 UI 名称行）

- 语义：最大体力 ×v1‰ 回复。
- 非零字段：`effectValue1` 4/4
  - effectValue1 取值：[50, 100, 150, 200]
- 被谁引用：ProduceCard.playEffects=16, StatusEnchant=10
- 示例行：`{"id": "e_effect-exam_stamina_recover_multiple-0050", "effectValue1": 50}`
  - 文本：「最大体力の5%分体力回復」
  - 另一例 `e_effect-exam_stamina_recover_multiple-0150`：「最大体力の15%分体力回復」

#### ExamLessonPerSearchCount  — rows=4  （无 UI 名称行）

- 语义：パラメータ +v1，按筛选卡数每张 +v2‰（未被引用）。
- 非零字段：`effectValue1` 4/4, `effectValue2` 4/4, `effectCount` 4/4, `produceCardSearchId` 4/4
  - effectValue1 取值：[9, 15, 19, 23]
  - effectValue2 取值：[1]
  - effectCount 取值：[1]
- 被谁引用：（无引用）
- 示例行：`{"id": "e_effect-exam_lesson_per_search_count-0009-0001-01-p_card_search-active_skill-deck_all", "effectValue1": 9, "effectValue2": 1, "effectCount": 1, "produceCardSearchId": "p_card_search-active_skill-deck_all"}`
  - 文本：「パラメータ+9（アクティブスキルカードの数×0.1%分、さらに増加）」
  - 另一例 `e_effect-exam_lesson_per_search_count-0019-0001-01-p_card_search-active_skill-deck_all`：「パラメータ+19（アクティブスキルカードの数×0.1%分、さらに増加）」

#### ExamBlockFix  — rows=16  UI名=**固定元気**

- 语义：固定元気 +v1（不受 buff/debuff 影响）。
- 说明文（Label_ExamBlockFix）：強化状態や低下状態の影響を受けず元気を増加させる
- 非零字段：`effectValue1` 16/16
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
- 被谁引用：StatusEnchant=29, Gimmick=6, ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_block_fix-0001", "effectValue1": 1}`
  - 文本：「固定元気+1」
  - 另一例 `e_effect-exam_block_fix-0009`：「固定元気+9」

#### ExamLessonAddMultipleLessonBuff  — rows=8  （无 UI 名称行）

- 语义：集中 ×(1+v1‰)（“集中1.2倍”）。
- 非零字段：`effectValue1` 8/8
  - effectValue1 取值：[200, 300, 400, 500, 700, 1000, 1500, 2000]
- 被谁引用：Gimmick=16, StatusEnchant=11, ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_lesson_add_multiple_lesson_buff-0200", "effectValue1": 200}`
  - 文本：「集中1.2倍」
  - 另一例 `e_effect-exam_lesson_add_multiple_lesson_buff-0700`：「集中1.7倍」

#### ExamCardStatusEnchant  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamBlockDown  — rows=2  （无 UI 名称行）

- 语义：元気 -v1‰（百分比削减）。
- 非零字段：`effectValue1` 2/2
  - effectValue1 取值：[500, 1000]
- 被谁引用：chain=1
- 示例行：`{"id": "e_effect-exam_block_down-0500", "effectValue1": 500}`
  - 文本：「元気-50%」
  - 另一例 `e_effect-exam_block_down-1000`：「元気-100%」

#### ExamLessonChangeSpecifyMoreThan  — rows=0  UI名=**うわの空**

- 语义：うわの空（定义，无行）。
- 说明文（Label_ExamLessonChangeSpecifyMoreThan）：スキルカードのパラメータ上昇値が以下ならになる
- dump 中无 ProduceExamEffect 行。

#### ExamLessonDependExamReview  — rows=47  （无 UI 名称行）

- 语义：好印象 ×v1‰ 的パラメータ。
- 非零字段：`effectValue1` 47/47, `effectCount` 47/47
  - effectValue1 取值：[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=81, StatusEnchant=69, Gimmick=18, chain=11, Drink=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_lesson_depend_exam_review-0100-01", "effectValue1": 100, "effectCount": 1}`
  - 文本：「好印象の10%分パラメータ上昇」
  - 另一例 `e_effect-exam_lesson_depend_exam_review-2400-01`：「好印象の240%分パラメータ上昇」

#### ExamLessonDependExamCardPlayAggressive  — rows=25  （无 UI 名称行）

- 语义：やる気 ×v1‰ 的パラメータ。
- 非零字段：`effectValue1` 25/25, `effectCount` 25/25
  - effectValue1 取值：[500, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=24, StatusEnchant=20, Gimmick=1, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_lesson_depend_exam_card_play_aggressive-0500-01", "effectValue1": 500, "effectCount": 1}`
  - 文本：「やる気の50%分パラメータ上昇」
  - 另一例 `e_effect-exam_lesson_depend_exam_card_play_aggressive-1800-01`：「やる気の180%分パラメータ上昇」

#### ExamReviewDependExamBlock  — rows=8  （无 UI 名称行）

- 语义：元気 ×v1‰ 的好印象。
- 非零字段：`effectValue1` 8/8, `effectCount` 8/8, `effectValue2` 4/8
  - effectValue1 取值：[500, 600, 700, 750, 850, 1000]
  - effectValue2 取值：[1000]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=8
- 示例行：`{"id": "e_effect-exam_review_depend_exam_block-0500-01", "effectValue1": 500, "effectCount": 1}`
  - 文本：「元気の50%分好印象増加」
  - 另一例 `e_effect-exam_review_depend_exam_block-0750-01`：「元気の75%分好印象増加」

#### ExamBlockDependExamReview  — rows=2  （无 UI 名称行）

- 语义：好印象 ×v1‰ 的元気。
- 非零字段：`effectValue1` 2/2, `effectCount` 2/2
  - effectValue1 取值：[1000, 2500]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=5
- 示例行：`{"id": "e_effect-exam_block_depend_exam_review-1000-01", "effectValue1": 1000, "effectCount": 1}`
  - 文本：「好印象の100%分元気増加」
  - 另一例 `e_effect-exam_block_depend_exam_review-2500-01`：「好印象の250%分元気増加」

#### ExamReviewDependExamCardPlayAggressive  — rows=1  （无 UI 名称行）

- 语义：やる気 ×v1‰ 的好印象。
- 非零字段：`effectValue1` 1/1, `effectCount` 1/1
  - effectValue1 取值：[3000]
  - effectCount 取值：[1]
- 被谁引用：（无引用）
- 示例行：`{"id": "e_effect-exam_review_depend_exam_card_play_aggressive-3000-01", "effectValue1": 3000, "effectCount": 1}`
  - 文本：「やる気の300%分好印象増加」

#### ExamParameterBuffMultiplePerTurn  — rows=12  UI名=**絶好調**

- 语义：絶好調 effectTurn 回合：好調的加成按好調剩余回合每回合 +10%。
- 说明文（Label_ExamParameterBuffMultiplePerTurn）：好調のパラメータ上昇量を好調1ターンごとに10%増加
- 非零字段：`effectTurn` 12/12
  - effectTurn 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
- 被谁引用：ProduceCard.playEffects=45, StatusEnchant=35, Gimmick=31, Drink=2, GrowEffect=1, chain=1
- 示例行：`{"id": "e_effect-exam_parameter_buff_multiple_per_turn-01", "effectTurn": 1}`
  - 文本：「絶好調1ターン」
  - 另一例 `e_effect-exam_parameter_buff_multiple_per_turn-07`：「絶好調7ターン」

#### ExamLessonBuffDependParameterBuff  — rows=11  （无 UI 名称行）

- 语义：好調回合数 ×v1‰ 的集中（v2 存在时同时把集中减半等）。
- 非零字段：`effectValue1` 11/11, `effectCount` 11/11
  - effectValue1 取值：[150, 200, 300, 400, 500, 900, 1000, 1200, 1300, 1500, 2000]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=8, ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_lesson_buff_depend_parameter_buff-0150-01", "effectValue1": 150, "effectCount": 1}`
  - 文本：「好調の15%分集中増加」
  - 另一例 `e_effect-exam_lesson_buff_depend_parameter_buff-0900-01`：「好調の90%分集中増加」

#### ExamLessonDependParameterBuff  — rows=20  （无 UI 名称行）

- 语义：好調回合数 ×v1‰ 的パラメータ。
- 非零字段：`effectValue1` 20/20, `effectCount` 20/20, `effectValue2` 4/20
  - effectValue1 取值：[300, 700, 800, 900, 1000, 1200, 1500, 1800, 2000, 2300, 2500, 11000, 13000, 14000]
  - effectValue2 取值：[500, 1000]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=21, StatusEnchant=17, Gimmick=1, chain=1
- 示例行：`{"id": "e_effect-exam_lesson_depend_parameter_buff-0300-01", "effectValue1": 300, "effectCount": 1}`
  - 文本：「好調の30%分パラメータ上昇」
  - 另一例 `e_effect-exam_lesson_depend_parameter_buff-1500-01`：「好調の150%分パラメータ上昇」

#### ExamLessonAddMultipleParameterBuff  — rows=41  （无 UI 名称行）

- 语义：パラメータ +v1，其中好調加成按 v2‰ 倍率（“好調効果を2倍適用”）。
- 非零字段：`effectValue1` 41/41, `effectValue2` 41/41, `effectCount` 41/41
  - effectValue1 取值：[4, 7, 8, 9, 10, 12, 13, 15, 16, 18, 20, 21, 22, 23]
  - effectValue2 取值：[500, 700, 1000, 1500, 2000, 2500]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=21, GrowEffect=6, chain=6, StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_lesson_add_multiple_parameter_buff-0004-1000-01", "effectValue1": 4, "effectValue2": 1000, "effectCount": 1}`
  - 文本：「パラメータ+4（好調効果を2倍適用）」
  - 另一例 `e_effect-exam_lesson_add_multiple_parameter_buff-0027-0500-01`：「パラメータ+27（好調効果を1.5倍適用）」

#### ExamBlockPerUseCardCount  — rows=13  （无 UI 名称行）

- 语义：元気 +v1，本场每用 1 张卡 元気增量 +v2。
- 非零字段：`effectValue1` 13/13, `effectValue2` 13/13
  - effectValue1 取值：[2, 3, 4]
  - effectValue2 取值：[3, 4, 5, 6, 8, 9, 10, 12, 13, 14]
- 被谁引用：ProduceCard.playEffects=12, StatusEnchant=3
- 示例行：`{"id": "e_effect-exam_block_per_use_card_count-0002-0003", "effectValue1": 2, "effectValue2": 3}`
  - 文本：「元気+2（レッスン中に使用したスキルカード1枚につき、元気増加量+3）」
  - 另一例 `e_effect-exam_block_per_use_card_count-0002-0013`：「元気+2（レッスン中に使用したスキルカード1枚につき、元気増加量+13）」

#### ExamChainEffect  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### StanceLock  — rows=2  UI名=**指針固定**

- 语义：指針固定 effectTurn 回合（不能变更指針与段数）。
- 说明文（Label_StanceLock）：指針と段階を変更できない / 全力値が10以上の場合でも、効果中は全力にならない / 全力状態の場合は、ターン終了時に全力を解除する
- 非零字段：`effectTurn` 2/2
  - effectTurn 取值：[1, 2]
- 被谁引用：ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-stance_lock-01", "effectTurn": 1}`
  - 文本：「指針固定1ターン」
  - 另一例 `e_effect-stance_lock-02`：「指針固定2ターン」

#### ExamLessonDependStamina  — rows=3  （无 UI 名称行）

- 语义：当前体力 ×v1‰ 的パラメータ。
- 非零字段：`effectValue1` 3/3, `effectCount` 3/3
  - effectValue1 取值：[8000, 10000, 12000]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_lesson_depend_stamina-10000-01", "effectValue1": 10000, "effectCount": 1}`
  - 文本：「体力の1000%分パラメータ上昇」
  - 另一例 `e_effect-exam_lesson_depend_stamina-12000-01`：「体力の1200%分パラメータ上昇」

#### ExamBlockAddMultipleAggressive  — rows=23  （无 UI 名称行）

- 语义：元気 +v1，其中やる気加成按 v2‰ 倍率适用（“やる気効果を1.4倍適用”）。
- 非零字段：`effectValue1` 23/23, `effectValue2` 23/23, `effectCount` 23/23
  - effectValue1 取值：[1, 2, 3, 4, 6, 7, 8, 9, 10, 15, 20]
  - effectValue2 取值：[300, 400, 500, 600, 800, 1000, 1200, 1300, 1400, 1500, 2000]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=15, StatusEnchant=13, Gimmick=3, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_block_add_multiple_aggressive-0001-0400-01", "effectValue1": 1, "effectValue2": 400, "effectCount": 1}`
  - 文本：「元気+1（やる気効果を1.4倍適用）」
  - 另一例 `e_effect-exam_block_add_multiple_aggressive-0004-1500-01`：「元気+4（やる気効果を2.5倍適用）」

#### ExamLessonDependStaminaConsumptionSum  — rows=7  （无 UI 名称行）

- 语义：本场消耗体力总量 ×v1‰ 的パラメータ。
- 非零字段：`effectValue1` 7/7, `effectCount` 7/7
  - effectValue1 取值：[1500, 1800, 2200, 5000, 10000, 15000, 30000]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=18
- 示例行：`{"id": "e_effect-exam_lesson_depend_stamina_consumption_sum-10000-01", "effectValue1": 10000, "effectCount": 1}`
  - 文本：「レッスン中に消費した体力の1000%分パラメータ上昇」
  - 另一例 `e_effect-exam_lesson_depend_stamina_consumption_sum-1800-01`：「レッスン中に消費した体力の180%分パラメータ上昇」

#### ExamChainEffectPerPassedTurn  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamChainEffectPerRemainTurn  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamLessonDependPlayCardCountSum  — rows=11  （无 UI 名称行）

- 语义：パラメータ +v1，本场每用 1 张卡再 +v2。
- 非零字段：`effectValue2` 11/11, `effectCount` 11/11, `effectValue1` 10/11
  - effectValue1 取值：[2, 3, 5, 6, 8, 20]
  - effectValue2 取值：[1, 2, 3, 4, 8, 9, 10, 14]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=9, ProduceCard.playEffects=4, Gimmick=3, chain=1
- 示例行：`{"id": "e_effect-exam_lesson_depend_play_card_count_sum-0002-0001-01", "effectValue1": 2, "effectValue2": 1, "effectCount": 1}`
  - 文本：「パラメータ+2（レッスン中に使用したスキルカード1枚につき、パラメータ上昇量+1）」
  - 另一例 `e_effect-exam_lesson_depend_play_card_count_sum-0005-0002-01`：「パラメータ+5（レッスン中に使用したスキルカード1枚につき、パラメータ上昇量+2）」

#### ExamDebuffRecover  — rows=3  UI名=**低下状態回復**

- 语义：低下状態回復 v1 个（0=全部）。
- 说明文（Label_ExamDebuffRecover）：低下状態を回復する
- 非零字段：`effectValue1` 2/3
  - effectValue1 取值：[1, 2]
- 被谁引用：Gimmick=66, ProduceCard.playEffects=4, StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_debuff_recover"}`
  - 文本：「すべての低下状態回復」
  - 另一例 `e_effect-exam_debuff_recover-0001`：「低下状態回復1」

#### ExamAggressiveValueMultiple  — rows=4  （无 UI 名称行）

- 语义：やる気 ×(1+v1‰)（“やる気1.3倍”）。
- 非零字段：`effectValue1` 4/4
  - effectValue1 取值：[300, 500, 1000, 1500]
- 被谁引用：StatusEnchant=10, ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_aggressive_value_multiple-0300", "effectValue1": 300}`
  - 文本：「やる気1.3倍」
  - 另一例 `e_effect-exam_aggressive_value_multiple-1000`：「やる気2倍」

#### ExamItemFireLimitAdd  — rows=1  （无 UI 名称行）

- 语义：偶像固有 P道具 发动次数 +v1。
- 非零字段：`effectValue1` 1/1
  - effectValue1 取值：[1]
- 被谁引用：StatusEnchant=12
- 示例行：`{"id": "e_effect-exam_item_fire_limit_add-0001", "effectValue1": 1}`
  - 文本：「アイドル固有Pアイテムの発動回数+1」

#### ExamReviewReduce  — rows=2  UI名=**好印象減少**

- 语义：好印象 -v1。
- 说明文（Label_ExamReviewReduce）：好印象を減少させる
- 非零字段：`effectValue1` 2/2
  - effectValue1 取值：[1, 2]
- 被谁引用：StatusEnchant=5
- 示例行：`{"id": "e_effect-exam_review_reduce-0001", "effectValue1": 1}`
  - 文本：「好印象減少1」
  - 另一例 `e_effect-exam_review_reduce-0002`：「好印象減少2」

#### ExamAggressiveReduce  — rows=3  UI名=**やる気減少**

- 语义：やる気 -v1。
- 说明文（Label_ExamAggressiveReduce）：やる気を減少させる
- 非零字段：`effectValue1` 3/3
  - effectValue1 取值：[1, 2, 3]
- 被谁引用：StatusEnchant=9
- 示例行：`{"id": "e_effect-exam_aggressive_reduce-0001", "effectValue1": 1}`
  - 文本：「やる気減少1」
  - 另一例 `e_effect-exam_aggressive_reduce-0002`：「やる気減少2」

#### ExamLessonBuffReduce  — rows=1  UI名=**集中減少**

- 语义：集中 -v1。
- 说明文（Label_ExamLessonBuffReduce）：集中を減少させる
- 非零字段：`effectValue1` 1/1
  - effectValue1 取值：[1]
- 被谁引用：StatusEnchant=7
- 示例行：`{"id": "e_effect-exam_lesson_buff_reduce-0001", "effectValue1": 1}`
  - 文本：「集中減少1」

#### ExamParameterBuffReduce  — rows=2  UI名=**好調減少**

- 语义：好調 -v1 回合。
- 说明文（Label_ExamParameterBuffReduce）：好調を減少させる
- 非零字段：`effectValue1` 2/2
  - effectValue1 取值：[1, 3]
- 被谁引用：StatusEnchant=9
- 示例行：`{"id": "e_effect-exam_parameter_buff_reduce-0001", "effectValue1": 1}`
  - 文本：「好調減少1」
  - 另一例 `e_effect-exam_parameter_buff_reduce-0003`：「好調減少3」

#### ExamLessonValueMultipleDown  — rows=10  UI名=**パラメータ上昇量減少**

- 语义：パラメータ上昇量減少 v1‰，effectTurn。
- 说明文（Label_ExamLessonValueMultipleDown）：パラメータ上昇量減少上昇量を減少（好印象による上昇も含む）
- swap=Swap_Label_ExamLessonValueMultipleDown
- 非零字段：`effectValue1` 9/10, `effectTurn` 9/10, `produceCardSearchId` 1/10, `pickRangeType` 1/10, `produceCardGrowEffectIds` 1/10
  - effectValue1 取值：[200, 500, 600, 750, 800, 1000]
  - effectTurn 取值：[-1, 2, 3, 4, 5]
  - pickRangeType 取值：['All']
- 被谁引用：StatusEnchant=38
- 示例行：`{"id": "e_effect-exam_lesson_value_multiple_down-0200-04", "effectValue1": 200, "effectTurn": 4}`
  - 文本：「パラメータ上昇量減少20%（4ターン）」
  - 另一例 `e_effect-exam_lesson_value_multiple_down-0750-02`：「パラメータ上昇量減少75%（2ターン）」

#### ExamAddGrowEffect  — rows=160  UI名=**成長**

- 语义：成長：对筛选到的卡（pickRange All）附加 produceCardGrowEffectIds（レッスン終了まで）。
- 说明文（Label_ExamAddGrowEffect）：条件を満たすごとに、レッスン終了まで、このスキルカード自身の性能が変化する
- 非零字段：`produceCardSearchId` 160/160, `produceCardGrowEffectIds` 160/160, `pickRangeType` 159/160
  - pickRangeType 取值：['All']
- 被谁引用：StatusEnchant=148, Gimmick=82, ProduceCard.playEffects=69, GrowEffect=24, chain=7, ProduceCard.move=1
- 示例行：`{"id": "e_effect-exam_add_grow_effect-p_card_search-active_skill-deck_all-all-0_0-g_effect-lesson…", "produceCardSearchId": "p_card_search-active_skill-deck_all", "pickRangeType": "ProducePickRangeType_All", "produceCardGrowEffectIds": ["g_effect-lesson_add-10"]}`
  - 文本：「アクティブスキルカードのパラメータ値増加+10」
  - 另一例 `e_effect-exam_add_grow_effect-p_card_search-deck_all-effect_group-visible-exam_concentration-000-all-0_0-g_effect-lesson_add-45-g_effect-cost_add-7`：「強気効果のスキルカードのパラメータ値増加+45・コスト値増加+7」

#### ExamParameterBuffPerSearchCount  — rows=0  （无 UI 名称行）

- 语义：按筛选卡数加好調（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamLessonBuffPerSearchCount  — rows=1  （无 UI 名称行）

- 语义：筛选卡数每 v2‰⁻¹ 张 集中+1（“除外2枚につき集中+1”）。
- 非零字段：`effectValue2` 1/1, `produceCardSearchId` 1/1, `pickRangeType` 1/1
  - effectValue2 取值：[500]
  - pickRangeType 取值：['All']
- 被谁引用：StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_lesson_buff_per_search_count-0500-p_card_search-lost-all-0_0", "effectValue2": 500, "produceCardSearchId": "p_card_search-lost", "pickRangeType": "ProducePickRangeType_All"}`
  - 文本：「除外にあるスキルカード2枚につき、集中+1」

#### ExamReviewPerSearchCount  — rows=4  （无 UI 名称行）

- 语义：筛选卡每张 好印象 +v2‰⁻¹。
- 非零字段：`effectValue2` 4/4, `produceCardSearchId` 4/4, `pickRangeType` 2/4
  - effectValue2 取值：[1000, 2000]
  - pickRangeType 取值：['All']
- 被谁引用：ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_review_per_search_count-1000-p_card_search-deck_grave", "effectValue2": 1000, "produceCardSearchId": "p_card_search-deck_grave"}`
  - 文本：「山札か捨札にあるスキルカード1枚ごとに、好印象+1」
  - 另一例 `e_effect-exam_review_per_search_count-2000-p_card_search-deck_grave`：「山札か捨札にあるスキルカード1枚ごとに、好印象+2」

#### ExamAggressivePerSearchCount  — rows=0  （无 UI 名称行）

- 语义：按筛选卡数每 v2 张 やる気+…（dump 1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamBlockPerSearchCount  — rows=0  （无 UI 名称行）

- 语义：按筛选卡数增加元気（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamFullPowerPointPerSearchCount  — rows=0  （无 UI 名称行）

- 语义：按筛选卡数加全力値（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamLessonDependBlockAndSearchCount  — rows=2  （无 UI 名称行）

- 语义：筛选卡每张 元気×v2‰ 的パラメータ。
- 非零字段：`effectValue2` 2/2, `effectCount` 2/2, `produceCardSearchId` 2/2, `pickRangeType` 2/2
  - effectValue2 取值：[200, 250]
  - effectCount 取值：[1]
  - pickRangeType 取值：['All']
- 被谁引用：StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_lesson_depend_block_and_search_count-0200-01-p_card_search-lost-p_card-02-i…", "effectValue2": 200, "effectCount": 1, "produceCardSearchId": "p_card_search-lost-p_card-02-ido-3_190", "pickRangeType": "ProducePickRangeType_All"}`
  - 文本：「除外にある私を超えて（翔）1枚につき、元気の20%分パラメータ上昇」
  - 另一例 `e_effect-exam_lesson_depend_block_and_search_count-0250-01-p_card_search-lost-p_card-02-ido-3_190-all-0_0`：「除外にある私を超えて（翔）1枚につき、元気の25%分パラメータ上昇」

#### ExamLessonDependAggressiveAndSearchCount  — rows=0  （无 UI 名称行）

- 语义：筛选卡每张 やる気×v2‰ 的パラメータ。
- dump 中无 ProduceExamEffect 行。

#### ExamLessonDependReviewAndSearchCount  — rows=0  （无 UI 名称行）

- 语义：筛选卡每张 好印象×v2‰ 的パラメータ。
- dump 中无 ProduceExamEffect 行。

#### ExamEffectPerSearchCount  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamOverPreservation  — rows=1  UI名=**のんびり**

- 语义：指針→のんびり（温存 3 段）。
- 说明文（Label_ExamOverPreservation_Produce）：指針をのんびりに変更する / パラメータ上昇量と消費体力を100%減少 / 解除されたとき、固定元気+5・スキルカード使用数追加+1 / 強気に変更または解除した場合、熱意+10 / 全力に変更した場合、すべてのスキルカードのパラメータ値増加+10 /  / のんびりは温存3段階目に相当し、のんびりから温存には変更できない / 温存からのんびりに変更した場合、温存解除時の効果は発生しない
- 考试内说明（Label_ExamOverPreservation_Exam）：パラメータ上昇量と消費体力を100%減少 / 解除されたとき、固定元気+5・スキルカード使用数追加+1 / 強気に変更または解除した場合、熱意+10 / 全力に変更した場合、すべてのスキルカードのパラメータ値増加+10 /  / のんびりは温存3段階目に相当し、のんびりから温存には変更できない / 温存からのんびりに変更した場合、温存解除時の効果は発生しない
- 非零字段：
- 被谁引用：StatusEnchant=8
- 示例行：`{"id": "e_effect-exam_over_preservation"}`
  - 文本：「のんびりに変更」

#### ExamParameterBuffDependLessonBuff  — rows=4  （无 UI 名称行）

- 语义：集中 ×v1‰ 的好調回合（v2 存在时集中减半）。
- 非零字段：`effectValue1` 4/4, `effectCount` 4/4, `effectValue2` 3/4
  - effectValue1 取值：[500, 750, 1000, 2000]
  - effectValue2 取值：[500, 1000]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=8
- 示例行：`{"id": "e_effect-exam_parameter_buff_depend_lesson_buff-0500-01", "effectValue1": 500, "effectCount": 1}`
  - 文本：「集中の50%分好調増加」
  - 另一例 `e_effect-exam_parameter_buff_depend_lesson_buff-1000-0500-01`：「集中の100%分好調増加させ、集中を半分にする」

#### ExamAggressiveDependReview  — rows=0  （无 UI 名称行）

- 语义：按好印象比例增加やる気（dump 1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamEnthusiasticAdditive  — rows=31  UI名=**熱意追加**

- 语义：熱意追加 +v1（固定值），effectTurn(-1)。
- 说明文（Label_ExamEnthusiasticAdditive）：熱意の増加量を増加
- 非零字段：`effectValue1` 31/31, `effectTurn` 31/31
  - effectValue1 取值：[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
  - effectTurn 取值：[-1, 1, 2]
- 被谁引用：ProduceCard.playEffects=16, StatusEnchant=15, Gimmick=1
- 示例行：`{"id": "e_effect-exam_enthusiastic_additive-0001-inf", "effectValue1": 1, "effectTurn": -1}`
  - 文本：「熱意追加+1」
  - 另一例 `e_effect-exam_enthusiastic_additive-0011-inf`：「熱意追加+11」

#### ExamEnthusiasticMultiple  — rows=32  UI名=**熱意増加**

- 语义：熱意増加 +v1‰。
- 说明文（Label_ExamEnthusiasticMultiple）：熱意の増加量を増加
- 非零字段：`effectValue1` 32/32, `effectTurn` 32/32
  - effectValue1 取值：[100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400]
  - effectTurn 取值：[-1, 1, 3]
- 被谁引用：ProduceCard.playEffects=13, StatusEnchant=11
- 示例行：`{"id": "e_effect-exam_enthusiastic_multiple-0100-inf", "effectValue1": 100, "effectTurn": -1}`
  - 文本：「熱意増加+10%」
  - 另一例 `e_effect-exam_enthusiastic_multiple-1200-inf`：「熱意増加+120%」

#### ExamFullPowerLessonMultipleAdditive  — rows=3  UI名=**全力強化**

- 语义：全力強化：全力倍率再 +v1‰，effectTurn。
- 说明文（Label_ExamFullPowerLessonMultipleAdditive）：全力によるパラメータ上昇量を増加
- 非零字段：`effectValue1` 3/3, `effectTurn` 3/3
  - effectValue1 取值：[200, 250, 350]
  - effectTurn 取值：[-1, 4]
- 被谁引用：StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_full_power_lesson_multiple_additive-0200-04", "effectValue1": 200, "effectTurn": 4}`
  - 文本：「全力強化+20%（4ターン）」
  - 另一例 `e_effect-exam_full_power_lesson_multiple_additive-0250-inf`：「全力強化+25%」

#### ExamConcentrationLessonMultipleAdditive  — rows=2  UI名=**強気強化**

- 语义：強気強化：強気倍率再 +v1‰。
- 说明文（Label_ExamConcentrationLessonMultipleAdditive）：強気によるパラメータ上昇量を増加
- 非零字段：`effectValue1` 2/2, `effectTurn` 2/2
  - effectValue1 取值：[350, 600]
  - effectTurn 取值：[-1]
- 被谁引用：StatusEnchant=2
- 示例行：`{"id": "e_effect-exam_concentration_lesson_multiple_additive-0350-inf", "effectValue1": 350, "effectTurn": -1}`
  - 文本：「強気強化+35%」
  - 另一例 `e_effect-exam_concentration_lesson_multiple_additive-0600-inf`：「強気強化+60%」

#### ExamLessonBuffAdditive  — rows=11  UI名=**集中増加量増加**

- 语义：集中増加量増加 +v1‰，effectTurn。
- 说明文（Label_ExamLessonBuffAdditive）：集中の増加量を増加
- 非零字段：`effectValue1` 11/11, `effectTurn` 11/11
  - effectValue1 取值：[100, 250, 500, 1000]
  - effectTurn 取值：[-1, 2, 3, 4, 5, 6]
- 被谁引用：StatusEnchant=19, ProduceCard.playEffects=6, Gimmick=2
- 示例行：`{"id": "e_effect-exam_lesson_buff_additive-0100-inf", "effectValue1": 100, "effectTurn": -1}`
  - 文本：「集中増加量増加+10%」
  - 另一例 `e_effect-exam_lesson_buff_additive-0250-inf`：「集中増加量増加+25%」

#### ExamParameterBuffAdditive  — rows=7  UI名=**好調増加量増加**

- 语义：好調増加量増加 +v1‰。
- 说明文（Label_ExamParameterBuffAdditive）：好調の増加量を増加
- 非零字段：`effectValue1` 7/7, `effectTurn` 7/7
  - effectValue1 取值：[250, 500, 1000]
  - effectTurn 取值：[-1, 3, 4, 5]
- 被谁引用：StatusEnchant=6, ProduceCard.playEffects=1
- 示例行：`{"id": "e_effect-exam_parameter_buff_additive-0250-03", "effectValue1": 250, "effectTurn": 3}`
  - 文本：「好調増加量増加+25%（3ターン）」
  - 另一例 `e_effect-exam_parameter_buff_additive-0500-04`：「好調増加量増加+50%（4ターン）」

#### ExamAggressiveAdditive  — rows=5  UI名=**やる気増加量増加**

- 语义：やる気増加量増加 +v1‰。
- 说明文（Label_ExamAggressiveAdditive）：やる気の増加量を増加
- 非零字段：`effectValue1` 5/5, `effectTurn` 5/5
  - effectValue1 取值：[250, 500, 750]
  - effectTurn 取值：[1, 2, 3]
- 被谁引用：StatusEnchant=9, ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_aggressive_additive-0250-03", "effectValue1": 250, "effectTurn": 3}`
  - 文本：「やる気増加量増加+25%（3ターン）」
  - 另一例 `e_effect-exam_aggressive_additive-0500-02`：「やる気増加量増加+50%（2ターン）」

#### ExamReviewAdditive  — rows=7  UI名=**好印象増加量増加**

- 语义：好印象増加量増加 +v1‰。
- 说明文（Label_ExamReviewAdditive）：好印象の増加量を増加
- 非零字段：`effectValue1` 7/7, `effectTurn` 7/7
  - effectValue1 取值：[250, 500, 750, 1000]
  - effectTurn 取值：[-1, 1, 2, 3, 5]
- 被谁引用：StatusEnchant=11, ProduceCard.playEffects=8
- 示例行：`{"id": "e_effect-exam_review_additive-0250-03", "effectValue1": 250, "effectTurn": 3}`
  - 文本：「好印象増加量増加+25%（3ターン）」
  - 另一例 `e_effect-exam_review_additive-0500-05`：「好印象増加量増加+50%（5ターン）」

#### ExamFullPowerPointAdditive  — rows=5  UI名=**全力値増加量増加**

- 语义：全力値増加量増加 +v1‰。
- 说明文（Label_ExamFullPowerPointAdditive）：全力値の増加量を増加
- 非零字段：`effectValue1` 5/5, `effectTurn` 5/5
  - effectValue1 取值：[250, 500]
  - effectTurn 取值：[1, 3, 4]
- 被谁引用：ProduceCard.playEffects=4, StatusEnchant=4, chain=1
- 示例行：`{"id": "e_effect-exam_full_power_point_additive-0250-01", "effectValue1": 250, "effectTurn": 1}`
  - 文本：「全力値増加量増加+25%（1ターン）」
  - 另一例 `e_effect-exam_full_power_point_additive-0500-01`：「全力値増加量増加+50%（1ターン）」

#### ExamGrowEffectLessonAddAdditive  — rows=0  UI名=**パラメータ上昇値増加量増加**

- 语义：（定义，无行）。
- 说明文（Label_ExamGrowEffectLessonAddAdditive）：パラメータ上昇値増加量増加の増加量を増加
- swap=Swap_Label_ExamGrowEffectLessonAddAdditive
- dump 中无 ProduceExamEffect 行。

#### ExamParameterBuffMultiplePerTurnReduce  — rows=1  UI名=**絶好調減少**

- 语义：絶好調 -v1。
- 说明文（Label_ExamParameterBuffMultiplePerTurnReduce）：絶好調を減少させる
- 非零字段：`effectValue1` 1/1
  - effectValue1 取值：[1]
- 被谁引用：StatusEnchant=1
- 示例行：`{"id": "e_effect-exam_parameter_buff_multiple_per_turn_reduce-0001", "effectValue1": 1}`
  - 文本：「絶好調減少1」

#### ExamLessonValueMultipleDependReviewOrAggressive  — rows=3  UI名=**プライド**

- 语义：プライド effectTurn 回合：min(好印象,やる気)×2%（上限 50%）参数加成。
- 说明文（Label_ExamLessonValueMultipleDependReviewOrAggressive）：やる気か好印象の最小値に応じて、1ごとに、パラメータ上昇量を2%増加（最大50%）
- 非零字段：`effectTurn` 3/3
  - effectTurn 取值：[2, 3, 5]
- 被谁引用：ProduceCard.playEffects=4, StatusEnchant=4
- 示例行：`{"id": "e_effect-exam_lesson_value_multiple_depend_review_or_aggressive-02", "effectTurn": 2}`
  - 文本：「プライド（2ターン）」
  - 另一例 `e_effect-exam_lesson_value_multiple_depend_review_or_aggressive-03`：「プライド（3ターン）」

#### ExamReviewMultiple  — rows=18  UI名=**好印象強化**

- 语义：好印象強化 +v1‰（好印象带来的参数上升倍率），effectTurn。
- 说明文（Label_ExamReviewMultiple）：好印象によるパラメータ上昇量を増加
- 非零字段：`effectValue1` 18/18, `effectTurn` 18/18
  - effectValue1 取值：[100, 200, 250, 300, 500, 600, 700, 1000, 2000, 2700]
  - effectTurn 取值：[-1, 1, 3, 4, 5]
- 被谁引用：ProduceCard.playEffects=26, StatusEnchant=12, Gimmick=2, GrowEffect=1
- 示例行：`{"id": "e_effect-exam_review_multiple-0100-inf", "effectValue1": 100, "effectTurn": -1}`
  - 文本：「好印象強化+10%」
  - 另一例 `e_effect-exam_review_multiple-0500-05`：「好印象強化+50%（5ターン）」

#### ExamMultipleEnthusiasticLesson  — rows=3  （无 UI 名称行）

- 语义：パラメータ +v1，熱意效果 ×v2‰。
- 非零字段：`effectValue1` 3/3, `effectValue2` 3/3, `effectCount` 3/3
  - effectValue1 取值：[1, 3, 5]
  - effectValue2 取值：[1000]
  - effectCount 取值：[1]
- 被谁引用：ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_multiple_enthusiastic_lesson-0001-1000-01", "effectValue1": 1, "effectValue2": 1000, "effectCount": 1}`
  - 文本：「パラメータ+1（熱意効果を2倍適用）」
  - 另一例 `e_effect-exam_multiple_enthusiastic_lesson-0003-1000-01`：「パラメータ+3（熱意効果を2倍適用）」

#### ExamMultipleConcentrationLesson  — rows=0  （无 UI 名称行）

- 语义：強気效果倍率适用（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamMultipleFullPowerLesson  — rows=0  （无 UI 名称行）

- 语义：全力效果倍率适用（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamLessonDependBlockConsumptionSum  — rows=7  （无 UI 名称行）

- 语义：本场消耗元気总量 ×v1‰ 的パラメータ。
- 非零字段：`effectValue1` 7/7, `effectCount` 7/7
  - effectValue1 取值：[900, 1000, 1200, 1500, 1700, 2200, 4000]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=2, ProduceCard.playEffects=1
- 示例行：`{"id": "e_effect-exam_lesson_depend_block_consumption_sum-0900-01", "effectValue1": 900, "effectCount": 1}`
  - 文本：「レッスン中に消費した元気の90%分パラメータ上昇」
  - 另一例 `e_effect-exam_lesson_depend_block_consumption_sum-1500-01`：「レッスン中に消費した元気の150%分パラメータ上昇」

#### ExamForcePlayCardSearchWithCost  — rows=1  （无 UI 名称行）

- 语义：选择一张卡付费使用。
- 非零字段：`produceCardSearchId` 1/1, `pickRangeType` 1/1, `pickCountMin` 1/1, `pickCountMax` 1/1
  - pickRangeType 取值：['Select']
  - pickCountMin 取值：[1]
  - pickCountMax 取值：[1]
- 被谁引用：StatusEnchant=1
- 示例行：`{"id": "e_effect-exam_force_play_card_search_with_cost-p_card_search-not_lost-select-1_1", "produceCardSearchId": "p_card_search-not_lost", "pickRangeType": "ProducePickRangeType_Select", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本：「除外以外のスキルカードを1枚選択し、コストを消費して使用」

#### ExamBlockDependBlockConsumptionSum  — rows=3  （无 UI 名称行）

- 语义：本场消耗元気总量 ×v1‰ 的元気。
- 非零字段：`effectValue1` 3/3, `effectCount` 3/3
  - effectValue1 取值：[750, 800, 1000]
  - effectCount 取值：[1]
- 被谁引用：StatusEnchant=3
- 示例行：`{"id": "e_effect-exam_block_depend_block_consumption_sum-0750-01", "effectValue1": 750, "effectCount": 1}`
  - 文本：「レッスン中に消費した元気の75%分元気増加」
  - 另一例 `e_effect-exam_block_depend_block_consumption_sum-0800-01`：「レッスン中に消費した元気の80%分元気増加」

#### ExamEnthusiasticTurnAdd  — rows=0  （无 UI 名称行）

- 语义：熱意回合延长（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamEffectTimerEndTurn  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamStanceLockConcentration  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamStanceLockFullPower  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamStanceLockPreservation  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamCardShuffleDeckGrave  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamReviewCountAdd  — rows=1  UI名=**好印象追加発動**

- 语义：好印象追加発動 +v1（回合末好印象结算次数），effectTurn。
- 说明文（Label_ExamReviewCountAdd_Produce）：ターン終了時に発生する好印象によるパラメータ上昇回数を増加
- 考试内说明（Label_ExamReviewCountAdd_Exam）：ターン終了時に発生する好印象によるパラメータ上昇回数を回増加
- 非零字段：`effectValue1` 1/1, `effectTurn` 1/1
  - effectValue1 取值：[1]
  - effectTurn 取值：[3]
- 被谁引用：StatusEnchant=1
- 示例行：`{"id": "e_effect-exam_review_count_add-0001-03", "effectValue1": 1, "effectTurn": 3}`
  - 文本：「好印象追加発動+1（3ターン）」

#### ExamReviewTurnEndReduceLock  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamParameterBuffTurnEndReduceLock  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamBuffConsumptionDown  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamBuffConsumptionAdd  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamSearchPlayCardBuffConsumptionChange  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamPlayCardLimitPlayableValueAdd  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamReviewDependReviewConsumptionSum  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamLessonBuffReduceCancellable  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamParameterBuffReduceCancellable  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamAggressiveReduceCancellable  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamReviewReduceCancellable  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamFullPowerPointReduceCancellable  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamStatusEnchantTurnAdd  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamStatusEnchantCountAdd  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamParameterBuffAdditiveFix  — rows=0  UI名=**好調増加量追加**

- 语义：好調増加量追加 +v1（固定）（定义，无行）。
- 说明文（Label_ExamParameterBuffAdditiveFix）：好調の増加量を追加
- dump 中无 ProduceExamEffect 行。

#### ExamLessonBuffAdditiveFix  — rows=2  UI名=**集中増加量追加**

- 语义：集中増加量追加 +v1（固定），effectTurn。
- 说明文（Label_ExamLessonBuffAdditiveFix）：集中の増加量を追加
- 非零字段：`effectValue1` 2/2, `effectTurn` 2/2
  - effectValue1 取值：[1, 2]
  - effectTurn 取值：[2, 4]
- 被谁引用：ProduceCard.playEffects=8
- 示例行：`{"id": "e_effect-exam_lesson_buff_additive_fix-0001-04", "effectValue1": 1, "effectTurn": 4}`
  - 文本：「集中増加量追加+1（4ターン）」
  - 另一例 `e_effect-exam_lesson_buff_additive_fix-0002-02`：「集中増加量追加+2（2ターン）」

#### ExamAggressiveAdditiveFix  — rows=1  UI名=**やる気増加量追加**

- 语义：やる気増加量追加 +v1。
- 说明文（Label_ExamAggressiveAdditiveFix）：やる気の増加量を追加
- 非零字段：`effectValue1` 1/1, `effectTurn` 1/1
  - effectValue1 取值：[1]
  - effectTurn 取值：[2]
- 被谁引用：ProduceCard.playEffects=4
- 示例行：`{"id": "e_effect-exam_aggressive_additive_fix-0001-02", "effectValue1": 1, "effectTurn": 2}`
  - 文本：「やる気増加量追加+1（2ターン）」

#### ExamReviewAdditiveFix  — rows=0  UI名=**好印象増加量追加**

- 语义：（定义，无行）。
- 说明文（Label_ExamReviewAdditiveFix）：やる気の増加量を追加
- dump 中无 ProduceExamEffect 行。

#### ExamFullPowerPointAdditiveFix  — rows=0  UI名=**全力値増加量追加**

- 语义：（定义，无行）。
- 说明文（Label_ExamFullPowerPointAdditiveFix）：全力値の増加量を追加
- dump 中无 ProduceExamEffect 行。

#### ExamMoveGrowEffect  — rows=0  （无 UI 名称行）

- 语义：移动成长效果（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamLessonDependEnthusiasticGetSum  — rows=0  （无 UI 名称行）

- 语义：本场累计熱意 比例的パラメータ（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamCardShuffleDeckLost  — rows=0  （无 UI 名称行）

- dump 中无 ProduceExamEffect 行。

#### ExamFullPowerPointDependFullPowerPointGetSum  — rows=0  （无 UI 名称行）

- 语义：按累计全力値加全力値（1 行）。
- dump 中无 ProduceExamEffect 行。

#### ExamStatusEnchantEncore  — rows=5  UI名=**再演**

- 语义：再演：挂载 produceExamStatusEnchantId，条件满足时再次使用自身（不付费用），effectCount 次、每回合 1 次；isOncePlayEffect。
- 说明文（Label_ExamStatusEnchantEncore）：再演は、レッスン中、初めて自身を使用した時にのみ発動する / 以降のレッスン中、指定の条件を満たした時、ターン内に1回まで、自身を再使用（スキルカードコストは消費はしない）
- 非零字段：`effectValue1` 5/5, `effectCount` 5/5, `effectTurn` 5/5, `produceExamStatusEnchantId` 5/5
  - effectValue1 取值：[1]
  - effectCount 取值：[2, 3, 4]
  - effectTurn 取值：[-1]
- 被谁引用：ProduceCard.playEffects=20
- 示例行：`{"id": "e_effect-exam_status_enchant_encore-0001-02-inf-enchant-p_card-01-ido-3_202-enc02", "effectValue1": 1, "effectCount": 2, "effectTurn": -1, "produceExamStatusEnchantId": "enchant-p_card-01-ido-3_202-enc02"}`
  - 文本：「レッスン終了まで、2ターンごとに、体力が80%以上の場合、自身を再使用（2回まで発動・ターン内1回まで）」
  - 另一例 `e_effect-exam_status_enchant_encore-0001-02-inf-enchant-p_card-02-ido-3_201-enc01`：「レッスン終了まで、直接効果でやる気が5回増加時、自身を再使用（2回まで発動・ターン内1回まで）」

### 2.2 ProduceExamPhaseType / ProduceExamFieldStatusType（触发时机与条件）

#### ProduceExamPhaseType 各时机的触发器示例

- **Unknown**（0 个触发器；phaseValues 分布 —）：
- **ExamCardDraw**（0 个触发器；phaseValues 分布 —）：
- **ExamCardPlay**（82 个触发器；phaseValues 分布 {(): 81, (0,): 1}）：スキルカード使用時（结算前；配合 produceCardSearch=playing 表示“使用的是 X 卡”）。
  - `e_trigger-exam_card_play-block_up-15-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用時、元気が15以上の場合、」 / 使用条件文案「元気が15以上の場合、使用可」
  - `e_trigger-exam_card_play-block_up-15-p_card_search-playing-idol-unique-0_1` → 「アイドル固有スキルカード使用時、元気が15以上の場合、」 / 使用条件文案「元気が15以上の場合、使用可」
- **ExamCardPlayAfter**（194 个触发器；phaseValues 分布 {(): 193, (0,): 1}）：スキルカード使用後（结算后）。
  - `e_trigger-exam_card_play_after` → 「スキルカード使用後、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_card_play_after-block_up-30-p_card_search-mental_skill-playing-0_1` → 「メンタルスキルカード使用後、元気が30以上の場合、」 / 使用条件文案「元気が30以上の場合、使用可」
- **ExamStartTurn**（95 个触发器；phaseValues 分布 {(): 95}）：ターン開始時（发牌前）。
  - `e_trigger-exam_start_turn` → 「ターン開始時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_start_turn-block_up-14` → 「ターン開始時、元気が14以上の場合、」 / 使用条件文案「元気が14以上の場合、使用可」
- **ExamEndTurn**（65 个触发器；phaseValues 分布 {(): 65}）：ターン終了時。
  - `e_trigger-exam_end_turn` → 「ターン終了時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_end_turn-block_up-12` → 「ターン終了時、元気が12以上の場合、」 / 使用条件文案「元気が12以上の場合、使用可」
- **ExamStartExam**（12 个触发器；phaseValues 分布 {(): 12}）：レッスン/試験 开始时。
  - `e_trigger-exam_start_exam` → 「レッスン開始時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_start_exam-card_search_count_up-21-p_card_search-r-sr-ssr-legend-deck_all` → 「レッスン開始時、スキルカード（R以上）が21枚以上の場合、」 / 使用条件文案「スキルカード（R以上）が21枚以上の場合、使用可」
- **ExamCardMove**（0 个触发器；phaseValues 分布 —）：
- **ExamCardAdd**（0 个触发器；phaseValues 分布 —）：
- **ExamLesson**（0 个触发器；phaseValues 分布 —）：
- **ExamForecast**（0 个触发器；phaseValues 分布 —）：
- **ExamSearchCardPlay**（2 个触发器；phaseValues 分布 {(): 2}）：使用符合筛选的卡时（2 行，描述未定义）。
  - `e_trigger-exam_search_card_play-full_power_up-p_card_search-target_is_self-0_1` → 「未定義のパターン(Type: ExamSearchCardPlay, PhaseValue: 0, ProduceCardSearchID: p_card_search-target_is_self, UpperCount: 0, LowerCount: 1)全力の場合、」 / 使用条件文案「全力の場合、使用可」
  - `e_trigger-exam_search_card_play-p_card_search-target_is_self-0_1` → 「未定義のパターン(Type: ExamSearchCardPlay, PhaseValue: 0, ProduceCardSearchID: p_card_search-target_is_self, UpperCount: 0, LowerCount: 1)」 / 使用条件文案「の場合、使用可」
- **ExamStanceChange**（0 个触发器；phaseValues 分布 —）：
- **ExamStatusChange**（28 个触发器；phaseValues 分布 {(30,): 1, (6,): 1, (7,): 3, (): 23}）：直接効果で X が N 以上増加後（effectTypes+phaseValue）。
  - `e_trigger-exam_status_change-30-exam_block` → 「直接効果で元気が30以上増加後、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_status_change-6-exam_review` → 「直接効果で好印象が6以上増加後、」 / 使用条件文案「の場合、使用可」
- **ExamTurnCheck**（0 个触发器；phaseValues 分布 —）：
- **ExamUseDrink**（0 个触发器；phaseValues 分布 —）：
- **ExamGetPoint**（0 个触发器；phaseValues 分布 —）：
- **ExamShuffle**（0 个触发器；phaseValues 分布 —）：
- **ExamStaminaReduce**（1 个触发器；phaseValues 分布 {(): 1}）：直接効果で体力が減少した時。
  - `e_trigger-exam_stamina_reduce` → 「直接効果で体力が減少した時、」 / 使用条件文案「の場合、使用可」
- **ExamTurnTimer**（19 个触发器；phaseValues 分布 {(1,): 3, (10,): 2, (11,): 1, (12,): 1, (2,): 1, (3,): 3, (4,): 1, (5,): 3, (7,): 1, (8,): 2, (9,): 1}）：第 N 回合开始时（phaseValue=N；用于 ExamEffectTimer 延迟）。
  - `e_trigger-exam_turn_timer-1` → 「」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_turn_timer-1-description` → 「1ターン目開始時、」 / 使用条件文案「の場合、使用可」
- **ExamTurnInterval**（12 个触发器；phaseValues 分布 {(2,): 6, (3,): 5, (4,): 1}）：每 N 回合（回合开始）。
  - `e_trigger-exam_turn_interval-2` → 「2ターンごとに、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_turn_interval-2-block_up-30` → 「2ターンごとに、元気が30以上の場合、」 / 使用条件文案「元気が30以上の場合、使用可」
- **ExamPlayCountInterval**（26 个触发器；phaseValues 分布 {(2,): 9, (3,): 11, (4,): 5, (5,): 1}）：每使用 N 张卡时。
  - `e_trigger-exam_play_count_interval-2` → 「スキルカードを2回使用するごとに、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_play_count_interval-2-card_play_aggressive_up-6-p_card_search-active_skill-target` → 「やる気が6以上の場合、アクティブスキルカードを2回使用するごとに、」 / 使用条件文案「やる気が6以上の場合、使用可」
- **ExamStaminaReduceCard**（2 个触发器；phaseValues 分布 {(): 2}）：スキルカードコストで体力減少時。
  - `e_trigger-exam_stamina_reduce_card` → 「スキルカードコストで体力減少時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_stamina_reduce_card-lesson_visual` → 「【ビジュアルレッスン・ビジュアルターンのみ】スキルカードコストで体力減少時、」 / 使用条件文案「の場合、使用可」
- **ExamPlayTurnCountInterval**（8 个触发器；phaseValues 分布 {(2,): 7, (3,): 1}）：回合内每使用 N 张（筛选）卡。
  - `e_trigger-exam_play_turn_count_interval-2-p_card_search-mental_skill-target` → 「ターン内にメンタルスキルカードを2回使用するごとに、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_play_turn_count_interval-2-p_card_search-mental_skill-target-_` → 「ターン内にメンタルスキルカードを2回使用するごとに、」 / 使用条件文案「の場合、使用可」
- **StartPlay**（23 个触发器；phaseValues 分布 {(): 23}）：ターン開始後（发牌后、可出牌时）。
  - `e_trigger-start_play` → 「ターン開始後、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-start_play-card_play_aggressive_up-5` → 「ターン開始後、やる気が5以上の場合、」 / 使用条件文案「やる気が5以上の場合、使用可」
- **StartExamPlay**（1 个触发器；phaseValues 分布 {(): 1}）：レッスン開始後（首回合发牌后）。
  - `e_trigger-start_exam_play` → 「レッスン開始後、」 / 使用条件文案「の場合、使用可」
- **ExamCardMoveHand**（1 个触发器；phaseValues 分布 {(): 1}）：手札に移動した時。
  - `e_trigger-exam_card_move_hand-p_card_search-target_is_self` → 「自身が手札に移動した時、」 / 使用条件文案「の場合、使用可」
- **ExamCardMoveGrave**（1 个触发器；phaseValues 分布 {(): 1}）：（自身）捨札に移動した時。
  - `e_trigger-exam_card_move_grave-p_card_search-target_is_self` → 「自身が捨て札に移動した時、」 / 使用条件文案「の場合、使用可」
- **ExamCardMoveLost**（2 个触发器；phaseValues 分布 {(): 2}）：除外に移動した時。
  - `e_trigger-exam_card_move_lost-p_card_search-target` → 「スキルカードが除外に移動した時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_card_move_lost-p_card_search-target-_` → 「スキルカードが除外に移動した時、」 / 使用条件文案「の場合、使用可」
- **ExamLessonParameterUp**（0 个触发器；phaseValues 分布 —）：
- **ExamBuffConsume**（7 个触发器；phaseValues 分布 {(): 6, (0,): 1}）：スキルカードコストで強化状態を消費した時（好調/集中等作费用）。
  - `e_trigger-exam_buff_consume` → 「スキルカードコストで強化状態を消費した時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_buff_consume-lesson_buff_up-13` → 「スキルカードコストで強化状態を消費した時、集中が13以上の場合、」 / 使用条件文案「集中が13以上の場合、使用可」
- **ExamStanceChangeCountInterval**（3 个触发器；phaseValues 分布 {(1,): 1, (2,): 1, (3,): 1}）：直接効果で指針を N 回変更するたび。
  - `e_trigger-exam_stance_change_count_interval-1` → 「直接効果で指針を変更するたび、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_stance_change_count_interval-2` → 「直接効果で指針を2回変更するたび、」 / 使用条件文案「の場合、使用可」
- **ExamStanceChangeCount**（0 个触发器；phaseValues 分布 —）：
- **ExamStanceChangeConcentration**（6 个触发器；phaseValues 分布 {(): 5, (2,): 1}）：直接効果で強気になった時（phaseValue=段）。
  - `e_trigger-exam_stance_change_concentration` → 「直接効果で強気になった時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_stance_change_concentration-2` → 「直接効果で強気2段階目になった時、」 / 使用条件文案「の場合、使用可」
- **ExamStanceChangePreservation**（1 个触发器；phaseValues 分布 {(): 1}）：温存になった時。
  - `e_trigger-exam_stance_change_preservation` → 「直接効果で温存になった時、」 / 使用条件文案「の場合、使用可」
- **ExamStanceChangeFullPower**（6 个触发器；phaseValues 分布 {(): 6}）：全力になった時。
  - `e_trigger-exam_stance_change_full_power` → 「全力になった時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_stance_change_full_power-block_up-30` → 「全力になった時、元気が30以上の場合、」 / 使用条件文案「元気が30以上の場合、使用可」
- **ExamStanceReset**（0 个触发器；phaseValues 分布 —）：
- **ExamTurnSkip**（2 个触发器；phaseValues 分布 {(): 2}）：ターンスキップ時。
  - `e_trigger-exam_turn_skip` → 「ターンスキップ時、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_turn_skip-parameter_buff_multiple_per_turn_up-1` → 「ターンスキップ時、絶好調状態の場合、」 / 使用条件文案「絶好調状態の場合、使用可」
- **ExamEndTurnTimer**（0 个触发器；phaseValues 分布 —）：
- **ExamEndTurnInterval**（2 个触发器；phaseValues 分布 {(2,): 1, (3,): 1}）：每 N 回合的回合结束时（phaseValue=N）。
  - `e_trigger-exam_end_turn_interval-2-not-card_search_count_up-9-p_card_search-lost` → 「2ターンごとのターン終了時、除外にあるスキルカードが8枚以下の場合、」 / 使用条件文案「除外にあるスキルカードが8枚以下の場合、使用可」
  - `e_trigger-exam_end_turn_interval-3` → 「3ターンごとのターン終了時、」 / 使用条件文案「の場合、使用可」
- **ExamPlayCountIntervalAfter**（5 个触发器；phaseValues 分布 {(2,): 2, (3,): 2, (4,): 1}）：使用后每 N 张。
  - `e_trigger-exam_play_count_interval_after-2-not-parameter_buff_up-21` → 「好調が20ターン以下の場合、スキルカード使用後2回ごとに、」 / 使用条件文案「好調が20ターン以下の場合、使用可」
  - `e_trigger-exam_play_count_interval_after-2-p_card_search-active_skill-target` → 「アクティブスキルカード使用後2回ごとに、」 / 使用条件文案「の場合、使用可」
- **ExamStanceChangeFromConcentration**（1 个触发器；phaseValues 分布 {(): 1}）：強気を解除後。
  - `e_trigger-exam_stance_change_from_concentration-full_power_up` → 「直接効果で強気を解除後、全力の場合、」 / 使用条件文案「全力の場合、使用可」
- **ExamStanceChangeFromPreservation**（0 个触发器；phaseValues 分布 —）：
- **ExamStanceChangeFromFullPower**（5 个触发器；phaseValues 分布 {(): 5}）：全力を解除後。
  - `e_trigger-exam_stance_change_from_full_power` → 「全力を解除後、」 / 使用条件文案「の場合、使用可」
  - `e_trigger-exam_stance_change_from_full_power-card_search_count_up-1-p_card_search-lost-p_card-03-ido-3_144` → 「全力を解除後、除外にあるでこれーとまじっくが1枚以上の場合、」 / 使用条件文案「除外にあるでこれーとまじっくが1枚以上の場合、使用可」
- **ExamCardUpgrade**（0 个触发器；phaseValues 分布 —）：
- **ExamPlayCardMoveGrave**（0 个触发器；phaseValues 分布 —）：
- **ExamParameterBuffUpInterval**（0 个触发器；phaseValues 分布 —）：
- **ExamLessonBuffUpInterval**（0 个触发器；phaseValues 分布 —）：
- **ExamReviewUpInterval**（0 个触发器；phaseValues 分布 —）：
- **ExamAggressiveUpInterval**（1 个触发器；phaseValues 分布 {(5,): 1}）：直接効果でやる気が N 回増加時。
  - `e_trigger-exam_aggressive_up_interval-5-exam_card_play_aggressive` → 「直接効果でやる気が5回増加時、」 / 使用条件文案「の場合、使用可」
- **ExamFullPowerPointUpInterval**（0 个触发器；phaseValues 分布 —）：
- **ExamStanceChangePreservationInterval**（0 个触发器；phaseValues 分布 —）：
- **ExamStanceChangeConcentrationInterval**（0 个触发器；phaseValues 分布 —）：
- **ExamStanceChangeFullPowerInterval**（0 个触发器；phaseValues 分布 —）：
- **ExamCardUpgradeInterval**（0 个触发器；phaseValues 分布 —）：
- **ExamCardDrawInterval**（0 个触发器；phaseValues 分布 —）：
- **None**（63 个触发器；phaseValues 分布 {(): 63}）：无时机，纯条件（用于 playProduceExamTriggerId 使用条件、GrowEffect 的条件）。
  - `e_trigger-none-block_up-15` → 「元気が15以上の場合、」 / 使用条件文案「元気が15以上の場合、使用可」
  - `e_trigger-none-block_up-30` → 「元気が30以上の場合、」 / 使用条件文案「元気が30以上の場合、使用可」

#### ProduceExamFieldStatusType 各条件的触发器示例

- **Unknown**（触发器 0，阈值分布 —；Gimmick 中 {'Unknown': 791}）：无条件。
- **ParameterBuff**（触发器 10，阈值分布 {None: 9, 1: 1}；Gimmick 中 {'Unknown': 215, 'Not': 76}）：好調状態（Not=非好調）。
  - `e_trigger-exam_card_play-parameter_buff` → 「スキルカード使用時、好調状態の場合、」
  - `e_trigger-exam_end_turn-not-parameter_buff` → 「ターン終了時、非好調状態の場合、」
- **StaminaUpMultiple**（触发器 24，阈值分布 {500: 13, 800: 6, 100: 1, 1000: 2, 130: 1, 60: 1}；Gimmick 中 {'Unknown': 82}）：体力 ≥ v‰ 最大体力。
  - `e_trigger-exam_card_play_after-stamina_up_multiple-500-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用後、体力が50%以上の場合、」
  - `e_trigger-exam_card_play_after-stamina_up_multiple-800-p_card_search-target-idol-unique-0_1` → 「アイドル固有スキルカード使用後、体力が80%以上の場合、」
- **StaminaLessMultiple**（触发器 14，阈值分布 {500: 10, 300: 1, 0: 1, 40: 1, 250: 1}；Gimmick 中 {'Unknown': 17}）：体力 ≤ v‰。
  - `e_trigger-exam_card_play_after-stamina_less_multiple-500-p_card_search-active_skill-target-0_1` → 「アクティブスキルカード使用後、体力が50%以下の場合、」
  - `e_trigger-exam_card_play-stamina_less_multiple-300-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用時、体力が30%以下の場合、」
- **StaminaConsumptionDown**（触发器 6，阈值分布 {None: 6}；Gimmick 中 {'Unknown': 24}）：消費体力減少状態。
  - `e_trigger-exam_card_play-stamina_consumption_down` → 「スキルカード使用時、消費体力減少状態の場合、」
  - `e_trigger-exam_end_turn-not-stamina_consumption_down` → 「ターン終了時、非消費体力減少状態の場合、」
- **ConcentrationUp**（触发器 17，阈值分布 {2: 6, None: 10, 1: 1}；Gimmick 中 {'Unknown': 10}）：強気（v=段）。
  - `e_trigger-exam_card_play_after-concentration_up-2-p_card_search-active_skill-target-0_1` → 「アクティブスキルカード使用後、強気2段階目の場合、」
  - `e_trigger-exam_card_play_after-concentration_up-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用後、強気の場合、」
- **PreservationUp**（触发器 16，阈值分布 {2: 3, None: 12, 1: 1}；Gimmick 中 {'Unknown': 12, 'Not': 12}）：温存（v=段）。
  - `e_trigger-exam_card_play_after-preservation_up-2-p_card_search-mental_skill-playing-0_1` → 「メンタルスキルカード使用後、温存2段階目の場合、」
  - `e_trigger-exam_card_play_after-preservation_up-2-p_card_search-mental_skill-target-0_1` → 「メンタルスキルカード使用後、温存2段階目の場合、」
- **FullPowerUp**（触发器 21，阈值分布 {None: 20, 1: 1}；Gimmick 中 —）：全力。
  - `e_trigger-exam_card_play_after-full_power_up-p_card_search-playing-effect_group-visible-exam_preservation-000-0_1` → 「温存効果のスキルカード使用後、全力の場合、」
  - `e_trigger-exam_card_play_after-full_power_up-p_card_search-target_is_self-0_1` → 「自身使用後、全力の場合、」
- **PlayCardRestriction**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **NoBlock**（触发器 6，阈值分布 {None: 6}；Gimmick 中 —）：元気 = 0。
  - `e_trigger-exam_card_play_after-no_block-p_card_search-active_skill-target-0_1` → 「アクティブスキルカード使用後、元気が0の場合、」
  - `e_trigger-exam_card_play-no_block` → 「スキルカード使用時、元気が0の場合、」
- **PlayCardSkill**（触发器 2，阈值分布 {None: 2}；Gimmick 中 {'Unknown': 50}）：直前使用的是メンタル卡。
  - `e_trigger-exam_card_play-play_card_skill-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用時、直前にメンタルスキルカードを使用した状態の場合、」
  - `e_trigger-exam_card_play-play_card_skill-p_card_search-mental_skill-playing-0_1` → 「メンタルスキルカード使用時、直前にメンタルスキルカードを使用した状態の場合、」
- **PlayCardLesson**（触发器 2，阈值分布 {None: 2}；Gimmick 中 {'Unknown': 33}）：直前使用的是アクティブ卡。
  - `e_trigger-exam_card_play-play_card_lesson-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用時、直前にアクティブスキルカードを使用した状態の場合、」
  - `e_trigger-start_play-play_card_lesson` → 「ターン開始後、直前にアクティブスキルカードを使用した状態の場合、」
- **PlayCardSupport**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **TurnProgressUp**（触发器 5，阈值分布 {5: 1, 2: 2, 3: 2}；Gimmick 中 —）：第 v+1 回合以后。
  - `e_trigger-exam_card_play-turn_progress_up-5` → 「スキルカード使用時、6ターン目以降の場合、」
  - `e_trigger-exam_start_turn-turn_progress_up-2` → 「ターン開始時、3ターン目以降の場合、」
- **ConditionThresholdMultiple**（触发器 2，阈值分布 {500: 1, 1000: 1}；Gimmick 中 {'Not': 94, 'Unknown': 102}）：レッスンCLEAR 条件的 v‰ 以上（試験：スコア ≥ v）。
  - `e_trigger-exam_card_play-condition_threshold_multiple-500` → 「スキルカード使用時、レッスンCLEARの50%以上の場合、」
  - `e_trigger-exam_start_turn-not-condition_threshold_multiple-1000` → 「ターン開始時、レッスン未CLEARの場合、」
- **ConditionThresholdMultipleDown**（触发器 3，阈值分布 {250: 1, 500: 1, 1000: 1}；Gimmick 中 {'Unknown': 20}）：CLEAR 的 v‰ 以下。
  - `e_trigger-exam_card_play-condition_threshold_multiple_down-250` → 「スキルカード使用時、未定義のパターン(Type: ConditionThresholdMultipleDown, CheckType: , Value: 250)の場合、」
  - `e_trigger-exam_card_play-condition_threshold_multiple_down-500` → 「スキルカード使用時、レッスンCLEARの50%以下の場合、」
- **LessonBuffUp**（触发器 43，阈值分布 {13: 7, 5: 10, 1: 2, 3: 5, 6: 3, 8: 6, 20: 2, 7: 3, 10: 2, 25: 1, 15: 1, 16: 1}；Gimmick 中 {'Not': 156, 'Unknown': 378}）：集中 ≥ v。
  - `e_trigger-exam_buff_consume-lesson_buff_up-13` → 「スキルカードコストで強化状態を消費した時、集中が13以上の場合、」
  - `e_trigger-exam_card_play_after-lesson_buff_up-13-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用後、集中が13以上の場合、」
- **BlockUp**（触发器 33，阈值分布 {30: 10, 7: 8, 15: 5, 31: 1, 12: 2, 230: 1, 50: 3, 14: 1, 80: 1, 10: 1}；Gimmick 中 {'Not': 52, 'Unknown': 62}）：元気 ≥ v。
  - `e_trigger-exam_card_play_after-block_up-30-p_card_search-mental_skill-playing-0_1` → 「メンタルスキルカード使用後、元気が30以上の場合、」
  - `e_trigger-exam_card_play_after-block_up-30-p_card_search-mental_skill-target-0_1` → 「メンタルスキルカード使用後、元気が30以上の場合、」
- **ReviewUp**（触发器 45，阈值分布 {10: 9, 3: 8, 6: 13, 1: 4, 5: 3, 7: 2, 15: 3, 20: 1, 55: 1, 8: 1}；Gimmick 中 {'Not': 157, 'Unknown': 349}）：好印象 ≥ v。
  - `e_trigger-exam_buff_consume-review_up-10` → 「スキルカードコストで強化状態を消費した時、好印象が10以上の場合、」
  - `e_trigger-exam_buff_consume-review_up-3` → 「スキルカードコストで強化状態を消費した時、好印象が3以上の場合、」
- **GimmickLessonDebuffUp**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **GimmickSleepyUp**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **ParameterBuffUp**（触发器 43，阈值分布 {3: 7, 6: 6, 8: 7, 4: 4, 10: 9, 7: 1, 12: 2, 15: 2, 21: 1, 5: 1, 16: 1, 1: 1, 2: 1}；Gimmick 中 {'Unknown': 123, 'Not': 8}）：好調残り ≥ v ターン。
  - `e_trigger-exam_buff_consume-parameter_buff_up-3` → 「スキルカードコストで強化状態を消費した時、好調が3ターン以上の場合、」
  - `e_trigger-exam_buff_consume-parameter_buff_up-6` → 「スキルカードコストで強化状態を消費した時、好調が6ターン以上の場合、」
- **BlockAddDown**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **GimmickParameterDebuff**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **RemainingTurn**（触发器 14，阈值分布 {3: 5, 1: 3, 2: 3, 4: 1, 5: 1, 6: 1}；Gimmick 中 —）：残り ≤ v ターン。
  - `e_trigger-exam_card_play-remaining_turn-3-p_card_search-ssr-playing-0_1` → 「残り3ターン以内の場合、スキルカード（SSR）使用時、」
  - `e_trigger-exam_end_turn-remaining_turn-1` → 「最終ターンのターン終了時、」
- **CardPlayAggressiveUp**（触发器 34，阈值分布 {12: 5, 3: 6, 5: 7, 8: 5, 6: 5, 7: 2, 13: 1, 20: 1, 9: 2}；Gimmick 中 {'Unknown': 350, 'Not': 166}）：やる気 ≥ v。
  - `e_trigger-exam_card_play_after-card_play_aggressive_up-12-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用後、やる気が12以上の場合、」
  - `e_trigger-exam_card_play_after-card_play_aggressive_up-12-p_card_search-active_skill-target-0_1` → 「アクティブスキルカード使用後、やる気が12以上の場合、」
- **ParameterLessThan**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **FullPowerPointUp**（触发器 13，阈值分布 {10: 6, 1: 2, 5: 3, 3: 2}；Gimmick 中 —）：全力値 ≥ v。
  - `e_trigger-exam_card_play_after-not-full_power_point_up-10-p_card_search-playing-idol-unique-0_1` → 「アイドル固有スキルカード使用後、全力値が9以下の場合、」
  - `e_trigger-exam_card_play_after-not-full_power_point_up-10-p_card_search-target-idol-unique-0_1` → 「アイドル固有スキルカード使用後、全力値が9以下の場合、」
- **FullPowerPointGetSumUp**（触发器 9，阈值分布 {13: 2, 5: 3, 15: 1, 18: 1, 8: 1, 10: 1}；Gimmick 中 {'Unknown': 125, 'Not': 11}）：本场累计全力値 ≥ v。
  - `e_trigger-exam_end_turn-full_power_point_get_sum_up-13` → 「ターン終了時、このレッスン中の累計全力値が13以上の場合、」
  - `e_trigger-exam_stance_change_concentration-full_power_point_get_sum_up-5` → 「直接効果で強気になった時、このレッスン中の累計全力値が5以上の場合、」
- **NoStance**（触发器 4，阈值分布 {None: 4}；Gimmick 中 —）：无指針（Not=いずれかの指針）。
  - `e_trigger-exam_play_count_interval_after-3-not-no_stance-p_card_search-target-effect_group-visible-exam_concentration-000` → 「いずれかの指針の場合、強気効果のスキルカード使用後3回ごとに、」
  - `e_trigger-exam_play_count_interval_after-4-not-no_stance-p_card_search-target-effect_group-visible-exam_concentration-000` → 「いずれかの指針の場合、強気効果のスキルカード使用後4回ごとに、」
- **StanceChangeCountUp**（触发器 6，阈值分布 {3: 2, 4: 4}；Gimmick 中 {'Not': 7, 'Unknown': 53}）：指針変更回数 ≥ v。
  - `e_trigger-exam_card_play_after-stance_change_count_up-3-p_card_search-playing-effect_group-visible-exam_concentration-000-0_1` → 「強気効果のスキルカード使用後、指針を変更した回数が3回以上の場合、」
  - `e_trigger-exam_card_play_after-stance_change_count_up-4-p_card_search-playing-effect_group-visible-exam_concentration-000-0_1` → 「強気効果のスキルカード使用後、指針を変更した回数が4回以上の場合、」
- **ConcentrationChangeCountUp**（触发器 10，阈值分布 {3: 4, 4: 2, 1: 1, 2: 3}；Gimmick 中 {'Unknown': 84, 'Not': 9}）：強気になった回数 ≥ v。
  - `e_trigger-exam_card_play-concentration_change_count_up-3-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用時、強気になった回数が3回以上の場合、」
  - `e_trigger-exam_card_play-concentration_change_count_up-4-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用時、強気になった回数が4回以上の場合、」
- **PreservationChangeCountUp**（触发器 7，阈值分布 {2: 3, 3: 1, 4: 2, 1: 1}；Gimmick 中 {'Unknown': 53, 'Not': 3}）：温存になった回数 ≥ v。
  - `e_trigger-exam_card_play_after-preservation_change_count_up-2-p_card_search-target-p_card-03-ido-3_197-0_1` → 「手を伸ばした先に使用後、温存になった回数が2回以上の場合、」
  - `e_trigger-exam_start_turn-preservation_change_count_up-2` → 「ターン開始時、温存になった回数が2回以上の場合、」
- **FullPowerChangeCountUp**（触发器 3，阈值分布 {2: 2, 1: 1}；Gimmick 中 {'Unknown': 15, 'Not': 7}）：全力になった回数 ≥ v。
  - `e_trigger-exam_stance_change_full_power-full_power_change_count_up-2` → 「全力になった時、全力になった回数が2回以上の場合、」
  - `e_trigger-none-full_power_change_count_up-1` → 「全力になった回数が1回以上の場合、」
- **CardSearchCountUp**（触发器 19，阈值分布 {1: 6, 9: 2, 21: 1, 7: 3, 2: 2, 3: 1, 4: 1, 6: 1, 12: 1, 18: 1}；Gimmick 中 —）：fieldStatusProduceCardSearchIds 命中的卡 ≥ v 张。
  - `e_trigger-exam_card_play_after-card_search_count_up-1-p_card_search-hand-p_card-01-ido-3_213-p_card_search-target-0_1` → 「スキルカード使用後、手札にある自然体の魅力が1枚以上の場合、」
  - `e_trigger-exam_card_play_after-card_search_count_up-1-p_card_search-hold-p_card_search-playing-1-p_card-03-act-1_038-0_1` → 「ジャストアピール使用後、保留にあるスキルカードが1枚以上の場合、」
- **PlayCardSearch**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **ParameterBuffMultiplePerTurnUp**（触发器 7，阈值分布 {1: 5, 5: 2}；Gimmick 中 {'Unknown': 1}）：絶好調 ≥ v。
  - `e_trigger-exam_card_play_after-parameter_buff_multiple_per_turn_up-1-p_card_search-active_skill-playing-0_1` → 「アクティブスキルカード使用後、絶好調状態の場合、」
  - `e_trigger-exam_card_play_after-parameter_buff_multiple_per_turn_up-1-p_card_search-active_skill-target-0_1` → 「アクティブスキルカード使用後、絶好調状態の場合、」
- **EnthusiasticUp**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **EnchantCountUp**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **TurnPlayCardCountUp**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **DeckCardAllNoDuplicate**（触发器 0，阈值分布 —；Gimmick 中 —）：
- **DebuffCountUp**（触发器 0，阈值分布 —；Gimmick 中 —）：

### 2.3 ProduceEffectType（培育外循环效果类型）

#### Unknown — rows=0
- dump 中无 ProduceEffect 行。

#### VocalAddition — rows=200  UI名=**ボーカル上昇**
- 语义：Vocal +v。
- 非零字段：{'effectValueMin': 200, 'effectValueMax': 200}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]
- 被谁引用：{'Skill': 228, 'Event': 281, 'Item': 16, 'Suggestion': 615, 'GrowthPanel': 5}
- 示例行：`{"id": "p_effect-vocal_addition-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「ボーカルレッスン終了時、ボーカル上昇+1」

#### DanceAddition — rows=200  UI名=**ダンス上昇**
- 语义：Dance +v。
- 非零字段：{'effectValueMin': 200, 'effectValueMax': 200}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]
- 被谁引用：{'Skill': 211, 'Event': 277, 'Item': 13, 'Suggestion': 618, 'GrowthPanel': 5}
- 示例行：`{"id": "p_effect-dance_addition-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「ダンスレッスン終了時、ダンス上昇+1」

#### VisualAddition — rows=200  UI名=**ビジュアル上昇**
- 语义：Visual +v。
- 非零字段：{'effectValueMin': 200, 'effectValueMax': 200}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]
- 被谁引用：{'Skill': 222, 'Event': 281, 'Item': 14, 'Suggestion': 624, 'GrowthPanel': 5}
- 示例行：`{"id": "p_effect-visual_addition-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「ビジュアルレッスン終了時、ビジュアル上昇+1」

#### VocalDown — rows=0  UI名=**ボーカル低下**
- dump 中无 ProduceEffect 行。

#### DanceDown — rows=0  UI名=**ダンス低下**
- dump 中无 ProduceEffect 行。

#### VisualDown — rows=0  UI名=**ビジュアル低下**
- dump 中无 ProduceEffect 行。

#### VocalGrowthRateAddition — rows=86  UI名=**ボーカルパラメータボーナス+**
- 语义：Vocal 成长率 +v‰。
- 非零字段：{'effectValueMin': 86, 'effectValueMax': 86}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]
- 被谁引用：{'Skill': 37, 'GrowthPanel': 5, 'Item': 1}
- 示例行：`{"id": "p_effect-vocal_growth_rate_addition-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「ボーカルパラメータボーナス+1.2%」

#### DanceGrowthRateAddition — rows=86  UI名=**ダンスパラメータボーナス+**
- 语义：。
- 非零字段：{'effectValueMin': 86, 'effectValueMax': 86}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]
- 被谁引用：{'Skill': 37, 'GrowthPanel': 5, 'Item': 1}
- 示例行：`{"id": "p_effect-dance_growth_rate_addition-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「ダンスパラメータボーナス+1.2%」

#### VisualGrowthRateAddition — rows=86  UI名=**ビジュアルパラメータボーナス+**
- 语义：。
- 非零字段：{'effectValueMin': 86, 'effectValueMax': 86}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]
- 被谁引用：{'Skill': 37, 'GrowthPanel': 5, 'Item': 1}
- 示例行：`{"id": "p_effect-visual_growth_rate_addition-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「ビジュアルパラメータボーナス+1.2%」

#### VocalGrowthRateDown — rows=0  UI名=**ボーカルパラメータボーナス-**
- dump 中无 ProduceEffect 行。

#### DanceGrowthRateDown — rows=0  UI名=**ダンスパラメータボーナス-**
- dump 中无 ProduceEffect 行。

#### VisualGrowthRateDown — rows=0  UI名=**ビジュアルパラメータボーナス-**
- dump 中无 ProduceEffect 行。

#### StaminaRecoverFix — rows=11  UI名=**体力回復**
- 语义：体力 +v。
- 非零字段：{'effectValueMin': 11, 'effectValueMax': 11}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]
- 被谁引用：{'Skill': 45, 'Item': 65, 'CustomizeItem': 60, 'Event': 2, 'Suggestion': 216}
- 示例行：`{"id": "p_effect-stamina_recover_fix-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「ダンスSPレッスン終了時、体力回復2」

#### StaminaRecoverMultiple — rows=12  UI名=**体力割合回復**
- 语义：最大体力 ×v‰ 回复。
- 非零字段：{'effectValueMin': 12, 'effectValueMax': 12}；(min,max) 取值：[(50, 50), (70, 70), (75, 75), (100, 100), (105, 105), (140, 140), (200, 200), (300, 300), (400, 400), (500, 500)]
- 被谁引用：{'Suggestion': 714, 'Item': 6}
- 示例行：`{"id": "p_effect-stamina_recover_multiple-0050_0050", "effectValueMin": 50, "effectValueMax": 50}`
  - 文本（Suggestion）：「最大体力の10%分回復 / ランダムなスキルカードを強化」

#### StaminaReduceFix — rows=10  UI名=**体力減少**
- 语义：体力 -v。
- 非零字段：{'effectValueMin': 10, 'effectValueMax': 10}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9), (10, 10)]
- 被谁引用：{'Item': 13}
- 示例行：`{"id": "p_effect-stamina_reduce_fix-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Item）：「好調効果のスキルカード獲得時、体力が50%以上の場合、 / ライバルのスコアが5%増加 / 体力減少1 / 次のレッスン開始時、好調3ターン / （プロデュース中3回）」

#### StaminaReduceMultiple — rows=0  UI名=**体力割合減少**
- dump 中无 ProduceEffect 行。

#### StaminaSpecify — rows=0  UI名=**体力変更**
- dump 中无 ProduceEffect 行。

#### StaminaRecoverValueUp — rows=0  UI名=**体力回復量増加**
- dump 中无 ProduceEffect 行。

#### StaminaRecoverValueDown — rows=0  UI名=**体力回復量減少**
- dump 中无 ProduceEffect 行。

#### StaminaReduceValueUp — rows=0  UI名=**体力減少量増加**
- dump 中无 ProduceEffect 行。

#### StaminaReduceValueDown — rows=0  UI名=**体力減少量軽減**
- dump 中无 ProduceEffect 行。

#### StaminaRecoverDisable — rows=0  UI名=**体力回復無効**
- dump 中无 ProduceEffect 行。

#### MaxStaminaAddition — rows=9  UI名=**最大体力増加**
- 语义：最大体力 +v。
- 非零字段：{'effectValueMin': 9, 'effectValueMax': 9}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6), (7, 7), (8, 8), (9, 9)]
- 被谁引用：{'Skill': 10, 'Suggestion': 4}
- 示例行：`{"id": "p_effect-max_stamina_addition-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「最大体力上昇+1」

#### MaxStaminaReduceFix — rows=6  UI名=**最大体力減少**
- 语义：最大体力 -v。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6}；(min,max) 取值：[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6)]
- 被谁引用：（无引用）
- 示例行：`{"id": "p_effect-max_stamina_reduce_fix-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`

#### MaxStaminaReduceMultiple — rows=0  UI名=**最大体力割合減少**
- dump 中无 ProduceEffect 行。

#### ProducePointReduceFix — rows=15  UI名=**Pポイント減少**
- 语义：P点 -v。
- 非零字段：{'effectValueMin': 15, 'effectValueMax': 15}；(min,max) 取值：[(10, 10), (20, 20), (30, 30), (40, 40), (50, 50), (60, 60), (70, 70), (80, 80), (90, 90), (100, 100)]
- 被谁引用：{'Item': 6}
- 示例行：`{"id": "p_effect-produce_point_reduce_fix-0010_0010", "effectValueMin": 10, "effectValueMax": 10}`
  - 文本（Item）：「好調効果のスキルカード獲得時、 / Pポイント-10 / ライバルのスコアが3%増加 / 次のレッスン開始時、元気+3 / （プロデュース中5回）」

#### ProducePointReduceMultiple — rows=0  UI名=**Pポイント割合減少**
- dump 中无 ProduceEffect 行。

#### ProducePointSpecify — rows=0  UI名=**Pポイント変更**
- dump 中无 ProduceEffect 行。

#### ProducePointAdditionValueUp — rows=0  UI名=**Pポイント獲得量増加**
- dump 中无 ProduceEffect 行。

#### ProducePointAdditionValueDown — rows=0  UI名=**Pポイント獲得量減少**
- dump 中无 ProduceEffect 行。

#### ProducePointReduceValueUp — rows=0  UI名=**Pポイント減少量増加**
- dump 中无 ProduceEffect 行。

#### ProducePointReduceValueDown — rows=0  UI名=**Pポイント減少量減少**
- dump 中无 ProduceEffect 行。

#### ProduceCardUpgrade — rows=9  UI名=**強化**
- 语义：强化筛选/选择的卡。
- 非零字段：{'effectValueMin': 9, 'effectValueMax': 9, 'produceCardSearchId': 9, 'pickRangeType': 9, 'pickCountMin': 8, 'pickCountMax': 9}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Suggestion': 166, 'Item': 16, 'Event': 99, 'CustomizeItem': 18, 'Skill': 1}
- 示例行：`{"id": "p_effect-produce_card_upgrade-0001_0001-p_card_search-active_skill-deck_all-random-01_01", "effectValueMin": 1, "effectValueMax": 1, "produceCardSearchId": "p_card_search-active_skill-deck_all", "pickRangeType": "ProducePickRangeType_Random", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本（Suggestion）：「最大体力の30%分回復 / ランダムなアクティブスキルカードを強化 / スキルカードを選択して獲得」

#### ProduceCardDuplicate — rows=7  UI名=**コピー**
- 语义：コピー。
- 非零字段：{'effectValueMin': 7, 'effectValueMax': 7, 'produceCardSearchId': 7, 'pickRangeType': 7, 'pickCountMin': 7, 'pickCountMax': 7}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Item': 15, 'CustomizeItem': 9}
- 示例行：`{"id": "p_effect-produce_card_duplicate-0001_0001-p_card_search-deck_all-effect_group-visible-exa…", "effectValueMin": 1, "effectValueMax": 1, "produceCardSearchId": "p_card_search-deck_all-effect_group-visible-exam_card_play_aggressive-000", "pickRangeType": "ProducePickRangeType_Select", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本（Item）：「活動支給・差し入れ選択時、ボーカルが700以上の場合、 / ボーカル上昇+20 / スキルカードを選択してコピー / （プロデュース中1回）」

#### ProduceCardDuplicateUpgrade — rows=0  UI名=**コピーして強化**
- dump 中无 ProduceEffect 行。

#### ProduceCardChange — rows=37  UI名=**チェンジ**
- 语义：チェンジ 为集合内其他卡。
- 非零字段：{'effectValueMin': 37, 'effectValueMax': 37, 'produceResourceType': 37, 'produceCardSearchId': 37, 'pickRangeType': 37, 'pickCountMin': 37, 'pickCountMax': 37}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Suggestion': 155, 'Item': 4, 'Event': 20}
- 示例行：`{"id": "p_effect-produce_card_change-0001_0001-p_rd-card_set-ssr-upgrade_0-p_card_search-deck_all…", "effectValueMin": 1, "effectValueMax": 1, "produceResourceType": "ProduceResourceType_ProduceCard", "produceCardSearchId": "p_card_search-deck_all", "pickRangeType": "ProducePickRangeType_Select", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本（Suggestion）：「最大体力の40%分回復 / ランダムなPドリンク（SR以上）を獲得 / スキルカードを選択して異なるやる気関係のスキルカードにチェンジ」

#### ProduceCardChangeUpgrade — rows=35  UI名=**チェンジして強化**
- 语义：チェンジして強化。
- 非零字段：{'effectValueMin': 35, 'effectValueMax': 35, 'produceResourceType': 35, 'produceCardSearchId': 35, 'pickRangeType': 35, 'pickCountMin': 10, 'pickCountMax': 10}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Skill': 13, 'Suggestion': 12}
- 示例行：`{"id": "p_effect-produce_card_change_upgrade-0001_0001-p_rd-p_ability-p_idol_skill-cidol-shro-3-0…", "effectValueMin": 1, "effectValueMax": 1, "produceResourceType": "ProduceResourceType_ProduceCard", "produceCardSearchId": "p_card_search-deck_all-1-p_card-00-act-0_001", "pickRangeType": "ProducePickRangeType_All"}`
  - 文本（Skill）：「アピールの基本か距離感の基本をえいえいおーにチェンジして強化」

#### ProduceCardDelete — rows=6  UI名=**削除**
- 语义：删除卡。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1, 'produceCardSearchId': 6, 'pickRangeType': 6, 'pickCountMin': 6, 'pickCountMax': 6}；(min,max) 取值：[(0, 0), (1, 1)]
- 被谁引用：{'Item': 126, 'Event': 5, 'CustomizeItem': 9, 'Suggestion': 35}
- 示例行：`{"id": "p_effect-produce_card_delete-0001_0001-p_card_search-deck_all-starter-random-01_01", "effectValueMin": 1, "effectValueMax": 1, "produceCardSearchId": "p_card_search-deck_all-starter", "pickRangeType": "ProducePickRangeType_Random", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本（Item）：「好調効果のスキルカード獲得時、ダンスが700以上の場合、 / スキルカードを選択して削除 / Pポイント+40 / （プロデュース中1回）」

#### ProducePointAddition — rows=41  UI名=**Pポイント獲得**
- 语义：P点 +v。
- 非零字段：{'effectValueMin': 41, 'effectValueMax': 41}；(min,max) 取值：[(10, 10), (15, 15), (20, 20), (25, 25), (30, 30), (34, 34), (35, 35), (40, 40), (45, 45), (50, 50)]
- 被谁引用：{'Event': 236, 'Item': 51, 'CustomizeItem': 84, 'Suggestion': 217}
- 示例行：`{"id": "p_effect-produce_point_addition-0010_0010", "effectValueMin": 10, "effectValueMax": 10}`
  - 文本（Event）：「Pポイント+10」

#### ProducePointGetDisable — rows=0  UI名=**Pポイント獲得不可**
- dump 中无 ProduceEffect 行。

#### ProduceItemGetDisable — rows=0  UI名=**Pアイテム獲得不可**
- dump 中无 ProduceEffect 行。

#### ProduceDrinkGetDisable — rows=0  UI名=**Pドリンク獲得不可**
- dump 中无 ProduceEffect 行。

#### ProduceReward — rows=207  UI名=**報酬獲得**
- 语义：给固定奖励 produceRewards。
- 非零字段：{'effectValueMin': 207, 'effectValueMax': 207, 'produceRewards': 207, 'isResearch': 2}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Suggestion': 14, 'Event': 254, 'Skill': 10, 'Item': 2}
- 示例行：`{"id": "p_effect-produce_reward-0001_0001-produce_card-p_card-00-acc-0_002-0", "effectValueMin": 1, "effectValueMax": 1, "produceRewards": [{"resourceType": "ProduceResourceType_ProduceCard", "resourceId": "p_card-00-acc-0_002", "resourceLevel": 0}]}`
  - 文本（Suggestion）：「最大体力の40%分回復 / 70%の確率で成功しスキルカード（高確率でSSR）を選択して獲得 / 30%の確率で失敗しトラブルカード「眠気」を獲得」

#### ProduceRewardSet — rows=204  UI名=**報酬獲得**
- 语义：从奖励集合（id 内 p_rd-…）按 pickRange 给 pickCount 个 produceResourceType。
- 非零字段：{'produceResourceType': 204, 'pickRangeType': 204, 'pickCountMin': 203, 'pickCountMax': 203, 'isResearch': 1}；(min,max) 取值：[(0, 0)]
- 被谁引用：{'Item': 138, 'CustomizeItem': 105, 'Suggestion': 2620, 'Event': 204}
- 示例行：`{"id": "p_effect-produce_reward_set-p_rd-card_set-card_play_aggressive_ssr_set-exam_card_play_agg…", "produceResourceType": "ProduceResourceType_ProduceCard", "pickRangeType": "ProducePickRangeType_Select", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本（Item）：「相談選択時、ビジュアルが400以上の場合、 / ビジュアル上昇+10 / ランダムなスキルカード（R）を獲得 / （プロデュース中2回）」

#### AuditionParameterBonusMultiple — rows=7  UI名=**スコアボーナス増加**
- 语义：试炼スコアボーナス +v‰。
- 非零字段：{'effectValueMin': 7, 'effectValueMax': 7}；(min,max) 取值：[(50, 50), (100, 100), (150, 150), (200, 200), (300, 300), (400, 400), (500, 500)]
- 被谁引用：{'Skill': 7}
- 示例行：`{"id": "p_effect-audition_parameter_bonus_multiple-0050_0050", "effectValueMin": 50, "effectValueMax": 50}`
  - 文本（Skill）：「試験・オーディション時のスコアボーナスを5%増加」

#### LessonSpChangeRatePermilAddition — rows=24  UI名=**SPレッスン発生率増加**
- 语义：SP 课程发生率 +v‰。
- 非零字段：{'effectValueMin': 24, 'effectValueMax': 24}；(min,max) 取值：[(10, 10), (20, 20), (30, 30), (40, 40), (50, 50), (52, 52), (70, 70), (100, 100), (105, 105), (110, 110)]
- 被谁引用：{'GrowthPanel': 5, 'Skill': 23}
- 示例行：`{"id": "p_effect-lesson_sp_change_rate_permil_addition-0010_0010", "effectValueMin": 10, "effectValueMax": 10}`
  - 文本（GrowthPanel）：「ボーカル、ダンス、ビジュアルすべてのSPレッスン発生率+1%」

#### LessonVocalSpChangeRatePermilAddition — rows=6  UI名=**ボーカルSPレッスン発生率増加**
- 语义：。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6}；(min,max) 取值：[(70, 70), (105, 105), (140, 140), (150, 150), (210, 210), (280, 280)]
- 被谁引用：{'Skill': 8}
- 示例行：`{"id": "p_effect-lesson_vocal_sp_change_rate_permil_addition-0070_0070", "effectValueMin": 70, "effectValueMax": 70}`
  - 文本（Skill）：「ボーカルSPレッスン発生率+7%」

#### LessonDanceSpChangeRatePermilAddition — rows=6  UI名=**ダンスSPレッスン発生率増加**
- 语义：。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6}；(min,max) 取值：[(70, 70), (105, 105), (140, 140), (150, 150), (210, 210), (280, 280)]
- 被谁引用：{'Skill': 8}
- 示例行：`{"id": "p_effect-lesson_dance_sp_change_rate_permil_addition-0070_0070", "effectValueMin": 70, "effectValueMax": 70}`
  - 文本（Skill）：「ダンスSPレッスン発生率+7%」

#### LessonVisualSpChangeRatePermilAddition — rows=6  UI名=**ビジュアルSPレッスン発生率増加**
- 语义：。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6}；(min,max) 取值：[(70, 70), (105, 105), (140, 140), (150, 150), (210, 210), (280, 280)]
- 被谁引用：{'Skill': 8}
- 示例行：`{"id": "p_effect-lesson_visual_sp_change_rate_permil_addition-0070_0070", "effectValueMin": 70, "effectValueMax": 70}`
  - 文本（Skill）：「ビジュアルSPレッスン発生率+7%」

#### LessonSpChangeRatePermilDown — rows=0  UI名=**SPレッスン発生率減少**
- dump 中无 ProduceEffect 行。

#### ExamStatusEnchant — rows=201  UI名=**レッスン時発生効果**
- 语义：下次课程/试炼开始时挂持续效果。
- 非零字段：{'produceExamStatusEnchantId': 201}；(min,max) 取值：[(0, 0)]
- 被谁引用：{'CustomizeItem': 45, 'Item': 90, 'Skill': 303}
- 示例行：`{"id": "p_effect-exam_status_enchant-enchant-customize_pitem-01-04-3-001_00-04-2-001_01-01-1-001-…", "produceExamStatusEnchantId": "enchant-customize_pitem-01-04-3-001_00-04-2-001_01-01-1-001-enc01"}`
  - 文本（CustomizeItem）：「レッスン終了時、 / 体力回復6 / ランダムなPドリンクを獲得 / 次の試験開始時、集中+3・好調3ターン / （プロデュース中2回）」

#### LessonPresentProduceCardRewardCountUp — rows=1  UI名=**レッスン報酬のスキルカード選択肢追加**
- 语义：课程奖励选卡数 +v。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Item': 1}
- 示例行：`{"id": "p_effect-lesson_present_produce_card_reward_count_up-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Item）：「レッスン終了時、 / レッスン報酬のスキルカードの選択肢を追加」

#### LessonPresentProduceCardRewardCountDown — rows=0  UI名=**レッスン報酬のスキルカード選択肢減少**
- dump 中无 ProduceEffect 行。

#### LessonPresentSearchProduceCardRewardCountUp — rows=0
- dump 中无 ProduceEffect 行。

#### ShopPriceDiscountMultiple — rows=2  UI名=**相談の全項目を割引**
- 语义：相談全项 -v‰。
- 非零字段：{'effectValueMin': 2, 'effectValueMax': 2}；(min,max) 取值：[(200, 200), (500, 500)]
- 被谁引用：{'Item': 1}
- 示例行：`{"id": "p_effect-shop_price_discount_multiple-0200_0200", "effectValueMin": 200, "effectValueMax": 200}`
  - 文本（Item）：「相談選択時、 / 相談の全項目を20%割引」

#### ShopProduceCardPriceDiscountMultiple — rows=10  UI名=**相談のスキルカードを割引**
- 语义：相談卡 -v‰（本次）。
- 非零字段：{'effectValueMin': 10, 'effectValueMax': 10, 'produceCardSearchId': 10}；(min,max) 取值：[(50, 50), (100, 100), (105, 105), (140, 140), (150, 150), (200, 200), (210, 210), (250, 250), (280, 280), (500, 500)]
- 被谁引用：{'Skill': 5, 'Item': 1, 'CustomizeItem': 9}
- 示例行：`{"id": "p_effect-shop_produce_card_price_discount_multiple-0050_0050-p_card_search-deck_all", "effectValueMin": 50, "effectValueMax": 50, "produceCardSearchId": "p_card_search-deck_all"}`
  - 文本（Skill）：「相談のスキルカードを10.5%割引」

#### ShopProduceDrinkPriceDiscountMultiple — rows=5  UI名=**相談のPドリンクを割引**
- 语义：。
- 非零字段：{'effectValueMin': 5, 'effectValueMax': 5}；(min,max) 取值：[(79, 79), (105, 105), (158, 158), (210, 210), (500, 500)]
- 被谁引用：{'Skill': 5, 'CustomizeItem': 9}
- 示例行：`{"id": "p_effect-shop_produce_drink_price_discount_multiple-0079_0079", "effectValueMin": 79, "effectValueMax": 79}`
  - 文本（Skill）：「相談のPドリンクを7.9%割引」

#### ShopProduceCardUpgradePriceDiscountMultiple — rows=5  UI名=**相談のスキルカード強化を割引**
- 语义：。
- 非零字段：{'effectValueMin': 5, 'effectValueMax': 5}；(min,max) 取值：[(42, 42), (55, 55), (83, 83), (110, 110), (500, 500)]
- 被谁引用：{'Skill': 5, 'CustomizeItem': 9}
- 示例行：`{"id": "p_effect-shop_produce_card_upgrade_price_discount_multiple-0042_0042", "effectValueMin": 42, "effectValueMax": 42}`
  - 文本（Skill）：「相談のスキルカード強化を4.2%割引」

#### ShopProduceCardUpgradePriceSpecify — rows=0  UI名=**相談のスキルカード強化を変更**
- dump 中无 ProduceEffect 行。

#### ShopProduceCardDeletePriceDiscountMultiple — rows=5  UI名=**相談のスキルカード削除を割引**
- 语义：。
- 非零字段：{'effectValueMin': 5, 'effectValueMax': 5}；(min,max) 取值：[(72, 72), (95, 95), (143, 143), (190, 190), (500, 500)]
- 被谁引用：{'Skill': 5, 'CustomizeItem': 9}
- 示例行：`{"id": "p_effect-shop_produce_card_delete_price_discount_multiple-0072_0072", "effectValueMin": 72, "effectValueMax": 72}`
  - 文本（Skill）：「相談のスキルカード削除を7.2%割引」

#### ShopProduceCardDeletePriceSpecify — rows=0  UI名=**相談のスキルカード強化を変更**
- dump 中无 ProduceEffect 行。

#### ProduceResultRewardMoneyUp — rows=0  UI名=**プロデュース完了時の獲得マニー増加**
- dump 中无 ProduceEffect 行。

#### ProduceResultRewardSupportCardEnhancePointUp — rows=0  UI名=**プロデュース完了時のサポートPt増加**
- dump 中无 ProduceEffect 行。

#### SupportCardEventStaminaRecoverUp — rows=3  UI名=**サポートイベントの体力回復量増加**
- 语义：支援事件体力回复 +v‰。
- 非零字段：{'effectValueMin': 3, 'effectValueMax': 3}；(min,max) 取值：[(500, 500), (750, 750), (1000, 1000)]
- 被谁引用：{'Skill': 9}
- 示例行：`{"id": "p_effect-support_card_event_stamina_recover_up-0500_0500", "effectValueMin": 500, "effectValueMax": 500}`
  - 文本（Skill）：「このサポートカードのイベントによる体力回復量を50%増加」

#### SupportCardEventProducePointAdditionValueUp — rows=3  UI名=**サポートイベントのPポイント獲得量増加**
- 语义：。
- 非零字段：{'effectValueMin': 3, 'effectValueMax': 3}；(min,max) 取值：[(500, 500), (750, 750), (1000, 1000)]
- 被谁引用：{'Skill': 9}
- 示例行：`{"id": "p_effect-support_card_event_produce_point_addition_value_up-0500_0500", "effectValueMin": 500, "effectValueMax": 500}`
  - 文本（Skill）：「このサポートカードのイベントによる獲得Pポイントを50%増加」

#### SupportCardEventParameterAdditionValueUp — rows=3  UI名=**サポートイベントのパラメータ上昇量増加**
- 语义：。
- 非零字段：{'effectValueMin': 3, 'effectValueMax': 3}；(min,max) 取值：[(500, 500), (750, 750), (1000, 1000)]
- 被谁引用：{'Skill': 9}
- 示例行：`{"id": "p_effect-support_card_event_parameter_addition_value_up-0500_0500", "effectValueMin": 500, "effectValueMax": 500}`
  - 文本（Skill）：「このサポートカードのイベントによるパラメータ上昇を50%増加」

#### SupportCardEventProbabilityUp — rows=0  UI名=**サポートイベント発生率増加**
- dump 中无 ProduceEffect 行。

#### LessonPresentProducePointUp — rows=6  UI名=**レッスン報酬のPポイント獲得量増加**
- 语义：课程奖励 P点 +v‰。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6}；(min,max) 取值：[(83, 83), (110, 110), (165, 165), (220, 220), (330, 330), (450, 450)]
- 被谁引用：{'Skill': 23}
- 示例行：`{"id": "p_effect-lesson_present_produce_point_up-0083_0083", "effectValueMin": 83, "effectValueMax": 83}`
  - 文本（Skill）：「レッスン終了時、Pポイント獲得量増加+8.3%」

#### LessonPresentProducePointDown — rows=0
- dump 中无 ProduceEffect 行。

#### SupportCardProduceCardUpgradeProbabilityUp — rows=141  UI名=**レッスンサポート発生率増加**
- 语义：该支援卡 レッスンサポート 发生率 +v‰。
- 非零字段：{'effectValueMin': 141, 'effectValueMax': 141}；(min,max) 取值：[(17, 17), (20, 20), (26, 26), (34, 34), (41, 41), (51, 51), (61, 61), (68, 68), (77, 77), (82, 82)]
- 被谁引用：{'Skill': 147}
- 示例行：`{"id": "p_effect-support_card_produce_card_upgrade_probability_up-0017_0017", "effectValueMin": 17, "effectValueMax": 17}`
  - 文本（Skill）：「このサポートカードのスキルカードサポート発生率を1.7%増加」

#### ProduceCardSelectRerollCountUp — rows=3  UI名=**再抽選回数増加**
- 语义：获得卡再抽次数 +v。
- 非零字段：{'effectValueMin': 3, 'effectValueMax': 3}；(min,max) 取值：[(1, 1), (2, 2), (3, 3)]
- 被谁引用：{'Skill': 5}
- 示例行：`{"id": "p_effect-produce_card_select_reroll_count_up-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「獲得スキルカード再抽選回数+1」

#### ProducePointAdditionDisableTrigger — rows=20  UI名=**初期Pポイント増加**
- 语义：初期 P点 +v（不触发获得事件）。
- 非零字段：{'effectValueMin': 20, 'effectValueMax': 20}；(min,max) 取值：[(10, 10), (15, 15), (20, 20), (30, 30), (34, 34), (40, 40), (45, 45), (50, 50), (55, 55), (60, 60)]
- 被谁引用：{'Skill': 25, 'GrowthPanel': 12}
- 示例行：`{"id": "p_effect-produce_point_addition_disable_trigger-0010_0010", "effectValueMin": 10, "effectValueMax": 10}`
  - 文本（Skill）：「初期Pポイント+10」

#### LessonLimitUp — rows=0
- dump 中无 ProduceEffect 行。

#### ParameterLimitUp — rows=6  UI名=**パラメータ上限増加**
- 语义：参数上限 +v。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6}；(min,max) 取值：[(50, 50), (80, 80), (110, 110), (140, 140), (170, 170), (200, 200)]
- 被谁引用：{'GrowthPanel': 6}
- 示例行：`{"id": "p_effect-parameter_limit_up-0050_0050", "effectValueMin": 50, "effectValueMax": 50}`
  - 文本（GrowthPanel）：「ボーカル、ダンス、ビジュアルすべての上限値を増加+50」

#### VocalLimitUp — rows=0
- dump 中无 ProduceEffect 行。

#### DanceLimitUp — rows=0
- dump 中无 ProduceEffect 行。

#### VisualLimitUp — rows=0
- dump 中无 ProduceEffect 行。

#### SupportCardEventProduceCardUpgrade — rows=0
- dump 中无 ProduceEffect 行。

#### ExamTurnUp — rows=0  UI名=**ターン数増加**
- dump 中无 ProduceEffect 行。

#### ExamTurnDown — rows=1  UI名=**ターン数減少**
- 语义：回合数 -v。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Item': 6}
- 示例行：`{"id": "p_effect-exam_turn_down-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Item）：「追い込みレッスン開始時、 / ターン数が1ターン減少 / ライバルのスコアが10%増加 / 元気+3 / 好調4ターン」

#### AuditionNpcEnhance — rows=8  UI名=**ライバルのスコア**
- 语义：对手分数 +v‰。
- 非零字段：{'effectValueMin': 8, 'effectValueMax': 8}；(min,max) 取值：[(20, 20), (30, 30), (50, 50), (80, 80), (100, 100), (150, 150), (200, 200), (300, 300)]
- 被谁引用：{'Item': 225}
- 示例行：`{"id": "p_effect-audition_npc_enhance-0020_0020", "effectValueMin": 20, "effectValueMax": 20}`
  - 文本（Item）：「差し入れ終了時、 / ランダムな名前に「基本」を含むスキルカードを削除 / やる気関係のスキルカードを選択して獲得 / 体力回復4 / Pポイント+20 / ライバルのスコアが2%増加 / （プロデュース中3回）」

#### ShopPriceUpMultiple — rows=1  UI名=**相談の全項目を割増**
- 语义：+v‰。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(50, 50)]
- 被谁引用：{'Item': 1}
- 示例行：`{"id": "p_effect-shop_price_up_multiple-0050_0050", "effectValueMin": 50, "effectValueMax": 50}`
  - 文本（Item）：「相談選択時、 / 体力回復6 / 相談の全項目が5%割増 / ライバルのスコアが5%増加 / （プロデュース中2回）」

#### ShopProduceCardPriceUpMultiple — rows=0  UI名=**相談のスキルカードを割増**
- dump 中无 ProduceEffect 行。

#### ShopProduceDrinkPriceUpMultiple — rows=0  UI名=**相談のPドリンクを割増**
- dump 中无 ProduceEffect 行。

#### ShopProduceCardUpgradePriceUpMultiple — rows=0  UI名=**相談のスキルカード強化を割増**
- dump 中无 ProduceEffect 行。

#### ShopProduceCardDeletePriceUpMultiple — rows=0  UI名=**相談のスキルカード削除を割増**
- dump 中无 ProduceEffect 行。

#### EventSchoolStaminaUp — rows=5  UI名=**授業の消費体力増加**
- 语义：授業消耗体力 +v‰。
- 非零字段：{'effectValueMin': 5, 'effectValueMax': 5}；(min,max) 取值：[(100, 100), (200, 200), (250, 250), (300, 300), (500, 500)]
- 被谁引用：{'Item': 3}
- 示例行：`{"id": "p_effect-event_school_stamina_up-0100_0100", "effectValueMin": 100, "effectValueMax": 100}`
  - 文本（Item）：「初期 / Pポイント+50 / 授業の消費体力が20%増加 / ライバルのスコアが5%増加」

#### EventSchoolStaminaDown — rows=1  UI名=**授業の消費体力減少**
- 语义：-v‰。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(500, 500)]
- 被谁引用：{'Item': 1}
- 示例行：`{"id": "p_effect-event_school_stamina_down-0500_0500", "effectValueMin": 500, "effectValueMax": 500}`
  - 文本（Item）：「初期 / Pポイント+80 / 授業の消費体力を50%減少 / ライバルのスコアが15%増加」

#### EventActivityProducePointUp — rows=1  UI名=**お出かけの消費Pポイント増加**
- 语义：お出かけ P点消耗 +v‰。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(250, 250)]
- 被谁引用：{'Item': 1}
- 示例行：`{"id": "p_effect-event_activity_produce_point_up-0250_0250", "effectValueMin": 250, "effectValueMax": 250}`
  - 文本（Item）：「授業・営業終了時、 / ランダムな名前に「基本」を含むスキルカードを削除 / お出かけのPポイント消費量が25%増加 / ライバルのスコアが15%増加 / （プロデュース中1回）」

#### EventActivityProducePointDown — rows=1  UI名=**お出かけの消費Pポイント減少**
- 语义：-v‰。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(500, 500)]
- 被谁引用：（无引用）
- 示例行：`{"id": "p_effect-event_activity_produce_point_down-0500_0500", "effectValueMin": 500, "effectValueMax": 500}`

#### BeforeAuditionRefreshStaminaUp — rows=6  UI名=**試験前体力回復量増加**
- 语义：试炼前回复 +v‰。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6}；(min,max) 取值：[(50, 50), (70, 70), (90, 90), (110, 110), (130, 130), (150, 150)]
- 被谁引用：{'GrowthPanel': 6}
- 示例行：`{"id": "p_effect-before_audition_refresh_stamina_up-0050_0050", "effectValueMin": 50, "effectValueMax": 50}`
  - 文本（GrowthPanel）：「試験前の体力回復量を5%増加」

#### BeforeAuditionRefreshStaminaDown — rows=2  UI名=**試験前体力回復量減少**
- 语义：-v‰。
- 非零字段：{'effectValueMin': 2, 'effectValueMax': 2}；(min,max) 取值：[(250, 250), (750, 750)]
- 被谁引用：{'Item': 2}
- 示例行：`{"id": "p_effect-before_audition_refresh_stamina_down-0250_0250", "effectValueMin": 250, "effectValueMax": 250}`
  - 文本（Item）：「授業・営業終了時、 / ランダムな名前に「基本」を含むスキルカードを2枚削除 / 試験前の体力回復量が25%減少 / ライバルのスコアが10%増加 / （プロデュース中1回）」

#### ShopRerollCountUp — rows=1
- 语义：相談刷新 +v。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Skill': 1}
- 示例行：`{"id": "p_effect-shop_reroll_count_up-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「相談リフレッシュ回数+1」

#### ProduceCardExcludeCountUp — rows=2  UI名=**スキルカード除去**
- 语义：スキルカード除去回数 +v。
- 非零字段：{'effectValueMin': 2, 'effectValueMax': 2}；(min,max) 取值：[(1, 1), (2, 2)]
- 被谁引用：{'Skill': 3}
- 示例行：`{"id": "p_effect-produce_card_exclude_count_up-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「スキルカード除去回数+1」

#### CustomizeProduceCardCountUp — rows=0
- dump 中无 ProduceEffect 行。

#### CustomizeProduceCardProducePointUpMultiple — rows=0
- dump 中无 ProduceEffect 行。

#### CustomizeProduceCardProducePointDownMultiple — rows=2
- 语义：下次定制费用 -v‰。
- 非零字段：{'effectValueMin': 2, 'effectValueMax': 2}；(min,max) 取值：[(200, 200), (500, 500)]
- 被谁引用：{'Item': 1}
- 示例行：`{"id": "p_effect-customize_produce_card_produce_point_down_multiple-0200_0200", "effectValueMin": 200, "effectValueMax": 200}`
  - 文本（Item）：「特別指導開始時、ダンスが900以下の場合、 / ボーカル上昇+25 / スキルカードを選択して強化 / 次の特別指導のカスタマイズを20%割引 / （プロデュース中1回）」

#### VoteCountAddition — rows=27
- 语义：票数 +v。
- 非零字段：{'effectValueMin': 27, 'effectValueMax': 27}；(min,max) 取值：[(800, 800), (1150, 1150), (1500, 1500), (1700, 1700), (1900, 1900), (2000, 2000), (2200, 2200), (2210, 2210), (2400, 2400), (2470, 2470)]
- 被谁引用：{'Event': 3456, 'Item': 9}
- 示例行：`{"id": "p_effect-vote_count_addition-0800_0800", "effectValueMin": 800, "effectValueMax": 800}`
  - 文本（Event）：「ファン投票数+1700」

#### EventBusinessVoteCountUp — rows=9
- 语义：营业票数 +v‰。
- 非零字段：{'effectValueMin': 9, 'effectValueMax': 9}；(min,max) 取值：[(50, 50), (100, 100), (150, 150), (200, 200), (250, 250), (300, 300), (350, 350), (400, 400), (500, 500)]
- 被谁引用：{'Skill': 9}
- 示例行：`{"id": "p_effect-event_business_vote_count_up-0050_0050", "effectValueMin": 50, "effectValueMax": 50}`
  - 文本（Skill）：「営業で獲得するファン投票数を5%増加」

#### EventBusinessVoteCountDown — rows=0
- dump 中无 ProduceEffect 行。

#### EventBusinessExcellentPermilUp — rows=0
- dump 中无 ProduceEffect 行。

#### EventBusinessExcellentPermilDown — rows=0
- dump 中无 ProduceEffect 行。

#### AuditionVoteCountUp — rows=9
- 语义：试炼票数 +v‰。
- 非零字段：{'effectValueMin': 9, 'effectValueMax': 9}；(min,max) 取值：[(50, 50), (100, 100), (150, 150), (200, 200), (250, 250), (300, 300), (350, 350), (400, 400), (500, 500)]
- 被谁引用：{'Skill': 9}
- 示例行：`{"id": "p_effect-audition_vote_count_up-0050_0050", "effectValueMin": 50, "effectValueMax": 50}`
  - 文本（Skill）：「オーディションで獲得するファン投票数を5%増加」

#### AuditionVoteCountDown — rows=0
- dump 中无 ProduceEffect 行。

#### SelfLessonStaminaUp — rows=0
- dump 中无 ProduceEffect 行。

#### SelfLessonStaminaDown — rows=0
- dump 中无 ProduceEffect 行。

#### HighScoreGoldAddition — rows=6
- 语义：活动货币 +v。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6}；(min,max) 取值：[(20, 20), (25, 25), (30, 30), (35, 35), (50, 50), (80, 80)]
- 被谁引用：{'Item': 16}
- 示例行：`{"id": "p_effect-high_score_gold_addition-0020_0020", "effectValueMin": 20, "effectValueMax": 20}`
  - 文本（Item）：「好調効果のスキルカード獲得時、 / ほしのきらめき+20 / 体力回復2 / （プロデュース中5回）」

#### IdolCardProduceCardCustomizeEnable — rows=1
- 语义：允许定制固有卡。
- 非零字段：{}；(min,max) 取值：[(0, 0)]
- 被谁引用：{'Skill': 1}
- 示例行：`{"id": "p_effect-idol_card_produce_card_customize_enable"}`
  - 文本（Skill）：「未定義のパターン(Type: IdolCardProduceCardCustomizeEnable, ProduceCardSearchID: , PickRangeType: , PickCountMin: 0, PickCountMax: 0, EffectValueMin: 0, EffectValueMax: 0, ProduceRewardSetID: )」

#### LegendProduceCardCountAddition — rows=0
- dump 中无 ProduceEffect 行。

#### ExamPermanentLessonStatusEnchant — rows=7
- 语义：以后所有课程开始时挂。
- 非零字段：{'produceExamStatusEnchantId': 7}；(min,max) 取值：[(0, 0)]
- 被谁引用：{'Item': 9}
- 示例行：`{"id": "p_effect-exam_permanent_lesson_status_enchant-enchant-pitem_00-1-048-challenge-enc01", "produceExamStatusEnchantId": "enchant-pitem_00-1-048-challenge-enc01"}`
  - 文本（Item）：「ボーカルパラメータボーナス+8.5% / ライバルのスコアが15%増加 / 以降のレッスン開始時のみ、パラメータ上昇量増加10%」

#### ExamPermanentAuditionStatusEnchant — rows=51
- 语义：以后所有试炼开始时挂持续效果。
- 非零字段：{'produceExamStatusEnchantId': 51}；(min,max) 取值：[(0, 0)]
- 被谁引用：{'CustomizeItem': 135, 'Item': 42}
- 示例行：`{"id": "p_effect-exam_permanent_audition_status_enchant-enchant-customize_pitem-01-04-3-001_00-04…", "produceExamStatusEnchantId": "enchant-customize_pitem-01-04-3-001_00-04-2-001_01-01-1-001_00-04-4-001-enc01"}`
  - 文本（CustomizeItem）：「レッスン終了時、 / 体力回復6 / Pドリンクを選択して獲得 / 以降の試験開始時、集中+3・好調3ターン / （プロデュース中2回）」

#### AuditionNpcWeaken — rows=2  UI名=**ライバルのスコア**
- 语义：对手分数 -v‰。
- 非零字段：{'effectValueMin': 2, 'effectValueMax': 2}；(min,max) 取值：[(500, 500), (800, 800)]
- 被谁引用：{'Item': 1}
- 示例行：`{"id": "p_effect-audition_npc_weaken-0500_0500", "effectValueMin": 500, "effectValueMax": 500}`
  - 文本（Item）：「ライバルのスコアが80%減少」

#### ProduceCustomizeItemUpgrade — rows=1
- 语义：升级定制道具。
- 非零字段：{'pickRangeType': 1, 'pickCountMin': 1, 'pickCountMax': 1}；(min,max) 取值：[(0, 0)]
- 被谁引用：{'Event': 2}
- 示例行：`{"id": "p_effect-produce_customize_item_upgrade-select-01_01", "pickRangeType": "ProducePickRangeType_Select", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本（Event）：「未定義のパターン(Type: ProduceCustomizeItemUpgrade, ProduceCardSearchID: , PickRangeType: Select, PickCountMin: 1, PickCountMax: 1, EffectValueMin: 0, EffectValueMax: 0, ProduceRewardSetID: )」

#### StarPermilUp — rows=9  UI名=**スター性獲得量増加**
- 语义：スター性获得 +v‰。
- 非零字段：{'effectValueMin': 9, 'effectValueMax': 9}；(min,max) 取值：[(50, 50), (100, 100), (150, 150), (200, 200), (250, 250), (300, 300), (350, 350), (400, 400), (500, 500)]
- 被谁引用：{'Skill': 9}
- 示例行：`{"id": "p_effect-star_permil_up-0050_0050", "effectValueMin": 50, "effectValueMax": 50}`
  - 文本（Skill）：「獲得するスター性を5%増加」

#### StarAddition — rows=1  UI名=**スター性獲得**
- 语义：スター性 +v。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(10, 10)]
- 被谁引用：{'Item': 1}
- 示例行：`{"id": "p_effect-star_addition-0010_0010", "effectValueMin": 10, "effectValueMax": 10}`
  - 文本（Item）：「スキルカード獲得時、 / スター性+10 / （プロデュース中20回）」

#### ProduceCardChangeSelect — rows=23  UI名=**セレクトチェンジ**
- 语义：セレクトチェンジ。
- 非零字段：{'effectValueMin': 23, 'effectValueMax': 23, 'produceResourceType': 23, 'produceCardSearchId': 23, 'pickRangeType': 23, 'pickCountMin': 23, 'pickCountMax': 23}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'CustomizeItem': 45, 'Suggestion': 45}
- 示例行：`{"id": "p_effect-produce_card_change_select-0001_0001-p_rd-produce_007-customizeitem-p_card_searc…", "effectValueMin": 1, "effectValueMax": 1, "produceResourceType": "ProduceResourceType_ProduceCard", "produceCardSearchId": "p_card_search-active_skill-mental_skill-deck_all", "pickRangeType": "ProducePickRangeType_Select", "pickCountMin": 1, "pickCountMax": 1}`
  - 文本（CustomizeItem）：「レッスン終了時、 / 体力回復6 / トラブルカード以外のスキルカードを選択して異なるスキルカードにセレクトチェンジ / 以降の試験開始時、集中+3・好調3ターン / （プロデュース中2回）」

#### ProduceDrinkPossessLimitUp — rows=1  UI名=**Pドリンク所持上限増加**
- 语义：饮料上限 +v。
- 非零字段：{'effectValueMin': 1, 'effectValueMax': 1}；(min,max) 取值：[(1, 1)]
- 被谁引用：{'Skill': 1}
- 示例行：`{"id": "p_effect-produce_drink_possess_limit_up-0001_0001", "effectValueMin": 1, "effectValueMax": 1}`
  - 文本（Skill）：「Pドリンク所持上限+1」

#### ShopProduceCardPriceDiscountMultiplePermanent — rows=6  UI名=**相談のスキルカードを割引**
- 语义：永久。
- 非零字段：{'effectValueMin': 6, 'effectValueMax': 6, 'produceCardSearchId': 6}；(min,max) 取值：[(50, 50), (100, 100), (150, 150), (200, 200), (250, 250), (300, 300)]
- 被谁引用：{'GrowthPanel': 6}
- 示例行：`{"id": "p_effect-shop_produce_card_price_discount_multiple_permanent-0050_0050-p_card_search-deck…", "effectValueMin": 50, "effectValueMax": 50, "produceCardSearchId": "p_card_search-deck_all"}`
  - 文本（GrowthPanel）：「相談のスキルカードを5%割引」

## 3. 全部枚举：完整取值与计数

每张表：proto 定义值（含 dump 中未出现者）+ dump 中出现但 proto 未定义者；计数为该值在整个 dump（含嵌套 produceDescriptions）中的出现次数。

### ProduceExamEffectType（proto 定义 169 个值；dump 中出现 138 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 305366 | ProduceCard.produceDescriptions=36201; ProduceCard.produceDescriptions.examEffectType=36201; ProduceExamStatusEnchant.produceDescriptions=24374; ProduceExamStatusEnchant.produceDescriptions.examEffectType=24374 | 占位/未指定。 |
| `ExamLesson` | 1 | 6543 | ProduceCard.produceDescriptions=904; ProduceCard.produceDescriptions.examEffectType=904; ProduceExamEffect.produceDescriptions=788; ProduceExamEffect.produceDescriptions.examEffectType=788 | パラメータ/スコア +v1，effectCount 次（“パラメータ+9（2回）”）。受 好調/集中/強気/全力/熱意 等倍率修正。 |
| `ExamParameterBuff` | 2 | 5962 | ProduceExamAutoEvaluation.examEffectType=1855; ProduceExamGimmickEffectGroup.produceDescriptions=658; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=658; ProduceCard.produceDescriptions=370 | 好調 +effectTurn 回合（参数 ×1.5，ExamSetting.examParameterBuffPermil）。 |
| `ExamBlock` | 3 | 5584 | ProduceCard.produceDescriptions=698; ProduceCard.produceDescriptions.examEffectType=698; ProduceExamGimmickEffectGroup.produceDescriptions=628; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=628 | 元気 +v1（受 やる気 加成、不安/弱気 减成）。 |
| `ExamCardDraw` | 4 | 8 | ProduceExamEffect.effectType=5; EffectGroup.examEffectType=1; EffectGroup.examEffectTypes=1; ProduceDescriptionExamEffect.type=1 | 抽 v1 张牌。 |
| `ExamStaminaConsumptionDown` | 5 | 615 | ProduceExamGimmickEffectGroup.produceDescriptions=95; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=95; ProduceCard.produceDescriptions=66; ProduceCard.produceDescriptions.examEffectType=66 | 消費体力減少 状态 effectTurn 回合（×50%）。 |
| `ExamCardCreateId` | 6 | 466 | ProduceExamGimmickEffectGroup.produceDescriptions=61; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=61; ProduceCard.produceDescriptions=45; ProduceCard.produceDescriptions.examEffectType=45 | 生成指定卡 targetProduceCardId（targetUpgradeCount 段）pickCount 张到 movePositionType；レッスン結束后删除。 |
| `ExamStaminaReduceFix` | 7 | 1130 | ProduceCard.produceDescriptions=213; ProduceCard.produceDescriptions.examEffectType=213; ProduceExamStatusEnchant.produceDescriptions=170; ProduceExamStatusEnchant.produceDescriptions.examEffectType=170 | 体力消費 v1（无视元気直接扣体力）。 |
| `ExamCardMove` | 9 | 44 | ProduceExamEffect.effectType=44 | 移动筛选/选择的卡到 movePositionType（手札/山札/捨札/除外/保留）。 |
| `ExamLessonBuff` | 10 | 6781 | ProduceExamAutoEvaluation.examEffectType=1855; ProduceExamGimmickEffectGroup.produceDescriptions=925; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=925; ProduceCard.produceDescriptions=384 | 集中 +v1（每点使 パラメータ +1）。 |
| `ExamCardUpgrade` | 11 | 198 | ProduceCard.produceDescriptions=43; ProduceCard.produceDescriptions.examEffectType=43; ProduceExamEffect.produceDescriptions=15; ProduceExamEffect.produceDescriptions.examEffectType=15 | レッスン中強化：把筛选到的卡临时升级（pickRange/pickCount）。 |
| `ExamBlockValueMultiple` | 13 | 9 | ProduceExamEffect.effectType=8; EffectGroup.examEffectTypes=1 | 元気 ×(1+v1‰)。 |
| `ExamPlayableValueAdd` | 14 | 2068 | ProduceCard.produceDescriptions=353; ProduceCard.produceDescriptions.examEffectType=353; ProduceExamStatusEnchant.produceDescriptions=234; ProduceExamStatusEnchant.produceDescriptions.examEffectType=234 | スキルカード使用数追加 +effectCount（本回合额外出牌次数）。 |
| `ExamLessonBuffMultiple` | 15 | 116 | ProduceExamEffect.effectType=15; ProduceExamEffect.produceDescriptions=15; ProduceExamEffect.produceDescriptions.examEffectType=15; ProduceExamEffect.customizeProduceDescriptions=15 | 集中強化：集中带来的参数增量 ×(1+v1‰)，effectTurn 回合。 |
| `ExamCardStaminaConsumptionChange` | 17 | 1 | ProduceDescriptionExamEffect.type=1 | （proto/描述表定义，dump 无行）改变某卡消耗体力。 |
| `ExamBlockRestriction` | 18 | 170 | ProduceExamStatusEnchant.produceDescriptions=29; ProduceExamStatusEnchant.produceDescriptions.examEffectType=29; ProduceExamGimmickEffectGroup.produceDescriptions=15; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=15 | 元気増加無効 effectTurn 回合。 |
| `ExamLessonDependBlock` | 19 | 87 | ProduceExamEffect.effectType=83; EffectGroup.examEffectTypes=2; EffectGroup.examEffectType=1; ProduceExamTrigger.effectTypes=1 | 元気 ×v1‰ 的パラメータ（v2 为附加倍率）。 |
| `ExamCardCreateSearch` | 21 | 8 | ProduceExamEffect.effectType=8 | 生成 pickCount 张来自 produceCardSearch（随机池）的卡到 movePositionType；pickCountType=Shortage 时补足到 N 张。 |
| `ExamStatusEnchant` | 22 | 473 | ProduceExamEffect.effectType=448; ProduceDescriptionLabel.produceDescriptions=11; ProduceDescriptionLabel.produceDescriptions.examEffectType=11; EffectGroup.examEffectType=1 | 挂载持续效果 produceExamStatusEnchantId，持续 effectTurn(-1=整场)，最多 effectCount 次；本身无数值。 |
| `ExamMultipleLessonBuffLesson` | 23 | 105 | ProduceExamEffect.effectType=104; EffectGroup.examEffectTypes=1 | パラメータ +v1，集中效果按 v2‰ 倍率适用。 |
| `ExamForcePlayCardSearch` | 24 | 8 | ProduceExamEffect.effectType=8 | 无视费用直接使用筛选到的卡。 |
| `ExamCardStaminaConsumptionDownSpecify` | 26 | 1 | ProduceDescriptionExamEffect.type=1 | （定义，dump 无行）指定卡消耗降低。 |
| `ExamStaminaDamage` | 27 | 1030 | ProduceExamGimmickEffectGroup.produceDescriptions=480; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=480; ProduceExamEffect.effectType=11; ProduceExamEffect.produceDescriptions=11 | 体力減少 v1（试炼 gimmick 用，元気可抵挡）。 |
| `ExamStaminaRecoverFix` | 28 | 693 | ProduceExamStatusEnchant.produceDescriptions=95; ProduceExamStatusEnchant.produceDescriptions.examEffectType=95; ProduceExamGimmickEffectGroup.produceDescriptions=56; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=56 | 体力回復 v1。 |
| `ExamLessonFix` | 29 | 74 | ProduceExamEffect.effectType=14; ProduceExamEffect.produceDescriptions=14; ProduceExamEffect.produceDescriptions.examEffectType=14; ProduceExamEffect.customizeProduceDescriptions=14 | 固定パラメータ +v1（不受强化/低下状态影响）。 |
| `ExamCardDuplicate` | 30 | 42 | ProduceExamStatusEnchant.produceDescriptions=12; ProduceExamStatusEnchant.produceDescriptions.examEffectType=12; ProduceItem.produceDescriptions=6; ProduceItem.produceDescriptions.examEffectType=6 | 複製：把筛选/选择的卡复制到 movePositionType。 |
| `ExamReview` | 31 | 7125 | ProduceExamAutoEvaluation.examEffectType=1855; ProduceExamGimmickEffectGroup.produceDescriptions=899; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=899; ProduceCard.produceDescriptions=513 | 好印象 +v1（回合结束按好印象值加参数，回合开始 -1）。 |
| `ExamLessonValueChangePerPlay` **(dump 中无)** | 32 | 0 | — |  |
| `ExamCardStaminaConsumptionReduce` **(dump 中无)** | 33 | 0 | — |  |
| `ExamReviewValueMultiple` | 36 | 9 | ProduceExamEffect.effectType=8; EffectGroup.examEffectTypes=1 | 好印象 ×(1+v1‰)。 |
| `ExamCardSearchEffectPlayCountBuff` | 38 | 11 | ProduceExamEffect.effectType=8; EffectGroup.examEffectType=1; EffectGroup.examEffectTypes=1; ProduceDescriptionExamEffect.type=1 | スキルカード追加発動：下 effectCount 张符合筛选的卡效果再发动 v1 次，effectTurn 回合内。 |
| `ExamLessonValueMultiple` | 39 | 1405 | ProduceExamGimmickEffectGroup.produceDescriptions=293; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=293; ProduceExamStatusEnchant.produceDescriptions=140; ProduceExamStatusEnchant.produceDescriptions.examEffectType=140 | パラメータ上昇量増加 +v1‰（含好印象带来的上升），effectTurn 回合。 |
| `ExamCardPlayAggressive` | 42 | 5949 | ProduceExamAutoEvaluation.examEffectType=1855; ProduceExamGimmickEffectGroup.produceDescriptions=758; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=758; ProduceCard.produceDescriptions=380 | やる気 +v1（每点使 元気增量 +1）。 |
| `ExamConcentration` | 45 | 5407 | ProduceExamAutoEvaluation.examEffectType=1855; ProduceExamAutoGrowEffectEvaluation.examEffectType=1855; ProduceCard.produceDescriptions=224; ProduceCard.produceDescriptions.examEffectType=224 | 指針→強気（v1=段数 1/2）。 |
| `ExamPreservation` | 46 | 1318 | ProduceCard.produceDescriptions=227; ProduceCard.produceDescriptions.examEffectType=227; ProduceExamStatusEnchant.produceDescriptions=108; ProduceExamStatusEnchant.produceDescriptions.examEffectType=108 | 指針→温存（v1=段数）。 |
| `ExamFullPower` | 47 | 4934 | ProduceExamAutoEvaluation.examEffectType=1855; ProduceExamAutoGrowEffectEvaluation.examEffectType=1855; ProduceCard.produceDescriptions=123; ProduceCard.produceDescriptions.examEffectType=123 | 指針→全力。 |
| `ExamStanceReset` | 48 | 18 | ProduceExamEffect.produceDescriptions=2; ProduceExamEffect.produceDescriptions.examEffectType=2; ProduceExamEffect.customizeProduceDescriptions=2; ProduceExamEffect.customizeProduceDescriptions.examEffectType=2 | 指針解除（解除温存/強気）。 |
| `ExamFullPowerPoint` | 49 | 1917 | ProduceCard.produceDescriptions=312; ProduceCard.produceDescriptions.examEffectType=312; ProduceExamGimmickEffectGroup.produceDescriptions=187; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=187 | 全力値 +v1（回合末 ≥10 则下回合开始消费 10 进入全力）。 |
| `ExamForecast` **(dump 中无)** | 50 | 0 | — |  |
| `ExamFullPowerPointReduce` | 51 | 42 | ProduceExamStatusEnchant.produceDescriptions=8; ProduceExamStatusEnchant.produceDescriptions.examEffectType=8; ProduceItem.produceDescriptions=4; ProduceItem.produceDescriptions.examEffectType=4 | 全力値 -v1。 |
| `ExamLessonAddBlock` **(dump 中无)** | 52 | 0 | — |  |
| `ExamLessonFullPowerPoint` | 56 | 56 | ProduceExamEffect.effectType=55; EffectGroup.examEffectTypes=1 | パラメータ +v1（累计全力値 ×v2‰ 追加），effectCount 次。 |
| `ExamSearchPlayCardStaminaConsumptionChange` | 59 | 6 | ProduceExamEffect.effectType=5; ProduceDescriptionExamEffect.type=1 | 使用的符合筛选的卡消耗体力改为 0，effectCount 次，effectTurn(-1)。 |
| `ExamStaminaReduce` | 60 | 7 | ProduceExamEffect.effectType=5; EffectGroup.examEffectTypes=2 | 最大体力 ×v1‰ 消耗（可为负=回复）。 |
| `ExamUplifting` | 62 | 1 | ProduceDescriptionExamEffect.type=1 | 高揚（定义，dump 无行）：回合末按高揚值加元気。 |
| `ExamExtraTurn` | 63 | 152 | ProduceExamGimmickEffectGroup.produceDescriptions=31; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=31; ProduceExamStatusEnchant.produceDescriptions=21; ProduceExamStatusEnchant.produceDescriptions.examEffectType=21 | ターン追加 +1。 |
| `ExamAntiDebuff` | 66 | 145 | ProduceExamStatusEnchant.produceDescriptions=22; ProduceExamStatusEnchant.produceDescriptions.examEffectType=22; ProduceExamGimmickEffectGroup.produceDescriptions=14; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=14 | 低下状態無効 effectCount 次。 |
| `ExamStaminaConsumptionAdd` | 69 | 300 | ProduceExamGimmickEffectGroup.produceDescriptions=62; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=62; ProduceExamStatusEnchant.produceDescriptions=28; ProduceExamStatusEnchant.produceDescriptions.examEffectType=28 | 消費体力増加 effectTurn 回合（+100%）。 |
| `ExamThresholdDown` **(dump 中无)** | 70 | 0 | — |  |
| `ExamBlockAddDown` | 73 | 113 | ProduceExamStatusEnchant.produceDescriptions=16; ProduceExamStatusEnchant.produceDescriptions.examEffectType=16; ProduceExamGimmickEffectGroup.produceDescriptions=10; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=10 | 不安 effectTurn 回合（元気获得 -33%）。 |
| `ExamBlockAddDownRestriction` | 74 | 1 | ProduceDescriptionExamEffect.type=1 | 不安無効（定义，无行）。 |
| `ExamStaminaRecoverAdd` | 76 | 1 | ProduceDescriptionExamEffect.type=1 | 体力回復効果増加（定义，无行）。 |
| `ExamStaminaReduceChange` | 77 | 1 | ProduceDescriptionExamEffect.type=1 | 体力消費軽減（定义，无行）。 |
| `ExamPanic` | 78 | 98 | ProduceExamGimmickEffectGroup.produceDescriptions=38; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=38; ProduceExamEffect.produceDescriptions=4; ProduceExamEffect.produceDescriptions.examEffectType=4 | 気まぐれ effectTurn 回合：手牌消耗体力随机（候选 ExamSetting.produceExamPanicStaminaCandidates）。 |
| `ExamLessonChangeSpecifyLessThan` | 81 | 1 | ProduceDescriptionExamEffect.type=1 | パラメータ上昇値変更（定义，无行）。 |
| `ExamHandHold` | 82 | 1 | ProduceDescriptionExamEffect.type=1 | 手札持ち越し（定义，无行）。 |
| `ExamStaminaConsumptionAddFix` | 84 | 203 | ProduceExamStatusEnchant.produceDescriptions=45; ProduceExamStatusEnchant.produceDescriptions.examEffectType=45; ProduceItem.produceDescriptions=26; ProduceItem.produceDescriptions.examEffectType=26 | 消費体力追加 +v1（固定值），effectTurn(-1)。 |
| `ExamStaminaConsumptionAddDown` | 85 | 1 | ProduceDescriptionExamEffect.type=1 | （定义，无行）。 |
| `ExamStaminaRecoverRestriction` | 86 | 42 | ProduceExamStatusEnchant.produceDescriptions=12; ProduceExamStatusEnchant.produceDescriptions.examEffectType=12; ProduceItem.produceDescriptions=6; ProduceItem.produceDescriptions.examEffectType=6 | 体力回復無効，effectTurn。 |
| `ExamStaminaConsumptionDownAdd` | 89 | 1 | ProduceDescriptionExamEffect.type=1 | （定义，无行）。 |
| `ExamGetCardUpgrade` | 90 | 1 | ProduceDescriptionExamEffect.type=1 | 生成強化（定义，无行）。 |
| `ExamStaminaConsumptionDownFix` | 93 | 259 | ProduceExamStatusEnchant.produceDescriptions=46; ProduceExamStatusEnchant.produceDescriptions.examEffectType=46; ProduceCard.produceDescriptions=28; ProduceCard.produceDescriptions.examEffectType=28 | 消費体力削減 -v1（固定值），effectTurn(-1)。 |
| `ExamHandGraveCountCardDraw` | 98 | 4 | EffectGroup.examEffectType=1; EffectGroup.examEffectTypes=1; ProduceDescriptionExamEffect.type=1; ProduceExamEffect.effectType=1 | 手札をすべて入れ替える（弃全部手牌并抽同数）。 |
| `ExamHandGraveCountCardAdd` **(dump 中无)** | 99 | 0 | — |  |
| `ExamEffectTimer` | 103 | 161 | ProduceExamEffect.effectType=138; ProduceDescriptionLabel.produceDescriptions=10; ProduceDescriptionLabel.produceDescriptions.examEffectType=10; EffectGroup.examEffectType=1 | 発動予約：v1 回合后（effectCount 次）发动 chainProduceExamEffectId(s)。“次のターン、…”。 |
| `ExamGimmickLessonDebuff` | 105 | 57 | ProduceExamStatusEnchant.produceDescriptions=12; ProduceExamStatusEnchant.produceDescriptions.examEffectType=12; ProduceItem.produceDescriptions=6; ProduceItem.produceDescriptions.examEffectType=6 | 緊張 v1（每点参数 -1），effectTurn。 |
| `ExamGimmickParameterDebuff` | 106 | 229 | ProduceExamGimmickEffectGroup.produceDescriptions=63; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=63; ProduceExamStatusEnchant.produceDescriptions=16; ProduceExamStatusEnchant.produceDescriptions.examEffectType=16 | 不調 effectTurn 回合（参数 ×2/3）。 |
| `ExamGimmickSleepy` | 107 | 82 | ProduceExamStatusEnchant.produceDescriptions=12; ProduceExamStatusEnchant.produceDescriptions.examEffectType=12; ProduceExamGimmickEffectGroup.produceDescriptions=10; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=10 | 弱気 v1（每点元気获得 -1）。 |
| `ExamGimmickEnthusiastic` | 109 | 41 | ProduceDescriptionLabel.produceDescriptions=10; ProduceDescriptionLabel.produceDescriptions.examEffectType=10; ProduceCard.produceDescriptions=4; ProduceCard.produceDescriptions.examEffectType=4 | 熱意（定义，直接行为 0；通过温存解除等产生）：每点参数 +1，回合末清零。 |
| `ExamGimmickPlayCardLimit` | 113 | 43 | ProduceExamEffect.effectType=26; ProduceExamEffect.produceDescriptions=4; ProduceExamEffect.produceDescriptions.examEffectType=4; ProduceExamEffect.customizeProduceDescriptions=4 | 使用不可：筛选到的卡 effectTurn 回合不可用。 |
| `ExamGimmickSlump` | 114 | 191 | ProduceExamGimmickEffectGroup.produceDescriptions=36; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=36; ProduceExamStatusEnchant.produceDescriptions=27; ProduceExamStatusEnchant.produceDescriptions.examEffectType=27 | スランプ effectTurn 回合：参数不上升。 |
| `ExamGimmickStartTurnCardDrawDown` | 115 | 96 | ProduceExamGimmickEffectGroup.produceDescriptions=16; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=16; ProduceExamStatusEnchant.produceDescriptions=14; ProduceExamStatusEnchant.produceDescriptions.examEffectType=14 | 手札減少 v1（回合开始少抽 v1 张），effectTurn。 |
| `ExamStaminaRecoverMultiple` | 117 | 5 | ProduceExamEffect.effectType=4; EffectGroup.examEffectTypes=1 | 最大体力 ×v1‰ 回复。 |
| `ExamLessonPerSearchCount` | 118 | 5 | ProduceExamEffect.effectType=4; EffectGroup.examEffectTypes=1 | パラメータ +v1，按筛选卡数每张 +v2‰（未被引用）。 |
| `ExamBlockFix` | 119 | 228 | ProduceExamStatusEnchant.produceDescriptions=29; ProduceExamStatusEnchant.produceDescriptions.examEffectType=29; ProduceExamEffect.produceDescriptions=17; ProduceExamEffect.produceDescriptions.examEffectType=17 | 固定元気 +v1（不受 buff/debuff 影响）。 |
| `ExamLessonAddMultipleLessonBuff` | 120 | 9 | ProduceExamEffect.effectType=8; EffectGroup.examEffectTypes=1 | 集中 ×(1+v1‰)（“集中1.2倍”）。 |
| `ExamCardStatusEnchant` **(dump 中无)** | 121 | 0 | — |  |
| `ExamBlockDown` | 122 | 2 | ProduceExamEffect.effectType=2 | 元気 -v1‰（百分比削减）。 |
| `ExamLessonChangeSpecifyMoreThan` | 123 | 1 | ProduceDescriptionExamEffect.type=1 | うわの空（定义，无行）。 |
| `ExamLessonDependExamReview` | 124 | 50 | ProduceExamEffect.effectType=47; EffectGroup.examEffectTypes=2; EffectGroup.examEffectType=1 | 好印象 ×v1‰ 的パラメータ。 |
| `ExamLessonDependExamCardPlayAggressive` | 125 | 27 | ProduceExamEffect.effectType=25; EffectGroup.examEffectTypes=2 | やる気 ×v1‰ 的パラメータ。 |
| `ExamReviewDependExamBlock` | 126 | 9 | ProduceExamEffect.effectType=8; EffectGroup.examEffectTypes=1 | 元気 ×v1‰ 的好印象。 |
| `ExamBlockDependExamReview` | 127 | 3 | ProduceExamEffect.effectType=2; EffectGroup.examEffectTypes=1 | 好印象 ×v1‰ 的元気。 |
| `ExamReviewDependExamCardPlayAggressive` | 128 | 2 | EffectGroup.examEffectTypes=1; ProduceExamEffect.effectType=1 | やる気 ×v1‰ 的好印象。 |
| `ExamParameterBuffMultiplePerTurn` | 129 | 487 | ProduceCard.produceDescriptions=62; ProduceCard.produceDescriptions.examEffectType=62; ProduceExamStatusEnchant.produceDescriptions=48; ProduceExamStatusEnchant.produceDescriptions.examEffectType=48 | 絶好調 effectTurn 回合：好調的加成按好調剩余回合每回合 +10%。 |
| `ExamLessonBuffDependParameterBuff` | 130 | 12 | ProduceExamEffect.effectType=11; EffectGroup.examEffectTypes=1 | 好調回合数 ×v1‰ 的集中（v2 存在时同时把集中减半等）。 |
| `ExamLessonDependParameterBuff` | 131 | 21 | ProduceExamEffect.effectType=20; EffectGroup.examEffectTypes=1 | 好調回合数 ×v1‰ 的パラメータ。 |
| `ExamLessonAddMultipleParameterBuff` | 132 | 42 | ProduceExamEffect.effectType=41; EffectGroup.examEffectTypes=1 | パラメータ +v1，其中好調加成按 v2‰ 倍率（“好調効果を2倍適用”）。 |
| `ExamBlockPerUseCardCount` | 133 | 14 | ProduceExamEffect.effectType=13; EffectGroup.examEffectTypes=1 | 元気 +v1，本场每用 1 张卡 元気增量 +v2。 |
| `ExamChainEffect` **(dump 中无)** | 140 | 0 | — |  |
| `StanceLock` | 141 | 21 | ProduceCard.produceDescriptions=4; ProduceCard.produceDescriptions.examEffectType=4; ProduceExamEffect.effectType=2; ProduceExamEffect.produceDescriptions=2 | 指針固定 effectTurn 回合（不能变更指針与段数）。 |
| `ExamLessonDependStamina` | 142 | 4 | ProduceExamEffect.effectType=3; EffectGroup.examEffectTypes=1 | 当前体力 ×v1‰ 的パラメータ。 |
| `ExamBlockAddMultipleAggressive` | 143 | 24 | ProduceExamEffect.effectType=23; EffectGroup.examEffectTypes=1 | 元気 +v1，其中やる気加成按 v2‰ 倍率适用（“やる気効果を1.4倍適用”）。 |
| `ExamLessonDependStaminaConsumptionSum` | 144 | 8 | ProduceExamEffect.effectType=7; EffectGroup.examEffectTypes=1 | 本场消耗体力总量 ×v1‰ 的パラメータ。 |
| `ExamChainEffectPerPassedTurn` **(dump 中无)** | 145 | 0 | — |  |
| `ExamChainEffectPerRemainTurn` **(dump 中无)** | 146 | 0 | — |  |
| `ExamLessonDependPlayCardCountSum` | 147 | 12 | ProduceExamEffect.effectType=11; EffectGroup.examEffectTypes=1 | パラメータ +v1，本场每用 1 张卡再 +v2。 |
| `ExamDebuffRecover` | 148 | 196 | ProduceExamGimmickEffectGroup.produceDescriptions=78; ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType=78; ProduceExamEffect.produceDescriptions=5; ProduceExamEffect.produceDescriptions.examEffectType=5 | 低下状態回復 v1 个（0=全部）。 |
| `ExamAggressiveValueMultiple` | 149 | 5 | ProduceExamEffect.effectType=4; EffectGroup.examEffectTypes=1 | やる気 ×(1+v1‰)（“やる気1.3倍”）。 |
| `ExamItemFireLimitAdd` | 150 | 1 | ProduceExamEffect.effectType=1 | 偶像固有 P道具 发动次数 +v1。 |
| `ExamReviewReduce` | 151 | 35 | ProduceExamStatusEnchant.produceDescriptions=6; ProduceExamStatusEnchant.produceDescriptions.examEffectType=6; ProduceExamEffect.produceDescriptions=3; ProduceExamEffect.produceDescriptions.examEffectType=3 | 好印象 -v1。 |
| `ExamAggressiveReduce` | 152 | 52 | ProduceExamStatusEnchant.produceDescriptions=10; ProduceExamStatusEnchant.produceDescriptions.examEffectType=10; ProduceItem.produceDescriptions=5; ProduceItem.produceDescriptions.examEffectType=5 | やる気 -v1。 |
| `ExamLessonBuffReduce` | 153 | 36 | ProduceExamStatusEnchant.produceDescriptions=8; ProduceExamStatusEnchant.produceDescriptions.examEffectType=8; ProduceItem.produceDescriptions=4; ProduceItem.produceDescriptions.examEffectType=4 | 集中 -v1。 |
| `ExamParameterBuffReduce` | 154 | 67 | ProduceExamStatusEnchant.produceDescriptions=10; ProduceExamStatusEnchant.produceDescriptions.examEffectType=10; ProduceExamEffect.produceDescriptions=7; ProduceExamEffect.produceDescriptions.examEffectType=7 | 好調 -v1 回合。 |
| `ExamLessonValueMultipleDown` | 155 | 169 | ProduceExamStatusEnchant.produceDescriptions=38; ProduceExamStatusEnchant.produceDescriptions.examEffectType=38; ProduceItem.produceDescriptions=22; ProduceItem.produceDescriptions.examEffectType=22 | パラメータ上昇量減少 v1‰，effectTurn。 |
| `ExamAddGrowEffect` | 156 | 423 | ProduceExamEffect.effectType=160; ProduceCardStatusEnchant.produceDescriptions=77; ProduceCardStatusEnchant.produceDescriptions.examEffectType=77; ProduceCard.produceDescriptions=53 | 成長：对筛选到的卡（pickRange All）附加 produceCardGrowEffectIds（レッスン終了まで）。 |
| `ExamParameterBuffPerSearchCount` | 157 | 1 | EffectGroup.examEffectTypes=1 | 按筛选卡数加好調（1 行）。 |
| `ExamLessonBuffPerSearchCount` | 158 | 2 | EffectGroup.examEffectTypes=1; ProduceExamEffect.effectType=1 | 筛选卡数每 v2‰⁻¹ 张 集中+1（“除外2枚につき集中+1”）。 |
| `ExamReviewPerSearchCount` | 159 | 5 | ProduceExamEffect.effectType=4; EffectGroup.examEffectTypes=1 | 筛选卡每张 好印象 +v2‰⁻¹。 |
| `ExamAggressivePerSearchCount` | 160 | 1 | EffectGroup.examEffectTypes=1 | 按筛选卡数每 v2 张 やる気+…（dump 1 行）。 |
| `ExamBlockPerSearchCount` | 161 | 1 | EffectGroup.examEffectTypes=1 | 按筛选卡数增加元気（1 行）。 |
| `ExamFullPowerPointPerSearchCount` | 162 | 1 | EffectGroup.examEffectTypes=1 | 按筛选卡数加全力値（1 行）。 |
| `ExamLessonDependBlockAndSearchCount` | 163 | 4 | EffectGroup.examEffectTypes=2; ProduceExamEffect.effectType=2 | 筛选卡每张 元気×v2‰ 的パラメータ。 |
| `ExamLessonDependAggressiveAndSearchCount` | 164 | 2 | EffectGroup.examEffectTypes=2 | 筛选卡每张 やる気×v2‰ 的パラメータ。 |
| `ExamLessonDependReviewAndSearchCount` | 165 | 2 | EffectGroup.examEffectTypes=2 | 筛选卡每张 好印象×v2‰ 的パラメータ。 |
| `ExamEffectPerSearchCount` **(dump 中无)** | 166 | 0 | — |  |
| `ExamOverPreservation` | 167 | 83 | ProduceCard.produceDescriptions=13; ProduceCard.produceDescriptions.examEffectType=13; ProduceExamStatusEnchant.produceDescriptions=8; ProduceExamStatusEnchant.produceDescriptions.examEffectType=8 | 指針→のんびり（温存 3 段）。 |
| `ExamParameterBuffDependLessonBuff` | 168 | 5 | ProduceExamEffect.effectType=4; EffectGroup.examEffectTypes=1 | 集中 ×v1‰ 的好調回合（v2 存在时集中减半）。 |
| `ExamAggressiveDependReview` | 169 | 1 | EffectGroup.examEffectTypes=1 | 按好印象比例增加やる気（dump 1 行）。 |
| `ExamEnthusiasticAdditive` | 170 | 243 | ProduceExamEffect.produceDescriptions=32; ProduceExamEffect.produceDescriptions.examEffectType=32; ProduceExamEffect.customizeProduceDescriptions=32; ProduceExamEffect.customizeProduceDescriptions.examEffectType=32 | 熱意追加 +v1（固定值），effectTurn(-1)。 |
| `ExamEnthusiasticMultiple` | 171 | 228 | ProduceExamEffect.produceDescriptions=33; ProduceExamEffect.produceDescriptions.examEffectType=33; ProduceExamEffect.customizeProduceDescriptions=33; ProduceExamEffect.customizeProduceDescriptions.examEffectType=33 | 熱意増加 +v1‰。 |
| `ExamFullPowerLessonMultipleAdditive` | 172 | 37 | ProduceExamEffect.produceDescriptions=4; ProduceExamEffect.produceDescriptions.examEffectType=4; ProduceExamEffect.customizeProduceDescriptions=4; ProduceExamEffect.customizeProduceDescriptions.examEffectType=4 | 全力強化：全力倍率再 +v1‰，effectTurn。 |
| `ExamConcentrationLessonMultipleAdditive` | 173 | 20 | ProduceExamEffect.effectType=2; ProduceExamEffect.produceDescriptions=2; ProduceExamEffect.produceDescriptions.examEffectType=2; ProduceExamEffect.customizeProduceDescriptions=2 | 強気強化：強気倍率再 +v1‰。 |
| `ExamLessonBuffAdditive` | 174 | 137 | ProduceExamStatusEnchant.produceDescriptions=19; ProduceExamStatusEnchant.produceDescriptions.examEffectType=19; ProduceExamEffect.produceDescriptions=12; ProduceExamEffect.produceDescriptions.examEffectType=12 | 集中増加量増加 +v1‰，effectTurn。 |
| `ExamParameterBuffAdditive` | 175 | 59 | ProduceExamEffect.effectType=7; ProduceExamEffect.produceDescriptions=7; ProduceExamEffect.produceDescriptions.examEffectType=7; ProduceExamEffect.customizeProduceDescriptions=7 | 好調増加量増加 +v1‰。 |
| `ExamAggressiveAdditive` | 176 | 63 | ProduceExamStatusEnchant.produceDescriptions=9; ProduceExamStatusEnchant.produceDescriptions.examEffectType=9; ProduceExamEffect.effectType=5; ProduceExamEffect.produceDescriptions=5 | やる気増加量増加 +v1‰。 |
| `ExamReviewAdditive` | 177 | 89 | ProduceExamStatusEnchant.produceDescriptions=11; ProduceExamStatusEnchant.produceDescriptions.examEffectType=11; ProduceCard.produceDescriptions=8; ProduceCard.produceDescriptions.examEffectType=8 | 好印象増加量増加 +v1‰。 |
| `ExamFullPowerPointAdditive` | 178 | 79 | ProduceExamStatusEnchant.produceDescriptions=12; ProduceExamStatusEnchant.produceDescriptions.examEffectType=12; ProduceExamEffect.produceDescriptions=7; ProduceExamEffect.produceDescriptions.examEffectType=7 | 全力値増加量増加 +v1‰。 |
| `ExamGrowEffectLessonAddAdditive` | 179 | 2 | EffectGroup.examEffectTypes=1; ProduceDescriptionExamEffect.type=1 | （定义，无行）。 |
| `ExamParameterBuffMultiplePerTurnReduce` | 180 | 16 | ProduceExamEffect.produceDescriptions=2; ProduceExamEffect.produceDescriptions.examEffectType=2; ProduceExamEffect.customizeProduceDescriptions=2; ProduceExamEffect.customizeProduceDescriptions.examEffectType=2 | 絶好調 -v1。 |
| `ExamLessonValueMultipleDependReviewOrAggressive` | 181 | 36 | ProduceCard.produceDescriptions=4; ProduceCard.produceDescriptions.examEffectType=4; ProduceExamStatusEnchant.produceDescriptions=4; ProduceExamStatusEnchant.produceDescriptions.examEffectType=4 | プライド effectTurn 回合：min(好印象,やる気)×2%（上限 50%）参数加成。 |
| `ExamReviewMultiple` | 182 | 202 | ProduceCard.produceDescriptions=26; ProduceCard.produceDescriptions.examEffectType=26; ProduceExamEffect.produceDescriptions=20; ProduceExamEffect.produceDescriptions.examEffectType=20 | 好印象強化 +v1‰（好印象带来的参数上升倍率），effectTurn。 |
| `ExamMultipleEnthusiasticLesson` | 183 | 4 | ProduceExamEffect.effectType=3; EffectGroup.examEffectTypes=1 | パラメータ +v1，熱意效果 ×v2‰。 |
| `ExamMultipleConcentrationLesson` | 184 | 1 | EffectGroup.examEffectTypes=1 | 強気效果倍率适用（1 行）。 |
| `ExamMultipleFullPowerLesson` | 185 | 1 | EffectGroup.examEffectTypes=1 | 全力效果倍率适用（1 行）。 |
| `ExamLessonDependBlockConsumptionSum` | 186 | 9 | ProduceExamEffect.effectType=7; EffectGroup.examEffectTypes=2 | 本场消耗元気总量 ×v1‰ 的パラメータ。 |
| `ExamForcePlayCardSearchWithCost` | 187 | 1 | ProduceExamEffect.effectType=1 | 选择一张卡付费使用。 |
| `ExamBlockDependBlockConsumptionSum` | 188 | 4 | ProduceExamEffect.effectType=3; EffectGroup.examEffectTypes=1 | 本场消耗元気总量 ×v1‰ 的元気。 |
| `ExamEnthusiasticTurnAdd` | 189 | 1 | EffectGroup.examEffectTypes=1 | 熱意回合延长（1 行）。 |
| `ExamEffectTimerEndTurn` **(dump 中无)** | 190 | 0 | — |  |
| `ExamStanceLockConcentration` **(dump 中无)** | 191 | 0 | — |  |
| `ExamStanceLockFullPower` **(dump 中无)** | 192 | 0 | — |  |
| `ExamStanceLockPreservation` **(dump 中无)** | 193 | 0 | — |  |
| `ExamCardShuffleDeckGrave` **(dump 中无)** | 194 | 0 | — |  |
| `ExamReviewCountAdd` | 195 | 21 | ProduceCard.produceDescriptions=4; ProduceCard.produceDescriptions.examEffectType=4; ProduceExamEffect.produceDescriptions=2; ProduceExamEffect.produceDescriptions.examEffectType=2 | 好印象追加発動 +v1（回合末好印象结算次数），effectTurn。 |
| `ExamReviewTurnEndReduceLock` **(dump 中无)** | 196 | 0 | — |  |
| `ExamParameterBuffTurnEndReduceLock` **(dump 中无)** | 197 | 0 | — |  |
| `ExamBuffConsumptionDown` **(dump 中无)** | 198 | 0 | — |  |
| `ExamBuffConsumptionAdd` **(dump 中无)** | 199 | 0 | — |  |
| `ExamSearchPlayCardBuffConsumptionChange` **(dump 中无)** | 200 | 0 | — |  |
| `ExamPlayCardLimitPlayableValueAdd` **(dump 中无)** | 201 | 0 | — |  |
| `ExamReviewDependReviewConsumptionSum` **(dump 中无)** | 202 | 0 | — |  |
| `ExamLessonBuffReduceCancellable` **(dump 中无)** | 203 | 0 | — |  |
| `ExamParameterBuffReduceCancellable` **(dump 中无)** | 204 | 0 | — |  |
| `ExamAggressiveReduceCancellable` **(dump 中无)** | 205 | 0 | — |  |
| `ExamReviewReduceCancellable` **(dump 中无)** | 206 | 0 | — |  |
| `ExamFullPowerPointReduceCancellable` **(dump 中无)** | 207 | 0 | — |  |
| `ExamStatusEnchantTurnAdd` **(dump 中无)** | 208 | 0 | — |  |
| `ExamStatusEnchantCountAdd` **(dump 中无)** | 209 | 0 | — |  |
| `ExamParameterBuffAdditiveFix` | 210 | 2 | EffectGroup.examEffectTypes=1; ProduceDescriptionExamEffect.type=1 | 好調増加量追加 +v1（固定）（定义，无行）。 |
| `ExamLessonBuffAdditiveFix` | 211 | 28 | ProduceCard.produceDescriptions=8; ProduceCard.produceDescriptions.examEffectType=8; ProduceExamEffect.effectType=2; ProduceExamEffect.produceDescriptions=2 | 集中増加量追加 +v1（固定），effectTurn。 |
| `ExamAggressiveAdditiveFix` | 212 | 15 | ProduceCard.produceDescriptions=4; ProduceCard.produceDescriptions.examEffectType=4; EffectGroup.examEffectTypes=1; ProduceDescriptionExamEffect.type=1 | やる気増加量追加 +v1。 |
| `ExamReviewAdditiveFix` | 213 | 2 | EffectGroup.examEffectTypes=1; ProduceDescriptionExamEffect.type=1 | （定义，无行）。 |
| `ExamFullPowerPointAdditiveFix` | 214 | 2 | EffectGroup.examEffectTypes=1; ProduceDescriptionExamEffect.type=1 | （定义，无行）。 |
| `ExamMoveGrowEffect` | 215 | 1 | EffectGroup.examEffectTypes=1 | 移动成长效果（1 行）。 |
| `ExamLessonDependEnthusiasticGetSum` | 216 | 1 | EffectGroup.examEffectTypes=1 | 本场累计熱意 比例的パラメータ（1 行）。 |
| `ExamCardShuffleDeckLost` **(dump 中无)** | 217 | 0 | — |  |
| `ExamFullPowerPointDependFullPowerPointGetSum` | 218 | 1 | EffectGroup.examEffectTypes=1 | 按累计全力値加全力値（1 行）。 |
| `ExamStatusEnchantEncore` | 219 | 60 | ProduceCard.produceDescriptions=20; ProduceCard.produceDescriptions.examEffectType=20; ProduceExamEffect.effectType=5; ProduceExamEffect.customizeProduceDescriptions=5 | 再演：挂载 produceExamStatusEnchantId，条件满足时再次使用自身（不付费用），effectCount 次、每回合 1 次；isOncePlayEffect。 |

### ProduceExamPhaseType（proto 定义 57 个值；dump 中出现 30 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ExamCardDraw` **(dump 中无)** | 1 | 0 | — |  |
| `ExamCardPlay` | 2 | 82 | ProduceExamTrigger.phaseTypes=82 | スキルカード使用時（结算前；配合 produceCardSearch=playing 表示“使用的是 X 卡”）。 |
| `ExamCardPlayAfter` | 3 | 194 | ProduceExamTrigger.phaseTypes=194 | スキルカード使用後（结算后）。 |
| `ExamStartTurn` | 4 | 95 | ProduceExamTrigger.phaseTypes=95 | ターン開始時（发牌前）。 |
| `ExamEndTurn` | 5 | 65 | ProduceExamTrigger.phaseTypes=65 | ターン終了時。 |
| `ExamStartExam` | 6 | 12 | ProduceExamTrigger.phaseTypes=12 | レッスン/試験 开始时。 |
| `ExamCardMove` **(dump 中无)** | 7 | 0 | — |  |
| `ExamCardAdd` **(dump 中无)** | 8 | 0 | — |  |
| `ExamLesson` **(dump 中无)** | 9 | 0 | — |  |
| `ExamForecast` **(dump 中无)** | 10 | 0 | — |  |
| `ExamSearchCardPlay` | 11 | 2 | ProduceExamTrigger.phaseTypes=2 | 使用符合筛选的卡时（2 行，描述未定义）。 |
| `ExamStanceChange` **(dump 中无)** | 12 | 0 | — |  |
| `ExamStatusChange` | 13 | 28 | ProduceExamTrigger.phaseTypes=28 | 直接効果で X が N 以上増加後（effectTypes+phaseValue）。 |
| `ExamTurnCheck` **(dump 中无)** | 16 | 0 | — |  |
| `ExamUseDrink` **(dump 中无)** | 17 | 0 | — |  |
| `ExamGetPoint` **(dump 中无)** | 18 | 0 | — |  |
| `ExamShuffle` **(dump 中无)** | 19 | 0 | — |  |
| `ExamStaminaReduce` | 20 | 1 | ProduceExamTrigger.phaseTypes=1 | 直接効果で体力が減少した時。 |
| `ExamTurnTimer` | 21 | 19 | ProduceExamTrigger.phaseTypes=19 | 第 N 回合开始时（phaseValue=N；用于 ExamEffectTimer 延迟）。 |
| `ExamTurnInterval` | 22 | 12 | ProduceExamTrigger.phaseTypes=12 | 每 N 回合（回合开始）。 |
| `ExamPlayCountInterval` | 23 | 26 | ProduceExamTrigger.phaseTypes=26 | 每使用 N 张卡时。 |
| `ExamStaminaReduceCard` | 24 | 2 | ProduceExamTrigger.phaseTypes=2 | スキルカードコストで体力減少時。 |
| `ExamPlayTurnCountInterval` | 25 | 8 | ProduceExamTrigger.phaseTypes=8 | 回合内每使用 N 张（筛选）卡。 |
| `StartPlay` | 27 | 23 | ProduceExamTrigger.phaseTypes=23 | ターン開始後（发牌后、可出牌时）。 |
| `StartExamPlay` | 28 | 1 | ProduceExamTrigger.phaseTypes=1 | レッスン開始後（首回合发牌后）。 |
| `ExamCardMoveHand` | 29 | 1 | ProduceExamTrigger.phaseTypes=1 | 手札に移動した時。 |
| `ExamCardMoveGrave` | 30 | 1 | ProduceExamTrigger.phaseTypes=1 | （自身）捨札に移動した時。 |
| `ExamCardMoveLost` | 31 | 2 | ProduceExamTrigger.phaseTypes=2 | 除外に移動した時。 |
| `ExamLessonParameterUp` **(dump 中无)** | 33 | 0 | — |  |
| `ExamBuffConsume` | 34 | 7 | ProduceExamTrigger.phaseTypes=7 | スキルカードコストで強化状態を消費した時（好調/集中等作费用）。 |
| `ExamStanceChangeCountInterval` | 35 | 3 | ProduceExamTrigger.phaseTypes=3 | 直接効果で指針を N 回変更するたび。 |
| `ExamStanceChangeCount` **(dump 中无)** | 36 | 0 | — |  |
| `ExamStanceChangeConcentration` | 37 | 6 | ProduceExamTrigger.phaseTypes=6 | 直接効果で強気になった時（phaseValue=段）。 |
| `ExamStanceChangePreservation` | 38 | 1 | ProduceExamTrigger.phaseTypes=1 | 温存になった時。 |
| `ExamStanceChangeFullPower` | 39 | 6 | ProduceExamTrigger.phaseTypes=6 | 全力になった時。 |
| `ExamStanceReset` **(dump 中无)** | 40 | 0 | — |  |
| `ExamTurnSkip` | 41 | 2 | ProduceExamTrigger.phaseTypes=2 | ターンスキップ時。 |
| `ExamEndTurnTimer` **(dump 中无)** | 42 | 0 | — |  |
| `ExamEndTurnInterval` | 43 | 2 | ProduceExamTrigger.phaseTypes=2 | 每 N 回合的回合结束时（phaseValue=N）。 |
| `ExamPlayCountIntervalAfter` | 44 | 5 | ProduceExamTrigger.phaseTypes=5 | 使用后每 N 张。 |
| `ExamStanceChangeFromConcentration` | 45 | 1 | ProduceExamTrigger.phaseTypes=1 | 強気を解除後。 |
| `ExamStanceChangeFromPreservation` **(dump 中无)** | 46 | 0 | — |  |
| `ExamStanceChangeFromFullPower` | 47 | 5 | ProduceExamTrigger.phaseTypes=5 | 全力を解除後。 |
| `ExamCardUpgrade` **(dump 中无)** | 48 | 0 | — |  |
| `ExamPlayCardMoveGrave` **(dump 中无)** | 49 | 0 | — |  |
| `ExamParameterBuffUpInterval` **(dump 中无)** | 50 | 0 | — |  |
| `ExamLessonBuffUpInterval` **(dump 中无)** | 51 | 0 | — |  |
| `ExamReviewUpInterval` **(dump 中无)** | 52 | 0 | — |  |
| `ExamAggressiveUpInterval` | 53 | 1 | ProduceExamTrigger.phaseTypes=1 | 直接効果でやる気が N 回増加時。 |
| `ExamFullPowerPointUpInterval` **(dump 中无)** | 54 | 0 | — |  |
| `ExamStanceChangePreservationInterval` **(dump 中无)** | 55 | 0 | — |  |
| `ExamStanceChangeConcentrationInterval` **(dump 中无)** | 56 | 0 | — |  |
| `ExamStanceChangeFullPowerInterval` **(dump 中无)** | 57 | 0 | — |  |
| `ExamCardUpgradeInterval` **(dump 中无)** | 58 | 0 | — |  |
| `ExamCardDrawInterval` **(dump 中无)** | 59 | 0 | — |  |
| `None` | 999 | 63 | ProduceExamTrigger.phaseTypes=63 | 无时机，纯条件（用于 playProduceExamTriggerId 使用条件、GrowEffect 的条件）。 |

### ProduceExamFieldStatusType（proto 定义 42 个值；dump 中出现 29 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 791 | ProduceExamGimmickEffectGroup.fieldStatusType=791 | 无条件。 |
| `ParameterBuff` | 1 | 301 | ProduceExamGimmickEffectGroup.fieldStatusType=291; ProduceExamTrigger.fieldStatusTypes=10 | 好調状態（Not=非好調）。 |
| `StaminaUpMultiple` | 4 | 106 | ProduceExamGimmickEffectGroup.fieldStatusType=82; ProduceExamTrigger.fieldStatusTypes=24 | 体力 ≥ v‰ 最大体力。 |
| `StaminaLessMultiple` | 5 | 31 | ProduceExamGimmickEffectGroup.fieldStatusType=17; ProduceExamTrigger.fieldStatusTypes=14 | 体力 ≤ v‰。 |
| `StaminaConsumptionDown` | 9 | 30 | ProduceExamGimmickEffectGroup.fieldStatusType=24; ProduceExamTrigger.fieldStatusTypes=6 | 消費体力減少状態。 |
| `ConcentrationUp` | 11 | 27 | ProduceExamTrigger.fieldStatusTypes=17; ProduceExamGimmickEffectGroup.fieldStatusType=10 | 強気（v=段）。 |
| `PreservationUp` | 12 | 40 | ProduceExamGimmickEffectGroup.fieldStatusType=24; ProduceExamTrigger.fieldStatusTypes=16 | 温存（v=段）。 |
| `FullPowerUp` | 13 | 21 | ProduceExamTrigger.fieldStatusTypes=21 | 全力。 |
| `PlayCardRestriction` **(dump 中无)** | 16 | 0 | — |  |
| `NoBlock` | 18 | 6 | ProduceExamTrigger.fieldStatusTypes=6 | 元気 = 0。 |
| `PlayCardSkill` | 19 | 52 | ProduceExamGimmickEffectGroup.fieldStatusType=50; ProduceExamTrigger.fieldStatusTypes=2 | 直前使用的是メンタル卡。 |
| `PlayCardLesson` | 20 | 35 | ProduceExamGimmickEffectGroup.fieldStatusType=33; ProduceExamTrigger.fieldStatusTypes=2 | 直前使用的是アクティブ卡。 |
| `PlayCardSupport` **(dump 中无)** | 21 | 0 | — |  |
| `TurnProgressUp` | 22 | 5 | ProduceExamTrigger.fieldStatusTypes=5 | 第 v+1 回合以后。 |
| `ConditionThresholdMultiple` | 27 | 198 | ProduceExamGimmickEffectGroup.fieldStatusType=196; ProduceExamTrigger.fieldStatusTypes=2 | レッスンCLEAR 条件的 v‰ 以上（試験：スコア ≥ v）。 |
| `ConditionThresholdMultipleDown` | 28 | 23 | ProduceExamGimmickEffectGroup.fieldStatusType=20; ProduceExamTrigger.fieldStatusTypes=3 | CLEAR 的 v‰ 以下。 |
| `LessonBuffUp` | 33 | 577 | ProduceExamGimmickEffectGroup.fieldStatusType=534; ProduceExamTrigger.fieldStatusTypes=43 | 集中 ≥ v。 |
| `BlockUp` | 34 | 147 | ProduceExamGimmickEffectGroup.fieldStatusType=114; ProduceExamTrigger.fieldStatusTypes=33 | 元気 ≥ v。 |
| `ReviewUp` | 35 | 551 | ProduceExamGimmickEffectGroup.fieldStatusType=506; ProduceExamTrigger.fieldStatusTypes=45 | 好印象 ≥ v。 |
| `GimmickLessonDebuffUp` **(dump 中无)** | 36 | 0 | — |  |
| `GimmickSleepyUp` **(dump 中无)** | 37 | 0 | — |  |
| `ParameterBuffUp` | 38 | 174 | ProduceExamGimmickEffectGroup.fieldStatusType=131; ProduceExamTrigger.fieldStatusTypes=43 | 好調残り ≥ v ターン。 |
| `BlockAddDown` **(dump 中无)** | 39 | 0 | — |  |
| `GimmickParameterDebuff` **(dump 中无)** | 40 | 0 | — |  |
| `RemainingTurn` | 41 | 14 | ProduceExamTrigger.fieldStatusTypes=14 | 残り ≤ v ターン。 |
| `CardPlayAggressiveUp` | 42 | 550 | ProduceExamGimmickEffectGroup.fieldStatusType=516; ProduceExamTrigger.fieldStatusTypes=34 | やる気 ≥ v。 |
| `ParameterLessThan` **(dump 中无)** | 43 | 0 | — |  |
| `FullPowerPointUp` | 44 | 13 | ProduceExamTrigger.fieldStatusTypes=13 | 全力値 ≥ v。 |
| `FullPowerPointGetSumUp` | 45 | 145 | ProduceExamGimmickEffectGroup.fieldStatusType=136; ProduceExamTrigger.fieldStatusTypes=9 | 本场累计全力値 ≥ v。 |
| `NoStance` | 46 | 4 | ProduceExamTrigger.fieldStatusTypes=4 | 无指針（Not=いずれかの指針）。 |
| `StanceChangeCountUp` | 47 | 66 | ProduceExamGimmickEffectGroup.fieldStatusType=60; ProduceExamTrigger.fieldStatusTypes=6 | 指針変更回数 ≥ v。 |
| `ConcentrationChangeCountUp` | 48 | 103 | ProduceExamGimmickEffectGroup.fieldStatusType=93; ProduceExamTrigger.fieldStatusTypes=10 | 強気になった回数 ≥ v。 |
| `PreservationChangeCountUp` | 49 | 63 | ProduceExamGimmickEffectGroup.fieldStatusType=56; ProduceExamTrigger.fieldStatusTypes=7 | 温存になった回数 ≥ v。 |
| `FullPowerChangeCountUp` | 50 | 25 | ProduceExamGimmickEffectGroup.fieldStatusType=22; ProduceExamTrigger.fieldStatusTypes=3 | 全力になった回数 ≥ v。 |
| `CardSearchCountUp` | 51 | 19 | ProduceExamTrigger.fieldStatusTypes=19 | fieldStatusProduceCardSearchIds 命中的卡 ≥ v 张。 |
| `PlayCardSearch` **(dump 中无)** | 52 | 0 | — |  |
| `ParameterBuffMultiplePerTurnUp` | 53 | 8 | ProduceExamTrigger.fieldStatusTypes=7; ProduceExamGimmickEffectGroup.fieldStatusType=1 | 絶好調 ≥ v。 |
| `EnthusiasticUp` **(dump 中无)** | 54 | 0 | — |  |
| `EnchantCountUp` **(dump 中无)** | 55 | 0 | — |  |
| `TurnPlayCardCountUp` **(dump 中无)** | 56 | 0 | — |  |
| `DeckCardAllNoDuplicate` **(dump 中无)** | 57 | 0 | — |  |
| `DebuffCountUp` **(dump 中无)** | 58 | 0 | — |  |

### ProduceExamTriggerCheckType（proto 定义 2 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 2949 | ProduceExamGimmickEffectGroup.fieldStatusCheckType=2949 |  |
| `Not` | 1 | 795 | ProduceExamGimmickEffectGroup.fieldStatusCheckType=758; ProduceExamTrigger.fieldStatusCheckTypes=37 |  |

### ProduceEffectType（proto 定义 119 个值；dump 中出现 103 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 39 | EffectGroup.produceEffectType=39 |  |
| `VocalAddition` | 1 | 239 | ProduceEffect.produceEffectType=200; SupportCardProduceSkillFilter.produceEffectTypes=35; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1 | Vocal +v。 |
| `DanceAddition` | 2 | 239 | ProduceEffect.produceEffectType=200; SupportCardProduceSkillFilter.produceEffectTypes=35; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1 | Dance +v。 |
| `VisualAddition` | 3 | 239 | ProduceEffect.produceEffectType=200; SupportCardProduceSkillFilter.produceEffectTypes=35; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1 | Visual +v。 |
| `VocalDown` | 4 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `DanceDown` | 5 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `VisualDown` | 6 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `VocalGrowthRateAddition` | 7 | 89 | ProduceEffect.produceEffectType=86; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | Vocal 成长率 +v‰。 |
| `DanceGrowthRateAddition` | 8 | 89 | ProduceEffect.produceEffectType=86; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | 。 |
| `VisualGrowthRateAddition` | 9 | 89 | ProduceEffect.produceEffectType=86; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | 。 |
| `VocalGrowthRateDown` | 10 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `DanceGrowthRateDown` | 11 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `VisualGrowthRateDown` | 12 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `StaminaRecoverFix` | 13 | 18 | ProduceEffect.produceEffectType=11; SupportCardProduceSkillFilter.produceEffectTypes=3; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1 | 体力 +v。 |
| `StaminaRecoverMultiple` | 14 | 15 | ProduceEffect.produceEffectType=12; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 最大体力 ×v‰ 回复。 |
| `StaminaReduceFix` | 15 | 16 | ProduceEffect.produceEffectType=10; EffectGroup.produceEffectType=2; EffectGroup.produceEffectTypes=2; ProduceDescriptionProduceEffect.type=1 | 体力 -v。 |
| `StaminaReduceMultiple` | 16 | 4 | EffectGroup.produceEffectTypes=2; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `StaminaSpecify` | 17 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `StaminaRecoverValueUp` | 18 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `StaminaRecoverValueDown` | 19 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `StaminaReduceValueUp` | 20 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `StaminaReduceValueDown` | 21 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `StaminaRecoverDisable` | 22 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `MaxStaminaAddition` | 23 | 12 | ProduceEffect.produceEffectType=9; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | 最大体力 +v。 |
| `MaxStaminaReduceFix` | 24 | 8 | ProduceEffect.produceEffectType=6; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 最大体力 -v。 |
| `MaxStaminaReduceMultiple` | 25 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProducePointReduceFix` | 26 | 19 | ProduceEffect.produceEffectType=15; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | P点 -v。 |
| `ProducePointReduceMultiple` | 27 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProducePointSpecify` | 28 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProducePointAdditionValueUp` | 29 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProducePointAdditionValueDown` | 30 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProducePointReduceValueUp` | 31 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProducePointReduceValueDown` | 32 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProduceCardUpgrade` | 33 | 13 | ProduceEffect.produceEffectType=9; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 强化筛选/选择的卡。 |
| `ProduceCardDuplicate` | 34 | 9 | ProduceEffect.produceEffectType=7; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | コピー。 |
| `ProduceCardDuplicateUpgrade` | 35 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProduceCardChange` | 36 | 39 | ProduceEffect.produceEffectType=37; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | チェンジ 为集合内其他卡。 |
| `ProduceCardChangeUpgrade` | 37 | 37 | ProduceEffect.produceEffectType=35; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | チェンジして強化。 |
| `ProduceCardDelete` | 38 | 10 | ProduceEffect.produceEffectType=6; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 删除卡。 |
| `ProducePointAddition` | 39 | 45 | ProduceEffect.produceEffectType=41; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | P点 +v。 |
| `ProducePointGetDisable` | 40 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProduceItemGetDisable` | 41 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProduceDrinkGetDisable` | 42 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProduceReward` | 43 | 212 | ProduceEffect.produceEffectType=207; ProduceEffectIcon.type=4; ProduceDescriptionProduceEffect.type=1 | 给固定奖励 produceRewards。 |
| `ProduceRewardSet` | 44 | 209 | ProduceEffect.produceEffectType=204; ProduceEffectIcon.type=4; ProduceDescriptionProduceEffect.type=1 | 从奖励集合（id 内 p_rd-…）按 pickRange 给 pickCount 个 produceResourceType。 |
| `AuditionParameterBonusMultiple` | 53 | 9 | ProduceEffect.produceEffectType=7; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 试炼スコアボーナス +v‰。 |
| `LessonSpChangeRatePermilAddition` | 54 | 29 | ProduceEffect.produceEffectType=24; SupportCardProduceSkillFilter.produceEffectTypes=3; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | SP 课程发生率 +v‰。 |
| `LessonVocalSpChangeRatePermilAddition` | 55 | 9 | ProduceEffect.produceEffectType=6; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | 。 |
| `LessonDanceSpChangeRatePermilAddition` | 56 | 9 | ProduceEffect.produceEffectType=6; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | 。 |
| `LessonVisualSpChangeRatePermilAddition` | 57 | 9 | ProduceEffect.produceEffectType=6; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | 。 |
| `LessonSpChangeRatePermilDown` | 58 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ExamStatusEnchant` | 60 | 203 | ProduceEffect.produceEffectType=201; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 下次课程/试炼开始时挂持续效果。 |
| `LessonPresentProduceCardRewardCountUp` | 61 | 3 | ProduceDescriptionProduceEffect.type=1; ProduceEffect.produceEffectType=1; ProduceEffectIcon.type=1 | 课程奖励选卡数 +v。 |
| `LessonPresentProduceCardRewardCountDown` | 62 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `LessonPresentSearchProduceCardRewardCountUp` **(dump 中无)** | 63 | 0 | — |  |
| `ShopPriceDiscountMultiple` | 65 | 6 | ProduceEffect.produceEffectType=2; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 相談全项 -v‰。 |
| `ShopProduceCardPriceDiscountMultiple` | 66 | 14 | ProduceEffect.produceEffectType=10; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 相談卡 -v‰（本次）。 |
| `ShopProduceDrinkPriceDiscountMultiple` | 68 | 10 | ProduceEffect.produceEffectType=5; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 。 |
| `ShopProduceCardUpgradePriceDiscountMultiple` | 69 | 9 | ProduceEffect.produceEffectType=5; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 。 |
| `ShopProduceCardUpgradePriceSpecify` | 70 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ShopProduceCardDeletePriceDiscountMultiple` | 71 | 9 | ProduceEffect.produceEffectType=5; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 。 |
| `ShopProduceCardDeletePriceSpecify` | 72 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProduceResultRewardMoneyUp` | 77 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ProduceResultRewardSupportCardEnhancePointUp` | 79 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `SupportCardEventStaminaRecoverUp` | 80 | 5 | ProduceEffect.produceEffectType=3; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 支援事件体力回复 +v‰。 |
| `SupportCardEventProducePointAdditionValueUp` | 81 | 5 | ProduceEffect.produceEffectType=3; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 。 |
| `SupportCardEventParameterAdditionValueUp` | 82 | 5 | ProduceEffect.produceEffectType=3; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 。 |
| `SupportCardEventProbabilityUp` | 83 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `LessonPresentProducePointUp` | 84 | 9 | ProduceEffect.produceEffectType=6; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | 课程奖励 P点 +v‰。 |
| `LessonPresentProducePointDown` **(dump 中无)** | 85 | 0 | — |  |
| `SupportCardProduceCardUpgradeProbabilityUp` | 86 | 143 | ProduceEffect.produceEffectType=141; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 该支援卡 レッスンサポート 发生率 +v‰。 |
| `ProduceCardSelectRerollCountUp` | 87 | 5 | ProduceEffect.produceEffectType=3; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 获得卡再抽次数 +v。 |
| `ProducePointAdditionDisableTrigger` | 88 | 23 | ProduceEffect.produceEffectType=20; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1; SupportCardProduceSkillFilter.produceEffectTypes=1 | 初期 P点 +v（不触发获得事件）。 |
| `LessonLimitUp` **(dump 中无)** | 89 | 0 | — |  |
| `ParameterLimitUp` | 90 | 8 | ProduceEffect.produceEffectType=6; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 参数上限 +v。 |
| `VocalLimitUp` **(dump 中无)** | 91 | 0 | — |  |
| `DanceLimitUp` **(dump 中无)** | 92 | 0 | — |  |
| `VisualLimitUp` **(dump 中无)** | 93 | 0 | — |  |
| `SupportCardEventProduceCardUpgrade` **(dump 中无)** | 94 | 0 | — |  |
| `ExamTurnUp` | 95 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ExamTurnDown` | 96 | 5 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffect.produceEffectType=1 | 回合数 -v。 |
| `AuditionNpcEnhance` | 97 | 12 | ProduceEffect.produceEffectType=8; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 对手分数 +v‰。 |
| `ShopPriceUpMultiple` | 98 | 5 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffect.produceEffectType=1 | +v‰。 |
| `ShopProduceCardPriceUpMultiple` | 99 | 4 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ShopProduceDrinkPriceUpMultiple` | 100 | 4 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ShopProduceCardUpgradePriceUpMultiple` | 101 | 4 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `ShopProduceCardDeletePriceUpMultiple` | 102 | 4 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 |  |
| `EventSchoolStaminaUp` | 103 | 9 | ProduceEffect.produceEffectType=5; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 授業消耗体力 +v‰。 |
| `EventSchoolStaminaDown` | 104 | 5 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffect.produceEffectType=1 | -v‰。 |
| `EventActivityProducePointUp` | 105 | 5 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffect.produceEffectType=1 | お出かけ P点消耗 +v‰。 |
| `EventActivityProducePointDown` | 106 | 5 | EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1; ProduceEffect.produceEffectType=1 | -v‰。 |
| `BeforeAuditionRefreshStaminaUp` | 107 | 10 | ProduceEffect.produceEffectType=6; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | 试炼前回复 +v‰。 |
| `BeforeAuditionRefreshStaminaDown` | 108 | 6 | ProduceEffect.produceEffectType=2; EffectGroup.produceEffectType=1; EffectGroup.produceEffectTypes=1; ProduceDescriptionProduceEffect.type=1 | -v‰。 |
| `ShopRerollCountUp` | 109 | 2 | ProduceEffect.produceEffectType=1; ProduceEffectIcon.type=1 | 相談刷新 +v。 |
| `ProduceCardExcludeCountUp` | 110 | 4 | ProduceEffect.produceEffectType=2; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | スキルカード除去回数 +v。 |
| `CustomizeProduceCardCountUp` **(dump 中无)** | 111 | 0 | — |  |
| `CustomizeProduceCardProducePointUpMultiple` **(dump 中无)** | 112 | 0 | — |  |
| `CustomizeProduceCardProducePointDownMultiple` | 113 | 2 | ProduceEffect.produceEffectType=2 | 下次定制费用 -v‰。 |
| `VoteCountAddition` | 114 | 27 | ProduceEffect.produceEffectType=27 | 票数 +v。 |
| `EventBusinessVoteCountUp` | 115 | 10 | ProduceEffect.produceEffectType=9; ProduceEffectIcon.type=1 | 营业票数 +v‰。 |
| `EventBusinessVoteCountDown` **(dump 中无)** | 116 | 0 | — |  |
| `EventBusinessExcellentPermilUp` **(dump 中无)** | 117 | 0 | — |  |
| `EventBusinessExcellentPermilDown` **(dump 中无)** | 118 | 0 | — |  |
| `AuditionVoteCountUp` | 119 | 10 | ProduceEffect.produceEffectType=9; ProduceEffectIcon.type=1 | 试炼票数 +v‰。 |
| `AuditionVoteCountDown` **(dump 中无)** | 120 | 0 | — |  |
| `SelfLessonStaminaUp` **(dump 中无)** | 121 | 0 | — |  |
| `SelfLessonStaminaDown` **(dump 中无)** | 122 | 0 | — |  |
| `HighScoreGoldAddition` | 123 | 6 | ProduceEffect.produceEffectType=6 | 活动货币 +v。 |
| `IdolCardProduceCardCustomizeEnable` | 124 | 1 | ProduceEffect.produceEffectType=1 | 允许定制固有卡。 |
| `LegendProduceCardCountAddition` **(dump 中无)** | 125 | 0 | — |  |
| `ExamPermanentLessonStatusEnchant` | 126 | 7 | ProduceEffect.produceEffectType=7 | 以后所有课程开始时挂。 |
| `ExamPermanentAuditionStatusEnchant` | 127 | 51 | ProduceEffect.produceEffectType=51 | 以后所有试炼开始时挂持续效果。 |
| `AuditionNpcWeaken` | 128 | 3 | ProduceEffect.produceEffectType=2; ProduceDescriptionProduceEffect.type=1 | 对手分数 -v‰。 |
| `ProduceCustomizeItemUpgrade` | 129 | 1 | ProduceEffect.produceEffectType=1 | 升级定制道具。 |
| `StarPermilUp` | 130 | 11 | ProduceEffect.produceEffectType=9; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | スター性获得 +v‰。 |
| `StarAddition` | 131 | 2 | ProduceDescriptionProduceEffect.type=1; ProduceEffect.produceEffectType=1 | スター性 +v。 |
| `ProduceCardChangeSelect` | 132 | 24 | ProduceEffect.produceEffectType=23; ProduceDescriptionProduceEffect.type=1 | セレクトチェンジ。 |
| `ProduceDrinkPossessLimitUp` | 133 | 3 | ProduceDescriptionProduceEffect.type=1; ProduceEffect.produceEffectType=1; ProduceEffectIcon.type=1 | 饮料上限 +v。 |
| `ShopProduceCardPriceDiscountMultiplePermanent` | 134 | 8 | ProduceEffect.produceEffectType=6; ProduceDescriptionProduceEffect.type=1; ProduceEffectIcon.type=1 | 永久。 |

### ProducePhaseType（proto 定义 44 个值；dump 中出现 29 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 1 | ProduceTrigger.phaseType=1 | p_trigger-none-stamina_ratio-… 纯条件。 |
| `RecoveryStamina` **(dump 中无)** | 1 | 0 | — |  |
| `CustomizeProduceCard` | 3 | 1 | ProduceTrigger.phaseType=1 | 定制卡时。 |
| `GetProducePoint` **(dump 中无)** | 4 | 0 | — |  |
| `GetProduceItem` | 6 | 1 | ProduceTrigger.phaseType=1 | 获得道具时。 |
| `GetProduceDrink` | 7 | 1 | ProduceTrigger.phaseType=1 | 获得饮料时。 |
| `UseProduceDrink` **(dump 中无)** | 8 | 0 | — |  |
| `GetProduceCard` | 9 | 46 | ProduceTrigger.phaseType=46 | 获得卡时（筛选：类别/effectGroup）。 |
| `UpgradeProduceCard` | 10 | 7 | ProduceTrigger.phaseType=7 | 强化卡时。 |
| `DeleteProduceCard` | 11 | 3 | ProduceTrigger.phaseType=3 | 删除卡时。 |
| `ProduceStart` | 12 | 3 | ProduceTrigger.phaseType=3 | 培育开始时（-initial 变体用于“初期…”，-no_description 无文案）。 |
| `StartStep` **(dump 中无)** | 13 | 0 | — |  |
| `StartCustomize` | 14 | 9 | ProduceTrigger.phaseType=9 | 特別指導 开始。 |
| `StartShop` | 15 | 5 | ProduceTrigger.phaseType=5 | 相談 选择时。 |
| `StartRefresh` | 16 | 1 | ProduceTrigger.phaseType=1 | 休む 选择时。 |
| `StartPresent` | 17 | 5 | ProduceTrigger.phaseType=5 | 活動支給・差し入れ 选择时。 |
| `StartLesson` | 18 | 13 | ProduceTrigger.phaseType=13 | 课程开始时（lesson/lesson_sp/lesson_hard/按属性）。 |
| `EndLessonBeforePresent` | 19 | 7 | ProduceTrigger.phaseType=7 | 课程结束、领取奖励前（P点获得量加成）。 |
| `EndLesson` | 20 | 36 | ProduceTrigger.phaseType=36 | 课程结束时（含 CLEAR 后奖励前）。 |
| `FailedLesson` **(dump 中无)** | 21 | 0 | — |  |
| `EndStepEventActivity` | 22 | 6 | ProduceTrigger.phaseType=6 | お出かけ 结束。 |
| `EndStepEventSchool` | 23 | 6 | ProduceTrigger.phaseType=6 | 授業・営業 结束。 |
| `EndStepEventCharacterOpening` **(dump 中无)** | 24 | 0 | — |  |
| `ChangeProduceCard` | 25 | 1 | ProduceTrigger.phaseType=1 | チェンジ 时。 |
| `EndStepEventBusiness` | 26 | 4 | ProduceTrigger.phaseType=4 | 营业结束（按营业种类）。 |
| `EndBeforeAuditionRefresh` | 27 | 5 | ProduceTrigger.phaseType=5 | 试炼前自动回复结束时（= 试炼开始前）。 |
| `StartAuditionMid` **(dump 中无)** | 42 | 0 | — |  |
| `StartAuditionMid1` | 43 | 1 | ProduceTrigger.phaseType=1 | 1 次试炼开始。 |
| `StartAuditionMid2` | 44 | 1 | ProduceTrigger.phaseType=1 | 2 次。 |
| `StartAuditionFinal` | 45 | 1 | ProduceTrigger.phaseType=1 | 最終试炼开始。 |
| `StartAudition` | 46 | 4 | ProduceTrigger.phaseType=4 | 试炼开始时。 |
| `EndAuditionMid` **(dump 中无)** | 47 | 0 | — |  |
| `EndAuditionMid1` **(dump 中无)** | 48 | 0 | — |  |
| `EndAuditionMid2` **(dump 中无)** | 49 | 0 | — |  |
| `EndAuditionFinal` **(dump 中无)** | 50 | 0 | — |  |
| `EndAudition` | 51 | 3 | ProduceTrigger.phaseType=3 | 试炼结束。 |
| `BuyShopItem` **(dump 中无)** | 52 | 0 | — |  |
| `BuyShopItemProduceCard` | 53 | 1 | ProduceTrigger.phaseType=1 | 相談交换卡后。 |
| `BuyShopItemProduceDrink` | 54 | 1 | ProduceTrigger.phaseType=1 | 相談交换饮料后。 |
| `BuyShopItemProduceItem` **(dump 中无)** | 55 | 0 | — |  |
| `BuyShopItemUpgradeProduceCard` **(dump 中无)** | 56 | 0 | — |  |
| `BuyShopItemDeleteProduceCard` **(dump 中无)** | 57 | 0 | — |  |
| `EndPresent` | 58 | 2 | ProduceTrigger.phaseType=2 | 同结束。 |
| `EndShop` | 59 | 1 | ProduceTrigger.phaseType=1 | 相談 结束。 |

### ProduceCardGrowEffectType（proto 定义 54 个值；dump 中出现 54 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 349036 | ProduceCard.produceDescriptions=41289; ProduceCard.produceDescriptions.produceCardGrowEffectType=41289; ProduceExamStatusEnchant.produceDescriptions=27987; ProduceExamStatusEnchant.produceDescriptions.produceCardGrowEffectType=27987 |  |
| `LessonAdd` | 1 | 1904 | ProduceExamEffect.produceDescriptions=149; ProduceExamEffect.produceDescriptions.produceCardGrowEffectType=149; ProduceExamEffect.customizeProduceDescriptions=149; ProduceExamEffect.customizeProduceDescriptions.produceCardGrowEffectType=149 | パラメータ値 +v。 |
| `LessonReduce` | 2 | 105 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=20; ProduceExamEffect.produceDescriptions=2; ProduceExamEffect.produceDescriptions.produceCardGrowEffectType=2 | -v。 |
| `LessonCountAdd` | 3 | 273 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCard.produceDescriptions=26; ProduceCard.produceDescriptions.produceCardGrowEffectType=26; ProduceExamGimmickEffectGroup.produceDescriptions=17 | パラメータ上昇回数 +v。 |
| `LessonCountReduce` | 4 | 81 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=10; ProduceDescriptionProduceCardGrowEffect.type=1 | -v。 |
| `BlockAdd` | 5 | 278 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceExamEffect.produceDescriptions=23; ProduceExamEffect.produceDescriptions.produceCardGrowEffectType=23; ProduceExamEffect.customizeProduceDescriptions=23 | 元気値 +v。 |
| `BlockReduce` | 6 | 91 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=20; ProduceDescriptionProduceCardGrowEffect.type=1 | -v。 |
| `FullPowerPointAdd` | 7 | 118 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=20; ProduceExamStatusEnchant.produceDescriptions=4; ProduceExamStatusEnchant.produceDescriptions.produceCardGrowEffectType=4 | 全力値 +v。 |
| `FullPowerPointReduce` | 8 | 91 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=20; ProduceDescriptionProduceCardGrowEffect.type=1 | -v。 |
| `CostBuffReduce` | 10 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 | 强化状态费用 -v（未使用）。 |
| `CostBuffAdd` | 11 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 | 强化状态费用 +v（未使用）。 |
| `CostReduce` | 12 | 118 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=5; ProduceExamEffect.produceDescriptions=5; ProduceExamEffect.produceDescriptions.produceCardGrowEffectType=5 | -v。 |
| `CostAdd` | 13 | 323 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCard.produceDescriptions=33; ProduceCard.produceDescriptions.produceCardGrowEffectType=33; ProduceExamEffect.produceDescriptions=32 | 体力コスト +v。 |
| `CostPenetrateReduce` | 14 | 96 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=5; ProduceCard.produceDescriptions=4; ProduceCard.produceDescriptions.produceCardGrowEffectType=4 | -v。 |
| `CostPenetrateAdd` | 15 | 112 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=5; ProduceCard.produceDescriptions=4; ProduceCard.produceDescriptions.produceCardGrowEffectType=4 | 体力消費(无视元気)コスト +v。 |
| `ParameterBuffTurnAdd` | 16 | 81 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardCustomize.overwriteProduceCardGrowEffectType=5; ProduceCardGrowEffect.effectType=5; ProduceDescriptionProduceCardGrowEffect.type=1 | 好調回合 +v。 |
| `ParameterBuffTurnReduce` | 17 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `LessonBuffAdd` | 18 | 79 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=5; ProduceCardCustomize.overwriteProduceCardGrowEffectType=3; ProduceDescriptionProduceCardGrowEffect.type=1 | 集中 +v。 |
| `LessonBuffReduce` | 19 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `ReviewAdd` | 20 | 92 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=6; ProduceCardCustomize.overwriteProduceCardGrowEffectType=5; ProduceExamEffect.produceDescriptions=2 | 好印象 +v。 |
| `ReviewReduce` | 21 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `AggressiveAdd` | 22 | 79 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=5; ProduceCardCustomize.overwriteProduceCardGrowEffectType=3; ProduceDescriptionProduceCardGrowEffect.type=1 | やる気 +v。 |
| `AggressiveReduce` | 23 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `CardDrawAdd` | 24 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `CardDrawReduce` | 25 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `ParameterBuffMultiplePerTurnAdd` | 26 | 77 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=5; ProduceCardCustomize.overwriteProduceCardGrowEffectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 絶好調 +v。 |
| `ParameterBuffMultiplePerTurnReduce` | 27 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `StaminaConsumptionDownTurnAdd` | 28 | 81 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardCustomize.overwriteProduceCardGrowEffectType=5; ProduceCardGrowEffect.effectType=5; ProduceDescriptionProduceCardGrowEffect.type=1 | 消費体力減少 回合 +v。 |
| `StaminaConsumptionDownTurnReduce` | 29 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `StaminaConsumptionAddTurnAdd` | 30 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `StaminaConsumptionAddTurnReduce` | 31 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `EffectAdd` | 32 | 126 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=52; ProduceCardCustomize.overwriteProduceCardGrowEffectType=3; ProduceDescriptionProduceCardGrowEffect.type=1 | 追加效果 playProduceExamEffectId。 |
| `EffectDelete` | 33 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 | 删除效果（未使用）。 |
| `EffectChange` | 34 | 95 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=24; ProduceDescriptionProduceCardGrowEffect.type=1 | 把 targetPlayProduceExamEffectIds 替换为 playProduceExamEffectId。 |
| `CardStatusEnchantChange` | 35 | 106 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardCustomize.overwriteProduceCardGrowEffectType=19; ProduceCardGrowEffect.effectType=16; ProduceDescriptionProduceCardGrowEffect.type=1 | 替换成长规则。 |
| `PlayTriggerChange` | 36 | 75 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=4; ProduceDescriptionProduceCardGrowEffect.type=1 | 替换使用条件。 |
| `PlayEffectTriggerChange` | 37 | 75 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=4; ProduceDescriptionProduceCardGrowEffect.type=1 | 替换效果条件。 |
| `PlayMovePositionTypeChange` | 38 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 用后去向改为 playMovePositionType。 |
| `InitialAdd` | 39 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 开始时入手牌。 |
| `CostLessonBuffReduce` | 40 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | -v。 |
| `CostLessonBuffAdd` | 41 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 集中コスト +v。 |
| `CostReviewReduce` | 42 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | -v。 |
| `CostReviewAdd` | 43 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 好印象コスト +v。 |
| `CostAggressiveReduce` | 44 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | -v。 |
| `CostAggressiveAdd` | 45 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | やる気コスト +v。 |
| `CostParameterBuffReduce` | 46 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | -v。 |
| `CostParameterBuffAdd` | 47 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 好調コスト +v。 |
| `CostFullPowerPointReduce` | 48 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | -v。 |
| `CostFullPowerPointAdd` | 49 | 84 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCard.produceDescriptions=4; ProduceCard.produceDescriptions.produceCardGrowEffectType=4; ProduceCardStatusEnchant.produceDescriptions=2 | 全力値コスト +v。 |
| `LessonDependBlockAdd` | 50 | 91 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=19; ProduceCardCustomize.overwriteProduceCardGrowEffectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 元気分パラメータ倍率 +v‰。 |
| `LessonDependExamCardPlayAggressiveAdd` | 51 | 119 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=47; ProduceCardCustomize.overwriteProduceCardGrowEffectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | やる気分 +v‰。 |
| `LessonDependExamReviewAdd` | 52 | 109 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=37; ProduceCardCustomize.overwriteProduceCardGrowEffectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 好印象分 +v‰。 |
| `CostParameterBuffMultiplePerTurnAdd` | 53 | 71 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceDescriptionProduceCardGrowEffect.type=1 |  |
| `CostParameterBuffMultiplePerTurnReduce` | 54 | 72 | ProduceExamAutoGrowEffectEvaluation.growEffectType=70; ProduceCardGrowEffect.effectType=1; ProduceDescriptionProduceCardGrowEffect.type=1 | 絶好調コスト -v。 |

### ProducePlanType（proto 定义 5 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 298 | ProduceCardSearch.planType=277; MemoryGift.planType=21 | 未指定。 |
| `Common` | 1 | 1745 | ProduceSkill.planType=1326; ProduceItem.planType=169; ProduceCard.planType=129; SupportCard.planType=73 | 共通。 |
| `Plan1` | 2 | 1174 | ProduceCard.planType=544; ProduceItem.planType=308; ProduceCustomizeItem.planType=60; IdolCard.planType=56 | センス（好調/集中）。 |
| `Plan2` | 3 | 1251 | ProduceCard.planType=584; ProduceItem.planType=327; IdolCard.planType=60; ProduceCustomizeItem.planType=60 | ロジック（好印象/やる気）。 |
| `Plan3` | 4 | 956 | ProduceCard.planType=457; ProduceItem.planType=234; ProduceCustomizeItem.planType=60; ProduceSkill.planType=54 | アノマリー（指針：全力/強気/温存）。 |

### ProduceStepType（proto 定义 51 个值；dump 中出现 34 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 360071 | ProduceCard.produceDescriptions=41486; ProduceCard.produceDescriptions.produceStepType=41486; ProduceExamStatusEnchant.produceDescriptions=28156; ProduceExamStatusEnchant.produceDescriptions.produceStepType=28156 |  |
| `LessonVocalNormal` | 1 | 314 | ProduceStepTransition.stepType=182; ProduceStepEventSuggestion.stepType=131; TutorialProduceStep.stepType=1 |  |
| `LessonVocalSp` | 2 | 182 | ProduceStepTransition.stepType=182 |  |
| `LessonVocalHard` **(dump 中无)** | 3 | 0 | — |  |
| `LessonDanceNormal` | 4 | 316 | ProduceStepTransition.stepType=182; ProduceStepEventSuggestion.stepType=131; TutorialProduceStep.stepType=3 |  |
| `LessonDanceSp` | 5 | 182 | ProduceStepTransition.stepType=182 |  |
| `LessonDanceHard` **(dump 中无)** | 6 | 0 | — |  |
| `LessonVisualNormal` | 7 | 315 | ProduceStepTransition.stepType=182; ProduceStepEventSuggestion.stepType=131; TutorialProduceStep.stepType=2 |  |
| `LessonVisualSp` | 8 | 182 | ProduceStepTransition.stepType=182 |  |
| `LessonVisualHard` **(dump 中无)** | 9 | 0 | — |  |
| `Event` **(dump 中无)** | 10 | 0 | — |  |
| `EventActivity` | 11 | 192 | ProduceStepTransition.stepType=164; ProduceStepEventSuggestion.successStepType=26; ProduceStepEventSuggestion.stepType=2 |  |
| `EventSchool` | 12 | 105 | ProduceStepTransition.stepType=104; ProduceDescriptionProduceStep.type=1 |  |
| `Shop` **(dump 中无)** | 13 | 0 | — |  |
| `Refresh` | 14 | 49 | ProduceStepTransition.stepType=46; TutorialProduceStep.stepType=3 |  |
| `Present` | 15 | 53 | ProduceStepTransition.stepType=52; ProduceDescriptionProduceStep.type=1 |  |
| `AuditionMid1` | 16 | 1968 | ProduceStepAuditionDifficulty.stepType=1544; ProduceStepAuditionMotion.stepType=325; ProduceStepAuditionCharacter.stepType=39; ProduceStepAuditionCharacterUnitMotion.stepType=28 |  |
| `AuditionMid2` | 17 | 1117 | ProduceStepAuditionDifficulty.stepType=905; ProduceStepAuditionMotion.stepType=151; ProduceStepAuditionCharacter.stepType=39; ProduceStepAuditionCharacterUnitMotion.stepType=12 |  |
| `AuditionFinal` | 18 | 2323 | ProduceStepAuditionDifficulty.stepType=1810; ProduceStepAuditionMotion.stepType=390; ProduceStepAuditionCharacter.stepType=52; ProduceStepAuditionCharacterUnitMotion.stepType=26 |  |
| `SelfLessonVocalNormal` | 19 | 156 | ProduceStepSelfLessonMotion.stepType=78; ProduceStepTransition.stepType=78 |  |
| `SelfLessonVocalSp` | 20 | 130 | ProduceStepTransition.stepType=78; ProduceStepSelfLessonMotion.stepType=52 |  |
| `SelfLessonDanceNormal` | 21 | 156 | ProduceStepSelfLessonMotion.stepType=78; ProduceStepTransition.stepType=78 |  |
| `SelfLessonDanceSp` | 22 | 130 | ProduceStepTransition.stepType=78; ProduceStepSelfLessonMotion.stepType=52 |  |
| `SelfLessonVisualNormal` | 23 | 156 | ProduceStepSelfLessonMotion.stepType=78; ProduceStepTransition.stepType=78 |  |
| `SelfLessonVisualSp` | 24 | 156 | ProduceStepSelfLessonMotion.stepType=78; ProduceStepTransition.stepType=78 |  |
| `Business` | 25 | 104 | ProduceStepTransition.stepType=104 |  |
| `EventBusiness` **(dump 中无)** | 26 | 0 | — |  |
| `FanPresent` | 27 | 46 | ProduceStepTransition.stepType=46 |  |
| `Customize` **(dump 中无)** | 28 | 0 | — |  |
| `LegendLessonVocalNormal` **(dump 中无)** | 29 | 0 | — |  |
| `LegendLessonVocalSp` **(dump 中无)** | 30 | 0 | — |  |
| `LegendLessonDanceNormal` **(dump 中无)** | 31 | 0 | — |  |
| `LegendLessonDanceSp` **(dump 中无)** | 32 | 0 | — |  |
| `LegendLessonVisualNormal` **(dump 中无)** | 33 | 0 | — |  |
| `LegendLessonVisualSp` **(dump 中无)** | 34 | 0 | — |  |
| `OpenLessonVocalNormal` | 35 | 132 | ProduceStepTransition.stepType=112; ProduceStepOpenLessonMotion.stepType=20 |  |
| `OpenLessonVocalSp` | 36 | 136 | ProduceStepTransition.stepType=112; ProduceStepOpenLessonMotion.stepType=24 |  |
| `OpenLessonVocalNormalStar` | 37 | 120 | ProduceStepTransition.stepType=80; ProduceStepOpenLessonMotion.stepType=40 |  |
| `OpenLessonVocalSpStar` | 38 | 120 | ProduceStepTransition.stepType=80; ProduceStepOpenLessonMotion.stepType=40 |  |
| `OpenLessonDanceNormal` | 39 | 132 | ProduceStepTransition.stepType=112; ProduceStepOpenLessonMotion.stepType=20 |  |
| `OpenLessonDanceSp` | 40 | 152 | ProduceStepTransition.stepType=112; ProduceStepOpenLessonMotion.stepType=40 |  |
| `OpenLessonDanceNormalStar` | 41 | 120 | ProduceStepTransition.stepType=80; ProduceStepOpenLessonMotion.stepType=40 |  |
| `OpenLessonDanceSpStar` | 42 | 120 | ProduceStepTransition.stepType=80; ProduceStepOpenLessonMotion.stepType=40 |  |
| `OpenLessonVisualNormal` | 43 | 132 | ProduceStepTransition.stepType=112; ProduceStepOpenLessonMotion.stepType=20 |  |
| `OpenLessonVisualSp` | 44 | 172 | ProduceStepTransition.stepType=112; ProduceStepOpenLessonMotion.stepType=60 |  |
| `OpenLessonVisualNormalStar` | 45 | 120 | ProduceStepTransition.stepType=80; ProduceStepOpenLessonMotion.stepType=40 |  |
| `OpenLessonVisualSpStar` | 46 | 120 | ProduceStepTransition.stepType=80; ProduceStepOpenLessonMotion.stepType=40 |  |
| `Interval` **(dump 中无)** | 47 | 0 | — |  |
| `EventSchoolVocal` **(dump 中无)** | 48 | 0 | — |  |
| `EventSchoolDance` **(dump 中无)** | 49 | 0 | — |  |
| `EventSchoolVisual` **(dump 中无)** | 50 | 0 | — |  |

### ProduceStepBusinessType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 351216 | ProduceCard.produceDescriptions=41486; ProduceCard.produceDescriptions.produceStepBusinessType=41486; ProduceExamStatusEnchant.produceDescriptions=28156; ProduceExamStatusEnchant.produceDescriptions.produceStepBusinessType=28156 |  |
| `ProduceCard` | 1 | 26 | ProduceItem.produceDescriptions=13; ProduceItem.produceDescriptions.produceStepBusinessType=13 | 商業施設（得强化卡）。 |
| `ProduceDrink` | 2 | 26 | ProduceItem.produceDescriptions=13; ProduceItem.produceDescriptions.produceStepBusinessType=13 | 企業イベント会場（得饮料）。 |
| `ProducePoint` | 3 | 26 | ProduceItem.produceDescriptions=13; ProduceItem.produceDescriptions.produceStepBusinessType=13 | 自治体イベント会場（得 P点）。 |
| `Stamina` **(dump 中无)** | 4 | 0 | — | リゾート施設（回体力；仅标签）。 |

### ProduceCardCategory（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 348334 | ProduceCard.produceDescriptions=41369; ProduceCard.produceDescriptions.produceCardCategory=41369; ProduceExamStatusEnchant.produceDescriptions=27762; ProduceExamStatusEnchant.produceDescriptions.produceCardCategory=27762 |  |
| `ActiveSkill` | 1 | 2294 | ProduceCard.category=840; ProduceExamStatusEnchant.produceDescriptions=214; ProduceExamStatusEnchant.produceDescriptions.produceCardCategory=214; ProduceExamGimmickEffectGroup.produceDescriptions=94 | アクティブスキルカード。 |
| `MentalSkill` | 2 | 1871 | ProduceCard.category=873; ProduceExamStatusEnchant.produceDescriptions=136; ProduceExamStatusEnchant.produceDescriptions.produceCardCategory=136; ProduceExamGimmickEffectGroup.produceDescriptions=95 | メンタルスキルカード。 |
| `Trouble` | 3 | 533 | ProduceStepEventSuggestion.produceDescriptions=111; ProduceStepEventSuggestion.produceDescriptions.produceCardCategory=111; ProduceExamStatusEnchant.produceDescriptions=44; ProduceExamStatusEnchant.produceDescriptions.produceCardCategory=44 | トラブルカード。 |

### ProduceCardRarity（proto 定义 6 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `N` | 1 | 165 | ProduceCard.rarity=161; ProduceCardSearch.cardRarities=3; ProduceCardCustomizeRarityEvaluation.rarity=1 | N。 |
| `R` | 2 | 297 | ProduceCard.rarity=288; ProduceCardSearch.cardRarities=8; ProduceCardCustomizeRarityEvaluation.rarity=1 | R。 |
| `Sr` | 3 | 418 | ProduceCard.rarity=408; ProduceCardSearch.cardRarities=9; ProduceCardCustomizeRarityEvaluation.rarity=1 | SR。 |
| `Ssr` | 4 | 844 | ProduceCard.rarity=832; ProduceCardSearch.cardRarities=11; ProduceCardCustomizeRarityEvaluation.rarity=1 | SSR。 |
| `Legend` | 100 | 26 | ProduceCard.rarity=25; ProduceCardSearch.cardRarities=1 | Legend（レジェンド/H.I.F 专属）。 |

### ExamCostType（proto 定义 7 个值；dump 中出现 7 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 2295 | ProduceCard.costType=1562; ProduceCardGrowEffect.costType=453; ProduceCardSearch.costType=280 | 无非体力费用（普通体力费用看 stamina/forceStamina）。 |
| `ExamLessonBuff` | 1 | 25 | ProduceCard.costType=25 | 消费集中。 |
| `ExamReview` | 2 | 16 | ProduceCard.costType=16 | 消费好印象。 |
| `ExamCardPlayAggressive` | 3 | 41 | ProduceCard.costType=41 | 消费やる気。 |
| `ExamParameterBuff` | 4 | 33 | ProduceCard.costType=33 | 消费好調 costValue 回合。 |
| `ExamFullPowerPoint` | 5 | 33 | ProduceCard.costType=33 | 消费全力値。 |
| `ExamParameterBuffMultiplePerTurn` | 6 | 4 | ProduceCard.costType=4 | 消费絶好調。 |

### ProduceCardMovePositionType（proto 定义 8 个值；dump 中出现 8 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 351618 | ProduceCard.produceDescriptions=40084; ProduceCard.produceDescriptions.produceCardMovePositionType=40084; ProduceExamStatusEnchant.produceDescriptions=28156; ProduceExamStatusEnchant.produceDescriptions.produceCardMovePositionType=28156 | 不适用。 |
| `Hand` | 1 | 25 | ProduceExamEffect.movePositionType=24; ProduceDescriptionProduceCardMovePosition.type=1 | 手札。 |
| `DeckFirst` | 2 | 9 | ProduceExamEffect.movePositionType=8; ProduceDescriptionProduceCardMovePosition.type=1 | 山札の一番上。 |
| `DeckLast` | 3 | 6 | ProduceExamEffect.movePositionType=5; ProduceDescriptionProduceCardMovePosition.type=1 | 一番下。 |
| `DeckRandom` | 4 | 12 | ProduceExamEffect.movePositionType=11; ProduceDescriptionProduceCardMovePosition.type=1 | 山札のランダムな位置。 |
| `Grave` | 5 | 319 | ProduceCard.playMovePositionType=312; ProduceExamEffect.movePositionType=5; ProduceCardGrowEffect.playMovePositionType=1; ProduceDescriptionProduceCardMovePosition.type=1 | 捨札。 |
| `Lost` | 6 | 4211 | ProduceCard.playMovePositionType=1402; ProduceCard.produceDescriptions=1402; ProduceCard.produceDescriptions.produceCardMovePositionType=1402; ProduceExamEffect.movePositionType=4 | 除外（レッスン中1回）。 |
| `Hold` | 7 | 14 | ProduceExamEffect.movePositionType=13; ProduceDescriptionProduceCardMovePosition.type=1 | 保留（全力用，上限 holdLimit=2）。 |

### ProduceCardMoveEffectTriggerType（proto 定义 6 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 1706 | ProduceCard.moveEffectTriggerType=1706 | 无移动时效果。 |
| `Lost` **(dump 中无)** | 1 | 0 | — |  |
| `Grave` **(dump 中无)** | 2 | 0 | — |  |
| `Draw` **(dump 中无)** | 3 | 0 | — |  |
| `Hold` | 4 | 1 | ProduceCard.moveEffectTriggerType=1 | 移动到保留时发动。 |
| `Hand` | 5 | 7 | ProduceCard.moveEffectTriggerType=7 | 移动到手札时发动 moveProduceExamEffectIds。 |

### ProduceCardPositionType（proto 定义 15 个值；dump 中出现 10 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `None` **(dump 中无)** | 1 | 0 | — |  |
| `Hand` | 2 | 11 | ProduceCardSearch.cardPositionType=11 | 手札。 |
| `Deck` | 3 | 6 | ProduceCardSearch.cardPositionType=6 | 山札。 |
| `Grave` **(dump 中无)** | 4 | 0 | — |  |
| `Lost` | 5 | 12 | ProduceCardSearch.cardPositionType=12 | 除外。 |
| `DeckAll` | 6 | 44 | ProduceCardSearch.cardPositionType=44 | 所有卡（山札+手札+捨札…，即“持有的卡”）。 |
| `RandomPool` | 7 | 10 | ProduceCardSearch.cardPositionType=10 | 随机池（生成卡）。 |
| `Playing` | 8 | 41 | ProduceCardSearch.cardPositionType=41 | 正在使用的卡。 |
| `PlayHand` **(dump 中无)** | 9 | 0 | — |  |
| `Target` | 11 | 140 | ProduceCardSearch.cardPositionType=140 | 效果的目标卡（用于 trigger 的 lowerSearchCount 判定）。 |
| `Self` **(dump 中无)** | 12 | 0 | — |  |
| `Hold` | 13 | 1 | ProduceCardSearch.cardPositionType=1 | 保留。 |
| `DeckGrave` | 14 | 12 | ProduceCardSearch.cardPositionType=12 | 山札か捨札。 |
| `NotLost` | 15 | 3 | ProduceCardSearch.cardPositionType=3 | 除外以外。 |

### ProduceCardOrderType（proto 定义 4 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 264 | ProduceCardSearch.orderType=264 |  |
| `First` | 1 | 3 | ProduceCardSearch.orderType=3 |  |
| `Last` **(dump 中无)** | 2 | 0 | — |  |
| `Random` | 3 | 13 | ProduceCardSearch.orderType=13 |  |

### ProducePickRangeType（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 5666 | ProduceExamEffect.pickRangeType2=2070; ProduceExamEffect.pickRangeType=1804; ProduceEffect.pickRangeType=1792 |  |
| `Select` | 1 | 288 | ProduceEffect.pickRangeType=271; ProduceExamEffect.pickRangeType=17 |  |
| `Random` | 2 | 50 | ProduceEffect.pickRangeType=25; ProduceExamEffect.pickRangeType=25 |  |
| `All` | 3 | 250 | ProduceExamEffect.pickRangeType=224; ProduceEffect.pickRangeType=26 |  |

### ProducePickCountType（proto 定义 4 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 4134 | ProduceExamEffect.pickCountType2=2070; ProduceExamEffect.pickCountType=2064 |  |
| `Normal` **(dump 中无)** | 1 | 0 | — |  |
| `Shortage` | 2 | 6 | ProduceExamEffect.pickCountType=6 |  |
| `Over` **(dump 中无)** | 3 | 0 | — |  |

### ExamDescriptionType（proto 定义 22 个值；dump 中出现 19 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 293552 | ProduceCard.produceDescriptions=31328; ProduceCard.produceDescriptions.examDescriptionType=31328; ProduceExamStatusEnchant.produceDescriptions=20932; ProduceExamStatusEnchant.produceDescriptions.examDescriptionType=20932 | 非数值槽片段。 |
| `CustomizeEffectValue1` | 1 | 18116 | ProduceCard.produceDescriptions=2403; ProduceCard.produceDescriptions.examDescriptionType=2403; ProduceExamGimmickEffectGroup.produceDescriptions=2213; ProduceExamGimmickEffectGroup.produceDescriptions.examDescriptionType=2213 | 填 effectValue1。 |
| `CustomizeEffectValue2` | 2 | 188 | ProduceExamEffect.produceDescriptions=29; ProduceExamEffect.produceDescriptions.examDescriptionType=29; ProduceExamEffect.customizeProduceDescriptions=29; ProduceExamEffect.customizeProduceDescriptions.examDescriptionType=29 | 填 effectValue2。 |
| `CustomizeEffectCount` | 3 | 4268 | ProduceCard.produceDescriptions=570; ProduceCard.produceDescriptions.examDescriptionType=570; ProduceExamStatusEnchant.produceDescriptions=411; ProduceExamStatusEnchant.produceDescriptions.examDescriptionType=411 | 填 effectCount。 |
| `CustomizeTurn` | 4 | 5216 | ProduceExamGimmickEffectGroup.produceDescriptions=678; ProduceExamGimmickEffectGroup.produceDescriptions.examDescriptionType=678; ProduceExamStatusEnchant.produceDescriptions=496; ProduceExamStatusEnchant.produceDescriptions.examDescriptionType=496 | 填 turn。 |
| `CustomizeInitialAdd` | 5 | 3428 | ProduceCard.produceDescriptions=1714; ProduceCard.produceDescriptions.examDescriptionType=1714 | 引用 Description_ProduceCardIsInitial（开始时入手牌）。 |
| `CustomizePlayMovePositionLost` | 6 | 3428 | ProduceCard.produceDescriptions=1714; ProduceCard.produceDescriptions.examDescriptionType=1714 | 卡面末尾“レッスン中1回”槽。 |
| `CustomizeEffectAdd` | 7 | 3428 | ProduceCard.produceDescriptions=1714; ProduceCard.produceDescriptions.examDescriptionType=1714 | 定制追加效果的插入点。 |
| `CustomizeLessonCountAdd` | 8 | 5060 | ProduceCard.produceDescriptions=776; ProduceCard.produceDescriptions.examDescriptionType=776; ProduceExamEffect.produceDescriptions=621; ProduceExamEffect.produceDescriptions.examDescriptionType=621 | 引用 Description_LessonCountAdd_CountSection（“（N回）”）。 |
| `CustomizeCostValue` | 9 | 728 | ProduceCard.produceDescriptions=364; ProduceCard.produceDescriptions.examDescriptionType=364 | 填 costValue。 |
| `ExamValue` | 10 | 72 | ProduceDescriptionLabel.produceDescriptions=36; ProduceDescriptionLabel.produceDescriptions.examDescriptionType=36 | Label 模板里运行时填的值。 |
| `ExamValue2` | 11 | 4 | ProduceDescriptionLabel.produceDescriptions=2; ProduceDescriptionLabel.produceDescriptions.examDescriptionType=2 | 同 v2。 |
| `ExamTurn` | 12 | 4180 | ProduceExamStatusEnchant.produceDescriptions=2003; ProduceExamStatusEnchant.produceDescriptions.examDescriptionType=2003; ProduceDescriptionLabel.produceDescriptions=45; ProduceDescriptionLabel.produceDescriptions.examDescriptionType=45 | 运行时回合数。 |
| `ExamTurnTimer` | 13 | 2 | ProduceDescriptionLabel.produceDescriptions=1; ProduceDescriptionLabel.produceDescriptions.examDescriptionType=1 | 发动预约回合。 |
| `ExamCount` | 14 | 4022 | ProduceExamStatusEnchant.produceDescriptions=2003; ProduceExamStatusEnchant.produceDescriptions.examDescriptionType=2003; ProduceExamEffect.produceDescriptions=5; ProduceExamEffect.produceDescriptions.examDescriptionType=5 | 运行时次数。 |
| `ExamCardCreateSearchTurnTimerProduceCardName` **(dump 中无)** | 15 | 0 | — |  |
| `ExamProduceExamEffect` | 16 | 12 | ProduceDescriptionLabel.produceDescriptions=6; ProduceDescriptionLabel.produceDescriptions.examDescriptionType=6 | 运行时填子效果描述（exam_template）。 |
| `ExamProduceCardSearch` | 17 | 8 | ProduceDescriptionLabel.produceDescriptions=4; ProduceDescriptionLabel.produceDescriptions.examDescriptionType=4 | 运行时填筛选器描述。 |
| `CustomizeEffectValuePercent1` | 20 | 5188 | ProduceExamStatusEnchant.produceDescriptions=526; ProduceExamStatusEnchant.produceDescriptions.examDescriptionType=526; ProduceExamEffect.produceDescriptions=517; ProduceExamEffect.produceDescriptions.examDescriptionType=517 | effectValue1 以 % 显示（‰/10）。 |
| `CustomizeEffectValuePercent2` | 21 | 394 | ProduceExamEffect.produceDescriptions=68; ProduceExamEffect.produceDescriptions.examDescriptionType=68; ProduceExamEffect.customizeProduceDescriptions=68; ProduceExamEffect.customizeProduceDescriptions.examDescriptionType=68 | 同 v2。 |
| `ExamEndTurnTimer` **(dump 中无)** | 22 | 0 | — |  |
| `ExamTurnMinus` **(dump 中无)** | 23 | 0 | — |  |

### ProduceDescriptionType（proto 定义 24 个值；dump 中出现 12 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `PlainText` | 1 | 178928 | ProduceCard.produceDescriptions=18407; ProduceCard.produceDescriptions.produceDescriptionType=18407; ProduceExamStatusEnchant.produceDescriptions=14188; ProduceExamStatusEnchant.produceDescriptions.produceDescriptionType=14188 | 纯文本（空=换行）。 |
| `ProduceExamEffectType` | 2 | 48454 | ProduceExamGimmickEffectGroup.produceDescriptions=6114; ProduceExamGimmickEffectGroup.produceDescriptions.produceDescriptionType=6114; ProduceCard.produceDescriptions=5285; ProduceCard.produceDescriptions.produceDescriptionType=5285 | 效果名标签（可点击）。 |
| `ProduceCardCategory` | 3 | 2960 | ProduceExamStatusEnchant.produceDescriptions=394; ProduceExamStatusEnchant.produceDescriptions.produceDescriptionType=394; ProduceExamGimmickEffectGroup.produceDescriptions=189; ProduceExamGimmickEffectGroup.produceDescriptions.produceDescriptionType=189 | 卡类别标签。 |
| `DiffText` | 5 | 18696 | ProduceStepEventDetail.produceDescriptions=4533; ProduceStepEventDetail.produceDescriptions.produceDescriptionType=4533; ProduceStepEventSuggestion.produceDescriptions=2954; ProduceStepEventSuggestion.produceDescriptions.produceDescriptionType=2954 | 强化前后差异高亮文本。 |
| `Exam` | 6 | 57742 | ProduceCard.produceDescriptions=10158; ProduceCard.produceDescriptions.produceDescriptionType=10158; ProduceExamStatusEnchant.produceDescriptions=7224; ProduceExamStatusEnchant.produceDescriptions.produceDescriptionType=7224 | 数值槽（见 ExamDescriptionType）。 |
| `ProduceCardGrowEffectType` | 7 | 2530 | ProduceExamEffect.produceDescriptions=232; ProduceExamEffect.produceDescriptions.produceDescriptionType=232; ProduceExamEffect.customizeProduceDescriptions=232; ProduceExamEffect.customizeProduceDescriptions.produceDescriptionType=232 | 成长效果名标签。 |
| `ProduceStepType` **(dump 中无)** | 8 | 0 | — |  |
| `ProduceStepBusinessType` | 9 | 78 | ProduceItem.produceDescriptions=39; ProduceItem.produceDescriptions.produceDescriptionType=39 | 营业种类名。 |
| `ProduceDescription` | 10 | 9892 | ProduceCard.produceDescriptions=2835; ProduceCard.produceDescriptions.produceDescriptionType=2835; ProduceStepEventSuggestion.produceDescriptions=423; ProduceStepEventSuggestion.produceDescriptions.produceDescriptionType=423 | 引用 Label（术语）。 |
| `ProduceDescriptionName` | 11 | 28446 | ProduceCard.produceDescriptions=4412; ProduceCard.produceDescriptions.produceDescriptionType=4412; ProduceItem.produceDescriptions=3781; ProduceItem.produceDescriptions.produceDescriptionType=3781 | 引用 Label/Convert（受场景替换）。 |
| `ProduceCard` | 12 | 3172 | ProduceExamStatusEnchant.produceDescriptions=428; ProduceExamStatusEnchant.produceDescriptions.produceDescriptionType=428; ProduceExamEffect.produceDescriptions=189; ProduceExamEffect.produceDescriptions.produceDescriptionType=189 | 卡名（targetId=卡 id）。 |
| `ProduceCardAnyUpgradeCount` **(dump 中无)** | 13 | 0 | — |  |
| `ProduceItem` | 14 | 394 | ProduceStepEventDetail.produceDescriptions=197; ProduceStepEventDetail.produceDescriptions.produceDescriptionType=197 | 道具名。 |
| `ProduceDrink` | 15 | 2 | ProduceItem.produceDescriptions=1; ProduceItem.produceDescriptions.produceDescriptionType=1 | 饮料名。 |
| `ExamValue` **(dump 中无)** | 30 | 0 | — |  |
| `ExamValue2` **(dump 中无)** | 31 | 0 | — |  |
| `ExamTurn` **(dump 中无)** | 32 | 0 | — |  |
| `ExamTurnTimer` **(dump 中无)** | 33 | 0 | — |  |
| `ExamCount` **(dump 中无)** | 34 | 0 | — |  |
| `ExamCardCreateSearchTurnTimerProduceCardName` **(dump 中无)** | 35 | 0 | — |  |
| `ExamProduceExamEffect` **(dump 中无)** | 36 | 0 | — |  |
| `ExamProduceCardSearch` **(dump 中无)** | 37 | 0 | — |  |
| `IconAsset` **(dump 中无)** | 50 | 0 | — |  |

### ProduceDescriptionSwapType（proto 定义 4 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Lesson` | 1 | 39 | ProduceDescriptionSwap.swapType=39 |  |
| `Audition` | 2 | 39 | ProduceDescriptionSwap.swapType=39 |  |
| `Contest` **(dump 中无)** | 3 | 0 | — |  |

### ProduceExamAutoEvaluationType（proto 定义 54 个值；dump 中出现 53 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Parameter` | 1 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `Block` | 2 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `Stamina` | 3 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamLessonBuff` | 4 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamReview` | 5 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamCardPlayAggressive` | 6 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamParameterBuff` | 7 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamStaminaConsumptionDown` | 8 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamStaminaConsumptionAdd` | 9 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamBlockAddDown` | 10 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamGimmickLessonDebuff` | 11 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamGimmickParameterDebuff` | 12 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamGimmickSleepy` | 13 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamGimmickSlump` | 14 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamStaminaConsumptionDownFix` | 15 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `PlayableValueAdd` | 16 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ParameterBuffMultiplePerTurn` | 17 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ParameterBuffOverTurn` | 18 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamExtraTurn` | 19 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamConcentration` | 20 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamPreservation` | 21 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamFullPower` | 22 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamFullPowerPointTotal` | 23 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamConcentrationCount` | 24 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamPreservationCount` | 25 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamFullPowerCount` | 26 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `HoldCount` | 27 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `DrawCardCount` | 28 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `RemainTurn` | 29 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamAntiDebuff` | 30 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `StanceLock` | 31 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamBlockRestriction` | 32 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamLessonValueMultiple` | 33 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamReviewMultiple` | 34 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamEnthusiasticAdditive` | 35 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamEnthusiasticMultiple` | 36 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamFullPowerLessonMultipleAdditive` | 37 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamConcentrationLessonMultipleAdditive` | 38 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamLessonBuffAdditive` | 39 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamParameterBuffAdditive` | 40 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamAggressiveAdditive` | 41 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamReviewAdditive` | 42 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamFullPowerPointAdditive` | 43 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamGrowEffectLessonAddAdditive` | 44 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamLessonValueMultipleDependReviewOrAggressive` | 45 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `StanceLockConcentration` | 46 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `StanceLockFullPower` | 47 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `StanceLockPreservation` | 48 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamReviewCountAdd` | 49 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamReviewTurnEndReduceLock` | 50 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamParameterBuffTurnEndReduceLock` | 51 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamBuffConsumptionDown` | 52 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |
| `ExamBuffConsumptionAdd` | 53 | 210 | ProduceExamAutoEvaluation.evaluationType=210 |  |

### ProduceExamAutoCardSelectEvaluationType（proto 定义 4 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `LessonCoefficient` | 1 | 70 | ProduceExamAutoCardSelectEvaluation.evaluationType=70 |  |
| `FullPowerPointCoefficient` | 2 | 70 | ProduceExamAutoCardSelectEvaluation.evaluationType=70 |  |
| `FullPowerPointValue2Coefficient` | 3 | 70 | ProduceExamAutoCardSelectEvaluation.evaluationType=70 |  |

### ExamPlayType（proto 定义 6 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `AutoPlay` | 1 | 3662 | ProduceExamAutoEvaluation.type=2226; ProduceExamAutoGrowEffectEvaluation.type=742; ProduceExamAutoPlayProduceCardEvaluation.type=589; ProduceExamAutoTriggerEvaluation.type=63 | 培育内自动打牌。 |
| `ManualPlayLesson` | 2 | 3073 | ProduceExamAutoEvaluation.type=2226; ProduceExamAutoGrowEffectEvaluation.type=742; ProduceExamAutoTriggerEvaluation.type=63; ProduceExamAutoCardSelectEvaluation.type=42 | 手动课程时的提示评估。 |
| `ManualPlayLessonHard` | 3 | 3073 | ProduceExamAutoEvaluation.type=2226; ProduceExamAutoGrowEffectEvaluation.type=742; ProduceExamAutoTriggerEvaluation.type=63; ProduceExamAutoCardSelectEvaluation.type=42 | 追い込み。 |
| `ManualPlayAudition` | 4 | 3073 | ProduceExamAutoEvaluation.type=2226; ProduceExamAutoGrowEffectEvaluation.type=742; ProduceExamAutoTriggerEvaluation.type=63; ProduceExamAutoCardSelectEvaluation.type=42 | 试炼。 |
| `AutoPlayCompetition` | 5 | 3324 | ProduceExamAutoEvaluation.type=2226; ProduceExamAutoGrowEffectEvaluation.type=742; ProduceExamAutoPlayProduceCardEvaluation.type=251; ProduceExamAutoTriggerEvaluation.type=63 | コンテスト自动。 |

### ProduceType（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 1788 | ProduceSkill.produceType=1373; CharacterDearnessLevel.trueEndAchievementProduceType=415 |  |
| `FirstStar` | 1 | 55 | ProduceAdv.produceType=14; CharacterDearnessLevel.trueEndAchievementProduceType=13; CharacterTrueEndAchievement.produceType=13; CharacterTrueEndBonus.produceType=13 | 定期公演『初』。 |
| `NextIdolAudition` | 2 | 69 | ProduceAdv.produceType=18; CharacterDearnessLevel.trueEndAchievementProduceType=13; CharacterTrueEndAchievement.produceType=13; CharacterTrueEndBonus.produceType=13 | N.I.A。 |
| `HatsuboshiIdolFestival` | 3 | 174 | ProduceSkill.produceType=115; ProduceSplitAdv.produceType=24; CharacterDearnessLevel.trueEndAchievementProduceType=10; CharacterTrueEndAchievement.produceType=10 | H.I.F。 |

### ProduceSplitType（proto 定义 3 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 1519 | ProduceSkill.produceSplitType=1478; ProduceGrowthPanel.produceSplitType=32; Produce.produceSplitType=6; ProduceDescriptionProduceType.produceSplitType=3 |  |
| `Selection` | 1 | 20 | ProduceSplitAdv.produceSplitTypes=12; ProduceGrowthPanel.produceSplitType=6; Produce.produceSplitType=1; ProduceDescriptionProduceType.produceSplitType=1 | H.I.F 選抜試験（produce-007）。 |
| `Final` | 2 | 36 | ProduceGrowthPanel.produceSplitType=12; ProduceSplitAdv.produceSplitTypes=12; ProduceSkill.produceSplitType=10; Produce.produceSplitType=1 | H.I.F 本戦（produce-008）。 |

### ExamStatusEffectType（proto 定义 73 个值；dump 中出现 6 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ParameterBuff` | 1 | 1 | CompetitionExamStatusEffectIcon.examStatusEffectType=1 | 好調。 |
| `ParameterDebuff` **(dump 中无)** | 2 | 0 | — |  |
| `Enthusiastic` **(dump 中无)** | 3 | 0 | — |  |
| `LessonBuff` | 4 | 1 | CompetitionExamStatusEffectIcon.examStatusEffectType=1 | 集中。 |
| `LessonDebuff` **(dump 中无)** | 5 | 0 | — |  |
| `LessonParameterMultiple` **(dump 中无)** | 6 | 0 | — |  |
| `LessonParameterBuffMultiple` **(dump 中无)** | 7 | 0 | — |  |
| `StaminaConsumptionAdd` **(dump 中无)** | 8 | 0 | — |  |
| `StaminaConsumptionAddFix` **(dump 中无)** | 9 | 0 | — |  |
| `StaminaConsumptionDown` **(dump 中无)** | 10 | 0 | — |  |
| `StaminaConsumptionDownFix` **(dump 中无)** | 11 | 0 | — |  |
| `BlockAddDown` **(dump 中无)** | 12 | 0 | — |  |
| `BlockAddDownFix` **(dump 中无)** | 13 | 0 | — |  |
| `StaminaConsumptionAddDown` **(dump 中无)** | 14 | 0 | — |  |
| `StaminaConsumptionDownAdd` **(dump 中无)** | 15 | 0 | — |  |
| `StaminaRecoverAdd` **(dump 中无)** | 16 | 0 | — |  |
| `StaminaReduceChange` **(dump 中无)** | 17 | 0 | — |  |
| `BlockRestriction` **(dump 中无)** | 18 | 0 | — |  |
| `BlockAddDownRestriction` **(dump 中无)** | 19 | 0 | — |  |
| `StaminaRecoverRestriction` **(dump 中无)** | 20 | 0 | — |  |
| `PlayCountBuff` **(dump 中无)** | 21 | 0 | — |  |
| `SearchPlayCardCostChange` **(dump 中无)** | 22 | 0 | — |  |
| `SearchPlayCardLimitLesson` **(dump 中无)** | 24 | 0 | — |  |
| `SearchPlayCardLimitPower` **(dump 中无)** | 25 | 0 | — |  |
| `SearchPlayCardLimitSkill` **(dump 中无)** | 26 | 0 | — |  |
| `HandHold` **(dump 中无)** | 27 | 0 | — |  |
| `EffectTimer` **(dump 中无)** | 30 | 0 | — |  |
| `TriggerEffect` **(dump 中无)** | 31 | 0 | — |  |
| `ExamPlayableValueAdd` **(dump 中无)** | 34 | 0 | — |  |
| `Review` | 35 | 1 | CompetitionExamStatusEffectIcon.examStatusEffectType=1 | 好印象。 |
| `ReviewValueMultiple` **(dump 中无)** | 36 | 0 | — |  |
| `Uplifting` **(dump 中无)** | 37 | 0 | — |  |
| `Aggressive` | 38 | 1 | CompetitionExamStatusEffectIcon.examStatusEffectType=1 | やる気。 |
| `StartTurnCardDrawDown` **(dump 中无)** | 40 | 0 | — |  |
| `Slump` **(dump 中无)** | 41 | 0 | — |  |
| `FullPowerPoint` | 42 | 1 | CompetitionExamStatusEffectIcon.examStatusEffectType=1 | 全力値。 |
| `AntiDebuff` **(dump 中无)** | 43 | 0 | — |  |
| `GetCardUpgrade` **(dump 中无)** | 45 | 0 | — |  |
| `LessonChangeSpecifyLessThan` **(dump 中无)** | 47 | 0 | — |  |
| `LessonChangeSpecifyMoreThan` **(dump 中无)** | 48 | 0 | — |  |
| `Panic` **(dump 中无)** | 49 | 0 | — |  |
| `ParameterBuffMultiplePerTurn` | 50 | 1 | CompetitionExamStatusEffectIcon.examStatusEffectType=1 | 絶好調。 |
| `StanceLock` **(dump 中无)** | 51 | 0 | — |  |
| `LessonParameterMultipleDown` **(dump 中无)** | 52 | 0 | — |  |
| `EnthusiasticAdditive` **(dump 中无)** | 53 | 0 | — |  |
| `EnthusiasticMultiple` **(dump 中无)** | 54 | 0 | — |  |
| `FullPowerLessonMultipleAdditive` **(dump 中无)** | 55 | 0 | — |  |
| `ConcentrationLessonMultipleAdditive` **(dump 中无)** | 56 | 0 | — |  |
| `LessonBuffAdditive` **(dump 中无)** | 57 | 0 | — |  |
| `ParameterBuffAdditive` **(dump 中无)** | 58 | 0 | — |  |
| `AggressiveAdditive` **(dump 中无)** | 59 | 0 | — |  |
| `ReviewAdditive` **(dump 中无)** | 60 | 0 | — |  |
| `FullPowerPointAdditive` **(dump 中无)** | 61 | 0 | — |  |
| `GrowEffectLessonAddAdditive` **(dump 中无)** | 62 | 0 | — |  |
| `ReviewMultiple` **(dump 中无)** | 63 | 0 | — |  |
| `LessonParameterMultipleDependReviewOrAggressive` **(dump 中无)** | 64 | 0 | — |  |
| `StanceLockConcentration` **(dump 中无)** | 65 | 0 | — |  |
| `StanceLockFullPower` **(dump 中无)** | 66 | 0 | — |  |
| `StanceLockPreservation` **(dump 中无)** | 67 | 0 | — |  |
| `ReviewCountAdd` **(dump 中无)** | 68 | 0 | — |  |
| `EffectTimerEndTurn` **(dump 中无)** | 69 | 0 | — |  |
| `ReviewTurnEndReduceLock` **(dump 中无)** | 70 | 0 | — |  |
| `ParameterBuffTurnEndReduceLock` **(dump 中无)** | 71 | 0 | — |  |
| `BuffConsumptionDown` **(dump 中无)** | 72 | 0 | — |  |
| `BuffConsumptionAdd` **(dump 中无)** | 73 | 0 | — |  |
| `SearchPlayCardBuffConsumptionChange` **(dump 中无)** | 74 | 0 | — |  |
| `PlayCardLimitPlayableValueAdd` **(dump 中无)** | 75 | 0 | — |  |
| `ParameterBuffAdditiveFix` **(dump 中无)** | 76 | 0 | — |  |
| `LessonBuffAdditiveFix` **(dump 中无)** | 77 | 0 | — |  |
| `AggressiveAdditiveFix` **(dump 中无)** | 78 | 0 | — |  |
| `ReviewAdditiveFix` **(dump 中无)** | 79 | 0 | — |  |
| `FullPowerPointAdditiveFix` **(dump 中无)** | 80 | 0 | — |  |

### ProduceItemEffectType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProduceEffect` | 1 | 418 | ProduceItemEffect.effectType=238; ProduceCustomizeItem.effectType=180 |  |
| `ExamStatusEnchant` | 2 | 693 | ProduceItemEffect.effectType=693 |  |

### ProduceResourceType（proto 定义 18 个值；dump 中出现 6 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 1907 | ProduceEffect.produceResourceType=1815; ProduceEffectIcon.resourceType=92 |  |
| `ProduceCard` | 1 | 375 | ProduceEffect.produceResourceType=233; ProduceEffect.produceRewards=70; ProduceEffect.produceRewards.resourceType=70; ProduceEffectIcon.resourceType=2 |  |
| `ProduceItem` | 2 | 306 | ProduceEffect.produceRewards=136; ProduceEffect.produceRewards.resourceType=136; ProduceEffect.produceResourceType=34 |  |
| `ProduceDrink` | 3 | 35 | ProduceEffect.produceResourceType=31; ProduceEffectIcon.resourceType=2; ProduceEffect.produceRewards=1; ProduceEffect.produceRewards.resourceType=1 |  |
| `ProducePoint` | 4 | 2 | ProduceEffectIcon.resourceType=2 |  |
| `Stamina` **(dump 中无)** | 5 | 0 | — |  |
| `ParameterVocal` **(dump 中无)** | 6 | 0 | — |  |
| `ParameterDance` **(dump 中无)** | 7 | 0 | — |  |
| `ParameterVisual` **(dump 中无)** | 8 | 0 | — |  |
| `Vote` **(dump 中无)** | 9 | 0 | — |  |
| `Star` **(dump 中无)** | 10 | 0 | — |  |
| `ProduceCustomizeItem` | 11 | 1 | ProduceEffect.produceResourceType=1 |  |
| `HighScoreGold` **(dump 中无)** | 100 | 0 | — |  |
| `CardChange` **(dump 中无)** | 994 | 0 | — |  |
| `CardCustomize` **(dump 中无)** | 995 | 0 | — |  |
| `CardUpgrade` **(dump 中无)** | 997 | 0 | — |  |
| `CardDelete` **(dump 中无)** | 998 | 0 | — |  |
| `Set` **(dump 中无)** | 999 | 0 | — |  |

### ProduceEventType（proto 定义 8 个值；dump 中出现 8 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 78 | ProduceStepEventDetail.eventType=78 |  |
| `Activity` | 1 | 529 | ProduceStepEventDetail.eventType=529 |  |
| `School` | 2 | 1188 | ProduceStepEventDetail.eventType=1188 |  |
| `Character` | 3 | 760 | ProduceStepEventDetail.eventType=760 |  |
| `CharacterGrowth` | 4 | 39 | ProduceStepEventDetail.eventType=39 |  |
| `IdolCard` | 5 | 339 | ProduceStepEventDetail.eventType=339 |  |
| `SupportCard` | 6 | 511 | ProduceStepEventDetail.eventType=511 |  |
| `Business` | 7 | 3444 | ProduceStepEventDetail.eventType=3444 |  |

### ProduceEventCharacterType（proto 定义 15 个值；dump 中出现 15 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 6128 | ProduceStepEventDetail.eventCharacterType=6128 |  |
| `Opening` | 1 | 126 | ProduceStepEventDetail.eventCharacterType=126 |  |
| `AfterStep1` | 2 | 42 | ProduceStepEventDetail.eventCharacterType=42 |  |
| `BeforeAuditionMid1` | 3 | 27 | ProduceStepEventDetail.eventCharacterType=27 |  |
| `AfterAuditionMid1` | 4 | 162 | ProduceStepEventDetail.eventCharacterType=162 |  |
| `AfterStep2` | 5 | 42 | ProduceStepEventDetail.eventCharacterType=42 |  |
| `BeforeAuditionMid2` | 6 | 13 | ProduceStepEventDetail.eventCharacterType=13 |  |
| `AfterAuditionMid2` | 7 | 53 | ProduceStepEventDetail.eventCharacterType=53 |  |
| `BeforeAuditionFinal` | 8 | 14 | ProduceStepEventDetail.eventCharacterType=14 |  |
| `AfterAuditionFinal` | 9 | 122 | ProduceStepEventDetail.eventCharacterType=122 |  |
| `Failure` | 10 | 43 | ProduceStepEventDetail.eventCharacterType=43 |  |
| `Ending` | 11 | 112 | ProduceStepEventDetail.eventCharacterType=112 |  |
| `AfterStepBeforeAuditionMid1` | 12 | 2 | ProduceStepEventDetail.eventCharacterType=2 |  |
| `AfterStepBeforeAuditionMid2` | 13 | 1 | ProduceStepEventDetail.eventCharacterType=1 |  |
| `AfterStepBeforeAuditionFinal` | 14 | 1 | ProduceStepEventDetail.eventCharacterType=1 |  |

### ProduceStepAuditionType（proto 定义 11 个值；dump 中出现 11 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 2400 | ProduceStepAuditionDifficulty.auditionType=1599; ProduceStepAuditionMotion.auditionType=801 |  |
| `Mid1Easy` | 1 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `Mid1Normal` | 2 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `Mid1Hard` | 3 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `Mid2Easy` | 4 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `Mid2Normal` | 5 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `Mid2Hard` | 6 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `FinalEasy` | 7 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `FinalNormal` | 8 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `FinalHard` | 9 | 266 | ProduceStepAuditionDifficulty.auditionType=266 |  |
| `FinalVeryHard` | 10 | 331 | ProduceStepAuditionDifficulty.auditionType=266; ProduceStepAuditionMotion.auditionType=65 |  |

### ProduceStepLessonType（proto 定义 17 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 633 | ProduceExamTrigger.lessonType=633 |  |
| `Lesson` **(dump 中无)** | 1 | 0 | — |  |
| `LessonNormal` **(dump 中无)** | 2 | 0 | — |  |
| `LessonSp` | 3 | 1 | ProduceExamTrigger.lessonType=1 |  |
| `LessonHard` **(dump 中无)** | 4 | 0 | — |  |
| `LessonVocal` | 5 | 7 | ProduceExamTrigger.lessonType=7 |  |
| `LessonDance` | 6 | 18 | ProduceExamTrigger.lessonType=18 |  |
| `LessonVisual` | 7 | 17 | ProduceExamTrigger.lessonType=17 |  |
| `LessonVocalNormal` **(dump 中无)** | 8 | 0 | — |  |
| `LessonVocalSp` **(dump 中无)** | 9 | 0 | — |  |
| `LessonVocalHard` **(dump 中无)** | 10 | 0 | — |  |
| `LessonDanceNormal` **(dump 中无)** | 11 | 0 | — |  |
| `LessonDanceSp` **(dump 中无)** | 12 | 0 | — |  |
| `LessonDanceHard` **(dump 中无)** | 13 | 0 | — |  |
| `LessonVisualNormal` **(dump 中无)** | 14 | 0 | — |  |
| `LessonVisualSp` **(dump 中无)** | 15 | 0 | — |  |
| `LessonVisualHard` **(dump 中无)** | 16 | 0 | — |  |

### ProduceStepPhaseType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Before` | 1 | 1910 | ProduceStepTransition.stepPhaseType=1910 |  |
| `After` | 2 | 1318 | ProduceStepTransition.stepPhaseType=1318 |  |

### ResultGrade（proto 定义 20 个值；dump 中出现 19 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `F` | 1 | 19 | MemoryGift.grade=9; ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2 |  |
| `E` | 2 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `D` | 3 | 12 | ResultGradePattern.grade=4; ProduceGrade.grade=3; MemoryGift.grade=2; ProduceSeasonZeroGrade.grade=2 |  |
| `C` | 4 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `CPlus` | 5 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `B` | 6 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `BPlus` | 7 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `A` | 8 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `APlus` | 9 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `S` | 10 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `SPlus` | 11 | 10 | ResultGradePattern.grade=4; ProduceGrade.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `Ss` | 12 | 9 | ProduceGrade.grade=3; ResultGradePattern.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `SsPlus` | 13 | 9 | ProduceGrade.grade=3; ResultGradePattern.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `Sss` | 14 | 19 | MemoryGift.grade=10; ProduceGrade.grade=3; ResultGradePattern.grade=3; ProduceSeasonZeroGrade.grade=2 |  |
| `SssPlus` | 15 | 10 | ProduceGrade.grade=3; ResultGradePattern.grade=3; ProduceSeasonZeroGrade.grade=2; MemoryExchangeItemQuantity.grade=1 |  |
| `Ssss` | 16 | 5 | ProduceGrade.grade=2; MemoryExchangeItemQuantity.grade=1; ProduceGroup.limitGrade=1; ResultGradePattern.grade=1 |  |
| `SsssPlus` | 17 | 3 | MemoryExchangeItemQuantity.grade=1; ProduceGrade.grade=1; ResultGradePattern.grade=1 |  |
| `Sssss` | 18 | 4 | MemoryExchangeItemQuantity.grade=1; ProduceGrade.grade=1; ProduceGroup.limitGrade=1; ResultGradePattern.grade=1 |  |
| `SssssPlus` | 19 | 1 | ResultGradePattern.grade=1 |  |

### ResultGradeType（proto 定义 6 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProduceScore` | 1 | 19 | ResultGradePattern.type=19 |  |
| `MemoryParameter` **(dump 中无)** | 3 | 0 | — |  |
| `ProduceIdolCardParameter` | 5 | 15 | ResultGradePattern.type=15 |  |
| `ProduceVoteCount` | 6 | 15 | ResultGradePattern.type=15 |  |
| `ProduceStar` | 7 | 11 | ResultGradePattern.type=11 |  |

### ProduceLiveType（proto 定义 7 个值；dump 中出现 7 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 1 | ProduceGroup.disableForceLiveCommonEndingLiveType=1 |  |
| `TrueEnd` | 1 | 488 | ProduceLive.type=264; ProduceResultMotion.liveType=108; ProduceLiveEvaluation.liveType=88; ProduceGroupLiveCommon.type=26 |  |
| `A` | 2 | 245 | ProduceResultMotion.liveType=108; ProduceLiveEvaluation.liveType=88; ProduceGroupLiveCommon.type=36; ProduceLive.type=13 |  |
| `B` | 3 | 104 | ProduceLiveEvaluation.liveType=52; ProduceResultMotion.liveType=26; ProduceGroupLiveCommon.type=13; ProduceLive.type=13 |  |
| `C` | 4 | 104 | ProduceLiveEvaluation.liveType=52; ProduceResultMotion.liveType=26; ProduceGroupLiveCommon.type=13; ProduceLive.type=13 |  |
| `D` | 5 | 124 | ProduceLiveEvaluation.liveType=52; ProduceResultMotion.liveType=46; ProduceGroupLiveCommon.type=13; ProduceLive.type=13 |  |
| `E` | 6 | 78 | ProduceLiveEvaluation.liveType=78 |  |

### ProduceItemRarity（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `N` | 1 | 318 | ProduceItem.rarity=318 |  |
| `R` | 2 | 105 | ProduceItem.rarity=105 |  |
| `Sr` | 3 | 171 | ProduceItem.rarity=171 |  |
| `Ssr` | 4 | 444 | ProduceItem.rarity=444 |  |

### ProduceDrinkRarity（proto 定义 5 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `N` **(dump 中无)** | 1 | 0 | — |  |
| `R` | 2 | 8 | ProduceDrink.rarity=8 |  |
| `Sr` | 3 | 9 | ProduceDrink.rarity=9 |  |
| `Ssr` | 4 | 12 | ProduceDrink.rarity=12 |  |

### SkillRarity（proto 定义 5 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 575 | MemoryAbility.rarity=575 |  |
| `R` | 1 | 381 | ProduceSkill.rarity=381 |  |
| `Sr` | 2 | 393 | ProduceSkill.rarity=393 |  |
| `Ssr` | 3 | 707 | ProduceSkill.rarity=707 |  |
| `Ur` | 4 | 7 | ProduceSkill.rarity=7 |  |

### IdolCardRarity（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 349 | Item.idolCardRarity=349 |  |
| `R` | 1 | 27 | IdolCard.rarity=25; IdolCardPieceQuantity.rarity=1; Item.idolCardRarity=1 |  |
| `Sr` | 2 | 15 | IdolCard.rarity=13; IdolCardPieceQuantity.rarity=1; Item.idolCardRarity=1 |  |
| `Ssr` | 3 | 115 | IdolCard.rarity=113; IdolCardPieceQuantity.rarity=1; Item.idolCardRarity=1 |  |

### IdolCardLevelLimitRank（proto 定义 10 个值；dump 中出现 7 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` | 1 | 46 | IdolCardLevelLimit.rank=27; IdolCardLevelLimitProduceSkill.rank=13; IdolCardLevelLimitStatusUp.rank=6 |  |
| `_2` | 2 | 48 | IdolCardLevelLimit.rank=27; IdolCardLevelLimitProduceSkill.rank=15; IdolCardLevelLimitStatusUp.rank=6 |  |
| `_3` | 3 | 33 | IdolCardLevelLimit.rank=27; IdolCardLevelLimitStatusUp.rank=6 |  |
| `_4` | 4 | 33 | IdolCardLevelLimit.rank=27; IdolCardLevelLimitStatusUp.rank=6 |  |
| `_5` | 5 | 33 | IdolCardLevelLimit.rank=27; IdolCardLevelLimitStatusUp.rank=6 |  |
| `_6` | 6 | 184 | IdolCard.maxIdolCardLevelLimitRank=136; IdolCardLevelLimit.rank=27; IdolCardLevelLimitProduceSkill.rank=15; IdolCardLevelLimitStatusUp.rank=6 |  |
| `_7` | 7 | 27 | IdolCard.maxIdolCardLevelLimitRank=15; IdolCardLevelLimit.rank=9; IdolCardLevelLimitStatusUp.rank=2; IdolCardLevelLimitProduceSkill.rank=1 |  |
| `_8` **(dump 中无)** | 8 | 0 | — |  |
| `_9` **(dump 中无)** | 9 | 0 | — |  |

### IdolCardLevelLimitEffectType（proto 定义 7 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProduceCardUpgrade` | 1 | 6 | IdolCardLevelLimitStatusUp.effectTypes=6 |  |
| `ProduceVoDaVi` | 2 | 9 | IdolCardLevelLimitStatusUp.effectTypes=9 |  |
| `ProduceStamina` | 3 | 9 | IdolCardLevelLimitStatusUp.effectTypes=9 |  |
| `ProduceSkill` | 4 | 16 | IdolCardLevelLimitStatusUp.effectTypes=16 |  |
| `SecondProduceCardUpgrade` | 5 | 2 | IdolCardLevelLimitStatusUp.effectTypes=2 |  |
| `ProduceItemUpgrade` **(dump 中无)** | 6 | 0 | — |  |

### IdolCardPotentialRank（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` | 1 | 276 | IdolCardPotential.rank=151; IdolCardPotentialProduceSkill.rank=125 |  |
| `_2` | 2 | 151 | IdolCardPotential.rank=151 |  |
| `_3` | 3 | 151 | IdolCardPotential.rank=151 |  |
| `_4` | 4 | 276 | IdolCardPotential.rank=151; IdolCardPotentialProduceSkill.rank=125 |  |

### IdolCardPotentialEffectType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProduceVoDaViGrowthRatePermil` | 1 | 151 | IdolCardPotential.effectTypes=151 |  |
| `ProduceStamina` | 2 | 151 | IdolCardPotential.effectTypes=151 |  |
| `InitialProduceItemChange` | 3 | 151 | IdolCardPotential.effectTypes=151 |  |
| `ProduceSkill` | 4 | 302 | IdolCardPotential.effectTypes=302 |  |

### SupportCardType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Vocal` | 1 | 67 | SupportCard.type=67 |  |
| `Dance` | 2 | 63 | SupportCard.type=63 |  |
| `Visual` | 3 | 67 | SupportCard.type=67 |  |
| `Assist` | 4 | 4 | SupportCard.type=4 |  |

### SupportCardRarity（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 349 | Item.supportCardRarity=349 |  |
| `R` | 1 | 18 | SupportCard.rarity=13; SupportCardBonus.rarity=4; Item.supportCardRarity=1 |  |
| `Sr` | 2 | 85 | SupportCard.rarity=79; SupportCardBonus.rarity=5; Item.supportCardRarity=1 |  |
| `Ssr` | 3 | 116 | SupportCard.rarity=109; SupportCardBonus.rarity=6; Item.supportCardRarity=1 |  |

### SupportCardLevelLimitRank（proto 定义 5 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 3 | SupportCardLevelLimit.rank=3 |  |
| `_1` | 1 | 3 | SupportCardLevelLimit.rank=3 |  |
| `_2` | 2 | 3 | SupportCardLevelLimit.rank=3 |  |
| `_3` | 3 | 3 | SupportCardLevelLimit.rank=3 |  |
| `_4` | 4 | 3 | SupportCardLevelLimit.rank=3 |  |

### ProduceParameterType（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 4 | SupportCard.produceCardUpgradeLessonParameterType=4 |  |
| `Vocal` | 1 | 83 | SupportCard.produceCardUpgradeLessonParameterType=67; ProduceStepOpenLesson.subParameterType=16 |  |
| `Dance` | 2 | 79 | SupportCard.produceCardUpgradeLessonParameterType=63; ProduceStepOpenLesson.subParameterType=16 |  |
| `Visual` | 3 | 83 | SupportCard.produceCardUpgradeLessonParameterType=67; ProduceStepOpenLesson.subParameterType=16 |  |

### ProduceMemoryProduceCardPhaseType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProduceStart` | 1 | 16 | MemoryGift.produceCardPhaseType=16 |  |
| `EndAuditionMid` | 2 | 5 | MemoryGift.produceCardPhaseType=5 |  |

### ProducerLevelUnlockType（proto 定义 8 个值；dump 中出现 7 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProduceCard` | 1 | 236 | ProducerLevel.unlockTargets=118; ProducerLevel.unlockTargets.type=118 |  |
| `ProduceDrink` | 2 | 36 | ProducerLevel.unlockTargets=18; ProducerLevel.unlockTargets.type=18 |  |
| `ProduceCardConversion` | 3 | 42 | ProducerLevel.unlockTargets=21; ProducerLevel.unlockTargets.type=21 |  |
| `ShopProduceCardUpgrade` | 10 | 2 | ProducerLevel.unlockTargets=1; ProducerLevel.unlockTargets.type=1 |  |
| `ShopProduceCardDelete` | 11 | 2 | ProducerLevel.unlockTargets=1; ProducerLevel.unlockTargets.type=1 |  |
| `ProduceCardSelectRerollCount` | 12 | 2 | ProducerLevel.unlockTargets=1; ProducerLevel.unlockTargets.type=1 |  |
| `ProduceCardExcludeCount` | 13 | 2 | ProducerLevel.unlockTargets=1; ProducerLevel.unlockTargets.type=1 |  |

### ConditionType（proto 定义 77 个值；dump 中出现 44 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `TimeTerm` | 1 | 1380 | ConditionSet.conditionType=1380 |  |
| `TimeDuration` | 2 | 5 | ConditionSet.conditionType=5 |  |
| `TimeWeekday` | 3 | 69 | ConditionSet.conditionType=69 |  |
| `HomeTime` **(dump 中无)** | 4 | 0 | — |  |
| `Birthday` | 5 | 39 | ConditionSet.conditionType=39 |  |
| `Login` | 6 | 3 | ConditionSet.conditionType=3 |  |
| `TutorialClear` | 7 | 1 | ConditionSet.conditionType=1 |  |
| `GameStartTutorialClearHour` | 8 | 5 | ConditionSet.conditionType=5 |  |
| `HomeCharacter` | 9 | 40 | ConditionSet.conditionType=40 |  |
| `ProducerLevel` | 10 | 83 | ConditionSet.conditionType=83 |  |
| `Character` **(dump 中无)** | 11 | 0 | — |  |
| `FanCount` **(dump 中无)** | 12 | 0 | — |  |
| `DearnessLevel` | 13 | 738 | ConditionSet.conditionType=738 |  |
| `Costume` | 14 | 87 | ConditionSet.conditionType=87 |  |
| `IdolCard` | 15 | 88 | ConditionSet.conditionType=88 |  |
| `DearnessStoryFirstReadTime` | 16 | 10 | ConditionSet.conditionType=10 |  |
| `IdolCardPotentialRank` | 17 | 1 | ConditionSet.conditionType=1 |  |
| `IdolCardLevelLimitRank` **(dump 中无)** | 18 | 0 | — |  |
| `SupportCard` | 19 | 2 | ConditionSet.conditionType=2 |  |
| `SupportCardLevel` **(dump 中无)** | 20 | 0 | — |  |
| `SupportCardLevelLimitRank` **(dump 中无)** | 21 | 0 | — |  |
| `MemoryCount` **(dump 中无)** | 22 | 0 | — |  |
| `ProduceCard` **(dump 中无)** | 23 | 0 | — |  |
| `Music` | 24 | 274 | ConditionSet.conditionType=274 |  |
| `CharacterProducePlayCount` | 26 | 38 | ConditionSet.conditionType=38 |  |
| `CharacterProduceClearCount` | 27 | 2 | ConditionSet.conditionType=2 |  |
| `ProduceClearCount` | 28 | 2 | ConditionSet.conditionType=2 |  |
| `ProducePlanClearCount` **(dump 中无)** | 29 | 0 | — |  |
| `PvpRateOpen` **(dump 中无)** | 30 | 0 | — |  |
| `PvpRateSeasonPlayCount` **(dump 中无)** | 31 | 0 | — |  |
| `PvpRateSeasonWinCount` **(dump 中无)** | 32 | 0 | — |  |
| `PvpRateSeasonRate` **(dump 中无)** | 33 | 0 | — |  |
| `PvpRateUnitOverallPower` **(dump 中无)** | 34 | 0 | — |  |
| `WorkCount` **(dump 中无)** | 35 | 0 | — |  |
| `WorkCharacterCount` **(dump 中无)** | 36 | 0 | — |  |
| `StoryRead` | 37 | 57 | ConditionSet.conditionType=57 |  |
| `FollowCount` **(dump 中无)** | 38 | 0 | — |  |
| `CostumeHead` | 39 | 73 | ConditionSet.conditionType=73 |  |
| `GuildJoin` **(dump 中无)** | 40 | 0 | — |  |
| `MeishiUpdateCount` **(dump 中无)** | 41 | 0 | — |  |
| `GashaOpen` | 42 | 9 | ConditionSet.conditionType=9 |  |
| `GashaDraw` | 43 | 21 | ConditionSet.conditionType=21 |  |
| `ExchangeItemCount` | 44 | 560 | ConditionSet.conditionType=560 |  |
| `ShopItemPurchase` | 45 | 132 | ConditionSet.conditionType=132 |  |
| `MissionPassProgress` **(dump 中无)** | 46 | 0 | — |  |
| `MainTaskCompleted` | 47 | 441 | ConditionSet.conditionType=441 |  |
| `MissionCompleted` | 48 | 220 | ConditionSet.conditionType=220 |  |
| `AchievementCompleted` | 49 | 50 | ConditionSet.conditionType=50 |  |
| `ItemObtained` **(dump 中无)** | 50 | 0 | — |  |
| `ItemCount` | 51 | 61 | ConditionSet.conditionType=61 |  |
| `SeminarExamClear` | 53 | 6 | ConditionSet.conditionType=6 |  |
| `PvpRateSeasonGrade` | 54 | 1 | ConditionSet.conditionType=1 |  |
| `PvpRateBestGrade` | 55 | 29 | ConditionSet.conditionType=29 |  |
| `ProduceStoryRead` | 56 | 66 | ConditionSet.conditionType=66 |  |
| `TowerLayerClear` **(dump 中无)** | 57 | 0 | — |  |
| `StoryUnlockKeyUse` | 58 | 16 | ConditionSet.conditionType=16 |  |
| `MissionDailyReleaseNotComplete` | 59 | 6 | ConditionSet.conditionType=6 |  |
| `MissionPanelNotComplete` | 60 | 12 | ConditionSet.conditionType=12 |  |
| `AchievementFirstThresholdClearHour` **(dump 中无)** | 61 | 0 | — |  |
| `MainTaskFirstThresholdClearHour` | 62 | 1 | ConditionSet.conditionType=1 |  |
| `MissionFirstThresholdClearHour` | 63 | 26 | ConditionSet.conditionType=26 |  |
| `PhotoBackground` | 64 | 1 | ConditionSet.conditionType=1 |  |
| `PhotoPose` **(dump 中无)** | 65 | 0 | — |  |
| `Comeback` | 66 | 3 | ConditionSet.conditionType=3 |  |
| `MissionGroupComplete` | 67 | 2 | ConditionSet.conditionType=2 |  |
| `MissionGroupNotComplete` | 68 | 1 | ConditionSet.conditionType=1 |  |
| `AppVersionGreaterThanOrEqual` **(dump 中无)** | 69 | 0 | — |  |
| `AppVersionLessThanOrEqual` **(dump 中无)** | 70 | 0 | — |  |
| `ProduceCardConversion` **(dump 中无)** | 71 | 0 | — |  |
| `CompetitionSeasonGrade` **(dump 中无)** | 72 | 0 | — |  |
| `CompetitionBestGrade` **(dump 中无)** | 73 | 0 | — |  |
| `ProduceGrowthPanelLevel` **(dump 中无)** | 74 | 0 | — |  |
| `ProduceGrowthPanelLevelCount` **(dump 中无)** | 75 | 0 | — |  |
| `IdolCardPrimaStellaCount` **(dump 中无)** | 76 | 0 | — |  |
| `Set` | 998 | 156 | ConditionSet.conditionType=156 |  |
| `NegativeSet` | 999 | 267 | ConditionSet.conditionType=267 |  |

### ConditionOperatorType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `And` | 1 | 4187 | ConditionSet.conditionOperatorType=4187 |  |
| `Or` | 2 | 897 | ConditionSet.conditionOperatorType=897 |  |

### ConditionMinMaxType（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 3677 | ConditionSet.minMaxType=3400; ProduceCardSearch.staminaMinMaxType=277 |  |
| `MinMax` | 1 | 351 | ConditionSet.minMaxType=348; ProduceCardSearch.staminaMinMaxType=3 |  |
| `Min` | 2 | 1298 | ConditionSet.minMaxType=1298 |  |
| `Max` | 3 | 38 | ConditionSet.minMaxType=38 |  |

### ResourceType（proto 定义 30 个值；dump 中出现 18 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 586 | ShopItem.consumptionResourceType=280; Story.reward.resourceType=265; MissionPassProgress.premiumReward.resourceType=29; GashaButton.resourceType=7 |  |
| `ProduceCard` **(dump 中无)** | 1 | 0 | — |  |
| `Item` | 2 | 9986 | MissionProgress.rewards=2273; MissionProgress.rewards.resourceType=2273; AchievementProgress.rewards=1106; AchievementProgress.rewards.resourceType=1106 |  |
| `Memory` **(dump 中无)** | 3 | 0 | — |  |
| `SupportCard` | 4 | 5 | ShopItem.rewards=2; ShopItem.rewards.resourceType=2; ExchangeItemCategory.resourceType=1 |  |
| `IdolCardSkin` | 5 | 18 | ShopItem.rewards=9; ShopItem.rewards.resourceType=9 |  |
| `MissionPassPoint` | 6 | 12 | MissionPointRewardSet.rewards=6; MissionPointRewardSet.rewards.resourceType=6 |  |
| `MissionPassPremiumPass` | 7 | 58 | ShopItem.rewards=29; ShopItem.rewards.resourceType=29 |  |
| `ActionPoint` **(dump 中无)** | 8 | 0 | — |  |
| `UserExp` | 9 | 4506 | AchievementProgress.rewards=1842; AchievementProgress.rewards.resourceType=1842; MainTask.rewards=310; MainTask.rewards.resourceType=310 |  |
| `FanCount` **(dump 中无)** | 10 | 0 | — |  |
| `FriendFollowLimitCount` | 11 | 8 | MissionProgress.rewards=4; MissionProgress.rewards.resourceType=4 |  |
| `Music` | 12 | 2 | Story.reward.resourceType=2 |  |
| `CostumeHead` | 13 | 268 | MissionPassProgress.premiumReward.resourceType=100; ShopItem.rewards=82; ShopItem.rewards.resourceType=82; CharacterDearnessLevel.rewards=2 |  |
| `Costume` | 14 | 232 | ShopItem.rewards=102; ShopItem.rewards.resourceType=102; AchievementProgress.rewards=13; AchievementProgress.rewards.resourceType=13 |  |
| `MeishiBaseAsset` | 15 | 52 | AchievementProgress.rewards=13; AchievementProgress.rewards.resourceType=13; ShopItem.rewards=8; ShopItem.rewards.resourceType=8 |  |
| `MeishiIllustrationAsset` | 16 | 101 | MissionGroup.rewards=45; MissionGroup.rewards.resourceType=45; ShopItem.rewards=4; ShopItem.rewards.resourceType=4 |  |
| `InvitationPoint` **(dump 中无)** | 17 | 0 | — |  |
| `Story` | 18 | 104 | MissionPointRewardSet.rewards=52; MissionPointRewardSet.rewards.resourceType=52 |  |
| `StoryEventPoint` | 19 | 742 | MissionProgress.rewards=371; MissionProgress.rewards.resourceType=371 |  |
| `PvpRatePlayCount` **(dump 中无)** | 20 | 0 | — |  |
| `PhotoBackground` **(dump 中无)** | 21 | 0 | — |  |
| `PhotoPose` **(dump 中无)** | 22 | 0 | — |  |
| `DearnessPoint` | 23 | 720 | MissionProgress.rewards=360; MissionProgress.rewards.resourceType=360 |  |
| `Badge` **(dump 中无)** | 24 | 0 | — |  |
| `CompetitionPlayCount` **(dump 中无)** | 25 | 0 | — |  |
| `ProduceCardConversion` **(dump 中无)** | 26 | 0 | — |  |
| `JewelTotal` | 1100 | 5766 | AchievementProgress.rewards=2076; AchievementProgress.rewards.resourceType=2076; MissionProgress.rewards=547; MissionProgress.rewards.resourceType=547 |  |
| `JewelPaidOnly` | 1101 | 35 | GashaButton.resourceType=31; ConsumptionSet.resourceType=4 |  |
| `Set` **(dump 中无)** | 9999 | 0 | — |  |

### AchievementCategory（proto 定义 4 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Idol` | 1 | 1148 | Achievement.category=1148 |  |
| `Produce` | 2 | 33 | Achievement.category=33 |  |
| `Other` | 99 | 25 | Achievement.category=25 |  |

### AntiCheatFeatureType（proto 定义 8 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ExamProduceLesson` **(dump 中无)** | 1 | 0 | — |  |
| `ExamProduceAudition` **(dump 中无)** | 2 | 0 | — |  |
| `ExamPvpRate` **(dump 中无)** | 3 | 0 | — |  |
| `ExamTower` **(dump 中无)** | 4 | 0 | — |  |
| `ExamGvgRaid` **(dump 中无)** | 5 | 0 | — |  |
| `ExamTour` **(dump 中无)** | 6 | 0 | — |  |
| `AndroidPlayIntegrity` **(dump 中无)** | 101 | 0 | — |  |

### AppReviewType（proto 定义 5 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Gasha` | 1 | 1 | AppReview.type=1 |  |
| `MainTask` | 2 | 1 | AppReview.type=1 |  |
| `Achievement` **(dump 中无)** | 3 | 0 | — |  |
| `ProduceClear` **(dump 中无)** | 4 | 0 | — |  |

### AssetCopyRuleGroup（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Common` **(dump 中无)** | 1 | 0 | — |  |
| `Motion` **(dump 中无)** | 2 | 0 | — |  |
| `Voice` **(dump 中无)** | 3 | 0 | — |  |
| `Camera` **(dump 中无)** | 4 | 0 | — |  |

### AssetCopyRuleType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Require` **(dump 中无)** | 1 | 0 | — |  |
| `Ignore` **(dump 中无)** | 2 | 0 | — |  |
| `RequireServer` **(dump 中无)** | 3 | 0 | — |  |
| `RequireClient` **(dump 中无)** | 4 | 0 | — |  |

### AssetDownloadType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `First` | 1 | 687 | AssetDownload.type=687 |  |
| `Second` | 2 | 3280 | AssetDownload.type=3280 |  |

### AssetKind（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `AssetBundle` **(dump 中无)** | 1 | 0 | — |  |
| `Resource` **(dump 中无)** | 2 | 0 | — |  |

### AuthProviderType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `BandaiNamcoId` **(dump 中无)** | 1 | 0 | — |  |
| `DmmgamesId` **(dump 中无)** | 2 | 0 | — |  |

### BadgeGrade（proto 定义 11 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` | 1 | 39 | Badge.grade=39 |  |
| `_2` | 2 | 78 | Badge.grade=78 |  |
| `_3` | 3 | 78 | Badge.grade=78 |  |
| `_4` | 4 | 39 | Badge.grade=39 |  |
| `_5` | 5 | 39 | Badge.grade=39 |  |
| `_6` **(dump 中无)** | 6 | 0 | — |  |
| `_7` **(dump 中无)** | 7 | 0 | — |  |
| `_8` **(dump 中无)** | 8 | 0 | — |  |
| `_9` **(dump 中无)** | 9 | 0 | — |  |
| `_10` **(dump 中无)** | 10 | 0 | — |  |

### BadgeType（proto 定义 2 个值；dump 中出现 1 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProducerRanking` | 1 | 273 | Badge.type=273 |  |

### CharacterDetailType（proto 定义 15 个值；dump 中出现 14 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Grade` | 1 | 13 | CharacterDetail.type=13 |  |
| `Height` | 2 | 13 | CharacterDetail.type=13 |  |
| `Weight` | 3 | 13 | CharacterDetail.type=13 |  |
| `BloodType` | 4 | 13 | CharacterDetail.type=13 |  |
| `ThreeSize` | 5 | 13 | CharacterDetail.type=13 |  |
| `ZodiacSign` | 6 | 13 | CharacterDetail.type=13 |  |
| `Cv` | 7 | 13 | CharacterDetail.type=13 |  |
| `Age` | 8 | 13 | CharacterDetail.type=13 |  |
| `Birthday` | 9 | 13 | CharacterDetail.type=13 |  |
| `DominantHand` | 10 | 13 | CharacterDetail.type=13 |  |
| `Birthplace` | 11 | 13 | CharacterDetail.type=13 |  |
| `SpecialSkill` | 12 | 13 | CharacterDetail.type=13 |  |
| `Hobby` | 13 | 13 | CharacterDetail.type=13 |  |
| `Introduction` | 14 | 12 | CharacterDetail.type=12 |  |

### CharacterPersonalityType（proto 定义 5 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 10 | Character.personalityType=10 |  |
| `A` | 1 | 2 | Character.personalityType=2 |  |
| `B` | 2 | 3 | Character.personalityType=3 |  |
| `C` | 3 | 5 | Character.personalityType=5 |  |
| `D` | 4 | 4 | Character.personalityType=4 |  |

### CoinGashaBoxResetTypeType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `EmptyAll` **(dump 中无)** | 1 | 0 | — |  |
| `EmptyFeature` **(dump 中无)** | 2 | 0 | — |  |
| `Optional` **(dump 中无)** | 3 | 0 | — |  |

### CoinGashaType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Default` **(dump 中无)** | 1 | 0 | — |  |
| `Feature` **(dump 中无)** | 2 | 0 | — |  |
| `Box` **(dump 中无)** | 3 | 0 | — |  |

### CompetitionGrade（proto 定义 9 个值；dump 中出现 8 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` | 1 | 3 | CompetitionStageSectionLock.grade=3 |  |
| `_2` | 2 | 3 | CompetitionStageSectionLock.grade=3 |  |
| `_3` | 3 | 3 | CompetitionStageSectionLock.grade=3 |  |
| `_4` | 4 | 3 | CompetitionStageSectionLock.grade=3 |  |
| `_5` | 5 | 3 | CompetitionStageSectionLock.grade=3 |  |
| `_6` | 6 | 3 | CompetitionStageSectionLock.grade=3 |  |
| `_7` | 7 | 3 | CompetitionStageSectionLock.grade=3 |  |
| `_8` | 8 | 3 | CompetitionStageSectionLock.grade=3 |  |

### CompetitionPhaseType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `MatchedRivals` **(dump 中无)** | 1 | 0 | — |  |
| `Start` **(dump 中无)** | 2 | 0 | — |  |
| `Playing` **(dump 中无)** | 3 | 0 | — |  |
| `Result` **(dump 中无)** | 4 | 0 | — |  |

### CompetitionSeasonStatusType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `OutOfTerm` **(dump 中无)** | 1 | 0 | — |  |
| `PrepareStartTerm` **(dump 中无)** | 2 | 0 | — |  |
| `InPlayable` **(dump 中无)** | 3 | 0 | — |  |
| `NotAttended` **(dump 中无)** | 4 | 0 | — |  |

### CompetitionStageSectionType（proto 定义 4 个值；dump 中出现 1 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Op` **(dump 中无)** | 1 | 0 | — |  |
| `Mid` | 2 | 12 | CompetitionStageSectionLock.sectionTypes=12 |  |
| `Ed` **(dump 中无)** | 3 | 0 | — |  |

### CompetitionStageType（proto 定义 4 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` | 1 | 8 | CompetitionStageSectionLock.stageType=8 |  |
| `_2` | 2 | 8 | CompetitionStageSectionLock.stageType=8 |  |
| `_3` | 3 | 8 | CompetitionStageSectionLock.stageType=8 |  |

### ConsentAgreementType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Unanswered` **(dump 中无)** | 1 | 0 | — |  |
| `Disagreement` **(dump 中无)** | 2 | 0 | — |  |
| `Agreement` **(dump 中无)** | 3 | 0 | — |  |

### ConsentType（proto 定义 6 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Overview` **(dump 中无)** | 1 | 0 | — |  |
| `Analysis` **(dump 中无)** | 2 | 0 | — |  |
| `Advertisement` **(dump 中无)** | 3 | 0 | — |  |
| `CustomizedAdvertisement` **(dump 中无)** | 4 | 0 | — |  |
| `Sns` **(dump 中无)** | 5 | 0 | — |  |

### CostumeFeatureType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Home` | 1 | 2 | Costume.invalidCostumeFeatureTypes=2 |  |
| `Produce` | 2 | 17 | Costume.invalidCostumeFeatureTypes=17 |  |
| `Live` | 3 | 17 | Costume.invalidCostumeFeatureTypes=17 |  |
| `Photography` | 4 | 2 | Costume.invalidCostumeFeatureTypes=2 |  |

### CostumeMotionType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Wait` | 1 | 14 | CostumeMotion.motionType=14 |  |
| `Start` | 2 | 14 | CostumeMotion.motionType=14 |  |
| `Finish` | 3 | 14 | CostumeMotion.motionType=14 |  |
| `TapReaction` | 4 | 56 | CostumeMotion.motionType=56 |  |

### CostumeSetType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Home` **(dump 中无)** | 1 | 0 | — |  |
| `ProduceSchedule` **(dump 中无)** | 2 | 0 | — |  |
| `ProduceLive` **(dump 中无)** | 3 | 0 | — |  |
| `ProduceTraining` **(dump 中无)** | 4 | 0 | — |  |

### CountType（proto 定义 20 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Login` **(dump 中无)** | 1 | 0 | — |  |
| `ProduceRentalMemory` **(dump 中无)** | 2 | 0 | — |  |
| `ProduceContinue` **(dump 中无)** | 3 | 0 | — |  |
| `Achievement` **(dump 中无)** | 4 | 0 | — |  |
| `ReceivedTotalLoginBonus` **(dump 中无)** | 5 | 0 | — |  |
| `ConfirmedTotalLoginBonus` **(dump 中无)** | 6 | 0 | — |  |
| `MeishiUpdate` **(dump 中无)** | 7 | 0 | — |  |
| `MeishiFollow` **(dump 中无)** | 8 | 0 | — |  |
| `GuildDonation` **(dump 中无)** | 9 | 0 | — |  |
| `MainTask` **(dump 中无)** | 10 | 0 | — |  |
| `AchievementIdol` **(dump 中无)** | 11 | 0 | — |  |
| `AchievementProduce` **(dump 中无)** | 12 | 0 | — |  |
| `AchievementOther` **(dump 中无)** | 13 | 0 | — |  |
| `MainTaskMainStory` **(dump 中无)** | 14 | 0 | — |  |
| `MainTaskProducer` **(dump 中无)** | 15 | 0 | — |  |
| `ProduceClearTimeBanWarning` **(dump 中无)** | 16 | 0 | — |  |
| `MainTaskProducer2` **(dump 中无)** | 100 | 0 | — |  |
| `MainTaskProducer3` **(dump 中无)** | 101 | 0 | — |  |
| `MainTaskProducer4` **(dump 中无)** | 102 | 0 | — |  |

### DearnessMotionType（proto 定义 10 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Wait1` | 1 | 114 | DearnessMotion.motionType=114 |  |
| `Wait2` **(dump 中无)** | 2 | 0 | — |  |
| `Reaction` | 3 | 1862 | DearnessMotion.motionType=1862 |  |
| `ReactionOnce` **(dump 中无)** | 4 | 0 | — |  |
| `WaitLookAround` **(dump 中无)** | 5 | 0 | — |  |
| `MultipleTaps` | 6 | 228 | DearnessMotion.motionType=228 |  |
| `Transition` | 7 | 1634 | DearnessMotion.motionType=1634 |  |
| `WaitOnce` | 8 | 134 | DearnessMotion.motionType=134 |  |
| `WaitLoop` **(dump 中无)** | 9 | 0 | — |  |

### DeckRecommendType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Manual` **(dump 中无)** | 1 | 0 | — |  |
| `Recommend` **(dump 中无)** | 2 | 0 | — |  |
| `RecommendAndManual` **(dump 中无)** | 3 | 0 | — |  |
| `Reset` **(dump 中无)** | 4 | 0 | — |  |

### ErrorCode（proto 定义 68 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `InvalidArgument` **(dump 中无)** | 1001 | 0 | — |  |
| `Internal` **(dump 中无)** | 1002 | 0 | — |  |
| `Unauthenticated` **(dump 中无)** | 1003 | 0 | — |  |
| `PermissionDenied` **(dump 中无)** | 1004 | 0 | — |  |
| `NotFound` **(dump 中无)** | 1005 | 0 | — |  |
| `OutdatedMasterData` **(dump 中无)** | 2001 | 0 | — |  |
| `LockFailed` **(dump 中无)** | 2002 | 0 | — |  |
| `PurchaseRecoverFailed` **(dump 中无)** | 2003 | 0 | — |  |
| `OutdatedApp` **(dump 中无)** | 2004 | 0 | — |  |
| `ExchangeNeedRefresh` **(dump 中无)** | 2005 | 0 | — |  |
| `DateChanged` **(dump 中无)** | 2006 | 0 | — |  |
| `FriendFollowCountLimitExceeded` **(dump 中无)** | 2007 | 0 | — |  |
| `FriendFollowersCountLimitExceeded` **(dump 中无)** | 2008 | 0 | — |  |
| `MeishiFollowCountLimitExceeded` **(dump 中无)** | 2009 | 0 | — |  |
| `MeishiDuplicatedFollow` **(dump 中无)** | 2010 | 0 | — |  |
| `UserNotFound` **(dump 中无)** | 2011 | 0 | — |  |
| `GuildNotFound` **(dump 中无)** | 2012 | 0 | — |  |
| `GuildAlreadyJoined` **(dump 中无)** | 2013 | 0 | — |  |
| `GuildDismiss` **(dump 中无)** | 2014 | 0 | — |  |
| `MeishiNotFound` **(dump 中无)** | 2015 | 0 | — |  |
| `InvalidPlayIntegrity` **(dump 中无)** | 2016 | 0 | — |  |
| `InMaintenance` **(dump 中无)** | 2017 | 0 | — |  |
| `AccountBan` **(dump 中无)** | 2018 | 0 | — |  |
| `TemporaryAccountBan` **(dump 中无)** | 2019 | 0 | — |  |
| `PurchaseBan` **(dump 中无)** | 2020 | 0 | — |  |
| `TemporaryPurchaseBan` **(dump 中无)** | 2021 | 0 | — |  |
| `RecoveryPurchaseTransactionNotFound` **(dump 中无)** | 2022 | 0 | — |  |
| `DataUpdated` **(dump 中无)** | 2023 | 0 | — |  |
| `InFeatureMaintenance` **(dump 中无)** | 2024 | 0 | — |  |
| `NgWordContains` **(dump 中无)** | 2025 | 0 | — |  |
| `MigrationBan` **(dump 中无)** | 2026 | 0 | — |  |
| `TemporaryMigrationBan` **(dump 中无)** | 2027 | 0 | — |  |
| `InvitationInvalidCode` **(dump 中无)** | 2028 | 0 | — |  |
| `AuthLinkAccountNotFound` **(dump 中无)** | 2029 | 0 | — |  |
| `ShopInvalidBirthday` **(dump 中无)** | 2030 | 0 | — |  |
| `RequestConflict` **(dump 中无)** | 2031 | 0 | — |  |
| `GameAuthTokenInvalid` **(dump 中无)** | 2032 | 0 | — |  |
| `OutOfTerm` **(dump 中无)** | 2033 | 0 | — |  |
| `ConditionInvalid` **(dump 中无)** | 2034 | 0 | — |  |
| `ShopExceedPurchaseThresholdOnRecover` **(dump 中无)** | 2035 | 0 | — |  |
| `ShopExceedMaxJewelQuantityOnRecover` **(dump 中无)** | 2036 | 0 | — |  |
| `ShopExceedPurchaseLimit` **(dump 中无)** | 2037 | 0 | — |  |
| `UserDataUpdated` **(dump 中无)** | 2038 | 0 | — |  |
| `DmmGamesIdDuplicated` **(dump 中无)** | 2039 | 0 | — |  |
| `DmmGamesIdLinkAccountAlreadyExists` **(dump 中无)** | 2040 | 0 | — |  |
| `DmmGamesIdLocalUserDataNotLinked` **(dump 中无)** | 2041 | 0 | — |  |
| `HistoryNotFound` **(dump 中无)** | 2042 | 0 | — |  |
| `RankingAggregating` **(dump 中无)** | 2043 | 0 | — |  |
| `ShopExceedPurchaseThresholdOnRegisterPurchase` **(dump 中无)** | 2044 | 0 | — |  |
| `ShopExceedMaxJewelQuantityOnRegisterPurchase` **(dump 中无)** | 2045 | 0 | — |  |
| `ShopExceedPurchaseAlertThresholdOnRegisterPurchase` **(dump 中无)** | 2046 | 0 | — |  |
| `ShopExceedPurchaseLimitOnRegisterPurchase` **(dump 中无)** | 2047 | 0 | — |  |
| `ShopExceedPurchaseThresholdOnPurchase` **(dump 中无)** | 2048 | 0 | — |  |
| `ShopExceedMaxJewelQuantityOnPurchase` **(dump 中无)** | 2049 | 0 | — |  |
| `ShopExceedPurchaseLimitOnPurchase` **(dump 中无)** | 2050 | 0 | — |  |
| `PaymentBalanceInvalid` **(dump 中无)** | 2051 | 0 | — |  |
| `BlockCountLimitExceeded` **(dump 中无)** | 2052 | 0 | — |  |
| `ProduceOutdatedRentalSupportCard` **(dump 中无)** | 2301 | 0 | — |  |
| `ProduceOutdatedRentalMemory` **(dump 中无)** | 2302 | 0 | — |  |
| `ProduceHistoryNotFound` **(dump 中无)** | 2303 | 0 | — |  |
| `ProduceUuidInvalid` **(dump 中无)** | 2304 | 0 | — |  |
| `ProduceNeedReset` **(dump 中无)** | 2305 | 0 | — |  |
| `ProduceClearTimeBanWarning` **(dump 中无)** | 2306 | 0 | — |  |
| `GvgRaidStageAlreadyCleared` **(dump 中无)** | 3000 | 0 | — |  |
| `TowerProgressReset` **(dump 中无)** | 3300 | 0 | — |  |
| `BnidlinkUserNotFound` **(dump 中无)** | 5000 | 0 | — |  |
| `BnidlinkMasterDataInvalid` **(dump 中无)** | 5001 | 0 | — |  |

### EventStoryFilterType（proto 定义 5 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 67 | StoryGroup.eventStoryFilterType=67 |  |
| `StoryEvent` | 1 | 13 | StoryGroup.eventStoryFilterType=13 |  |
| `SeasonEvent` | 2 | 11 | StoryGroup.eventStoryFilterType=11 |  |
| `GvgRaid` | 3 | 1 | StoryGroup.eventStoryFilterType=1 |  |
| `Tour` | 4 | 4 | StoryGroup.eventStoryFilterType=4 |  |

### EventType（proto 定义 13 个值；dump 中出现 12 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `MissionDailyRelease` | 1 | 1 | EventLabel.eventType=1 |  |
| `MissionPanel` | 2 | 1 | EventLabel.eventType=1 |  |
| `ProduceHighScore` | 3 | 1 | EventLabel.eventType=1 |  |
| `StoryCampaign` | 4 | 1 | EventLabel.eventType=1 |  |
| `StoryEvent` | 5 | 1 | EventLabel.eventType=1 |  |
| `StoryEventMainStory` | 6 | 1 | EventLabel.eventType=1 |  |
| `StoryEventBoxGasha` | 7 | 1 | EventLabel.eventType=1 |  |
| `StoryEventGuildMission` | 8 | 1 | EventLabel.eventType=1 |  |
| `GvgRaid` | 9 | 1 | EventLabel.eventType=1 |  |
| `DearnessBoost` | 10 | 1 | EventLabel.eventType=1 |  |
| `Tour` | 11 | 1 | EventLabel.eventType=1 |  |
| `Research` | 12 | 1 | EventLabel.eventType=1 |  |

### ExamActionType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `UseHand` **(dump 中无)** | 1 | 0 | — |  |
| `UseDrink` **(dump 中无)** | 2 | 0 | — |  |
| `TurnEnd` **(dump 中无)** | 3 | 0 | — |  |
| `EffectCardSelect` **(dump 中无)** | 4 | 0 | — |  |

### ExamAiModelType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Audition` **(dump 中无)** | 1 | 0 | — |  |
| `Competition` **(dump 中无)** | 2 | 0 | — |  |

### ExamCommandType（proto 定义 17 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `TurnDraw` **(dump 中无)** | 1 | 0 | — |  |
| `UseHand` **(dump 中无)** | 2 | 0 | — |  |
| `UseDrink` **(dump 中无)** | 3 | 0 | — |  |
| `UsePool` **(dump 中无)** | 4 | 0 | — |  |
| `PlayEffect` **(dump 中无)** | 5 | 0 | — |  |
| `MovePlayCard` **(dump 中无)** | 6 | 0 | — |  |
| `TurnCheck` **(dump 中无)** | 7 | 0 | — |  |
| `PhaseChange` **(dump 中无)** | 8 | 0 | — |  |
| `SeparateActivity` **(dump 中无)** | 9 | 0 | — |  |
| `SeparateTrigger` **(dump 中无)** | 10 | 0 | — |  |
| `NoUsableCardActivity` **(dump 中无)** | 11 | 0 | — |  |
| `TurnEnd` **(dump 中无)** | 12 | 0 | — |  |
| `UserCardAfterCheck` **(dump 中无)** | 13 | 0 | — |  |
| `CardEnchantTrigger` **(dump 中无)** | 14 | 0 | — |  |
| `SupportCardUpgrade` **(dump 中无)** | 15 | 0 | — |  |
| `Panic` **(dump 中无)** | 16 | 0 | — |  |

### ExamGameType（proto 定义 7 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProduceLesson` **(dump 中无)** | 1 | 0 | — |  |
| `ProduceAudition` **(dump 中无)** | 2 | 0 | — |  |
| `PvpRate` **(dump 中无)** | 3 | 0 | — |  |
| `Tower` **(dump 中无)** | 4 | 0 | — |  |
| `GvgRaid` **(dump 中无)** | 5 | 0 | — |  |
| `Tour` **(dump 中无)** | 6 | 0 | — |  |

### ExamIdolStatusType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Concentration` **(dump 中无)** | 1 | 0 | — |  |
| `Preservation` **(dump 中无)** | 2 | 0 | — |  |
| `FullPower` **(dump 中无)** | 3 | 0 | — |  |
| `OverPreservation` **(dump 中无)** | 4 | 0 | — |  |

### ExamMotionTargetType（proto 定义 10 个值；dump 中出现 9 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `VocalLesson` | 2 | 377 | ExamMotion.type=234; ExamOutGameMotion.type=143 |  |
| `DanceLesson` | 3 | 377 | ExamMotion.type=234; ExamOutGameMotion.type=143 |  |
| `VisualLesson` | 4 | 377 | ExamMotion.type=234; ExamOutGameMotion.type=143 |  |
| `VocalLessonHard` | 5 | 351 | ExamMotion.type=234; ExamOutGameMotion.type=117 |  |
| `DanceLessonHard` | 6 | 351 | ExamMotion.type=234; ExamOutGameMotion.type=117 |  |
| `VisualLessonHard` | 7 | 351 | ExamMotion.type=234; ExamOutGameMotion.type=117 |  |
| `Audition` | 8 | 514 | ExamMotion.type=514 |  |
| `Contest` | 9 | 142 | ExamMotion.type=142 |  |
| `Tour` | 10 | 153 | ExamMotion.type=153 |  |

### ExamMotionType（proto 定义 9 个值；dump 中出现 8 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ParameterUp` | 1 | 532 | ExamMotion.motionType=532 |  |
| `ParameterUpLarge` | 2 | 302 | ExamMotion.motionType=302 |  |
| `BlockAdd` | 3 | 302 | ExamMotion.motionType=302 |  |
| `Buff` | 4 | 302 | ExamMotion.motionType=302 |  |
| `Debuff` | 5 | 302 | ExamMotion.motionType=302 |  |
| `Wait` | 6 | 245 | ExamMotion.motionType=239; ExamUnitMotion.motionType=6 |  |
| `NoMotionUseDrink` | 7 | 156 | ExamMotion.motionType=156 |  |
| `WaitOnce` | 8 | 78 | ExamMotion.motionType=78 |  |

### ExamOutGameMotionType（proto 定义 7 个值；dump 中出现 6 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Start1` | 1 | 78 | ExamOutGameMotion.motionType=78 |  |
| `Start2` | 2 | 39 | ExamOutGameMotion.motionType=39 |  |
| `ResultPerfect` | 3 | 234 | ExamOutGameMotion.motionType=234 |  |
| `ResultSuccess` | 4 | 234 | ExamOutGameMotion.motionType=234 |  |
| `ResultFailure` | 5 | 78 | ExamOutGameMotion.motionType=78 |  |
| `Clear` | 6 | 117 | ExamOutGameMotion.motionType=117 |  |

### ExamPhaseType（proto 定义 8 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ExamStandBy` **(dump 中无)** | 1 | 0 | — |  |
| `TurnStart` **(dump 中无)** | 2 | 0 | — |  |
| `TurnStartAfter` **(dump 中无)** | 3 | 0 | — |  |
| `TurnStartDraw` **(dump 中无)** | 4 | 0 | — |  |
| `Main` **(dump 中无)** | 5 | 0 | — |  |
| `TurnEnd` **(dump 中无)** | 6 | 0 | — |  |
| `ExamEnd` **(dump 中无)** | 7 | 0 | — |  |

### ExchangeItemCategoryType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `All` | 1 | 2 | ExchangeItemCategory.categoryType=2 |  |
| `ResourceType` | 2 | 1 | ExchangeItemCategory.categoryType=1 |  |
| `ItemType` | 3 | 1 | ExchangeItemCategory.categoryType=1 |  |
| `Other` | 999 | 2 | ExchangeItemCategory.categoryType=2 |  |

### ExchangeItemResetCheckStatus（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Open` **(dump 中无)** | 1 | 0 | — |  |
| `Locked` **(dump 中无)** | 2 | 0 | — |  |

### ExchangeType（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 315 | Item.exchangeType=315 |  |
| `Daily` | 1 | 1 | Item.exchangeType=1 |  |
| `Item` | 2 | 4 | Item.exchangeType=4 |  |
| `Event` | 3 | 32 | Item.exchangeType=32 |  |

### FeatureMaintenanceType（proto 定义 26 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Exchange` **(dump 中无)** | 1 | 0 | — |  |
| `Shop` **(dump 中无)** | 2 | 0 | — |  |
| `Work` **(dump 中无)** | 3 | 0 | — |  |
| `Mission` **(dump 中无)** | 4 | 0 | — |  |
| `CoinGasha` **(dump 中无)** | 5 | 0 | — |  |
| `MissionPass` **(dump 中无)** | 6 | 0 | — |  |
| `Gasha` **(dump 中无)** | 7 | 0 | — |  |
| `Guild` **(dump 中无)** | 8 | 0 | — |  |
| `Produce` **(dump 中无)** | 9 | 0 | — |  |
| `PvpRate` **(dump 中无)** | 10 | 0 | — |  |
| `Tower` **(dump 中无)** | 11 | 0 | — |  |
| `TicketExchange` **(dump 中无)** | 12 | 0 | — |  |
| `ShopTop` **(dump 中无)** | 13 | 0 | — |  |
| `StoryEvent` **(dump 中无)** | 14 | 0 | — |  |
| `ProduceHighScore` **(dump 中无)** | 15 | 0 | — |  |
| `MissionPanel` **(dump 中无)** | 16 | 0 | — |  |
| `MissionDailyRelease` **(dump 中无)** | 17 | 0 | — |  |
| `StoryCampaign` **(dump 中无)** | 18 | 0 | — |  |
| `GvgRaid` **(dump 中无)** | 19 | 0 | — |  |
| `Dearness` **(dump 中无)** | 20 | 0 | — |  |
| `Tour` **(dump 中无)** | 21 | 0 | — |  |
| `Research` **(dump 中无)** | 22 | 0 | — |  |
| `ProducerRanking` **(dump 中无)** | 23 | 0 | — |  |
| `ProduceEvent` **(dump 中无)** | 24 | 0 | — |  |
| `Competition` **(dump 中无)** | 25 | 0 | — |  |

### FourPanelComicSeries（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 219 | Media.fourPanelComicSeries=219 |  |
| `Radio` | 1 | 3 | Media.fourPanelComicSeries=3 |  |
| `Live` **(dump 中无)** | 2 | 0 | — |  |

### FriendStatusType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `None` **(dump 中无)** | 1 | 0 | — |  |
| `MutualFollow` **(dump 中无)** | 2 | 0 | — |  |
| `Follow` **(dump 中无)** | 3 | 0 | — |  |
| `Follower` **(dump 中无)** | 4 | 0 | — |  |

### GashaAnimationRarity（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `R` | 1 | 5 | GashaAnimationStep.rarity=5 |  |
| `Sr` | 2 | 12 | GashaAnimationStep.rarity=12 |  |
| `Ssr` | 3 | 31 | GashaAnimationStep.rarity=31 |  |
| `PickupSsridolCard` | 4 | 95 | GashaAnimationStep.rarity=95 |  |

### GashaAnimationStepType（proto 定义 12 个值；dump 中出现 9 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Start` | 1 | 12 | GashaAnimationStep.currentStepType=12 |  |
| `Tap` | 2 | 43 | GashaAnimationStep.currentStepType=31; GashaAnimationStep.nextStepType=12 |  |
| `Monitor` | 3 | 62 | GashaAnimationStep.currentStepType=36; GashaAnimationStep.nextStepType=26 |  |
| `Step1` | 4 | 72 | GashaAnimationStep.currentStepType=42; GashaAnimationStep.nextStepType=30 |  |
| `Step2` | 5 | 43 | GashaAnimationStep.nextStepType=29; GashaAnimationStep.currentStepType=14 |  |
| `Step3` **(dump 中无)** | 6 | 0 | — |  |
| `Step4` **(dump 中无)** | 7 | 0 | — |  |
| `Freeze` | 8 | 25 | GashaAnimationStep.nextStepType=24; GashaAnimationStep.currentStepType=1 |  |
| `FreezeAfter` | 9 | 2 | GashaAnimationStep.currentStepType=1; GashaAnimationStep.nextStepType=1 |  |
| `LightList` | 10 | 23 | GashaAnimationStep.nextStepType=17; GashaAnimationStep.currentStepType=6 |  |
| `End` | 11 | 4 | GashaAnimationStep.nextStepType=4 |  |

### GashaButtonAppealType（proto 定义 6 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 193 | GashaButton.bottomAppealType=84; GashaButton.highAppealType=81; GashaButton.appealType=28 |  |
| `AppealText` | 1 | 26 | GashaButton.appealType=21; GashaButton.highAppealType=4; GashaButton.bottomAppealType=1 |  |
| `DrawableCount` | 2 | 28 | GashaButton.bottomAppealType=18; GashaButton.appealType=10 |  |
| `CurrentStep` | 3 | 3 | GashaButton.appealType=3 |  |
| `FixSsr` | 4 | 59 | GashaButton.appealType=41; GashaButton.highAppealType=18 |  |
| `DiscountDrawableCount` **(dump 中无)** | 5 | 0 | — |  |

### GashaButtonType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Static` | 1 | 48 | GashaButton.type=48 |  |
| `Dynamic` | 2 | 55 | GashaButton.type=55 |  |

### GashaCardBonusType（proto 定义 6 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `All` **(dump 中无)** | 1 | 0 | — |  |
| `IdolCardAll` **(dump 中无)** | 2 | 0 | — |  |
| `SupportCardAll` **(dump 中无)** | 3 | 0 | — |  |
| `IdolCard` **(dump 中无)** | 4 | 0 | — |  |
| `SupportCard` **(dump 中无)** | 5 | 0 | — |  |

### GashaContinuousStepType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Drew` **(dump 中无)** | 1 | 0 | — |  |
| `Continued` **(dump 中无)** | 2 | 0 | — |  |
| `Result` **(dump 中无)** | 3 | 0 | — |  |
| `Finish` **(dump 中无)** | 4 | 0 | — |  |

### GashaLimitType（proto 定义 6 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 156 | GashaButton.discountLimitType=101; GashaButton.limitType=55 |  |
| `None` | 1 | 10 | GashaButton.limitType=10 |  |
| `Total` | 2 | 32 | GashaButton.limitType=30; GashaButton.discountLimitType=2 |  |
| `Daily` | 3 | 3 | GashaButton.limitType=3 |  |
| `DailyAccumulation` **(dump 中无)** | 4 | 0 | — |  |
| `DailyLoginAccumulation` | 5 | 5 | GashaButton.limitType=5 |  |

### GashaType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Default` **(dump 中无)** | 1 | 0 | — |  |
| `StepUp` **(dump 中无)** | 2 | 0 | — |  |
| `SelectPickup` **(dump 中无)** | 3 | 0 | — |  |
| `Continuous` **(dump 中无)** | 4 | 0 | — |  |

### GiftFilterType（proto 定义 8 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Jewel` **(dump 中无)** | 1 | 0 | — |  |
| `IdolCard` **(dump 中无)** | 2 | 0 | — |  |
| `SupportCard` **(dump 中无)** | 3 | 0 | — |  |
| `Memory` **(dump 中无)** | 4 | 0 | — |  |
| `Item` **(dump 中无)** | 5 | 0 | — |  |
| `Costume` **(dump 中无)** | 6 | 0 | — |  |
| `Other` **(dump 中无)** | 99 | 0 | — |  |

### GuildActivityPolicyType（proto 定义 7 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` **(dump 中无)** | 1 | 0 | — |  |
| `_2` **(dump 中无)** | 2 | 0 | — |  |
| `_3` **(dump 中无)** | 3 | 0 | — |  |
| `_4` **(dump 中无)** | 4 | 0 | — |  |
| `_5` **(dump 中无)** | 5 | 0 | — |  |
| `_6` **(dump 中无)** | 6 | 0 | — |  |

### GuildJoinRequestRouteType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Search` **(dump 中无)** | 1 | 0 | — |  |
| `Id` **(dump 中无)** | 2 | 0 | — |  |
| `Suggestion` **(dump 中无)** | 3 | 0 | — |  |

### GuildJoinType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `NotJoined` **(dump 中无)** | 1 | 0 | — |  |
| `Joined` **(dump 中无)** | 2 | 0 | — |  |

### GuildMissionPhaseType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProduceConditionSet1Unlocked` **(dump 中无)** | 1 | 0 | — |  |
| `ProduceConditionSet2Unlocked` **(dump 中无)** | 2 | 0 | — |  |
| `ProduceConditionSet3Unlocked` **(dump 中无)** | 3 | 0 | — |  |
| `Cleared` **(dump 中无)** | 99 | 0 | — |  |

### GuildNotificationType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Join` **(dump 中无)** | 1 | 0 | — |  |
| `Dismiss` **(dump 中无)** | 2 | 0 | — |  |

### GuildRoleType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Member` **(dump 中无)** | 1 | 0 | — |  |
| `Leader` **(dump 中无)** | 2 | 0 | — |  |
| `JoinRequester` **(dump 中无)** | 999 | 0 | — |  |

### GuildSearchMemberCountRangeType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` **(dump 中无)** | 1 | 0 | — |  |
| `_2` **(dump 中无)** | 2 | 0 | — |  |
| `_3` **(dump 中无)** | 3 | 0 | — |  |

### GvgRaidStageIconSizeType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Small` **(dump 中无)** | 1 | 0 | — |  |
| `Medium` **(dump 中无)** | 2 | 0 | — |  |
| `Large` **(dump 中无)** | 3 | 0 | — |  |

### HomeLocationType（proto 定义 6 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Home` | 1 | 1373 | HomeMotion.locationType=1373 |  |
| `Idol` | 2 | 143 | HomeMotion.locationType=143 |  |
| `Contest` | 3 | 143 | HomeMotion.locationType=143 |  |
| `Story1` | 4 | 78 | HomeMotion.locationType=78 |  |
| `Story2` | 5 | 52 | HomeMotion.locationType=52 |  |

### HomeMotionType（proto 定义 9 个值；dump 中出现 8 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Wait1` | 1 | 78 | HomeMotion.motionType=78 |  |
| `Wait2` | 2 | 26 | HomeMotion.motionType=26 |  |
| `Reaction` | 3 | 836 | HomeMotion.motionType=836 |  |
| `ReactionOnce` | 4 | 26 | HomeMotion.motionType=26 |  |
| `WaitLookAround` | 5 | 13 | HomeMotion.motionType=13 |  |
| `MultipleTaps` | 6 | 91 | HomeMotion.motionType=91 |  |
| `Transition` | 7 | 706 | HomeMotion.motionType=706 |  |
| `WaitOnce` | 8 | 13 | HomeMotion.motionType=13 |  |

### HomeTimeType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Morning` | 1 | 1 | HomeTime.type=1 |  |
| `Daytime` | 2 | 1 | HomeTime.type=1 |  |
| `Evening` | 3 | 1 | HomeTime.type=1 |  |
| `Night` | 4 | 1 | HomeTime.type=1 |  |

### HomeType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Home` **(dump 中无)** | 1 | 0 | — |  |
| `Idol` **(dump 中无)** | 2 | 0 | — |  |
| `Contest` **(dump 中无)** | 3 | 0 | — |  |
| `Story` **(dump 中无)** | 4 | 0 | — |  |

### IdolCardDifficultyType（proto 定义 4 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Low` | 1 | 3 | IdolCardSkinSelectReward.difficultyType=3 |  |
| `Middle` | 2 | 4 | IdolCardSkinSelectReward.difficultyType=4 |  |
| `High` | 3 | 5 | IdolCardSkinSelectReward.difficultyType=5 |  |

### IdolSkillPossessionType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `IdolSkill1` **(dump 中无)** | 1 | 0 | — |  |
| `IdolSkill2` **(dump 中无)** | 2 | 0 | — |  |
| `IdolSkill3` **(dump 中无)** | 3 | 0 | — |  |

### ItemRarity（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 97 | Item.rarity=97 |  |
| `N` **(dump 中无)** | 1 | 0 | — |  |
| `R` | 2 | 66 | Item.rarity=66 |  |
| `Sr` | 3 | 27 | Item.rarity=27 |  |
| `Ssr` | 4 | 162 | Item.rarity=162 |  |

### ItemType（proto 定义 24 个值；dump 中出现 24 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 5 | ExchangeItemCategory.itemType=5 |  |
| `Money` | 1 | 2 | Item.type=1; LimitItem.type=1 |  |
| `ProduceContinue` | 2 | 2 | Item.type=1; LimitItem.type=1 |  |
| `SupportCardEnhancePoint` | 3 | 2 | Item.type=1; LimitItem.type=1 |  |
| `ActionPointRecovery` | 4 | 2 | Item.type=1; LimitItem.type=1 |  |
| `IdolCardLevelLimitMaterial` | 5 | 25 | Item.type=24; LimitItem.type=1 |  |
| `ProduceRerollMemory` | 6 | 2 | Item.type=1; LimitItem.type=1 |  |
| `GashaTicket` | 7 | 58 | Item.type=57; LimitItem.type=1 |  |
| `Coin` | 8 | 17 | Item.type=16; LimitItem.type=1 |  |
| `ExchangeMaterial` | 9 | 3 | Item.type=2; LimitItem.type=1 |  |
| `Medal` | 10 | 65 | Item.type=64; LimitItem.type=1 |  |
| `IdolCardPiece` | 11 | 153 | Item.type=151; ExchangeItemCategory.itemType=1; LimitItem.type=1 |  |
| `FriendCoin` | 12 | 2 | Item.type=1; LimitItem.type=1 |  |
| `PvpRateCoin` | 13 | 2 | Item.type=1; LimitItem.type=1 |  |
| `StoryUnlockKey` | 14 | 2 | Item.type=1; LimitItem.type=1 |  |
| `ExchangeTicket` | 15 | 9 | Item.type=8; LimitItem.type=1 |  |
| `ProduceLiveUnlockItem` | 16 | 1 | LimitItem.type=1 |  |
| `IdolCardPotentialRankUpgrade` | 17 | 4 | Item.type=3; LimitItem.type=1 |  |
| `SupportCardLevelLimitRankUpgrade` | 18 | 4 | Item.type=3; LimitItem.type=1 |  |
| `MemoryInherit` | 19 | 2 | Item.type=1; LimitItem.type=1 |  |
| `DearnessStoryUnlock` | 20 | 14 | Item.type=13; LimitItem.type=1 |  |
| `CompetitionCoin` | 21 | 1 | LimitItem.type=1 |  |
| `ProduceBoostRewardSupportCardEnhancePoint` | 102 | 2 | Item.type=1; LimitItem.type=1 |  |
| `ProduceBoostRewardIdolCardLevelLimitMaterial` | 103 | 2 | Item.type=1; LimitItem.type=1 |  |

### LangType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Ja` **(dump 中无)** | 1 | 0 | — |  |
| `Ko` **(dump 中无)** | 2 | 0 | — |  |
| `ZhTw` **(dump 中无)** | 3 | 0 | — |  |

### LinkType（proto 定义 42 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Story` **(dump 中无)** | 1 | 0 | — |  |
| `Notice` **(dump 中无)** | 2 | 0 | — |  |
| `Seminar` **(dump 中无)** | 3 | 0 | — |  |
| `Produce` **(dump 中无)** | 4 | 0 | — |  |
| `Memory` **(dump 中无)** | 5 | 0 | — |  |
| `CoinGasha` **(dump 中无)** | 7 | 0 | — |  |
| `TicketExchange` **(dump 中无)** | 9 | 0 | — |  |
| `MissionPass` **(dump 中无)** | 10 | 0 | — |  |
| `MissionGroup` **(dump 中无)** | 11 | 0 | — |  |
| `MissionDailyRelease` **(dump 中无)** | 12 | 0 | — |  |
| `MissionPanel` **(dump 中无)** | 13 | 0 | — |  |
| `Music` **(dump 中无)** | 14 | 0 | — |  |
| `Guild` **(dump 中无)** | 15 | 0 | — |  |
| `Friend` **(dump 中无)** | 16 | 0 | — |  |
| `MediaMovie` **(dump 中无)** | 17 | 0 | — |  |
| `MediaComic` **(dump 中无)** | 18 | 0 | — |  |
| `Invitation` **(dump 中无)** | 19 | 0 | — |  |
| `PvpRate` **(dump 中无)** | 20 | 0 | — |  |
| `Meishi` **(dump 中无)** | 21 | 0 | — |  |
| `StoryEvent` **(dump 中无)** | 22 | 0 | — |  |
| `ProduceHighScore` **(dump 中无)** | 23 | 0 | — |  |
| `Tower` **(dump 中无)** | 24 | 0 | — |  |
| `Gasha` **(dump 中无)** | 25 | 0 | — |  |
| `ShopJewel` **(dump 中无)** | 26 | 0 | — |  |
| `ShopPass` **(dump 中无)** | 27 | 0 | — |  |
| `ShopPack` **(dump 中无)** | 28 | 0 | — |  |
| `ExchangeDaily` **(dump 中无)** | 29 | 0 | — |  |
| `ExchangeItem` **(dump 中无)** | 30 | 0 | — |  |
| `ExchangeEvent` **(dump 中无)** | 31 | 0 | — |  |
| `MediaFourPanelComic` **(dump 中无)** | 32 | 0 | — |  |
| `PhotoTop` **(dump 中无)** | 33 | 0 | — |  |
| `PhotoIdol` **(dump 中无)** | 34 | 0 | — |  |
| `GvgRaid` **(dump 中无)** | 35 | 0 | — |  |
| `ShopCostume` **(dump 中无)** | 36 | 0 | — |  |
| `PhotoLiveSelect` **(dump 中无)** | 37 | 0 | — |  |
| `Tour` **(dump 中无)** | 38 | 0 | — |  |
| `Research` **(dump 中无)** | 39 | 0 | — |  |
| `ProducerRanking` **(dump 中无)** | 40 | 0 | — |  |
| `Competition` **(dump 中无)** | 41 | 0 | — |  |
| `WebStore` **(dump 中无)** | 42 | 0 | — |  |
| `ProduceCardConversion` **(dump 中无)** | 43 | 0 | — |  |

### LoginBonusType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Normal` **(dump 中无)** | 1 | 0 | — |  |
| `Event3D` **(dump 中无)** | 2 | 0 | — |  |
| `Event2D` **(dump 中无)** | 3 | 0 | — |  |

### MainTaskType（proto 定义 6 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `MainStory` | 1 | 1 | MainTaskGroup.mainTaskType=1 |  |
| `Producer` | 2 | 3 | MainTaskGroup.mainTaskType=3 |  |
| `Producer2` **(dump 中无)** | 3 | 0 | — |  |
| `Producer3` **(dump 中无)** | 4 | 0 | — |  |
| `Producer4` **(dump 中无)** | 5 | 0 | — |  |

### MediaMovieType（proto 定义 3 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 189 | Media.mediaMovieType=189 |  |
| `Movie` | 1 | 6 | Media.mediaMovieType=6 |  |
| `Birthday` | 2 | 16 | Media.mediaMovieType=16 |  |

### MediaType（proto 定义 6 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Movie` | 1 | 33 | Media.mediaType=33 |  |
| `Comic` | 2 | 23 | Media.mediaType=23 |  |
| `Other` **(dump 中无)** | 3 | 0 | — |  |
| `FourPanelComic` | 4 | 163 | Media.mediaType=163 |  |
| `FourPanelComicOther` | 5 | 3 | Media.mediaType=3 |  |

### MeishiBaseAssetType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `StoryBackground` | 1 | 70 | MeishiBaseAsset.meishiBaseAssetType=70 |  |
| `CommonBackground` | 2 | 42 | MeishiBaseAsset.meishiBaseAssetType=42 |  |
| `Frame` | 3 | 153 | MeishiBaseAsset.meishiBaseAssetType=153 |  |
| `Other` | 99 | 34 | MeishiBaseAsset.meishiBaseAssetType=34 |  |

### MeishiIllustrationType（proto 定义 8 个值；dump 中出现 7 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Idol` | 1 | 13 | MeishiIllustrationAsset.type=13 |  |
| `Sdcharacter` | 2 | 23 | MeishiIllustrationAsset.type=23 |  |
| `IdolSign` | 3 | 23 | MeishiIllustrationAsset.type=23 |  |
| `Logo` | 4 | 21 | MeishiIllustrationAsset.type=21 |  |
| `PictoIcon` | 5 | 109 | MeishiIllustrationAsset.type=109 |  |
| `Badge` | 6 | 333 | MeishiIllustrationAsset.type=333 |  |
| `Other` | 99 | 177 | MeishiIllustrationAsset.type=177 |  |

### MeishiObjectType（proto 定义 19 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `UserName` **(dump 中无)** | 1 | 0 | — |  |
| `Achievement` **(dump 中无)** | 2 | 0 | — |  |
| `Illustration` **(dump 中无)** | 3 | 0 | — |  |
| `PublicUserId` **(dump 中无)** | 4 | 0 | — |  |
| `ProducerLevel` **(dump 中无)** | 5 | 0 | — |  |
| `Comment` **(dump 中无)** | 6 | 0 | — |  |
| `TotalFanCount` **(dump 中无)** | 7 | 0 | — |  |
| `PvpRateGrade` **(dump 中无)** | 8 | 0 | — |  |
| `IdolCardSkin` **(dump 中无)** | 9 | 0 | — |  |
| `SupportCard` **(dump 中无)** | 10 | 0 | — |  |
| `ProduceCard` **(dump 中无)** | 11 | 0 | — |  |
| `ProduceItem` **(dump 中无)** | 12 | 0 | — |  |
| `ProduceDrink` **(dump 中无)** | 13 | 0 | — |  |
| `Photo` **(dump 中无)** | 14 | 0 | — |  |
| `Memory` **(dump 中无)** | 15 | 0 | — |  |
| `Movie` **(dump 中无)** | 16 | 0 | — |  |
| `BaseAsset` **(dump 中无)** | 17 | 0 | — |  |
| `Other` **(dump 中无)** | 999 | 0 | — |  |

### MissionCategory（proto 定义 8 个值；dump 中出现 7 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `MainTask` | 1 | 310 | Mission.category=310 |  |
| `Daily` | 2 | 21 | Mission.category=21 |  |
| `Weekly` | 3 | 8 | Mission.category=8 |  |
| `Normal` | 4 | 265 | Mission.category=265 |  |
| `Special` | 5 | 1400 | Mission.category=1400 |  |
| `Event` | 6 | 157 | Mission.category=157 |  |
| `Achievement` | 7 | 1206 | Mission.category=1206 |  |

### MissionType（proto 定义 127 个值；dump 中出现 126 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `IncrementMissionClear` | 101 | 171 | Mission.type=167; Achievement.missionType=3; MainTaskIcon.missionType=1 |  |
| `IncrementLoginCount` | 102 | 3 | Mission.type=2; MainTaskIcon.missionType=1 |  |
| `IncrementDailyHomeEnterCount` | 103 | 44 | Mission.type=43; MainTaskIcon.missionType=1 |  |
| `IncrementGashaDrawCount` | 104 | 10 | Mission.type=9; MainTaskIcon.missionType=1 |  |
| `IncrementWorkCount` | 105 | 15 | Mission.type=13; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementWorkExcellentCount` | 106 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementWorkDurationHour` | 107 | 15 | Mission.type=8; MainTask.missionType=5; Achievement.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementConsumeActionPoint` | 108 | 87 | Mission.type=85; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementShopCoinGashaDrawCount` | 109 | 15 | Mission.type=11; MainTask.missionType=3; MainTaskIcon.missionType=1 |  |
| `IncrementEventCoinGashaDrawCount` | 110 | 12 | Mission.type=11; MainTaskIcon.missionType=1 |  |
| `IncrementDailyExchangeCount` | 111 | 7 | Mission.type=5; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementItemExchangeCount` | 112 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementEventExchangeCount` | 113 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementProvideItemCount` | 114 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementReceiveMoney` | 115 | 8 | Mission.type=5; Achievement.missionType=1; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementIdolCardLevelLimitRankUpdateCount` | 121 | 4 | Mission.type=2; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementIdolCardPotentialRankUpdateCount` | 122 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementSupportCardCount` | 123 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementSupportCardLevelUpdateCount` | 124 | 6 | Mission.type=4; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementSupportCardLevelLimitRankUpdateCount` | 125 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementFanCount` | 134 | 51 | Mission.type=50; MainTaskIcon.missionType=1 |  |
| `IncrementMemoryGradeCount` | 137 | 8 | Mission.type=7; MainTaskIcon.missionType=1 |  |
| `IncrementMemoryExchangeCount` | 138 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementMeishiUpdateCount` | 142 | 3 | MainTask.missionType=1; MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementMeishiExchangeCount` | 144 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementMeishiXpostCount` | 145 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementGuildDonationRequestCount` | 146 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementGuildDonationCount` | 147 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementPvpRatePlayCount` | 160 | 14 | Mission.type=9; MainTask.missionType=4; MainTaskIcon.missionType=1 |  |
| `IncrementPvpRateCharacterPlayCount` | 161 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementPvpRateWinCount` | 162 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementPvpRateCharacterWinCount` | 163 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementPvpRateExamBattleScoreCount` | 164 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementUrlTransition` | 165 | 3 | Mission.type=2; MainTaskIcon.missionType=1 |  |
| `IncrementProfileUpdateCount` | 166 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementPvpRateCharacterExamBattleScoreCount` | 167 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementPhotoIdolCount` | 168 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementGvgRaidChallengeCount` | 169 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementGvgRaidLoopChallengeCount` | 170 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementTourLevelPlayCount` | 171 | 14 | Mission.type=13; MainTaskIcon.missionType=1 |  |
| `IncrementCompetitionPlayCount` | 172 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementCompetitionWinCount` | 173 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementCompetitionUseProduceCardCount` | 174 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementCompetitionStageScoreCount` | 175 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementGashaContinuousSnsShareCount` | 176 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementProduceSupportCardDeckUpdateCount` | 201 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementProduceMemoryDeckUpdateCount` | 202 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementProduceTotalScore` | 203 | 406 | Mission.type=400; Achievement.missionType=4; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementProduceVoteCount` | 205 | 32 | Mission.type=16; Achievement.missionType=13; MainTask.missionType=2; MainTaskIcon.missionType=1 |  |
| `IncrementProduceTotalProducePoint` | 206 | 10 | Mission.type=8; Achievement.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementProduceGetProduceCardCount` | 207 | 9 | Mission.type=7; Achievement.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementProduceGetProduceDrinkCount` | 208 | 9 | Mission.type=7; Achievement.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementProduceGetProduceItemCount` | 209 | 3 | Achievement.missionType=1; MainTaskIcon.missionType=1; Mission.type=1 |  |
| `IncrementProduceTotalAdditionExamBlock` | 213 | 11 | Achievement.missionType=5; Mission.type=5; MainTaskIcon.missionType=1 |  |
| `IncrementProduceConsumedStamina` | 214 | 17 | Mission.type=11; Achievement.missionType=5; MainTaskIcon.missionType=1 |  |
| `IncrementProduceExamUseProduceCardCount` | 215 | 40 | Mission.type=26; Achievement.missionType=13; MainTaskIcon.missionType=1 |  |
| `IncrementProduceCustomizeProduceCardCount` | 216 | 43 | Mission.type=37; MainTask.missionType=5; MainTaskIcon.missionType=1 |  |
| `IncrementProduceUpgradeProduceCardCount` | 217 | 39 | Mission.type=32; Achievement.missionType=5; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementProduceUseProduceDrinkCount` | 218 | 44 | Mission.type=38; Achievement.missionType=5; MainTaskIcon.missionType=1 |  |
| `IncrementProduceAdditionParameter` | 219 | 1 | MainTaskIcon.missionType=1 |  |
| `IncrementProducePlayCount` | 220 | 38 | Mission.type=21; MainTask.missionType=15; Achievement.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementProducePlanPlayCount` | 221 | 43 | Mission.type=30; MainTask.missionType=12; MainTaskIcon.missionType=1 |  |
| `IncrementProduceCharacterPlayCount` | 222 | 37 | Mission.type=23; Achievement.missionType=13; MainTaskIcon.missionType=1 |  |
| `IncrementProduceIdolCardPlayCount` | 223 | 253 | Achievement.missionType=126; Mission.type=126; MainTaskIcon.missionType=1 |  |
| `IncrementProduceClearCount` | 224 | 177 | Mission.type=165; Achievement.missionType=11; MainTaskIcon.missionType=1 |  |
| `IncrementProducePlanClearCount` | 225 | 26 | Mission.type=16; MainTask.missionType=9; MainTaskIcon.missionType=1 |  |
| `IncrementProduceCharacterClearCount` | 226 | 441 | Mission.type=271; Achievement.missionType=138; MainTask.missionType=31; MainTaskIcon.missionType=1 |  |
| `IncrementProduceIdolCardClearCount` | 227 | 266 | Mission.type=139; Achievement.missionType=126; MainTaskIcon.missionType=1 |  |
| `IncrementProduceSelectStepCount` | 228 | 102 | Mission.type=82; Achievement.missionType=18; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementProduceShopBuyCount` | 229 | 36 | Mission.type=30; Achievement.missionType=5; MainTaskIcon.missionType=1 |  |
| `IncrementProduceLessonClearCount` | 230 | 149 | Mission.type=119; Achievement.missionType=28; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `IncrementProduceGroupSelectStepCount` | 231 | 21 | Mission.type=20; MainTaskIcon.missionType=1 |  |
| `AbsoluteLinkBandaiNamco` | 301 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteLoginCount` | 302 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteAchievementCount` | 303 | 43 | MainTask.missionType=21; Mission.type=21; MainTaskIcon.missionType=1 |  |
| `AbsoluteCharacterIdolAchievementCount` | 304 | 27 | Achievement.missionType=13; Mission.type=13; MainTaskIcon.missionType=1 |  |
| `AbsoluteMainTaskCount` | 305 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteProducerLevel` | 310 | 50 | Mission.type=26; MainTask.missionType=20; Achievement.missionType=3; MainTaskIcon.missionType=1 |  |
| `AbsoluteIdolCardCount` | 311 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteIdolCardLevelLimitRank` | 312 | 1058 | Mission.type=529; Achievement.missionType=528; MainTaskIcon.missionType=1 |  |
| `AbsoluteIdolCardLevelLimitRankCount` | 313 | 33 | MainTask.missionType=16; Mission.type=16; MainTaskIcon.missionType=1 |  |
| `AbsoluteIdolCardPotentialRankCount` | 314 | 5 | Mission.type=4; MainTaskIcon.missionType=1 |  |
| `AbsoluteSupportCardCount` | 315 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteSupportCardLevelCount` | 316 | 25 | MainTask.missionType=12; Mission.type=12; MainTaskIcon.missionType=1 |  |
| `AbsoluteSupportCardLevelLimitRankCount` | 317 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteSupportCardLevel` | 319 | 6 | Mission.type=3; MainTask.missionType=2; MainTaskIcon.missionType=1 |  |
| `AbsoluteIdolCardPrimaStellaCount` | 320 | 3 | Achievement.missionType=1; MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteFanCount` | 335 | 44 | Mission.type=22; Achievement.missionType=16; MainTask.missionType=5; MainTaskIcon.missionType=1 |  |
| `AbsoluteDearnessLevel` | 337 | 157 | Mission.type=98; MainTask.missionType=45; Achievement.missionType=13; MainTaskIcon.missionType=1 |  |
| `AbsoluteMeishiUpdateCount` | 343 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteMeishiExchangeCount` | 346 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteFollowCount` | 348 | 3 | MainTask.missionType=1; MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteFollowerCount` | 349 | 3 | Achievement.missionType=1; MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteStoryRead` | 364 | 30 | Mission.type=15; MainTask.missionType=14; MainTaskIcon.missionType=1 |  |
| `AbsoluteGuildJoin` | 365 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsolutePvpRateGrade` | 366 | 14 | Mission.type=13; MainTaskIcon.missionType=1 |  |
| `AbsolutePvpRateUnitOverallPower` | 367 | 31 | Mission.type=16; MainTask.missionType=14; MainTaskIcon.missionType=1 |  |
| `AbsolutePvpRateExamBattleMaxScore` | 368 | 36 | Mission.type=18; MainTask.missionType=14; Achievement.missionType=3; MainTaskIcon.missionType=1 |  |
| `AbsolutePvpRateCharacterExamBattleMaxScore` | 369 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsolutePvpRateRank` | 370 | 5 | Mission.type=4; MainTaskIcon.missionType=1 |  |
| `AbsoluteTowerTotalClearRank` | 371 | 35 | MainTask.missionType=17; Mission.type=17; MainTaskIcon.missionType=1 |  |
| `AbsoluteTowerCharacterTotalClearRank` | 372 | 40 | Mission.type=26; Achievement.missionType=13; MainTaskIcon.missionType=1 |  |
| `AbsoluteTowerClearRank` | 373 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteIdolCardSkin` | 374 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteSupportCard` | 375 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteTowerLayerClear` | 376 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsolutePvpRateCurrentGrade` | 377 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteLinkSmartphoneWithDmm` | 378 | 2 | MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteCompetitionGrade` | 379 | 8 | Mission.type=7; MainTaskIcon.missionType=1 |  |
| `AbsoluteCompetitionRank` | 380 | 5 | Mission.type=4; MainTaskIcon.missionType=1 |  |
| `AbsoluteCompetitionDeckPower` | 381 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteCompetitionTotalHighScore` | 382 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteCompetitionStageHighScore` | 383 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteProduceIdolCardHighScore` | 401 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteProducePlanTotalHighScore` | 402 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteProducePictureBookProduceCardCount` | 410 | 24 | Mission.type=15; MainTask.missionType=7; Achievement.missionType=1; MainTaskIcon.missionType=1 |  |
| `AbsoluteProducePictureBookProduceDrinkCount` | 411 | 5 | Mission.type=2; Achievement.missionType=1; MainTask.missionType=1; MainTaskIcon.missionType=1 |  |
| `AbsoluteProducePictureBookProduceItemCount` | 412 | 3 | Achievement.missionType=1; MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteProduceCharacterEnding` | 420 | 185 | Mission.type=139; Achievement.missionType=37; MainTask.missionType=8; MainTaskIcon.missionType=1 |  |
| `AbsoluteSeminarExamClear` | 421 | 18 | Mission.type=9; MainTask.missionType=8; MainTaskIcon.missionType=1 |  |
| `AbsoluteProducePlayCharacterCount` | 422 | 3 | MainTask.missionType=1; MainTaskIcon.missionType=1; Mission.type=1 |  |
| `AbsoluteProduceStoryRead` | 423 | 1 | MainTaskIcon.missionType=1 |  |
| `AbsoluteProduceGrowthPanelComplete` | 424 | 3 | Achievement.missionType=1; MainTaskIcon.missionType=1; Mission.type=1 |  |
| `ConditionClear` | 998 | 54 | Mission.type=42; Achievement.missionType=11; MainTaskIcon.missionType=1 |  |
| `ProduceConditionClear` | 999 | 37 | Mission.type=29; MainTask.missionType=7; MainTaskIcon.missionType=1 |  |
| `ProduceConditionClearBeforeLiveEvaluation` | 1000 | 197 | Mission.type=158; Achievement.missionType=38; MainTaskIcon.missionType=1 |  |

### MusicType（proto 定义 4 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Music` | 1 | 293 | Music.type=293 |  |
| `Instrumental` | 2 | 87 | Music.type=87 |  |
| `Bgm` | 3 | 36 | Music.type=36 |  |

### MusicWishListRequesterType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Self` **(dump 中无)** | 1 | 0 | — |  |
| `OtherUser` **(dump 中无)** | 2 | 0 | — |  |
| `Character` **(dump 中无)** | 3 | 0 | — |  |

### NoticeCategory（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Info` **(dump 中无)** | 1 | 0 | — |  |
| `Bug` **(dump 中无)** | 2 | 0 | — |  |
| `Pr` **(dump 中无)** | 3 | 0 | — |  |

### NoticeType（proto 定义 9 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Update` **(dump 中无)** | 1 | 0 | — |  |
| `Gasha` **(dump 中无)** | 2 | 0 | — |  |
| `Campaign` **(dump 中无)** | 3 | 0 | — |  |
| `Event` **(dump 中无)** | 4 | 0 | — |  |
| `Important` **(dump 中无)** | 5 | 0 | — |  |
| `Information` **(dump 中无)** | 6 | 0 | — |  |
| `Maintenance` **(dump 中无)** | 7 | 0 | — |  |
| `Bug` **(dump 中无)** | 8 | 0 | — |  |

### PaymentPendingReceiptDialogTimingType（proto 定义 2 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Skip` **(dump 中无)** | 1 | 0 | — |  |

### PhotoBackgroundCategory（proto 定义 5 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Gakuen` | 1 | 4 | PhotoBackground.category=4 |  |
| `Dormitory` **(dump 中无)** | 2 | 0 | — |  |
| `Around` | 3 | 2 | PhotoBackground.category=2 |  |
| `Other` | 99 | 2 | PhotoBackground.category=2 |  |

### PhotoBackgroundTimeType（proto 定义 5 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Morning` **(dump 中无)** | 1 | 0 | — |  |
| `Noon` | 2 | 7 | PhotoBackground.timeTypes=7 |  |
| `Evening` | 3 | 1 | PhotoBackground.timeTypes=1 |  |
| `Night` | 4 | 2 | PhotoBackground.timeTypes=2 |  |

### PhotoButtonExecuteType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Click` **(dump 中无)** | 1 | 0 | — |  |
| `PressStart` **(dump 中无)** | 2 | 0 | — |  |
| `PressEnd` **(dump 中无)** | 3 | 0 | — |  |

### PhotoLookTargetType（proto 定义 4 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Ng` | 1 | 197 | PhotoPose.lookTargetType=197 |  |
| `Eye` **(dump 中无)** | 2 | 0 | — |  |
| `FullBody` | 3 | 843 | PhotoPose.lookTargetType=843 |  |

### PhotoPoseMotionType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Reaction` | 1 | 780 | PhotoPose.motionType=780 |  |
| `Wait` | 2 | 260 | PhotoPose.motionType=260 |  |

### PlatformType（proto 定义 6 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Ios` | 1 | 9 | Rule.platformType=8; ForceAppVersion.platformType=1 |  |
| `Android` | 2 | 9 | Rule.platformType=8; ForceAppVersion.platformType=1 |  |
| `Dmm` | 3 | 8 | Rule.platformType=7; ForceAppVersion.platformType=1 |  |
| `Sbps` **(dump 中无)** | 4 | 0 | — |  |
| `Other` | 999 | 1 | ForceAppVersion.platformType=1 |  |

### PreferenceType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `PhotoButtonExecuteType` **(dump 中无)** | 1 | 0 | — |  |
| `ProduceDisableForceLiveCommon` **(dump 中无)** | 2 | 0 | — |  |
| `ProduceNextIdolAuditionProEasyMode` **(dump 中无)** | 3 | 0 | — |  |

### ProduceAdvType（proto 定义 20 个值；dump 中出现 19 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `BeforeFinalLessonHard` | 1 | 2 | ProduceAdv.type=2 |  |
| `BeforeMid1LessonHard` | 2 | 2 | ProduceAdv.type=2 |  |
| `BeforeMid2LessonHard` | 3 | 2 | ProduceAdv.type=2 |  |
| `BeforeFinalAuditionRefresh` | 10 | 4 | ProduceAdv.type=2; ProduceSplitAdv.type=2 |  |
| `BeforeMid1AuditionRefresh` | 11 | 4 | ProduceAdv.type=2; ProduceSplitAdv.type=2 |  |
| `BeforeMid2AuditionRefresh` | 12 | 3 | ProduceAdv.type=2; ProduceSplitAdv.type=1 |  |
| `BeforeFinalAuditionSelect` | 13 | 1 | ProduceAdv.type=1 |  |
| `BeforeMid1AuditionSelect` | 14 | 1 | ProduceAdv.type=1 |  |
| `BeforeMid2AuditionSelect` | 15 | 1 | ProduceAdv.type=1 |  |
| `Introduction` | 17 | 10 | ProduceCharacterAdv.type=10 |  |
| `StepSkip` | 18 | 1 | ProduceAdv.type=1 |  |
| `Opening` | 19 | 8 | ProduceSplitAdv.type=6; ProduceAdv.type=2 |  |
| `ProduceResultTrueEnd` | 20 | 4 | ProduceAdv.type=2; ProduceSplitAdv.type=2 |  |
| `ProduceResultA` | 21 | 4 | ProduceAdv.type=2; ProduceSplitAdv.type=2 |  |
| `ProduceResultB` | 22 | 4 | ProduceAdv.type=2; ProduceSplitAdv.type=2 |  |
| `ProduceResultC` | 23 | 4 | ProduceAdv.type=2; ProduceSplitAdv.type=2 |  |
| `ProduceResultFailedFinal` | 24 | 4 | ProduceAdv.type=2; ProduceSplitAdv.type=2 |  |
| `ProduceResultFailedMid1` | 25 | 4 | ProduceAdv.type=2; ProduceSplitAdv.type=2 |  |
| `ProduceResultFailedMid2` | 26 | 3 | ProduceAdv.type=2; ProduceSplitAdv.type=1 |  |

### ProduceCampaignType（proto 定义 9 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ActionPointDown` **(dump 中无)** | 1 | 0 | — |  |
| `MemoryRentalCountUp` **(dump 中无)** | 2 | 0 | — |  |
| `RewardQuantityUp` **(dump 中无)** | 3 | 0 | — |  |
| `ProduceResultRewardAdd` **(dump 中无)** | 4 | 0 | — |  |
| `ProduceResultRewardChange` **(dump 中无)** | 5 | 0 | — |  |
| `MemoryRerollCountUp` **(dump 中无)** | 6 | 0 | — |  |
| `MemoryRerollFree` **(dump 中无)** | 7 | 0 | — |  |
| `Event` **(dump 中无)** | 8 | 0 | — |  |

### ProduceCardSearchStatusType（proto 定义 6 个值；dump 中出现 1 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 280 | ProduceCardSearch.cardStatusType=280 |  |
| `LostPlay` **(dump 中无)** | 1 | 0 | — |  |
| `EndTurnLost` **(dump 中无)** | 2 | 0 | — |  |
| `Initial` **(dump 中无)** | 4 | 0 | — |  |
| `Restrict` **(dump 中无)** | 5 | 0 | — |  |
| `GravePlay` **(dump 中无)** | 6 | 0 | — |  |

### ProduceConditionType（proto 定义 76 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `EventOccurred` **(dump 中无)** | 1 | 0 | — |  |
| `EventNotOccurred` **(dump 中无)** | 2 | 0 | — |  |
| `SupportCard` **(dump 中无)** | 3 | 0 | — |  |
| `MemoryCharacter` **(dump 中无)** | 4 | 0 | — |  |
| `SelectStepCount` **(dump 中无)** | 6 | 0 | — |  |
| `ProduceCardUpgradeCount` **(dump 中无)** | 9 | 0 | — |  |
| `ProduceCardDeleteCount` **(dump 中无)** | 10 | 0 | — |  |
| `CurrentStepCountPermil` **(dump 中无)** | 12 | 0 | — |  |
| `LessonClearCount` **(dump 中无)** | 13 | 0 | — |  |
| `CurrentStepCount` **(dump 中无)** | 14 | 0 | — |  |
| `Vocal` **(dump 中无)** | 15 | 0 | — |  |
| `Dance` **(dump 中无)** | 16 | 0 | — |  |
| `Visual` **(dump 中无)** | 17 | 0 | — |  |
| `Stamina` **(dump 中无)** | 18 | 0 | — |  |
| `ProducePoint` **(dump 中无)** | 20 | 0 | — |  |
| `HasProduceCard` **(dump 中无)** | 21 | 0 | — |  |
| `ProduceCardCount` **(dump 中无)** | 22 | 0 | — |  |
| `ProduceDrinkCount` **(dump 中无)** | 23 | 0 | — |  |
| `ProduceItemCount` **(dump 中无)** | 24 | 0 | — |  |
| `ShopPreviousConsumedProducePoint` **(dump 中无)** | 26 | 0 | — |  |
| `ShopProduceCardBuyCount` **(dump 中无)** | 27 | 0 | — |  |
| `ShopProduceItemBuyCount` **(dump 中无)** | 28 | 0 | — |  |
| `ShopProduceDrinkBuyCount` **(dump 中无)** | 29 | 0 | — |  |
| `LessonVocalScore` **(dump 中无)** | 30 | 0 | — |  |
| `LessonDanceScore` **(dump 中无)** | 31 | 0 | — |  |
| `LessonVisualScore` **(dump 中无)** | 32 | 0 | — |  |
| `ProduceEffectTypeCount` **(dump 中无)** | 33 | 0 | — |  |
| `AuditionMid1Score` **(dump 中无)** | 34 | 0 | — |  |
| `AuditionMid2Score` **(dump 中无)** | 35 | 0 | — |  |
| `AuditionFinalScore` **(dump 中无)** | 36 | 0 | — |  |
| `AuditionMid1Pass` **(dump 中无)** | 37 | 0 | — |  |
| `AuditionMid2Pass` **(dump 中无)** | 38 | 0 | — |  |
| `AuditionFinalPass` **(dump 中无)** | 39 | 0 | — |  |
| `SelectStepCountVocalLesson` **(dump 中无)** | 43 | 0 | — |  |
| `SelectStepCountDanceLesson` **(dump 中无)** | 44 | 0 | — |  |
| `SelectStepCountVisualLesson` **(dump 中无)** | 45 | 0 | — |  |
| `SelectableStep` **(dump 中无)** | 46 | 0 | — |  |
| `NextAuditionBaseVocalPermil` **(dump 中无)** | 47 | 0 | — |  |
| `NextAuditionBaseDancePermil` **(dump 中无)** | 48 | 0 | — |  |
| `NextAuditionBaseVisualPermil` **(dump 中无)** | 49 | 0 | — |  |
| `DearnessLevel` **(dump 中无)** | 50 | 0 | — |  |
| `ClearProduceAchievement` **(dump 中无)** | 51 | 0 | — |  |
| `ConditionSet` **(dump 中无)** | 52 | 0 | — |  |
| `CurrentProduce` **(dump 中无)** | 53 | 0 | — |  |
| `ProduceScoreGrade` **(dump 中无)** | 55 | 0 | — |  |
| `ProduceScore` **(dump 中无)** | 56 | 0 | — |  |
| `Character` **(dump 中无)** | 57 | 0 | — |  |
| `IdolCard` **(dump 中无)** | 58 | 0 | — |  |
| `IdolCardExamEffectType` **(dump 中无)** | 59 | 0 | — |  |
| `LatestAuditionRank` **(dump 中无)** | 60 | 0 | — |  |
| `LatestAuditionReachForceEndScore` **(dump 中无)** | 61 | 0 | — |  |
| `LatestAuditionBaseScorePermil` **(dump 中无)** | 62 | 0 | — |  |
| `LatestAuditionExamSkipCount` **(dump 中无)** | 63 | 0 | — |  |
| `Result` **(dump 中无)** | 64 | 0 | — |  |
| `NextAuditionEasyBaseVocalPermil` **(dump 中无)** | 65 | 0 | — |  |
| `NextAuditionEasyBaseDancePermil` **(dump 中无)** | 66 | 0 | — |  |
| `NextAuditionEasyBaseVisualPermil` **(dump 中无)** | 67 | 0 | — |  |
| `ProduceCardGet` **(dump 中无)** | 68 | 0 | — |  |
| `ProduceDrinkGet` **(dump 中无)** | 69 | 0 | — |  |
| `ProduceItemGet` **(dump 中无)** | 70 | 0 | — |  |
| `ProduceCardUseCount` **(dump 中无)** | 71 | 0 | — |  |
| `ProduceDrinkUseCount` **(dump 中无)** | 72 | 0 | — |  |
| `ProduceItemUseCount` **(dump 中无)** | 73 | 0 | — |  |
| `ExamTriggerCount` **(dump 中无)** | 74 | 0 | — |  |
| `LessonExamTriggerCount` **(dump 中无)** | 75 | 0 | — |  |
| `AuditionExamTriggerCount` **(dump 中无)** | 76 | 0 | — |  |
| `IdolCardProducePlanType` **(dump 中无)** | 77 | 0 | — |  |
| `VoteCount` **(dump 中无)** | 78 | 0 | — |  |
| `LatestAuditionStepSelectNumber` **(dump 中无)** | 79 | 0 | — |  |
| `CurrentAuditionStepType` **(dump 中无)** | 80 | 0 | — |  |
| `CurrentAuditionStepSelectNumber` **(dump 中无)** | 81 | 0 | — |  |
| `DearnessPoint` **(dump 中无)** | 82 | 0 | — |  |
| `Star` **(dump 中无)** | 83 | 0 | — |  |
| `Set` **(dump 中无)** | 998 | 0 | — |  |
| `NegativeSet` **(dump 中无)** | 999 | 0 | — |  |

### ProduceDisplayType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Itself` **(dump 中无)** | 1 | 0 | — |  |
| `Choice` **(dump 中无)** | 2 | 0 | — |  |

### ProduceEventSuggestionType（proto 定义 3 个值；dump 中出现 1 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Primary` | 1 | 6888 | ProduceStepEventDetail.suggestionType=6888 |  |
| `Secondary` **(dump 中无)** | 2 | 0 | — |  |

### ProduceExamResultType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Success` **(dump 中无)** | 1 | 0 | — |  |
| `Normal` **(dump 中无)** | 2 | 0 | — |  |
| `Failed` **(dump 中无)** | 3 | 0 | — |  |

### ProduceHighScoreEventType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Normal` | 1 | 4 | ProduceHighScore.produceHighScoreEventType=4 |  |
| `Rush` | 2 | 15 | ProduceHighScore.produceHighScoreEventType=15 |  |

### ProduceProgressAuditionStatusType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ReadyForExamBattle` **(dump 中无)** | 1 | 0 | — |  |
| `InProgressExamBattle` **(dump 中无)** | 2 | 0 | — |  |
| `ExamBattleSuccess` **(dump 中无)** | 3 | 0 | — |  |
| `ExamBattleFailure` **(dump 中无)** | 4 | 0 | — |  |

### ProduceProgressConditionType（proto 定义 12 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `StaminaRatio` **(dump 中无)** | 1 | 0 | — |  |
| `StaminaFix` **(dump 中无)** | 2 | 0 | — |  |
| `ProducePoint` **(dump 中无)** | 3 | 0 | — |  |
| `ProduceItemCount` **(dump 中无)** | 4 | 0 | — |  |
| `ProduceDrinkCount` **(dump 中无)** | 5 | 0 | — |  |
| `ProduceCardCount` **(dump 中无)** | 6 | 0 | — |  |
| `Vocal` **(dump 中无)** | 7 | 0 | — |  |
| `Dance` **(dump 中无)** | 8 | 0 | — |  |
| `Visual` **(dump 中无)** | 9 | 0 | — |  |
| `StepNumber` **(dump 中无)** | 10 | 0 | — |  |
| `ProduceCardSearchCount` **(dump 中无)** | 11 | 0 | — |  |

### ProduceProgressStatus（proto 定义 28 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `OpeningAdv` **(dump 中无)** | 1 | 0 | — |  |
| `OpeningCharacterDearnessStory` **(dump 中无)** | 2 | 0 | — |  |
| `CharacterEventOpening` **(dump 中无)** | 3 | 0 | — |  |
| `SelectNextStep` **(dump 中无)** | 4 | 0 | — |  |
| `BeforeAuditionRefresh` **(dump 中无)** | 5 | 0 | — |  |
| `BeforeStepCharacterEvent` **(dump 中无)** | 6 | 0 | — |  |
| `BeforeStepSupportCardEvent` **(dump 中无)** | 7 | 0 | — |  |
| `StepAction` **(dump 中无)** | 8 | 0 | — |  |
| `AfterStepAuditionCharacterEvent` **(dump 中无)** | 9 | 0 | — |  |
| `AfterStepCharacterGrowthEvent` **(dump 中无)** | 10 | 0 | — |  |
| `AfterStepCharacterDearnessStory` **(dump 中无)** | 11 | 0 | — |  |
| `AfterStepIdolCardEvent` **(dump 中无)** | 12 | 0 | — |  |
| `AfterStepSupportCardEvent` **(dump 中无)** | 13 | 0 | — |  |
| `AfterStepCharacterEvent` **(dump 中无)** | 14 | 0 | — |  |
| `StartBeforeLiveEvaluation` **(dump 中无)** | 15 | 0 | — |  |
| `EndBeforeLiveEvaluation` **(dump 中无)** | 16 | 0 | — |  |
| `IdolCardEvent` **(dump 中无)** | 17 | 0 | — |  |
| `CharacterEventFailure` **(dump 中无)** | 18 | 0 | — |  |
| `CharacterEventEnding` **(dump 中无)** | 19 | 0 | — |  |
| `BeforeStepCampaignEvent` **(dump 中无)** | 20 | 0 | — |  |
| `AfterStepCampaignEvent` **(dump 中无)** | 21 | 0 | — |  |
| `End` **(dump 中无)** | 30 | 0 | — |  |
| `Result` **(dump 中无)** | 31 | 0 | — |  |
| `GuildMission` **(dump 中无)** | 32 | 0 | — |  |
| `EndingCharacterDearnessStory` **(dump 中无)** | 33 | 0 | — |  |
| `DearnessBoost` **(dump 中无)** | 34 | 0 | — |  |
| `Finished` **(dump 中无)** | 99 | 0 | — |  |

### ProduceResourceOriginType（proto 定义 15 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Produce` **(dump 中无)** | 1 | 0 | — |  |
| `IdolCard` **(dump 中无)** | 2 | 0 | — |  |
| `SupportCard` **(dump 中无)** | 3 | 0 | — |  |
| `MemoryAbility` **(dump 中无)** | 4 | 0 | — |  |
| `ProduceCard` **(dump 中无)** | 5 | 0 | — |  |
| `ProduceItem` **(dump 中无)** | 6 | 0 | — |  |
| `ProduceCustomizeItem` **(dump 中无)** | 7 | 0 | — |  |
| `Character` **(dump 中无)** | 8 | 0 | — |  |
| `StepAudition` **(dump 中无)** | 10 | 0 | — |  |
| `StepEvent` **(dump 中无)** | 11 | 0 | — |  |
| `StepPresent` **(dump 中无)** | 12 | 0 | — |  |
| `StepShop` **(dump 中无)** | 13 | 0 | — |  |
| `ExamGimmick` **(dump 中无)** | 14 | 0 | — |  |
| `StepInterval` **(dump 中无)** | 15 | 0 | — |  |

### ProduceRewardType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Probability` **(dump 中无)** | 1 | 0 | — |  |
| `Ratio` **(dump 中无)** | 2 | 0 | — |  |

### ProduceScheduleLocationType（proto 定义 16 个值；dump 中出现 15 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ProducerRoom1` | 1 | 79 | ProduceScheduleMotion.locationType=78; ProduceScheduleBackground.locationType=1 |  |
| `ProducerRoom2` | 2 | 92 | ProduceScheduleMotion.locationType=91; ProduceScheduleBackground.locationType=1 |  |
| `Classroom` | 3 | 144 | ProduceScheduleMotion.locationType=143; ProduceScheduleBackground.locationType=1 |  |
| `Rooftop` | 4 | 53 | ProduceScheduleMotion.locationType=52; ProduceScheduleBackground.locationType=1 |  |
| `Courtyard` | 5 | 53 | ProduceScheduleMotion.locationType=52; ProduceScheduleBackground.locationType=1 |  |
| `ProducerRoom3` | 6 | 53 | ProduceScheduleMotion.locationType=52; ProduceScheduleBackground.locationType=1 |  |
| `ProducerRoom4` | 7 | 92 | ProduceScheduleMotion.locationType=91; ProduceScheduleBackground.locationType=1 |  |
| `Classroom2` | 8 | 144 | ProduceScheduleMotion.locationType=143; ProduceScheduleBackground.locationType=1 |  |
| `Rooftop2` | 9 | 53 | ProduceScheduleMotion.locationType=52; ProduceScheduleBackground.locationType=1 |  |
| `Courtyard2` | 10 | 53 | ProduceScheduleMotion.locationType=52; ProduceScheduleBackground.locationType=1 |  |
| `ProducerRoom5` | 11 | 41 | ProduceScheduleMotion.locationType=40; ProduceScheduleBackground.locationType=1 |  |
| `ProducerRoom6` | 12 | 71 | ProduceScheduleMotion.locationType=70; ProduceScheduleBackground.locationType=1 |  |
| `Rooftop3` | 13 | 41 | ProduceScheduleMotion.locationType=40; ProduceScheduleBackground.locationType=1 |  |
| `Courtyard3` | 14 | 41 | ProduceScheduleMotion.locationType=40; ProduceScheduleBackground.locationType=1 |  |
| `Classroom3` | 15 | 71 | ProduceScheduleMotion.locationType=70; ProduceScheduleBackground.locationType=1 |  |

### ProduceScheduleMotionType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Wait1` | 1 | 252 | ProduceScheduleMotion.motionType=252 |  |
| `Wait2` | 2 | 65 | ProduceScheduleMotion.motionType=65 |  |
| `Reaction` | 3 | 684 | ProduceScheduleMotion.motionType=684 |  |
| `ReactionOnce` | 4 | 65 | ProduceScheduleMotion.motionType=65 |  |

### ProduceScheduleStaminaMotionType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Enough` | 1 | 798 | ProduceScheduleMotion.staminaMotionType=798 |  |
| `NotEnough` | 2 | 268 | ProduceScheduleMotion.staminaMotionType=268 |  |

### ProduceSelectScreenOrderType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `First` | 1 | 7 | Produce.produceSelectScreenOrderType=7 |  |
| `Second` | 2 | 1 | Produce.produceSelectScreenOrderType=1 |  |

### ProduceSkillEffectType（proto 定义 10 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `VocalAddition` **(dump 中无)** | 100 | 0 | — |  |
| `VocalGrowthRateAddition` **(dump 中无)** | 101 | 0 | — |  |
| `DanceAddition` **(dump 中无)** | 200 | 0 | — |  |
| `DanceGrowthRateAddition` **(dump 中无)** | 201 | 0 | — |  |
| `VisualAddition` **(dump 中无)** | 300 | 0 | — |  |
| `VisualGrowthRateAddition` **(dump 中无)** | 301 | 0 | — |  |
| `StaminaAddition` **(dump 中无)** | 500 | 0 | — |  |
| `ProduceRewardSet` **(dump 中无)** | 1000 | 0 | — |  |
| `ProduceEffect` **(dump 中无)** | 1001 | 0 | — |  |

### ProduceStartMotionType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Reaction` | 1 | 26 | ProduceStartMotion.motionType=26 |  |
| `Wait` | 2 | 13 | ProduceStartMotion.motionType=13 |  |

### ProduceStepAuditionMotionType（proto 定义 7 个值；dump 中出现 6 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Start` | 1 | 125 | ProduceStepAuditionMotion.motionType=115; ProduceStepAuditionCharacterUnitMotion.motionType=10 |  |
| `Result1` | 2 | 315 | ProduceStepAuditionMotion.motionType=295; ProduceStepAuditionCharacterUnitMotion.motionType=20 |  |
| `Result2` | 3 | 176 | ProduceStepAuditionMotion.motionType=164; ProduceStepAuditionCharacterUnitMotion.motionType=12 |  |
| `Result3` | 4 | 176 | ProduceStepAuditionMotion.motionType=164; ProduceStepAuditionCharacterUnitMotion.motionType=12 |  |
| `Failure` | 5 | 128 | ProduceStepAuditionMotion.motionType=118; ProduceStepAuditionCharacterUnitMotion.motionType=10 |  |
| `PreResult` | 6 | 14 | ProduceStepAuditionMotion.motionType=10; ProduceStepAuditionCharacterUnitMotion.motionType=2; ProduceStepAuditionRivalActorMotion.motionType=2 |  |

### ProduceStepFanPresentMotionType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Reaction` | 1 | 26 | ProduceStepFanPresentMotion.motionType=26 |  |
| `Wait` | 2 | 13 | ProduceStepFanPresentMotion.motionType=13 |  |

### ProduceStoryType（proto 定义 10 个值；dump 中出现 8 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 453 | ProduceStory.type=453 |  |
| `Dearness` **(dump 中无)** | 1 | 0 | — |  |
| `Character` | 2 | 686 | ProduceStory.type=686 |  |
| `CharacterGrowth` | 3 | 39 | ProduceStory.type=39 |  |
| `IdolCard` | 4 | 339 | ProduceStory.type=339 |  |
| `SupportCard` | 5 | 511 | ProduceStory.type=511 |  |
| `StepActivityEvent` | 6 | 306 | ProduceStory.type=306 |  |
| `StepSchoolEvent` | 7 | 383 | ProduceStory.type=383 |  |
| `Campaign` **(dump 中无)** | 8 | 0 | — |  |
| `StepBusinessEvent` | 9 | 624 | ProduceStory.type=624 |  |

### ProduceTriggerOriginType（proto 定义 12 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Character` **(dump 中无)** | 1 | 0 | — |  |
| `IdolCard` **(dump 中无)** | 2 | 0 | — |  |
| `SupportCard` **(dump 中无)** | 3 | 0 | — |  |
| `Memory` **(dump 中无)** | 4 | 0 | — |  |
| `Event` **(dump 中无)** | 5 | 0 | — |  |
| `Item` **(dump 中无)** | 6 | 0 | — |  |
| `Drink` **(dump 中无)** | 7 | 0 | — |  |
| `Produce` **(dump 中无)** | 8 | 0 | — |  |
| `DearnessStory` **(dump 中无)** | 9 | 0 | — |  |
| `ProduceCustomizeItem` **(dump 中无)** | 10 | 0 | — |  |
| `ProduceGrowthPanel` **(dump 中无)** | 11 | 0 | — |  |

### ProducerRankingGrade（proto 定义 7 个值；dump 中出现 6 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Normal` | 1 | 4 | ProducerRankingRankGrade.grade=4 |  |
| `Bronze` | 2 | 4 | ProducerRankingRankGrade.grade=4 |  |
| `Silver` | 3 | 4 | ProducerRankingRankGrade.grade=4 |  |
| `Gold` | 4 | 4 | ProducerRankingRankGrade.grade=4 |  |
| `Rainbow` | 5 | 4 | ProducerRankingRankGrade.grade=4 |  |
| `RainbowPlus` | 6 | 4 | ProducerRankingRankGrade.grade=4 |  |

### ProducerRankingPointType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Produce` **(dump 中无)** | 1 | 0 | — |  |
| `Tower` **(dump 中无)** | 2 | 0 | — |  |

### PurchaseTransactionStatusType（proto 定义 7 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `None` **(dump 中无)** | 1 | 0 | — |  |
| `Initialized` **(dump 中无)** | 2 | 0 | — |  |
| `InvalidMasterData` **(dump 中无)** | 3 | 0 | — |  |
| `ChargeFailed` **(dump 中无)** | 4 | 0 | — |  |
| `ProvideBonusFailed` **(dump 中无)** | 5 | 0 | — |  |
| `Completed` **(dump 中无)** | 999 | 0 | — |  |

### PushType（proto 定义 8 个值；dump 中出现 7 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `ApFull` | 1 | 26 | CharacterPushMessage.type=26 |  |
| `MoneyFull` | 2 | 26 | CharacterPushMessage.type=26 |  |
| `DailyMission` | 3 | 13 | CharacterPushMessage.type=13 |  |
| `Login` | 4 | 13 | CharacterPushMessage.type=13 |  |
| `PvpRateRemainingPlayCount` | 5 | 13 | CharacterPushMessage.type=13 |  |
| `WorkMiniLiveFinish` | 101 | 39 | CharacterPushMessage.type=39 |  |
| `WorkLiveStreamingFinish` | 102 | 39 | CharacterPushMessage.type=39 |  |

### PvpRateGrade（proto 定义 9 个值；dump 中出现 8 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` | 1 | 1 | PvpRateUnitSlotUnlock.grade=1 |  |
| `_2` | 2 | 1 | PvpRateUnitSlotUnlock.grade=1 |  |
| `_3` | 3 | 1 | PvpRateUnitSlotUnlock.grade=1 |  |
| `_4` | 4 | 1 | PvpRateUnitSlotUnlock.grade=1 |  |
| `_5` | 5 | 1 | PvpRateUnitSlotUnlock.grade=1 |  |
| `_6` | 6 | 1 | PvpRateUnitSlotUnlock.grade=1 |  |
| `_7` | 7 | 1 | PvpRateUnitSlotUnlock.grade=1 |  |
| `_8` | 8 | 1 | PvpRateUnitSlotUnlock.grade=1 |  |

### PvpRateMotionType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Win` | 1 | 26 | PvpRateMotion.motionType=26 |  |
| `Lose` | 2 | 26 | PvpRateMotion.motionType=26 |  |

### PvpRatePhaseType（proto 定义 6 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `MatchedRivals` **(dump 中无)** | 1 | 0 | — |  |
| `BeforeFirstStage` **(dump 中无)** | 2 | 0 | — |  |
| `BeforeSecondStage` **(dump 中无)** | 3 | 0 | — |  |
| `BeforeThirdStage` **(dump 中无)** | 4 | 0 | — |  |
| `Result` **(dump 中无)** | 5 | 0 | — |  |

### PvpRateRivalType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `High` **(dump 中无)** | 1 | 0 | — |  |
| `Middle` **(dump 中无)** | 2 | 0 | — |  |
| `Low` **(dump 中无)** | 3 | 0 | — |  |

### PvpRateSeasonStatusType（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `OutOfTerm` **(dump 中无)** | 1 | 0 | — |  |
| `PrepareStartTerm` **(dump 中无)** | 2 | 0 | — |  |
| `NotAttended` **(dump 中无)** | 3 | 0 | — |  |
| `InTerm` **(dump 中无)** | 4 | 0 | — |  |

### PvpRateStageType（proto 定义 4 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `_1` | 1 | 102 | PvpRateConfig.stages=51; PvpRateConfig.stages.stageType=51 |  |
| `_2` | 2 | 102 | PvpRateConfig.stages=51; PvpRateConfig.stages.stageType=51 |  |
| `_3` | 3 | 102 | PvpRateConfig.stages=51; PvpRateConfig.stages.stageType=51 |  |

### ResetTimingType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Daily` | 1 | 4 | MissionPoint.resetTimingType=3; ShopItem.resetTimingType=1 |  |
| `Weekly` | 2 | 4 | ShopItem.resetTimingType=3; MissionPoint.resetTimingType=1 |  |
| `Monthly` | 3 | 3 | ShopItem.resetTimingType=3 |  |
| `Never` | 999 | 309 | ShopItem.resetTimingType=273; MissionPoint.resetTimingType=31; Shop.resetTimingType=5 |  |

### ResourceOriginType（proto 定义 4 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 231 | Costume.resourceOriginType=126; CostumeHead.resourceOriginType=105 |  |
| `IdolCard` | 1 | 176 | Costume.resourceOriginType=100; CostumeHead.resourceOriginType=76 |  |
| `IdolCardSkin` | 2 | 384 | Costume.resourceOriginType=253; CostumeHead.resourceOriginType=131 |  |
| `Shop` | 3 | 149 | CostumeHead.resourceOriginType=81; Costume.resourceOriginType=68 |  |

### RewardProvideType（proto 定义 6 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `PatternA` **(dump 中无)** | 1 | 0 | — |  |
| `PatternB` **(dump 中无)** | 2 | 0 | — |  |
| `PatternC` **(dump 中无)** | 3 | 0 | — |  |
| `PatternD` **(dump 中无)** | 4 | 0 | — |  |
| `PatternE` **(dump 中无)** | 5 | 0 | — |  |

### RewardSetType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Probability` **(dump 中无)** | 1 | 0 | — |  |
| `Ratio` **(dump 中无)** | 2 | 0 | — |  |

### RuleType（proto 定义 5 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `FundSettlement` | 1 | 3 | Rule.type=3 |  |
| `CommercialTransaction` | 2 | 3 | Rule.type=3 |  |
| `Copyright` | 3 | 15 | Rule.type=15 |  |
| `PrereleaseMaintenance` | 4 | 2 | Rule.type=2 |  |

### ServingStatus（proto 定义 5 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `UnknownServing` **(dump 中无)** | 1 | 0 | — |  |
| `Serving` **(dump 中无)** | 2 | 0 | — |  |
| `NotServing` **(dump 中无)** | 3 | 0 | — |  |
| `ServiceUnknown` **(dump 中无)** | 4 | 0 | — |  |

### ShopItemLabelType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Sale` | 1 | 21 | ShopItem.labelTypes=21 |  |
| `Recommend` | 2 | 105 | ShopItem.labelTypes=105 |  |

### ShopType（proto 定义 6 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Jewel` | 1 | 1 | Shop.type=1 |  |
| `Pass` | 2 | 1 | Shop.type=1 |  |
| `Pack` | 3 | 1 | Shop.type=1 |  |
| `Costume` | 4 | 1 | Shop.type=1 |  |
| `WebStore` | 999 | 1 | Shop.type=1 |  |

### StartupNotificationDisplayType（proto 定义 11 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Home` **(dump 中无)** | 1 | 0 | — |  |
| `Shop` **(dump 中无)** | 2 | 0 | — |  |
| `StoryEvent` **(dump 中无)** | 3 | 0 | — |  |
| `ProduceHighScore` **(dump 中无)** | 4 | 0 | — |  |
| `Tower` **(dump 中无)** | 5 | 0 | — |  |
| `MissionPanel` **(dump 中无)** | 6 | 0 | — |  |
| `MissionDailyRelease` **(dump 中无)** | 7 | 0 | — |  |
| `StoryCampaign` **(dump 中无)** | 8 | 0 | — |  |
| `ProduceResult` **(dump 中无)** | 9 | 0 | — |  |
| `GvgRaid` **(dump 中无)** | 10 | 0 | — |  |

### StartupNotificationEffectType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Confetti1` **(dump 中无)** | 1 | 0 | — |  |
| `Confetti2` **(dump 中无)** | 2 | 0 | — |  |
| `Twinkling1` **(dump 中无)** | 3 | 0 | — |  |

### StartupNotificationRemindType（proto 定义 6 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `CoinGasha` **(dump 中无)** | 1 | 0 | — |  |
| `Exchange` **(dump 中无)** | 2 | 0 | — |  |
| `PlayItem` **(dump 中无)** | 3 | 0 | — |  |
| `GashaPoint` **(dump 中无)** | 4 | 0 | — |  |
| `CommonLimitItem` **(dump 中无)** | 5 | 0 | — |  |

### StartupNotificationType（proto 定义 13 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Movie` **(dump 中无)** | 1 | 0 | — |  |
| `Adv` **(dump 中无)** | 2 | 0 | — |  |
| `Image` **(dump 中无)** | 3 | 0 | — |  |
| `Notice` **(dump 中无)** | 4 | 0 | — |  |
| `Shop` **(dump 中无)** | 5 | 0 | — |  |
| `ProfileReport` **(dump 中无)** | 6 | 0 | — |  |
| `FreeText` **(dump 中无)** | 7 | 0 | — |  |
| `GashaPointExpire` **(dump 中无)** | 8 | 0 | — |  |
| `ExchangeItemExpire` **(dump 中无)** | 9 | 0 | — |  |
| `CoinGashaItemExpire` **(dump 中无)** | 10 | 0 | — |  |
| `PlayItemExpire` **(dump 中无)** | 11 | 0 | — |  |
| `CommonLimitItemExpire` **(dump 中无)** | 12 | 0 | — |  |

### StoryCampaignType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Event` **(dump 中无)** | 1 | 0 | — |  |
| `DearnessStory` **(dump 中无)** | 2 | 0 | — |  |

### StoryEventMotionType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Wait` **(dump 中无)** | 1 | 0 | — |  |
| `Reaction` **(dump 中无)** | 2 | 0 | — |  |
| `ReactionOnce` **(dump 中无)** | 3 | 0 | — |  |

### StoryEventType（proto 定义 5 个值；dump 中出现 5 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 72 | StoryGroup.storyEventType=72 |  |
| `Normal` | 1 | 22 | StoryEvent.storyEventType=11; StoryGroup.storyEventType=11 |  |
| `BoxGasha` | 2 | 22 | StoryEvent.storyEventType=11; StoryGroup.storyEventType=11 |  |
| `MainStory` | 3 | 10 | StoryEvent.storyEventType=10 |  |
| `GuildMission` | 4 | 4 | StoryEvent.storyEventType=2; StoryGroup.storyEventType=2 |  |

### StoryType（proto 定义 12 个值；dump 中出现 9 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Main` | 1 | 80 | Story.type=66; StoryGroup.storyType=14 |  |
| `CampaignDearnessStory` | 2 | 10 | Story.type=10 |  |
| `Birthday` | 3 | 26 | Story.type=26 |  |
| `ExtraDearnessStory` | 4 | 12 | Story.type=11; StoryGroup.storyType=1 |  |
| `DearnessStory` | 5 | 49 | StoryGroup.storyType=49 |  |
| `AprilFool` | 6 | 14 | Story.type=11; StoryGroup.storyType=3 |  |
| `Tour` | 7 | 23 | Story.type=19; StoryGroup.storyType=4 |  |
| `StoryEvent` | 9 | 144 | Story.type=120; StoryGroup.storyType=24 |  |
| `GvgRaid` | 10 | 6 | Story.type=5; StoryGroup.storyType=1 |  |
| `ProduceHighScore` **(dump 中无)** | 11 | 0 | — |  |
| `Other` **(dump 中无)** | 99 | 0 | — |  |

### TermsType（proto 定义 4 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `TermsOfService` | 1 | 1 | Terms.type=1 |  |
| `PrivacyPolicy` | 2 | 1 | Terms.type=1 |  |
| `GlobalConsent` | 3 | 1 | Terms.type=1 |  |

### TimeType（proto 定义 10 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `LastLoginTime` **(dump 中无)** | 1 | 0 | — |  |
| `WorkLastInitializedTime` **(dump 中无)** | 2 | 0 | — |  |
| `NoticeInfoViewedTime` **(dump 中无)** | 3 | 0 | — |  |
| `NoticeBugViewedTime` **(dump 中无)** | 4 | 0 | — |  |
| `NoticePrviewedTime` **(dump 中无)** | 5 | 0 | — |  |
| `LastFriendCoinReceiveTime` **(dump 中无)** | 6 | 0 | — |  |
| `GuildJoinableTime` **(dump 中无)** | 10 | 0 | — |  |
| `GuildEstablishableTime` **(dump 中无)** | 11 | 0 | — |  |
| `GuildDonationRequestableTime` **(dump 中无)** | 12 | 0 | — |  |

### TipsType（proto 定义 6 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `CharacterDetail` **(dump 中无)** | 1 | 0 | — |  |
| `CharacterGossip` **(dump 中无)** | 2 | 0 | — |  |
| `World` | 3 | 1 | Tips.type=1 |  |
| `Help` | 4 | 6 | Tips.type=6 |  |
| `Comic` | 5 | 23 | Tips.type=23 |  |

### TourProgressPhaseType（proto 定义 3 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Progress` **(dump 中无)** | 1 | 0 | — |  |
| `ExamEnd` **(dump 中无)** | 2 | 0 | — |  |

### TourScoreGrade（proto 定义 14 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `F` **(dump 中无)** | 1 | 0 | — |  |
| `E` **(dump 中无)** | 2 | 0 | — |  |
| `D` **(dump 中无)** | 3 | 0 | — |  |
| `C` **(dump 中无)** | 4 | 0 | — |  |
| `CPlus` **(dump 中无)** | 5 | 0 | — |  |
| `B` **(dump 中无)** | 6 | 0 | — |  |
| `BPlus` **(dump 中无)** | 7 | 0 | — |  |
| `A` **(dump 中无)** | 8 | 0 | — |  |
| `APlus` **(dump 中无)** | 9 | 0 | — |  |
| `S` **(dump 中无)** | 10 | 0 | — |  |
| `SPlus` **(dump 中无)** | 11 | 0 | — |  |
| `Ss` **(dump 中无)** | 12 | 0 | — |  |
| `SsPlus` **(dump 中无)** | 13 | 0 | — |  |

### TourStageIconSizeType（proto 定义 4 个值；dump 中出现 0 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Small` **(dump 中无)** | 1 | 0 | — |  |
| `Medium` **(dump 中无)** | 2 | 0 | — |  |
| `Large` **(dump 中无)** | 3 | 0 | — |  |

### TutorialCharacterVoiceType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Select` | 1 | 3 | TutorialCharacterVoice.type=3 |  |
| `Random` | 2 | 18 | TutorialCharacterVoice.type=18 |  |

### TutorialNavigationPositionType（proto 定义 6 个值；dump 中出现 4 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 162 | Tutorial.navigationPositionType=162 |  |
| `Top` | 1 | 3 | Tutorial.navigationPositionType=3 |  |
| `Upper` | 2 | 48 | Tutorial.navigationPositionType=48 |  |
| `Middle` **(dump 中无)** | 3 | 0 | — |  |
| `Lower` | 4 | 3 | Tutorial.navigationPositionType=3 |  |
| `Bottom` **(dump 中无)** | 5 | 0 | — |  |

### TutorialNavigationType（proto 定义 6 个值；dump 中出现 6 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 8 | Tutorial.navigationType=8 |  |
| `Tips` | 1 | 96 | Tutorial.navigationType=96 |  |
| `Arrow` | 2 | 41 | Tutorial.navigationType=41 |  |
| `Focus` | 3 | 55 | Tutorial.navigationType=55 |  |
| `Character` | 4 | 6 | Tutorial.navigationType=6 |  |
| `Adv` | 5 | 10 | Tutorial.navigationType=10 |  |

### TutorialProduceCommandType（proto 定义 9 个值；dump 中出现 9 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 100 | Tutorial.tutorialProduceCommandType=100 |  |
| `Start` | 1 | 1 | Tutorial.tutorialProduceCommandType=1 |  |
| `Next` | 2 | 19 | Tutorial.tutorialProduceCommandType=19 |  |
| `StepLessonEnd` | 3 | 76 | Tutorial.tutorialProduceCommandType=76 |  |
| `StepPresentReceive` | 4 | 5 | Tutorial.tutorialProduceCommandType=5 |  |
| `StepAuditionExamEnd` | 5 | 9 | Tutorial.tutorialProduceCommandType=9 |  |
| `StepAuditionEnd` | 6 | 1 | Tutorial.tutorialProduceCommandType=1 |  |
| `CheckBeforeLiveProduceEvaluation` | 7 | 1 | Tutorial.tutorialProduceCommandType=1 |  |
| `Result` | 8 | 4 | Tutorial.tutorialProduceCommandType=4 |  |

### TutorialType（proto 定义 90 个值；dump 中出现 78 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 300 | MainTask.unlockFeatureTutorialType=300 |  |
| `GameStart` | 1 | 137 | Tutorial.tutorialType=122; TutorialProduceStep.tutorialType=12; TutorialProduce.tutorialType=3 |  |
| `MainTask` | 2 | 1 | Tutorial.tutorialType=1 |  |
| `Work` | 3 | 3 | FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1; Tutorial.tutorialType=1 |  |
| `IdolCard` | 4 | 1 | Tutorial.tutorialType=1 |  |
| `IdolCardSkin` | 5 | 1 | Tutorial.tutorialType=1 |  |
| `PvpRate` | 6 | 9 | Tutorial.tutorialType=7; FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1 |  |
| `CoinGasha` | 7 | 3 | FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1; Tutorial.tutorialType=1 |  |
| `MoneyReceive` | 8 | 3 | FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1; Tutorial.tutorialType=1 |  |
| `MissionPass` | 9 | 1 | Tutorial.tutorialType=1 |  |
| `Profile` | 10 | 1 | Tutorial.tutorialType=1 |  |
| `Meishi` | 11 | 1 | Tutorial.tutorialType=1 |  |
| `Friend` | 12 | 1 | Tutorial.tutorialType=1 |  |
| `Achievement` | 14 | 1 | Tutorial.tutorialType=1 |  |
| `IdolCardLevelLimitRankUpdate` | 15 | 3 | FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1; Tutorial.tutorialType=1 |  |
| `SupportCardLevelUpdate` | 16 | 3 | FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1; Tutorial.tutorialType=1 |  |
| `ItemExchange` **(dump 中无)** | 17 | 0 | — |  |
| `DailyExchange` | 18 | 2 | FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1 |  |
| `Tower` | 19 | 2 | FeatureLock.tutorialType=1; Tutorial.tutorialType=1 |  |
| `Guild` | 20 | 3 | FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1; Tutorial.tutorialType=1 |  |
| `TutorialReceiveIdolCard` | 21 | 1 | Tutorial.tutorialType=1 |  |
| `PhotoTop` | 22 | 1 | Tutorial.tutorialType=1 |  |
| `PhotoIdol` | 23 | 1 | Tutorial.tutorialType=1 |  |
| `PhotoPrepare` | 24 | 1 | Tutorial.tutorialType=1 |  |
| `Photo` | 25 | 1 | Tutorial.tutorialType=1 |  |
| `MeishiEditCustom` | 26 | 1 | Tutorial.tutorialType=1 |  |
| `MeishiEditCustomManual` | 27 | 1 | Tutorial.tutorialType=1 |  |
| `IdolCardSkinUnit` | 28 | 1 | Tutorial.tutorialType=1 |  |
| `DearnessTop` | 29 | 2 | FeatureLock.tutorialType=1; Tutorial.tutorialType=1 |  |
| `DearnessPoint` | 30 | 1 | Tutorial.tutorialType=1 |  |
| `PrimaStella` | 31 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceIdolCardSelect` | 100 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceSupportCardSelect` | 101 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceMemorySelect` | 102 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceSchedule` | 103 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceEvent` | 104 | 1 | Tutorial.tutorialType=1 |  |
| `ProducePresentStep` | 105 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceShopStep` | 106 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceExamGimmick` | 107 | 3 | Tutorial.tutorialType=3 |  |
| `ProduceExamPerfect` | 108 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceBeforeLiveEvaluation` | 109 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceDifficultySelect` | 110 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceCardUpgrade` | 111 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceCardDelete` | 112 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceDrink` **(dump 中无)** | 113 | 0 | — |  |
| `ProduceCardUpgradeBySupportCard` **(dump 中无)** | 114 | 0 | — |  |
| `ProduceExamBattle` **(dump 中无)** | 115 | 0 | — |  |
| `ProduceSupportCardEvent` **(dump 中无)** | 116 | 0 | — |  |
| `ProduceStepLessonHardBonus` **(dump 中无)** | 117 | 0 | — |  |
| `ProduceStepLessonPresent` **(dump 中无)** | 118 | 0 | — |  |
| `ProduceBeforeAuditionRefresh` **(dump 中无)** | 119 | 0 | — |  |
| `ProduceBeforeLessonHard` **(dump 中无)** | 120 | 0 | — |  |
| `ProduceChallenge` | 121 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceNextIdolAuditionTop` | 122 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceNextIdolAuditionSchedule` | 123 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceNextIdolAuditionStepAuditionSelect` | 124 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceNextIdolAuditionStepAuditionStart` | 125 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceNextIdolAuditionResult` | 126 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceStepBusiness` | 127 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceStepCustomize` | 128 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceStepFanPresent` | 129 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceLegendTop` | 130 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceHatsuboshiIdolFestivalTop` | 131 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceHatsuboshiIdolFestivalFinalTop` | 132 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceHatsuboshiIdolFestivalSelectionSchedule` | 133 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceHatsuboshiIdolFestivalFinalSchedule` | 134 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceGrowthPanelTop` | 135 | 8 | Tutorial.tutorialType=8 |  |
| `ProduceCustomizeItemCustomizeEffect` | 136 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceStepOpenLesson` | 137 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceHatsuboshiIdolFestivalStepSchool` | 138 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceHatsuboshiIdolFestivalFinalStepAuditionMid1` | 139 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceStepInterval` **(dump 中无)** | 140 | 0 | — |  |
| `ProduceSelectionMemoryCreate` | 141 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceSelectionMemorySelect` | 142 | 1 | Tutorial.tutorialType=1 |  |
| `MissionPanel` | 200 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceHighScore` | 201 | 1 | Tutorial.tutorialType=1 |  |
| `StoryEvent` | 202 | 1 | Tutorial.tutorialType=1 |  |
| `StoryEventMainStroy` | 203 | 1 | Tutorial.tutorialType=1 |  |
| `StoryEventBoxGasha` | 204 | 1 | Tutorial.tutorialType=1 |  |
| `StoryEventGuildMission` | 205 | 1 | Tutorial.tutorialType=1 |  |
| `GvgRaid` | 206 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceNextIdolAuditionMaster` | 207 | 1 | Tutorial.tutorialType=1 |  |
| `ProduceNextIdolAuditionMasterRanking` | 208 | 1 | Tutorial.tutorialType=1 |  |
| `Tour` | 209 | 1 | Tutorial.tutorialType=1 |  |
| `Research` | 210 | 1 | Tutorial.tutorialType=1 |  |
| `ProducerRanking` | 211 | 3 | FeatureLock.tutorialType=1; MainTask.unlockFeatureTutorialType=1; Tutorial.tutorialType=1 |  |
| `ProduceCardConvert` | 212 | 2 | FeatureLock.tutorialType=1; Tutorial.tutorialType=1 |  |
| `Competition` **(dump 中无)** | 213 | 0 | — |  |
| `CompetitionPreOpen` | 214 | 1 | Tutorial.tutorialType=1 |  |
| `Badge` **(dump 中无)** | 215 | 0 | — |  |

### ViewAreaType（proto 定义 3 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 23 | Tips.viewAreaType=23 |  |
| `Produce` | 1 | 1 | Tips.viewAreaType=1 |  |
| `OutGame` | 2 | 6 | Tips.viewAreaType=6 |  |

### VoicePlayScreenType（proto 定义 5 个值；dump 中出现 3 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `Home` | 1 | 689 | VoiceRoster.type=689 |  |
| `Produce` | 2 | 829 | VoiceRoster.type=829 |  |
| `Other` | 3 | 397 | VoiceRoster.type=397 |  |
| `IdolCard` **(dump 中无)** | 4 | 0 | — |  |

### Weekday（proto 定义 8 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` | 0 | 282 | ShopItem.resetWeekday=277; Shop.resetWeekday=5 |  |
| `Sunday` **(dump 中无)** | 1 | 0 | — |  |
| `Monday` | 2 | 3 | ShopItem.resetWeekday=3 |  |
| `Tuesday` **(dump 中无)** | 3 | 0 | — |  |
| `Wednesday` **(dump 中无)** | 4 | 0 | — |  |
| `Thursday` **(dump 中无)** | 5 | 0 | — |  |
| `Friday` **(dump 中无)** | 6 | 0 | — |  |
| `Saturday` **(dump 中无)** | 7 | 0 | — |  |

### WorkMotionType（proto 定义 7 个值；dump 中出现 6 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `CharacterSelectWait` | 1 | 13 | WorkMotion.motionType=13 |  |
| `CharacterSelectReaction` | 2 | 13 | WorkMotion.motionType=13 |  |
| `StartNormal` | 3 | 13 | WorkMotion.motionType=13 |  |
| `StartFine` | 4 | 13 | WorkMotion.motionType=13 |  |
| `FinishNormal` | 5 | 13 | WorkMotion.motionType=13 |  |
| `FinishExcellent` | 6 | 13 | WorkMotion.motionType=13 |  |

### WorkType（proto 定义 3 个值；dump 中出现 2 个）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `Unknown` **(dump 中无)** | 0 | 0 | — |  |
| `MiniLive` | 1 | 1384 | WorkLevelReward.type=1368; WorkLevel.type=12; WorkTime.type=3; Work.type=1 |  |
| `LiveStreaming` | 2 | 1384 | WorkLevelReward.type=1368; WorkLevel.type=12; WorkTime.type=3; Work.type=1 |  |

### Convert（dump 中出现，proto 未定义 — 可能是 id 噪声）

| 值 | proto# | dump 出现次数 | 出现字段（前 4） | 含义 |
|---|---|---|---|---|
| `002` **(不在 proto 中)** |  | 1538 | ProduceItem.produceDescriptions=620; ProduceExamEffect.produceDescriptions=441; ProduceExamGimmickEffectGroup.produceDescriptions=140; ProduceCard.produceDescriptions=123 |  |
| `ConditionThreshold` **(不在 proto 中)** |  | 61 | ProduceExamGimmickEffectGroup.produceDescriptions=48; ProduceCard.produceDescriptions=4; ProduceExamTrigger.produceDescriptions=3; ProduceExamTrigger.playProduceDescriptions=3 |  |
| `ConditionThreshold_NotClear` **(不在 proto 中)** |  | 55 | ProduceExamGimmickEffectGroup.produceDescriptions=52; ProduceExamTrigger.produceDescriptions=1; ProduceExamTrigger.playProduceDescriptions=1; ProduceExamTrigger.playEffectProduceDescriptions=1 |  |
| `ConditionThreshold_Value_100` **(不在 proto 中)** |  | 3 | ProduceExamGimmickEffectGroup.produceDescriptions=3 |  |
| `ConditionThreshold_Value_1000` **(不在 proto 中)** |  | 15 | ProduceExamGimmickEffectGroup.produceDescriptions=8; ProduceCard.produceDescriptions=4; ProduceExamTrigger.produceDescriptions=1; ProduceExamTrigger.playProduceDescriptions=1 |  |
| `ConditionThreshold_Value_300` **(不在 proto 中)** |  | 17 | ProduceExamGimmickEffectGroup.produceDescriptions=17 |  |
| `ConditionThreshold_Value_500` **(不在 proto 中)** |  | 26 | ProduceExamGimmickEffectGroup.produceDescriptions=20; ProduceExamTrigger.produceDescriptions=2; ProduceExamTrigger.playProduceDescriptions=2; ProduceExamTrigger.playEffectProduceDescriptions=2 |  |
| `StepLessonType_DanceLesson` **(不在 proto 中)** |  | 77 | ProduceExamStatusEnchant.produceDescriptions=40; ProduceItem.produceDescriptions=19; ProduceExamTrigger.produceDescriptions=18 |  |
| `StepLessonType_SpLesson` **(不在 proto 中)** |  | 19 | ProduceExamStatusEnchant.produceDescriptions=12; ProduceItem.produceDescriptions=6; ProduceExamTrigger.produceDescriptions=1 |  |
| `StepLessonType_VisualLesson` **(不在 proto 中)** |  | 59 | ProduceExamStatusEnchant.produceDescriptions=27; ProduceExamTrigger.produceDescriptions=17; ProduceItem.produceDescriptions=15 |  |
| `StepLessonType_VocalLesson` **(不在 proto 中)** |  | 39 | ProduceExamStatusEnchant.produceDescriptions=21; ProduceItem.produceDescriptions=11; ProduceExamTrigger.produceDescriptions=7 |  |

## 4. H.I.F / プリマステラ / festival 相关出现位置（grep）

| 表.字段 | 命中数 | 示例 |
|---|---|---|
| ProduceExamStatusEnchant.produceDescriptions | 1309 | e_trigger-exam_start_exam-for_hif_final_customize_item |
| ProduceSkill.produceDescriptions | 1289 | e_effect-exam_status_enchant-01-inf-enchant-p_ef-hif_memory-p_card-01-men-1_034-enc01 |
| ProduceExamEffect.produceDescriptions | 1279 | e_effect-exam_status_enchant-01-inf-enchant-p_ef-hif_memory-p_card-01-act-1_020-enc01 |
| ProduceExamEffect.produceDescriptions.originProduceExamEffectId | 1279 | e_effect-exam_status_enchant-01-inf-enchant-p_ef-hif_memory-p_card-01-act-1_020-enc01 |
| ProduceExamEffect.customizeProduceDescriptions | 1174 | e_effect-exam_status_enchant-01-inf-enchant-p_ef-hif_memory-p_card-01-act-1_020-enc01 |
| ProduceExamEffect.customizeProduceDescriptions.originProduceExamEffectId | 1174 | e_effect-exam_status_enchant-01-inf-enchant-p_ef-hif_memory-p_card-01-act-1_020-enc01 |
| ProduceSkill.produceDescriptions.originProduceExamEffectId | 1174 | e_effect-exam_status_enchant-01-inf-enchant-p_ef-hif_memory-p_card-01-men-1_034-enc01 |
| ProduceExamStatusEnchant.produceDescriptions.originProduceExamEffectId | 1069 | e_effect-exam_status_enchant-02-inf-enchant-p_ef-hif_memory-p_card-01-act-1_001-enc01 |
| ProduceExamStatusEnchant.produceDescriptions.originProduceExamTriggerId | 240 | e_trigger-exam_start_exam-for_hif_final_customize_item |
| ProduceExamTrigger.produceDescriptions | 213 | e_trigger-exam_card_play_after-p_card_search-target-p_card-01-act-1_001-for_hif_memory-0_1 |
| ProduceExamTrigger.produceDescriptions.originProduceExamTriggerId | 213 | e_trigger-exam_card_play_after-p_card_search-target-p_card-01-act-1_001-for_hif_memory-0_1 |
| ProduceExamStatusEnchant.id | 210 | enchant-p_ef-hif_memory-p_card-01-act-1_001-enc01 |
| ProduceCustomizeItem.produceDescriptions | 180 | e_trigger-exam_start_exam-for_hif_selection_customize_item |
| ProduceCustomizeItem.produceDescriptions.originProduceExamTriggerId | 180 | e_trigger-exam_start_exam-for_hif_selection_customize_item |
| ProduceExamStatusEnchant.produceExamTriggerId | 129 | e_trigger-exam_start_exam-for_hif_final_customize_item |
| ProduceSkill.id | 115 | p_memory_skill-common-hatsuboshi_idol_festival-p_trigger-start_audition-for_hif_memory-exam_status_e |
| ProduceSkill.produceType | 115 | ProduceType_HatsuboshiIdolFestival |
| ProduceSkill.produceDescriptions.targetId | 115 | Label_ProduceType_HatsuboshiIdolFestival |
| ProduceExamTrigger.id | 108 | e_trigger-exam_card_play_after-p_card_search-target-p_card-01-act-1_001-for_hif_memory-0_1 |
| ProduceExamTrigger.playProduceDescriptions | 108 | e_trigger-exam_card_play_after-p_card_search-target-p_card-01-act-1_001-for_hif_memory-0_1 |
| ProduceExamTrigger.playProduceDescriptions.originProduceExamTriggerId | 108 | e_trigger-exam_card_play_after-p_card_search-target-p_card-01-act-1_001-for_hif_memory-0_1 |
| ProduceExamTrigger.playEffectProduceDescriptions | 108 | e_trigger-exam_card_play_after-p_card_search-target-p_card-01-act-1_001-for_hif_memory-0_1 |
| ProduceExamTrigger.playEffectProduceDescriptions.originProduceExamTriggerId | 108 | e_trigger-exam_card_play_after-p_card_search-target-p_card-01-act-1_001-for_hif_memory-0_1 |
| ProduceEffect.id | 106 | p_effect-exam_status_enchant-enchant-p_ef-hif_memory-p_card-01-act-1_001-enc02 |
| MemoryAbility.id | 105 | memory_ability-p_memory_skill-common-hatsuboshi_idol_festival-p_trigger-start_audition-for_hif_memor |
| MemoryAbility.skillId | 105 | p_memory_skill-common-hatsuboshi_idol_festival-p_trigger-start_audition-for_hif_memory-exam_status_e |
| ProduceCardSearch.id | 105 | p_card_search-target-p_card-01-act-1_001-for_hif_memory |
| ProduceEffect.produceExamStatusEnchantId | 105 | enchant-p_ef-hif_memory-p_card-01-act-1_001-enc02 |
| ProduceExamEffect.id | 105 | e_effect-exam_status_enchant-01-inf-enchant-p_ef-hif_memory-p_card-01-act-1_020-enc01 |
| ProduceExamEffect.produceExamStatusEnchantId | 105 | enchant-p_ef-hif_memory-p_card-01-act-1_020-enc01 |
| ProduceExamStatusEnchant.produceExamEffectIds | 105 | e_effect-exam_status_enchant-02-inf-enchant-p_ef-hif_memory-p_card-01-act-1_001-enc01 |
| ProduceExamTrigger.produceCardSearchId | 105 | p_card_search-target-p_card-01-act-1_001-for_hif_memory |
| ProduceSkill.produceEffectId1 | 105 | p_effect-exam_status_enchant-enchant-p_ef-hif_memory-p_card-01-men-1_034-enc02 |
| ProduceSkill.produceTriggerId1 | 105 | p_trigger-start_audition-for_hif_memory |
| ProduceStepAuditionMotion.bodyAssetId | 103 | mot_aud_chr_cmmn_cmmn-hif-final01-start-c-001_in |
| ProduceStepAuditionMotion.cameraId | 103 | mot_aud_cmmn-hif-final01-start-c-001_in_cam |
| ProduceGrowthPanel.id | 50 | produce_growth_panel_sheet-hif-01 |
| ProduceGrowthPanel.produceGrowthPanelSheetId | 50 | produce_growth_panel_sheet-hif |
| MissionProgress.missionId | 42 | mission-daily_mission_HIF_clear-mission_11 |
| MissionProgress.rewards | 42 | item-produce-produce_growth_panel_sheet_point-hif |
| MissionProgress.rewards.resourceId | 42 | item-produce-produce_growth_panel_sheet_point-hif |
| ProduceExamBattleNpcGroup.produceExamBattleNpcMobId | 30 | npc_hif_border |
| ProduceSplitAdv.produceType | 24 | ProduceType_HatsuboshiIdolFestival |
| ConditionSet.id | 23 | cd_close-hif |
| Mission.id | 21 | mission-daily_mission_HIF_clear-mission_11 |
| Mission.missionGroupId | 21 | mission-group-mission_HIF_clear_1 |
| MissionGroup.missionIds | 21 | mission-daily_mission_HIF_clear-mission_11 |
| AchievementProgress.rewards | 20 | item-primastellamaterial-idol_amao-001 |
| AchievementProgress.rewards.resourceId | 20 | item-primastellamaterial-idol_amao-001 |
| ConsumptionSet.id | 20 | cs-idol_card_prima_stella-i_card-amao-3-015 |
| ConsumptionSet.resourceId | 20 | item-primastellamaterial-common-001 |
| ExamMotion.bodyMotionId | 20 | mot_aud_chr_cmmn_cmmn-hif-final01-idle-c-001_lp |
| ExamMotion.cameraId | 20 | mot_aud_cmmn-hif-final01-idle-c-001_lp_cam |
| ProduceStepAuditionCharacterUnitMotion.bodyAssetId | 16 | mot_aud_chr_ssmk_unit-hif-final01-start-unit1-kllj-001_in |
| Item.id | 14 | item-gacha-coin-hif-001 |
| Item.assetId | 14 | item_gacha-coin-hif-001 |
| ProduceItem.produceDescriptions | 12 | e_trigger-exam_start_exam-for_hif |
| ProduceItem.produceDescriptions.originProduceExamTriggerId | 12 | e_trigger-exam_start_exam-for_hif |
| HelpContent.id | 11 | idol-primastella |
| CharacterDearnessLevel.trueEndAchievementProduceType | 10 | ProduceType_HatsuboshiIdolFestival |
| CharacterTrueEndAchievement.produceType | 10 | ProduceType_HatsuboshiIdolFestival |
| CharacterTrueEndBonus.produceType | 10 | ProduceType_HatsuboshiIdolFestival |
| IdolCard.primaStellaConsumptionSetId | 10 | cs-idol_card_prima_stella-i_card-amao-3-015 |
| IdolCard.idolCardPrimaStellaProduceSkillId | 10 | prima_stella_produce_skill-i_card-amao-3-015 |
| IdolCardPrimaStellaProduceSkill.id | 10 | prima_stella_produce_skill-i_card-amao-3-015 |
| IdolCardPrimaStellaProduceSkill.produceSkillId | 10 | p_primastella_skill-common-hatsuboshi_idol_festival-final-p_trigger-produce_start-produce_reward-p_c |
| MemoryGift.id | 10 | memory_gift-20260516-hif-plan1-1 |
| MemoryGift.assetId | 10 | img_general_memory_hif-gift-001 |
| ProduceGroupLiveCommon.environmentAssetId | 10 | env_3d_live_hifstage-00-00-noon |
| ProduceStepAuditionMotion.motionSeAssetId | 10 | sud_se_produce_hif_final-002_start_C_01 |
| Localization.id | 9 | card.idol_card.prima_stella.unlock_confirm_sheet.limit_level_condition_text |
| AssetDownload.id | 7 | img_gasha_text_gasha-ticket-fes-001 |
| Tutorial.tutorialType | 7 | TutorialType_PrimaStella |
| ProduceCharacter.unlockConditionSetId | 6 | cd_close-hif |
| ProduceDescriptionSwap.id | 6 | Swap_Label_ProduceType_HatsuboshiIdolFestival |
| ConditionSet.resourceId1 | 4 | gasha-00910-2phif-fes-001 |
| ExamUnitMotion.bodyMotionId | 4 | mot_aud_chr_kllj_unit-hif-final01-idle-unit1-001_lp |
| HelpInfo.type | 4 | ProduceBeforeLiveEvaluateHif |
| HelpInfo.openHelpContentId | 4 | help-hif-produce-open-lesson |
| GashaButton.id | 3 | gasha_button-640-fes |
| ProduceDescriptionLabel.id | 3 | Label_ProduceType_HatsuboshiIdolFestival |
| ProduceDescriptionLabel.produceDescriptionSwapId | 3 | Swap_Label_ProduceType_HatsuboshiIdolFestival |
| ProduceDescriptionProduceType.produceType | 3 | ProduceType_HatsuboshiIdolFestival |
| ProduceDescriptionProduceType.template | 3 | {Label_ProduceType_HatsuboshiIdolFestival} |
| Rule.html | 3 | <div>    END OF TERMS AND CONDITIONS </div> <br> <div>    APPENDIX: How to apply the Apache License  |
| Produce.unlockConditionSetId | 2 | cd-hif_selection_produce-unlock_open |
| Produce.assetId | 2 | produce-hif-1 |
| ProduceStepAuditionRivalActorMotion.bodyAssetId | 2 | mot_aud_chr_cmmn_cmmn-hif-final02-result-score-rival-002_in |
| Tutorial.assetIds | 2 | img_tutorial_produce_03_hif-bonus-01 |
| Achievement.targetIds1 | 1 | produce_growth_panel_sheet-hif |
| Achievement.missionType | 1 | MissionType_AbsoluteIdolCardPrimaStellaCount |
| CoinGashaButton.id | 1 | coin_gasha_button-hif-001 |
| CoinGashaButton.resourceId | 1 | item-gacha-coin-hif-001 |
| HelpContent.name | 1 | Hatsuboshi IDOL FESTIVAL |
| Item.shopCoinGashaId | 1 | coin_gasha-hif-001 |
| Item.exchangeId | 1 | exchange-hif-aniv-001 |
| Item.produceGrowthPanelSheetId | 1 | produce_growth_panel_sheet-hif |
| MainStoryChapter.description | 1 | Hatsuboshi IDOL FESTIVAL |
| MainTaskIcon.missionType | 1 | MissionType_AbsoluteIdolCardPrimaStellaCount |
| Media.assetId | 1 | mov_general_media_pv_hif-2026 |
| Media.thumbnailAssetId | 1 | img_general_media_pv_hif-thumb |
| MeishiBaseAsset.id | 1 | story-bg-outschool-summer-festival-00-night |
| Mission.targetIds1 | 1 | produce_growth_panel_sheet-hif |
| Mission.type | 1 | MissionType_AbsoluteIdolCardPrimaStellaCount |
| MissionGroup.id | 1 | mission-group-mission_HIF_clear_1 |
| MissionGroup.name | 1 | HIFクリアミッション |
| MissionGroup.assetId | 1 | img_general_produce_hif-mission-banner-01 |
| ProduceExamBattleNpcMob.id | 1 | npc_hif_border |
| ProduceGroup.name | 1 | Hatsuboshi IDOL FESTIVAL |
| ProduceGroup.type | 1 | ProduceType_HatsuboshiIdolFestival |
| ProduceGroup.unlockConditionSetId | 1 | cd-hif_selection_produce-unlock_open |
| ProduceGroup.description | 1 | 『Hatsuboshi IDOL FESTIVAL』── 初星学園のトップをめぐる戦いの火蓋が切られる さぁ、目指せ！　『一番星』を！ |
| ProduceGrowthPanelSheet.id | 1 | produce_growth_panel_sheet-hif |
| ProduceGrowthPanelSheet.produceType | 1 | ProduceType_HatsuboshiIdolFestival |
| ProduceGrowthPanelSheet.unlockItemId | 1 | item-produce-produce_growth_panel_sheet_point-hif |
| ProduceGrowthPanelSheet.missionGroupId | 1 | mission-group-mission_HIF_clear_1 |
| ProduceTrigger.id | 1 | p_trigger-start_audition-for_hif_memory |

### 4.1 H.I.F 在 master 里的落点（解读）

- **剧本定义**：`ProduceGroup` produce_group-003 `ProduceType_HatsuboshiIdolFestival`（limitGrade=Sssss）；`Produce` produce-007『選抜試験』(ProduceSplitType_Selection, 20 周) 与 produce-008『本戦』(ProduceSplitType_Final, 9 周) 互为 `splitPairProduceId`；解锁条件 `cd-hif_selection_produce-unlock_open`（任一偶像亲爱度 Lv27）。`ProduceSetting` p_setting-7/8：休息回复 50%、定制 2 张、Legend 卡 1 张。
- **選抜メモリー**：`Produce.selectionMemoryEmbedProduceCardId` → `ExamContestEmbedProduceCard` exam_contest_embed_produce_card-produce_008（按流派 18 张）；`ProduceSetting.selectionMemoryNeedProduceCardCount`=1。本戦开始时通过 `ProduceSkill(p_memory_skill-common-hatsuboshi_idol_festival-…)`（`produceType=HatsuboshiIdolFestival`，触发 `p_trigger-start_audition-for_hif_memory`）把 `ProduceExamStatusEnchant enchant-p_ef-hif_memory-p_card-…` 挂到试炼里（“試験ごとに、以降1回まで、X 使用後、…”），`MemoryAbility` 有 105 条对应。
- **公開レッスン**：`ProduceStepOpenLesson`（produce_007，主/副参数 + `star` スター性）；`ProduceStepType_OpenLesson{Vocal,Dance,Visual}{Normal,Sp}{,Star}` 12 个周程类型。
- **スター性**：`ResultGradePattern` ResultGradeType_ProduceStar（E=20…S+=1200）；`ProduceEffectType_StarAddition / StarPermilUp`；`ProduceStepAuditionDifficulty.starScoreBonusBaseLine`（本戦 600/800）。
- **本戦试炼**：`ProduceStepAuditionDifficulty` produce-008 两轮（AuditionMid1 rankThreshold 3、AuditionFinal rankThreshold 1），`isStaticNpcScore=true`，NPC 组含 `npc_hif_border`（`ProduceExamBattleNpcMob.isBorder`=合格线）。
- **プリマステラ（一番星）**：`IdolCard.primaStellaConsumptionSetId/idolCardPrimaStellaProduceSkillId/primaStellaAchievementId`（10 张 SSR）→ `IdolCardPrimaStellaProduceSkill` → `ProduceSkill(p_primastella_skill-…-final-…)`：本戦开始时获得专属 Legend 卡 `p_card-0x-ido-100_0xx`（`ProduceCard.originPrimaStellaIdolCardId`）；`TutorialType_PrimaStella`；`MissionType_AbsoluteIdolCardPrimaStellaCount`。
- **育成パネル**：`ProduceGrowthPanelSheet` produce_growth_panel_sheet-hif → `ProduceGrowthPanel` 50 格（`produceSplitType` 区分 選抜/本戦 生效），点数道具 `item-produce-produce_growth_panel_sheet_point-hif`。
- **ADV/演出**：`ProduceSplitAdv`（24）、`ProduceStepTransition.produceIds=[produce-007, produce-008]`、`ProduceStepAuditionMotion` `mot_aud_*-hif-final01-*`、unit REVERSI（`ProduceCharacterUnit`）。
- **描述标签**：`Label_ProduceType_HatsuboshiIdolFestival{,_Selection,_Final}` / `Swap_…`，`ProduceDescriptionProduceType` 模板 `{Label_ProduceType_HatsuboshiIdolFestival_Final}` → “H.I.F本戦専用”。
- **未在 master 中**：フェス回合流程、投票/一番星判定公式、周程排布——需从游戏内/攻略确认。

## 5. 附录：按字段列出的枚举取值（dump 实测）

- `Achievement.category`：Idol=1148, Other=25, Produce=33
- `Achievement.missionType`：AbsoluteCharacterIdolAchievementCount=13, AbsoluteDearnessLevel=13, AbsoluteFanCount=16, AbsoluteFollowerCount=1, AbsoluteIdolCardLevelLimitRank=528, AbsoluteIdolCardPrimaStellaCount=1, AbsoluteProduceCharacterEnding=37, AbsoluteProduceGrowthPanelComplete=1, AbsoluteProducePictureBookProduceCardCount=1, AbsoluteProducePictureBookProduceDrinkCount=1, AbsoluteProducePictureBookProduceItemCount=1, AbsoluteProducerLevel=3, AbsolutePvpRateExamBattleMaxScore=3, AbsoluteTowerCharacterTotalClearRank=13, ConditionClear=11, IncrementMissionClear=3, IncrementProduceCharacterClearCount=138, IncrementProduceCharacterPlayCount=13, IncrementProduceClearCount=11, IncrementProduceConsumedStamina=5, IncrementProduceExamUseProduceCardCount=13, IncrementProduceGetProduceCardCount=1, IncrementProduceGetProduceDrinkCount=1, IncrementProduceGetProduceItemCount=1, IncrementProduceIdolCardClearCount=126, IncrementProduceIdolCardPlayCount=126, IncrementProduceLessonClearCount=28, IncrementProducePlayCount=1, IncrementProduceSelectStepCount=18, IncrementProduceShopBuyCount=5, IncrementProduceTotalAdditionExamBlock=5, IncrementProduceTotalProducePoint=1, IncrementProduceTotalScore=4, IncrementProduceUpgradeProduceCardCount=5, IncrementProduceUseProduceDrinkCount=5, IncrementProduceVoteCount=13, IncrementReceiveMoney=1, IncrementWorkDurationHour=1, ProduceConditionClearBeforeLiveEvaluation=38
- `AchievementProgress.rewards.resourceType`：Costume=13, Item=1106, JewelTotal=2076, MeishiBaseAsset=13, UserExp=1842
- `AppReview.type`：Gasha=1, MainTask=1
- `AssetDownload.type`：First=687, Second=3280
- `Badge.type`：ProducerRanking=273
- `Badge.grade`：_1=39, _2=78, _3=78, _4=39, _5=39
- `Character.personalityType`：A=2, B=3, C=5, D=4, Unknown=10
- `CharacterDearnessLevel.trueEndAchievementProduceType`：FirstStar=13, HatsuboshiIdolFestival=10, NextIdolAudition=13, Unknown=415
- `CharacterDearnessLevel.rewards.resourceType`：Costume=1, CostumeHead=2
- `CharacterDetail.type`：Age=13, Birthday=13, Birthplace=13, BloodType=13, Cv=13, DominantHand=13, Grade=13, Height=13, Hobby=13, Introduction=12, SpecialSkill=13, ThreeSize=13, Weight=13, ZodiacSign=13
- `CharacterPushMessage.type`：ApFull=26, DailyMission=13, Login=13, MoneyFull=26, PvpRateRemainingPlayCount=13, WorkLiveStreamingFinish=39, WorkMiniLiveFinish=39
- `CharacterTrueEndAchievement.produceType`：FirstStar=13, HatsuboshiIdolFestival=10, NextIdolAudition=13
- `CharacterTrueEndBonus.produceType`：FirstStar=13, HatsuboshiIdolFestival=10, NextIdolAudition=13
- `CoinGashaButton.resourceType`：Item=36
- `CompetitionExamStatusEffectIcon.planType`：Plan1=3, Plan2=2, Plan3=1
- `CompetitionExamStatusEffectIcon.examStatusEffectType`：Aggressive=1, FullPowerPoint=1, LessonBuff=1, ParameterBuff=1, ParameterBuffMultiplePerTurn=1, Review=1
- `CompetitionStageSectionLock.grade`：_1=3, _2=3, _3=3, _4=3, _5=3, _6=3, _7=3, _8=3
- `CompetitionStageSectionLock.stageType`：_1=8, _2=8, _3=8
- `CompetitionStageSectionLock.sectionTypes`：Mid=12
- `ConditionSet.conditionOperatorType`：And=4187, Or=897
- `ConditionSet.conditionType`：AchievementCompleted=50, Birthday=39, CharacterProduceClearCount=2, CharacterProducePlayCount=38, Comeback=3, Costume=87, CostumeHead=73, DearnessLevel=738, DearnessStoryFirstReadTime=10, ExchangeItemCount=560, GameStartTutorialClearHour=5, GashaDraw=21, GashaOpen=9, HomeCharacter=40, IdolCard=88, IdolCardPotentialRank=1, ItemCount=61, Login=3, MainTaskCompleted=441, MainTaskFirstThresholdClearHour=1, MissionCompleted=220, MissionDailyReleaseNotComplete=6, MissionFirstThresholdClearHour=26, MissionGroupComplete=2, MissionGroupNotComplete=1, MissionPanelNotComplete=12, Music=274, NegativeSet=267, PhotoBackground=1, ProduceClearCount=2, ProduceStoryRead=66, ProducerLevel=83, PvpRateBestGrade=29, PvpRateSeasonGrade=1, SeminarExamClear=6, Set=156, ShopItemPurchase=132, StoryRead=57, StoryUnlockKeyUse=16, SupportCard=2, TimeDuration=5, TimeTerm=1380, TimeWeekday=69, TutorialClear=1
- `ConditionSet.minMaxType`：Max=38, Min=1298, MinMax=348, Unknown=3400
- `ConsumptionSet.resourceType`：Item=803, JewelPaidOnly=4, JewelTotal=7
- `Costume.resourceOriginType`：IdolCard=100, IdolCardSkin=253, Shop=68, Unknown=126
- `Costume.invalidCostumeFeatureTypes`：Home=2, Live=17, Photography=2, Produce=17
- `CostumeHead.resourceOriginType`：IdolCard=76, IdolCardSkin=131, Shop=81, Unknown=105
- `CostumeMotion.motionType`：Finish=14, Start=14, TapReaction=56, Wait=14
- `DearnessMotion.motionType`：MultipleTaps=228, Reaction=1862, Transition=1634, Wait1=114, WaitOnce=134
- `EffectGroup.examEffectType`：ExamAddGrowEffect=1, ExamAggressiveReduce=1, ExamAntiDebuff=1, ExamBlock=1, ExamBlockRestriction=1, ExamCardDraw=1, ExamCardPlayAggressive=1, ExamCardSearchEffectPlayCountBuff=1, ExamCardUpgrade=1, ExamConcentration=1, ExamEffectTimer=1, ExamExtraTurn=1, ExamFullPower=1, ExamFullPowerPointReduce=1, ExamGimmickSlump=1, ExamHandGraveCountCardDraw=1, ExamLesson=1, ExamLessonBuff=1, ExamLessonBuffReduce=1, ExamLessonDependBlock=1, ExamLessonDependExamReview=1, ExamLessonValueMultiple=1, ExamLessonValueMultipleDown=1, ExamParameterBuff=1, ExamParameterBuffMultiplePerTurn=1, ExamParameterBuffMultiplePerTurnReduce=1, ExamParameterBuffReduce=1, ExamPlayableValueAdd=1, ExamPreservation=1, ExamReview=1, ExamReviewReduce=1, ExamStaminaConsumptionAdd=1, ExamStaminaConsumptionAddFix=1, ExamStaminaConsumptionDown=1, ExamStaminaConsumptionDownFix=1, ExamStanceReset=1, ExamStatusEnchant=1, ExamStatusEnchantEncore=1, StanceLock=1, Unknown=28
- `EffectGroup.produceEffectType`：AuditionNpcEnhance=1, BeforeAuditionRefreshStaminaDown=1, BeforeAuditionRefreshStaminaUp=1, DanceAddition=1, EventActivityProducePointDown=1, EventActivityProducePointUp=1, EventSchoolStaminaDown=1, EventSchoolStaminaUp=1, ExamTurnDown=1, ProduceCardDelete=1, ProduceCardUpgrade=1, ProducePointAddition=1, ProducePointReduceFix=1, ShopPriceDiscountMultiple=1, ShopPriceUpMultiple=1, ShopProduceCardDeletePriceDiscountMultiple=1, ShopProduceCardDeletePriceUpMultiple=1, ShopProduceCardPriceDiscountMultiple=1, ShopProduceCardPriceUpMultiple=1, ShopProduceCardUpgradePriceDiscountMultiple=1, ShopProduceCardUpgradePriceUpMultiple=1, ShopProduceDrinkPriceDiscountMultiple=1, ShopProduceDrinkPriceUpMultiple=1, StaminaRecoverFix=1, StaminaReduceFix=2, Unknown=39, VisualAddition=1, VocalAddition=1
- `EffectGroup.examEffectTypes`：ExamAddGrowEffect=1, ExamAggressiveAdditive=1, ExamAggressiveAdditiveFix=1, ExamAggressiveDependReview=1, ExamAggressivePerSearchCount=1, ExamAggressiveReduce=1, ExamAggressiveValueMultiple=1, ExamAntiDebuff=1, ExamBlock=1, ExamBlockAddMultipleAggressive=1, ExamBlockDependBlockConsumptionSum=1, ExamBlockDependExamReview=1, ExamBlockFix=1, ExamBlockPerSearchCount=1, ExamBlockPerUseCardCount=1, ExamBlockRestriction=1, ExamBlockValueMultiple=1, ExamCardDraw=1, ExamCardPlayAggressive=1, ExamCardSearchEffectPlayCountBuff=1, ExamCardUpgrade=1, ExamConcentration=1, ExamConcentrationLessonMultipleAdditive=1, ExamEffectTimer=1, ExamEnthusiasticAdditive=1, ExamEnthusiasticMultiple=1, ExamEnthusiasticTurnAdd=1, ExamExtraTurn=1, ExamFullPower=1, ExamFullPowerLessonMultipleAdditive=1, ExamFullPowerPoint=1, ExamFullPowerPointAdditive=1, ExamFullPowerPointAdditiveFix=1, ExamFullPowerPointDependFullPowerPointGetSum=1, ExamFullPowerPointPerSearchCount=1, ExamFullPowerPointReduce=1, ExamGimmickSlump=1, ExamGrowEffectLessonAddAdditive=1, ExamHandGraveCountCardDraw=1, ExamLesson=1, ExamLessonAddMultipleLessonBuff=1, ExamLessonAddMultipleParameterBuff=1, ExamLessonBuff=1, ExamLessonBuffAdditive=1, ExamLessonBuffAdditiveFix=1, ExamLessonBuffDependParameterBuff=1, ExamLessonBuffPerSearchCount=1, ExamLessonBuffReduce=1, ExamLessonDependAggressiveAndSearchCount=2, ExamLessonDependBlock=2, ExamLessonDependBlockAndSearchCount=2, ExamLessonDependBlockConsumptionSum=2, ExamLessonDependEnthusiasticGetSum=1, ExamLessonDependExamCardPlayAggressive=2, ExamLessonDependExamReview=2, ExamLessonDependParameterBuff=1, ExamLessonDependPlayCardCountSum=1, ExamLessonDependReviewAndSearchCount=2, ExamLessonDependStamina=1, ExamLessonDependStaminaConsumptionSum=1, ExamLessonFix=1, ExamLessonFullPowerPoint=1, ExamLessonPerSearchCount=1, ExamLessonValueMultiple=1, ExamLessonValueMultipleDown=1, ExamMoveGrowEffect=1, ExamMultipleConcentrationLesson=1, ExamMultipleEnthusiasticLesson=1, ExamMultipleFullPowerLesson=1, ExamMultipleLessonBuffLesson=1, ExamOverPreservation=1, ExamParameterBuff=1, ExamParameterBuffAdditive=1, ExamParameterBuffAdditiveFix=1, ExamParameterBuffDependLessonBuff=1, ExamParameterBuffMultiplePerTurn=1, ExamParameterBuffMultiplePerTurnReduce=1, ExamParameterBuffPerSearchCount=1, ExamParameterBuffReduce=1, ExamPlayableValueAdd=1, ExamPreservation=1, ExamReview=1, ExamReviewAdditive=1, ExamReviewAdditiveFix=1, ExamReviewCountAdd=1, ExamReviewDependExamBlock=1, ExamReviewDependExamCardPlayAggressive=1, ExamReviewMultiple=1, ExamReviewPerSearchCount=1, ExamReviewReduce=1, ExamReviewValueMultiple=1, ExamStaminaConsumptionAdd=1, ExamStaminaConsumptionAddFix=1, ExamStaminaConsumptionDown=1, ExamStaminaConsumptionDownFix=1, ExamStaminaDamage=2, ExamStaminaRecoverFix=1, ExamStaminaRecoverMultiple=1, ExamStaminaReduce=2, ExamStaminaReduceFix=2, ExamStanceReset=1, ExamStatusEnchant=1, ExamStatusEnchantEncore=1, StanceLock=1
- `EffectGroup.produceEffectTypes`：AuditionNpcEnhance=1, BeforeAuditionRefreshStaminaDown=1, BeforeAuditionRefreshStaminaUp=1, DanceAddition=1, EventActivityProducePointDown=1, EventActivityProducePointUp=1, EventSchoolStaminaDown=1, EventSchoolStaminaUp=1, ExamTurnDown=1, ProduceCardDelete=1, ProduceCardUpgrade=1, ProducePointAddition=1, ProducePointReduceFix=1, ShopPriceDiscountMultiple=1, ShopPriceUpMultiple=1, ShopProduceCardDeletePriceDiscountMultiple=1, ShopProduceCardDeletePriceUpMultiple=1, ShopProduceCardPriceDiscountMultiple=1, ShopProduceCardPriceUpMultiple=1, ShopProduceCardUpgradePriceDiscountMultiple=1, ShopProduceCardUpgradePriceUpMultiple=1, ShopProduceDrinkPriceDiscountMultiple=1, ShopProduceDrinkPriceUpMultiple=1, StaminaRecoverFix=1, StaminaRecoverMultiple=1, StaminaReduceFix=2, StaminaReduceMultiple=2, VisualAddition=1, VocalAddition=1
- `EventLabel.eventType`：DearnessBoost=1, GvgRaid=1, MissionDailyRelease=1, MissionPanel=1, ProduceHighScore=1, Research=1, StoryCampaign=1, StoryEvent=1, StoryEventBoxGasha=1, StoryEventGuildMission=1, StoryEventMainStory=1, Tour=1
- `ExamContestEmbedProduceCard.examEffectType`：ExamCardPlayAggressive=4, ExamConcentration=4, ExamFullPower=4, ExamLessonBuff=4, ExamParameterBuff=4, ExamReview=4
- `ExamMotion.type`：Audition=514, Contest=142, DanceLesson=234, DanceLessonHard=234, Tour=153, VisualLesson=234, VisualLessonHard=234, VocalLesson=234, VocalLessonHard=234
- `ExamMotion.motionType`：BlockAdd=302, Buff=302, Debuff=302, NoMotionUseDrink=156, ParameterUp=532, ParameterUpLarge=302, Wait=239, WaitOnce=78
- `ExamMotion.targetStepTypes`：AuditionFinal=10, AuditionMid1=10
- `ExamOutGameMotion.type`：DanceLesson=143, DanceLessonHard=117, VisualLesson=143, VisualLessonHard=117, VocalLesson=143, VocalLessonHard=117
- `ExamOutGameMotion.motionType`：Clear=117, ResultFailure=78, ResultPerfect=234, ResultSuccess=234, Start1=78, Start2=39
- `ExamUnitMotion.motionType`：Wait=6
- `ExamUnitMotion.targetStepTypes`：AuditionFinal=4, AuditionMid1=4, AuditionMid2=2
- `ExchangeItemCategory.categoryType`：All=2, ItemType=1, Other=2, ResourceType=1
- `ExchangeItemCategory.resourceType`：SupportCard=1, Unknown=5
- `ExchangeItemCategory.itemType`：IdolCardPiece=1, Unknown=5
- `FeatureLock.tutorialType`：CoinGasha=1, DailyExchange=1, DearnessTop=1, Guild=1, IdolCardLevelLimitRankUpdate=1, MoneyReceive=1, ProduceCardConvert=1, ProducerRanking=1, PvpRate=1, SupportCardLevelUpdate=1, Tower=1, Work=1
- `ForceAppVersion.platformType`：Android=1, Dmm=1, Ios=1, Other=1
- `GashaAnimationStep.rarity`：PickupSsridolCard=95, R=5, Sr=12, Ssr=31
- `GashaAnimationStep.currentStepType`：Freeze=1, FreezeAfter=1, LightList=6, Monitor=36, Start=12, Step1=42, Step2=14, Tap=31
- `GashaAnimationStep.nextStepType`：End=4, Freeze=24, FreezeAfter=1, LightList=17, Monitor=26, Step1=30, Step2=29, Tap=12
- `GashaButton.type`：Dynamic=55, Static=48
- `GashaButton.resourceType`：Item=57, JewelPaidOnly=31, JewelTotal=8, Unknown=7
- `GashaButton.limitType`：Daily=3, DailyLoginAccumulation=5, None=10, Total=30, Unknown=55
- `GashaButton.discountLimitType`：Total=2, Unknown=101
- `GashaButton.appealType`：AppealText=21, CurrentStep=3, DrawableCount=10, FixSsr=41, Unknown=28
- `GashaButton.highAppealType`：AppealText=4, FixSsr=18, Unknown=81
- `GashaButton.bottomAppealType`：AppealText=1, DrawableCount=18, Unknown=84
- `HomeMotion.locationType`：Contest=143, Home=1373, Idol=143, Story1=78, Story2=52
- `HomeMotion.motionType`：MultipleTaps=91, Reaction=836, ReactionOnce=26, Transition=706, Wait1=78, Wait2=26, WaitLookAround=13, WaitOnce=13
- `HomeTime.type`：Daytime=1, Evening=1, Morning=1, Night=1
- `IdolCard.rarity`：R=25, Sr=13, Ssr=113
- `IdolCard.maxIdolCardLevelLimitRank`：_6=136, _7=15
- `IdolCard.planType`：Plan1=56, Plan2=60, Plan3=35
- `IdolCard.examEffectType`：ExamCardPlayAggressive=31, ExamConcentration=19, ExamFullPower=16, ExamLessonBuff=27, ExamParameterBuff=29, ExamReview=29
- `IdolCard.showExamEffectType`：ExamPreservation=3, Unknown=148
- `IdolCardLevelLimit.rank`：_1=27, _2=27, _3=27, _4=27, _5=27, _6=27, _7=9
- `IdolCardLevelLimitProduceSkill.rank`：_1=13, _2=15, _6=15, _7=1
- `IdolCardLevelLimitStatusUp.rank`：_1=6, _2=6, _3=6, _4=6, _5=6, _6=6, _7=2
- `IdolCardLevelLimitStatusUp.effectTypes`：ProduceCardUpgrade=6, ProduceSkill=16, ProduceStamina=9, ProduceVoDaVi=9, SecondProduceCardUpgrade=2
- `IdolCardPiece.exchangeReward.resourceType`：Item=151
- `IdolCardPieceQuantity.rarity`：R=1, Sr=1, Ssr=1
- `IdolCardPotential.rank`：_1=151, _2=151, _3=151, _4=151
- `IdolCardPotential.effectTypes`：InitialProduceItemChange=151, ProduceSkill=302, ProduceStamina=151, ProduceVoDaViGrowthRatePermil=151
- `IdolCardPotentialProduceSkill.rank`：_1=125, _4=125
- `IdolCardSkinSelectReward.difficultyType`：High=5, Low=3, Middle=4
- `InvitationPointReward.reward.resourceType`：JewelTotal=11
- `Item.type`：ActionPointRecovery=1, Coin=16, DearnessStoryUnlock=13, ExchangeMaterial=2, ExchangeTicket=8, FriendCoin=1, GashaTicket=57, IdolCardLevelLimitMaterial=24, IdolCardPiece=151, IdolCardPotentialRankUpgrade=3, Medal=64, MemoryInherit=1, Money=1, ProduceBoostRewardIdolCardLevelLimitMaterial=1, ProduceBoostRewardSupportCardEnhancePoint=1, ProduceContinue=1, ProduceRerollMemory=1, PvpRateCoin=1, StoryUnlockKey=1, SupportCardEnhancePoint=1, SupportCardLevelLimitRankUpgrade=3
- `Item.rarity`：R=66, Sr=27, Ssr=162, Unknown=97
- `Item.exchangeType`：Daily=1, Event=32, Item=4, Unknown=315
- `Item.idolCardRarity`：R=1, Sr=1, Ssr=1, Unknown=349
- `Item.supportCardRarity`：R=1, Sr=1, Ssr=1, Unknown=349
- `LimitItem.type`：ActionPointRecovery=1, Coin=1, CompetitionCoin=1, DearnessStoryUnlock=1, ExchangeMaterial=1, ExchangeTicket=1, FriendCoin=1, GashaTicket=1, IdolCardLevelLimitMaterial=1, IdolCardPiece=1, IdolCardPotentialRankUpgrade=1, Medal=1, MemoryInherit=1, Money=1, ProduceBoostRewardIdolCardLevelLimitMaterial=1, ProduceBoostRewardSupportCardEnhancePoint=1, ProduceContinue=1, ProduceLiveUnlockItem=1, ProduceRerollMemory=1, PvpRateCoin=1, StoryUnlockKey=1, SupportCardEnhancePoint=1, SupportCardLevelLimitRankUpgrade=1
- `MainTask.missionType`：AbsoluteAchievementCount=21, AbsoluteDearnessLevel=45, AbsoluteFanCount=5, AbsoluteFollowCount=1, AbsoluteIdolCardLevelLimitRankCount=16, AbsoluteProduceCharacterEnding=8, AbsoluteProducePictureBookProduceCardCount=7, AbsoluteProducePictureBookProduceDrinkCount=1, AbsoluteProducePlayCharacterCount=1, AbsoluteProducerLevel=20, AbsolutePvpRateExamBattleMaxScore=14, AbsolutePvpRateUnitOverallPower=14, AbsoluteSeminarExamClear=8, AbsoluteStoryRead=14, AbsoluteSupportCardLevel=2, AbsoluteSupportCardLevelCount=12, AbsoluteTowerTotalClearRank=17, IncrementConsumeActionPoint=1, IncrementDailyExchangeCount=1, IncrementIdolCardLevelLimitRankUpdateCount=1, IncrementMeishiUpdateCount=1, IncrementProduceCharacterClearCount=31, IncrementProduceCustomizeProduceCardCount=5, IncrementProduceLessonClearCount=1, IncrementProducePlanClearCount=9, IncrementProducePlanPlayCount=12, IncrementProducePlayCount=15, IncrementProduceSelectStepCount=1, IncrementProduceTotalScore=1, IncrementProduceUpgradeProduceCardCount=1, IncrementProduceVoteCount=2, IncrementPvpRatePlayCount=4, IncrementReceiveMoney=1, IncrementShopCoinGashaDrawCount=3, IncrementSupportCardLevelUpdateCount=1, IncrementWorkCount=1, IncrementWorkDurationHour=5, ProduceConditionClear=7
- `MainTask.rewards.resourceType`：Item=183, JewelTotal=124, UserExp=310
- `MainTask.unlockFeatureTutorialType`：CoinGasha=1, DailyExchange=1, Guild=1, IdolCardLevelLimitRankUpdate=1, MoneyReceive=1, ProducerRanking=1, PvpRate=1, SupportCardLevelUpdate=1, Unknown=300, Work=1
- `MainTask.additionalRewards.resourceType`：Item=1, JewelTotal=7
- `MainTaskGroup.mainTaskType`：MainStory=1, Producer=3
- `MainTaskIcon.missionType`：AbsoluteAchievementCount=1, AbsoluteCharacterIdolAchievementCount=1, AbsoluteCompetitionDeckPower=1, AbsoluteCompetitionGrade=1, AbsoluteCompetitionRank=1, AbsoluteCompetitionStageHighScore=1, AbsoluteCompetitionTotalHighScore=1, AbsoluteDearnessLevel=1, AbsoluteFanCount=1, AbsoluteFollowCount=1, AbsoluteFollowerCount=1, AbsoluteGuildJoin=1, AbsoluteIdolCardCount=1, AbsoluteIdolCardLevelLimitRank=1, AbsoluteIdolCardLevelLimitRankCount=1, AbsoluteIdolCardPotentialRankCount=1, AbsoluteIdolCardPrimaStellaCount=1, AbsoluteIdolCardSkin=1, AbsoluteLinkBandaiNamco=1, AbsoluteLinkSmartphoneWithDmm=1, AbsoluteLoginCount=1, AbsoluteMainTaskCount=1, AbsoluteMeishiExchangeCount=1, AbsoluteMeishiUpdateCount=1, AbsoluteProduceCharacterEnding=1, AbsoluteProduceGrowthPanelComplete=1, AbsoluteProduceIdolCardHighScore=1, AbsoluteProducePictureBookProduceCardCount=1, AbsoluteProducePictureBookProduceDrinkCount=1, AbsoluteProducePictureBookProduceItemCount=1, AbsoluteProducePlanTotalHighScore=1, AbsoluteProducePlayCharacterCount=1, AbsoluteProduceStoryRead=1, AbsoluteProducerLevel=1, AbsolutePvpRateCharacterExamBattleMaxScore=1, AbsolutePvpRateCurrentGrade=1, AbsolutePvpRateExamBattleMaxScore=1, AbsolutePvpRateGrade=1, AbsolutePvpRateRank=1, AbsolutePvpRateUnitOverallPower=1, AbsoluteSeminarExamClear=1, AbsoluteStoryRead=1, AbsoluteSupportCard=1, AbsoluteSupportCardCount=1, AbsoluteSupportCardLevel=1, AbsoluteSupportCardLevelCount=1, AbsoluteSupportCardLevelLimitRankCount=1, AbsoluteTowerCharacterTotalClearRank=1, AbsoluteTowerClearRank=1, AbsoluteTowerLayerClear=1, AbsoluteTowerTotalClearRank=1, ConditionClear=1, IncrementCompetitionPlayCount=1, IncrementCompetitionStageScoreCount=1, IncrementCompetitionUseProduceCardCount=1, IncrementCompetitionWinCount=1, IncrementConsumeActionPoint=1, IncrementDailyExchangeCount=1, IncrementDailyHomeEnterCount=1, IncrementEventCoinGashaDrawCount=1, IncrementEventExchangeCount=1, IncrementFanCount=1, IncrementGashaContinuousSnsShareCount=1, IncrementGashaDrawCount=1, IncrementGuildDonationCount=1, IncrementGuildDonationRequestCount=1, IncrementGvgRaidChallengeCount=1, IncrementGvgRaidLoopChallengeCount=1, IncrementIdolCardLevelLimitRankUpdateCount=1, IncrementIdolCardPotentialRankUpdateCount=1, IncrementItemExchangeCount=1, IncrementLoginCount=1, IncrementMeishiExchangeCount=1, IncrementMeishiUpdateCount=1, IncrementMeishiXpostCount=1, IncrementMemoryExchangeCount=1, IncrementMemoryGradeCount=1, IncrementMissionClear=1, IncrementPhotoIdolCount=1, IncrementProduceAdditionParameter=1, IncrementProduceCharacterClearCount=1, IncrementProduceCharacterPlayCount=1, IncrementProduceClearCount=1, IncrementProduceConsumedStamina=1, IncrementProduceCustomizeProduceCardCount=1, IncrementProduceExamUseProduceCardCount=1, IncrementProduceGetProduceCardCount=1, IncrementProduceGetProduceDrinkCount=1, IncrementProduceGetProduceItemCount=1, IncrementProduceGroupSelectStepCount=1, IncrementProduceIdolCardClearCount=1, IncrementProduceIdolCardPlayCount=1, IncrementProduceLessonClearCount=1, IncrementProduceMemoryDeckUpdateCount=1, IncrementProducePlanClearCount=1, IncrementProducePlanPlayCount=1, IncrementProducePlayCount=1, IncrementProduceSelectStepCount=1, IncrementProduceShopBuyCount=1, IncrementProduceSupportCardDeckUpdateCount=1, IncrementProduceTotalAdditionExamBlock=1, IncrementProduceTotalProducePoint=1, IncrementProduceTotalScore=1, IncrementProduceUpgradeProduceCardCount=1, IncrementProduceUseProduceDrinkCount=1, IncrementProduceVoteCount=1, IncrementProfileUpdateCount=1, IncrementProvideItemCount=1, IncrementPvpRateCharacterExamBattleScoreCount=1, IncrementPvpRateCharacterPlayCount=1, IncrementPvpRateCharacterWinCount=1, IncrementPvpRateExamBattleScoreCount=1, IncrementPvpRatePlayCount=1, IncrementPvpRateWinCount=1, IncrementReceiveMoney=1, IncrementShopCoinGashaDrawCount=1, IncrementSupportCardCount=1, IncrementSupportCardLevelLimitRankUpdateCount=1, IncrementSupportCardLevelUpdateCount=1, IncrementTourLevelPlayCount=1, IncrementUrlTransition=1, IncrementWorkCount=1, IncrementWorkDurationHour=1, IncrementWorkExcellentCount=1, ProduceConditionClear=1, ProduceConditionClearBeforeLiveEvaluation=1
- `Media.mediaType`：Comic=23, FourPanelComic=163, FourPanelComicOther=3, Movie=33
- `Media.fourPanelComicSeries`：Radio=3, Unknown=219
- `Media.mediaMovieType`：Birthday=16, Movie=6, Unknown=189
- `MeishiBaseAsset.meishiBaseAssetType`：CommonBackground=42, Frame=153, Other=34, StoryBackground=70
- `MeishiIllustrationAsset.type`：Badge=333, Idol=13, IdolSign=23, Logo=21, Other=177, PictoIcon=109, Sdcharacter=23
- `MemoryAbility.rarity`：Unknown=575
- `MemoryExchangeItem.planType`：Plan1=1, Plan2=1, Plan3=1
- `MemoryExchangeItemQuantity.grade`：A=1, APlus=1, B=1, BPlus=1, C=1, CPlus=1, D=1, E=1, F=1, S=1, SPlus=1, Ss=1, SsPlus=1, Sss=1, SssPlus=1, Ssss=1, SsssPlus=1, Sssss=1
- `MemoryGift.grade`：D=2, F=9, Sss=10
- `MemoryGift.planType`：Unknown=21
- `MemoryGift.produceCardPhaseType`：EndAuditionMid=5, ProduceStart=16
- `Mission.category`：Achievement=1206, Daily=21, Event=157, MainTask=310, Normal=265, Special=1400, Weekly=8
- `Mission.type`：AbsoluteAchievementCount=21, AbsoluteCharacterIdolAchievementCount=13, AbsoluteCompetitionGrade=7, AbsoluteCompetitionRank=4, AbsoluteDearnessLevel=98, AbsoluteFanCount=22, AbsoluteFollowCount=1, AbsoluteFollowerCount=1, AbsoluteIdolCardCount=1, AbsoluteIdolCardLevelLimitRank=529, AbsoluteIdolCardLevelLimitRankCount=16, AbsoluteIdolCardPotentialRankCount=4, AbsoluteIdolCardPrimaStellaCount=1, AbsoluteLinkBandaiNamco=1, AbsoluteLinkSmartphoneWithDmm=1, AbsoluteMeishiExchangeCount=1, AbsoluteProduceCharacterEnding=139, AbsoluteProduceGrowthPanelComplete=1, AbsoluteProducePictureBookProduceCardCount=15, AbsoluteProducePictureBookProduceDrinkCount=2, AbsoluteProducePictureBookProduceItemCount=1, AbsoluteProducePlayCharacterCount=1, AbsoluteProducerLevel=26, AbsolutePvpRateExamBattleMaxScore=18, AbsolutePvpRateGrade=13, AbsolutePvpRateRank=4, AbsolutePvpRateUnitOverallPower=16, AbsoluteSeminarExamClear=9, AbsoluteStoryRead=15, AbsoluteSupportCardCount=1, AbsoluteSupportCardLevel=3, AbsoluteSupportCardLevelCount=12, AbsoluteTowerCharacterTotalClearRank=26, AbsoluteTowerTotalClearRank=17, ConditionClear=42, IncrementCompetitionPlayCount=1, IncrementConsumeActionPoint=85, IncrementDailyExchangeCount=5, IncrementDailyHomeEnterCount=43, IncrementEventCoinGashaDrawCount=11, IncrementFanCount=50, IncrementGashaDrawCount=9, IncrementGuildDonationCount=1, IncrementGvgRaidChallengeCount=1, IncrementIdolCardLevelLimitRankUpdateCount=2, IncrementIdolCardPotentialRankUpdateCount=1, IncrementLoginCount=2, IncrementMeishiUpdateCount=1, IncrementMemoryGradeCount=7, IncrementMissionClear=167, IncrementProduceCharacterClearCount=271, IncrementProduceCharacterPlayCount=23, IncrementProduceClearCount=165, IncrementProduceConsumedStamina=11, IncrementProduceCustomizeProduceCardCount=37, IncrementProduceExamUseProduceCardCount=26, IncrementProduceGetProduceCardCount=7, IncrementProduceGetProduceDrinkCount=7, IncrementProduceGetProduceItemCount=1, IncrementProduceGroupSelectStepCount=20, IncrementProduceIdolCardClearCount=139, IncrementProduceIdolCardPlayCount=126, IncrementProduceLessonClearCount=119, IncrementProduceMemoryDeckUpdateCount=1, IncrementProducePlanClearCount=16, IncrementProducePlanPlayCount=30, IncrementProducePlayCount=21, IncrementProduceSelectStepCount=82, IncrementProduceShopBuyCount=30, IncrementProduceSupportCardDeckUpdateCount=1, IncrementProduceTotalAdditionExamBlock=5, IncrementProduceTotalProducePoint=8, IncrementProduceTotalScore=400, IncrementProduceUpgradeProduceCardCount=32, IncrementProduceUseProduceDrinkCount=38, IncrementProduceVoteCount=16, IncrementProfileUpdateCount=1, IncrementPvpRatePlayCount=9, IncrementPvpRateWinCount=1, IncrementReceiveMoney=5, IncrementShopCoinGashaDrawCount=11, IncrementSupportCardLevelLimitRankUpdateCount=1, IncrementSupportCardLevelUpdateCount=4, IncrementTourLevelPlayCount=13, IncrementUrlTransition=2, IncrementWorkCount=13, IncrementWorkDurationHour=8, ProduceConditionClear=29, ProduceConditionClearBeforeLiveEvaluation=158
- `MissionGroup.rewards.resourceType`：Item=32, JewelTotal=30, MeishiBaseAsset=4, MeishiIllustrationAsset=45, UserExp=2
- `MissionPassProgress.normalReward.resourceType`：Item=601
- `MissionPassProgress.premiumReward.resourceType`：CostumeHead=100, Item=399, JewelTotal=73, Unknown=29
- `MissionPoint.resetTimingType`：Daily=3, Never=31, Weekly=1
- `MissionPointRewardSet.rewards.resourceType`：Item=42, JewelTotal=29, MissionPassPoint=6, Story=52
- `MissionProgress.rewards.resourceType`：DearnessPoint=360, FriendFollowLimitCount=4, Item=2273, JewelTotal=547, MeishiBaseAsset=1, MeishiIllustrationAsset=1, StoryEventPoint=371, UserExp=54
- `Music.type`：Bgm=36, Instrumental=87, Music=293
- `PhotoBackground.category`：Around=2, Gakuen=4, Other=2
- `PhotoBackground.timeTypes`：Evening=1, Night=2, Noon=7
- `PhotoPose.motionType`：Reaction=780, Wait=260
- `PhotoPose.lookTargetType`：FullBody=843, Ng=197
- `Produce.produceSelectScreenOrderType`：First=7, Second=1
- `Produce.produceSplitType`：Final=1, Selection=1, Unknown=6
- `ProduceAdv.produceType`：FirstStar=14, NextIdolAudition=18
- `ProduceAdv.type`：BeforeFinalAuditionRefresh=2, BeforeFinalAuditionSelect=1, BeforeFinalLessonHard=2, BeforeMid1AuditionRefresh=2, BeforeMid1AuditionSelect=1, BeforeMid1LessonHard=2, BeforeMid2AuditionRefresh=2, BeforeMid2AuditionSelect=1, BeforeMid2LessonHard=2, Opening=2, ProduceResultA=2, ProduceResultB=2, ProduceResultC=2, ProduceResultFailedFinal=2, ProduceResultFailedMid1=2, ProduceResultFailedMid2=2, ProduceResultTrueEnd=2, StepSkip=1
- `ProduceCard.rarity`：Legend=25, N=161, R=288, Sr=408, Ssr=832
- `ProduceCard.planType`：Common=129, Plan1=544, Plan2=584, Plan3=457
- `ProduceCard.category`：ActiveSkill=840, MentalSkill=873, Trouble=1
- `ProduceCard.costType`：ExamCardPlayAggressive=41, ExamFullPowerPoint=33, ExamLessonBuff=25, ExamParameterBuff=33, ExamParameterBuffMultiplePerTurn=4, ExamReview=16, Unknown=1562
- `ProduceCard.playMovePositionType`：Grave=312, Lost=1402
- `ProduceCard.moveEffectTriggerType`：Hand=7, Hold=1, Unknown=1706
- `ProduceCard.produceDescriptions.produceDescriptionType`：Exam=10158, PlainText=18407, ProduceCard=75, ProduceCardCategory=117, ProduceCardGrowEffectType=197, ProduceDescription=2835, ProduceDescriptionName=4412, ProduceExamEffectType=5285
- `ProduceCard.produceDescriptions.examDescriptionType`：CustomizeCostValue=364, CustomizeEffectAdd=1714, CustomizeEffectCount=570, CustomizeEffectValue1=2403, CustomizeEffectValue2=16, CustomizeEffectValuePercent1=393, CustomizeEffectValuePercent2=30, CustomizeInitialAdd=1714, CustomizeLessonCountAdd=776, CustomizePlayMovePositionLost=1714, CustomizeTurn=464, Unknown=31328
- `ProduceCard.produceDescriptions.examEffectType`：ExamAddGrowEffect=53, ExamAggressiveAdditive=4, ExamAggressiveAdditiveFix=4, ExamAntiDebuff=12, ExamBlock=698, ExamBlockFix=8, ExamBlockRestriction=8, ExamCardCreateId=45, ExamCardPlayAggressive=380, ExamCardUpgrade=43, ExamConcentration=224, ExamDebuffRecover=4, ExamEnthusiasticAdditive=17, ExamEnthusiasticMultiple=14, ExamExtraTurn=7, ExamFullPower=123, ExamFullPowerPoint=312, ExamFullPowerPointAdditive=4, ExamGimmickEnthusiastic=4, ExamLesson=904, ExamLessonBuff=384, ExamLessonBuffAdditive=6, ExamLessonBuffAdditiveFix=8, ExamLessonBuffMultiple=12, ExamLessonValueMultiple=14, ExamLessonValueMultipleDependReviewOrAggressive=4, ExamOverPreservation=13, ExamParameterBuff=370, ExamParameterBuffAdditive=1, ExamParameterBuffMultiplePerTurn=62, ExamParameterBuffMultiplePerTurnReduce=1, ExamParameterBuffReduce=4, ExamPlayableValueAdd=353, ExamPreservation=227, ExamReview=513, ExamReviewAdditive=8, ExamReviewCountAdd=4, ExamReviewMultiple=26, ExamStaminaConsumptionAdd=24, ExamStaminaConsumptionDown=66, ExamStaminaConsumptionDownFix=28, ExamStaminaRecoverFix=52, ExamStaminaReduceFix=213, ExamStatusEnchantEncore=20, StanceLock=4, Unknown=36201
- `ProduceCard.produceDescriptions.produceCardGrowEffectType`：BlockAdd=16, CostAdd=33, CostFullPowerPointAdd=4, CostPenetrateAdd=4, CostPenetrateReduce=4, CostReduce=4, LessonAdd=105, LessonCountAdd=26, ReviewAdd=1, Unknown=41289
- `ProduceCard.produceDescriptions.produceCardCategory`：ActiveSkill=50, MentalSkill=39, Trouble=28, Unknown=41369
- `ProduceCard.produceDescriptions.produceCardMovePositionType`：Lost=1402, Unknown=40084
- `ProduceCard.produceDescriptions.produceStepType`：Unknown=41486
- `ProduceCard.produceDescriptions.produceStepBusinessType`：Unknown=41486
- `ProduceCardCustomize.overwriteProduceCardGrowEffectType`：AggressiveAdd=3, BlockAdd=17, CardStatusEnchantChange=19, EffectAdd=3, FullPowerPointAdd=1, LessonAdd=6, LessonBuffAdd=3, LessonDependBlockAdd=1, LessonDependExamCardPlayAggressiveAdd=1, LessonDependExamReviewAdd=1, ParameterBuffMultiplePerTurnAdd=1, ParameterBuffTurnAdd=5, ReviewAdd=5, StaminaConsumptionDownTurnAdd=5, Unknown=272
- `ProduceCardCustomizeRarityEvaluation.rarity`：N=1, R=1, Sr=1, Ssr=1
- `ProduceCardGrowEffect.effectType`：AggressiveAdd=5, BlockAdd=20, BlockReduce=20, CardStatusEnchantChange=16, CostAdd=10, CostAggressiveAdd=1, CostAggressiveReduce=1, CostFullPowerPointAdd=1, CostFullPowerPointReduce=1, CostLessonBuffAdd=1, CostLessonBuffReduce=1, CostParameterBuffAdd=1, CostParameterBuffMultiplePerTurnReduce=1, CostParameterBuffReduce=1, CostPenetrateAdd=5, CostPenetrateReduce=5, CostReduce=5, CostReviewAdd=1, CostReviewReduce=1, EffectAdd=52, EffectChange=24, FullPowerPointAdd=20, FullPowerPointReduce=20, InitialAdd=1, LessonAdd=61, LessonBuffAdd=5, LessonCountAdd=10, LessonCountReduce=10, LessonDependBlockAdd=19, LessonDependExamCardPlayAggressiveAdd=47, LessonDependExamReviewAdd=37, LessonReduce=20, ParameterBuffMultiplePerTurnAdd=5, ParameterBuffTurnAdd=5, PlayEffectTriggerChange=4, PlayMovePositionTypeChange=1, PlayTriggerChange=4, ReviewAdd=6, StaminaConsumptionDownTurnAdd=5
- `ProduceCardGrowEffect.costType`：Unknown=453
- `ProduceCardGrowEffect.playMovePositionType`：Grave=1, Unknown=452
- `ProduceCardSearch.cardRarities`：Legend=1, N=3, R=8, Sr=9, Ssr=11
- `ProduceCardSearch.planType`：Plan1=1, Plan2=1, Plan3=1, Unknown=277
- `ProduceCardSearch.cardCategories`：ActiveSkill=10, MentalSkill=8, Trouble=6
- `ProduceCardSearch.cardStatusType`：Unknown=280
- `ProduceCardSearch.orderType`：First=3, Random=13, Unknown=264
- `ProduceCardSearch.cardPositionType`：Deck=6, DeckAll=44, DeckGrave=12, Hand=11, Hold=1, Lost=12, NotLost=3, Playing=41, RandomPool=10, Target=140
- `ProduceCardSearch.staminaMinMaxType`：MinMax=3, Unknown=277
- `ProduceCardSearch.examEffectType`：Unknown=280
- `ProduceCardSearch.produceDescriptions.produceDescriptionType`：PlainText=134, ProduceCard=182, ProduceCardCategory=20, ProduceDescription=4, ProduceExamEffectType=38
- `ProduceCardSearch.produceDescriptions.examDescriptionType`：Unknown=378
- `ProduceCardSearch.produceDescriptions.examEffectType`：ExamBlock=3, ExamCardCreateId=2, ExamCardPlayAggressive=3, ExamConcentration=5, ExamFullPower=4, ExamLessonBuff=4, ExamParameterBuff=3, ExamParameterBuffMultiplePerTurn=2, ExamPreservation=6, ExamReview=3, ExamStaminaConsumptionDown=1, ExamStaminaRecoverFix=2, Unknown=340
- `ProduceCardSearch.produceDescriptions.produceCardGrowEffectType`：Unknown=378
- `ProduceCardSearch.produceDescriptions.produceCardCategory`：ActiveSkill=8, MentalSkill=7, Trouble=5, Unknown=358
- `ProduceCardSearch.produceDescriptions.produceCardMovePositionType`：Unknown=378
- `ProduceCardSearch.produceDescriptions.produceStepType`：Unknown=378
- `ProduceCardSearch.produceDescriptions.produceStepBusinessType`：Unknown=378
- `ProduceCardSearch.costType`：Unknown=280
- `ProduceCardStatusEnchant.produceDescriptions.produceDescriptionType`：PlainText=387, ProduceCardCategory=2, ProduceCardGrowEffectType=102, ProduceDescription=68, ProduceDescriptionName=78, ProduceExamEffectType=129
- `ProduceCardStatusEnchant.produceDescriptions.examDescriptionType`：Unknown=766
- `ProduceCardStatusEnchant.produceDescriptions.examEffectType`：ExamAddGrowEffect=77, ExamConcentration=26, ExamFullPower=18, ExamFullPowerPoint=3, ExamPreservation=5, Unknown=637
- `ProduceCardStatusEnchant.produceDescriptions.produceCardGrowEffectType`：BlockAdd=5, CostAdd=12, CostFullPowerPointAdd=2, CostPenetrateAdd=2, CostPenetrateReduce=2, CostReduce=2, FullPowerPointAdd=3, LessonAdd=65, LessonCountAdd=9, Unknown=664
- `ProduceCardStatusEnchant.produceDescriptions.produceCardCategory`：ActiveSkill=1, MentalSkill=1, Unknown=764
- `ProduceCardStatusEnchant.produceDescriptions.produceCardMovePositionType`：Unknown=766
- `ProduceCardStatusEnchant.produceDescriptions.produceStepType`：Unknown=766
- `ProduceCardStatusEnchant.produceDescriptions.produceStepBusinessType`：Unknown=766
- `ProduceCharacterAdv.produceType`：NextIdolAudition=10
- `ProduceCharacterAdv.type`：Introduction=10
- `ProduceCustomizeItem.effectType`：ProduceEffect=180
- `ProduceCustomizeItem.planType`：Plan1=60, Plan2=60, Plan3=60
- `ProduceCustomizeItem.produceDescriptions.produceDescriptionType`：DiffText=180, Exam=252, PlainText=2121, ProduceCardCategory=27, ProduceCardGrowEffectType=60, ProduceDescription=99, ProduceDescriptionName=726, ProduceExamEffectType=252
- `ProduceCustomizeItem.produceDescriptions.examDescriptionType`：CustomizeEffectValue1=192, CustomizeTurn=60, Unknown=3465
- `ProduceCustomizeItem.produceDescriptions.examEffectType`：ExamBlockFix=12, ExamCardPlayAggressive=60, ExamLessonBuff=60, ExamParameterBuff=60, ExamReview=60, Unknown=3465
- `ProduceCustomizeItem.produceDescriptions.produceCardGrowEffectType`：LessonAdd=60, Unknown=3657
- `ProduceCustomizeItem.produceDescriptions.produceCardCategory`：Trouble=27, Unknown=3690
- `ProduceCustomizeItem.produceDescriptions.produceCardMovePositionType`：Unknown=3717
- `ProduceCustomizeItem.produceDescriptions.produceStepType`：Unknown=3717
- `ProduceCustomizeItem.produceDescriptions.produceStepBusinessType`：Unknown=3717
- `ProduceDescriptionExamEffect.type`：ExamAddGrowEffect=1, ExamAggressiveAdditive=1, ExamAggressiveAdditiveFix=1, ExamAggressiveReduce=1, ExamAntiDebuff=1, ExamBlock=1, ExamBlockAddDown=1, ExamBlockAddDownRestriction=1, ExamBlockFix=1, ExamBlockRestriction=1, ExamCardCreateId=1, ExamCardDraw=1, ExamCardDuplicate=1, ExamCardPlayAggressive=1, ExamCardSearchEffectPlayCountBuff=1, ExamCardStaminaConsumptionChange=1, ExamCardStaminaConsumptionDownSpecify=1, ExamCardUpgrade=1, ExamConcentration=1, ExamConcentrationLessonMultipleAdditive=1, ExamDebuffRecover=1, ExamEffectTimer=1, ExamEnthusiasticAdditive=1, ExamEnthusiasticMultiple=1, ExamExtraTurn=1, ExamFullPower=1, ExamFullPowerLessonMultipleAdditive=1, ExamFullPowerPoint=1, ExamFullPowerPointAdditive=1, ExamFullPowerPointAdditiveFix=1, ExamFullPowerPointReduce=1, ExamGetCardUpgrade=1, ExamGimmickEnthusiastic=1, ExamGimmickLessonDebuff=1, ExamGimmickParameterDebuff=1, ExamGimmickPlayCardLimit=1, ExamGimmickSleepy=1, ExamGimmickSlump=1, ExamGimmickStartTurnCardDrawDown=1, ExamGrowEffectLessonAddAdditive=1, ExamHandGraveCountCardDraw=1, ExamHandHold=1, ExamLesson=1, ExamLessonBuff=1, ExamLessonBuffAdditive=1, ExamLessonBuffAdditiveFix=1, ExamLessonBuffMultiple=1, ExamLessonBuffReduce=1, ExamLessonChangeSpecifyLessThan=1, ExamLessonChangeSpecifyMoreThan=1, ExamLessonFix=1, ExamLessonValueMultiple=1, ExamLessonValueMultipleDependReviewOrAggressive=1, ExamLessonValueMultipleDown=1, ExamOverPreservation=1, ExamPanic=1, ExamParameterBuff=1, ExamParameterBuffAdditive=1, ExamParameterBuffAdditiveFix=1, ExamParameterBuffMultiplePerTurn=1, ExamParameterBuffMultiplePerTurnReduce=1, ExamParameterBuffReduce=1, ExamPlayableValueAdd=1, ExamPreservation=1, ExamReview=1, ExamReviewAdditive=1, ExamReviewAdditiveFix=1, ExamReviewCountAdd=1, ExamReviewMultiple=1, ExamReviewReduce=1, ExamSearchPlayCardStaminaConsumptionChange=1, ExamStaminaConsumptionAdd=1, ExamStaminaConsumptionAddDown=1, ExamStaminaConsumptionAddFix=1, ExamStaminaConsumptionDown=1, ExamStaminaConsumptionDownAdd=1, ExamStaminaConsumptionDownFix=1, ExamStaminaDamage=1, ExamStaminaRecoverAdd=1, ExamStaminaRecoverFix=1, ExamStaminaRecoverRestriction=1, ExamStaminaReduceChange=1, ExamStaminaReduceFix=1, ExamStanceReset=1, ExamStatusEnchant=1, ExamStatusEnchantEncore=1, ExamUplifting=1, StanceLock=1
- `ProduceDescriptionLabel.produceDescriptions.produceDescriptionType`：Exam=98, PlainText=401, ProduceCardGrowEffectType=3, ProduceDescription=7, ProduceDescriptionName=15, ProduceExamEffectType=206
- `ProduceDescriptionLabel.produceDescriptions.examDescriptionType`：CustomizeEffectCount=1, ExamCount=3, ExamProduceCardSearch=4, ExamProduceExamEffect=6, ExamTurn=45, ExamTurnTimer=1, ExamValue=36, ExamValue2=2, Unknown=632
- `ProduceDescriptionLabel.produceDescriptions.examEffectType`：ExamBlock=15, ExamBlockFix=4, ExamCardCreateId=2, ExamCardPlayAggressive=8, ExamCardUpgrade=1, ExamConcentration=8, ExamEffectTimer=10, ExamFullPower=14, ExamFullPowerPoint=12, ExamGimmickEnthusiastic=10, ExamLesson=44, ExamLessonBuff=7, ExamOverPreservation=7, ExamParameterBuff=8, ExamParameterBuffMultiplePerTurn=3, ExamPlayableValueAdd=7, ExamPreservation=13, ExamReview=15, ExamStaminaReduceFix=6, ExamStatusEnchant=11, ExamStatusEnchantEncore=1, Unknown=524
- `ProduceDescriptionLabel.produceDescriptions.produceCardGrowEffectType`：LessonAdd=3, Unknown=727
- `ProduceDescriptionLabel.produceDescriptions.produceCardCategory`：Unknown=730
- `ProduceDescriptionLabel.produceDescriptions.produceCardMovePositionType`：Unknown=730
- `ProduceDescriptionLabel.produceDescriptions.produceStepType`：Unknown=730
- `ProduceDescriptionLabel.produceDescriptions.produceStepBusinessType`：Unknown=730
- `ProduceDescriptionProduceCardGrowEffect.type`：AggressiveAdd=1, AggressiveReduce=1, BlockAdd=1, BlockReduce=1, CardDrawAdd=1, CardDrawReduce=1, CardStatusEnchantChange=1, CostAdd=1, CostAggressiveAdd=1, CostAggressiveReduce=1, CostBuffAdd=1, CostBuffReduce=1, CostFullPowerPointAdd=1, CostFullPowerPointReduce=1, CostLessonBuffAdd=1, CostLessonBuffReduce=1, CostParameterBuffAdd=1, CostParameterBuffMultiplePerTurnAdd=1, CostParameterBuffMultiplePerTurnReduce=1, CostParameterBuffReduce=1, CostPenetrateAdd=1, CostPenetrateReduce=1, CostReduce=1, CostReviewAdd=1, CostReviewReduce=1, EffectAdd=1, EffectChange=1, EffectDelete=1, FullPowerPointAdd=1, FullPowerPointReduce=1, InitialAdd=1, LessonAdd=1, LessonBuffAdd=1, LessonBuffReduce=1, LessonCountAdd=1, LessonCountReduce=1, LessonDependBlockAdd=1, LessonDependExamCardPlayAggressiveAdd=1, LessonDependExamReviewAdd=1, LessonReduce=1, ParameterBuffMultiplePerTurnAdd=1, ParameterBuffMultiplePerTurnReduce=1, ParameterBuffTurnAdd=1, ParameterBuffTurnReduce=1, PlayEffectTriggerChange=1, PlayMovePositionTypeChange=1, PlayTriggerChange=1, ReviewAdd=1, ReviewReduce=1, StaminaConsumptionAddTurnAdd=1, StaminaConsumptionAddTurnReduce=1, StaminaConsumptionDownTurnAdd=1, StaminaConsumptionDownTurnReduce=1
- `ProduceDescriptionProduceCardMovePosition.type`：DeckFirst=1, DeckLast=1, DeckRandom=1, Grave=1, Hand=1, Hold=1, Lost=1
- `ProduceDescriptionProduceEffect.type`：AuditionNpcEnhance=1, AuditionNpcWeaken=1, AuditionParameterBonusMultiple=1, BeforeAuditionRefreshStaminaDown=1, BeforeAuditionRefreshStaminaUp=1, DanceAddition=1, DanceDown=1, DanceGrowthRateAddition=1, DanceGrowthRateDown=1, EventActivityProducePointDown=1, EventActivityProducePointUp=1, EventSchoolStaminaDown=1, EventSchoolStaminaUp=1, ExamStatusEnchant=1, ExamTurnDown=1, ExamTurnUp=1, LessonDanceSpChangeRatePermilAddition=1, LessonPresentProduceCardRewardCountDown=1, LessonPresentProduceCardRewardCountUp=1, LessonPresentProducePointUp=1, LessonSpChangeRatePermilAddition=1, LessonSpChangeRatePermilDown=1, LessonVisualSpChangeRatePermilAddition=1, LessonVocalSpChangeRatePermilAddition=1, MaxStaminaAddition=1, MaxStaminaReduceFix=1, MaxStaminaReduceMultiple=1, ParameterLimitUp=1, ProduceCardChange=1, ProduceCardChangeSelect=1, ProduceCardChangeUpgrade=1, ProduceCardDelete=1, ProduceCardDuplicate=1, ProduceCardDuplicateUpgrade=1, ProduceCardExcludeCountUp=1, ProduceCardSelectRerollCountUp=1, ProduceCardUpgrade=1, ProduceDrinkGetDisable=1, ProduceDrinkPossessLimitUp=1, ProduceItemGetDisable=1, ProducePointAddition=1, ProducePointAdditionDisableTrigger=1, ProducePointAdditionValueDown=1, ProducePointAdditionValueUp=1, ProducePointGetDisable=1, ProducePointReduceFix=1, ProducePointReduceMultiple=1, ProducePointReduceValueDown=1, ProducePointReduceValueUp=1, ProducePointSpecify=1, ProduceResultRewardMoneyUp=1, ProduceResultRewardSupportCardEnhancePointUp=1, ProduceReward=1, ProduceRewardSet=1, ShopPriceDiscountMultiple=1, ShopPriceUpMultiple=1, ShopProduceCardDeletePriceDiscountMultiple=1, ShopProduceCardDeletePriceSpecify=1, ShopProduceCardDeletePriceUpMultiple=1, ShopProduceCardPriceDiscountMultiple=1, ShopProduceCardPriceDiscountMultiplePermanent=1, ShopProduceCardPriceUpMultiple=1, ShopProduceCardUpgradePriceDiscountMultiple=1, ShopProduceCardUpgradePriceSpecify=1, ShopProduceCardUpgradePriceUpMultiple=1, ShopProduceDrinkPriceDiscountMultiple=1, ShopProduceDrinkPriceUpMultiple=1, StaminaRecoverDisable=1, StaminaRecoverFix=1, StaminaRecoverMultiple=1, StaminaRecoverValueDown=1, StaminaRecoverValueUp=1, StaminaReduceFix=1, StaminaReduceMultiple=1, StaminaReduceValueDown=1, StaminaReduceValueUp=1, StaminaSpecify=1, StarAddition=1, StarPermilUp=1, SupportCardEventParameterAdditionValueUp=1, SupportCardEventProbabilityUp=1, SupportCardEventProducePointAdditionValueUp=1, SupportCardEventStaminaRecoverUp=1, SupportCardProduceCardUpgradeProbabilityUp=1, VisualAddition=1, VisualDown=1, VisualGrowthRateAddition=1, VisualGrowthRateDown=1, VocalAddition=1, VocalDown=1, VocalGrowthRateAddition=1, VocalGrowthRateDown=1
- `ProduceDescriptionProducePlan.type`：Common=1, Plan1=1, Plan2=1, Plan3=1
- `ProduceDescriptionProduceStep.type`：EventSchool=1, Present=1
- `ProduceDescriptionProduceType.produceType`：FirstStar=1, HatsuboshiIdolFestival=3, NextIdolAudition=1
- `ProduceDescriptionProduceType.produceSplitType`：Final=1, Selection=1, Unknown=3
- `ProduceDescriptionSwap.swapType`：Audition=39, Lesson=39
- `ProduceDrink.planType`：Common=11, Plan1=6, Plan2=6, Plan3=6
- `ProduceDrink.rarity`：R=8, Sr=9, Ssr=12
- `ProduceDrink.produceDescriptions.produceDescriptionType`：Exam=47, PlainText=133, ProduceCardCategory=1, ProduceDescription=1, ProduceDescriptionName=3, ProduceExamEffectType=44
- `ProduceDrink.produceDescriptions.examDescriptionType`：CustomizeEffectCount=3, CustomizeEffectValue1=26, CustomizeEffectValuePercent1=3, CustomizeLessonCountAdd=2, CustomizeTurn=13, Unknown=182
- `ProduceDrink.produceDescriptions.examEffectType`：ExamBlock=3, ExamCardCreateId=2, ExamCardPlayAggressive=2, ExamCardUpgrade=2, ExamConcentration=2, ExamExtraTurn=1, ExamFullPowerPoint=3, ExamLesson=2, ExamLessonBuff=2, ExamLessonValueMultiple=2, ExamParameterBuff=1, ExamParameterBuffMultiplePerTurn=2, ExamPlayableValueAdd=1, ExamPreservation=2, ExamReview=3, ExamStaminaConsumptionAdd=3, ExamStaminaConsumptionDown=3, ExamStaminaRecoverFix=3, ExamStaminaReduceFix=5, Unknown=185
- `ProduceDrink.produceDescriptions.produceCardGrowEffectType`：Unknown=229
- `ProduceDrink.produceDescriptions.produceCardCategory`：ActiveSkill=1, Unknown=228
- `ProduceDrink.produceDescriptions.produceCardMovePositionType`：Unknown=229
- `ProduceDrink.produceDescriptions.produceStepType`：Unknown=229
- `ProduceDrink.produceDescriptions.produceStepBusinessType`：Unknown=229
- `ProduceEffect.produceEffectType`：AuditionNpcEnhance=8, AuditionNpcWeaken=2, AuditionParameterBonusMultiple=7, AuditionVoteCountUp=9, BeforeAuditionRefreshStaminaDown=2, BeforeAuditionRefreshStaminaUp=6, CustomizeProduceCardProducePointDownMultiple=2, DanceAddition=200, DanceGrowthRateAddition=86, EventActivityProducePointDown=1, EventActivityProducePointUp=1, EventBusinessVoteCountUp=9, EventSchoolStaminaDown=1, EventSchoolStaminaUp=5, ExamPermanentAuditionStatusEnchant=51, ExamPermanentLessonStatusEnchant=7, ExamStatusEnchant=201, ExamTurnDown=1, HighScoreGoldAddition=6, IdolCardProduceCardCustomizeEnable=1, LessonDanceSpChangeRatePermilAddition=6, LessonPresentProduceCardRewardCountUp=1, LessonPresentProducePointUp=6, LessonSpChangeRatePermilAddition=24, LessonVisualSpChangeRatePermilAddition=6, LessonVocalSpChangeRatePermilAddition=6, MaxStaminaAddition=9, MaxStaminaReduceFix=6, ParameterLimitUp=6, ProduceCardChange=37, ProduceCardChangeSelect=23, ProduceCardChangeUpgrade=35, ProduceCardDelete=6, ProduceCardDuplicate=7, ProduceCardExcludeCountUp=2, ProduceCardSelectRerollCountUp=3, ProduceCardUpgrade=9, ProduceCustomizeItemUpgrade=1, ProduceDrinkPossessLimitUp=1, ProducePointAddition=41, ProducePointAdditionDisableTrigger=20, ProducePointReduceFix=15, ProduceReward=207, ProduceRewardSet=204, ShopPriceDiscountMultiple=2, ShopPriceUpMultiple=1, ShopProduceCardDeletePriceDiscountMultiple=5, ShopProduceCardPriceDiscountMultiple=10, ShopProduceCardPriceDiscountMultiplePermanent=6, ShopProduceCardUpgradePriceDiscountMultiple=5, ShopProduceDrinkPriceDiscountMultiple=5, ShopRerollCountUp=1, StaminaRecoverFix=11, StaminaRecoverMultiple=12, StaminaReduceFix=10, StarAddition=1, StarPermilUp=9, SupportCardEventParameterAdditionValueUp=3, SupportCardEventProducePointAdditionValueUp=3, SupportCardEventStaminaRecoverUp=3, SupportCardProduceCardUpgradeProbabilityUp=141, VisualAddition=200, VisualGrowthRateAddition=86, VocalAddition=200, VocalGrowthRateAddition=86, VoteCountAddition=27
- `ProduceEffect.produceResourceType`：ProduceCard=233, ProduceCustomizeItem=1, ProduceDrink=31, ProduceItem=34, Unknown=1815
- `ProduceEffect.pickRangeType`：All=26, Random=25, Select=271, Unknown=1792
- `ProduceEffect.produceRewards.resourceType`：ProduceCard=70, ProduceDrink=1, ProduceItem=136
- `ProduceEffectIcon.type`：AuditionNpcEnhance=1, AuditionParameterBonusMultiple=1, AuditionVoteCountUp=1, BeforeAuditionRefreshStaminaDown=1, BeforeAuditionRefreshStaminaUp=1, DanceAddition=1, DanceDown=1, DanceGrowthRateAddition=1, DanceGrowthRateDown=1, EventActivityProducePointDown=1, EventActivityProducePointUp=1, EventBusinessVoteCountUp=1, EventSchoolStaminaDown=1, EventSchoolStaminaUp=1, ExamStatusEnchant=1, ExamTurnDown=1, ExamTurnUp=1, LessonDanceSpChangeRatePermilAddition=1, LessonPresentProduceCardRewardCountDown=1, LessonPresentProduceCardRewardCountUp=1, LessonPresentProducePointUp=1, LessonSpChangeRatePermilAddition=1, LessonSpChangeRatePermilDown=1, LessonVisualSpChangeRatePermilAddition=1, LessonVocalSpChangeRatePermilAddition=1, MaxStaminaAddition=1, MaxStaminaReduceFix=1, MaxStaminaReduceMultiple=1, ParameterLimitUp=1, ProduceCardChange=1, ProduceCardChangeUpgrade=1, ProduceCardDelete=1, ProduceCardDuplicate=1, ProduceCardDuplicateUpgrade=1, ProduceCardExcludeCountUp=1, ProduceCardSelectRerollCountUp=1, ProduceCardUpgrade=1, ProduceDrinkGetDisable=1, ProduceDrinkPossessLimitUp=1, ProduceItemGetDisable=1, ProducePointAddition=1, ProducePointAdditionDisableTrigger=1, ProducePointAdditionValueDown=1, ProducePointAdditionValueUp=1, ProducePointGetDisable=1, ProducePointReduceFix=1, ProducePointReduceMultiple=1, ProducePointReduceValueDown=1, ProducePointReduceValueUp=1, ProducePointSpecify=1, ProduceResultRewardMoneyUp=1, ProduceResultRewardSupportCardEnhancePointUp=1, ProduceReward=4, ProduceRewardSet=4, ShopPriceDiscountMultiple=1, ShopPriceUpMultiple=1, ShopProduceCardDeletePriceDiscountMultiple=1, ShopProduceCardDeletePriceSpecify=1, ShopProduceCardDeletePriceUpMultiple=1, ShopProduceCardPriceDiscountMultiple=1, ShopProduceCardPriceDiscountMultiplePermanent=1, ShopProduceCardPriceUpMultiple=1, ShopProduceCardUpgradePriceDiscountMultiple=1, ShopProduceCardUpgradePriceSpecify=1, ShopProduceCardUpgradePriceUpMultiple=1, ShopProduceDrinkPriceDiscountMultiple=1, ShopProduceDrinkPriceUpMultiple=1, ShopRerollCountUp=1, StaminaRecoverDisable=1, StaminaRecoverFix=1, StaminaRecoverMultiple=1, StaminaRecoverValueDown=1, StaminaRecoverValueUp=1, StaminaReduceFix=1, StaminaReduceMultiple=1, StaminaReduceValueDown=1, StaminaReduceValueUp=1, StaminaSpecify=1, StarPermilUp=1, SupportCardEventParameterAdditionValueUp=1, SupportCardEventProbabilityUp=1, SupportCardEventProducePointAdditionValueUp=1, SupportCardEventStaminaRecoverUp=1, SupportCardProduceCardUpgradeProbabilityUp=1, VisualAddition=1, VisualDown=1, VisualGrowthRateAddition=1, VisualGrowthRateDown=1, VocalAddition=1, VocalDown=1, VocalGrowthRateAddition=1, VocalGrowthRateDown=1
- `ProduceEffectIcon.resourceType`：ProduceCard=2, ProduceDrink=2, ProducePoint=2, Unknown=92
- `ProduceExamAutoCardSelectEvaluation.type`：AutoPlay=42, AutoPlayCompetition=42, ManualPlayAudition=42, ManualPlayLesson=42, ManualPlayLessonHard=42
- `ProduceExamAutoCardSelectEvaluation.examEffectType`：ExamConcentration=105, ExamFullPower=105
- `ProduceExamAutoCardSelectEvaluation.evaluationType`：FullPowerPointCoefficient=70, FullPowerPointValue2Coefficient=70, LessonCoefficient=70
- `ProduceExamAutoEvaluation.type`：AutoPlay=2226, AutoPlayCompetition=2226, ManualPlayAudition=2226, ManualPlayLesson=2226, ManualPlayLessonHard=2226
- `ProduceExamAutoEvaluation.examEffectType`：ExamCardPlayAggressive=1855, ExamConcentration=1855, ExamFullPower=1855, ExamLessonBuff=1855, ExamParameterBuff=1855, ExamReview=1855
- `ProduceExamAutoEvaluation.evaluationType`：Block=210, DrawCardCount=210, ExamAggressiveAdditive=210, ExamAntiDebuff=210, ExamBlockAddDown=210, ExamBlockRestriction=210, ExamBuffConsumptionAdd=210, ExamBuffConsumptionDown=210, ExamCardPlayAggressive=210, ExamConcentration=210, ExamConcentrationCount=210, ExamConcentrationLessonMultipleAdditive=210, ExamEnthusiasticAdditive=210, ExamEnthusiasticMultiple=210, ExamExtraTurn=210, ExamFullPower=210, ExamFullPowerCount=210, ExamFullPowerLessonMultipleAdditive=210, ExamFullPowerPointAdditive=210, ExamFullPowerPointTotal=210, ExamGimmickLessonDebuff=210, ExamGimmickParameterDebuff=210, ExamGimmickSleepy=210, ExamGimmickSlump=210, ExamGrowEffectLessonAddAdditive=210, ExamLessonBuff=210, ExamLessonBuffAdditive=210, ExamLessonValueMultiple=210, ExamLessonValueMultipleDependReviewOrAggressive=210, ExamParameterBuff=210, ExamParameterBuffAdditive=210, ExamParameterBuffTurnEndReduceLock=210, ExamPreservation=210, ExamPreservationCount=210, ExamReview=210, ExamReviewAdditive=210, ExamReviewCountAdd=210, ExamReviewMultiple=210, ExamReviewTurnEndReduceLock=210, ExamStaminaConsumptionAdd=210, ExamStaminaConsumptionDown=210, ExamStaminaConsumptionDownFix=210, HoldCount=210, Parameter=210, ParameterBuffMultiplePerTurn=210, ParameterBuffOverTurn=210, PlayableValueAdd=210, RemainTurn=210, Stamina=210, StanceLock=210, StanceLockConcentration=210, StanceLockFullPower=210, StanceLockPreservation=210
- `ProduceExamAutoGrowEffectEvaluation.type`：AutoPlay=742, AutoPlayCompetition=742, ManualPlayAudition=742, ManualPlayLesson=742, ManualPlayLessonHard=742
- `ProduceExamAutoGrowEffectEvaluation.examEffectType`：ExamConcentration=1855, ExamFullPower=1855
- `ProduceExamAutoGrowEffectEvaluation.growEffectType`：AggressiveAdd=70, AggressiveReduce=70, BlockAdd=70, BlockReduce=70, CardDrawAdd=70, CardDrawReduce=70, CardStatusEnchantChange=70, CostAdd=70, CostAggressiveAdd=70, CostAggressiveReduce=70, CostBuffAdd=70, CostBuffReduce=70, CostFullPowerPointAdd=70, CostFullPowerPointReduce=70, CostLessonBuffAdd=70, CostLessonBuffReduce=70, CostParameterBuffAdd=70, CostParameterBuffMultiplePerTurnAdd=70, CostParameterBuffMultiplePerTurnReduce=70, CostParameterBuffReduce=70, CostPenetrateAdd=70, CostPenetrateReduce=70, CostReduce=70, CostReviewAdd=70, CostReviewReduce=70, EffectAdd=70, EffectChange=70, EffectDelete=70, FullPowerPointAdd=70, FullPowerPointReduce=70, InitialAdd=70, LessonAdd=70, LessonBuffAdd=70, LessonBuffReduce=70, LessonCountAdd=70, LessonCountReduce=70, LessonDependBlockAdd=70, LessonDependExamCardPlayAggressiveAdd=70, LessonDependExamReviewAdd=70, LessonReduce=70, ParameterBuffMultiplePerTurnAdd=70, ParameterBuffMultiplePerTurnReduce=70, ParameterBuffTurnAdd=70, ParameterBuffTurnReduce=70, PlayEffectTriggerChange=70, PlayMovePositionTypeChange=70, PlayTriggerChange=70, ReviewAdd=70, ReviewReduce=70, StaminaConsumptionAddTurnAdd=70, StaminaConsumptionAddTurnReduce=70, StaminaConsumptionDownTurnAdd=70, StaminaConsumptionDownTurnReduce=70
- `ProduceExamAutoPlayProduceCardEvaluation.type`：AutoPlay=589, AutoPlayCompetition=251
- `ProduceExamAutoTriggerEvaluation.type`：AutoPlay=63, AutoPlayCompetition=63, ManualPlayAudition=63, ManualPlayLesson=63, ManualPlayLessonHard=63
- `ProduceExamEffect.effectType`：ExamAddGrowEffect=160, ExamAggressiveAdditive=5, ExamAggressiveAdditiveFix=1, ExamAggressiveReduce=3, ExamAggressiveValueMultiple=4, ExamAntiDebuff=4, ExamBlock=60, ExamBlockAddDown=8, ExamBlockAddMultipleAggressive=23, ExamBlockDependBlockConsumptionSum=3, ExamBlockDependExamReview=2, ExamBlockDown=2, ExamBlockFix=16, ExamBlockPerUseCardCount=13, ExamBlockRestriction=5, ExamBlockValueMultiple=8, ExamCardCreateId=15, ExamCardCreateSearch=8, ExamCardDraw=5, ExamCardDuplicate=1, ExamCardMove=44, ExamCardPlayAggressive=16, ExamCardSearchEffectPlayCountBuff=8, ExamCardUpgrade=13, ExamConcentration=2, ExamConcentrationLessonMultipleAdditive=2, ExamDebuffRecover=3, ExamEffectTimer=138, ExamEnthusiasticAdditive=31, ExamEnthusiasticMultiple=32, ExamExtraTurn=1, ExamForcePlayCardSearch=8, ExamForcePlayCardSearchWithCost=1, ExamFullPower=1, ExamFullPowerLessonMultipleAdditive=3, ExamFullPowerPoint=11, ExamFullPowerPointAdditive=5, ExamFullPowerPointReduce=3, ExamGimmickLessonDebuff=4, ExamGimmickParameterDebuff=10, ExamGimmickPlayCardLimit=26, ExamGimmickSleepy=5, ExamGimmickSlump=4, ExamGimmickStartTurnCardDrawDown=3, ExamHandGraveCountCardDraw=1, ExamItemFireLimitAdd=1, ExamLesson=122, ExamLessonAddMultipleLessonBuff=8, ExamLessonAddMultipleParameterBuff=41, ExamLessonBuff=20, ExamLessonBuffAdditive=11, ExamLessonBuffAdditiveFix=2, ExamLessonBuffDependParameterBuff=11, ExamLessonBuffMultiple=15, ExamLessonBuffPerSearchCount=1, ExamLessonBuffReduce=1, ExamLessonDependBlock=83, ExamLessonDependBlockAndSearchCount=2, ExamLessonDependBlockConsumptionSum=7, ExamLessonDependExamCardPlayAggressive=25, ExamLessonDependExamReview=47, ExamLessonDependParameterBuff=20, ExamLessonDependPlayCardCountSum=11, ExamLessonDependStamina=3, ExamLessonDependStaminaConsumptionSum=7, ExamLessonFix=14, ExamLessonFullPowerPoint=55, ExamLessonPerSearchCount=4, ExamLessonValueMultiple=62, ExamLessonValueMultipleDependReviewOrAggressive=3, ExamLessonValueMultipleDown=10, ExamMultipleEnthusiasticLesson=3, ExamMultipleLessonBuffLesson=104, ExamOverPreservation=1, ExamPanic=3, ExamParameterBuff=17, ExamParameterBuffAdditive=7, ExamParameterBuffDependLessonBuff=4, ExamParameterBuffMultiplePerTurn=12, ExamParameterBuffMultiplePerTurnReduce=1, ExamParameterBuffReduce=2, ExamPlayableValueAdd=3, ExamPreservation=2, ExamReview=18, ExamReviewAdditive=7, ExamReviewCountAdd=1, ExamReviewDependExamBlock=8, ExamReviewDependExamCardPlayAggressive=1, ExamReviewMultiple=18, ExamReviewPerSearchCount=4, ExamReviewReduce=2, ExamReviewValueMultiple=8, ExamSearchPlayCardStaminaConsumptionChange=5, ExamStaminaConsumptionAdd=7, ExamStaminaConsumptionAddFix=4, ExamStaminaConsumptionDown=8, ExamStaminaConsumptionDownFix=4, ExamStaminaDamage=11, ExamStaminaRecoverFix=25, ExamStaminaRecoverMultiple=4, ExamStaminaRecoverRestriction=1, ExamStaminaReduce=5, ExamStaminaReduceFix=7, ExamStanceReset=1, ExamStatusEnchant=448, ExamStatusEnchantEncore=5, StanceLock=2
- `ProduceExamEffect.targetExamEffectType`：Unknown=2070
- `ProduceExamEffect.movePositionType`：DeckFirst=8, DeckLast=5, DeckRandom=11, Grave=5, Hand=24, Hold=13, Lost=4, Unknown=2000
- `ProduceExamEffect.pickRangeType`：All=224, Random=25, Select=17, Unknown=1804
- `ProduceExamEffect.pickCountType`：Shortage=6, Unknown=2064
- `ProduceExamEffect.pickRangeType2`：Unknown=2070
- `ProduceExamEffect.pickCountType2`：Unknown=2070
- `ProduceExamEffect.produceDescriptions.produceDescriptionType`：Exam=2853, PlainText=7049, ProduceCard=189, ProduceCardCategory=137, ProduceCardGrowEffectType=232, ProduceDescription=99, ProduceDescriptionName=543, ProduceExamEffectType=2577
- `ProduceExamEffect.produceDescriptions.examDescriptionType`：CustomizeEffectCount=335, CustomizeEffectValue1=962, CustomizeEffectValue2=29, CustomizeEffectValuePercent1=517, CustomizeEffectValuePercent2=68, CustomizeLessonCountAdd=621, CustomizeTurn=274, ExamCount=5, ExamTurn=42, Unknown=10826
- `ProduceExamEffect.produceDescriptions.examEffectType`：ExamAggressiveAdditive=5, ExamAggressiveAdditiveFix=1, ExamAggressiveReduce=4, ExamAntiDebuff=5, ExamBlock=340, ExamBlockAddDown=9, ExamBlockFix=17, ExamBlockRestriction=7, ExamCardCreateId=31, ExamCardDuplicate=1, ExamCardPlayAggressive=97, ExamCardUpgrade=15, ExamConcentration=47, ExamConcentrationLessonMultipleAdditive=2, ExamDebuffRecover=5, ExamEnthusiasticAdditive=32, ExamEnthusiasticMultiple=33, ExamExtraTurn=2, ExamFullPower=49, ExamFullPowerLessonMultipleAdditive=4, ExamFullPowerPoint=96, ExamFullPowerPointAdditive=7, ExamFullPowerPointReduce=3, ExamGimmickEnthusiastic=3, ExamGimmickLessonDebuff=4, ExamGimmickParameterDebuff=11, ExamGimmickPlayCardLimit=4, ExamGimmickSleepy=5, ExamGimmickSlump=9, ExamGimmickStartTurnCardDrawDown=5, ExamLesson=788, ExamLessonBuff=210, ExamLessonBuffAdditive=12, ExamLessonBuffAdditiveFix=2, ExamLessonBuffMultiple=15, ExamLessonBuffReduce=2, ExamLessonFix=14, ExamLessonValueMultiple=67, ExamLessonValueMultipleDependReviewOrAggressive=3, ExamLessonValueMultipleDown=9, ExamOverPreservation=5, ExamPanic=4, ExamParameterBuff=142, ExamParameterBuffAdditive=7, ExamParameterBuffMultiplePerTurn=17, ExamParameterBuffMultiplePerTurnReduce=2, ExamParameterBuffReduce=7, ExamPlayableValueAdd=86, ExamPreservation=17, ExamReview=183, ExamReviewAdditive=7, ExamReviewCountAdd=2, ExamReviewMultiple=20, ExamReviewReduce=3, ExamStaminaConsumptionAdd=7, ExamStaminaConsumptionAddFix=4, ExamStaminaConsumptionDown=9, ExamStaminaConsumptionDownFix=6, ExamStaminaDamage=11, ExamStaminaRecoverFix=38, ExamStaminaRecoverRestriction=1, ExamStaminaReduceFix=20, ExamStanceReset=2, StanceLock=2, Unknown=11102
- `ProduceExamEffect.produceDescriptions.produceCardGrowEffectType`：BlockAdd=23, CostAdd=32, CostPenetrateAdd=3, CostPenetrateReduce=1, CostReduce=5, FullPowerPointAdd=2, LessonAdd=149, LessonCountAdd=13, LessonReduce=2, ReviewAdd=2, Unknown=13447
- `ProduceExamEffect.produceDescriptions.produceCardCategory`：ActiveSkill=89, MentalSkill=46, Trouble=2, Unknown=13542
- `ProduceExamEffect.produceDescriptions.produceCardMovePositionType`：Unknown=13679
- `ProduceExamEffect.produceDescriptions.produceStepType`：Unknown=13679
- `ProduceExamEffect.produceDescriptions.produceStepBusinessType`：Unknown=13679
- `ProduceExamEffect.customizeProduceDescriptions.produceDescriptionType`：Exam=2853, PlainText=6953, ProduceCard=189, ProduceCardCategory=137, ProduceCardGrowEffectType=232, ProduceDescription=99, ProduceDescriptionName=2219, ProduceExamEffectType=2582
- `ProduceExamEffect.customizeProduceDescriptions.examDescriptionType`：CustomizeEffectCount=340, CustomizeEffectValue1=962, CustomizeEffectValue2=29, CustomizeEffectValuePercent1=517, CustomizeEffectValuePercent2=68, CustomizeLessonCountAdd=621, CustomizeTurn=316, Unknown=12411
- `ProduceExamEffect.customizeProduceDescriptions.examEffectType`：ExamAggressiveAdditive=5, ExamAggressiveAdditiveFix=1, ExamAggressiveReduce=4, ExamAntiDebuff=5, ExamBlock=340, ExamBlockAddDown=9, ExamBlockFix=17, ExamBlockRestriction=7, ExamCardCreateId=31, ExamCardDuplicate=1, ExamCardPlayAggressive=97, ExamCardUpgrade=15, ExamConcentration=47, ExamConcentrationLessonMultipleAdditive=2, ExamDebuffRecover=5, ExamEnthusiasticAdditive=32, ExamEnthusiasticMultiple=33, ExamExtraTurn=2, ExamFullPower=49, ExamFullPowerLessonMultipleAdditive=4, ExamFullPowerPoint=96, ExamFullPowerPointAdditive=7, ExamFullPowerPointReduce=3, ExamGimmickEnthusiastic=3, ExamGimmickLessonDebuff=4, ExamGimmickParameterDebuff=11, ExamGimmickPlayCardLimit=4, ExamGimmickSleepy=5, ExamGimmickSlump=9, ExamGimmickStartTurnCardDrawDown=5, ExamLesson=788, ExamLessonBuff=210, ExamLessonBuffAdditive=12, ExamLessonBuffAdditiveFix=2, ExamLessonBuffMultiple=15, ExamLessonBuffReduce=2, ExamLessonFix=14, ExamLessonValueMultiple=67, ExamLessonValueMultipleDependReviewOrAggressive=3, ExamLessonValueMultipleDown=9, ExamOverPreservation=5, ExamPanic=4, ExamParameterBuff=142, ExamParameterBuffAdditive=7, ExamParameterBuffMultiplePerTurn=17, ExamParameterBuffMultiplePerTurnReduce=2, ExamParameterBuffReduce=7, ExamPlayableValueAdd=86, ExamPreservation=17, ExamReview=183, ExamReviewAdditive=7, ExamReviewCountAdd=2, ExamReviewMultiple=20, ExamReviewReduce=3, ExamStaminaConsumptionAdd=7, ExamStaminaConsumptionAddFix=4, ExamStaminaConsumptionDown=9, ExamStaminaConsumptionDownFix=6, ExamStaminaDamage=11, ExamStaminaRecoverFix=38, ExamStaminaRecoverRestriction=1, ExamStaminaReduceFix=20, ExamStanceReset=2, ExamStatusEnchantEncore=5, StanceLock=2, Unknown=12682
- `ProduceExamEffect.customizeProduceDescriptions.produceCardGrowEffectType`：BlockAdd=23, CostAdd=32, CostPenetrateAdd=3, CostPenetrateReduce=1, CostReduce=5, FullPowerPointAdd=2, LessonAdd=149, LessonCountAdd=13, LessonReduce=2, ReviewAdd=2, Unknown=15032
- `ProduceExamEffect.customizeProduceDescriptions.produceCardCategory`：ActiveSkill=89, MentalSkill=46, Trouble=2, Unknown=15127
- `ProduceExamEffect.customizeProduceDescriptions.produceCardMovePositionType`：Unknown=15264
- `ProduceExamEffect.customizeProduceDescriptions.produceStepType`：Unknown=15264
- `ProduceExamEffect.customizeProduceDescriptions.produceStepBusinessType`：Unknown=15264
- `ProduceExamGimmickEffectGroup.fieldStatusType`：BlockUp=114, CardPlayAggressiveUp=516, ConcentrationChangeCountUp=93, ConcentrationUp=10, ConditionThresholdMultiple=196, ConditionThresholdMultipleDown=20, FullPowerChangeCountUp=22, FullPowerPointGetSumUp=136, LessonBuffUp=534, ParameterBuff=291, ParameterBuffMultiplePerTurnUp=1, ParameterBuffUp=131, PlayCardLesson=33, PlayCardSkill=50, PreservationChangeCountUp=56, PreservationUp=24, ReviewUp=506, StaminaConsumptionDown=24, StaminaLessMultiple=17, StaminaUpMultiple=82, StanceChangeCountUp=60, Unknown=791
- `ProduceExamGimmickEffectGroup.fieldStatusCheckType`：Not=758, Unknown=2949
- `ProduceExamGimmickEffectGroup.produceDescriptions.produceDescriptionType`：Exam=3636, PlainText=11808, ProduceCard=61, ProduceCardCategory=189, ProduceCardGrowEffectType=148, ProduceDescription=201, ProduceDescriptionName=373, ProduceExamEffectType=6114
- `ProduceExamGimmickEffectGroup.produceDescriptions.examDescriptionType`：CustomizeEffectCount=219, CustomizeEffectValue1=2213, CustomizeEffectValue2=4, CustomizeEffectValuePercent1=379, CustomizeEffectValuePercent2=4, CustomizeLessonCountAdd=139, CustomizeTurn=678, Unknown=18894
- `ProduceExamGimmickEffectGroup.produceDescriptions.examEffectType`：ExamAntiDebuff=14, ExamBlock=628, ExamBlockAddDown=10, ExamBlockFix=6, ExamBlockRestriction=15, ExamCardCreateId=61, ExamCardPlayAggressive=758, ExamConcentration=120, ExamDebuffRecover=78, ExamEnthusiasticAdditive=1, ExamExtraTurn=31, ExamFullPower=32, ExamFullPowerLessonMultipleAdditive=1, ExamFullPowerPoint=187, ExamGimmickParameterDebuff=63, ExamGimmickSleepy=10, ExamGimmickSlump=36, ExamGimmickStartTurnCardDrawDown=16, ExamLesson=202, ExamLessonBuff=925, ExamLessonBuffAdditive=3, ExamLessonValueMultiple=293, ExamPanic=38, ExamParameterBuff=658, ExamParameterBuffMultiplePerTurn=35, ExamPlayableValueAdd=143, ExamPreservation=84, ExamReview=899, ExamReviewMultiple=2, ExamStaminaConsumptionAdd=62, ExamStaminaConsumptionAddFix=19, ExamStaminaConsumptionDown=95, ExamStaminaConsumptionDownFix=14, ExamStaminaDamage=480, ExamStaminaRecoverFix=56, ExamStaminaReduceFix=39, Unknown=16416
- `ProduceExamGimmickEffectGroup.produceDescriptions.produceCardGrowEffectType`：CostPenetrateReduce=2, CostReduce=2, LessonAdd=127, LessonCountAdd=17, Unknown=22382
- `ProduceExamGimmickEffectGroup.produceDescriptions.produceCardCategory`：ActiveSkill=94, MentalSkill=95, Unknown=22341
- `ProduceExamGimmickEffectGroup.produceDescriptions.produceCardMovePositionType`：Unknown=22530
- `ProduceExamGimmickEffectGroup.produceDescriptions.produceStepType`：Unknown=22530
- `ProduceExamGimmickEffectGroup.produceDescriptions.produceStepBusinessType`：Unknown=22530
- `ProduceExamStatusEnchant.produceDescriptions.produceDescriptionType`：Exam=7224, PlainText=14188, ProduceCard=428, ProduceCardCategory=394, ProduceCardGrowEffectType=169, ProduceDescription=273, ProduceDescriptionName=1698, ProduceExamEffectType=3782
- `ProduceExamStatusEnchant.produceDescriptions.examDescriptionType`：CustomizeEffectCount=411, CustomizeEffectValue1=1471, CustomizeEffectValue2=12, CustomizeEffectValuePercent1=526, CustomizeEffectValuePercent2=18, CustomizeLessonCountAdd=284, CustomizeTurn=496, ExamCount=2003, ExamTurn=2003, Unknown=20932
- `ProduceExamStatusEnchant.produceDescriptions.examEffectType`：ExamAggressiveAdditive=9, ExamAggressiveReduce=10, ExamAntiDebuff=22, ExamBlock=391, ExamBlockAddDown=16, ExamBlockFix=29, ExamBlockRestriction=29, ExamCardCreateId=34, ExamCardDuplicate=12, ExamCardPlayAggressive=303, ExamCardUpgrade=10, ExamConcentration=125, ExamConcentrationLessonMultipleAdditive=2, ExamDebuffRecover=4, ExamEnthusiasticAdditive=15, ExamEnthusiasticMultiple=11, ExamExtraTurn=21, ExamFullPower=104, ExamFullPowerLessonMultipleAdditive=4, ExamFullPowerPoint=110, ExamFullPowerPointAdditive=12, ExamFullPowerPointReduce=8, ExamGimmickLessonDebuff=12, ExamGimmickParameterDebuff=16, ExamGimmickSleepy=12, ExamGimmickSlump=27, ExamGimmickStartTurnCardDrawDown=14, ExamLesson=361, ExamLessonBuff=292, ExamLessonBuffAdditive=19, ExamLessonBuffMultiple=4, ExamLessonBuffReduce=8, ExamLessonFix=1, ExamLessonValueMultiple=140, ExamLessonValueMultipleDependReviewOrAggressive=4, ExamLessonValueMultipleDown=38, ExamOverPreservation=8, ExamPanic=1, ExamParameterBuff=278, ExamParameterBuffAdditive=6, ExamParameterBuffMultiplePerTurn=48, ExamParameterBuffMultiplePerTurnReduce=1, ExamParameterBuffReduce=10, ExamPlayableValueAdd=234, ExamPreservation=108, ExamReview=368, ExamReviewAdditive=11, ExamReviewCountAdd=1, ExamReviewMultiple=16, ExamReviewReduce=6, ExamStaminaConsumptionAdd=28, ExamStaminaConsumptionAddFix=45, ExamStaminaConsumptionDown=55, ExamStaminaConsumptionDownFix=46, ExamStaminaDamage=4, ExamStaminaRecoverFix=95, ExamStaminaRecoverRestriction=12, ExamStaminaReduceFix=170, ExamStanceReset=2, Unknown=24374
- `ProduceExamStatusEnchant.produceDescriptions.produceCardGrowEffectType`：BlockAdd=12, CostAdd=8, CostPenetrateAdd=4, CostReduce=2, FullPowerPointAdd=4, LessonAdd=125, LessonCountAdd=12, LessonReduce=2, Unknown=27987
- `ProduceExamStatusEnchant.produceDescriptions.produceCardCategory`：ActiveSkill=214, MentalSkill=136, Trouble=44, Unknown=27762
- `ProduceExamStatusEnchant.produceDescriptions.produceCardMovePositionType`：Unknown=28156
- `ProduceExamStatusEnchant.produceDescriptions.produceStepType`：Unknown=28156
- `ProduceExamStatusEnchant.produceDescriptions.produceStepBusinessType`：Unknown=28156
- `ProduceExamTrigger.phaseTypes`：ExamAggressiveUpInterval=1, ExamBuffConsume=7, ExamCardMoveGrave=1, ExamCardMoveHand=1, ExamCardMoveLost=2, ExamCardPlay=82, ExamCardPlayAfter=194, ExamEndTurn=65, ExamEndTurnInterval=2, ExamPlayCountInterval=26, ExamPlayCountIntervalAfter=5, ExamPlayTurnCountInterval=8, ExamSearchCardPlay=2, ExamStaminaReduce=1, ExamStaminaReduceCard=2, ExamStanceChangeConcentration=6, ExamStanceChangeCountInterval=3, ExamStanceChangeFromConcentration=1, ExamStanceChangeFromFullPower=5, ExamStanceChangeFullPower=6, ExamStanceChangePreservation=1, ExamStartExam=12, ExamStartTurn=95, ExamStatusChange=28, ExamTurnInterval=12, ExamTurnSkip=2, ExamTurnTimer=19, None=63, StartExamPlay=1, StartPlay=23
- `ProduceExamTrigger.fieldStatusCheckTypes`：Not=37
- `ProduceExamTrigger.fieldStatusTypes`：BlockUp=33, CardPlayAggressiveUp=34, CardSearchCountUp=19, ConcentrationChangeCountUp=10, ConcentrationUp=17, ConditionThresholdMultiple=2, ConditionThresholdMultipleDown=3, FullPowerChangeCountUp=3, FullPowerPointGetSumUp=9, FullPowerPointUp=13, FullPowerUp=21, LessonBuffUp=43, NoBlock=6, NoStance=4, ParameterBuff=10, ParameterBuffMultiplePerTurnUp=7, ParameterBuffUp=43, PlayCardLesson=2, PlayCardSkill=2, PreservationChangeCountUp=7, PreservationUp=16, RemainingTurn=14, ReviewUp=45, StaminaConsumptionDown=6, StaminaLessMultiple=14, StaminaUpMultiple=24, StanceChangeCountUp=6, TurnProgressUp=5
- `ProduceExamTrigger.cardMovePositionType`：Unknown=676
- `ProduceExamTrigger.effectTypes`：ExamBlock=3, ExamCardPlayAggressive=5, ExamConcentration=1, ExamFullPowerPoint=4, ExamLessonBuff=5, ExamLessonDependBlock=1, ExamParameterBuff=5, ExamReview=5
- `ProduceExamTrigger.lessonType`：LessonDance=18, LessonSp=1, LessonVisual=17, LessonVocal=7, Unknown=633
- `ProduceExamTrigger.produceDescriptions.produceDescriptionType`：PlainText=1032, ProduceCard=138, ProduceCardCategory=73, ProduceDescription=59, ProduceDescriptionName=65, ProduceExamEffectType=410
- `ProduceExamTrigger.produceDescriptions.examDescriptionType`：Unknown=1777
- `ProduceExamTrigger.produceDescriptions.examEffectType`：ExamBlock=47, ExamCardPlayAggressive=41, ExamConcentration=44, ExamFullPower=35, ExamFullPowerPoint=26, ExamLesson=1, ExamLessonBuff=54, ExamParameterBuff=60, ExamParameterBuffMultiplePerTurn=10, ExamPreservation=27, ExamReview=56, ExamStaminaConsumptionDown=7, ExamStaminaRecoverFix=2, Unknown=1367
- `ProduceExamTrigger.produceDescriptions.produceCardGrowEffectType`：Unknown=1777
- `ProduceExamTrigger.produceDescriptions.produceCardCategory`：ActiveSkill=41, MentalSkill=27, Trouble=5, Unknown=1704
- `ProduceExamTrigger.produceDescriptions.produceCardMovePositionType`：Unknown=1777
- `ProduceExamTrigger.produceDescriptions.produceStepType`：Unknown=1777
- `ProduceExamTrigger.produceDescriptions.produceStepBusinessType`：Unknown=1777
- `ProduceExamTrigger.playProduceDescriptions.produceDescriptionType`：PlainText=726, ProduceCard=2, ProduceCardCategory=9, ProduceDescription=12, ProduceDescriptionName=16, ProduceExamEffectType=321
- `ProduceExamTrigger.playProduceDescriptions.examDescriptionType`：Unknown=1086
- `ProduceExamTrigger.playProduceDescriptions.examEffectType`：ExamBlock=39, ExamCardPlayAggressive=34, ExamConcentration=27, ExamFullPower=23, ExamFullPowerPoint=22, ExamLessonBuff=43, ExamParameterBuff=52, ExamParameterBuffMultiplePerTurn=7, ExamPreservation=23, ExamReview=45, ExamStaminaConsumptionDown=6, Unknown=765
- `ProduceExamTrigger.playProduceDescriptions.produceCardGrowEffectType`：Unknown=1086
- `ProduceExamTrigger.playProduceDescriptions.produceCardCategory`：ActiveSkill=2, MentalSkill=2, Trouble=5, Unknown=1077
- `ProduceExamTrigger.playProduceDescriptions.produceCardMovePositionType`：Unknown=1086
- `ProduceExamTrigger.playProduceDescriptions.produceStepType`：Unknown=1086
- `ProduceExamTrigger.playProduceDescriptions.produceStepBusinessType`：Unknown=1086
- `ProduceExamTrigger.playEffectProduceDescriptions.produceDescriptionType`：PlainText=726, ProduceCard=2, ProduceCardCategory=9, ProduceDescription=12, ProduceDescriptionName=16, ProduceExamEffectType=321
- `ProduceExamTrigger.playEffectProduceDescriptions.examDescriptionType`：Unknown=1086
- `ProduceExamTrigger.playEffectProduceDescriptions.examEffectType`：ExamBlock=39, ExamCardPlayAggressive=34, ExamConcentration=27, ExamFullPower=23, ExamFullPowerPoint=22, ExamLessonBuff=43, ExamParameterBuff=52, ExamParameterBuffMultiplePerTurn=7, ExamPreservation=23, ExamReview=45, ExamStaminaConsumptionDown=6, Unknown=765
- `ProduceExamTrigger.playEffectProduceDescriptions.produceCardGrowEffectType`：Unknown=1086
- `ProduceExamTrigger.playEffectProduceDescriptions.produceCardCategory`：ActiveSkill=2, MentalSkill=2, Trouble=5, Unknown=1077
- `ProduceExamTrigger.playEffectProduceDescriptions.produceCardMovePositionType`：Unknown=1086
- `ProduceExamTrigger.playEffectProduceDescriptions.produceStepType`：Unknown=1086
- `ProduceExamTrigger.playEffectProduceDescriptions.produceStepBusinessType`：Unknown=1086
- `ProduceGrade.grade`：A=3, APlus=3, B=3, BPlus=3, C=3, CPlus=3, D=3, E=3, F=3, S=3, SPlus=3, Ss=3, SsPlus=3, Sss=3, SssPlus=3, Ssss=2, SsssPlus=1, Sssss=1
- `ProduceGroup.type`：FirstStar=1, HatsuboshiIdolFestival=1, NextIdolAudition=1
- `ProduceGroup.disableForceLiveCommonEndingLiveType`：TrueEnd=2, Unknown=1
- `ProduceGroup.limitGrade`：SssPlus=1, Ssss=1, Sssss=1
- `ProduceGroupLiveCommon.type`：A=36, B=13, C=13, D=13, TrueEnd=26
- `ProduceGrowthPanel.produceSplitType`：Final=12, Selection=6, Unknown=32
- `ProduceGrowthPanel.produceDescriptions.produceDescriptionType`：DiffText=65, PlainText=92, ProduceDescription=15
- `ProduceGrowthPanel.produceDescriptions.examDescriptionType`：Unknown=172
- `ProduceGrowthPanel.produceDescriptions.examEffectType`：Unknown=172
- `ProduceGrowthPanel.produceDescriptions.produceCardGrowEffectType`：Unknown=172
- `ProduceGrowthPanel.produceDescriptions.produceCardCategory`：Unknown=172
- `ProduceGrowthPanel.produceDescriptions.produceCardMovePositionType`：Unknown=172
- `ProduceGrowthPanel.produceDescriptions.produceStepType`：Unknown=172
- `ProduceGrowthPanel.produceDescriptions.produceStepBusinessType`：Unknown=172
- `ProduceGrowthPanelSheet.produceType`：HatsuboshiIdolFestival=1
- `ProduceHighScore.produceHighScoreEventType`：Normal=4, Rush=15
- `ProduceInitialDeck.examEffectType`：ExamCardPlayAggressive=8, ExamConcentration=8, ExamFullPower=8, ExamLessonBuff=8, ExamParameterBuff=8, ExamReview=8
- `ProduceItem.rarity`：N=318, R=105, Sr=171, Ssr=444
- `ProduceItem.planType`：Common=169, Plan1=308, Plan2=327, Plan3=234
- `ProduceItem.produceDescriptions.produceDescriptionType`：DiffText=456, Exam=1421, PlainText=9769, ProduceCard=74, ProduceCardCategory=179, ProduceCardGrowEffectType=95, ProduceDescription=302, ProduceDescriptionName=3781, ProduceDrink=1, ProduceExamEffectType=1853, ProduceStepBusinessType=39
- `ProduceItem.produceDescriptions.examDescriptionType`：CustomizeEffectCount=79, CustomizeEffectValue1=721, CustomizeEffectValue2=4, CustomizeEffectValuePercent1=259, CustomizeEffectValuePercent2=9, CustomizeLessonCountAdd=87, CustomizeTurn=262, Unknown=16549
- `ProduceItem.produceDescriptions.examEffectType`：ExamAggressiveAdditive=5, ExamAggressiveReduce=5, ExamAntiDebuff=11, ExamBlock=192, ExamBlockAddDown=8, ExamBlockFix=12, ExamBlockRestriction=15, ExamCardCreateId=17, ExamCardDuplicate=6, ExamCardPlayAggressive=166, ExamCardUpgrade=5, ExamConcentration=74, ExamConcentrationLessonMultipleAdditive=2, ExamEnthusiasticAdditive=8, ExamEnthusiasticMultiple=6, ExamExtraTurn=10, ExamFullPower=68, ExamFullPowerLessonMultipleAdditive=3, ExamFullPowerPoint=52, ExamFullPowerPointAdditive=6, ExamFullPowerPointReduce=4, ExamGimmickLessonDebuff=6, ExamGimmickParameterDebuff=8, ExamGimmickSleepy=6, ExamGimmickSlump=11, ExamGimmickStartTurnCardDrawDown=6, ExamLesson=119, ExamLessonBuff=153, ExamLessonBuffAdditive=10, ExamLessonBuffMultiple=4, ExamLessonBuffReduce=4, ExamLessonValueMultiple=87, ExamLessonValueMultipleDependReviewOrAggressive=2, ExamLessonValueMultipleDown=22, ExamOverPreservation=2, ExamParameterBuff=157, ExamParameterBuffAdditive=4, ExamParameterBuffMultiplePerTurn=26, ExamParameterBuffReduce=3, ExamPlayableValueAdd=50, ExamPreservation=64, ExamReview=181, ExamReviewAdditive=7, ExamReviewMultiple=7, ExamReviewReduce=3, ExamStaminaConsumptionAdd=14, ExamStaminaConsumptionAddFix=26, ExamStaminaConsumptionDown=27, ExamStaminaConsumptionDownFix=26, ExamStaminaDamage=2, ExamStaminaRecoverFix=47, ExamStaminaRecoverRestriction=6, ExamStaminaReduceFix=87, ExamStanceReset=1, Unknown=16117
- `ProduceItem.produceDescriptions.produceCardGrowEffectType`：BlockAdd=6, CostAdd=4, CostPenetrateAdd=2, CostReduce=1, FullPowerPointAdd=2, LessonAdd=73, LessonCountAdd=6, LessonReduce=1, Unknown=17875
- `ProduceItem.produceDescriptions.produceCardCategory`：ActiveSkill=93, MentalSkill=59, Trouble=27, Unknown=17791
- `ProduceItem.produceDescriptions.produceCardMovePositionType`：Unknown=17970
- `ProduceItem.produceDescriptions.produceStepType`：Unknown=17970
- `ProduceItem.produceDescriptions.produceStepBusinessType`：ProduceCard=13, ProduceDrink=13, ProducePoint=13, Unknown=17931
- `ProduceItemEffect.effectType`：ExamStatusEnchant=693, ProduceEffect=238
- `ProduceLegendProduceCard.examEffectType`：ExamCardPlayAggressive=1, ExamConcentration=1, ExamFullPower=1, ExamLessonBuff=1, ExamParameterBuff=1, ExamReview=1
- `ProduceLive.type`：A=13, B=13, C=13, D=13, TrueEnd=264
- `ProduceLiveEvaluation.liveType`：A=88, B=52, C=52, D=52, E=78, TrueEnd=88
- `ProduceResultMotion.liveType`：A=108, B=26, C=26, D=46, TrueEnd=108
- `ProduceScheduleBackground.locationType`：Classroom=1, Classroom2=1, Classroom3=1, Courtyard=1, Courtyard2=1, Courtyard3=1, ProducerRoom1=1, ProducerRoom2=1, ProducerRoom3=1, ProducerRoom4=1, ProducerRoom5=1, ProducerRoom6=1, Rooftop=1, Rooftop2=1, Rooftop3=1
- `ProduceScheduleMotion.locationType`：Classroom=143, Classroom2=143, Classroom3=70, Courtyard=52, Courtyard2=52, Courtyard3=40, ProducerRoom1=78, ProducerRoom2=91, ProducerRoom3=52, ProducerRoom4=91, ProducerRoom5=40, ProducerRoom6=70, Rooftop=52, Rooftop2=52, Rooftop3=40
- `ProduceScheduleMotion.staminaMotionType`：Enough=798, NotEnough=268
- `ProduceScheduleMotion.motionType`：Reaction=684, ReactionOnce=65, Wait1=252, Wait2=65
- `ProduceSeasonZeroGrade.grade`：A=2, APlus=2, B=2, BPlus=2, C=2, CPlus=2, D=2, E=2, F=2, S=2, SPlus=2, Ss=2, SsPlus=2, Sss=2, SssPlus=2
- `ProduceSkill.rarity`：R=381, Sr=393, Ssr=707, Ur=7
- `ProduceSkill.planType`：Common=1326, Plan1=54, Plan2=54, Plan3=54
- `ProduceSkill.produceType`：HatsuboshiIdolFestival=115, Unknown=1373
- `ProduceSkill.produceSplitType`：Final=10, Unknown=1478
- `ProduceSkill.produceDescriptions.produceDescriptionType`：DiffText=1160, Exam=329, PlainText=4084, ProduceCard=188, ProduceCardCategory=62, ProduceCardGrowEffectType=27, ProduceDescription=313, ProduceDescriptionName=278, ProduceExamEffectType=313
- `ProduceSkill.produceDescriptions.examDescriptionType`：CustomizeEffectCount=176, CustomizeEffectValue1=108, CustomizeTurn=45, Unknown=6425
- `ProduceSkill.produceDescriptions.examEffectType`：ExamBlock=24, ExamCardPlayAggressive=29, ExamFullPowerPoint=9, ExamLessonBuff=41, ExamParameterBuff=36, ExamPlayableValueAdd=71, ExamPreservation=39, ExamReview=46, ExamStaminaConsumptionDown=18, Unknown=6441
- `ProduceSkill.produceDescriptions.produceCardGrowEffectType`：LessonAdd=27, Unknown=6727
- `ProduceSkill.produceDescriptions.produceCardCategory`：ActiveSkill=27, MentalSkill=35, Unknown=6692
- `ProduceSkill.produceDescriptions.produceCardMovePositionType`：Unknown=6754
- `ProduceSkill.produceDescriptions.produceStepType`：Unknown=6754
- `ProduceSkill.produceDescriptions.produceStepBusinessType`：Unknown=6754
- `ProduceSplitAdv.produceType`：HatsuboshiIdolFestival=24
- `ProduceSplitAdv.type`：BeforeFinalAuditionRefresh=2, BeforeMid1AuditionRefresh=2, BeforeMid2AuditionRefresh=1, Opening=6, ProduceResultA=2, ProduceResultB=2, ProduceResultC=2, ProduceResultFailedFinal=2, ProduceResultFailedMid1=2, ProduceResultFailedMid2=1, ProduceResultTrueEnd=2
- `ProduceSplitAdv.produceSplitTypes`：Final=12, Selection=12
- `ProduceStartMotion.motionType`：Reaction=26, Wait=13
- `ProduceStepAuditionCharacter.stepType`：AuditionFinal=52, AuditionMid1=39, AuditionMid2=39
- `ProduceStepAuditionCharacterBgm.stepType`：AuditionFinal=18, AuditionMid1=18, AuditionMid2=8
- `ProduceStepAuditionCharacterUnitMotion.stepType`：AuditionFinal=26, AuditionMid1=28, AuditionMid2=12
- `ProduceStepAuditionCharacterUnitMotion.motionType`：Failure=10, PreResult=2, Result1=20, Result2=12, Result3=12, Start=10
- `ProduceStepAuditionDifficulty.stepType`：AuditionFinal=1810, AuditionMid1=1544, AuditionMid2=905
- `ProduceStepAuditionDifficulty.auditionType`：FinalEasy=266, FinalHard=266, FinalNormal=266, FinalVeryHard=266, Mid1Easy=266, Mid1Hard=266, Mid1Normal=266, Mid2Easy=266, Mid2Hard=266, Mid2Normal=266, Unknown=1599
- `ProduceStepAuditionMotion.stepType`：AuditionFinal=390, AuditionMid1=325, AuditionMid2=151
- `ProduceStepAuditionMotion.motionType`：Failure=118, PreResult=10, Result1=295, Result2=164, Result3=164, Start=115
- `ProduceStepAuditionMotion.auditionType`：FinalVeryHard=65, Unknown=801
- `ProduceStepAuditionRivalActor.stepType`：AuditionFinal=10
- `ProduceStepAuditionRivalActorMotion.motionType`：PreResult=2
- `ProduceStepEventDetail.suggestionType`：Primary=6888
- `ProduceStepEventDetail.eventType`：Activity=529, Business=3444, Character=760, CharacterGrowth=39, IdolCard=339, School=1188, SupportCard=511, Unknown=78
- `ProduceStepEventDetail.eventCharacterType`：AfterAuditionFinal=122, AfterAuditionMid1=162, AfterAuditionMid2=53, AfterStep1=42, AfterStep2=42, AfterStepBeforeAuditionFinal=1, AfterStepBeforeAuditionMid1=2, AfterStepBeforeAuditionMid2=1, BeforeAuditionFinal=14, BeforeAuditionMid1=27, BeforeAuditionMid2=13, Ending=112, Failure=43, Opening=126, Unknown=6128
- `ProduceStepEventDetail.produceDescriptions.produceDescriptionType`：DiffText=4533, PlainText=5067, ProduceCard=57, ProduceCardCategory=2, ProduceDescription=124, ProduceItem=197
- `ProduceStepEventDetail.produceDescriptions.examDescriptionType`：Unknown=9980
- `ProduceStepEventDetail.produceDescriptions.examEffectType`：Unknown=9980
- `ProduceStepEventDetail.produceDescriptions.produceCardGrowEffectType`：Unknown=9980
- `ProduceStepEventDetail.produceDescriptions.produceCardCategory`：Trouble=2, Unknown=9978
- `ProduceStepEventDetail.produceDescriptions.produceCardMovePositionType`：Unknown=9980
- `ProduceStepEventDetail.produceDescriptions.produceStepType`：Unknown=9980
- `ProduceStepEventDetail.produceDescriptions.produceStepBusinessType`：Unknown=9980
- `ProduceStepEventSuggestion.stepType`：EventActivity=2, LessonDanceNormal=131, LessonVisualNormal=131, LessonVocalNormal=131, Unknown=2671
- `ProduceStepEventSuggestion.successStepType`：EventActivity=26, Unknown=3040
- `ProduceStepEventSuggestion.failStepType`：Unknown=3066
- `ProduceStepEventSuggestion.produceDescriptions.produceDescriptionType`：DiffText=2954, PlainText=6186, ProduceCard=1, ProduceCardCategory=122, ProduceDescription=423
- `ProduceStepEventSuggestion.produceDescriptions.examDescriptionType`：Unknown=9686
- `ProduceStepEventSuggestion.produceDescriptions.examEffectType`：Unknown=9686
- `ProduceStepEventSuggestion.produceDescriptions.produceCardGrowEffectType`：Unknown=9686
- `ProduceStepEventSuggestion.produceDescriptions.produceCardCategory`：ActiveSkill=11, Trouble=111, Unknown=9564
- `ProduceStepEventSuggestion.produceDescriptions.produceCardMovePositionType`：Unknown=9686
- `ProduceStepEventSuggestion.produceDescriptions.produceStepType`：Unknown=9686
- `ProduceStepEventSuggestion.produceDescriptions.produceStepBusinessType`：Unknown=9686
- `ProduceStepFanPresentMotion.motionType`：Reaction=26, Wait=13
- `ProduceStepOpenLesson.subParameterType`：Dance=16, Visual=16, Vocal=16
- `ProduceStepOpenLessonMotion.stepType`：OpenLessonDanceNormal=20, OpenLessonDanceNormalStar=40, OpenLessonDanceSp=40, OpenLessonDanceSpStar=40, OpenLessonVisualNormal=20, OpenLessonVisualNormalStar=40, OpenLessonVisualSp=60, OpenLessonVisualSpStar=40, OpenLessonVocalNormal=20, OpenLessonVocalNormalStar=40, OpenLessonVocalSp=24, OpenLessonVocalSpStar=40
- `ProduceStepSelfLessonMotion.stepType`：SelfLessonDanceNormal=78, SelfLessonDanceSp=52, SelfLessonVisualNormal=78, SelfLessonVisualSp=78, SelfLessonVocalNormal=78, SelfLessonVocalSp=52
- `ProduceStepTransition.stepType`：Business=104, EventActivity=164, EventSchool=104, FanPresent=46, LessonDanceNormal=182, LessonDanceSp=182, LessonVisualNormal=182, LessonVisualSp=182, LessonVocalNormal=182, LessonVocalSp=182, OpenLessonDanceNormal=112, OpenLessonDanceNormalStar=80, OpenLessonDanceSp=112, OpenLessonDanceSpStar=80, OpenLessonVisualNormal=112, OpenLessonVisualNormalStar=80, OpenLessonVisualSp=112, OpenLessonVisualSpStar=80, OpenLessonVocalNormal=112, OpenLessonVocalNormalStar=80, OpenLessonVocalSp=112, OpenLessonVocalSpStar=80, Present=52, Refresh=46, SelfLessonDanceNormal=78, SelfLessonDanceSp=78, SelfLessonVisualNormal=78, SelfLessonVisualSp=78, SelfLessonVocalNormal=78, SelfLessonVocalSp=78
- `ProduceStepTransition.stepPhaseType`：After=1318, Before=1910
- `ProduceStory.type`：Character=686, CharacterGrowth=39, IdolCard=339, StepActivityEvent=306, StepBusinessEvent=624, StepSchoolEvent=383, SupportCard=511, Unknown=453
- `ProduceTrigger.phaseType`：BuyShopItemProduceCard=1, BuyShopItemProduceDrink=1, ChangeProduceCard=1, CustomizeProduceCard=1, DeleteProduceCard=3, EndAudition=3, EndBeforeAuditionRefresh=5, EndLesson=36, EndLessonBeforePresent=7, EndPresent=2, EndShop=1, EndStepEventActivity=6, EndStepEventBusiness=4, EndStepEventSchool=6, GetProduceCard=46, GetProduceDrink=1, GetProduceItem=1, ProduceStart=3, StartAudition=4, StartAuditionFinal=1, StartAuditionMid1=1, StartAuditionMid2=1, StartCustomize=9, StartLesson=13, StartPresent=5, StartRefresh=1, StartShop=5, Unknown=1, UpgradeProduceCard=7
- `ProducerLevel.reward.resourceType`：Item=64, JewelTotal=16
- `ProducerLevel.unlockTargets.type`：ProduceCard=118, ProduceCardConversion=21, ProduceCardExcludeCount=1, ProduceCardSelectRerollCount=1, ProduceDrink=18, ShopProduceCardDelete=1, ShopProduceCardUpgrade=1
- `ProducerRankingRankGrade.grade`：Bronze=4, Gold=4, Normal=4, Rainbow=4, RainbowPlus=4, Silver=4
- `PvpRateCommonProduceCard.planType`：Plan1=1, Plan2=1, Plan3=1
- `PvpRateConfig.stages.stageType`：_1=51, _2=51, _3=51
- `PvpRateConfig.stages.planType`：Common=18, Plan1=50, Plan2=52, Plan3=33
- `PvpRateMotion.motionType`：Lose=26, Win=26
- `PvpRateUnitSlotUnlock.grade`：_1=1, _2=1, _3=1, _4=1, _5=1, _6=1, _7=1, _8=1
- `ResultGradePattern.type`：ProduceIdolCardParameter=15, ProduceScore=19, ProduceStar=11, ProduceVoteCount=15
- `ResultGradePattern.grade`：A=4, APlus=4, B=4, BPlus=4, C=4, CPlus=4, D=4, E=4, F=4, S=4, SPlus=4, Ss=3, SsPlus=3, Sss=3, SssPlus=3, Ssss=1, SsssPlus=1, Sssss=1, SssssPlus=1
- `Rule.type`：CommercialTransaction=3, Copyright=15, FundSettlement=3, PrereleaseMaintenance=2
- `Rule.platformType`：Android=8, Dmm=7, Ios=8
- `SeminarExamTransition.examEffectType`：ExamCardPlayAggressive=2, ExamConcentration=2, ExamFullPower=2, ExamLessonBuff=2, ExamParameterBuff=2, ExamReview=2
- `SeminarExamTransition.rewards`：JewelTotal=12
- `SeminarExamTransition.rewards.resourceType`：JewelTotal=12
- `Shop.type`：Costume=1, Jewel=1, Pack=1, Pass=1, WebStore=1
- `Shop.resetTimingType`：Never=5
- `Shop.resetWeekday`：Unknown=5
- `ShopItem.labelTypes`：Recommend=105, Sale=21
- `ShopItem.rewards.resourceType`：Costume=102, CostumeHead=82, IdolCardSkin=9, Item=196, MeishiBaseAsset=8, MeishiIllustrationAsset=4, MissionPassPremiumPass=29, SupportCard=2
- `ShopItem.resetTimingType`：Daily=1, Monthly=3, Never=273, Weekly=3
- `ShopItem.resetWeekday`：Monday=3, Unknown=277
- `ShopItem.consumptionResourceType`：Unknown=280
- `Story.type`：AprilFool=11, Birthday=26, CampaignDearnessStory=10, ExtraDearnessStory=11, GvgRaid=5, Main=66, StoryEvent=120, Tour=19
- `Story.reward.resourceType`：JewelTotal=1, Music=2, Unknown=265
- `StoryEvent.storyEventType`：BoxGasha=11, GuildMission=2, MainStory=10, Normal=11
- `StoryGroup.storyType`：AprilFool=3, DearnessStory=49, ExtraDearnessStory=1, GvgRaid=1, Main=14, StoryEvent=24, Tour=4
- `StoryGroup.storyEventType`：BoxGasha=11, GuildMission=2, Normal=11, Unknown=72
- `StoryGroup.eventStoryFilterType`：GvgRaid=1, SeasonEvent=11, StoryEvent=13, Tour=4, Unknown=67
- `SupportCard.type`：Assist=4, Dance=63, Visual=67, Vocal=67
- `SupportCard.planType`：Common=73, Plan1=39, Plan2=50, Plan3=39
- `SupportCard.rarity`：R=13, Sr=79, Ssr=109
- `SupportCard.exchangeReward.resourceType`：Item=201
- `SupportCard.produceCardUpgradeLessonParameterType`：Dance=63, Unknown=4, Visual=67, Vocal=67
- `SupportCard.upgradeProduceCardProduceDescriptions.produceDescriptionType`：PlainText=201
- `SupportCard.upgradeProduceCardProduceDescriptions.examDescriptionType`：Unknown=201
- `SupportCard.upgradeProduceCardProduceDescriptions.examEffectType`：Unknown=201
- `SupportCard.upgradeProduceCardProduceDescriptions.produceCardGrowEffectType`：Unknown=201
- `SupportCard.upgradeProduceCardProduceDescriptions.produceCardCategory`：Unknown=201
- `SupportCard.upgradeProduceCardProduceDescriptions.produceCardMovePositionType`：Unknown=201
- `SupportCard.upgradeProduceCardProduceDescriptions.produceStepType`：Unknown=201
- `SupportCard.upgradeProduceCardProduceDescriptions.produceStepBusinessType`：Unknown=201
- `SupportCardBonus.rarity`：R=4, Sr=5, Ssr=6
- `SupportCardLevelLimit.rank`：Unknown=3, _1=3, _2=3, _3=3, _4=3
- `SupportCardProduceSkillFilter.produceEffectTypes`：DanceAddition=35, DanceGrowthRateAddition=1, LessonDanceSpChangeRatePermilAddition=1, LessonPresentProducePointUp=1, LessonSpChangeRatePermilAddition=3, LessonVisualSpChangeRatePermilAddition=1, LessonVocalSpChangeRatePermilAddition=1, MaxStaminaAddition=1, ProducePointAdditionDisableTrigger=1, ShopProduceDrinkPriceDiscountMultiple=1, StaminaRecoverFix=3, VisualAddition=35, VisualGrowthRateAddition=1, VocalAddition=35, VocalGrowthRateAddition=1
- `Terms.type`：GlobalConsent=1, PrivacyPolicy=1, TermsOfService=1
- `Tips.type`：Comic=23, Help=6, World=1
- `Tips.viewAreaType`：OutGame=6, Produce=1, Unknown=23
- `TowerTotalClearRankReward.reward.resourceType`：Item=6, MeishiIllustrationAsset=1, UserExp=90
- `Tutorial.tutorialType`：Achievement=1, CoinGasha=1, CompetitionPreOpen=1, DearnessPoint=1, DearnessTop=1, Friend=1, GameStart=122, Guild=1, GvgRaid=1, IdolCard=1, IdolCardLevelLimitRankUpdate=1, IdolCardSkin=1, IdolCardSkinUnit=1, MainTask=1, Meishi=1, MeishiEditCustom=1, MeishiEditCustomManual=1, MissionPanel=1, MissionPass=1, MoneyReceive=1, Photo=1, PhotoIdol=1, PhotoPrepare=1, PhotoTop=1, PrimaStella=1, ProduceBeforeLiveEvaluation=1, ProduceCardConvert=1, ProduceCardDelete=1, ProduceCardUpgrade=1, ProduceChallenge=1, ProduceCustomizeItemCustomizeEffect=1, ProduceDifficultySelect=1, ProduceEvent=1, ProduceExamGimmick=3, ProduceExamPerfect=1, ProduceGrowthPanelTop=8, ProduceHatsuboshiIdolFestivalFinalSchedule=1, ProduceHatsuboshiIdolFestivalFinalStepAuditionMid1=1, ProduceHatsuboshiIdolFestivalFinalTop=1, ProduceHatsuboshiIdolFestivalSelectionSchedule=1, ProduceHatsuboshiIdolFestivalStepSchool=1, ProduceHatsuboshiIdolFestivalTop=1, ProduceHighScore=1, ProduceIdolCardSelect=1, ProduceLegendTop=1, ProduceMemorySelect=1, ProduceNextIdolAuditionMaster=1, ProduceNextIdolAuditionMasterRanking=1, ProduceNextIdolAuditionResult=1, ProduceNextIdolAuditionSchedule=1, ProduceNextIdolAuditionStepAuditionSelect=1, ProduceNextIdolAuditionStepAuditionStart=1, ProduceNextIdolAuditionTop=1, ProducePresentStep=1, ProduceSchedule=1, ProduceSelectionMemoryCreate=1, ProduceSelectionMemorySelect=1, ProduceShopStep=1, ProduceStepBusiness=1, ProduceStepCustomize=1, ProduceStepFanPresent=1, ProduceStepOpenLesson=1, ProduceSupportCardSelect=1, ProducerRanking=1, Profile=1, PvpRate=7, Research=1, StoryEvent=1, StoryEventBoxGasha=1, StoryEventGuildMission=1, StoryEventMainStroy=1, SupportCardLevelUpdate=1, Tour=1, Tower=1, TutorialReceiveIdolCard=1, Work=1
- `Tutorial.navigationType`：Adv=10, Arrow=41, Character=6, Focus=55, Tips=96, Unknown=8
- `Tutorial.navigationPositionType`：Lower=3, Top=3, Unknown=162, Upper=48
- `Tutorial.tutorialProduceCommandType`：CheckBeforeLiveProduceEvaluation=1, Next=19, Result=4, Start=1, StepAuditionEnd=1, StepAuditionExamEnd=9, StepLessonEnd=76, StepPresentReceive=5, Unknown=100
- `TutorialCharacterVoice.type`：Random=18, Select=3
- `TutorialProduce.tutorialType`：GameStart=3
- `TutorialProduceStep.tutorialType`：GameStart=12
- `TutorialProduceStep.stepType`：AuditionFinal=3, LessonDanceNormal=3, LessonVisualNormal=2, LessonVocalNormal=1, Refresh=3
- `VoiceRoster.type`：Home=689, Other=397, Produce=829
- `Work.type`：LiveStreaming=1, MiniLive=1
- `Work.rewardResourceType`：Item=2
- `WorkLevel.type`：LiveStreaming=12, MiniLive=12
- `WorkLevelReward.type`：LiveStreaming=1368, MiniLive=1368
- `WorkMotion.motionType`：CharacterSelectReaction=13, CharacterSelectWait=13, FinishExcellent=13, FinishNormal=13, StartFine=13, StartNormal=13
- `WorkTime.type`：LiveStreaming=3, MiniLive=3
