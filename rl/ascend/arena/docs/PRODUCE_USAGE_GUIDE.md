# HIF 全局培育接口

更新：2026-09-10。推荐规则 `hif-report3/2`，本轮完整取舍及证据见 [Report 3 交付](HIF_REPORT3_RL_READY.md)。

`create_hif_training_produce` 将主数据驱动的培育外循环接到用户指定的 pinned gakumas-tools 考试引擎。支持 HIF 选拔三场、选拔记忆交接、本战第一轮、中场、第二轮。考试不再经过旧 Python `ExamRuntime`，缺少映射会报错。

这是可配置培育环境。HIF 外出已从 master Activity 表解析为固定机制，见 [事件抽象](HIF_EVENT_ABSTRACTION.md)。默认安装 Report 3 日程与独立来源池；官方随机事件概率、部分奖励池成员和抽样分布仍不完整，默认规划模型及覆盖参数见本轮交付。2026-09-10 已接入用户提供的三维＋スター性研究公式，可通过 `hif_scoring` 进行当前近似加点收益实验，见 [换算接口](HIF_SCORING_MODEL.md)；也可继续传最终百分比。已有两轮照片样本见 [RL 小汇总](HIF_MULTIPLIER_SAMPLES_FOR_RL.md)，不要把第一轮配置当成第二轮。

## 默认完整课程

省略 `exam_config` 自动采用当前偶像的五场 HIF 配置，详见 [默认课程、奖励与近似数值](HIF_FIVE_EXAM_COURSES.md)。传 `exam_config` 可继续覆盖全部考试配置。

正常失败可以选择重试或接受；`run.abandon()` 主动放弃。选拔成功后 `run.runtime.export_hif_selection_memory()` 用于本战；失败不发选拔回忆。终局 `run.memory_products()` 返回回忆候选，票据与选择接口见 [回忆产物](HIF_MEMORY_GENERATION.md)。

## 最小接入

```python
from gakumas_arena.produce import create_hif_training_produce

def examination_config(context):
    # 按 context['produce_id']、context['stage_type']、context['state']
    # 查询调用方的课程配置。以下仅为集成测试值，不是官方 HIF 配置。
    return {
        'score_percents': [100, 100, 100],  # Vo/Da/Vi；100 = 1.00 倍
        'turn_types': ['vocal', 'dance', 'visual'],
        'rival_scores': [0, 0],
        'scoring_source': 'integration-fixture-explicit-percent',
    }

def examination_policy(obs):
    if obs['choice']:
        return list(range(obs['choice']['min']))
    return next((a for a in obs['actions'] if a['type'] == 'play'), obs['actions'][-1])

def produce_choice(request):
    # 换成你的选择策略；返回 request['options'] 中的下标。
    return 0

run = create_hif_training_produce(
    scenario='hif_final', seed=23,
    loadout={'idol_card_id': 'i_card-amao-1-000', 'idol_rank': 4,
             'auto_support_cards': False},
    exam_config=examination_config, exam_policy=examination_policy,
    produce_choice_selector=produce_choice,
)
while True:
    obs = run.observe()
    if obs['terminated']:
        break
    # 策略替换此行；必须提交当前 observation 的完整候选。
    run.act(obs['actions'][0])
```

`loadout` 支持既有 `LoadoutConfig`、字典和命名编成。指定支援卡用 `support_card_ids` 与 `support_card_levels`，并设置 `auto_support_cards=False`；不要假设默认配置等于用户实机编成。培育层使用 master ID，考试入场包使用 gktools ID。

## 三类策略边界

1. `run.observe()` / `run.act(action)`：选择当日行动、咨询商品、课后奖励、接受考试结果等。重复 observe 不重新采样；旧版本 action 会被拒绝。
2. `produce_choice_selector(request)`：执行过程中同步请求事件选项、道具配置/升级、选择型奖励、强化/换卡目标、饮料溢出时的丢弃。请求含 `kind/options/context/step/choice_id`，返回一个合法整数下标。强化的可选放弃会在 options 中显式给出 `skip`。新入口要求选择器。请求还含效果链当前 `public_state`；自选、放弃与规则本身的随机操作分开处理。
3. `exam_policy(obs)`：仅接收 golden 公共考试观察；普通决策返回完整 action，choice 决策返回下标列表。外循环负责依次推进考试。

目前是同步回调接口；支持全局公开决策边界 checkpoint，不序列化 Python 内部选择回调栈。需要训练时在回调内记录选择、状态和奖励归因。不要将 `snapshot` 或私有 RNG 提供给策略。

## 自定义事件和每日行动

构造器可传：

