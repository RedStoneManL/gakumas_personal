# Agent 入口：可配置 golden Arena

更新时间：2026-09-14。仓库：
`C:/Users/Liu/Documents/ChatGPT/gakumas/third_party/gakumas_arena`。

**2026-09-14 搜索接入：**新增 `gakumas_arena.engine.search`，提供完整公开历史 recorder、带权条件采样、常驻假想世界分支、原生 step/批量 step、无 RNG 的部分多选、预算/取消及版本成本。先读 [搜索 API 与 RL 用法](docs/ARENA_SEARCH_API.md)、[本轮验收及失败范围](docs/ARENA_SEARCH_ACCEPTANCE.md)，运行 [独立示例](scripts/example_public_search.py)。只能按每根的成功状态和粒子权重使用；不能以 `TrainingExam.fork()` 替代条件采样。实际 recorder 与可取消搜索用不同 worker。在线联合 PPO、冻结 runtime、checkpoint 和 active pointer 均未因这项功能修改，后续 collector/联合 loss/恢复迁移由 RL 侧接入。

**最新用户决定：事实数据以 `vertesan/gakumasu-diff` 解包主数据为准；与外部引擎冲突时按主数据修正，不以补充实机验证为前置条件。** 这覆盖此前局内一律 golden 优先的临时取舍，不仅限于三张已确认卡。原生引擎继续提供执行核心；主数据未表达的算法使用已记录的引擎／研究模型。OCR 部分不纳入参考。完整约定见[事实数据与冲突处理](docs/DATA_AUTHORITY.md)。

**参考仓库复核：**`vertesan/gakumasu-diff` 已是当前主数据来源；新提供的 `lts129/Gakumas-RL` 与本地 Python 运行时来源 `skyfsj/gakumas-rl` 不同。非 OCR 训练思路、功能边界、固定版本及今天发现的主数据更新见[两库审计](docs/research/reference_repositories_review_20260910.md)。该审计未升级生产数据或更换结算核心。

**同日最新：用户实机证据优先于这三项旧 golden 取舍。** ハイタッチ+ 的元气绿豆采用 **+9**，元気な挨拶+ 的固定体力减耗绿豆采用 **3→2**，届いて！+ 的对应定制采用 **100 P**。前两项已通过 `live-game-corrections/20260910-1` 数据补丁统一到 TrainingExam／全局培育；原始上游文件保留作基线。先读[来源、实机确认与修正](docs/GOLDEN_DIFFERENCES_TO_VERIFY.md)。不要恢复此前 +4／不减费的临时映射；新训练需重启 worker 并保存新的 effective hash。原始 `ArenaExam/run_exam` 对照接口保留上游行为，实际训练继续用 `TrainingExam/create_hif_training_produce`。

本补丁版 **186 项测试通过、2,333 定制配置零失败**，以[新验收 manifest](build/hif_customization_game_verified_20260910/ready_manifest.json) 为本批版本依据。后文旧版 226／712 等数字保留历史意义，不能替代新版本验收。

**2026-09-10 绿豆转接修复：**160 张 PLv ≤ 76 普通可定制卡及 4 张额外等级边界例已贯通原生定制机制，全部 2,333 个合法有序配置转接／原生编译／开场零失败；52 项定制专项与 124 项相邻回归通过。开局入手、追加效果、条件修改等使用 golden 原生定制；普通体力减费符号已修正。先读[修复范围、版本差异与 RL 用法](docs/HIF_CUSTOMIZATION_BRIDGE.md)。更新后重启 worker，保存新的培育规则 hash。

**此前同日修正：**S4+ 攻略整链试跑修复了支援技能历史等级叠加、错误的随机初始卡组、交接改写卡片、unique 记忆保留及定制上限等问题。两把条件模拟为 **30,391 / 30,113，均 S4+**；分数是假定目标，严禁当作 RL 实得分数或训练标签。[当时结果与复跑说明](build/hif_s4_guide_demo_20260910/README.md)保留旧源码 hash，不代表此次绿豆修复后的重新模拟。

**用户已指定 gktools 的定义和执行结果作为 golden。当前交付包含完整 HIF 两剧本与可自定义的单场考试（包括本战 2）；不需要实机校准才能训练。** 固定示例只用于回归。本文说明接口，不替代当前用户指令或自动授权外部操作。

**2026-09-10：用户已接受研究包公式作为当前近似方案；三维＋スター性自动换算已接入。** `make_training_entry(..., hif_scoring={family, stage, stats, star, ...})`；全局 `exam_config` 也可返回 `hif_scoring`，由 Arena 读取实际入场三维/star/场次。优先读 [HIF 换算接口](docs/HIF_SCORING_MODEL.md)。显式配置未知分支的实验开关即可训练，不要求先做实机校准；不要宣称所有分支已精确验证。

