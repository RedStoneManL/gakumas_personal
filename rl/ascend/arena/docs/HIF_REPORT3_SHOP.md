# HIF Report 3：普通咨询商店

2026-09-10。本说明仅适用于安装 `research_profile` 的 HIF 培育；旧入口继续保留既有近似经济规则。价格采用用户研究包第 8 节的社区 V 级表，真实接入可替换配置，不称主数据公开概率。

| 项目 | 基础价格 |
|---|---:|
| R+ / SR / SR+ / SSR / SSR+ | 100 / 50 / 110 / 100 / 150 |
| R / SR / SSR 饮料 | 50 / 75 / 100 |
| 第 1～6 次强化 | 100 / 125 / 150 / 175 / 200 / 250 |
| 第 1～6 次删除 | 100 / 125 / 150 / 175 / 200 / 250 |

普通 R 未强化不进入报价。强化与删除分别保存 `shop_upgrade_count`、`shop_delete_count`，进入下一次咨询不重置价格进度。PLv 5 开放强化，PLv 15 开放删除；公开策略候选中执行门槛与费用校验。服务第 7 次以后默认保持末档 250，显式标为尾端假设，可通过 `consult_upgrade_prices`、`consult_delete_prices` 替换。

卡片行与饮料行左端 SALE 取 0.7，和通用/资源专用折扣相乘后向下取整。最高 30% 卡片折扣的 SSR+ SALE 预测为 `floor(150 × 0.7 × 0.7) = 73`。强化和删除折扣不影响其他商品。普通强化只发 `UpgradeProduceCard`，保留卡片实例字段；普通咨询进入只发 `StartShop`，不误发特别指导的 `StartCustomize`。

未知部分采用明确的可替换训练配置：

- `consult_card_slots`、`consult_drink_slots`：默认 4+4；报告没有确认普通咨询槽位数，默认是规划模型，支持设为 0。
- `consult_card_sale_slots`、`consult_drink_sale_slots`：默认各行索引 0。
- `consult_service_limit_per_visit`：默认每种服务各 1 次，每次咨询重置；次数限制是规划假设。
- `consult_refresh_reopens_services`：默认 false。`consult_refresh_preserves_sold_out`：默认 false。两项刷新语义未被报告确定，可显式覆盖；刷新使用咨询次数资源，不消耗卡片候选重抽次数。
- 来源池：`hif_consult:card:{slot}` 与 `hif_consult:drink:{slot}`（slot 从 0 开始），交给统一 `HifSamplingKernel`。池成员、权重、SR/SSR 强化概率未配置时记录 placeholder。R 固定使用强化版；SR/SSR 默认未强化不是实机概率。

已购槽位在本次库存中保持售罄；商品更新由明确刷新触发，重复 `observe()` 不重抽。配置池当前无合法成员时保留空槽，不悄悄从全局池补货。删除后服务候选重新对应当前牌组实例。99 张牌组上限会屏蔽买卡。

公开课程选卡也已切换为独立来源池 `hif_open_lesson:{produce_id}:{audition_index}`，只使用该池 `upgrade_probability`；支援卡的“技能卡 support 发生率”不再误用为拿卡强化率。

验证：`tests/test_hif_report3_shop.py` 覆盖价表、独立服务计数、PLv、SALE 乘法、来源池/空池、稳定库存、刷新资源分离、服务折扣、目标索引更新、强化实例保留及旧入口兼容。
