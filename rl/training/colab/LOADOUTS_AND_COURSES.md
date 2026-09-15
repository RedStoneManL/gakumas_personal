# 当前五编成、真实开局与五场试镜

核查日期：2026-09-11。本文对应 `configs/full_produce_mixed.json` 和本地已固定的 Arena 主数据。五项是五个训练编成，涉及四位角色、三个大 Plan；不是五套已经训练好的策略，也不表示五种完全不重叠的大流派。训练环境每局按 `seed % 5` 分配一个编成，策略没有选择偶像的动作；模型从该编成的培育开局学习，切换编成不会继承上一局的牌组。

## 1. 五项分别是什么

“主数据推荐机制”取自 `IdolCard.examEffectType` 和 `examInitialDeckId`；“固有机制”取自实际专属卡和 P item 的定义。这两个概念需要分开。

| 配置名 | 角色、卡面与 master ID | 大 Plan / 主数据推荐机制 | 固有机制概要 |
|---|---|---|---|
| saki-wild | 花海咲季【Wildest Flower】`i_card-hski-3-017` | Logic / 好印象；`ExamReview` | 固有卡跟踪好印象类卡的使用，在已有好印象达到条件后增加好印象结算次数；固有物品在指定回合补资源和出牌次数。 |
| saki-hif | 花海咲季【ガラクタロード】`i_card-hski-3-018` | Anomaly / 强气；`ExamConcentration` | 固有卡要求累计温存至少两次；处于强气时能转温存，进入已使用区后在最后三个回合再发动。固有物品进一步强化该固有卡并补抽牌。属于强气与温存切换、准备终盘输出的机制。 |
| hiro-hif | 篠澤広【ガラクタロード】`i_card-shro-3-018` | Sense / 集中；`ExamLessonBuff` | 固有卡抽牌、提高集中效果并在回合末增加集中；高体力条件下可再次发动。固有物品也要求体力达到上限的 80%，提供减耗、元气和额外出牌。 |
| ume-campus | 花海佑芽【Campus mode!!】`i_card-hume-3-006` | Anomaly / 全力；`ExamFullPower` | 固有卡从牌库/弃牌中选择保留卡，增加全力值和出牌次数；固有物品与倒计时卡、保留牌联动，改变姿态并强化保留牌。 |
| liliya-xmas | 葛城リーリヤ【White Night! White Wish!】`i_card-kllj-3-005` | Logic / 干劲（日文「やる気」）；`ExamCardPlayAggressive` | 固有卡同时取得元气，并按照干劲直接增加分数；固有物品在干劲达标后放大干劲并抽牌。 |

特别注意命名：`ExamConcentration` 在 Anomaly 主数据中对应日文「強気」，不是 Sense 的「集中」；后者是 `ExamLessonBuff`。咲季 HIF 的推荐标签是强气，固有卡带有温存条件，不能因此把主数据标签改成温存。

主数据证据：仓库 `third_party/gakumas_arena/data/raw/gakumasu-diff/IdolCard.yaml` 的 3666、3726、7283、4125、6163 行分别是以上五张卡；包内对应 `arena/data/raw/gakumasu-diff/IdolCard.yaml`。`ProduceCard.yaml:757325` 的 `p_card-03-act-0_042` 明确将 `ProduceExamEffectType_ExamConcentration` 描述为「強気」。原生效果定义位于 `arena/gakumas_arena/_vendor/gakumas_tools/packages/gakumas-data/json/skill_cards.json` 和 `p_items.json`，由 bridge 绑定 master 身份后执行。

## 2. 模型实际看见的开局数据

以下来自五个真实 episode 的第一处公开决策状态，不是直接把偶像裸卡数值填进表。它已经包含当前配置的 PLv76、偶像 rank6、亲爱度37、成长面板和各编成六支援等初始化影响。后续改支援、rank、面板或记忆，这些数值会重新计算；它们不是角色永远固定的数值。

成长率一栏表示对应属性增加时使用的额外成长比例，例如 22% 对应状态中的 `vocal_growth=0.22`。

