# 历史审计：v1 私有 ArenaExam 的 Round2 能力

本文件保留首次审计结果；新 `TrainingExam` 实施后的判定见 [当前矩阵](ARENA_ROUND2_READINESS.md)。本文关于“缺失应援棒”的表述指旧适配入口，原始 gktools 道具定义本身已有该效果。

2026-09-09。回应 [RL 规划师检查清单](../../../design/rl-selection-20260908/ARENA_ROUND2_READINESS_CHECKLIST.md)，优先级遵循 [Round2 起步边界](../../../design/rl-selection-20260908/HIF_ROUND2_FIRST.md)。本文审计现有能力并提供调用资料；未把清单中的待建能力视为已完成。

**结论：可以继续基于当前 gktools golden 建设；当前不通过正式 Round2 纯策略或公平搜索准入。** 通用规则执行、外部决策、解析效果和确定性恢复已经可复用。主要缺口是 HIF 最终入场/补牌流程、严格机制闭包、完整公共观察、决策版本、结束原因及对应独立验收证据。无需先打通整个培育，也无需重写已有卡牌机制。

当前状态针对 `gakumas_arena.create_exam` / `gakumas_arena.engine`。旧 Gym、Content、live、HIF 自动考试仍运行 `gakumas_rl`；旧公共状态、回忆与被动协议可以参考，但不能当作新后端已通过本清单。

## 本轮证据与判定方式

状态按清单使用“已实现且有证据／已实现待验收／部分实现／缺失／不适用”。“已实现且有证据”仅覆盖行中声明的现有工程范围，不扩大为 HIF 全内容认证；“缺失”指该新接口未提供，不表示仓库没有相关数据或旧代码。

| 证据 | 入口与 2026-09-09 最近结果 | 证明什么 / 不证明什么 |
|---|---|---|
| E1 接入测试 | [test_golden_engine.py](../tests/test_golden_engine.py)：`python -m pytest tests/test_golden_engine.py -q`，**5 passed** | 原始文件校验、4 条 Python→Node 对拍、补选恢复、饮料/用卡分离、非法输入原子性、终局；不是 R/T 全通过 |
| E2 上游固定预期 | [tests/run.mjs](../gakumas_arena/_vendor/gakumas_tools/tests/run.mjs) 与 [suite.jsonl](../gakumas_arena/_vendor/gakumas_tools/tests/suite.jsonl)，**524/524 match，0 mismatch** | 预期分数来自已保存的上游 goldens，符合用户指定的当前规则真值；不是截图逐动作对齐或 HIF Round2 preset 验收 |
| E3 工程审计 | [audit_round2_readiness.py](../scripts/audit_round2_readiness.py)，[checks](examples/round2_readiness/checks.json)、[result](examples/round2_readiness/result.json) | 合成例子 **14 次提交、3 次补选、正常终局 score=106**；开局/卡内补选、恢复、双实例、非法选择检查通过。106 是执行输出，不能反作独立计分预期 |
| E4 内容与有效版本 | [vendor provenance](../gakumas_arena/_vendor/gakumas_tools/PROVENANCE.json)、[本轮 manifest](examples/round2_readiness/manifest.json) | 74 个 vendor 文件逐一 SHA256 相同，规则 commit `6c3d00648c32ea72a05086a18c63ab62e0d0c7e5`；manifest 另记实际接口/脚本文件 hash、配置和环境 |
| E5 成本测量 | [measurements](examples/round2_readiness/measurements.json) | create/observe/act/choose/snapshot/restore 单次样本及顶层重放条目数；没有原生效果级计数、峰值内存或训练吞吐认证 |

完整复现命令在 [使用指南](ARENA_USAGE_GUIDE.md)；所有命令在 Arena 仓库根目录运行。上游 runner 只对照既有预期，未使用 `--update`。未操作游戏/Maa，未启动训练。

## 最小可用配置与准确边界

**当前能交付的是工程测试配置，不是合法 HIF Round2 preset。** [engineering_config.json](examples/round2_readiness/engineering_config.json) 可立即使用，来源为显式合成机制测试：

