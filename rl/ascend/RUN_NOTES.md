# prod-v3 运行记录(2026-09-16 18:05 启动)

跑完一轮后用这份记录定位瓶颈。分析脚本都在 `/mnt/local/gakumas/scripts/`。

## 一、这次改了什么

### 代码(3 个文件,只动日志)
| 文件 | 改动 |
|---|---|
| `draftrl/stage_progress.py` | 新增。进程内的当前阶段视图:阶段名、进度、速率、ETA、每阶段耗时 |
| `draftrl/runner.py` | `publish()` 渲染阶段行 + PPO/搜索细节;`rollout()` 上报阶段;PPO 更新变成一个有名字的阶段;`progress.json` 带 `stage` 结构体 |
| `draftrl/bank_rollout.py` | fork/bank 阶段上报(3 处) |

日志对比:
```
旧  [16:12:37] search_progress batch=0 decisions=0 elapsed=32.4m
新  [18:23:20] b0 best4_validation run 18m decisions=0 | no stage running |
        done evaluate:1.2m validation_best4:1.8m validation_fixed:4.6m
             evaluate:1.3m validation_keycard:2.2m evaluate:1.2m validation_best4:1.9m
```

### 配置 `configs/prod/search.json`
| 字段 | 改前 | 改后 | 理由 |
|---|---|---|---|
| `max_roots_per_episode` | **null** | 4 | 出厂失效。`trajectory_every=1` 下每个考试决策都成根,约 25 个/局,完全无上限 |
| `parallel_roots` | 512 | 128 | 争抢是根超时的唯一原因(见下) |
| `inference_batch` | 512 | 16 | 超过每卡 parallel_roots 的部分不可达 |
| `workers` | 1024 | 256 | 每卡 128→32。采集主循环每圈变快,搜索进程等估值的间隔随之缩短 |
| `microbatch` | 4 | 128 | smoke 已实测 128 在 64GiB HBM 上安全 |
| `batch_decisions` | 49152 | 32768 | 原值是虚的:每个开始的对局都要跑完,真实下限 = workers × 每局决策数 |

**没有改**:`simulations=64`、`seconds=60`、`trajectory_every=1`、搜索算法本身。

## 二、撤回的改动(试过但没用,已还原到上游)

| 改动 | 为什么撤 |
|---|---|
| MCTS 渐进加宽(progressive widening) | 离线实测只有 1.08x(生产形状)。改搜索语义换 8%,不值 |
| 推理泵排空(pump drain) | 当 `inference_batch` ≥ 每卡搜索进程数时,一次泵已服务全部请求,排空是空操作。测试脚本 `p2/test_pump.py` 证伪 |

`async_decisions.py` / `async_service.py` / `public_mcts.py` / `search_adapter.py` / `search_router.py` 的 md5 与上游一致,未被修改。

## 三、待验证的核心指标

**搜索根采纳率**。历史值:
- prod-48h-v2: 1431/25126 = **5.7%**
- smoke2: 0/2856 = **0.0%**,`search_records=0`,即 MCTS 监督分支完全空转,模型实际是纯 PPO

诊断结论(`scripts/failwork.py`):
```
成功的根  15.0s  完成 3837 原生动作  = 256/秒
超时的根  60.0s  完成 1583 原生动作  =  26/秒   <- 慢 10 倍
```
失败的根不是活多,是抢不到 CPU/NPU。所以降并发是对症的。

**如果 prod-v3 的采纳率仍然接近 0**,下一步选项(按代价排序):
1. `parallel_roots` 128 → 64
2. `rollout_steps` 8 → 3、`max_depth` 12 → 8(直接减少每次模拟的顺序步)
3. `seconds` 60 → 120(只有在确认根接近完成时才有意义)
4. `search.enabled = false`,先用纯 PPO 跑,把搜索当独立课题修

注意 `search.seconds` 是**硬丢弃**:跑了 559 步差一步也是零,没有部分学分。这是结构性问题,本次未改。

## 四、分析脚本(都在 /mnt/local/gakumas/scripts/)

| 脚本 | 用途 |
|---|---|
| `rootprobe.sh` | 当前运行的根状态直方图 + 采纳率,不用等整批 |
| `rootcost.py <run>` | 根成本剖析:顺序步数、每步秒数、按状态分组 |
| `failwork.py <run>` | 判定失败的根是"活太多"还是"被饿死" |
| `stages.py <log> <run>` | 每阶段墙钟 + metrics.jsonl 成本分解 |
| `search_stats.py <run>` | 根结果统计 + 阶段时间线 |
| `upd.py <run> <log>` | PPO 更新形状 + 每局决策数分布 |

## 五、基线数字(smoke2,批次 1,用于对比)

```
collect      26.4m      fork_exam 14.3m     bank_exam 2.3m     ppo_update 19.1m
批次合计约 62 分钟,实际采集 35351 决策(配置写的是 4096)
search_records=0   ppo_records=36057   根秒 30548 = 8.5 核时全部浪费
```

---

# 追加(18:45):找到并修复真正的结构性缺陷

## 症状链

1. `rollout_steps: 8 → 2` 后采纳率 0% → **48.0%**,实测验证了成本模型:
   ```
   成功的根: 400 个顺序步 × 0.125 秒/步 = 50 秒   (死线 60 秒, 实测 p50 = 49.9 秒)
   ```
   整个分布骑在死线上,一半刚好挤进去,一半刚好差一点。

2. 但剩下 48% 仍然是**全额丢弃**。这不是速度问题,是机制问题。

## 根因:死线一到,已完成的模拟全部作废

`public_mcts.search()` 的模拟循环里,任何预算异常都直接穿透整个函数,
`search_adapter.py` 把 `report['search'] = None`。跑完 45 次模拟的根和跑完 0 次的根,
结果完全一样 —— 都是零。

