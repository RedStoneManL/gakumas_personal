# Arena 内容创作指南

入口版本：`arena-content/1`。这里描述**已实现并可执行**的 JSON/YAML 内容包；旧 `gakumas_arena/scenarios/hif.yaml` 是早期草图，不是本入口的配置格式。

新增内容遵循同一条路径：**配置 → 严格校验 → 编译为引擎定义 → 离线执行／检查 → 保存与恢复**。
现有机制的新数值和组合只改数据；新增结算机制才需要注册代码。卡名与 ID 不参与效果分发。

2026-09-08：运行规则已升级为 `arena-content-rules/4`；同阶段附魔监听者默认按稳定ID字典序执行，包内列表先后不代表执行优先级。同批条件、开始后阶段、准备自动使用和状态寿命见 [行为契约](ENGINE_RULE_CONTRACT.md)。[最小批次示例](examples/rule_alignment_minimal.json) 可直接运行；旧规则digest的存档需要使用原规则版本恢复。

## 1. 从一个能跑完的剧本开始

在 Arena 仓库终端执行（Windows 可以将 `python` 替换为 `.venv/Scripts/python.exe`）：

```powershell
python -m gakumas_arena.content init examples/my_pack.json --namespace my_pack
python -m gakumas_arena.content validate examples/my_pack.json
python -m gakumas_arena.content demo examples/my_pack.json --output examples/my_trace.json
python -m gakumas_arena.content inspect examples/my_pack.json cards my_pack/good
```

`init` 创建卡牌、效果、检索、触发器、被动、饮料、道具、事件、训练、试镜和完整剧本，拒绝覆盖已有文件。
`demo` 使用一个明确的外部“选择第一个合法选项”测试策略；运行时本身不会替玩家选择目标。
内容包标注 `synthetic=true`，产生的日志另外标注 `real_game_verified=false`，不是游戏内素材或实机验收。

- 完整样例：[content_starter.json](examples/content_starter.json)
- 字段 Schema：[arena-content-v1.schema.json](schemas/arena-content-v1.schema.json)
- 操作和参数目录：[content_mechanisms.json](examples/content_mechanisms.json)
- 实现入口：[content/__init__.py](../gakumas_arena/content/__init__.py)

```powershell
python -m gakumas_arena.content schema --output examples/schema.json
python -m gakumas_arena.content catalog --output examples/operations.json
python -m gakumas_arena.content export examples/my_pack.json --output examples/compiled.json
```

编译产物包含原内容包与原生主数据行，便于评审。运行时加载原内容包；导出文件不是另一种可直接运行的包格式。
YAML 用相同字段，安全加载，不支持 Python 标签、脚本、动态 import 或 eval。

## 2. 定义、实例、机制分别是什么

| 概念 | 示例 | 创建时的含义 |
|---|---|---|
| 机制 | `good_condition` | 引擎怎样增加并结算好调 |
| 效果定义 | `my_pack/good3` | 用这个机制增加 3 回合 |
| 卡牌定义 | `my_pack/good` | 费用、效果列表、使用后去向 |
| 卡牌变体 | 同 ID，`upgrade: 1` | 显式定义升级后的完整费用／效果 |
| 运行时副本 | `card:17` / `entity:3` | 一张具体卡；同名副本有不同身份 |
| 被动实例 | 动态次数、剩余时间、来源 | 当前状态，不是重新执行一次定义 |

作者 ID 必须是 `namespace/name`，例如 `my_pack/good`。不同包用不同命名空间；包内按类型查引用。
卡牌允许相同 ID 的多个不同 `upgrade`；其他同类型重复 ID 会报错。禁止覆盖固定主数据库中的定义。
每次编译创建独立仓库视图，不污染全局缓存或另一个包。

## 3. 创建一张新卡

在包的 `effects` 添加：

```json
{"id":"my_pack/good3","operation":"good_condition","arguments":{"turns":3}}
```

在 `cards` 添加：

```json
{
  "id":"my_pack/new_card",
  "name":"自定义：好调三回合",
  "kind":"mental",
  "plan":"sense",
  "cost":{"resource":"stamina","amount":3},
  "effects":["my_pack/good3"],
  "after_play":"exhaust"
}
```

