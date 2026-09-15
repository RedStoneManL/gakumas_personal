"""HIF interval shop: repeatable services and purchases, independent of consultation."""
from copy import deepcopy
import math


def _legal_customize_options(runtime, card):
    """A branch may have a next level even when the physical card is already full."""
    if not runtime._can_customize_card(card):
        return []
    applied = card.get('customizedProduceCardCustomizeIds') or ()
    if len(applied) >= int(card.get('maxCustomizeCount') or 0):
        return []
    return runtime._customize_options_for_card(card)


def _validate_customize_action(runtime, candidate, customized_indices, capacity):
    """Reject stale branches before charging P or changing a card."""
    index = candidate.target_deck_index
    if not isinstance(index, int) or not 0 <= index < len(runtime.deck):
        raise ValueError('Invalid customization target')
    if len(customized_indices) >= capacity and index not in customized_indices:
        raise ValueError('Customization card-slot limit exceeded')
    options = _legal_customize_options(runtime, runtime.deck[index])
    ids = tuple(candidate.customize_ids)
    option = next((row for row in options if ids == (row['id'],)), None)
    if option is None:
        raise ValueError('Unavailable/stale customization branch or card limit')
    price = math.floor(float(option.get('producePoint') or 0)
                       * max(0, 1-runtime.state.get('customize_point_discount', 0)))
    if not candidate.available or candidate.produce_point_delta != -price:
        raise ValueError('Unavailable/stale customization price')


