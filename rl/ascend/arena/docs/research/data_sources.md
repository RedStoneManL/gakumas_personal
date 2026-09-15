# 学マス 模拟器数据源调研：名称映射 / 校验源 / 社区数据 / 官方公告

> 调研日期：2026-09-07。本文与 `user_report_02_data_and_formulas.md`（公式推导）互补：那篇讲"公式从哪来"，本文讲"**id → 中/英/日名称怎么对上**、**拿什么校验模拟器数值**、**各社区站点能不能抓**"。
>
> 约定：master 数据 = `vertesan/gakumasu-diff` 的 YAML（本地 `scratchpad/ext/gakumasu-diff`，HEAD 2026-09-04，286 张表）；id 形如 `p_card-00-acc-0_002` / `pitem_00-0-004-0-000` / `pdrink_00-1-001` / `s_card-1-0000` / `i_card-amao-1-000` / 角色 `amao`。
>
> 样本文件统一放在 `scratchpad/datasrc/samples/`（文件名前缀标明来源：`imas-tools_*`、`natsume-en_*`、`chinosk_*`、`gakumas-tools_*`、`haru-1125_*`、`campus_*`）。
>
> 网络限制：本会话的出口代理放行 github.com，但**屏蔽了** gktools.ris.moe、skypenguin.net、noanyan.com、gakumas.moe、*.github.io、*.netlify.app、seesaawiki.jp、wikiwiki.jp、gamekee.com、wiki.biligame.com、moegirl、gakuen.idolmaster-official.jp。凡是站点本身无法访问的，本文用其 GitHub 源码克隆（`scratchpad/ext/`）或搜索引擎摘要代替，并在文中标注"未直接验证"。

---

## 1. 名称映射 / 翻译数据集

### 1.1 总览

| 数据集 | 语言 | 键 | 覆盖 master 表 | 格式 | 最新提交 | 本地路径 |
|---|---|---|---|---|---|---|
| `imas-tools/gakumas-master-translation` | zh-Hans | **master 表 + 主键**（含嵌套主键） | 106 张（含 ProduceCard/Item/Drink/IdolCard/SupportCard/Character/ProduceDescription*/ProduceExamEffect/ProduceSkill） | JSON `{rules:{primaryKeys}, data:[...]}` | 2026-09-04 | `datasrc/gakumas-master-translation` |
| `chinosk6/GakumasTranslationData` | zh-Hans | 同上（`local-files/masterTrans/` = 上表 `data/` 原样拷贝，`diff -q` 一致）+ `localization.json`(key) + `generic.json`(日文原文) | 同上 | JSON + Release zip | 2026-09-04 (v2.3.36) | `datasrc/GakumasTranslationData` |
| `NatsumeLS/Gakumas-Translation-Data-EN` | en | **同一 masterTrans 格式**（108 张）+ `localization.json` + `generic.json` | ProduceCard/Item/Drink/IdolCard/SupportCard/Character/ProduceSkill/ProduceExamEffect/… **但没有 `ProduceDescription.json`** | JSON | 2026-09-04 | `datasrc/Gakumas-Translation-Data-EN` |
| `surisuririsu/gakumas-tools` `packages/gakumas-data` | ja（名称）+ 自家 DSL | **自有整数 id**，无 master id；只能按日文名 join | SkillCards 869 / PItems 483 / PDrinks 27 / PIdols 153 / Stages 179 / Customizations 110 | CSV(源) + JSON(生成) | 2026-09-05 | `datasrc/gakumas-tools/packages/gakumas-data` |
| `haru-1125.github.io` `data/*.js` | ja | 按日文卡名 | 支援卡能力表（支援卡 + 能力档位数值） | JS 常量数组 | 2026-08-13 | `datasrc/haru-1125.github.io/data` |
| `vertesan/hatsuboshi-library` | UI en / zh-Hans | — | 不含卡名翻译（卡名走后端 API 返回的 master） | TS | 2026-08-02 | `datasrc/hatsuboshi-library` |
| `chinosk6/gakuen-imas-localify` | — | — | 插件本体，2024-07 被 BNEI DMCA 下架（GitHub 仓库已禁用），代码镜像在 `git.chinosk6.cn/chinosk/gkms-local` | — | — | 未克隆 |

结论先行：**中文用 imas-tools，英文用 NatsumeLS，两者是同一套 "masterTrans" 格式、同一套主键规则，可用同一段合并代码处理**；`gakumas-tools` 的数据没有 master id，只作校验/对照，不作名称主源。

### 1.2 imas-tools/gakumas-master-translation（中文，主推）

