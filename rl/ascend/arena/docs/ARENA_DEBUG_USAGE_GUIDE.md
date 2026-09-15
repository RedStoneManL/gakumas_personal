# Arena 原有私有调试 API 指南

本文保留 v1 `ArenaExam` 调试接口；公共 `TrainingExam` 训练入口及常驻进程在 [当前指南](ARENA_USAGE_GUIDE.md)。下文“尚未实现”的判断只针对旧接口。

2026-09-09。适用于 `gakumas_arena.create_exam` / `gakumas_arena.engine`。当前规则版本为 `arena-gakumas-tools/6c3d00648c32ea72a05086a18c63ab62e0d0c7e5/1`。

当前可以运行通用考试、由调用者逐步选择并恢复。**公共 observation 尚未实现**：下文使用 `debug` 命名返回状态，它包含私有牌序。正式 Round2 状态见 [验收矩阵](ARENA_ROUND2_READINESS.md)，不要把这个示例直接改名为公共策略接口。

## 1. 运行环境

所有相对路径以仓库 `third_party/gakumas_arena` 为起点。Python 3.11+、Node.js 20+；Python 项目依赖见 [pyproject.toml](../pyproject.toml)，不需要 PyTorch/CUDA、浏览器、Maa 或网站的 npm 依赖。

```powershell
Set-Location C:/Users/Liu/Documents/ChatGPT/gakumas/third_party/gakumas_arena
.venv/Scripts/python.exe -m gakumas_arena.engine --config docs/examples/golden_exam.json --output result.json
```

新环境使用其 Python 执行 `python -m pip install -e ".[dev]"`。已有工作区虚拟环境可直接运行，无须为了示例修改依赖。非 Windows 环境通常使用 `.venv/bin/python`。Node 必须在 PATH，或在 Python API 中传 `node="/absolute/path/to/node"`；该参数也适用于 `ArenaExam.restore`、`run_exam`、`find_effects`。

每次原生调用最多等待 60 秒。当前没有可调超时、原生调用取消协议或常驻 worker；规模限制见第 7 节。Colab/Linux 未在本轮验证，不把可安装当成已通过跨平台验收。

## 2. 两种运行方式

### 固定示例自动跑分

```bash
python -m gakumas_arena.engine --config docs/examples/golden_exam.json --output result.json
```

使用上游 `StagePlayer + HeuristicStrategy`，默认 seed `610397104`，此固定样例预期 `13257`。Python 对应 `from gakumas_arena.engine import run_exam`。该路径让启发式处理整场选择，适合对拍；不用于把全部决策交给 RL。当前自动跑分不接受非空饮料、`starting_stamina` 或 `turn_types`，这些配置需使用逐步接口。

网站 query 可以经 `loadout_from_query(query)` 解码；传的是 URL 的 `?` 后 query 字符串，不是整个 URL。这里的数字 ID 属于 gktools，不能直接填入游戏 master 的字符串 ID，也不能与旧内容包 ID 混用。

### 外部决策、补选与终局

先生成本文配套工程配置/证据：

```bash
python scripts/audit_round2_readiness.py --output docs/examples/round2_readiness
```

下面可在仓库根目录直接作为 Python 脚本运行；它与审计脚本采用相同的演示选择规则：

```python
import json
from pathlib import Path
from gakumas_arena import create_exam

cfg = json.loads(Path("docs/examples/round2_readiness/engineering_config.json").read_text(encoding="utf-8"))
exam = create_exam(cfg, seed=7)

for _ in range(200):  # 调用者的工程防护预算；不是游戏回合上限
    debug = exam.observe()
    assert debug["observation_scope"] == "offline_full_state"
    if debug["terminated"]:
        print({"score": debug["score"], "scope": "synthetic_engineering"})
        break
    choice = debug["choice"]
    if choice is not None:
        # 演示选择第一批候选；实际使用由调用者作决定。
        indices = [c["index"] for c in choice["candidates"][:choice["min"]]]
        exam.choose(indices)
    else:
        action = next((a for a in debug["actions"] if a["type"] == "drink"), debug["actions"][0])
        exam.act(action)
else:
    raise RuntimeError("外部预算耗尽；保留 exam.snapshot()，不生成终局训练样本")
```

当前配套样例得到 `106`，14 次提交，3 次补选。这是工程连通性结果，没有独立手算分数预期。引擎会在开局或行动内部选牌处暂停，`create_exam()` 返回时不保证已经完成开局。一次用卡也可能自动结束当前回合并进入下一回合；以新返回状态为准，不强行每张卡后补一个 `end_turn`。

| 提交 | 含义 |
|---|---|
| `exam.act({"type": "play", "card": ...})` | `card` 是当前候选中的实例键，不是定义 ID/显示槽位 |
| `exam.act({"type": "drink", "slot": ...})` | `slot` 是当前饮料库存索引；喝完后可能移动，必须重新读取 |
| `exam.act({"type": "end_turn"})` | 主动结束当前回合；自动结算由引擎推进 |
| `exam.choose([index, ...])` | 当前 `choice.candidates` 的候选索引，不是其中的 `card` 或 `id` |

