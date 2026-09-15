# HIF 结局回忆产物与 RL 筛选

版本：`arena-hif-memory-products/1`、`arena-hif-memory-product/1`；生成规则 `hif-ending-memory-planning/1`。代码：[memory_generation.py](../gakumas_arena/produce/memory_generation.py)。

本模块补上结局之后的真实执行路径：生成初次产物、消耗配置的再生成票产生候选、筛选、选取一份、导出为下一次培育可用的回忆。效果身份来自本地主数据，考试中的 HIF 能力继续交由 golden。服务器抽选概率尚无权威表，默认分布是可配置的规划近似，导出明确标记 `official_probability_model=false`。

## 两阶段规则

| 终局 | 产物 | 关键规则 |
|---|---|---|
| 选拔成功 | 1 个 `hif_selection_handoff` | 使用现有完整 HifSelectionMemory 快照；保存卡实例、强化/自定义、能力与 P 道具触发状态等；不携带 P 点、饮料、当前体力 |
| 选拔失败 | 无 | `no_product_reason=selection_not_cleared` |
| 本战正常结束，包括失败 | 初次普通回忆 + 配置的再生成候选 | 从结束时持有的永久卡组抽选；最终只能取得一份 |
| 任一阶段主动放弃 | 无 | `no_product_reason=produce_abandoned`；不花再生成票 |

选拔阶段不使用普通回忆再生成票。活动限定选拔产物记录 `event_id/event_expires_at`，导入时可验证活动和到期时间；到期产物不可继续作为常规本战起点。游戏账户上的转换货币不由此模块修改。

官方当前生成帮助明确是“结束时仍持有”的卡组；已删除卡和考试临时生成卡不会因为曾出现过而成为本模块候选。旧资料中“本局曾获得过”的说法不能用作当前实现依据。

## 调用

```python
from gakumas_arena.produce.memory_generation import (
    generate_hif_memory_products, filter_memory_candidates,
    select_memory_candidate, memory_spec_from_product,
    selection_memory_from_product,
)

# runtime 必须已经写入 accepted final_summary。
batch = generate_hif_memory_products(runtime, seed=123, config={
    "tickets_available": 2,
    "regeneration_count": 2,
    "max_regenerations": 3,
})

# 一份初次产物 + 两份再生成；内容允许重复，candidate_id 各自唯一。
eligible = filter_memory_candidates(
    batch, card_ids=["p_card-01-act-1_001"], minimum_upgrade=1,
)
# 不满意时可以保存这次失败筛选结果；不要偷偷重新抽到满足目标。
if eligible:
    award = select_memory_candidate(batch, eligible[0]["candidate_id"],
                                    repository=runtime.repository)
    spec = memory_spec_from_product(runtime.repository, award["product"])
    # spec 可直接传给 build_idol_loadout(..., memories=(spec,))。

# 选拔产物使用另一条类型明确的导入路径：
# handoff = selection_memory_from_product(repository, product,
#                                         event_id="", now=unix_seconds)
# create_training_produce(..., selection_memory=handoff)
```

`select_memory_candidate` 返回所选产物、丢弃候选 ID、票据账本；同一 batch 的 receipt 是本地记录，外部账户库存由调用方原子写入一次，不能把所有候选都加入背包。`filter_memory_candidates` 是硬约束筛选，不定义“回忆质量分”。支持卡 ID、必需/排除能力 ID、最低强化、必需定制、产物种类。

生成器不改 runtime，不消耗培育/考试 RNG。相同终局、配置、种子得到相同候选；JSON 往返保留结果。产品 SHA-256 校验可发现误改；它不是防恶意伪造的签名。完整产物是权威记录：`ProduceMemorySpec` 当前只表达培育用携带卡与能力，竞赛卡实例的强化/定制仍在产品 `contest.cards` 中保存，不能只留 `exam_battle_produce_card_ids` 后声称竞赛状态无损。

## 数据与约束