```python
run = create_hif_training_produce(
    exam_config=examination_config, exam_policy=examination_policy,
    produce_choice_selector=produce_choice,
    event_schedule={0: ['next_support'], 2: ['next_support']},
    day_actions={0: ['activity_supply', 'refresh']},
)
```

日编号从 0 开始。`event_schedule` 在当日行动结束、推进下一日之前执行；若随后自动进入考试，事件先结算。值可为具体 `ProduceStepEventDetail` ID，或 `next_support`（按编成顺序取第一个已解锁、未完成的支援事件）。`day_actions` 是候选动作类型过滤器，不增加不存在的动作；咨询/奖励等内部选择不受每日过滤器裁剪。非法空菜单报错。

也可传 `event_sampler(context)` 返回事件 ID 列表；context 含日编号、当前状态、可触发支援事件。调用方可实现自己的随机分布，应保存配置和 RNG。它不代表官方出现概率。查询/执行指定事件见 [事件库](PRODUCE_EVENT_LIBRARY.md)。

## 选拔交接、本战与考试入场

选拔构造时用 `scenario='hif_selection'`。结束后：

```python
memory = selection_run.runtime.export_hif_selection_memory()
final_run = create_hif_training_produce(
    scenario='hif_final', selection_memory=memory,  # 编成身份从交接包恢复
    exam_config=examination_config, exam_policy=examination_policy,
    produce_choice_selector=produce_choice,
)
```

继承卡组及其已解析定制、记忆来源、普通道具次数/冷却、自定义道具具体配置/次数、累积考试附加效果、已完成事件。两轮考试之间结算体力和未用饮料，并应用中场及第一轮应援棒奖励。所有支持的 loadout 输入（命名预设、字典、配置或已解析对象）均冻结为可恢复的 JSON 编成，保留偶像、实际支援/等级、回忆、转换和成长面板；同时继承完整卡片实例、支援状态和资源修正。完整交接包中的编成优先于本战构造时另传的 loadout；旧包缺少完整编成时至少按记录的偶像身份恢复，显式不同偶像会被拒绝。P 点、饮料与当前 HP 不直接继承。这不是任意阶段的完整检查点。

仅自定义 `exam_config` 时，回调须提供 `score_percents` 或 `hif_scoring`，以及 `turn_types`、`rival_scores`。可选 `rank_threshold/rival_ids/basic_card_pool/stage_effects/persistent_effects/memory_abilities/scoring_source`。`hif_scoring` 自动读取实际三维、star、场次。默认课程会解析配置族、实际状态和追加回合；自定义回调须自行处理这些覆盖。两轮原始分、登记分、身份合计和名次由 HIF 适配层处理。

`GoldenProduceBridge` 转换卡、饮料、考试道具及已支持的成长/开场附加效果。所有自定义 P 道具产生的 18 类开场附加效果已有 golden 执行用例。普通考试道具交由原生规则执行，避免同一主数据附加效果重复施加。应援棒携带六组原始主数据权重，经独立适配器使用原生 RNG 与插入；旧没有权重的单场入口仍均匀。显式覆盖基础池时不误套主数据权重。

映射不唯一时传 `id_overrides={'card': {'master-card-id@1': golden_id}, 'item': {...}, 'drink': {...}}`；未知附加效果可传 `enchant_overrides={'master-enchant-id': native_dsl}`。已有的 `golden_bindings` 会保留；HIF 105 条回忆已自动编译；其他来源仍按明确能力支持范围准入。缺少语义映射、持续时间或次数转换时必须显式配置，不静默丢弃。

## 记录、失败与验证

`run.exam_history` 保存每场 entry、golden snapshot 和结果；`run.export_run()` 导出选择、事件、道具与考试记录，供诊断使用，**不是全局恢复快照**。恢复使用 `run.snapshot()` 与同配置新环境的 `restore_snapshot(saved)`，见 [checkpoint 指南](HIF_PRODUCE_CHECKPOINTS.md)。单场 snapshot 可用 `TrainingExam.restore` 恢复，受既有内容 hash 检查约束。

未知效果或考试执行失败会抛异常，`observe()['fault']` 保留原因、`normal_terminal=False`，合法动作清空。不能把异常转换为正常 0 分样本；出错后的培育状态不可继续训练，应保留记录并重新构建。

```powershell
.venv/Scripts/python.exe scripts/export_produce_events.py
.venv/Scripts/python.exe scripts/validate_hif_report3.py
.venv/Scripts/python.exe -m pytest tests/test_produce_golden.py -q
```

示范脚本只生成一次选拔→本战的集成证据，不启动 RL。产物在 `build/hif_report3/demo/`，含五场考试可恢复记录及 manifest。当前已覆盖的内容与缺口见 [能力审计](PRODUCE_CAPABILITY_AUDIT.md)。
