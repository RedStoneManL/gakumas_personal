# Arena 训练使用指南

2026-09-09。当前入口是公共 TrainingExam；HIF 本战 2 是可编辑模板，机制与成绩以 pinned gktools 为 golden，实机校准不作为开训前提。[验收矩阵](ARENA_ROUND2_READINESS.md) 给出证据与接口范围。

## 环境与自检

需要 Python3.11+、Node20+。已有工作区环境直接运行：

```powershell
Set-Location C:/Users/Liu/Documents/ChatGPT/gakumas/third_party/gakumas_arena
.venv/Scripts/python.exe scripts/validate_training_ready.py --full
```

新环境安装 `python -m pip install -e ".[dev]"`。无需游戏/Maa/npm/GPU。--output 指定证据目录；不带 --full 只跳过 pytest 和上游524条对拍，仍执行完整轨迹、变体、多进程与探针。脚本不训练模型。

Node默认PATH，可在创建/恢复时传 node="/absolute/path/to/node"。本轮实际运行平台为 Windows；Colab/Linux路径按包定位，但尚未跑过平台验收。

## 自定义 HIF 本战 2

同一个入场包可用 `gakumas_arena.preview.write_deck_preview(entry, "outputs/deck.html")` 渲染成图标卡组，便于人类检查。图片默认从本地缓存读取并内嵌，生成的 HTML 可离线打开。完整接口和 CLI 见 [卡组预览](DECK_PREVIEW.md)。

```python
from gakumas_arena import hif_round2_entry, create_training_exam

entry = hif_round2_entry(
    score_percents=[3000, 2400, 1800],
    max_stamina=44,
    stamina=32,
    drinks=[22, 14, 18],
    p_items=[428, 442],
    turn_types=[
        "vocal", "dance", "visual", "vocal",
        "dance", "visual", "vocal", "dance",
        "vocal", "visual", "dance", "vocal",
    ],
)
exam = create_training_exam(entry, seed=7)
```

cards= 可传完整牌表：列表元素为具体定义ID或完整副本字典。未传 cards 时使用默认广的牌组；所有默认配置均可覆盖。改另一偶像时，按需要一并替换 cards、idol_id、p_items 和 basic_card_pool；工厂不会替你猜装备。

通用课程使用 make_training_entry。以下是可独立运行的一回合环境，不依赖默认 HIF 道具或牌表：

```python
from gakumas_arena import make_training_entry, create_training_exam

entry = make_training_entry(
    cards=[647, 668, 648],
    plan="sense",
    score_percents=[250, 100, 100],
    max_stamina=40,
    turn_types=["vocal"],
)
exam = create_training_exam(entry, seed=0)
```

每局重新采样 entry 的配置，再 create_training_exam(entry, seed=...)，即可自定义课程。RL决定采样分布，Arena验证并执行。旧 default_training_entry 是 v1 回归fixture；新无参数 create_training_exam() 已返回 v2模板环境。

## 倍率和回合

| 配置 | 含义 |
|---|---|
| score_percents=[Vo,Da,Vi] | golden 的最终百分比输入。2030表示2030%=20.30倍，不是2030点属性 |
| hif_scoring={family,stage,stats,star,...} | 用户研究包近似换算，生成最终 percent；详见 HIF_SCORING_MODEL.md |
| scoring.mode="percent" | 等价显式配置；values为百分比，support_bonus必须0，避免重复加成 |
| scoring.mode="golden_contest_params" | values为三维，按原引擎contest属性公式、season、criteria和support_bonus计算 |
| context.turn_types | 完整公开属性序列；显式指定时严格执行，不额外追加回合 |
| context.stage.turnCounts | 各属性回合数；工厂根据显式turn_types推导，双方都传则要求一致 |
| stage.firstTurns / criteria | 原生随机回合生成概率 / 审查比例，各自合计1 |
| stage.effects | 原生DSL的舞台效果，须声明顶层触发阶段 |
| basic_card_pool | 原生基础卡定义ID池，交给原应援棒处理器抽取 |

原生计分模式有 percent 与 golden_contest_params；工厂的 `score_percents`、`scoring`、`hif_scoring` 三个参数只选一个。例如：

```python
entry = make_training_entry(
    cards=[647, 668],
    scoring={
        "mode": "golden_contest_params",
        "values": [1800, 1500, 1200],
        "support_bonus": 0.1,
    },
    stage={
        "type": "contest",
        "season": 51,
        "criteria": {"vocal": 0.45, "dance": 0.30, "visual": 0.25},
    },
)
```

HIF 模板最终采用原生 percent 接口。**2026-09-10 已按用户要求接入研究包的原始三维＋スター性近似换算**，可用 `hif_scoring` 自动生成百分比并保存模型来源，见 [换算指南](HIF_SCORING_MODEL.md)。`golden_contest_params` 仍只是普通竞赛公式。未识别分支通过显式实验配置使用，不把实机校准作为采用当前近似模型的前置条件。