而采纳门槛其实很低:
```python
target_budget_eligible = all(n > 0 for n in root.visits) and total >= 2*len(root.visits)
```
配置用 `root_selection='soft_budget'`,它**优先把每个动作填到 soft_min_visits=2 次**。
5 个动作只要 10 次模拟就达标 —— 64 次预算里的 15%。
按实测 400 步/64 次模拟算,10 次模拟约 63 步约 8 秒。
**凡是活过 60 秒的根,早在第 8 秒就已经够格了。**

## 改动(2 个文件)

| 文件 | 改动 |
|---|---|
| `draftrl/public_mcts.py` | `search()` 新增 `recoverable` 谓词。预算耗尽时跳出循环保留树,由原有的准入规则决定是否采纳;`salvageable()` 确保保留的树能被后续代码消费;新增 `simulations_completed` / `truncated_reason` 上报 |
| `draftrl/search_adapter.py` | 传入 `spent_budget` 谓词(只有 RejectedRoot 和特定 TrainingError kind 算预算耗尽);截断的根跳过 `budget()` 复检;状态区分 `ok` 与 `ok_truncated` |

`recoverable=None` 时行为与改前**逐位相同**,已测。

## 我自己引入又修掉的两个缺陷

1. **`improve()` 会崩溃**:`search_learning.improve()` 要求每个动作至少 2 个样本。
   截断可能停在 `visits=[2,2,1,1,1]`,ValueError 在循环外抛出,无人捕获,搜索进程直接死。
   → `salvageable()` 增加该检查。
2. **`budget()` 复检会把刚救下的根再扔掉**:`search()` 返回后紧跟一行 `budget()`,
   而截断的根按定义就是超预算的,必然抛 RejectedRoot。
   → 只对未截断的根复检。

## 测试 `p2/test_partial.py`

```
1. recoverable=None 与原实现逐位相同        ok
2. 7 个截断场景中 6 个现在产出标签(原来 0 个)
3. 截断标签内部有效(动作全覆盖/策略和为1/选中动作合法/学习目标完整)
4. 截断不虚构:访问数是完整运行的前缀
5. 非预算错误仍然销毁整个根           ok
6. 截断过早时不伪造标签(0 个假标签)   ok
```

## 预期

活过 60 秒的根在第 8 秒就够格,所以 48% → 预计 95%+。待实测。

---

# 追加(09-17 02:00):采集线程是唯一瓶颈,三项改动

## 实测(每卡 192 局 / 192 搜索槽)

```
整机 CPU        76 / 192 核         (之前 41)
每卡 HBM        5.1 / 64 GB
主机内存        362 / 2011 GB
搜索进程        400 个采样, 0 个在运行, 全在等
根              6936 个, 92% inference_deadline, 每根完成 6/64 次模拟
```

搜索进程不是缺 CPU,是在等**每卡唯一的采集线程**喂推理。槽从 16 加到 192,每根分到的模拟从 45 掉到 6。槽数不改变总吞吐(采集线程是上限),只决定每个根能不能跑完。

py-spy 采集线程自身时间:
```
37.6%  queue.get —— 反序列化 Encoded 对象(几百个 Python tuple 逐个重建)
28.7%  collate  —— 纯 Python 逐 atom 拼装
16.9%  NPU 前向
```
前两项 66% 是搜索进程自己就能做的活,而 1500 个搜索进程各有一个空闲核。

## 改动

### 1. 工作进程侧预拼接(`fast_collate.py` / `process_service.py` / `async_service.py`)

`precollate(encoded)` 在搜索进程里把 Encoded 转成 numpy 数组(示例内局部词 id),走队列;
采集线程 `merge()` 按顺序 intern 各示例词表、一次 fancy-index 重映射。

**逐位一致**(10 项测试,含跨示例词序相反、±0.0、无边、五种 phase、64 个随机示例)。
**采集线程每次泵 192 个请求**:390 ms → 54 ms,**7.2 倍**。
pickle 反而大 5.8 倍(int64 填充),但反序列化成本在对象数不在字节数:一个 numpy 数组是整块拷贝。
紧凑 dtype 版本试过,主线程侧 widen 回来的 Python 循环把收益吃光(1.39 倍),不采用。

`fast_collate.py` 的 `import torch` 改为函数内惰性:`precollate()` 在 1500+ 个搜索进程里跑,
不能把 torch 拉进每个进程(`process_service.py` 原注释明确警告过)。已用 `sys.modules['torch']=None` 验证。

### 2. 分叉局不开搜索根(`practice.py`,`search.fork_episodes: false`)

分叉局通过 `retained_metadata` 继承父局的 `search_enabled`,所以同一套牌 4 局都搜,根数 4 倍。
分叉的目的是给 signed credit 提供真实 Best-of-4 终局分数,不需要搜索。
关掉后每卡每批根数 3072 → 768。`fork_replicas` 仍为 4,signed credit 契约不变(已测)。

**用户提议 4 副本改 3:不可行。** `signed_credit.py:26` 写死 `fork_replicas != 4` 抛异常,
`public_mcts.py` 只接受 `objective_k in (1,4)`。

### 3. 搜索槽 192 → 48 每卡

采集线程约 13 模拟/秒(预拼接后)。48 槽下每根约 0.27 模拟/秒,64 次约 240 秒,能在 300 秒内跑完。
每卡局数保持 192:不在根上的局照常推进。

## 验证

- 回归 53 + 56 项全过。第一次跑出 3 个 error 是我把 deploy 树复制到 stage 目录时漏了 `training/` 符号链接,
  `source_identity.py` 找不到训练后端 —— 测试环境问题,不是代码。按 deploy 结构建符号链接树后全过。
- 一个真实隐患被逮到并修掉:`fast_collate.py` 顶层 `import torch` 会进 1536 个搜索进程。

## 预期(待实测)

- 根:每根 64 次模拟跑完,采纳率接近 100%,终局落地
- fork 阶段:无 300 秒冻结,三波各约 3 分钟
- collect:192 局 × 4 根 / 48 槽 = 16 波 × 240 秒 ≈ 64 分钟搜索时间(采集线程上限)

