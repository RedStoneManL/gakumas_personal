# gakumas_arena 架构设计

> 2026-09-08 实现更新：[CONTENT_ARCHITECTURE.md](CONTENT_ARCHITECTURE.md) 和 [CONTENT_AUTHORING.md](CONTENT_AUTHORING.md) 描述已运行的内容包基础设施。下文包含早期设计意图；尤其 `scenarios/hif.yaml` 尚非官方 HIF 执行入口，不能将旧草图当成已完成的配置驱动实现。

> 目标：一个本地、可配置剧本、可复现（seeded RNG）、可给 RL 直接用的 学園アイドルマスター(学マス) 培育沙盒。
> 第一优先剧本：H.I.F編（Hatsuboshi IDOL FESTIVAL，2026-05 上线）。次优先：初(Hajime)、N.I.A.（作为基线和验证对照）。

## 1. 分层

```
┌──────────────────────────────────────────────────────────────┐
│ agents/     启发式 / MCTS / RL policy（PyTorch 等，后期）        │
├──────────────────────────────────────────────────────────────┤
│ env/        Gymnasium 封装：StageEnv(内层打牌) ProduceEnv(外层培育) │
├──────────────────────────────────────────────────────────────┤
│ produce/    培育外循环：周程、行动(课程/休息/外出/商店…)、考试调度     │
│             剧本由 scenarios/*.yaml 驱动，不写死在代码里            │
├──────────────────────────────────────────────────────────────┤
│ gakumas_rl/ vendored 引擎：exam/produce 运行时、效果注册表、Gym env     │
│             （env/ produce/ 两层实际由它实现，gakumas_arena 只做适配）     │
├──────────────────────────────────────────────────────────────┤
│ masterdata/ 解包 master data(YAML→JSON缓存) 访问层（工具/校验用）      │
│ tools/      拉取/转换/对比 master data、覆盖率(新机制)报告            │
└──────────────────────────────────────────────────────────────┘
```

依赖方向只能向下。引擎（`gakumas_rl`）按 `Produce.id` 装配剧本；`gakumas_arena.env` 只做构造/编码适配，
剧本专属规则（H.I.F）后续以 `produce/plugins` 形式接入而不改引擎核心。

## 2. 目录（2026-09-07 修订：facade over gakumas_rl）

引擎本体不再自研：`skyfsj/gakumas-rl` 以包 `gakumas_rl/` vendor 进仓库（GPL-3.0，来源与提交见
`third_party/gakumas_rl_upstream/PROVENANCE.txt`），`gakumas_arena/` 只保留薄适配层。

```
gakumas_arena/
  masterdata/  store.py —— 我们自己的 dump 加载层（YAML→JSON 缓存，table/by_id/where/enum_values）；工具与校验只经它读数据
  env/         make_exam_env() / make_produce_env()：剧本别名(first_star/初/nia/hif…→Produce.id)、偶像卡、
               LoadoutConfig、seed → gakumas_rl 的 GakumasExamEnv / GakumasPlanningEnv；legal_actions(obs)
  sim/         run_exam() / run_produce()：seeded rollout + 策略(random / gakumas_rl 启发式 / callable) → RolloutResult
               （score、逐步 log、ExamRuntime.event_log、dump 版本）
  agents/      random_agent.py（更多 baseline 后续加）
  produce/     scenario.py + scenarios/hif.yaml：剧本配置 DSL（H.I.F 专属机制的落脚点，尚未接入 gakumas_rl）
gakumas_rl/    vendored 引擎：repository/master_data.py(表加载+pickle 缓存+ScenarioSpec), simulation/exam/(效果注册表、
               触发器、ExamRuntime), simulation/produce/(ProduceRuntime、P アイテム解释器), simulation/envs.py(Gym env),
               interfaces/service.py(装配), training/(MaskablePPO/BC)
third_party/gakumas_rl_upstream/   LICENSE、PROVENANCE.txt、上游 README/AGENTS/训练指南
data/          raw/（dump 与缓存，gitignore）、coverage.json（覆盖率报告 JSON）
tools/masterdata/  fetch.sh, build_cache.py, history_diff.py, inspect_dump.py, coverage.py(新机制探测器)
tests/         test_facade.py, test_masterdata.py, gakumas_rl/（上游测试原样搬入）
docs/          rules/ scenarios/ research/（engine_coverage.md 由 coverage.py 生成）
```

