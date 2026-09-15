# 支援 / 回忆编成阶段：已有接口、规则与数据缺口

核查日期：2026-09-11。此次只读检查了 Arena 实现、主数据、已有实验配置、用户截图转录与本地官方帮助副本；未读取凭据，未修改训练或 Arena 核心。

后续范围更新：用户已选择研究环境，允许使用全支援图鉴，并要求使用明确生成的金色因子回忆候选；不要求复现个人拥有清单。跨 Plan 回忆作为研究偏好从候选中排除，不修改 Arena 的现有拒绝。下文保留最初账号模式审计事实，其中“需要真实库存”不再阻塞研究模式；21个 MemoryGift 也不是最终研究候选池默认。

## 结论

Arena 已能从完整支援和回忆配置启动真实培育。新工作主要是：在开局前加入模型选择支援/回忆的决策阶段；用账号实际候选库存和槽位规则生成合法动作；选择完成后调用现有初始化接口。偶像继续由环境均衡分配，不是模型动作。原“给定编成”模式可以保留。

当前不能把全图鉴、满级支援或 HIF 回忆能力模板当作用户已拥有的候选。已有五张自有支援、一张租借支援的历史实测子集；没有发现完整的当前账号支援仓库或可直接重建的回忆实例清单。

## 1. 已有接口

| 用途 | 位置与行为 |
|---|---|
| 完整输入 | `gakumas_rl/interfaces/service.py:46` 的 `LoadoutConfig`：偶像、PLv、rank、亲爱度、潜能、一番星、卡片切换、支援 IDs、逐卡等级、回忆等。 |
| JSON 转 typed | `gakumas_arena/produce/loadout_handoff.py:27` 的 `thaw_loadout`：深拷贝；将支援数组转 tuple；将回忆和携带卡记录转 frozen dataclass；不修改原配置。 |
| 解析和校验 | `gakumas_rl/interfaces/service.py:108` 的 `resolve_loadout`，最终调用 `idol_config.py:973` 附近的 `build_idol_loadout`。resolver 有 LRU 缓存，因此回忆和数组必须可哈希。 |
| 实际开局 | `gakumas_arena.produce.create_hif_training_produce(loadout=..., research_config=..., seed=..., exam_policy=..., produce_choice_selector=...)`。当前 FullProduceTask 已通过 `thaw_loadout` 走该路径。 |
| 选拔 / 本战交接 | `loadout_handoff.py:41` 的 `freeze_loadout` 保存解析后的实际支援、逐卡等级和完整回忆；后续不会重选编成。 |
| 实测信息导入 | `gakumas_arena/live/contracts.py` 的 `RunLoadout/SupportSetup/MemorySetup` 可表达未知字段和证据；`live/loadout.py:13` 的 `to_loadout_config` 对缺失字段拒绝转换，不自动套训练默认。 |

部分支援阵容不能直接送最终 resolver：显式非空手动支援阵容必须恰好六张。setup 应独立维护“已选实例”和“剩余候选”，填满后构造一次完整 `LoadoutConfig(auto_support_cards=False, support_card_ids=..., support_card_levels=..., memories=...)`。不要靠 `auto_support_cards=True` 补齐模型没选的槽位。

用于候选机制解析的现有内部函数：`idol_config._load_support_card_produce_skills(repository, support_cards)` 会按每张卡实际等级选最高已解锁技能级别，保留不同支援的同名技能贡献与装备顺序；`_load_memory_skills(repository, scenario, memories)` 解析具体能力与剧本适用范围。它们不是已存在的完整 setup 环境，应由新适配层封装。

## 2. 支援：游戏规则与当前校验

本地官方帮助 `design/hif-mechanics-20260909/official-produce-support-card-deck-edit.html` 明确：必须编成六张，其中一张必须从其他制作人租借。

当前 `_resolve_selected_support_cards`（`gakumas_rl/idol_config.py:784`）校验：

- 显式数组恰好六张；IDs 不重复；主数据存在。
- Plan 为 Common 或与偶像相同。
- `support_card_levels` 与 IDs 一一对应；逐卡等级必须在实现允许范围内。
- 等级缺失时会使用稀有度默认上限；当前 R/SR/SSR 为40/50/60。账号模式必须显式提供实测等级，不能触发此默认。

当前 `LoadoutConfig` 不保存 borrowed/rental 字段，也不检查“5自有+1租借”。`SupportSetup.borrowed` 虽可表达，转换为旧 LoadoutConfig 后该所有权信息不继续保存。新 setup 层需要把它留在候选和 episode/setup provenance 中，并在送入 Arena 前检查。

`SupportCardAutoSelectConfig.support_card_ids_pool` 支持白名单，但空白名单会使用整个合法 Plan 图鉴，而且只有一个统一等级参数。它是启发式自动编成器，不是用户库存接口，也不适合替代模型选择。

## 3. 回忆：完整对象与使用语义

`gakumas_rl/loadout.py:49`：

```text
ProduceMemoryCardSpec:
  card_id, upgrade_count, customize_ids（按获得顺序；重复ID表示同定制多级）,
  phase_type（ProduceStart 或 EndAuditionMid 的完整枚举）

ProduceMemorySpec:
  memory_id, idol_card_id（生成来源）, grade,
  produce_card（上述完整携带卡，可为空）, ability_ids, ability_levels,
  allowed_character_ids,
  vocal, dance, visual, stamina,
  exam_battle_produce_card_ids, exam_battle_produce_item_ids
```

