# 学マス 术语表（JP / CN / EN / master-data 枚举 / 代码标识符）

> 规范：代码标识符使用 snake_case（Python）；枚举名去掉 `ProduceExamEffectType_` / `ProduceStepType_` / `ProduceEffectType_` 前缀时在“枚举”列注明前缀缩写：`EET`=ProduceExamEffectType、`PST`=ProduceStepType、`PET`=ProduceEffectType、`PPT`=ProduceExamPhaseType、`AET`=ProduceExamAutoEvaluationType、`Label`=ProduceDescriptionLabel.id。官方日文名以 `ProduceDescriptionLabel.name` 为准（`[確認:master]`）；EN 列优先采用 gakumas-tools engine 的字段名以便对拍。

## A. 对局资源 / 基本量

| JP | CN | EN | 枚举 | 代码标识符 |
|---|---|---|---|---|
| 体力 | 体力 | stamina | Label_ExamStaminaReduceFix(消费) | `stamina` |
| 最大体力 | 最大体力 | max stamina | PET_MaxStaminaAddition | `max_stamina` |
| 元気 | 元气 | genki (vitality) | EET_ExamBlock / Label_ExamBlock | `genki` |
| 固定元気 | 固定元气 | fixed genki | EET_ExamBlockFix | `fixed_genki` |
| パラメータ | 参数（课程得分） | parameter / score | EET_ExamLesson | `score` |
| スコア | 分数（考试得分） | score | — | `score` |
| スコアボーナス | 分数加成% | score bonus (type multiplier) | ProduceExamBattleScoreConfig.*Permil | `type_multiplier` |
| Pポイント | P点数 | produce points | PET_ProducePointAddition | `p_points` |
| ターン | 回合 | turn | ProduceExamBattleConfig.turn | `turn` |
| 残りターン | 剩余回合 | turns remaining | AET_RemainTurn | `turns_remaining` |
| ターン追加 | 追加回合 | extra turn | EET_ExamExtraTurn | `extra_turns` |
| ボーカル / ダンス / ビジュアル | 歌唱 / 舞蹈 / 视觉 | vocal / dance / visual | ProduceParameterType_Vocal/Dance/Visual | `vocal`,`dance`,`visual` |
| スキルカード使用数 | 出牌次数 | card uses remaining | AET_PlayableValueAdd | `card_uses_remaining` |
| スキルカード使用数追加 | 追加出牌次数 | additional card uses | EET_ExamPlayableValueAdd | `extra_card_uses` |
| スキップ | 跳过回合 | skip turn | PPT_ExamTurnSkip | `skip_turn` |
| クリア / パーフェクト | 课程达标 / 满分 | clear / perfect | ProduceStepLessonLevel.successThreshold / resultTargetValueLimit | `clear_score`,`perfect_score` |

## B. 牌堆与卡牌

