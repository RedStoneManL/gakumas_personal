# 路线图（PLAN）

> 2026-09-07 接手：M5-a 已完成；M6 的课程三选和咨询模拟已完成首版，HIF 通过率仍 0/10。实况契约/奖励与咨询绑定已交付，考试/其余页面绑定继续推进。详情和确切限制见 [ARENA_ENGINE_UPDATE.md](ARENA_ENGINE_UPDATE.md)。下表其余状态保留原计划历史。

> 目标：本地沙盒 → 能算出最优策略 → 自动培育/自动打牌脚本 → RL 训练。第一优先剧本 H.I.F編。
> 当前进度与阻塞见 `docs/HANDOFF.md`；逐条待验证项见 `docs/OPEN_ITEMS.md`。

## 里程碑

| # | 内容 | 状态 | 产出 |
|---|------|------|------|
| M0 | 调研（现有引擎、数据源、规则、剧本、机制时间线） | ✅ | `docs/research/`、`docs/rules/`、`docs/scenarios/` |
| M1 | 主数据加载层 + 图谱 + 枚举字典 + 覆盖率探测器 | ✅ | `gakumas_arena/masterdata/`、`tools/masterdata/` |
| M2 | 引擎底座（vendor gakumas-rl）+ facade + Gym env | ✅ | `gakumas_rl/`、`gakumas_arena/env`、`sim` |
| M3 | H.I.F 支持：9 个考试效果类型 + 培育路线 + 评价公式 | ✅ | `simulation/produce/hif.py`、`produce_score.py` |
| M4 | 编成预设 + 评估脚本（random / heuristic / search） | ✅ | `gakumas_arena/loadouts.py`、`scripts/eval_*.py` |
| **M5** | **数值保真：取整审计 + 实机录像回归 + 修 絶好調 建模** | 🔄 进行中 | `tests/gakumas_rl/fixtures/recorded_games/`、`docs/rules/scoring_fidelity.md`（待写） |
| **M6** | **补齐培育机制：课程发卡、HIF 相談商店** | ⬜ 未开始 | `simulation/produce/runtime.py` |
| M7 | HIF 能稳定通关 → 策略搜索（束搜索 / MCTS）出「最优打法」 | ⬜ | `gakumas_arena/policies/` |
| M8 | RL 训练（MaskablePPO + BC 自举，上游已有流程） | ⬜ | `gakumas_rl/training/` |
| M9 | 实机数据采集与拟合（隐藏概率、スター性 换算） | ⬜ | 录像 → jsonl 采集格式 |

## 下一步建议顺序

1. **M5-a 修 絶好調 建模**（`OPEN_ITEMS.md` A9）。它同时影响分数公式，先改这个再谈其他数值。
   改完跑录像夹具，那条 xfail 应转绿。
2. **M6 课程发卡**（B6）+ **HIF 相談商店**（B2）。这是 HIF 过不了選抜的推断主因。
3. **重测 HIF 基线**：`scripts/eval_produce.py --scenario hif --loadout hif_sense_default --seeds 20`，
   更新 `docs/loadouts.md`（现有数字已失效）和 `OPEN_ITEMS.md` C0。
4. **M5-b 补完取整审计**，写出 `docs/rules/scoring_fidelity.md`（被中断的 agent 未产出）。
5. **M7 策略搜索**：HIF 能稳定通关后，用 `search` 策略跑分数分布，对比 heuristic，产出「最优打法」结论。
6. **M8 RL**：`gakumas_rl/training/` 有现成的 MaskablePPO → 固定 seed 轨迹选优 → masked BC → 微调 流程。
   注意 `EffectTaxonomy.action_types` 尚未加入 HIF 动作（`OPEN_ITEMS.md` B1），影响特征表达力。

## 设计约束（不要违反）

- **数据驱动**：新卡/新机制随 dump 更新自动可用，不手写卡牌定义。
- **未知即报错**：未实现的枚举值抛异常，不静默降级（`GAKUMAS_STRICT_EFFECTS=1`）。
- **可复现**：所有随机性走单个 seeded RNG；同 seed 同结果是测试断言。
- **公式版本化**：结算规则按生效日期配置，因为部分改动不出现在 master data 里。
- **剧本以 `Produce.id` 为键**：新剧本 = 新配置 + 可选 plugin，不改引擎核心。
