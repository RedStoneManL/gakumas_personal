# 预设编成（loadout presets）与基线测量

> 对应 `docs/OPEN_ITEMS.md` C1 / D2。代码：`gakumas_arena/loadouts.py`，测试：`tests/test_loadouts.py`。
> 所有数字均来自 **本仓库工作树 2026-09-07（HEAD `21933a5` + 未提交的考试引擎改动）** 的 `policy="heuristic"` 跑局，
> 考试内核当时正被另一 agent 审计修改，**同一预设在不同时刻测出的数字差异很大**（见 §4 与 §6），请把这些数当作「当前引擎的量级」而非结论。

## 1. 用法

```python
from gakumas_arena.sim import run_produce
from gakumas_arena.loadouts import list_loadouts, get_loadout, describe_loadout

list_loadouts()                     # ['hif_sense_default', 'hif_logic_default', 'hif_anomaly_default']
run_produce("hif", seed=1, policy="heuristic")                          # scenario="hif" 默认即 hif_sense_default
run_produce("hif", seed=1, policy="heuristic", loadout="hif_logic_default")
run_produce("hif", seed=1, idol="i_card-amao-3-018", loadout="hif_sense_default")  # 显式偶像覆盖预设里的偶像卡
run_produce("first_star", seed=1, policy="heuristic")                   # 初 仍用 DEFAULT_IDOL（R 有村麻央），无预设
describe_loadout("hif_sense_default")                                   # 含日文原名 + 中文译名（data/raw/GakumasTranslationData）
```

- `make_produce_env` / `make_exam_env` / `run_produce` / `run_exam` 的 `loadout` 参数现在接受预设名或 `LoadoutPreset`；`idol` 默认值改为 `AUTO`：
  剧本在 `DEFAULT_PRESET_BY_SCENARIO` 里（目前 produce-007/008 = H.I.F）就用预设的偶像，否则回退 `DEFAULT_IDOL`。
  显式传 `idol=DEFAULT_IDOL`（`gakumas_arena/policies/evaluation.py`、`scripts/eval_*.py` 的做法）行为不变。
- 预设包含一个剧本级覆盖：H.I.F ボーナス 成长面板等级（`HifScenarioConfig.growth_panel_levels`），由 `apply_preset_to_scenario` 写进 `ScenarioSpec`。
- `RolloutResult.loadout` 记录实际使用的预设名。
- 支援卡 id 由 `suggest_support_cards(idol, "hif", level=60)`（gakumas_rl 的 `SupportCardAutoSelector`）生成后固化；主数据更新后可重新生成。

## 2. 预设内容

三套都为：SSR 偶像卡 rank 6（`IdolCard.maxIdolCardLevelLimitRank`）、プロデューサー Lv50、亲爱度 20、6 张 SSR 支援卡 Lv60（`SupportCardLevelLimit` 上限）、H.I.F ボーナス 面板全满（01~04 Lv5，05~09 Lv6）。

### `hif_sense_default`（センス）

- 偶像卡：`i_card-ttmr-3-000` 月村手毬「Luna say maybe」SSR，基础三维 [75, 65, 55]，体力 30，`ProduceExamEffectType_ExamLessonBuff`
- 支援卡（Lv60）：

| id | 名称 | 译名 | 类型 | プラン |
|---|---|---|---|---|
| `s_card-3-0010` | 可愛いと可愛いで可愛い！ | 可爱与可爱叠加就是最可爱！ | Vocal | Common |
| `s_card-3-0001` | 何やってるんだろう、 | 我到底在做什么呢， | Vocal | Common |
| `s_card-3-0098` | 大運動会、開催っ！ | 大运动会，开始！ | Vocal | Common |
| `s_card-3-0030` | あっちも行きたいですわ！ | 我也想要去那里！ | Dance | Plan1 |
| `s_card-3-0070` | おい、来てやったぞ！ | 嘿，我们来了！ | Dance | Plan1 |
| `s_card-3-0093` | 長旅おつかれさま！ | 长途旅行辛苦啦！ | Visual | Plan1 |

