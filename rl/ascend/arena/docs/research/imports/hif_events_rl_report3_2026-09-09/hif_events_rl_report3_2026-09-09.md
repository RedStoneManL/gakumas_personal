# HIF 事件、资源与随机机制：RL 建模参考（报告 3）

## 1. 主要结论

HIF 的日常部分适合建成“固定日程与选项骨架 + 按来源区分的随机奖励池 + 有次数限制的连锁触发”。目前可以较完整地还原固定数值、选项分支、道具进化关系和部分随机权重；**还不能把商店、慰问品、外出的所有卡牌和饮料概率写成一张经过验证的分布表。**

对实现影响最大的结论如下。

1. **外出和上课的基础选项没有成功／失败抽签。**当前主数据中对应 92 条事件记录、72 个独立选项，全部为 `alwaysSuccessful=true`。随机性主要发生在奖励候选生成，以及部分“随机强化／删除”等后续效果。[^M-event]
2. **慰问品因粉丝投票数而追加 P 点的概率，在 HIF 中为 0%。**官方帮助明确排除了 HIF。装备、支援卡或其他事件产生的额外 P 点必须单独结算，不能算成慰问品基础抽奖。[^O-present]
3. **上课前期拿卡，后期主要换卡。**选拔第 3、6 日基础属性增量为 120；第 10、17 日为 150；本战第 1、4 日为 180。拿卡和换卡对牌组大小、徽章、支援触发的影响不同。[^M-event]
4. **普通咨询与本战中场有不同的商店状态。**中场刷新使用 P 点，并恢复强化／定制服务的可用次数；不能把普通咨询的剩余刷新次数直接套过去。[^O-interval][^M-proto]
5. **当前 HIF 卡片折扣面板最高为 30%。**2026-09-07 的主数据与显示文本均如此；攻略中“最高级 15%”的算例不适合作为当前默认参数。[^M-panel]
6. **180 条自定义 P 道具记录可以压缩成 60 个经济分支状态，再乘 3 种计划的战斗增益。**进化候选关系已知，但“四种候选中展示三种”的抽样权重没有公开；75% 只能作为等权假设，不能标成实测概率。[^M-pouch]
7. **应援棒补基本卡的六组权重能具体算出来，而且并非均匀分布。**它们是战斗内补牌池，不能拿来当商店或慰问品的卡池。[^M-pool][^M-penlight]

建议本地实现先固定可靠的数值骨架，把尚未识别的概率做成独立配置；保留事件来源、候选集合、槽位、阶段和触发日志，以便用后续实机数据更新。

## 2. 范围、单位与证据等级

本报告覆盖通常 HIF：`produce-007` 选拔试验、`produce-008` 本战。数值基线锁定公开主数据快照 `571dbb62601e78998cddeacdbce3ea1bc672d7fc`，提交时间为 2026-09-07 08:03:22 UTC；资料核对截至 2026-09-09。限时活动模式、其他剧本和将来更新应使用不同的环境版本。主数据镜像是公开提取资料，**并不是完整的官方服务端代码**。[^M-version]

| 标记 | 含义 | 实现建议 |
|---|---|---|
| O | 官方游戏内帮助有明确说明 | 可作为规则依据，注意适用剧本 |
| M | 当前主数据／协议能直接定位 | 可读取具体值；单有记录不证明该记录一定在当前场景可达 |
| V | 原始游玩记录或社区整理 | 可作暂定规则，保留来源与复核开关 |
| H | 本报告提出的推断或建模假设 | 必须允许替换，不标成真实游戏概率 |
| U | 未识别 | JSON 中用 `null`，不能用 0 代替 |

除非另有说明，本文属性顺序为 **Vo / Da / Vi**；P 点指养成内 `producePoint`；体力指养成体力，不是考试内的元气。

必须区分三个不同概念：

| 概念 | 决定什么 | 不应混同的内容 |
|---|---|---|
| 计划：Sense／Logic／Anomaly | 可用技能体系、上课两个方向、道具战斗增益 | 偶像的 Vo/Da/Vi 排名 |
| 推荐效果：好调、集中、好印象、干劲、强气、全力 | 部分奖励池和应援棒颜色／卡池 | 属性达标图标 |
| 偶像审查类型与流 1/2/3 映射 | 均衡／突出型的考试要求与属性价值 | 不能简单按当前三个属性的数值大小重排 |

RL 仍应保存三维、スター性、审查类型以及 ◎／○／△／× 状态。它们影响培养决策的收益；**目前没有证据表明某个属性图标直接改变慰问品稀有度或商店抽卡概率**。如果怀疑存在这种关联，应作为待检验条件变量，不能预先写入概率公式。

## 3. 固定日程与事件入口

日程上的“有这个入口”与“玩家选择该入口”是两件事。比如选拔有 4 个外出机会，不代表一局必然发生 4 次外出。以下是通常日程；额外休息及装备事件另按可用状态处理。日程表属于 V 级；环境接入实机时优先读取 `UserProduceProgressSchedule.stepTypes`。[^V-hif][^M-proto]

| 选拔日 | 常规可选行动／固定节点 |
|---:|---|
| 1 | 咨询、慰问品、特别指导 |
| 2 | スター性重视公开课 |
| 3 | 上课，选择 Vo/Da/Vi |
| 4 | 属性重视公开课 |
| 5 | 外出、咨询 |
| 6 | 上课，选择 Vo/Da/Vi |
| 7 | 选拔试验 1 |
| 8 | 外出、慰问品 |
| 9 | スター性重视公开课 |
| 10 | 上课，选择 Vo/Da/Vi |
| 11 | 属性重视公开课 |
| 12 | 咨询、特别指导 |
| 13 | 选拔试验 2 |
| 14 | 外出、慰问品 |
| 15 | スター性重视公开课 |
| 16 | 外出、咨询、慰问品 |
| 17 | 上课，选择 Vo/Da/Vi |
| 18 | 属性重视公开课 |
| 19 | 咨询、特别指导 |
| 20 | 选拔试验 3 |

| 本战节点 | 行动 |
|---|---|
| 第 1 日 | 上课 |
| 第 2 日 | スター性重视公开课 |
| 第 3 日 | 外出、慰问品 |
| 第 4 日 | 上课 |
| 第 5 日 | 属性重视公开课 |
| 第 6 日 | 咨询 |
| 比赛日 | Round 1 → 中场 Interval → Round 2 |

主数据把选拔记为 20 个 step、本战记为 9 个 step。因此 UI 的“本战 7 日”不能作为内部状态数；两个 Round 和中场需要分开。[^M-setting]

### 3.1 叙事事件怎样合并

固定选项对应 20 条外出事件、72 条上课事件。只按引用的选项 ID 列表归并，得到 **3 组外出 + 27 组上课 = 30 组**；再把属性和计划作为参数，才进一步压缩成后面的少量数值模板。[^M-event]

这比给每段剧情单独拟合发生概率更合适。但不能把所有阶段的奖励池合并：外出至少引用了 `before_2nd`、`before_3rd`、本战三个来源池，即使固定数值相同，也不证明卡牌分布相同。

## 4. 上课：完整基础选项矩阵

先选上课属性 `j∈{Vo,Da,Vi}`，再在该事件内选一个分支。表中的属性增量只加到 `j`。当前基础选项全部确定执行；**没有旧剧本式的低成功率／大成功／失败变种**。[^M-event]

| 阶段 | 分支 | 基础成本 | 属性增量 | 卡组操作 |
|---|---|---|---:|---|
| 选拔第 3、6 日 | 方向 A | 体力 −5 | `j +120` | 从方向 A 奖励池选获 1 张卡 |
| 同上 | 方向 B | 体力 −5 | `j +120` | 从方向 B 奖励池选获 1 张卡 |
| 同上 | Trouble 分支 | 加入眠气 1 张，基础体力成本 0 | `j +120` | 对 1 张合法非 Trouble 卡执行 Select Change |
| 选拔第 10、17 日 | 方向 A | 体力 −5 | `j +150` | Select Change 到方向 A 池 |
| 同上 | 方向 B | 体力 −5 | `j +150` | Select Change 到方向 B 池 |
| 同上 | Trouble 分支 | 加入眠气 1 张，基础体力成本 0 | `j +150` | 对 1 张合法非 Trouble 卡执行 Select Change |
| 本战第 1、4 日 | 方向 A | 体力 −5 | `j +180` | Select Change 到方向 A 池 |
| 同上 | 方向 B | 体力 −5 | `j +180` | Select Change 到方向 B 池 |
| 同上 | Trouble 分支 | 加入眠气 1 张，基础体力成本 0 | `j +180` | 对 1 张合法非 Trouble 卡执行 Select Change |

