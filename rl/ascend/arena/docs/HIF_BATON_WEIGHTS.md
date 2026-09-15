# HIF 应援棒：基础卡权重与 golden 接入

2026-09-10。六种应援棒已使用本地主数据 `ProduceCardRandomPool` 的实际权重，考试开始时补足山札到 22 张。抽样适配器使用 golden 的随机数流；卡片创建、随机位置插入、洗牌、抽牌与后续结算仍交给原生 golden。

| 应援棒 | golden ID | 基础卡 golden ID : 权重 |
|---|---:|---|
| 紫 | 427 | 642:1、644:2、664:1、666:1、670:1 |
| 緑 | 428 | 646:2、648:1、666:1、668:1、670:1 |
| 黄 | 429 | 650:2、672:2、674:1、676:1 |
| 赤 | 430 | 652:1、654:1、678:3、680:1 |
| 青 | 440 | 656:1、658:2、682:2、684:1 |
| 桃 | 441 | 660:1、662:2、686:2、688:1 |

每组总权重为 6。权重 1、2、3 分别表示每次独立生成的概率为 1/6、1/3、1/2。生成会重复抽取同一种卡，不是按比例固定发一套卡。已达到 22 张时不生成；以后回合不会再次补足。

## 全局 HIF 培育

`GoldenProduceBridge.entry` 从持有应援棒追踪到附魔、生成效果、搜索行，再读取 `ProduceCardRandomPool.all(pool_id)`。它保留原始主数据顺序，将普通/强化身份映射到 golden ID，并把权重放入考试 entry。

旧实现丢弃了权重；原生方法还会对 ID 去重，因此简单重复 ID 不能实现加权。这次增加独立的剧本抽样适配模块，通过原生 `getRand()` 选择加权区间，再调用原有 `addCardToDeck()` 在随机位置插入。每张生成卡消耗一次选卡随机数和一次插入位置随机数。所有 vendor 文件仍与锁定版本按字节一致；未提供权重时直接调用原来的均匀抽样方法。

配置入口位于 `entry.context.basic_card_pool` 与可选的 `entry.context.basic_card_weights`。二者顺序一一对应，权重允许为 0，但总和必须大于 0；加权池中的 ID 必须唯一。

## 单场自定义考试

```python
from gakumas_arena import TrainingExam, make_training_entry

entry = make_training_entry(
    cards=[],
    plan="sense",
    p_items=[428],
    basic_card_pool=[646, 648, 666, 668, 670],
    basic_card_weights=[2, 1, 1, 1, 1],
    turn_types=["vocal", "dance", "visual"],
)
exam = TrainingExam(entry, seed=42)
saved = exam.snapshot()
restored = TrainingExam.restore(saved)
assert restored.observe() == exam.observe()
```

不提供 `basic_card_weights` 时，保持旧 golden 的“去重后的 ID 均匀抽样”，旧 entry 与旧配置无需补字段。全局培育调用者显式覆盖 `basic_card_pool` 后，也不会误套原应援棒权重；需要加权时同时传入 `basic_card_weights`。`hif_round2_entry` 的旧默认配置保留均匀语义，调用者可以显式传上述真实权重。

同一场持有多个颜色应援棒不符合 HIF 编成，入口会明确报错，避免混合不同卡池。无论培育入口还是单场训练入口都执行此限制。

私有诊断 `exam.inspect_private()["debug"]["opening_audit"]` 会记录池、权重、生成卡身份、补齐数量与模式：`configured_weighted_basic_pool` 或 `golden_uniform_unique_ids`。它包含真实插入位置，只供调试，不能输入训练策略。

## 验证与文件

`python -m pytest tests/test_hif_baton_weights.py -q`：15 项测试，包括六组主数据映射、原生初始化、每组 120 张的独立整数票枚举 oracle、随机数消耗、快照恢复、显式覆盖、零权重与无权重兼容。

- [Python 配置入口](../gakumas_arena/engine/training.py)
- [配置验证](../gakumas_arena/engine/training_config.mjs)
- [原生配置与诊断桥](../gakumas_arena/engine/training_worker.mjs)
- [权重策略适配器](../gakumas_arena/engine/training_basic_pool.mjs)
- [原生卡片创建与插入](../gakumas_arena/_vendor/gakumas_tools/packages/gakumas-engine/engine/CardManager/index.js)
- [培育入口自动读取主数据](../gakumas_arena/produce/golden.py)
- [行为测试](../tests/test_hif_baton_weights.py)
- [原生整数票验证](../tests/test_hif_baton_native.mjs)

这是基于主数据的显式剧本抽样配置。适配器与实际效果文件哈希都会进入 `TrainingExam` 的版本校验；代码升级前创建的运行中快照必须使用原版本恢复，不能跨版本悄悄改变分布。
