# 文档索引

**2026-09-10 全局 HIF：** [Report 3 RL-ready 交付](HIF_REPORT3_RL_READY.md) → [培育指南](PRODUCE_USAGE_GUIDE.md) → [Agent 入口](../AGENT_ENTRY.md)。默认 Report 3 日程、特殊 P 道具、105 回忆、普通咨询/中场/特别指导及全局 checkpoint 已接通。下文历史状态以本轮交付覆盖。

**当前入门顺序（2026-09-09）：** [仓库 README](../README.md) → [使用指南](ARENA_USAGE_GUIDE.md) → [Agent 入口](../AGENT_ENTRY.md)。`TrainingExam` 已支持可自定义的 HIF 本战 2 / 单偶像 golden 考试纯策略训练，边界与证据见 [R/S/B/F/T 验收矩阵](ARENA_ROUND2_READINESS.md)。实机校准不作为开训前提；公平搜索条件采样尚缺。下方旧兼容接口覆盖率不代表本轮能力。

> **2026-09-09 当前入口更新：**用户指定 gakumas-tools 为局内规则 golden；已直接纳入原始源码与数据，新 `gakumas_arena.create_exam` / `gakumas_arena.engine` 可运行。旧 HIF/Gym/Content/live 路径仍兼容，未整体改接；范围、验证和下一步迁移见 [ARENA_GOLDEN_ENGINE](ARENA_GOLDEN_ENGINE.md)。

最新取舍：[同阶段触发的字典序默认与后续校准](ARENA_TRIGGER_ORDER_UPDATE.md)。规则v4保留确定性、恢复及去重；精细道具次序暂缓，不阻塞HIF基础建设。

最新规则实施：[2026-09-08 底层行为对齐交付](ARENA_RULE_ALIGNMENT_UPDATE.md)、[行为契约](ENGINE_RULE_CONTRACT.md)、[最小JSON](examples/rule_alignment_minimal.json)、[实机采样清单](RULE_ALIGNMENT_LOG_REQUESTS.md)。共享数值、阶段、准备队列及寿命已修正，17项定向探针全部符合参考；实机1:1尚需证据。此前 [4一致／13差异审计](research/effect_order_comparison_2026-09-08.md) 保留为历史基线。

RL 研究交接：[模型拆分、整局奖励、输入缺口与本地/Colab 实验课题](RL_DESIGN_HANDOFF.md)。方案待独立 agent 选型，Arena 继续完善规则与公共接口。

Arena 后续顺序：[完整底座设计与完成标准](ARENA_COMPLETION_ROADMAP.md)；新增机制：[卡牌移区字段与合成样例](CARD_MOVEMENT_CONTRACT.md)。

本轮验收与兼容说明：[RL 交接及移区机制交付记录](ARENA_MOVEMENT_UPDATE.md)。

真实内容目录：[全部卡牌／饮料／P 道具、偶像与支援卡关联及复用流程](REAL_CONTENT_CATALOGUE.md)。
本轮验证与发布：[真实内容交付记录](ARENA_CATALOGUE_UPDATE.md)。

现状交互报告：[系统关系、真实卡牌参数实验与在线交付](ARENA_REPORT_UPDATE.md)。

内容创作与扩展：[创建卡牌／效果／事件／训练／试镜／剧本](CONTENT_AUTHORING.md)、[实际架构与支持边界](CONTENT_ARCHITECTURE.md)、[实况被动 v2 与编码 v3](LIVE_PASSIVE_GENERIC.md)、[本轮交付记录](ARENA_CONTENT_UPDATE.md)。

新接手请按顺序读前三份。

## 入门 / 交接

| 文档 | 内容 |
|---|---|
| [HANDOFF.md](HANDOFF.md) | **交接说明**：项目是什么、能用什么、不能用什么、怎么验证、协作约定 |
| [PLAN.md](PLAN.md) | 路线图、里程碑状态、下一步建议顺序、设计约束 |
| [OPEN_ITEMS.md](OPEN_ITEMS.md) | 待验证 / 待办清单（推断值、引擎缺口、实测发现） |
| [LIVE_CONTRACT.md](LIVE_CONTRACT.md) | adapter 联调入口、JSON Schema、调用顺序与当前页面支持范围 |
| [LIVE_EXAM_CONTRACT.md](LIVE_EXAM_CONTRACT.md) | HIF センス出牌、饮料、检索/弃牌字段、共用编码与会话恢复 |
| [ARENA_EXAM_UPDATE.md](ARENA_EXAM_UPDATE.md) | 考试阶段交付、合成往返验收与下一批实机证据需求 |
| [LIVE_PASSIVE_CONTRACT.md](LIVE_PASSIVE_CONTRACT.md) | 真实证据分类、非空被动来源/次数、回合行动语义、缺项分类与 v2 编码 |
| [ARENA_PASSIVE_UPDATE.md](ARENA_PASSIVE_UPDATE.md) | 被动阶段验收与剩余确切证据缺口 |
| [ARENA_ENGINE_UPDATE.md](ARENA_ENGINE_UPDATE.md) | codex/arena-live-bridge 本地交付记录、数据版本、验证及剩余边界 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 设计文档：分层、数据与效果表示、剧本配置、RL 接口、版本化原则 |
| [../README.md](../README.md) | 仓库入口：许可、布局、快速开始、数据更新流程 |

