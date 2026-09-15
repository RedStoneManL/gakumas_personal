# 给 RL 的事件机制抽象

更新：2026-09-09。

**HIF 外出的 20 条剧情记录可以合并成 1 个机制模板，保留 3 个阶段奖励池配置。** 原数据类型是 `ProduceEventType_Activity`，不是 NIA 的 Business。此前按 Business 检索得出的“本地没有 HIF 外出表”结论已更正。

本地主数据的选项和效果与 [HIF wiki 的「おでかけ」](https://seesaawiki.jp/gakumasu/d/H.I.F)相符：外出选项固定，不随剧情文本变化。运行时已将它接到 `outing`，并与 `activity_supply`（差し入れ）分开。

## 唯一的 HIF 外出机制

三项共同获得：回复最大体力的 60%、选择一瓶 P 饮料、选择一张通常技能卡。通常卡可以以强化状态出现。

| 选项下标 | 代价 | 额外收益 |
|---|---|---|
| 0 | 50 P 点 | 再选择一张保证强化的技能卡 |
| 1 | 向卡组加入一张「眠気」 | 再选择一张保证强化的技能卡 |
| 2 | 无额外代价 | 无额外卡 |

卡和饮料获得会继续触发支援技能/P 道具。加入「眠気」也保留为实际获得卡的事件。保证强化的奖励直接给予强化版本，不冒充一次“对已有卡进行强化”的动作。

| 阶段配置 | 主数据剧情行数 | 抽象处理 |
|---|---:|---|
| 选拔 `before_2nd` | 9 | 相同选项及效果，保留本阶段奖励池引用 |
| 选拔 `before_3rd` | 9 | 相同选项及效果，保留本阶段奖励池引用 |
| 本战 `produce_008` | 2 | 相同选项及效果，保留本阶段奖励池引用 |

这 3 个配置共享程序结构；不会把不同奖励池 ID 直接丢掉。20 份剧情不需要形成 20 个策略状态，也不能按 9:9:2 推断事件概率。候选卡/饮料的精确官方池成员与出现权重未全部解析；当前发放机制已执行，候选池抽样仍在 `sampling_scope` 中标为近似。

## 可复用的去重接口

```python
from gakumas_arena.produce import ProduceEventTemplates
from gakumas_rl.repository.master_data import MasterDataRepository

templates = ProduceEventTemplates(MasterDataRepository())
hif = templates.hif_outings()
assert len(hif['mechanism_families']) == 1
assert len(hif['stage_variants']) == 3

# 给策略使用的效果/选项程序，不包含故事标题、角色立绘、台词。
program = hif['mechanism_families'][0]['program']
```

全局 `run.observe()['actions']` 中的事件行动现在有 `event_template_id` 和 `event_family_id`。前者区分实际奖励池；后者供 HIF 共用机制编码。仍提交原 observation 的完整 action，内部选择回调按该源事件的 options 下标返回。

`templates.program(event_id)` 解析具体源事件；`template_id(event_id)` 返回稳定 SHA256 标识。`groups()` 对全库进行保守去重，保留原选项顺序、数值、成本、卡与强化、效果顺序、成功概率、失败分支、事件型后续步骤及奖励池引用。所有权、解锁等级、事件顺序、故事来源作为 `members` 上的上下文保留，不当作相同效果即可随意互换的许可。

本次全库归类结果：

| 范围 | 原始行 | 效果/选项模板 |
|---|---:|---:|
| 全部事件 | 6,888 | 2,170 |
| Activity（包含多个剧本） | 529 | 42 |
| 支援卡事件 | 511 | 206 |
| HIF 外出 | 20 | 3 个具体配置 / 1 个机制 |

以上是主数据事件效果层的等价分类，不表示所有周程钩子或官方发生概率都已经解析。非 HIF 剧本也没有被自动加入 HIF。

## 交付给 RL

- [HIF 外出小包](../data/catalogue/hif_outing_templates.json)：1 个机制、3 个配置、20 个来源映射。
- [全库抽象目录](../data/catalogue/produce_event_templates.json)：2,170 个模板及其源事件/支援条件关联。
- [原始结构化事件目录](../data/catalogue/produce_events.json)：保留完整主数据引用，便于审计。

执行 `python scripts/export_produce_events.py` 一次重建三份文件。效果顺序与选择语义变化会改变模板 hash；仅剧情名称变化不应创建新机制。
