# HIF 事件闭包、Switch 与奖励控制

适用规则：`hif-report3/2`。主入口是 `create_hif_training_produce`；本文件补充事件执行及奖励选项的可执行边界。考试效果继续使用 golden。

## 已执行验证的事件闭包

`tests/test_hif_event_closure.py` 逐条执行当前主数据的 511 条支援事件，覆盖 `produce-007` / `produce-008` × Plan1 / Plan2 / Plan3，共 3,066 条执行路径。验证实际资源变化，未只统计效果名称。

实际闭包有 9 类：固定奖励、强化、换卡、删卡、Vo / Da / Vi 固定加值、P 点固定加值、体力固定回复。固定属性不乘成长率；仅支援来源应用支援事件奖励修正。装备、支援等级、事件编号及前置完成状态继续决定可达性。

当前 HIF 92 条外出/课堂事件共有 72 个选项；结合 511 条支援事件，所有实际可达选项的 `produceEffectFireStep` 都为 0，且没有 `stepId/successStepId/failStepId` 非事件跳转。其他剧本存在的日程跳转不属于本次 HIF 闭包，也不被声称已模拟。后续主数据增加该类引用会使测试失败，要求重新审计。

固定事件的 `alwaysSuccessful` 优先，概率单位为 Permyriad / 10000。头部体力、P 点、眠气成本先支付；99 张时含必付眠气的选项不可选。后期课堂换卡保留原强化阶段，触发 Change 而非 Get；空来源池保持原卡。随机支援换卡同样绑定来源池，并保留撤回所需原卡。复制采用独立副本，显式 `instance_id` 分配新 ID，嵌套元数据不共享。

## 支援事件发生模型

支援事件的固定效果来自主数据；事件出现的基准概率及竞争分布没有公开完整权重。以下都是可配置的规划模型，不是服务器概率：

| 配置 | 行为 |
|---|---|
| `support_event_probability` | 默认 0.25；每天通过一次基准概率门槛，再选最多一个合法事件 |
| `support_event_probability_up_permyriad` | 总概率加值，按 /10000；夹在 0..1 |
| `support_event_days` | 可选、从 0 开始的可触发日索引 |
| `support_event_weights` | 以事件 ID 或支援卡 ID 配置竞争权重；0 表示排除 |
| `support_event_probabilities` | 逐事件基准概率；启用后独立判定候选，再至多选择一个 |
| `support_event_probability_up_permyriad_by_event` / `support_event_probability_up_permyriad_by_card` | 逐事件、逐支援卡的配置修正 |

每次采样写入 `runtime.events.occurrence_history`，包括模型、合法候选、概率、权重与选择结果。合法事件在每次抽样时重新计算；抽样不把事件提前标记完成。负权重及非有限数值直接拒绝。

## 25% 跳过与 50% 休息

共享 ProduceSetting 有 `stepSkipStaminaRecoveryPermil=250`，但当前 `ProduceAdvType_StepSkip` 的明确行属于 NIA；这不能证明 HIF 日常菜单有该按钮。

因此默认 HIF 菜单维持有证据的动作。模拟/重放可传 `research_config={'enable_step_skip': True}`：非考试、非中场的普通日开放 `step_skip`，回复 `floor(max_stamina*0.25)`、消耗一天，不能在奖励/咨询/重试等嵌套决策中执行，不触发 StartRefresh，也不增加休息次数。可用性假设写入 `step_skip_availability_model`。常规休息仍走主数据 50% 回复及其触发系统。

## 技能卡 Switch

复用已有 `IdolLoadout.produce_card_conversions` 和主数据 `ProduceCardConversion`，没有新增局内转换按钮。21 对转换的 PLv 条件沿用现有 resolver。

原入口的 `loadout.produce_card_conversion_after_ids` 继续有效。推荐入口另支持：

```python
research_config={
    'card_switches': {'p_card-01-act-2_002': True},
}
```

字典键为转换前 ID，值 True / False；显式 False 可以关闭 loadout 中已有设置。开始时深拷贝设置；已开始的培育不受调用方随后修改字典影响。选拔记忆保存设置并传到本战。