- 仓库结构：`data/*.json`（译文）、`gakumasu-diff/orig`（submodule 指向 vertesan/gakumasu-diff）、`gakumasu-diff/json/*.json`（由 `scripts/gakumasu_diff_to_json.py` 从 YAML 抽出的**日文原文**，同格式）、`scripts/`（抽取/合并脚本）。`Makefile`: `make update` = 拉最新 gakumasu-diff 并重新生成 JSON；`make gen-todo` / `make merge` 走人工预翻译流程。
- 文件格式（每表一个文件）：

  ```json
  {"rules": {"primaryKeys": ["id","upgradeCount",
       "produceDescriptions.produceDescriptionType", "produceDescriptions.examDescriptionType",
       "produceDescriptions.examEffectType", "produceDescriptions.produceCardCategory",
       "produceDescriptions.produceCardMovePositionType", "produceDescriptions.produceStepType",
       "produceDescriptions.targetId"]},
   "data": [{"id":"p_card-00-acc-0_002","upgradeCount":0,"name":"睡意",
             "produceDescriptions":[{"produceDescriptionType":"ProduceDescriptionType_Exam", ..., "text":""}, ...]}]}
  ```

  `rules.primaryKeys` 里带点号的项表示**嵌套数组的复合主键**：`produceDescriptions` 数组里的每个段落用 7 个枚举字段 + `targetId` 定位，而不是按下标。这很重要——我实测 `p_card-00-act-0_002` 译文有 14 个段落、同仓库日文 JSON 只有 11 个（译文含历史遗留段落），**按下标 zip 会错位**，必须按 `rules.primaryKeys` 做 key 合并。`huochai67/gakumas-wiki/pipeline/translation.ts` 的 `applyTranslation()` 是现成的参考实现（TypeScript，~120 行，处理根主键 + 嵌套主键 + 重复键降级）。
- 各表主键与被翻译字段（摘自 `scripts/gakumasu_diff_to_json.py` 的 `primary_key_rules`）：
  - `Character`: `[id]` → `lastName, firstName`
  - `IdolCard`: `[id]` → `name`；`SupportCard`: `[id, upgradeProduceCardProduceDescriptions.*]` → `name` + 描述段
  - `ProduceCard`: `[id, upgradeCount, produceDescriptions.*]` → `name` + 描述段；`ProduceItem` / `ProduceDrink`: `[id, produceDescriptions.*]`
  - `ProduceSkill`: `[id, level, produceDescriptions.*]`；`ProduceExamEffect`: `[id, produceDescriptions.*, customizeProduceDescriptions.*]`
  - `ProduceDescriptionLabel`: `[id, produceDescriptions.*]` → `name` + 段；`ProduceDescriptionExamEffect`/`…ProduceEffect`/`…ProduceStep`/`…ProducePlan(Type)`/`…ProduceType`/`…ProduceExamEffectType`: `[type]` → `name`(`swapName`)；`ProduceDescriptionSwap`: `[id, swapType]` → `text`
  - `ProduceDescription`: `[id]` → `name, swapName`（**注意：该表已于 2025-01-20 从 master 删除**，`ext/gakumasu-diff` 里没有 `ProduceDescription.yaml`；译文仓库仍保留 157 行旧数据，可当术语表用但不要依赖）
  - `Localization`: `[id]` → `description`（游戏内 UI 文案，key 形如 `achievement.true_end.receive.initial_status`）
- 覆盖率（2026-09-04 数据，与 master 逐 id 对比）：

  | 表 | 译文行数 | master 行数 | 缺失 id | `name` 非空 |
  |---|---|---|---|---|
  | ProduceCard | 1714（448 卡 × upgradeCount） | 1714 | 0 | 1714/1714 |
  | ProduceItem | 1038 | 1038 | 0 | 1038/1038 |
  | ProduceDrink | 29 | 29 | 0 | 29/29 |
  | SupportCard | 201 | 201 | 0 | 201/201 |
  | IdolCard | 151 | 151 | 0 | 151/151 |
  | Character | 24 | 24 | 0 | 24 |
  | ProduceDescriptionLabel | 226 | 226 | 0 | 223/226 |
  | ProduceExamEffect | 2070 | 2070 | 0 | — |

  描述段里有大量 `text:""`，这不是漏译：`ProduceDescriptionType_Exam` 类段落本来就是占位（数值由 `targetId` 指向的 `ProduceExamEffect`/`Label` 在运行时替换），日文原文同样为空。
- 新鲜度：submodule 指向的 gakumasu-diff 与本会话 `ext/gakumasu-diff` 同一天（2026-09-04），译者 PR 频率约每周（`git log` 最近 8 次全在 2026-08/09）。一般新卡池上线后 1–7 天补齐。
- 样本：`samples/imas-tools_{ProduceCard,ProduceItem,ProduceDrink,SupportCard,IdolCard,Character,ProduceDescription,ProduceDescriptionLabel,ProduceExamEffect}.{zh,ja}.sample.json`（zh = `data/`，ja = `gakumasu-diff/json/`，同一格式便于对照）。

### 1.3 chinosk6/GakumasTranslationData（中文，打包发布版）

