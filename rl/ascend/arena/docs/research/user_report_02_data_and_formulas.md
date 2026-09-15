# 学マス（Gakuen Idolmaster）本地育成模拟器：数据源清单、公式推导与缺口评估

## TL;DR
- **数据层已基本解决**：vertesan/gakumasu-diff（YAML 全表）是唯一权威原始 master data 源，surisuririsu/gakumas-data（CSV→JSON，含 Effects.md 效果语法文档）是最好的人类可读派生数据集；两者足以覆盖卡牌/道具/支援卡/偶像的所有静态字段。最终评分公式已被社区完整逆向，且与你已确认的 ResultGradePattern / ProduceExamBattleScoreConfig 表吻合。
- **公式层可直接落地**：最终プロデュース評価 = 順位点 + 2.3×ステータス合計 + α×最終試験スコア（α 为分段折算，40001+ 为 0.01 倍，全部端数切り捨て），卡牌对局内 `(基礎+集中)×好調倍率×(1+ボーナス%)×スコアボーナス`，**参数/分数步骤切り上げ(ceil)、元気步骤切り捨て(floor)** 已由 seesaawiki + 传奇玩家 60 次实测 + 模拟器 changelog 三重确认。
- **真正的缺口有三**：①完整的 ~107 个 ProduceExamEffectType 枚举语义字典无人公开（只有原始 dump + Vibbit 的部分分析）；②隐藏概率/事件随机权重/授業·おでかけ收益权重必须自己实测拟合；③官方 AutoPlay AI 权重表已被 Vibbit 逆向（ProduceExamAutoEvaluation 的 evaluation 权重与 r1–r19 向量公式），可直接复用为 baseline 出牌策略。

## Key Findings

### 1. 数据源（数据 + 机制文档），按可操作性排序
- **vertesan/gakumasu-diff**（原始 master DB，YAML，无 API，git clone）——你已确认。它是全生态的上游，由 Go cronjob（campus 仓库）自动更新。
- **surisuririsu/gakumas-data**（已 archive，只读，2025-04-11 起冻结）+ monorepo 内 packages/gakumas-data——CSV 为 source of truth（如 `csv/skill_cards.csv`），生成 JSON；提供 `Idols`/`PIdols`/`SkillCards` 类与 `getById()`/`getAll()`/`getFiltered({types,rarities})`。关键是随包的 **Effects.md** 文档了模拟器使用的效果语法，是目前最好的人类可读效果映射。数据来自一个公开 Google Sheet（手工转录维护）。**无正式 license 声明**，仅注明「unofficial, fan-made… Not affiliated with Gakuen Idolmaster」。
- **kjirou/gakumas-core**——in-lesson 引擎的 JS 复刻，是读取每步取整逻辑的最佳来源（直接 grep `Math.ceil`/`Math.floor`）。
- **seesaawiki.jp/gakumasu（学マスwiki）**——机制文档的中枢：「レッスン・試験詳細」页含完整取整规则与 buff 处理顺序；「最終プロデュース評価」页含全档位公式、NIA/HIF 换算表、A+ 早见表。
- **wikiwiki.jp/gakumas**（コンテスト Wiki*）——含「各種便利リンク」聚合了社区 Google Sheets（如 protonさん的 EXP 效率计算器）与官方 companion wiki 的技能卡全表（センス/ロジック/アノマリー）。
- **计算器/模拟器站点**：gktools.ris.moe（Produce Rank Calculator、Contest Simulator、Rehearsal OCR，多语言 en/ja/zh-Hans/ko，镜像 gktools.unoeins.org）、skypenguin.net、noanyan.com/gkmas/calc、gakumas.moe、leafierlemon、lamrongol、haru-1125.github.io、kantouzin.github.io/gkmas-rank-calculator、gakumas-final-score.netlify.app。
- **中文数据站**：GameKee 学马仕 wiki（gamekee.com/gakumas/，由学园偶像大师同好会维护；图鉴/技能卡/P物品/支援卡/剧情翻译；HTML 无公开 JSON API，受 Gamekee 用户协议约束）、借卡库 idolmaster.caimogu.cc（支援卡共享 DB）、biligame 通用解包指南。
- **翻译/剧情数据**：imas-tools 组织（gakumas-master-translation、gakumas-viewer、GakumasTranslationData）、NatsumeLS/Gakumas-Translation-Data-EN（据 git.natsume.io 镜像快照约 1,024 commits / 286 tags，维护者含 ToastyBuns3939、Mocca；含 localization.json/generic.json）、db.gakumas.info（剧情台词数据库，robots 屏蔽自动访问，**公开 JSON API 状态未确认**，需手动核查）。