class HifIntervalShop:
    VERSION = 'hif-report3-interval/1'
    PRICES = {'R': {0: None, 1: 30}, 'Sr': {0: None, 1: 50}, 'Ssr': {0: 50, 1: 80}}

    def __init__(self, runtime):
        self.runtime = runtime
        self.inventory = []
        self.refresh_count = 0
        self.upgrades_used = 0
        self.batch_upgrade_used = 0
        self.batch_customizes_used = 0
        self.customized_indices = set()
        self.started = False

    def _candidate(self, kind, label, cost=0, **kwargs):
        from .runtime import ProduceActionCandidate
        return ProduceActionCandidate(action_type=kind, label=label, produce_point_delta=-float(cost),
                                      effect_types=[], produce_effect_ids=[], **kwargs)

    def _refresh(self):
        rt = self.runtime
        kernel = rt.hif_sampling_kernel
        self.inventory = []
        # Four purchase slots, two Select Change slots, two drink slots (V-level profile).
        for index in range(6):
            change = index >= 4
            pool = f'hif_interval:{"change" if change else "buy"}:{index % 4}'
            rows = kernel.candidates(pool, upgraded=None, count=1,
                                     rarity={'ProduceCardRarity_R','ProduceCardRarity_Sr','ProduceCardRarity_Ssr'})
            if not rows:
                self.inventory.append(self._candidate('interval_change' if change else 'interval_buy_card',
                    '空货位', slot_index=index, available=False))
                continue
            row = rows[0]
            rarity = row['rarity'].rsplit('_', 1)[-1]
            level = 1
            if not change and rarity == 'Ssr':
                probability = float(rt.hif_research_config.get('interval_ssr_upgrade_probability',0.5))
                if not 0 <= probability <= 1:
                    raise ValueError('Invalid interval SSR upgrade probability')
                level = (int(row.get('upgradeCount') or 0) if 'upgrade_probability' in kernel.pools.get(pool,{})
                         else int(rt.np_random.random()<probability))
                kernel.history[-1]['upgrade_model'] = 'configured-interval-SSR' if 'upgrade_probability' in kernel.pools.get(pool,{}) else f'interval-SSR-Bernoulli-{probability:g}-placeholder/v1'
            row = rt._lookup_card_upgrade_row(row['id'],level)
            price = {'R': 30, 'Sr': 50, 'Ssr': 80}[rarity] if change else self.PRICES[rarity][level]
            self.inventory.append(self._candidate('interval_change' if change else 'interval_buy_card',
                ('换卡 ' if change else '购买 ') + row['name'], price, slot_index=index,
                resource_type='ProduceResourceType_ProduceCard', resource_id=row['id'], resource_level=level))
        for index in range(2):
            rows = kernel.candidates(f'hif_interval:drink:{index}', kind='drink', count=1)
            if not rows:
                self.inventory.append(self._candidate('interval_buy_drink','空货位',slot_index=6+index,available=False))
                continue
            row = rows[0]
            cost = {'R': 50, 'Sr': 75, 'Ssr': 100}.get(row['rarity'].rsplit('_', 1)[-1])
            if cost is None:
                raise ValueError(f'Unknown HIF drink price: {row["id"]}')
            self.inventory.append(self._candidate('interval_buy_drink', row['name'], cost,
                slot_index=6+index, resource_type='ProduceResourceType_ProduceDrink', resource_id=row['id']))
        self.batch_upgrade_used = 0
        self.batch_customizes_used = 0
        self.customized_indices = set()

    def _refresh_price(self):
        sequence = getattr(self.runtime, 'hif_interval_refresh_prices', (10,10,20,30,40,50))
        return sequence[min(self.refresh_count, len(sequence)-1)]

    def legal_actions(self):
        rt = self.runtime
        if not self.started:
            self.started = True
            rt.pre_audition_phase = 'hif_interval'
            self._refresh()
        actions = [deepcopy(a) for a in self.inventory]
        for a in actions:
            if not a.resource_id:
                a.available = False
                continue
            a.available = a.available and rt.state['produce_points'] + a.produce_point_delta >= 0
            if a.action_type == 'interval_buy_drink':
                a.available &= len(rt.drinks) < rt._effective_drink_limit()
            elif a.action_type == 'interval_buy_card':
                row = rt._lookup_card_row(a.resource_id, a.resource_level)
                a.available &= len(rt.deck) < 99 and not (row.get('noDeckDuplication') and any(c['id']==row['id'] for c in rt.deck))
            elif a.action_type == 'interval_change':
                a.available &= bool(rt._matching_deck_indices('p_card_search-active_skill-mental_skill-deck_all'))
                row = rt._lookup_card_row(a.resource_id, a.resource_level)
                a.available &= not (row.get('noDeckDuplication') and any(c['id']==row['id'] for c in rt.deck))
        actions.append(self._candidate('interval_reroll', '刷新中场', self._refresh_price(),
                                      available=rt.state['produce_points'] >= self._refresh_price()))
        actions.append(self._candidate('interval_recover', '回复2体力', 10,
                                      available=rt.state['produce_points']>=10 and rt.state['stamina']<rt.state['max_stamina']))
        cost = 100 + 25 * self.upgrades_used
        actions.append(self._candidate('interval_upgrade', '强化一张卡', cost,
            available=self.batch_upgrade_used < 1 and rt.state['produce_points']>=cost and bool(rt._eligible_shop_upgrade_targets())))
        if self.batch_customizes_used <= 2:
            for index, card in enumerate(rt.deck):
                if self.batch_customizes_used >= 2 and index not in self.customized_indices:
                    continue
                for option in _legal_customize_options(rt, card):
                    cost = math.floor(float(option.get('producePoint') or 0) * max(0,1-rt.state.get('customize_point_discount',0)))
                    actions.append(self._candidate('interval_customize', '定制 '+card['name'], cost,
                        target_deck_index=index, customize_ids=(option['id'],), available=rt.state['produce_points']>=cost))
        actions.append(self._candidate('interval_finish', '进入 Round 2'))
        rt._candidates = actions
        rt.state['hif_interval_state'] = {'refresh_count':self.refresh_count, 'refresh_price':self._refresh_price(),
            'upgrade_count':self.upgrades_used, 'upgrade_price':100+25*self.upgrades_used,
            'remaining_upgrade':1-self.batch_upgrade_used, 'remaining_customize':2-self.batch_customizes_used,
            'pricing_model':'report3-V-table; tail50-and-per-upgrade25-assumptions'}
        return actions

    def step(self, candidate):
        rt = self.runtime
        kind = candidate.action_type
        if not candidate.available or rt.state['produce_points']+candidate.produce_point_delta < 0:
            raise ValueError('Unaffordable/stale interval action')
        if kind == 'interval_customize':
            _validate_customize_action(rt, candidate, self.customized_indices, 2)
        rt.state['produce_points'] += candidate.produce_point_delta
        if kind == 'interval_finish':
            rt.state['hif_interval_used'] = True
            rt.pre_audition_phase = 'weekly'
            return rt._close_week(0.0, {'action_type':kind}, {})
        if kind == 'interval_reroll':
            self.refresh_count += 1
            self._refresh()
        elif kind == 'interval_recover':
            rt.state['stamina'] = min(rt.state['stamina']+2, rt.state['max_stamina'])
        elif kind == 'interval_upgrade':
            rt._upgrade_matching_cards('', 1, source_action_type=kind, select_targets=True, minimum_count=1)
            self.upgrades_used += 1
            self.batch_upgrade_used += 1
        elif kind == 'interval_customize':
            from ...idol_config import apply_card_customizations
            card = rt.deck[candidate.target_deck_index]
            updated = apply_card_customizations(rt.repository, card, tuple(candidate.customize_ids))
            rt.deck[candidate.target_deck_index] = updated
            rt._dispatch_produce_item_phase('ProducePhaseType_CustomizeProduceCard', card=updated)
            self.customized_indices.add(candidate.target_deck_index)
            self.batch_customizes_used = len(self.customized_indices)
        elif kind in {'interval_buy_card','interval_buy_drink','interval_change'}:
            if kind == 'interval_change':
                targets = rt._matching_deck_indices('p_card_search-active_skill-mental_skill-deck_all')
                i = targets[rt.choose_produce_option('interval_change_target', [{'deck_index':i,'card':rt.deck[i]} for i in targets])]
                # Select Change preserves the target's upgrade level, but removes customization.
                level = int(rt.deck[i].get('upgradeCount') or 0)
                card = deepcopy(rt._lookup_card_row(candidate.resource_id,level))
                rt.deck[i] = card
                rt._dispatch_produce_item_phase('ProducePhaseType_ChangeProduceCard',card=card)
            else:
                rt._grant_resource(candidate.resource_type,candidate.resource_id,candidate.resource_level)
            self.inventory[candidate.slot_index].available = False
        else:
            raise ValueError(f'Unknown interval action: {kind}')
        rt._refresh_quality_scores()
        return 0.0, False, {'action_type':kind,'interval_version':self.VERSION}


