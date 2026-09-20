# V6 关系编码的验收范围

日期：2026-09-18。基线源码：`cb599a1502c832311558749ec48d2729de4af119`。交付分支：`codex/relational-v6`。

## 已在本地验证

平台 Windows AMD64，Python 3.12，PyTorch 2.9.1+cu128；本版新增模型验收使用 CPU，不能视作 Ascend/NPU 验收。本次没有启动正式长训练，没有访问游戏或 Maa，没有更改远端运行。

回归结果汇总：训练基础组 **53 项通过**；搜索/关系模型/打包组 **124 项中 121 通过、3 跳过**；另一个分片规约脚本全部通过。合计 174 项通过、3 项明确跳过。跳过项为 Windows 原生 Gloo 与两项历史 Windows supervisor 流程。训练基础组有一项 CUDA 批处理测试最初因本地缺少完整培育依赖失败，补齐仓库声明的 PyYAML/Gymnasium/Pydantic/orjson 后单独复测通过；这不涉及服务器环境变更。搜索组最新日志为 `regression-final.txt`，该依赖复测为 `regression-dependency-rerun.txt`。

| 验证层次 | 实际验证内容 |
|---|---|
| 原生语义桥 | 调用绑定的 JS 规则编译；绿豆 37 四栏 AST 不变而用后区域改变；强制初始牌、成长 overlay、语句顺序、DSL 原生解析、RNG 增量 0 |
| 预编译目录 | 当前 870 个基础定义，合计 2207 个去重形态、106 个 DSL 程序；遍历真实五 profile 可达 Guidance.actions 的下一形态，均可离线命中 |
| 编码关系 | 旧 atoms/edges 不变；固定卡与候选计数去重；公开回合 uses turnsElapsed；隐式依赖与 fixed 运算区分；前后强化；临时 effective 优先；共享次数和 allocator 匿名关联 |
| 模型及梯度 | 五阶段初始输出逐项等于旧网络；13 类 adapter、6 类 encoder、receiver gate、candidate query 在输出层预热后有梯度；Actor/Critic 独立；mask/type/phase 错误拒绝 |
| 实际场景整合 | 五 profile × 五阶段的 25 个观察走 cache-only sideview；原生五个 3 回合短局均能使用饮料、出牌并结束；这是通路验收，不是正常九回合成绩评估 |
| 进程采样 | 异构 batch 的 collate 与 worker precollate→merge 逐 tensor 相同；真实 spawn 子进程继承离线目录，无 Node 编译，重建结果一致 |
| 学习入口 | 真实观察的五阶段 forward/backward；PPO + 非零搜索 CE 可更新新 Actor；非零 CE 的目标为明确标注的合成通路测试，不冒充高质量搜索发现 |
| 迁移与日程 | 旧张量/Adam 按名严格继承，新参数 fresh；重排保存组不会错配；旧 5 组及新 7 组计划兼容；8 批适配不被慢速初始评估消耗 |
| V6 恢复/冻结 | 新分支预热两步后 save/load，下一步 loss、全部参数/Adam/RNG 逐项相同；critic completion 实际更新新 Critic，同时旧/新 Actor 及其 Adam 状态不变 |
| 打包 | Python/MJS/配置/指导/测试完整；exam_search 与部署 exam-search 两种布局有效；语义缓存从包中排除，要求目标部署重新准备 |

单独的真实引擎 CPU 预检使用发布 checkpoint：

```text
SHA256 f482b54dccaddfd3d154e963b28142aad6d831baca93b9ac777e2c3a13954eb8
新模型参数       4,563,708
有效 MCTS 根     2 / 2
原生短局        4
实际决策记录    8
七组 Adam 更新  1
变化参数张量    122（新 Actor 末层 2，新 Critic 末层 4）
RNG 恢复        通过
```

这个极短预检中的搜索学习权重为 0，所以它只证明 MCTS/标签/推理/更新连接正常；非零 CE 另由上表的独立通路测试覆盖。零残差首步主要更新末层符合设计，不能据此宣称新深层已学会游戏。

## 明确的限制

- 未验证真实 Ascend 新模型算子覆盖、HCCL 训练、峰值内存、吞吐和长期稳定性。既有底层适配文件未改，不等于新增算子自动已在 NPU 验收。
- 未证明比 V5 得分更高，也未运行一个完整规模的生产联合批次。服务器必须执行训练指导中的单卡、多卡、单批烟雾流程。
- 旧分支保留历史输入以保持初始函数，包括 pending-choice 的嵌套效果 allocator 无关数值；新关系视图已匿名化并验证重命名不变。不能宣称整个模型已经具有该不变性。
- 临时支援强化使用 public effective，无法由基础卡缓存保证的 traits 明确 unresolved；未知程序符号仍保留，不把“没显式关系边”解释为“无影响”。
- 多固有/P-item 用同一实体接口表达，不等于活动周或其他新模式的完整规则已接入。当前合法候选池、场景配置、训练目标均保留。
- 初始大 draft 的副视图约 1.9k 实体、21k–22k atoms，构建成本高于旧输入；CPU冷构建约 78–89ms 的窄测量不能推断 Ascend 吞吐。本版缓存不可变观察的副视图，不缓存跨更新的学习 embedding。

复现入口见 [训练指导](RELATIONAL_V6_TRAINING.md)。本地原始预检与回归日志保存在忽略目录 `rl/ascend/artifacts/relational-v6/`；后续服务器证据应另存并标注机器和版本。
