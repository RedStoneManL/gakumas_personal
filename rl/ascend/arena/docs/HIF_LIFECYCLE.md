# HIF 考试、重试与终局

实现入口为 `gakumas_arena/produce/lifecycle.py` 的 `HifProduceLifecycle`。排名、两轮合计和达标奖励由考试适配器计算；生命周期只消费其 `rank`、`cleared` 和分数，不再实现另一套换算。

## 状态与结算

选拔包含三个考试槽，本战包含两个。每个槽可以保留多次尝试记录，只接受最新的一次；重试不是“历史最高分”。接受失败结果进入 `failed`，接受中途成功结果回到 `active`，接受最后一次成功结果进入 `selection_clear`、`final_clear` 或 `prima_stella`。未接受的分数不加进总分、スター性或晋级记录。

每个剧本的 `ProduceSetting.continueCount=3`，在该剧本所有考试间共用。本战是从选拔回忆开始的一次新培育，重新拥有该剧本的配额。`retry_ticket_count=None` 明确表示 RL 假设外部重试券充足；配置整数余额和 `free_retries_remaining` 后，先扣免费次数，再扣一张券。每日账户重置、实际券购买和跨账户余额不由 Arena 执行。

重试锚点建立在考试所有前置触发之前。重试恢复体力、饮料、牌组、道具与支援触发计数、一次性考试增益以及其他培育执行状态，保留已经扣除的一次继续次数，并沿当前 RNG 流抽取新考试种子。Round 2 的锚点位于中场之后，不能退回 Round 1 或撤销中场购买。接受当前尝试后清除锚点。历史尝试留在审计记录中；账号成就的累计暂以尝试记录提供，不混入游戏效果触发计数。

## 失败、放弃与保存

| 操作 | 后续状态 | 保留的 Arena 产物 | 游戏回忆资格 |
|---|---|---|---|
| 接受选拔失败 | `failed` | 终局摘要、卡组、道具、属性、接受的考试、全部尝试 | 不生成选拔回忆 |
| 接受本战失败 | `failed` | 同上，保留上轮已接受成绩 | 与独立的最终回忆生成器对接；诊断产物本身不是游戏回忆 |
| 放弃培育 | `abandoned` | 同上；未接受尝试标记丢弃 | 不生成回忆、不计“挑战培育”次数 |
| 保存并恢复 | 原决策状态 | JSON checkpoint，包括隐藏重试锚点和 RNG | 不算失败或放弃 |
| 选拔三场全部接受成功 | `selection_clear` | 同上以及合法选拔回忆 | 可用于开始本战 |

`terminal_artifact()` 返回诊断和 RL 终局结果，不会把失败卡组伪装成可入场的选拔回忆。官方资格由 `require_selection_memory()` 检查；旧底层 `runtime.hif.export_selection_memory()` 仍可用于手工夹具，调用者应把它当调试快照。

中断只允许培育决策边界；效果链或考试执行中拒绝保存。checkpoint 会保存重试锚点、次数、钱包和尝试日志；恢复时先验证版本、配置、RNG、道具及生命周期状态，再提交。公开观察只暴露当前结果和剩余次数，不包含锚点或 RNG。

## 集成钩子

1. `HifProduceLifecycle(run, config)` 绑定 `run.lifecycle` 和 `runtime.hif_lifecycle`。
2. `runtime._run_audition` 的所有前置触发之前调用 `before_exam(stage_type)`；沿用 runtime 原有“一次重试先扣一次 continue”的逻辑。
3. golden 完成一次考试及 carry 后调用 `after_attempt(result)`。
4. runtime 接受结果、应用奖励并创建终局摘要后调用 `accepted(result)`。
5. 对一次 `runtime.step` 使用 `with lifecycle.atomic_step():`。异常恢复本步前的运行状态、RNG、日志和重试次数，异常仍抛给调用者；外部回调自己的可变状态不被序列化。
6. 公开动作的重试可用性使用 `can_retry()`；放弃调用 `abandon(reason=...)`，公开字段调用 `public_state()`。

## 依据与保留的约定

- 当前官方[试验流程帮助](https://stat.game-gakuen-idolmaster.jp/html/help/c6b4e29fae184f1405f50b3bf53c1b74c2dcff351fa8d56e35551e779be2dc60/index.html)说明同条件重试、每次培育最多三次，以及每日一次免费、其后需券。旧通用帮助中的排名阈值不套用 HIF，HIF 排名由独立数值配置决定。
- 官方[选拔回忆帮助](https://stat.game-gakuen-idolmaster.jp/html/help/2bab14e7b7e2f34cf831f6ba171377e8e07c1e15e4fbbb6f477083ecbcdfb25b/index.html)明确选拔失败不生成该回忆，并区分可继承内容与体力、饮料、P 点。
- 官方[菜单帮助](https://stat.game-gakuen-idolmaster.jp/html/help/6a0caafaabbc2c95612be9fd206e9ccc72c88e72accafefa3d37800b5a88975c/index.html)说明保存中断和放弃；放弃不获得回忆、不退 AP，不计挑战次数。
- 原网页缓存位于 `docs/research/hif_lifecycle/`，抓取日期 2026-09-10。`restore-pre-exam-gameplay; advance-RNG/v1` 是对“同条件再挑战”的可测试执行约定；精确服务器随机种子协议不在公开资料中，Arena 明示采用连续本地 RNG 流。

验证：`pytest tests/test_hif_lifecycle.py tests/test_produce_checkpoint.py`。包含饮料和一次性效果恢复、三次共享额度、成功后重试成失败、免费与券钱包、第二轮独立锚点、放弃、失败产物、异常原子回滚及带重试锚点的 JSON 恢复。
