# 待验证 / 待办清单（持续更新）

> **2026-09-09 新基准优先：**按用户决定，gakumas-tools `6c3d006` 的源码与数据成为当前局内 golden。已直接纳入 Arena，并提供 `create_exam`、逐步出牌/饮料、连续选牌、快照恢复及原始启发式 rollout；524 个上游回归不变。详见 [golden 接入](ARENA_GOLDEN_ENGINE.md)。旧 Gym/ContentExam/HIF内部考试继续作为兼容路径，下一步迁移其ID/实例/被动初始状态到新接口；不能声称现有调用已全部切换。实机差异留档，不阻塞当前采用上游规则。

> **HIF 新图证：**34张图确认本战Round1 508647分及第1–7天培育，分项算术闭合，见 [整理](research/produce_score_photo_review_2026-09-08.md)。夏夜的独立计数在新golden探针一致；脚光隔离差异留档，不以旧全局计数补丁替代上游实现。

> **触发排序先用默认，精确校准暂缓**：按用户2026-09-08最新要求，同阶段附魔监听者采用稳定ID字典序，见 [政策与交付](ARENA_TRIGGER_ORDER_UPDATE.md)。[佑芽7张日志](research/riceball_photo_review_2026-09-08.md) 的最终元气17对20差异保留为跨阶段校准案例，不阻塞HIF基础建设，不要求专门穷举道具排列。饭团＋首卡元气0→2的计数证据继续有效；其他模式的共用机制样本不扩大本阶段建设范围。

> **当前范围：HIF。** 按用户最新要求，偶像之路专属麻烦（例如パニック）和偏门跨模式组合暂缓，不阻塞当前HIF建设。先采 [真实卡牌操作版](RULE_ALIGNMENT_REAL_CARD_RECIPES.md) 的A/B/C，其他组仅在已有HIF编成中复现；原始全机制边界保留历史记录。

> **2026-09-08 规则实施优先**：[交付记录](ARENA_RULE_ALIGNMENT_UPDATE.md) 与 [行为契约](ENGINE_RULE_CONTRACT.md) 为当前状态。集中／好印象强化、批次资格、卡内条件、费用事件、准备自动使用、再演首次注册、阶段顺序和行动数寿命已按报告修正。17项探针全部符合参考；历史4一致／13差异不再描述当前实现。剩余政策及证据缺口见 [实机采样清单](RULE_ALIGNMENT_LOG_REQUESTS.md)，不能据合成结果宣称1:1。

> **2026-09-08 RL 交接及继续建设**：模型/奖励/本地与 Colab 选型交由独立 agent，见 [RL_DESIGN_HANDOFF.md](RL_DESIGN_HANDOFF.md)。完整 Arena 的当前设计与阶段验收见 [ARENA_COMPLETION_ROADMAP.md](ARENA_COMPLETION_ROADMAP.md)。卡牌自身进入手牌/保留时的效果已接入通用处理器，完整排序仍需实机证据；字段与迁移见 [CARD_MOVEMENT_CONTRACT.md](CARD_MOVEMENT_CONTRACT.md)。

> **2026-09-08 数据驱动基础阶段**：[创作指南](CONTENT_AUTHORING.md) 与 [交付记录](ARENA_CONTENT_UPDATE.md) 为最新状态。
> JSON/YAML 卡牌、效果、事件、训练、试镜及流程图已可执行；多选、连续选择、暂停恢复和共用考试编码已实现。
> 新被动绑定采用按机制的 passive/2，旧六个 ID 入口保留兼容。以下旧记录中“宏动作暂无通用暂停”等不再适用于 ContentExam。
> 仍待：官方历史路线逐步迁移内容包、未验证机制的实机对拍、预约/再演/卡绑定等实况字段语义、完整自创流程训练适配器。

> **2026-09-08 被动阶段**：四个 HIF 回忆、願いの力、勇気の標基础版已支持观察绑定；
> 公共缺项分类与考试编码v2见 [新交付](ARENA_PASSIVE_UPDATE.md)。预约/再演、卡自身附魔和
> StartPlay 的离线阶段混用现已修正为回合开始后；完整实况绑定仍按现有准入范围判断，历史片段不等于当前完整状态。

> **考试阶段更新**：[ARENA_EXAM_UPDATE.md](ARENA_EXAM_UPDATE.md) 记录已实现的 HIF センス观察绑定、
> 饮料/固定选一张检索与弃牌、arena-session/1 公共恢复。本阶段只验收合成数据，未实机联调。
> 下一步：非空附魔与更多持续效果、饮料溢出/多选、模拟宏动作的通用暂停续跑，以及 adapter 实测字段对拍。
> 以下 433 项与 HIF 胜率是上阶段记录，本阶段不训练或优化通关率。