奖励池、来源权重、固定获得及初始卡组使用同一有效 ID；转换前后的同系列不会同时入池。已持有的重複不可卡仍受原有过滤约束，Switch 不绕过该约束。未升级 / 升级身份及副本来源保留，主数据本身不修改。

[官方 Switch 帮助](../../../design/hif-mechanics-20260909/official-ProduceCardConvert.html) 明确排除“局内随机生成的卡”和“触发条件指定的卡”；golden 的随机生成及 HIF 回忆条件目标因此仍按原定义处理。

## 奖励重抽与候选除去

公开课通过公开动作提供 `card_reward_reroll`、`card_reward_exclude_N`。课堂、外出、慰问品、Select 换卡及特殊 P 道具的 Select 奖励通过 `produce_choice_selector` 提供相同控制。选项带 `control='reroll'` 或 `control='exclude'`；主动放弃带 `skip=True`。

重抽始终保留原 `pool_id`、资源类型、升级约束及对应来源配置。次数来自全局 `card_select_reroll_count_bonus - card_reward_rerolls_used`，多个来源共享余额。除去次数为整数（主数据 +2 就是 +2），不除以 1000；不会删除已持有卡。当前规划模型将所选候选 ID 加入本次培育奖励排除集合，后续来源也过滤，使用次数记入 `excludes_used`。排除作用域与各来源按钮可用范围尚无完整公开证据，均作为模型声明，不能解读为实机验证结果。

可逐来源关闭不适合的操作：

```python
research_config={'pools': {
    'hif_open_lesson:produce-008:0': {
        'weights': {'p_card-01-men-1_034': 1},
        'upgrade_probability': 0,
        'allow_reroll': True,
        'allow_exclude': False,
    },
}}
```

所有随机获得使用来源采样后自动结算；不会错误弹出玩家选卡/重抽/除去。Select 奖励可主动放弃；空池不从其他池补卡。配置权重在 Switch 后按有效 ID 合并，未知成员或非法权重报错；已持有 no-dup、PLv/计划限制导致的空池合法。

以上控制模型与 Switch 快照随 `sampling_scope` 输出。咨询商店刷新和中场服务刷新沿用各自系统，不消耗技能卡奖励重抽次数。

## 与技能卡支援的接口区别

[官方技能卡支援帮助](../../../design/hif-mechanics-20260909/official-lesson-support.html) 说明：效果在课程/考试中概率触发，仅当回合临时提升 1 强化阶段，上限 3，条件与概率依支援卡而异。`SupportCardProduceCardUpgradeProbabilityUp` 不加入永久奖励的 `upgrade_probability`。相关临时强化由 golden 桥处理，事件发生概率与奖励卡升级概率是独立系统。

## 回归入口

### 运行时副本隔离与持久 ID

整套回归揭示并确定复现了一个进程共享数据问题：低层 `ProduceRuntime.reset` 原来只拷贝初始牌组列表，部分卡片仍直接引用主数据；向运行时副本写入 `instance_id` 会污染共享 TableIndex，后续环境重复获得同一卡时带上重复显式 ID。

现已在初始、获得、升级、换卡及选拔记忆还原边界逐卡深拷贝。逐卡复制也避免重复主数据引用在新列表中仍指向同一对象。golden 桥首次看到无 ID 副本时，通过环境的 `card_instance_serial` 分配并写回稳定 ID；后续删卡、重排、下一场考试及跨剧本继承不会重新按位置命名。计数器单调递增、预留已有显式编号，并随 checkpoint / 选拔记忆保存，删掉旧卡后不复用其 ID。用户传入的显式重复 ID 仍严格报错。

新增 `tests/test_produce_card_identity.py` 覆盖上述七类边界。最小顺序复现（修前第二条报 `entry.cards[29].instance_id` 重复，修后均通过）：

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest tests/test_hif_report3_events.py::test_select_delete_uses_policy_target_not_random_target tests/test_produce_golden.py::test_selection_then_final_carry_runs_through_golden -q
```

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest tests/test_produce_card_identity.py tests/test_hif_event_closure.py tests/test_hif_reward_controls.py tests/test_hif_report3_events.py tests/test_hif_report3_profile.py tests/test_hif_report3_reward_boundaries.py -q
```

这些测试仅执行规则、模拟考试和资源断言，不启动 RL 训练或游戏。
