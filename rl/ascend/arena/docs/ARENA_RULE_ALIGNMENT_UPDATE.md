# Arena 底层行为对齐：阶段交付

后续更新：[规则v4：触发字典序默认](ARENA_TRIGGER_ORDER_UPDATE.md)。下文保留v3实施与验收历史；当前排序政策以新版行为契约为准，精细排序校准暂缓。

2026-09-08。用户已授权按新效果／结算报告修正行为，模糊部分保留暂定规则并由后续实机日志对拍。工作位于现有 `codex/arena-live-bridge` 工作树，只修改 Arena。

依据：[历史审计与17个合成反例／正例](research/effect_order_comparison_2026-09-08.md)。历史审计及 JSON 保留原样，实施后的结果另行输出。E1/E2 的明确规则作为本轮实现目标，不能把合成通过标为实机1:1。

| 阶段 | 范围 | 状态 |
|---|---|---|
| S1 | 集中／好印象强化：获取、出分贡献、自然结算分开 | 已完成；整数向量与获取量隔离通过，混合舍入仍待实机 |
| S2 | 批次资格、卡内条件、费用事件、开始／结束阶段 | 已完成；条件冻结而数值保持实时，开始后不再每卡触发 |
| S3 | 自动使用准备队列、条件失败、再演首次注册和来源语义 | 已完成；自动卡内部选择、恢复与预览通过 |
| S4 | 行动数寿命、负面解除、全力边界、版本与恢复验证 | 已完成；完整回归623通过、3跳过 |

恢复与去重约束：新增执行状态必须参与快照；ContentExam旧规则快照通过规则digest拒绝跨版本重放。实况 `submitted/uncertain` 保留原命令、command_id和消费账本，不因为引擎变更重新发出命令。

## 交付入口与变更

- [行为与字段契约](ENGINE_RULE_CONTRACT.md)：共享机制、阶段顺序、次数／寿命、来源和版本兼容。
- [最小可执行 JSON](examples/rule_alignment_minimal.json) 与 [独立预期](examples/rule_alignment_minimal.expected.json)：只定义效果、触发器、被动和一张空白卡，无卡名特判。第一回合集中3、分数0；第二回合集中6、分数14。
- [修正后的17项对照](research/effect_order_alignment_2026-09-08.json)：保留参考预期、证据等级、合成内容包与实施代码SHA256。原 [4一致／13差异审计](research/effect_order_audit_2026-09-08.json) 未覆盖。
- [实机采样清单](RULE_ALIGNMENT_LOG_REQUESTS.md)：U01–U08以及另外四项旧规则／组合边界的当前政策和可区分实验。
- [真实卡牌操作版](RULE_ALIGNMENT_REAL_CARD_RECIPES.md)：已补实际偶像/支援取得来源、强化等级、操作步骤及候选结果；A/B/C可优先采样。方案按固定主数据核验，尚未操作游戏取得实测日志。

本次采样范围按用户最新要求收敛为HIF；偶像之路专属麻烦（如パニック）与偏门跨模式组合暂缓，未验证项不再一律作为HIF完成前置要求。操作版已核对41个真实定义、9个偶像归属、2条支援取得事件链及付费自动卡的HIF能力来源。

本轮修改共享 runtime、效果上下文、阶段批次和配置编译入口；不按卡牌或道具ID修补行为。新增 `resolution.py` 集中管理资格收集、准备使用队列和实例寿命。好印象／好调完全耗尽后再次获得视为新寿命；仍存在时续加保留旧寿命。延迟直接来源保留资源事件（包括やる気增加次数），但不错误继承卡身成长。

实际使用计数和玩家行动窗口分开；上一张主动／心态卡用实例身份表示并跨回合保存。阶段轨迹记录 `trigger_batch`、`card_prepared`、`enchant_triggered`、`turn_draw_completed`，供合成诊断。它们是模拟日志，不是新增 adapter 输入字段。

## 验收

- 参考定向探针：**17/17 符合**。这些是刻意选择的规则样例，不是游戏正确率。
- 新增数值、批次、生命周期、来源、选择与恢复回归：`test_effect_order_alignment.py` 与 `test_resolution_lifecycle.py`；现代真实卡面和开始后饮料另在 `test_catalogue.py` 验证。
- 全量 pytest：**623 passed、3 skipped、0 failed**，230.43秒；包含九段录像、实况submitted/uncertain原命令恢复与去重，以及奖励／咨询接口回归。新数值／生命周期两个文件合计46个测试。
- 当前目录独立考试准入：**1,714 个卡牌变体、29 种饮料、699 条考试 P 道具，共2,442条**。合成12回合运行检查 **2,442通过、0错误**；58个卡牌／饮料探针未达到使用条件。P道具探针不证明所有触发条件均发动；此检查不是数值或交互认证。
- 原生导出与机制目录已更新；原始主数据仍为 `571dbb62601e78998cddeacdbce3ea1bc672d7fc`，没有修改或升级原始数据快照。339条含其他生命周期需求的P道具仍明确不支持独立考试装配。

九段既有录像参与正常回归。两段2024藤田ことね录像使用历史「星屑センセーション」卡面：固定 [gakumasu-diff 4202981](https://github.com/vertesan/gakumasu-diff/blob/4202981ce2e36107e30ef22393e14ee7427c4f91/ProduceCard.yaml) 的效果列表；[来源摘要及文件SHA256](research/historical_hoshikuzu_2024.json) 随仓库保留。现代卡面新增的条件效果现在正确执行，不能套用于旧录像。仅修改两份fixture的setup.card_overrides；所有动作、逐回合与最终分数期望保持原样。另以当前真实卡面的好印象9／10边界测试确保新效果不会再次漏执行。

复现命令（Arena根目录）：

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -q
.venv/Scripts/python.exe -X utf8 -m scripts.audit_effect_order_reference
.venv/Scripts/python.exe -X utf8 -m scripts.audit_catalogue --output data/catalogue/validation.json
.venv/Scripts/python.exe -X utf8 -m gakumas_arena.content validate docs/examples/rule_alignment_minimal.json
```

## 兼容与下一步

`arena-content-rules/3`、`arena-native-exam-capabilities/3` 已升级。内容包仍用 `arena-content/1`，原有字段和创作流程兼容；旧规则模拟快照因digest不同明确拒绝，不能悄悄按新行为回放旧存档。实况事务及奖励／咨询接口保持原协议；没有修改识别、映射、持久化日志、Maa或游戏操作。

`StartPlay` 在离线模拟中已确定为回合开始后并接通；这不代表预约、再演、卡绑定历史等全部实况字段已支持。实况继续区分缺少观察需补读与机制尚不支持，不用模拟状态填造实机历史。

按后续用户取舍，精细排序先用默认并暂缓校准，继续推进P道具培育生命周期与官方流程迁移；舍入、行动数合并等可独立顺手采样，不再以完成所有采样为前置条件。本轮不训练RL，也不以通关率调规则。在线HTML仍是此前发布版本，本轮更新保存在Arena仓库。
