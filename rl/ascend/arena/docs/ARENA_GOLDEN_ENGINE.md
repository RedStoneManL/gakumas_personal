# Arena 当前局内引擎：gakumas-tools golden

**2026-09-10 最新来源规则：**明确的事实字段以 `gakumasu-diff` 主数据为准，冲突时修正有效数据／适配，不再为对齐上游结果保留错误值。`gakumas-tools` 是执行核心与算法参考；“golden”不表示其目录高于主数据。详见[事实数据与冲突处理](DATA_AUTHORITY.md)。下文保留原始接入的历史说明。

实际训练先读 [使用指南](ARENA_USAGE_GUIDE.md) 或 [AGENT_ENTRY](../AGENT_ENTRY.md)。`TrainingExam` 已支持可自定义的单偶像 golden 考试，包括 HIF 本战 2；实机校准不作为开训前提，范围见 [Round2 矩阵](ARENA_ROUND2_READINESS.md)。下文介绍原始接入；其中旧 `ArenaExam.observe()` 仍为私有调试接口。

**2026-09-10 用户证据修正：**TrainingExam／全局培育保留原生结算核心，并采用 `live-game-corrections/20260910-1` 的两条卡目录补丁：ハイタッチ+ 的元气追加 +9、元気な挨拶+ 定制后固定体力费用 2。配套 JSON 引用错误由本地有效目录修正，上游原始文件和 `ArenaExam/run_exam` 对照接口保留。来源、hash 和用户截图见[实机确认记录](GOLDEN_DIFFERENCES_TO_VERIFY.md)。因此当前训练版应标识为“固定上游基线＋已确认数据修正”，不能描述成上游原样输出。

2026-09-09，按用户决定，将 **gakumas-tools 的效果定义与执行结果作为当前 Arena 局内规则 golden**。本次直接纳入原始引擎，并通过 Python 调用；不另写一套卡牌解释器再逐条翻译。

固定版本：`6c3d00648c32ea72a05086a18c63ab62e0d0c7e5`（核对时远端 master 同此提交）。
规则标识：`arena-gakumas-tools/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/1`。

## 已落地

- 源码及数据位于 [`gakumas_arena/_vendor/gakumas_tools`](../gakumas_arena/_vendor/gakumas_tools)。74 个上游文件按字节保留；[PROVENANCE](../gakumas_arena/_vendor/gakumas_tools/PROVENANCE.json) 锁定每个文件的 SHA-256，保留 BSD-3-Clause 许可。
- 新的默认入口 [`gakumas_arena.create_exam`](../gakumas_arena/__init__.py) / [`ArenaExam`](../gakumas_arena/engine/__init__.py) 直接运行这份 golden。支持合法出牌、结束回合、结构化观察、效果日志、嵌套选牌、序列化恢复。
- [`gakumas_arena.engine.run_exam`](../gakumas_arena/engine/__init__.py) 使用上游原始 HeuristicStrategy + StagePlayer，可直接输入其模拟器 URL query。
- [`find_effects`](../gakumas_arena/engine/__init__.py) 按名称查询卡牌、道具、饮料、改造，返回上游解析后的效果 AST。
- 饮料库存/使用入口由 Arena 包装；饮料效果直接执行上游 `PDrinks.actions`，不增加卡牌使用次数。库存扣除与暂停选牌一起提交。

**迁移边界必须保持明确：**已有 `gakumas_arena.env.make_exam_env`、`gakumas_arena.sim.run_exam`、ContentExam、旧 `make_produce_env/run_produce` 仍是 `gakumas_rl` 兼容路径；它们的通过结果不能标成新 golden。新增 `gakumas_arena.produce.create_training_produce` 则把 HIF 培育考试显式交给 `TrainingExam`，见 [培育指南](PRODUCE_USAGE_GUIDE.md)。现有 live submitted/uncertain、命令去重、恢复协议没有被替换。

## 运行

需要 Python 3.11+、Node.js 20+。不需要安装网站、Next.js、ONNX、OCR 或 pnpm 依赖。

```powershell
python -m gakumas_arena.engine --config docs/examples/golden_exam.json --output result.json
```

[示例编成](examples/golden_exam.json) 对应上游 `seed1-001`，默认种子 `610397104`，输出 **13257**；[实际结果及日志](examples/golden_exam_result.json)。这是上游测试编成，不是用户的 508647 分 HIF 局。

```python
import json
from gakumas_arena import create_exam, ArenaExam
from gakumas_arena.engine import find_effects, loadout_from_query, run_exam

config = json.load(open("docs/examples/golden_exam.json", encoding="utf-8"))
exam = create_exam(config, seed=17)
obs = exam.observe()
while not obs["terminated"]:
    if obs["choice"]:
        # 示例策略：选择满足最小数量的前几个候选；这里填候选 index。
        obs = exam.choose(list(range(obs["choice"]["min"])))
    else:
        obs = exam.act(obs["actions"][0])

restored = ArenaExam.restore(json.loads(json.dumps(exam.snapshot())))
assert restored.observe() == exam.observe()
effects = find_effects("夏夜に咲く思い出")
```

查询效果不需要识别图片：

