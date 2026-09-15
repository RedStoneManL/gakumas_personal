# 自动打牌 / 自动培育评估

> 对应 `docs/OPEN_ITEMS.md` D3（自动打牌脚本）与 D4 的前半（固定 seed 的贪心/搜索）。
> 代码：`gakumas_arena/policies/`、`scripts/eval_exam.py`、`scripts/eval_produce.py`；测试：`tests/test_policies.py`。

## 1. 策略

| 名称 | 类 | 说明 |
|------|----|------|
| `random` | `RandomPolicy(seed)` | 合法动作槽上均匀随机，作为下限 |
| `heuristic` | `HeuristicPolicy(seed)` | gakumas_rl 内置：考试用官方 `ProduceExamAutoEvaluation` 先验 + 一步前瞻（`ProduceRuntime._choose_exam_action`）；培育用 `interfaces.service._choose_planning_action` |
| `search` | `SearchPolicy(depth, samples, seed, leaf=...)` | 仅考试。深度受限 expectimax（思路来自 katabami83 `ContestAI` 的全动作枚举 + 期望估值），状态复制用 `ExamRuntime.capture_preview_state / restore_preview_state` |

接口：`Policy.act(env, obs, info) -> int`；实例本身可调用（`policy(obs, info, env)`），可直接传给 `run_exam(..., policy=SearchPolicy())`。
`SearchPolicy` 还实现 `select_action(runtime)`（`ExamActionSelector` 协议），可注入培育里的考试（`--exam-policy search`）。

### SearchPolicy 细节

- 决策节点：枚举 `runtime.legal_actions()`（出牌 / 饮料 / 结束回合），取最大值；并列取手牌顺序靠前者。
- 机会节点：执行动作后若 runtime 的 `np_random` 状态变了（回合末抽牌、回合颜色、随机检索……），就用 `samples=K` 个由 `(seed, 决策序号, 路径, k)` 派生的 RNG 状态各跑一次取平均；没消耗 RNG 的动作只算一次。
- `depth` 是**动作数（ply）**不是回合数。默认 `depth=2, samples=2`；每加一层约 ×4 开销。
- 叶子估值 `leaf`：
  - `rollout`（默认）：从叶子起用官方先验（`card_play_priors` + `exam_effect_priors`）贪心打到考试结束，取终局分数。rollout 不用饮料——饮料留给搜索层决定。
  - `heuristic`：当前分数 + 剩余资源（元気 / 集中 / 好調 / 絶好調 / 好印象等差数列 / やる気 / 体力 / 手牌先验）的手工权重估值，`resource_weights` / `resource_scale` 可调。**实测比 `rollout` 差，也比 `score` 差**（见 §4），权重未标定，留作实验入口。
  - `score`：只看当前分数。
- 确定性：搜索结束后恢复快照（含 RNG），真实环境的随机流不受搜索影响；同 seed 同局面 → 同动作（`test_search_policy_does_not_disturb_env_rng`）。
- 单次决策统计在 `policy.last_stats`（访问节点数、各候选估值）。

## 2. 怎么跑

```bash
# 考试：单策略 10 局
python scripts/eval_exam.py --scenario 初 --stage mid1 --policy search --seeds 10 --out out/exam.csv
# 考试：相同 seed 上对比多策略（打印汇总表 + 逐 seed 胜负）
python scripts/eval_exam.py --scenario 初 --stage final --compare random,heuristic,search --seeds 20
# 搜索参数：--depth/--samples，或简写 search:d3k2
python scripts/eval_exam.py --compare heuristic,search:d1k2,search:d2k2 --seeds 10
# 培育：外层策略 heuristic / random；--exam-policy search 让培育内考试用搜索打牌
python scripts/eval_produce.py --scenario 初 --compare heuristic,random --seeds 10 --out out/produce.csv
python scripts/eval_produce.py --scenario 初 --policy heuristic --exam-policy search --depth 1 --seeds 10
```

公共参数：`--scenario`（别名或 `Produce.id`：初 / nia / hif / produce-001…）、`--idol`（默认 `i_card-amao-1-000` 花海咲季 R）、`--loadout`（JSON 字符串或 .json/.yaml，字段同 `LoadoutConfig`：`idol_rank` / `producer_level` / `support_card_ids` / `challenge_item_ids`…）、`--seeds N --seed-start S`（seed = S..S+N-1）、`--out CSV`、`--quiet`。