### `hif_logic_default`（ロジック）

- 偶像卡：`i_card-kllj-3-000` 葛城リーリヤ「白線」（译名「白线」）SSR，基础三维 [55, 55, 65]，体力 28，`ProduceExamEffectType_ExamReview`
- 支援卡（Lv60）：

| id | 名称 | 译名 | 类型 | プラン |
|---|---|---|---|---|
| `s_card-3-0074` | ちょっと詳しいんです！ | 更加详细一点！ | Visual | Plan2 |
| `s_card-3-0007` | まるで王子様みたいな | 简直像王子一样 | Visual | Common |
| `s_card-3-0035` | ゆっくりと過ごしましょう | 慢慢地度过吧 | Visual | Plan2 |
| `s_card-3-0040` | そろそろ焼けたかな？ | 差不多烤好了吧？ | Dance | Plan2 |
| `s_card-3-0050` | あなたたちのことが好き | 我喜欢你们 | Dance | Plan2 |
| `s_card-3-0010` | 可愛いと可愛いで可愛い！ | 可爱与可爱叠加就是最可爱！ | Vocal | Common |

### `hif_anomaly_default`（アノマリー）

- 偶像卡：`i_card-hmsz-3-016` 秦谷美鈴「VEIL」SSR（2026-04，带 プリマステラ 技能，但引擎不读取），基础三维 [65, 70, 80]，体力 27，`ProduceExamEffectType_ExamConcentration`
- 支援卡（Lv60）：

| id | 名称 | 译名 | 类型 | プラン |
|---|---|---|---|---|
| `s_card-3-0054` | 相手にとって不足なしよ！ | 真是个够格的对手！ | Visual | Plan3 |
| `s_card-3-0007` | まるで王子様みたいな | 简直像王子一样 | Visual | Common |
| `s_card-3-0051` | 新生活のはじまりだね | 新生活开始了呢 | Visual | Plan3 |
| `s_card-3-0043` | 待ちなさーい！ | 请等一下！ | Dance | Plan3 |
| `s_card-3-0062` | よくやったな、倉本。 | 好样的，仓本 | Dance | Plan3 |
| `s_card-3-0108` | 風紀が乱れるぞ！ | 这样会败坏风纪的！ | Vocal | Plan3 |

### 引擎无法表达、因此预设里没有的账号要素

| 要素 | 现状 |
|---|---|
| 偶像 ポテンシャル | `IdolCard.idolCardPotentialId` / `idolCardPotentialProduceSkillId`（`IdolCardPotential` 604 行、`IdolCardPotentialProduceSkill` 250 行）未被 `gakumas_rl/idol_config.py` 读取 |
| プリマステラ 技能 | `idolCardPrimaStellaProduceSkillId` 未被读取（所以「HIF 时代带 prima-stella 的卡」在引擎里与旧卡无区别） |
| 培育メモリー | `IdolLoadout` 没有メモリー字段；引擎只有 選抜試験メモリー → 本戦 的交接（`HifSelectionMemory`） |
| 挑战 P 道具 | 模型支持 `challenge_item_ids`，预设未启用 |

## 3. 为得到这套预设顺手修的两个引擎问题

1. **planning 启发式从不上课**（`gakumas_rl/interfaces/service.py::_choose_planning_action`）：原打分只看 `success_probability + P点×0.05 + 效果数`，
   「差入」P 点 +10 → +0.5，课程三维收益不计分，于是整局 11 周全选差入（初 里是全选活動支給），選抜2 必挂。
   加了 `Σstat_deltas × 0.01 + star_delta × 0.02` 两项（每 100 点三维 ≈ +1.0），课程稳定优先，体力不够时自然回落到休息/差入。
   `tests/test_loadouts.py::test_planning_heuristic_takes_lessons_on_hif` 回归。
