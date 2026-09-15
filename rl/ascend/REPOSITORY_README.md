# Gakumas 训练引擎与 Arena

独立的训练源码仓库，包含最新纯打牌搜索模型、完整育成 PPO、各自绑定的 Arena，前台观测台、最新完整 checkpoint，以及 Linux ARM64 / 昇腾 NPU 部署入口。

## 从这里开始

**[安装、配置规模、开始训练和恢复：完整 README](rl/ascend/README.md)**

在训练服务器上拉取本仓库并构建、解压部署包：

```bash
git clone https://github.com/RedStoneManL/gakumas_personal.git
cd gakumas_personal
python rl/hif-colab/build_training_bundle.py --target ascend
python -m zipfile -e rl/training/artifacts/ascend/gakumas-ascend-training.zip ../gakumas-deploy
cd ../gakumas-deploy
# 接着按此目录 README.md：加载 CANN → 安装 → 配置 → 预检 → 训练。
```

构建只需 Python 标准库；训练环境要求 Python >= 3.11、Node >= 20 和配套的 PyTorch / torch_npu / CANN。

## 已包含的版本

- 最新 `generalist-search-signed-credit`：公开历史 MCTS、软预算、Best4、32 分位价值头、异步采样、正负贡献学习、分离的搜索学习目标，以及 KL 停止后的价值补训。
- 完整 checkpoint：2026-09-15 18:48:58（北京时间）、batch 14、190,584 个有效决策；保留模型和 Adam。来源为当时仍在运行的 soft-value 版本，使用 `--initial` 在新框架建立新运行。来源、大小与 SHA256 见 [provenance.json](rl/ascend/checkpoints/provenance.json)。
- 最新前台观测台：进度、曲线、MCTS、正负贡献、价值补训覆盖、对局回放、日志和可配置并行资源表单；包含卡牌/饮料图标。

加载环境、安装和预检后，在解压包根目录先试一批：

```bash
python exam-search/train.py --config ascend/configs/search_smoke.json \
  --initial checkpoints/latest.pt --output ../gakumas-runs/search-smoke
# 另一个终端查看；远程浏览器用 README 中的 SSH 转发。
python dashboard/server.py --run ../gakumas-runs/search-smoke --port 8900
```

## 可调整的训练规模

学习卡数、Arena 采集进程数、MCTS 搜索进程数、推理合批、采样批量、PPO mini/microbatch 和 CPU 线程数均可配置为正整数，没有应用层固定上限。以下数字只是起点，在解压后的目录执行：

```bash
python ascend/configure.py --output-dir ../gakumas-configs/run1 \
  --learners 8 --workers 96 --search-workers 24 --inference-batch 32 \
  --batch-decisions 32768 --episodes-per-update 96 \
  --minibatch-size 512 --microbatch-size 2 --torch-threads 2
```

实际规模受硬件、内存和操作系统约束。微批不能超过全局批量；当前是单机多卡同步更新，采样期的策略推理集中在 rank 0。具体启动命令、参数含义、运行中调参和续训规则见上面的完整 README。

## 代码与来源

| 目录 | 内容 |
|---|---|
| `rl/ascend/exam_search` | 公开历史蒙特卡洛搜索、异步采样、四局潜力估值、32 分位价值头、构筑/考试分支和样本库 |
| `rl/training` | 完整育成 / 独立考试训练核心、PPO、编码、设备、多卡、持久化、Notebook 和测试 |
| `rl/ascend/arena` | 完整育成绑定的 Arena 源码及主数据快照 |
| `rl/ascend/exam_search/runtime/arena` | 搜索模型绑定的 Arena 版本 |
| `rl/ascend/checkpoints` | 完整模型/Adam checkpoint 与来源哈希 |
| `rl/ascend/dashboard` | 前台观测台、读取与回放接口、批次间资源控制、图标 |
| `rl/ascend/scripts` | 安装、配置生成、预检、训练启动和回归入口 |
| `rl/hif-colab` | 可复现部署包的构建脚本 |

Arena 来源为 [RedStoneManL/gakumas_arena](https://github.com/RedStoneManL/gakumas_arena)，绑定快照还包括本地接收的后续改动。
逐文件来源哈希见 `rl/ascend/full-arena-import.json` 与 `rl/ascend/source-import.json`，第三方许可随源码保留。两套 Arena 保留各自契约，完整育成和四局考试目标分别训练。

[移植清单](rl/ascend/PORTING.md) 和 [验收记录](rl/ascend/ACCEPTANCE.md) 说明具体改动、测试证据与实测范围。当前本地验证覆盖 CPU/CUDA、真实 Arena 小规模训练与恢复；ARM64/NPU/HCCL、大规模容量和吞吐仍需在服务器上验证。