模板默认12回合、Vo/Da/Vi=5/4/3、首Vo、criteria=.45/.30/.25；不传 turn_types 时由 golden 和 seed 生成。原随机生成器保留三种属性的最后回合以及首回合，需要相应最低计数；更短、单属性等课程直接传显式 turn_types。支持1..300回合，stage.type为contest/event；多偶像linkContest未接入。

## 入场包与副本

完整可导入JSON见 [entry](examples/training_ready/entry.json)。schema_version为arena-exam-entry/2，边界为before_opening。

| 字段 | 语义 |
|---|---|
| preset / source | 自定义环境名称与来源标签；source.kind支持custom_environment、constrained_curriculum、recorded_entry |
| cards | 0..512个入场副本；不是固定22张。运行中最多4096个实例 |
| instance_id | 唯一、稳定字符串；不得使用generated:前缀，保留给局内新增实例 |
| definition_id | gktools具体版本ID，强化版本是独立定义 |
| customizations | 定制ID→层数，按该牌允许项与最大层数校验，如{"59":1} |
| growth | 原生g.*字段→数值，如{"g.concentration":3}；技术范围[-10000,10000] |
| bindings | 精确绑定此副本的能力声明列表 |
| resources | max_stamina=1..100000，stamina=0..max；最多64槽原生饮料，可重复 |
| p_items | 最多256个不同原生ID，按输入顺序安装；不限制为广的两件道具 |
| memory_abilities / persistent_effects | 各最多256条全局原生效果声明，可带计数、预约和剩余次数 |
| context | plan、idol_id、scoring、stage、turn_types、basic_card_pool、boundary |

plan支持sense/logic/anomaly。idol_id可为null；给定偶像但不传plan时工厂查目录推导。完整JSON中二者矛盾会报错。卡牌/道具组合可自由实验，仍验证原生ID、唯一卡重复和定制资格；这不替代自然培育可达性判断。

初始化保留输入副本，不追加contest默认牌组、不去重普通同名卡。只有配置的实际应援棒按其原生开局阶段、牌数和门槛补牌，使用指定基础池；后续移除/抽牌不持续补到22。使用应援棒必须给非空池。池采样遵循golden，不另实现权重算法。

export_entry()导出原始补牌前配置，不是当前牌表。运行中状态用snapshot恢复，不拿当前牌表重新开局。

## 回忆绑定、持续效果与预约

effect_declaration只包装声明；DSL解析、条件、计数、费用和触发仍由原引擎执行。使用原生字段与操作名，未知阶段/动作会报路径错误。

```python
from gakumas_arena import effect_declaration, make_training_entry, create_training_exam

entry = make_training_entry(
    [647, 647],
    turn_types=["vocal", "vocal"],
    stage_effects="at:afterStartOfTurn { cardUsesRemaining+=2 }",
    memory_abilities=[
        effect_declaration("opening-buff",
                           "at:startOfStage { goodConditionTurns+=3; limit:1 }"),
    ],
    persistent_effects=[
        effect_declaration("remaining-trigger",
                           "at:endOfTurn { concentration+=2; limit:2 }"),
    ],
)
entry["cards"][0]["bindings"] = [
    effect_declaration("copy-a-memory",
                       "at:afterCardUsed { concentration+=7; limit:1 }"),
]
exam = create_training_exam(entry)
```

此绑定只响应第一张副本的完整用卡，第二张同名牌不会替它触发。绑定的顶层用卡阶段自动加usedCard==该副本条件；beforeCardUsed、cardUsed、activeCardUsed、mentalCardUsed及对应after阶段均支持。其他阶段按原始全局时点触发，仍保留绑定来源。不要用at:afterCardUsed[this]代替绑定，原phase filter不接收绑定来源；如需限制副本直接放在bindings。

安装顺序：原生舞台→输入P道具→牌自带效果→逐副本bindings→memory_abilities→persistent_effects，然后原生开局。绑定只属于指定实例，局内复制新卡不会自动复制外部绑定。修改实例顺序时携带该实例的全部字段，不能单独换定义ID。

声明格式为{"id":str,"effects":DSL,"counters":{}}。各声明有独立effectInstanceId；counters如{"main":2}代表原生effectCounter已计2次，命名counter采用相应键。limit写剩余触发次数，delay/ttl/turn等使用原DSL语义。跨场已知buff可通过显式开局效果带入，已预约效果通过persistent_effects声明；Arena暂不自动从旧培育对象推导跨场重置/保留表。

原生DSL例子、现有卡/道具AST在training_catalog()及vendor内。任意新自造操作不属于golden，不能期待引擎自行推断。调用方应描述规则事实，不塞入模型奖励。

## 公共观察与训练循环

```python
while True:
    obs = exam.observe()
    result = obs["result"]
    if result["terminated"] or result["truncated"]:
        break
    if obs["choice"] is not None:
        selected = list(range(obs["choice"]["min"]))  # 换成策略
        exam.choose(selected, decision_version=obs["decision_version"])
    else:
        exam.act(obs["actions"][0])  # 换成策略
final_raw_score = result["final_score"]
```

返回dict是深拷贝。无需决策的效果自动推进到下一选择/正常决策/终局；不会替策略完成真实补选。

