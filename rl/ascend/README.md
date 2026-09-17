# ARM64 + 昇腾：搜索训练、完整育成与 Arena

本包接入 `generalist-search-signed-credit` 的最新源码：公开历史蒙特卡洛搜索、异步搜索进程、软搜索预算、四局目标、32 分位价值头、构筑/考试分支和样本库，并包括正负贡献学习、搜索行为/学习目标分离、KL 停止后的独立价值补训。随包提供完整 checkpoint 和前台观测台。另含独立的 `gakumas_training` 完整育成/单场考试训练包。两个入口都支持单卡 NPU 和多卡同步梯度更新。

**两套任务保留各自的观察、奖励和检查点契约。** 搜索改进在 `exam-search` 入口中完整保留；完整育成入口仍优化整局原始育成评价，没有把“四局考试最高分”替换成育成目标，也没有把搜索标签直接塞进育成 PPO。

本地完成的检查见 [验收记录](ACCEPTANCE.md)。真机（Atlas 800T A2 / 8×Ascend 910B3）上的八卡性能改造见 [ASCEND_OPTIMIZATION.md](ASCEND_OPTIMIZATION.md)，生产训练期间的修复、改造与实测结果见 [生产训练报告](PRODUCTION_RUN.md)，逐日排查流水账见 [RUN_NOTES.md](RUN_NOTES.md)。

## 1. 环境和安装