### 2. 解包管线（除 campus 外）
- **nijinekoyo/Gakuen-idolmaster-ab-decrypt**（GitHub 确认 149★ / 10 forks，Python）：AssetBundle 解密主力，配 export_asset_bundle.py 导出资产，输入是 `/data/data/com.bandainamcoent.idolmaster_gakuen/files/octo` 目录（需 Root）。
- **dhlrunner/Gakumas_mod**：PC(DMM) 版 modding 工具，F8 从 IL2CPP 生成 dump.cs、dump 受保护的 GameAssembly.dll（IAT 仍破损但可用 Ghidra 读），基于 Umamusume_mod。
- **Il2CppDumper / Cpp2IL / Zygisk-Il2CppDumper / Auto-Il2cppDumper**：il2cpp 元数据 dump；注意学マス metadata version=29，Il2CppInspector/Il2CppDumper 可能报 unsupported，需运行时 dump 或绕过保护。
- **AssetStudio（RazTools/Studio 分支）/ UnityPy**：资产查看导出。
- **MasterMemory（Cysharp）**：master DB 的二进制 KVS 引擎（源生成、只读、排序数组二分查找）。据其 README：「4700 times faster than SQLite and achieves zero allocation per query… When SQLite is 3560kb then MasterMemory is only 222kb」。解析需对应生成的 Resolver + MessagePack。

### 3. 最终评分公式（决定 S/A+ 的评价值）——已完整逆向
「初」レジェンド公式（与你确认的 ResultGradePattern 阈值一致；引用 seesaawiki 学マスwiki）：
```
評価点 = 順位点 + 2.3 × ステータス合計値 + α × 最終試験スコア   （各段端数切り捨て）
順位点: 1位=1700, 2位=900, 3位=500, 4位以下=0          （seesaawiki 原文）
ステ换算: 合計値の2.3倍（端数切り捨て）
最終試験順位による全パラメータ上昇: 1位=+30, 2位=+20, 3位=+10（换算前需相应处理）
α 分段（端数切り捨て）: 0–5,000=0.30 / 5,001–10,000=0.15 / 10,001–20,000=0.08 /
                     20,001–30,000=0.04 / 30,001–40,000=0.02 / 40,001–199,999=0.01 / 200,000+=0
```
档位阈值（seesaawiki 原文）：SS≥16,000 / S+≥14,500 / S≥13,000 / A+≥11,500 / A≥10,000 / B+≥8,000 / B≥6,000 / C+≥4,500 / C≥3,000；与你确认的 ResultGradePattern 完全对齐（含更高档 SSS=20000…SSSSS+=40000）。レジェンド版パラメータ系数改为 **2.1**、且加入中間試験スコア项。**2025/10/31 11:00 官方给最終試験スコア影响加了上限**（200,000+ 段 α=0）。经验值来自 seesaawiki 早见表原文：「パラメータの合計が3100、最終試験1位15000点で評価点11480であと20点となる」（即 3100+15000 ≈ 11480，接近 A+ 的 11500）。

### 4. 卡牌对局内结算公式与取整
社区共识 + 本轮新确认的取整方向（seesaawiki「レッスン・試験詳細」）：
```
最終基礎パラメータ上昇 = カード基礎値 + 集中 × (1+絶好調) × N   （乗算ごとに切り上げ ceil, N=效果适用次数默认1）
最終パラメータ上昇 = 最終基礎 × 好調倍率 × (1+パラメータ上昇割合加算) × (1+上昇量減少割合)  （计算每步切り上げ ceil）
最終スコア上昇 = 最終パラメータ上昇 × スコアボーナス          （切り上げ ceil）
最終元気上昇 = 元気上昇 × 元気上昇率 + 加算 − 減少           （切り捨て floor）
```
- **好調倍率**：好調あり絶好調なし=1.5；絶好調あり=1.5+0.1×好調残ターン；好調なし=1。「好調n倍適用」卡：絶好調なし=1+0.5×n，絶好調あり=1+(0.5+0.1×好調ターン)×n（例 n=3：2.5 / 2.5+0.3×好調ターン）。
- **好印象**：回合结束产分，`ceil(好印象×rate)` 后走好調×スコアボーナス管线。**元気→ブロック**：元気增加率 好調中=2 否则=1。
- **未决项**：集中の複合倍率（集中をN倍適用 与 好調のX%分上昇）是「合算后切り上げ」还是「各自切り上げ再合算」——seesaawiki 明确标注「検証の必要あり」。
- **参数上限**（超出浪费）：レギュラー1000 / プロ1500 / マスター1800 / N.I.A 2000 / NIAマスター2300。

