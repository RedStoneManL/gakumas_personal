# 培育事件、支援卡事件与效果库

核查日期：2026-09-09；来源为仓库已有 `data/raw/gakumasu-diff` 主数据。图鉴截图不是唯一来源，效果以结构化 ID 和数值存储。

| 本地内容 | 数量 | 含义 |
|---|---:|---|
| ProduceStepEventDetail | 6,888 | 全剧本事件定义行，不能全部混入 HIF 随机池 |
| ProduceStepEventSuggestion | 3,066 | 选项、P 点/体力代价、直接效果、成功/失败效果及后续步骤 |
| ProduceEventSupportCard | 511 | 201 张支援卡的事件关联，含等级要求与序号 |
| 明确标记 HIF 的事件行 | 72 / 20 | 选拔 / 本战的授业与外出条目，含阶段和培养类型变体 |
| ProduceCustomizeItem | 180 | 自定义 P 道具配置；171 条升级关联；累积到考试的 18 类附加效果 |

事件→选项→培育效果，以及事件型后续步骤引用均已核查，无缺失引用。引用完整不等于每个效果、每条路径都已独立验收。

导出文件：[produce_events.json](../data/catalogue/produce_events.json)。用 `python scripts/export_produce_events.py` 重建。文件含 schema、内容 SHA256、上述目录、所有 ProduceEffect、支援卡关联、故事标题/资源引用和自定义道具升级图；去除了大量展示用 description，保留数值字段。考试效果、技能等更深层引用仍从主数据仓库查询，不将该 JSON 声称为独立完整游戏包。

## 查询

```python
from gakumas_arena.produce import ProduceEventLibrary
from gakumas_rl.repository.master_data import MasterDataRepository

repo = MasterDataRepository()
lib = ProduceEventLibrary(repo)
summary = lib.summary()
ids = lib.hif_event_ids('produce-007', kind='Activity', pool_tag='before_2nd')
event = lib.event(ids[0])
# event['effects'] 与 event['options'][i]['effects/success_effects/fail_effects'] 已展开。
support_ids = lib.support_event_ids('s_card-1-0000', level=40)
support_event = lib.event(support_ids[0])
```

`kind` 可用 Activity、School；`plan` 可用 plan1/plan2/plan3。池标签只限定主数据行范围，不赋予官方抽样概率。故事组可用 `event(id, character_id='...')` 过滤人物版本；剧情全文/演出脚本不在该元数据目录中。

## 执行

运行时通过 `run.runtime.events` 调用。`eligible_support_events()` 为每张实际装备的支援卡返回下一个已解锁、未完成的事件。`execute(event_id, option_index=None)` 不消耗一天，选择器决定可支付的选项，按序应用直接效果、代价、成功/失败分支、事件型后续步骤；整条事件链结束后分发对应阶段触发。支援事件检查所有权、等级、顺序和是否重复。

正常整局使用构造器的 `event_schedule/event_sampler`，避免绕过 `TrainingProduce` 的缓存和决策版本直接修改运行时。`repeat=True` 是离线调试的显式重复执行开关，不应用作正常事件概率模型。

支持效果链如：咨询 → 花もじゃ（黄）给两瓶饮料 → 支援技能分别加舞蹈 +4 → 累积开场附加效果；差し入れ → つやつやでふさふさ 强化两张卡 → 支援技能分别加 Vocal +3。均使用实际主数据条目测试。

## 尚不能称为齐全的部分

- **HIF「おでかけ」已定位到 Activity 表。** 20 条剧情合成 1 个机制、3 个阶段奖励池配置，见 [事件抽象](HIF_EVENT_ABSTRACTION.md)。此前按 Business 查找而判断缺表有误；Business 主要是 NIA，不应混入。具体候选奖励池与官方抽样权重仍未完全解析。
- 官方随机事件概率、精确每日菜单未提供；目前由环境显式配置。未指定菜单时仍沿用旧候选菜单；部分课程奖励池、稀有度和替换采样保留旧版近似。
- 非事件型后续步骤（如旧剧本某个选项直接进入课程考试）在本次事件执行器中明确报错，不能当作普通事件递归执行。
- golden 原仓库主要覆盖局内执行。培育数值、支援触发与随机调度是 Arena 的主数据解释层，不应标成“全部由 golden 验证”。

因此，可以进行明确课程和抽样规则下的培育实验；要声称官方完整 HIF 分布，还缺精确奖励池/出现概率与原始属性倍率等数据或规则。
