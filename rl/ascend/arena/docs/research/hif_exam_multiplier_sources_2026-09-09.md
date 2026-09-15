# HIF 局内倍率：公开资料核查

2026-09-09。当前结论：找到部分规则与主数据，尚未找到可直接复用的完整 HIF 原始属性换算实现。本次只更新文档，没有添加近似计分公式。

## 用户提供的 Wiki

[H.I.F Wiki](https://seesaawiki.jp/gakumasu/d/H.I.F)，页面标注最后更新 2026-09-05。核对“スター性について”和“H.I.F本戦について → 審査基準・ターン割”两节。

| 资料明确给出的内容 | 能支持什么 |
|---|---|
| 本战 Round1/2 的スター性基准为 600/800 | 按场次选择基准 |
| 达到基准时スター性因子为 2；低于基准约 1.85–2，高于基准 2–3，上限 3 | 基准点和范围，未给出完整曲线 |
| 三维基础分数加成、亲爱度分数加成、スター性因子依次作用 | 分层处理，不重复应用 |
| 一维不足会降低其余两维的加成 | 不能只做三个互相独立的单维函数 |

该页直接注明：**“スコアボーナスの詳細な計算式は調査中”**。因此，不能仅从这些范围和基准点推出 star=900 或 1000 的精确因子，也不能确定各层取整顺序。上述描述是公开检证资料，未作为完整函数实现验收。

## 主数据与 golden 的实际范围

本地主数据来自 [vertesan/gakumasu-diff](https://github.com/vertesan/gakumasu-diff)，记录版本 `571dbb62601e78998cddeacdbce3ea1bc672d7fc`。可定位以下文件：

- `data/raw/masterdata_json/ProduceExamBattleConfig.json`：广 Round2 配置 `p_exam_battle_config-voda-03-produce_008-02`，三维基准 `[1871, 1392, 1088]`，12 回合。
- `ProduceExamBattleScoreConfig.json`：对应属性曲线节点；例如 Vo 在 1871 为 6772 permil，Da 在 1392 为 4908 permil，Vi 在 1088 为 3662 permil。这些是表值，不是本场最终百分比。
- `ProduceStepAuditionDifficulty.json`：对应 `starScoreBonusBaseLine=800`。
- `Setting.json`：`produceExamBattleScorePenaltyMinPermil=100`、`produceExamBattleScorePenaltyMaxPermil=250`。常量本身不能证明 HIF 的具体调用方式和取整顺序。
- `ExamSetting.json`：局内增益、消耗及抽牌等设置；未提供完整的 HIF star 换算函数。

[gktools 原生倍率源码](https://github.com/surisuririsu/gakumas-tools/blob/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/packages/gakumas-engine/typeMultipliers.js) 提供最终百分比输入和普通 contest 属性换算，没有 HIF star 参数。

[gktools HIF utility](https://github.com/surisuririsu/gakumas-tools/blob/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/gakumas-tools/utils/hif.js) 计算培育完成后的评价值及分数兑换スター性，不是开局倍率解析器。

## 对训练入口的影响

当前 `hif_round2_entry(score_percents=[...])` 可自由配置三色最终百分比，课程可以改变它们；并非只能运行单一固定课程。局内卡牌、道具和结算仍由用户指定的 golden 执行。

**当前没有公共 `raw Vo/Da/Vi + star → HIF score_percents` 解析器。** 因此现有训练成绩可用于给定倍率下的出牌策略，不能直接据此计算培育增加 100 Vo 或 20 star 的收益。

剩余实现依据是完整 star 曲线、跨属性不足惩罚的组合方式、各层取整规则。无需把重新采集实机截图作为前置条件；若取得可复用公开实现，可固定其版本接入。未经来源支持的线性插值不作为 golden。

更完整的入场解析契约和原始数据摘录见 [RL 的倍率核查](../../../../design/rl-selection-20260908/HIF_SCORING_AND_TURN_AUDIT.md)。

## 新增用户实机样本：仅本战 Round 1

用户补充四张截图并明确要求记作第一轮：[可读记录](hif_round1_multiplier_observation_2026-09-09.md)、[结构化观察](hif_round1_multiplier_observation_2026-09-09.json)。三维 `[2759,1727,1209]`、入场スター性 `915`，局内菜单最终百分比为 **`[4397,2997,2223]`**，共 9 回合。审查界面显示スター性基准 600。

开场两帧分别显示 `[977,666,494]` 与 `[1466,999,741]`。后者直接乘 3 会得到 Vo 4398%，而最终为 4397%；因此要保留显示取整与内部计算的区别。该样本没有补齐整个原始属性换算函数，不能迁移为 Round 2 的默认倍率，也不与此前 508647 分的第一轮日志合并。

## 新增用户实机样本：本战 Round 2

用户随后明确提供第二轮的三阶段截图：[可读记录](hif_round2_multiplier_observation_2026-09-09.md)、[结构化观察](hif_round2_multiplier_observation_2026-09-09.json)。三维 **`[2759,1744,1209]`**、入场スター性 **1083**，本轮スター性基准 **800**。三个阶段依次显示 `[977,670,494]` → `[1466,1005,741]` → **`[4208,2886,2128]`%**。

最后数值来自开场スター性加成画面；本组没有局内菜单、回合数或回合顺序截图。它与第一轮样本单独保存，不能套用第一轮的 600 基准、近似 3 倍关系或 9 回合顺序。
