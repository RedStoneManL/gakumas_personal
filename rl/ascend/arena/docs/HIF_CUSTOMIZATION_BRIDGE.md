# HIF 绿豆定制转入考试：修复与 RL 入口

2026-09-10。PLv ≤ 76 普通卡范围的定制转接阻塞已修复。沿用用户指定的 pinned gktools 作为考试效果 golden；无需追加实机校准。

**同日用户实机证据更新：**用户确认元气 +9、固定体力费用 2、价格 100 P。前两项现通过 `live-game-corrections/20260910-1` 修正卡目录引用，TrainingExam／培育桥接统一使用；第三项价格原已正确。原始上游文件保留。[实机证据和来源说明](GOLDEN_DIFFERENCES_TO_VERIFY.md)，[修正后 2,333 配置审计](../build/hif_customization_game_verified_20260910/after.json)。下表的 226 项结果及原 manifest 属于此次实机数据修正之前的版本，不替代新版本验收。

补丁版已完成 **186 项测试，0 失败**，包含修正值的实际执行、原始版本差异、临时支援强化与定制组合、两类快照恢复、全局培育以及独立 2,333 配置审计。[当前验收 manifest](../build/hif_customization_game_verified_20260910/ready_manifest.json) 保存本版 effective hash；不能与旧基线 manifest 混用。

## 问题与修复

旧转接主要将 `growEffectIds` 转为标量增长，无法完整表达追加动作、开局入手、取消一次性限制、修改条件、替换持续效果等定制。旧普通体力减费还将 `g.cost` 写成负数，造成反向增加消耗：`スタートダッシュ+` 减费 2 后，体力 40 被扣至 33，正确 golden 结果是 37。

现在按卡片实际的 `customizedProduceCardCustomizeIds` 统计最终等级，映射为原生 `customizations`，由 golden 编译、执行。重复升级只使用最终累计值；对应的 grow 按出现次数消费，其他独立永久成长仍保留在 `growth`，不会双算。暂时支援强化、发动顺序、卡片移动及存档恢复继续由同一原生机制处理。

映射校验卡片可选分支、总定制上限、分支等级、完整累计 grow、主数据递归效果来源及原生定义的 SHA256。来源改变或未知分支仍报明确错误，防止悄悄丢掉效果。

实现：[转接](../gakumas_arena/produce/customization_bridge.py)、[固定映射表](../gakumas_arena/produce/data/customization_registry.json)、[考试入口](../gakumas_arena/produce/golden.py)。映射表位于已纳入安装包及培育 checkpoint 版本校验的 `produce/data`。

## 验证范围

| 项目 | 结果 |
|---|---:|
| Common／Sense／Logic／Anomaly 范围内定义 | 190 |
| 基础／强化卡面 | 354 |
| 可定制卡定义 | 160 张 PLv ≤ 76 ＋ 4 张扩展边界例 |
| 定制分支引用 | 426 |
| 合法有序配置，含空配置和中间等级 | 2,333 |
| 去掉添加次序后的等级组合 | 1,503 |
| 修复前转接失败 | 1,132 |
| 修复后转接、原生编译／开场失败 | **0** |
| 定制专项测试 | **52 通过** |
| 独立审计测试，含整组原生编译／开场 | **6 通过** |
| 培育、交接、课程、奖励、生命周期、快照、P 道具与支援相邻回归 | **124 通过** |
| Switch 等级边界与既有奖励控制 | **44 通过** |

审计集合按主数据等级筛选，覆盖 PLv ≤ 76、所有计划、账户 Switch 两端；不按当前持有卡片筛掉候选。排除隐藏、限定、初始基本牌和偶像／支援来源牌。对账发现 4 张主数据等级为 0、golden 等级为 77–80 的牌也被纳入；它们作为额外覆盖保留，不能称为 76 级内牌。另含 25 张无定制 Legend 与眠気边界例。登记表还覆盖若干独立匹配成功的范围外卡片，但不能据此声称全部特殊来源、全部等级都已穷举。

