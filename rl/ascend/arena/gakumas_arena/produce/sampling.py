"""Versioned source-specific planning kernels. Unknown weights stay assumptions."""
from copy import deepcopy
import math


class HifSamplingKernel:
    VERSION = 'hif-report3-source-pools/1'

    def __init__(self, runtime, pools=None):
        self.runtime = runtime
        self.pools = deepcopy(pools or {})
        self.history = []

    def __call__(self, request):
        """Custom item adapter; return exactly the sampled IDs, never choose for RL."""
        pool_id = request['pool_id']
        config = self.pools.get(pool_id, {})
        rows = request['legal_candidates']
        resource_type = request['resource_type']
        is_card = resource_type in ('card', 'ProduceResourceType_ProduceCard')
        if is_card:
            from .initial_deck import reserved_memory_card_ids
            excluded = set(self.runtime.state.get('excluded_card_ids', []))
            excluded.update(reserved_memory_card_ids(self.runtime))
            owned_ids = {r['id'] for r in self.runtime.deck}
            rows = [r for r in rows if r['id'] not in excluded
                    and not (r.get('noDeckDuplication') and r['id'] in owned_ids)]
        by_id = {r['id']: r for r in rows}
        configured = config.get('weights')
        if configured is not None:
            catalog = (self.runtime.repository.produce_drinks if not is_card
                       else self.runtime.repository.produce_cards)
            if any(catalog.first(k) is None for k in configured):
                raise ValueError(f'Configured pool has unknown membership: {pool_id}')
            all_weights = [float(w) for w in configured.values()]
            if any(not math.isfinite(w) or w < 0 for w in all_weights) or (all_weights and sum(all_weights) <= 0):
                raise ValueError(f'Invalid pool weights: {pool_id}')
            # Known pool members can become illegal (already owned no-dup card, PLv, plan).
            resolved_weights = {}
            for card_id, weight in configured.items():
                if is_card:
                    from .card_switches import active_card_id
                    card_id = active_card_id(self.runtime, card_id)
                resolved_weights[card_id] = resolved_weights.get(card_id, 0) + float(weight)
            ids = [k for k in resolved_weights if k in by_id]
            weights = [resolved_weights[k] for k in ids]
        else:
            ids = list(by_id)
            weights = [1.0] * len(ids)
        positive = [(i, w) for i, w in zip(ids, weights) if w > 0]
        count = int(request.get('count', 3))
        if count < 0:
            raise ValueError(f'Negative offer count for {pool_id}')
        replace = bool(request.get('replace', False))
        result = {'resource_ids': [],
                  'model': config.get('model', 'configured-weights' if configured is not None else 'legal-pool-uniform-placeholder/v1'),
                  'evidence': config.get('evidence', 'configured' if configured is not None else 'unknown'),
                  'membership_known': bool(config.get('membership_known', False))}
        if not positive or count == 0:
            result['empty_reason'] = ('requested_zero' if count == 0 else
                                      'configured_empty_pool' if configured == {} else 'no_legal_candidates')
        else:
            ids, weights = map(list, zip(*positive))
            if not replace:
                count = min(count, len(ids))
            probabilities = [w / sum(weights) for w in weights]
            indices = self.runtime.np_random.choice(len(ids), size=count, replace=replace, p=probabilities)
            result['resource_ids'] = [ids[int(i)] for i in indices]
        self.history.append({'offer_set_id': len(self.history), 'pool_id': pool_id,
                             'resource_type': request['resource_type'], 'effect_id': request.get('effect_id'),
                             **deepcopy(result)})
        return result

    def reward_controls(self, pool_id):
        """Source-specific availability; actual server UI scope is configurable."""
        config = self.pools.get(pool_id, {})
        state = self.runtime.state
        return {
            'reroll': bool(config.get('allow_reroll', True)) and float(state.get('card_reward_rerolls_used', 0)) < float(state.get('card_select_reroll_count_bonus', 0)),
            'exclude': bool(config.get('allow_exclude', True)) and float(state.get('excludes_used', 0)) < float(state.get('exclude_count_bonus', 0)),
        }

    def exclude(self, pool_id, card_id):
        if not self.reward_controls(pool_id)['exclude']:
            raise ValueError('No available candidate-exclusion allowance')
        self.runtime.state['excludes_used'] = int(self.runtime.state.get('excludes_used', 0)) + 1
        excluded = self.runtime.state.setdefault('excluded_card_ids', [])
        if card_id not in excluded:
            excluded.append(card_id)
        self.history.append({'kind':'exclude_candidate','pool_id':pool_id,'resource_id':card_id,
            'scope':'produce-card-id-planning-assumption','permanent_deck_changed':False})

    def choose_reward(self, pool_id, rows, *, resample, choice_kind='card_reward', **context):
        """Inline choice, reroll and candidate removal, sharing whole-run budgets."""
        rt = self.runtime
        rows = deepcopy(rows)
        while True:
            controls = self.reward_controls(pool_id)
            options = deepcopy(rows)
            if controls['reroll']:
                options.append({'control':'reroll','label':'重新抽选'})
            if controls['exclude']:
                options.extend({'control':'exclude','resource_id':r['id'],'label':'从候选除去 '+r.get('name',r['id'])} for r in rows)
            options.append({'skip':True})
            index = rt.choose_produce_option(choice_kind, options, pool_id=pool_id,
                reward_control_model='source-configured-allowances/v1', **context)
            option = options[index]
            if option.get('skip'):
                return None
            if option.get('control') == 'reroll':
                rt.state['card_reward_rerolls_used'] = int(rt.state.get('card_reward_rerolls_used', 0)) + 1
                self.history.append({'kind':'reroll_reward','pool_id':pool_id})
                rows = resample()
                latest = next((entry for entry in reversed(self.history)
                    if entry.get('pool_id') == pool_id and 'offer_set_id' in entry), None)
                if latest is not None:
                    context['offer_set_id'] = latest['offer_set_id']
                continue
            if option.get('control') == 'exclude':
                self.exclude(pool_id, option['resource_id'])
                rows = [r for r in rows if r['id'] != option['resource_id']]
                continue
            return deepcopy(rows[index])

    def candidates(self, pool_id, *, kind='card', count=3, upgraded=None, rarity=None, effect_id=None):
        rt = self.runtime
        if kind == 'drink':
            rows = [r for r in rt.repository.produce_drinks.rows
                    if not r.get('libraryHidden') and r.get('planType') in rt._allowed_plan_types()]
        else:
            rows = rt._selection_card_pool()
        if rarity:
            rows = [r for r in rows if r.get('rarity') in rarity]
        if kind == 'card' and upgraded is not None:
            rows = [v for r in rows if (v := rt._lookup_card_upgrade_row(r['id'], int(upgraded))) is not None]
        picked = self({'pool_id': pool_id, 'resource_type': kind, 'count': count,
                       'replace': False, 'legal_candidates': rows, 'effect_id': effect_id})
        by_id = {r['id']: r for r in rows}
        result = [deepcopy(by_id[i]) for i in picked['resource_ids']]
        if kind == 'card' and upgraded is None:
            probability = float(self.pools.get(pool_id, {}).get('upgrade_probability', 0.0))
            if not 0 <= probability <= 1:
                raise ValueError(f'Invalid upgrade probability for {pool_id}')
            for i, row in enumerate(result):
                level = 1 if rt.np_random.random() < probability else 0
                result[i] = deepcopy(rt._lookup_card_upgrade_row(row['id'], level) or row)
            self.history[-1]['upgrade_model'] = ('configured' if 'upgrade_probability' in self.pools.get(pool_id, {})
                                                 else 'unupgraded-placeholder')
        return result

    def grant(self, effect, *, source_action_type=''):
        from gakumas_rl.simulation.produce.event_rules import effect_pool_reference
        rt = self.runtime
        kind = 'drink' if effect.get('produceResourceType') == 'ProduceResourceType_ProduceDrink' else 'card'
        pool_id = effect_pool_reference(effect) or str(effect['id'])
        upgrade = 1 if '-upgrade_1' in pool_id else (0 if 'event_school-before_1st' in pool_id else None)
        count = max(int(effect.get('pickCountMax') or effect.get('pickCountMin') or 1), 1)
        is_select = effect.get('pickRangeType') == 'ProducePickRangeType_Select'
        for _ in range(count):
            if kind == 'card' and len(rt.deck) >= 99:
                self.history.append({'kind': 'reward_declined', 'pool_id': pool_id,
                    'effect_id': effect['id'], 'reason': 'card_capacity', 'capacity': 99})
                return
            rows = self.candidates(pool_id, kind=kind, count=3 if is_select else 1,
                                   upgraded=upgrade, effect_id=effect['id'])
            if not rows:
                # No replacement from a different source pool: a legal source
                # can be empty after equipment/plan/unique-card filtering.
                continue
            offer_set = len(self.history)-1
            if not is_select:
                row = rows[0]
            elif kind == 'card':
                row = self.choose_reward(pool_id, rows,
                    resample=lambda:self.candidates(pool_id,kind=kind,upgraded=upgrade,effect_id=effect['id']),
                    effect_id=effect['id'],offer_set_id=offer_set)
            else:
                picked = rt.choose_produce_option(kind+'_reward',rows+[{'skip':True}],pool_id=pool_id,
                    effect_id=effect['id'],offer_set_id=offer_set)
                row = rows[picked] if picked<len(rows) else None
            if row is None:
                self.history[-1]['resolution'] = 'declined_by_policy'
                continue
            self.history[-1]['resolution'] = 'accepted_by_policy' if is_select else 'automatic_random_grant'
            self.history[-1]['selected_resource_id'] = row['id']
            rt._grant_resource('ProduceResourceType_ProduceDrink' if kind == 'drink' else 'ProduceResourceType_ProduceCard',
                               row['id'], int(row.get('upgradeCount') or 0))

    def public_contract(self):
        return {'version': self.VERSION, 'official_reward_probabilities': False,
                'unconfigured_pool_model': 'legal-pool-uniform-placeholder/v1',
                'reward_control_model': 'source-configured-allowances/v1',
                'candidate_exclusion_scope': 'produce-card-id-planning-assumption',
                'card_switches': deepcopy(getattr(self.runtime,'hif_card_switch_settings',{})),
                'configured_pool_ids': sorted(self.pools),
                'offer_sets_generated': len(self.history)}
