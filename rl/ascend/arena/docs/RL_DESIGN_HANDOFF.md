# RL 设计选型交接

**2026-09-09 当前更新：**`create_training_exam` 已可接自定义 HIF 本战 2 / 单偶像 golden 考试纯策略训练，范围与实测见 [能力矩阵](ARENA_ROUND2_READINESS.md)，接入见 [Agent 入口](../AGENT_ENTRY.md) 和 [使用指南](ARENA_USAGE_GUIDE.md)。用户已指定 golden 为当前权威，实机校准不作为开训前提。公平条件采样尚未实现。旧 Gym/live 未整体迁移；下文为历史研究。

2026-09-08。交给独立 agent 研究和设计；本文记录用户目标、代码事实、已做测量及待选方案，**不是已经批准的模型/奖励方案，也不要求立刻训练**。

## 用户目标与职责

- Arena 要成为供程序操作、无 UI 的学園アイドルマスター完整游戏环境。卡牌、状态、体力、培育事件、课程、商店、试镜与剧本机制以 1:1 复刻为目标；新增内容应复用机制、通过数据配置创建。
- 最终在 Arena 中训练策略，并通过另一 session 的 adapter 在真实游戏中使用。培育的体力管理、卡组获取和删卡会影响后续考试，考试消耗也会影响后续培育，不能将二者当作互不相关的任务。
- 用户希望研究一个模型、两个模型或共享编码/分支模型的取舍，尤其是联合目标、长期信用分配、训练成本。
- 用户最新说明：本地资源不是硬约束，必要时可去 Colab 训练。不要为了适配 5080 过早限定架构；先测量，再给本地与云端方案。没有授权购买算力或启动付费训练。
- RL agent 负责模型、算法、目标/奖励、课程训练、基线和实验方案的选型。Arena agent 继续规则、状态推进、合法动作、内容配置、公共观测和兼容性。Adapter session 负责识别、映射、日志与游戏输入。
- 本文不派发其他会话、不操作游戏/Maa、不改变运行控制文件。若需要引擎接口，先列出字段、语义、验收样例，与 Arena 对齐后实现；不要在训练层复制一套游戏公式。

## 工作树与阅读入口

仓库：`C:/Users/Liu/Documents/ChatGPT/gakumas/third_party/gakumas_arena`。

当前分支 `codex/arena-live-bridge`，HEAD `ef2402958547b2050e873841b9ff5066a895b1a9`；**大量本轮成果仍未提交**，不能根据 HEAD 推断功能状态，也不能清理、reset、覆盖或切回 main。报告目录 `reports/arena-status` 是独立仓库。

先读：

1. [CONTENT_ARCHITECTURE.md](CONTENT_ARCHITECTURE.md)、[CONTENT_AUTHORING.md](CONTENT_AUTHORING.md)。
2. [ARENA_CATALOGUE_UPDATE.md](ARENA_CATALOGUE_UPDATE.md)、[REAL_CONTENT_CATALOGUE.md](REAL_CONTENT_CATALOGUE.md)。
3. [LIVE_EXAM_CONTRACT.md](LIVE_EXAM_CONTRACT.md)、[LIVE_PASSIVE_GENERIC.md](LIVE_PASSIVE_GENERIC.md)、[LIVE_CONTRACT.md](LIVE_CONTRACT.md)。
4. [rules/scoring_fidelity.md](rules/scoring_fidelity.md)。旧 PLAN/OPEN_ITEMS 下方的历史胜率、未实现列表不能作为当前结论。

目前卡牌/饮料/P 道具等 11 类共 4628 条定义已收录，独立考试准入 2370 条。上阶段完整测试 562 passed、3 skipped；合成探针无异常不等于所有触发都命中，更不等于全游戏 1:1 已认证。官方事件和路线尚未全部迁移为内容包，HIF 部分曲线、随机分布及触发边界仍需验证。

## 已确认的输入与接口问题

### 1. 卡牌数值信息缺失，不能仅靠换大模型解决

`gakumas_rl/simulation/envs.py::_card_feature` 的静态部分编码效果种类、触发相位、类别/稀有度/费用类型；14 个数值主要是费用、强化/成长数量、可用性、当前公共资源和候选槽位，**不完整表达效果数值、持续时间、条件阈值、顺序及嵌套机制**。

已做明确标记的合成比较：在其余属性和候选槽位相同的情况下，“好调 3 回合”和“好调 7 回合”的旧候选特征完全相同；引擎实际执行值不同。这是输入表达缺口，不是游戏结算把它们视为同一张卡。本轮 RL 讨论没有修改旧编码。

可复现命令：`.venv/Scripts/python.exe scripts/audit_rl_observation_gap.py`。它用两个只差持续时间的合成配置，比较同槽候选特征，再实际执行卡牌；[测量 JSON](examples/rl_observation_gap.json) 保存编码版本/形状和执行值。该探针配置不是下表的默认 HIF，不应把其维度当固定常量。