| JP | CN | EN | 枚举 | 代码标识符 |
|---|---|---|---|---|
| 山札 | 牌库 | deck | Label_ProduceCardPositionType_DeckFirst/Last/Random | `deck` |
| 手札 | 手牌 | hand | Label_ProduceCardPositionType_Hand | `hand` |
| 捨札 | 弃牌堆 | discard pile | Label_ProduceCardPositionType_Grave | `discard` |
| 除外 | 除外堆 | removed (lost) pile | Label_ProduceCardPositionType_Lost | `removed` |
| 保留 | 保留区 | held cards | Label_ProduceCardPositionType_Hold, ExamSetting.holdLimit | `held` |
| スキルカード | 技能卡 | skill card | ProduceCard | `SkillCard` |
| アクティブスキルカード | 主动卡 | active card | Label_ActiveSkillCard | `CardType.ACTIVE` |
| メンタルスキルカード | 精神卡 | mental card | Label_MentalSkillCard | `CardType.MENTAL` |
| トラブルカード | 干扰卡 | trouble card | Label_TroubleSkillCard | `CardType.TROUBLE` |
| 眠気 | 困意（干扰卡） | Nemuke | — | `card_nemuke` |
| レッスン中1回 | 每局一次（用后除外） | once per stage | Label_ProduceCardMovePositionType_Lost | `once_per_stage` |
| 重複不可 | 不可重复持有 | unique / no duplication | Label_NoDeckDuplication | `unique` |
| レッスン開始時手札に入る | 开局入手 | innate / force initial hand | Label_InitialAdd | `innate` |
| 強化（+） | 强化 | upgrade | Label_ProduceCardUpgrade | `upgrade_level` |
| レッスン中強化 | 局内强化 | in-stage upgrade | EET_ExamCardUpgrade | `stage_upgraded` |
| レッスンサポート（一時強化） | 支援卡临时强化 | lesson support | Label_LessonSupport | `lesson_support` |
| カスタマイズ | 定制 | customization | ProduceCardCustomize | `customization` |
| 成長 | 成长（局内永久改写） | growth | EET_ExamAddGrowEffect, Label_ProduceCardGrowEffect | `growth` |
| 生成 | 生成卡 | generate card | EET_ExamCardCreateId | `generate_card` |
| 複製 | 复制卡 | duplicate card | EET_ExamCardDuplicate | `duplicate_card` |
| 手札をすべて入れ替える | 换手牌 | exchange hand | EET_ExamHandGraveCountCardDraw | `exchange_hand` |
| スキルカードを引く | 抽牌 | draw card | EET_ExamCardDraw | `draw_cards` |
| 固有スキルカード | 固有技能卡 | signature card | ProduceCard.sourceType=pIdol | `signature_card` |
| レジェンドカード | 传说卡 | legend card (rarity L) | ProduceLegendProduceCard | `Rarity.L` |
| プラン（センス/ロジック/アノマリー/共通） | 计划 | plan | Label_ProducePlanType1/2/3/0 | `Plan.SENSE/LOGIC/ANOMALY/FREE` |
| チェンジ / セレクトチェンジ | 换卡 | card change | PET_ProduceCardChange/ChangeSelect | `card_change` |
| 削除 | 删卡 | delete card | PET_ProduceCardDelete | `delete_card` |

## C. 状态效果（強化状態 / 低下状態）

