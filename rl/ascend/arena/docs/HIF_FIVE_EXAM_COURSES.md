# HIF 五场默认考试与奖励

`hif-report3/2` 的 `create_hif_training_produce` 不再要求 `exam_config`。省略时使用 [课程适配器](../gakumas_arena/produce/courses.py)，按入场偶像固定审查类型、实际三维和スター性生成考试。显式传 `exam_config` 仍可完整自定义。

原始证据为 [2026-09-10 考试研究快照](../gakumas_arena/produce/data/hif_exam_profiles.json)。它包含固定 master commit、来源、配置端点和未知字段；适配器按字段含义转换，未把研究 JSON 直接当成引擎配置。研究包公式由既有 [HIF scoring](HIF_SCORING_MODEL.md) 执行，局内元件仍由 pinned gktools 执行。

| 场次 | 基础回合 | 均衡型主/副/第三 | 特化型主/副/第三 | 星性审查基准 | 星性基础奖励上限 |
|---|---:|---|---|---:|---:|
| 选拔 1 | 10 | 5/3/2 | 5/3/2 | 50 | 40 |
| 选拔 2 | 12 | 5/4/3 | 6/3/3 | 200 | 110 |
| 选拔 3 | 12 | 5/4/3 | 6/3/3 | 400 | 110 |
| 本战 1 | 9 | 4/3/2 | 4/3/2 | 600 | 120 |
| 本战 2 | 12 | 5/4/3 | 6/3/3 | 800 | 150 |

“主属性”由偶像审查类型固定，不能按本局当前属性排序。默认保留末三回合第三→副→主；追加回合接在末尾且为主属性，不重新分配基础回合。已覆盖快照里的 10 个偶像、6 个曲线族、50 个场次配置。快照尚无可用关联的偶像须显式指定 `courses.profile_character_id` 采用一个规划 profile，或传自己的 `exam_config`，不会静默套错偶像。

NPC 从该偶像、该场次的真实配置组读取。保留人物身份供两轮合计，选拔边界 NPC 的固定分数保留。本战 R1 登记分为 `floor(raw*6/5)`，本战 R2 为 raw；最终比较同一人物的两轮合计。星性奖励始终使用 raw。

五场星性奖励分别按研究表分段，先 ceil，再由实际 `StarPerMil` 乘算 floor 和剧本上限处理。R1 的 400,000 raw 获得基础 108；R2 同分基础 75。两场不能共用一条曲线。

选拔三维奖励的已知上限分别为每色固定 20/80/100，加上按实际颜色得分分配的共享 80/200/220。适配层记录每次 native score 赋值所属颜色，合计必须等于原始总分；不会根据回合数或主属性猜占比。对应成长加成只应用一次，接受考试结果时才入账。R1 另有最多 200 P 点，R2 没有这项奖励。

最终评价使用实际结算后的スター性与保留的两轮原始分数：

```text
floor(2*三维合计 + 7.5*最终スター性)
  + floor(f_R1(raw_R1)) + floor(f_R2(raw_R2)) - 2000
```

不从登记分逆推 raw，也不再次补算一遍 R2 星性。基准例：三维合计 6000、结算后 star=1335、R1 raw=700000、R2 raw=1500000，评价为 **30012**。

## 未确定数值的运行模型

以下均已执行，属于可替换近似，不是已确认的服务器概率：

| 参数/机制 | 默认及覆盖方式 |
|---|---|
| 首回合与中间顺序 | 均衡副属性首回合 0.15，特化 0；其余多重集合 shuffle。`courses.secondary_first_probability` 可覆盖 |
| NPC 分数分布 | static 配置取区间整数中点，其他组整数均匀抽样。`courses.npc_model='midpoint'/'uniform-integer'` |
| 属性达标与不足惩罚 | master 属性基准作为 ○/△ 门槛，采用已接受研究包的 settings-prior 惩罚。不是实测完整门槛。`courses.scoring` 可覆盖 |
| 得分亲爱度因子 | `courses.dearness_factor=1.5`；与实际星性获得率是不同参数，不叠乘到最终百分比 |
| 选拔低分三维奖励 | 线性增长到该场星性封顶分数对应的三维上限；`exam_rewards.stat_cap_scores` 按 selection_1/2/3 覆盖 |
| 整数共享池 | 最大余数分配，余数相同按 Vo/Da/Vi；保持池总量 |
| R1 低分 P 点 | 线性到 raw=400000 获得 200 P；`exam_rewards.round1_point_cap_score` 可覆盖 |
| 同分排名 | 默认玩家同分优先；不是已验证的全部服务器同分规则 |

```python
run = create_hif_training_produce(
    scenario='hif_selection', loadout=my_loadout, seed=23,
    exam_policy=my_exam_policy, produce_choice_selector=my_choice,
    research_config={
        'courses': {'npc_model':'uniform-integer', 'dearness_factor':1.5},
        'exam_rewards': {'round1_point_cap_score':400000},
    },
)
```

课程使用培育环境 RNG；重复 observe 不重新抽课程。checkpoint 保存隐藏课程记录和 RNG；policy 只能读公开观察。`export_run()['courses']`、每场 result 的 `course_provenance`、`scoring_provenance`、`reward_provenance` 用于诊断和版本追溯。

## 验证

`tests/test_hif_courses.py` 覆盖五条奖励曲线、分色奖励守恒、成长单次应用、评价 30012、50 个课程配置、追加回合、RNG 恢复与五场实际 golden 执行。示例策略可在默认 NPC 下失败，这是正常结局；不修改考试分数让示例强行通过。

```powershell
.venv/Scripts/python.exe -m pytest tests/test_hif_courses.py -q
.venv/Scripts/python.exe scripts/validate_hif_report3.py --default-courses --output build/hif_report3/default_courses
```

末尾保留回合顺序、NPC 抽样、达标门槛及低分奖励曲线的近似，是当前训练模型的一部分。更换这些参数后保存新规则配置/hash，不能与旧环境的标签无区别混用。
