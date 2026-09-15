# HIF センス考试实况阶段交付

> 后续 2026-09-08 非空状态和分类交付见 [ARENA_PASSIVE_UPDATE.md](ARENA_PASSIVE_UPDATE.md)。
> 本文保留原464项/v1编码的历史验收，不代表新示例 manifest；非空状态限制已部分解除。

2026-09-07。在既有 `codex/arena-live-bridge` 工作树继续，基点仍是
`ef2402958547b2050e873841b9ff5066a895b1a9`，保留上一阶段未提交改动。
本阶段只修改 Arena，没有操作游戏、Maa、PAUSE 或 adapter 文件；没有训练 RL 或重测通关率。
未新建 commit/push。已有调研来源与版本固定记录沿用 [来源审计](research/live_reference_sources.md)。

## adapter 可以接的入口

先读 [考试字段契约](LIVE_EXAM_CONTRACT.md) 和 [最小 JSON](examples/live_exam_minimal.json)。
这两份先于实现交出，现已更新成实际支持范围。`LiveBackend` 将奖励/咨询交给原 `PlanningBackend`，
将 exam/search/discard 交给 `ExamBackend`，使用原 `LiveSession` 调用顺序。

| 部分 | 已交付 | 当前边界 |
|---|---|---|
| HIF センス考试 | produce-007/008；完整手牌实例、强化/自定义、动态成长；当前体力/元气/集中/好调/绝好调/回合/出牌窗；card/end_turn | 稳定且已结算的决策点；非空附魔及部分复杂触发器返回 Inspect |
| 规则合法性 | 复用引擎费用、can_play_card、can_use_drink 与禁用检索；UI 和引擎掩码取交集 | 不用界面候选替代引擎合法性；不预测实机抽牌、触发和伤害结果 |
| 身份及消费 | run/exam/instance 稳定映射；换槽身份不变，新考试重建；实际绝对快照替换状态 | 事件仅审计；仅提交或动画不提前扣费，无法识别变体需补读 |
| 饮料与补选 | drink → 独立 search → card_select → 新手牌；独立 discard → card_select → 移牌回执 | 固定选一张；源区域完整；多选、随机选择与饮料溢出未绑定 |
| 共享编码 | 原 GakumasExamEnv 特征 + 已知掩码；训练 wrapper、manifest、补选 kind、绝好调/行动数 context | 旧 checkpoint 不兼容该新空间；没有训练新策略 |
| 公共恢复 | snapshot / restore、pending_command、command_state；恢复原 proposed/submitted/uncertain；历史结果/事件去重 | adapter 持久化日志和补读 UI；不执行输入，不重复询问策略；不静默迁移版本 |
| 模拟选择边界 | 共用区域与卡过滤器枚举全部目标，显式 resolver 可移动指定卡 | 旧 seeded 宏动作尚无通用暂停/续跑；不能当作已接通的交互轨迹 |

所有实况样例明确 synthetic。出牌样例故意采用两张同名、不同自定义卡，当前集中只能支付第二张；
按实际结果格式手工填写下一帧，再确认入账。结果不由 seeded runtime 生成。
考试 runtime 的 reset/step 和随机初始库存构建在测试中被设为一旦调用就失败。

## 版本及复现

- wire：`arena-live/1`，奖励/咨询保持原字段与语义。
- rules：`arena-rules/2`；规划编码仍 `arena-planning-observed/2`。
- 考试编码：`arena-exam-observed/1`；快照：`arena-session/1`。
- master：`571dbb62601e78998cddeacdbce3ea1bc672d7fc`，未重新拉取/覆盖数据。
- 本地虚拟环境沿用 Arena `.venv`；无 torch/SB3/fastapi 训练/API 依赖。

在 Arena 仓库运行：

```powershell
.venv/Scripts/python.exe scripts/demo_live_bridge.py
.venv/Scripts/python.exe scripts/demo_live_exam.py
.venv/Scripts/python.exe scripts/demo_live_exam_choices.py
.venv/Scripts/python.exe scripts/export_live_schema.py
.venv/Scripts/python.exe -m pytest tests -q -rs
```

产物：[正常出牌与 uncertain 恢复往返](examples/live_exam_recovery.json)、
[饮料/检索/弃牌往返](examples/live_exam_choices.json)、[编码 manifest](examples/live_exam_encoder_manifest.json)、
[恢复 schema](schemas/arena-session-v1.json)。例程均使用确定性的本地测试策略，不是专家或 RL 训练样本。
恢复例程包含保存 submitted/uncertain、JSON 序列化、新实例恢复、保留原命令并阻塞消费、补交确认、继续决策，
以及更早结果重发不回滚快照。

完整回归：**464 passed / 3 skipped，69.06 秒**。两项跳过因未安装可选 SB3，另一项因该 seed
没有可执行的考前准备动作；无 xfail。缺少 torch/fastapi 时，上游相关可选训练/API 模块按既有配置不收集，
本数字不代表这些可选功能已验收。原奖励/咨询测试与九段游戏录像回归均通过。

三个离线示例和 schema 导出全部成功；原 `arena-live-v1.json` 重新生成前后的 SHA256 完全一致。
本阶段改动模块 Ruff 检查及 `git diff --check` 通过。
考试示例 manifest SHA256 为 `03ed8355216d21a08e4b9d811d86a497cf052be2f7c197dfbe087c76250dd2b6`，
这里只记录该固定样例，实际调用以环境输出为准。

## 下一批最小实机证据

以下通过本文交回 adapter 采集；本 session 不操作游戏。

| 页面/前后状态 | 最小字段 | 用途 |
|---|---|---|
| 已结算普通考试页 | exam_id/stage、turn/max_turns/extra_turns、plays_used/remaining、当前属性、体力/最大体力、元气、集中、好调/绝好调 | 建立第一次可执行状态；明确 0 与未读 |
| 手牌卡面与详情 | 所有手牌实例、definition_id、强化、自定义和局内变化；同名两副本及换槽前后映射 | 校验费用与目标不会串卡；临时强化不能简化成永久基础变体 |
| 状态/P 道具完整展开 | 效果主数据 ID、当前剩余回合/次数、应用回合、非空附魔/预约/再演详情；明确空列表证据 | 判定是否落入首批支持范围；优先补齐真实存在的非空效果绑定 |
| 一次可支付卡前后 | 提交原命令、动画结束后的独立 observation、资源/行动数/手牌/弃牌变化、确认凭据 | 验证绝对快照消费，不把点击成功当游戏确认 |
| 饮料触发检索页 | 饮料 ID 与实例、消耗前后库存、提示对应 effect_id、源山札/弃牌多重集、所有候选实例 | 分开饮料消费与 card_select，不提前移动卡或多扣出牌次数 |
| 一次弃牌页前后 | 确切 effect_id、完整可选手牌、所选实例、确认后手牌/弃牌 | 验证补选不再次支付费用；源检索 limit=1 也不能默认选第一张 |
| submitted/uncertain 的复读 | adapter 保存的原 snapshot/command、较新 revision、能证明发生或未发生的页面证据 | 恢复原命令对账，不能将新提案当成旧事务结果 |

score/target_score/当前属性最终倍率暂为可选编码字段；若要核验预测分数，再提供这些值及具体前后分数。
本阶段验收不依赖伤害预测，也不声称通过实机端到端联调。