“选获 1 张”表示领取数量，不表示只展示 1 张候选。前期普通拿卡观察为未强化状态；后期 Select Change 的强化状态取决于被换出的卡。上课基础属性增量不吃普通参数成长 bonus；上课触发的支援卡、道具固定加点应另加。后两条属于 V 级交叉核对。[^V-hif][^V-shato]

| 计划 | 方向 A | 主数据池后缀 | 方向 B | 主数据池后缀 |
|---|---|---|---|---|
| Sense / `Plan1` | 好调 | `exam_parameter_buff` | 集中 | `exam_lesson_buff` |
| Logic / `Plan2` | 好印象 | `exam_review` | 干劲／やる気 | `exam_card_play_aggressive` |
| Anomaly / `Plan3` | 强气／強気 | `exam_concentration` | 全力 | `exam_full_power` |

这里的 `concentration` 是 Anomaly 强气方向的内部名；不能望文生义地把它映射成 Sense 的“集中”。[^M-event]

Trouble 分支使用的是没有 A/B 后缀的池。社区怀疑它按偶像推荐效果收窄，但没有足够直接权重证据。本版保存为独立 `class_common_pool`，不直接当成“A 与 B 各 50%”。

### 4.1 实现陷阱

- `alwaysSuccessful=true` 时，不能再读取默认 `successProbabilityPermyriad=0` 得出“成功率 0%”。其他真正有成功率的事件，该字段的分母是 **10000**，不是 1000。
- `producePoint`、`stamina` 和 `produceCardId` 成本字段位于选项头部；只执行 `produceEffectIds` 会漏掉扣体力、扣 P 点或加眠气。
- 第三选项的“加眠气”与之后的“换卡”是两个操作，前者可能触发获取卡片效果，后者走换卡触发。
- `p_card_search-active_skill-mental_skill-deck_all` 指向 ActiveSkill/MentalSkill 类别的合法目标；不要写成“任意牌，包括眠气”。
- 保留 `eventSchoolStaminaPermil` 等成本修正以及动作合法性；5 点是无额外修正的基础成本。[^M-event][^M-search][^M-proto]

## 5. 外出：三条基础分支

外出没有成功率分支，三种选择的基本结构如下。[^M-event]

| 分支 | 基础成本 | 体力恢复 | 饮料 | 强化卡奖励 | 普通卡奖励 | 接受全部奖励后的牌组净增 |
|---|---|---|---|---|---|---:|
| 支付 P 点 | P 点 −50 | 最大体力的 60% | 选获 1 瓶 | 选获 1 张 | 选获 1 张 | +2 |
| 加入 Trouble | 眠气 +1 | 最大体力的 60% | 选获 1 瓶 | 选获 1 张 | 选获 1 张 | +3 |
| 无额外成本 | 0 | 最大体力的 60% | 选获 1 瓶 | 无 | 选获 1 张 | +1 |

恢复效果原值为 `StaminaRecoverMultiple=600`，即 600‰。恢复受最大体力上限约束；其他体力回复修正的叠加顺序、出现小数时的最终取整应记录实机值。若暂用向下取整，须标为待校正实现约定，不能只凭 `600` 推导出完整取整算法。

这三条的“结果会发生”是确定的，**具体展示哪几张卡、哪个稀有度、普通卡是否带 `+`，仍是随机内核**。当前公开数据只暴露来源池引用，没有给出这些奖励池的成员权重。普通卡奖励也不能直接当成未强化卡；社区记录显示其强化状态可能变化。[^V-hif]

### 5.1 外出奖励池的阶段区别

| 来源组 | 奖励效果 ID 中可见的池前缀 | 需要单独保留的抽样部分 |
|---|---|---|
| 选拔前段 | `p_rd-produce_007-event_activity-before_2nd` | `drink`、`upgrade_1`、普通卡 |
| 选拔后段 | `p_rd-produce_007-event_activity-before_3rd` | 同上 |
| 本战 | `p_rd-produce_008-event_activity` | 同上 |

固定选项可以合并，三个阶段池不能未经检验就合并。日程到事件 ID 的精确映射应从实机保留；不要只用英文 `before_2nd` 的字面含义自行编造日数范围。[^M-event]

### 5.2 外出与 HIF 徽章

`H.I.Fワッペン` 在获取卡片时增加基础スター性 10，触发上限 20 次。原始游玩记录也把外出加眠气作为多触发一次徽章的手段。[^M-item][^V-shato]

无额外星性 bonus、徽章次数充足、全部接受卡片时，三条外出分支的基础星性收益分别为 **20 / 30 / 10**。这个差异来自卡片获取次数，不是外出事件自己有三档星性抽奖。

设本次真实发生的获取次数为 `n_get`，徽章已触发 `used` 次：

```text
n_badge = min(n_get, max(0, 20 - used))
base_star_gain = 10 * n_badge
```

之后按每次实际星性加成规则结算。亲爱度修正、上限和触发顺序都不能丢；尤其不要把“先累加基础星性再统一取整”无条件当成“逐次加成并取整”。

## 6. 慰问品：固定奖励、额外 P 点与稀有度

### 6.1 基础结果

通常 HIF 慰问品的社区记录为：**P 点 80 + 饮料领取机会 + 技能卡领取机会**；饮料候选为 SR 以上。应保留三个资源部分，不建成“三者抽一个”。候选张数、领取数与实际接受结果分别记录。[^V-hif]

| 问题 | 当前结论 | 证据 |
|---|---|---|
| 是否因粉丝投票数随机追加 P 点 | **不会，概率 0%** | O |
| 基础 P 点 | 80，无额外修正时 | V |
| 是否有基础卡片奖励机会 | 有；具体取得仍由领取、候选和合法性决定 | O/V |
| 饮料候选中 R 的概率 | 通常 HIF 规则下为 0% | V |
| SR 与 SSR 饮料的分配 | 未识别 | U |
| 卡片 R/SR/SSR 的概率 | 未识别 | U |
| 卡片强化状态的概率 | 未识别 | U |
| 特定卡片／特定饮料的出现率 | 未识别，不能按候选总数倒数填写 | U |

官方原句仅需引用这一句即可消除剧本混淆：**「※H.I.Fではボーナスは発生しません」**。它指前文的粉丝投票数 bonus；不排除装备产生额外收益。[^O-present]

### 6.2 为什么实机可能看到超过 80 P 点

应该把来源拆成：

```text
实际 P 点变化
  = 慰问品基础奖励及适用修正
  + 进入慰问品触发的效果
  + 领取卡片／饮料触发的效果
  + 慰问品结束触发的效果
  + 同时发生的其他事件
```

例如绿袋路线的 `くま（緑）` 在慰问品结束时给 P 点 60，并执行一次 Select Change；在次数尚未用完且无其他修正时，就可以与基础 80 组成 140。另有 `お似合いネクタイ` 的相关触发条件满足时给 P 点 30、回复体力 5。它们是状态条件和剩余次数决定的效果，不是全体 HIF 通用的“额外 P 点概率”。[^M-pouch][^M-item]

协议也明确区分 `UserProduceProgressPresent` 中的奖励和 `ProduceEffectResult.origin` 中的效果来源。记录 `beforeProducePoint/afterProducePoint` 和 `origin`，比单看最终总额更容易辨认机制。[^M-proto]

## 7. 卡片／饮料的随机内核应该怎样拆

至少保留下面这些不同分布，不能用同一个全局 SSR 概率替代。

| 内核 | 已知约束 | 仍未知 |
|---|---|---|
| 外出强化奖励 | 必须是强化状态；奖励来源独立 | 稀有度与卡 ID 权重 |
| 外出普通奖励 | 允许观察到强化状态变化 | 稀有度与强化状态的联合分布 |
| 上课前期 A/B 奖励 | 按计划、方向和阶段取池 | 每张卡权重 |
| 上课／道具 Select Change | 由目标约束、来源池和原卡状态决定 | 候选抽样、去重及退化规则 |
| 慰问品饮料 | SR 以上候选 | SR/SSR 比例、单瓶权重 |
| 黄色道具的“特定饮料” | 与 `drink_set-all` 是不同池 | 完整成员及权重 |
| 普通咨询的各槽位 | 价格与强化状态有关，有 SALE 槽位 | 各槽位概率及它们之间的相关性 |
| 中场购买与换卡槽位 | 购买与换卡是不同资源操作 | 各槽位生成分布 |
| 随机强化／删除 | 从当前合法目标集合选对象 | 是否对每个卡片实例等权 |