`choice` 目前有 `hold`、`move_to_hand`、`use_selected`；`min/max` 决定允许选择数，索引必须有效且不重复。仅 `min == 0` 时可提交 `[]` 跳过。没有通用 `STOP` 动作。序列按提交顺序交给上游；不把所有多选都假定为无序。当前 choice 未完整输出来源、区域、支付语义或决策版本，`use_selected` 也不是完整的效果上下文。

补选未完成时普通 `act()` 被拒绝，必须持续处理新 choice；`actions` 为空可能只是待补选，不能当作终局。逐步接口的 `TapeStrategy` 不替调用者做启发式选择，但这不等于所有 HIF 内容已经接入。

## 3. 配置的实际含义

完整可运行配置见 [engineering_config.json](examples/round2_readiness/engineering_config.json)；带真实上游 stage ID 的例子见 [golden_exam.json](examples/golden_exam.json)。

| 字段 | 当前语义与限制 |
|---|---|
| `loadout.params` | 四个数：Vo、Da、Vi、最大体力。前三项的单位取决于 `enter_percents`；最大体力必须大于 0 |
| `enter_percents` | 为 true 时前三项直接是百分数，例如 `100` → 1 倍，`3879` → 38.79 倍；contest 默认为 false 时按上游赛季公式从属性推导。这个开关不能代替 HIF 明星性等推导 |
| `loadout.supportBonus` | 上游支持加成比例，例如 `0.04`；默认为 0。直接百分数路径不再套普通 contest 推导 |
| `loadout.skillCardIdGroups` | 二维 gktools 定义 ID 列表；0 为占位忽略。强化通常是另一个定义 ID，不能仅凭末尾 `+` 自行加 1 |
| `loadout.customizationGroups` | 与卡槽对应的对象，如 `{"33": 1}` 表示改造 ID 和层数。上游会丢弃未知 ID/零层，并非严格准入校验 |
| `loadout.pItemIds` | gktools 道具 ID；0 忽略，上游会去重。没有该入口的逐实例绑定/剩余次数导入字段 |
| `drinks` | gktools 饮料 ID 列表，同种多瓶用重复 ID；省略则为空。当前为 Arena 库存分派扩展，效果执行仍使用原始 AST |
| `starting_stamina` | 可选当前体力，范围 0 至最大值；省略则从满体力开始 |
| `stage_id` / `stage` | 二选一；同时提供时 `stage` 优先。stage 包含 type/plan/season、各属性回合数、首回合概率、审查比例、effects 等；不是 HIF 场景标识 |
| `stage.effects` | 原始效果 DSL 或上游 AST；DSL 由上游解析和执行。可用于合成探针，不自动证明规则自然可达 |
| `turn_types` | 可选逐回合属性序列，逐步接口专用；目前只检查长度和枚举，不核对属性频数与 turnCounts 是否一致 |

**入场边界限制：**调用从 golden 的配置初始化和 `startStage` 开始。上游按 `IdolStageConfig` 选择基础牌集追加到 loadout，`IdolConfig` 对部分唯一卡去重；它不是“保留所有副本、已有成长、绑定与预约状态的 HIF 最终入场包”。本示例是 4 张配置牌加 8 张基础牌的合成测试，9 回合/100% 倍率均为测试假设。22 张应援棒门槛没有在这里实现，不能靠截断、拒收 21 张或每回合补到 22 张模拟。

当前没有正式可用的 HIF Round2 preset，也没有自然可达性/机制闭包 validator。未知卡/道具/饮料 ID 会报错，但“目录中存在的空效果”“未知自定义被丢弃”等情况不能靠这一层拒绝。给正式 RL 输入前需由 Arena 增加严格的限定内容准入。

## 4. 查询和消费结构化效果

```bash
python -m gakumas_arena.engine --find "夏夜" --output summer_effects.json
python -m gakumas_arena.engine --find "脚光" --output spotlight_effects.json
```

Python：`from gakumas_arena.engine import find_effects; data = find_effects("夏夜")`。结果含 `rules_version` 和 `matches`，每项有种类、ID、名称与解析后的 `definition`。效果操作、参数、条件与嵌套结构来自 gktools 数据，不是图片 OCR。

批量读取 [gakumas_tools_effects.json](../data/reference/gakumas_tools_effects.json) 可获得原始 DSL、AST 和来源；语法参考 [上游 Effects.md](../gakumas_arena/_vendor/gakumas_tools/packages/gakumas-data/Effects.md)。定义层数值应保留，不能用 ID/hash/图标取代。仍须结合实例成长、自定义和当下规则状态才能解释有效效果；目前没有完整公共实例解析协议。

别把目录收录数、非空 AST 数、执行命中数、独立预期验证数混为一个覆盖率。效果为空的培育道具可能仅在局外有效，也可能缺少所需机制；首批考试闭包必须逐项分类，不能一律当作无效果的合法输入。

## 5. 私有快照和分叉

