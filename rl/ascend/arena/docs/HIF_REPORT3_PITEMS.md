# HIF 特殊 P 道具：Report 3 实现核对

2026-09-10。依据用户提供的 [Report 3](research/imports/hif_events_rl_report3_2026-09-09/hif_events_rl_report3_2026-09-09.md) 第 10、13 节及附录 A；主数据快照 `571dbb62601e78998cddeacdbce3ea1bc672d7fc`。考试效果执行继续使用 gktools golden。

## 已实现

| 能力 | 行为与证据 |
|---|---|
| 全配置覆盖 | 180 个配置、60 个名称/经济状态、171 条进化边，与报告的 ID、触发、效果列表、次数字段逐项一致。3 种计划分别展开各自战斗增益。 |
| 四种触发 | 公开课结束、进入咨询、慰问品结束、外出结束各覆盖 45 个配置；未触发时不授予战斗增益。 |
| 次数与间隔 | 消耗当前节点的触发预算后执行奖励，避免奖励递归重复触发。进化获得新节点预算；导出/恢复保存节点 ID、次数、间隔和历史。本次所有 180 条实际间隔均为 0，额外非零夹具验证仅匹配事件推进间隔。 |
| 下一场与永久累积 | 基础袋/第一次进化记录 `duration_scope=next_audition`；末级记录 `persistent`。一次实际触发追加一次效果。`complete_audition()` 在真正考试结算时消耗下一场效果；预览不消费。跨选拔/本战保留未消费效果和剩余触发预算。 |
| 进化选项 | 候选必须是当前节点的同计划合法子节点。4 子节点展示 3 个，3 子节点全部展示；策略选择具体进化。 |
| 黄袋饮料 | `p_rd-drink_set-produce_007-customize_item` 与 `p_rd-drink_set-all` 单独传入来源采样接口；每获得 1 瓶独立分发 GetProduceDrink，支援获取触发可串联。 |
| 卡片奖励与换卡 | 普通与高 SSR 权重来源保留不同 pool ID；指定未强化/强化奖励分别落 0/1。Select Change 先选择实例再选择替换候选，继承原卡强化，丢弃原定制，分发 ChangeProduceCard 而非获取。 |
| 自选删除/复制 | 使用策略目标选择。复制保留卡片属性与定制，创建新实例身份；唯一/Legend 不作为复制目标。 |
| 专用折扣 | 强化/删除折扣分别落 `shop_upgrade_discount`、`shop_delete_discount`，不影响卡片和饮料价格。 |
| 红色外出末级 | 按当前配置原始附魔执行固定元气 6；不把该末级特性赋给前级。全部 18 种 custom-item 附魔已由既有 golden 测试编译执行。 |

## 冲突取舍

1. 45 个慰问品配置复用 `p_trigger-end_present-for_nia_master`。旧实现按 ID 后缀拒绝 HIF，导致完全不触发。当前仅在 HIF 自定义道具解释器内移除这个历史标签限制；普通 NIA 道具规则保持原有语义。
2. 旧实现把“下一场”与“永久考试”效果都永久保存。本版分开持久性，避免前两级效果在后续每场重复领取。
3. 旧实现把 Select 删除/复制当随机，把进化 4 个子节点全展示，把所有饮料来源交给同一强弱分层抽样。以上均已修正。
4. Select Change 继承原卡强化优先采用报告引用的官方说明。来源 ID 的 `upgrade_0` 不解释为强制把原来的 `+` 卡降级。

## 未识别概率与替换接口

主数据没有提供黄袋特定池的完整成员和权重、高 SSR 来源概率、4 选 3 展示权重。默认训练可运行替代模型会明确记录 `evidence=unknown`、`membership_known=false` 和含 `placeholder` 的版本名；**这些不是实机概率，也不代表普通池与特定池真实成员相同**。不能用该默认模型评估未知池之间的真实收益差异。

- `runtime.customize_item_reward_selector(request)`：输入 `pool_id`、`resource_type`、`count`、`replace`、`legal_candidates`、`effect_id`、`customize_item_id`、`pick_range`；返回 `resource_ids`、`model`、`evidence`，可选 `membership_known`。返回 ID 必须属于合法宇宙，最多返回请求数量；当前合法池不足允许缺额/空池，并记录 `empty_reason`。未知 ID、超量或不允许的重复报错，不悄悄回退。Select 奖励可主动放弃；头部事件成本不因此撤销。
- `runtime.customize_item_offer_selector(request)`：输入父节点、完整合法子节点和展示数量；返回 3 个不同合法 `item_ids` 及模型来源。
- `customize_items.export()/restore()`：保存已发生的候选、奖励来源、触发次数、间隔和效果消耗历史；不公开未来随机数。

## 验证

`python -m pytest tests/test_hif_report3_pitems.py -q`：**14 passed**。覆盖 180 节点实际触发/上限/效果期限、主数据对照、进化合法性、黄袋双来源、非法配置拒绝、SC 强化继承、删除复制自选、折扣隔离、选拔→本战继承、非零间隔恢复。既有 `test_produce_golden.py` 包含全部 18 类自定义道具附魔的 golden 执行覆盖。