```powershell
python -m gakumas_arena.engine --find "夏夜に咲く思い出" --output summer-effects.json
```

`loadout_from_query` 接收 URL 的 query 部分；`run_exam` 是本模块的 golden rollout，不是旧 `gakumas_arena.sim.run_exam`。

## 配置与恢复

- 使用上游数字 ID，不能直接传 `p_card-...` 等 master ID。卡牌升级和改造同样按上游数据配置；现有原生 ID 需通过有版本的映射再迁移。
- `stage_id` 选择已有舞台；或提供 `stage` 的类型、三属性回合数、首回合权重、审查权重与效果 DSL。
- `enter_percents: true` 时，`loadout.params` 的前三项直接是百分比。例如用户 HIF 图中是 `[3879,3335,2430]`；第四项为最大体力，截图未给出，不能猜填后声称整局复现。
- 步进模式可传 `turn_types` 完整属性顺序、`starting_stamina` 当前体力及 `drinks` 饮料列表。这是显式初始条件，不是内置 HIF 培育逻辑。
- 观察是 **离线完整状态**，含牌库信息，不可直接当作实机可观测信息或 RL 输入。现有观察编码/脱敏契约仍需专门接线。
- 每次 Python 请求使用一个独立 Node 进程，按种子、操作序列和已选答案重放。上游 RNG 是模块级变量；这一做法避免多局相互污染，也不需要修改它的 RNG 机制。
- 一个操作遇到第二、第三个选择时，保留整个答案序列重放，避免上游一次性选择变量被消耗后重复询问第一项。只有完整成功才把操作加入已提交历史；无效操作或答案不改变已有快照。
- 当前恢复优先可复现，单步会重放历史；高吞吐训练可在后续做常驻 worker/实例 RNG 优化，再用同一 golden 验收。
- 适配器暂不开放需要多偶像配置的 linkContest；原始引擎代码仍完整保留。HIF 培育不依赖这一模式。

## 结构化效果来源

[`data/reference/gakumas_tools_effects.json`](../data/reference/gakumas_tools_effects.json) 同时包含原始 DSL、严格解析得到的 `engine_ast`、元数据与版本指纹。

| 表 | 记录数 | 说明 |
|---|---:|---|
| skill_cards | 870 | 869 有效果正文/监听；1 条只有费用/条件。基础与 + 分开计数 |
| p_items | 484 | 374 有可执行规则；110 无效果定义，其中 104 为培育道具、6 为 NIA 舞台道具 |
| p_drinks | 28 | 全部有 `actions` |
| customizations | 111 | 105 正文补丁、4 费用/条件补丁、2 通过 limit/forceInitialHand 元数据实现 |
| stages | 180 | 153 contest、24 event、3 linkContest |

另有 154 条 P 偶像、14 条角色数据，随 vendored 包保留。数字是该版本的记录数，不是“与实机一致率”。

`no_effect_definition` 表示这个源没有给出执行定义，不代表游戏内没有效果。培育道具如「ふわふわでもこもこ」「つやつやでふさふさ」的图鉴条目确实没有 effects；其机制可以从现有 master 的 ProduceItem → ProduceTrigger / ProduceItemEffect / ProduceEffect 继续取得。「花もじゃ（黄）」在 master 的 ProduceCustomizeItem 中，包含咨询触发、随机饮料奖励和累计考试附魔的结构化引用。

严格重导出命令：

```powershell
node --loader ./gakumas_arena/_vendor/gakumas_tools/scripts/extensionless-loader.mjs scripts/audit_gakumas_tools_reuse.mjs
```

## Golden 政策

1. 当上游有实现时，以锁定版本源码和输出作为当前预期。不能用新引擎输出覆盖预期后称为对齐。
2. 截图与上游差异单独保留，不阻塞使用这份 golden；只有明确决定升级/修正时才变更来源版本与规则标识。
3. 上游没有的培育机制、HIF 特殊配置和接入协议，明确作为 Arena 扩展。不能把“有图鉴条目”当作“已实现”。
4. 新后端使用上游自己的 phase/group/注册顺序，不叠加旧 Python 后端的 `stable_id_lexicographic/1` 排序策略。旧策略只描述兼容路径。

## 验收

- vendored 原始回归：**524/524 一致**，未修改 suite 的分数。
- 严格 DSL 校验：0 错误。
- Python 接口测试：5 项通过，含源码哈希、跨计划 golden 编成、连续选择恢复、非法操作原子性、饮料/卡次数区分、独立实例重放和终局。
- 旧 live recovery / exam choices / content：32 项通过。
- wheel 包含源码、数据、loader 和许可；解包到隔离目录后，用包内引擎运行示例仍为13257，已验证不依赖旁边的参考 checkout。
- 上游体力与 OCR 数值恢复单元：39 项通过；OCR 模型本身未执行，也未接入游戏。
- 上游覆盖脚本仍报告 139 个未纳入样例的可达实体，退出 1；不影响现有 524 个 golden 的一致性，不能将它当作全卡效果已覆盖。

规则差异及完整复用调查见 [调研报告](research/gakumas_tools_reuse_review_2026-09-09.md)，HIF 图证见 [截图整理](research/produce_score_photo_review_2026-09-08.md)。
