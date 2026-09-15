# 独立强化学习训练包

这个目录实现两个独立任务：`full_produce` 学习育成流程中的公开决策，`exam_score` 从给定入场配置开始优化单场考试得分。两者共用编码、模型和 PPO 的实现代码，各自持有词表、权重、Adam 状态、采样数据和评估记录。

实际网络与状态表达见 [MODEL_CONTRACT.md](MODEL_CONTRACT.md)，本次测试、真实更新和恢复结果见 [ACCEPTANCE.md](ACCEPTANCE.md)。

Colab 长训入口、五编成配置与 Drive 续训见 [Colab 使用说明](colab/README.md)。
ARM64 + 昇腾 NPU、多卡更新、可配置规模的 Arena 采样与最新搜索训练源码见工作区的 `rl/ascend/README.md`（昇腾 ZIP 解压后为根目录 `README.md`）。卡数、进程数、批量和 PyTorch CPU 线程数没有应用层固定上限；配置生成器及完整命令也在该 README 中。
从工作区根运行 `python rl/hif-colab/build_training_bundle.py` 生成训练 ZIP；
配套 Notebook 为 `colab/HIF_Training.ipynb`。ZIP 根目录的 README 包含同一份长训说明。

`exam_score` 默认使用 Arena 的原生考试预设，也可以在配置的 `task_config.entry` 中提供完整入场条目。它目前不学习考试前的自由构筑。`full_produce` 使用配置中的偶像和外部编成，也支持 `task_config.loadout_pool` 在每局按种子轮换完整编成；实际训练覆盖范围取决于 Arena 已实现的流程和当前配置，不代表已验证所有自然育成路径或全部效果的语义等价。

## 依赖边界

`gakumas_training` 负责公开观察编码、合法候选评分、轨迹采集、PPO 和检查点。独立的 Arena 负责游戏规则、合法动作、资源变化、考试执行和终局信息；训练包不复制 Arena 的规则实现，不导入旧实验的 `r1rl`、`round2rl` 或 `draftrl`。

通过 `--arena-root` 指定 Arena checkout 根目录，该目录应包含 `gakumas_arena/`。在本仓库布局下可以省略，适配器会寻找 `third_party/gakumas_arena`；安装到其他位置时建议显式指定。Arena 的原生考试后端还需要其自身要求的 Node.js 和数据资源，详见 Arena README。

## 当前机器直接运行

在本目录打开 PowerShell：

```powershell
cd C:\Users\Liu\Documents\ChatGPT\gakumas\rl\training
.\run.ps1 --help
.\run.ps1 --task exam_score --config configs/exam_score.json --updates 1 --episodes-per-update 2 --output runs/check-exam --device cpu
.\run.ps1 --task full_produce --config configs/full_produce.json --updates 1 --episodes-per-update 2 --output runs/check-produce --device cpu
```

`run.ps1` 优先使用本目录 `.venv`。尚未创建时，它使用现有 Arena `.venv` 的 Python，并仅在该子进程中追加 `rl/round2/.venv/Lib/site-packages` 以读取已安装的 PyTorch 及其依赖。引导脚本不激活、不安装、不修改旧环境，也不把旧训练源码加入导入路径。这个回退仅用于本仓库的开发便利，安装后的训练包不依赖这些本机路径。

`--updates` 表示本次追加的完整 PPO 更新次数。每次更新先完成配置数量的整局，再更新模型；这里的短命令用于检查运行链路。真实训练应根据实际吞吐、内存和独立评估结果设置更多回合与更新。

## 创建独立环境与正常安装

下面命令从 `rl/training` 执行。创建环境和安装依赖由使用者显式运行，`run.ps1` 不会代为执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ..\..\third_party\gakumas_arena
.\.venv\Scripts\python.exe -m pip install -e ".[arena]"
.\.venv\Scripts\python.exe -m gakumas_training --help
```

`torch` 的 CPU/CUDA 构建应与实际机器匹配。需要 CUDA 时，先按 PyTorch 官方安装说明在这个独立环境内安装对应构建，再用 `--device cuda`；请求 CUDA 但不可用时程序会报错，不会悄悄切回 CPU。

普通安装同样支持 `python -m pip install .` 或安装构建出的 wheel。包内包含默认配置和编码所需的语义清单，命令入口为 `gakumas-train`，也可以使用 `python -m gakumas_training`。Arena checkout、其数据和原生运行依赖仍需单独准备。

## 训练、恢复和独立评估

两个任务的输出会自动追加任务名。例如 `--output runs/demo` 下会分别产生 `runs/demo/exam_score/` 和 `runs/demo/full_produce/`，不会把两个模型混放。

```powershell
# 单场任务：先运行一个完整更新。
.\run.ps1 --task exam_score --config configs/exam_score.json --updates 1 --episodes-per-update 2 --seed 91000000 --output runs/demo --device cpu

