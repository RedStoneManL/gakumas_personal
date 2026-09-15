# 学マス（学園アイドルマスター）本地沙盒模拟器现状调研

## TL;DR
- **能。** 已存在离线可跑、纯逻辑、可编程调用的学マス「打牌」引擎——核心是 `kjirou/gakumas-core`（TypeScript、MIT、发布到 npm、无 UI/DOM 依赖），配合 `surisuririsu/gakumas-data`（Idols/PIdols/SkillCards/PItems/Stages 的 JSON 数据）与 `vertesan/gakumasu-diff`（解包出来的完整 master data），可以拼出「卡数据 + 回合制对局模拟 + 可编程 API」的自用沙盒。
- **但没有现成的 RL 环境。** 没有人把学マス 封装成 Gym/Gymnasium 环境或开源 MCTS/强化学习 solver；官方（QualiArts）在 CEDEC 2024 讲过内部用深度强化学习 + MCTS + 灰盒优化做卡牌平衡，但**代码不公开**。社区侧只有启发式（heuristic）出牌 AI（gakumas-tools 的 contest simulator）和纯逻辑引擎。
- **主要缺口是「胶水层」**：把 TypeScript 引擎接上批量/蒙特卡洛跑分、seed 可复现、以及 Gym 风格 step/reset 接口，需要你自己写；这部分工作量小到中等（数天到两周级别）。

## Key Findings

**1. 引擎层（核心，能打牌）**
- `kjirou/gakumas-core` — 学マス 卡牌对局部分的纯逻辑再现引擎。TypeScript、MIT 许可、已发布到 npm（`npm install gakumas-core`）。公开 API 包括 `initializeGamePlay`、`startTurn`、`playCard`、`skipTurn`、`endTurn`、`useDrink`、`getNextPhase`、`generateLessonDisplay`、`getLesson`、`diffUpdates`、`patchDiffs` 等，采用不可变状态设计（每次返回新的 `gamePlay`）。13 star、TypeScript，最后更新 2024/09/22；作者本人称已在 2024 年 9 月后停止追随新卡（最后一次主要 PR 是 2024/09/22 加入【Feel Jewel Dream】有村麻央）。
- `kjirou/gakumas-lesson-simulator` — 基于 gakumas-core 的 Gatsby 网页 UI（β），2 star。作者在 README 明说：「作ってみたはいいですが、使い道が思いつかないので、アイディア募集中です。特に、コアエンジンを使って何か作ってくれると、とてもありがたいです。」（做出来了但想不到用途，尤其希望有人用 core engine 做点东西。）——对你的用例是好消息：作者本人就期待有人拿它做二次开发。
- `surisuririsu/gakumas-tools` 内含 `gakumas-engine` + contest simulator — 一个**独立于 gakumas-core 的第二套 JS 模拟引擎**，76 star、16 fork，作者 risりす(Robert, Canada)，维护非常活跃（changelog 更新到 2026-08-28）。据 DeepWiki 分析，它是 Next.js web app + 自定义 game engine，"executes simulations using web workers"，可"run thousands of simulations to analyze performance distributions"——实现了竞技场（コンテスト）打牌模拟、启发式出牌策略、Web Worker 并行跑多次模拟、分布图/箱线图/中位数、CSV 导出分数。

**2. 数据层**
- `surisuririsu/gakumas-data` — Idols / PIdols / SkillCards / PItems / Stages 的结构化数据，JSON 格式，静态方法 `getById` / `getAll` / `getFiltered`。数据靠人工从 Google Sheet 誊写维护（非解包），standalone 仓库已于 2025-04-11 归档，现行版本在 gakumas-tools monorepo 的 `packages/gakumas-data`。无明确 license。
- `vertesan/gakumasu-diff` — 直接从游戏 master DB 解包/追踪出来的完整数据，YAML 格式，覆盖 `IdolCard`、`ProduceCard`（技能卡）、`ProduceItem`（Pアイテム）、`Character`、`ExamInitialDeck` 等上百张表。README：「Traces the master database changes of Gakuen-Idolmaster」，57 star、2 fork、180 commits，作者 Vertesan(UK)，随游戏版本自动更新（背后是 `vertesan/campus` 定时任务，Go 写的 cronjob）。这是最权威、最全、最新的原始数据源。
- 解包工具链：`nijinekoyo/Gakuen-idolmaster-ab-decrypt`（AssetBundle 解密，Python）、`DerPopo/UABE`、`Perfare/AssetStudio`、UnityPy 等通用工具；数据存储用的是 MasterMemory（二进制 KVS）。

**3. AI / RL 现状**
- 官方 QualiArts 在 CEDEC 2024 初日（2024/08/21）公开了做法：讲题「『学園アイドルマスター』における適応的ゲームAIとグレーボックス最適化を用いたバランス調整支援システムの実現」，由 CyberAgent 研究工程师伊原滉也氏 与 QualiArts 学マス首席服务端工程师那須勇弥氏 主讲（据 Famitsu / 4Gamer 2024/08/21 报道）。做法是深度强化学习 lesson AI + MCTS 基线 + 灰盒优化 deck 探索，Python 训练 + .NET/Unity 逻辑 socket 通讯——但**不开源**。
- 社区侧无 Gym/Gymnasium 封装、无开源 MCTS/DQN solver。最接近的是 gakumas-tools 的启发式策略 + 批量蒙特卡洛跑分。

