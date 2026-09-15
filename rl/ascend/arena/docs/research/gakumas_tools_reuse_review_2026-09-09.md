# gakumas-tools 复用调查与决定

结论：这个项目已经具备我们大部分局内效果和模拟基础设施。此前仅拿它做了局部数值/改造对照，利用范围偏窄。本次实际读源码、导出规则、运行测试后，按用户要求，将其固定版本直接作为 Arena 当前局内 golden。

来源为 [gakumas-tools](https://github.com/surisuririsu/gakumas-tools/tree/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5)，核对日期 2026-09-09；[落地接口与使用方法](../ARENA_GOLDEN_ENGINE.md)。

## 图片之外有什么

网站 [图鉴](https://gktools.ris.moe/zh-Hans/dex/reference/skill-cards) 的显示方式不代表底层没有结构化规则。`gakumas-data/csv` 生成 `json`；`data/skillCards.js` 等把 DSL 解析为效果树，交给引擎执行。[数据包源码](https://github.com/surisuririsu/gakumas-tools/tree/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/packages/gakumas-data)。

实际得到 870 技能卡、484 P 道具、28 饮料、111 改造、180 舞台。不是从截图 OCR 推测，而是读取原始字段。导出的每条记录保留原始 DSL 与解析树，费用、条件、重复次数、触发阶段、目标筛选、持续时间、成长补丁都能查。[导出 JSON](../../data/reference/gakumas_tools_effects.json)。

例如「夏夜に咲く思い出」的正文除移除麻烦与追加行动，还注册 `cardUsed` 监听；其 `effectCounter` 独立计数，每第五次使用时加分。`EffectManager` 复制计数条件快照，说明 `%5==4` 判断读的是自增前的值，不能直接翻译成第四次发动。

「脚光+」还先检查好调≤20，只有满足时才递增自己的计数。这个机制比“全局出牌数取模”复杂，也不能简化成一个全局偏移。

## 能直接用与需要接线的部分

| 部分 | 核对到的实现 | Arena 的使用方式 |
|---|---|---|
| 效果数据 | 卡、饮料、P 道具、条件、费用、改造补丁、舞台 DSL | 已 vendor；作为当前效果 golden；查询与导出 |
| 局内结算 | StageEngine；Buff/Card/Effect/TurnManager；Evaluator/Executor；三种计划 | 直接运行原始代码，继承其结算行为 |
| 手动操作 | ManualStrategy 三类中间选择与逐卡决策 | 包装为 Python act/choose；用完整答案序列恢复 |
| 模拟与调试 | HeuristicStrategy、StagePlayer、逐段日志、图表数据、固定种子回归 | 已接整局 rollout 与日志；524 个存量样例锁定 |
| HIF 评级 | `gakumas-tools/utils/hif.js`：Round1/2分数分段、明星性增益与目标评级计算 | 可作为外层评级规则参考；不是 HIF 逐日培育引擎 |
| 属性倍率 | contest 分赛季公式；非 contest/enterPercents 可直接输入显示倍率 | HIF 先用明确输入的倍率；不套用竞技场公式 |
| 其他工具 | 回忆概率/抽选、体力来源计算、图鉴组件、排练数字修复、ONNX 图像分类 | 有复用价值；本次只接引擎/数据，未接 OCR 或账号服务 |
| 培育链 | 104 条 produce 道具元数据，但 effects 为空；没有完整支援卡事件/日程运行时 | 保留现有 HIF 外层，后续把已实现链路映射进 golden 初始状态 |

HIF `hif.js` 的评级分段并不是考试每一击分数的倍率公式。两者需分开使用。用户截图只展示 Round1 完成，也不能用它计算最终 HIF 评级。

## 实际跑了什么

- 原始和 vendored `tests/run.mjs`：524/524 与仓库存量分数一致。
- `scripts/validate-data.mjs`：0 DSL 引用错误。
- `tests/stamina.test.mjs` 与 `tests/rehearsalRecovery.test.mjs`：39 通过。
- 覆盖统计：舞台129/153，技能卡805/870，局内P道具334/380，可达改造107/111。该统计只表示样例编成包含实体，不证明每个条件都触发。
- 两条截图计数隔离探针：夏夜 `[12,17,22,27]` 与上游一致；脚光上游 `[18,20,22,24,26,28]`，截图重建为 `[19,21,23,25,27,29]`。这是人工设置阶段状态的探针，不是完整录像回放，见 [原始结果](gakumas_tools_reuse_audit_2026-09-09.json)。

用户已决定先采用上游 golden，因此保留脚光差异而不修改 vendored 行为。原始样例主要由引擎捕获分数，用途是防回归，不能描述为实机标注集。

## 复用时发现的工程边界

上游 `resetRand` 控制模块级 RNG；仅保存 state 数组不等于保存随机数位置。Arena 当前通过独立进程及历史重放恢复，保留原始随机语义。单步性能优化不在这次规则迁移中混做。

上游 `IdolConfig` 按其编成规则去重唯一卡与道具；`IdolStageConfig` 会补默认卡组。我们输入的是它的完整编成配置，不偷偷把 HIF 当前牌库当成同一种数据。原生 master ID、上游数字 ID、实际卡实例必须分别表示。

原始 `StageEngine.executeDecision` 接卡/结束回合，没有库存饮料动作；但所有28条饮料已有可执行 AST。Arena 补上库存与动作入口，效果复用原实现，明确记录为包装扩展。

BSD-3-Clause 文件及版权声明随源码保留。游戏图片未复制；上游源未改写。完整源码指纹在 [PROVENANCE](../../gakumas_arena/_vendor/gakumas_tools/PROVENANCE.json)。