# 从同一任务的 latest.pt 追加一个更新；省略 --config 时恢复保存的完整配置。
.\run.ps1 --task exam_score --resume --updates 1 --output runs/demo

# 指定检查点做贪心评估，不执行训练更新。
.\run.ps1 --task exam_score --evaluate --checkpoint runs/demo/exam_score/checkpoints/latest.pt --episodes 10 --seed 291000000 --output runs/demo

# 完整育成任务使用自己的权重、种子和输出空间。
.\run.ps1 --task full_produce --config configs/full_produce.json --updates 1 --episodes-per-update 2 --seed 92000000 --output runs/demo --device cpu
.\run.ps1 --task full_produce --resume --updates 1 --output runs/demo
.\run.ps1 --task full_produce --evaluate --checkpoint runs/demo/full_produce/checkpoints/latest.pt --episodes 10 --seed 292000000 --output runs/demo
```

恢复仅支持“整局采样及 PPO 更新均已完成”的安全边界。程序核对任务、完整配置、模型/编码/契约版本及 Arena 版本，恢复模型、优化器、词表、Python/NumPy/Torch/CUDA 随机状态、种子游标和更新编号。更改奖励尺度、编成、批量或设备等保存配置不属于精确恢复，会被拒绝；需要这种迁移时应另行实现明确的迁移流程。

检查点通过临时文件原子替换写入，`checkpoints/latest.pt` 之外保留最近三个更新快照。错误会抛出并写入 `progress.json`；人工决策上限或引擎异常不会伪装成零分样本。现阶段没有中途暂停对局后恢复的能力。

## 学习目标与实现范围

采用合法动作屏蔽的 on-policy PPO-Clip：每次采样固定一个策略版本，保存真实动作概率，更新前重新核对概率；不同任务或不同策略版本的数据不能混入同一更新。独立 Arena/Node 采样进程数接受任意正整数，主进程统一编码并批量推理；按固定 slot 顺序同步收集，完整批次结束后再优化。worker、每批局数和 mini/microbatch 可在安全边界热调整，没有应用层固定上限，微批不能超过全局批量。实际值及控制状态保存在检查点中；种子进度按实际累计局数计算。基础配置中的 `torch_threads` 设置每个学习进程的 CPU 计算线程数，默认 2，接受任意正整数。

奖励在中间步骤为零，终局为 `raw_final_score / C`，`gamma=1`。单场考试默认 `C=150000`，完整育成默认 `C=50000`；尺度在一次运行中固定。每一步使用同一整局终局回报，优势为该回报减去采样时的价值预测，是 Monte Carlo actor–critic，没有 GAE 或 TD bootstrap。没有额外通关奖励、体力奖励、分数对数变换或奖励裁剪；PPO 的概率比率裁剪与奖励裁剪是不同的操作。

损失由 PPO 策略项、SmoothL1 价值项和可配置熵项组成，支持优势标准化、微批梯度累计、KL 提前停止和梯度范数裁剪。配置中的 `minibatch_size` 是一次优化器更新累计的样本数，`microbatch_size` 是一次前向/反向处理的样本数。

完整育成的提前终止须特别解释：默认配置显式选择 `final_formula_zero_unplayed_v1`。选拔阶段正常失败时，以当前参数与星素质代入最终评分公式，未进行的决赛分数按零代入。它是当前训练契约定义的失败估值映射，**尚未实测为游戏在这种失败时实际发放的评价值**。日志保留该来源标记；它不把引擎故障或超时当作正常终止。

## 查看结果与验证

每个任务目录包含：

- `manifest.json`：配置、版本和目标约定。
- `training/episodes.jsonl`、`training/metrics.jsonl`：原始分数、终止类型、决策数、PPO统计及采样/编码/推理/更新耗时。
- `evaluation/`：独立种子下的贪心评估记录，评估会保存并恢复训练随机状态与词表。
- `checkpoints/`：完整恢复状态；`progress.json`：最近进度或异常。

训练与评估种子区间不能重叠。统计包含正常失败的原始得分，不只计算成功局。评估使用贪心动作，环境本身的随机性仍然存在。训练批次均分不是留出评估成绩；完成一次更新只说明训练链条能运行，不能据此宣称策略已经提高。

在包含所有依赖的独立环境中可运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

单元测试和真实 Arena 短验收的具体结果由本次验收报告记录。开始较长实验之前，应先检查任务配置、当前 Arena 能力边界和相同条件下的评估基线。
