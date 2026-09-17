# 8 卡生产训练：改动记录与运行报告

目标机 `B04-11U-AT800T-BMS-NODE-10`，Atlas 800T A2，8×Ascend 910B3（64 GiB HBM），
Kunpeng-920 192 核 / 2011 GiB RAM，容器 `gakumas-rl-8npu`。
性能改造的第一阶段见 [ASCEND_OPTIMIZATION.md](ASCEND_OPTIMIZATION.md)；本篇接在其后，
记录 2026-09-16 至 09-17 真实生产训练中做的修复、改造与实测结果。
逐日排查流水账见 [RUN_NOTES.md](RUN_NOTES.md)（中文，随运行持续追加）。

运行谱系：

| 运行 | 起点 | 主要变化 | 批次 | 结束 |
|---|---|---|---|---|
| `prod-v3` | `checkpoints/latest.pt` 全新启动 | 搜索质量修复 + 每卡 48 局 / 48 搜索槽 | 1–4 | 完成，test index 1.1745 |
| `prod-v4` | 续训 `prod-v3` | 记录留在本卡（rank-local records）、`search.seconds` 400 | 5–6 | 完成，test index 1.2728 |
| `prod-v5` | 续训 `prod-v4` | 精神統一同名上限 4（保留历史）、搜索预算 ×1.5 | 7– | 运行中 |

（批次号取 `metrics.jsonl` 的提交序号；日志里的 `batch=` 是从 0 起的运行内计数器，比它小 1。）

---

## 1. 搜索质量：从"算了半天一条都不采纳"到 95% 采纳

### 1.1 症状与根因

根搜索的死线一到，`public_mcts.search()` 整根抛弃，已经跑完的几十次模拟全部作废；
实测采纳率 0%，整批的根一条训练目标都拿不到，槽时全部空转。

### 1.2 改动

- **部分信用**（`draftrl/public_mcts.py`）：`search()` 新增 `recoverable` 谓词与 `salvageable()`
  判据。预算类异常（死线、native 动作上限、worker 超时）不再上抛，而是截断在当前模拟数，
  只要每个根动作都有样本、且 `learning_target` 需要的样本数够，就把已完成的部分作为训练目标返回，
  记 `truncated_reason`；`target_budget_eligible` 要求每个动作被访问过且总访问数 ≥ 2×动作数。
- **只认打到终局的模拟**（同文件 `require_terminal`）：没有 rollout 到终局的模拟不做回传，
  计入 `discarded_unterminated`。价值头因此只学真实的全程分数，不学截断估计。
- **`rollout_steps` 48**：考试长 26–53 回合，原来的 8 步前瞻在 `require_terminal` 下 0% 落地。
- **搜索槽 384 → 每卡 48**：根搜索受制于"每张卡一个采集线程"的串行推理往返（每步 0.125–0.22 s），
  是延迟受限而非 CPU 受限；槽位再多只会让每个根都拿不到足够的推理配额。
- **分叉局不开搜索根**（`draftrl/practice.py` 的 `search.fork_episodes`）：分叉局是按父局前缀重放，
  其根搜索 92% 以 `inference_deadline` 作废，标签价值有限却占着槽位；关掉后槽位全部留给 joint 局。
- **超时后不再复检预算**（`draftrl/search_adapter.py`）：截断的根按定义已经超预算，
  再调一次 `budget()` 会把要保住的模拟全部丢掉。

### 1.3 推理通道去 Python 开销

采集线程 37.6% 的时间在反序列化 `Encoded`、28.7% 在合批，吞吐不随搜索进程数增长。
改为工作进程侧预合批（`draftrl/fast_collate.py` 的 `precollate` / `merge`，
`process_service.py` 发送 `{'pre': ...}`，`async_service.py` 在全部任务带 `pre` 时走 `merge`），
单次合批快 7.2 倍。`fast_collate` 的 `import torch` 改为函数内惰性导入，
否则 1500+ 个工作进程每个都会加载一份 torch。

### 1.4 结果

根采纳率 0% → 87–95%，终局落地 99%，每根平均 39/64 次模拟。

---

## 2. 记录留在产出它的卡上（rank-local records）

### 2.1 原来的代价