| JP | CN | EN | 枚举 (EET) | 代码标识符 |
|---|---|---|---|---|
| 状態修正 / 持続効果 | 状态效果 | modifier / status enchant | ExamStatusEnchant | `Modifier` |
| 強化状態 | 增益 | buff | — | `buff` |
| 低下状態 | 减益 | debuff | — | `debuff` |
| 好調 | 好调 | good condition | ExamParameterBuff | `good_condition_turns` |
| 絶好調 | 绝好调 | perfect (excellent) condition | ExamParameterBuffMultiplePerTurn | `perfect_condition_turns` |
| 集中 | 集中 | concentration (focus) | ExamLessonBuff | `concentration` |
| やる気 | 干劲 | motivation | ExamCardPlayAggressive | `motivation` |
| 好印象 | 好印象 | good impression | ExamReview | `good_impression` |
| プライド | 骄傲 | pride | ExamLessonValueMultipleDependReviewOrAggressive | `pride_turns` |
| 指針 | 方针（姿态） | stance | Label_Stance | `stance` |
| 強気 (1/2段階) | 强势 | strength (aggressive) | ExamConcentration | `Stance.STRENGTH / STRENGTH2` |
| 温存 (1/2段階) | 保留（温存） | preservation | ExamPreservation | `Stance.PRESERVATION / PRESERVATION2` |
| のんびり | 悠闲 | leisure (over-preservation) | ExamOverPreservation | `Stance.LEISURE` |
| 全力 | 全力 | full power | ExamFullPower | `Stance.FULL_POWER` |
| 全力値 | 全力值 | full power charge | ExamFullPowerPoint | `full_power_charge` |
| 累計全力値 | 累计全力值 | cumulative full power charge | AET_ExamFullPowerPointTotal | `cumulative_full_power_charge` |
| 熱意 | 热意 | enthusiasm | ExamGimmickEnthusiastic | `enthusiasm` |
| 熱意追加 / 熱意増加 | 热意追加 / 热意增幅% | enthusiasm bonus / buff | ExamEnthusiasticAdditive / ExamEnthusiasticMultiple | `enthusiasm_bonus`,`enthusiasm_buff` |
| 指針固定 | 方针锁定 | stance lock | StanceLock | `lock_stance_turns` |
| 指針解除 | 解除方针 | stance reset | ExamStanceReset | `reset_stance` |
| 強気強化 / 全力強化 | 强势强化 / 全力强化 | strength / full power effect buff | ExamConcentrationLessonMultipleAdditive / ExamFullPowerLessonMultipleAdditive | `strength_effect_buff`,`full_power_effect_buff` |
| パラメータ上昇量増加 | 参数上升量增加% | score buff | ExamLessonValueMultiple | `score_buffs` |
| パラメータ上昇量減少 | 参数上升量减少% | score debuff | ExamLessonValueMultipleDown | `score_debuffs` |
| 消費体力減少 | 消耗体力减半 | half cost | ExamStaminaConsumptionDown | `half_cost_turns` |
| 消費体力増加 | 消耗体力加倍 | double cost | ExamStaminaConsumptionAdd | `double_cost_turns` |
| 消費体力削減 | 消耗体力削减 n | cost reduction | ExamStaminaConsumptionDownFix | `cost_reduction` |
| 消費体力追加 | 消耗体力追加 n | cost increase | ExamStaminaConsumptionAddFix | `cost_increase` |
| 元気増加無効 | 元气增加无效 | nullify genki | ExamBlockRestriction | `nullify_genki_turns` |
| 不安 | 不安 | unease | ExamBlockAddDown | `unease_turns` |
| 不調 | 不调 | poor condition | ExamGimmickParameterDebuff | `poor_condition_turns` |
| 緊張 | 紧张 | tension (score debuff gimmick) | ExamGimmickLessonDebuff | `tension_turns` |
| 弱気 | 弱气 | timid | ExamGimmickSleepy | `timid_turns` |
| スランプ | 低潮 | slump | ExamGimmickSlump | `slump_turns` |
| 手札減少 | 手牌减少 | draw down | ExamGimmickStartTurnCardDrawDown | `draw_down_turns` |
| スキルカード使用不可 | 禁止出牌 | no card use | ExamGimmickPlayCardLimit | `no_card_use_turns` |
| 気まぐれ | 反复无常（随机耗体） | panic | ExamPanic | `panic` |
| 疲労 | 疲劳 | fatigue | ExamGimmickTiredFix | `fatigue` |
| 高揚 | 高扬 | uplifting | ExamUplifting | `uplifting` |
| 低下状態無効 | 减益无效 | anti-debuff | ExamAntiDebuff | `nullify_debuff` |
| 低下状態回復 | 减益解除 | remove debuffs | ExamDebuffRecover | `remove_debuffs` |
| 体力回復無効 | 回复无效 | no stamina recovery | ExamStaminaRecoverRestriction | `no_recovery_turns` |
| スキルカード追加発動 | 卡效果再发动 | double card effect | ExamCardSearchEffectPlayCountBuff | `double_card_effect_cards` |
| 好印象追加発動 | 好印象再结算 | good impression times | ExamReviewCountAdd | `good_impression_times_buffs` |
| 発動予約 | 预约发动 | reservation (delayed effect) | ExamEffectTimer | `reservation` |
| 直接効果 | 直接效果 | direct effect | Label_OnHitEffect | `is_direct_effect` |
| 再演 | 再演 | encore | ExamStatusEnchantEncore | `encore` |
| 好調増加量増加 / 集中増加量増加 / やる気増加量増加 / 好印象増加量増加 / 全力値増加量増加 | 各增益获得量增加% | *_buffs | ExamParameterBuffAdditive / ExamLessonBuffAdditive / ExamAggressiveAdditive / ExamReviewAdditive / ExamFullPowerPointAdditive | `good_condition_buffs` 等 |
| 集中強化 / 好印象強化 | 集中/好印象效果强化 | concentration / good impression effect buff | ExamLessonBuffMultiple / ExamReviewMultiple | `concentration_effect_buffs`,`good_impression_effect_buffs` |
| 好調減少 / 集中減少 / やる気減少 / 好印象減少 / 全力値減少 | 各减少 | *_reduce | ExamParameterBuffReduce / ExamLessonBuffReduce / ExamAggressiveReduce / ExamReviewReduce / ExamFullPowerPointReduce | `reduce_*` |
| 体力回復 / 体力消費 / 体力減少 | 回复 / 费用 / 伤害 | recover / cost / damage | ExamStaminaRecoverFix / ExamStaminaReduceFix / ExamStaminaDamage | `recover_stamina`,`stamina_cost`,`stamina_damage` |
| コスト0化 | 费用归零 | nullify cost | (engine) nullifyCostCards | `nullify_cost_cards` |
| 強化状態コスト | 增益作费用 | buff cost | ExamSetting.examBuffConsumption* / PPT_ExamBuffConsume | `buff_cost` |