---

# 追加(09-17 02:50):48 局 / 48 槽实测 —— 延迟链,不是算力瓶颈

## 四角诊断(采集跑热 7 分钟后)

| | 192/卡(改前) | 48/卡(现在) |
|---|---|---|
| 整机 CPU | 76 核 | **126 核** |
| 根采纳率 | 3.8% | **93.9%** |
| 终局落地 | 100% | **99.2%** |
| 每根模拟 | 6/64 | **39/64**(p10=27,92% 到 300 秒被截断) |
| 采集线程:反序列化 | 37.6% | **5.9%** |
| 采集线程:拼装 | 28.7% | **4.3%** |
| 采集线程:NPU 前向 | ~17% | **42%** |
| 采集线程:等请求(空闲) | — | **27%** |

预拼接兑现了基准测试的数字。采集线程的 Python 开销没了,剩下的是 NPU 前向本身和等搜索进程来要东西的空闲。

## 关键发现:三方都在互相等

采集线程 27% 空闲,搜索进程各 2% CPU,Node 各 3% CPU。没有任何一方被打满。
一次模拟约 30 步 Node 世界推进(`rollout_steps=48` 走到终局),每步一次 IPC 往返。
45 次模拟 × 30 步 / 300 秒 ≈ 220 毫秒一步。

佐证:16 槽每根 45 次,48 槽每根 39 次。槽数 3 倍,每根几乎不变 → 限制在每个搜索进程自己的顺序链,不在共享资源。

**下一个杠杆是 Node 单步延迟,或者更多并行链来掩盖它。** 后者要同时加局数(否则槽空转),会把 PPO 批推大;用户明确要 48,先不动。

## 观测编码下放:已验证,未部署

`patch_encode_offload.py`(r1rl/environment.py worker 预编码 + runner/bank_rollout 消费):
- 回归 53 + 56 全过
- 真实 arena 一局 9 步:worker 侧 Encoded 与采集侧 Encoded 全字段相同;终局视图不预编码;choice 视图留给采集线程
- **但诊断显示对局编码路径已不在采集线程前十** —— 它针对的成本在 48 局下可忽略。不部署。文件留在 `scripts/stage/`。

教训:测量先于部署。这个补丁在 192 局时会有用,在 48 局时是无用功。

## 4021 个 Python 进程

每 rank 96 个直接子进程 = 48 局 arena worker + 48 搜索 worker。其余约 3250 个是各 worker 再开的约 4 个子进程(arena 引擎 SearchClient 自己的结构)。每个约 2% CPU、43 MB RSS,合计约 140 GB。2 TB 内存下不是问题,不是我们的代码。

## 测试脚本的坑(记一笔)

`live_encode_check.py` 第一版没有 `if __name__ == '__main__'` 守卫。spawn 子进程重跑主模块 → 递归 spawn → worker 被 reset。
补丁树和原始树**一模一样地挂**,才确认是脚本不是补丁。以后凡是用 mp spawn 的临时脚本都要加守卫。

---

# 追加(09-17 03:40):僵尸进程 + 池拆除噪音

## 21,674 个僵尸进程

```
按父进程: 19148 python3 → pid 1 | 2086 node → pid 1 | 22 pt_elastic → pid 1 | 394 → 存活的父进程
容器 pid 1 = `sleep infinity`, init=<nil>  → 孤儿永远不被回收
pids.current 35644 / pids.max 629145  (5.6%)
```

**来源是我的重启,不是训练本身。** 22 个 `pt_elastic` 僵尸 = 22 次 torchrun 启动被 `pkill -KILL`,
每次孤儿化约 1000 个 python3(搜索 worker 及其子进程)。稳态训练里 worker 由 executor 正常 join,
不产生僵尸。394 个存活父进程下的僵尸是 arena `close()` 里 Node 子进程 kill 后 `wait(timeout=5)` 超时被丢弃的残留,量小。

**本次运行内无需处理。** 下次重建容器时 `docker run --init`(tini 做 pid 1)。已记入待办,未改 `run_container.sh`。

## 日志里的 `subprocess.TimeoutExpired` 回溯(每批约 4 条)

来自 `process_service._close_worker` → arena `SearchClient.close()` → `process.wait(timeout=5)`。
触发点是**我的分片代码**:`distributed.py` 在 collect 和 fork 各自为 worker rank 建一个 SearchRouter、阶段结束就 close,
每批 7 rank × 2 阶段 × 48 worker = 672 次 worker 退出,每次 finalizer 去杀 Node。极少数 Node 5 秒内没退。
是拆除噪音,不是训练失败。watcher 的错误匹配已改为只认 `^(RuntimeError|ValueError|AssertionError|FloatingPointError|KeyError|TypeError)`。

## 批次 0 时间线(48 局 / 48 槽,首批)

```
collect   44.0 min   96 局/rank(2 波),5400 决策 = 132% of 4096
fork       ~9 min    288 任务/rank,无搜索根 → 无 300 秒冻结
```
collect 是 2 波:48 局 × 约 55 决策 = 2640 < 4096,所以再开一波。每波下限 = 4 根 × 300 秒 ≈ 20 分钟。
`batch_decisions` 与 `workers` 的搭配决定波数:48 局要一波填满得设 ≈ 2400;要维持 ≈ 5 万条 PPO 记录就是 2 波。
这是时间与批大小的取舍,等首批报告后由用户定。

---

# 追加(09-17 04:15):PPO 前的 18 分钟静默 + 部署安全规则

## 03:48 → 04:06 日志无输出,训练未停

py-spy 两次采样:先是 8 个 rank 全在 `mesh.shuffle()` 的 `broadcast_object_list`,两分钟后已进 PPO 主循环
(collate / 前向 / 反向 / `totals` all-reduce)。更新在推进。

