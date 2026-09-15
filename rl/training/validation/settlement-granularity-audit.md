# 自写适配、培育与编码的结算粒度审查（2026-09-12）

golden **仅指引用的 JS 库**，即 `gakumas_tools/packages/`。我们写的 Python 培育、
主数据解释、JS 调用与状态桥接（包括名为 `golden.py` 的文件）、训练投影和编码均属检查对象。
JS 的行为作为对照；Python 培育测试只能证明已测试的实现/契约，不会因此成为 golden。
本次修正自写的固定元气映射，并收紧携带效果翻译和桶化的准入检查。未修改引用的 JS 库、
模型、训练算法或冻结 v4 ZIP。当前本地源代码的修正尚未进入用户的 Colab 包。

## 已验证的边界

| 层 | 当前行为 | 证据 |
|---|---|---|
| 训练投影 | 只认证 GetCard/GetDrink 下纯 Vo/Da/Vi 非负整数加成、确定概率、无限次数、无复杂程序；按可交换的监听器区段分组 | `encoding/projection.py` 的 `_PLAIN_TRIGGERS`、`_ADDITIONS`、`eligible`、`listener_segment` |
| 桶台账 | 默认不认证；概率、独立次数、冷却、来源敏感、逐贡献派发均阻止合并；期限对象全部参与 key | `encoding/buckets.py` 的 `BuffContribution.mergeable` / `_key` |
| 考试输入 | action 列表长度、各条数值、顺序、重复控制表达式和效果实例不进入上述属性加成桶 | `encoding/graph.py` 的序列节点、带 position 的关系与 `_exam_projection` |
| 考试执行 | 每个 score 动作重新加集中并取整；每次好印象获得分别应用获得量倍率及取整；相关变化监听按允许的 phase 逐动作执行 | Native `Executor/index.js` / `resolvers.js` |
| 饮料奖励 | 显式奖励列表、普通随机奖励、HIF sampling kernel、特殊P道具奖励都逐件调用获得事件；每件的同步监听完成后才进入下一件 | `produce/runtime.py` 的 `_grant_rewards` / `_grant_resource`、`produce/sampling.py:grant`、`produce/customize_item_rewards.py:apply` |

受控结果（native score multiplier=1，其余未设置增益为零）：

- 集中=3：`score+=10; score+=10` 得26；`score+=20` 得23。
- `scoreTimes=1; score+=10` 得26，重复命中未折成一次20基础分。
- 好印象获得量倍率+10%：`+3; +5` 逐次取整得到10；`+8` 得9。
- 两个真实 Dance+4 效果定义的受控无限次监听器：获得第1瓶后 Dance=8、
  两来源计数各1；第2瓶后 Dance=16、两来源计数各2。四种奖励路径一致。
- 同样的两个监听器各限制1次时，两瓶共只加8；来源防连锁生效时，
  饮料可以获得而 support/memory 监听器不触发。桶不能替代这些守卫。
- 编码明确区分两次10与一次20、好印象3/5与8、动作3/5与5/3，
  以及奖励的 pickCount=1/2；投影不修改原观察或引擎计数。

例如安全的 `GetDrink -> Dance+8` 桶表示**每次合格获得事件的效果**，
并不是把两次 GetDrink 合成一次事件。获得两瓶应分别套用这个桶，且不能绕过来源守卫。
已有状态值（例如已结算的好印象总量）与“将执行的两条增加效果”是不同对象。

## 撤回先前对引擎内部 fresh 合并的错误判定

2026-09-11 的审查曾自行要求倍率 buff 按各自 fresh 独立到期，并将 golden 的不同
结果标为信息丢失。这个预期不是已确认的规则契约，不能据此认定引擎有错。
2026-09-12 按用户指定的 golden 边界撤回该结论，并删除对应 strict xfail；
这是修正错误测试预期，不是修复引擎或将未解决的引擎问题隐瞒为通过。

需要区分已经结算的状态和待执行程序：

- 好调已有2回合再获得2回合，golden 返回当前好调4回合。外部编码保留这个4，
  不自行拆成两个独立到期的2回合对象。新增真实公开观察测试验证了数值进入编码。
