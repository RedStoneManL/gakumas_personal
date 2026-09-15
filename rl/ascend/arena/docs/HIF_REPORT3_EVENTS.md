# HIF 报告 3：事件、选项与支援事件核对

本页记录事件执行与抽象层的落地结果。研究来源是随用户提供的
[`hif_event_catalog.json`](research/imports/hif_events_rl_report3_2026-09-09/hif_event_catalog.json)
及[报告第 3—7、9、12 节](research/imports/hif_events_rl_report3_2026-09-09/hif_events_rl_report3_2026-09-09.md)。
研究主数据版本为 `571dbb62601e78998cddeacdbce3ea1bc672d7fc`。
本次逐字段比对的 92 条 HIF 外出／上课事件、72 个独立选项与本地主数据一致。
无需以额外实机校准作为运行这些固定规则的前置条件；考试继续采用项目已有 golden。

## 已完成的固定规则

| 机制 | 当前行为与核验 |
|---|---|
| 事件抽象 | 20 条外出按选项别名归成 3 组；72 条上课归成 27 组。30 组保留源事件 ID、选项顺序与池引用。外出固定数值骨架还可参数化为 1 个家族，仍保留 3 个阶段绑定。 |
| 选项成功率 | 72 个 HIF 选项均 `alwaysSuccessful=true`，优先于默认值 0，不额外抽成功／失败。其他真正有分支的事件按 `successProbabilityPermyriad / 10000` 解码。 |
| 上课属性 | 选拔前期 +120、后期 +150、本战 +180；均加到所选属性，普通课程成长率不乘这部分固定增量。 |
| 上课成本 | A/B 基础体力成本 5；Trouble 分支基础体力成本 0，先获得眠气，再执行后续换卡。P 点和体力成本均读取选项头部。 |
| 前期获得／后期换卡 | `ProduceRewardSet` 与 `ProduceCardChangeSelect` 分开识别。每个选项的契约暴露 `acquire` 或 `select_change`，不根据描述文本猜测。 |
| 目标合法性 | 上课换卡使用 `p_card_search-active_skill-mental_skill-deck_all`。眠气不在合法目标集合内；新获得眠气不会成为该分支随后换出的目标。 |
| 三种计划 | Sense：好调／集中；Logic：好印象／干劲；Anomaly：强气／全力。内部名 `exam_concentration` 在这里是 Anomaly 强气方向。 |
| 外出 | 三分支成本为 50 P 点／眠气 1 张／无额外成本；固定恢复 600‰ 最大体力；饮料、强化卡、普通卡是分开的领取操作。接受全部卡片时净增 2／3／1。 |
| 支援事件数据 | 报告的 511 条支援事件在本地均有对应装备、等级及顺序关系；这些事件自身没有基础三选一列表。 |
| 支援事件门槛 | 仅装备且达到等级的支援事件可用，同一支援按事件序号前进；未完成前序事件不能跳到后序。即使 `repeat=True` 也不能绕过装备、等级与顺序。 |
| 支援事件增量 | 支援事件属性、P 点、体力 bonus 仅用于 `support_event` 来源。外出、普通上课与慰问品固定结果不因此被放大。 |
| 自选和随机目标 | 自选删除、复制、强化通过策略选目标；随机类型仍由环境 RNG 取目标。`pickCountMin/Max` 决定必选与可跳过数量。 |
| 可追溯记录 | 显式事件执行结果记录事件／选项、头部成本、实际支援卡 ID／等级、成功概率、卡片操作与奖励池绑定。 |

支援技能概率与支援事件发生概率是两层不同机制：前者仍读 `ProduceSkill` 的 trigger、
档位、次数与 `activationRatePermil`；不能用其 300/450/600‰ 数值替代支援剧情事件的每日发生率。

## 本次发现并修复的实现冲突

1. 原事件抽象只保留 `ProduceRewardSet` 的池名，丢掉了 `ProduceCardChangeSelect` ID 中的目标池。
   后期多个计划因此被误合并，课堂只剩 15 个机制组。现在保留换卡池绑定，恢复为 27 组。