静默来自两处:
1. **日志缺口(我的)**:`stage_progress.begin('ppo_update')` 后没有 `publish`,第一条 `ppo_progress` 要等第一个优化器块。
2. **块之前的准备慢**:`LearnerGroup.update` 把 `{weights, Adam state, 全部 records(约 4.3 万条 × Encoded), config}`
   一次 `broadcast_object_list` 给 7 个 worker rank —— 单线程 pickle 约 1 GB,7 份单线程 unpickle。
   之前审计估 60–90 秒,实际疑似 10 分钟以上。**批次提交后看 `update_seconds` 和首条 `ppo_progress` 的 `stage` 字段确认。**

为什么广播不能直接去掉:worker rank 在采集结束时确实持有同一份 gathered records,但之后 rank 0 独自做了
`apply_fork_returns`(改 return / loss_weight / policy_advantage)、`apply_draft_penalty`、bank 回放(80 局只在 rank 0)。
worker 的副本是旧的。去广播 = 让每个 rank 确定性地重做这些后处理 + 把 bank 回放也分片。
是真重构,有实测数再定。

## 已暂存、下次重启才部署(纯日志)

| 文件 | 改动 |
|---|---|
| `draftrl/runner.py` | `ppo_update` 阶段开始时立即 `publish('ppo_update_begin')` |
| `draftrl/distributed.py` | 广播前后计时,打 `{"event":"records_broadcast","seconds":…}` |

`runner.py` 同时带着已验证的 encode-offload 消费端改动(`row.get('pre_encoded')`,无 worker 侧改动时自动回退),inert。
`environment.py` worker 侧**不部署**。

## 部署安全规则(硬)

`source_identity.source_version()` 对以下文件做指纹,`unchanged()` 在**每次 checkpoint 前**比对,变了就 RuntimeError 终止训练:
```
deploy/exam-search/draftrl/*.py
deploy/exam-search/train.py
deploy/exam-search/runtime/shared/**/*.py
deploy/training/gakumas_training/{device,collectives}.py
```
**训练进行中绝不能写这些路径。** 只在重启前那一刻部署。`dashboard/`、`scripts/`、`runtime/arena/`(arena 有自己的哈希)不在集合内。

之前 stage 树回归报 3 个 error 的原因也在这:`root.parents[1]/'training'` 在复制树里不存在 → `FileNotFoundError`。符号链接树修好了。

---

# 批次 1 完整报告(09-17 04:32 提交,48 局 / 48 槽)

## 时间线(实测,115.2 分钟)

```
02:37  collect        44.0 min   2 波 × 4 根 × 300 秒;96 局/rank,5486 决策 = 134% of 4096
03:21  → 间隙          ~5 min    all_gather 4.2 万条记录;7 个 rank 各起 48 个搜索进程池
03:27  fork_exam       9.0 min   288 任务/rank,无搜索根
03:36  → 间隙         ~8.7 min   拆池(672 worker 退出);all_gather 6.5 万条;apply_fork_returns
03:44  bank_exam       3.7 min   80 局,rank 0 单独跑
03:48  ppo_update      44.4 min
         广播记录到 7 个 rank     22.9 min   ← 首个 ppo_progress 在 04:10:57,stage=22.9m,仅 1024 条完成
         PPO 循环 416 步         21.2 min   3.1 秒/步
04:32  提交
```

**记录序列化约 30 分钟(26%)**:2 次 all_gather + 1 次 broadcast,每次每个 rank 都 pickle/unpickle 全量 `Encoded` 对象(约 1 GB)。
更新只需要每个 rank 自己的份,却拿了 3 份全量。

## 改进循环信号(健康)

| 指标 | 值 | 判断 |
|---|---|---|
| PPO KL | 0.0094(目标 0.03) | 信任域内,4 轮全跑完 |
| clip 比例 | 0.117 | 正常 |
| 根采纳率 | 365/384 = 95.1% | 353 截断(部分学分)+ 12 完整 |
| 终局落地 | 99% | — |
| 搜索记录占比 | 2925 / 105774 = 2.8% | 加权可学习 2186(75%),均权 0.453 |
| 搜索目标熵 vs 先验熵 | 0.863 < 0.932 | 搜索在收紧策略,有信号 |
| mean_estimated_gain | 0.1152 | **首个点,要看批次 2 起是否下降** |
| 探索熵 exam/draft/guidance/drink/memory | .94/.55/.93/.64/.60 | 无坍缩 |
| 符号信用 +/−/0 | 12388/63258/5404 | 78% 负是结构性的:4 局里 3 局对 max 贡献 0 |

验证指数 `eval_every_batches=4` → 首个真实改善信号在**批次 4,约 8 小时后**。

## 每步 3.1 秒(PPO 循环 21 分钟)

每块 1024 条,每 rank 128 条,一次前向+反向。预期约 0.7 秒。多出来的可能是每块约 10 次 `float(tensor)` 设备同步
+ `clip_grad_norm_` + `mesh.totals` 的 NPU 张量往返。未剖析,次要。

## 结构性修法(未做,等用户定)

每个 rank **端到端只持有自己的记录**:
- fork 任务按来源 rank 分片,使 (joint, 3 forks) 组落在同一 rank → `apply_fork_returns` 本地做,不需要 gather
- 采集/fork 只 gather **摘要**(小),不 gather 记录
- PPO 从"全局 shuffle + 跨 rank 跨步"改为"各 rank 本地 shuffle + 本地块",梯度 all-reduce 不变,数学等价
- bank 仍 rank 0 单独跑(80 局,小)
- `metrics.jsonl` 里遍历 records 的统计改为各 rank 算完 reduce

去掉 2 次 gather + 1 次 broadcast ≈ **−30 分钟/批(−26%)**,内存少 7 GB 拷贝。约 200 行,涉及 distributed.py / runner.py / ppo.py / practice.py。

---