奖励处理应至少分成三步：

1. 环境生成候选集合 `C`，并展示给策略。
2. 策略选择 `a∈C`，或在允许时跳过／重抽。
3. 环境执行领取与连锁触发。

否则，只记录“最终选到了哪些卡”会把玩家偏好当成卡池概率。也不能从 `pickCountMin=pickCountMax=1` 推出候选集合大小为 1：它们约束的是选择／作用数量。[^M-proto]

### 7.1 合法候选与卡片身份

候选生成至少要考虑：剧本和阶段、计划、推荐效果、PLv、开关卡配置、已除去卡片、特定来源限制、重复限制和强化状态。`ProduceCard` 提供 `unlockProducerLevel`、`noDeckDuplication`、`originSupportCardId`、`originIdolCardId`、`isInitialDeckProduceCard` 等字段；但这些只是组成合法性规则的材料。[^M-card]

尤其注意：当前镜像中 `isReward` 不能直接拿来判定“能否在养成中获得”。对读取到的 `upgradeCount=0` 记录直接筛 `isReward=true`，结果为 0；因此它不是可直接使用的奖励池清单。

持有多张同名卡时，目标随机性要按**卡片实例**记录。若抽样是对实例等权，两张 A、一张 B 对 A 的命中率为 2/3；若按名称等权则是 1/2。两种模型不能混用，此处尚无足够 HIF 实测来定案。

## 8. 咨询商店与本战中场

### 8.1 基础价格和折扣

以下价格来自社区整理，作为 V 级默认表；真实接入时以每个货位返回的 `price`、`nextPrice` 为准。`+` 表示强化状态。[^V-hif][^M-proto]

| 商品 | 普通咨询基础价 | 中场购买基础价 |
|---|---:|---:|
| R 未强化卡 | 通常不出现 | 通常不出现 |
| R+ | 100 | 30 |
| SR | 50 | 通常不出现 |
| SR+ | 110 | 50 |
| SSR | 100 | 50 |
| SSR+ | 150 | 80 |
| R 饮料 | 50 | 50 |
| SR 饮料 | 75 | 75 |
| SSR 饮料 | 100 | 100 |

中场另有 Select Change 货位，按照新卡稀有度收费：R 30、SR 50、SSR 80。这里花钱是“把一张已有卡换成货位指定卡”，不是额外增加一张卡。普通咨询的具体货位数与稀有度配置没有获得足够无歧义的当前版本数据，不把槽位数臆定成常量；中场观察为购买卡 4 格、换卡 2 格、饮料 2 格。[^V-hif]

普通咨询的卡片行、饮料行左端 SALE 槽位为七折。与 HIF 面板及道具折扣叠加的暂定计算为先乘各价格系数，再向下取整：

\[
P_{pay}=\left\lfloor P_{base}\prod_k d_k\right\rfloor.
\]

当前 HIF 面板卡片折扣为 **5%、10%、15%、20%、25%、30%**。这六档来自主数据和 UI 文本，不是从成交价拟合得到。最高级时，一张基础价 150 的 SALE 卡按上述乘法规则是 `floor(150×0.7×0.7)=73`；这个 73 是计算预测，仍建议用一张当前实机价签确认。[^M-panel][^M-setting]

旧攻略最高级算例用了 15%，会得到 89；它与当前记录的 30% 不一致。应以版本化配置处理，不能为了复现旧算例把主数据的 300‰改成 150‰。

中场不属于普通咨询，普通“进入咨询”触发以及咨询专属折扣不可自动套用；原始游玩记录明确指出了这一点。卡片“定制时”等非咨询限定触发，则应独立按条件判断。[^V-shato][^O-interval]

### 8.2 两种刷新机制

| 项目 | 普通咨询 | 本战中场 |
|---|---|---|
| 刷新状态 | `shopRemainRerollCount` 等次数资源 | `intervalRerollPrice` 等 P 点价格状态 |
| 亲爱度提供的修正 | 亲爱 27 的技能提供咨询刷新次数 +1 | 不能把这个 +1 直接当作中场次数 |
| 跨选拔／本战 | 剩余次数状态需要继承 | 独立中场状态 |
| 刷新后的商品 | 重新生成可刷新货位 | 更新技能卡与饮料 |
| 强化／定制服务 | 是否随普通刷新重置，需实机核对 | 官方明确刷新后重新可用 |
| 价格进度 | 保留每个服务的 `price/nextPrice` | 保留中场强化计数、当前与下一次价格 |

普通咨询的刷新费用、已购货位是否保留，以及是否重新开放强化／删除，不宜只从“刷新”两个字推断；应录一次完整前后状态后再锁定。本报告没有把这些缺口伪装成已知规则。[^M-proto][^M-dear]

中场刷新费用的 V 级序列为 **10、10、20、30、40、50**；50 是否为永久上限仍未验证。官方确认刷新会恢复强化、定制服务，中场配置则给出每批 **强化 1 张、定制 2 张**。[^V-hif][^O-interval][^M-setting]

中场强化观察为起价 100，强化后再次刷新时后续报价增加 25。还需要区分“每次强化涨价”与“只要刷新就涨价”：一次没有强化的空刷新就能识别。不要提前把两个计数器合成一个。

### 8.3 强化、删除与回复

普通咨询的强化和删除应分别保存价格状态，协议确实有 `shopProduceCardUpgradePrice` 与 `shopProduceCardDeletePrice` 两个字段。社区前五次报价为 100、125、150、175、200；第六次表中写 250，不能据此同时又声称永远每次 +25。超出已确认区间时读取 `nextPrice`，离线默认表保留待验证标记。[^V-hif][^M-proto]

账号解锁状态也不能省略：PLv 5 开放咨询强化，PLv 15 开放咨询删除；PLv 10 增加一次卡片候选重抽。最后这一项是卡片奖励候选的重抽，不是咨询商店刷新。通常能进入 HIF 的账号已经经过这些等级，环境仍应区分这两种计数。[^M-dear]

中场体力回复观察为每次 10 P 点、回复 2 体力；距离满体力只差 1 时也收费 10。官方说明 Round 2 前没有自动回复，所以这项动作必须存在。普通咨询没有证据支持直接复制这项中场回复服务。[^V-hif][^O-final]

## 9. 拿卡、强化、定制、换卡、复制、删除是不同操作

| 操作 | 牌组净变化 | 应处理的主要触发 | 关键约束 |
|---|---:|---|---|
| 领取／购买卡片 | +1 | 获取卡片、对应获取来源；可能触发徽章 | 重复限制、牌组上限、主动放弃 |
| 加入眠气 | +1 | 实际获取卡片；可触发徽章 | 不能当作“纯扣费，无卡组变化” |
| 强化已有卡 | 0 | 卡片强化 | 不等于获得一张新卡 |
| 定制已有卡 | 0 | 卡片定制 | 通常要求已强化；受该卡定制上限和项目限制 |
| Select Change | 0 | 卡片变化 | 保留原卡强化状态，丢失定制；目标合法性因来源不同 |
| 普通随机变化 | 0 | 卡片变化 | 与 Select Change 不同；不能默认有三个候选可选 |
| 复制 | +1 | 获取卡片 | 复制后的具体状态必须保存，不能只复制名称 |
| 删除 | −1 | 卡片删除 | 目标是否合法、随机还是自选 |
| 应援棒战斗内生成 | 养成牌组不变 | 战斗内生成 | 不增加养成获取次数或徽章次数 |

Select Change 的强化继承、定制不继承有官方说明；取得与变化的区分还得到原始游玩记录支持。[^O-interval][^V-shato]

### 9.1 定制机制

特别指导的基础配置一次可定制 **2 张卡**，还可能有额外名额／折扣。它限制的是本次服务中的可处理卡片，不等于每张卡只能定制 2 次。当前 `ProduceCard.maxCustomizeCount` 为 0、1、2、3 中的一种；具体项目由该卡的 `produceCardCustomizeIds` 决定。[^M-setting][^M-custom]

官方帮助规定：未开放定制的偶像固有卡、初始持有的基本卡、Trouble 卡不能定制；定制追加的效果在原有效果之后执行。[^O-custom]

`ProduceCardCustomize` 中有 343 条“项目 × 档位”记录，本次快照的价格集合为 **20、40、70、100、120**。这些是配置中的项目价，不代表每次定制都依次经过这五档。[^M-custom]