- 这是 localify 插件加载的"成品包"，四个 submodule 全在 `imas-tools` 组织下：`GakumasPreTranslation`（剧情预翻译 + `etc/localization.json`）、`gakuen-adapted-translation-data`（人工校对剧情）、`gakumas-generic-strings-translation`（`generic.json`：**以日文原文为 key** 的 UI 零散字串）、`gakumas-master-translation`（上一节）。`merge.py` 把它们合成 `local-files/{localization.json, generic.json, genericTrans/, masterTrans/, resource/}`。
- `local-files/masterTrans/*.json` 与 imas-tools `data/` 逐字节一致（已 `diff -q` 验证），所以**只需要跟踪 imas-tools 一个仓库**。
- 额外资产：`name_dictionary.json`（207 条，日→中人名/称谓表，如 `"おばあちゃん":"老婆婆"`，样本 `samples/chinosk_name_dictionary.head.json`）；`version.txt` = `v2.3.36`。GitHub Release 附件 `GakumasTranslationData.zip`——`huochai67/gakumas-wiki` 的 `config.yaml` 就是这样消费的（`translation.owner: chinosk6, repository: GakumasTranslationData, asset_name: GakumasTranslationData.zip`），可作为"不想 clone 整个仓库"时的下载入口。
- `gakuen-imas-localify` 本体：README 说明数据布局 `localization.json`（按游戏内 key）/ `generic.json`（按原文）/ `genericTrans/`（同 generic，分文件）/ `resource/`（剧情 .txt 替换）；仓库已被 DMCA 禁用。

### 1.4 NatsumeLS/Gakumas-Translation-Data-EN（英文，主推）

- 文档站 https://gakumas.natsume.io ；镜像 `git.natsume.io/Mirror/Gakumas-Translation-Data-EN`；活跃度高（1,491 commits，最新 2026-09-04）。
- `local-files/`：`localization.json`（6,942 条 UI key，如 `achievement.cell.true_end.hif_produce_condition: "Available in \"H.I.F\" produce"`）、`generic.json`（525 条，key 为日文原文）、`genericTrans/{index,lyrics}/`（`index/ProduceSkill.json` 等实质是空壳，仅 `{"": ""}`）、`masterTrans/`（**108 张表，格式与 imas-tools 完全相同**）、`resource/`（349 MB 剧情 txt）。
- masterTrans 覆盖（与 master 行数一致；正则 `[぀-ヿ]` 检假名残留）：ProduceCard 1714 行 / 0 残留；ProduceItem 1038 / 0；ProduceDrink 29 / 0；SupportCard 201 / 0；IdolCard 151 / 0；Character 24 / 0；ProduceSkill 1488 / 0；ProduceExamEffect 2070 / 24 处残留；ProduceDescriptionLabel 226 / 0。比 imas-tools 多出 `Tour.json` 等表，但**缺 `ProduceDescription.json`**（合理，该表已从 master 删除）。
- 英文名样例：`p_card-00-acc-0_002 → "Trouble "`（注意尾随空格，需 `strip()`）、`アピールの基本 → "Appeal Basics"`、`s_card-1-0000 → "Stretch Carefully"`、`初星水 → "Hatsuboshi Water"`。
- 样本：`samples/natsume-en_*.sample.json`、`natsume-en_localization.head.json`、`natsume-en_generic.head.json`。

### 1.5 surisuririsu/gakumas-tools `packages/gakumas-data`（日文名 + 效果 DSL，不含 master id）

- CSV 为源（`csv/skill_cards.csv` 等），`scripts/csv_to_json.py` 生成 `json/`。字段：`id`(自家整数), `name`(日文), `rarity, type, plan, unlockPlv, upgraded, unique, sourceType, pIdolId, forceInitialHand, conditions, cost, actions, limit, effects`——最后几列是作者自定义的块结构效果 DSL（`Effects.md` 有完整语法：`at:startOfTurn { if:goodConditionTurns>=4 { concentration+=4 } limit:1 }`）。
- 与 master 的关系：**人工从 Google Sheet 誊写**，没有 `p_card-*` id；同名不同强化用 `upgraded` 列区分（`アピールの基本` / `アピールの基本+` 各一行）。要 join 只能 `(name, upgraded)` ↔ `(ProduceCard.name, upgradeCount>0)`；同名卡（不同偶像专属 SSR 同名情况少见但存在）需再用 `pIdolId`↔`originIdolCardId` 消歧。
- 站点四语（`i18n/routing.js`: `en, ja, zh-Hans, ko`）但 `messages/*.json` 只是 UI 文案，**卡名不在其中**（网站上英文卡名另有来源，仓库里没找到，`grep "Appeal Basics"` 无命中）。
- 价值：`stages.csv`（153 个 contest 舞台 + 24 event + 3 linkContest，含 `criteria`(Vo/Da/Vi 权重)、`turnCounts`、`firstTurns`、舞台效果）是**唯一结构化的コンテスト舞台参数表**；`p_idols.csv` 的 `recommendedEffect` 也是 master 里没有的社区标注。
- 样本：`samples/gakumas-tools_skill_cards.csv`（全量 870 行）、`samples/gakumas-tools_p_items.head.csv`。

### 1.6 其它

- **`vertesan/hatsuboshi-library`**（hatsuboshi.app 前端，Remix SPA）：数据从私有后端 `/api/{master,csprt,cidol,pcard,memory}` 取（`app/api/index.ts`，需要 `VITE_API_KEY`），仓库内不含卡名翻译；`app/locales/{en,zh-Hans}.ts` 仅 UI。真正有价值的是 `app/types/proto/pmaster.d.ts`（3,927 行）+ `penum.ts`（2,923 行）——**master 全表的 TypeScript 类型 + 全部枚举**（例：`ProduceExamEffectType_ExamLesson`），和 `campus/proto/pmaster.proto` 同源。`app/data/calculation.ts` 有站内的评价值计算。
- **萌娘百科 `学园偶像大师/支援卡`**（mzh.moegirl.org.cn）：搜索结果显示有全支援卡索引页 + 单卡条目，MediaWiki 站（api.php 理论可用），但本会话被屏蔽，未验证结构。