2. **SSR 支援卡被钳到 40 级**：主数据稀有度枚举实际是 `SupportCardRarity_Ssr`（混合大小写），`idol_config.py` / `support_card_selector.py` 的表用 `_SSR` 做键，
   查不到就回退 R 卡的 40。加了 `normalize_support_card_rarity`，SSR=60 / SR=50 / R=40（与 `SupportCardLevelLimit` 一致）。
   `tests/test_loadouts.py::test_support_card_rarity_is_normalised_to_master_level_limit` 回归。

## 4. 测量：`run_produce(scenario, policy="heuristic")`，seed 1~20

`hif` = produce-007（選抜試験 1/2/3；border 由 `npc_hif_border` 给出，本次 ≈ 6.0k / 49.8k / 136k，按偶像的 audition difficulty 略有不同）。

### 4.1 H.I.F（各 20 seeds）

| 预设 | 選抜1 通过 | 選抜1 分数 median（min–max） | 選抜2 通过 | 選抜2 median | 選抜3 通过 | 選抜 全通 | rating mean / median / min / max |
|---|---|---|---|---|---|---|---|
| `hif_sense_default` | **20/20** | 41,590（9,890 – 72,471,038 ⚠） | **8/20** | 41,039 | 1/8 | 1/20 | 9,654 / 8,392 / 7,626 / 13,987 |
| `hif_logic_default` | 17/20 | 13,972（3,423 – 385,737） | **9/17** | 49,703 | 4/9 | **4/20** | 9,335 / 7,762 / 5,375 / 14,844 |
| `hif_anomaly_default` | 19/20 | 15,962（5,736 – 42,825） | 3/19 | 18,945 | 0/3 | 0/20 | 8,386 / 7,980 / 5,545 / 12,330 |
| 参照：`DEFAULT_IDOL`（R 有村麻央，自动支援卡 Lv60，无面板） | 12/20 | 7,857（mean） | 1/12 | — | 0/1 | 0/20 | 6,095 / 6,478 / 4,168 / 11,451 |
| 参照：修启发式前（整局差入，旧考试代码） | 20/20 | ≈12k | 0/20 | ≈17k | — | 0/20 | ≈6.5k |

- 三套预设的 rating 分布都是双峰：挂在 選抜2 的局 ≈ 7.5k–8.4k（B/B+），通过 選抜2 的局 ≈ 11k–15k（A+/S+）。
- seed=1：sense 選抜1 21,620 通过 → 選抜2 43,029 未过；logic 全通（69,696 / 182,391 / 385,654，S+ 14,844）；anomaly 選抜1 通过 → 選抜2 14,184 未过。
  这是历史观测。2026-09-08 已修复“显式空饮料栏生成随机默认饮料”；固定 seed 的旧通过保证不再成立。
  `tests/test_loadouts.py` 现断言运行结束、预设身份与选拔顺序、仅在通过后推进；另有确定性重放和空物品回归测试。
- 平均 スター性 選抜 结束时 ≈ 180–270（社区目标 ≥ 700）；三维均值 sense [2433, 1238, 1230]、logic [1277, 1269, 2121]、anomaly [2028, 1236, 1253]
  —— 启发式只堆最大收益的一维（SP 课），与社区「授業选最低属性」相反，尚未处理。

**選抜2 通过率 ≤ 45%，未达到 80% 的目标。** 原因不在编成，见 §6。

### 4.2 初（first_star, produce-001；同一预设，成长面板不生效）

| 预设 | 最终试验通过 | 最终分数 median（min–max） | ending | rating mean / median / min / max |
|---|---|---|---|---|
| `hif_sense_default` | 20/20 | 14,672（2,840 – 11,765,959 ⚠） | first_star_a ×20 | 20,418 / 10,164 / 8,393 / 128,676 |
| `hif_logic_default` | 20/20 | 43,315（5,063 – 426,193） | first_star_a ×20 | 11,471 / 11,387 / 9,416 / 15,192 |
| `hif_anomaly_default` | 20/20 | 13,880（4,083 – 39,978） | first_star_a ×20 | 10,358 / 10,332 / 8,865 / 11,551 |
| 参照：`DEFAULT_IDOL` | 20/20 | 12,197（mean） | first_star_a ×17, _b ×3 | 9,543 / 9,687 / 7,332 / 11,739 |