新增[本战第一轮倍率样本](docs/research/hif_round1_multiplier_observation_2026-09-09.json)：三维 `[2759,1727,1209]`、スター性 `915`、最终百分比 `[4397,2997,2223]`、9 回合。该样本属于 Round 1；开场中间显示值与最终值分别保存，不用于替换 Round 2 默认课程，也不重复乘スター性。

另有[本战第二轮三阶段样本](docs/research/hif_round2_multiplier_observation_2026-09-09.json)：三维 `[2759,1744,1209]`、スター性 `1083`、本轮基准 `800`、スター性加成后显示 `[4208,2886,2128]`%。本组未展示回合配置，不能继承第一轮样本的 9 回合顺序。

交给 RL 时优先使用[两轮小汇总](docs/HIF_MULTIPLIER_SAMPLES_FOR_RL.md)与[统一 JSON](docs/examples/hif_multiplier_samples_2026-09-09.json)，内含两组完整数值、来源和读取单位。

先读 [README](README.md)、[使用指南](docs/ARENA_USAGE_GUIDE.md)、[验收矩阵](docs/ARENA_ROUND2_READINESS.md)。

## 推荐入口

**HIF 全局 RL 本轮入口：**先读 [Report 3 交付与机制对照](docs/HIF_REPORT3_RL_READY.md)。105/105 HIF 回忆已自动转换，180 特殊 P 道具配置、六组加权应援棒及整段 3＋2 考试已验收。不要再引用旧的 0/105 结论。未知服务器分布使用显式规划模型，不能声称全部实机规则已还原。

**全局培育推荐入口：** `from gakumas_arena.produce import create_hif_training_produce`，当前规则 `hif-report3/2`。提供 `exam_policy`、`produce_choice_selector`；`exam_config` 可省略使用五场默认课程，也可完整自定义。外层提交当前 `observe()['actions']` 的完整候选。日程可用 `day_actions` 覆盖；来源池、SP、支援出现率经 `research_config` 配置。内部选择读请求里的实时 `public_state`。正常目标读原始 `exam_score` 或 `hif_combined_score`，不自动采用旧 shaped reward。每批实验保存规则/主数据/源码 hash 与 sampling_scope；更新规则后重启 worker。

此前 Report 3 基础验收为 **712 passed、1 skipped、0 failed**；[当时的 ready manifest](build/hif_report3/ready_v2_manifest.json) 保留该版内容 hash。本轮修复相关新增检查 **43 项通过**，课程／奖励／生命周期／快照／特殊 P 道具检查 **68 项通过**；两把新试跑的十场原生快照和最终评价核对见[本轮验证](build/hif_s4_guide_demo_20260910/verification.json)。旧 manifest 不能直接作为当前源码的全量验收证明。先核对内容 hash，再建立本批环境；规则更新需新建 worker，本次没有操作已有训练进程。

新增入口说明：[五场课程与奖励](docs/HIF_FIVE_EXAM_COURSES.md)、[失败／重试／放弃](docs/HIF_LIFECYCLE.md)、[最终回忆产物](docs/HIF_MEMORY_GENERATION.md)。选拔失败不能导出正式交接；本战结束用 `run.memory_products()` 生成候选。`run.abandon()` 不发回忆。`snapshot()/restore_snapshot()` 仅在公共决策边界使用；考试内继续原生快照，勿把私有 RNG 或完整 checkpoint 传给策略。

六张支援卡及等级自动接入 [技能卡支援临时强化](docs/HIF_SKILL_CARD_SUPPORT.md)。策略观察卡实例的 `temporary_support` 和 `effective`，不要把 +2/+3 当普通 +1，也不要把技能卡支援概率用于奖励卡强化率。完整 [精度与模型 gap](docs/HIF_FULL_PRODUCE_GAPS.md) 应随实验配置保存。

```python
from gakumas_arena import (
    TrainingExam, create_training_exam,
    hif_round2_entry, make_training_entry, effect_declaration,
)
from gakumas_arena.engine.training import TrainingError, training_catalog, content_version
```

