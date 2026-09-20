# V6 搜索与四局信用分配改进

本版基于 `f5e64df` 的关系编码 V6，分支 `codex/v6-search-credit`。网络结构、参数名称和形状不变；可以加载已有 V6 权重及 Adam 状态。训练数据合同改变，首次切换使用新目录和 `--initial`，不要对旧运行使用 `--resume` 或 `--continue-from`。同版本同配置的新运行内部仍可正常 resume。

## 本版执行方式

同一个构筑的四局真实考试全部由冻结策略执行。温度与 epsilon 混合后的真实行为概率仍用于 PPO，真实终局分数仍用于 critic，四局最高分仍用于构筑。没有改为四局平均分。

原有重复牌惩罚继续仅作用于 draft：严格的选卡回报为“四局最高归一化分 − 重复牌惩罚”，不改变考试终分或其他阶段的目标。本版不改变卡池及同名卡限制。

在选中的真实决策边界，搜索从公开历史采样假想世界并续跑，结果写入 `search_aux`。搜索不替换真实动作、行为概率或终局分数。完成同行四局以后，根据另外三局最高分 `M_peer` 计算每个候选动作的辅助价值：

`Q_aux(a) = mean(max(search_terminal_score - M_peer, 0))`

通过相对原策略的边际收益构造辅助策略分布，单独计算交叉熵。每条真实记录只训练一次 critic，不把搜索模拟当成新的真实局或真实 decision。同行成绩仅是训练标签，不能进入策略观察。

这是搜索辅助学习。搜索续局包含树内探索和温度采样，不等同于真实行为策略，辅助标签不能解释成无偏 PPO advantage 或最优价值证明。

## 搜索层修复和证据边界

- 初始覆盖按 `root_attempts` 分配尝试；有效终局不足的动作之间公平轮转。无法在预算内终局的动作不能阻止其他动作获得首次尝试。
- 有效 `root_visits` 和终局样本门槛仍独立计算。未完成模拟不补 0 分，不生成伪标签。
- 报告每动作的尝试量、成功终局量、根粒子槽覆盖和不同公开续局路径。粒子槽只是内部证据身份，不是神经网络特征；更多遍历不等于更多独立环境样本。
- 终局样本均值保持原后验采样频率。分组只用于不确定性及证据门槛，不把不等后验权重强行改成粒子等权。
- 辅助目标采用按粒子分组的误差启发式、至少三个有效粒子组、噪声缓冲和有限 logit 改变量。缺失/重复粒子元数据或不足证据的根会被拒绝或不给更新权重。详细拒绝原因写入诊断。
- 新配置的 `rollout_temperature=1.0` 让树外续局按模型概率采样，避免总是只尝试一个贪心后续。旧配置默认 0，保持原来的贪心模式。
- 尚未加入另一批独立续局来验证每个标签。分组误差不是置信区间，也未消除自适应搜索选优偏差；报告明确标记没有独立 held-out 验证。

## 配置

完整配置：`ascend/configs/prod/search-v6-credit.json`。

短批次配置：`ascend/configs/search_v6_credit_smoke.json`。

生产配置仍为每个根最多 96 次模拟、8 个根粒子，最多搜索 4 个真实决策边界；初始每动作有效访问目标改为 4，原有总预算不扩大。若合法动作数乘初始访问目标已超过总预算，直接记录预算不足，真实策略照常执行。追加三局可以不运行旁路搜索，因为是否生成辅助标签不会改变真实行为。

新模式显式设置 `search.execution_mode="auxiliary"` 和 `search.auxiliary_credit.schema="arena-peer-marginal-search/1"`。旧配置不设置 execution_mode 时继续采用 `act` 搜索接管方式，用于历史对照，不将其混合轨迹声明为纯策略轨迹。

## 从现有服务器权重开始

在新源码及部署目录操作。使用服务器上已经完整写出的最新 V6 checkpoint；仓库附带 checkpoint 是历史快照，不能代表服务器当前训练进展。

```bash
git clone --branch codex/v6-search-credit https://github.com/RedStoneManL/gakumas_personal.git gakumas-v6-credit-src
cd gakumas-v6-credit-src
python rl/hif-colab/build_training_bundle.py --target ascend
python -m zipfile -e rl/training/artifacts/ascend/gakumas-ascend-training.zip ../gakumas-v6-credit-deploy
cd ../gakumas-v6-credit-deploy

INITIAL=/absolute/path/to/completed-v6-checkpoint.pt
python exam-search/prepare_relational.py
python ascend/run_tests.py
python ascend/preflight_search.py --device npu --relational --auxiliary \
  --initial "$INITIAL" --output ../evidence/v6-credit-1npu.json
```

预检后按原环境进行多卡预检；原驱动、CANN、torch_npu、通信和设备适配保持不变：

```bash
torchrun --standalone --nnodes=1 --nproc-per-node=8 ascend/preflight_search.py \
  --device npu --relational --auxiliary --initial "$INITIAL" \
  --output ../evidence/v6-credit-8npu.json

python exam-search/train.py --config ascend/configs/search_v6_credit_smoke.json \
  --initial "$INITIAL" --output ../runs/v6-credit-smoke

torchrun --standalone --nnodes=1 --nproc-per-node=8 exam-search/train.py \
  --config ascend/configs/prod/search-v6-credit.json \
  --initial "$INITIAL" --output ../runs/v6-credit
```

短批次配置的设备和并行度应与实际执行命令一致；它是单 learner NPU 配置。完整配置继承原生产版的 8 learner 设置，不在同一设备上额外启动两个满负载作业。

`--initial`、`--resume`、`--continue-from` 互斥，误传组合会在读取配置或初始化设备前报错，避免忽略指定权重。首次跨合同切换只用 `--initial`。

## 看哪些指标

1. `ppo_records` 应覆盖所有真实有效训练记录；`search_records` 在 auxiliary 模式为 0，辅助标签单列为 `auxiliary_search_records`，不能计入真实采样局数。
2. 检查每动作 attempted coverage、有效 terminal coverage、粒子覆盖和拒绝原因。只有尝试次数增长不等于学习证据改善。
3. 检查 auxiliary weighted roots 和 estimated gain；零权重是证据不足/无优势的正常结果，不能靠降低门槛把它包装成进展。
4. 固定测试继续四局最高分，同时保留各局分数、均值、通过率和场景分项。评价纯策略进步时关闭搜索接管。
5. 对照相同时间或引擎动作预算下的旧版与新版。实际学习效果、Ascend 吞吐和长期稳定性需要服务器验证，本地合成/短局测试不能证明分数提升。

本地验收记录见 `V6_SEARCH_CREDIT_ACCEPTANCE.md`。