| 编成 | Vo / Da / Vi | Vo / Da / Vi 成长率 | 当前 HP / 上限 | 开局牌数 |
|---|---|---|---|---|
| saki-wild | 200 / 265 / 335 | 22% / 45.4% / 25% | 35 / 35 | 8 |
| saki-hif | 200 / 330 / 205 | 22% / 36.9% / 42% | 35 / 35 | 8 |
| hiro-hif | 175 / 305 / 245 | 32% / 42.9% / 28.5% | 28 / 28 | 8 |
| ume-campus | 175 / 315 / 185 | 27% / 44.9% / 39% | 33 / 33 | 8 |
| liliya-xmas | 180 / 245 / 320 | 24% / 49.4% / 28% | 31 / 31 | 8 |

实测原件：仓库 `rl/training/colab/validation/mixed-pool-audit.json`，五项 `first_public` 分别在 31、597、1164、1730、2309 行。该诊断轨迹没有用于 PPO 训练；正常培育失败也如实保留。

### 开局牌组

下表是实测八张牌的身份与份数；重复基本牌是不同实例。没有把未来会拿到的支援卡奖励预先塞进初始牌组。

| 编成 | 初始牌组（名称 × 份数；master ID） |
|---|---|
| saki-wild | 盛り上げの基本 ×1 `p_card-02-men-0_035`；ファンサの基本 ×2 `p_card-02-act-0_032`；笑顔の基本 ×3 `p_card-02-men-0_034`；セリフの基本 ×1 `p_card-02-men-0_036`；鮮やかに咲く花 ×1 `p_card-02-ido-3_173` |
| saki-hif | ブランディングの基本 ×1 `p_card-03-act-0_042`；魅せ方の基本 ×3 `p_card-03-act-0_043`；立ち回りの基本 ×2 `p_card-03-men-0_044`；ウォームアップの基本 ×1 `p_card-03-men-0_045`；手を伸ばした先に ×1 `p_card-03-ido-3_197` |
| hiro-hif | リアクションの基本 ×1 `p_card-01-act-0_028`；パフォーマンスの基本 ×2 `p_card-01-act-0_027`；思考の基本 ×1 `p_card-01-men-0_025`；落ち着きの基本 ×2 `p_card-01-men-0_026`；タイミングの基本 ×1 `p_card-01-men-0_029`；わたしだけの思い出 ×1 `p_card-01-ido-3_202` |
| ume-campus | アドリブの基本 ×1 `p_card-03-act-0_047`；カウントダウン ×1 `p_card-03-act-2_073`；スピーチの基本 ×1 `p_card-03-act-0_048`；自己管理の基本 ×2 `p_card-03-men-0_049`；レスポンスの基本 ×2 `p_card-03-men-0_050`；新たなステージ ×1 `p_card-03-ido-3_107` |
| liliya-xmas | アイコンタクトの基本 ×1 `p_card-02-act-0_037`；仕草の基本 ×1 `p_card-02-act-0_038`；距離感の基本 ×4 `p_card-02-men-0_039`；セルフケアの基本 ×1 `p_card-02-men-0_041`；愛を込めて ×1 `p_card-02-ido-3_086` |

### 开局固有 P item

| 编成 | 实测持有的固有 P item |
|---|---|
| saki-wild | すべてを超えた先へ+ — `pitem_02-3-299-1`（native 403） |
| saki-hif | 不屈の輝き+ — `pitem_03-3-320-1`（native 466） |
| hiro-hif | すべてを賭けた輝き+ — `pitem_01-3-313-1`（native 443） |
| ume-campus | 叶える覚悟+ — `pitem_03-3-078-1`（native 213） |
| liliya-xmas | 海の向こうまで+ — `pitem_02-3-050-1`（native 181） |

五项第一处公开状态还都持有 H.I.Fワッペン `pitem_00-3-265-0`：获得卡片触发星属性 +10，培育内上限20次。支援技能另有独立的有效等级、触发条件、效果参数、已触发次数，模型也能看到；没有将支援名字当成唯一输入。

输入路径：`arena/gakumas_arena/produce/public_state.py:31` 的 `live_public_state` 返回实时 `state/deck/drinks/produce_items/support_skills/exam_enchants`；`training/gakumas_training/tasks/full_produce/__init__.py:139` 将其与规则和当前考试观察组合，再建立主数据机制引用闭包。初始化规则先执行，再出现决策：`arena/gakumas_rl/simulation/produce/runtime.py:886`；初始牌组来自 `arena/gakumas_arena/produce/initial_deck.py:31`。

## 3. 五场试镜的属性回合数

