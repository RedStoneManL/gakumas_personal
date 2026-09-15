# HIF 普通卡定制：PLv76 范围及全组合验收

本次修复后，全部 **2,333 种合法有序配置**都能通过真实 `GoldenProduceBridge.entry`，并在 pinned native 引擎中完成编译及考试开场。独立对照的标量效果也全部一致。这里不使用定制数组的位置配对。

## 范围如何计算

起点是当前主数据 `unlockProducerLevel <= 76` 的普通来源卡，取 Common 及三个计划的并集；排除 `libraryHidden`、`isLimited`、`originIdolCardId`、`originSupportCardId`、`isInitialDeckProduceCard`。保留账户 Switch 两端的可选定义，不因某局已持有、排除或 noDup 状态缩小覆盖面。

| 口径 | 数量 |
|---|---:|
| 主数据过滤后的定义 | 190 |
| Common / Sense / Logic / Anomaly | 10 / 60 / 60 / 60 |
| 实际存在的基础及强化卡面 | 354 |
| 具有定制的定义/强化面 | 164 |
| 无定制边界定义：25 Legend + 眠気 | 26 |
| 每卡定制分支引用 | 426 |
| 不同 master 定制 ID | 160 |
| 全部合法有序配置，含空配置和中间等级 | 2,333 |
| 不计获得顺序的等级组合 | 1,503 |

190 是主数据筛选所得的**审计超集**，并非认证为真实 PLv76 普通奖励池。26 张无定制边界卡仅验证现存基础面，因此卡面数不是 380。

## 主数据 164 张与 native 160 张的差异

native 的 `sourceType=produce && unlockPlv<=76` 可定制集合是上述 164 张的真子集，没有其他差集。多出的四张在主数据中解锁等级为 0，native 明确标为 77–80。全部保留测试，未静默剔除。

| 主数据定义 | 强化卡名 | master 解锁 | native ID / 解锁 |
|---|---|---:|---|
| `p_card-03-act-3_188` | エンターテイナー+ | 0 | 774 / PLv77 |
| `p_card-01-act-3_184` | 話題沸騰+ | 0 | 776 / PLv78 |
| `p_card-02-act-3_187` | びしっとキメ顔+ | 0 | 778 / PLv79 |
| `p_card-03-act-3_189` | 羽ばたけ！+ | 0 | 780 / PLv80 |

四张 native 来源均为 `produce`，不是来源类型过滤造成的差异。进一步走真实奖励池确认：它们均为账户 Switch 的转换后卡，`ProduceCardConversion.conditionSetId` 已分别设置 PLv77–80。默认未启用时会映回旧卡，低于门槛强行启用会被原解析器拒绝，达到等级且启用后才进入对应计划的候选池。因此这不是已证实的提前掉落问题，也没有保留额外生产门槛改动。

`tests/test_hif_golden_reward_unlocks.py` 覆盖两剧本、三个计划、PLv76–80 的真实 `_selection_card_pool`，并核对基础/+面 native ID、解锁等级及四种提前开启拒绝。与既有奖励控制测试共 44 项通过。独立机器可读对账见 `build/hif_plv76_customizations/scope_reconciliation.json`。

## 修复前后证据

| 检查 | 修复前 | 修复后 |
|---|---:|---:|
| 入口构造通过 | 1,201 | 2,333 |
| 入口构造失败 | 1,132，涉及125定义 | 0 |
| 可构造但标量错误 | 119配置，涉及40定义 | 0 |
| native 编译、开场及标量值检查 | 未运行 | 2,333通过、0失败 |

修复前的 119 个静默差异是普通 `CostReduce` 被写成负的 `g.cost`；native 用正增量表示减费。复核直接读取不可变的旧入口字典，没有回退生产代码或改写旧证据。

独立分支比对结果：250 分支按完整逐级数值、价格及最大等级唯一匹配；174 个结构分支保留原始主数据和 native DSL 供结构语义测试；另有以下两种标量对应差异。桥接通过和开场通过不替代对结构效果执行行为的独立测试。

| 卡 | 差异 | 取舍 |
|---|---|---|
| 元気な挨拶+ | master 穿透消耗减1；native custom29 为通用 `g.cost+=2` | 按用户选定 golden，使用该卡显式覆盖；不泛化给所有穿透消耗 |
| 届いて！+ | 效果同为 `g.scoreByGenki+=1`；master100P，native参考价格70P | 效果使用 native；培育收费保留 master100P |
| ハイタッチ+ | 结构分支 master 增加元气9，native custom27 增加元气4 | 显式 golden 优先；由结构效果测试覆盖 |

## 复现与文件

```powershell
.venv/Scripts/python.exe -X utf8 scripts/audit_hif_plv76_customizations.py --compile-native --require-zero-gaps --baseline build/hif_plv76_customizations/before.json --output build/hif_plv76_customizations/after.json
.venv/Scripts/python.exe -X utf8 -m pytest -q tests/test_hif_plv76_customization_inventory.py
```

审计新增文件：`scripts/audit_hif_plv76_customizations.py`、同名 `.mjs`、`tests/test_hif_plv76_customization_inventory.py`。没有修改生产桥接代码。Node 批量复用模块，但每个配置建立独立 native 上下文，只编译并开场，不运行策略或 RL。

产物 `before.json/.md` 保留原始失败；`after.json/.md` 保存逐卡、逐分支、逐次序结果及八份有效生产/数据文件 SHA256。`integration_snapshot.json/.md` 是修复过程中仍有两项缺口的中间快照，不能当作最终结果。

最终已重新核对八份文件哈希，均与冻结代码一致。

- `after.json`: `c45c19a977b011429838adc9522b123570de06b4fc30c4d078a6e3d9931572ae`
- `before.json`: `2fa460ccba35993549d55f3e48ffe5fc28c283dd023854b15f89468ee0ce09b4`
