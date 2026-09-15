# Ascend 910B3 八卡:性能改造记录

目标机 `B04-11U-AT800T-BMS-NODE-10`,Atlas 800T A2,8×Ascend 910B3(64 GiB HBM),
Kunpeng-920 192 核 / 8 NUMA / 2011 GiB RAM,Ubuntu 22.04 aarch64。
容器 `vllm-ascend:v0.23.0rc1`(CANN 9.0.1 / Python 3.12.13 / torch 2.10.0 / torch_npu 2.10.0.post2),
Node.js v22.23.2 arm64。所有数字均为该机实测,未实测的一律标注。

## 0. 起因

八卡环境部署完成后,实测发现资源几乎没被使用:

```
CPU        0.5% 占用     (192 核中约 3.3 核在忙)
NPU        AICore 0% × 8
rank0      单进程 106% CPU     <- 一个核跑满
rank1-7    各 13%
内存       141 GB / 2011 GB
```

把 `workers` 从 144 加到 1024、`parallel_roots` 从 36 加到 512,**利用率完全不变**。
这排除了"并发不够",指向单线程串行瓶颈。

`py-spy` 抓 rank0(需要容器 `--cap-add SYS_PTRACE`)给出根因:

```
Thread (active+gil): "MainThread"
    tensor  (draftrl/fast_collate.py:69)      51.92%  self
    collate (draftrl/encoding.py:310)         80.70%  cumulative
    choose  (draftrl/runner.py:59)
    rollout (draftrl/runner.py:227)
```

rank0 的时间 **80.7% 花在纯 Python 的观测编码/张量拼装上**,真正的网络前向只占 15.3%。
而 `train.py:30` 把采样钉死在 rank0:

```python
if mesh.rank != 0: mesh.serve()   # rank1-7 只做梯度
else:              train(...)     # rank0 独占采样 + 搜索推理 + 主循环
```

---

## 1. CPU 热路径优化(所有 rollout 共享,单卡也受益)

### 1.1 `fast_collate.collate` — 去掉嵌套 list 的 numpy 转换

`paths` / `numbers` 原本是 N 个指向少量去重行的引用,却每次都对 list-of-list 做
`np.asarray`,逐 Python 对象遍历。实测 85k atoms 时 `paths` 16.4 ms、`numbers` 11.5 ms,
而 13 次 `.to(npu)` 合计只要 1.3 ms —— **瓶颈是对象转换,不是传输**。

改为:唯一行建小表 → 收集整数索引 → 一次 fancy-index;扁平 list 用 `np.fromiter`。

| | 原 | 改后 |
|---|---|---|
| 180 examples / 85708 atoms | 317.74 ms | **161.69 ms** |

**1.97×**。三种规模(1 / 8 / 180 examples,含 ±0.0 边界值)输出**逐位相同**。

### 1.2 `round2rl/encoding.encode` — 去掉两处冗余 deepcopy

`state` 和 `effect` 只在顶层 `.pop()`,随后交给 `clean()`;`clean()` 是纯函数
(只读输入、返回全新 dict/list,`grep "state\["` 零命中)。浅拷贝即可保持
`obs["state"]` 不被修改。

profile 中 `encoding.clean` 从 **24.15% 降到消失**。

第三处 `copy.deepcopy(a) for a in obs["actions"]`(encoding.py:74)**故意保留** ——
其结果会外传给调用方,无法证明不被修改。

### 1.3 `round2rl/model.pool` — 绕开 NPU 不支持的 scatter_reduce

```python
maximum.scatter_reduce_(0, group[:, None].expand_as(x), x, reduce="amax", include_self=True)
```

`aten::scatter_reduce.two_out` **没有 Ascend kernel,静默回落 CPU**,整张量
NPU→CPU→NPU。日志每次前向都报警告,`pool()` 每次前向调用 3 次。

改为按组排序后填入 `[size, widest, C]` 缓冲区再 `amax`,全程留在设备上;
当某组过大导致缓冲区超过预算(64M 元素 ≈ 256 MB)时回落 `index_reduce_`。

