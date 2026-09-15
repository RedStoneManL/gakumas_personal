# 两个参考仓库与当前 Arena 的关系

2026-09-10。按用户新提供的两个链接复核远端说明、源码、当前本地来源及版本。此次交付为参考审计；未切换训练引擎、主数据、奖励函数或已有训练进程。[机器可读版本记录](reference_repositories_20260910.json)保存主数据比较结果。

**用户后续取舍已纳入：**事实数据与冲突处理统一以 `gakumasu-diff` 为准，见[数据权威约定](../DATA_AUTHORITY.md)。OCR 部分排除，不继续参考或移植；已阅读的非 OCR 训练思路仅作资料。

## 结论与来源区分

| 来源 | 在当前项目中的作用 | 此次取舍 |
|---|---|---|
| [vertesan/gakumasu-diff](https://github.com/vertesan/gakumasu-diff) | 已经使用的游戏主数据镜像，YAML 结构化表 | 继续提供卡片、绿豆、支援、事件、道具和剧本字段；固定数据版本 |
| [lts129/Gakumas-RL](https://github.com/lts129/Gakumas-RL) | 独立的感性打牌训练与 OCR 项目；没有作为 Arena 运行时引入 | 仅保留策略编码、轨迹筛选调研；排除 OCR |
| [skyfsj/gakumas-rl](https://github.com/skyfsj/gakumas-rl) | 我们早期引入并持续扩展的 Python 培育运行时 | 与 lts129 的同名项目分开记录 |
| [surisuririsu/gakumas-tools](https://github.com/surisuririsu/gakumas-tools) | 用户指定的局内结算 golden | 当前 TrainingExam 使用固定原生核心及已确认的两条卡目录修正 |

本地 `gakumas_rl/` 的上游是 **skyfsj**，固定提交 `40b8d8b19da8480ce8ffe393067442afd872e398`，见 [PROVENANCE](../../third_party/gakumas_rl_upstream/PROVENANCE.txt)。不能因为名字相似而把 lts129 的功能、限制或模型归到它身上。当前完整培育入口仍是 `create_hif_training_produce`，通过 `GoldenProduceBridge` 接入 `TrainingExam`，参见 [Agent 入口](../../AGENT_ENTRY.md)。

## gakumasu-diff：结构化效果已经在使用

当前数据位于 `data/raw/gakumasu-diff`，固定提交 `571dbb62601e78998cddeacdbce3ea1bc672d7fc`（2026-09-07）；JSON 缓存元信息也指向同一提交。

| 所需信息 | 主要表及关系 | 当前消费位置 |
|---|---|---|
| 卡片效果、触发和持续状态 | `ProduceCard → ProduceExamEffect / ProduceExamTrigger / ProduceExamStatusEnchant` | 主数据内容解析及考试桥接 |
| 绿豆效果与价格 | `ProduceCardCustomize / ProduceCardGrowEffect` | `gakumas_arena/produce/customization_bridge.py` 与定制注册表 |
| 外出、上课和选项 | `ProduceStepEventDetail → ProduceStepEventSuggestion → ProduceEffect` | `gakumas_rl/simulation/produce/events.py`、`event_templates.py`、`runtime.py` |
| 支援技能及剧情事件 | `SupportCard / SupportCardProduceSkillLevel* / ProduceSkill / ProduceTrigger / ProduceEventSupportCard` | 装备等级、触发、事件前序和成长链 |
| P 道具及获得后触发 | `ProduceItem / ProduceItemEffect / ProduceEffect / ProduceSkill` | 培育道具解释与考试携带效果桥接 |
| HIF 剧本和考试条件 | `Produce / ProduceStepAuditionDifficulty / ProduceStepOpenLesson` | HIF 生命周期及已接受的换算模型 |

本地表实读包含：1,714 行卡片、343 行绿豆定制、453 行成长效果、2,070 行局内效果、6,888 行事件详情、3,066 行事件选项、511 行支援事件关联、1,038 行 P 道具。它们是**表行数**，包含等级、变体和非 HIF 内容，不是已验证效果数量。

已有 HIF 事件审计把 92 条外出／上课事件、72 个选项归成 30 个机制组，并按装备、等级和前序筛选支援事件；详见 [事件实现说明](../HIF_REPORT3_EVENTS.md)。固定效果有主数据，发生概率、池权重和部分客户端算法仍须由已记录的研究模型或环境配置解释；仅发现一张表不能证明完整规则已经实现。

用户刚确认的元气 +9、固定体力费用 2、定制价格 100 P 继续按[实机确认记录](../GOLDEN_DIFFERENCES_TO_VERIFY.md)执行。最新主数据事实优先规则适用于后续冲突；这与“三项实测不代表全部结算语义已验证”是两件事。

### 今天发现的远端更新

查询时远端 HEAD 为 `8f3f325edfc18a9db53587f94ae9edea7ad66f86`（2026-09-10 02:03:24 UTC），比本地多 1 个提交，涉及 87 个文件。依据[固定版本比较](https://github.com/vertesan/gakumasu-diff/compare/571dbb62601e78998cddeacdbce3ea1bc672d7fc...8f3f325edfc18a9db53587f94ae9edea7ad66f86)：

- `ProduceCardCustomize`、`ProduceCardGrowEffect`、`ProduceStepEventSuggestion`、`Produce`、`MemoryAbility`、`ProduceStepOpenLesson` 文件未变。
- 卡片、局内效果、支援、P 道具、事件详情和考试难度等文件有变更；此次记录文件级变化，尚未把所有新增／修改行做语义验收。
- 当前训练仍固定在已验收数据提交。升级主数据时应另外生成内容覆盖及效果差异记录，再以新版本身份运行；不能覆盖旧训练的环境身份。

“绿豆两张表未变”只说明这些表在该提交中没有变化，不代表引用它们的全部卡片都未变化，也不代表整个更新不影响训练。

## lts129/Gakumas-RL：可参考的训练方案与边界

查询时 `main` 固定为 `fe57c6235bda44393de998f1b43ed08477ede525`（2026-04-26）。[README](https://github.com/lts129/Gakumas-RL/blob/fe57c6235bda44393de998f1b43ed08477ede525/readme.md)明确说明只支持感性打牌，角色卡、支援卡与道具仅部分收录，场地效果只加入偶像之路千奈第一关的集中场地，OCR 尚不识别绿豆定制。

其数据来自手工整理的卡牌工作簿及自定义词条，并非通用主数据效果解释器。源码有局内卡牌环境、训练、专家轨迹与实机部署，没有完整 HIF 日程、局外获得卡／饮料后的支援触发链或 HIF 全事件执行层。

已阅读、可保留为非 OCR 训练参考的部分：

1. **效果词条编码与卡组区域编码。** [模型源码](https://github.com/lts129/Gakumas-RL/blob/fe57c6235bda44393de998f1b43ed08477ede525/models/model.py#L7)用共享词条 embedding 表达卡片效果，结合手牌和整个卡组的区域信息。我们可以参考表示方式；可观察状态仍由 Arena 公共接口提供，不能把私有牌序或检查点直接给策略。
2. **固定 seed 下筛选优质轨迹，交替进行 PPO 和模仿学习。** [多模型轨迹筛选](https://github.com/lts129/Gakumas-RL/blob/fe57c6235bda44393de998f1b43ed08477ede525/train/MakeExpertDataFromModel.py#L107)及[PPO／BC 代码](https://github.com/lts129/Gakumas-RL/blob/fe57c6235bda44393de998f1b43ed08477ede525/train/ppo_trainer_withbc.py#L132)适合参考专家数据采集与自举训练；本地 `gakumas_rl/training/self_bootstrap.py` 已有同类流程。轨迹应由当前 Arena 重新生成并记录环境版本。

OCR 状态回填部分已按用户决定排除，不列为后续方案。

不能直接套用的默认项：动作空间是休息加最多 5 个手牌槽，没有我们的独立饮料和多阶段选牌动作；默认随机 12 回合场景与随机属性倍率不等于 HIF 本战配置。预训练模型的词条、动作和观察维度也不与 Arena 契约通用。

奖励只作为该项目自己的训练选择：[当前环境源码](https://github.com/lts129/Gakumas-RL/blob/fe57c6235bda44393de998f1b43ed08477ede525/envs/card_game_env_base.py#L191)的终局奖励为 `4 * log10(score + 1) + score / 2000`。旧调研写的 `8 * log10(总分)`不适用于此次核对的版本。此奖励不是游戏最终评价公式，也未写入我们的 Arena 或训练配置。

此次新增的是版本与接入取舍记录，不以外部项目的 README、表条数或同名模型代替 HIF 规则验收。需要实际使用的本地 API 与范围仍以 [AGENT_ENTRY.md](../../AGENT_ENTRY.md)、[培育接口](../HIF_REPORT3_RL_READY.md)及[当前 golden 说明](../ARENA_GOLDEN_ENGINE.md)为准。