依赖方向：`gakumas_arena.env/sim → gakumas_rl`；`gakumas_arena.masterdata` 与 `gakumas_rl.repository` 各自读同一份
`data/raw/gakumasu-diff`（`GAKUMAS_MASTERDATA_DIR` 同时覆盖两者）。不要在 `gakumas_arena` 里复制引擎逻辑；缺的机制
优先在 `gakumas_rl/` 内补（保持可回溯到上游），剧本专属规则走 `produce/plugins`。

## 3. 数据与效果表示（核心决定，2026-09-07 修订）

**唯一真源 = 解包 master data**（`vertesan/gakumasu-diff`，YAML，每表一文件，随游戏版本自动更新）。
不再解析 wiki 文本；wiki/攻略站只用于**校验数值和补充语义**。

- dump 不入库（版权原因）：`tools/masterdata/fetch.sh` 拉到 `data/raw/gakumasu-diff`（gitignore），
  `tools/masterdata/build_cache.py` 一次性转 JSON 缓存（YAML 解析太慢）。
- 访问层：`gakumas_arena/masterdata/store.py` 的 `MasterData.table()/by_id()/where()/enum_values()`；
  其余代码只经过它读数据。
- 关键联表：`ProduceCard.playEffects[].produceExamEffectId → ProduceExamEffect`，
  `ProduceExamEffect.effectType`（`ProduceExamEffectType_*` 枚举，~100 个）+ `effectValue1/2/effectCount/effectTurn`
  + `chainProduceExamEffectIds` + `produceExamStatusEnchantId`（状态附魔）+ `produceExamTriggerId`（触发条件）。
  `ProduceItem/ProduceDrink` 同样引用效果与触发表；`Produce/ProduceStep*/ProduceStepAuditionDifficulty/ResultGradePattern`
  描述培育外循环和评级；`ProduceExamAutoEvaluation*` 是官方自动出牌 AI 的权重表（可直接做 baseline 策略）。
- **效果解释器 = 按 `ProduceExamEffectType` 分发**：现由 vendored `gakumas_rl/simulation/exam/effects/registry.py`
  （`EXAM_EFFECT_REGISTRY`：精确匹配 → `ExamLesson*` 前缀 → fallback 计时效果）与 `simulation/produce/runtime.py::_apply_produce_effect`
  承担。这样新卡随 dump 更新自动可用，不需要手写卡牌定义。注意上游对未知枚举**不抛错**（走 fallback），
  所以 `tools/masterdata/coverage.py` 的报告是唯一的"新机制"信号（见 §8）。
- 之前设计的自研 JSON DSL 降级为「测试/自定义卡」用途，保留但不作为主路径。
- 校验：`ProduceDescription*` 表把枚举映射到日文说明文案，是效果语义的官方文档；再叠加 seesaawiki 的取整/时序表。

## 4. 剧本配置（scenarios/*.yaml）

```yaml
id: hif
weeks: 
  - {week: 1, kind: free, actions: [lesson, sp_lesson, rest, outing, consult]}
  - {week: 6, kind: exam, exam: midterm}
  ...
lesson:
  base_gain: ...
  sp_multiplier: ...
exam:
  midterm: {turns: 6, target: ..., stat_order: by_stat_desc}
special:    # 剧本特有系统（HIF：フェス回合、一番星 等）走 plugin
  module: gakumas_arena.produce.plugins.hif
evaluate:
  rank_table: [...]
```

通用部分靠配置；确实无法配置化的剧本特有逻辑放 `produce/plugins/<scenario>.py`，通过固定的 hook 接口接入（`on_week_start`, `on_action`, `on_exam_end` …）。

## 5. RL 接口（gakumas_rl 的 env，经 `gakumas_arena.env` 构造）

- **考试/课程（内层）`GakumasExamEnv`** ← `make_exam_env(scenario, idol, loadout, seed, stage_type, battle_kind='exam'|'lesson', reward_mode='score'|'clear')`。
  `action_space = Discrete(max_hand_cards + max_drinks + 1)`（手牌槽 / 饮料槽 / 结束回合）；
  `obs = Dict{global: Box(global_dim), action_features: Box(max_actions, feat_dim), action_mask: Box(max_actions)}`，
  每个动作槽的特征 = `EffectTaxonomy` 对卡牌 `ProduceExamEffectType` 多热 + 触发相位多热 + 类别/稀有度/费用类型 one-hot + 14 个数值；
  掩码在 obs 里（`legal_actions(obs)`），非法动作返回 `invalid_action_penalty` 而不是异常。reward 由 `RewardConfig` 决定
  （`score`：势能差分 + 分数增量密集奖励；`clear`：课程 clear/perfect）。终局时 `info` 带 `score`、`rank`、rival 结果。