| 示例卡 | 最大定制数 | 可见项目示例与基础价 |
|---|---:|---|
| 天真烂漫／天真爛漫+ | 1 | 消耗 −2：20；集中 +2：70 |
| Overdrive／オーバードライブ+ | 1 | 消耗 −2：20；追加元气 9：70 |
| 国民的アイドル+ | 1 | 元气 +9：70；追加一次参数值 6 效果：70 |
| アイドル宣言+ | 1 | 体力消耗减少状态延长 2 回合：70；追加元气 4：70 |
| ファンサ+ | 3 | 参数值定制同一项目的档位：+6 / +12 / +30，对应本次费用 40 / 40 / 70；另有好调、绝好调追加项目 |

对于同一个 `customize_id`，档位值应按当前档位解释，不能把 6、12、30 不加区分地永久相加。`overwriteProduceCardGrowEffectType` 等覆盖规则也要保留。每张卡的定制数、同一项目的升级次数、本次特别指导消耗了几张名额，是三种不同状态。

主数据有 `upgradeCount=0/1/2/3` 的卡片版本，但这不表示普通商店一定允许把每张卡付费连升到 `+++`。普通永久强化、战斗内强化、支援的“技能卡 support”属于不同机制；`SupportCardProduceCardUpgradeProbabilityUp` 的显示文本实际描述的是“技能卡 support 发生率增加”，不能拿来填充“慰问品出强化卡概率”。[^M-card][^M-skill]

## 10. 自定义 P 道具：完整经济分支

选拔试验 1 后选基础袋；试验 2 后第一次进化；试验 3 后第二次进化。主数据能直接确认 180 个节点和父子关系。按经济效果合并三个计划后为 60 个状态，完整数值表见附录 A。[^M-story][^M-pouch]

| 触发路线 | 红袋第一次进化 | 绿袋第一次进化 | 黄袋第一次进化 |
|---|---|---|---|
| 公开课结束 | くま | インコ | ロボ |
| 进入咨询 | 人形 | うさぎ | もじゃ |
| 慰问品结束 | ロボ | くま | インコ |
| 外出结束 | もじゃ | 人形 | うさぎ |

每种基础袋有 4 条第一次进化路径。公开课路线的末级有 3 个子节点；其他三条路线各有 4 个。社区与原始记录一致描述：有 4 个子节点时随机展示 3 个，公开课路线末级三个全部可选。[^M-pouch][^V-shato]

**已知“4 中展示 3”不等于已知均匀抽样。**如果四条路径等权，则某个指定路径出现率为 3/4；如果抽样有权重，则未必。关系表没有 `ratio` 字段，因此本版把相应概率保留为 U。

### 10.1 道具效果必须先触发，才获得下一场／后续比赛的增益

不能在选中道具时就直接发放所有战斗 buff。先满足公开课、咨询、慰问品或外出触发条件，再登记对应增益；未触发的道具不产生这部分收益。

附录中的战斗增益键含义如下，每次实际道具触发附加一次相应效果。[^M-pouch][^M-enchant]

| 键 | Sense | Logic | Anomaly |
|---|---|---|---|
| B2 | 集中 +2、好调 2 回合 | 好印象 +2、干劲 +2 | 全部技能卡参数值成长 +4 |
| B3 | 集中 +3、好调 3 回合 | 好印象 +3、干劲 +3 | 全部技能卡参数值成长 +6 |
| B6 | 集中 +6、好调 6 回合 | 好印象 +6、干劲 +6 | 全部技能卡参数值成长 +12 |

基础袋和第一次进化登记的是下一场比赛效果；第二次进化使用 `ExamPermanentAuditionStatusEnchant`，会影响后续比赛。触发次数与已登记增益都需要保存，尤其是本战 Round 1 到 Round 2 之间。

当前主数据中，红色外出路线末级会额外登记固定元气 6；第一阶段 `もじゃ（赤）` 的增益列表里没有这条。实现应按当前节点 ID 读效果，不把某条路线的末级特性复制到所有前级。

### 10.2 黄色“特定饮料”与普通饮料是两个池

黄色袋使用 `p_rd-drink_set-produce_007-customize_item`，额外随机普通饮料使用 `p_rd-drink_set-all`。例如 `花ロボ（黄）` 每次触发给“特定池随机 1 瓶 + 普通池自选 1 瓶”，最多触发 2 次。其结果不是“随机抽两瓶完全相同分布的饮料”。[^M-pouch]

“高概率 SSR”卡片池也要独立保存。标签描述倾向，**并没有提供一个可填写的 80%／90% 数值**；尤其不能仅因池 ID 含 `ssr` 就断言 100% SSR。

## 11. 公开课、SP 与休息

公开课是确定数值成长步骤。主属性由玩家选，另一个属性由日程指定；主、副属性各自使用对应的成长修正。官方特别指出，副属性增长也适用相应 lesson bonus。[^O-open][^M-lesson]

| 阶段 | 课程类型 | 普通：体力／主属性／副属性／星性 | SP：体力／主属性／副属性／星性 |
|---|---|---|---|
| 选拔第 1 段 | 星性重视 | 6 / 50 / 10 / 20 | 8 / 60 / 20 / 30 |
| 选拔第 1 段 | 属性重视 | 6 / 60 / 20 / 5 | 8 / 80 / 50 / 10 |
| 选拔第 2 段 | 星性重视 | 6 / 70 / 10 / 20 | 8 / 80 / 20 / 30 |
| 选拔第 2 段 | 属性重视 | 6 / 80 / 30 / 5 | 8 / 100 / 60 / 10 |
| 选拔第 3 段 | 星性重视 | 6 / 90 / 10 / 20 | 8 / 100 / 20 / 30 |
| 选拔第 3 段 | 属性重视 | 6 / 100 / 40 / 5 | 8 / 120 / 70 / 10 |
| 本战 | 星性重视 | 6 / 110 / 10 / 20 | 8 / 120 / 20 / 30 |
| 本战 | 属性重视 | 6 / 120 / 50 / 5 | 8 / 140 / 80 / 10 |

这些数值均为修正前。课程本身、课程后支援、获得卡片／饮料等连锁效果不能混入基础主副属性。公开课获得 P 点的社区记录为选拔 30、本战 50；这一奖励不在 `ProduceStepOpenLesson` 的基础字段中，应作为独立奖励节点。[^V-hif]

SP 的 HIF 基础率有社区检证线索支持约 **10%**，不是已找到的官方完整抽样公式。可用的暂定边际模型为：

\[
p_{SP,j}\approx\operatorname{clip}\left(0.10+G_j,0,1\right),
\]

其中 `G_j` 为该属性已经汇总的 SP 增加量，包含已生效的支援和 HIF 面板修正时不能再加一次。**Vo、Da、Vi 是否独立抽样，以及副属性分配的联合概率，仍未知。**不应只因为边际率可相加，就默认三色 SP 同时发生的概率是三个边际的乘积。[^V-hif][^M-panel]

休息的通常 HIF 基线为回复最大体力的 50%，社区记录为向下取整；主数据为 `refreshStaminaRecoveryPermil=500`，没有普通休息次数限制。它不是重新抽取商店的 refresh。另有 `stepSkipStaminaRecoveryPermil=250`，属于不同内部动作，不能与“休息回复 50%”混用。[^M-setting]

## 12. 固定剧情节点、支援事件与触发修正

### 12.1 固定剧情奖励

当前 HIF 共通节点有以下可直接定位的效果。[^M-story]

| 节点 | 明确效果 |
|---|---|
| 选拔开场 | 获得 HIF 徽章 |
| 选拔试验 1 后 | 随机删除基本卡 2 张；选择基础自定义 P 道具 |
| 选拔试验 2 后 | 随机删除基本卡 2 张；第一次道具进化 |
| 选拔试验 3 后 | 第二次道具进化 |
| 本战 Round 1 后 | 发放对应应援棒来源奖励；另按考试分数结算星性／P 点 |

**不要把“每次试验后删 2 张基本卡”写成无条件通用规则。**本次读取的共通事件仅在选拔 1、2 后列出删除 2 张，选拔 3 后没有这一项。删除目标不足 2 张的退化处理以及目标是否等权需实测；无论如何不能删除不在合法集合内的牌。

考试分数产生的属性、星性与 P 点应由考试结算模块提供。官方确认选拔结算有属性与星性，本战 R1 有星性与 P 点、R2 有星性；本报告不把这些分数函数冒充随机剧情奖励。[^O-selection][^O-final]