回忆自身的 Vo/Da/Vi/HP 和 contest 牌/物品是对战快照，培育开局不直接把这些数值加到偶像身上。真正进入培育的是携带卡，以及通过 `MemoryAbility → ProduceSkill → ProduceEffect` 生效的能力。若能力本身增加初始属性，则由正常能力规则加算。

已有规则：

- 回忆生成自别的角色不等于不能使用；`idol_card_id` 是来源，不能据此禁止跨角色使用。只有 `allowed_character_ids` 的显式限制适用。
- ProduceStart 卡加入初始牌组；EndAuditionMid 卡由 `ProduceRuntime._grant_mid_audition_memory_cards`（`runtime.py:3136`）在首次中期考试确认通过后一次性发放。
- 相同“不可重复”携带卡不会授予多张；相关卡在培育候选中被预先保留排除，代码见 `produce/initial_deck.py`。
- `MemoryAbility.produceGroupIds` 限定剧本；`isUniqueActivation` 的同技能跨回忆只注册一次。
- 携带卡强化、定制与来源记号都保留，后续交接会冻结完整回忆信息。

本地官方 `official-produce-memory-deck-edit.html` 明确：最多四张回忆；最多一张可租借，租借消耗 money，每日最多三次。这些是账号操作限制，不能在离线训练中不声明地伪装成真实无限租借。

### 必须补齐的确定缺口

1. **回忆槽位和实例限制**：当前 resolver 不检查最多四张，也没有借用额度/拥有实例唯一性检查。必须在 setup 层先校验实际实例；相同能力可以来自不同真实回忆，不能用能力 ID 当实例身份。
2. **跨 Plan 回忆**：官方 `official-memory-memory-produce.html` 允许编成携带不同 Plan 卡的回忆，只是不获得该卡；能力仍按其自身适用规则处理。当前 `_resolve_memories` 在 `idol_config.py:614` 会因携带卡 Plan 不符而拒绝整个回忆。若支持真实自选回忆，需将“回忆可编成”和“携带卡可获得”分开；不能把当前更严的拒绝当作游戏规则。
3. **能力等级严格性**：当前 `_load_memory_skills`（约642行）会给缺失等级补1，找不到指定等级时回退该 ID 的第一行。账号候选应要求 `ability_ids/ability_levels` 长度一致且精确 ID+level 存在，避免静默改效果。
4. **借用卡的解锁规则**：本地官方帮助列出低PLv租借回忆的区间解锁规则，当前 memory resolver 没有 borrowed 参数，不能区分自有/租借解锁。当前文档所列区间止于PLv75，不应据此发明更高区间。PLv76也应按候选卡实际解锁条件校验。

## 4. 本地究竟有什么库存证据

`design/user-loadouts/hif-garakuta-hiro-20260909/loadout.json:1080` 是用户某次培育结果截图中看到的六支援，不是全仓库导出。截图所示培育日期为2026-06-28；不能假设今天等级未变，也不能将当时租借卡变成自有。

| 历史实测身份 | 支援ID | 当时等级 |
|---|---|---|
| 自有 | `s_card-3-0005` | 55 |
| 自有 | `s_card-3-0037` | 50 |
| 自有 | `s_card-2-0007` | 50 |
| 自有 | `s_card-3-0030` | 60 |
| 自有 | `s_card-3-0069` | 45 |
| 租借 | `s_card-3-0044` | 60 |

同文件1438行开始的四张回忆都记录 `memory_id=null`、`inherited_card_instance_id=null`。已知若干属性能力文字和四条HIF能力文字，但缺少完整携带卡、强化/定制、获得阶段及确定实例对应关系；不能据这些文字拼装四张声称真实存在的回忆。

当前混合训练配置的六支援组合属于实验基线，曾为不同Plan替换卡片，并使用显式50/60级，不是用户拥有清单。`rl/draft-memory/memory-catalog.json` 等旧实验文件是105类HIF能力的候选模板，不是105张拥有的回忆。

主数据当前有201个 SupportCard、21个 MemoryGift、575个 MemoryAbility ID。MemoryGift 是配布回忆定义，可解析成完整模板，但存在主数据不代表账号已领取。不能擅自把21个模板全部放进 owned_pool。

未在本次限定的安全配置/设计目录检索中发现完整当前账号库存。没有检查账号凭据或调用外部应用。

## 5. 可落地的 setup 数据契约建议

新增显式候选文件，区分 `owned_supports`、`rental_supports`、`owned_memories`、`rental_memories`。每项提供稳定库存实例 ID、实测等级/完整回忆内容、拥有或可租借来源与采集日期。未知记录可以保留在资料文件中，但不能成为可执行候选。只有数据实际明确的 MemoryGift，才允许以 gift ID 引用完整模板。

环境先选偶像，然后候选合法性按该偶像/剧本/PLv计算。模型依次填支援与回忆槽位；支援最终5自有+1租借，回忆允许提前结束且最多4张/最多1租借。选择属于同一个 full_produce episode，奖励仍只来自最终培育评价；given 模式跳过该阶段。完整 loadout 再交给 Arena reset，禁止先 reset 再把已生效的支援/回忆硬替换。

下一步实现不必等待全库存才开发接口与fixture，但用真实账号候选验收必须有真实候选文件。若只有一套可用支援/没有完整回忆，不能把自动完成固定阵容的空动作包装成“已经学习了编成策略”。