| 调用形状 | 原 | 改后 | | 走的路径 |
|---|---|---|---|---|
| atoms→entities 85k→20k | 101.6 ms | 18.7 ms | **5.42×** | sort/pad |
| nodes→batches 20k→180 | 13.1 ms | 4.2 ms | **3.13×** | sort/pad |
| 极端倾斜(单组 28355) | 63.1 ms | 20.1 ms | **3.14×** | 自动回落 index_reduce |

三种分布输出**逐位相同**。运行日志中 `scatter_reduce.two_out` 警告**降为 0 次**。

**三项合计**:rank0 单线程采集吞吐 **14 → 33 → 42 决策/秒**(每档对应加一个补丁)。

---

## 2. 八卡分片(把 rank0 独占的工作分出去)

`CollectiveGroup` 已有 `gather_lists()`(`all_gather_object` + 拼接),
full-produce 训练器的 `ppo.py:263` 已在使用 —— 不是新造的机制。

### 2.1 分片原语

`distributed.shard(count, size, rank)` 返回**连续**切片而非跨步切片:
`rollout` 用 `index % len(profiles)` 决定 profile,连续块才能让每个 rank 的
profile 轮转与单卡序列在相同索引上一致。已对
`count ∈ {0,1,5,7,8,9,180,540,1024,49152} × size ∈ {1,2,3,5,8,16}` 验证
**不重、不漏、连续、有序**。

`rollout()` 新增两个参数:

- `index_offset` — 评估路径用**本地计数器** `started` 决定 profile/scenario,
  分片后必须补上偏移,否则同一种子会落到不同 profile。
- `seed_stride` — rank r 从 `start_seed + r` 起、步长为 rank 数,
  **构造上保证两个 rank 不可能采到同一局**。

### 2.2 主评估 rollout 分片

评估是 `greedy=True`、固定 `eval_seed_base`、**只读**,且 `describe()` 按种子排序、
聚合顺序无关 —— 可以做严格验证。

| 到基线的墙钟 | |
|---|---|
| 单 rank | 27.9 分钟 |
| 8 卡分片 | **14.3 分钟(1.95×)** |

**验证:180 局的 (seed, score, profile, scenario) digest 与单 rank 完全相同,0 局差异。**

### 2.3 best-of-4 replay 分片(540 局)

`construction_evaluation` 的任务列表是显式的、按 parent seed 分组、顺序无关,
且代码自带"540 个任务必须全回、每组必须恰好 4 个结果"的断言 —— 切错会立刻报错。

| 到基线的墙钟 | |
|---|---|
| 仅评估分片 | 14.3 分钟 |
| 加 replay 分片 | **4.2–4.3 分钟(3.3×)** |

**合计 27.9 → 4.2 分钟,6.6×。** 这一段每次周期性验证都会跑。

### 2.4 训练采集分片

每批最大的一块。比评估复杂,因为涉及共享状态:

| 风险 | 处理 |
|---|---|
| 两 rank 采到同一局 | `seed_stride`,构造上不可能重叠 |
| 样本库并发写 | worker rank 用轻量收集器只记录,gather 后由 rank0 按种子序喂给唯一的真库(自带按 loadout 去重) |
| SearchRouter 种子撞车 | 每 rank 独立 router,种子基址错开 1,000,000 |
| 日志交错 | 各写分片文件,gather 屏障后按种子合并 |
| collective 顺序错位 → 全局死锁 | AST 静态检查,三对协调端/服务端序列逐个比对 |
| `episode_index` 重用 | 推进到所有 rank 用过的最大种子之后 |

**验证边界:采集分片无法做逐位验证。** 各 rank 在决策预算耗尽时停在不同的对局数,
索引序列会有空隙,部分按 `block % 4 == 3` 排期的覆盖率事件会被跳过。这与修改
`workers` 属于同一类变更,项目本身即要求为此新建 run。每一局本身仍由其种子经
未修改的 rollout 生成。

实测(生产配置):8 个独立 `rollout_begin`,`start_seed` = 34000000…34000007,
**rank1-7 的 CPU 从 13% 升至 84–96%**。

---

## 3. 一并修复的问题