### 12.2 支援卡事件不是一张固定“每次外出概率表”

支援事件由编成、支援卡等级、事件解锁、进度与发生率修正决定。官方只说明会概率发生，没有公开完整的逐日抽样权重。协议保留 `eventProbabilityUpPermyriad`，但单个增加值不足以反推出基础发生率或事件之间的竞争顺序。[^O-support][^M-proto]

在当前所有支援事件目录中，可定位 511 条事件，均没有基础三选一选项列表。它们的数值效果可以归为下表；**这是目录中的效果类别，不是每局 HIF 必然发生的次数或概率**。实际只启用编成支援卡及其等级可达的事件。[^M-support]

| 效果类别 | 目录中出现的基础数值／操作 |
|---|---|
| 单项属性增加 | 10、15、20 |
| P 点增加 | 10、25、40 |
| 体力回复 | 7 |
| 固定资源奖励 | 指定卡／P 道具等资源 1 个，按 `resourceType/resourceId` 判断 |
| 强化 | 自选或随机 1 张，强化增量 1 |
| 普通随机变化 | 随机 1 张，不能当成 Select Change |
| 删除 | 自选或随机 1 张 |

这些事件还受支援自身的 `eventParameterAdditionValueUpPermil`、`eventStaminaRecoverUpPermil`、`eventProducePointAdditionValueUpPermil` 等状态修正。只存事件 ID、不存支援来源及等级，会把固定收益误判为随机数值。

对于支援技能本身，`ProduceSkill.activationRatePermil1` 非零时有明确的千分概率值，例如部分课程后体力回复 4 的技能档位为 300／450／600，即 30%／45%／60%。但它们是否适用于 HIF 的该种公开课，仍要满足具体触发条件。概率为默认 0 的技能不能全部当成永不触发：这类字段和 `alwaysSuccessful` 属于不同配置语义，应结合技能显示文本及实际执行条件解码。[^M-skill]

## 13. 本战继承、容量与面板修正

### 13.1 选拔结束 → 本战开始

官方确认继承三维、最大体力与参数 bonus；保存的是**选拔开始时**的偶像育成、亲爱度、支援编成、记忆编成，以及部分 HIF bonus 状态。卡片、道具、已使用的部分触发与除去／重抽次数也要保存。P 点、饮料和结束时当前体力不直接继承。[^O-memory]

因此，不能拿当前账号亲爱度替换旧选拔记忆中的亲爱度，也不能在进入本战时恢复所有支援触发次数。HIF 徽章累计次数同样应保存在道具状态中；读取并继承实际状态，不在本战开场凭空补满 20 次。

### 13.2 必须进入 RL 状态的几个面板值

| 项目 | 当前主数据 |
|---|---|
| 无加成基础 P 点 | 两阶段配置均为 0；实际起始值还叠加亲爱／面板等 |
| 饮料基础容量 | 3 |
| HIF 饮料配置最大容量 | 4；亲爱 37 有容量 +1 |
| P 点上限 | 9999 |
| 牌组数量上限 | 99 |
| 体力上限配置 | 999 |
| 选拔／本战初始 P 点面板 | 各自 50、80、110、140、170、200 |
| 单属性面板 | 初始属性 +20/+40/+60/+80/+100；相应成长 bonus +2/+4/+6/+8/+10% |
| SP 面板 | +1/+2/+3/+4/+5 个百分点 |
| 本战属性上限面板 | +50/+80/+110/+140/+170/+200 |
| 咨询卡片折扣面板 | 5/10/15/20/25/30% |

初始 P 点面板使用 `ProducePointAdditionDisableTrigger`，不能因此额外触发“获得 P 点时”效果。面板可关闭，且本战继承存在快照语义，所以不能简单用账号面板最高等级。[^M-panel][^M-setting]

| 亲爱度 | 星性获取 bonus |
|---:|---:|
| 27 | 无此项新增 |
| 28 | +5% |
| 29 | +10% |
| 30 | +15% |
| 31 | +20% |
| 32 | +25% |
| 33 | +30% |
| 34 | +35% |
| 35 | +40% |
| 36、37 | +50% |

该表来自亲爱度对应技能和效果记录；星性帮助也明确，亲爱度提高带来的收益从**下一次养成**起生效。[^M-dear][^O-star]

试验前基础回复配置为最大体力 50%，HIF 面板另有 `BeforeAuditionRefreshStaminaUp` 的 50/70/90/110/130/150‰。它与基础回复的具体叠加顺序应对照显示值；不要未经验证直接写成 `50%+15%=65% 最大体力`。Round 2 没有这一自动回复入口。[^M-panel][^O-final]

## 14. 应援棒补牌：可以计算的真实权重

这部分与中场购物策略直接相关，因此纳入环境模型。触发时，系统按**当时山札**距离 22 张的缺口生成基本卡，插入随机位置：

\[
n_{generated}=\max(0,22-|deck_{at\ trigger}|).
\]

原始效果使用 `ExamCardCreateSearch`、`pickCountType=Shortage`、`pickCountMin=pickCountMax=22`，引用的集合是 `p_card_search-deck`。**不能未经触发顺序验证就把这里的山札数量等同于整副养成牌组数量**，因为其他开场抽牌／移牌可能改变当时的山札。[^M-penlight]

附录 B 给出各基本卡的单次归一化权重。`ProduceCardPool` 与 `ProduceCardRandomPool` 在这六组上的原始权重尺度不同，但归一化后逐卡一致。这里可以使用：

\[
P(c\mid pool)=w_c/\sum_{k\in pool}w_k.
\]

例如干劲池中“距离感的基本”权重 75，其余三张各 25，总和 **150**，所以它的概率是 **50%**，不是 75%。两个 Sense 池总权重为 **120**，权重 40 的卡对应 **1/3**，不是 40%。[^M-pool]

多张补牌之间是否按独立重复抽样，以及其他开场生成的排序，仍应通过日志验证。已知单次权重不自动证明所有连续抽样的联合分布。更不能把这些低稀有度基本卡权重用于商店 SSR 生成。

## 15. 推荐的环境状态与转移接口

以下为建模建议，不声称是完整的服务端实现。

```text
episode_state
  version, produce_id, selection_memory_id, day, subphase
  character_id, idol_card_id, plan, recommended_effect
  judging_profile, rank_to_stat, Vo/Da/Vi, stat_bonuses, star, star_bonus
  hp, max_hp, p_points, drinks, drink_capacity
  card_instances[id, upgrade_state, customizations, origin]
  item_states[id, trigger_count, reaction_count]
  support_states[id, level, unlocked_events, completed_events, skill_counts]
  pending_effects[origin, effect_id, target_set, reward_candidates]
  temporary_exam_enchants, permanent_exam_enchants
  shop_inventory[slot, resource, rarity, upgrade, price, next_price, purchased]
  shop_refresh_remaining, card_reroll_remaining, exclude_remaining, excluded_ids
  interval_state[refresh_price, upgrade_count, remaining_services]
  growth_panel_levels_and_toggles_at_relevant_snapshot
```

建议用事件队列，而不是“选一个日程按钮后一步加总所有收益”：

```text
选择入口 → 处理入口触发 → 展示选项
→ 支付合法成本／加入 Trouble → 执行基础效果
→ 按来源生成候选 → 玩家领取／换卡／放弃
→ 处理获取、强化、变化、删除等连锁触发
→ 处理结束触发 → 推进日程
```

上面的流程是组织模型的骨架。不同触发的**精确先后顺序**以实机 `effectResults` 为准；在未确认前，不把它当作已证实的全部服务器执行顺序。

对未知内核建议分两种运行模式：

- **实机回放模式：**直接输入实际候选和结果，先核对所有资源守恒、牌组变化、触发次数与取整。
- **离线规划模式：**使用带版本、来源和置信状态的候选生成器；无数据时可以做多组概率假设的敏感性分析，但训练结果必须注明使用了哪些假设。

不建议在没有数据时把所有未知概率填成 0.5，也不建议让策略通过内部隐藏卡池、未来随机数或未展示候选获得额外信息。

## 16. 未识别参数与后续采样优先级

