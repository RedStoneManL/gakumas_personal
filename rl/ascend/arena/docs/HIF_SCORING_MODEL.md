# HIF 三维／スター性换算接口

更新：2026-09-10。用户提供并同意采用的研究包已接入，模型版本为 `hif-display-v0.3-empirical-2026-09-09`。它是目前用于训练的近似换算方案；不要求先补实机校准。卡牌、饮料、道具及局内得分仍由 pinned gakumas-tools golden 执行。

原包七个文件保存在 [研究包目录入口](research/imports/hif_research_pack_2026-09-09/README.md)。包内六项 SHA-256 全部核对通过；运行时的参考 Python 和 JSON 与原文件逐字节一致。完整来源与公式见 [原研究报告](research/imports/hif_research_pack_2026-09-09/HIF_考试倍率公式核对_2026-09-09.md)。

## 单场考试直接使用

```python
from gakumas_arena import make_training_entry, TrainingExam
from gakumas_arena.scoring import calculate_hif_multiplier

raw = dict(
    family='voda-03', stage='round2',
    stats=[2759, 1744, 1209], star=1083,  # Vo / Da / Vi；本场入场 star
    judging_icons=['◎', '◎', '◎'],
    dearness_factor='1.5',
)
detail = calculate_hif_multiplier(**raw)
assert detail['score_percents'] == [4208, 2886, 2128]

# 单张原生卡、单回合仅演示接口；卡组、饮料、道具和回合可自行配置。
entry = make_training_entry([647], hif_scoring=raw, turn_types=['vocal'])
exam = TrainingExam(entry, seed=23)
assert exam.observe()['context']['multipliers']['vocal'] == 42.08
```

`hif_round2_entry(hif_scoring=raw, ...)` 同样支持，会替换模板的固定百分比。`score_percents`、`scoring`、`hif_scoring` 三选一。已有实机倍率仍可直接传 `score_percents`。

`family` 是偶像的固定考试曲线族，支持 `vida-03 / voda-03 / davo-03 / voda-01 / davi-01 / vovi-01`；**不会按当前三维高低排序，也不会根据卡组猜 family**。主次属性的映射见原报告，调用方按所选偶像的考试配置提供。`stage` 为 `selection1 / selection2 / selection3 / round1 / round2`。

单场接口不强制回合数：研究包给出五场基础回合数 `10/12/12/9/12`，详细回合顺序和培育效果造成的回合变化仍由课程提供。

## 全局培育随状态换算

`create_training_produce` 的 `exam_config(context)` 可以返回 `hif_scoring`，不必再提前算最终百分比：

```python
def examination_config(context):
    course = my_courses[(context['produce_id'], context['stage_type'])]
    return {
        'hif_scoring': {
            'family': course['curve_family'],
            'dearness_factor': course['dearness_factor'],
            **course['qualification_policy'],
            'allow_experimental': True,
        },
        'turn_types': course['turn_types'],
        'rival_scores': course['rival_scores'],
    }
```

`my_courses` 是训练方的课程表。全局入口从当前 `state.vocal/dance/visual/star_quality` 读取入场数值，自动将 `produce-007` 的三场映射为 selection1/2/3，将 `produce-008` 的 Mid1/Final 映射为 round1/2。每场重新计算，不能在这里提供或固定 `stats/star/stage`。

`qualification_policy` 可以是 `{'all_qualified': True}`，表示这份课程明确假设全达标；或 `{'judging_icons': ['◎','◎','△'], 'penalty_mode': 'settings-prior'}`。动态课程应按自己的判定策略逐场产生图标，不能把全达标假设用于所有低属性状态后声称已模拟短板。

亲爱度因子默认沿用研究包的 **1.5**，会记录为默认假设；其他亲爱度／倍率效果请在 `dearness_factor` 明确提供合并后的因子。接口**不读取旧 loadout 的估算分数倍率**，也不自动叠加 `audition_parameter_bonus`；调用方如要应用这类效果，应在此参数中处理一次。回合增减仍由 `turn_types` 显式体现。

浮点储存的整数（如 `915.0`）可接受；真正带小数的属性／star 会报错，不悄悄截断。

## 公式与近似分支

无短板时：从本场／曲线族查表线性插值 `L`，先算 `A=ceil(100+L/10)`，随后 `B内部=A×亲爱度因子`，最后 `ceil(B内部×K/1000)`。B 的显示值不能回填；例如 `1465.5` 虽显示 `1466`，后续仍使用 `1465.5`。

本战的经验候选为 `K=min(3000, 2000+ceil(1000×(star−基准)/D))`：第一轮基准 600、D=270，第二轮基准 800、D=325。每场都使用该场入场 star。

以下选项保留研究包定义，**不阻止选择近似方案进行训练**：

| 情况 | 使用方式 |
|---|---|
| 三维达标 | 提供实际 `judging_icons` 或 `all_qualified=True` |
| 本战 star 达标 | 直接使用经验候选；输出标注模型版本 |
| 选拔未封顶、任意场 star 未达标 | `allow_experimental=True` 启用包内插值假设 |
| △／× 短板 | 同时传图标、`penalty_mode='settings-prior'` 和 `allow_experimental=True` |
| 惩罚竞争解释 | 可选 `penalty_placement='after-A'`、`penalty_combination='multiplicative'`；默认是 curve-bonus／additive |
| 自定义短板阈值 | `penalty_thresholds=[Vo阈值, Da阈值, Vi阈值]`；不传时实验分支采用包内配置基准 |

未知图标不会自动当作达标。当前重建的是界面倍率；Arena 选择把最终显示整数百分比交给 golden 作为当前评分近似，不额外乘 star／亲爱度，也不改 golden 的卡牌得分舍入。

## 给 RL 的记录与验证

每场 `entry['source']['hif_scoring']` 保存原始输入、A/B/最终内部与显示值、模型版本、参考代码及数据 SHA、实验开关和证据标记。snapshot 保存同一记录；百分比与 provenance 不一致会在考试入口报错。全局培育的 `exam_history[*].result.scoring_provenance` 也保存详情。

原始照片记录保持原样。复算结果见 [本地两组逐层结果](../build/hif_scoring/local_samples.json)：

| 场次 | A（Vo/Da/Vi） | B 显示 | 最终百分比 |
|---|---|---|---|
| 用户 Round1 | 977/666/494 | 1466/999/741 | 4397/2997/2223 |
| 用户 Round2 | 977/670/494 | 1466/1005/741 | 4208/2886/2128 |

[研究包样本审计](../build/hif_scoring/research_audit.json) 为 14 组中 13 组全相符、42 个最终值中 41 个相符；SM-R2 的 Vi 保留原始 2681%，模型预测 2757%。这是同一批研究样本的复算，不是独立验证集表现。

```powershell
.venv/Scripts/python.exe -X utf8 scripts/validate_hif_scoring.py
.venv/Scripts/python.exe -X utf8 -m pytest tests/test_hif_scoring.py tests/test_training_custom.py tests/test_produce_golden.py -q --junitxml=build/hif_scoring/pytest.xml
```

测试覆盖两组本地截图的所有倍率层、五场映射、短板跨颜色影响、星值边界取整、显式实验开关、golden 实际入场／计分、两轮动态入口以及恢复。它只验证本次换算接入，不把此前独立列出的 HIF 回忆映射或全局随机分布缺口标为完成。

本次上述测试组合 **66 通过、0 失败**，包括 18 项新增换算用例；[测试报告](../build/hif_scoring/pytest.xml)。