`simulation/exam/structural_encoding.py` 已提供被动的次数、回合、部分效果数值和结构指纹，但指纹不能代替完整语义；也不能据此认为候选卡已经有同等结构编码。需要统一表达有序效果、条件、搜索目标、链式效果、成长/自定义及当前实例状态，并明确未知值与容量溢出。

### 2. 默认测量规模（单个默认 HIF 配置，不是固定接口常量）

| 输入 | 测得形状 | 浮点元素数 |
|---|---|---:|
| 旧考试 | global 69；action_features 52×252；action_mask 52 | 13225 |
| 考试 observed/3 | 上述值与已知掩码；decision_kind 3；exam_context 2 与掩码；passive 32×77 与掩码；passive_effect 128×133 与掩码 | 65381 |
| 旧培育 | global 81；action_features 40×320；action_mask 40 | 12921 |

seed=0 的重置样例分别有 7 个考试、13 个培育合法动作；它们不是所有局面的动作上限。

observed/3 全按 float32 保存时每步 261524 字节，16384 步的观测约 3.99 GiB；还未包含下一状态、优势、梯度和激活等。轨迹可放在 CPU 内存中分批送到 GPU，不代表必须一次占据同等显存。可考虑 bool 掩码、紧凑结构、静态定义缓存；可训练 embedding 不能跨参数更新无条件复用过期缓存。

维度受数据词表、场景和容量影响，必须读取 manifest/hash，不能硬编码以上数字。多种编码共存，旧 checkpoint 不能静默使用新语义。

### 3. 现有网络/训练后端不等于已经统一

- `gakumas_rl/training/model.py::MaskedPolicyValueNet` 共享候选编码后逐项打分；读取 `global/action_features/action_mask`。目前不消费 observed 的已知掩码和新增被动结构。
- 该网络把候选末尾 41 维当稠密尾部，考试当前尾部是 14 维。需按接口 manifest 适配，不能认为同一入口天然适用所有阶段。
- `training/backends.py` 的 SB3 路径使用 `MultiInputPolicy`；它不自动等同于上面的自定义网络。BC 权重装载采用键/形状匹配和非严格加载，需要检查实际载入数量并对不兼容失败，不要默认 BC 已成功传递到 PPO。尚未测出实际加载比例。
- `gakumas_arena/env/__init__.py` 分别暴露考试和培育环境；`make_produce_env` 的考试默认由启发式策略自动完成，可提供 `exam_action_selectors`。
- `gakumas_arena/content/flow.py::ContentSession` 和 `content/exam.py::ContentExam` 能明确暂停并处理自创流程及考试选择，但整个新流程尚无完整 Gym/SB3 细粒度训练适配器。`ContentExam.encode()` 是特征 API，不是完整训练闭环。
- `ContentExam` 为明确选择与恢复，会复制动作前状态并确定性重放；训练吞吐尚未测量。若引入快路径，必须共享同一套规则，并验证状态、RNG、选择结果与可恢复路径一致。

## 设计课题（需要提出并比较方案）

### A. 决策架构

比较至少：单一阶段条件策略、独立培育/考试策略、共享编码器与阶段分支。讨论信息共享、梯度干扰、数据不平衡、跨剧本迁移、训练稳定性、部署与替换成本。

此前 Arena agent 提议“共享状态/卡牌编码 + 培育/考试策略分支 + 同一整局目标”，只是候选建议。两个策略分支不必对应两个奖励目标；两个独立模型也可以围绕共同回报协调训练。请用基线和消融决定，不能把前述建议当用户已拍板。

### B. 目标、奖励与长期信用分配

- 先区分最终试镜分、整局总评、路线通关率、回忆质量等不同目标；用户尚未确定首个主指标的精确定义和权重。
- 构筑/删卡/留体力的价值应与整体目标对齐。不要无条件奖励删卡、出牌或剩余体力，也不要默认每场考试局部分数的加总就是最终目标。
- 一次中间考试结束不意味着整局 episode 终止；之后的资源、卡组和未来价值需要衔接。明确失败、选拔完成、本战/下一阶段、正常结束、时间截断的区别，以及 terminal/truncated/bootstrap 语义。
- 完整培育包含大量中间选择。折扣不能仅因为某个操作多出一个内部/UI 选择页就无意改变相同游戏目标；讨论有限回合 gamma=1 或具有明确时间语义的折扣。
- 现有 `training/reward_config.py` 混合分段目标、局部通过、评价、体力、速度等权重，是历史实验配置，不是已确认的整局目标契约。规则保持 1:1，学习奖励留在训练 wrapper，不能为奖励改变游戏结算。
- 共同模型不能自动解决稀疏回报。比较 critic bootstrap、课程训练、辅助预测、模仿/搜索数据及必要的 shaping；如果采用势函数 shaping，交代折扣、终止势函数与适用条件。