之后把这张卡加入某个 `auditions[].deck` 或 `scenarios[].deck`，运行 `validate` 和 `demo`。
把 `turns` 改为 5，或在 `effects` 追加抽牌、集中等已有效果，不需修改 Python。

常用属性：

- `kind`：active / mental / trouble；`plan`：common / sense / logic / anomaly。
- `cost.resource`：stamina / penetrate / concentration / good_condition / excellent_condition / good_impression / motivation / full_power。
- `after_play`：discard / exhaust / hold / deck_bottom。普通“レッスン中1回”使用 `exhaust`；被动触发次数用 `uses`，二者不是同一个限制。
- `opening: true`：初始入手规则交给原生引擎；不是手牌槽位编号。
- `upgrade: 1`：增加一条同 ID 的完整强化定义。只写 `+` 名称不产生强化；缺失变体不会自动回退到基础卡。

卡的可用条件：配置一个 `phase: condition` 的触发器，并将其 ID 写入卡的 `condition`。

```json
{"id":"my_pack/focus13","phase":"condition",
 "field":"ProduceExamFieldStatusType_LessonBuffUp","value":13}
```

某一条效果的条件与整张卡的可用条件不同。例如先打分，再在集中达标时抽牌：

```json
"effects": ["my_pack/score", {"effect":"my_pack/draw", "condition":"my_pack/when_playing_focus13"}]
```

后一触发器用 `phase: card_used`，数值字段同上。效果列表按顺序执行。

## 4. 创建效果与成长

优先使用 `catalog` 列出的友好操作：

| 类别 | 已有操作 |
|---|---|
| 资源／状态 | concentration、good_condition、excellent_condition、good_impression、motivation、block、block_fixed、full_power |
| 消耗／计分 | recover_stamina、damage_stamina、half_cost、score、score_multiplier |
| 行动／卡牌 | draw、extra_action、extra_turn、move_card、force_play、grow_card |
| 生命周期 | passive、delay |
| 培育效果 | gain、grant_card、grant_drink、choose_card、card_reward、resource |

`score.arguments` 使用 `amount` 与 `hits`；沿用集中、好调、倍率与逐次取整。
`score_multiplier.permille=1000` 表示额外 +100%；试镜 `score_bonus=1` 表示最终倍率 ×1，这两个单位不同。
好调与绝好调用 `turns`，触发次数用 `uses`，不要把持续时间和增益数值混在一起。
高级 `native_scalar` 接受原生 `effect_type/value1/value2/count/turns`，只用于无引用的标量效果；未知类型及需要检索／附魔／成长等引用的类型会拒绝。
“已有效果器”表示代码路径存在，不等于该原生枚举的全部边界都已经过实机验证。

成长也可以单独定义并复用：

```json
"growth": [{"id":"my_pack/score_growth","effect_type":"ProduceCardGrowEffectType_LessonAdd","value":5}]
```

```json
{"id":"my_pack/grow_hand","operation":"grow_card",
 "arguments":{"search":"my_pack/hand","growth":"my_pack/score_growth"}}
```

支持的标量成长类型如下，填写时加上 `ProduceCardGrowEffectType_` 前缀：

| 改变什么 | 类型后缀 |
|---|---|
| 分数 | LessonAdd / LessonReduce |
| 元气 | BlockAdd |
| 费用 | CostAdd / CostReduce |
| 好印象／やる気／集中 | ReviewAdd / AggressiveAdd / LessonBuffAdd |
| 好调／绝好调回合 | ParameterBuffTurnAdd / ParameterBuffMultiplePerTurnAdd |
| 全力值 | FullPowerPointAdd |

成长属于课内副本状态；剧本永久强化通过 `choose_card` 的 upgrade 或显式变体处理。

## 5. 创建检索、弃牌和自动使用

先声明筛选器：

```json
{"id":"my_pack/mental_hand","zone":"hand","card_kind":"mental"}
```

支持 hand / deck / deck_grave / hold / lost / not_lost / playing / target；可按 `card_ids` 精确过滤，也可设置 `self_only`。

```json
{"id":"my_pack/discard_one","operation":"move_card",
 "arguments":{"search":"my_pack/mental_hand","destination":"discard","mode":"select","count":1}}
```