# 批次 2 报告(09-17 06:34 提交)—— 循环在转

| 信号 | 批次 1 | 批次 2 | 方向 |
|---|---|---|---|
| `mean_estimated_gain`(搜索相对先验的预期增益) | 0.1152 | **0.0922** | ↓ 20%:策略在吸收搜索 |
| Best-of-4 验证指数(优化目标) | 1.000 | **1.0624** | ↑ 6.2% |
| 训练归一化均分 | 0.381 | **0.496** | ↑ 30% |
| PPO KL / clip 比例 | 0.009 / 0.117 | 0.011 / 0.147 | 更大的策略步,仍在 0.03 信任域内 |
| 符号信用 +/−/0 | 15% / 78% / 7% | 20% / 59% / 21% | 价值头在校准 |
| 8 次重打均分验证 | 1.000 | **0.9645** | ↓ 3.5% |
| 根采纳 / 终局落地 | 95.1% / 99% | 94.8% / 99% | 稳定 |
| 探索熵(五阶段) | .94/.55/.93/.64/.60 | .92/.55/.92/.63/.57 | 无坍缩 |

**Best-of-4 涨、均分跌**与 `objective: best_of_k` 一致(换上限不换均值)。一次更新不定论;
若持续则策略在变高方差,需判断是否是想要的。`play_validation` 用 `paired_comparison` 可做显著性。

## 时间(121 分钟,比批次 1 多 6)

```
validation(批后)  13.7 min   evaluate 1.8 / best4 3.5 / validation_fixed 8.4(批次 0 时 4.1,翻倍)
collect            46.6 min   (43.8)
fork_exam          12.9 min   (8.8)
bank_exam           1.0 min
update             44.6 min   (44.4,稳定;广播约 23 + 循环约 21)
```

同配置下 `validation_fixed`(rank 0 单跑)翻倍、fork +47%。**rank 0 RSS 62.8 GB,worker rank 6–8 GB。**
rank 0 持全量记录、样本库、常驻搜索路由,大是应该的,8–10 倍要看是否逐批增长。
8 次 py-spy 采样未见 GC 帧,原因未定。watcher 已加 rank 0 RSS 时间序列,批次 3 给增长率。

僵尸 21674 不变(稳态不增,确认)。主机内存 264 / 2011 GB。


---

# 2026-09-17 批次 3–4 结果,以及切换到"记录留在本卡"版本(prod-v3 → prod-v4)

## 批次 3/4 数字(prod-v3,48 局 / 48 槽)

批次 3(metrics 第 4 行)各阶段(progress 里的 stage 计时):collect 46.4 / fork_exam 12.7 /
bank_exam 4.0 / ppo_update 50.0 / 批后验证约 14 分钟;metrics 的 `collection_seconds`
(79.7 分钟)= collect+fork+bank+验证,`update_seconds` = 50.0。

| 信号 | 批次 1 | 批次 2 | 批次 4 | 方向 |
|---|---|---|---|---|
| `mean_estimated_gain` | 0.1152 | 0.0922 | 0.1045 | 降后回弹,不是单调;继续看 |
| PPO KL | 0.009 | 0.011 | 0.0081 | 信任域内 |
| 训练归一化均分 | 0.381 | 0.496 | **0.820** | 持续涨 |
| 根采纳率 | 95.1% | 94.8% | **86.5%** | 缓慢下滑(48 个 inference_deadline),待查 |
| Best-of-4 验证指数 | 1.000 | 1.062 | 1.118 | 涨 |

### 每个 profile 的绝对验证分(用户要求:不能只看相对增长)

验证指数是相对初始策略的几何均值,起点低的 profile 百分比虚高,所以 `batch_report.py`
现在打印每个 profile 的原始均分表。validation-initial → validation-0003:

```
hiro-hif      576841 → 679769   (+17.8%)
liliya-xmas   141745 → 192293   (+35.7%,起点最低,百分比最虚)
saki-hif      349821 → 388404   (+11.0%)
saki-wild     242884 → 295613   (+21.7%)
ume-campus    225484 → 238586   ( +5.8%,最慢)
```

## 改造:记录留在产出它的卡上(rank-local records)

**之前**每批三次把全量记录发给每张卡:collect 后 all_gather、fork 后 all_gather、update 前
broadcast(约 1 GB,约 23 分钟)+ 阶段间 gather 约 14 分钟。update 50 分钟里只有约 21 分钟
在算梯度。

**现在**记录不动:
- 采集:每卡只留自己的记录(`local_records`);只 gather 摘要(summary)、样本库行、计数。
  摘要打上 `origin_rank`。
- fork_exam:分叉任务按父局的 `origin_rank` 路由(`shard_rank`),同一 (joint, 4 replicas) 组
  整组落在持有父局记录的卡上,`apply_fork_returns` 在本卡做;不再需要全量记录。
- bank_exam:按 replica 组轮转分卡,`apply_bank_returns` 本卡做;`bank.feedback` 从 gather 回来
  的摘要里的 `bank_key/normalized_score` 补,次数和之前一致。
- update:各卡本地洗牌;`sharded.block_plan` 让所有卡走同样多的 block(每卡把自己的记录切成
  等份的块,每个全局 block 都有每张卡的份),`block_length` 全局求和做 loss 分母(梯度是求和不是
  再平均,所以和单学习器目标一致);`profile_weights` 的每 profile 均值/方差/RMS/权重和全部
  all-reduce;返回的统计(`record_stats`、覆盖率、符号信用分组)也 all-reduce。
- 兼容:`shared_records` 回退(直接调 `update()` 的调用方、两进程 parity 测试)保持原来的
  全局 strided 布局,逐位相同。

文件:`sharded.py`(新)、`ppo.py`、`critic_completion.py`、`distributed.py`、`runner.py`、
`bank_rollout.py`、`practice.py`、`continuation.py`、`train.py`;暂存在
`scripts/stage4/`,由 `scripts/launch_cont.sh` 部署。