> **2026-09-07 本轮状态优先**（本地 codex/arena-live-bridge，见 [交付记录](ARENA_ENGINE_UPDATE.md)）：
> A9 已修，九段录像全通过；B1 动作 taxonomy 已补并版本化；B2/B6 的初/HIF 课程奖励与咨询模拟闭环已补。
> B7 的延迟入组/source/customization 已接通；HIF 延迟阶段映射仍是可配置推断。
> 实况首版支持奖励和咨询购买，其他中间选择/考试绑定未完成；A1 核心审计已写出但非全量认证，A2/A3/A4/B5 仍待样本。
> HIF 0–9 基线仍 0/10，全量 433 passed / 3 skipped / 0 xfailed。seed=5 首场 520525 的高分须追加验证。
> 已用外部源码交叉核对并修正多级自定义累计错误；版本化数据源和四张目标卡映射见 [来源审计](research/live_reference_sources.md)。
> 下文未改写的表格是原交接记录，不能将其中“未写/未实现”当成本轮状态。


> 引擎能跑通 ≠ 数值正确。本页记录所有「代码里已做出选择但尚未用实机验证」的点，以及下一步的工作项。
> 代码中对应位置以 `TODO(HIF-verify)` / `ScoringRules` 开关标注。

## A. 数值保真（最高优先）

| # | 项目 | 现状 | 验证方式 |
|---|------|------|----------|
| A1 | 分数/参数取整（每步 ceil）、元気 floor、好調/絶好調整数化 | **部分完成**：`ScoringRules` 开关 + 9 段实机录像夹具（`tests/gakumas_rl/fixtures/recorded_games/`，8 通过 1 xfail）。审计 agent 被额度中断，`docs/rules/scoring_fidelity.md` **未写出** | 继续按 `docs/rules/lesson_exam_engine.md` §5/§15 逐项核对；补写该文档 |
| A2 | 集中倍率与好調百分比的 ceil 先后 | seesaawiki 标「検証の必要あり」 | 实机录像逐回合对拍 |
| A3 | HIF 選抜分数 → スター性 换算（14k/150k/390k 线性分段） | 推断 | 实机记录 選抜 分数与获得スター性 |
| A4 | スター性 → 考试分数加成曲线（线性到 1335 时 +25%） | 推断 | 实机记录不同スター性下同牌组分数 |
| A5 | 公開レッスン SP 概率（0.15 基础）与副属性选择 | 推断 | 实机统计 |
| A6 | 本戦 NPC 分数生成（静态/采样） | `isStaticNpcScore` 字段 + 采样模式 | 实机记录对手分数分布 |
| A7 | 2025-10-31 最终考试分数上限等代码侧结算改动 | 需版本化配置 | 对照官方公告 + 社区计算器 |
| A8 | ~~考试分数爆炸~~ **已修复**：考试分数爆炸：`i_card-shro-3-012`（固有卡 `p_card-03-ido-3_135`）選抜1 中位 27.7 万、单局 5,435 万；`i_card-kcna-3-005`（`p_card-01-ido-3_097`）中位 8.7 万；`i_card-ttmr-3-000` 单局 7,247 万。同一预设 選抜1 分数跨 4 个数量级（`docs/loadouts.md` §5） | 根因：スコアボーナス 在 `ProduceExamBattleScoreConfig` 查表结果之外又乘了「属性/基准线」与「属性/期望属性」两个比例，高属性下叠成 ×70（`runtime.py:_effective_score_bonus_multiplier`）。修复后 選抜1 分数回到 9k–32k | 与社区计算器对拍最终分数 |

| A9 | **絶好調 建模**：实机录像（倉本千奈 SSR-2 最終試験 turn8）显示 絶好調 是回合型状态、同种叠加为**回合数相加**（残6 + 応援4 = 10）；当前引擎按**层数**建模（每实例 1 层，`ExamParameterBuffMultiplePerTurnReduce` 消耗 1 层，`_sync_effect_resources` 数实例个数） | 录像夹具 `kuramotochina_ssr2_exam_final.jsonl` 已标 xfail 记录该差异；上游单测 `test_exam_runtime_parameter_buff_multiple_per_turn_reduce_consumes_one_stack` 编码的是层数语义 | 改为回合型需同时改 `_sync_effect_resources`、分数公式（§5 絶好調 = 1.5 + 0.1×好調残回合）、观测特征与该单测；**优先级最高，因为它同时影响分数公式** |

## B. 引擎能力

