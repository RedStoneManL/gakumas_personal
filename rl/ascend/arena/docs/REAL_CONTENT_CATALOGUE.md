# 真实内容目录与复用流程

> **最新补充（2026-09-08）**：共享结算与开始后阶段已修正，独立考试准入为 **1714卡牌版本、29饮料、699 P道具，共2442条**，合成运行检查全部通过，58个卡／饮料探针未达到使用条件。阶段、证据限制和实机待查项见 [规则交付](ARENA_RULE_ALIGNMENT_UPDATE.md)。本地导出已更新；在线页面仍是此前版本。原始收录总量和数据revision不变。

2026-09-08。底座可以组合内容，但仍需补齐部分机制、官方剧本流程和实机数值验证；不是只剩事件录入。

## 数据范围与在线来源

主要来源是社区维护的 [gakumasu-diff 主数据库](https://github.com/vertesan/gakumasu-diff)，本轮通过 `git ls-remote` 核对在线 HEAD 与本地一致：`571dbb62601e78998cddeacdbce3ea1bc672d7fc`。
同时核对了 [Gakumas Tools 图鉴入口](https://gktools.ris.moe/en/dex) 与 [学マス Wiki](https://seesaawiki.jp/gakumasu/) 的内容分类。
Wiki 用于交叉参考，未复制文章、剧情或图片；没有用网页描述推导数值，也没有复制第三方模拟器代码。

统计单位必须区分：技能卡 ID、强化版本、P 道具的独立定义不是同一单位。

| 类别 | 定义行数 | 不同 ID | 说明 |
|---|---:|---:|---|
| 技能卡 | 1714 | 448 | 每个 upgradeCount 单独保留 |
| P 饮料 | 29 | 29 | 包括隐藏定义 |
| P 道具 | 1038 | 1038 | 包括固有、强化、挑战、塔、活动及隐藏定义 |
| 自定义 P 道具 | 180 | 180 | 培育触发与升级组合 |
| 偶像卡 | 151 | 151 | 固有卡、前后 P 道具、角色、成长表关联 |
| 支援卡 | 201 | 201 | 等级技能与事件奖励关联 |
| 角色 | 24 | 24 | 包括不可育成角色，不能视为 24 名可选偶像 |
| 通用道具 | 352 | 352 | 票券、材料等，不属于考试动作 |
| 回忆能力 | 575 | 575 | skillId → ProduceSkill，保留级别 |
| 固定回忆 | 21 | 21 | 预置卡与能力、考试物品关联 |
| 卡牌自定义 | 343 | 256 | customizeCount 不合并 |

共 4628 条主目录定义。`manifest.json` 固定全部 286 个 YAML 文件的 SHA256；此前报告写 284 是旧统计，本轮按实际文件重计。原始快照没有修改。
范围是该快照包含的全部定义，不承诺覆盖游戏服务端尚未公开的数据，也不推断当前可获得性。`libraryHidden`、`viewStartTime`、`isLimited` 保留原值。

## 数据契约

公共 Python API：`gakumas_arena.catalogue.Catalogue`。独立于 adapter，可直接离线使用。

```python
from gakumas_arena.catalogue import Catalogue

c = Catalogue()
hits = c.search("軽い足取り", kind="cards")
detail = c.inspect("cards/p_card-01-act-1_002@0")
card = c.definition("cards/p_card-01-act-1_002@0")
```

- 主目录：`arena-catalogue/1`，稳定键 `cards/<id>@<upgradeCount>`；卡牌自定义使用 `@<customizeCount>`；其他种类用 `<kind>/<id>`。
- `id` 始终是原始主数据 ID。不会按同名合并，不会将不存在的强化版本退回基础版。
- `name_ja` 是原名；`name` 在已有本地翻译存在时采用译名，否则回退原名。没有伪造完整中文翻译覆盖。
- `references` 是 `{table,id,path}`，指向原始字段路径。关系解析保留同 ID 的全部级别；执行时仍必须显式选定级别。
- `inspect` 返回当前行、反向主目录关联、递归效果/触发/成长依赖和缺失引用。
- 展示性 description 字段不导出；数值、枚举、ID、费用、次数、持续时间等从主数据保留。完整原始 YAML 仍是来源；导出不是 YAML 的无损备份。
- 原始来源版本、文件内容哈希与导出文件哈希均在清单中，不会在加载时自动联网更新。

最小字段样例见 [catalogue_entry.json](examples/catalogue_entry.json)。

## 收录、可运行、实况支持是不同状态

`offline_exam` 的分类：

| 值 | 含义 |
|---|---|
| eligible | 定义通过独立考试入口的结构/依赖检查，已有执行路径；不等于实机数值正确 |
| unsupported | 独立考试入口会明确拒绝，`issues` 带字段路径和机制原因 |
| not_applicable | 由角色编成、培育或其他资源系统使用，不是独立考试卡/饮料/P 道具 |

当前独立考试可接入：1714个卡牌版本、29种饮料、699条考试内P道具定义；另有339条P道具不能独立装配。此前被拒绝的主要机制及当前变化：

- `ambiguous_StartPlay`：旧拒绝原因；已按主数据原文和新报告绑定为“回合开始后”，不再每次出牌触发。
- `card_move_hooks_not_bound`：旧拒绝原因；自身进入手牌／保留的效果已接入。更广的移区交互仍需实机对拍。
- `item_requires_produce_lifecycle`：含培育阶段的触发、次数、间隔或收益，需要课程/购物/事件等上下文，不能只安装其中一部分考试效果。

对培育物品这一分类不代表“数据缺失”或“整个 Arena 完全没有该效果”，只是不能绕过培育生命周期直接装入这个独立考试入口。
自定义 P 道具、支援卡事件的原始表与关系已导出，但不因此宣称官方所有培育流程已完成迁移。

`live_definition_issues` 只检查实况机制范围。它不是当前观察状态，不能据此填造被动剩余次数、累计出牌数或最后触发时间。`arena-live/1` 及现有被动契约仍负责判断“需要补读”与“引擎不支持”，本轮没有修改其恢复、submitted/uncertain 原命令或去重协议。

## 不再逐张实现：直接引用真实定义

技能卡已能以 ID + upgrade 引用；本轮为饮料和可支持的原生考试 P 道具补上了同样入口。
可运行最小包：[real_inventory_exam.json](examples/real_inventory_exam.json)。卡与物品来自真实主数据，但试镜规则和初始状态是明确标注的合成数据。

```python
from gakumas_arena.content import compile_pack

content = compile_pack("docs/examples/real_inventory_exam.json")
exam = content.create_exam("real_inventory_demo/exam", seed=0)
exam.act("drink:0", revision=0)
print(exam.view())
```

P 道具按照 ProduceItem → ProduceItemEffect → ProduceExamStatusEnchant 链安装。持续回合和次数读取原始定义；非正值表示该层无限。每个物品槽保留独立 source_identity，多个副本不会合并次数。
遇到含培育效果或未支持依赖的物品，编译即报错，不能静默丢弃这部分效果。奖励和初始库存中的饮料也通过同一检查。

创建改版卡时，在自己的命名空间定义效果与卡组合，参照 [内容创作指南](CONTENT_AUTHORING.md)。真实条目用于参考或直接引用，不能覆盖原始 ID。新增卡没有新机制时只加配置；新增机制时扩展通用操作和测试，不能加按卡 ID 分支。

偶像和支援卡的等级装配继续用已有 `gakumas_rl.idol_config.build_idol_loadout`：显式提供 `idol_card_id`、`idol_rank`、`potential_level`、`prima_stella_level`，支援编成为 `selected_support_card_ids` 与对应 `selected_support_card_levels`。不要把各级技能同时安装，也不要把 before/after 物品同时当成当前固有道具。关联目录用于找到这些定义，现有 loadout 负责按当前等级取值。

## 导出、查询与更新

在 Arena 目录执行：

```powershell
.venv/Scripts/python.exe -m gakumas_arena.catalogue search "軽い足取り" --kind cards
.venv/Scripts/python.exe -m gakumas_arena.catalogue inspect "cards/p_card-01-act-1_002@0"
.venv/Scripts/python.exe -m gakumas_arena.catalogue export data/catalogue --output .gakumas_rl_cache/catalogue-export.json
.venv/Scripts/python.exe -m gakumas_arena.catalogue verify data/catalogue/manifest.json
.venv/Scripts/python.exe scripts/audit_catalogue.py
```

- `data/catalogue/catalogue.json`：所有主目录条目、支持状态、关系和数据版本。
- `data/catalogue/catalogue.sqlite3`：可离线查询的规范化原始行与关系。生成文件约 128 MiB，Git 忽略，按上述命令可重建。
- `data/catalogue/manifest.json`：源文件哈希、数量、导出校验和。
- `data/catalogue/validation.json`：逐项合成运行结果。与目录分开，不把 smoke test 当成实机认证。

SQL 示例：

```sql
SELECT native_id, variant, name, offline_exam FROM entries WHERE kind = 'cards';
SELECT payload FROM definitions WHERE table_name = 'ProduceSkill' AND native_id = ?;
SELECT source_table, source_row_key, field_path FROM relations
WHERE target_table = 'ProduceItem' AND target_id = ?;
```

外部引用可能指向未导出的非游戏机制表，仍可按原始表名回到固定快照；关联边不是“已完整实现该功能”的证据。
未来更新数据：先在隔离快照中查看上游差异、重新生成清单和目录、运行合成检查及相关测试、检查新增 unsupported，再更新交付记录。不要直接在运行中的会话下修改数据版本。

## 验证结果与实机限制

2,370 个 eligible 条目逐项完成 12 回合合成探针，无运行异常；其中 57 个卡牌探针未达到出牌条件，明确保留 `condition_reached=false`。P 道具检查确认安装与回合推进，不能据此声称所有触发条件都覆盖。
测试另外覆盖真实饮料消耗后恢复、P 道具第 8 回合仅触发一次、同物品双实例、未支持物品提前拒绝、所有强化版本保留及 SQL 导出。
本轮发现并修复通用延迟效果的 `chainProduceExamEffectIds` 列表执行，保留原单个 ID 字段，按定义顺序调度。没有为任何具体卡写分支。

在线目录：[真实内容目录](https://arena-system-report.redstonemanliu.chatgpt.site/catalogue.html)。与原报告同一站点，保持原有私人访问范围。