| 优先级 | 缺口 | 最小有效记录方式 |
|---|---|---|
| P0 | 慰问品卡／饮料稀有度分布 | 每次完整候选，不只记录最终所选；区分基础与道具追加 |
| P0 | 普通咨询与中场的各槽位分布 | 保存所有槽位、价格、强化状态、刷新前后、版本、阶段 |
| P0 | 外出三组卡池与强化概率 | 来源事件 ID、两次卡奖励分别记录、全部候选 |
| P0 | 刷新对已购／强化／删除服务的影响 | 有购买、有强化、空刷各记录一组前后对照 |
| P0 | 中场强化与刷新涨价计数 | 连续空刷、强化后刷新，分开观察 `price/nextPrice` |
| P1 | 上课 A/B/common 的成员和分布 | 计划、推荐效果、PLv、阶段、换出卡状态、全部候选 |
| P1 | 四选三是否等权 | 记录每次“未展示”的那一种，按父节点分组 |
| P1 | SP 联合分布与副属性安排 | 同一天三色全记录，保留支援、面板后的 SP 修正 |
| P1 | 随机强化／删牌是否按实例等权 | 保存所有合法目标，尤其多张同名卡的实例数 |
| P2 | 支援事件发生率 | 同编成多局逐日记录：未发生也要记录，标明已完成事件 |
| P2 | 60% 外出回复、各种奖励的取整顺序 | 奇数最大体力、非整数修正、上限附近的前后值 |

每条观察至少要有：`run_id`、阶段／日数、PLv、选拔开始亲爱度、计划、推荐效果、面板开关、支援编成、道具及剩余次数、所有展示候选、实际选择、变动前后资源、事件来源、截图或视频时间戳。配套采样 JSON 模板保留了这些字段。

### 16.1 样本怎样用于估计

对一个明确的条件组，例如“本战中场第一个购买槽位是否 SSR”，可用二项计数估计并给置信区间；对 R/SR/SSR 使用多项计数。相同商店内的多个槽位可能相关，置信区间和重采样宜按“一次商店生成”分组，而不是把槽位当作互相独立的多局。

在独立二项样本的近似下，最保守的 95% 精度规划：约 96 次对应 ±10 个百分点，约 385 次对应 ±5 个百分点。看到 100 次都没有出现某结果，单侧 95% 上界仍约为 2.95%，不能据此声称概率严格为 0。**本报告的 HIF 粉丝投票追加 P 点 0% 来自官方排除说明，不是零次观察的误推。**

四选三若按父节点记录四种遗漏次数，可以检验是否接近等权；保留全部候选还能区分“先抽稀有度再抽卡”和“直接对卡片加权”两种实现。但在没有服务端权重表前，即便拟合很好，也应叫估计模型。

## 17. 当前交付可直接使用到什么程度

| 模块 | 可直接使用的部分 | 仍须配置／实测的部分 |
|---|---|---|
| 上课 | 阶段数值、成本、三分支、计划映射 | 奖励候选生成、部分换卡退化规则 |
| 外出 | 三分支、60% 回复、卡／饮料领取次数 | 取整细节、具体候选分布 |
| 慰问品 | 投票 bonus 关闭；固定三类奖励结构 | 稀有度与具体卡／饮料权重 |
| 商店 | 已列基础价格、当前面板折扣、服务类型 | 未识别槽位分布、普通刷新细节、价格后段 |
| 定制 | 卡片项目与档位、价格、效果、次数上限 | 个别覆盖／顺序边界需实机回放 |
| 自定义 P 道具 | 全部经济分支、父子关系、触发点和次数 | 四选三权重、特定奖励池分布 |
| 应援棒 | 补到 22 的目标、六组单次权重 | 开场顺序与多抽相关性 |
| 支援／继承 | 事件目录、效果字段、保存的状态 | 逐日发生率与竞争顺序 |

配套数据目录保留的是**规则与证据**，不是一个声称完全复刻概率的模拟器。后续最有价值的新增材料，是一整局连续的事件、候选与日志记录，而不是只截到最终选中了某张卡的画面。

## 附录 A：60 个自定义 P 道具经济状态

以下合并三个计划的经济效果；战斗增益按第 10 节的 B2/B3/B6 展开。SC = Select Change。“普通池”“特定池”“高 SSR 权重池”是不同来源；后者只保留游戏所表达的倾向，精确概率未知。每一行的次数是该节点配置上限，不是每天都重新获得的次数。[^M-pouch][^M-enchant]

### 红色道具

| 状态（日文名） | 触发点 | 次数上限 | 每次经济／卡组效果 | 战斗增益键 |
|---|---|---:|---|---|
| ポーチ（赤） | 公开课结束 | 2 | 体力 +6 | B2，下一场 |
| くま（赤） | 公开课结束 | 2 | 体力 +6；普通饮料随机 1 瓶 | B3，下一场 |
| 花くま（赤） | 公开课结束 | 2 | 体力 +6；普通饮料选 1 瓶 | B3，永久 |
| リボンくま（赤） | 公开课结束 | 2 | 体力 +6；非 Trouble 合法牌 SC 1 张→普通池 | B3，永久 |
| 羽くま（赤） | 公开课结束 | 1 | 体力 +12；高 SSR 权重池选卡 1 张（未强化） | B6，永久 |
| 人形（赤） | 进入咨询 | 1 | 体力 +12；P 点 +40 | B6，下一场 |
| 花人形（赤） | 进入咨询 | 1 | 体力 +12；咨询饮料价格 ×0.5 | B6，永久 |
| リボン人形（赤） | 进入咨询 | 1 | 体力 +12；P 点 +40；咨询强化价格 ×0.5 | B6，永久 |
| メダル人形（赤） | 进入咨询 | 1 | 体力 +12；P 点 +40；咨询删除价格 ×0.5 | B6，永久 |
| 羽人形（赤） | 进入咨询 | 1 | 体力 +12；P 点 +20；咨询卡片价格 ×0.5 | B6，永久 |
| ロボ（赤） | 慰问品结束 | 1 | 体力 +12；非 Trouble 合法牌 SC 1 张→普通池 | B6，下一场 |
| 花ロボ（赤） | 慰问品结束 | 1 | 体力 +12；非 Trouble 合法牌 SC 1 张→高 SSR 权重池 | B6，永久 |
| リボンロボ（赤） | 慰问品结束 | 1 | 体力 +12；高 SSR 权重池选卡 1 张（未强化） | B6，永久 |
| メダルロボ（赤） | 慰问品结束 | 1 | 体力 +6；含眠气的合法牌 SC 1 张→高 SSR 权重池 | B6，永久 |
| 羽ロボ（赤） | 慰问品结束 | 1 | 体力 +6；高 SSR 权重池选卡 1 张（强化） | B6，永久 |
| もじゃ（赤） | 外出结束 | 1 | 体力 +6；随机强化 1 张 | B6，下一场 |
| 花もじゃ（赤） | 外出结束 | 1 | 体力 +6；含眠气的合法牌 SC 1 张→普通池 | B6 + 固定元气 6，永久 |
| リボンもじゃ（赤） | 外出结束 | 1 | 体力 +6；自选复制 1 张 | B6 + 固定元气 6，永久 |
| メダルもじゃ（赤） | 外出结束 | 1 | 体力 +6；自选强化 1 张 | B6 + 固定元气 6，永久 |
| 羽もじゃ（赤） | 外出结束 | 1 | 体力 +6；自选删除 1 张 | B6 + 固定元气 6，永久 |

### 绿色道具