**4. 对比案例（生态成熟度参照）**
- ウマ娘：`hzyhhzy/UmaAi`（育成场景模拟器 + 搜索）、`mee1080/umasim`（育成模拟器网页 + 开源）等，生态明显更成熟、有真正的搜索/最优化 AI。学マス 目前停留在「纯逻辑引擎 + 启发式」阶段，比 ウマ娘 落后一档。

## Details

### 引擎保真度对比

**gakumas-core（kjirou）**
- 建模范围：只做「レッスン/试验」的卡牌对局部分，**不含育成（プロデュース 全流程）**。作者原话：「再現したのはデッキ構築型カードバトル部分のみで、育成ゲーム部分は含みません」「カードバトル部分については、通常発生しないような状況を除いて、正確に再現できているつもり」。
- 状态效果：README 明确出现「好印象」「バフ/デバフ」「パラメータ/スコアのパーフェクト」；`clearScoreThresholds: {clear, perfect}` 是初始化核心参数，分数计算已实现。集中/やる気/元気/好調/絶好調 等标准 buff 未在 README 逐个点名，但 TODO 未把它们列为未实现，基本可判定已作为 modifier 实现（建议直接看 `src/data` 确认）。
- Pアイテム：已实现（`producerItems` 是初始化参数），仅「コンテスト专属 Pアイテム」未实现。
- 卡牌强化：`{id, enhanced:true}` 支持；部分经レッスンサポート 升到 ++/+++ 的数值未知。
- headless：是，纯状态转换库，无 DOM 依赖，`generateLessonDisplay` 只产出显示数据不渲染。
- 初始化示例（README）：
  ```js
  initializeGamePlay({
    idolDataId: "kuramotochina-ssr-1",
    specialTrainingLevel: 3,
    talentAwakeningLevel: 2,
    cards: [{ id: "apirunokihon" }, { id: "genkinaaisatsu", enhanced: true }],
    producerItems: [{ id: "masukottohikonin" }],
    turns: ["dance", "dance", "dance", "dance", "dance", "dance", "dance"],
    clearScoreThresholds: { clear: 100, perfect: 200 },
  });
  ```
- 生命周期：`getNextPhase` 返回 `"lessonStart" → "turnStart" → "playerInput" → "turnEnd" → ... → "lessonEnd"`，配合 `startTurn / playCard(gamePlay, handIndex) / skipTurn / endTurn` 驱动。`diffUpdates` 可抽出每步的细粒度变更记录（如 `{kind:"score", actual:9, max:9}`），非常适合做日志/reward 提取。
- **RNG 可复现性：未确认**——README 的 `initializeGamePlay` 没有显式 `seed`/`rng` 参数。不可变设计架构上兼容确定性重放（RNG 状态可能存在 gamePlay 对象内），但洗牌是否 seedable 需要读源码确认（若用裸 `Math.random` 则需 patch）。这是 AI 训练复用的**最关键待验证点**。
- batch/CLI：无现成 CLI 或蒙特卡洛封装，但作为 npm 库可直接在 Node 脚本里 for-loop 跑。

**gakumas-engine（gakumas-tools monorepo）**
- 建模范围：竞技场（コンテスト）打牌，含体力/元气(genki)/集中(concentration)/好印象(good impression)/やる気(motivation)/好調(good condition)/絶好調(perfect condition)、full power（全力）stance、支援卡加成、赛季 stage 效果、卡牌 customization。
- 保真度：changelog 显示对分数公式、效果触发顺序、各卡各 Pアイテム 反复精修（如「Score formula now multiplies concentrationMultiplier...」「limit hand size to 5」「improve simulator performance by 3x」等），2024/08 起持续更新至 2026/08，是**目前最活跃、覆盖新卡最全**的模拟器。
- 内置**启发式出牌 AI**（heuristic strategy，带 action depth 限制的浅层搜索 + 效果加权），并行跑多次模拟出分数分布，可导出 CSV。
- 语言 JavaScript，是 Next.js Web app 的一部分，headless 复用需要从 monorepo 里把 engine 包抽出来。

### 数据获取路径与法务
- 三条路径：(a) 解包（vertesan/gakumasu-diff，最权威最新，YAML；需 AssetBundle 解密工具）；(b) 人工誊写（gakumas-data，Google Sheet→CSV→JSON，可能滞后/有笔误）；(c) 爬 wiki（wikiwiki.jp/gakumas、GameKee 等）。
- **无官方公开 API**。所有数据均来自解包或社区誊写。
- ToS 风险：解包与自动化操作游戏客户端（如 MaaGakumasu、gakumas-assistant 这类基于机器视觉的自动脚本）违反运营方使用条款；但**纯离线用解包数据 + 纯逻辑引擎跑模拟**（不触碰线上服务、不自动化真实客户端）风险显著更低——这正是你的用例。注意 gakumas-data 无明确 license，商用/再分发需谨慎；gakumas-core 是 MIT，可放心复用。