初 的中期试验（900 分固定线）100% 通过，预设主要抬高 rating 下限。

## 5. 偶像卡筛选（113 张 SSR 全量，每张 20 seeds，预设同规格：rank6 + selector 支援卡 Lv60 + 面板全满）

跑在 **比 §4 更早的考试代码** 上（另一 agent 期间改了 `simulation/exam/runtime.py`），所以与 §4 的数字不一致；只用于挑卡。每プラン前 6 名（Mid1/Mid2 = 通过局数，med = 分数中位数）：

| プラン | 偶像卡 | examEffectType | 選抜1 | 選抜2 | 全通 | rating mean |
|---|---|---|---|---|---|---|
| センス | `i_card-kcna-3-005` ようこそ初星温泉 | LessonBuff | 20 (med 86,870 ⚠) | 17 | 1 | 10,917 |
| センス | **`i_card-ttmr-3-000` Luna say maybe** | LessonBuff | 20 (med 32,620) | 7 | 1 | 9,460 |
| センス | `i_card-hmsz-3-020`「ねえ、言っちゃうよ。」 | LessonBuff | 16 | 3 | 0 | 7,937 |
| センス | `i_card-hume-3-016` ENDLESS DANCE | LessonBuff | 16 | 3 | 0 | 7,797 |
| センス | `i_card-ssmk-3-018` 標 | LessonBuff | 13 | 3 | 1 | 7,517 |
| センス | `i_card-amao-3-000` Fluorite | ParameterBuff | 17 | 2 | 0 | 7,857 |
| ロジック | **`i_card-kllj-3-000` 白線** | Review | 17 | 9 | 4 | 9,417 |
| ロジック | `i_card-atbm-3-000` 理論武装して | CardPlayAggressive | 17 | 3 | 1 | 8,388 |
| ロジック | `i_card-ttmr-3-001` アイヴイ | Review | 20 | 1 | 1 | 8,330 |
| ロジック | `i_card-ttmr-3-002` 仮装狂騒曲 | CardPlayAggressive | 18 | 2 | 1 | 8,169 |
| ロジック | `i_card-fktn-3-000` 世界一可愛い私 | Review | 20 | 2 | 0 | 8,185 |
| ロジック | `i_card-jsna-3-006` Our Chant | Review | 19 | 2 | 0 | 8,028 |
| アノマリー | `i_card-shro-3-012` サンフェーデッド | Concentration | 18 (med 276,770 ⚠) | 15 | 4 | 10,837 |
| アノマリー | `i_card-ssmk-3-002` カクシタワタシ | FullPower | 19 | 3 | 1 | 8,281 |
| アノマリー | `i_card-hski-3-015` がむしゃらに行こう！ | Concentration | 18 | 4 | 0 | 8,618 |
| アノマリー | **`i_card-hmsz-3-016` VEIL** | Concentration | 19 | 3 | 0 | 8,395 |
| アノマリー | `i_card-kcna-3-012` Howling over the World | Concentration | 17 | 3 | 0 | 7,914 |
| アノマリー | `i_card-hski-3-011` 桜フォトグラフ | FullPower | 15 | 2 | 1 | 7,836 |

- ⚠ `i_card-kcna-3-005`（固有卡 `p_card-01-ido-3_097` こくりとひとくち）与 `i_card-shro-3-012`（固有卡 `p_card-03-ido-3_135` 日が差す方へ）
  的 選抜1 分数中位数 8.7 万 / 27.7 万，单局最高 5,435 万 —— 是考试内核的分数爆炸而非真实强度，**故意不选为默认**（已记入 OPEN_ITEMS A8）。
  `ttmr-3-000` 在 §4 的最终测量里也出现了 7,247 万的单局（20 局里 1 局），同类型 `ExamLessonBuff` 卡整体偏高，选它是因为除爆炸局外它的 選抜1 中位数（3–4 万）和 選抜2 通过数最好；
  如果考试审计修掉爆炸后它的优势可能消失，届时用 `suggest_support_cards` + 本节脚本重新筛一遍即可（脚本在会话 scratchpad，逻辑就是对每张 SSR 跑 `run_produce(loadout=LoadoutPreset(...))` 20 seeds）。