## D. 触发时机（Pアイテム / 持続効果）

| JP | CN | EN | 枚举 (PPT) | 代码标识符 |
|---|---|---|---|---|
| レッスン開始時 | 对局开始时 | start of stage | ExamStartExam / StartPlay | `on_stage_start` |
| ターン開始時 | 回合开始时 | start of turn | ExamStartTurn | `on_turn_start` |
| ターン終了時 | 回合结束时 | end of turn | ExamEndTurn | `on_turn_end` |
| nターンごとに | 每 n 回合 | every n turns | ExamTurnInterval | `every_n_turns` |
| 次のターン / nターン後 | n 回合后 | after n turns | ExamTurnTimer | `after_turns` |
| スキルカード使用時 | 出牌时（效果前） | on card used | ExamCardPlay | `on_card_used` |
| スキルカード使用後 | 出牌后 | after card used | ExamCardPlayAfter | `after_card_used` |
| n回使用するごとに | 每出 n 张 | every n plays | ExamPlayCountInterval(After) | `every_n_plays` |
| 〇〇が増加後 | 某状态增加后 | on modifier increased | ExamStatusChange | `on_*_increased` |
| 体力が減少した時 | 体力减少时 | on stamina decreased | ExamStaminaReduce(Card) | `on_stamina_decreased` |
| 指針が変更した時 | 方针变更时 | on stance changed | ExamStanceChange* | `on_stance_changed` |
| ターンスキップ時 | 跳过回合时 | on turn skipped | ExamTurnSkip | `on_turn_skipped` |
| 手札/捨札/除外へ移動時 | 卡移动时 | on card moved | ExamCardMoveHand/Grave/Lost | `on_card_moved` |
| 【〇〇レッスン・〇〇ターンのみ】 | 仅某属性回合 | turn-type condition | ProduceExamTrigger.lessonType | `turn_type_filter` |
| （レッスン内n回） | 每局发动 n 次 | activation limit | (engine) limit:N | `activation_limit` |
| Pアイテム | P道具 | producer item | ProduceItem | `PItem` |
| Pドリンク | P饮料 | producer drink | ProduceDrink | `PDrink` |
| 応援 / トラブル | 加油 / 干扰事件 | encouragement / trouble | — | `Encouragement` |
| メモリーのアビリティ | 回忆能力 | memory ability | MemoryAbility | `MemoryAbility` |

## E. 培育外循环