### 验证
- `scripts/stage4/test_sharded.py`:线程模拟 K 张卡的假 mesh,每个集合通信是 barrier 交换,
  少一次/多一次调用就死锁。T1 mesh=None 逐位等于原 `practice.profile_weights`;T2 8 卡分片 ==
  单卡参考(2e-5);T3 block 计划锁步/覆盖/等份;T4/T5 归约。ALL PASSED。
- 回归 53 + 56 用例 OK(deploy 根的符号链接树 + 覆盖文件)。
- 三视角对抗评审(锁步/死锁、数值语义、runner 数据流与续训),结果:
  1. 锁步:0 发现。每个命令 rank 0 与 serve() 的集合通信次数、顺序逐一对上,含空尾块、
     KL 早停分支、finally 里的 gather。
  2. **修了:尾块参差**。原 block_plan 每卡固定 per_rank 切块,卡间记录数不等时每个 epoch 末尾
     (max_blocks − min_blocks)个 block 只有长卡的记录,分母很小 → 多出一批"小 block 优化步"
     且 block-KL 早停在几条记录上判。改成每卡把自己的记录切成 num_blocks 等份(每份 ≤ per_rank),
     每个全局 block 都有所有卡,`block_length ≈ n_global/num_blocks`。
  3. **修了(启动即崩)**:`continuation.process_alive` 只有 Windows 实现(`ctypes.WinDLL`),
     Linux 上 AttributeError。加 POSIX 分支读 `/proc/<pid>/stat`,僵尸(Z)算已退出
     (本容器没有 init 收割,旧 trainer 可能留僵尸)。
  4. **修了(加固)**:同特性续训分支跳过 `validate_signed` 后,`critic_completion` 会把
     `target_kl` 放进 permitted,变更无人审。现在显式钉死 `target_kl / critic_completion /
     signed_exam_credit` 三个键。
  5. 接受不改:几个诊断量现在只覆盖 rank 0 的约 1/8 记录(`post_update_kl` 抽样、
     `duplicate_regularization.draft_records`、`signed_credit.samples/records_sha256`、梯度探针)。
     **这几个键 v3/v4 之间不可比**;`batch_report.py` 用的 gain/KL/覆盖/符号信用分组都是全局归约的。

## 续训 prod-v3 → prod-v4(版本化续训,不是从头)

- 11:47 放 `runs/prod-v3/stop-after-batch.json`,正好赶上批次 3 的边界(下一批还没开始);
  trainer 收到后跑最终评估(validation-final / best4 / validation_fixed / test-best /
  test-initial),`status=complete` 后退出。
- `scripts/launch_cont.sh`(**必须在容器里跑**:`docker exec gakumas-rl-8npu bash
  /mnt/local/gakumas/scripts/launch_cont.sh`;宿主机没有 torch):
  1. 门槛:progress.status==complete 且没有 train.py 进程,否则拒绝(源码哈希一变,活着的
     trainer 下一个 checkpoint 就会被 `unchanged()` 杀掉);
  2. 把 deploy 里 prod-v3 的代码备份到 `scripts/prod-v3-code/`,再拷入 stage4 文件;
  3. 写 `configs/prod/search-v4.json` = search.json + `search.seconds 300 → 400`
     (用户:省下时间了,允许更长程思考);
  4. `torchrun ... --continue-from runs/prod-v3 --output runs/prod-v4`,日志 `logs/prod-v4.log`。
- `continuation.py`:原 dispatch 对已带 SIGNED 设置的源必跑 `validate_signed`,而它是"迁移"
  校验(要求源没有、目标有),SIGNED→SIGNED 直接报 Unexpected signed credit settings,等于
  这条产线根本没法续训。加了同特性分支;其余字段仍走 permitted 键 diff。`train.py` 补了
  `--continue-from`(runner 早就收 `continuation=`,只是入口没接)。
- 审计预演(容器里读 latest.pt 的 training_config 对比 search-v4.json):非 permitted 键全等,
  permitted 键里只差 `search.seconds`。
- 时间窗:续训的 deadline = 源 `started_at`(2026-09-16 18:20 UTC)+ `max_minutes` 2880,
  即 **2026-09-18 18:20 UTC 到期**,prod-v4 继承这个窗口;要延长就在 search-v4.json 里调
  `max_minutes`(permitted)后再续一次。
- 回滚:杀 v4,把 `scripts/prod-v3-code/*` 拷回 deploy,再从 prod-v3(原样未动)续到新目录。

## 切换后要看的

- 首批 collect → fork → bank → update 的过渡(真 8 卡集合通信路径此前只有假 mesh 和两进程测试);
  `records_broadcast` 事件应只剩摘要级别,update 目标从 50 分钟降到约 25 分钟。
- 本地 watcher:`loop_batch4.sh <行数> prod-v4`(rank 0 RSS 改用 `/proc/<pid>/environ` 里的
  `LOCAL_RANK=0` 定位)。dashboard 由 `dashd2.sh` 跟着 trainer 的 `--output` 自动切换。
- 继续跟:rank 0 RSS(62.8 → 86 GB,现在 rank 0 不再持全量记录,应明显下降)、采纳率
  95 → 86.5% 的下滑、僵尸 21674(下次重建容器加 `--init`)。
- 用户要求:以后少拉 Fable 子代理(贵),评审/排查直接在会话里做。

## 12:20 切换实录(prod-v4 已启动)