`mode` 为 select / random / all。select 返回全部候选并暂停，支持一次选 N 张和连续嵌套选择；目标不足时选实际存在的数量，零候选直接结束该效果。
选择用**实例 ID**，重复、过期、不在候选集合内的输入会被拒绝。
`force_play` 同样可暂停选择；`pay_cost` 控制是否付费。它计入完整卡牌使用次数，但不占玩家行动窗口。
抽牌继续遵循原生手牌上限；手牌满时不会凭空抽出更多牌。

## 6. 创建被动、P 道具、饮料

```json
"triggers": [{"id":"my_pack/start","phase":"turn_start"}],
"passives": [{"id":"my_pack/start_focus","trigger":"my_pack/start",
              "effects":["my_pack/focus2"],"uses":2,"turns":4}],
"items": [{"id":"my_pack/item","passives":["my_pack/start_focus"]}],
"drinks": [{"id":"my_pack/drink","effects":["my_pack/draw"]}]
```

省略／null 的 `uses` 与 `turns` 表示不限；零值不是不限。
卡牌要在使用时挂上被动，可引用 `operation: passive`，其 `arguments.id` 为被动 ID。
`delay` 将 `arguments.id` 指定的效果延后 `arguments.turns` 回合执行。
触发时机支持 exam_start / turn_start / turn_end / card_used / after_card / status_change / every_turn / every_card；间隔型必须给 `every`。
`condition` 只用来表达卡牌可用性，不作为自动触发时机。

真实内容可从 [完整目录](REAL_CONTENT_CATALOGUE.md) 查询后，直接在试镜 `deck` 中引用卡 ID 与强化等级，在 `drinks` / `items` 中引用原生 ID。编译器检查整个定义依赖；含培育阶段触发或未支持机制的 P 道具会明确拒绝，不会只运行其中一部分。独立 `passives` 仍须声明持续时间与次数，不能裸挂原生附魔 ID。

## 7. 创建一个事件

事件由有序选项组成；选项支持条件、费用、效果和分支。成本先合并检查，再一次支付。

```json
{
  "id":"my_pack/event",
  "options":[
    {"id":"practice","label":"消耗5体力，获得40歌唱",
     "costs":[{"field":"stamina","amount":5}],
     "effects":[{"operation":"gain","arguments":{"field":"vocal","amount":40}}]},
    {"id":"rest","label":"恢复5体力",
     "effects":[{"operation":"gain","arguments":{"field":"stamina","amount":5}}]}
  ]
}
```

gain 复用 ProduceRuntime 的资源收益公式：三维增量会应用已配置成长率，体力回复不超过上限。
成长率存储为比例，例如 `vocal_growth: 0.2`；通过 gain 增加成长率时参数单位为千分比，例如 amount=200。
条件比较支持 ge / gt / le / lt / eq / ne，多条条件取 AND。
需要 OR 时可建立多个 branch 条目或多个选项；不使用字符串表达式执行任意代码。

`card_reward` 的 cards 为明确候选 ID 列表；`choose_card` 的 action 为 remove / upgrade / duplicate。
取得饮料超过剧本容量时暂停为 `drink_overflow`，由调用者选择丢弃哪些具体实例。
一个选项产生多个选择时，所有后续效果和流程跳转都等待选择完成。

## 8. 创建训练、课程与试镜

纯收益训练：

```json
{"id":"my_pack/training","costs":[{"field":"stamina","amount":5}],
 "effects":[{"operation":"gain","arguments":{"field":"vocal","amount":40}}]}
```

可打牌的课程：在 training 增加 `audition: "my_pack/exam"`。训练成本先支付；打牌结束后，按是否达标应用 effects 或 failure_effects。
试镜自身的 success_effects / failure_effects 也会先执行，再执行训练结果奖励。

```json
{
  "id":"my_pack/exam","turns":6,"clear_score":100,"perfect_score":300,
  "weights":[1,1,1],"starting_stamina":30,"max_stamina":30,"score_bonus":1,
  "deck":[{"card":"my_pack/new_card","copies":2}],
  "hand_limit":5,"turn_draw":3,"plays_per_turn":1,
  "hold_limit":2,"hold_overflow":"oldest"
}
```

`colors` 可指定每个基础回合的属性；长度必须等于 turns。省略时使用原生随机属性；指定后额外回合沿用最后一个指定属性。
`weights` 非负且至少一项非零。`clear_score` 是本入口明确的分数达标线，`perfect_score` 可提前结束。
这里不会依据未知 NPC 成长曲线估算自创试镜的胜负。
`hold_overflow: oldest` 沿用丢弃最早保留卡的规则；自创玩法可以改为 choose，此时显式暂停选择。
卡牌效果、费用、好调／好印象结算、回合衰减等仍使用原生 ExamRuntime。