| 依赖 | 本配置值 / 范围 | 可信度 |
|---|---|---|
| 执行核心、数值与触发 | 未修改的固定 gktools `StageEngine` | **已验证**：E1/E2；用户指定 golden，不额外声称实机完全一致 |
| 偶像/流派 | 通用 sense，未指定 HIF 偶像或自然来源 | **配置假设** |
| 舞台与倍率 | contest season 51，9 回合，Vo/Da/Vi=4/3/2；`enter_percents=true`、三属性 100%，最大体力 40、当前 30 | **配置假设**；不是 Round2 推导结果 |
| 属性顺序 | 上游按 firstTurns/criteria/seed 生成；固定 seed=7 | **已验证**确定性；未验证为 HIF 对应顺序 |
| 卡牌实例 | 配置 ID 1/5/7/17，各 1 张，无改造；上游追加 sense 基础牌 5/7/1/1/15/15/17/17，共 12 张 | **已验证**工程配置路径；不是完整牌组导入或应援棒 22 张规则 |
| 饮料 / P 道具 | 饮料 ID 18 一瓶，P 道具为空 | **已验证**库存消耗和追加行动不计作完整用卡；未测试完整 HIF 饮料准入 |
| 选择效果 | 首回合 `moveSelectedToHand[deck]` 连续两次，首次 `afterCardUsed` 再检索一次；各事件组 limit=1 | **已验证**3 次选择真实暂停/继续；舞台效果为合成插入 |
| 跨场成长、绑定、预约、应援棒、明星性 | 无导入协议或正式推导 | **未支持**此入场路径 |

测试内容范围是上述卡牌及基础牌、饮料 18、舞台检索效果和它们实际触发的通用计分/状态/抽牌/回合操作。样例不引入随机生成卡、HIF 特殊道具或跨场被动；该范围只是声明的工程 fixture，**没有**对外暴露为受 validator 强制执行的机制闭包 allowlist。任意编辑它不能自动获得支持资格。

入场时点为 golden 的 `getInitialState/startStage` 之前。调用 `create_exam` 会立即执行初始化、基础牌构造和开局，直到下一选择。示例快照 `before_start_private` 表示空 history、待执行 start；不能把它称为“已补牌后的 HIF 世界”。上游 `IdolConfig/IdolStageConfig` 的去重和基础牌追加必须在正式入场适配时处理，不允许默默损失副本或重复补牌。

用户提供的 508,647 分截图已确认是 **HIF 本战考试**，后续培育图明确标注 **Round1**。它可以作为相应实机机制参考，不能把这场的 9 回合和 3879/3335/2430% 直接命名为 Round2 的固定 preset。现有 [截图审阅](research/produce_score_photo_review_2026-09-08.md) 与 [gktools 复用审计](research/gakumas_tools_reuse_review_2026-09-09.md) 保留作来源证据。

## R：Round2 训练和入场评分

实现定位简称：**API** = [engine/__init__.py](../gakumas_arena/engine/__init__.py)；**Worker** = [worker.mjs](../gakumas_arena/engine/worker.mjs)；**Config** = [IdolConfig](../gakumas_arena/_vendor/gakumas_tools/packages/gakumas-engine/config/IdolConfig.js) / [IdolStageConfig](../gakumas_arena/_vendor/gakumas_tools/packages/gakumas-engine/config/IdolStageConfig.js)；**AST** = [结构化内容](../data/reference/gakumas_tools_effects.json) / [Effects 语法](../gakumas_arena/_vendor/gakumas_tools/packages/gakumas-data/Effects.md)。

