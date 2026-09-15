# 移植与审查入口

## 接收的算法与引擎

- 从 `rl/generalist-search-signed-credit` 接收最新源文件、配置与绑定数据；导入时的逐文件哈希保存在 `source-import.json`。其中包括公开历史 MCTS、异步采样/搜索、软预算、四局潜力估值、32 分位价值头、样本库和独立构筑/考试分支。
- `arena/` 是另行冻结的完整育成 Arena，共 700 个源码、主数据与来源文件，逐文件对应 `full-arena-import.json`。
- 搜索入口继续使用自己绑定的 `exam_search/runtime/arena`，完整育成入口使用 `arena/`。源码目录的 `exam_search` 在 ZIP 中命名为 `exam-search`。
- 新增 `.gitattributes` 保留原始字节，避免 Windows/Linux 换行转换破坏引擎与检查点指纹。

## 重点改动

| 位置 | 改动与原因 |
|---|---|
| `gakumas_training/device.py` | 显式注册 NPU、设备编号检查、只保存当前进程负责的 NPU 随机状态、OOM 分类、恢复 Adam 时重新应用 NPU 执行选项。请求的设备不可用时直接报错。 |
| `gakumas_training/collectives.py` | 单机学习进程数和 CPU 线程数可配置，无应用层固定上限；Gloo 传 CPU 控制和样本，HCCL 求和 NPU 梯度。每个分片按全局批量归一化，再求和，保持原损失权重。 |
| 两套 `distributed.py` 与 PPO 更新器 | rank 0 发出同一批记录、模型和 Adam 状态，各卡分担微批；统一打乱、KL 停止、梯度裁剪与更新边界。空分片和未使用参数有专门处理。 |
| `exam_search/draftrl/portable_gru.py` 与 `model.py` | NPU 上用普通张量算子实现同一层 GRU，保留参数和完整梯度；避免依赖 PackedSequence 设备内核。原输出及梯度经过对照。 |
| `exam_search/draftrl/runner.py`、`resource_modes.py` | 可从随机模型开始，支持兼容权重导入；新增大规模采样配置、小批运行边界与 NPU 状态报告。 |
| 检查点、恢复和持久化入口 | 保存 NPU RNG 与学习卡数，拒绝把不同卡数/源版本冒充同一断点；保留完整育成跨临时目录恢复。 |
| `scripts/`、`configs/`、打包器 | 环境检查、真实 Arena/搜索/Adam 预检、`configure.py` 生成两套可调整规模的配置，以及可独立解压使用的源码包。 |

`gakumas_training` 在工作区位于 `rl/training/gakumas_training`，在 ZIP 中位于 `training/gakumas_training`。脚本在工作区位于 `scripts/`，在 ZIP 中位于 `ascend/`。

## 最新学习逻辑和观测台

- 正负贡献使用冻结的动作前分位预测作为控制变量，保留实际单局回报；搜索行为继续探索，学习目标由证据调整原策略。
- 价值补训只覆盖 actor 未接受的本批记录，冻结 actor 参数和 Adam；多卡按全局批量归一化、求和梯度。单/双进程参数及 Adam 对比涵盖 KL 早停、奇数尾批和空分片。
- `dashboard/` 保留最新曲线与正负贡献展示，改为显式 `--run`、当前 Python 回放、冻结 Arena 路径校验和 localhost 服务。资源请求写入选中运行的 `resource-mode.json`，在完整批次边界生效。

## 并行边界

默认搜索配置使用 96 个采样进程和 24 个搜索进程；可分别填写任意正整数，没有应用层固定上限。搜索服务内部原有的 16 并发根 / 64 推理合批限制也已移除。完整育成的初始配置、热控制、迁移和 Notebook 同步开放进程数及批量；仍检查微批不超过全局批量。每个进程还可能创建 Node 子进程，需要根据主机内存和实际采样时间调整。

rank 0 负责采样期的网络推理。8 张 NPU 在更新阶段并行计算微批并求和梯度；采样数据会复制给每个学习进程。当前没有多机训练、采样期多卡推理或吞吐倍数承诺。

两套训练目标保持原契约：搜索任务保留四局考试目标，完整育成仍使用最终原始育成评价。包内提供源码、完整 checkpoint 和随机初始化入口；随包 checkpoint 通过 `--initial checkpoints/latest.pt` 继承模型和 Adam。

最终本地验证结果见 [ACCEPTANCE.md](ACCEPTANCE.md)，服务器安装和启动见 [README.md](README.md)。
