# RL 交接与 Arena 移区机制阶段交付

2026-09-08，继续现有 `codex/arena-live-bridge` 工作树；没有清理或覆盖前阶段成果。

## RL 交接

- [RL_DESIGN_HANDOFF.md](RL_DESIGN_HANDOFF.md) 汇总用户目标、培育/考试耦合、模型拆分候选、奖励/终止语义、输入缺口、现有后端差异、硬件测量与独立 agent 的交付要求。
- 用户允许将来使用 Colab，5080 不作为选型硬上限；未购买算力、安装训练依赖或启动 RL。
- [输入诊断脚本](../scripts/audit_rl_observation_gap.py) 与 [合成测量结果](examples/rl_observation_gap.json) 再现：好调 3/7 回合的旧候选特征相同，但实际引擎执行分别为 3/7。该缺口保留给公共编码的下一版本处理，不强行替 RL agent 选架构。

## Arena 实现

- [完整设计路线图](ARENA_COMPLETION_ROADMAP.md) 按资源/机制、实体/选择、培育生命周期、官方内容、全局接口和保真划分完成标准。
- 原生运行时新增自身移区效果处理，按 `moveEffectTriggerType` 与有序 `moveProduceExamEffectIds` 执行；不使用卡牌 ID 分支。
- 抽牌、生成/复制入手、保留和返回手牌复用处理入口；同区移动、满手牌退回牌堆、保留溢出拒收不误触发；移区不被计为出牌。
- `Card.on_move` 开放给内容作者。严格检查效果引用；Hand/Hold 之外的目标和未知条件列表明确拒绝。
- 复用 ContentExam 的开场/动作暂停和确定性恢复，不新增外部日志/游戏执行器。
- 原生准入增加 8 个真实卡牌版本：当前 1688 个卡牌版本 + 28 饮料 + 662 考试 P 道具，共 2378 条；仍有 26 卡牌版本、1 饮料、376 P 道具被标为独立考试入口不支持。全部 4628 条定义继续保留。

字段、执行语义、最小 JSON 与证据边界：[CARD_MOVEMENT_CONTRACT.md](CARD_MOVEMENT_CONTRACT.md)。完整可运行样例：[content_card_movement.json](examples/content_card_movement.json)。

## 版本与产物

- 内容 Schema `arena-content/1` 新增可选 `Card.on_move`；Schema 与合成流程 trace 已重新生成。
- `arena-content-rules/2` 进入编译 digest，公共 ContentExam/ContentSession view 与 encode 返回 `rules_version`。旧模拟快照不能按新规则静默重放；保留旧执行环境读取，或启动新模拟会话。快照格式/恢复 API 保持。
- 目录能力版本 `arena-native-exam-capabilities/2` 进入 manifest/JSON 导出；verify 同时检查能力版本，防止主数据未变就误认旧准入结果仍有效。
- `data/catalogue` 的目录 JSON、SQLite、manifest 与合成验证结果已更新；源数据 revision 和哈希保持。
- 已发布的在线报告仍是前阶段版本，本轮没有重新部署，不把本地更新冒充已上线。
- `arena-live/1`、`arena-session/1`、submitted/uncertain 原命令恢复和去重、既有奖励/咨询接口、observed/2/3 张量语义均未改动。

## 验证

- 新增 12 项移区测试：自身效果数值/顺序、同区与满手牌、复制和返回、保留成长目标、溢出两种选择、开场选择、保存恢复、非法配置与真实 8 版本。
- 真实 8 版本分别触发了新增自身效果，并断言卡面给出的元气/やる気/抽牌/保留/成长结果。场景为明确合成数据，未作新增实机录像声明。
- 全量 2378 条 12 回合合成探针：2378 passed；58 个卡牌探针未达到出牌条件，结果单独保留。该结果不表示所有组合/被动触发已验证。
- 目录源/产物/能力版本校验通过；Ruff 和 Python 编译检查通过。
- 完整 Python 回归：**574 passed, 3 skipped，193.22 秒**，日志 `.gakumas_rl_cache/movement-full-tests.txt`。包括既有奖励/咨询、实况 submitted/uncertain 恢复与去重、录像及内容流程回归。

## 剩余边界与下一步

自身移区效果与其他 P 道具/卡绑定触发的完整先后顺序、批量移动及溢出时点仍需实机边界证据。本阶段没有改变 HIF 明星性近似、隐藏随机分布，也没有宣告整个游戏 1:1 完成。

接着完善通用 P 道具培育生命周期（取得、替换、次数、间隔与周次/阶段触发），再批量迁移真实事件与官方路线；模型/算法/奖励比较交由 RL agent。