### 相关但不直接适用的项目
- `chinosk6/gakuen-imas-localify`、`NatsumeLS/Gakumas-Translation-Data-EN`：汉化/英化本地化数据。
- `SuperWaterGod/MaaGakumasu`、`hjx986234675-ai/MaaGakumasu-AutoProduce`、`skyfsj/gakumas-assistant`、`Pigeon-Server/gakumas-assistant`：基于图像识别（YOLOv11）自动操作真机/模拟器的脚本，**不是纯逻辑沙盒**，且有明确 ToS 风险，不适合作为 AI 训练环境。
- `dhlrunner/Gakumas_mod`：PC(DMM)版 IL2CPP dump/hook 工具。
- `imas-tools/gakumas-viewer`、`vertesan/hatsuboshi-library`：剧情/图鉴查看器。

## Recommendations

**推荐技术栈（自用本地沙盒）**
1. **数据**：直接用 `vertesan/gakumasu-diff` 的 YAML 作为权威 master data 源（技能卡 `ProduceCard`、Pアイテム `ProduceItem`、偶像卡 `IdolCard`、初始牌组 `ExamInitialDeck`）。若只想快速起步、要现成 JSON + 查询 API，用 `surisuririsu/gakumas-data`（注意可能滞后、无 license）。
2. **打牌引擎**：以 `kjirou/gakumas-core`（MIT、npm、纯逻辑）为主，因为它 API 最干净、最适合被程序驱动。若你要的是**竞技场对局 + 现成启发式 AI + 批量跑分**，改用/参考 `gakumas-tools` 里的 `gakumas-engine`。
3. **可编程接口**：gakumas-core 本身就是 Node 库，`initializeGamePlay → startTurn → (playCard|skipTurn) → endTurn` 循环即可脚本化。

**分阶段落地**
- **阶段 0（半天）**：clone gakumas-core，跑通它的 e2e 测试（作者用录像还原的测试用例，如 `kuramotochina-ssr-1.test.ts`），确认引擎行为符合预期。
- **阶段 1（1–3 天）**：读 `src/` 确认 (a) RNG 是否 seedable、(b) 集中/やる気/元气/好調/絶好調 modifier 是否齐全。若 RNG 用 `Math.random`，注入一个可 seed 的 PRNG（这是 AI 复现的前提）。
- **阶段 2（2–5 天）**：写一层薄封装，暴露 `reset(config) / step(action) → (obs, reward, done)` 的 Gym 风格接口（Node 端），或用 socket/stdio 桥接到 Python（官方 CEDEC 方案也是 Python↔逻辑 socket 通讯，可借鉴）。reward 用最终 score / 是否达 perfect 阈值。
- **阶段 3（可选，1–2 周）**：接 MCTS 或 PPO/DQN。因为学マス レッスン 本质是 MDP（官方也这么建模），MCTS 是性价比最高的第一版 baseline。
- **数据同步**：写个脚本把 gakumasu-diff 的新卡 YAML 转成 gakumas-core 的卡定义格式——这是长期维护的主要成本（gakumas-core 作者已停更，新卡要自己补）。

**阈值/触发条件**
- 若你只需要「跑固定牌组、算分数分布」→ 直接用 gakumas-tools 的 engine + 它现成的蒙特卡洛，几乎零开发。
- 若你要「训练会自己出牌的 agent」→ 必须先解决 seed 可复现（阶段 1），否则训练不稳定。
- 若你要「最新卡池」→ 必须走 gakumasu-diff + 自己补引擎卡定义；gakumas-core 的内置卡只到 2024/09。

## Caveats
- gakumas-core 的卡数据**停在 2024 年 9 月**，之后所有新偶像/新卡/新机制（如アノマリー，作者自己都说「アノマリーって何ですか？」）都没有；gakumas-tools/gakumas-engine 才是持续跟新卡的那个。
- gakumas-core 的 **RNG 是否可 seed 未经源码确认**，这是 AI 训练能否复现的关键，需你亲自验证。
- gakumas-core 只做卡牌对局，**不含育成全流程**（レッスン 之外的日程、支援事件、参数继承等都没有）；如果你的 AI 目标是「整个プロデュース 周目最优化」而非单场对局，缺口很大，需要自己补育成层（可参考 gakumas-data 的支援卡数据 + 各计算器的评分公式）。
- gakumas-data 靠人工誊写，可能有笔误或滞后；无明确 license。
- 没有任何现成的学マス Gym 环境或开源 RL solver——这块得从零写，本报告的工作量估计基于「复用引擎、只写胶水层」。
- 官方 CEDEC 2024 提到的「AIによってリリース前にレッスンを10億回、人力なら1900年分の検証を実現」（10 亿次模拟、1900 年人力当量，Famitsu 2024/08/21）、MCTS+深度强化学习 等均为**官方内部系统，不开源**，仅可作为方法论参考。
- 部分社区自动化工具（MaaGakumasu 等）操作真实客户端，涉及 ToS 风险，与「离线纯逻辑沙盒」是两回事，不建议用于训练。