- 如果 golden 已经合并某类倍率 buff，外部采用合并后的公开项；如果它仍返回多项，
  外部保留多项的 amount/turns/fresh 等字段，不二次合并或自行反向拆分。
- 卡牌或监听器的“获得2回合”动作程序依然按 golden 的动作列表保存。
  保留程序粒度不等于要求结算后的状态保存逐来源历史。

以上补充测试验证常见动作次数和 JS 已结算状态的保留，并非全量效果或新增字段的
穷尽验证。后续检查新增字段准入时发现的自写代码问题列于下文。

## 扩展约束

共享效果定义可以减少重复数据；效果执行次数、顺序、每次取整与事件边界必须保留。
两次同值动作可表示成 `Repeat(2, Action(x))`，不能表示成 `Action(2*x)`。
外部只对已认证的修正项进行聚合，不能改变 JS 可区分的中间状态、触发、来源、
独立预算或到期。我们实现的培育状态与效果解释也需验证，不能因它们位于 Arena 中
就免检。未知/新效果默认保留程序和状态，不能凭同 type 或同 turns 在外部追加合并，
也不要求重建 JS 已经合并的来源实例。

## 本次发现并修正的自写代码问题

1. **固定元气错译成普通元气。** `GoldenProduceBridge._effect` 原将 `ExamBlockFix`
   编译为 `genki+=6`，JS 会附加干劲；现在编译为 JS 自带的 `fixedGenki+=6`。
   干劲10的对照中，旧翻译得到16，正确固定操作得到6。真实 Logic 特殊P道具的
   开场程序先增加干劲6，旧适配会随后获得12元气，修正后只获得固定6元气。
   对比冻结v4与当前代码，原先支持的50条开场 enchant 全部仍支持，仅3条含
   `ExamBlockFix` 的程序改变；没有新增拒绝。回归还覆盖全部18种特殊P道具考试附魔。

2. **通用携带效果翻译会静默忽略额外语义。** 原先即使加入 effectCount=2、后续连锁
   或新监听器字段，也只输出基础加成。现在逐分支检查未翻译的非默认字段，未支持的
   活跃字段抛出 `ProduceBridgeError`；不擅自推断新字段含义。这是扩展准入缺口，
   不表示当前主数据已有这些变体进入训练。

3. **桶化可绕过后续未知字段检查。** 投影先于图编译：原先在纯属性效果上添加未知
   字段后，效果仍可能被聚合并从机制定义中删除，后面的语义校验便看不到它。
   现在只聚合已知字段形状及默认辅助字段，并检查来源记录形状。未知字段（包括值0）
   保留原定义交给正常校验；带新增冷却等字段的来源也保持独立。
   当前已经认证的普通 Vo/Da/Vi 例子继续通过，未扩张合并范围。

## 验证

命令：使用 Arena Python，添加 training 导入目录后运行
`pytest -q rl/training/tests/test_settlement_granularity.py rl/training/tests/test_encoding_buckets.py`。
上述15项基线在本次继续通过。连同新增桶化准入测试、桥接语义测试和原有
`third_party/gakumas_arena/tests/test_produce_golden.py` 回归，43项通过、6个subtests通过。
随后另补真实Logic道具固定元气用例并单独验证通过，合计44项及6个subtests通过。
包含真实 Arena / Node 控制探针，无训练。

2026-09-11 首次逐字节核对：projection.py、buckets.py、graph.py、produce/runtime.py、
produce/sampling.py、produce/customize_item_rewards.py、Native BuffManager.js、Executor/index.js、resolvers.js
当时均与冻结的 `gakumas-colab-training-v4.zip` 对应文件一致。本次 projection.py 与
自写 produce/golden.py 已修正，不再声称所有本地源码都与旧包相同。
重新核对引用库 packages/ 下全部67个文件，与冻结v4逐字节一致。
冻结 ZIP SHA256：`0168a71503bebeeee1bc95f3f807489f392dacbb7c5b874d6f0aeb7b4dbcf2e7`。
