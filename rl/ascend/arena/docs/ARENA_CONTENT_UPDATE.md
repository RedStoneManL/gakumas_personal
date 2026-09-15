# 数据驱动内容基础设施交付

2026-09-08，沿用 `codex/arena-live-bridge`，基点 `ef2402958547b2050e873841b9ff5066a895b1a9`。
固定主数据 `gakumasu-diff@571dbb62601e78998cddeacdbce3ea1bc672d7fc`。保留已有未提交成果；本轮只修改 Arena，不操作游戏或 Maa，不训练 RL、不调整策略追求通过率，未提交或推送。

## 创作者从这里开始

- [创建新卡、效果、成长、被动、饮料、道具、事件、训练、试镜、剧本](CONTENT_AUTHORING.md)：逐类流程、完整字段、组合例子、运行与恢复、新机制扩展 API。
- [最小完整内容包](examples/content_starter.json)：明确标记合成数据，包含事件 → 训练 → 饮料奖励／强化选择 → 试镜 → 成功／失败。
- [完整运行记录](examples/content_demo_trace.json)：合成输入、每次明确选择、最终状态和可恢复快照。
- [内容 JSON Schema](schemas/arena-content-v1.schema.json)、[可用操作及参数 Schema](examples/content_mechanisms.json)。
- [实际架构](CONTENT_ARCHITECTURE.md)、[实况被动机制契约](LIVE_PASSIVE_GENERIC.md)、[最小实况 passive/2 JSON](examples/live_passive_generic.json)。

```powershell
.venv/Scripts/python.exe -m gakumas_arena.content init examples/my_pack.json --namespace my_pack
.venv/Scripts/python.exe -m gakumas_arena.content validate examples/my_pack.json
.venv/Scripts/python.exe -m gakumas_arena.content demo examples/my_pack.json --output examples/my_trace.json
.venv/Scripts/python.exe -m gakumas_arena.content inspect examples/my_pack.json cards my_pack/good
```

全部包通过 `compile_pack()` 使用同一条编译路径；`init` 拒绝覆盖已有文件。导出文档和示例可运行 `python -m scripts.export_content_artifacts` 重建。

## 本轮实现

| 基础能力 | 可用行为 |
|---|---|
| 定义与实例 | JSON/YAML、命名空间、严格字段和数值、同 ID 强化变体、独立主数据视图、实例身份 |
| 卡牌／效果 | 费用、条件、顺序效果、出牌去向；集中、好调、绝好调、好印象、やる気、元气、体力、抽牌、追加行动／回合等复用原生机制 |
| 触发／成长 | 相位、资源门槛、目标筛选、持续时间／次数；多个来源实例独立计数；卡成长和条件效果 |
| 选择 | 检索、弃牌、移动、强制使用、连续／多目标选择、保留容量选择；暂停时不自动选目标 |
| 事件／训练 | 条件与累计费用、资源收益、卡奖励、升级／删除／复制、饮料容量选择；训练可关联一场可打牌课程 |
| 试镜 | 精确达标线、提前结束线、属性权重／回合属性、体力、手牌／保留／行动容量、卡组／饮料／道具、成功失败效果 |
| 剧本 | 有向无环流程图、条件分支、公共 hooks、显式库存模式、跨场体力／牌组／饮料、声明式特殊资源 |
| 恢复 | 内容／规则／主数据摘要校验、确定性日志重放、原选择续跑、非法与过期输入回滚 |
| 状态与编码 | 可 JSON 序列化的完整离线视图；考试复用公共特征及 observed/3，被动以机制结构编码，合法动作槽位映射公开 |
| 真正的新机制 | 宿主显式注册参数编译器与本地处理器；现有机制的新卡／新数值无需增加卡 ID 分支 |

高级 `native_scalar` 只接受已知且具有处理器的标量类型；需要引用、目标或剧本特殊配置的类型需使用明确操作／扩展。编译器检查效果、触发及附魔引用链和已知机制，未知机制报错；这不等于所有已注册规则都有实机数值认证。