2. 显式 `events.execute()` 曾在选项主体之后才发头部的眠气，与日程动作执行顺序不一致。
   现在先付头部成本／获取眠气，再结算选项主体；因此 `GetProduceCard` 先于 `ChangeProduceCard`。
3. 原 `support_event_point_bonus`／`support_event_stamina_bonus` 加在普通事件集合，却漏掉了真实
   `support_event` 来源。现已按支援事件来源应用。
4. 原删除效果不论 `pickRangeType` 都随机选目标。现自选效果由策略选择，并保留随机效果的原语义。
5. 原 `repeat=True` 可以执行未装备支援事件。现只允许对满足来源与前序要求的事件重复执行。

其中卡组获得与换卡的生命周期必须继续保持分离：获取触发获取卡片效果；换卡触发换卡效果。
Select Change 的强化继承、定制不继承由运行时换卡路径处理，池抽样由奖励内核配置。

## 明确保留为环境假设的部分

- 三个外出池 `before_2nd`、`before_3rd`、本战池各自绑定。池中具体卡片、稀有度、普通奖励强化状态、
  抽样权重未知时保留 `null`，不把 `null` 写成 0，也不把不同阶段并成一个真实池。
- 事件目录的出现次数不是出现权重。支援事件的发生率、事件之间的竞争、准确日程映射由运行配置或
  显式事件脚本决定；不能声称 511 条目录就是一局中可必然发生的 511 次事件。
- HIF 慰问品基础奖励和装备额外奖励分开。粉丝票产生额外 P 点的概率按报告所引官方帮助为 0；
  这不禁止支援或 P 道具另外加 P 点。SR/SSR 饮料比例及卡池权重仍是可配置假设。
- `event_school_stamina_permil` 保存学校成本的累计增减量，默认 0。
  学校成本为 `基础成本 × max(0, 1 + 增减量 / 1000)`。
  `event_school_stamina_rounding` 支持 `continuous`（默认）、`floor`、`ceil`。
  默认保留 Arena 连续数值约定；该选择不是对实机小数取整规则的断言。
- 普通外出 600‰ 恢复的最终取整及额外回复修正次序，不由仅有的字段值推导为已知事实。

这些未知项不阻塞 RL 使用：固定机制按主数据执行，奖励与事件发生的假设随环境配置记录。
切换概率假设时应使用新的环境配置身份，不能与旧实验混作同一分布。

## Agent 与 RL 的读取入口

```python
from gakumas_rl.repository.master_data import MasterDataRepository
from gakumas_rl.simulation.produce.events import ProduceEventLibrary
from gakumas_rl.simulation.produce.event_templates import ProduceEventTemplates

repo = MasterDataRepository()
catalog = ProduceEventLibrary(repo).hif_fixed_event_catalog()
assert catalog['event_count'] == 92
assert catalog['option_count'] == 72
assert len(catalog['alias_groups']) == 30

# 每个 option 保留头部成本、操作种类、合法目标引用、奖励池引用。
option_contracts = catalog['options']
classes = ProduceEventTemplates(repo).hif_classes()
outings = ProduceEventTemplates(repo).hif_outings()
```

已初始化的培育 runtime 上可用：

```python
eligible = runtime.events.eligible_support_events()
if eligible:
    # 仅当环境的事件发生调度已选中这条事件时执行。
    result = runtime.events.execute(eligible[0])
```

`eligible_support_events()` 表示可达集合，不是发生率，也不会自动把所有事件执行一遍。
日程 RL 必须使用统一培育入口，由其在适当的日程边界调用事件调度。

## 验证

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest tests/test_hif_report3_events.py tests/test_produce_golden.py -q
```

本次结果：**38 passed**。其中报告 3 的 17 个测试覆盖数据对齐、30 组别名、学校矩阵、
Trouble 目标限制及触发顺序、两种执行入口的成本、支援来源／次序、选择删除／复制等边界。
未启动训练或游戏。
