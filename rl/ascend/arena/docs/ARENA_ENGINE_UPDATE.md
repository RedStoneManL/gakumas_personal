# Arena 引擎与实况接口：本轮交付记录

> 本文保留上一阶段的奖励/咨询交付与 433 项回归记录。后续考试绑定、饮料/补选、公共恢复已推进，
> 当前接口与验收以 [ARENA_EXAM_UPDATE.md](ARENA_EXAM_UPDATE.md) 为准；下表“尚无恢复 API/考试未绑定”是历史状态。

2026-09-07。工作分支 `codex/arena-live-bridge`，基于 `ef2402958547b2050e873841b9ff5066a895b1a9`。
已用远端 `ls-remote` 确认 `claude/school-idol-sandbox-ifjkh8` 仍在 ef24029；main 为 c495837。
本轮改动是本地可审阅 diff，**没有新 commit 或 push**。仓库没有配置 Git 作者身份，未替用户填写身份。

## 先交给 adapter 的文件

- [确定的数据契约](LIVE_CONTRACT.md)，版本 `arena-live/1`。
- [生成的 JSON Schema](schemas/arena-live-v1.json)，源类型在 `gakumas_arena/live/contracts.py`。
- [可执行离线示例](../scripts/demo_live_bridge.py) 与 [完整 JSON 对话](examples/live_reward_consult.json)。
- `LiveSession.initialize / observe / decide / mark_submitted / accept_result`。
- `PlanningBackend` 是当前可用的奖励/咨询绑定；`to_loadout_config` 将完整编成转换成已有引擎配置。

运行（仓库根目录）：

```powershell
.venv/Scripts/python.exe scripts/demo_live_bridge.py
.venv/Scripts/python.exe scripts/export_live_schema.py
.venv/Scripts/python.exe -m pytest tests -q -rs
```

示例为**合成数据**，不是实机轨迹，也不是专家/RL 训练样本。稳定输出：
选择 `reward-b` → 确认卡入组 → 咨询选择 `buy-card` → 实测余额 100→80；最终两张不同实例，
重复回执不重复入组/扣费，下一观察为 ready。测试禁止调用 ProduceRuntime.reset/step，确保没有用 seed 冒充游戏结果。

## 已实现与剩余边界

| 项目 | 本轮落地 | 仍未完成 / 未验证 |
|---|---|---|
| 实况事务 | 版本化类型、四态决策、旧观察拒绝、语义目标绑定、提交/确认分离、uncertain 阻塞、command/result/event 去重 | 会话账本在内存；跨进程恢复必须由 adapter 保留日志及未决事务，尚无公共持久化恢复 API |
| 状态消费 | 当前绝对快照替换事实；事件只存证，校验包含水位；partial/unknown 显式保留 | 未建立完整考试 shadow runtime 与预测差异解释器 |
| 真实页面绑定 | card_reward：三候选选择/放弃/刷新；consult：卡/饮料购买、刷新、结束；真实候选复用 ProduceActionCandidate 和规则合法性 | 授业事件、考试出牌、检索/弃牌、饮料溢出、升级/删除/自定义 UI 等只有协议类型，暂返回 Inspect；不是完整实况自动培育 |
| 模拟选择边界 | 初/HIF 课程奖励停在独立子阶段；咨询进入/购买/售罄/结束；所有候选稳定，结束选择才推进周数 | 其他 ProduceReward 随机授予路径、授业内部抽样、考试补选尚未全部拆成可暂停流程 |
| 絶好調 A9 | 同种剩余回合合并、减去回合数、资源槽反映持续时间；原 xfail 录像转为正常通过 | 只证明所覆盖录像，不外推到全部 HIF 卡效果 |
| 回忆 | 复用现有类型；延迟发卡钩子与去重；memory_skill 连锁保护；自定义进入真实成长/费用路径；HIF 交接保留自定义和来源 | HIF 的 EndAuditionMid 具体对应哪次选拔需确认；配置 `memory_card_mid_stage_type` 可调整，默认 Mid1 标为推断 |
| 回忆来源 | idol_card_id 作为生成来源；另校验显式 allowed_character_ids、卡流派和合法变体 | 不再从生成角色推导同角色限制；四槽实测不能外推所有路线槽数。仍需映射实机回忆主数据 ID |
| 支援 | 配置链增加逐槽 `support_card_levels`，保留原统一等级入口 | 实机完整六槽 ID/等级与效果分页仍由 adapter 读取 |
| 编码 B1 | HIF、奖励、咨询等动作进入共用 taxonomy；同一 env 编码增加可观测缺失掩码；训练可用 PlanningVisibilityWrapper | 未训练新 actor；依赖隐藏完整运行时的 Heuristic/Search 不直接用于局部实况 |
| 推理旧路径 | 取消补 43 维和全零 52×100 的假编码；旧 ExamState 明确拒绝；predict_encoded 检查 manifest/空间/掩码并使用 MaskablePPO | 旧 HTTP 请求结构尚未升级到实况协议。旧 checkpoint 不能直接用于新编码 |
| 取整 A1 | [核心管线审计与独立向量](rules/scoring_fidelity.md)，9 段录像均通过 | 集中复合倍率、HIF 新机制与全部效果处理器仍需补边界样本，不声称全量审计完成 |

