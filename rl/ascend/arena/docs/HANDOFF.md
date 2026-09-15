# 交接说明（HANDOFF）

**当前训练交接从 [AGENT_ENTRY.md](../AGENT_ENTRY.md) 进入。** `TrainingExam` 已支持可自定义的 HIF 本战 2 / 单偶像 golden 考试，实机校准不作为当前开训前提；调用见 [使用指南](ARENA_USAGE_GUIDE.md)，范围见 [验收矩阵](ARENA_ROUND2_READINESS.md)。旧 `ArenaExam` 仍是私有调试接口；下文保留历史架构，不能替代本轮范围。

> **2026-09-09 当前入口更新：**用户指定 gakumas-tools 为局内规则 golden；已直接纳入原始源码与数据，新 `gakumas_arena.create_exam` / `gakumas_arena.engine` 可运行。旧 HIF/Gym/Content/live 路径仍兼容，未整体改接；范围、验证和下一步迁移见 [ARENA_GOLDEN_ENGINE](ARENA_GOLDEN_ENGINE.md)。

> **2026-09-08 内容基础设施更新**：新增 `gakumas_arena.content` 配置编译、通用流程与显式选择恢复；本包已不只承担薄 facade。
> 新内容从 [CONTENT_AUTHORING.md](CONTENT_AUTHORING.md) 入手；当前验收和兼容边界见 [ARENA_CONTENT_UPDATE.md](ARENA_CONTENT_UPDATE.md)。
> 以下原始架构及历史胜率不能替代最新实现状态。

> **2026-09-07 Arena 接手更新**：当前开发分支 `codex/arena-live-bridge`，最新实现/测试/未完成范围见 [ARENA_ENGINE_UPDATE.md](ARENA_ENGINE_UPDATE.md)，实况联调先读 [LIVE_CONTRACT.md](LIVE_CONTRACT.md)。以下其余内容保留 ef24029 的历史交接状态。

> 写给接手这个仓库的下一个 agent / 开发者。**先读这一页，再读 `docs/ARCHITECTURE.md` 和 `docs/OPEN_ITEMS.md`。**
> 截止提交：见 `git log`；主数据 dump 版本见 `data/raw/masterdata_json/_meta.json`。

## 1. 这个项目是什么

学園アイドルマスター（学マス / gakumas）**培育模式的本地沙盒**：可配置剧本、seeded 可复现、Gymnasium 接口，
目标是先有沙盘能算出最优策略，再做自动培育 / 自动打牌脚本，最后给 RL 训练用。**第一优先剧本是 H.I.F編**。

## 2. 最重要的三个事实