```python
import json
from pathlib import Path
from gakumas_arena.engine import ArenaExam

# 接上面的 exam；snapshot 包含 seed/config/history/pending 选择答案。
saved = exam.snapshot()
Path("private_snapshot.json").write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
branch = ArenaExam.restore(json.loads(Path("private_snapshot.json").read_text(encoding="utf-8")))
assert branch.observe() == exam.observe()
```

快照 schema 为 `arena-golden-snapshot/1`。它是从固定种子重建的事件日志，不是任意原生状态的内存 dump；恢复会从头执行历史并停在当前补选。不能删 `pending`、手动改种子/历史冒充同一世界，或拿旧后端的 live snapshot 直接恢复。版本字符串不符会拒绝；当前还不会自动检查所有实现文件的内容 hash，归档时同时保存 manifest 并保持代码版本一致。

配套 [private_checkpoints.json](examples/round2_readiness/private_checkpoints.json) 有初始化前、开局两次选择中、用卡后的选择中、终局前与终局快照。`ArenaExam.restore()` 返回新对象，后续操作不会改变原对象或输入字典。

这是“同一个隐藏世界的独立副本”。**公平搜索还缺公共条件采样器**，不允许把恢复原局隐藏 RNG、任意换 seed 或洗掉已知顶牌称作已支持公平搜索。

## 6. 错误、终局和可见性

引擎返回的是 `score` 与 `terminated`，暂没有统一的 `termination_reason`。正常终局后动作列表为空，再次操作被拒绝。最终 score 来自完成结算后的状态，但不能把它自动标注成 Round2 分数、两轮总分或名次。

`GoldenEngineError` 包括输入错误及原生执行错误，调用失败前的 Python 对象快照保持不变；缺 Node 为 `RuntimeError`，进程超时可能为 `subprocess.TimeoutExpired`。当前错误没有统一的 JSON 路径/结构化种类，调用者应保存原错误和当前私有快照，不转换成 0 分或自动 reset 的训练样本。

当前候选没有 revision/token：之前返回的动作只要此刻仍合法就可能被接受。示例检查证实“读取用卡候选→喝饮料→提交旧候选”会成功；这是 R09 缺口。提交前重新观察是当前使用习惯，不能代替引擎级过期动作拒绝。

`observe()` 返回 `state` 的完整内部变量、所有区域、牌实例、未来属性序列及调试日志。`observation_scope` 为 `offline_full_state`。只删 `deckCards` 仍可能通过日志、cardMap 或未来序列泄漏，因此这里不提供伪装成公共观察的删字段函数；正式公共决策循环需等待 R07 完成。

公开已知的回合顺序、已揭示顶牌等应当保留；公共边界需要依据实际可见性逐项定义，不是把所有涉及未来的字段一律隐藏。

## 7. 验收文件与运行成本

```bash
python -m pytest tests/test_golden_engine.py -q
node --no-warnings --loader ./gakumas_arena/_vendor/gakumas_tools/scripts/extensionless-loader.mjs ./gakumas_arena/_vendor/gakumas_tools/tests/run.mjs
python scripts/audit_round2_readiness.py --output docs/examples/round2_readiness
```

输出目录包含工程配置、私有轨迹、私有检查点、终局结果、检查结果、测量和 manifest。允许用 `--output` 指定新目录；同一目录重复运行会更新这些示例文件。manifest 包含本轮有效接口文件 hash、配置 hash、上游 74 文件校验和运行环境，不仅记录 Git HEAD；它用于证据追溯，尚不是运行时强制准入。

每次 `act/choose/restore` 都新起 Node 并重放日志；`observe/snapshot` 仅在 Python 中深拷贝缓存。长局会反复解析静态数据和累计日志，补选恢复也有成本。示例测量把重放的顶层行动次数列出，**没有**把它称作原生效果调用数，也不承诺训练 steps/s。详见 [measurements.json](examples/round2_readiness/measurements.json)。

本轮核对了两个独立实例并行与串行一致。没有同一对象多线程写入的保证；并发时每个 worker 持有自己的实例。未测峰值内存、最佳并发、长局吞吐或 Colab；没有关闭引擎日志的等价 fast path。先补 R 组，再基于测量优化常驻 worker/静态缓存及分叉，避免在训练端复制规则。

## 8. 旧入口

`gakumas_arena.env.make_exam_env`、`gakumas_arena.sim.run_exam/run_produce`、内容包和 live 使用旧后端。它们已有 Gym、公共状态/恢复等实现可供迁移参考，但其规则版本、卡牌 ID 和快照协议与本文不同。旧 `sim.run_exam` 和本文 `engine.run_exam` 同名不同路径，导入时请写完整模块名。

旧能力资料见 [LIVE_EXAM_CONTRACT](LIVE_EXAM_CONTRACT.md)、[CONTENT_AUTHORING](CONTENT_AUTHORING.md)、[历史交接](HANDOFF.md)。现在接入新的 Arena 考试应以本文、[AGENT_ENTRY](../AGENT_ENTRY.md) 和最新 Round2 矩阵为准。