目标为 Linux ARM64、Python >= 3.11、Node.js >= 20、配套的 PyTorch/torch_npu/CANN 和驱动。以平台提供的昇腾镜像为准。2026-09-15 查阅的[官方配套表](https://github.com/Ascend/pytorch/blob/master/COMPATIBILITY.md)列出 推荐 PyTorch 2.12.0 / torch_npu 2.12.0 / CANN 9.1.0，同时列有 torch_npu 2.12.0.post2 / CANN 9.1.X 的更新组合；这不是对尚未确认的“900 系列”硬件型号的驱动兼容承诺。[官方安装说明](https://github.com/Ascend/pytorch#installation)要求驱动、固件也匹配实际硬件。

解压 ZIP 后在包根目录执行。先按服务器的实际路径加载 CANN 环境，常见路径之一为：

```bash
source /usr/local/Ascend/cann/set_env.sh
# 较早镜像常用 /usr/local/Ascend/ascend-toolkit/set_env.sh
bash ascend/install.sh
source .venv/bin/activate
mkdir -p ../gakumas-evidence ../gakumas-runs ../gakumas-scratch
python ascend/doctor.py --expected-npus 8 --output ../gakumas-evidence/environment.json
```

安装脚本继承已有 PyTorch/torch_npu；不会替换驱动/CANN/PyTorch。Node 必须是服务器架构的版本，不能搬入 Windows 的 node.exe 或虚拟环境。版本不匹配、设备不可用会报错，不自动改成 CPU。

## 2. 按机器配置规模

学习卡数、Arena 采集进程数、并发搜索数、推理合批、训练批量和 PyTorch CPU 线程数都接受正整数，**没有 8 卡、128 进程等应用层固定上限**。实际规模取决于可见设备、内存、操作系统和 PyTorch/CANN 的能力。`microbatch_size` 不能超过全局 `minibatch_size`；多卡仍要求在同一台主机上。

下面生成一套新配置；可以任意修改这些数字。8/96/24 是针对所述机器的起点。已有配置文件会拒绝覆盖，以免改写正在运行的实验。

```bash
CONFIG_DIR=../gakumas-configs/first-run
python ascend/configure.py --output-dir "$CONFIG_DIR" \
  --learners 8 --workers 96 --search-workers 24 --inference-batch 32 \
  --batch-decisions 32768 --episodes-per-update 96 \
  --minibatch-size 512 --microbatch-size 2 --torch-threads 2
LEARNERS=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["learner_world_size"])' "$CONFIG_DIR/search.json")
```

输出 `search.json` 和 `full_produce.json`，分别供两个训练入口使用。省略的参数继承预设；可用 `--search-base` / `--full-base` 指定自己的基础配置，`--device` 指定 `npu:0`、`cuda:0` 或 `cpu`。生成器只需 Python 标准库。重新打开终端后，先设置同一个 `CONFIG_DIR`，并重跑上面的 `LEARNERS=...` 读取命令。

| 命令参数 | 搜索配置字段 | 完整育成配置字段 | 含义 |
|---|---|---|---|
| `--learners` | `learner_world_size` | 启动时的 `--world-size` | 单机学习进程数；多卡时每进程一张卡，`torchrun` 数量必须一致 |
| `--workers` | `parallelism.workers`、`workers` | `workers` | 全作业的 Arena 采样并行度，不乘学习卡数；每个环境还可能启动 Node |
| `--search-workers` | `parallelism.parallel_roots` | — | 全作业的独立 MCTS 搜索进程数 |
| `--inference-batch` | `parallelism.inference_batch` | — | 搜索推理一次最多合并多少条请求，不强制等满 |
| `--batch-decisions` | `batch_decisions` | — | 每批有效采样决策数的软预算；完整对局收尾可超过它 |
| `--episodes-per-update` | — | `episodes_per_update` | 每轮 PPO 前采集的完整育成局数 |
| `--minibatch-size` | `effective_minibatch` | `ppo.minibatch_size` | 一次 Adam 更新的全局记录数；各卡分担，不再乘卡数 |
| `--microbatch-size` | `parallelism.microbatch` | `ppo.microbatch_size` | 每卡每次前向/反向的记录数，梯度累计到全局批量 |
| `--torch-threads` | `parallelism.torch_threads` | `torch_threads` | 每个学习进程的 PyTorch CPU 计算线程数，不是 Node/系统总线程数 |

默认配置文件名中的 `1npu` / `8npu` 只是示例。比如 16 卡、256 个采集进程、64 个搜索进程，可以填 `--learners 16 --workers 256 --search-workers 64`，无需改源码。提高完整育成的 `workers` 时也要提高 `episodes_per_update`，实际启动环境数不会超过本次待采集的局数；评估局数仍由 `eval_episodes` 等任务参数控制。

## 3. 先做单卡与多卡检查

```bash
python ascend/run_tests.py
python ascend/preflight_search.py --device npu --output ../gakumas-evidence/search-1npu.json
python ascend/doctor.py --expected-npus "$LEARNERS" --output ../gakumas-evidence/environment.json
torchrun --standalone --nnodes=1 --nproc-per-node="$LEARNERS" ascend/preflight_search.py --device npu --output ../gakumas-evidence/search-multinpu.json
python colab/preflight.py --bundle-root . --device npu:0 --config "$CONFIG_DIR/full_produce.json" --output ../gakumas-evidence/full-produce.json
```

搜索预检真实调用 Arena/Node，验证两个公开历史搜索根不改变真实对局，完成一场短考试、前向反向、Adam 更新和随机状态恢复。8 卡命令还实际执行 HCCL 梯度求和。完整育成预检覆盖所选编成和初始选择模式，但这些通过都不等于策略已提高或游戏规则已全量实证。

多卡用 Gloo 传递 CPU 控制/样本数据，用 HCCL 传递 NPU 梯度。容器须允许进程间通信；若平台指定网卡，按平台说明设置 `GLOO_SOCKET_IFNAME`/HCCL 网络参数。当前为**单机多卡**；不要把命令改成多机运行。

## 4. 开始最新搜索模型的训练

先用小配置加载随包 checkpoint，跑完整一批。使用新输出目录：

```bash
python exam-search/train.py --config ascend/configs/search_smoke.json --initial checkpoints/latest.pt --output ../gakumas-runs/search-smoke
```

再按生成的配置正式运行：

```bash
torchrun --standalone --nnodes=1 --nproc-per-node="$LEARNERS" exam-search/train.py --config "$CONFIG_DIR/search.json" --initial checkpoints/latest.pt --output ../gakumas-runs/search-main
```

`search_8npu.json`：96 个 Arena 采集进程、24 个搜索进程、32 个搜索推理合批上限、每批至少 32768 个有效决策、全局优化批量 512、每卡微批 2。对局会完整收尾，实际样本数可超过软预算。四局复测与样本库会增加实际场数。

CPU 进程数还伴随 Node 子进程，96+24 是 128 核机器的起始配置。采集、搜索和各学习进程的 CPU 线程会共同使用主机资源。先看 `collection_seconds`、`update_seconds`、搜索超时率和内存，再调整 `parallelism`。应用不会按固定数字裁小你的设置；操作系统或设备无法承载时仍可能失败。

**rank 0 持有策略、采样与搜索推理；各学习卡在 PPO/搜索/价值损失更新阶段分担微批并求和梯度。** 采样期的推理集中在 rank 0，其余学习卡可能空闲，吞吐不会保证按卡数增长。完整批数据以 CPU 对象分发到每个学习进程，主机内存约随卡数增长；大批量先逐级增大。

单卡较长实验使用 `search_1npu.json`。正式配置保留 180 场评估以及固定打牌分层评估；首次基线可能耗时较长。

### 权重、恢复和停止

包内的 `checkpoints/latest.pt` 是封存时最新的完整检查点：**2026-09-15 18:48:58（北京时间），batch 14，190,584 个有效决策，33,809,227 字节**。保留全部模型、32 分位价值头、Adam 和原始恢复元数据；文件 SHA256 为 `f482b54dccaddfd3d154e963b28142aad6d831baca93b9ac777e2c3a13954eb8`。详见 [checkpoint 来源](checkpoints/provenance.json)。

它由 `generalist-search-soft-value` 运行产生；最新 signed-credit 源码在封存时尚未完成生产运行切换。服务器用 `--initial` 继承该权重和 Adam，再开始新框架训练，建立新的基线、随机状态和日程。原 Windows 日志、源实验计数和已结束的绝对截止时间不带入新运行。该 checkpoint 仅供搜索训练入口，完整育成具有独立模型契约。

省略 `--initial` 可从随机权重开始。后续自己的新 checkpoint 也可替换该路径；应使用兼容的模型和编码。

同一部署版本、配置、卡数与输出恢复：

```bash
torchrun --standalone --nnodes=1 --nproc-per-node="$LEARNERS" exam-search/train.py --config "$CONFIG_DIR/search.json" --output ../gakumas-runs/search-main --resume
```

写入停止标记后会完成当前批次、保存并做收尾评估：

```bash
printf '{}\n' > ../gakumas-runs/search-main/stop-after-batch.json
```

再次继续前删除这个明确的停止文件。改卡数或配置须新建运行，不能冒充同一断点的精确恢复。看输出下的 `progress.json`、`metrics.jsonl`、`search-roots.jsonl` 和 `latest.pt`。

## 5. 完整育成与大规模采样

```bash
torchrun --standalone --nnodes=1 --nproc-per-node="$LEARNERS" ascend/train_full.py --world-size "$LEARNERS" --bundle-root . --task full_produce --config "$CONFIG_DIR/full_produce.json" --run-name full-produce-main --local-root ../gakumas-scratch --persistent-root ../gakumas-runs --total-hours 48 --session-hours 8
```

上面的生成命令配置了 96 个独立 Arena/Node 采样进程、每批 96 场完整育成、每卡微批 2、全局优化批量 512；原 `full_produce_npu.json` 示例的微批为 1。初始基线、完整育成与检查点同步可能较慢。先用另一份配置把 workers/episodes_per_update 减小，并加 `--max-updates 1` 做链路检查；正式运行用新名字。

相同命令再次执行会从持久化目录的完整检查点恢复。`local-root` 为临时运行盘，`persistent-root` 必须是平台真正保留的数据卷，二者必须不同；8 小时会话窗口只在完整更新边界结束。完整育成仍使用原有合法候选、原始育成分奖励和五编成边界，详细规则见 `training/README.md`。

### 运行中调整完整育成规模

完整育成的四项执行参数可通过控制文件热调整，保持当前模型、Adam 和训练进度。先写临时文件，再改名提交：

```bash
mkdir -p ../gakumas-runs/_runtime_controls
cat > ../gakumas-runs/_runtime_controls/full-produce-main.json.tmp <<'JSON'
{"workers": 256, "episodes_per_update": 512, "minibatch_size": 2048, "microbatch_size": 8}
JSON
mv ../gakumas-runs/_runtime_controls/full-produce-main.json.tmp ../gakumas-runs/_runtime_controls/full-produce-main.json
```

四项都必须为正整数，微批不超过全局批量。workers/局数在下一次采集边界生效，mini/micro 在下一次 PPO 更新开始前生效。查看同目录的 `full-produce-main.status.json`，其中包含请求值、实际值和错误；无应用层上限在状态元数据中记为 `null`。Notebook 第 8 格提供相同控制，也接受大于旧上限的值。

学习卡数与 CPU 线程数按启动配置设置。改变这些参数时建立新运行；搜索任务的采样进程、搜索并发、推理合批、微批和线程数可在下面的观测台中热调整；基础配置或学习卡数改变时，用新配置和新输出目录配合 `--initial` 承接兼容权重。精确 `--resume` 仍要求同一源码、基础配置和卡数，不能把改变训练轨迹的配置当作精确恢复。

## 6. 前台观测台

在另一个终端激活同一虚拟环境，从包根目录执行。`--run` 明确选择本次训练目录，支持绝对路径：

```bash
source .venv/bin/activate
python dashboard/server.py --run ../gakumas-runs/search-main --port 8900
```

第一次测试可改成 `--run ../gakumas-runs/search-smoke`。训练开始并创建目录后即可启动观测台。它展示进度与损失曲线、分偶像/场景的固定评估、Best4、搜索预算和回退、正负贡献统计、搜索行为与学习目标、actor/critic 样本覆盖、对局与逐步回放、训练日志。随包包含卡牌/饮料名称和 892 个已有图标；缺失图标按文字显示。

在自己电脑上建立 SSH 转发，再打开 [本地观测台](http://127.0.0.1:8900)：

```bash
ssh -N -L 8900:127.0.0.1:8900 USER@TRAINING_SERVER
```

观测台绑定服务器 `127.0.0.1`。资源表单接受正整数，没有 48/128 等固定档位上限；每卡微批不能超过该运行全局批量。提交后等待当前完整批次收尾、更新完成，再重建采样/搜索进程并应用参数。页面同时显示当前值与待应用状态。学习卡数与全局批量仍在启动配置里设置；已结束任务的表单禁用。

回放使用该运行 manifest 指定并校验哈希的冻结 Arena，在当前 Python 的独立 CPU 子进程中执行，不加载 NPU 模型。训练目录移动后，应保持部署包路径与 manifest 中的引擎路径一致；精确恢复要求保留同一部署版本。此观测台对应搜索训练；完整育成的运行状态和持久化规则见上一节及 `training/README.md`。

## 7. 本地重新打包与来源

集中审查设备、多卡、采样和恢复改动，可先看 [移植清单](PORTING.md)。

在原工作区根目录执行：

```text
python rl/hif-colab/build_training_bundle.py --target ascend
```

输出为 `rl/training/artifacts/ascend/gakumas-ascend-training.zip`，旁边有 SHA256。包内 manifest 逐文件校验。`ascend/source-import.json` 保存从 `generalist-search-signed-credit` 接收的源文件原始哈希；`ascend/full-arena-import.json` 记录另行冻结的 700 个当前 Arena 源码和主数据文件。适配后的变化由 Git 记录。

搜索目录内的 `continue_*.py` 是保留供审计的旧 Windows 监督脚本，依赖原本机监控环境；昇腾只使用上面列出的 `train.py --resume` 入口。相关旧监督测试不列为昇腾验收。

搜索入口绑定其原冻结 Arena，完整育成使用当前独立 Arena，均随包携带。它们的版本各自校验；没有用一个不同版本的引擎冒充旧搜索预设绑定的规则。
