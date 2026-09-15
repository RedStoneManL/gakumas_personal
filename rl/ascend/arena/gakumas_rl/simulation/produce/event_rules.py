"""Shared event option semantics, independent of story text and reward sampling.

Master data stores option costs on the option header and success probabilities
in permyriad. Reward-pool membership/weights are deliberately not inferred here.
"""

from __future__ import annotations

import math
import re


def option_success_probability(option: dict) -> float:
    """Decode the branch lottery; alwaysSuccessful overrides its zero default."""
    if option.get('alwaysSuccessful'):
        return 1.0
    has_branches = any(option.get(key) for key in (
        'successProduceEffectIds', 'failProduceEffectIds', 'successStepId', 'failStepId'))
    if not has_branches:
        return 1.0
    value = int(option.get('successProbabilityPermyriad') or 0)
    if not 0 <= value <= 10000:
        raise ValueError(f'Invalid successProbabilityPermyriad: {value}')
    return value / 10000.0


def support_occurrence_probability(base: float, up_permyriad: float = 0) -> float:
    """Configured occurrence lottery, distinct from an option's success lottery.

    The protocol's probability adjustment unit is permyriad. The unknown base
    and event competition model remain caller configuration, never master facts.
    """
    base, up_permyriad = float(base), float(up_permyriad)
    if not math.isfinite(base + up_permyriad) or not 0 <= base <= 1:
        raise ValueError('Invalid configured support-event probability')
    return min(1.0, max(0.0, base + up_permyriad / 10000.0))


def event_option_costs(option: dict, state: dict, event_type: str = '') -> dict:
    """Return payable header costs, using the school's signed cost modifier.

    ``event_school_stamina_permil`` is an accumulated delta (0 = base cost).
    Fractional school-cost rounding is configurable; ``continuous`` preserves
    the previous arena arithmetic and makes no claim about server rounding.
    Zero-cost Trouble branches remain zero under every modifier.
    """
    stamina = float(option.get('stamina') or 0)
    points = float(option.get('producePoint') or 0)
    if stamina < 0 or points < 0 or not math.isfinite(stamina + points):
        raise ValueError(f'Invalid event option cost: {option.get("id", "")}')
    is_school = event_type in ('ProduceEventType_School', 'School', 'school_class') or event_type.startswith('school_class_')
    if is_school:
        delta = float(state.get('event_school_stamina_permil') or 0)
        if not math.isfinite(delta):
            raise ValueError('event_school_stamina_permil must be finite')
        stamina *= max(0.0, 1.0 + delta / 1000.0)
        rounding = state.get('event_school_stamina_rounding', 'continuous')
        if rounding == 'ceil':
            stamina = float(math.ceil(stamina))
        elif rounding == 'floor':
            stamina = float(math.floor(stamina))
        elif rounding != 'continuous':
            raise ValueError(f'Unknown school stamina rounding: {rounding}')
    return {
        'stamina': stamina, 'produce_points': points,
        'produce_card_id': str(option.get('produceCardId') or ''),
        'produce_card_upgrade_count': int(option.get('produceCardUpgradeCount') or 0),
    }


def event_option_is_legal(option: dict, state: dict, event_type: str = '', *,
                          deck_count: int | None = None, deck_limit: int = 99) -> bool:
    """Affordability includes a compulsory header card's required deck slot.

    A full deck may decline an optional body reward, but cannot decline the
    Trouble card while still receiving that option's benefits for free.
    Pass ``deck_count=None`` only for legacy scenarios without a deck cap.
    """
    costs = event_option_costs(option, state, event_type)
    if costs['produce_points'] > float(state.get('produce_points') or 0):
        return False
    if costs['stamina'] > float(state.get('stamina') or 0):
        return False
    return not (costs['produce_card_id'] and deck_count is not None and deck_count >= deck_limit)


def effect_pool_reference(effect: dict | str) -> str | None:
    """Recover a source-pool ID embedded in a master effect ID, if present."""
    effect_id = effect if isinstance(effect, str) else str(effect.get('id') or '')
    if '-p_rd-' not in effect_id:
        return None
    pool = 'p_rd-' + effect_id.split('-p_rd-', 1)[1]
    if '-p_card_search-' in pool:
        pool = pool.split('-p_card_search-', 1)[0]
    else:
        pool = re.sub(r'-(?:select|random|all)-\d+_\d+$', '', pool)
    return pool


def effect_card_operation(effect: dict) -> str | None:
    """Classify acquisition and transformation without conflating their hooks."""
    kind = effect.get('produceEffectType')
    if kind == 'ProduceEffectType_ProduceCardChangeSelect':
        return 'select_change'
    if kind in ('ProduceEffectType_ProduceCardChange', 'ProduceEffectType_ProduceCardChangeUpgrade'):
        return 'random_change'
    if kind in ('ProduceEffectType_ProduceReward', 'ProduceEffectType_ProduceRewardSet') and (
            effect.get('produceResourceType') == 'ProduceResourceType_ProduceCard' or any(
                r.get('resourceType') == 'ProduceResourceType_ProduceCard' for r in effect.get('produceRewards') or ())):
        return 'acquire'
    return None


def option_contract(option: dict) -> dict:
    """A compact policy-facing option contract with source bindings preserved."""
    return {
        'option_id': option['id'],
        'base_costs': event_option_costs(option, {}),
        'success_probability': option_success_probability(option),
        'header_card_is_acquisition': bool(option.get('produceCardId')),
        'effects': [
            {'effect_id': e['id'], 'effect_type': e['produceEffectType'],
             'card_operation': effect_card_operation(e),
             'target_search_id': e.get('produceCardSearchId') or None,
             'reward_pool_reference': effect_pool_reference(e)}
            for e in option.get('effects') or ()
        ],
        'reward_weights': None,
    }
