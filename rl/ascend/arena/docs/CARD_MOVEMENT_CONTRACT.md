# 卡牌移区触发契约

2026-09-08，`arena-card-movement/1`。这是离线规则扩展；实况继续消费已结算的绝对观察，不因为观察到手牌而重新发动效果。

## 字段与最小 JSON

`Card.on_move` 可选；存在时必须指定 `destination: hand | hold` 和非空有序 `effects` 引用。它与 `effects`（出牌效果）、`condition`（出牌条件）、`after_play`（出牌落点）独立。

```json
{
  "namespace": "movement",
  "revision": "1",
  "synthetic": true,
  "effects": [
    {"id": "movement/focus", "operation": "concentration", "arguments": {"amount": 3}}
  ],
  "cards": [
    {
      "id": "movement/card",
      "name": "合成：入手获得集中",
      "effects": [],
      "on_move": {"destination": "hand", "effects": ["movement/focus"]}
    }
  ],
  "auditions": [
    {
      "id": "movement/exam",
      "turns": 2,
      "clear_score": 100,
      "colors": ["vocal", "vocal"],
      "deck": [{"card": "movement/card"}]
    }
  ]
}
```

编译为原生 `moveEffectTriggerType`、`moveProduceExamEffectIds`；数值与引用继续走共用机制注册表，不解析卡面文本、不按卡牌 ID 分支。

## 执行语义

- 只有卡牌实际进入指定区域时发动。抽牌、检索、生成/复制入手、保留及返回手牌共用入口；满手牌退回牌堆顶不视作进入手牌，同一区域请求不再重复触发。
- 卡牌先进入目标区域，再按定义顺序执行自身移区效果；搜索“保留中的卡”时包含刚进入保留的卡。保留溢出先按已配置规则解决；若新卡被直接弃置，它没有成功进入保留区。
- 效果使用引擎原有资源/伤害/搜索/成长处理器；移区本身不支付出牌费用、不计为出牌、不消耗玩家行动。效果明确要求自动使用卡牌时，仍沿用既有自动使用计数语义。
- 自身/搜索上下文指向发生移动的副本；嵌套抽牌/检索结束后恢复外层上下文。同名副本独立，每次离开后重新进入可以再次发动。
- 移区效果引发的中间选择，包括开场抽牌中的选择，使用已有 ContentExam 暂停、指令日志和确定性恢复。恢复不重复消费此前效果。递归过深明确报错，不静默丢弃后续效果。
- 已有环境移区 phase 分发保留；本阶段不补造一个主数据未确认的 Hold phase，也不以这次扩展证明全部 P 道具/卡片触发次序已经正确。

## 实证范围与未支持项

固定 master `571dbb62601e78998cddeacdbce3ea1bc672d7fc` 的 8 条卡牌变体具有非空移区效果，`moveEffectTriggerType` 为 Hand 或 Hold，`moveProduceExamTriggerIds` 均为空：輝きの到達点、理想に手が届く日まで（4 版本）、スーパーノヴァ、グランドフィナーレ、エキスパート。定义及卡面文字支持进入目标区域后执行所列效果这一最小语义。

[独立引擎 Effects DSL](https://github.com/surisuririsu/gakumas-tools/blob/master/packages/gakumas-data/Effects.md) 也区分进入手牌/保留之后的触发时机。此资料仅作分类交叉核对，未复制其实现；这些测试不是新增实机录像验证。

非空 `moveProduceExamTriggerIds`、其他目标区域继续明确拒绝，不能猜测条件列表与效果列表的配对/组合规则。自身移区效果与多个 P 道具、卡绑定触发之间的完整排序，以及批量移区/保留溢出的游戏时点，仍需相应实机前后帧对拍。准入报告表示有执行路径，不表示真实保真认证。

## 版本与兼容

内容 JSON 仍为 `arena-content/1`，新增可选字段；旧程序会明确拒绝它，不会静默丢字段。内容规则签名升级 `arena-content-rules/2`，编译 digest 随之改变；旧 ContentExam/ContentSession 的模拟日志快照不能冒充新规则重放，应保留旧版本运行环境或新开模拟会话。快照格式和恢复 API 不变。

`arena-live/1`、`arena-session/1`、submitted/uncertain 原始命令恢复与去重不变。本阶段不升级现有张量编码，也不声称旧特征已完整表达移区效果；RL agent 应按交接需求设计新的机制输入。
