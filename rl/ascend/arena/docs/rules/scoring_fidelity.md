# 核心结算管线审计

> 2026-09-08后续实施：集中强化现作用于集中出分贡献，好印象强化现只作用于自然结算；状态再次获得、阶段和来源也有修正。最新结果为17项参考探针符合、全套623通过／3跳过，见 [规则交付](../ARENA_RULE_ALIGNMENT_UPDATE.md)。下文是09-07审计记录，不能覆盖新 [行为契约](../ENGINE_RULE_CONTRACT.md)。

2026-09-07，基于 ef24029。范围是 `simulation/exam/scoring.py` 与 runtime 的主结算调用，
不是全部 107 种效果的最终认证。来源沿用 [lesson_exam_engine.md](lesson_exam_engine.md) §4/5/6/15、
主数据 ExamSetting，以及 `tests/gakumas_rl/fixtures/recorded_games/` 中保留来源链接的九段录像。

| 环节 | 当前实现与核对 | 结论 |
|---|---|---|
| 正增量 | ceil_int 带 1e-9 浮点容差；非正值归零 | 核对核心路径；极端溢出/所有复合效果尚未全审 |
| 元气 | _gain_resource 使用 round_genki，默认 floor，可配置 ceil | 13.9→13 独立断言；缺不同增减叠加的新实机边界样本 |
| 集中/热意进入基础值 | _resolve_lesson_effect_value 的 S1 | 文档列出的常见向量通过；复合集中倍率先合并还是分别取整仍是 A2 |
| 好调/绝好调 | good_condition_permil：无好调=1000；好调=1500；同时有绝好调则每个好调剩余回合+100 | 好调6+绝好调→2100；绝好调自身持续时间不乘进倍率 |
| S2 倍率组 | scale_by_permils 将好调、指针、上升/下降等相乘成整数分数后 **一次 ceil** | 与已有 §5.1 engine 路径一致；不能把调研里“每步 ceil”理解为每个标量都 ceil，暂无证据改这个分组 |
| S3 属性倍率 | S2 后单独 apply_permil_ceil；倍率转整数千分比 | 9×1.5→14；14×1.75→25，禁止合并成一次 ceil 得到 24 |
| 绝好调状态 A9 | 叠加剩余回合、按回合减少，状态槽显示总剩余回合 | 已修：录像 turn8 6+4=10；另一断言 4+4−1=7，耗尽移除 |
| 回合衰减 | fresh_modifier_no_decay 沿用获得时机语义，已存在状态延长保留原获得回合 | 九段既有录像通过；新的 HIF 触发排序仍需验证 |
| HIF 明星性 | 现有线性/分段近似配置 | 未改 A3/A4，缺结果分数与加成面板证据 |

独立数值向量在 `tests/gakumas_rl/test_scoring_vectors.py`：14、25、49、66 等结果来自既有规则文档的
游戏/参考实现记录，不从引擎自己算出答案再断言。回忆费用测试另外确认同一张シュプレ+ 的集中费用
在 `cost_lesson_buff_reduce-1` 自定义下为 2→1。

原 `kuramotochina_ssr2_exam_final.jsonl` 的 strict xfail 在修复后 XPASS，随后只移除了 xfail 标记；
其原始预期值、出牌序列与历史卡面覆盖全部保留。现在九段录像均为正常通过。

保留待办：集中复合倍率、好印象是否吃集中/热意的边界、消耗减半与增加同时存在、体力伤害是否穿元气、
HIF 持续效果次序和更广的多级自定义组合。现有 ScoringRules 开关没有被通关率驱动修改。

在线参考交叉核对：gakumas-tools `6c3d006` 的
[resolveScore](https://github.com/surisuririsu/gakumas-tools/blob/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/packages/gakumas-engine/engine/Executor/resolvers.js)
同样在基础值、组合倍率、属性倍率三个位置取整，没有在每次标量乘法后取整。
这是独立实现的佐证，不替代新机制的实机边界样本。精神統一+ 的二级集中/元气自定义总量
已依据原始主数据与该库当前等级 patch 修复并补回归，详见 [来源审计](../research/live_reference_sources.md)。

新增录像请沿用 `recorded_game_harness.py` 和现有 JSONL：setup 中注明来源/数据版本、卡面/自定义，
每个动作以稳定帧前后作为边界。动画预览值不作分数或体力的真值。
