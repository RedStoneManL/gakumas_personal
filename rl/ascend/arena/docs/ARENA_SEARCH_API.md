# Arena 公开历史搜索接口

2026-09-14，响应 [Arena 搜索接口契约](../../../design/rl-search-split-20260914/ARENA_SEARCH_CONTRACT.md) 与 [联合训练设计](../../../design/rl-search-split-20260914/DESIGN.md)。

**已提供独立搜索接口，可接入隔离实验。生产联合 PPO 没有切换。** 这是有限加权粒子采样器，必须逐根检查成功、权重与预算；不保证任意卡组、任意历史都能在两秒内采到足够世界。完整基准和失败场景见 [验收记录](ARENA_SEARCH_ACCEPTANCE.md)。

事实来源沿用 [DATA_AUTHORITY](DATA_AUTHORITY.md)：解包主数据的明确字段优先，局内执行继续由当前有效版本的原生 JS 完成。本功能不改卡牌、费用、计分、随机事件概率或训练奖励。搜索专用 loader 仅在自己的进程内接入 RNG 保存、公开抽牌记录、条件提案与工作计数；原生产 loader、TrainingExam 及 vendor 文件没有因本功能修改。

## 给 RL 的接口映射

```python
from gakumas_arena.engine.search import (
    SearchClient, SearchBudget, RecordedExam, SearchWorld,
    public_history, append_public_transition,
    public_build_rules, search_content_version, search_capabilities,
)
```

| 需求 | 实际入口 | 结果与边界 |
|---|---|---|
| 完整公开轨迹 | `client.create_recorded_exam(entry, seed=...)`；`live.export_public_history()` | 初始观察、每次原生动作/choose、后继观察、有序公开抽牌 ID；导出不含真实 seed |
| 接已有 recorder | `public_history(...)`、`append_public_transition(...)` | 必须从初始观察起完整记录；无抽牌 trace 时退化为有界全历史拒绝采样 |
| 条件采样 | `search.sample_public_worlds(entry, history, search_seed=..., particles=..., budget=...)` | `status`、`valid_for_search`、`worlds`、`weights`、ESS、重复/不同粒子数、分布假设、版本与成本 |
| 假想世界分支 | `world.clone()` | 常驻状态复制，不重建考试、不重放整段历史；不是常数时间承诺 |
| 原生推进 | `world.step(command, budget=..., cancel=...)` | 当前原生命令一次执行；嵌套选择仅重跑正在等待选择的这一个命令 |
| 公开输入 | `world.observe()` | 仅 `observation`、有序 `partial_selection`、子选择版本、合法 `actions`、`public_history_key` |
| 部分多选 | `choice_append` / `choice_finish` | append 不推进原生规则或 RNG；finish 一次提交有序原生 choose |
| 批量推进 | `client.step_batch([(world, command), ...], budget=...)` | 共享本次请求预算、按序完成；失败返回已完成前缀，未执行/失败项不计为终局 |
| 回收与限制 | `world.release()`、`client.stats()`、`SearchClient(max_worlds=...)` | 有界常驻句柄；释放后不能复用 |
| 构筑可知规则 | `public_build_rules(entry, turn_order_known=False, drink_supply=...)` | 默认抽/弃/洗/保留规则、配额、信息公布阶段；未来实际饮料库存不进入该对象 |

`RecordedExam` 是新增的记录会话，未替换原 `TrainingExam`。它的公开观察经过与后者同 seed 对照。真实采集器若继续使用 `TrainingExam`，需自己从开局保留完整公开轨迹，不能拿 `inspect_private()` / `snapshot()` 补采样器输入。不要根据最新手牌猜造遗漏的抽牌历史。

## 最小接入

实际局 recorder 与可取消的搜索必须放在**两个不同的 client/worker**。硬取消会销毁其所属 worker 的所有句柄，因此不能把真实采集局放进同一个可销毁 worker。单 worker 同时放诊断 recorder 与假想世界只适合一次性接口诊断。

```python
from gakumas_arena.engine.training import make_training_entry
from gakumas_arena.engine.search import SearchClient, SearchBudget

entry = make_training_entry([647] * 8, turn_types=["vocal"] * 4)
with SearchClient() as recording, SearchClient(max_worlds=64) as search:
    live = recording.create_recorded_exam(entry, seed=123)  # 实际局随机源
    history = live.export_public_history()                 # 不含 seed
    sampled = search.sample_public_worlds(
        entry, history, search_seed=880001, particles=4,    # 独立搜索随机源
        budget=SearchBudget(milliseconds=2000, candidates=512),
    )
    if sampled["valid_for_search"]:
        try:
            parent = sampled["worlds"][0]
            with parent.clone() as branch:
                policy_view = branch.observe()
                # 此处交给 RL 的网络/搜索树；示例只选一个合法动作。
                result = branch.step(policy_view["actions"][0])
                # 只有 status == "terminal" 才使用实际 final_score。
        finally:
            for world in sampled["worlds"]:
                world.release()
    else:
        # 明确记录失败；不制造搜索动作分布或 0 分终局。
        print(sampled["status"], sampled.get("diagnostics"))
    live.close()
```