每批把全量记录在 8 张卡之间搬三次：采集后 all_gather、分叉后 all_gather、更新前 broadcast。
单批约 1 GB 的广播耗时约 23 分钟，阶段间 gather 约 14 分钟；50 分钟的 PPO 更新里只有约 21 分钟
真的在算梯度。

### 2.2 改造

新增 `draftrl/sharded.py`，并改写 `ppo.py` / `critic_completion.py` / `distributed.py` / `runner.py`：

- **采集**：每张卡只保留自己产出的记录（`local_records`），只 gather 摘要、样本库行和计数；
  摘要打上 `origin_rank`。
- **分叉**：分叉任务按父局的 `origin_rank` 路由（`sharded.stamp_shards` / `mine`），
  同一 (joint, 4 replicas) 组整组落在持有父局记录的卡上，`apply_fork_returns` 在本卡执行。
- **样本库重放**：按 replica 组轮转分卡，`apply_bank_returns` 本卡执行；
  `bank.feedback` 从 gather 回来的摘要里的 `bank_key` / `normalized_score` 补齐，次数与原来一致。
- **更新**：各卡本地洗牌；`sharded.block_plan` 让所有卡走同样多的 block，每卡把自己的记录切成
  **等份**的块（每份 ≤ ceil(effective/size)），因此每个全局 block 都含每张卡的份额；
  `block_length` 给出全局块长作为 loss 分母（梯度是求和不是再平均，等价于单学习器目标）；
  `profile_weights` 的每 profile 均值/方差/RMS/权重和全部 all-reduce；
  返回的统计（`record_stats`、覆盖率、符号信用分组）同样 all-reduce。
- **兼容回退**：`shared_records` 分支保留原来的"全量记录 + 全局 strided 块"布局，
  供直接调用 `update()` 的调用方和两进程对等测试使用，逐位不变。

### 2.3 验证

`exam_search/tests/test_sharded.py`：用线程模拟 K 张卡的假 mesh，每个集合通信都是 barrier 交换，
任何一卡多调或少调一次就死锁而不是悄悄通过。

| 用例 | 内容 |
|---|---|
| T1 | `mesh=None` 与原 `practice.profile_weights` 逐位相同；单卡块布局仍是 `range(0, n, effective)` |
| T2 | 8 卡分片的 `profile_weights` == 单卡参考（float32 容差 2e-5） |
| T3 | 块计划锁步：各卡 `num_blocks` 相同、块内近似等分、全局块长之和 == 全局记录数 |
| T4/T5 | `search_totals` / `reduce_nested` / `reduce_coverage` 跨卡求和与键并集 |

另有 53 + 56 项回归在部署根的符号链接树上通过（`ops/verify_stage4.sh`）。

### 2.4 对抗评审发现并修复的三处

1. **尾块参差**（`sharded.block_plan`）：原实现按固定 `per_rank` 切块，卡间记录数不等时，
   每个 epoch 末尾会出现只有长卡记录的小块——额外的优化步、每条记录权重被放大数倍，
   且块级 KL 早停在几条记录上判定。改为等分切块后每个全局块都有全部卡。
2. **续训在 Linux 上必崩**（`continuation.process_alive`）：原实现只有 Windows 分支
   （`ctypes.WinDLL`），在服务器上抛 `AttributeError`，且发生在 runner 的 try 之前，
   不会留下失败记录。新增 POSIX 分支读 `/proc/<pid>/stat`，僵尸（Z）视为已退出
   （容器没有 init 收割，旧 trainer 常留僵尸）。
3. **同特性续训漏审 `target_kl`**：新分支跳过 `validate_signed` 后，`critic_completion`
   会把 `target_kl` 放进 permitted 集合而无人校验。现在显式钉死
   `target_kl` / `critic_completion` / `signed_exam_credit`。

评审还确认了一点并接受不改：若干诊断量现在只覆盖 rank 0 的约 1/8 记录
（`post_update_kl` 抽样、`duplicate_regularization.draft_records`、
`signed_credit.samples` / `records_sha256`、梯度探针）。
**这些键在 prod-v3 与 prod-v4 之间不可比**；批次报告依赖的增益、KL、覆盖率、
符号信用分组都是全局归约的。`search_batch.counts` 也只是 rank 0 的路由计数，乘 8 才是全批。

