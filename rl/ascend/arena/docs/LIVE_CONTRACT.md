# Arena 与 adapter 联调契约

首版 `arena-live/1`，实现位于 `gakumas_arena.live`。传输为本地 Python 对象或 JSON，
不需要 HTTP。游戏输入仍由 adapter 唯一执行。此文的协议已实现；当前页面绑定和缺口见下文及
[规划交付记录](ARENA_ENGINE_UPDATE.md) 与 [考试交付记录](ARENA_EXAM_UPDATE.md)。

HIF センス考试新增字段与实例规则见 [LIVE_EXAM_CONTRACT.md](LIVE_EXAM_CONTRACT.md)。
`LiveBackend()` 按页面分发到 `PlanningBackend` 或 `ExamBackend`；原奖励/咨询接口不变。
非空回忆/P 道具/卡触发、计数语义与公共 classify_issues 见 [被动契约](LIVE_PASSIVE_CONTRACT.md)。

## 调用顺序

```python
from gakumas_arena.live import RunSetup, Observation, ActionResult, LiveSession

session = LiveSession(policy, backend)
report = session.initialize(RunSetup.model_validate(setup_json), Observation.model_validate(checkpoint_json))
decision = session.decide()
if decision.kind == "Act":
    command = decision.command
    # adapter 必须同时核对自己当前画面的 run/observation/revision 与语义目标。
    session.mark_submitted(command)
    # adapter 在此执行语义输入并读取游戏实际结果。
    report = session.accept_result(ActionResult.model_validate(result_json), events, next_observation)
```

`mark_submitted` 表示输入已进入提交事务，不证明输入到达游戏。进程中断或执行异常时提交 `uncertain`；
它会阻止新的消费命令。必须补交同一 command 的 `confirmed` 或 `not_applied` 回执与新快照才能继续。
若无法判断，继续观察并保留未决事务；不要自动重试点击。

`decide()` 返回 `Act / Inspect / Wait / Halt`。`Inspect.missing` 为具体字段路径；
`Wait` 用于转场、预览或已提交等待结果，`Halt` 用于已结束的运行。
未配置 `DecisionBackend` 时返回 `Inspect(arena.engine_binding)`，不会把 UI 可用性当游戏合法性。

## 类型与既有引擎对应

| 实况类型 | 既有类型 / 语义 |
|---|---|
| `RunSetup.scenario_id` | 主数据 `Produce.id`，例如 produce-007；不接受库存索引 |
| `RunLoadout` | `LoadoutConfig` / `build_idol_loadout` 输入；未知成长等级为 null |
| `SupportSetup` | 逐卡 `SupportCardSelection`；各自等级与租借状态分别保存 |
| `MemorySetup` | `ProduceMemorySpec` / `ProduceMemoryCardSpec`；生成来源与使用限制分开 |
| `Observation.facts` | 当前绝对事实，字段名使用引擎语义；例如 `stamina`、`produce_points` |
| `EntityRef` | 主数据 definition_id + 强化/自定义 + 实机 instance_id；RuntimeCard.uid 由绑定维护 |
| `Choice` | 当前 `ProduceActionCandidate` / `ExamActionCandidate` 的语义动作；action index 只在 Arena 内部使用 |
| `PendingDecision` | 每个奖励、咨询、授业、检索、弃牌、溢出等独立决策边界 |
| `PreparedDecision` | 既有 `Policy.act(env, obs, info)` 输入与槽到 Choice 的映射，必须附 encoder manifest |
| `ActionResult` | 提交命令的游戏确认结果，禁止用“点击成功”填 confirmed |

状态命名注意：`stamina`=体力，`block`=元气，`lesson_buff`=集中，`parameter_buff`=好调，
`parameter_buff_multiple_per_turn`=绝好调剩余回合；`concentration` 是アノマリー强气指针。

## 完整性、身份与时序

- `contract_version` 必须是 `arena-live/1`。未知字段会被拒绝；对象可用 `model_dump_json()` 序列化。
- `RunSetup.checkpoint_mode` 仅支持 `after_initial_effects`。编成用于规则配置，实测起点已含开场结算，
  不重复叠加。回忆的コンテスト属性在 `contest_snapshot` 单独存证，不用于培育初始加算。
- `ObservedValue(status="unknown", value=null)` 保留缺失；已知 0 必须写 observed、0 和 evidence。
  所有 facts 属于本 observation；未出现的字段不从上次快照自动补齐。模型估计由 backend 单独管理，
  不得标成 observed；encoder 若用估计须提供来源和缺失掩码，否则返回 Inspect。
- 每个命名资产区域的 `Inventory.coverage` 为 complete/partial/unknown。只有 complete 才可替换完整多重集。
  definition_id、upgrade_count、customize_ids 未识别时分别为 null；空自定义数组代表已确认无自定义。
- 同名卡/饮料使用不同 instance_id；同一副本换槽不换 ID。实例身份不确定时补读，不能由槽位推定。
- observation_id 在运行内唯一，revision 严格递增。相同 ID 相同内容的当前观察可重发；旧观察、
  同 ID 不同内容、回退的 event_watermark 均拒绝。较新观察使尚未提交的旧 command 失效。
- Choice 必须是 adapter 真正看到的候选，`ui_enabled` 表示 UI 状态；游戏规则合法性由 backend 验证。
  `PendingDecision.coverage != complete` 时暂不决策。多选页面由 adapter 给出一次完整语义输入的目标集合，
  不允许 bridge 在宏动作中偷偷处理下一个选择。
- command 绑定 run_id、observation_id、revision、decision_id 和完整 Choice。重复 decide 返回同一提案。
  adapter 在实际输入前必须校验这几个字段和目标仍可见；仅调用 mark_submitted 不能检测外部 UI 的自行变化。