## 9. 创建剧本与特殊资源

剧本是有向无环流程图。节点类型：event、training、audition、effects、branch、end。
所有非 end 节点必须声明默认 next_node；事件选项可覆盖去向，试镜可设置 failure_node。
branch 按声明顺序选择第一个满足条件的分支；都不满足则进入默认 next_node。
循环依赖在加载时拒绝。重复日程可以明确列出多个节点，不依赖隐式无限循环。

```json
{
  "id":"my_pack/scenario","start":"start",
  "initial":{"stamina":30,"max_stamina":30,"produce_points":100},
  "parameter_limit":2000,"drink_limit":3,
  "resources":{"scenario.fame":{"initial":0,"minimum":0,"maximum":100}},
  "hooks":{"after_node":[{"operation":"resource",
            "arguments":{"field":"scenario.fame","delta":5}}]},
  "nodes":[
    {"id":"start","kind":"event","content":"my_pack/event","next_node":"exam"},
    {"id":"exam","kind":"audition","content":"my_pack/exam","next_node":"end"},
    {"id":"end","kind":"end"}
  ]
}
```

未声明的三维、成长率、P 点默认为 0；体力／最大体力默认为 30。这里是自创玩法的明确默认值，不继承官方剧本的估算初始属性。
特殊资源必须声明在 resources 下，名字用 `scenario.` 前缀，`resource.delta` 可正可负并受上下界约束。
公共 hooks：start、before_node、after_node、finish；按列表顺序执行，也允许产生选择。
`base` 仅选择现有基础数据环境，默认 produce-001；不会偷偷执行该官方剧本的 HIF 日程或开场事件。

若 scenario 声明了非空 deck，各试镜使用当前持久牌组，包含事件取得／强化／删除结果；体力与剩余饮料跨试镜保留，课内弃牌／除外／成长不永久改写牌组。
若未声明 scenario deck，每场使用试镜自己的 deck 和 drinks；这适用于互相独立的关卡串联。
也可以显式指定 `inventory_mode: scenario` 或 `audition`。前者允许从空牌组开始，再通过开场事件取得卡牌；后者始终使用每场试镜配置的物品。省略该字段时采用上述按初始 deck 判断的默认规则。剧本体力始终跨节点保留。

## 10. 在 Python 中运行、决策与恢复

```python
from gakumas_arena.content import compile_pack, ContentSession, ContentExam

content = compile_pack("examples/my_pack.json")
session = content.create_scenario("my_pack/scenario", seed=7)
view = session.view()
# 把 pending.candidates 展示给玩家或交给策略；此处是调用者明确选了一个选项。
session.choose(["practice"], revision=view["revision"])

snapshot = session.snapshot()       # 可直接 JSON 序列化；文件持久化由调用方负责
restored = ContentSession.restore(content, snapshot)
assert restored.view() == session.view()

exam = content.create_exam("my_pack/audition", seed=7)  # init 模板中的试镜 ID
view = exam.view()
exam.act(view["actions"][0]["id"], revision=view["revision"])
if exam.pending:
    exam.choose([exam.pending["candidates"][0]["id"]], revision=exam.revision)
```

剧本内考试通过 session.exam_act / session.exam_choose 推进，传的是外层 session.revision。
独立 ContentExam 则传 exam.revision。选 N 张时一次提供 N 个不同实例 ID。
快照绑定内容摘要、主数据 revision、机制 revision 和规则版本；不匹配、篡改和非法日志会拒绝。
校验哈希用于检测损坏，不是防恶意调用方伪造的数字签名。
恢复时重放本地确定性操作，包含原选择和随机种子；不调用游戏输入、网络、策略或文件日志。

考试也提供共用编码入口：

```python
encoded = exam.encode()
observation = encoded["observation"]     # 原生卡牌特征 + observed/3 被动结构及掩码
manifest = encoded["manifest"]           # 读取版本、尺寸和各字段含义
action_ids = encoded["action_ids"]       # 合法张量槽位 → act/choose 接收的 ID
selection_count = encoded["selection_count"]  # 多选时必须提交不同目标，数量恰好为此值
```