### 2.5 实测（prod-v3 最后一批 → prod-v4 第一批，同为每卡 48 局）

| 阶段 | prod-v3 | prod-v4 |
|---|---|---|
| collect | 46.4 min | 57.0 min（搜索预算 300 → 400 s） |
| fork_exam | 12.7 min | 7.6 min |
| bank_exam | 4.0 min | 0.6 min |
| ppo_update | 50.0 min | **25.6 min** |
| 采集到更新合计 | 约 113 min | 约 91 min |
| rank 0 常驻内存 | 62–86 GB | **11 GB** |

`records_broadcast` 事件从约 23 分钟降到 15411 行 / 0.3 秒。
正确性交叉核对：ppo 121584 + search 2956 = 124540 = `update_coverage.record_count`
= 五个 profile 的 `task_records` 之和。

---

## 3. 版本化续训（不重跑、按批次边界切换）

改造要上线而训练不能从头开始，靠 `continuation.stage()` / `prepare()` 在批次边界做版本化续训：
权重、Adam 动量、RNG、样本库、覆盖率、分叉种子计数、批次/决策计数、验证历史和原始基准全部继承。

流程：在运行目录放 `stop-after-batch.json` → 训练器在下个批次边界停下、跑完最终评估、
`status=complete` 后退出 → 部署新代码 → `train.py --continue-from <源目录> --output <新目录>`。
**代码必须在训练器退出后再部署**：冻结源码指纹（`source_identity.source_version()`）
会在下一个检查点发现文件变化并终止运行。

本次为此修的四处：

- **同特性续训此前根本不可能**（`continuation.py`）：原 dispatch 对带 signed-credit 设置的配置
  一律调用 `learning_settings.validate_config`，而那是**迁移**校验（要求源没有、目标有），
  从已经带该设置的运行续训必然抛 `Unexpected signed credit settings`。
  现在源与目标都携带同一套已审定设置时跳过迁移校验，其余字段仍走 permitted 键差分审计。
- **`--continue-from` 没接线**（`train.py`）：runner 的 `train()` 一直接受 `continuation=`，
  但 Ascend 入口的 argparse 里没有这个参数。
- **校准证据缺失**（`continuation.py`）：`critic_completion` 要求源目录存在
  `value-calibration/report.json`。prod-v3 是从可移植检查点快照全新启动的，
  快照的 provenance 明说只带权重与 Adam、不拷源日志，该目录留在了原始运行里，训练本身也不读它。
  改为：同特性续训且源目录没有该目录时放行，并在审计里记
  `calibration_provenance: absent_in_source`；有目录时行为不变（必须 `passed` 且拷贝）。
- **改硬上限不再强制清空验证历史**（`continuation.py` 的
  `practice.duplicates.keep_benchmark_history`）：原逻辑一旦同名卡上限变化就归档验证文件、
  清空 `validation-history.jsonl`、重测 180 局新基准。打开该开关后保留谱系，
  在审计和 `construction-benchmark.json` 里记下"第几批起上限变了"。
  **代价**：此后的验证指数是新上限下的分数除以旧上限下的初始基准，涨幅里混有上限本身的效果，
  `best.pt` / `best4.pt` 的选择也会偏向改动之后的检查点。

---

## 4. 搜索预算按 profile 的差异，以及 ×1.5

一个常见疑问：PPO 记录 12 万条，搜索监督只有 3000 条，是不是丢数据了。不是。
PPO 记录是每局每个决策（exam 约 9.96 万 + draft 1.5 万 + guidance 0.7 万 + drink 0.1 万 + memory 0.15 万）；
搜索监督是每个通过采纳的根一条，而根只开在 joint 局的 exam 决策上，每局最多
`max_roots_per_episode` 4 个，每个根独占一个搜索槽最长 `seconds` 秒。
8 卡 × 48 槽 × 57 分钟 ÷ 每根约 6 分钟 ≈ 3600 根的槽时上限，实测约 3000。
梯度上搜索损失按自己的记录数单独归一化（`sharded.search_totals`，每 profile 权重和 = n_global/P）
再乘 `search.loss_coefficient`，所以条数少不等于话语权只有 2.4%。