### 5. 官方 AutoPlay AI 权重表——已被逆向，可直接做 baseline
Vibbit 博客（blog.vibbit.me，两篇：2024/09 手动推荐出牌算法、2024/11 コンテスト全自动）逆向了目标方法，原文：「最终确定目标方法是 `Campus.InGame.Exam.ExamRuleCalculator.Evaluate`」，直接分析 **ProduceExamAutoEvaluation / ProduceExamAutoTriggerEvaluation** 表：
- AI 对每张可出牌算 evaluation，出最高分者。v1.4.0 的 evaluation = 19 个加权项 floor 求和（v1.0.0 为 15 项）：`rn = vn × ProduceExamAutoEvaluation.evaluation`，vn 为实时状态（v1=总分, v2=元気, v3=体力, v4=集中, v5=好印象, v6=やる気, v7=min(好調,残), v8=好調ターン … v18=追加ターン）。
- **表字段**（确认）：ProduceExamAutoEvaluation = {type(ExamPlayType), examEffectType(ProduceExamEffectType), remainingTerm, evaluationType(ProduceExamAutoEvaluationType), evaluation(int 权重), examStatusEnchantCoefficientPermil}；ProduceExamAutoTriggerEvaluation = {type, examStatusEnchantProduceExamTriggerId, coefficientPermil}。样例行：`type: ExamPlayType_AutoPlay / examEffectType: ProduceExamEffectType_ExamCardPlayAggressive / remainingTerm: 2 / evaluationType: ...ExamStaminaConsumptionAdd / evaluation: -585`。
- **ExamPlayType 枚举**（完整）：Unknown=0; AutoPlay=1; ManualPlayLesson=2; ManualPlayLessonHard=3; ManualPlayAudition=4。
- 持续/延迟效果项 r19 用第二张表：`r19 = Σ floor(m1×m2+0.0001)`，m1=(coefficientPermil/1000)×剩余回合。审查战特例 r1 按三属性 bonus permil 归一化：`r1 = round(v1×3000 / (dance+vocal+visual permil), 6)`。
- **已知 AI「bug」**：无匹配 coefficientPermil 的卡默认权重=1 导致 AI 几乎不出（如「輝くキミへ」）；审查战持续加分效果跳过三属性平衡而被高估。作者不确定是否有意为之。

## Details

**取整证据链**：seesaawiki「レッスン・試験詳細」页两处不同方向——元気标注「小数切り捨て」、参数与スコアボーナス步骤标注「計算する毎に小数点以下切り上げ」；页内一位传奇档玩家在评论区回复称做了约 60 次游戏内验证、未发现与「切り上げ」不符的结果。surisuririsu/gakumas-tools 模拟器 CHANGELOG 佐证元气方向：「Round stamina numbers down (i.e. round consumed stamina up)」。

**レッスン上昇量公式**（note.com/涼鈴，实测整理）：
```
通常上昇 = CLEAR + PERFECT
レッスンボーナス分 = (CLEAR+PERFECT) × ボーナス率%   （切り捨て）
追い込み上昇 = CLEAR；追い込みボーナス全属性 = PERFECT/3（除不尽时被选属性优先+1，其余相等整数分配）
```
最終試験前追い込み CLEAR=165 / PERFECT=435（合计600）。终盘授業触发的レッスン目标=45（等同4回合目SPレッスン），获得 目標+パーフェクト=90+レッスンボーナス，且触发授業系与レッスン終了系效果、体力回复，性价比高。

**NIA 审查战分数**（seesaawiki）：素点=`round(系数×パラメータ+常数)`，如 FINALE 適性◎流1 `round(0.223×param+362)`；親密度20→`ROUNDUP(素点×1.5)`；ファン数换算 `ROUND(素点×2.20005/2.26673/2.23333)` 分别对应メロBang/GALAXY/FINALE。NIA 的评价由「パラメータ×2.3 + ファン数分段」构成，最终审查约20万分后分数价值骤降（减衰开始线：一次约5354/二次约64272/最终约199203）。