- 「HIF 时代 / プリマステラ」的新卡（2025-09 以后，如 `amao-3-015`、`hski-3-017`、`kllj-3-015`）在引擎里没有优势（技能不被读取），实测普遍在中下游。
- 不同 examEffectType 的差距远大于同类型内卡与卡的差距：LessonBuff / Review / Concentration 明显优于 ParameterBuff / CardPlayAggressive / FullPower，
  这更像是考试内核对各流派实现完整度的差异，不是卡本身。

## 6. 为什么 選抜2 还是过不了 80%（根因，均超出「编成」范围）

1. **课程不给技能卡**：引擎里 初 与 H.I.F 的课程结束都没有卡片奖励（`docs/rules/produce_loop.md` §91 写明「课程结束附带获得 1 张技能卡（3 选 1）」，
   `ProduceStepOpenLesson` 行也只有 `mainParameter/subParameter/star/stamina`），卡组整局停在 13–15 张（選抜1 通过后的剧情事件还删 2 张基础卡）。
   真实游戏里 選抜1 → 選抜2 的分数 ×8（15k → 150k 目安）主要靠卡组成长 + 相談，引擎里只能靠三维倍率与 スター性，所以 選抜2 的 49.8k border 大多数局够不到。
   → OPEN_ITEMS B6。
2. **相談（商店）未暴露**（B2），P 点只能靠差入攒着没处花。
3. **分数方差极大**：同一预设 選抜1 分数从 3k 到 7,000 万，考试内核有可无限叠加的效果（A8），启发式出牌也只是 1-ply。
4. 启发式培育只堆单一维度、不看 スター性 目标（≥700）、不会为了卡组去差入/活動支給。改进方向：让 `_choose_planning_action` 看考试权重与最低属性、卡组大小；或直接上 `gakumas_arena/policies` 的搜索。

以上 1–3 修好后请重跑 §4（`python -m pytest tests/test_loadouts.py` + 20 seeds 测量），并考虑重新筛卡（§5）。

## 7. 偶像卡完整套件：才能開花 / ポテンシャル / プリマステラ / メモリー（OPEN_ITEMS B7）

> 代码：`gakumas_rl/idol_config.py`（解析）、`gakumas_rl/loadout.py`（数据结构）、`gakumas_arena/loadouts.py`（预设选项）；
> 测试：`tests/gakumas_rl/test_idol_kit.py`。全部数据驱动：主数据行 → `ProduceSkill` → `ProduceEffect` id，
> 交给培育运行时已有的 `_register_produce_skill` / `_apply_effect_rows` 路径，本节没有硬编码任何效果数值。

### 7.1 loadout 选项

| 选项（`LoadoutConfig` / `LoadoutPreset` / `run_produce(loadout=dict(...))`） | 含义 | 默认 |
|---|---|---|
| `idol_rank` | 才能開花 段数（原有） | `LoadoutConfig` 0；预设 6 |
| `potential_level` | ポテンシャル 段数 0~4（`IdolCardPotential`） | `LoadoutConfig` `None`=0（未解放）；预设 `None`=**主数据上限**（4） |
| `prima_stella_level` | プリマステラ 解放 0/1（`IdolCardPrimaStellaProduceSkill`） | `LoadoutConfig` `None`=0；预设 `None`=**主数据上限**（一番星卡 1，其余 0） |
| `memories` | 带入培育的メモリー：`MemoryGift` id 字符串或 `gakumas_rl.loadout.ProduceMemorySpec` 的元组 | `()` |