- 第一次启动在 `continuation.stage()` 被拒:`Missing passed distribution calibration provenance`。
  该检查要求源运行目录里有 `value-calibration/report.json`(status=passed)。prod-v3 是用
  `deploy/checkpoints/latest.pt` **全新启动**的,这个快照的 provenance.json 明说"只带权重+Adam,
  源日志不拷";日历校准的证据留在原来 Windows 侧的 `joint-mcts-soft-value-20260915-121503`,
  服务器和 /mnt 上都找不到。训练本身不读这个目录(只有 stage() 和离线 probe 脚本读)。
  **处理**:同特性续训(already_signed 且 critic_completion 配置相同)且源里没有该目录时,
  不再拒绝,而是在 `continuation.json` 审计里记 `calibration_provenance: absent_in_source`
  (附源 manifest 的 transfer 记录);有目录时行为不变(必须 passed 且拷贝)。runner 仍会在
  模型没有 `exam_quantile_head` 时拒绝续训。
- 第二次启动成功:`continuation-staging.json complete=true`,progress 从 batches=4 /
  decisions=450312 继续,审计里 `configuration_changes` 只有 `search`(seconds 300→400)。
- 第一批(b4)collect 开始:前 2 分钟 1509 决策是抽卡阶段的快决策,之后 48 根搜索同时在飞
  (400 s 预算),节奏会回到约 45 分钟一批的 collect。rank 0 RSS 3.2 GB(prod-v3 同期 60+ GB)。
- dashboard 由 dashd2 自动切到 prod-v4;本地 watcher `loop_batch4.sh 5 prod-v4` 在跑。
- 回滚材料:`scripts/prod-v3-code/`(prod-v3 部署时的 ppo/distributed/runner/continuation/
  practice/bank_rollout/critic_completion/train.py,启动脚本有"已存在则不覆盖"保护)。

## prod-v4 第一批(b4,14:03 提交)实测:改造生效

```
                     prod-v3 b3     prod-v4 b4
collect               46.4 min       57.0 min   (搜索预算 300→400 s;'ok' 满 64 次模拟的根 0 → 91)
fork_exam             12.7 min        7.6 min
bank_exam              4.0 min        0.6 min
ppo_update            50.0 min       25.6 min   (records_broadcast 约 23 min → 0.3 s,每卡只发自己的 15k 条)
批次(采集→更新)    ~113 min        ~91 min
rank 0 RSS            62–86 GB        11 GB
```

正确性交叉核对(全部全局归约):ppo 121584 + search 2956 = 124540 = update_coverage.record_count
= task_records 五个 profile 之和;signed credit all_exam 99618 = phase_decisions[0];无 Traceback。

学习信号继续向好:gain 0.1045 → **0.0712**,KL 0.0076,训练归一化均分 0.820 → **0.887**,
best-of-4 验证指数 1.118 → **1.157**,根采纳率 86.5% → **94.9%**(inference_deadline 48 → 12)。
每 profile 绝对分(0003 → 0004):hiro-hif 679769 → 656826(唯一回落),liliya-xmas 192293 → 200082,
saki-hif 388404 → 431699,saki-wild 295613 → 333551,ume-campus 238586 → 241689。

已知只覆盖 rank 0 的诊断键(v3/v4 不可比):`duplicate_regularization.draft_records`(1885 vs
之前约 15000)、`post_update_kl` 抽样、`signed_credit.samples`、梯度探针。

待用户决定:精神統一同名上限 2 → 4(硬上限改动会重置构筑基准并需要边界续训;
`free_copies` 3 意味着第 4 张在抽卡阶段扣 0.1)。

## 精神統一 同名上限 2 → 4,保留验证历史(prod-v4 → prod-v5,用户 14:35 决定)

用户:"精神统一我们放开吧但是能不能就是不清空历史啊?"

- 原代码:续训时 `max_same_name` / `max_same_name_overrides` 任一变化 → `reset_joint_reference`:
  validation-*.json 和 validation-history.jsonl 挪进 `previous-construction-benchmark/`、
  best*.pt 复制归档、重跑 180 局 validation-initial 当新基准、best 指数归 1。什么都没删,
  只是新目录里的曲线从头开始。理由是上限变了,新旧验证分不在同一规则下。
- 新增 `practice.duplicates.keep_benchmark_history: true`(continuation.py):上限变化但不归档、
  不重测基准,`reset_joint_reference=False`;审计里记 `construction_benchmark_change.history_kept`,
  并写 `construction-benchmark.json`(新上限、起始批次、说明)。**代价**:之后的验证指数是
  新上限下的分数除以旧上限下的初始基准,涨幅里混着上限本身的效果;best.pt/best4.pt 的选择也会
  偏向改上限之后的 checkpoint。用户已知晓并选择保留历史。
- 软惩罚 `free_copies` 仍是 3:第 4 张精神統一在抽卡阶段扣 0.1 × 1² = 0.1 归一化分(封顶 0.75)。
  用户没要求改 free_copies,本次不动;要完全放开再在下一个边界改。
- 离线验证:用 stage4 树里的新 continuation.py 以 prod-v3 为源、临时目录为输出跑完整 `stage()`:
  `reset_joint_reference=False`,历史 4 行 / 7 个 validation 文件原样保留,无归档目录,
  `configuration_changes` 只有 practice,staging complete。临时目录已删。
- 流程:14:35 放 `runs/prod-v4/stop-after-batch.json`(b5 采集中,约 15:35 边界)→ 最终评估
  约 25 分钟 → `docker exec gakumas-rl-8npu bash scripts/launch_v5.sh`:门槛 → 备份 prod-v4 的
  continuation.py 到 `scripts/prod-v4-code/` → 部署新 continuation.py(唯一改动文件)→
  `configs/prod/search-v5.json` = v4 + 精神統一 4 + keep_benchmark_history → 续训到 runs/prod-v5。

## 搜索监督 3000 vs PPO 120000,以及搜索预算/超时 ×1.5(用户 15:10 决定,随 prod-v5 一起生效)