## 结果与事件的包含关系

本版采用**绝对快照为唯一事实来源**。`ObservedEvent` 只进审计账本，payload 的数值 delta 不做加减。
next_observation.event_watermark 声明快照发生在该事件序号之后，所有随回执提交的事件 sequence 必须 ≤ watermark。
缺少的资源留 unknown，不能通过事件 delta 推算后冒充实测值。

confirmed / not_applied 必须提供 evidence 和比 command 新的快照。uncertain 可先不带新快照，
但不能携带“已发生事件”。事件只能随 confirmed 结果登记，且 command_id 必须一致。
result_id / event_id 去重；相同 ID 不同内容拒绝。事件 sequence 在 run 内唯一。重复旧结果不会回滚新观察。
不支持一次消费多个未决命令；每个 LiveSession 只处理一次运行，调用需串行。

## 公共会话恢复

```python
saved_json = session.snapshot().model_dump_json()  # adapter 负责持久化
restored = LiveSession.restore(saved_json, policy, backend)
original_command = restored.pending_command
transaction_state = restored.command_state  # idle/proposed/submitted/uncertain
```

版本为 `arena-session/1`；[schema](schemas/arena-session-v1.json) 与 [合成恢复往返](examples/live_exam_recovery.json)。
restore 不调用 policy.act，也不执行游戏输入。submitted/uncertain 保留原命令与去重账本并阻塞新消费，
补交原命令的 confirmed/not_applied 及新快照后继续。proposed 保留原提案，执行前仍必须核验当前 UI。
拒绝损坏或不一致账本，不静默迁移 master/rules，不允许重用任何历史 command_id。
SHA256 仅检查完整性，调用方负责可信来源、原子落盘和 UI 补读；无需修改 session 私有字段。

## 首次联调所需最小材料

1. 当前页面稳定观察：run_id、observation_id、revision、page、stability、完整候选及 ui_enabled。
2. 卡/饮料候选：主数据 ID、强化级、自定义 ID（无则 []）、具体 instance_id 与详情证据。
3. 消费动作：前一观察 → command → 输入提交 → 游戏后快照，附确认凭据；失败时区分未发生与不确定。
4. 初始配置暂缺字段可传 null：偶像成长等级、各支援等级/ID、回忆来源与能力/获得时机、
   初始牌组及物品完整性。历史 preparation-evidence.json 仍不能直接视为完整初始化配置。

JSON Schema 由 `python scripts/export_live_schema.py` 生成至 `docs/schemas/arena-live-v1.json`。
此契约不改变 adapter 的游戏预算或输入权限，也不发送消息或驱动游戏。

## 当前可运行的页面绑定

使用 `PlanningBackend()`，参照 [完整示例](../scripts/demo_live_bridge.py) 和
[示例 JSON 往返](examples/live_reward_consult.json)。规划页面支持：

| 页面 | action_type | 额外必需实测字段 |
|---|---|---|
| card_reward | card_reward_pick_1/2/3、card_reward_skip | pick 的一个完整卡实体 target |
| card_reward | card_reward_reroll | card_reward_rerolls_used、card_select_reroll_count_bonus |
| consult | shop_buy_card_* | 一个完整卡实体、parameters.price、produce_points |
| consult | shop_buy_drink_* | 一个饮料实体、price、produce_points、完整 drinks、drink_limit_bonus |
| consult | shop_reroll | shop_rerolls_used、shop_reroll_count_bonus |
| consult | consult_finish | 无额外消费字段 |

共同要求：稳定帧、完整候选、明确 ui_enabled、完整 deck 及所有卡变体；已知 loadout.idol_card_id；
masterdata_revision 与本地 master Git commit 一致；rules_revision=`arena-rules/2`。
UI 明确禁用的商品可不提供已不可读的卡详情/价格，掩码禁止其动作且不补造特征。
`pick_1/2/3` 是当前候选动作类型，命令仍绑定完整 target.instance_id，不能据编号定位旧页面。

此 backend 构造当前选择点的编码视图，不运行 reset/step，也不提供隐藏牌序。
特征来自既有 env 编码，再用 `global_known_mask`、`action_features_known_mask` 标明未知项。
训练使用同一 `PlanningVisibilityWrapper`；encoder version 为 `arena-planning-observed/2`。
示例维度 global=81、动作槽=40、动作宽=320，以完整 manifest 为准。
Policy 需声明 `supports_partial_observations=True`；旧 Heuristic/Search 和旧 checkpoint 不能直接接入。
考试页面使用 `ExamBackend()` 或统一的 `LiveBackend()`：支持 card/drink/end_turn，以及 search/discard 的
固定选一张 card_select；详见 [考试契约](LIVE_EXAM_CONTRACT.md)。考试编码为 `arena-exam-observed/2`。
其余未绑定页面返回具体 Inspect；尚不是完整实况自动培育。

## 编成与四张回忆卡

`to_loadout_config(setup.loadout)` 在全部编成字段完整时转换到既有 `LoadoutConfig`，
可传给 `build_loadout_from_config(setup.scenario_id, config)`。缺失则抛 `MissingFields`，不补训练默认值。
此操作只解析配置；实况起点依然消费已结算的绝对快照。

[主数据对照 JSON](examples/live_card_reference.json) 给出脚光+、国民的アイドル+、シュプレヒコール+、精神統一+
的 definition_id、费用、可选自定义和等级效果；它不是实机已选配置。
其中 selected_instance_id、selected_customize_ids、acquisition_phase 特意保留 null。
社区数据库数字 ID 与主数据 ID 不通用，命令一律使用主数据 ID。
例如精神統一的集中自定义升到 Lv2：customize_ids 写同一个 ID 两次，效果为总计 +3，不是 +1 再加 +3。