| JP | CN | EN | 枚举 | 代码标识符 |
|---|---|---|---|---|
| プロデュース | 培育 | produce | Produce | `ProduceRun` |
| 定期公演『初』 | 定期公演「初」 | Hajime | ProduceType_FirstStar | `Scenario.HAJIME` |
| N.I.A.（NEXT IDOL AUDITION） | N.I.A. | NIA | ProduceType_NextIdolAudition | `Scenario.NIA` |
| Hatsuboshi IDOL FESTIVAL (H.I.F) | H.I.F | HIF | ProduceType_HatsuboshiIdolFestival | `Scenario.HIF` |
| レギュラー / プロ / マスター / レジェンド | 难度 | regular / pro / master / legend | Produce.name | `Difficulty.*` |
| 週 | 周 | week / step | Produce.steps | `week` |
| 通常レッスン | 普通课程 | normal lesson | PST_Lesson{Vocal,Dance,Visual}Normal | `Action.LESSON` |
| SPレッスン | SP课程 | SP lesson | PST_Lesson*Sp | `Action.SP_LESSON` |
| 追い込みレッスン | 冲刺课程 | hard (oikomi) lesson | ProduceStepLesson.name=追い込みレッスン | `Action.HARD_LESSON` |
| 自主練 | 自主训练（NIA） | self lesson | PST_SelfLesson* | `Action.SELF_LESSON` |
| 休む | 休息 | rest / refresh | PST_Refresh | `Action.REST` |
| おでかけ | 外出 | outing | (PET_StaminaRecoverMultiple…) | `Action.OUTING` |
| 相談 | 咨询（商店） | consultation (shop) | Label_ShopProduceCardPriceDiscountMultiple | `Action.CONSULT` |
| 授業 | 授课 | school class | PST_EventSchool / Label_ProduceStepType_EventSchool=学園活動 | `Action.CLASS` |
| 活動支給 | 活动支给 | activity supply | PST_EventActivity | `Action.ACTIVITY_SUPPLY` |
| 営業 | 营业（NIA） | business | PST_Business | `Action.BUSINESS` |
| プレゼント | 礼物 | present | PST_Present / FanPresent | `Action.PRESENT` |
| 中間試験 | 期中考试 | midterm exam | PST_AuditionMid1 | `Exam.MIDTERM` |
| 最終試験 | 期末考试 | final exam | PST_AuditionFinal | `Exam.FINAL` |
| オーディション（一次/二次/最終） | 试镜 | audition | PST_AuditionMid1/Mid2/Final | `Audition.FIRST/SECOND/FINAL` |
| ファン投票数 | 粉丝票数 | votes | ProduceStepAuditionDifficulty.voteCount | `votes` |
| レッスンボーナス | 课程加成% | lesson bonus | PET_*GrowthRateAddition | `lesson_bonus` |
| パラメータボーナス | 参数加成% | parameter bonus | Label_LessonBonus | `param_bonus` |
| 初期パラメータ | 初始参数 | initial params | PET_*Addition (produce_start) | `initial_params` |
| ステータス上限 | 参数上限 | parameter cap | Produce.idolCardParameterGrowthLimit | `param_cap` |
| サポートカード | 支援卡 | support card | SupportCard | `SupportCard` |
| Pアイドル | P偶像 | produce idol | ProduceCharacter / IdolCard | `PIdol` |
| 特訓 / 才能開花 | 特训 / 才能开花 | special training / talent awakening | — | `training_rank`,`awakening_rank` |
| 親愛度 | 亲密度 | dearness (affection) | CharacterDearnessLevel | `dearness_level` |
| True End | 真结局 | true end | CharacterTrueEndBonus | `true_end` |
| 思い出 / メモリー | 回忆 | memory | MemoryAbility / MemoryTag | `Memory` |
| 最終プロデュース評価 | 最终评价 | final produce rating | ResultGradeType_ProduceScore | `produce_rating` |
| 評価ランク（F…SSSSS+） | 评价等级 | grade | ResultGradePattern.grade | `Grade` |
| 順位点 | 名次分 | place rating | — | `place_rating` |
| コンティニュー | 重试 | continue | ProduceSetting.continueCount | `continues_left` |
| AP | 行动点（培育开始消耗） | action points | Produce.actionPointQuantity | `ap_cost` |
| オート（AutoPlay） | 自动出牌 | autoplay | ExamPlayType_AutoPlay, ProduceExamAutoEvaluation | `AutoPlayAgent` |
| コンテスト | 竞赛 | contest | CompetitionSeason | `Stage.CONTEST` |

## F. 取整与计算用语

| JP | CN | EN | 代码标识符 |
|---|---|---|---|
| 切り上げ | 向上取整 | ceil | `ceil` |
| 切り捨て | 向下取整 | floor | `floor` |
| 端数 | 小数部分 | fractional part | — |
| 〇倍適用 | 按 n 倍应用 | multiplier applied | `*_multiplier` |
| 〇%分 | 按 n% 换算 | percent-of | `percent_of` |
| パーミル (permil) | 千分比 | permil | `_permil` 字段后缀 |
