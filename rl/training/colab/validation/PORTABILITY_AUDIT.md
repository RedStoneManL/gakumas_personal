# Colab 搬运与恢复审查

本文件仅记录源代码审查和本地原生引擎短测；未执行 Colab/Linux 长训。对应脚本：`portability_audit.py`、`mixed_pool_audit.py`。

## 最小可靠打包范围

训练侧保留 `gakumas_training/**/*.py`、`gakumas_training/encoding/*.json`、`gakumas_training/configs/*.json`、`pyproject.toml`，以及选定的 Colab 配置和运行入口。

Arena 保留相对目录：

- 根 `pyproject.toml`：主数据仓库据此识别 checkout 根目录，不能仅复制两个包后丢掉此文件。
- `gakumas_arena/**/*.py`、`gakumas_rl/**/*.py`。
- `gakumas_arena/produce/data/*.json`，包含课程/终局公式和定制桥接注册表。
- `gakumas_arena/scoring/*.json`、`gakumas_arena/content/*.json`、`gakumas_arena/scenarios/*.yaml`。
- `gakumas_rl/configs/*.json`。
- `gakumas_arena/engine/*.mjs`。
- `gakumas_arena/_vendor/gakumas_tools/packages/**/*.{js,json}`，包含两个 workspace 包的 `package.json`。
- `gakumas_arena/_vendor/gakumas_tools/scripts/extensionless-loader.mjs`，以及该 vendor 的 `LICENSE`、`PROVENANCE.json`。
- `data/raw/gakumasu-diff/*.yaml`：本次盘点为 286 个文件；不能只凭单条 smoke 的已加载表删减其余主数据。

不需要携带 Windows `.venv`、`.git`、`node_modules`、历史训练输出或 `.gakumas_rl_cache`。主数据缓存由当前平台重建。翻译 JSON 可选；仓库在不存在翻译文件时使用空本地化映射。

只安装 Arena wheel 不包含外部 `data/raw` YAML。推荐直接保留上述 checkout，入口显式传 `--arena-root /实际解压路径/arena`。显式路径错误现在会失败，不会悄悄使用另一份已安装 Arena。

## 运行依赖和 Linux 边界

- Python 3.11+，训练依赖 torch/numpy，以及 Arena extras 的 gymnasium、PyYAML、orjson、pydantic。
- 原生考试使用 PATH 中的 Node.js 20+。扩展名 loader 直接解析随包两个 workspace 包，无需 npm 安装整个上游网站。
- 本次静态扫描覆盖 47 个 vendor JS、9 个 JSON：所有相对导入可解析，未发现大小写不匹配；外部包引用均指向已携带的两个 workspace 包。此检查不能替代 Linux 上真实启动 Node 的 preflight。
- Colab 启动时应记录 Python/torch/NumPy/Node/CUDA 实际版本。当前本地检查不代表任意未来依赖版本组合已验收。

## 版本与恢复

修复了 `arena_version()` 的确定漏项：原先未包含实际影响倍率的 scoring Python/JSON，以及部分场景/运行配置。现在 schema 为 `arena-effective-rules-and-master/2`：native JS/JSON 用 Arena 原生版本；全部 Arena/Python 规则、场景和运行数据，以及**实际被选中的主数据目录**进入另一摘要。

摘要使用逻辑相对路径与原始文件字节，解压位置变化不改变版本；重新格式化代码/YAML会改变版本。新增测试证明移动目录摘要不变、修改 scoring/配置/场景/master 会改变摘要。

新版本不自动接收旧版本口径的 checkpoint。当前完整恢复边界是“完整 episode 批次及 PPO 更新完成后”，恢复模型、优化器、词表、行为版本、种子游标和 RNG；不会恢复被 Colab 中断到一半的 episode/梯度步。最多回退至最近保存的完整更新。

恢复要求任务配置一致，包括 `device`、模型、PPO、编成池。不要把 CPU smoke checkpoint 直接作为 CUDA 长训的 `--resume`。保存过 CUDA RNG 时，恢复检查可用 CUDA 设备数量；跨硬件/软件版本不能宣称逐位一致。`--updates` 是额外执行的更新数，不是总目标数。累计时限由外层长训入口维护。

当前 `workers=1` 是明确限制，改成大于 1 会立即报错。游戏正常失败保留为样本；未支持语义/引擎异常中止，不生成零分数据，外层不能用无限重试掩盖相同错误。

## 编成和输入

PLv76、广 HIF、六张指定支援和满成长面板已真实执行到自然终止，见 `portability-audit.json`，观察中 producer_level 始终为 76、有效技能数为 37。该短测正常选拔失败，不是自然完成五场证明。

五偶像配置最初共用广的六支援，其中四张限定 Plan1，导致 Plan2/3 偶像初始化直接拒绝。已反馈根代理，按相同稀有度/属性改为对应流派合法基线；五项逐条结果见 `mixed-pool-audit.json`，报告必须区分正常失败与执行错误。

`loadout_pool` 是非空列表，每项 `{name, loadout, research_config}`。每局按 `seed % len(pool)` 均衡选定，整个 loadout/research_config 替换基础配置，不做嵌套合并；不改变 task.config。无 pool 使用原单编成。选择标签仅进入 episode metadata，策略读取该编成初始化后的真实属性、牌组、支援/P 道具有效机制和当前偶像课程规则。

## 搬运后建议验收

1. 在新进程中从解压目录导入训练包，显式指定解压后的 Arena；不要复用已导入旧 Arena 的 Python 进程。
2. 校验打包 manifest 和 `task.arena_version`，确认 286 张主数据、native loader、scoring/reference、semantic manifest 存在。
3. 每个编成进行真实初始化并编码；任一编成报流派/内容错误，应直接停止修复配置。
4. 在目标设备执行至少一个真实 episode、一次 PPO 更新；关闭进程后恢复，再完成下一更新，确认策略版本/种子游标递增。
5. 只有上述检查通过，再运行累计时限入口并把完整更新的 checkpoint 持久化。