可运行例子：[example_public_search.py](../scripts/example_public_search.py)。它从多个粒子分别续局到真正终局，报告按粒子权重计算的均值；只是接口示范，未实现 MCTS，也不声明涨分。

```powershell
Set-Location C:/Users/Liu/Documents/ChatGPT/gakumas/third_party/gakumas_arena
.venv/Scripts/python.exe -X utf8 scripts/example_public_search.py
```

真实动作仍通过 `live.act(observation["actions"][i])` 或 `live.choose(indices, decision_version=...)` 提交。每次成功提交自动追加公开历史。中间 append/finish 是搜索树的动作形式；真实 recorder 只记录一次最终 `choose`，直接给 recorder 提交 append/finish 会在变更前拒绝。

## 策略输入与多选

`world.observe()["observation"]` 复用 `arena-public-exam/1`。`view["actions"]` 在普通节点与原生合法动作相同，在 choice 节点展开为子动作。原 `observation["choice"]` 保留 min/max、ordered、skip、来源及完整候选实例。

```python
view = world.observe()
# 从 view["actions"] 选动作，包含实例 ID 和两个版本号：
# {type: "choice_append", index, instance_id,
#  decision_version, selection_version}
result = world.step(view["actions"][0])
# 之后重新 observe；达到 min 才有 choice_finish，达到 max 不能再 append。
```

append 只更新公开的有序索引序列及 `selection_version`。不耗牌、不抽牌、不扣费，不增加 native/rule/RNG/replay 计数。重复候选、过期版本、未达到 min 的 finish 都原子拒绝。完整 choose 与 append→finish 的后继观察及公共历史键一致。

模型只能接收 `view`，以及该实验阶段已公布的 entry/构筑信息。**句柄、粒子数组索引、seed、成本、拒绝诊断及内部状态不得作为策略特征或树的决策键。** 同一公开历史共享决策节点，真正出现新的公开抽牌结果后才分树。各粒子权重用于机会节点期望，不能先在每个隐藏世界各自选最优动作再平均。

## 条件采样的分布与限制

方法标识：`draw-conditioned-sequential-importance/1`。

1. 从独立搜索 seed 生成独立提案；按当前原生引擎建局，重放完整实际公开动作历史。
2. Fisher–Yates 洗出的随机排列保留可交换槽位。遇到公开抽牌，条件化该槽位并乘以 `1 / 剩余可交换槽位数` 的历史似然。无放回相关性、强制开局牌分区和洗牌边界都保留。
3. 随机单张检索只固定/移走被选实例，保留未选槽位的随机顺序；向完全可交换的牌山均匀插牌后仍是均匀排列。固定牌顶与已知相对顺序不会因此丢失。
4. 当前明确保守处理的顺序相关方法包括 `useAllCardsFree`、`moveAllToHandByTarget`、`moveAllToTopOfDeckByTarget`、`holdAllByTarget`：固化当时抽到的潜在排列，随后按完整历史拒绝不兼容提案。未知新 CardManager 方法默认同样保守。
5. 随机选中哪张牌、随机新卡定义、含固定顺序约束时的随机插入位置等，尚未全部实现直接条件提案；仍按其原生分布抽取并检验历史，可能很慢。
6. 每一个历史公开观察和记录的抽牌序列都必须相等。没有“只对齐最新手牌”的路径，也不接受真实 seed/私有快照作采样输入。

返回的是**有限、按似然加权的近似后验**。随机数模型按理想独立均匀调用解释，未求解真实 32 位伪随机 seed 的精确条件分布。即使本次所有权重相同，也不宣称得到了无限后验的独立等权样本。

`weights` 归一化后与 `worlds` 一一对应；`effective_sample_size = 1/sum(w²)`；`distinct_particles` 按原生状态区分、排除 RNG 状态，`duplicate_particles` 为其差数。重复数不是独立样本数。公开历史已经确定全部剩余状态时，distinct 可以为 1，此时不能单凭 distinct 判定出错。没有隐藏的重采样，`resampled=false`。