Python 里直接用：

```python
from gakumas_arena.policies import SearchPolicy, evaluate_exam, summarize
rows = evaluate_exam("初", stage="mid1", policy="search", seeds=10, depth=2, samples=2)
summarize([r["score"] for r in rows])   # {'n','mean','median','p10','p90','min','max'}
```

## 3. CSV 列

`eval_exam.py`（每 seed 一行）：

| 列 | 含义 |
|----|------|
| `seed` | 环境 reset 的 seed，同时用作策略 seed |
| `policy` | 策略名（search 会带参数：`search_d2_k2_rollout`） |
| `score` | 考试终局分数（`ExamRuntime.score`） |
| `passed` | 0/1，是否达到 `rank_threshold`（默认前 3）或 `force_end_score` |
| `rank` | 终局名次（1 = 第一；-1 = 不可得） |
| `turns` | 终局回合数（`runtime.turn`，正常结束 = max_turns+1） |
| `steps` | 环境 step 数（出牌 + 饮料 + 结束回合） |
| `wall_s` | 该局耗时（秒，含策略思考） |

`eval_produce.py`：

| 列 | 含义 |
|----|------|
| `label` | `外层策略/考试策略`，如 `heuristic/builtin`、`heuristic/search_d1_k2_rollout` |
| `rating` / `rank` | 评价值与评级（`final_summary.produce_result`，初 走 `hajime_external_formula`） |
| `final_score` | 最终考试分数 |
| `ending_type` | `first_star_a` 等；`failed` = 中途考试失败；`truncated` = 步数用尽 |
| `route_clear` | 0/1 |
| `auditions` | 每场考试 `阶段:pass/fail(分数)` |
| `auditions_passed` / `auditions_total` | 通过场数 / 总场数 |
| `vocal` / `dance` / `visual` / `stamina` | 终局属性 |

汇总表：每策略 `n / mean / median / p10 / p90 / min / max`，以及 0/1 列的比例、`wall_s/ep`；`--compare` 时额外打印相同 seed 下对第一个策略的 胜/平/负 与平均差。

## 4. 首批数字（初 / 默认编成）

条件：`--scenario 初`（produce-001）、`--idol i_card-amao-1-000`（花海咲季 R，无支援卡 / 无 P 道具的 facade 默认编成）、seeds 0–9、2026-09-07 引擎（分数每步取整改动已合入，分数为整数）。
默认编成很弱：`base_score` 600 / `force_end_score` 900，**任何策略 10 局都没通过**（`passed` 全 0），只能比较分数分布。数字随引擎与主数据变化，请以重新跑的结果为准。

### 4.1 考试 mid1（`ProduceStepType_AuditionMid1`，9 回合）

```
              policy |  n |  mean | median |  p10 |   p90 | min |  max | passed | wall_s/ep
              random | 10 |  34.1 |   38.0 | 10.1 |  59.2 |   2 |   70 |   0.00 |      0.06
           heuristic | 10 |  70.5 |   60.5 | 12.9 | 103.7 |  12 |  299 |   0.00 |      0.08
search_d2_k2_rollout | 10 | 146.6 |  125.5 | 60.2 | 251.2 |  53 |  352 |   0.00 |      2.76
```

逐 seed 分数（seed 0–9）：

| | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|--|--|--|--|--|--|--|--|--|--|--|
| random | 40 | 11 | 58 | 38 | 11 | 70 | 38 | 2 | 39 | 34 |
| heuristic | 36 | 62 | 62 | 18 | 61 | 299 | 82 | 13 | 12 | 60 |
| search | 61 | 240 | 126 | 75 | 69 | 352 | 209 | 125 | 53 | 156 |

相同 seed 胜负：search vs heuristic **10 胜 0 负**（平均 +76.1）；search vs random 10 胜 0 负（+112.5）；heuristic vs random 7 胜 3 负（+36.4）。

### 4.2 考试 final（`ProduceStepType_AuditionFinal`）

```
              policy |  n |  mean | median |  p10 |   p90 | min |  max | passed | wall_s/ep
              random | 10 | 133.5 |  122.0 | 59.3 | 203.7 |  35 |  300 |   0.00 |      0.15
           heuristic | 10 | 198.2 |  155.5 | 21.8 | 292.5 |  20 |  765 |   0.00 |      0.12
search_d2_k2_rollout | 10 | 412.2 |  307.5 | 74.9 | 688.4 |  56 | 1574 |   0.00 |      4.20
```

| | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|--|--|--|--|--|--|--|--|--|--|--|
| random | 104 | 179 | 117 | 127 | 35 | 300 | 149 | 69 | 193 | 62 |
| heuristic | 173 | 240 | 148 | 22 | 128 | 765 | 208 | 20 | 115 | 163 |
| search | 56 | 302 | 266 | 188 | 331 | 1574 | 590 | 425 | 77 | 313 |

search vs heuristic **8 胜 2 负**（平均 +214）：seed 0（56 vs 173）与 seed 8（77 vs 115）输给启发式——深度 2 + 贪心 rollout 仍会在个别开局上误判饮料时机；heuristic vs random 7 胜 3 负。

### 4.3 搜索参数消融（mid1，seeds 0–9，取整改动前的引擎，仅供相对比较）

| 配置 | mean | median | 对 heuristic 胜/负 | wall_s/ep |
|------|------|--------|-------------------|-----------|
| heuristic | 186.3 | 104.0 | — | 0.17 |
| search d2 k2 `leaf=score` | 155.0 | 134.4 | 6/4 | 0.55 |
| search d2 k2 `leaf=heuristic`(×0.3) | 125.1 | 88.4 | 5/5 | 0.55 |
| search d1 k2 `leaf=rollout` | 250.2 | 155.1 | 8/1(平1) | 0.51 |
| search d2 k1 `leaf=rollout` | 245.3 | 175.2 | 9/1 | 1.20 |
| **search d2 k2 `leaf=rollout`**（默认） | 250.5 | 200.4 | 8/2 | 2.96 |

结论：叶子用 rollout 是关键，深度从 1 提到 2 主要改善中位数/下限而非均值；手工资源权重（`leaf=heuristic`）在未标定前反而有害。要更快就用 `search:d1k2`（0.5 s/局，效果接近）。

### 4.4 完整培育（初，外层策略）

```
                         label |  n |    mean |  median |     p10 |     p90 |  route_clear | auditions_passed | final_score | wall_s/ep
             heuristic/builtin | 10 |  8992.3 |  8997.5 |  7718.1 |  9855.8 |         1.00 |             2.00 |      6798.6 |      0.39
                random/builtin | 10 | 10558.3 | 10446.5 | 10018.6 | 11249.1 |         1.00 |             2.00 |     10614.1 |      0.35
heuristic/search_d1_k2_rollout | 10 | 10173.5 | 10072.0 |  9782.1 | 10723.2 |         1.00 |             2.00 |     15071.1 |      1.07
```

- 评级：heuristic/builtin 8×B+ 1×A 1×B；random/builtin 8×A 1×A+ 1×B+；heuristic/search 6×A 4×B+。
- **诚实地说：默认编成下，外层每周动作用 random 比 gakumas_rl 的 planning heuristic 高出 +1566 评价值，10 局全胜。** 两者都能过 mid1（都打到 900 强制结束）与 final，差别在于 heuristic 的周计划把 vocal 顶到上限 1000 后仍在堆同一属性，dance/visual 只有 720/793（三维合计 2513）；random 则是 1000/889/989（合计 2878）。初 的评价值公式吃总属性，所以 random 反而高。这说明 D4（培育策略搜索）有很大空间，当前的 planning heuristic 不能当 baseline 用。
- 把培育内的考试换成 `SearchPolicy(depth=1, samples=2)`，最终考试分数均值 6799 → 15071，评价值 8992 → 10174（final 分数在 初 评价值里权重不高，所以提升有限）。

## 5. 已知限制 / 下一步

- `SearchPolicy` 每局 2–4 s（depth 2）；depth 3 约 20 s/局，只适合离线分析。
- rollout 叶子不用饮料、不做 hold 等决策，估值偏保守；`leaf=heuristic` 的资源权重需要用大量 seed 拟合后才能启用。
- 没有 MCTS；D4 的培育外层搜索（贪心 / 束搜索）尚未开始，§4.4 的 random > heuristic 是它的第一个靶子。
- 数字只对应默认编成（R 偶像、无支援卡）。换成像样的编成（OPEN_ITEMS D2）后请重跑并更新本页。