卡实例与被动来源实例分开。普通“课内一次”由出牌后除外表示，被动的使用次数单独配置。完整强制使用增加卡使用计数，同时保留玩家窗口；补选、饮料和普通多段伤害不增加该计数，定义仍为 `arena-exam-counters/1`。

## 实况兼容与迁移

新 `arena-passive/2` 根据来源定义链及 phase/field/effect/search 检查支持情况，不要求为每个新卡或 enchant ID 写白名单。不同参数、相同支持机制的自创卡已通过合成绑定验证。

旧 passive/1、observed/2 空间保留；v2 profile 才使用 observed/3。v3 被动 32 槽、效果 128 槽，有独立 known masks；超容量返回 unsupported，不能请求 adapter 不断补读。
缺少当前观察为 observation；来源矛盾或不可能次数为 contract；预约、再演、卡绑定、未支持历史语义等为 unsupported；未决命令仍走 resolution。

`arena-live/1`、`arena-session/1`、奖励／咨询接口和 submitted/uncertain 原命令恢复、去重保持兼容。
LiveSession 只消费实际观察，不用离线模拟重放推断游戏状态。宿主注入自创仓库时，主数据 revision 附加内容摘要；这不向游戏安装新内容。

## 验证与底层修正

运行命令：

```powershell
.venv/Scripts/python.exe -m pytest -q --disable-warnings --maxfail=3
.venv/Scripts/python.exe -m scripts.export_content_artifacts
```

验收：全仓 **554 passed / 3 skipped**；其中新增内容及通用绑定测试 **49 项**。新代码通过 Ruff；`git diff --check` 通过。
测试包括规则资源消费、强化、源实例隔离、条件、额外回合、嵌套强制使用、连续选择恢复、错误输入原子性、CLI 从生成到恢复、导出 Schema 一致性、新 ID 编码稳定性和超容量分类。全部新增完整场景均明确为 synthetic，未作为实机联调结论。

为使参数真正生效，修复原生层以下行为：显式空牌组／空饮料不再触发随机默认；最大体力可配置；追加回合读取数量；非卡绑定触发器接收事件卡；自动使用窗口补偿在后续追加行动时保留；嵌套使用恢复外层 playing/current_card/临时效果水位。

旧 `test_loadouts` 固定 seed=1 必过首场的断言依赖空饮料栏被补出随机默认饮料。对照实验只恢复该旧行为，就再次出现两次随机默认库存、首场 37176 分通过。
因此回归改为校验终止、正确预设和选拔顺序、只有前场通过才推进；另加显式空库存禁止随机生成的规则测试。没有为了维持旧通过率调卡牌参数或策略。

## 尚未覆盖的范围

1. 现有官方初／NIA／HIF 路线仍使用原 master 与 ProduceRuntime 装配，并未逐事件迁移为新内容包。旧 hif.yaml 仍是草图。
2. 构造入口、机制实现、离线验收和实机验证分别记录；不能把可配置解释为官方全部规则与数值已验证。官方实况考试绑定仍限当前 HIF センス支持范围。
3. 实况预约、再演、卡绑定、StartPlay 歧义时序等仍明确不支持；离线新机制也必须配套规则与编码支持。
4. 内容包入口目前一次编译一个包；复用同包定义或原 master，跨包依赖加载／自动升级迁移尚未提供。快照仅恢复相同版本内容。
5. 整个自创流程提供 view/choose/恢复 API，尚无新增完整流程 Gym/SB3 训练适配器。考试的结构化被动摘要不是可逆规则描述，也不代表旧模型理解新机制。

线上参考分类和来源链接见 [CONTENT_ARCHITECTURE.md](CONTENT_ARCHITECTURE.md#机制参考与证据)。所有新增第三方资料仅作机制分类和数据核对参考。