`LoadoutPreset.resolved_potential_level(idol)` / `resolved_prima_stella_level(idol)` 给出实际值；`run_produce("hif", idol="i_card-hmsz-3-016", loadout="hif_sense_default")`
这类显式偶像覆盖会按覆盖后的偶像查上限。解析结果记录在 `IdolLoadout.potential_level / prima_stella_level / memories` 与 `metadata`，
每条 `ProduceSkillEffect` 新增 `source`（`level_limit` / `potential` / `prima_stella` / `memory` / `support_card`）便于追溯；`describe_loadout()` 的 `idol_kit_skills` 列出前四类。

### 7.2 主数据 → 效果的映射

| 来源 | 主数据 | 解析成 | 备注 |
|---|---|---|---|
| 才能開花 三维/体力 | `IdolCardLevelLimitStatusUp`（rank ≤ `idol_rank`） | `stat_profile.vocal/dance/visual/stamina` | 原有，已验证 |
| 才能開花 技能 | `IdolCardLevelLimitProduceSkill` → `ProduceSkill p_idol_skill-*` | `produce_skills[source=level_limit]` | **修正**：同一技能 rank2 给 Lv1、rank6 给 Lv2（SP 発生率 +5% → +10%），`ProduceSkill` 每级是总量，旧代码两级都注册会叠成 +15%；现在每个技能只注册已解锁的最高一级 |
| ポテンシャル 1 段 / 4 段 | `IdolCardPotential[effectTypes=ProduceSkill]` + `IdolCardPotentialProduceSkill` | `produce_skills[source=potential]` | 例 `hmsz-3-016`：1 段 獲得スキルカード再抽選+1（Lv1）→ 4 段 +2（Lv2，同样只保留最高级）；`ttmr-3-000`：1 段「基本」卡 2 张强化开局、4 段 再抽選+1 |
| ポテンシャル 2 段 | `IdolCardPotentialEffectType_InitialProduceItemChange` | `use_after_item`（+ 版固有 P 道具） | 仅当 `use_after_item=None` **且显式给了** `potential_level` 时按此决定；没给 `potential_level` 沿用旧规则 `idol_rank >= 4`（保持既有测试/训练行为） |
| ポテンシャル 3 段 | `produceVocal/Dance/VisualGrowthRatePermil` | `stat_profile.*_growth_rate += permil/1000` | 例 `hmsz-3-016` vo +40‰ / vi +20‰ |
| ポテンシャル 4 段 | `IdolCardPotentialEffectType_ProduceStamina.effectValue` | `stat_profile.stamina += 3` | 全库 151 张都是 +3 |
| プリマステラ | `IdolCardPrimaStellaProduceSkill` → `ProduceSkill p_primastella_skill-*`（`produceType=HIF`, `produceSplitType=Final`） | `produce_skills[source=prima_stella]` | 效果 `ProduceEffectType_ProduceReward` → 培育开始获得专属「一番星」Legend 卡；**只在 produce-008（本戦）注册**，選抜 / 初 / NIA 按 `produceType/produceSplitType` 过滤掉（hif.md §9） |
| メモリー アビリティ | `MemoryAbility.skillId` → `ProduceSkill p_memory_skill-*` | `produce_skills[source=memory]` | `MemoryAbility.produceGroupIds` 非空时只对该 `ProduceGroup` 生效（H.I.F 専用アビリティ = produce_group-003）；`isUniqueActivation` 的同名アビリティ跨メモリー只注册一次 |
| メモリー 技能卡 | `MemoryGift.produceCard`（id / upgradeCount / customizes）+ `produceCardPhaseType` | `build_initial_exam_deck` 把 **ProduceStart** 阶段的卡放进初始卡组（与固定底牌同级，先于随机补牌） | `EndAuditionMid` 阶段的卡需要运行时钩子（§7.5）；`customizes` 已转为 growEffectIds 并保留原 ID |
| メモリー 三维/体力/コンテスト卡与道具 | `MemoryGift.vocal/dance/visual/stamina/examBattleProduceCards/examBattleProduceItemIds` | `ProduceMemorySpec` 字段，只记录 | 这些是メモリー对战（コンテスト）用数值，培育里不生效 |