- B1 `EffectTaxonomy.action_types` 未加入 HIF 动作（one-hot 全零），旧 checkpoint 兼容 vs 特征表达力，需要决定。
- B2 HIF 相談（商店）未作为每周动作暴露。
- B3 `p_rd-item_set-produce_008-end_mid_audition-all` 在 dump 中无可解析的奖励池。
- ~~B4 `RemainingTurn` 触发条件 ≥/≤ 方向~~ **已修复**：改为「以内 = ≤」（`triggers/field_status.py`）。
- B5 隐藏概率：SP 課程率、事件权重、shop 刷新、回合颜色分布、`ProduceCardRandomPool` 权重——全部为近似，需实测拟合。
- B6 课程结束不发技能卡：初 / H.I.F 的课程（含公開レッスン）都没有卡片奖励，卡组整局停在 13–15 张（`docs/rules/produce_loop.md` §91 写明应 3 选 1 得 1 张）。这是 H.I.F 選抜2（border ≈ 49.8k）过不了的主因，见 `docs/loadouts.md` §6。
- ~~B7~~ **已完成**（`tests/gakumas_rl/test_idol_kit.py`）：原问题为 `idol_config.py` 不读取 `IdolCard.idolCardPotentialId` / `idolCardPotentialProduceSkillId` / `idolCardPrimaStellaProduceSkillId`（ポテンシャル、プリマステラ 技能），也没有培育メモリー的 loadout 字段。现已全部读取，并修复了才能開花技能重复登记（同一技能 Lv1/Lv2 都注册，而 `ProduceSkill` 每级数值是总量）。遗留两个 runtime hook 见 `docs/loadouts.md` §7.5。
  **已处理**（`docs/loadouts.md` §7）：`build_idol_loadout(potential_level=, prima_stella_level=, memories=)` 读取 `IdolCardPotential(+ProduceSkill)` / `IdolCardPrimaStellaProduceSkill` / `MemoryGift`+`MemoryAbility`；预设默认拉满。剩余：メモリー EndAuditionMid 阶段入组卡、`p_memory_skill` 的 `source='memory_skill'` 连锁保护需要 `simulation/produce/runtime.py` 钩子（见 §7.5）。

## C. 观察到的现象

- **C0（当前最重要）A8 修复后 HIF 通过率归零。** `scripts/eval_produce.py --scenario hif --loadout hif_sense_default --policy heuristic --seeds 10`：
  route_clear 0/10，選抜1 全部不过（分数 1.7k–8.7k），评分均值 6233（C+/B+）。
  对照 初：`--scenario first_star --seeds 6` route_clear 6/6、评分 7.1k–8.7k、mid1 基本通过 —— **说明不是取整/分数修复改过头，而是 HIF 特有的短板**。
  推断主因是 B6（课程不发技能卡 → 卡组停在 13–15 张，撑不起 HIF 高得多的分数线）+ B2（相談商店未暴露）+ A3/A4（スター性 加成偏低）。
  **注意：`docs/loadouts.md` 里 選抜1 通过 17–20/20 的数字是 A8 修复前测的，已失效**，修好 B6/B2 后需要重测。

- C1 `run_produce(scenario="hif", policy="heuristic")` 使用默认偶像/空编成时在第 2 场選抜試験失败（`ending_type: failed`）。
  **已处理一半**（`docs/loadouts.md`）：加了 `gakumas_arena/loadouts.py` 三套预设（`hif_sense/logic/anomaly_default`，SSR rank6 + 6 张 SSR 支援卡 Lv60 + H.I.F 面板全满），
  `scenario="hif"` 默认用 `hif_sense_default`。20 seeds：選抜1 通过 20/17/19，選抜2 通过 8/9/3，全通 1/4/0 —— **仍未达到 80%**，根因是 B6/B2/A8，不是编成。
- C2 planning 启发式（`interfaces/service.py::_choose_planning_action`）原本只看 P 点，整局只选差入/活動支給从不上课；已加三维与 スター性 项（`docs/loadouts.md` §3）。
  仍然只堆单一维度、不看 スター性 目标、不为卡组去差入 —— 之后应换成看考试权重/最低属性/卡组大小的策略或搜索。
- C3 主数据稀有度枚举是 `SupportCardRarity_Ssr`（混合大小写），`idol_config.py`/`support_card_selector.py` 用 `_SSR` 查表 → SSR 支援卡被钳到 40 级；已归一化修复。
  同类大小写陷阱可能还在别处（grep `Rarity_` 时注意）。

## D. 下一步（建议顺序）

1. A1 完成后跑一遍全量测试 + `tools/masterdata/coverage.py --strict`。
2. ~~构造一套合理的 HIF 默认 loadout（从 `SupportCard`/`IdolCard` 里选高等级卡），让 heuristic 能稳定通过選抜。~~ 已做 `gakumas_arena/loadouts.py` + `docs/loadouts.md`；但「稳定通过」要等 B6（课程发卡）/B2（相談）落地后重测重筛。
3. ~~自动打牌脚本：对固定 loadout 用 heuristic / 1-ply / MCTS 做分数分布评估，输出 CSV。~~ 已做：`gakumas_arena/policies/`（Random / Heuristic / Search=深度受限 expectimax + rollout 叶子）、`scripts/eval_exam.py`、`scripts/eval_produce.py`，首批数字见 `docs/evaluation.md`。MCTS 未做。
4. 培育策略搜索：先做 seed 固定的贪心/束搜索，再上 MaskablePPO（`gakumas_rl.training` 已有流程）。
5. 建立实机录像 → jsonl 的采集格式（`gakumas_rl/manual_exam_setups.py`）用于 A 组验证。