| 状态（日文名） | 触发点 | 次数上限 | 每次经济／卡组效果 | 战斗增益键 |
|---|---|---:|---|---|
| ポーチ（緑） | 公开课结束 | 2 | P 点 +30 | B2，下一场 |
| くま（緑） | 慰问品结束 | 1 | P 点 +60；非 Trouble 合法牌 SC 1 张→普通池 | B6，下一场 |
| 花くま（緑） | 慰问品结束 | 1 | P 点 +60；非 Trouble 合法牌 SC 1 张→高 SSR 权重池 | B6，永久 |
| リボンくま（緑） | 慰问品结束 | 1 | P 点 +60；高 SSR 权重池选卡 1 张（未强化） | B6，永久 |
| メダルくま（緑） | 慰问品结束 | 1 | P 点 +30；含眠气的合法牌 SC 1 张→高 SSR 权重池 | B6，永久 |
| 羽くま（緑） | 慰问品结束 | 1 | P 点 +30；高 SSR 权重池选卡 1 张（强化） | B6，永久 |
| 人形（緑） | 外出结束 | 1 | P 点 +60；随机强化 1 张 | B6，下一场 |
| 花人形（緑） | 外出结束 | 1 | P 点 +60；含眠气的合法牌 SC 1 张→普通池 | B6，永久 |
| リボン人形（緑） | 外出结束 | 1 | P 点 +60；自选复制 1 张 | B6，永久 |
| メダル人形（緑） | 外出结束 | 1 | P 点 +60；自选强化 1 张 | B6，永久 |
| 羽人形（緑） | 外出结束 | 1 | P 点 +60；自选删除 1 张 | B6，永久 |
| インコ（緑） | 公开课结束 | 2 | P 点 +30；普通饮料随机 1 瓶 | B3，下一场 |
| 花インコ（緑） | 公开课结束 | 2 | P 点 +30；普通饮料选 1 瓶 | B3，永久 |
| リボンインコ（緑） | 公开课结束 | 2 | P 点 +30；非 Trouble 合法牌 SC 1 张→普通池 | B3，永久 |
| 羽インコ（緑） | 公开课结束 | 1 | P 点 +60；高 SSR 权重池选卡 1 张（未强化） | B6，永久 |
| うさぎ（緑） | 进入咨询 | 1 | P 点 +100 | B6，下一场 |
| 花うさぎ（緑） | 进入咨询 | 1 | P 点 +60；咨询饮料价格 ×0.5 | B6，永久 |
| リボンうさぎ（緑） | 进入咨询 | 1 | P 点 +100；咨询强化价格 ×0.5 | B6，永久 |
| メダルうさぎ（緑） | 进入咨询 | 1 | P 点 +100；咨询删除价格 ×0.5 | B6，永久 |
| 羽うさぎ（緑） | 进入咨询 | 1 | P 点 +80；咨询卡片价格 ×0.5 | B6，永久 |

### 黄色道具

| 状态（日文名） | 触发点 | 次数上限 | 每次经济／卡组效果 | 战斗增益键 |
|---|---|---:|---|---|
| ポーチ（黄） | 公开课结束 | 2 | 特定饮料随机 1 瓶 | B2，下一场 |
| ロボ（黄） | 公开课结束 | 2 | 特定饮料随机 1 瓶；普通饮料随机 1 瓶 | B3，下一场 |
| 花ロボ（黄） | 公开课结束 | 2 | 特定饮料随机 1 瓶；普通饮料选 1 瓶 | B3，永久 |
| リボンロボ（黄） | 公开课结束 | 2 | 特定饮料随机 1 瓶；非 Trouble 合法牌 SC 1 张→普通池 | B3，永久 |
| 羽ロボ（黄） | 公开课结束 | 1 | 特定饮料随机 2 瓶；高 SSR 权重池选卡 1 张（未强化） | B6，永久 |
| もじゃ（黄） | 进入咨询 | 1 | 特定饮料随机 2 瓶；P 点 +40 | B6，下一场 |
| 花もじゃ（黄） | 进入咨询 | 1 | 特定饮料随机 2 瓶；咨询饮料价格 ×0.5 | B6，永久 |
| リボンもじゃ（黄） | 进入咨询 | 1 | 特定饮料随机 2 瓶；P 点 +40；咨询强化价格 ×0.5 | B6，永久 |
| メダルもじゃ（黄） | 进入咨询 | 1 | 特定饮料随机 2 瓶；P 点 +40；咨询删除价格 ×0.5 | B6，永久 |
| 羽もじゃ（黄） | 进入咨询 | 1 | 特定饮料随机 2 瓶；P 点 +20；咨询卡片价格 ×0.5 | B6，永久 |
| インコ（黄） | 慰问品结束 | 1 | 特定饮料随机 2 瓶；非 Trouble 合法牌 SC 1 张→普通池 | B6，下一场 |
| 花インコ（黄） | 慰问品结束 | 1 | 特定饮料随机 2 瓶；非 Trouble 合法牌 SC 1 张→高 SSR 权重池 | B6，永久 |
| リボンインコ（黄） | 慰问品结束 | 1 | 特定饮料随机 2 瓶；高 SSR 权重池选卡 1 张（未强化） | B6，永久 |
| メダルインコ（黄） | 慰问品结束 | 1 | 特定饮料随机 1 瓶；含眠气的合法牌 SC 1 张→高 SSR 权重池 | B6，永久 |
| 羽インコ（黄） | 慰问品结束 | 1 | 特定饮料随机 1 瓶；高 SSR 权重池选卡 1 张（强化） | B6，永久 |
| うさぎ（黄） | 外出结束 | 1 | 特定饮料随机 2 瓶；随机强化 1 张 | B6，下一场 |
| 花うさぎ（黄） | 外出结束 | 1 | 特定饮料随机 2 瓶；含眠气的合法牌 SC 1 张→普通池 | B6，永久 |
| リボンうさぎ（黄） | 外出结束 | 1 | 特定饮料随机 2 瓶；自选复制 1 张 | B6，永久 |
| メダルうさぎ（黄） | 外出结束 | 1 | 特定饮料随机 2 瓶；自选强化 1 张 | B6，永久 |
| 羽うさぎ（黄） | 外出结束 | 1 | 特定饮料随机 2 瓶；自选删除 1 张 | B6，永久 |

## 附录 B：应援棒基本卡单次权重

仅用于对应应援棒的战斗内补牌。所有列出的生成版本 `upgradeCount=0`。[^M-pool][^M-penlight]

| 推荐效果／应援棒色 | 生成的基本卡 | 权重／总权重 | 单次归一化概率 |
|---|---|---:|---:|
| 干劲／红 | アイコンタクトの基本 | 25/150 | 1/6（16.67%） |
| 干劲／红 | 仕草の基本 | 25/150 | 1/6（16.67%） |
| 干劲／红 | 距離感の基本 | 75/150 | 1/2（50%） |
| 干劲／红 | セルフケアの基本 | 25/150 | 1/6（16.67%） |
| 强气／蓝 | ブランディングの基本 | 25/150 | 1/6（16.67%） |
| 强气／蓝 | 魅せ方の基本 | 50/150 | 1/3（33.33%） |
| 强气／蓝 | 立ち回りの基本 | 50/150 | 1/3（33.33%） |
| 强气／蓝 | ウォームアップの基本 | 25/150 | 1/6（16.67%） |
| 集中／绿 | リアクションの基本 | 20/120 | 1/6（16.67%） |
| 集中／绿 | パフォーマンスの基本 | 40/120 | 1/3（33.33%） |
| 集中／绿 | 思考の基本 | 20/120 | 1/6（16.67%） |
| 集中／绿 | 落ち着きの基本 | 20/120 | 1/6（16.67%） |
| 集中／绿 | タイミングの基本 | 20/120 | 1/6（16.67%） |
| 好调／紫 | ステージングの基本 | 20/120 | 1/6（16.67%） |
| 好调／紫 | ステップの基本 | 40/120 | 1/3（33.33%） |
| 好调／紫 | 視線の基本 | 20/120 | 1/6（16.67%） |
| 好调／紫 | 思考の基本 | 20/120 | 1/6（16.67%） |
| 好调／紫 | タイミングの基本 | 20/120 | 1/6（16.67%） |
| 好印象／黄 | 盛り上げの基本 | 25/150 | 1/6（16.67%） |
| 好印象／黄 | ファンサの基本 | 50/150 | 1/3（33.33%） |
| 好印象／黄 | 笑顔の基本 | 50/150 | 1/3（33.33%） |
| 好印象／黄 | セリフの基本 | 25/150 | 1/6（16.67%） |
| 全力／桃 | アドリブの基本 | 25/150 | 1/6（16.67%） |
| 全力／桃 | スピーチの基本 | 50/150 | 1/3（33.33%） |
| 全力／桃 | 自己管理の基本 | 50/150 | 1/3（33.33%） |
| 全力／桃 | レスポンスの基本 | 25/150 | 1/6（16.67%） |

## 附录 C：供本地 agent 定位的关键数据与排错点