| 编号 | 状态 | 已有入口/文件 | 示例/最近证据 | 限制、未验证部分 | 下一步 |
|---|---|---|---|---|---|
| R01 范围依据 | **缺失** | Worker `create`，上游 `StageConfig/typeMultipliers` | E2 固定舞台通过；E3 合成配置可跑 | 没有正式 Round2 preset、明星性依赖、规则可信度清单及闭包准入；上表是假设配置 | 选定一个偶像/流派与 Round2 配置，校对实际依赖并建立支持清单 |
| R02 完整入场 | **部分实现** | API 构造/restore；Worker `create`；Config | E1/E3 配置+seed+日志 JSON 恢复成功 | 缺跨场实例成长/绑定/剩余次数/预约入口、自然可达来源与必填校验；饮料和当前体力可默认；去重/追加基础牌不等于无损导入 | 提供补牌前版本化 entry schema，校验所选闭包必需状态，无静默修正 |
| R03 开局 | **部分实现** | `startStage`、`TapeStrategy`、replay | E1/E3 开局两次补选和途中恢复通过 | 未接 HIF 应援棒真实补牌；没有 21/22/23 规则用例；泛用 start 不是完整 HIF 开局 | 将应援棒计数区域、补牌池/权重/位置/先后纳入一次性结算和 checkpoint |
| R04 实例与区域 | **部分实现** | 上游 `CardManager`、state.cardMap；Config | E3 输出实例、手牌/山札/弃牌/保留/除外等内部区域 | 当前是全私有状态；入场不支持完整临时修改与精确绑定，同名差异组合未专项验收 | 无损实例入场+公共区域已知性；完成 T04 身份/绑定用例 |
| R05 可解析机制 | **部分实现** | AST、`find_effects`、原始 executor | E2 对拍；DSL/AST 已可查询，操作数/嵌套/顺序非图片 | 静态定义强于旧 tensor，但仍缺公共实例有效修正协议、单位/状态引用约定与严格闭包；T03 未全验 | 复用同一 AST 导出完整公共规则表达；针对 T03 给独立数值预期，不必在引擎重写 RL tensor |
| R06 公共考试状态 | **部分实现** | Worker `observe` 将 S 映射为 named state | E3 checks 列出实际字段；E1 验证饮料不增 cardsUsed | 体力/分数/次数/持续效果等已存在于私有状态，未建立公开性、来源/目标/间隔和所有计数口径契约 | 在原始状态基础上建立公共规则状态协议，区分行动/完整用卡/自动用卡/重复结算 |
| R07 可见性 | **缺失** | Worker `observe` 明确 offline_full_state | E3 保存 deckCards、cardMap、turnTypes 和日志；没有 public schema | 直接泄漏隐藏世界；没有已知 0/未知/无限/完整性语义或公共历史边界 | 建立可见性记录和公共导出；T09 隐藏世界置换测试；不能仅删 deckCards |
| R08 外部控制 | **部分实现** | API `act/choose`，Worker `TapeStrategy` | E3 开局→出牌→卡内检索→继续→终局，3 次补选；无内置演示选择 | 已暴露上游三类 pick 回调，但未证明覆盖所选 HIF 闭包的所有决策/弃牌/开局类型。CLI rollout 另用启发式 | 在受支持的真实内容闭包完成嵌套选择验收；坚持逐步入口，不用 rollout 替代 |
| R09 候选/多选 | **部分实现** | `pick`、`execute`、API 候选副本后 adopt | E1/E3 非法、重复索引拒绝且快照未变；E3 旧用卡候选在喝饮料后仍被接受 | 缺 decision revision、完整来源/目标/支付上下文；重复探针因单选长度拒绝，未覆盖合法大小内重复的真实多选 | 加版本校验及明确选择上下文，做真实多选/过期输入原子性测试 |
| R10 结果/结束 | **部分实现** | Worker `observe/execute`，上游 `endTurn` | E1/E3 正常终局后动作为空、再次提交拒绝；E2 完整分数对拍 | 仅有 terminated/score，无失败/放弃/截断/unsupported/exception 分类；无 Round2/合计/名次区分；未验 T08 延迟终局边界 | 明确结果 envelope 与非终局错误/截断行为，最后结算独立预期测试 |
| R11 确定性恢复 | **部分实现** | API snapshot/restore，Worker replay，独立进程 RNG | E1 补选续局相等；E3 初始化前/补选/终局前快照可恢复、终局全状态相等 | 通用配置的机制已实现且有证据；没有 HIF 入场/公共 schema，因此该完整需求未通过。日志重建不能导入任意编辑的 native 状态 | 保留现有 replay 作为参考路径；覆盖正式开局、绑定/预约和终局边界 |
| R12 版本/容量/诊断 | **部分实现** | RULES_VERSION、snapshot schema、E4 manifest | E1/E3 74 文件校验；E3 未知卡 ID 报错，实际配置/适配器 hash 已归档 | 运行时只验版本字符串；候选变长但无完整容量契约；未知自定义可能丢弃、空效果未严格拒绝；错误不带具体字段路径 | 准入 validator+运行时有效内容/schema 指纹；容量与资源上限分开，未知机制显式拒绝 |
| R13 可交付验收 | **部分实现** | E1–E5；配套 7 个 JSON 文件 | 配置、完整私有轨迹、检查点、结果、manifest 与新测量均可复现 | 没有合法 HIF Round2 入场和公开轨迹；合成 106 分不是独立规则预期，T 包尚不完整 | 在 R01–R12 补齐后输出正式公开验收包，保留独立上游/手算/主数据预期 |

