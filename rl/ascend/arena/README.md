# gakumas_arena

无 UI、可恢复、可自定义的学園アイドルマスター考试环境。以用户选定的 [gakumas-tools](https://github.com/surisuririsu/gakumas-tools/tree/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/packages/gakumas-engine) 为局内执行基础；事实冲突按 `gakumasu-diff` 主数据修正，当前包含本地适配，以 effective hash 标识实际版本。见 [数据权威约定](docs/DATA_AUTHORITY.md)。

**2026-09-14 搜索新接口：**公开历史条件采样、带权假想世界、常驻 clone/step、部分多选、预算与取消已提供给隔离 RL 实验。见 [搜索 API](docs/ARENA_SEARCH_API.md)、[验收记录](docs/ARENA_SEARCH_ACCEPTANCE.md)、[运行示例](scripts/example_public_search.py)。有限预算采样存在明确失败场景；逐根检查状态，当前在线联合 PPO 未切换。

**HIF 本战 2 可自定义并接入纯策略训练。** 牌组、偶像、培养类型、体力、饮料、P 道具、倍率、回合、补牌池及附加效果均可配置。固定样例是回归用例，不是训练环境的限制。实机校准不作为当前 golden 验收或开训的前置条件。

**2026-09-10 倍率更新：已采用用户提供的研究包，支持三维＋スター性经 `hif_scoring` 自动换算，用于当前近似训练。** 单场与全局培育均可接入，模型版本、各层倍率及实验假设随入场记录保存。见 [换算接口与用法](docs/HIF_SCORING_MODEL.md)。普通 `golden_contest_params` 仍不能替代 HIF 换算。

## 快速开始

**全局 HIF 新入口：`gakumas_arena.produce.create_hif_training_produce`，规则 `hif-report3/2`。** 已接通选拔三场 → 本战两轮，补齐特殊 P 道具、105 条回忆、商店/中场/特别指导与全局快照。先读 [本轮 RL-ready 交付与对照矩阵](docs/HIF_REPORT3_RL_READY.md)、[培育使用指南](docs/PRODUCE_USAGE_GUIDE.md)、[Agent 入口](AGENT_ENTRY.md)。未知随机概率保留为带版本的可替换规划配置。旧 `create_training_produce` 继续兼容。

需要 Python 3.11+、Node.js 20+；本地已验证 Python 3.12.7、Node 26.6.0。无需游戏、Maa、GPU 或 npm 安装。

```powershell
Set-Location C:/Users/Liu/Documents/ChatGPT/gakumas/third_party/gakumas_arena
.venv/Scripts/python.exe scripts/validate_training_ready.py --full
```

新 Python 环境安装：`python -m pip install -e ".[dev]"`。验证命令生成轨迹和证据，不启动训练。

```python
from gakumas_arena import create_training_exam, hif_round2_entry

entry = hif_round2_entry(
    score_percents=[3000, 2400, 1800],  # Vo/Da/Vi：3000% = 30倍
    max_stamina=44,
    stamina=32,
    drinks=[22, 14, 18],
)
# cards=[具体定义ID或完整副本字典, ...] 可替换整个牌组。
# turn_types=[...] 可指定每一回合属性；未指定时按 golden 配置和 seed 生成。
exam = create_training_exam(entry, seed=7)

while True:
    obs = exam.observe()
    if obs["result"]["terminated"] or obs["result"]["truncated"]:
        break
    if obs["choice"] is not None:
        exam.choose(list(range(obs["choice"]["min"])),
                    decision_version=obs["decision_version"])
    else:
        exam.act(obs["actions"][0])  # 替换成策略选中的当前候选
print(obs["result"]["final_score"])
```

每局可重新构造 entry 再创建 exam，实现自定义课程分布。Arena 输出原始成绩，不加人工学习奖励；现有旧 Gym 不会自动切换到这个接口。

## 文档与证据

人类检查卡组可直接调用 `from gakumas_arena.preview import write_deck_preview`，再运行 `write_deck_preview(entry, "outputs/deck.html")`。它把同一入场包渲染为可点击的卡牌图标，保留重复副本、定制和成长。原图默认缓存到本地并嵌入 HTML，生成文件可离线打开；见 [预览接口](docs/DECK_PREVIEW.md)。

| 内容 | 入口 |
|---|---|
| 配置字段、绑定、倍率、动作与恢复 | [使用指南](docs/ARENA_USAGE_GUIDE.md) |
| 其他 agent 接入 | [AGENT_ENTRY](AGENT_ENTRY.md) |
| RL 清单逐项状态 | [验收矩阵](docs/ARENA_ROUND2_READINESS.md) |
| 完整入场包、公共轨迹、私有快照、结果 | [manifest](docs/examples/training_ready/manifest.json) |
| golden 来源与旧接口 | [后端说明](docs/ARENA_GOLDEN_ENGINE.md) |

结构化目录可用 `training_catalog()` 获取：870 张卡、484 个 P 道具、28 种饮料、154 个偶像、111 个定制。目录含条件、数值、顺序和效果 AST，无需 OCR 网站截图。

此前单场 golden 接入证据包含 84 项接入/组合测试、524 条上游保存预期、7 组独立手算/隐藏信息探针、全目录效果指令分派检查、24 场自定义变体及 spawn 与串行一致性。完整 HIF 本版验收见 [本轮交付](docs/HIF_REPORT3_RL_READY.md)。目录大小与指令检查不等于所有组合都已独立验证；实际结果和有效源码 hash 以对应 manifest 为准。

## 接口边界

- `create_training_exam / TrainingExam`：公共策略接口；`hif_round2_entry` 是可编辑模板，`make_training_entry` 构建通用环境。
- `default_training_entry`：旧 v1 固定回归 fixture，仅用于兼容；新无参数 `create_training_exam()` 已使用可编辑 v2。
- `create_exam / ArenaExam`：私有调试；旧 env/content/live/sim 仍是 gakumas_rl 兼容路径。
- `snapshot / inspect_private / seed / last_cost` 用于恢复、诊断，不可混入公共策略输入。
- `fork()` 复制同一私有世界。公平搜索所需的公共条件采样 S02 尚未实现，不影响当前纯策略训练。
- 单偶像考试可独立运行；推荐 `create_hif_training_produce` 提供选拔三场→本战 R1→中场→R2、默认课程/奖励/回忆与全局恢复；服务器未知数值使用 [版本化近似](docs/HIF_FULL_PRODUCE_GAPS.md)。旧 `create_training_produce` 保留兼容。

发行保留 GPL-3.0-or-later 兼容层与 BSD-3-Clause golden 来源、许可。