- 普通能力取 `MemoryAbility` 中不限剧本且流派适用的条目，目前 74 条；HIF 专属能力取 `produce_group-003`，目前 105 条。每条保留 ID、等级、skill ID、效果 ID、稀有度、同效果不叠加标记和来源表。
- HIF 能力池不按 PLv、技能卡开关或结束卡组过滤；官方明确允许出现未解锁/关闭的目标卡能力。同一张回忆内抽样不重复同一能力，跨回忆同效果去重继续由既有 loadout/golden 桥执行。
- 携带卡保留原实例 ID、来源卡面、永久强化、全部源自定义和源增长信息；抽选后的强化/定制另外保存。自定义逐项经过主数据合法性校验。非自定义增长保留在来源证据中，不默默冒充可继承项。
- 回忆等级由现有最终评价值查 `ProduceGrade` 的 HIF 阈值；三维/最大体力作为竞赛参数保存，不作为下一局培育初始三维直接继承。
- HIF 可定制 P 道具不进入普通回忆；它们独立存在于 `runtime.customize_items`。普通 P 道具候选来自结束时持有道具。
- 生成角色是来源，不意味着只能给同角色使用；下一次携带卡流派与合法性仍经过 loadout 校验。

## 可配置近似

默认参数不等于实机概率，全部随产物导出：

| 配置 | 默认 | 作用 |
|---|---:|---|
| `regeneration_count/tickets_available` | 0/0 | 默认只生成初次一份；每次额外候选花一票 |
| `max_regenerations` | 3 | 规划用次数上限，官方仅明确存在上限 |
| `ordinary_ability_count/hif_ability_count` | 3/1 | 普通与 HIF 能力槽数 |
| `upgrade_retention_probability` | 0.5 | 源强化状态保留概率，否则基础版 |
| `customize_retention_probability` | 0.5 | 保留合法自定义子序列；未强化时不继承定制 |
| `initial_phase_probability` | 0.5 | 初始取得，否则中期考试后取得 |
| `contest_card_count/contest_item_count` | 6/1 | 竞赛部分抽样数量，最多取实际可用数 |
| `include_initial_cards` | true | 初始基础卡是否可成为携带卡 |
| `include_idol_cards/include_support_cards` | false/false | 固有/支援来源卡候选限制；主数据没有完整回忆抽选资格表 |
| `card_weights` | 每实例 1 | 按主数据卡 ID 覆盖权重，0 排除；同名不同实例分别保留 |
| `ability_weights` | 空 | 按主数据能力 ID 覆盖权重，0 排除 |
| `ordinary_rarity_weights` | R/SR/SSR/UR=4/3/2/1 | 普通能力默认相对权重 |
| `performance_bias` | 1 | 依据最终评价与对应三维调节普通能力权重；可置 0 关闭 |

官方确认强化/定制可能部分反映，但未提供抽选公式；当前只从结束实例自身的自定义抽子集，同名其他实例的跨副本定制匹配概率仍属于近似边界。全部可配置项必须记录到训练数据，不能混合不同模型后把分布当作实机统计。局外回忆合成、账户背包/货币结算由上层管理；此模块提供已选产品和费用收据。

## 验证与证据

`tests/test_hif_memory_generation.py` 20 项通过：确定性与 RNG 隔离、JSON 往返、最终卡组边界、源实例与合法强化/自定义、105 能力全部可抽、票数/上限/单份选取、失败/主动放弃/活动边界、坏配置与内容误改拒绝。另有实际链路：生成回忆 → 下局 loadout → HIF StartAudition → native golden 卡使用后再动。

权威帮助（当前页面由主数据 HelpContent 定位，2026-09-10 抓取）：

- [官方：メモリー生成](https://stat.game-gakuen-idolmaster.jp/html/help/57518177f6e31bea30b483caf16ea057793b78e9864a63d5131bb40b7e5a773c/index.html)，[本地副本](research/official-produce-generate-memory-20260910.html)：结束卡组、强化/定制抽选、再生成票与择一规则。
- [官方：メモリー](https://stat.game-gakuen-idolmaster.jp/html/help/5597f96b1017578d35bf8a7db9189c2c1fdb6c5449373c3027c20838ec7d87bb/index.html)，[本地副本](research/official-memory-memory-20260910.html)：成绩关联与培育/竞赛两种用途。
- [官方：コンテスト編成時の効果](https://stat.game-gakuen-idolmaster.jp/html/help/e93bd3c6581a3b5e277a166a3fa5d95c8a8d95a6ef166b4aa52b90bef758c6b4/index.html)，[本地副本](research/official-memory-memory-contest-20260910.html)。
- 既有 `design/hif-mechanics-20260909` 官方选拔回忆、HIF 能力、技能卡定制、可定制 P 道具帮助与 [Report3 对照](HIF_REPORT3_RL_READY.md)。