## S：公共信息搜索

| 编号 | 状态 | 已有入口/文件 | 示例/最近证据 | 限制 | 下一步 |
|---|---|---|---|---|---|
| S01 独立分叉 | **已实现且有证据**（当前通用决策） | API `ArenaExam.restore`、replay | E1 原局/分支饮料与嵌套补选续局一致；E3 两分支补选相同结果、原快照未变 | 从同一私有世界重放的隔离副本；尚无正式 HIF 入场，恢复成本非 O(1) | 在正式 preset 重用并扩展边界用例；不要把它称为 S02 |
| S02 公共条件采样 | **缺失** | 无对应接口 | E3 manifest 标记 fair_search=NO_GO | restore 克隆实际隐藏 RNG；没有按公共历史独立采样的 hidden-world 构建入口和概率校准 | 在 R07 公共历史/已知位置基础上实现受约束隐藏世界采样，分离搜索 RNG |
| S03 分支公共观察 | **缺失** | 分支仍调用全状态 observe | E3 同样 offline_full_state | 后续策略可见未来信息；不存在公共过滤层 | 重用 R07 导出，不向策略传模拟内部世界，完成 T09 |
| S04 成本/停止 | **部分实现** | API 每请求隔离、60 秒子进程 timeout；E5 | 示范 200 次外部提交预算，记录含恢复的顶层重放数和耗时 | 没有精确原生规则转移计数、分叉预算统计或可调取消协议；外部预算不是内部效果预算，未做预算耗尽分支用例 | 暴露原生执行/重放成本和停止结果；给固定预算分支失败不影响原局的用例 |

## B：规模实验前

| 编号 | 状态 | 已有入口/文件 | 示例/最近证据 | 限制 | 下一步 |
|---|---|---|---|---|---|
| B01 无 UI 多实例 | **已实现且有证据**（独立对象） | API 子进程隔离；E3 `ThreadPoolExecutor` | seed 2/17 的两实例并行操作与各自串行结果完全相同 | 不是同一 ArenaExam 对象可并发写入；未评估最佳 worker 数 | RL 可用外部 worker 独占实例；扩大并发前测内存与进程开销 |
| B02 轻量路径 | **部分实现** | headless JSON；observe/snapshot 本地副本 | E3 不启 UI、不逐步自动写磁盘；可批量取得完整状态 | 每次起 Node/重载静态数据/重放全部历史，日志始终生成并返回，无 log-off 等价测试 | 常驻 worker、静态定义缓存、日志开关/增量日志；对标准 replay 做逐决策对拍 |
| B03 测量/迁移 | **部分实现** | E5；API node 路径可配；脚本 --output | Win 本地完成 reset/create、observe、act/choose、snapshot/restore 测量，运行环境记录于 manifest | 短局样本；未测峰值 RSS、长局/并发上限、Colab；无原生效果计数 | 加原生执行成本与内存测量，验证目标 Linux/Colab 环境后再定实验规模 |