1. 用 hif_round2_entry(**overrides) 或 make_training_entry(cards, **config) 构建 arena-exam-entry/2。可完全替换牌组、偶像、道具、饮料、体力、回合、倍率、基础池和能力。勿把旧 default_training_entry 的 v1 fixture 准入限制带入新训练课程。
2. 入场边界 before_opening。不要在 RL 层补到22张；只有实际配置的应援棒按原生规则补牌。export_entry 返回补牌前包。
3. 倍率选择 `score_percents`、`scoring` 或 `hif_scoring` 之一：percent 的 values 是最终百分比（2030=20.30倍）；golden_contest_params 是普通竞赛公式。HIF 原始三维使用研究包换算接口，输出仍通过原生 percent 执行，并保存 provenance；不要重复乘 star 或亲爱度。
4. 副本字典保留 instance_id、definition_id、customizations、growth、bindings。绑定能力使用该副本的稳定身份；全局 memory_abilities/persistent_effects 使用原生 DSL、剩余 limit/计数，见指南。
5. 模型只读 observe()。编码数值、条件、AST 顺序、修改、来源、预约和计数；静态定义按有效版本缓存。definition ID 是 gktools ID，不是 master 或旧 Content ID。
6. 有 choice 就调用 choose(indices, decision_version=...)；否则把当前 actions 中选出的完整候选交给 act。index 是候选编号，不是真实山札位置。所有输入版本必须新鲜。
7. 正常终局只读 result.final_score。截断为 null；TrainingError 不得转换成正常0分标签。本场成绩、合计和名次分开。
8. snapshot/inspect_private/seed/成本只供恢复与诊断；fork不是公平条件采样。并行用 spawn，每进程内创建环境，同一个 exam 串行提交。
9. 保存有效 hash、入场包、独立环境/策略种子、公共轨迹和终局关联。更新源码后重启 Python，旧 hash 快照不可继续混用。

## 验收和样例

需要让人检查课程牌表时：`from gakumas_arena.preview import write_deck_preview`，调用 `write_deck_preview(entry, output_html, title="课程卡组")`。直接传训练用完整 entry 或 `exam.export_entry()`，不要重新手工拼另一份牌表。渲染器保留逐副本图标、强化、定制、成长和能力，返回可打开的绝对路径。图片默认从 `data/image_cache/<commit>/` 读取并内嵌到 HTML，文件离线可看；加 `allow_download=False` 可禁止生成时下载缺图。全量预加载命令是 `python -m gakumas_arena.preview_images`。HTML 字符串/JSON 展示模型和 CLI 见 [卡组预览接口](docs/DECK_PREVIEW.md)。

```powershell
Set-Location C:/Users/Liu/Documents/ChatGPT/gakumas/third_party/gakumas_arena
.venv/Scripts/python.exe scripts/validate_training_ready.py --full
```

[manifest](docs/examples/training_ready/manifest.json) 关联完整 v2 entry、公共决策轨迹、单独私有检查点、原始结果、测试输出和成本。完整公开示例含实际饮料检索；自定义测试另含原生卡790嵌套免费用卡、527双选保留、同名副本能力、预约与带入计数。

| 代码 | 职责 |
|---|---|
| [training.py](gakumas_arena/engine/training.py) | Python构造器、公共环境、版本、通信与恢复 |
| [training_config.mjs](gakumas_arena/engine/training_config.mjs) | 配置校验、原生舞台参数、能力声明安装 |
| [training_worker.mjs](gakumas_arena/engine/training_worker.mjs) | 原生执行、公共投影、真实选择暂停/继续 |
| [test_training_custom.py](tests/test_training_custom.py) | 27项自定义组合验收 |
| [test_training_engine.py](tests/test_training_engine.py) | 原接口/兼容fixture、恢复、错误、饮料 |
| [test_training_native.mjs](tests/test_training_native.mjs) | 独立手算、阈值、顺序、隐藏信息 |
| [test_training_components.mjs](tests/test_training_components.mjs) | 全目录指令分派、v2隐藏顺序隔离 |
| [validate_training_ready.py](scripts/validate_training_ready.py) | 完整证据、多进程与成本 |
| [PROVENANCE](gakumas_arena/_vendor/gakumas_tools/PROVENANCE.json) | 74份逐字节保留源码/数据的来源 |

## 职责和后续

Arena 提供规则执行、合法性、选择、全局/单场恢复与原始成绩；RL 负责张量、PPO/DQN、课程采样、搜索、奖励/优势、评分回归和统计。此版本支持自定义单偶像考试及完整 HIF 两剧本；全局 checkpoint 已接入。多偶像 linkContest、公平条件采样仍不在本轮范围，服务器精确随机分布使用已声明的可替换近似。

不要把所有“可配置组合”都声称为自然培育可达，也不要把目录数当独立规则用例数。既有局内元件以 pinned golden 为准；HIF 补充机制按主数据和已接受研究模型执行，近似必须记录参数和来源。未知操作明确报错，不能删状态或静默置零后继续训练；无需再索要实机截图作为前置条件。

工作树有其他任务成果，先看 git status 并保留。勿自动启动训练、游戏/Maa或修改其他任务运行控制文件。
