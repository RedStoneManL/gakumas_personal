# V6 训练优化与回放修复：2026-09-20 整理说明

这批改动在最新 V6 搜索贡献框架上保留六套偶像配置，并减少采样、进程间传输和 PPO 更新中的等待。正式生产已完成首个池化优化批次及常规评估，之后继续训练。本次整理只准备源码和文档提交，不触发部署、重启训练或推送。

## 阅读顺序与证据截止

- [优化台账](optimization-results.md)：每项改动、验证范围和第 1–14 批完整生产观察。
- [可移植证据摘要](evidence/optimization-20260920.json)：14 批指标、首个池化批次的资源采样、续训审计和回放结果；来自已保存的生产证据，不是再次运行测试生成的结果。
- [历史排查记录](optimization-progress-20260919.md)：保留失败尝试、候选版本和切换过程。旧 PID、待办和“尚未上线”均为当时快照，应以台账的收尾结论为准。

证据固定截止 **2026-09-20 07:32（北京时间）**。生产仍在继续，本文不作为实时状态页。局部数值门、整批生产吞吐和硬件采样分别陈述；不能把局部测试增幅或相邻批次差值当成严格因果收益。

## 代码改动范围

| 范围 | 最终行为 | 主要位置 |
|---|---|---|
| 配置与卡池 | 合并六套配置、producer level 80 卡池及 V6 搜索贡献框架；全局搜索计数汇总各 rank | `exam_search/setup/`、`scripts/build_profiles.py`、`draftrl/distributed.py`、`draftrl/runner.py` |
| CPU 和传输 | 冻结策略词法缓存、紧凑 prepared-input 编码、缓冲 GRU 反向和独立词法分支并行 | `draftrl/lexical_cache.py`、`compact_input.py`、`buffered_gru.py`、`parallel_lexical.py` |
| PPO 输入与聚合 | 在 CPU 预先准备结构和 tower 切分，有限深度预取微批，复用池化分组计数 | `draftrl/batch_pipeline.py`、`fast_collate.py`、`tower_inputs.py`、`runtime/shared/round2rl/model.py` |
| 阶段并发 | 辅助搜索尾部与真实 fork 回放重叠；保留动作、终局证据和信用分配契约 | `draftrl/fork_overlap.py`、`async_decisions.py`、`distributed.py` |
| 优化器与评估 | 可选原生 NPU foreach Adam/裁剪；固定打牌评估分片；复用一致的启动基线 | `rl/training/gakumas_training/device.py`、`draftrl/ppo.py`、`play_evaluation.py`、`best_of.py` |
| 可靠性 | 固定异步 choice 快照，拒绝动作不匹配的辅助 root，修复搜索进程退出等待 | `draftrl/async_decisions.py`、`async_service.py`、`search_router.py`、`process_service.py` |
| 回放 | 旧部署路径可回退到面板自带运行时；建局前仍验证记录中的内容哈希，并核对终局、分数与回合顺序 | `dashboard/generalist_data.py`、`test_replay_runtime_relocation.py` |
| 面板统计 | 区分预算准入、最终标签和正权重；展示逐批耗时、资源配置、活动时间及停止状态；支持六套配置筛选 | `dashboard/generalist.html`、`generalist.js`、`generalist_data.py`、`search-panel.js` |

表中的 `draftrl/` 均指 `exam_search/draftrl/`；部署包中搜索目录名为 `exam-search/`。配置、质量门、优化目标和训练轨迹未为追求利用率而放宽。

## 实际生产设置与开关

第 14 批的实际资源配置为：8 个 learner，384 个环境 worker，384 个全局搜索槽（每 rank 48），推理合批 48，CPU threads 4，microbatch 128，全局有效优化批量 1024；root 时限 1200 秒，最多 96 次模拟、8 个粒子，PPO 4 个 epoch。

这些是**运行时实际值**。`configs/prod/search-v6-credit-throughput.json` 保留了早期起点的 microbatch 64；当前 128 来自后续经过验证的资源调整，不能把配置文件默认值误作生产证据。`configs/search_v6_credit_perf.json` 是诊断配置，不应作为正式训练配置使用。