`PlanningBackend` 为当前选择点只取偶像定义的流派与卡元数据；不执行开场加成。
完整编成解析由 `to_loadout_config` 显式检查缺失字段，调用者可传给现有 `build_loadout_from_config`。
两者不能混称“已恢复整局引擎内部状态”。

## 版本和验证

主数据从公开来源拉取到 Arena 自己的 `data/raw/`，没有修改 Maa Python 环境：

- master：`571dbb62601e78998cddeacdbce3ea1bc672d7fc`，2026-09-07 08:03:22 UTC。
- 缓存转换 284 表；`Localization.yaml` 本身格式不合法而跳过，规则表可加载。未拉翻译包。
- 原交接覆盖报告使用 `5b8969e363ae…`（09-04）；本轮先在**新数据上对未修改 ef24029 复跑**，
  结果仍为 397 passed / 3 skipped / 1 xfailed，然后才改规则。
- 协议 `arena-live/1`；规则语义 `arena-rules/2`；局部规划编码 `arena-planning-observed/2`。
- HIF 示例：global 81、actions 40、action_features 宽 320（以 manifest 为准，禁止硬编码）。
  manifest sha256：`f5bd97059027579ca856af27429f253c115655a3a143a33abc1516d1ad55a0d7`。
- 本轮最终全量：**433 passed / 3 skipped / 0 xfailed**（43.82 秒），包含在线查证后的多级自定义修正。
  3 skipped：1 个固定 seed 无可执行考试前准备动作，2 个 SB3 测试缺可选依赖。
  另有 conftest 在收集前忽略的可选模块：缺 torch 的 autopilot/bootstrap/demo_exam/rllib_model，
  缺 fastapi 的 inference_api；它们不计入上述 3 skipped。没有做 RL 训练或实机端到端测试。
- 新 façade/编码、示例/审计脚本与其测试的 Ruff 检查通过；`git diff --check` 通过。
- `coverage.py --strict` 通过：107/66/29/1/39/33 个各类枚举均有处理路径；仍不代表数值语义正确。

固定 seed 0–9，HIF / hif_sense_default / heuristic / builtin：全路线 **0/10**，
评价均值 **7383.1**，中位数 **6415.5**。固定 seed 0–5，初：全路线 **6/6**，评价均值 **8512.5**。
逐 seed CSV 在 `docs/examples/hif_baseline_20260907.csv` 和 `first_star_baseline_20260907.csv`。

HIF seed=5 的已接受首场得分 **520525**、下一场 **5741**；该高方差值得继续核查。
这可能涉及新增奖励后的卡组组合或未验证效果，当前证据不足，**不据此调低分数公式，也不把它当强度证明**。
统计脚本的 `auditions` 字符串可能包含重试的先前结果，应以最终 accepted history 核对是否通过。

## 下一批最小实机材料

1. **奖励与咨询首轮联调**：一个完整三候选页面（ID、+级、自定义、实例、可用性），以及选中指定候选后的完整牌组变化；
   一次商品购买的前后 P 点、商品实例、售罄与卡/饮料入账。每场景一组即可，使用本契约 JSON。
2. **延迟回忆**：携带一张 EndAuditionMid 回忆，记录选拔1/2 结果确认前后牌组及获得卡弹窗，附原回忆时机文字；
   用于确定 `memory_card_mid_stage_type`，无需整局录像。
3. **自定义变体**：脚光/国民/精神/シュプレ各一个详情，给出完整自定义列表、原始日文文本、+级与实际费用；
   尤其区分同名同 + 但自定义不同的副本。当前已用主数据验证シュプレ+ 集中费用 2→1 的定制变体。
4. **明星性换算 A3/A4**：一次選抜结果分数、获得明星性、前后总明星性、亲爱/HIF 加成；
   另取两个不同明星性下同属性/同加成配置的考试倍率面板。暂不改既有推断曲线。
5. **取整争议**：小基数同时有两项分数倍率时的一次出牌，完整前后分数、集中/好调/绝好调/倍率与卡详情；
   使“合并倍率后 ceil”与“每次乘法 ceil”给出不同整数，才能区分两种解释。

## 参考资料与范围

已读取 Arena HANDOFF/PLAN/OPEN_ITEMS/ARCHITECTURE/loadouts §7、规则文档和录像 harness；
实机侧只读 ARENA_ADAPTER_DESIGN、LIVE_STATUS 顶部及 preparation-evidence 的小段。
额外 `compass_artifact1.md` / `compass_artifact2.md` 作为研究线索；其推荐重搭 JS 引擎、
“没有现成 Gym/RL 环境”等结论不作为本次执行指令，且已被当前仓库实现覆盖。
“每步 ceil”的概述也不能代替对具体结算阶段的核对。

补充在线查证已落实到 [版本化来源审计](research/live_reference_sources.md) 和
[四张目标卡的主数据/社区数据库对照](examples/live_card_reference.json)。
实际检查了当前 gakumas-tools 源码及 870 条卡记录、111 条自定义记录，并只读拉取 HIF 理论值计算器。
交叉查证发现并修复精神統一+ 多级自定义重复累加：Lv2 集中总增量 +3、元气总增量 +13，
替换 Lv1，不能得到 +4/+17。初始化与咨询逐级应用共用此逻辑；保留其他来源的成长。

本轮未修改 Maa 仓库、游戏输入、PAUSE、runs/hif-dev 或 adapter 采集输出。
