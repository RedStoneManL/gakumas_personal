"""课程奖励与咨询的暂停选择点，供模拟和实况共用候选合法性。"""

from __future__ import annotations

from dataclasses import replace
from copy import deepcopy
import math
from typing import TYPE_CHECKING, Any

import numpy as np

from ...constants.game.action_types import (
    ACTION_CARD_REWARD_REROLL, ACTION_CARD_REWARD_SKIP, ACTION_CONSULT_FINISH,
    ACTION_SHOP_REROLL, CARD_REWARD_PICK_ACTION_TYPES,
)
from ...idol_config import apply_card_customizations

if TYPE_CHECKING:
    from .runtime import ProduceActionCandidate, ProduceRuntime


class ProduceChoiceSupport:
    """暂停后不会因重新编码而刷新奖励或商店库存。"""

    def __init__(self, runtime: ProduceRuntime) -> None:
        """仅绑定宿主，不采样或执行开场效果。"""
        self.runtime = runtime
        self.external_candidates: list[ProduceActionCandidate] | None = None

    @property
    def research_shop(self):
        return getattr(self.runtime, 'hif_sampling_kernel', None) is not None

    def _consult_config(self):
        return getattr(self.runtime, 'hif_research_config', {})

    @staticmethod
    def consult_card_base_price(row):
        prices = {'ProduceCardRarity_R': {1: 100}, 'ProduceCardRarity_Sr': {0: 50, 1: 110},
                  'ProduceCardRarity_Ssr': {0: 100, 1: 150}}
        try:
            return prices[row['rarity']][int(row.get('upgradeCount') or 0)]
        except KeyError as error:
            raise ValueError(f'Unsupported ordinary consultation card price: {row["id"]}') from error

    @staticmethod
    def consult_drink_base_price(row):
        prices = {'ProduceCardRarity_R': 50, 'ProduceCardRarity_Sr': 75, 'ProduceCardRarity_Ssr': 100}
        # Drink rarity uses the corresponding ProduceDrinkRarity enum.
        rarity = str(row.get('rarity')).replace('ProduceDrinkRarity_', 'ProduceCardRarity_')
        if rarity not in prices:
            raise ValueError(f'Unsupported ordinary consultation drink price: {row["id"]}')
        return prices[rarity]

    def consult_service_base_price(self, kind):
        if kind not in ('upgrade', 'delete'):
            raise ValueError(f'Unknown consultation service: {kind}')
        table = self._consult_config().get(f'consult_{kind}_prices', [100, 125, 150, 175, 200, 250])
        if not table or any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in table):
            raise ValueError(f'Invalid consultation {kind} price profile')
        count = int(self.runtime.state.get(f'shop_{kind}_count') or 0)
        return table[min(count, len(table)-1)]

    def _service_inventory(self):
        rt = self.runtime
        result = {}
        for kind in ('upgrade', 'delete'):
            gate = 5 if kind == 'upgrade' else 15
            if int(rt.state.get('producer_level') or 0) < gate:
                continue
            base_price = self.consult_service_base_price(kind)
            price = rt._effective_shop_cost(base_price, 1, resource_kind=kind)
            targets = ([(i, upgraded) for i, _, upgraded in rt._eligible_shop_upgrade_targets()]
                       if kind == 'upgrade' else rt._eligible_shop_delete_targets())
            for slot, (index, row) in enumerate(targets, 1):
                action_type = f'shop_{kind}_card_{slot}'
                candidate = self.card_candidate(row, action_type)
                result[action_type] = replace(candidate, target_deck_index=index,
                    produce_point_delta=-price, slot_index=slot-1,
                    label=('强化 ' if kind == 'upgrade' else '删除 ') + row['name'])
        return result

    def _research_inventory(self):
        rt = self.runtime
        kernel = rt.hif_sampling_kernel
        config = self._consult_config()
        inventory = {}
        for kind in ('card', 'drink'):
            slots = config.get(f'consult_{kind}_slots', 4)
            if type(slots) is not int or slots < 0:
                raise ValueError(f'Invalid consultation {kind} slot count')
            sale_slots = config.get(f'consult_{kind}_sale_slots', [0] if slots else [])
            if any(type(i) is not int or not 0 <= i < slots for i in sale_slots):
                raise ValueError(f'Invalid consultation {kind} SALE slots')
            if kind == 'card':
                rows = {}
                for card in rt._selection_card_pool():
                    row = rt._lookup_card_upgrade_row(card['id'], 0)
                    if (row is not None and row['rarity'] in {'ProduceCardRarity_R', 'ProduceCardRarity_Sr', 'ProduceCardRarity_Ssr'}
                            and int(row.get('unlockProducerLevel') or 0) <= int(rt.state['producer_level'])):
                        rows[row['id']] = row
            else:
                rows = {r['id']: r for r in rt.repository.produce_drinks.rows
                        if not r.get('libraryHidden') and r.get('planType') in rt._allowed_plan_types()}
            for slot in range(slots):
                if not rows:
                    break
                pool_id = f'hif_consult:{kind}:{slot}'
                selected = kernel({'pool_id': pool_id, 'resource_type': kind, 'count': 1, 'replace': False,
                    'legal_candidates': list(rows.values()), 'effect_id': 'hif_consult_inventory'})
                if not selected['resource_ids']:
                    from .runtime import ProduceActionCandidate
                    action_type = f'shop_buy_{kind}_{slot+1}'
                    inventory[action_type] = ProduceActionCandidate(label='本槽无合法商品', action_type=action_type,
                        effect_types=[], produce_effect_ids=[], slot_index=slot, available=False)
                    continue
                resource_id = selected['resource_ids'][0]
                if resource_id not in rows:
                    raise ValueError(f'Illegal configured consultation resource: {resource_id}')
                row = deepcopy(rows[resource_id])
                # Unknown joint distribution is a source-specific planning model.
                # R is offered upgraded; SR/SSR use explicit probability or default 0.
                if kind == 'card':
                    pool_config = kernel.pools.get(pool_id, {})
                    probability = float(pool_config.get('upgrade_probability', 0))
                    if not math.isfinite(probability) or not 0 <= probability <= 1:
                        raise ValueError(f'Invalid consultation upgrade probability: {pool_id}')
                    upgrade = int(row['rarity'] == 'ProduceCardRarity_R' or rt.np_random.random() < probability)
                    row = deepcopy(rt._lookup_card_upgrade_row(resource_id, upgrade))
                    if row is None:
                        raise ValueError(f'Unavailable consultation card variant: {resource_id}@{upgrade}')
                    kernel.history[-1]['upgrade_model'] = ('configured' if 'upgrade_probability' in pool_config
                                                          else 'R-upgraded-other-unupgraded-placeholder')
                    candidate = self.card_candidate(row, f'shop_buy_card_{slot+1}')
                    base_price = self.consult_card_base_price(row)
                else:
                    from .runtime import ProduceActionCandidate
                    candidate = ProduceActionCandidate(label=row['name'], action_type=f'shop_buy_drink_{slot+1}',
                        effect_types=[], produce_effect_ids=[], resource_type='ProduceResourceType_ProduceDrink',
                        resource_id=resource_id, **rt._candidate_drink_metadata(row))
                    base_price = self.consult_drink_base_price(row)
                ratio = 0.7 if slot in sale_slots else 1.0
                price = rt._effective_shop_cost(base_price, ratio, resource_kind=kind)
                candidate = replace(candidate, produce_point_delta=-price, slot_index=slot,
                    source_row_id=resource_id, label=('SALE ' if ratio < 1 else '') + candidate.label)
                inventory[candidate.action_type] = candidate
                # No repeated names per merchandise row is an explicit planning convention.
                rows.pop(resource_id)
        rt.state['consult_shop_model'] = {
            'prices': 'report3-community-V', 'sale_ratio': 0.7,
            'card_slots': config.get('consult_card_slots', 4), 'drink_slots': config.get('consult_drink_slots', 4),
            'slot_distribution': 'configured-planning-model; default4+4-not-confirmed',
            'service_limit_per_visit': config.get('consult_service_limit_per_visit', 1),
            'service_limit_evidence': 'unknown', 'service_tail_price': 'last-configured-price-assumption',
            'refresh_reopens_services': bool(config.get('consult_refresh_reopens_services', False)),
            'refresh_preserves_sold_out': bool(config.get('consult_refresh_preserves_sold_out', False)),
            'refresh_semantics_evidence': 'unknown',
        }
        return inventory

    def card_candidate(self, row: dict[str, Any], action_type: str) -> ProduceActionCandidate:
        """从确切主数据变体创建同一类引擎候选。"""
        from .runtime import ProduceActionCandidate

        return ProduceActionCandidate(
            label=str(row.get('name') or row['id']), action_type=action_type,
            effect_types=[], produce_effect_ids=[], produce_card_id=str(row['id']),
            resource_type='ProduceResourceType_ProduceCard', resource_id=str(row['id']),
            resource_level=int(row.get('upgradeCount') or 0),
            customize_ids=tuple(row.get('customizedProduceCardCustomizeIds') or ()),
            card_evaluation=float(row.get('evaluation') or 0),
            **self.runtime._candidate_card_metadata(row),
        )

    def sample_reward_cards(self) -> list[dict[str, Any]]:
        """只在奖励出现或策略明确再抽选时采样；权重沿用已标记的近似配置。"""
        from .runtime import (
            LESSON_CARD_REWARD_CANDIDATE_COUNT, LESSON_CARD_REWARD_POOL_ID,
            LESSON_CARD_REWARD_RARITY_WEIGHTS, LESSON_CARD_REWARD_UPGRADE_BASE_RATE,
        )

        rt = self.runtime
        if self.research_shop:
            pool_id = f'hif_open_lesson:{rt.scenario.produce_id}:{int(rt.state["audition_index"])}'
            return rt.hif_sampling_kernel.candidates(pool_id, kind='card',
                count=LESSON_CARD_REWARD_CANDIDATE_COUNT, upgraded=None)
        pool_row = rt.repository.load_table('ProduceCardPool').first(LESSON_CARD_REWARD_POOL_ID)
        if pool_row is None:
            raise KeyError(LESSON_CARD_REWARD_POOL_ID)
        members = {str(row['id']) for row in pool_row.get('produceCardRatios') or []}
        rows = []
        for card_id in sorted(members):
            row = rt.repository.card_row_by_upgrade(card_id, 0, fallback_to_canonical=False)
            if row is None or str(row.get('planType')) not in rt._allowed_plan_types():
                continue
            if row.get('noDeckDuplication') and any(card['id'] == card_id for card in rt.deck):
                continue
            if rt.idol_loadout is not None and int(row.get('unlockProducerLevel') or 0) > int(rt.state['producer_level']):
                continue
            rows.append(row)
        if not rows:
            raise ValueError('No eligible lesson reward cards')
        stage = min(int(rt.state['audition_index']), len(LESSON_CARD_REWARD_RARITY_WEIGHTS) - 1)
        weights = np.array([
            LESSON_CARD_REWARD_RARITY_WEIGHTS[stage].get(str(row.get('rarity')), 1.0)
            for row in rows
        ], dtype=float)
        indices = rt.np_random.choice(len(rows), size=min(LESSON_CARD_REWARD_CANDIDATE_COUNT, len(rows)),
                                      replace=False, p=weights / weights.sum())
        selected = []
        for index in indices:
            row = rows[int(index)]
            # 主数据没有完整课程稀有度/强化抽选表，继续保留近似标记。TODO(HIF-verify)
            upgrade_rate = np.clip(LESSON_CARD_REWARD_UPGRADE_BASE_RATE + float(rt.state.get('card_upgrade_probability_bonus') or 0), 0, 1)
            if rt.np_random.random() < upgrade_rate:
                row = rt.repository.card_row_by_upgrade(str(row['id']), 1, fallback_to_canonical=False) or row
            selected.append(dict(row))
        return selected

    def start_reward(self, cards: list[dict[str, Any]] | None = None) -> None:
        """进入三选奖励；外部给定候选时完全跳过本地随机采样。"""
        rt = self.runtime
        cards = self.sample_reward_cards() if cards is None else cards
        if not (0 if self.research_shop else 1) <= len(cards) <= len(CARD_REWARD_PICK_ACTION_TYPES):
            raise ValueError('Reward accepts at most three explicit candidates')
        rt.pending_card_reward = {
            'candidates': [self.card_candidate(row, action_type)
                           for row, action_type in zip(cards, CARD_REWARD_PICK_ACTION_TYPES)],
            'pool_id': f'hif_open_lesson:{rt.scenario.produce_id}:{int(rt.state["audition_index"])}',
        }
        rt.pre_audition_phase = 'card_reward'
        rt._candidates = []

    def refresh_consult(self) -> None:
        """刷新可改卡目标与控制项，保留已经生成的商品和售罄槽。"""
        from .runtime import ProduceActionCandidate

        rt = self.runtime
        rt.pre_audition_action_inventory = dict(rt.shop_inventory)
        if self.research_shop:
            rt.pre_audition_action_inventory.update(self._service_inventory())
        for action_type, label in ((ACTION_SHOP_REROLL, '刷新商品'), (ACTION_CONSULT_FINISH, '结束咨询')):
            rt.pre_audition_action_inventory[action_type] = ProduceActionCandidate(
                label=label, action_type=action_type, effect_types=[], produce_effect_ids=[],
            )
        rt._candidates = []

    def start_consult(self) -> None:
        """每周进入咨询，结束前不推进周数或自动进入考试。"""
        rt = self.runtime
        rt.pre_audition_phase = 'consult'
        rt.state['consult_visits'] += 1
        rt.state['shop_card_modified_in_visit'] = 0.0
        if self.research_shop:
            for kind in ('upgrade', 'delete'):
                rt.state.setdefault(f'shop_{kind}_count', 0)
                rt.state[f'shop_{kind}_visit_used'] = 0
        rt._dispatch_produce_item_phase('ProducePhaseType_StartShop')
        if not self.research_shop:
            rt._dispatch_produce_item_phase('ProducePhaseType_StartCustomize')
        rt.shop_inventory = self._research_inventory() if self.research_shop else rt._build_shop_inventory()
        self.refresh_consult()

    def available(self, candidate: ProduceActionCandidate) -> bool:
        """统一规则合法性；UI 可用性在此之外由 adapter 掩码限制。"""
        rt = self.runtime
        kind = candidate.action_type
        if kind in CARD_REWARD_PICK_ACTION_TYPES or kind.startswith('shop_buy_card_'):
            if len(rt.deck) >= 99:
                return False
            row = rt.repository.card_row_by_upgrade(candidate.resource_id, candidate.resource_level, fallback_to_canonical=False)
            if row is None:
                return False
            if str(row.get('planType')) not in rt._allowed_plan_types():
                return False
            if row.get('noDeckDuplication') and any(card['id'] == candidate.resource_id for card in rt.deck):
                return False
            apply_card_customizations(rt.repository, row, candidate.customize_ids)
            return float(rt.state['produce_points']) + candidate.produce_point_delta >= 0
        if kind == ACTION_CARD_REWARD_SKIP or kind == ACTION_CONSULT_FINISH:
            return True
        if kind == ACTION_CARD_REWARD_REROLL:
            if self.research_shop:
                return rt.hif_sampling_kernel.reward_controls(rt.pending_card_reward['pool_id'])['reroll']
            return rt.state['card_reward_rerolls_used'] < rt.state['card_select_reroll_count_bonus']
        if kind.startswith('card_reward_exclude_'):
            return (self.research_shop and rt.hif_sampling_kernel.reward_controls(rt.pending_card_reward['pool_id'])['exclude']
                    and any(c.resource_id==candidate.resource_id for c in rt.pending_card_reward['candidates']))
        if kind == ACTION_SHOP_REROLL:
            return rt.state['shop_rerolls_used'] < rt.state['shop_reroll_count_bonus']
        if kind.startswith('shop_buy_drink_'):
            return (rt.repository.produce_drinks.first(candidate.resource_id) is not None
                    and len(rt.drinks) < rt._effective_drink_limit()
                    and rt.state['produce_points'] + candidate.produce_point_delta >= 0)
        if kind.startswith(('shop_upgrade_card_', 'shop_delete_card_')):
            if self.research_shop:
                service = 'upgrade' if kind.startswith('shop_upgrade_card_') else 'delete'
                gate = 5 if service == 'upgrade' else 15
                limit = self._consult_config().get('consult_service_limit_per_visit', 1)
                if type(limit) is not int or limit < 0:
                    raise ValueError('Invalid consultation service limit')
                if int(rt.state.get('producer_level') or 0) < gate or int(rt.state.get(f'shop_{service}_visit_used') or 0) >= limit:
                    return False
                if not 0 <= candidate.target_deck_index < len(rt.deck):
                    return False
                if service == 'upgrade' and not any(i == candidate.target_deck_index for i, _, _ in rt._eligible_shop_upgrade_targets()):
                    return False
                return rt.state['produce_points'] + candidate.produce_point_delta >= 0
            return (0 <= candidate.target_deck_index < len(rt.deck)
                    and rt.state['shop_card_modified_in_visit'] < 1
                    and rt.state['produce_points'] + candidate.produce_point_delta >= 0)
        return False

    def legal_actions(self) -> list[ProduceActionCandidate]:
        """产生当前子阶段动作，重复读取不改变候选或随机数状态。"""
        from .runtime import ProduceActionCandidate

        rt = self.runtime
        if self.external_candidates is not None:
            candidates = self.external_candidates
        elif rt.pre_audition_phase == 'card_reward':
            candidates = list(rt.pending_card_reward['candidates'])
            if self.research_shop:
                candidates += [replace(c, label='从候选除去 '+c.label,
                    action_type=f'card_reward_exclude_{i+1}') for i,c in enumerate(rt.pending_card_reward['candidates'])]
            candidates += [ProduceActionCandidate(label=label, action_type=kind, effect_types=[], produce_effect_ids=[])
                           for kind, label in ((ACTION_CARD_REWARD_SKIP, '放弃奖励'), (ACTION_CARD_REWARD_REROLL, '重新抽选'))]
        else:
            candidates = list(rt.pre_audition_action_inventory.values())
        rt._candidates = [replace(candidate, available=candidate.available and self.available(candidate))
                          for candidate in candidates]
        return rt._candidates

    def _grant_card(self, candidate: ProduceActionCandidate) -> None:
        """授予选中的确切副本变体，不再抽选卡牌。"""
        rt = self.runtime
        row = rt.repository.card_row_by_upgrade(candidate.resource_id, candidate.resource_level, fallback_to_canonical=False)
        card = deepcopy(apply_card_customizations(rt.repository, row, candidate.customize_ids))
        if candidate.instance_id:
            card['instance_id'] = candidate.instance_id
        rt.deck.append(card)
        rt._remember_legend_cards()
        rt._dispatch_produce_item_phase('ProducePhaseType_GetProduceCard', card=card)

    def step(self, candidate: ProduceActionCandidate) -> tuple[float, bool, dict[str, Any]]:
        """模拟模式消费一个选择；外部模式必须回灌实际快照。"""
        rt = self.runtime
        if self.external_candidates is not None:
            raise RuntimeError('External decisions require an observed result, never seeded step')
        if not self.available(candidate):
            return -0.25, False, {'invalid_action': True}
        kind = candidate.action_type
        info = {'action_type': kind, 'action': candidate.label}
        if rt.pre_audition_phase == 'card_reward':
            if kind.startswith('card_reward_exclude_'):
                rt.hif_sampling_kernel.exclude(rt.pending_card_reward['pool_id'],candidate.resource_id)
                rt.pending_card_reward['candidates'] = [c for c in rt.pending_card_reward['candidates']
                                                        if c.resource_id!=candidate.resource_id]
                return 0.0, False, info
            if kind == ACTION_CARD_REWARD_REROLL:
                rt.state['card_reward_rerolls_used'] += 1
                self.start_reward()
                return 0.0, False, info
            if kind in CARD_REWARD_PICK_ACTION_TYPES:
                self._grant_card(candidate)
                rt.state['lesson_card_rewards_taken'] += 1
            rt.pending_card_reward = None
        elif kind == ACTION_SHOP_REROLL:
            rt.state['shop_rerolls_used'] += 1
            if self.research_shop:
                old = rt.shop_inventory
                rt.shop_inventory = self._research_inventory()
                if self._consult_config().get('consult_refresh_preserves_sold_out', False):
                    for key, value in old.items():
                        if not value.available and key in rt.shop_inventory:
                            rt.shop_inventory[key] = value
                if self._consult_config().get('consult_refresh_reopens_services', False):
                    rt.state['shop_upgrade_visit_used'] = rt.state['shop_delete_visit_used'] = 0
            else:
                rt.shop_inventory = rt._build_shop_inventory()
            self.refresh_consult()
            return 0.0, False, info
        elif kind != ACTION_CONSULT_FINISH:
            rt.state['produce_points'] += candidate.produce_point_delta
            if kind.startswith('shop_buy_card_'):
                self._grant_card(candidate)
                rt._dispatch_produce_item_phase('ProducePhaseType_BuyShopItemProduceCard', card_id=candidate.resource_id)
            elif kind.startswith('shop_buy_drink_'):
                rt._grant_resource(candidate.resource_type, candidate.resource_id, candidate.resource_level)
                rt._dispatch_produce_item_phase('ProducePhaseType_BuyShopItemProduceDrink', drink_id=candidate.resource_id)
            elif kind.startswith('shop_upgrade_card_'):
                if self.research_shop:
                    self._apply_research_service(candidate, 'upgrade')
                elif not rt._apply_shop_upgrade_candidate(candidate):
                    rt.state['produce_points'] -= candidate.produce_point_delta
                    return -0.25, False, {'invalid_action': True}
            elif kind.startswith('shop_delete_card_'):
                if self.research_shop:
                    self._apply_research_service(candidate, 'delete')
                elif not rt._apply_shop_delete_candidate(candidate):
                    rt.state['produce_points'] -= candidate.produce_point_delta
                    return -0.25, False, {'invalid_action': True}
            if not self.research_shop or kind.startswith(('shop_buy_card_', 'shop_buy_drink_')):
                rt.shop_inventory[kind] = replace(candidate, available=False)
            rt._refresh_quality_scores()
            self.refresh_consult()
            return 0.0, False, info
        if kind == ACTION_CONSULT_FINISH:
            rt._dispatch_produce_item_phase('ProducePhaseType_EndShop')
        rt.pre_audition_phase = 'weekly'
        rt._refresh_quality_scores()
        close = rt.pending_week_close or {'reward': -0.01, 'info': {}, 'breakdown': {}}
        rt.pending_week_close = None
        return rt._close_week(close['reward'], {**close['info'], **info}, close['breakdown'])

    def _apply_research_service(self, candidate, kind):
        rt = self.runtime
        index = candidate.target_deck_index
        if kind == 'delete':
            card = rt.deck.pop(index)
            phase = 'ProducePhaseType_DeleteProduceCard'
        else:
            original = rt.deck[index]
            card = deepcopy(rt._lookup_card_upgrade_row(original['id'], 1))
            for key in ('instance_id', 'growEffectIds', 'customizedProduceCardCustomizeIds',
                        'sourceMemoryId', 'sourceMemoryIdolCardId', 'golden_bindings'):
                if key in original:
                    card[key] = deepcopy(original[key])
            rt.deck[index] = card
            phase = 'ProducePhaseType_UpgradeProduceCard'
        rt.state[f'shop_{kind}_count'] = int(rt.state.get(f'shop_{kind}_count') or 0) + 1
        rt.state[f'shop_{kind}_visit_used'] = int(rt.state.get(f'shop_{kind}_visit_used') or 0) + 1
        rt.state['shop_card_modify_count'] = float(rt.state.get('shop_card_modify_count') or 0) + 1
        rt.state['shop_card_modified_in_visit'] = float(rt.state.get('shop_card_modified_in_visit') or 0) + 1
        rt._dispatch_produce_item_phase(phase, card=card)