## 规则规格（实现依据）

| 文档 | 内容 |
|---|---|
| [rules/lesson_exam_engine.md](rules/lesson_exam_engine.md) | 课程/考试卡牌引擎：回合结构、取整、分数公式、センス/ロジック/アノマリー、状态效果目录、相位时序 |
| [PRODUCE_USAGE_GUIDE.md](PRODUCE_USAGE_GUIDE.md) | 新 HIF 全局培育接口：事件/选择/道具、选拔交接与 golden 考试 |
| [PRODUCE_EVENT_LIBRARY.md](PRODUCE_EVENT_LIBRARY.md) | 结构化事件及支援卡事件库、效果引用、数据边界 |
| [HIF_EVENT_ABSTRACTION.md](HIF_EVENT_ABSTRACTION.md) | 按效果/选项去重的早期报告；本版按来源池区分后的分组见 Report 3 交付 |
| [HIF_MEMORY_ABILITIES.md](HIF_MEMORY_ABILITIES.md) | 105 条 HIF 回忆能力与卡名对应表；已自动接入 golden |
| [HIF_FIVE_EXAM_COURSES.md](HIF_FIVE_EXAM_COURSES.md) | 五场默认考试、NPC、星性与三维奖励、最终评价及自定义入口 |
| [HIF_LIFECYCLE.md](HIF_LIFECYCLE.md) | 接受、失败、重试、放弃和正式交接资格 |
| [HIF_MEMORY_GENERATION.md](HIF_MEMORY_GENERATION.md) | 最终回忆生成、再生成、筛选及下一轮编成 |
| [HIF_SKILL_CARD_SUPPORT.md](HIF_SKILL_CARD_SUPPORT.md) | 支援卡来源/等级概率、临时 +2/+3 原生执行与观察接口 |
| [HIF_FULL_PRODUCE_GAPS.md](HIF_FULL_PRODUCE_GAPS.md) | 当前已执行的近似模型、默认数值、精度与范围差异 |
| [rules/produce_loop.md](rules/produce_loop.md) | 培育外循环（初 / N.I.A. 基线）：周程、行动、属性成长、最终评价公式 |
| [rules/hif_exam_effects.md](rules/hif_exam_effects.md) | H.I.F 新增考试效果类型的语义推导与证据 |
| [rules/glossary.md](rules/glossary.md) | 术语表：日文 / 中文 / 英文 / master 枚举名 / 代码标识符 |
| [scenarios/hif.md](scenarios/hif.md) | **H.I.F 剧本规格**：周程、行动数值、スター性、両ラウンド本戦、评价换算 |

## 数据与调研

| 文档 | 内容 |
|---|---|
| [research/master_data_atlas.md](research/master_data_atlas.md) | master data 图谱：127 张表逐字段注释、外键、样例行 |
| [research/master_data_enums.md](research/master_data_enums.md) | 枚举字典：214 个枚举全量，169 个考试效果类型逐条语义 |
| [research/engine_coverage.md](research/engine_coverage.md) | **覆盖率报告**（自动生成）：dump 里的枚举值哪些引擎已处理 |
| [research/mechanics_timeline.md](research/mechanics_timeline.md) | 数据时效性 + 机制/结算变更时间线 + 引擎扩展点清单 |
| [research/existing_engines.md](research/existing_engines.md) | 开源引擎/RL 仓库评估与选型依据 |
| [research/data_sources.md](research/data_sources.md) | 数据源清单：翻译数据、校验用计算器、抓取可行性 |
| [research/hif_round1_multiplier_observation_2026-09-09.md](research/hif_round1_multiplier_observation_2026-09-09.md) | 用户第一轮图证：三维 2759/1727/1209、star 915、最终倍率 4397/2997/2223%，含原图和结构化记录 |
| [research/hif_round2_multiplier_observation_2026-09-09.md](research/hif_round2_multiplier_observation_2026-09-09.md) | 用户第二轮图证：三维 2759/1744/1209、star 1083、基准 800，三个阶段至 4208/2886/2128%，与第一轮独立保存 |
| [HIF_MULTIPLIER_SAMPLES_FOR_RL.md](HIF_MULTIPLIER_SAMPLES_FOR_RL.md) | 给 RL 的两轮小汇总，附统一 JSON、倍率单位、回合与原图来源 |
| [HIF_SCORING_MODEL.md](HIF_SCORING_MODEL.md) | 用户研究公式已接入：单场／全局三维与 star 换算、近似分支、版本记录及测试 |
| [research/live_reference_sources.md](research/live_reference_sources.md) | 本轮在线查证、固定版本主数据/独立引擎对照、四张目标卡的 ID 与自定义 |
| [research/user_report_01_simulator_landscape.md](research/user_report_01_simulator_landscape.md) | 项目发起时的调研报告（生态现状） |
| [research/user_report_02_data_and_formulas.md](research/user_report_02_data_and_formulas.md) | 项目发起时的调研报告（数据源与公式） |

## 使用与测量

| 文档 | 内容 |
|---|---|
| [evaluation.md](evaluation.md) | 评估脚本用法、列含义、初剧本 random/heuristic/search 实测数字 |
| [loadouts.md](loadouts.md) | 编成预设内容与实测（⚠️ 通过率数字在分数爆炸修复前测得，已失效） |