默认 ESS 下限为请求粒子数的 0.5，可显式配置。粒子不足、低 ESS 或预算耗尽均返回 `valid_for_search=false`。ESS 高也不证明有限粒子已充分覆盖后验尾部；枚举测试和五偶像基准不构成所有组合的证明。

失败根若回退到当前网络采样，须记录其真实行为概率及 `loss_kind=ppo`，而非搜索蒸馏目标。该局仍继续采集实际终局回报；不得因采样失败或低分丢掉真实轨迹。是否回退与如何分配后续预算由 RL 明确配置，Arena 不自动选择替代动作。

未接入：`linkContest`、缺少初始历史、未知原生 DSL/定义、原生公开接口之外额外提供的窥牌或 `known_bottom`。最后两种知识不被忽略；返回错误或 `unsupported_knowledge`。原生已知牌顶/相对顺序和公开检索结果已有覆盖。

## 得分、错误与预算

正常终局 `status="terminal"`，返回原始 `final_score`；中途、异常、超时、取消及未完成续局的 final_score 都是 null。RL 负责外生正尺度、gamma=1、机会节点期望及真实轨迹回报。本接口不添加构筑质量分、buff 奖励或动作数量奖励。

| 状态 | 调用方处理 |
|---|---|
| `ok` / `terminal` | 仍按根采样权重和实际节点状态使用；非 terminal 不当作最终成绩 |
| `insufficient_particles` / `degenerate` | 不产生该根搜索标签；记录实际接受数、ESS 和预算 |
| `deadline` / `budget_exhausted` | 该请求没有有效搜索结果；已完成批量前缀单独列出，不能算完整搜索 |
| `illegal_action` / `illegal_choice` / `stale_decision` / `stale_selection` | 被操作世界维持原状态，修正输入后再请求 |
| `invalid_input` / `unsupported_knowledge` / `native_exception` | 显式接口/内容缺口，不静默略过 |
| `cancelled` / `worker_timeout` | 所属 worker 所有句柄失效；真实局须在另一 worker；成本标记不完整 |
| `version_mismatch` / transport 错误 | Python 抛 `TrainingError`，重新建立独立进程；不混用旧版本样本 |

每次响应的 `cost` 包含 candidates、accepted、branches、native_actions、rule_operations、replay_entries、rng_calls、conditional_draws、frozen_order_operations、world_initializations、projections、milliseconds、cost_complete。`client.total_cost` 汇总已完成请求；取消后保留的 checkpoint 是已完成工作下界，不能冒充准确总量。

常驻 clone 不执行原生动作、重放或 RNG，成本仍含状态复制的墙钟时间。普通 step 的 replay_entries 为 1，表示本次命令；嵌套 choose 重放当前 in-flight 命令也计 1。采样从开局重放的所有提案、被拒绝提案和 pending 重跑均计入。它不是“所有步骤零重放”的接口。

`SearchBudget` 限制**一次请求**，默认 5 秒、512 候选、20 万 native actions、100 万 rule operations、200 万 RNG、10 万 replay entries；单请求最多 60 秒。采样及 batch 可把整组工作放入一个预算。跨多个 step 的整根搜索预算由 RL 从同一根截止时间和剩余计数扣减，**不要给每个子步骤重新发一份完整根预算**。示例演示了整根时间和累计原生预算的扣减。

`SearchClient(max_worlds=64)` 限制该 worker 的常驻世界数；不会自动为 40 个 PPO worker 扩出 40 套搜索器。批次并发和搜索轨迹配额属于 RL 配置。原生工作 tick 检查截止/规则预算；外部 `threading.Event` cancel 由 Python 轮询，终止自己的子进程。异常原生阻塞还有“请求预算＋5 秒”的传输兜底超时，并明确标记成本不完整。未测 Colab、并发 RSS 或 32/64/128 次模拟的规模吞吐。

## 版本与接入顺序

`search_content_version()` 返回 base_effective_sha256、search_sha256、各搜索文件 hash 和后验模型版本。本轮新增文件不进入旧 TrainingExam 的源文件集合，旧基线 effective hash 保持 `929b0d99b3aef013c39f7ddf7b8b832300e526e2eda366c1a7ab1242f456b985`。搜索进程运行期间改源会拒绝下一次调用，需新 Python 进程。历史、搜索配置和训练样本都应保存搜索版本。

RL 下一步：独立 collector 从开局记录完整公开历史 → 按预算和状态筛选搜索根 → 构筑/未搜索动作保持 PPO、搜索动作使用独立 loss_kind → 同一冻结行为版本下联合收集与更新 → 检查点/optimizer 迁移及恢复验证 → 等墙钟对照。无需先冻结卡组做专门训练。该流程及 MCTS/网络实现仍由 RL 侧负责，此次没有自动修改在线训练。