prod-v4 的 400 秒时代按 profile 统计（每 profile 约 680 个根）：

| profile | 撞死线 | 平均模拟数 / 64 | 有效目标 | 整根丢失 |
|---|---|---|---|---|
| liliya-xmas | 61.5% | 54.8 | 99.7% | 2 |
| saki-wild | 75.4% | 50.6 | 100% | 0 |
| hiro-hif | 81.6% | 47.9 | 97.6% | 19 |
| saki-hif | 89.1% | 46.5 | 98.8% | 8 |
| ume-campus | **97.5%** | **32.9** | 87.4% | **73（10.7%）** |

ume-campus 考试长、rollout 到终局深，一次模拟约 12 秒，400 秒只够 33 次；
`inference_deadline` 是死线到时推理请求未返回、树还不足以"保住"就整根作废。
原生动作预算 `native_action_budget` 60000 各 profile 只用到 1.7–2.2 万，没有顶到；
根的动作数均值 4.7，`simulations` 的预检拒绝从未发生。

因此 prod-v5 起把预算与超时同步放大 1.5 倍：
`seconds` 400 → 600、`simulations` 64 → 96、`sampling_ms` 10000 → 15000。
`soft_budget` 根选择不随 `simulations` 缩放，提高上限只让本来跑得满的 profile 多跑。
代价是 collect 从 57 分钟涨到约 80 分钟，单批约 115 分钟。

---

## 5. 可观测性

- **进度**（`draftrl/stage_progress.py`，新增）：进程内阶段跟踪器，
  `runner.py` 的心跳行给出 `[时刻] b<批次> <事件> run <分钟> decisions=<数> | <阶段进度> | MCTS ...`，
  含每分钟速率、ETA、在飞根数；`progress.json` 里保留每批各阶段的用时。
- **观测台最近对局**（`dashboard/generalist_data.py`）：8 张卡各写
  `train-episodes.rankN.jsonl`，训练器只在一个阶段（collect / fork / bank）全部结束后才合并进
  `train-episodes.jsonl`，因此列表一批只变三次；600 秒预算下前 40 分钟一局都打不完，
  看起来像卡住。现在 `sources('train')` 先列按修改时间排序的分片、再列主文件，
  进行中的对局即时可见；分片被合并删除时跳过。打开某一局仍按文件名 + seed 定位。
- **运维脚本**（`ops/`）：`launch_v3.sh` / `launch_cont.sh` / `launch_v5.sh` 三次启动与续训、
  `batch_report.py`（每阶段用时、学习信号、**每 profile 绝对验证分**表）、
  `verify_stage4.sh`（单测 + 符号链接树回归）、`dashd2.sh` / `startdash.sh`（观测台跟随
  训练器命令行里的 `--output`，不会停在旧目录）、以及一组现场排查脚本
  （`where_blocked.sh` / `stages.py` / `rootcost.py` / `search_stats.py` / `zombies.sh` 等）。

---

## 6. 训练结果

每个 profile 的天花板不同，只看相对涨幅会被起点低的 profile 带偏，因此并列绝对分：

| 验证点 | hiro-hif | liliya-xmas | saki-hif | saki-wild | ume-campus |
|---|---|---|---|---|---|
| initial | 576841 | 141745 | 349821 | 242884 | 225484 |
| 0003 | 679769 | 192293 | 388404 | 295613 | 238586 |
| 0006 | 610188 | 236649 | 421764 | 414082 | 220483 |
| 比初值 | 1.058 | **1.675** | 1.206 | **1.706** | **0.978** |

Best-of-4 验证指数（对初始策略的匹配单元几何均值）：
1.000 → 1.062 → 1.019 → 1.118 → 1.157 → 1.199 → **1.241**；
固定对局（8 次重打均分）1.000 → 1.069。
prod-v4 最终留出测试：test index **1.2728**，best-of-4 test index **1.2835**。

学习信号方向正确（批次 1 至 6）：

| 批次 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| 搜索相对先验的预期增益 | 0.1152 | 0.0922 | 0.0888 | 0.1045 | 0.0712 | 0.0763 |
| 训练归一化均分 | 0.381 | 0.496 | 0.671 | 0.820 | 0.887 | **1.059** |
| PPO KL | 0.0094 | 0.0113 | 0.0095 | 0.0081 | 0.0076 | 0.0092 |