**为什么差 40 倍**:PPO 记录 = 每局每个决策(exam 99.6k + draft 15.2k + guidance 7.2k + drink 1.1k +
memory 1.5k ≈ 124.5k,含 640 joint + 288 fork + 12 bank 局);搜索监督记录 = 每个通过采纳的根搜索
一条。根搜索只在 joint 局的 exam 决策上开(fork 局自批次 2 起不开),每局最多 `max_roots_per_episode`
4 个,且每个根占一个槽最长 `seconds` 秒:8 卡 × 48 槽 × 57 分钟 / 约 6 分钟每根 ≈ 3600 根的槽时上限,
实测约 3000。所以比例是结构性的,由槽时决定,不是 bug。梯度上搜索损失按自己的记录数归一化
(`search_totals`,每 profile 权重和 = n_global/P),再乘 `loss_coefficient` 0.1,所以 3000 条不等于
只占 2.4% 的梯度。**注意 metrics 里 `search_batch.counts`(attempted 376 / accepted 357)只是 rank 0
的路由计数,乘 8 才是全批;batch_report.py 已标注。**

**佑芽(ume-campus)确实最吃亏**(prod-v4 400 s 时代 3402 根,按 profile):

```
profile       n    撞 400 s 墙   平均模拟数/64   有效目标   丢失的根(inference_deadline/deadline/root_budget)
hiro-hif     683      81.6%          47.9        97.6%      19
liliya-xmas  685      61.5%          54.8        99.7%       2
saki-hif     678      89.1%          46.5        98.8%       8
saki-wild    686      75.4%          50.6       100.0%       0
ume-campus   682      97.5%          32.9        87.4%      73  (10.7%)
```

ume 每次模拟约 12 s(考试长、rollout 到终局深),400 s 只跑 33 次;`inference_deadline` 是根的死线
到了时推理请求还没回来,树还不够"可保住"(每个动作 <2 个样本)就整根丢掉。原生动作预算
`native_action_budget` 60000 完全没顶到(各 profile 均值 1.7 万–2.2 万,0% 超 5 万),不用动;
根的动作数均值 4.7、没有超过 32 的,所以 `simulations` 64 的预检拒绝也没发生过。

**改动(search-v5.json,续训 permitted 键)**:`seconds` 400 → 600,`simulations` 64 → 96,
`sampling_ms` 10000 → 15000。`soft_budget` 根选择不随 simulations 缩放(按软概率分配欠账),
提高上限只让能跑满的根(liliya/saki-wild)多跑。预期:ume 模拟数 33 → 约 49、丢根明显减少;
collect 57 → 约 80 分钟,单批约 90 → 约 115 分钟。用户明确接受等待。

## 16:23 prod-v5 启动;prod-v4 收官;时限延到 96 小时;用户说不用一直盯

**prod-v4 最后一批(b5,16:03 提交)**:collect 68.3 / update 26.8 分钟;ppo 127331 + search 2942;
gain 0.0763,KL 0.0092,训练归一化均分 **1.059**;best-of-4 验证指数 1.157 → 1.199 → **1.241**;
固定对局 1.033 → 1.069。最终测试:test_index **1.2728**,test_best4_index **1.2835**,
best_validation_index 1.2515。

**每 profile 绝对分(initial → 0006)要注意分化**:saki-wild 242884 → 414082(+71%)、
liliya-xmas 141745 → 236649(+67%)、saki-hif 349821 → 421764(+21%)在涨;
**hiro-hif 679769(0003)→ 610188(0006)连跌三次,ume-campus 252796(0005)→ 220483(0006)
已低于初值 225484**。同一个共享模型在五个 profile 之间取舍,best-of-4 总指数还在涨,但佑芽和广
的绝对分在往下走,后面几批要看是不是趋势;佑芽这批起搜索预算 ×1.5,正好能看出有没有帮助。

**prod-v5**:16:23 启动,staging complete,从 batches=6 / decisions=697484 续;审计
`configuration_changes = [practice, search]`,`construction_benchmark_change.history_kept=true`
(change_batch 6);配置 精神統一 4、seconds 600 / simulations 96 / sampling_ms 15000。
第一批 collect 正常起跑(48 live)。

**时限 48 → 96 小时(用户 16:25)**:`RuntimeWindow` 只在每个批次边界重读
`runs/prod-v5/training-window.json`(原子替换,不重置 elapsed/探索/权重/RNG),所以热改即可:
absolute_deadline = 原始起点 2026-09-16 18:20:40 UTC + 5760 分钟 = **2026-09-20 18:20:40 UTC**,
max_minutes 5760。`configs/prod/search-v5.json` 的 max_minutes 同步改 5760,给以后的续训用
(续训的 deadline 由 started_at + max_minutes 算,不改会在 09-18 之后拒绝续训)。
下一批边界日志应出现 `training_window_updated`。
**提醒**:`learning_rate_schedule` 是 elapsed_minutes 基准、hold 120 + decay 2880 分钟线性降到
0.2 倍,48 小时后学习率停在 0.2× 地板;要让 96 小时都有像样的学习率,需要在某个边界续训时把
decay_minutes 改 5760(learning_rate_schedule 是 permitted 键,有 validate_schedule)。未改,等用户定。

**用户指令**:后面不用一直盯着,叫的时候再上去看。本地 watcher 已不再布置。

## 16:55 前台"最近对局"改为读每卡分片(用户 16:50 同意)

现象:列表自 15:20 没变。原因不是坏了:8 卡各写 `train-episodes.rankN.jsonl`,阶段(collect/fork/bank)
全部结束才合并进 `train-episodes.jsonl`,列表一批只变三次;600 s 搜索预算下第一批 collect 前 40 分钟
连一局都没打完。改动只在 dashboard 数据层:`generalist_data.sources('train')` 先列 mtime 最新的分片再列
主文件(分片被合并删掉时跳过);打开一局仍按文件名+seed 找,分片合并后会提示"刷新列表"。
19 个 dashboard 单测通过;dashd2 重启前台;API 已返回 7 张卡 10 局进行中对局 + 主文件 110 局。
原文件备份 `scripts/prod-v4-code/generalist_data.py.orig`。dashboard 目录不在源码指纹里,不影响训练。