| 公共字段 | 内容 |
|---|---|
| version | 规则、公共schema与实际有效源码/数据hash，包含未提交修改 |
| context | 输入配置、当前边界、实际倍率、最大体力、公开完整turn_types |
| state | 原生资源、buff、效果、预约、计数、阶段、完整用卡上下文 |
| cards | 实例、版本、定制、成长、有效conditions/cost/actions/effects AST |
| definitions | 相关原始结构化定义；v2增加configured_abilities |
| zones | hand/held有序；deck/discarded/removed按稳定实例排序 |
| zones.deck | 完整公开成员、size、known_top下一抽在前、已知相对顺序 |
| drinks | 当前饮料槽位 |
| choice / actions | 当前选择任务或合法动作，带decision_version |
| knowledge | 当前公共边界、缺省字段列表absent_fields与牌序知识 |
| result | score、结束/截断原因、最终成绩、合计与名次 |

公共schema为arena-public-exam/1。state.usedCard/lastUsedCard/movedCard和source.idx引用cards数组的稳定索引，不是手牌槽。effective AST未必已经代入成长求值；实际费用由原执行器计算，直接使用合法动作。

数值、条件、顺序、limit/ttl/delay和来源需分别编码，不能只看卡名/hash。缺省不等于0或无限；过期效果可能保留空对象。cardsUsed统计完整用卡；重复效果或多段得分不等于多次用卡。

全牌组组成在此Arena声明为公开，但隐藏真实山札顺序和RNG。策略可保留已见公共历史；顶牌的公开位置/相对顺序被维护，随机插入或洗牌按相应知识变化处理。observe不含seed、原生日志、真实deckCards或重放journal。

## 补选与错误原子性

act接受当前候选完整对象，例如：

```python
{"type":"play", "instance_id":"entry:002", "decision_version":4}
{"type":"drink", "slot":1, "decision_version":4}
{"type":"end_turn", "decision_version":4}
```

每次提交版本递增，旧候选不可复用。饮料消费后slot压缩；end_turn执行真实回合末。

choice给出type、min/max、ordered、allow_duplicates、can_skip、context、candidates及版本。indices是候选编号列表，不是牌定义ID或山札位置；保持指定次序，长度符合min/max且不重复。实际支持的补选包括hold、move_to_hand、use_selected。已验证饮料22单检索、卡790嵌套免费使用、卡527双选保留。

在操作实际需要选择时暂停，后续支付/触发待成功choose后继续。非法、重复、过期输入拒绝采用，不改变该局资源或RNG；内部重放仍有CPU成本。

TrainingError含kind/path/消息。未知内容、非法配置、机制异常、超容量和超预算都不能当成正常0分样本。

## 恢复、结果与运行成本

```python
from gakumas_arena import TrainingExam
private = exam.snapshot()  # 私有，不送给策略
restored = TrainingExam.restore(private)
assert restored.observe() == exam.observe()
branch = exam.fork()
same_opening = TrainingExam.restore(exam.initial_snapshot())
```

snapshot保存真实seed、完整journal和pending选择，可恢复到嵌套补选中。initial_snapshot是开局前边界，restore后执行开局一次。inspect_private含真实牌序、原生日志、补牌来源/计数/位置，只用于诊断，单独保存。

正常结束terminated=true、reason=normal，final_score含最后回合末结算；后续提交拒绝。truncate(decision_version=...)保留当前状态，truncated=true、final_score=null。异常为TrainingError。round2_score等于本场最终分，combined_score/rank未计算，返回null。

一个Python进程一个常驻Node，请求串行；多进程用spawn，各进程自己创建exam。单个exam不可并发提交。默认关闭日志/图表，与logs=True公共状态及成绩相同，没有另一套近似fast path。close_training_worker()关闭常驻进程。

last_cost计入重放的native_actions、rule_operations、replay_entries、rng_calls、milliseconds；计数有重叠不能相加。每次提交重放journal，长局成本增长。max_native_actions默认200000，可创建/恢复时调整；超限保留原局。通信超时默认60秒。脚本[测量](examples/training_ready/measurements.json)报告墙钟；未承诺规模吞吐，RSS/Colab待测。

源码变化后重启Python；有效hash包括training_config及未提交变化。旧hash快照拒绝恢复，避免混用规则版本。

## 目录、证据和分工

```python
from gakumas_arena.engine.training import training_catalog, content_version
catalog = training_catalog()  # 870卡/484道具/28饮料/154偶像/111定制
version = content_version()
```

目录可按hash缓存。完整指令分派检查、上游预期和实际组合执行是不同层次证据，见[manifest](examples/training_ready/manifest.json)。未知组合首次运行仍应记录错误，不能用“目录有条目”代替整局执行验收。

当前支持自定义单偶像golden考试和本场原始得分训练。RL负责张量、算法、奖励、课程、评分器和统计。fork复制真实世界，公共条件采样S02仍缺失，因此不能把fork冒充公平搜索教师。Round1/中场/完整培育流程为后续工作；不影响当前自定义HIF本战2。