1. **引擎不是自研的。** 仓库把 [skyfsj/gakumas-rl](https://github.com/skyfsj/gakumas-rl) vendor 成包 `gakumas_rl/`
   （GPL-3.0，整个发行物因此按 GPL-3.0 继承；出处见 `third_party/gakumas_rl_upstream/PROVENANCE.txt`）。
   选它的唯一理由：**它是全网唯一直接解释解包 master data 效果枚举的引擎**，其余项目都是手写卡牌定义
   （对比见 `docs/research/existing_engines.md`）。`gakumas_arena/` 只是薄 facade。
2. **数据是解包 master data，不是攻略站文本。** 单一真源 `vertesan/gakumasu-diff`（YAML，每表一文件，随游戏版本自动更新，
   与线上延迟 < 1 小时）。卡牌效果 = `ProduceCard.playEffects → ProduceExamEffect.effectType`（`ProduceExamEffectType_*` 枚举）。
   dump 不入库，用 `tools/masterdata/fetch.sh` 拉到 `data/raw/`。
3. **「跑通」不等于「数值正确」。** 全量测试绿 ≠ 分数和实机一致。所有「代码里已做选择但未经实机验证」的点都在
   `docs/OPEN_ITEMS.md`，代码里以 `TODO(HIF-verify)` 和 `ScoringRules` 开关标注。**不要把这些当成已验证的事实。**

## 3. 现在能用的东西

```python
from gakumas_arena.sim import run_exam, run_produce
run_exam("first_star", seed=1, policy="heuristic")     # 一局考试/课程
run_produce("hif", loadout="hif_sense_default", seed=1, policy="heuristic")  # 一次完整培育
```

```bash
python -m pytest tests -q                       # 397 passed, 3 skipped, 1 xfailed
python tools/masterdata/coverage.py --strict    # 新机制探测器：退出码 1 = dump 有引擎未处理的枚举值
python scripts/eval_exam.py    --scenario first_star --policy compare --seeds 10
python scripts/eval_produce.py --scenario hif --loadout hif_sense_default --seeds 10
```

- 三个剧本路线可跑：初（produce-001~003/006）、N.I.A.（004/005）、**H.I.F（007 選抜試験 20 步 / 008 本戦 9 步）**。
- 枚举覆盖率 100%：107 个考试效果、66 个培育效果、29 个触发相位、39 个成长效果、33 个步骤类型全部有处理器
  （`docs/research/engine_coverage.md`）。
- 策略：`random` / `heuristic`（官方 `ProduceExamAutoEvaluation` 权重 + 1 步前瞻）/ `search`（深度受限 expectimax，
  rollout 叶子评估）。初 中间考试均分：random 34 / heuristic 70 / search 147。

## 4. 现在**不**能用的东西（按优先级）

| 优先级 | 问题 | 位置 |
|---|---|---|
| **P0** | **HIF 通过率 0/10**：修掉分数爆炸后，heuristic + 预设编成 選抜1 全部不过（初剧本 6/6 正常，所以不是修过头） | `OPEN_ITEMS.md` C0 |
| **P0** | **课程不发技能卡**：初/HIF 的课程都没有 3 选 1 卡片奖励，卡组整局停在 13–15 张 —— 推断是 HIF 过不了的主因 | `OPEN_ITEMS.md` B6 |
| **P0** | **絶好調 建模错误**：实机录像证明是回合型且叠加为回合数相加，引擎按层数建模。影响分数公式本身 | `OPEN_ITEMS.md` A9 |
| P1 | HIF 相談（商店）未作为每周动作暴露 | `OPEN_ITEMS.md` B2 |
| P1 | 取整审计未完成（agent 被额度中断），`docs/rules/scoring_fidelity.md` 未写出 | `OPEN_ITEMS.md` A1 |
| P1 | スター性 的换算与加成曲线全是推断值 | `OPEN_ITEMS.md` A3/A4 |
| P2 | 隐藏概率（SP 率、事件权重、商店刷新、回合颜色分布）全为近似 | `OPEN_ITEMS.md` B5 |

**`docs/loadouts.md` 里 選抜 通过率 17–20/20 的数字是分数爆炸修复前测的，已失效**，修好 B6/B2 后必须重测。

## 5. 怎么验证你的改动是对的

按可信度从高到低：

1. **实机录像回归**（唯一的 ground truth）：`tests/gakumas_rl/fixtures/recorded_games/*.jsonl`，9 段来自
   gakumas-core 的 YouTube 录像逐回合数据（8 通过 / 1 xfail，xfail 那条正是 A9 的证据）。
   新增夹具格式见 `tests/gakumas_rl/recorded_game_harness.py`。**改分数公式必须跑这套。**
2. **规则文档**：`docs/rules/lesson_exam_engine.md`（取整、相位时序、三系公式）、`produce_loop.md`、`glossary.md`。
   每条结论都标了来源和「确认 / 推断」。
3. **master data 本身**：`docs/research/master_data_atlas.md`（127 表逐字段）、`master_data_enums.md`
   （214 枚举，169 个考试效果类型逐条语义 + 日文标签 + 示例）。`ExamSetting` 单行装着全部引擎常数。
4. **社区计算器对拍**：`docs/research/data_sources.md` 列了可读源码的计算器（HIF 评价公式已三方交叉确认）。

## 6. 数据更新后的固定流程

```bash
tools/masterdata/fetch.sh                       # 拉 dump + 翻译数据，重建 JSON 缓存
python tools/masterdata/coverage.py --strict    # 退出码 1 = 有新机制没实现
python tools/masterdata/history_diff.py A B     # 两个 commit 间新增的表/枚举值/配置改动
python -m pytest tests -q                       # 黄金分数序列变化 = 版本改动信号
```

注意：**结算公式的改动经常不在 master data 里**（例：2025-10-31 的最终考试分数上限、レジェンド 2.1 系数、HIF 换算
都是客户端代码侧），所以评价公式要按生效日期版本化，不能只信 dump（`docs/research/mechanics_timeline.md`）。

## 7. 协作约定

- `gakumas_rl/` 是 vendored 代码：改动请留在该目录内并在 PROVENANCE 里记录，方便日后与上游对比。
- 代码注释用中文（沿用上游 `AGENTS.md` 约定，见 `third_party/gakumas_rl_upstream/`）。
- 未实现的枚举值必须**报错而不是静默吞掉**（`GAKUMAS_STRICT_EFFECTS=1` 走严格模式）。
- 推断值一律配 `TODO(HIF-verify)` 注释 + 配置开关，并登记到 `docs/OPEN_ITEMS.md`。
- 多 agent 并行时按文件划分归属，避免同时改 `simulation/exam/**` 与 `simulation/produce/**`。
