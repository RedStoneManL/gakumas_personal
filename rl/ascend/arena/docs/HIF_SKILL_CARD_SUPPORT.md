# HIF 技能卡支援桥

已接入 `GoldenProduceBridge.entry()`，选拔、本战第一轮、本战第二轮等经该桥创建的考试都会读取实际支援卡编成与等级。没有支援卡或直接创建旧格式考试时，沿用原行为。

## 当前实现

- 每张支援卡独立读取 `SupportCard.produceCardUpgradePermil`、对应回合属性和手牌目标规则。
- 从四类 `SupportCardProduceSkillLevel*` 表取这张支援卡当前等级已解锁的每个技能的最高级，解析其 `SupportCardProduceCardUpgradeProbabilityUp`。同一个技能的中间等级不会累计；其他支援卡的增幅不会串到本卡。
- 支援生效时，一张合法手牌临时提高一级；强化后的总等级上限为 `+3`。抽牌与回合开始预约结算后执行；当回合结束效果结算完成后恢复永久等级。手牌、弃牌、除外、保留区都恢复，成长数值保留。
- 当临时强化中的原始未强化卡被原生 `upgradeHand` 等效果永久强化，永久 `+1` 会保留，临时等级相应提高并受 `+3` 上限限制。
- 卡实例保持原生 base/+1 身份，高阶等级保存在实例的 `temporary_support`；HIF 回忆的指定卡监听仍匹配原身份。
- `+2/+3` 采用主数据与 `+1` 的差值修正原生 AST，继续由原生解释器执行。覆盖 **422 张卡 × 2 = 844 个变体**、2,532 组 actions/effects/cost 字段；多段分数的每段、费用、嵌套预约、成长和条件阈值均经过编译审计。保留原有 golden 条件/时序语义。
- 临时增强的固有效果采用相同实例计数器，增强前后不会重新获得用尽次数；临时增强产生的实际成长保留。由出牌生成的预约效果继续使用出牌当时的程序。
- 不修改 vendor 文件；抽样使用原生 RNG，实例和持续效果采用 copy-on-write。快照保留完整支援配置和动作记录，恢复时复用该配置；`training_support.mjs` 已纳入引擎有效文件哈希。

## 概率与仍属模型假设的部分

默认概率公式为：

```text
每张支援卡概率 = min(1, 基础千分比 / 1000 × (1 + 本卡技能增加千分比 / 1000))
```

这是对主数据技能说明“このサポートカードのスキルカードサポート発生率を X% 増加”的相对增幅解释。例如 `s_card-1-0001` 的基础值为 19，Lv40 的技能增加量为 1000：默认概率为 `1.9% × 2 = 3.8%`。不能把后者解释成增加 100 个百分点，也不能将它写入奖励卡强化概率。

官方帮助确认“发生的回合临时提高一级、最多三级、条件/概率因支援卡而异”，但没有给出目标偏好、同回合多个来源的抽样顺序或与所有回合开始事件的精确先后。因此本版明确采用：

1. 按编成顺序逐张判定，每个符合属性的来源独立掷一次；成功后均匀选择一张尚未达到 `+3` 的合法手牌。
2. 不重复选择已达上限的卡；目标为空或概率为零时不消耗随机数。
3. 在原生回合开始抽牌、`afterStartOfTurn`、预约 `turn`、`everyTurn` 之后生效。

这些假设作为 `sampling_approximation` / `probability_basis` 进入配置和公开 observation，不能当成已还原实机隐藏抽样。精确概率可按来源覆盖；高阶主数据转换出错则在开局给出 `invalid_configuration`，不会默默保留部分 `+1` 效果。

## 使用

整培育模式只需正常配置六张支援卡及等级。可在 `exam_config` 返回值里显式覆盖特定来源概率：

```python
{
    "score_percents": [100, 100, 100],
    "turn_types": ["vocal", "dance"],
    "skill_card_support_settings": {
        "probability_overrides": {"s_card-1-0001": 0.038},
        "target_policy": "uniform",
    },
}
```

独立考试可以复用同一个编译接口：

```python
from gakumas_arena import make_training_entry, TrainingExam
from gakumas_arena.produce.support_bridge import build_skill_card_support

support = build_skill_card_support(runtime, bridge.definition_id)
entry = make_training_entry(
    [30], turn_types=["vocal", "dance"],
    skill_card_support=support,
)
exam = TrainingExam(entry, seed=123)
```

公开 `observation["cards"][i]["temporary_support"]` 包含 `permanent_id`、`level`、`sources`；`effective` 是包含当回合支援强化和原生自定义的实际执行 AST。临时效果过期后该字段消失。支援配置 schema 为 `arena-skill-card-support/1`。

## 验证与依据

`tests/test_skill_card_support.py` 的 13 项检查包含全目录执行字段审计、各等级和上限、回合属性、实算分数及费用、两段攻击、原生永久强化相互作用、真实姿态变更触发临时高阶成长并保留成长、整培育六支援入口、快照恢复，以及不匹配程序拒绝执行。

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest tests/test_skill_card_support.py -q
```

本地官方帮助留档：`../../../design/hif-mechanics-20260909/official-lesson-support.html`。结构化数据来自仓库当前 `SupportCard`、四类 `SupportCardProduceSkillLevel*`、`ProduceSkill`、`ProduceEffect`、`ProduceCard`、`ProduceExamEffect` 及其 enchant / growth 表。编译过程中不从截图推断卡面数值。