### C. 信息边界与泛化

- 运行时能访问的隐藏牌序、未来事件抽样、RNG、对手隐含值，不应默认交给真实部署策略。训练观测要对应 adapter 实际可见信息；已知牌组多重集不等于已知牌序。
- 明确是否需要历史/记忆，以及训练、重置、实况恢复时怎样保持一致。使用 MaskablePPO 时注意官方实现不直接支持 recurrent policy。
- 候选按机制和属性共享表达，避免每张新卡都新增专用模型分支。讨论效果顺序、条件和交互怎样进入编码。
- 固定主数据/规则/观测版本；按新卡、新组合、种子、偶像和剧本留出验证集。防止只学 ID 或只利用模拟器偏差。

### D. 训练与评估

建议研究的课程：短考试能力 → 构筑与资源规划 → 完整培育联合训练；这不意味着最终永久冻结考试策略。

至少提供随机合法、现有启发式、预算明确的搜索基线；再确定 BC/RL 的收益。记录环境决策数/秒、训练更新吞吐、CPU/GPU 峰值内存、有效样本、成功率/得分分布与方差。不要从 GPU 型号直接给“几小时练好”的结论。

## 算力事实与边界

2026-09-08 本机只读检查：RTX 5080，nvidia-smi 显存总量 16303 MiB，驱动 595.97；Ryzen 7 9700X 8 核/16 线程；物理内存约 61.6 GiB（标称 64GB）。Arena `.venv` 尚未安装 torch、stable_baselines3、sb3_contrib；本次没有安装或启动训练。

100 万～500 万参数是此前提出的起步实验范围，不是硬上限，也不是实测最优规模。500 万参数的 FP32 参数/梯度/Adam 两份动量约 80MB，仅用于量级解释，不包含激活等实际峰值。性能可能先受 Python 模拟、复制/日志和长局样本效率限制。

Colab 可作为后续运行地点；具体配额、GPU、价格和可用时长应在实际使用时重新核对。方案需支持断点续训、完整 RNG/checkpoint、数据与规则 manifest、评估重现、路径可迁移，不能依赖个人机器绝对路径。未经明确授权不采购或启动付费作业。

## 希望 RL agent 交回的成果

1. 设计对比与推荐方案，列出假设、风险及哪些判断需要实验；保留可替换边界。
2. 首阶段任务/episode/目标与奖励规范，并给“删卡影响后续抽牌”“中间考试消耗影响后续培育”两个跨阶段信用分配例子。
3. 对 Arena 的接口需求：输入字段与可见性、动作/选择结构、终止语义、manifest、快照/RNG、批量运行；给最小 JSON/伪代码样例和验收条件。
4. 模型与算法配置、基线/消融、数据划分、训练停止与验收标准；列出共享/分支/独立方案公平比较所需预算。
5. 本地 5080 和 Colab 两条可复现运行路线，以及先行 benchmark 方案。此时无需追求最优通关率。

## 已查阅的主要资料（作为研究线索）

- [The Option-Critic Architecture](https://arxiv.org/abs/1609.05140)：联合学习层次策略与回报；不意味着本游戏必须采用该算法。
- [Policy invariance under reward transformations](https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf)：势函数奖励塑形与成立条件。
- [Set Transformer](https://proceedings.mlr.press/v97/lee19d.html)：集合元素共享表达与交互，可供卡组/候选表示比较。
- [MaskablePPO 官方文档](https://sb3-contrib.readthedocs.io/en/master/modules/ppo_mask.html)：动作掩码、Dict 输入和 recurrent 限制，选型时重新核对版本。
- [NVIDIA RTX 5080 规格](https://www.nvidia.com/en-gb/geforce/graphics-cards/50-series/rtx-5080/)；安装 PyTorch 时重新核对 Blackwell/CUDA/驱动组合，不沿用旧 GPU 的固定安装命令。

## 后续状态

交接基线：以上输入问题未因讨论而修复，模型/算法/奖励尚未定案。Arena 后续独立交付应在此处补链接；RL agent 开始前请核对新记录，避免双方重复改动公共编码。

2026-09-08 后续：Arena 新增 [自身移区效果](CARD_MOVEMENT_CONTRACT.md)，`Card.on_move` 可配置 hand/hold 和有序效果；原生 8 个版本新增执行路径。内容规则签名为 `arena-content-rules/2`，新模型应表达这些效果。旧张量编码未改变，数值信息缺口仍然存在。完整 Arena 工作顺序见 [ARENA_COMPLETION_ROADMAP.md](ARENA_COMPLETION_ROADMAP.md)。

本阶段完整回归 574 passed、3 skipped；最新目录准入 2378 条，完整记录见 [ARENA_MOVEMENT_UPDATE.md](ARENA_MOVEMENT_UPDATE.md)。