测量的 `replayed_top_level_entries` 统计 completed history 与 pending 尝试，含重放开局；它不是“模型做了几个新动作”，也不是每个嵌套 effect 的调用次数。observe/snapshot 只是 Python 缓存复制，与原生推进不能混算。精确样本见 E5，不预先承诺 steps/s。

## F：后续阶段

| 编号 | 状态 | 现有参考入口 | 当前证据/限制 | 后续接入点 |
|---|---|---|---|---|
| F01 中场决策 | **不适用**（当前仅 Round2） | 旧 [produce/hif.py](../gakumas_rl/simulation/produce/hif.py)、[LIVE_CONTRACT](LIVE_CONTRACT.md) | 有旧菜单/资源路径，但本轮未验其与新 golden 的合法支付、被动和输出衔接 | 从最后一个中场决策接到 R02，再验完整选项/资格/费用/次数 |
| F02 Round1 衔接 | **不适用**（当前给定最终入场） | 旧 hif.py；用户 Round1 图片 | 不作为当前前置；没有新 golden 的跨轮持久/重置表验收 | 学习 R1 时导出跨轮状态，并分开本轮/合计成绩 |
| F03 完整准备/选拔 | **不适用**（后续倒推） | 旧 [produce/runtime.py](../gakumas_rl/simulation/produce/runtime.py) | 本轮不认证全事件/池/失败/转换；旧可运行不等于当前 golden 全通 | 更早阶段接入时验自然可达性、日程和转换 |
| F04 回忆专项 | **不适用**（独立未来目标） | 旧 [memory bridge 测试](../tests/gakumas_rl/test_memory_runtime_bridge.py) | 本轮不验回忆生成/筛选，不定义质量分 | 单独接入原始产物与真实选择规则 |

这些“不适用”仅表示阶段后置，不表示将来不用实现，也不意味着旧路径已经完成认证。

## T：最小机制包逐项回填

没有正式 Round2 首批 preset 时，不能以“暂不在闭包”绕开本应验的 T 项。以下如实记录现有相关证据和缺口。

| 编号 | 状态 | 入口 / 本轮相关证据 | 还需验收 |
|---|---|---|---|
| T01 重放/开局/补选 | **部分实现** | E1/E3，带 3 次补选的完整日志、6 类私有检查点 | 泛用初始化/嵌套一致已证实；正式 HIF 开局与公共状态对等未接入 |
| T02 21/22/23 补牌 | **缺失** | 本轮不提供伪补牌示例 | 真实应援棒触发区域/时点/池/权重/随机位置与补后移除，非持续补到 22 |
| T03 3/7 与顺序 | **部分实现** | AST 已保留数值与顺序；旧 [输入碰撞探针](../scripts/audit_rl_observation_gap.py) 是旧后端历史证据 | 在新 golden 做好调/得分/饮料 3/7 与顺序互换的完整执行、独立预期和公共表达比较；本轮未运行这些用例 |
| T04 双副本差异/绑定 | **部分实现** | Config/CardManager 有实例、自定义/成长结构；E3 区域输出 | 同名不同定制/费用/成长及同一道具不同绑定目标的组合执行与无损入场未验 |
| T05 脚光/精神統一阈值 | **部分实现** | 相关定义可由 `find_effects` 导出，上游执行器包含条件/次数 | 本轮未针对具体强化/定制版本重跑 20/21、15/16 和完整用卡计数边界，E2 总分不能替代 |
| T06 实际多选/弃牌/过期 | **部分实现** | E1/E3 合成检索、非法/重复输入原子性；旧合法候选跨饮料提交被接受 | 真实多选/弃牌、合法大小内重复、STOP/新信息边界、revision 原子拒绝；当前 stale 检查是暴露缺口 |
| T07 饮料/道具/预约/移区 | **部分实现** | E1/E3 饮料 18、一次性舞台触发与移牌真实改变局面 | 真实 P 道具、预约、清理眠气等适用组合的独立效果/次数/顺序证据尚未形成 |
| T08 终局与非正常结束 | **部分实现** | E1/E3 正常终局后拒绝行动，E2 全局分数 | 最后一次延迟/回合末效果的独立边界预期；外部截断/不支持/异常的分类输出 |
| T09 隐藏世界置换 | **缺失** | E3 明确当前返回完整私有状态 | R07、S02、S03 完成后验相同公共历史/不同隐藏世界/独立搜索 seed |
| T10 真实组合独立预期 | **部分实现** | E2 上游真实组合的保存分数 524 项匹配 | 选出首批 Round2 闭包内一个“铺垫→触发→收尾”完整组合，逐步绑定独立预期；合成 score=106 不替代该项 |