| 环境变量 | 本次生产值 | 作用 |
|---|---|---|
| `GAKUMAS_LEXICAL_GRU_BACKEND` | `cpu-buffered` | 词法 GRU 使用缓冲 CPU 路径 |
| `GAKUMAS_PARALLEL_LEXICAL` | `1` | 独立词法分支并行 |
| `GAKUMAS_PREPARED_TOWERS` | `1` | 复用预先准备的 tower 结构 |
| `GAKUMAS_PPO_PREFETCH` | `1` | 有界 CPU 微批准备与计算重叠 |
| `GAKUMAS_FORK_OVERLAP` | `1` | 辅助搜索与 fork 尾部重叠 |
| `GAKUMAS_NPU_FOREACH` | `1` | 原生 NPU foreach Adam/裁剪；代码默认 `0`，新启动须明确设置 |
| `GAKUMAS_PREPARED_POOL_COUNTS` | `1` | 复用 CPU 准备的池化计数 |

启用配置不等于承诺在其他设备、精度或样本规模上获得相同收益。改变续训版本应在完整批次及评估边界封存最新状态，并核对模型、Adam、RNG、种子、样本库和历史；历史切换脚本中的固定 PID、路径和旧检查点不能直接重跑。

## 实测结果与收尾

- 第 1 → 14 批，按 PPO 记录数归一的更新吞吐约 **2.42 倍**；采集＋更新的有效决策吞吐约 **1.90 倍**，不含评估。
- 输入预取首次生产观察约 **+16.22%** PPO 吞吐；搜索/fork 重叠首次观察采集时间约 **-19.06%**。
- foreach 第 9–13 批合并吞吐比第 8 批约 **+10.85%**。池化首批比这五批基线仅 **+1.47%**，局部 22.6% 耗时下降未在整批等比例兑现。
- 第 14 批 368/385 roots 预算准入，318 个最终辅助标签、51 个正权重，`search_loss=0.0117171`。`search_records=0` 表示辅助模式未接管真实动作，不代表监督为零。
- 259 个有效八卡采样中，PPO 平均 AICore 约 2.655%，主机 CPU 约 7.37%，单卡 HBM 峰值约 63.25 GiB。80% 参考值尚未达到；这里的吞吐倍数不是硬件利用率。

按实际收益和实施成本，本轮停止追加复杂性能改造，保留已验证版本继续训练。更大微批、跨批 actor/learner 重叠及全面图编译或算子重写，均需额外正确性工作且收益不确定。健康监视已降为每小时一次，普通进度不通知。

## 验证与发布边界

历史真机证据包括：池化改动 15 项 CPU 检查、一次 25.80 秒 NPU 数值门、31 项状态保全续训审计；回放在旧 run 与池化 run 上均用真实轨迹验证，后者为 28 帧、85159 分完全一致。原始远端证据索引保留在台账和历史记录中。

本次推送准备重新执行面板回归：27 项，其中 26 项通过，1 项因 Windows 创建符号链接权限跳过；Linux 上同一迁移测试已有 4 项通过的历史证据。两个 JavaScript 文件通过 `node --check`。六套配置均通过本地真实 Arena 对局检查（无模型、无训练）；55 个 Python 和 5 个 JSON 文件通过静态解析，四份文档/证据的打包清单、ZIP 内容和相对链接通过检查。检查结果保存在 `validation/push-preparation-20260920.json`。本机 Python 3.11/3.13 未安装 PyTorch，因此没有重新声称完整 learner 数学回归通过，也没有为整理提交重跑服务器 perf。

维护者在具备 PyTorch 的环境可运行仓库回归入口 `python rl/ascend/scripts/run_tests.py`；打包后对应 `python ascend/run_tests.py`。面板回归命令为 `python -m unittest discover -s rl/ascend/dashboard -p 'test_*.py' -v`，打包后目录为 `dashboard`。新增优化模块的单项数值与并发验证记录见历史文档。

## 提交与资料边界

发布分支为 `codex/npu-utilization-v6-credit`，保留相对 `origin/codex/v6-search-credit` 的原有实现、合并和验证历史，不压平或重写已有提交。本次补交面板统计，并增加文档导航、可移植证据摘要和打包文档清单。

原目录中 `distributed.py` / `runner.py` 的未提交搜索计数差异与提交 `43fbbf4` 一致，已被本分支包含；原文件保持原状。诊断目录中的 SSH helper、固定 PID 切换脚本、临时 ZIP、检查点和服务器日志不整体纳入 Git。只收录与结论直接相关、可在仓库中阅读的证据摘要。