上述 4 张是账户 Switch 的转换后卡面；既有转换条件已分别要求 77／78／79／80 级，低等级开关会拒绝，关闭开关时奖励池使用转换前卡片。因此原始字段差异并不构成推荐 HIF 入口提前掉落；本次没有改动等级门槛。

2,333 例核查入口、原生编译、开场及独立标量对照；专项测试进一步检查真实动作与正反条件边界、延迟效果、选牌、移除／弃牌、开局抽牌和逐步恢复。穷举入口不冒充所有战局轨迹穷举。

原始证据：[本次验收 manifest](../build/hif_plv76_customizations/ready_manifest.json)、[修复前](../build/hif_plv76_customizations/before.json)、[修复后明细](../build/hif_plv76_customizations/after.json)、[可读审计](HIF_PLV76_CUSTOMIZATION_AUDIT.md)。JSON 保存完整分支、逐配置结果和源码／数据 hash。本次四组测试合计 **226 通过、0 失败**。

## Golden 与主数据差异

| 卡片 | 主数据 | 实际执行／计费 |
|---|---|---|
| ハイタッチ+ | 追加元气 9 | 用户确认后，修正为原生定制 28，追加元气 **9**；原始版本误引定制 27（+4） |
| 元気な挨拶+ | 固定体力费用 3 → 2 | 用户截图确认后，修正为原生定制 30，实际扣 **2**；原始版本误引普通费用定制 29，仍扣 3 |
| 届いて！+ | 该分支价格 100 P | 效果与 golden 定制 11 相同；培育仍扣 **100 P**，原生图鉴标价 70 P 不参与培育扣费 |

前两项已由用户新证据覆盖此前的临时 golden 优先取舍；第三项价格始终取培育主数据。每次映射保存来源与差异：直接调用后读取 `bridge.last_customization_provenance`，完成考试后读取 `run.exam_history[-1]['result']['customization_bridge']`。修正卡的 `catalogue_override` 包含原始／有效卡片 hash、前后定制 ID、补丁版本及证据来源。该信息在考试入口之外保存，避免污染原生输入 schema。

历史核对明确原始版本的「元気な挨拶+」定制实际不减费：无增益时未定制与定制后均为体力 40 → 37。现依据用户证据改引固定费用减 1，定制后为 40 → 38。结算核心不变，改变的是这张卡引用的定制数据。

## RL 怎么使用

现有 `create_hif_training_produce` 和定制选择接口不变。通过正常定制动作，或通过 `apply_card_customizations(repository, card, ids)` 构造定制卡；考试入口自动转换。不要自行复制已消费的绿豆增长到 `growth`，也不要仅写一个未知 grow ID 代替完整定制来源。

更新后重启本地训练 worker，并为新批次保存新的培育规则 hash。旧 checkpoint 与旧版条件模拟结果保留其原版本证据；本次未操作已有训练进程、策略或权重。

在 Arena 目录复跑：

```powershell
.venv/Scripts/python.exe -X utf8 scripts/audit_hif_plv76_customizations.py --compile-native --require-zero-gaps --output build/hif_plv76_customizations/recheck.json
.venv/Scripts/python.exe -m pytest tests/test_produce_customization_contract.py tests/test_produce_customization_semantics.py tests/test_produce_buff_growth.py tests/test_produce_typed_cost_growth.py tests/test_produce_structural_customization.py -q
```

维护映射时运行 `.venv/Scripts/python.exe -X utf8 scripts/build_customization_registry.py`，默认只检查再生成结果是否与固定表一致。`--output` 可写候选文件供审阅；复杂效果和已知冲突有独立固化的来源校验，来源变化需要重新检查对应效果。按用户 2026-09-10 最新决定，明确的事实冲突统一以 `gakumasu-diff` 为准，不能新增“上游 golden 优先”例外来保留错误数值；见[数据权威约定](DATA_AUTHORITY.md)。
