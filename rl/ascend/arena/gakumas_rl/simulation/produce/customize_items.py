"""Execute HIF custom P items from their concrete master-data configuration."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from .customize_item_rewards import CustomizeItemRewards
from .items import RuntimeExamStatusEnchantSpec


class CustomizeItemSupport:
    def __init__(self, runtime):
        self.runtime = runtime
        self.table = runtime.repository.load_table('ProduceCustomizeItem')
        self.relationships = runtime.repository.load_table('ProduceCustomizeItemRelationship')
        self.rewards = CustomizeItemRewards(self)
        self.reset()

    def reset(self):
        self.item_id = ''
        self.fire_count = 0
        self.cooldown_remaining = 0
        self.history: list[dict[str, Any]] = []

    def offer_upgrades(self):
        """Show at most three legal children; unknown display weights are explicit."""
        rows = self.options(upgrade=True)
        if len(rows) <= 3:
            return rows
        chooser = getattr(self.runtime, 'customize_item_offer_selector', None)
        request = {'parent_id': self.item_id, 'options': deepcopy(rows), 'count': 3}
        if chooser:
            result = chooser(deepcopy(request))
            ids = result['item_ids']
            model = result.get('model', 'caller-supplied')
            evidence = result.get('evidence', 'configured')
        else:
            ids = [rows[int(i)]['id'] for i in self.runtime.np_random.choice(len(rows), 3, replace=False)]
            model = 'uniform-without-replacement-placeholder/v1'
            evidence = 'unknown'
        by_id = {row['id']: row for row in rows}
        if len(ids) != 3 or len(set(ids)) != 3 or any(i not in by_id for i in ids):
            raise ValueError('Custom P item offer must contain three distinct legal children')
        self.history.append({'kind': 'upgrade_offer', 'parent_id': self.item_id,
                             'offered_ids': list(ids), 'model': model, 'evidence': evidence})
        return [deepcopy(by_id[i]) for i in ids]

    @property
    def row(self):
        return self.table.first(self.item_id) if self.item_id else None

    def options(self, *, upgrade=False):
        if upgrade:
            allowed = {r['childProduceCustomizeItemId'] for r in self.relationships.rows
                       if r['parentProduceCustomizeItemId'] == self.item_id}
            rows = [r for r in self.table.rows if r['id'] in allowed]
        else:
            rows = [r for r in self.table.rows if r.get('isBase')]
        plan = (self.runtime.idol_loadout.stat_profile.plan_type
                if self.runtime.idol_loadout is not None else None)
        return [deepcopy(r) for r in rows
                if not plan or r.get('planType') in (plan, 'ProducePlanType_Common')]

    def acquire(self, item_id='', *, restoring=False):
        if not item_id:
            options = self.options()
            if not options:
                raise ValueError('No compatible custom P item in master data')
            item_id = options[self.runtime.choose_produce_option('customize_item', options)]['id']
        row = self.table.first(item_id)
        if row is None:
            raise KeyError(f'Unknown custom P item: {item_id}')
        plan = (self.runtime.idol_loadout.stat_profile.plan_type
                if self.runtime.idol_loadout is not None else None)
        if plan and row.get('planType') not in (plan, 'ProducePlanType_Common'):
            raise ValueError(f'Custom P item plan mismatch: {item_id}')
        self.item_id = item_id
        self.fire_count = self.cooldown_remaining = 0
        tier = 1 if row.get('isBase') else 3 if row.get('isTerminal') else 2
        self.runtime.state['customize_item_tier'] = float(tier)
        self.runtime.state['customize_item_id'] = item_id
        if not restoring:
            self.history.append({'kind': 'acquire', 'id': item_id})

    def upgrade(self):
        if not self.item_id:
            raise ValueError('Cannot upgrade a custom P item without its configuration ID')
        options = self.offer_upgrades()
        if not options:
            raise ValueError(f'Custom P item has no upgrade: {self.item_id}')
        previous = self.item_id
        index = self.runtime.choose_produce_option('customize_item_upgrade', options)
        self.acquire(options[index]['id'])
        self.history.append({'kind': 'upgrade', 'from': previous, 'to': self.item_id})

    def dispatch(self, phase_type, context):
        row = self.row
        if not row or not row.get('produceTriggerId'):
            return
        trigger = self.runtime.produce_item_interpreter.parse_trigger(row['produceTriggerId'])
        # This trigger ID is reused by the HIF custom-item master. Its historical
        # NIA suffix is not a restriction on these HIF-exclusive configurations.
        if (row['produceTriggerId'] == 'p_trigger-end_present-for_nia_master'
                and self.runtime.scenario.route_type in ('hif_selection', 'hif_final')):
            trigger = replace(trigger, scenario_tag='')
        if not self.runtime.produce_item_interpreter.trigger_matches(
            trigger, phase_type=phase_type, scenario=self.runtime.scenario,
            state=self.runtime.state, deck=self.runtime.deck, context=context,
        ):
            return
        limit = int(row.get('produceEffectTriggerCount') or 0)
        if limit > 0 and self.fire_count >= limit:
            return
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return
        # Consume the activation before executing rewards, which may trigger more phases.
        self.fire_count += 1
        self.cooldown_remaining = max(int(row.get('produceEffectTriggerInterval') or 0) - 1, 0)
        self.history.append({'kind': 'trigger', 'id': self.item_id, 'phase': phase_type,
                             'fire_count': self.fire_count})
        from gakumas_arena.produce.public_state import public_resolution_frame
        effect_ids = list(row.get('produceEffectIds') or ())
        with public_resolution_frame(self.runtime, kind='customize_item_listener',
                item_id=self.item_id, effect_ids=effect_ids, effect_index=0,
                counter_committed=True) as frame:
            for index, effect_id in enumerate(effect_ids):
                frame['effect_index'] = index
                effect = self.runtime.produce_effects.first(effect_id)
                if effect is None:
                    raise KeyError(f'Missing custom P item effect: {effect_id}')
                if self._apply_special_effect(effect):
                    continue
                self.runtime._apply_produce_effect(
                    effect, source_action_type='customize_item', source='produce_item',
                    source_identity=self.item_id,
                )

    def _apply_special_effect(self, effect):
        kind = effect.get('produceEffectType')
        if kind in {'ProduceEffectType_ExamStatusEnchant', 'ProduceEffectType_ExamPermanentAuditionStatusEnchant'}:
            spec = RuntimeExamStatusEnchantSpec(
                effect['produceExamStatusEnchantId'], source='produce_item', source_identity=self.item_id,
                duration_scope=('next_audition' if kind == 'ProduceEffectType_ExamStatusEnchant' else 'persistent'))
            self.runtime.exam_status_enchant_specs.append(spec)
            self.runtime.exam_status_enchant_ids.append(spec.enchant_id)
            return True
        if kind in {'ProduceEffectType_ShopProduceCardUpgradePriceDiscountMultiple',
                    'ProduceEffectType_ShopProduceCardDeletePriceDiscountMultiple'}:
            field = 'shop_upgrade_discount' if 'Upgrade' in kind else 'shop_delete_discount'
            self.runtime.state[field] = float(self.runtime.state.get(field) or 0) - self.runtime._sample_effect_value(effect) / 1000
            return True
        return self.rewards.apply(effect)

    def complete_audition(self):
        """Consume next-exam buffs only after a completed exam, never on preview."""
        specs = self.runtime.exam_status_enchant_specs
        consumed = [s for s in specs if s.duration_scope == 'next_audition']
        self.runtime.exam_status_enchant_specs = [s for s in specs if s.duration_scope != 'next_audition']
        self.runtime.exam_status_enchant_ids = [s.enchant_id for s in self.runtime.exam_status_enchant_specs]
        if consumed:
            self.history.append({'kind': 'consume_next_audition', 'count': len(consumed),
                                 'enchant_ids': [s.enchant_id for s in consumed]})
        return len(consumed)

    def export(self):
        return {'item_id': self.item_id, 'fire_count': self.fire_count,
                'cooldown_remaining': self.cooldown_remaining, 'history': deepcopy(self.history)}

    def restore(self, data):
        self.reset()
        if not data.get('item_id'):
            return
        self.acquire(data['item_id'], restoring=True)
        for key in ('fire_count', 'cooldown_remaining'):
            value = data.get(key, 0)
            if type(value) is not int or value < 0:
                raise ValueError(f'Invalid custom P item {key}')
            setattr(self, key, value)
        limit = int(self.row.get('produceEffectTriggerCount') or 0)
        if limit > 0 and self.fire_count > limit:
            raise ValueError('Custom P item fire_count exceeds its configured limit')
        self.history = deepcopy(data.get('history', []))
