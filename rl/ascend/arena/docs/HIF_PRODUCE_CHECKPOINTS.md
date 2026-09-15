# HIF 培育决策边界快照

`gakumas_arena.produce.checkpoint` 提供可经 JSON 保存的完整培育执行状态。适合 RL 回放、固定起点和断点恢复，涵盖普通日、选卡、咨询、中场商店、特别指导等已公开的培育决策边界。考试内暂停由 `TrainingExam.snapshot()` 负责；一次 `TrainingProduce.act()` 内的 Python 回调调用栈不保存。

```python
import json
from pathlib import Path
from gakumas_arena.produce.checkpoint import snapshot, restore_into

# run 是已配置好的 TrainingProduce。
saved = snapshot(run)
Path('produce-checkpoint.json').write_text(
    json.dumps(saved, ensure_ascii=False, allow_nan=False), encoding='utf-8')

# 使用相同环境配置和策略构造 fresh_run；初始化 seed 可以不同。
saved = json.loads(Path('produce-checkpoint.json').read_text(encoding='utf-8'))
restore_into(fresh_run, saved)
observation = fresh_run.observe()
result = fresh_run.act(observation['actions'][0])
```

恢复保存三维/星性/计数、牌组实例与饮料、P 道具/支援技能状态、待选卡和待结算结果、当前候选与观察缓存、事件完成记录、特殊道具与考试附加效果、中场库存/刷新/服务次数、特别指导用过的卡片名额、采样历史、numpy RNG、奖励势函数和公开决策版本。当前候选不因恢复重新抽取。

恢复前验证剧本 ID、规则版本、golden 与培育源码哈希、主数据 YAML 哈希、静态配置哈希及快照内容校验和。跨版本、不同编成/成长配置/日程/翻译覆写的环境会拒绝加载，不静默迁移。

仓库、函数、考试策略、事件采样器、奖励选择器不写入文件。调用者必须为目标 run 提供同样的确定性策略；有内部可变状态的外部策略需自行另存并恢复。JSON 不包含 pickle 或可执行代码，解码只允许本地列举的数据类。

**快照含环境随机数状态，不是 agent 的 observation。** 不要把原始 checkpoint 传给策略网络；策略仍只接收 `observe()`。

验证：`python -m pytest tests/test_produce_checkpoint.py -q`，**14 passed**。普通日/咨询/选卡及中场刷新从不同 seed 的新环境恢复后，同一步输出、候选、事件、采样历史与 RNG 状态一致；另测特别指导名额、道具累积效果、重复快照稳定性和不兼容/损坏快照拒绝。