本地已保存五场 profile，包括每场回合数、Vo/Da/Vi 配额、对应评分规则与对手组引用。这里按 **Vo / Da / Vi** 顺序列出基础配额。

| 角色（适用编成） | 属性优先顺序 | 选拔1，10回合 | 选拔2，12回合 | 选拔3，12回合 | 本战R1，9回合 | 本战R2，12回合 |
|---|---|---|---|---|---|---|
| 花海咲季（Wildest、HIF） | Vi > Da > Vo | 2 / 3 / 5 | 3 / 4 / 5 | 3 / 4 / 5 | 2 / 3 / 4 | 3 / 4 / 5 |
| 篠澤広（HIF） | Vo > Da > Vi | 5 / 3 / 2 | 5 / 4 / 3 | 5 / 4 / 3 | 4 / 3 / 2 | 5 / 4 / 3 |
| 花海佑芽（Campus） | Da > Vo > Vi | 3 / 5 / 2 | 4 / 5 / 3 | 4 / 5 / 3 | 3 / 4 / 2 | 4 / 5 / 3 |
| 葛城リーリヤ（圣诞） | Vi > Da > Vo | 2 / 3 / 5 | 3 / 4 / 5 | 3 / 4 / 5 | 2 / 3 / 4 | 3 / 4 / 5 |

当前适配器按角色身份选 profile，所以咲季两种卡面使用同一套试镜配额，尽管打牌流派不同。以上四位角色都属于 profile 的 `balanced` 类。若效果增加额外回合，当前实现将主属性回合追加在原末回合之后，不改原来的基础配额。

数据来源：`arena/gakumas_arena/produce/data/hif_exam_profiles.json`。角色行号：咲季446、广1479、佑芽1825、莉莉娅965。该文件是固定研究参考快照，`artifact_type` 明确为 `research_reference_not_drop_in_engine_config`：配额来自其中记录的 HIF 社区表，评分配置/对手组等引用来自主数据。不能将整个文件笼统称为游戏官方源码。

## 4. 回合排列：什么已知，什么仍是模拟假设

完整、永远不变的逐回合顺序没有被宣称已还原。当前 Arena 在进入每场考试时生成本场顺序：

1. 这四位角色默认首回合 85% 主属性、15% 次属性。**15% 是可配置模拟假设**；本地研究只记录过均衡型次属性开局约10%–20%的观察范围，精确游戏概率未确定。
2. 末三个基础回合固定为“第三属性 → 次属性 → 主属性”。因此咲季/莉莉娅为 Vo→Da→Vi，广为 Vi→Da→Vo，佑芽为 Vi→Vo→Da。此规则来自参考实现与本地 R1 观察，五场游戏运行时完整验证仍未完成。
3. 从基础配额扣去首回合与末三回合，其余属性多重集合打乱。`shuffle` 是参考模拟模型，尚未证明与游戏真实 RNG 分布完全相同。
4. 额外回合在原尾部之后追加主属性回合。

实现位置：`arena/gakumas_arena/produce/courses.py:119` 的 `default_exam_config`，首回合概率配置在127行、采样在130行，剩余回合 shuffle 在135行，额外回合在138行。证据边界由 `hif_exam_profiles.json:32` 的 `turn_sequence_rules` 明确标注。

模型在培育中已经收到当前角色五场配额、课程资源/门槛规则和日程，见 `training/gakumas_training/tasks/full_produce/__init__.py:130`。本場已生成的完整回合顺序通过考试公开观察 `context.turn_types` 给模型，见 `arena/gakumas_arena/engine/training_worker.mjs:249`。尚未进入的未来考试没有提前生成其具体随机排列；牌库未公开的抽牌顺序与 RNG 状态也不进入公开观察。

补充精确边界：当前全培育观察的 `rules` 带有五场配额和选拔/本战日程，但没有单独复制全局 `turn_sequence_rules` 字段；模型能看到当前场的实际顺序，不能声称“15%假设与末三回合文字规则也已作为独立字段全部输入”。

本地参考将选拔三场记为第7/13/20日，本战 R1、间歇、R2 都属于本战第7日；运行时将本战后段拆成顺序步骤处理，因此调度表中的步骤编号不能直接当成游戏日历日。相关调度见 `arena/gakumas_arena/produce/research.py:13`。
