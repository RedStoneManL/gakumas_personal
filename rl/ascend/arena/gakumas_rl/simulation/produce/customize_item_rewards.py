"""Source-preserving rewards for HIF custom P items.

Unpublished membership/weights are a replaceable model, never game probabilities.
The callback receives a legal universe, not a claim that it is the exact source pool.
"""

from __future__ import annotations

from copy import deepcopy
import re


class CustomizeItemRewards:
    def __init__(self, support):
        self.support = support

    @property
    def runtime(self):
        return self.support.runtime

    @staticmethod
    def pool_id(effect):
        match = re.search(r'(p_rd-.+?)(?:-p_card_search-|-(?:random|select)-\d|$)', effect['id'])
        if not match:
            raise ValueError(f'Custom P item reward has no source pool: {effect["id"]}')
        return match.group(1)

    def _legal_rows(self, resource_type, upgrade=0):
        rt = self.runtime
        if resource_type == 'drink':
            return [deepcopy(row) for row in rt.repository.produce_drinks.rows
                    if not row.get('libraryHidden') and row.get('planType') in rt._allowed_plan_types()]
        result = {}
        for row in rt._selection_card_pool():
            card = rt.repository.card_row_by_upgrade(row['id'], upgrade, fallback_to_canonical=False)
            if card is None:
                continue
            if int(card.get('unlockProducerLevel') or 0) > int(rt.state.get('producer_level') or 0):
                continue
            result[card['id']] = deepcopy(card)
        return list(result.values())

    def sample(self, effect, resource_type, *, count, replace, upgrade=0):
        rt = self.runtime
        rows = self._legal_rows(resource_type, upgrade)
        if not rows:
            self.support.history.append({'kind': 'reward_unavailable', 'effect_id': effect['id'],
                                         'resource_type': resource_type})
            return []
        count = count if replace else min(count, len(rows))
        request = {'pool_id': self.pool_id(effect), 'resource_type': resource_type,
                   'count': count, 'replace': replace, 'legal_candidates': deepcopy(rows),
                   'effect_id': effect['id'], 'customize_item_id': self.support.item_id,
                   'pick_range': 'select' if effect.get('pickRangeType') == 'ProducePickRangeType_Select' else 'random'}
        selector = getattr(rt, 'customize_item_reward_selector', None)
        if selector:
            result = selector(deepcopy(request))
        else:
            indices = rt.np_random.choice(len(rows), count, replace=replace)
            result = {'resource_ids': [rows[int(i)]['id'] for i in indices],
                      'model': 'custom-item-pool-uniform-placeholder/v1',
                      'evidence': 'unknown', 'membership_known': False}
        by_id = {row['id']: row for row in rows}
        ids = result.get('resource_ids', [])
        if (len(ids) > count or any(i not in by_id for i in ids)
                or not replace and len(set(ids)) != len(ids)):
            raise ValueError(f'Invalid custom P item reward sample for {request["pool_id"]}')
        self.support.history.append({'kind': 'reward_sample', 'pool_id': request['pool_id'],
            'effect_id': effect['id'], 'resource_ids': list(ids),
            'model': result.get('model', 'caller-supplied'), 'evidence': result.get('evidence', 'configured'),
            'membership_known': result.get('membership_known', False),
            **({'empty_reason': result['empty_reason']} if result.get('empty_reason') else {})})
        return [deepcopy(by_id[i]) for i in ids]

    def _target(self, effect, operation):
        rt = self.runtime
        indices = rt._matching_deck_indices(str(effect.get('produceCardSearchId') or ''))
        # Master explicitly excludes duplication for unique/legend cards. A
        # Trouble card is legal only when the effect search itself includes it.
        if operation == 'duplicate':
            indices = [i for i in indices if not rt.deck[i].get('noDeckDuplication')
                       and rt.deck[i].get('rarity') != 'ProduceCardRarity_Legend']
        if not indices:
            self.support.history.append({'kind': 'target_unavailable', 'effect_id': effect['id']})
            return None
        options = [{'deck_index': i, 'card': deepcopy(rt.deck[i])} for i in indices]
        selected = rt.choose_produce_option(f'customize_item_{operation}_target', options, effect_id=effect['id'])
        return indices[selected]

    def _choose_reward(self, effect, resource_type, upgrade=0):
        is_select = effect.get('pickRangeType') == 'ProducePickRangeType_Select'
        candidates = self.sample(effect, resource_type, count=3 if is_select else 1,
                                 replace=not is_select, upgrade=upgrade)
        if not candidates:
            return None
        if is_select and resource_type == 'card' and getattr(self.runtime, 'hif_sampling_kernel', None):
            return self.runtime.hif_sampling_kernel.choose_reward(self.pool_id(effect), candidates,
                resample=lambda:self.sample(effect,resource_type,count=3,replace=False,upgrade=upgrade),
                choice_kind=f'customize_item_{resource_type}_reward',effect_id=effect['id'])
        options = candidates + [{'skip': True}] if is_select else candidates
        index = (self.runtime.choose_produce_option(f'customize_item_{resource_type}_reward', options,
                 pool_id=self.pool_id(effect), effect_id=effect['id']) if is_select else 0)
        return candidates[index] if index < len(candidates) else None

    def apply(self, effect):
        kind = effect.get('produceEffectType')
        rt = self.runtime
        if kind == 'ProduceEffectType_ProduceRewardSet':
            resource_type = {'ProduceResourceType_ProduceDrink': 'drink',
                             'ProduceResourceType_ProduceCard': 'card'}.get(effect.get('produceResourceType'))
            if resource_type is None:
                return False
            count = int(effect.get('pickCountMax') or effect.get('pickCountMin') or 1)
            upgrade = 1 if '-upgrade_1-' in effect['id'] else 0
            for _ in range(count):
                row = self._choose_reward(effect, resource_type, upgrade)
                if row is None:
                    continue
                if resource_type == 'drink':
                    rt.drinks.append(row)
                    rt._dispatch_produce_item_phase('ProducePhaseType_GetProduceDrink')
                else:
                    rt._grant_resource('ProduceResourceType_ProduceCard', row['id'], upgrade)
            rt._trim_drinks()
            return True
        if kind == 'ProduceEffectType_ProduceCardChangeSelect':
            index = self._target(effect, 'change')
            if index is None:
                return True
            # Select Change inherits the selected card's upgrade stage. Pool
            # suffixes describe offered card definitions, not a downgrade cost.
            upgrade = int(rt.deck[index].get('upgradeCount') or 0)
            row = self._choose_reward(effect, 'card', upgrade)
            if row is not None:
                old = rt.deck[index]
                if 'instance_id' in old:
                    row['instance_id'] = old['instance_id']
                rt.deck[index] = row
                if row.get('rarity') == 'ProduceCardRarity_Legend':
                    rt.legend_seen_card_ids.add(row['id'])
                rt._dispatch_produce_item_phase('ProducePhaseType_ChangeProduceCard', card=row)
            return True
        if kind not in {'ProduceEffectType_ProduceCardDelete', 'ProduceEffectType_ProduceCardDuplicate'}:
            return False
        operation = 'delete' if kind.endswith('Delete') else 'duplicate'
        for _ in range(int(effect.get('pickCountMax') or effect.get('pickCountMin') or 1)):
            index = self._target(effect, operation)
            if index is None:
                break
            if operation == 'delete':
                row = rt.deck.pop(index)
                rt._dispatch_produce_item_phase('ProducePhaseType_DeleteProduceCard', card=row)
            else:
                row = deepcopy(rt.deck[index])
                # A copy is a new card instance, even though its learned effects
                # and customizations are copied. Leave ID allocation to the bridge.
                row.pop('instance_id', None)
                rt.deck.append(row)
                rt._dispatch_produce_item_phase('ProducePhaseType_GetProduceCard', card=row)
        return True