---

## 2. `datasrc/` 里其它克隆的定位

| 目录 | 是什么 | 对本项目的用处 |
|---|---|---|
| `campus` (vertesan, Go) | gakumasu-diff 的**上游 dumper**：`-db` 下载并解密 master DB → `cache/masterYaml`；`-ab` 解混淆 AssetBundle；`-analyze` 从 `dump.cs` 生成 proto。需要 Firebase refresh token（抓包获得）。 | 不需要自己跑。但 `proto/pmaster.proto`（574 个 message，3,928 行）+ `proto/penum.proto`（2,925 行）是**master 表的权威 schema**：字段类型、repeated、枚举全名。例：`message ProduceCard { string id=1; int32 upgradeCount=2; string name=3; ProduceCardRarity rarity=7; ProducePlanType planType=8; int32 stamina=10; ExamCostType costType=12; int32 costValue=13; string playProduceExamTriggerId=17; repeated PlayEffect playEffects=21; … repeated ProduceDescriptionSegment produceDescriptions=33; string originIdolCardId=39; string originSupportCardId=40; repeated string produceCardCustomizeIds=43; … }`（样本 `samples/campus_pmaster_ProduceCard.proto`）。建议用它生成/校验我们的 dataclass。 |
| `types` (hatsuboshi-app/types, TS) | hatsuboshi.app **自家应用模型**（`models/persistent/{PItem,PDrink,PIdol,SupportCard,Skill,Character,AuditionEffect}.ts`，`enums/{Plan,Rarity,SkillCategory,ProduceScenario,…}`），字段是他们清洗后的（`LocaleStringWithRomaji`、`ParsedEffectLine`），`SupportCard.ts` 还是 TODO 空壳。 | **不是** master 表 schema，别当 schema 文档用；可借鉴其"效果解析成 `ParsedEffectElement`"的建模思路。schema 文档请用 `campus/proto/pmaster.proto` 或 `hatsuboshi-library/app/types/proto/pmaster.d.ts`。 |
| `backend` (hatsuboshi-app/backend, Express) | hatsuboshi.app 后端（controllers/v1、services/{auth,repository,cdn}），有 OpenAPI/Redoc（2026-08-25）。 | 无数据；可看其 v1 路由了解他们如何切分 master → 前端 DTO。低价值。 |
| `kaa-game-data` (kotonebot, Python) | 离线数据构建：`gakumasu-diff YAML → game.db(SQLite, zstd) → tasks.json → 精灵图 zip → GitHub Release`，CI 每 6 小时。`schema/loader.py` 从 YAML 推断 schema 生成 `CREATE TABLE` + dataclass。 | 如果我们想要 SQLite 形态的 master，可直接下它的 `data-*` Release（`game.db.zst` + `manifest.json`），或复用 `schema/loader.py` 的 YAML→SQLite 推断逻辑；也是 P 卡/技能卡/饮品图标的现成来源。 |
| `gakumas-wiki` (huochai67, TS) | 中文静态资料站，`pipeline/`：`octo.ts` 直连官方资源网关（`config.yaml` 含 `app_id/version/base_url/client_secret/api_key_seed`）、`sources.ts` 拉 gakumasu-diff zip + chinosk6 Release zip、`translation.ts` 合并、`wiki-data.ts` 生成预索引 JSON。`CORE_TABLES = ['Character','IdolCard','SupportCard','ProduceItem','ProduceCard','ProduceSkill']`。 | **名称映射管线的参考实现**（见 §6）。`translation.ts` 的 `applyTranslation` 可以逐行翻译成 Python。 |
| `gakumasu-diff` | 同 `ext/gakumasu-diff`。commit message 是 master 版本 hash，**每个 commit 的 diff 就是一次数值变更记录**。 | 主数据 + 平衡调整追踪（见 §5）。 |
| `gakumas-core` (kjirou) / `gakumas-data` (Xilorole) / `gakumas-tools` | 分别是 2024-09 停更的 TS 对局引擎、コミュ文字起こし（剧情 OCR，与数值无关）、gakumas-tools monorepo。 | 见 report 01/02。 |
| `hatsuboshi-library` | 见 §1.6。 | proto 类型 + `data/calculation.ts`。 |

---

## 3. 校验源（拿来核对模拟器数值）

站点本身多被代理屏蔽；下表"可读性"一栏基于其 GitHub 源码克隆（`scratchpad/ext/`）判断。