预期增益总体下行，说明策略在吸收搜索的改进；KL 始终在信任域 0.03 内；五个阶段的行为熵没有坍缩。

**需要盯的分化**：总指数在涨，但共享同一个模型的五个 profile 之间在取舍——
saki-wild 与 liliya-xmas 大涨，hiro-hif 自第 3 批起连跌，ume-campus 已回落到初值以下。
ume-campus 从 prod-v5 起获得 1.5 倍搜索预算，正好可用于判断是否有效。

---

## 7. 已知问题与未决项

- **学习率计划与 96 小时窗口不匹配**：`learning_rate_schedule` 按 `elapsed_minutes`
  线性衰减，hold 120 分钟、decay 2880 分钟、地板 0.2 倍。训练窗口已延长到 96 小时
  （`max_minutes` 5760，通过运行目录的 `training-window.json` 热改，训练器在批次边界重读），
  但衰减长度仍是 2880，后半程会一直贴在 0.2 倍地板。要改需在某个边界续训时把
  `decay_minutes` 调到 5760（`learning_rate_schedule` 是 permitted 键，有 `validate_schedule`）。
- **`free_copies` 仍是 3**：精神統一硬上限放开到 4 之后，第 4 张在抽卡阶段仍扣
  0.1 × 1² = 0.1 归一化分（封顶 0.75）。要完全放开需一并调 `free_copies`，这是全局改动。
- **僵尸进程约 21700**：容器以 PID 1 非 init 方式启动，多次重启累积；稳态不再增长，
  下次重建容器时加 `--init`。
- **根采纳率曾从 95% 滑到 86.5%**（全部是 `inference_deadline`），提高预算后回到 94.9%；
  若再次下滑需要看是不是策略变复杂导致每步推理变慢。
- **rank 0 内存**：改造前逐批增长到 86 GB，改造后稳定在 11–15 GB；仍建议长跑时留意。

---

## 8. 本次改动的文件

| 文件 | 改动 |
|---|---|
| `draftrl/sharded.py` | **新增**。跨卡归约、块计划、批次级 profile 权重的全局统计 |
| `draftrl/stage_progress.py` | **新增**。进程内阶段进度跟踪 |
| `draftrl/ppo.py` | 两种记录布局；等分块计划；全局块长作 loss 分母；返回统计全局归约 |
| `draftrl/critic_completion.py` | 同上的块布局与覆盖率归约 |
| `draftrl/distributed.py` | 记录留本卡；分叉/样本库按卡路由；`bank_replay`；更新命令的两种负载 |
| `draftrl/runner.py` | 阶段进度与心跳；分叉/样本库新接口；指标改读全局归约的 `record_stats` |
| `draftrl/public_mcts.py` | 部分信用 `recoverable` / `salvageable`；`require_terminal` |
| `draftrl/search_adapter.py` | 预算谓词接线；截断状态 `ok_truncated`；不再复检预算 |
| `draftrl/search_router.py` | 任务键含 `require_terminal`；累计 attempted/accepted/fallback |
| `draftrl/practice.py` | `search.fork_episodes` 开关 |
| `draftrl/bank_rollout.py` | 阶段进度接线 |
| `draftrl/fast_collate.py` | `precollate` / `merge`；torch 惰性导入 |
| `draftrl/process_service.py` / `async_service.py` | 工作进程侧预合批的发送与消费 |
| `draftrl/continuation.py` | 同特性续训；POSIX `process_alive`；校准证据缺失放行；`keep_benchmark_history` |
| `draftrl/update_diagnostics.py` | 配合归约后的覆盖率字段 |
| `train.py` | `--continue-from` |
| `dashboard/generalist_data.py` | 最近对局先读每卡分片 |
| `exam_search/tests/test_sharded.py` | **新增**。假 mesh 的分片正确性与锁步测试 |
| `configs/prod/*.json` | 三次运行的实际配置（v3 / v4 / v5） |
| `ops/*` | 启动、续训、批次报告、验证与现场排查脚本 |
