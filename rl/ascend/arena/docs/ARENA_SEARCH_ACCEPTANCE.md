# Arena 搜索接口验收与边界

2026-09-14。结论：**可接入隔离 RL 实验，按根成功状态与权重准入；当前联合 PPO 未切换。不宣称所有历史都有高效条件采样，也不宣称搜索已涨分。**

最终版本：`06fc68d7509e612295b3bb60f6c7d1266a3c89acaf682cf33dd027be291c0293`。原生有效规则 hash：`929b0d99b3aef013c39f7ddf7b8b832300e526e2eda366c1a7ab1242f456b985`，与本轮改动前一致。新接口、后验解释和取消隔离要求见 [API 指南](ARENA_SEARCH_API.md)，RL 接手从 [交接文档](../../../design/rl-search-split-20260914/ARENA_IMPLEMENTATION_HANDOFF.md) 开始。

## 固定证据

- [ready_manifest.json](../build/public_search_20260914/ready_manifest.json)：源码版本、命令、文件 hash、测试和基准汇总。
- [最终测试 XML](../build/public_search_20260914/pytest_final.xml)：**103 passed**，其中 17 项搜索专项、86 项 TrainingExam/自定义组合/实机定制修正相邻回归；0 失败、0 跳过，48.69 秒。
- [最终 60 根基准](../build/public_search_20260914/benchmark_final.json)：每根粒子、权重、ESS、different/duplicate、规则/RNG/重放成本、诊断和续局。
- [可运行示例结果](../build/public_search_20260914/example_final.json)：4 个粒子续局全部正常终局，演示加权均分 50，原实际局历史未变化。50 是小例子的执行结果，不是 HIF 基线或构筑质量标签。
- [失败根清单](../build/public_search_20260914/failed_roots.json)：完整 task key、配置与拒绝诊断；失败没有伪造终局分数。

## 接口契约逐项结果

| 契约项 | 当前证据 | 边界 |
|---|---|---|
| 小牌库后验频率/均值 | 6 张牌开局公开 3 张后，剩余 3 张的 6 种排列，768 粒子；边际容差 .07、有序二元组 .055、首牌标签均值容差 .12，均通过 | 针对已声明的均匀随机模型，不证明任意牌组后验完全精确 |
| 随机插牌分布 | 3 张随机排列再均匀插入 1 张；512 粒子，4 个首牌结果各概率 .25、容差 .065，通过 | 混合固定顺序约束时仍可能使用拒绝采样 |
| 连续公开知识 | 已知两张牌顶→随机插牌保持相对顺序→饮料检索/选择→抽牌和回收洗牌，重放全历史；篡改早期顶牌信息会失败 | 额外 external peek/known_bottom 不接入，显式拒绝 |
| 公平输入 | 同公开历史的不同隐藏粒子 view 一致；搜索/分叉不改实际 TrainingExam 快照/私有调试状态；不同 worker 取消后实际 recorder 可继续 | 策略不得读取句柄/诊断/成本；collector 必须从开局记录 |
| 原生组件 | 3 seeds 与 TrainingExam 对照，覆盖饮料再动、检索、持续 buff、有限次回忆、生成与删除；5 偶像真实开发 entry 覆盖道具/定制/回忆与饮料 | 全目录所有组合未穷举 |
| 多选 | 原生卡 527 双选、嵌套选择、开局选择；append 原生/RNG/重放 0，完整提交与原 choose 的公开后继/历史键一致 | pending choose 仍重跑当前一个命令，已计费 |
| 错误与资源 | 过期/重复/非法操作原子拒绝；本地规则预算失败保留世界；容量回收、批量前缀、外部取消及版本错误测试通过 | 单请求预算；根总预算/并发配额由 RL 扣减；未测并发 RSS |
| CPU 有界基准 | 5 偶像 × 无/有回忆 × 无/有饮料 × 开/中/末局 = 60 根 | 57 根成功，3 根超时，失败场景见下 |
| 版本与生产门控 | 成功/失败响应保留版本；缺失或不匹配的历史版本拒绝；明确返回 valid_for_search | 未自动迁移 collector、loss、checkpoint/optimizer 或在线训练 |

## 五偶像基准