| 站点 | 计算什么 | 源码/数据可读性 | HIF 覆盖 | 备注 |
|---|---|---|---|---|
| **gktools.ris.moe**（surisuririsu/gakumas-tools） | Produce Rank Calculator（初/レジェンド）、N.I.A Calculator、**H.I.F Calculator**、Lesson Calculator、Memory Calculator、Contest Simulator、Rehearsal、Dex、Tier List | 全开源（`datasrc/gakumas-tools`）。公式在 `gakumas-tools/utils/{produceRank,nia,hif,lessons,stamina,contestPower}.js`；对局引擎 `packages/gakumas-engine/engine/{StageEngine,TurnManager,BuffManager,EffectManager,Evaluator}.js`；数据 `packages/gakumas-data/csv`。 | **是**。`utils/hif.js`：`MAX_PARAMS=3200, MAX_PRE_ROUND2_STAR=1110, MAX_ROUND1_SCORE=1,680,000, MAX_ROUND2_SCORE=2,400,000, STAT_MULTIPLIER=2, STAR_MULTIPLIER=7.5, ROUND2_STAR_GAIN_BOOST=1.5, RATING_OFFSET=-2000`；R1/R2/スター性 分段表见下。 | URL 可编码整套编成（`/en/simulator?stage=84&params=1500-2280-900-60&items=…&cards=…&customizations=…`），便于做回归用例。Contest Simulator 是**多次抽样的分布模拟**，不是逐回合复刻，作为分布级校验。 |
| **skypenguin.net** | WordPress 博客：`2024/05/28/gakumasu-sim/` 评价值計算機（"NIAマスター一部対応"）；大量卡表文章（`2025/12/26/post-129674/` レジェンドレア卡一览、`post-129697/` スキルスイッチ新卡、`2025/09/17/post-117846/` 好調卡性能、`2026/01/26/post-133914/` 强化状态消费卡一览…） | 站点被屏蔽，未直接验证。博客 HTML 表格，非 JSON；计算器为页内 JS。 | 部分（文章覆盖 HIF 相关卡；计算器标注 NIA） | 作为"卡效果变更史"的二手记录，不做数值主源。 |
| **noanyan.com/gkmas/calc/**（`/calc/` = NIA 版，`/calc/pro` = 初 プロ版） | 评价值計算機（NIA、初 プロ/マスター；2024-09-23 加 Master 支持） | 屏蔽，未验证；纯 HTML+JS 单页。 | 搜索结果未见 HIF | 低优先级。 |
| **gakumas.moe**（KagamiChan/gakumas.moe, Next.js T3） | 学マス計算機α：初 编评价值（順位点表 `1:1700`、α 分段 `0–5000: 0.3 …`）；有 `nia-notice.tsx` | 开源 `ext/gakumas.moe/src/components/calculator/index.tsx`（`rankingPointsTable`, `pointsTable`）。最后提交 2026-01-05。 | 否 | 与 kantouzin 同公式，可互证。 |
| **kantouzin.github.io/gkmas-rank-calculator**（Svelte） | 初 编（プロ 1500 / マスター 1800 上限）评价值 ↔ 目标分数双向计算 | 开源 `ext/gkmas-rank-calculator/src/{json/ranks.json,scenarios.json, lib/modules/calculator.js}`，用 big.js，**取整明确**：状态项 `floor(2.3×Σmin(p+30,limit))`，分数项分段后 `floor`，目标分 `roundHalfUp`。 | 否（2025-01-04 停更） | 分段 0.3/0.15/0.08/0.04/0.02/0.01，档位 SS+18000/SS16000/S+14500/S13000/A+11500/A10000/B+8000/B6000。 |
| **gakumas-final-score.netlify.app**（kjirou） | 同上（レギュラー1000/プロ1500/マスター1800；順位 1:1700+30 / 2:900+20 / 3:500+10） | 开源 `ext/gakumas-final-score/src/utils.ts`（rate 用百分整数避免浮点）+ `utils.test.ts` 有测试用例可直接借用。 | 否（2024-10 停更） | 最早的一批，公式已被后续站点确认。 |
| **haru-1125.github.io** | `pages/hajime-r-calculator.html` 評価値計算機（初/レジェンド，含 R1 补正 1.2 倍开关、HIF スター性 字段）、`pages/nia-simulator.html` NIA 模拟器（3,246 行 JS）、支援卡/角色所持率 checker | 开源克隆 `datasrc/haru-1125.github.io`：`js/hajime-r-calculator.js`（747 行）、`js/nia-simulator.js`、**`data/supports.js` + `data/supportAbility.js`**（支援卡 → 能力名 → SSR/SR 各档数值，如 `レスボ: ssra 6.5 … ssre 8.5, sra 4.4 … sre 6.4`；`固定値: 48/51/54/57/60`）。 | **是**（`updateHifSparkleFieldVisibility`, `getHifSparkleMax`, `toRound1Corrected` 等） | `data/supports.js` 以日文卡名为 key，是**独立于 master 的支援卡能力数值表**，可用来交叉验证我们从 `SupportCard`/`ProduceSkill` 解析出的数值。样本 `samples/haru-1125_support*.head.js`。 |
| huraru7/gakumas_HIF_Rating_Calculation（github.io） | HIF 评价值：`calcEvalScore = floor(paramTotal×2 + (floor(starGain(R2)×1.5) + min(1110,star))×7.5) + R1Eval + R2Eval − 2000`，档位 S5 35000 / S4+ 30000 / S4 26000 / SSS+ 23000 / SSS 20000 / SS+ 18000 / SS 16000 | 开源 `ext/gakumas_HIF_Rating_Calculation/js/formulas.js`（作者注明"ソースコード準拠"，即抄自 gktools 源码） | **是** | 与 gktools `hif.js` 数值逐项一致，可当第二份印证。 |
| tyuukiti.github.io/gakumasu-calc（`ext/gakumasu-calc`, WPF+React） | 支援卡编成 → 育成理论ステータス（HIF 29 日 / 初レジェンド 18 週 / NIA 26 週；含卡自带 P アイテム、サポートイベント +N%、凸数、上限 HIF 3000+面板） | 开源，`Data/` 目录有支援卡数据（C# 侧），`TestFixtures/` 有测试样例 | **是**（默认打开 HIF 页签） | 校验"育成阶段参数成长"而不是对局分数。 |
| tyuukiti/gakumasu-anomaly-sim | アノマリー最终回合模拟 | 开源 | — | 专项。 |

HIF 分段表（gktools `utils/hif.js` 与 huraru7 一致）：

```
R1 評価点: ≤300k→0; ≤700k→(s−300k)×0.01; ≤1.0M→4000+(s−700k)×0.003; ≤1.2M→4900+(s−1.0M)×0.002; ≤1.4M→5300+(s−1.2M)×0.001; else 5500   (floor)
R2 評価点: ≤600k→0; ≤900k→(s−600k)×0.004; ≤1.5M→1200+(s−900k)×0.008; ≤2.0M→6000+(s−1.5M)×0.002; ≤2.4M→7000+(s−2.0M)×0.001; else 7400 (floor)
R2→スター性: ≤400k→s×0.0001875; ≤600k→75+(s−400k)×0.000225; ≤1.0M→120+(s−600k)×0.000075; else 150  (ceil)
R1 显示分 = raw×1.2（日志里是补正前 raw）
```

### 3.1 含实测数字 / 逐回合日志的 wiki 页面

（seesaawiki / wikiwiki 在本会话被屏蔽，以下 URL 来自搜索结果与 report 02，内容描述以 report 02 已核实部分为准。）

- https://seesaawiki.jp/gakumasu/d/%A5%EC%A5%C3%A5%B9%A5%F3%A1%A6%BB%EE%B8%B3%BE%DC%BA%D9 ——「レッスン・試験詳細」：分数公式 `(基礎+集中)×(好調1.5 / 絶好調 +0.1×好調残ターン)×属性ボーナス%`、取整方向（参数/スコアボーナス 每步 ceil、元気 floor）、01A–TTTB 时机判定表；**评论区有玩家约 60 次实测**（report 02 §Details 已引）。这是最接近"逐回合验证"的公开页面。
- https://seesaawiki.jp/gakumasu/d/%A5%B5%A5%DD%A1%BC%A5%C8%A5%AB%A1%BC%A5%C9%C7%BD%CE%CF%C1%E1%B8%AB%C9%BD ——「サポートカード能力早見表」：R/SR/SSR 各能力档位数值模板（与 haru-1125 `supportAbility.js` 同源，可互证）。
- https://wikiwiki.jp/gakumas/%E5%90%84%E7%A8%AE%E4%BE%BF%E5%88%A9%E3%83%AA%E3%83%B3%E3%82%AF ——「各種便利リンク」：聚合社区 Google Sheets（含「コンテ育成最終試験スコア計算機」moti 版、proton 的 EXP 效率表）与官方 companion wiki 卡表链接。具体 Sheets URL 需人工打开该页抄录（本会话无法访问）。
- https://wikiwiki.jp/gakumas/%E3%82%B5%E3%83%9D%E3%83%BC%E3%83%88%E3%82%AB%E3%83%BC%E3%83%89%E4%B8%80%E8%A6%A7 ——コンテスト Wiki* 支援卡一览。
- https://gameo.jp/gkmas/3275 ——「好調・絶好調・集中の計算式」问答页，含公式与数值例（屏蔽，未验证）。
- 攻略博客（含 HIF 实战数字、非结构化）：morishimemo.com/gakumasu-memo-38 / -39（HIF センス 集中/好調 S4+ 路线）、note.com/nuo195/n/n61045e81865e（HIF 各 plan 用法）、game8.jp/gakuen-idolmaster/784587。

**结论**：真正可机读的"逐回合日志"公开数据集不存在；最可靠的逐回合校验方式是 (a) 用 gktools Contest Simulator 的 URL 编成做分布对拍，(b) 用 `gakumas-tools` 的 `StageLogger.js` 输出逐回合日志与我们的引擎逐行比对（两者都是模拟器，属"模拟器互证"），(c) 人工从上述 wiki 评论区抄若干实测样本进 `tests/`。

---

## 4. 中文社区源

| 源 | 结构化数据 | 抓取可行性 |
|---|---|---|
| **GameKee 学马仕 wiki** https://www.gamekee.com/gakumas/ （学园偶像大师同好会维护） | 图鉴（偶像卡/支援卡/技能卡/P 道具）、「支援卡倍率」(`/gakumas/659774.html`)、「2025.12.26 支援卡上修」(`/687906.html`)、「支援卡推荐」(`/660414.html`)、「环境简报与支援卡榜」(`/688446.html`, `/623706.html`)、「P课题②总览」(`/662914.html`)、新手攻略 (`/624112.html`)。 | 站点被屏蔽未直接验证。GameKee 通用架构是 SPA + 内部 JSON 接口（据我了解 `www.gamekee.com/v1/wiki/entry`、`/v1/content/detail?id=` 一类，需 `game-alias: gakumas` 请求头）——**本会话未能验证接口名**，需在可访问环境用浏览器 DevTools 确认；条目正文是富文本 HTML 表格，需要 per-page 解析。受 GameKee 用户协议约束，只建议用作人工对照（支援卡节奏榜、调整记录），不建议当数据管线上游。 |
| **BWIKI** https://wiki.biligame.com/gakumas/ | 搜索结果显示 `wiki.biligame.com/wiki/学园偶像大师WIKI`（2024-04-07 最后更新）与 `wiki.biligame.com/xms/首页`（2024-05-22 创建）两个入口，活跃度低，内容量远小于 GameKee。 | MediaWiki：`https://wiki.biligame.com/gakumas/api.php?action=query&list=allpages&format=json` / `action=parse&page=…&prop=wikitext` 标准接口理论可用（本会话被屏蔽，未验证 `gakumas` 子路径是否存在）。若有数据，wikitext 模板字段比 GameKee HTML 好解析得多；但预期覆盖差。 |
| **萌娘百科** `学园偶像大师/支援卡` | 全支援卡索引 + 单卡条目（效果/剧情） | MediaWiki（`mzh.moegirl.org.cn/api.php`），但 Cloudflare 防护严格，且被屏蔽未验证。 |
| **NGA / TapTap** | TapTap 论坛「支援卡节奏榜」「支援卡详细评价之 SSR 篇」(by 同好会)；NGA 学园偶像大师版块以攻略帖为主 | 纯帖子，无结构化数据，不抓。 |
| **bilibili 专栏/视频** | 攻略、节奏榜视频 | 无结构化数据，不抓。 |
| **idolmaster.caimogu.cc**（借卡库，report 02 提到） | 支援卡共享 DB | 未验证。 |

结论：中文名称映射**不需要**任何社区站——imas-tools 已按 master id 覆盖 100%；中文社区站的价值只在"支援卡倍率/上修记录"这类人工整理的解读，人读即可。

---

## 5. 官方公告

- 官方站 `gakuen.idolmaster-official.jp` 在本会话被屏蔽，站内 `/news/` 详情页 URL 模式**未能验证**；搜索引擎只能索引到 `/`, `/system/`, `/idol/`, `/media/`, `/road-to-a-plus/` 等静态页，说明其 news 很可能是 JS 动态渲染或根本不存在于官网（学マス 的アップデート/バランス調整公告主要发在**游戏内お知らせ**和 X 账号 @gkmas_official，例：`x.com/gkmas_official/status/1814210287819760091`「ver.1.3.0 アップデートお知らせ … 詳細はゲーム内お知らせをご確認ください」）。
- 可验证的官方聚合入口：**アイドルマスター ポータル** https://idolmaster-official.jp/news/latest/gakuen （学マス 最新ニュース列表），文章 URL 模式 `https://idolmaster-official.jp/news/01_{5位数字}`（例 `01_15280`, `01_17606`, `01_16368`, `01_16662`, `01_19241`），内容多为生配信总结、卡池/活动预告，**不含**具体数值调整表。
- 实用建议：**平衡调整的权威记录就是 `vertesan/gakumasu-diff` 的 commit 历史**——每个 commit = 一次 master 版本，`git log -p -- ProduceCard.yaml ProduceExamEffect.yaml ProduceItem.yaml SupportCard.yaml` 就是逐字段的调整日志（例：report 02 提到 2025-10-31 最终试验分数上限调整、2025-12-26 支援卡上修，都能在对应日期的 commit 中直接看到数值 diff）。官方公告只用来给 diff 加"为什么"的注释。二手记录：GameKee「支援卡上修」页、skypenguin 卡表文章、seesaawiki 更新履歴。

---

## 6. 推荐与管线

### 6.1 按实体的主/次源排序

| 实体 | 数值主源 | 中文名 | 英文名 | 校验/对照 |
|---|---|---|---|---|
| ProduceCard（技能卡） | `gakumasu-diff/ProduceCard.yaml`（schema: `campus/proto/pmaster.proto`） | imas-tools `data/ProduceCard.json`（by `id+upgradeCount`） | NatsumeLS `masterTrans/ProduceCard.json`（同键） | gakumas-tools `skill_cards.csv`（by 日文名+upgraded，效果 DSL 对照）；skypenguin 卡表文章 |
| ProduceItem（P 道具） | `ProduceItem.yaml` | imas-tools `ProduceItem.json`（by `id`） | NatsumeLS 同 | gakumas-tools `p_items.csv`（by 日文名） |
| ProduceDrink | `ProduceDrink.yaml` | imas-tools（by `id`） | NatsumeLS | gakumas-tools `p_drinks.csv` |
| IdolCard（P 偶像） | `IdolCard.yaml` + `IdolCardPotential*`/`IdolCardLevelLimit*` | imas-tools `IdolCard.json`（`name`） | NatsumeLS | gakumas-tools `p_idols.csv`（`recommendedEffect` 社区标注）；haru-1125 `characters.js`（成长率%） |
| SupportCard | `SupportCard.yaml` + `ProduceSkill.yaml`（能力值按 `id+level`） | imas-tools `SupportCard.json` / `ProduceSkill.json` | NatsumeLS 同（ProduceSkill 1488 行全译） | haru-1125 `supports.js`+`supportAbility.js`；seesaawiki 能力早見表；gakumasu-calc `Data/` |
| Character | `Character.yaml` | imas-tools `Character.json`（`lastName/firstName`） | NatsumeLS | gakumas-tools `idols.csv` |
| 描述模板 / 术语 | `ProduceDescriptionLabel.yaml`, `ProduceDescriptionSwap.yaml`, `ProduceDescription{ExamEffect,ProduceEffect,ProduceStep,ProducePlan,…}.yaml`, `ProduceExamEffect.yaml`, `Localization.yaml` | imas-tools 对应 JSON（`ProduceDescription.json` 仅作历史术语表） | NatsumeLS 对应 JSON（无 ProduceDescription） | — |
| 评价值公式（初/レジェンド/NIA/HIF） | gktools `utils/{produceRank,nia,hif}.js`（开源、活跃、含 HIF） | — | — | kantouzin / gakumas-final-score（取整最明确）、huraru7 HIF、gakumas.moe、seesaawiki「最終プロデュース評価」 |
| 对局内公式 | seesaawiki「レッスン・試験詳細」+ report 02 | — | — | gakumas-tools `gakumas-engine`（逐回合 `StageLogger`）、kjirou/gakumas-core（2024-09 停更） |
| コンテスト舞台参数 | gakumas-tools `stages.csv`（唯一结构化源） | — | — | master `PvpRateConfig`/`CompetitionSeason` 表（需自行解析） |
| 平衡调整历史 | `gakumasu-diff` commit diffs | GameKee 上修页（解读） | — | idolmaster-official.jp/news/latest/gakuen、@gkmas_official |

### 6.2 名称映射管线（建议实现于 `tools/build_names.py`）

1. **拉取**（三仓库，均 GitHub，可 `git clone --depth 1` 或下 zip；可选 chinosk6 Release `GakumasTranslationData.zip` 替代第 2 项）：
   - `vertesan/gakumasu-diff`（master 主体；记录 HEAD commit hash 作为数据版本）
   - `imas-tools/gakumas-master-translation` → `data/*.json`（zh-Hans）
   - `NatsumeLS/Gakumas-Translation-Data-EN` → `local-files/masterTrans/*.json`（en）
2. **解析**：YAML 用 C loader（PyYAML 纯 Python 解析 `ProduceExamEffect.yaml` 一类大表要几十秒；`yaml.CSafeLoader` 或 `ruamel` 的 C 实现 / 直接用 kaa-game-data 的 `game.db`）。
3. **按 `rules.primaryKeys` 合并**（移植 `gakumas-wiki/pipeline/translation.ts::applyTranslation`）：
   - 根键：不含 `.` 的主键（`id`、`id+upgradeCount`、`id+level`、`type`、`characterId+number` …）
   - 嵌套键：`produceDescriptions.*` 等 → 对数组按 7 个枚举字段 + `targetId` 建索引后逐段替换 `text`；重复键时降级为不翻译该数组（与参考实现一致）。
   - **不要按数组下标 zip**（已实测错位）。
4. **产出** `data/names/{table}.json`：`{id → {ja, zh, en}}`，对 ProduceCard 用 `f"{id}@{upgradeCount}"` 作 key；`en` 值做 `strip()`（NatsumeLS 有尾随空格）；`zh`/`en` 缺失时回退 `ja` 并在 `missing.json` 里列出。对 `SupportCard` 同时输出 `ProduceSkill` 的 `id@level` 描述译文。
5. **质量门**：
   - 行数 = master 行数、缺失 id = 0（当前三张核心表都满足）
   - 假名残留检查 `[぀-ヿ]`（EN 现存 24 处在 `ProduceExamEffect`，可容忍）
   - 与 gakumas-tools `skill_cards.csv` 按 `(ja name, upgraded)` 做左连接，报告匹配率；不匹配的多半是同名不同源卡或新卡，作为"社区数据是否已跟进"的信号。
6. **版本钉住**：把三仓库的 commit hash 写进产物头部；CI 里以 gakumasu-diff 新 commit 为触发重跑（imas-tools 平均滞后 1–7 天，EN 类似），未译新卡先回退日文名。

### 6.3 校验管线（补充 report 02）

- 评价值：把 `gkmas-rank-calculator/calculator.js`、`gakumas-final-score/utils.test.ts`、`gakumas_HIF_Rating_Calculation/formulas.js`、gktools `utils/hif.js` 的常量各抄一份进 `tests/test_rating.py`，四源互证（初/レジェンド/NIA/HIF 都有独立实现）。
- 对局：用 gktools Contest Simulator 的 URL 参数（`stage`, `params`, `items`, `cards`, `customizations`）定义 fixture，用 `gakumas-engine` 本地跑 N 次得分布，与我们的引擎比中位数/分位数；再从 seesaawiki「レッスン・試験詳細」评论区人工抄少量单回合实测进 `tests/fixtures/`。
- 支援卡：`haru-1125/data/supportAbility.js` 的档位表 vs 我们从 `ProduceSkill` 解析的值，按日文卡名对齐。