`ProduceSkill.produceType / produceSplitType` 的过滤对四类偶像/メモリー技能统一生效（`_produce_skill_applies_to_scenario`）；支援卡技能全库都是 Unknown，未改动其加载逻辑。

### 7.3 メモリー配置

```python
from gakumas_rl.loadout import ProduceMemorySpec, ProduceMemoryCardSpec
from gakumas_rl.idol_config import memory_spec_from_gift
from gakumas_arena.sim import run_produce

# 配布メモリー（生成角色保留为来源；流派和显式使用限制仍须合法）
run_produce("first_star", idol="i_card-hski-1-000", loadout=dict(idol_rank=4, memories=("memory_gift-20260516-hif-plan1-1",)))

# 自定义メモリー：MemoryAbility + 合法流派卡；idol_card_id 保留生成来源
custom = ProduceMemorySpec(
    memory_id="my_sss",
    produce_card=ProduceMemoryCardSpec(card_id="p_card-01-act-2_001", upgrade_count=1),
    ability_ids=("ability-p_cd-memory-vocal-450-001-p_memory_skill-common-p_trigger-produce_start-initial-vocal_addition-02-001",),
)
run_produce("hif", loadout=dict(memories=(custom,)))
```

校验：未知来源/能力/卡变体 → `KeyError`；显式 `allowed_character_ids`、卡流派或自定义不合法 → `ValueError`。
`idol_card_id` 是生成来源，不能据此要求使用者同角色；本轮实机 HIF 为 4 槽，旧“2 枠”说明不适用。主数据未给通用槽数上限，未硬编码。

### 7.4 三套预设的实际变化

`hif_sense/logic/anomaly_default` 现在都是 rank6 + ポテンシャル 4（成长率 + 体力 +3 + 两条 `p_idol_skill` + 初期Pアイテム変更 → 用 + 版固有道具）；
`hif_anomaly_default`（`hmsz-3-016`）在 `run_produce("produce-008")`（本戦）时额外获得「星々を見下ろす一番星」`p_card-03-ido-100_047`。
预设不带メモリー（配布行没有这三张卡的角色）。§4 的测量数字是在这之前跑的，未重测。

### 7.5 运行时钩子（2026-09-07 接手更新）

以下前两项已实现：延迟发卡在确认考试结果后执行且只发一次，自定义同步应用；memory_skill 来源连锁保护已启用。HIF 具体中期边界仍待实机确认，使用 `HifScenarioConfig.memory_card_mid_stage_type` 配置。旧钩子需求说明保留如下。

1. `ProduceMemoryProduceCardPhaseType_EndAuditionMid` 的メモリー卡：应在中期試験结束后加入卡组。`idol_config._load_memory_deck_rows(repository, loadout, phase_type=...)`
   已能给出这些卡行；运行时在 `AuditionMid` 结算处调用并 `_append_card` 即可。
2. `_register_produce_skill` 用 `'p_support_skill-' in skill_id` 判定 `source='support_skill'`，メモリーアビリティ（`p_memory_skill-*`）现在落到 `idol_skill`，
   于是 `_is_support_or_memory_ability_source` 的连锁保护（`{'support_skill','memory_skill'}`）对它不生效。建议改成读 `ProduceSkillEffect.source`
   （`'memory'` → `'memory_skill'`，`'support_card'` → `'support_skill'`）。
3. 选抜試験メモリー → 本戦 的交接（`HifSelectionMemory`）与本节的「编成メモリー」是两回事，未合并。

### 7.6 实况编成入口

`gakumas_arena.live.to_loadout_config(RunLoadout)` 拒绝未读字段并保留逐槽 `support_card_levels`、回忆来源/时机/自定义。统一 `support_card_level` 仍可用于训练预设；逐槽等级长度或范围错误会报错。

当前重测结果以 [ARENA_ENGINE_UPDATE.md](ARENA_ENGINE_UPDATE.md) 为准，早期高通过率仍无效。
