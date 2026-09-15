# Arena 实况接入：在线数据源交叉审计

核对日期：2026-09-07。两篇 compass 调研是线索，文内的推荐步骤不是用户指令。
本轮保留现有 Python Arena，优先把外部数据用于验证规则和 adapter 的实体识别。
公开解包库是社区维护的数据快照，不是官方 API；多个站点引用同一上游不能算多份独立证据。

## 已实际检查的来源

| 来源 | 检查范围与版本 | 本任务用途与边界 |
|---|---|---|
| [vertesan/gakumasu-diff](https://github.com/vertesan/gakumasu-diff) | 已克隆、转换 284 张表；commit `571dbb62601e78998cddeacdbce3ea1bc672d7fc`，09-07 08:03:22 UTC | 主数据定义 ID、卡变体、成长效果、支援/回忆能力、路线配置的第一查询源；数据表不等同于完整运行时语义 |
| [surisuririsu/gakumas-tools](https://github.com/surisuririsu/gakumas-tools) | 远端 HEAD 与已有只读副本一致：`6c3d00648c32ea72a05086a18c63ab62e0d0c7e5`，09-05；读取 data JSON、Effects.md、CardManager、Executor | 当前 870 条卡记录、111 条自定义记录；独立人工 DSL/引擎可验证等级和取整。数字 ID 不可直接填主数据 ID |
| [tyuukiti/gakumasu-calc](https://github.com/tyuukiti/gakumasu-calc) | 新找到并只读克隆：`3dc57ce5257f9a2700b61a3e820bf74fbb7a63ba`，08-31；读取 HIF 日程 YAML、状态计算入口、回忆/面板配置 | 支援编成和属性理论值对照，有四回忆及 HIF 面板；不是打牌状态机，也不能证明明星性→得分倍率公式 |
| [Vibbit 的 Contest 算法原始分析](https://blog.vibbit.me/2024/11/gkms-contest-simulator/) | 搜索缓存可读取作者 2024-11 的 v1.6.0 分析；直接打开曾超时 | 源作者逆向记录可帮助解释 AutoEvaluation/成长/触发权重表；这是旧版算法说明，不能当作当前全部效果的完整实现 |
| [kjirou/gakumas-core](https://github.com/kjirou/gakumas-core) | 在线核对项目 README；Arena 原有录像回归保留其来源 | 课内不可变状态、动作边界和旧卡录像参考；不覆盖完整培育路线 |
| [skyfsj/gakumas-rl](https://github.com/skyfsj/gakumas-rl) | 在线确认公开项目，核对本仓库 vendored provenance | 当前 Arena 已建立在其代码基础上；调研中“没有现成 RL 环境”不能继续作为当前事实 |
| [imas-tools/gakumas-master-translation](https://github.com/imas-tools/gakumas-master-translation) | README 明确 YAML→JSON→翻译映射流程，引用 gakumasu-diff | 可提供中文名/OCR 别名；与原始数值表同源，不是额外一套规则证据 |
| [AllenHeartcore/GkmasObjectManager](https://github.com/AllenHeartcore/GkmasObjectManager) | 在线读取 README 的 manifest/ProtoDB/JSON/CSV 与资产导出说明 | 新找到的资源清单和资产解包工具；这类 object database 不等于卡牌数值 master 表，本轮未执行取游戏资源的工具 |
| [DreamGallery/HatsuboshiToolkit](https://github.com/DreamGallery/HatsuboshiToolkit) | 在线核对 README 的 octo 缓存输入与版本差分流程 | 资源清单解析链的来源追踪；当前已有公开 master 快照，不需要接入客户端 |
| [tyuukiti/gakumasu-anomaly-sim](https://github.com/tyuukiti/gakumasu-anomaly-sim) | 在线核对 README | 新找到的アノマリー末回合搜索参考；只适用于局部解题，不是 HIF 全流程引擎，本轮未运行其代码 |

此外，GameVika 卡库明确派生自 gakumas-tools/gakumasu-diff；ADV/剧情数据库侧重资源及台词。
它们可辅助查找名称，但本轮技术结论引用上游数据和原作者实现。

## 主数据字段与具体落点

可复跑命令：

```powershell
.venv/Scripts/python.exe scripts/audit_live_reference_data.py --reference ../gakumas-tools-reference
```

产物 [live_card_reference.json](../examples/live_card_reference.json) 包含 source commit、12 张相关表的
SHA256 与行数、四张目标卡的原始费用和全部自定义等级。数据更新后可以按指纹定位差异。
下列行数包含变体，不等于独立卡种数。

| 表 | 本快照行数 | 使用方式 |
|---|---:|---|
| ProduceCard | 1714 | definition_id + upgradeCount 联合定位；不能只用名字/+号 |
| ProduceCardCustomize / ProduceCardGrowEffect | 343 / 453 | customize ID + 当前等级 → 实际成长/费用/附加效果 |
| MemoryGift / MemoryAbility | 21 / 575 | 示例回忆来源、能力和获得阶段；不是用户拥有的所有回忆实例数据库 |
| ProduceCardRandomPool | 313 | 指定 pool ID 下的卡及 ratio；不能外推为所有课程、咨询和事件的统一概率 |
| ProduceExamBattleScoreConfig | 4108 | 按具体配置 ID 查询属性换算；不能把全场景评分公式混成一条 |
| ProduceExamAutoEvaluation | 11130 | 当前有 53 种 evaluationType，按玩法/流派/remainingTerm 查询 |
| ProduceExamAutoGrowEffectEvaluation / AutoTriggerEvaluation / AutoCardSelectEvaluation | 3710 / 315 / 210 | 成长、触发、选卡的评估项；只搬一个总权重表会漏掉语义 |

## 四张目标回忆卡与本次修复

| 日文卡名 | master definition_id（均 upgrade_count=1） | 社区参考 ID | 最大自定义次数 |
|---|---|---:|---:|
| 脚光+ | p_card-01-act-3_185 | 762 | 1 |
| 国民的アイドル+ | p_card-01-men-3_006 | 163 | 1 |
| シュプレヒコール+ | p_card-01-act-2_001 | 87 | 1 |
| 精神統一+ | p_card-01-men-2_104 | 752 | 2 |

上表核对名称和强化级，详细效果仍须按 JSON 中的字段逐项对照；不声称两引擎全部语义等价。
这些 ID 解决了“卡定义是什么”；哪张回忆副本、实际自定义、获得阶段仍由 adapter 详情证据决定。
导出文件将三者保留 null，不用当前图鉴默认变体填实机配置。

原 helper 把同一个自定义的每级效果累加。主数据的精神統一+ 集中自定义
`p_card_custom-wrapper-p_card-01-men-2_104-b-01`：Lv1 对应 +1，Lv2 对应 **总计 +3**；
元气自定义 `...-c-01`：Lv1 +4，Lv2 **总计 +13**。
[独立引擎 CardManager](https://github.com/surisuririsu/gakumas-tools/blob/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/packages/gakumas-engine/engine/CardManager/index.js)
仅选择当前等级的 patch，与主数据一致。
现已改为替换该自定义的上一级效果；其他来源的成长保留。回归覆盖一次导入 Lv2、逐级购买 Lv2、
以及同类型外部成长不被删除，断言不再出现错误的 +4/+17。

シュプレ+ 原始集中费用 2；费用自定义减 1，实际成本为 1。
这不代表实机当前シュプレ一定选了减费；历史证据中读到的实际费用 2 仍应照实记录。

## 对两篇补充报告的修正

- “每步 ceil”过于简略。当前独立引擎
  [resolveScore](https://github.com/surisuririsu/gakumas-tools/blob/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/packages/gakumas-engine/engine/Executor/resolvers.js)
  在基础值、组合倍率、属性倍率三处取整，与 Arena 核心分组相符；不支持每次标量乘法后都 ceil 的改法。
- 当前 monorepo 有 [BSD-3-Clause LICENSE](https://github.com/surisuririsu/gakumas-tools/blob/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/LICENSE)。
  旧 standalone 仓库的描述不能套到现行包。本次摘取的社区卡/自定义记录附 [原许可证](reference_licenses/gakumas-tools.txt)。
- AutoPlay 不能只照搬报告中的 r1–r19：作者后续分析已经扩为 29 项；当前 master 又包含更多 evaluationType。
  需要以现版本字段和对应执行语义重建，再用实际出牌记录验证。
- 原始数据能回答静态 ID、费用和变体；它们不自动回答隐藏时序、随机池选取方式、未公开算法或实机当前状态。

## 留待证据确认的规则

本轮 MemoryGift 中 16 条标 ProduceStart、5 条标 EndAuditionMid。
枚举名称能证实两种获得阶段，不能单独证明 HIF 的 EndAuditionMid 对应选拔 1 还是其他节点。
保留当前可配置默认及 TODO；需要一组结果确认前后牌组变化。
HIF 理论值计算器的日程可交叉检查课程/考试属性收益，但尚不能据其推导明星性收益曲线和分数倍率。
因此 A3/A4 的推断标记仍保留，未按模拟通关率改公式。

后续采用顺序：先用该 JSON 完成真实奖励/咨询识别对照 → 接收最小实机结果样本 → 核实回忆时机和
HIF 换算 → 再扩考试状态绑定与策略评估。协议入口和当前可联调范围见 [LIVE_CONTRACT](../LIVE_CONTRACT.md)。