**发动预约/持续效果时机**（seesaawiki「レッスン・試験詳細」详列 01A–TTTB 各阶段判定表）：スキルカード/Pドリンク的「発動予約」实为「直接効果」，P アイテム/応援/トラブル 的才是真「持続効果」；2025/6/19 起区分「直接効果」。对精确复刻回合内 effect ordering 至关重要——出牌后先结算画面上侧（P アイテム）再结算下侧（卡牌自身），同一时机内按类别排序。

**亲愛度**：按各 Lv 解锁条件（非纯积分，如 Lv5=中間試験1位通過，Lv6→7=角色固有 achievement，Lv21–27=积分）提升；效果含试验スコアボーナス、削除回数、ドリンク獲得上限、お仕事报酬、コミュ解锁。对应表 CharacterDearnessLevel。

## Recommendations

**分阶段落地：**
1. **数据摄取（1–2天）**：直接消费 vertesan/gakumasu-diff 的 YAML 作为唯一真源；用 surisuririsu 的 Effects.md 作为效果语法参照；建立你已列出的关键表到内部 schema 的映射。不要重新解包，除非要图像/剧情资产或验证 diff 落后于当前版本。
2. **静态育成流程（3–5天）**：按 Produce.steps(13/16) + ProduceStepType 建周程状态机；レッスン上昇用涼鈴公式；最終参数进入 ResultGradePattern 前套用最終試験順位 ±30。
3. **卡牌对局引擎（1–2周）**：以 kjirou/gakumas-core 为参考实现（grep 其 Math.ceil/floor 逐行核对取整），buff 处理顺序照 seesaawiki 阶段判定表；ProduceExamEffectType 语义用 dump + Vibbit 的部分映射，缺失的枚举靠单元测试对拍游戏实测值补齐。
4. **AI baseline（3–5天）**：直接移植 ProduceExamAutoEvaluation 的 evaluation 权重 + r1–r19 向量作为 HeuristicStrategy 的 baseline，无需自研；再用你自己的搜索策略（如 beam/MCTS）超越它。
5. **最终评分模拟（2–3天）**：α 分段 + ResultGradePattern 阈值直接落地；用 gktools/skypenguin 计算器交叉验证边界值。

**触发调整的基准**：若 diff 版本落后当前游戏版本 → 自建 campus 或 nijinekoyo 管线重新 dump；若对局分数与游戏实测偏差 >1% → 优先排查取整方向与 buff 处理顺序（历史最大误差源）；若要覆盖コンテスト/アイドルの道 → 注意其 effect 公式与「初」不同，seesaawiki 明确标注「調査中」。

## Caveats
- **必须自己实测拟合的**：隐藏发动概率、授業/活動支給/おでかけ/相談 的随机权重与收益、レッスン CLEAR/PERFECT 的确切基线（ProduceStepAuditionDifficulty 提供 baseScore/forceEndScore/parameterBaseLine 但事件随机性未公开）。社区亦无这些的公开权重。
- **~107 个 ProduceExamEffectType 完整语义字典无人公开**：只有原始 dump（无注释）+ Vibbit 的部分枚举 + surisuririsu Effects.md 的语法。这是最大的手工工作量，建议用「dump 枚举名 → 单测对拍游戏实测」逐个补全。
- **取整未决项**：集中複合倍率的合算/切り上げ顺序 seesaawiki 标注需检证；コンテスト/道 的分数公式与初编不同。
- **公式随版本变动**：2025/10/31 加了最終試験スコア上限；レジェンド系数 2.1；新プラン（アノマリー等）持续加入。任何硬编码系数都要可配置。
- **法务/ToS 边界**：以上数据均为解包所得，版权归 BNEI。纯本地离线模拟器风险较低，但公开再分发 master data／资产可能侵权；使用运行时 hook/mod（nitidus、Gakumas_mod、skyfsj/gakumas-assistant）连接游戏客户端有封号风险（skyfsj 项目明确警告「使用本脚本将带来包括但不限于账号被封禁的风险」）。建议模拟器只依赖社区已公开的派生数据（CSV/JSON），避免自行再分发原始资产。