- **培育（外层）`GakumasPlanningEnv`** ← `make_produce_env(scenario, idol, loadout, seed)`。动作 = `ProduceRuntime.legal_actions()`
  的候选列表（lesson_*/refresh/授業/おでかけ/shop_buy_card_i/customize/audition_select_i…）填进固定槽位，同样带掩码；
  考试子局默认由 gakumas_rl 的启发式（`ProduceExamAutoEvaluation` 先验 + 一步前瞻）自动打，或用 `exam_action_selectors`
  接入训练好的考试 policy（`PlanningExamCheckpointSelector`），即分层策略。
- **可复现**：`env.reset(seed)` → gym `np_random` → 派生 `ExamRuntime(seed)` / `ProduceRuntime(seed)` 的
  `numpy.random.default_rng`；洗牌、回合颜色、随机卡、饮料库存、事件全部走它。`tests/test_facade.py` 断言同 seed 同分。
  MCTS 用 `ExamRuntime.capture_preview_state()/restore_preview_state()`。
- **便捷入口** `gakumas_arena.sim.run_exam / run_produce(scenario, idol, seed, policy)` 返回 `RolloutResult`
  （score、total_reward、逐步 log、event_log、dump commit）；`policy` 可为 `'random' | 'heuristic' | 'end_turn' | callable(obs, info, env) -> int`。
- 训练：沿用上游 `gakumas_rl.training`（SB3 `MaskablePPO` → 固定 seed 轨迹选优 → masked BC → 微调；可选 extras `.[sb3]`）。

## 6. 校验策略

1. 单元测试：每个 op、每个状态效果的公式（对照 wiki 数值）。
2. 与开源引擎对拍：把 gakumas-core / gakumas-engine 的同一牌组、同一 seed 场景跑出来的分数序列做 fixture。
3. 真机录像/攻略站的"回合记录"作为端到端用例。

## 7. 里程碑

| # | 内容 | 产出 |
|---|------|------|
| M0 | 调研 + 骨架（本轮） | docs/、包结构、DSL schema |
| M1 | master data 加载层 + 枚举图谱 + 类型化视图 | masterdata/, docs/research/master_data_*.md |
| M2 | 卡牌引擎跑通 センス/ロジック；对拍开源引擎 | engine/, tests |
| M3 | アノマリー + 全部状态效果 | engine/ |
| M4 | 培育外循环：初(Hajime) 基线 | produce/, scenarios/hajime.yaml |
| M5 | H.I.F 剧本 | scenarios/hif.yaml, plugins/hif.py |
| M6 | Gym env + 启发式 agent + 自动打牌脚本 | env/, agents/ |
| M7 | RL 训练（PPO 等） | 训练脚本 |

## 8. 数据时效性与新机制兼容（设计原则）

- **数据版本可追溯**：`MasterData` 记录 dump 的 commit/日期（`masterdata_json/_meta.json`）；每次模拟结果带上数据版本。
  `tools/masterdata/fetch.sh` 一条命令更新；`tools/masterdata/history_diff.py` 比较两个 commit 之间新增的表/枚举值/配置改动。
- **未知即报告**：gakumas_rl 对未注册的 `ProduceExamEffectType` 走 fallback（当作计时效果），未知 `ProduceEffectType`
  / 相位 / 步骤类型则静默忽略，运行时不会抛错。因此 `tools/masterdata/coverage.py` 是新机制探测器：扫描
  `ProduceExamEffectType` / `ProduceEffectType` / 触发相位 / `ProduceExamStatusEnchant`（派生）/ `ProduceCardGrowEffectType` /
  `ProduceStepType`，用 gakumas_rl 的注册表与 `ids` 常量（兜底 grep 源码）判定 handled / referenced / unhandled，
  列出行数与使用它的卡/道具，写 `docs/research/engine_coverage.md` + `data/coverage.json`；`--strict` 有未处理值即退出 1。
  **每次 dump 更新后先跑它**。
- **结算公式版本化**：评价/评级/分数换算不硬编码，放在 `rules/scoring/*.yaml`，带 `effective_from` 日期与来源
  （master 表优先：`ResultGradePattern`、`ProduceExamBattleScoreConfig`、`ProduceStepAuditionDifficulty`；wiki 公式次之）。
- **剧本以 `Produce.id` 为键**：新剧本 = 新配置 + 可选 plugin，不改引擎核心。
- **回归对拍**：固定 seed + 固定牌组的黄金分数序列作为 fixture；升级 dump 后跑一遍，差异即为版本变更信号。
