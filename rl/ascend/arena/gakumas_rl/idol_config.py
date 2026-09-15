"""偶像卡与 P 道具配置解析，负责生成训练时统一使用的 loadout。"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
import math
import re
from typing import Any

import numpy as np

from .deck_constraints import (
    UNSCOPED_FORCE_CARD_GROUP,
    normalize_forced_card_groups,
    normalize_guaranteed_effect_counts,
)
from .loadout import (
    DEFAULT_DEARNESS_LEVEL,
    DeckArchetype,
    ExamStatusEnchantSpec,
    IdolLoadout,
    IdolStatProfile,
    ProduceCardConversionSpec,
    ProduceMemoryCardSpec,
    ProduceMemorySpec,
    ProduceSkillEffect,
    SupportCardSelection,
)
from .support_card_selector import SupportCardAutoSelectConfig, auto_select_support_cards, normalize_support_card_rarity
from .repository.master_data import MasterDataRepository, ScenarioSpec


_ALLOWED_COMMON_PLAN_TYPES = {
    'ProducePlanType_Common',
    'ProducePlanType_Plan1',
    'ProducePlanType_Plan2',
    'ProducePlanType_Plan3',
}

_RARITY_BIAS_MAP = {
    'IdolCardRarity_N': 1.00,
    'IdolCardRarity_R': 0.96,
    'IdolCardRarity_Sr': 0.88,
    'IdolCardRarity_SSR': 0.78,
    'IdolCardRarity_Ssr': 0.78,
    'IdolCardRarity_Legend': 0.70,
}

_SUPPORT_CARD_RARITY_TO_DEFAULT_LEVEL = {
    'SupportCardRarity_R': 40,
    'SupportCardRarity_SR': 50,
    'SupportCardRarity_SSR': 60,
}


def _rank_value(raw_rank: str | None) -> int:
    """把 rank 字段末尾的数字解析成可比较的整数。"""

    if not raw_rank:
        return 0
    match = re.search(r'(\d+)$', str(raw_rank))
    return int(match.group(1)) if match else 0


def _canonical_card_row(repository: MasterDataRepository, card_id: str) -> dict[str, Any] | None:
    """返回卡片的基础版本，避免把强化版当作卡池基准。"""

    return repository.canonical_card_row(card_id)


def _card_row_by_upgrade(repository: MasterDataRepository, card_id: str, upgrade_count: int) -> dict[str, Any] | None:
    """按卡 id 和强化次数解析具体卡面。"""

    return repository.card_row_by_upgrade(card_id, upgrade_count)


def _load_exam_initial_deck_rows(repository: MasterDataRepository, deck_id: str) -> list[dict[str, Any]]:
    """读取指定初始牌组里的基础卡面，保留主数据中的重复张数。"""

    if not deck_id:
        return []
    exam_initial_deck = repository.exam_initial_decks.first(deck_id)
    if exam_initial_deck is None:
        return []
    card_rows: list[dict[str, Any]] = []
    for card_id in exam_initial_deck.get('produceCardIds', []):
        card_row = _canonical_card_row(repository, str(card_id))
        if card_row is not None:
            card_rows.append(card_row)
    return card_rows


def _producer_level_condition_matches(repository: MasterDataRepository, condition_set_id: str, producer_level: int) -> bool:
    """判断条件组是否被当前制作人等级满足。"""

    if not condition_set_id:
        return True
    rows = repository.load_table('ConditionSet').all(condition_set_id)
    if not rows:
        return False

    results: list[bool] = []
    operators = {str(row.get('conditionOperatorType') or 'ConditionOperatorType_And') for row in rows}
    for row in rows:
        if str(row.get('conditionType') or '') != 'ConditionType_ProducerLevel':
            results.append(False)
            continue
        min_max_type = str(row.get('minMaxType') or 'ConditionMinMaxType_Min')
        minimum = int(row.get('min') or 0)
        maximum = int(row.get('max') or 0)
        if min_max_type == 'ConditionMinMaxType_Max':
            results.append(producer_level <= maximum)
        elif min_max_type == 'ConditionMinMaxType_MinMax':
            upper = maximum if maximum > 0 else producer_level
            results.append(minimum <= producer_level <= upper)
        else:
            results.append(producer_level >= minimum)

    if operators == {'ConditionOperatorType_Or'}:
        return any(results)
    return all(results)


def list_available_produce_card_conversions(
    repository: MasterDataRepository,
    producer_level: int,
) -> tuple[ProduceCardConversionSpec, ...]:
    """返回当前制作人等级已解锁的技能卡切换配置。"""

    resolved: list[ProduceCardConversionSpec] = []
    for row in repository.load_table('ProduceCardConversion').rows:
        before_card_id = str(row.get('beforeProduceCardId') or '')
        after_card_id = str(row.get('afterProduceCardId') or '')
        if not before_card_id or not after_card_id:
            continue
        condition_set_id = str(row.get('conditionSetId') or '')
        if not _producer_level_condition_matches(repository, condition_set_id, producer_level):
            continue
        resolved.append(
            ProduceCardConversionSpec(
                before_card_id=before_card_id,
                after_card_id=after_card_id,
                condition_set_id=condition_set_id,
                is_not_reward=bool(row.get('isNotReward')),
            )
        )
    return tuple(resolved)


def _resolve_selected_produce_card_conversions(
    repository: MasterDataRepository,
    producer_level: int,
    selected_after_card_ids: tuple[str, ...] = (),
) -> tuple[ProduceCardConversionSpec, ...]:
    """把用户选择的切换项解析为当前 loadout 的生效配置。"""

    requested = tuple(dict.fromkeys(str(value) for value in selected_after_card_ids if str(value or '')))
    if not requested:
        return ()

    available = {spec.after_card_id: spec for spec in list_available_produce_card_conversions(repository, producer_level)}
    known_after_ids = {
        str(row.get('afterProduceCardId') or '')
        for row in repository.load_table('ProduceCardConversion').rows
        if str(row.get('afterProduceCardId') or '')
    }

    resolved: list[ProduceCardConversionSpec] = []
    for after_card_id in requested:
        spec = available.get(after_card_id)
        if spec is not None:
            resolved.append(spec)
            continue
        if after_card_id in known_after_ids:
            raise ValueError(f'Produce card conversion is locked for producer level {producer_level}: {after_card_id}')
        raise KeyError(f'Unknown produce card conversion target: {after_card_id}')
    return tuple(resolved)


def resolve_produce_card_id(loadout: IdolLoadout | None, card_id: str) -> str:
    """按当前技能卡切换配置解析最终应出现的卡 id。"""

    if loadout is None or not card_id:
        return card_id
    conversion_map = {spec.before_card_id: spec.after_card_id for spec in loadout.produce_card_conversions}
    return conversion_map.get(card_id, card_id)


def resolve_produce_card_row(
    repository: MasterDataRepository,
    card_id: str,
    loadout: IdolLoadout | None = None,
    upgrade_count: int = 0,
) -> dict[str, Any] | None:
    """按技能卡切换配置和强化次数解析卡牌行。"""

    resolved_card_id = resolve_produce_card_id(loadout, card_id)
    return _card_row_by_upgrade(repository, resolved_card_id, upgrade_count)


def _apply_loadout_card_conversions(
    repository: MasterDataRepository,
    rows: list[dict[str, Any]],
    loadout: IdolLoadout | None,
) -> list[dict[str, Any]]:
    """把一组卡牌列表按当前技能卡切换配置映射并去重。"""

    if loadout is None or not loadout.produce_card_conversions:
        return [dict(row) for row in rows]

    resolved_rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, int]] = set()
    for row in rows:
        resolved = resolve_produce_card_row(
            repository,
            str(row.get('id') or ''),
            loadout=loadout,
            upgrade_count=int(row.get('upgradeCount') or 0),
        )
        if resolved is None:
            continue
        key = (str(resolved.get('id') or ''), int(resolved.get('upgradeCount') or 0))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        resolved_rows.append(dict(resolved))
    return resolved_rows


def _applicable_plan_types(loadout: IdolLoadout | None) -> set[str]:
    """根据偶像流派决定允许进入随机池的 planType。"""

    if loadout is None:
        return set(_ALLOWED_COMMON_PLAN_TYPES)
    return {'ProducePlanType_Common', loadout.stat_profile.plan_type}


def _select_guide_row(rows: list[dict[str, Any]], producer_level: int) -> dict[str, Any] | None:
    """按制作人等级选择最接近且不超过当前等级的攻略行。"""

    if not rows:
        return None
    rows = sorted(rows, key=lambda row: int(row.get('producerLevel') or 0))
    eligible = [row for row in rows if int(row.get('producerLevel') or 0) <= producer_level]
    return eligible[-1] if eligible else rows[0]


def _load_deck_archetype(repository: MasterDataRepository, idol_card_id: str, producer_level: int) -> DeckArchetype | None:
    """从 ProduceGuide 读取偶像卡对应的推荐卡组与样例卡组。"""

    guide_rows = [row for row in repository.load_table('ProduceGuide').rows if str(row.get('idolCardId') or '') == idol_card_id]
    guide_row = _select_guide_row(guide_rows, producer_level)
    if guide_row is None:
        return None

    category_group_id = str(guide_row.get('produceGuideProduceCardCategoryGroupId') or '')
    sample_group_id = str(guide_row.get('produceGuideProduceCardSampleDeckCategoryGroupId') or '')
    category_group = repository.load_table('ProduceGuideProduceCardCategoryGroup').first(category_group_id) or {}
    sample_group = repository.load_table('ProduceGuideProduceCardSampleDeckCategoryGroup').first(sample_group_id) or {}

    recommended_card_ids: list[str] = []
    for category_id in category_group.get('produceGuideProduceCardCategoryIds', []):
        category = repository.load_table('ProduceGuideProduceCardCategory').first(str(category_id)) or {}
        recommended_card_ids.extend(str(card_id) for card_id in category.get('produceCardIds', []) if card_id)

    sample_card_ids: list[str] = []
    for category_id in sample_group.get('produceGuideProduceCardSampleDeckCategoryIds', []):
        category = repository.load_table('ProduceGuideProduceCardSampleDeckCategory').first(str(category_id)) or {}
        sample_card_ids.extend(str(card_id) for card_id in category.get('produceCardIds', []) if card_id)

    return DeckArchetype(
        group_id=category_group_id,
        sample_group_id=sample_group_id,
        description=str(category_group.get('description') or ''),
        recommended_card_ids=tuple(recommended_card_ids),
        sample_card_ids=tuple(sample_card_ids),
    )


def _find_base_r_idol_card_row(repository: MasterDataRepository, loadout: IdolLoadout) -> dict[str, Any] | None:
    """为当前偶像卡寻找同角色同流派的 R 卡，用于补齐默认底牌包。"""

    idol_rows = [
        row
        for row in repository.load_table('IdolCard').rows
        if str(row.get('characterId') or '') == loadout.stat_profile.character_id
        and str(row.get('planType') or 'ProducePlanType_Common') == loadout.stat_profile.plan_type
        and str(row.get('rarity') or '') == 'IdolCardRarity_R'
    ]
    if not idol_rows:
        return None
    preferred = [
        row
        for row in idol_rows
        if str(row.get('examInitialDeckId') or '') == loadout.stat_profile.initial_exam_deck_id
    ]
    candidates = preferred or idol_rows
    candidates.sort(key=lambda row: str(row.get('id') or ''))
    return candidates[0]


def _load_seed_exam_deck_rows(repository: MasterDataRepository, loadout: IdolLoadout) -> list[dict[str, Any]]:
    """为考试初始牌组加载固定底牌包。"""

    current_contest_rows = _load_exam_initial_deck_rows(repository, f'initial_deck-contest-{loadout.idol_card_id}')
    if current_contest_rows:
        return current_contest_rows

    seed_rows: list[dict[str, Any]] = []
    base_r_row = _find_base_r_idol_card_row(repository, loadout)
    if base_r_row is not None:
        seed_rows.extend(_load_exam_initial_deck_rows(repository, f'initial_deck-contest-{str(base_r_row.get("id") or "")}'))
    seed_rows.extend(_load_exam_initial_deck_rows(repository, loadout.stat_profile.initial_exam_deck_id))
    return seed_rows


_POTENTIAL_EFFECT_PRODUCE_SKILL = 'IdolCardPotentialEffectType_ProduceSkill'
_POTENTIAL_EFFECT_ITEM_CHANGE = 'IdolCardPotentialEffectType_InitialProduceItemChange'
_POTENTIAL_EFFECT_STAMINA = 'IdolCardPotentialEffectType_ProduceStamina'
_POTENTIAL_EFFECT_GROWTH_RATE = 'IdolCardPotentialEffectType_ProduceVoDaViGrowthRatePermil'

_MEMORY_CARD_PHASE_PRODUCE_START = 'ProduceMemoryProduceCardPhaseType_ProduceStart'
_MEMORY_CARD_PHASE_END_AUDITION_MID = 'ProduceMemoryProduceCardPhaseType_EndAuditionMid'

_UNSCOPED_PRODUCE_TYPES = {'', 'ProduceType_Unknown'}
_UNSCOPED_SPLIT_TYPES = {'', 'ProduceSplitType_Unknown'}


def _produce_skill_applies_to_scenario(skill_row: dict[str, Any], scenario: ScenarioSpec | None) -> bool:
    """按 ``ProduceSkill.produceType / produceSplitType`` 判断技能是否对当前剧本生效。

    大多数技能两项都是 Unknown（全剧本通用）；プリマステラ 技能标为 H.I.F + Final（仅本戦），
    H.I.F 専用メモリーアビリティ 标为 H.I.F + Unknown。``scenario=None`` 时不过滤。
    """

    if scenario is None:
        return True
    skill_produce_type = str(skill_row.get('produceType') or '')
    if skill_produce_type not in _UNSCOPED_PRODUCE_TYPES and skill_produce_type != str(scenario.produce_type or ''):
        return False
    skill_split_type = str(skill_row.get('produceSplitType') or '')
    if skill_split_type not in _UNSCOPED_SPLIT_TYPES and skill_split_type != str(scenario.produce_split_type or ''):
        return False
    return True


def _resolve_produce_skill_row(repository: MasterDataRepository, skill_id: str, skill_level: int) -> dict[str, Any] | None:
    """取 ``ProduceSkill`` 指定等级的行；没有该等级时退回第一行。"""

    if not skill_id:
        return None
    produce_skills = repository.load_table('ProduceSkill')
    candidates = [item for item in produce_skills.all(skill_id) if int(item.get('level') or 1) == int(skill_level)]
    return candidates[0] if candidates else produce_skills.first(skill_id)


def _produce_skill_effect_from_row(skill_row: dict[str, Any], skill_id: str, skill_level: int, source: str) -> ProduceSkillEffect:
    """把 ``ProduceSkill`` 行压成 loadout 用的 ``ProduceSkillEffect``（ProduceEffect id 列表 + 首个触发器）。"""

    effect_ids = tuple(
        str(effect_id)
        for effect_id in (
            skill_row.get('produceEffectId1'),
            skill_row.get('produceEffectId2'),
            skill_row.get('produceEffectId3'),
        )
        if effect_id
    )
    return ProduceSkillEffect(
        skill_id=skill_id,
        level=int(skill_level),
        trigger_id=str(skill_row.get('produceTriggerId1') or ''),
        effect_ids=effect_ids,
        source=source,
    )


def _resolve_ranked_skill_rows(
    rows: list[dict[str, Any]],
    unlocked_rank: int,
) -> list[tuple[str, int]]:
    """把「rank → (produceSkillId, produceSkillLevel)」表按已解锁段数收敛成每个技能一条（取最高等级）。

    主数据里同一技能在低段给 Lv1、高段给 Lv2（如 SP レッスン発生率 +5% → +10%），
    ``ProduceSkill`` 每级的数值是总量而非增量，所以只能注册最高一级，否则会叠加生效。
    """

    best_level: dict[str, int] = {}
    order: list[str] = []
    for row in sorted(rows, key=lambda item: (_rank_value(str(item.get('rank') or '')), int(item.get('order') or 0))):
        if _rank_value(str(row.get('rank') or '')) > unlocked_rank:
            continue
        skill_id = str(row.get('produceSkillId') or '')
        if not skill_id:
            continue
        skill_level = int(row.get('produceSkillLevel') or 1)
        if skill_id not in best_level:
            order.append(skill_id)
        best_level[skill_id] = max(best_level.get(skill_id, 0), skill_level)
    return [(skill_id, best_level[skill_id]) for skill_id in order]


def _build_ranked_skill_effects(
    repository: MasterDataRepository,
    scenario: ScenarioSpec | None,
    rows: list[dict[str, Any]],
    unlocked_rank: int,
    source: str,
) -> tuple[ProduceSkillEffect, ...]:
    """通用：rank 表 → 已解锁且对当前剧本生效的 ``ProduceSkillEffect``。"""

    resolved: list[ProduceSkillEffect] = []
    for skill_id, skill_level in _resolve_ranked_skill_rows(rows, unlocked_rank):
        skill_row = _resolve_produce_skill_row(repository, skill_id, skill_level)
        if skill_row is None or not _produce_skill_applies_to_scenario(skill_row, scenario):
            continue
        resolved.append(_produce_skill_effect_from_row(skill_row, skill_id, skill_level, source))
    return tuple(resolved)


def _load_produce_skills(
    repository: MasterDataRepository,
    idol_card_row: dict[str, Any],
    idol_rank: int,
    scenario: ScenarioSpec | None = None,
) -> tuple[ProduceSkillEffect, ...]:
    """解析偶像卡随 才能開花 rank 解锁的培育技能（``IdolCardLevelLimitProduceSkill``）。"""

    level_limit_skill_id = str(idol_card_row.get('idolCardLevelLimitProduceSkillId') or '')
    if not level_limit_skill_id:
        return ()
    rows = repository.load_table('IdolCardLevelLimitProduceSkill').all(level_limit_skill_id)
    return _build_ranked_skill_effects(repository, scenario, rows, idol_rank, source='level_limit')


def max_potential_level(repository: MasterDataRepository, idol_card_id: str) -> int:
    """偶像卡 ポテンシャル 的最高段数（``IdolCardPotential`` 里该卡的最大 rank，当前主数据均为 4）。"""

    idol_card_row = repository.load_table('IdolCard').first(idol_card_id)
    if idol_card_row is None:
        raise KeyError(f'Unknown idol card: {idol_card_id}')
    potential_id = str(idol_card_row.get('idolCardPotentialId') or '')
    if not potential_id:
        return 0
    return max((_rank_value(str(row.get('rank') or '')) for row in repository.load_table('IdolCardPotential').all(potential_id)), default=0)


def max_prima_stella_level(repository: MasterDataRepository, idol_card_id: str) -> int:
    """偶像卡 プリマステラ 的最高解放段（有 ``idolCardPrimaStellaProduceSkillId`` 的 H.I.F 卡为 1，否则 0）。"""

    idol_card_row = repository.load_table('IdolCard').first(idol_card_id)
    if idol_card_row is None:
        raise KeyError(f'Unknown idol card: {idol_card_id}')
    prima_stella_id = str(idol_card_row.get('idolCardPrimaStellaProduceSkillId') or '')
    if not prima_stella_id:
        return 0
    rows = repository.load_table('IdolCardPrimaStellaProduceSkill').all(prima_stella_id)
    return max((int(row.get('produceSkillLevel') or 1) for row in rows), default=0)


def _resolve_potential_level(repository: MasterDataRepository, idol_card_row: dict[str, Any], potential_level: int | None) -> int:
    """把请求的 ポテンシャル 段数裁到 ``[0, 该卡最高段]``；``None`` 视为 0（未解放）。"""

    if potential_level is None:
        return 0
    return max(0, min(int(potential_level), max_potential_level(repository, str(idol_card_row.get('id') or ''))))


def _load_potential_status(
    repository: MasterDataRepository,
    idol_card_row: dict[str, Any],
    potential_level: int,
) -> dict[str, Any]:
    """汇总 ポテンシャル 已解放段的数值效果（``IdolCardPotential``）。

    返回 ``growth_permil``（三维成长率千分比加成）、``stamina``（体力加成）、
    ``item_change``（是否已解放「初期Pアイテム変更」= 使用 + 版固有道具）。
    """

    result: dict[str, Any] = {'growth_permil': (0.0, 0.0, 0.0), 'stamina': 0.0, 'item_change': False}
    potential_id = str(idol_card_row.get('idolCardPotentialId') or '')
    if not potential_id or potential_level <= 0:
        return result
    vocal = dance = visual = 0.0
    stamina = 0.0
    item_change = False
    for row in repository.load_table('IdolCardPotential').all(potential_id):
        if _rank_value(str(row.get('rank') or '')) > potential_level:
            continue
        effect_types = {str(value) for value in row.get('effectTypes', []) or []}
        if _POTENTIAL_EFFECT_GROWTH_RATE in effect_types:
            vocal += float(row.get('produceVocalGrowthRatePermil') or 0)
            dance += float(row.get('produceDanceGrowthRatePermil') or 0)
            visual += float(row.get('produceVisualGrowthRatePermil') or 0)
        if _POTENTIAL_EFFECT_STAMINA in effect_types:
            stamina += float(row.get('effectValue') or 0)
        if _POTENTIAL_EFFECT_ITEM_CHANGE in effect_types:
            item_change = True
    result['growth_permil'] = (vocal, dance, visual)
    result['stamina'] = stamina
    result['item_change'] = item_change
    return result


def _load_potential_skills(
    repository: MasterDataRepository,
    scenario: ScenarioSpec | None,
    idol_card_row: dict[str, Any],
    potential_level: int,
) -> tuple[ProduceSkillEffect, ...]:
    """解析 ポテンシャル 已解放段的培育技能（``IdolCardPotentialProduceSkill`` → ``ProduceSkill``）。"""

    skill_table_id = str(idol_card_row.get('idolCardPotentialProduceSkillId') or '')
    if not skill_table_id or potential_level <= 0:
        return ()
    rows = repository.load_table('IdolCardPotentialProduceSkill').all(skill_table_id)
    return _build_ranked_skill_effects(repository, scenario, rows, potential_level, source='potential')


def _load_prima_stella_skills(
    repository: MasterDataRepository,
    scenario: ScenarioSpec | None,
    idol_card_row: dict[str, Any],
    prima_stella_level: int,
) -> tuple[ProduceSkillEffect, ...]:
    """解析 プリマステラ（一番星）技能（``IdolCardPrimaStellaProduceSkill``）。

    主数据里这些 ``ProduceSkill`` 标为 ``ProduceType_HatsuboshiIdolFestival`` + ``ProduceSplitType_Final``，
    所以只有 H.I.F 本戦（produce-008）剧本会得到它（培育开始时获得专属「一番星」卡）。
    """

    prima_stella_id = str(idol_card_row.get('idolCardPrimaStellaProduceSkillId') or '')
    if not prima_stella_id or prima_stella_level <= 0:
        return ()
    resolved: list[ProduceSkillEffect] = []
    rows = sorted(repository.load_table('IdolCardPrimaStellaProduceSkill').all(prima_stella_id), key=lambda row: int(row.get('order') or 0))
    for row in rows:
        skill_id = str(row.get('produceSkillId') or '')
        skill_level = int(row.get('produceSkillLevel') or 1)
        if not skill_id or skill_level > prima_stella_level:
            continue
        skill_row = _resolve_produce_skill_row(repository, skill_id, skill_level)
        if skill_row is None or not _produce_skill_applies_to_scenario(skill_row, scenario):
            continue
        resolved.append(_produce_skill_effect_from_row(skill_row, skill_id, skill_level, source='prima_stella'))
    return tuple(resolved)


def memory_spec_from_gift(repository: MasterDataRepository, memory_gift_id: str) -> ProduceMemorySpec:
    """把主数据 ``MemoryGift`` 行（配布メモリー）转成 ``ProduceMemorySpec``。"""

    row = repository.load_table('MemoryGift').first(memory_gift_id)
    if row is None:
        raise KeyError(f'Unknown memory gift: {memory_gift_id}')
    card_row = row.get('produceCard') or {}
    produce_card = None
    if str(card_row.get('id') or ''):
        produce_card = ProduceMemoryCardSpec(
            card_id=str(card_row.get('id') or ''),
            upgrade_count=int(card_row.get('upgradeCount') or 0),
            customize_ids=tuple(str(item.get('id') or '') for item in card_row.get('customizes', []) or [] if item.get('id')),
            phase_type=str(row.get('produceCardPhaseType') or _MEMORY_CARD_PHASE_PRODUCE_START),
        )
    abilities = [item for item in row.get('memoryAbilities', []) or [] if str(item.get('id') or '')]
    return ProduceMemorySpec(
        memory_id=str(row.get('id') or memory_gift_id),
        idol_card_id=str(row.get('idolCardId') or ''),
        grade=str(row.get('grade') or ''),
        produce_card=produce_card,
        ability_ids=tuple(str(item.get('id')) for item in abilities),
        ability_levels=tuple(int(item.get('level') or 1) for item in abilities),
        vocal=int(row.get('vocal') or 0),
        dance=int(row.get('dance') or 0),
        visual=int(row.get('visual') or 0),
        stamina=int(row.get('stamina') or 0),
        exam_battle_produce_card_ids=tuple(str(item.get('id') or '') for item in row.get('examBattleProduceCards', []) or [] if item.get('id')),
        exam_battle_produce_item_ids=tuple(str(value) for value in row.get('examBattleProduceItemIds', []) or [] if value),
    )


def _resolve_memories(
    repository: MasterDataRepository,
    idol_card_row: dict[str, Any],
    memories: tuple[ProduceMemorySpec | str, ...] | list[ProduceMemorySpec | str],
) -> tuple[ProduceMemorySpec, ...]:
    """把 ``memories``（``ProduceMemorySpec`` 或 ``MemoryGift`` id）解析成结构化メモリー并校验。

    ``idol_card_id`` 是生成来源，不能据此推导使用者必须同角色。
    实机清夏四槽包含其他角色来源；仅校验来源存在、显式角色限制和携带卡的流派。
    """

    resolved: list[ProduceMemorySpec] = []
    character_id = str(idol_card_row.get('characterId') or '')
    idol_cards = repository.load_table('IdolCard')
    ability_table = repository.load_table('MemoryAbility')
    for entry in memories:
        spec = memory_spec_from_gift(repository, entry) if isinstance(entry, str) else entry
        if not isinstance(spec, ProduceMemorySpec):
            raise TypeError(f'Unsupported memory spec: {type(entry).__name__}')
        if spec.idol_card_id:
            memory_card_row = idol_cards.first(spec.idol_card_id)
            if memory_card_row is None:
                raise KeyError(f'Unknown memory source idol: {spec.idol_card_id}')
        if spec.allowed_character_ids and character_id not in spec.allowed_character_ids:
            raise ValueError(f'Memory {spec.memory_id} is restricted to {spec.allowed_character_ids}')
        for ability_id in spec.ability_ids:
            if ability_table.first(ability_id) is None:
                raise KeyError(f'Unknown memory ability: {ability_id}')
        if spec.produce_card is not None:
            card = spec.produce_card
            row = repository.card_row_by_upgrade(card.card_id, card.upgrade_count, fallback_to_canonical=False)
            if row is None:
                raise KeyError(f'Unknown memory produce card variant: {card.card_id}+{card.upgrade_count}')
            if str(row.get('planType') or '') not in {'ProducePlanType_Common', str(idol_card_row.get('planType') or '')}:
                raise ValueError(f'Memory card plan does not match idol: {card.card_id}')
            if card.phase_type not in {_MEMORY_CARD_PHASE_PRODUCE_START, 'ProduceMemoryProduceCardPhaseType_EndAuditionMid'}:
                raise ValueError(f'Unknown memory acquisition phase: {card.phase_type}')
            apply_card_customizations(repository, row, card.customize_ids)
        resolved.append(spec)
    return tuple(resolved)


def _load_memory_skills(
    repository: MasterDataRepository,
    scenario: ScenarioSpec | None,
    memories: tuple[ProduceMemorySpec, ...],
) -> tuple[ProduceSkillEffect, ...]:
    """把メモリーアビリティ（``MemoryAbility.skillId`` → ``ProduceSkill p_memory_skill-*``）解析成培育技能。

    ``MemoryAbility.produceGroupIds`` 非空时只对列出的 ``ProduceGroup``（如 H.I.F 専用 = produce_group-003）生效；
    ``isUniqueActivation``（重複発動不可）的同名アビリティ跨メモリー只注册一次。
    """

    if not memories:
        return ()
    ability_table = repository.load_table('MemoryAbility')
    resolved: list[ProduceSkillEffect] = []
    seen_unique: set[str] = set()
    for memory in memories:
        levels = tuple(memory.ability_levels) + (1,) * max(len(memory.ability_ids) - len(memory.ability_levels), 0)
        for ability_id, ability_level in zip(memory.ability_ids, levels):
            ability_rows = [row for row in ability_table.all(ability_id) if int(row.get('level') or 1) == int(ability_level)]
            ability_row = ability_rows[0] if ability_rows else ability_table.first(ability_id)
            if ability_row is None:
                continue
            group_ids = {str(value) for value in ability_row.get('produceGroupIds', []) or [] if value}
            if group_ids and scenario is not None and str(scenario.group_id or '') not in group_ids:
                continue
            skill_id = str(ability_row.get('skillId') or '')
            skill_level = int(ability_row.get('level') or ability_level or 1)
            skill_row = _resolve_produce_skill_row(repository, skill_id, skill_level)
            if skill_row is None or not _produce_skill_applies_to_scenario(skill_row, scenario):
                continue
            if ability_row.get('isUniqueActivation'):
                if skill_id in seen_unique:
                    continue
                seen_unique.add(skill_id)
            resolved.append(_produce_skill_effect_from_row(skill_row, skill_id, skill_level, source='memory'))
    return tuple(resolved)


def apply_card_customizations(
    repository: MasterDataRepository,
    card_row: dict[str, Any],
    customize_ids: tuple[str, ...],
) -> dict[str, Any]:
    """按主数据逐级应用自定义，供回忆、实况和咨询共用。"""
    card = dict(card_row)
    applied = list(card.get('customizedProduceCardCustomizeIds') or [])
    grows = list(card.get('growEffectIds') or [])
    allowed = set(card.get('produceCardCustomizeIds') or [])
    for customize_id in customize_ids:
        if customize_id not in allowed:
            raise ValueError(f'Customize {customize_id} does not apply to card {card.get("id")}')
        if len(applied) >= int(card.get('maxCustomizeCount') or 0):
            raise ValueError(f'Customize limit exceeded for card {card.get("id")}')
        count = applied.count(customize_id) + 1
        row = next((row for row in repository.load_table('ProduceCardCustomize').all(customize_id)
                    if int(row.get('customizeCount') or 0) == count), None)
        if row is None:
            raise ValueError(f'Unknown customize level: {customize_id} x {count}')
        # 主数据每级记录的是该自定义的总效果，不是本次增量。
        # 例如精神統一+ 集中 Lv1=+1、Lv2=+3，不能叠成 +4。
        # 只替换该自定义的上一级，保留其他自定义及非自定义成长。
        if count > 1:
            previous = next(previous for previous in repository.load_table('ProduceCardCustomize').all(customize_id)
                            if int(previous.get('customizeCount') or 0) == count - 1)
            for effect_id in previous.get('produceCardGrowEffectIds') or []:
                if effect_id in grows:
                    grows.remove(effect_id)
        for effect_id in row.get('produceCardGrowEffectIds') or []:
            if repository.load_table('ProduceCardGrowEffect').first(effect_id) is None:
                raise KeyError(f'Unknown customize grow effect: {effect_id}')
            grows.append(effect_id)
        applied.append(customize_id)
    card['growEffectIds'] = grows
    card['customizedProduceCardCustomizeIds'] = applied
    return card


def _load_memory_deck_rows(
    repository: MasterDataRepository,
    loadout: IdolLoadout,
    phase_type: str = _MEMORY_CARD_PHASE_PRODUCE_START,
) -> list[dict[str, Any]]:
    """取メモリー在指定阶段入组的技能卡行（按 ``upgradeCount`` 解析具体卡面）。"""

    rows: list[dict[str, Any]] = []
    for memory in loadout.memories:
        card = memory.produce_card
        if card is None or str(card.phase_type or _MEMORY_CARD_PHASE_PRODUCE_START) != phase_type:
            continue
        row = resolve_produce_card_row(repository, card.card_id, loadout=loadout, upgrade_count=int(card.upgrade_count))
        if row is None:
            row = _canonical_card_row(repository, card.card_id)
        if row is not None:
            resolved = apply_card_customizations(repository, row, card.customize_ids)
            resolved['sourceMemoryId'] = memory.memory_id
            resolved['sourceMemoryIdolCardId'] = memory.idol_card_id
            rows.append(resolved)
    return rows


def _load_support_card_produce_skills(
    repository: MasterDataRepository,
    support_cards: tuple,
) -> tuple[ProduceSkillEffect, ...]:
    """每张支援的每个技能只注册当前等级；不同支援的同名技能独立叠加。"""

    if not support_cards:
        return ()
    skill_tables = (
        repository.support_card_skill_level_vocal,
        repository.support_card_skill_level_dance,
        repository.support_card_skill_level_visual,
        repository.support_card_skill_level_assist,
    )
    resolved: list[ProduceSkillEffect] = []
    best_level: dict[tuple[str, str], int] = {}
    level_by_card_id = {
        str(item.support_card_id): int(item.support_card_level)
        for item in support_cards
        if str(item.support_card_id or '')
    }
    for table in skill_tables:
        for row in table.rows:
            support_card_id = str(row.get('supportCardId') or '')
            support_level = level_by_card_id.get(support_card_id)
            if support_level is None or int(row.get('supportCardLevel') or 0) > support_level:
                continue
            skill_id = str(row.get('produceSkillId') or '')
            skill_level = int(row.get('produceSkillLevel') or 1)
            if not skill_id:
                continue
            key = (support_card_id, skill_id)
            best_level[key] = max(best_level.get(key, 0), skill_level)
    # Equipment order is also the deterministic order of independent supports.
    for support in support_cards:
        support_card_id = str(support.support_card_id)
        for (owner_id, skill_id), skill_level in best_level.items():
            if owner_id != support_card_id:
                continue
            skill_row = _resolve_produce_skill_row(repository, skill_id, skill_level)
            if skill_row is not None:
                resolved.append(replace(
                    _produce_skill_effect_from_row(skill_row, skill_id, skill_level, source='support_card'),
                    support_card_id=support_card_id))
    return tuple(resolved)


def _resolve_support_card_level(card_row: dict[str, Any], requested_level: int | None) -> int:
    """把手动指定的支援卡等级裁剪到该稀有度允许的区间。"""

    # 主数据枚举实际为 ``SupportCardRarity_Ssr``（混合大小写），先归一再查表，否则 SSR 会被钳到 40 级。
    rarity = normalize_support_card_rarity(card_row.get('rarity'))
    default_level = _SUPPORT_CARD_RARITY_TO_DEFAULT_LEVEL.get(rarity, 40)
    if requested_level is None:
        return default_level
    return max(1, min(int(requested_level), default_level))


def _resolve_selected_support_cards(
    repository: MasterDataRepository,
    loadout: IdolLoadout,
    selected_support_card_ids: tuple[str, ...],
    support_card_level: int | None = None,
    support_card_levels: tuple[int, ...] = (),
) -> tuple[SupportCardSelection, ...]:
    """把手动指定的支援卡 ID 列表解析成可直接挂到 loadout 的编成。"""

    normalized_support_card_ids = tuple(
        str(raw_support_card_id or '').strip()
        for raw_support_card_id in selected_support_card_ids
        if str(raw_support_card_id or '').strip()
    )
    if support_card_levels and len(support_card_levels) != len(normalized_support_card_ids):
        raise ValueError("support_card_levels must align with support_card_ids")
    if not normalized_support_card_ids:
        return ()
    if len(normalized_support_card_ids) != 6:
        raise ValueError(
            'Manual support card selection must contain exactly 6 cards '
            f'to match the in-game produce support deck, got {len(normalized_support_card_ids)}'
        )

    allowed_plan_types = {'ProducePlanType_Common', str(loadout.stat_profile.plan_type or 'ProducePlanType_Common')}
    resolved: list[SupportCardSelection] = []
    seen_ids: set[str] = set()
    for slot, support_card_id in enumerate(normalized_support_card_ids):
        if support_card_id in seen_ids:
            raise ValueError(f'Duplicate support card in manual selection: {support_card_id}')
        seen_ids.add(support_card_id)
        support_row = repository.support_cards.first(support_card_id)
        if support_row is None:
            raise KeyError(f'Unknown support card: {support_card_id}')
        plan_type = str(support_row.get('planType') or 'ProducePlanType_Common')
        if plan_type not in allowed_plan_types:
            raise ValueError(
                'Support card plan type does not match idol loadout: '
                f'{support_card_id} ({plan_type}) is incompatible with {loadout.stat_profile.plan_type}'
            )
        requested_level = support_card_levels[slot] if support_card_levels else support_card_level
        resolved_level = _resolve_support_card_level(support_row, requested_level)
        if support_card_levels and requested_level != resolved_level:
            raise ValueError(f"Invalid support level: {support_card_id} level {requested_level}")
        resolved.append(
            SupportCardSelection(
                support_card_id=support_card_id,
                support_card_level=resolved_level,
                support_card_type=str(support_row.get('type') or ''),
                score=0.0,
                reasons=('manual',),
            )
        )
    return tuple(resolved)


def _load_exam_status_enchants(repository: MasterDataRepository, item_id: str) -> tuple[ExamStatusEnchantSpec, ...]:
    """读取 P 道具附带的考试开场状态附魔规格。"""

    if not item_id:
        return ()
    item_row = repository.load_table('ProduceItem').first(item_id) or {}
    item_effects = repository.load_table('ProduceItemEffect')
    enchant_specs: list[ExamStatusEnchantSpec] = []
    for item_effect_id in item_row.get('produceItemEffectIds', []):
        effect_row = item_effects.first(str(item_effect_id))
        if not effect_row:
            continue
        if str(effect_row.get('effectType') or '') != 'ProduceItemEffectType_ExamStatusEnchant':
            continue
        enchant_id = str(effect_row.get('produceExamStatusEnchantId') or '')
        if not enchant_id:
            continue
        effect_turn = int(effect_row.get('effectTurn') or 0)
        effect_count = int(effect_row.get('effectCount') or 0)
        enchant_specs.append(
            ExamStatusEnchantSpec(
                enchant_id=enchant_id,
                effect_turn=None if effect_turn < 0 else effect_turn,
                effect_count=None if effect_count <= 0 else effect_count,
                source_identity=item_id,
            )
        )
    return tuple(enchant_specs)


def augment_loadout_with_produce_items(
    repository: MasterDataRepository,
    loadout: IdolLoadout,
    produce_item_ids: tuple[str, ...] | list[str],
    *,
    replace_existing: bool = False,
) -> IdolLoadout:
    """把手动选择的额外 P 道具追加到考试/课程训练用 loadout。"""

    item_table = repository.load_table('ProduceItem')
    resolved_item_ids = tuple(str(item_id) for item_id in produce_item_ids if str(item_id or '').strip())
    for item_id in resolved_item_ids:
        if item_table.first(item_id) is None:
            raise KeyError(f'Unknown produce item: {item_id}')
    specs: list[ExamStatusEnchantSpec] = [] if replace_existing else list(loadout.exam_status_enchant_specs)
    enchant_ids: list[str] = [] if replace_existing else list(loadout.exam_status_enchant_ids)
    seen_keys = {(spec.enchant_id, spec.source_identity) for spec in specs if spec.enchant_id}
    for item_id in resolved_item_ids:
        for spec in _load_exam_status_enchants(repository, item_id):
            key = (spec.enchant_id, spec.source_identity or item_id)
            if not spec.enchant_id or key in seen_keys:
                continue
            seen_keys.add(key)
            specs.append(spec)
            if spec.enchant_id not in enchant_ids:
                enchant_ids.append(spec.enchant_id)
    metadata = dict(loadout.metadata)
    if resolved_item_ids:
        metadata['manual_produce_item_count'] = len(resolved_item_ids)
    return replace(
        loadout,
        exam_status_enchant_ids=tuple(enchant_ids),
        exam_status_enchant_specs=tuple(specs),
        metadata=metadata,
    )


def _status_bonus(repository: MasterDataRepository, idol_card_row: dict[str, Any], idol_rank: int) -> tuple[float, float, float, float]:
    """汇总 rank 提升带来的属性与体力加成。"""

    status_up_id = str(idol_card_row.get('idolCardLevelLimitStatusUpId') or '')
    if not status_up_id:
        return 0.0, 0.0, 0.0, 0.0
    vocal = 0.0
    dance = 0.0
    visual = 0.0
    stamina = 0.0
    for row in repository.load_table('IdolCardLevelLimitStatusUp').all(status_up_id):
        if _rank_value(str(row.get('rank') or '')) > idol_rank:
            continue
        vocal += float(row.get('produceVocal') or 0)
        dance += float(row.get('produceDance') or 0)
        visual += float(row.get('produceVisual') or 0)
        if 'IdolCardLevelLimitEffectType_ProduceStamina' in set(str(value) for value in row.get('effectTypes', [])):
            stamina += float(row.get('effectValue') or 0)
    return vocal, dance, visual, stamina


def _estimate_exam_score_bonus_multiplier(
    repository: MasterDataRepository,
    scenario: ScenarioSpec,
    profile: IdolStatProfile,
    dearness_level: int,
) -> float:
    """根据主数据库中的考试权重、参数基准和亲爱度估算分数倍率。"""

    battle_profile = repository.battle_profile(
        scenario,
        scenario.default_stage,
        audition_difficulty_id=profile.audition_difficulty_id or None,
    )
    weights = np.array(
        [
            float(battle_profile.get('vocal_weight') or scenario.score_weights[0]),
            float(battle_profile.get('dance_weight') or scenario.score_weights[1]),
            float(battle_profile.get('visual_weight') or scenario.score_weights[2]),
        ],
        dtype=np.float32,
    )
    weighted_parameter = float(np.dot(np.array([profile.vocal, profile.dance, profile.visual], dtype=np.float32), weights))
    baseline = float(battle_profile.get('parameter_baseline') or 0.0)
    if baseline <= 0.0:
        raise ValueError(
            'Battle parameter baseline is missing from master database: '
            f'produce_id={scenario.produce_id}, stage_type={scenario.default_stage}, '
            f'audition_difficulty_id={profile.audition_difficulty_id or ""}'
        )
    parameter_ratio = max(weighted_parameter / baseline, 0.25)
    dearness_ratio = 1.0 + min(max(dearness_level, 0), 20) * 0.01
    return max(parameter_ratio * dearness_ratio, 0.25)


def _clamp_parameter_stats(scenario: ScenarioSpec, vocal: float, dance: float, visual: float) -> tuple[float, float, float]:
    """按当前模式的主数据上限裁剪三维属性。"""

    limit = float(scenario.parameter_growth_limit or 0.0)
    values = np.array([vocal, dance, visual], dtype=np.float32)
    if limit > 0:
        values = np.clip(values, 0.0, limit)
    else:
        values = np.clip(values, 0.0, None)
    return float(values[0]), float(values[1]), float(values[2])


def build_idol_loadout(
    repository: MasterDataRepository,
    scenario: ScenarioSpec,
    idol_card_id: str,
    producer_level: int = 35,
    idol_rank: int = 0,
    dearness_level: int = DEFAULT_DEARNESS_LEVEL,
    use_after_item: bool | None = None,
    selected_produce_card_conversion_after_ids: tuple[str, ...] = (),
    exam_score_bonus_multiplier: float | None = None,
    assist_mode: bool = False,
    auto_select_support_cards_for_training: bool = False,
    selected_support_card_ids: tuple[str, ...] = (),
    selected_support_card_level: int | None = None,
    selected_challenge_item_ids: tuple[str, ...] = (),
    potential_level: int | None = None,
    prima_stella_level: int | None = None,
    memories: tuple[ProduceMemorySpec | str, ...] = (),
    selected_support_card_levels: tuple[int, ...] = (),
) -> IdolLoadout:
    """把偶像卡、rank、亲爱度等外部配置整理成统一 loadout。

    - ``idol_rank``：才能開花 段数 → ``IdolCardLevelLimitStatusUp``（三维/体力）+ ``IdolCardLevelLimitProduceSkill``。
    - ``potential_level``：ポテンシャル 段数（``None`` = 0 未解放；超过该卡上限时裁到上限）→ ``IdolCardPotential``
      （成长率千分比 / 体力 / 初期Pアイテム変更）+ ``IdolCardPotentialProduceSkill``。
    - ``prima_stella_level``：プリマステラ（``None`` = 0）→ ``IdolCardPrimaStellaProduceSkill``，仅 H.I.F 本戦 剧本生效。
    - ``memories``：带入培育的メモリー（``ProduceMemorySpec`` 或 ``MemoryGift`` id）→ アビリティ 并入 ``produce_skills``，
      ProduceStart 阶段的卡进入初始卡组（``build_initial_exam_deck``）。
    - ``use_after_item`` 为 ``None`` 时：显式给了 ``potential_level`` 就按主数据（ポテンシャル 2 段「初期Pアイテム変更」）决定
      是否用 + 版固有道具；否则沿用旧规则 ``idol_rank >= 4``。
    """

    idol_card_row = repository.load_table('IdolCard').first(idol_card_id)
    if idol_card_row is None:
        raise KeyError(f'Unknown idol card: {idol_card_id}')

    bonus_vocal, bonus_dance, bonus_visual, bonus_stamina = _status_bonus(repository, idol_card_row, idol_rank)
    resolved_potential_level = _resolve_potential_level(repository, idol_card_row, potential_level)
    potential_status = _load_potential_status(repository, idol_card_row, resolved_potential_level)
    resolved_prima_stella_level = (
        max(0, min(int(prima_stella_level), max_prima_stella_level(repository, idol_card_id)))
        if prima_stella_level is not None
        else 0
    )
    if use_after_item is not None:
        resolved_use_after_item = bool(use_after_item)
    elif potential_level is not None:
        resolved_use_after_item = bool(potential_status['item_change'])
    else:
        resolved_use_after_item = idol_rank >= 4
    item_id = str(idol_card_row.get('afterProduceItemId') if resolved_use_after_item else idol_card_row.get('beforeProduceItemId') or '')
    growth_permil_vocal, growth_permil_dance, growth_permil_visual = potential_status['growth_permil']
    bonus_stamina += float(potential_status['stamina'])
    resolved_memories = _resolve_memories(repository, idol_card_row, tuple(memories))
    base_vocal, base_dance, base_visual = _clamp_parameter_stats(
        scenario,
        float(idol_card_row.get('produceVocal') or 0) + bonus_vocal,
        float(idol_card_row.get('produceDance') or 0) + bonus_dance,
        float(idol_card_row.get('produceVisual') or 0) + bonus_visual,
    )

    profile = IdolStatProfile(
        idol_card_id=idol_card_id,
        character_id=str(idol_card_row.get('characterId') or ''),
        plan_type=str(idol_card_row.get('planType') or 'ProducePlanType_Common'),
        exam_effect_type=str(idol_card_row.get('examEffectType') or ''),
        initial_exam_deck_id=str(idol_card_row.get('examInitialDeckId') or ''),
        audition_difficulty_id=str(idol_card_row.get('produceStepAuditionDifficultyId') or ''),
        unique_produce_card_id=str(idol_card_row.get('produceCardId') or ''),
        vocal=base_vocal,
        dance=base_dance,
        visual=base_visual,
        vocal_growth_rate=(float(idol_card_row.get('produceVocalGrowthRatePermil') or 0) + growth_permil_vocal) / 1000.0,
        dance_growth_rate=(float(idol_card_row.get('produceDanceGrowthRatePermil') or 0) + growth_permil_dance) / 1000.0,
        visual_growth_rate=(float(idol_card_row.get('produceVisualGrowthRatePermil') or 0) + growth_permil_visual) / 1000.0,
        stamina=float(idol_card_row.get('produceStamina') or 0) + bonus_stamina,
    )
    resolved_score_bonus = (
        float(exam_score_bonus_multiplier)
        if exam_score_bonus_multiplier is not None
        else _estimate_exam_score_bonus_multiplier(repository, scenario, profile, dearness_level)
    )
    exam_status_enchant_specs = list(_load_exam_status_enchants(repository, item_id))
    extra_produce_item_ids = tuple(str(value) for value in selected_challenge_item_ids if str(value or '').strip())
    for extra_item_id in extra_produce_item_ids:
        exam_status_enchant_specs.extend(_load_exam_status_enchants(repository, extra_item_id))
    produce_card_conversions = _resolve_selected_produce_card_conversions(
        repository,
        producer_level,
        selected_produce_card_conversion_after_ids,
    )
    idol_kit_skills = (
        *_load_produce_skills(repository, idol_card_row, idol_rank, scenario=scenario),
        *_load_potential_skills(repository, scenario, idol_card_row, resolved_potential_level),
        *_load_prima_stella_skills(repository, scenario, idol_card_row, resolved_prima_stella_level),
        *_load_memory_skills(repository, scenario, resolved_memories),
    )
    provisional_loadout = IdolLoadout(
        idol_card_id=idol_card_id,
        producer_level=producer_level,
        idol_rank=idol_rank,
        dearness_level=dearness_level,
        use_after_item=resolved_use_after_item,
        stat_profile=profile,
        deck_archetype=_load_deck_archetype(repository, idol_card_id, producer_level),
        produce_skills=idol_kit_skills,
        produce_card_conversions=produce_card_conversions,
        produce_item_id=item_id,
        extra_produce_item_ids=extra_produce_item_ids,
        support_cards=(),
        exam_status_enchant_ids=tuple(spec.enchant_id for spec in exam_status_enchant_specs),
        exam_status_enchant_specs=tuple(exam_status_enchant_specs),
        exam_score_bonus_multiplier=resolved_score_bonus,
        assist_mode=bool(assist_mode),
        potential_level=resolved_potential_level,
        prima_stella_level=resolved_prima_stella_level,
        memories=resolved_memories,
        metadata={
            'idol_name': str(idol_card_row.get('name') or idol_card_id),
            'rarity': str(idol_card_row.get('rarity') or ''),
            'exam_effect_type': str(idol_card_row.get('examEffectType') or ''),
            'potential_level': resolved_potential_level,
            'prima_stella_level': resolved_prima_stella_level,
            'memory_count': len(resolved_memories),
            'memory_ids': ','.join(memory.memory_id for memory in resolved_memories),
        },
    )
    manual_support_cards = _resolve_selected_support_cards(
        repository,
        provisional_loadout,
        tuple(str(value) for value in selected_support_card_ids if str(value or '').strip()),
        support_card_level=selected_support_card_level,
        support_card_levels=selected_support_card_levels,
    )
    support_cards = (
        manual_support_cards
        if manual_support_cards
        else auto_select_support_cards(
            repository,
            scenario,
            provisional_loadout,
            config=SupportCardAutoSelectConfig(support_card_level=int(selected_support_card_level or 60)),
        )
        if auto_select_support_cards_for_training
        else ()
    )
    support_card_skills = _load_support_card_produce_skills(repository, support_cards)
    merged_skills = tuple(dict.fromkeys([*provisional_loadout.produce_skills, *support_card_skills]))
    return replace(
        provisional_loadout,
        support_cards=support_cards,
        produce_skills=merged_skills,
        metadata={
            **provisional_loadout.metadata,
            'support_card_count': len(support_cards),
            'support_card_selection_mode': 'manual' if manual_support_cards else ('auto' if support_cards else 'none'),
        },
    )


def build_weighted_card_pool(
    repository: MasterDataRepository,
    scenario: ScenarioSpec,
    focus_effect_type: str | None = None,
    loadout: IdolLoadout | None = None,
) -> list[dict[str, Any]]:
    """按偶像流派和样例卡组构造带权随机候选池。"""

    base_pool = repository.weighted_card_pool(
        scenario,
        focus_effect_type=focus_effect_type,
        plan_type=loadout.stat_profile.plan_type if loadout is not None else None,
    )
    resolved_pool = _apply_loadout_card_conversions(repository, base_pool, loadout=loadout)
    if loadout is None or loadout.deck_archetype is None or not loadout.deck_archetype.sample_card_ids:
        return resolved_pool

    allowed_plan_types = _applicable_plan_types(loadout)
    sample_counts = Counter(resolve_produce_card_id(loadout, card_id) for card_id in loadout.deck_archetype.sample_card_ids)
    recommended_ids = {resolve_produce_card_id(loadout, card_id) for card_id in loadout.deck_archetype.recommended_card_ids}
    weighted: list[tuple[float, dict[str, Any]]] = []
    for index, card_row in enumerate(resolved_pool):
        card_id = str(card_row.get('id') or '')
        if not card_id:
            continue
        if card_row.get('libraryHidden') or card_row.get('isLimited'):
            continue
        if str(card_row.get('planType') or 'ProducePlanType_Common') not in allowed_plan_types:
            continue
        effect_types = repository.card_exam_effect_types(card_row)
        score = 0.5 / math.sqrt(index + 1.0)
        score += float(sample_counts.get(card_id, 0)) * 1.75
        score += 1.0 if card_id in recommended_ids else 0.0
        score += float(card_row.get('evaluation') or 0) / 250.0
        score += repository.card_play_priors.get(card_id, 0.0) / 120.0
        if focus_effect_type and focus_effect_type in effect_types:
            score += 1.5
        if any(value in effect_types for value in scenario.focus_effect_types):
            score += 0.5
        weighted.append((score, card_row))
    weighted.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in weighted]


def sample_card_from_weighted_pool(
    weighted_pool: list[dict[str, Any]],
    rng: np.random.Generator,
    *,
    sample_counts: Counter[str] | None = None,
    preferred_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    """按候选池顺序和样例卡组偏好做平滑抽样，避免始终只落到顶级卡。"""

    if not weighted_pool:
        return None
    sample_counts = sample_counts or Counter()
    preferred_ids = preferred_ids or set()
    pool_size = max(len(weighted_pool), 1)
    weights: list[float] = []
    for index, card in enumerate(weighted_pool):
        card_id = str(card.get('id') or '')
        percentile = index / max(pool_size - 1, 1)
        rank_bias = 1.0 - 0.35 * percentile
        sample_bias = min(float(sample_counts.get(card_id, 0)), 3.0) * 0.22
        preferred_bias = 0.12 if card_id in preferred_ids else 0.0
        evaluation_bias = float(card.get('evaluation') or 0) / 4000.0
        rarity_bias = _RARITY_BIAS_MAP.get(str(card.get('rarity') or ''), 0.90)
        weights.append(max(0.08, (rank_bias + sample_bias + preferred_bias + evaluation_bias) * rarity_bias))
    probabilities = np.array(weights, dtype=np.float64)
    probabilities = probabilities / max(probabilities.sum(), 1e-8)
    return weighted_pool[int(rng.choice(len(weighted_pool), p=probabilities))]


def _card_limit(card_row: dict[str, Any]) -> int:
    return 1 if card_row.get('noDeckDuplication') else 3


def _apply_initial_deck_constraints(
    repository: MasterDataRepository,
    deck: list[dict[str, Any]],
    weighted_pool: list[dict[str, Any]],
    *,
    loadout: IdolLoadout | None,
    guaranteed_effect_counts: dict[str, int] | None,
    forced_card_groups: dict[str, tuple[str, ...]] | None,
    deck_size: int,
) -> list[dict[str, Any]]:
    """Force/include cards after base deck assembly while preserving deck size."""

    required_effect_counts = normalize_guaranteed_effect_counts(guaranteed_effect_counts)
    normalized_forced_card_groups = normalize_forced_card_groups(forced_card_groups)
    if not required_effect_counts and not normalized_forced_card_groups:
        return deck[:deck_size]

    adjusted_deck = list(deck[:deck_size])
    effect_cache: dict[tuple[str, int], set[str]] = {}
    weighted_rank = {
        str(card.get('id') or ''): index
        for index, card in enumerate(weighted_pool)
        if str(card.get('id') or '')
    }
    seen_counts = Counter(str(card.get('id') or '') for card in adjusted_deck)
    effect_counts: Counter[str] = Counter()

    def _effect_types(card_row: dict[str, Any]) -> set[str]:
        card_id = str(card_row.get('id') or '')
        upgrade_count = int(card_row.get('upgradeCount') or 0)
        cache_key = (card_id, upgrade_count)
        cached = effect_cache.get(cache_key)
        if cached is not None:
            return cached
        cached = set(repository.card_axis_effect_types(card_row))
        effect_cache[cache_key] = cached
        return cached

    for card_row in adjusted_deck:
        effect_counts.update(_effect_types(card_row))

    forced_counts: Counter[str] = Counter()
    for axis_effect_type, card_ids in normalized_forced_card_groups.items():
        for raw_card_id in card_ids:
            resolved_card_id = resolve_produce_card_id(loadout, raw_card_id) if loadout is not None else str(raw_card_id)
            forced_counts[resolved_card_id] += 1

    def _resolve_candidate(card_id: str) -> dict[str, Any]:
        candidate = _canonical_card_row(repository, card_id)
        if candidate is None:
            raise KeyError(f'Unknown force-card id: {card_id}')
        return candidate

    def _replace_index_for(new_card: dict[str, Any]) -> int | None:
        new_card_id = str(new_card.get('id') or '')
        best_index: int | None = None
        best_rank = -1
        best_eval = float('inf')
        for index, existing_card in enumerate(adjusted_deck):
            existing_id = str(existing_card.get('id') or '')
            if seen_counts[existing_id] - 1 < forced_counts.get(existing_id, 0):
                continue
            existing_effects = _effect_types(existing_card)
            if any(
                effect in existing_effects and effect_counts[effect] - 1 < minimum
                for effect, minimum in required_effect_counts.items()
            ):
                continue
            if seen_counts[new_card_id] >= _card_limit(new_card):
                temp_seen = seen_counts.copy()
                temp_seen[existing_id] -= 1
                if temp_seen[new_card_id] >= _card_limit(new_card):
                    continue
            rank = weighted_rank.get(existing_id, len(weighted_rank) + 1_000)
            evaluation = float(existing_card.get('evaluation') or 0.0)
            if best_index is None or rank > best_rank or (rank == best_rank and evaluation < best_eval):
                best_index = index
                best_rank = rank
                best_eval = evaluation
        return best_index

    def _place_card(card_row: dict[str, Any]) -> bool:
        card_id = str(card_row.get('id') or '')
        if seen_counts[card_id] < _card_limit(card_row) and len(adjusted_deck) < deck_size:
            adjusted_deck.append(card_row)
            seen_counts[card_id] += 1
            effect_counts.update(_effect_types(card_row))
            return True
        replace_index = _replace_index_for(card_row)
        if replace_index is None:
            return False
        removed_card = adjusted_deck[replace_index]
        removed_id = str(removed_card.get('id') or '')
        seen_counts[removed_id] -= 1
        for effect_type in _effect_types(removed_card):
            effect_counts[effect_type] -= 1
        adjusted_deck[replace_index] = card_row
        seen_counts[card_id] += 1
        effect_counts.update(_effect_types(card_row))
        return True

    for axis_effect_type, card_ids in normalized_forced_card_groups.items():
        if axis_effect_type == UNSCOPED_FORCE_CARD_GROUP:
            continue
        for raw_card_id in card_ids:
            resolved_card_id = resolve_produce_card_id(loadout, raw_card_id) if loadout is not None else str(raw_card_id)
            candidate = _resolve_candidate(resolved_card_id)
            candidate_effect_types = _effect_types(candidate)
            if axis_effect_type not in candidate_effect_types:
                raise ValueError(
                    f'force-card {raw_card_id} does not match requested axis {axis_effect_type}'
                )

    for card_id, required_count in forced_counts.items():
        candidate = _resolve_candidate(card_id)
        if required_count > _card_limit(candidate):
            raise ValueError(f'force-card exceeds duplication limit: {card_id} x {required_count}')
        while seen_counts[card_id] < required_count:
            if not _place_card(candidate):
                raise RuntimeError(f'Unable to satisfy force-card requirement: {card_id}')

    for effect_type, minimum in required_effect_counts.items():
        candidates = [card for card in weighted_pool if effect_type in _effect_types(card)]
        if not candidates:
            raise RuntimeError(f'No candidate card matches guaranteed effect type: {effect_type}')
        while effect_counts[effect_type] < minimum:
            placed = False
            for candidate in candidates:
                if _place_card(candidate):
                    placed = True
                    break
            if not placed:
                raise RuntimeError(
                    f'Unable to satisfy guaranteed effect count: {effect_type} >= {minimum}'
                )

    return adjusted_deck[:deck_size]


def list_trainable_idol_card_ids(
    repository: MasterDataRepository,
    scenario: ScenarioSpec | None = None,
) -> tuple[str, ...]:
    """列出可用于通用训练的偶像卡池。"""

    rows = repository.load_table('IdolCard').rows
    idol_card_ids: list[str] = []
    for row in rows:
        idol_card_id = str(row.get('id') or '')
        if not idol_card_id:
            continue
        if str(row.get('planType') or 'ProducePlanType_Common') not in _ALLOWED_COMMON_PLAN_TYPES:
            continue
        if not str(row.get('characterId') or ''):
            continue
        if not str(row.get('produceCardId') or ''):
            continue
        if not (row.get('examInitialDeckId') or row.get('produceStepAuditionDifficultyId') or row.get('examEffectType')):
            continue
        idol_card_ids.append(idol_card_id)

    return tuple(sorted(dict.fromkeys(idol_card_ids)))



def build_initial_exam_deck(
    repository: MasterDataRepository,
    scenario: ScenarioSpec,
    focus_effect_type: str | None = None,
    deck_size: int = 15,
    rng: np.random.Generator | None = None,
    loadout: IdolLoadout | None = None,
    guaranteed_effect_counts: dict[str, int] | None = None,
    forced_card_groups: dict[str, tuple[str, ...]] | None = None,
) -> list[dict[str, Any]]:
    """根据偶像卡初始 deck、专属卡和流派补全考试初始牌组。"""

    rng = rng or np.random.default_rng()
    if loadout is None:
        base_deck = repository.build_initial_exam_deck(
            scenario,
            focus_effect_type=focus_effect_type,
            deck_size=deck_size,
            rng=rng,
        )
        weighted_pool = repository.weighted_card_pool(
            scenario,
            focus_effect_type=focus_effect_type,
            plan_type=None,
        )
        return _apply_initial_deck_constraints(
            repository,
            list(base_deck),
            weighted_pool,
            loadout=None,
            guaranteed_effect_counts=guaranteed_effect_counts,
            forced_card_groups=forced_card_groups,
            deck_size=deck_size,
        )

    seed_card_rows = _load_seed_exam_deck_rows(repository, loadout)
    # メモリー 在 ProduceStart 阶段入组的卡：与固定底牌一样先放进去（EndAuditionMid 阶段的卡需要运行时钩子，见 docs/loadouts.md）。
    memory_card_rows = _load_memory_deck_rows(repository, loadout, _MEMORY_CARD_PHASE_PRODUCE_START)
    if not seed_card_rows:
        if loadout.stat_profile.initial_exam_deck_id and repository.exam_initial_decks.first(loadout.stat_profile.initial_exam_deck_id) is None:
            raise RuntimeError(f'Unknown initial exam deck: {loadout.stat_profile.initial_exam_deck_id}')
        base_deck = memory_card_rows + _apply_loadout_card_conversions(
            repository,
            repository.build_initial_exam_deck(
                scenario,
                focus_effect_type=focus_effect_type or loadout.stat_profile.exam_effect_type,
                deck_size=deck_size,
                rng=rng,
                plan_type=loadout.stat_profile.plan_type,
            ),
            loadout=loadout,
        )
        weighted_pool = build_weighted_card_pool(
            repository,
            scenario,
            focus_effect_type=focus_effect_type or loadout.stat_profile.exam_effect_type,
            loadout=loadout,
        )
        return _apply_initial_deck_constraints(
            repository,
            base_deck,
            weighted_pool,
            loadout=loadout,
            guaranteed_effect_counts=guaranteed_effect_counts,
            forced_card_groups=forced_card_groups,
            deck_size=deck_size,
        )

    deck: list[dict[str, Any]] = []
    seen_counts: Counter[str] = Counter()

    def _append_card(card_row: dict[str, Any]) -> bool:
        card_id = str(card_row.get('id') or '')
        if not card_id:
            return False
        if card_row.get('noDeckDuplication') and seen_counts[card_id] > 0:
            return False
        limit = 1 if card_row.get('noDeckDuplication') else 3
        if seen_counts[card_id] >= limit:
            return False
        deck.append(card_row)
        seen_counts[card_id] += 1
        return True

    for card_row in _apply_loadout_card_conversions(repository, seed_card_rows, loadout=loadout):
        _append_card(card_row)
    for card_row in memory_card_rows:
        _append_card(card_row)

    unique_card_id = loadout.stat_profile.unique_produce_card_id
    resolved_unique_card_id = resolve_produce_card_id(loadout, unique_card_id)
    if resolved_unique_card_id and seen_counts[resolved_unique_card_id] <= 0:
        unique_card = _canonical_card_row(repository, resolved_unique_card_id)
        if unique_card is not None:
            _append_card(unique_card)
    for conversion in loadout.produce_card_conversions:
        if len(deck) >= deck_size:
            break
        converted_card = _canonical_card_row(repository, str(conversion.after_card_id))
        if converted_card is not None:
            _append_card(converted_card)

    weighted_pool = build_weighted_card_pool(
        repository,
        scenario,
        focus_effect_type=focus_effect_type or loadout.stat_profile.exam_effect_type,
        loadout=loadout,
    )
    sample_counts = (
        Counter(resolve_produce_card_id(loadout, card_id) for card_id in loadout.deck_archetype.sample_card_ids)
        if loadout.deck_archetype is not None
        else Counter()
    )
    preferred_ids = (
        {resolve_produce_card_id(loadout, card_id) for card_id in loadout.deck_archetype.recommended_card_ids}
        if loadout.deck_archetype is not None
        else set()
    )
    card_limit_by_id = {
        str(card.get('id') or ''): (
            1 if card.get('noDeckDuplication') else max(2, sample_counts.get(str(card.get('id') or ''), 1) + 1)
        )
        for card in weighted_pool
        if str(card.get('id') or '')
    }
    available = [
        card
        for card in weighted_pool
        if seen_counts[str(card.get('id') or '')] < card_limit_by_id.get(str(card.get('id') or ''), 0)
    ]

    while len(deck) < deck_size and available:
        selected = sample_card_from_weighted_pool(
            available,
            rng,
            sample_counts=sample_counts,
            preferred_ids=preferred_ids,
        )
        if selected is None:
            break
        sampled_variant = repository.sample_random_card_variant(str(selected.get('id') or ''), rng)
        _append_card(sampled_variant if sampled_variant is not None else selected)
        selected_card_id = str(selected.get('id') or '')
        if seen_counts[selected_card_id] >= card_limit_by_id.get(selected_card_id, 0):
            available = [
                card
                for card in available
                if str(card.get('id') or '') != selected_card_id
            ]

    return _apply_initial_deck_constraints(
        repository,
        deck,
        weighted_pool,
        loadout=loadout,
        guaranteed_effect_counts=guaranteed_effect_counts,
        forced_card_groups=forced_card_groups,
        deck_size=deck_size,
    )