| 数据表／结构 | 用途 | 注意 |
|---|---|---|
| `ProduceStepEventDetail` | 剧情别名到选项／默认效果 | 按效果合并文本，不能按文件记录数当概率 |
| `ProduceStepEventSuggestion` | 成本、基础效果、成功失败分支 | `alwaysSuccessful`；`Permyriad=/10000` |
| `ProduceEffect` | 固定资源、回复、卡组操作、奖励池引用 | `pickCount` 不是展示候选数；池引用不等于有权重 |
| `ProduceStepOpenLesson` | 主／副属性、星性与体力 | 本战对应配置 ID 中的第 04 段，不只搜 `produce_008` |
| `ProduceCustomizeItem` / `Relationship` | 道具节点和进化边 | 名称里的不同颜色不能直接套同一个路线效果 |
| `ProduceCard` / `ProduceCardCustomize` / `GrowEffect` | 卡片实例、定制项目与数值 | 按 `(card_id, upgradeCount)`、`(customize_id, customizeCount)` 联合键读取 |
| `ProduceCardPool` / `ProduceCardRandomPool` | 特定随机池权重 | 只有六组 HIF 补牌池已做归一化一致性核对；其他池成员可能不同 |
| `ProduceGrowthPanel` / `CharacterDearnessLevel` / `ProduceSkill` | 版本化修正 | 选拔开始时快照、ON/OFF、次数和适用阶段 |
| `UserProduceProgressPresent` | 实际慰问品候选与领取 | `isVoteBonus` 字段存在不等于 HIF 会启用 |
| `UserProduceProgressShop` / `Interval` | 实际货位与价签 | 以返回的价格、下一次价格、已购状态为准 |
| `ProduceEffectResult` / `UserProduceProgressEffect` | 连锁事件来源和队列 | 保存 `origin`、顺序、目标与前后值 |

随包的 `hif_event_catalog.json` 包含 92 条 HIF 固定事件、72 个选项、180 条自定义道具及进化关系、511 条支援事件目录、关联效果、公开课参数、六组权重和未知参数列表；还附有卡片版本元数据、343 条定制项目／档位、成长效果及账号等级修正，方便按 ID 继续追踪。支援和卡片参考目录是全局目录，必须按当前编成与合法性筛选，不能当作 HIF 奖励池；包内未提供完整战斗执行器。`sampling_template.json` 用于后续采样，未知概率统一使用 `null`。

## 来源

[^M-version]: [主数据快照提交](https://github.com/vertesan/gakumasu-diff/commit/571dbb62601e78998cddeacdbce3ea1bc672d7fc)。公开提取镜像；本报告固定此提交，不将其称为官方已公开概率表。
[^M-event]: [ProduceStepEventDetail](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceStepEventDetail.yaml)、[ProduceStepEventSuggestion](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceStepEventSuggestion.yaml)、[ProduceEffect](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceEffect.yaml)。外出 `event-detail-activity-003-*`，上课 `event-detail-school-{属性}-003-*`。
[^M-story]: [HIF 共通剧情事件主数据](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceStepEventDetail.yaml)。检索 `event-detail-p_story-003-produce-007` 与 `produce-008`。
[^M-setting]: [Produce](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/Produce.yaml)、[ProduceSetting](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceSetting.yaml)、[Setting](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/Setting.yaml)。
[^M-panel]: [ProduceGrowthPanel](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceGrowthPanel.yaml)。特别是 `produce_growth_panel_sheet-hif-09`，最高级显示文本 `30%` 与效果值 `0300_0300` 相互核对。
[^M-pouch]: [ProduceCustomizeItem](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceCustomizeItem.yaml)、[ProduceCustomizeItemRelationship](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceCustomizeItemRelationship.yaml)。
[^M-enchant]: [ProduceExamStatusEnchant](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceExamStatusEnchant.yaml)、[ProduceExamEffect](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceExamEffect.yaml)。用于核对自定义道具的下一场／永久增益和固定元气差异。
[^M-item]: [ProduceItem](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceItem.yaml)、[ProduceItemEffect](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceItemEffect.yaml)。徽章 ID：`pitem_00-3-265-0`。
[^M-lesson]: [ProduceStepOpenLesson](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceStepOpenLesson.yaml)。48 条配置，按阶段、课程类型、SP 与副属性拆分。
[^M-search]: [ProduceCardSearch](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceCardSearch.yaml)。
[^M-card]: [ProduceCard](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceCard.yaml)、[ProduceDrink](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceDrink.yaml)。
[^M-custom]: [ProduceCardCustomize](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceCardCustomize.yaml)、[ProduceCardGrowEffect](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceCardGrowEffect.yaml)。
[^M-pool]: [ProduceCardPool](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceCardPool.yaml)、[ProduceCardRandomPool](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceCardRandomPool.yaml)。六组 HIF pool 的逐卡归一化权重一致。
[^M-penlight]: [应援棒效果链接所在 ProduceItemEffect](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceItemEffect.yaml)、[补牌效果所在 ProduceExamEffect](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceExamEffect.yaml)。检索 `pitem_01-3-266` 和 `random_shortage-22_22`。
[^M-skill]: [ProduceSkill](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceSkill.yaml)。技能概率字段及显示文本须同时解释。
[^M-support]: [ProduceEventSupportCard](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceEventSupportCard.yaml)、[支援事件详情](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProduceStepEventDetail.yaml)。
[^M-dear]: [CharacterDearnessLevel](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/CharacterDearnessLevel.yaml)、[ProducerLevel](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/ProducerLevel.yaml)。
[^M-proto]: [ptransaction.proto](https://github.com/vertesan/campus/blob/a7f5b047b47594761c9623117f4f8aa159ba38c6/proto/ptransaction.proto)、[pcommon.proto](https://github.com/vertesan/campus/blob/a7f5b047b47594761c9623117f4f8aa159ba38c6/proto/pcommon.proto)、[papi.proto](https://github.com/vertesan/campus/blob/a7f5b047b47594761c9623117f4f8aa159ba38c6/proto/papi.proto)。公开协议结构只证明字段与交互类型，不能代替未公开的服务端抽样实现。
[^O-present]: [官方游戏内帮助：差し入れ](https://stat.game-gakuen-idolmaster.jp/html/help/457083185677d890aeba642fc3ea2defa439f1796a34d8b0c79f1686d0f15419/index.html)。地址由当前 [HelpContent](https://github.com/vertesan/gakumasu-diff/blob/571dbb62601e78998cddeacdbce3ea1bc672d7fc/HelpContent.yaml) 定位；正文明确 HIF 不发生粉丝投票 bonus。
[^O-interval]: [官方游戏内帮助：インターバル](https://stat.game-gakuen-idolmaster.jp/html/help/4d9240eb6dec18e36a036bbfed4e7dfc06e4387ec4e4f35db2be8c5bf139306c/index.html)。
[^O-final]: [官方游戏内帮助：本戦](https://stat.game-gakuen-idolmaster.jp/html/help/3848927b5372f010a0387005b003cb271d475eacc3a4b07a1afb8d823a33411d/index.html)。
[^O-selection]: [官方游戏内帮助：選抜試験](https://stat.game-gakuen-idolmaster.jp/html/help/7c4d347ab6b9a8432d1edb5ffaafa234671d9fe5e12f05e40cc34ae9125020a4/index.html)。
[^O-open]: [官方游戏内帮助：公開レッスン](https://stat.game-gakuen-idolmaster.jp/html/help/de43bb0cbfe2a8118f0630f7ee36f4ff41d3463ec4599dd66d611302e5a162b9/index.html)。
[^O-custom]: [官方游戏内帮助：スキルカードカスタマイズ](https://stat.game-gakuen-idolmaster.jp/html/help/c8badfde900eeb0a979ffe8fdc1632009d163f31b6b991b286336a3b8d8dd05f/index.html)。
[^O-support]: [官方游戏内帮助：サポートカードイベント](https://stat.game-gakuen-idolmaster.jp/html/help/74b138401b3780833b9bbd5096dd3d962f8cd47d141f28b57a3ac5aa75505468/index.html)。
[^O-memory]: [官方游戏内帮助：選抜試験メモリー](https://stat.game-gakuen-idolmaster.jp/html/help/2bab14e7b7e2f34cf831f6ba171377e8e07c1e15e4fbbb6f477083ecbcdfb25b/index.html)。
[^O-star]: [官方游戏内帮助：スター性](https://stat.game-gakuen-idolmaster.jp/html/help/765876e2a01bedfe02f787fe3a00bd486a93172e4f15faafdbdf7ba9de521f2a/index.html)。
[^V-hif]: [学园偶像大师 Wiki：H.I.F](https://seesaawiki.jp/gakumasu/d/H.I.F)。用于日程、商店与慰问品的数值核对及 SP 检证线索。存在与当前面板主数据不一致的旧折扣算例，相关内容已明确标为版本冲突／待验证。
[^V-shato]: [斜籐もなみ：HIF 中场与完整游玩记录](https://note.com/syato_monami/n/n3e6218f3c356)。原始作者的 2026 年游玩说明与截图；用于核对加眠气触发徽章、换卡强化继承、道具分支以及中场不属于咨询。