## 交付的数据和调用入口

| 文件 | 内容 / 可用于什么 |
|---|---|
| [engineering_config.json](examples/round2_readiness/engineering_config.json) | 当前可运行的合成配置，包含全部示例输入；不作合法 HIF entry |
| [private_decision_trace.json](examples/round2_readiness/private_decision_trace.json) | 开始状态与每次提交后的完整状态，含 3 次补选；明确 PRIVATE_DEBUG，不用于公共策略训练 |
| [private_checkpoints.json](examples/round2_readiness/private_checkpoints.json) | 初始化前/开局两处/卡内补选/终局前/终局的日志快照 |
| [result.json](examples/round2_readiness/result.json) | 原始工程分数、终局标记、提交数及最终状态 hash |
| [checks.json](examples/round2_readiness/checks.json) | 原子拒绝、恢复/并行结果，已发现 stale/public 缺口 |
| [measurements.json](examples/round2_readiness/measurements.json) | 当前短局各类调用成本及统计单位/限制 |
| [manifest.json](examples/round2_readiness/manifest.json) | 配置、代码、数据、运行环境、制品指纹；明确列出缺失的正式验收制品 |

完整可运行的构建→合法候选→提交→补选→终局例子及私有快照单独示例见 [使用指南第 2/5 节](ARENA_USAGE_GUIDE.md)。**当前无法提供清单要求的公共观察循环**；没有用调试数据冒名填补这一项。正式验收包仍缺合法 Round2 入场、公开轨迹、强制机制闭包和对应独立预期。

## 真正的阻塞项与实施顺序

| 分类 | 阻塞项 | 可复用部分 / 完成判据 |
|---|---|---|
| 阻塞 Round2 纯策略 | R01–R04：合法完整入场、Round2 参数推导、应援棒流程、实例/绑定和准入 | 复用上游效果执行；新入场模式明确与通用基础牌初始化的边界。21/22/23 和无损导入验收后才能发正式 preset |
| 阻塞 Round2 纯策略 | R05–R09：完整公共机制/状态、隐藏信息、选择上下文和版本 | 复用 AST、执行状态与 TapeStrategy，迁移有用的旧恢复/公共状态语义；通过数值区分、隐藏置换及过期原子拒绝 |
| 阻塞 Round2 纯策略 | R10–R13：结果分类、运行时有效版本和完整公开证据包 | 复用 snapshot/replay、vendor 指纹与固定上游 goldens，新增正式闭包的独立终局/机制预期 |
| 仅额外阻塞公平搜索 | S02/S03/S04：公共条件采样、分支公共输出、内部预算 | S01 私有分叉已可复用；必须保持已知位置和规则相关性，搜索随机源不依赖原局隐藏 RNG |
| 影响规模效率 | B02/B03：进程启动、重复解析/重放/日志、内存和平台测量 | 先用当前标准 replay 做等价参考，随后常驻 worker/缓存；不以速度优化绕过 R 组 |
| 未来才需 | F01–F04：中场、Round1、完整准备、回忆 | 更早阶段接入时再认证其合法菜单、持久状态与目标；不要求现在实现全培育或人工奖励 |

建议先打通一个受限 Round2 入场和公共决策闭环，再加入公平搜索，最后按测量改运行效率。S 的条件采样需要额外的公共历史/隐藏状态建模，不能由“已经能 clone”直接推定可用。此次修改完成审计、入口文档和工程示例，没有把上述缺口改写为已实现。