使用现有 `development-only` play-suite 的 20 个不同 entry，idol_id 为 130、148、140、74、64。实际诊断局用固定 seed，动作策略为优先饮料、否则第一合法牌/最小有序选择；不载入模型、不更新参数。每个 entry 取第 0、中位、最后一个未终局公开决策为采样点。

每根请求 4 粒子，**采样**最多 2,000 ms / 512 提案；成功后复制其中两个粒子，各自续局最多 160 步 / 2 秒。`--root-ms` 实际限制采样请求，后续两次续局另有上述预算，不能把它误读成整根总共两秒。每根墙钟含采样、clone、投影、推进和释放；实际诊断轨迹的建局成本单列 `live_setup_cost`，总实验耗时包含它。未运行神经网络，推理/编码数均为 0。

| 位置 | 采样成功 | 采样中位数（含失败） | 整根墙钟中位数 | 整根墙钟最大值 |
|---|---:|---:|---:|---:|
| 开局 | 20/20 | 14.81 ms | 1305.00 ms | 1875.00 ms |
| 中局 | 19/20 | 277.08 ms | 984.50 ms | 2110.00 ms |
| 末局 | 18/20 | 618.10 ms | 750.00 ms | 2031.00 ms |

最终 **57/60（95%）** 采样成功；114/114 次已启动续局正常到终局，失败根未启动续局，因此不能称 60 根全部完成。成功根 ESS 均为 4，distinct 为 1～4，未重采样。示例高 ESS 不排除未覆盖的后验尾部。

第一版相同套件/预算为 21/60；对安全的随机检索和纯随机牌山插牌保留可交换槽位后为 57/60。保留 [v1](../build/public_search_20260914/benchmark_v1.json)、[v2](../build/public_search_20260914/benchmark_v2.json)、[v3](../build/public_search_20260914/benchmark_v3.json) 历史证据。当前机器同时有既有 PPO 和诊断活动，时间仅为有界实测，不作为稳定吞吐上界或严格提速倍数。

### 三个尚未高效覆盖的根

均为広（idol_id=140）的有饮料配置。症状主要是随机插入/检索后，采到的固定位置与历史抽牌不相符；不是忽略效果或规则执行异常。当前 sampler 按原生概率继续拒绝，达到预算后返回 deadline。

| 回忆 | 饮料 ID | 位置 | 尝试 | 接受 |
|---|---|---|---:|---:|
| none | [12, 13, 21, 15] | 末局 / 第 36 次公开提交后 | 32 | 0 |
| hif | [12, 20, 21, 15] | 中局 / 第 17 次公开提交后 | 47 | 0 |
| hif | [12, 20, 21, 15] | 末局 / 第 33 次公开提交后 | 47 | 0 |

这些场景必须受失败门控；不保证简单延长预算就解决。下一项 Arena 性能工作是为带固定相对顺序的随机插牌及其他稀有非抽牌结果设计条件提案、推导似然并做枚举分布测试。在完成前，不能把未验证的后验近似默认为全量训练可用。

## 复现与 RL 后续

```powershell
Set-Location C:/Users/Liu/Documents/ChatGPT/gakumas/third_party/gakumas_arena
.venv/Scripts/python.exe -X utf8 -m pytest tests/test_public_search.py tests/test_training_engine.py tests/test_training_custom.py tests/test_live_game_customization_corrections.py -q
.venv/Scripts/python.exe -X utf8 scripts/example_public_search.py
.venv/Scripts/python.exe -X utf8 scripts/benchmark_public_search.py --suite C:/Users/Liu/Documents/ChatGPT/gakumas/rl/generalist/runs/batch512-20260914-014707/play-suite.json --output build/public_search_repeat/benchmark.json --root-ms 2000 --particles 4 --rollouts 2
```

benchmark 会拒绝覆盖已有输出，复跑使用新路径。证据属于固定版本，源码更新后重新验收。

RL 负责独立 collector、完整公开历史、根/worker 总预算、行为版本冻结、PPO/搜索目标分流、联合更新及检查点迁移。失败根如改用网络策略，仍保留其真实终局数据与正确行为概率。当前接口为联合训练提供搜索能力，不新增“先固定卡组”的前置要求；Colab/RSS/32、64、128 次模拟吞吐和实际涨分不在此次已验证结论内。