| 问题 | 说明 |
|---|---|
| **分片日志只落 1/8** | 监控台读 `validation-*-episodes.jsonl`(`generalist_data.py:468`),分片后只能看到 23/180 局回放。且该日志含 gather 会丢弃的 `submissions`/`entry` 字段,无法从聚合结果重建。改为各 rank 写 `*.rankN.jsonl`,gather 屏障后按种子合并、原子改名、清理分片。 |
| **`config['workers']` 越界隐患** | worker rank 收到 `workers=1024` 但自身池仅 128,`rollout` 的 `range(config['workers'])` 在切片够大时会访问不存在的槽位。现在每个 rank 的 `workers` 与自身池大小一致。 |
| **违反 README 的 workers 契约** | README 明确 `--workers` 是"全作业的并行度,不乘学习卡数"。原实现 rank0 独占全量。现在 `workers` / `parallel_roots` 按总量均分到各 rank。 |
| **`inference_batch` 是死旋钮** | `pump()` 最多攒 `inference_batch` 个请求,但发请求的是 `parallel_roots` 个搜索进程,每个投完即阻塞等自己的响应 —— 在途请求恒 ≤ `parallel_roots`。**仓库自带的三个配置全部踩中**(4>2、8>2、32>24),该参数从未生效过。`configure.py` 现在输出 `effective_inference_batch` 并给出告警(不报错:报错会拒绝项目自带的预设)。 |

---

## 4. 一个非优化事实:固有非确定性

**同一份代码、同一份配置连跑两遍,180 局评估中有 2 局分数不同:**

```
seed=74000045 saki-wild  346048 -> 348295  (+2247)
seed=74000075 saki-wild  390185 -> 385176  (-5009)
```

原因:`rollout` 将当时所有活跃对局合成**一个 batch** 前向,batch 组成取决于
Node worker 返回观测的时序;浮点归约顺序随之改变,greedy 的 `argmax` 在接近
平局的决策点会翻边。

**这不是本次改动引入的**(在任何分片之前即可复现)。影响:

- 评估分数的微小差异是噪声,**不能当作模型改善的信号**
- A/B 对比需要差异显著大于该噪声底,或使用 `play_evaluation.paired_comparison`
  (配对种子 + 分层 bootstrap + 置信区间)

---

## 5. 汇总

| 项 | 改造前 | 改造后 |
|---|---|---|
| 整机 CPU 占用 | **0.5%**(约 3.3 核) | **~29%**(约 55 核) |
| rank1-7 CPU | 13% | **84–96%** |
| 基线评估墙钟 | 27.9 分钟 | **4.2 分钟(6.6×)** |
| rank0 采集吞吐 | 14 决策/秒 | **42 决策/秒(3×)** |
| collate | 317.7 ms | **161.7 ms(1.97×)** |
| pool 段最大值 | 101.6 ms | **18.7 ms(5.4×)** |
| NPU CPU 回落警告 | 每次前向 | **0** |

**单轮完整时间尚无实测值** —— 此前每次都在第一轮结束前重启以部署下一个补丁。
当前 48 小时运行将给出第一个真实数字(但其配置搜索量为原来的 8 倍,不能与旧配置直接比较)。

回归:每次改动后均运行仓库自带的 `ascend/run_tests.py`,**56 项全部通过 / 跳过 2**。

---

## 6. 改动文件

| 文件 | 改动 |
|---|---|
| `draftrl/fast_collate.py` | 行内插 + fancy-index 替代嵌套 list 转换 |
| `runtime/shared/round2rl/encoding.py` | 两处 deepcopy → 浅拷贝 |
| `runtime/shared/round2rl/model.py` | `_segment_amax` 双路径,绕开 CPU 回落 |
| `draftrl/runner.py` | `index_offset` / `seed_stride` 参数;评估与采集走分片;资源按 rank 均分 |
| `draftrl/distributed.py` | `shard` / `shard_log` / `merge_shard_logs` / `_BankRows`;`evaluate_rollout` / `bank_rollout` / `collect_rollout` 及各自的 serve 端 |
| `draftrl/best_of.py` | `construction_evaluation` 的 replay 走分片 |
| `scripts/configure.py` | `advisories()` 与 `effective_inference_batch` |

每个被改文件在部署目录下都留有 `*.orig.bak`。