class HifSpecialTraining:
    """Two distinct card slots; modifying a card more than once uses that same slot."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.customized_indices = set()

    def start(self):
        self.customized_indices = set()
        self.runtime.pre_audition_phase = 'hif_special_training'
        self.runtime._dispatch_produce_item_phase('ProducePhaseType_StartCustomize')

    def legal_actions(self):
        from .runtime import ProduceActionCandidate
        rt = self.runtime
        candidates = []
        capacity = int(rt.produce_setting.get('customizeProduceCardCount') or 2)
        for i, card in enumerate(rt.deck):
            if len(self.customized_indices)>=capacity and i not in self.customized_indices:
                continue
            for option in _legal_customize_options(rt, card):
                price = math.floor(float(option.get('producePoint') or 0)*max(0,1-rt.state.get('customize_point_discount',0)))
                candidates.append(ProduceActionCandidate(label='定制 '+card['name'],action_type='special_customize',
                    effect_types=[],produce_effect_ids=[],produce_point_delta=-price,target_deck_index=i,
                    customize_ids=(option['id'],),available=rt.state['produce_points']>=price))
        candidates.append(ProduceActionCandidate(label='结束特别指导',action_type='special_finish',effect_types=[],produce_effect_ids=[]))
        rt._candidates = candidates
        rt.state['special_training_remaining_cards'] = max(0,capacity-len(self.customized_indices))
        return candidates

    def step(self, candidate):
        rt = self.runtime
        if candidate.action_type == 'special_finish':
            rt.pre_audition_phase = 'weekly'
            return rt._close_week(0.0,{'action_type':candidate.action_type},{})
        if candidate.action_type != 'special_customize' or rt.state['produce_points']+candidate.produce_point_delta<0:
            raise ValueError('Invalid special training action')
        _validate_customize_action(rt, candidate, self.customized_indices,
                                   int(rt.produce_setting.get('customizeProduceCardCount') or 2))
        from ...idol_config import apply_card_customizations
        rt.state['produce_points'] += candidate.produce_point_delta
        card = rt.deck[candidate.target_deck_index]
        card = apply_card_customizations(rt.repository,card,tuple(candidate.customize_ids))
        rt.deck[candidate.target_deck_index] = card
        self.customized_indices.add(candidate.target_deck_index)
        rt._dispatch_produce_item_phase('ProducePhaseType_CustomizeProduceCard',card=card)
        rt._refresh_quality_scores()
        return 0.0,False,{'action_type':candidate.action_type}