`ContentExam.encode()` 不推进状态。新效果 ID 不增加被动字典槽位；新的机制类型若没有编码语义，会明确拒绝编码，需要宿主同时扩展编码器。完整规则与候选信息始终可通过内容包和 view 检查。
整个自创培育流程当前使用结构化 view；本阶段没有新增完整流程的 Gym/SB3 训练适配器。
考试 view 明确标为 `simulation_full`，包含各卡区、饮料消耗、附魔／持续／预约状态，以及回合和行动计数，供离线调试和渲染。
其中附魔的 applied_turn 是引擎内部衰减标记；不能直接当作 live 契约的真实应用回合。
该完整模拟视图可见牌堆顺序，不应直接作为实际游戏可观察字段发送给 adapter；实况仍走 LiveSession 的证据与已知掩码契约。

回合与行动沿用 [公共计数语义](LIVE_PASSIVE_CONTRACT.md#回合与行动记账)：turn 从 1 开始；完整强制使用计入已用卡次数，但不消耗玩家行动窗口；饮料、补选与单卡多段伤害不增加卡使用次数。`plays_per_turn` 配置基础玩家窗口，追加行动效果在其上叠加。

## 11. 新增一种真正的新机制

仅改参数或组合时，继续使用 JSON。若引擎确实没有该结算操作，宿主程序显式注册它：

```python
from gakumas_arena.content import builtins, Operation, compile_pack
from gakumas_arena.content.operations import Amount

mechanisms = builtins()
mechanisms.revision = "my-mechanisms/1"

def apply_triple_focus(context, effect, source):
    context.resources["lesson_buff"] += effect["effectValue1"] * 3

mechanisms.register_exam(
    "triple_focus",
    Operation(Amount, lambda p: {"effectType":"MyTripleFocus", "effectValue1":p.amount},
              "示例：集中增加量乘三"),
    effect_type="MyTripleFocus", handler=apply_triple_focus,
)
content = compile_pack("examples/my_pack.json", mechanisms=mechanisms)
```

此例仅演示扩展 API。正式机制应复用 context 的资源增益／状态变化分发方法，明确连锁来源、触发顺序、取整、次数和生命周期，并用规则断言验证。
所有扩展处理器必须是确定性、无外部副作用的本地函数；随机性只取当前 runtime 的 RNG。不要在处理器里点击游戏、写日志文件或发请求，因为模拟恢复会重放它。
培育阶段用 register_flow(name, Operation(...), handler)；handler 接收 ContentSession 和校验后的参数。
注册表属于单次编译，不修改全局效果器。重复注册会报错；禁止通过内容包指定 Python 导入路径。
修改处理器语义必须提高 mechanisms.revision。增加新的编码语义也必须扩展并升级编码器，不能声称旧模型自动理解新规则。

## 12. 创作者的验收清单

1. validate 通过：字段拼写、命名空间、全部引用、变体、流程去向、循环、未知操作均检查。
2. inspect / export 核对生成的费用、持续时间、次数和效果顺序。
3. 在最小考试中分别测试：费用足够／不足，状态有／无，重复副本，强化前／后，回合边界。
4. 涉及选择时测试：合法目标、错误目标、多选、连续选择、保存后恢复。
5. 运行完整合成剧本，检查成功和失败分支。效果器存在、测试通过、实机证据支持是三种不同的覆盖状态。

本入口提供创作与执行基础设施；已有官方 HIF/NIA 路线继续通过原 master + ProduceRuntime 运行，尚未逐事件迁移成内容包。
官方主数据中的未知规则不会因新配置入口而自动得到验证。实况仍只消费已结算观察；新被动机制绑定见 [LIVE_PASSIVE_GENERIC.md](LIVE_PASSIVE_GENERIC.md)。

## 补充：卡牌进入区域时的效果

卡牌可配置 `on_move: {"destination": "hand", "effects": ["your_pack/effect"]}`；目标也可以是 `hold`。这与出牌的 `effects` 独立，多个效果按数组顺序执行。完整 JSON、开场/中间选择恢复及版本迁移见 [CARD_MOVEMENT_CONTRACT.md](CARD_MOVEMENT_CONTRACT.md) 和 [可运行样例](examples/content_card_movement.json)。
