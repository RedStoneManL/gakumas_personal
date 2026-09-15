"""Structured event catalogue and explicit event execution; no invented occurrence rates."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from .event_rules import event_option_costs, event_option_is_legal, option_contract, option_success_probability, support_occurrence_probability


class ProduceEventLibrary:
    def __init__(self, repository):
        self.repository = repository
        self.details = repository.load_table('ProduceStepEventDetail')
        self.suggestions = repository.load_table('ProduceStepEventSuggestion')
        self.support_links = repository.load_table('ProduceEventSupportCard')
        self.stories = repository.load_table('ProduceStory')
        self.groups = repository.load_table('ProduceStoryGroup')

    def _effects(self, ids):
        result = []
        for effect_id in ids or ():
            row = self.repository.produce_effects.first(effect_id)
            if row is None:
                raise KeyError(f'Missing event effect: {effect_id}')
            result.append(deepcopy(row))
        return result

    def suggestion(self, suggestion_id):
        row = self.suggestions.first(suggestion_id)
        if row is None:
            raise KeyError(f'Unknown event option: {suggestion_id}')
        return {**deepcopy(row), 'effects': self._effects(row.get('produceEffectIds')),
                'success_effects': self._effects(row.get('successProduceEffectIds')),
                'fail_effects': self._effects(row.get('failProduceEffectIds'))}

    def event(self, event_id, *, character_id=None):
        row = self.details.first(event_id)
        if row is None:
            raise KeyError(f'Unknown event: {event_id}')
        story_ids = [row['produceStoryId']] if row.get('produceStoryId') else []
        if row.get('produceStoryGroupId'):
            story_ids += [x['produceStoryId'] for x in self.groups.rows
                          if x['id'] == row['produceStoryGroupId']
                          and (not character_id or x.get('characterId') == character_id)]
        stories = [deepcopy(self.stories.first(s)) for s in story_ids if self.stories.first(s)]
        return {**deepcopy(row), 'stories': stories,
                'effects': self._effects(row.get('produceEffectIds')),
                'options': [self.suggestion(s) for s in row.get('produceStepEventSuggestionIds') or ()],
                'support_requirements': [deepcopy(x) for x in self.support_links.rows
                                         if x['produceStepEventDetailId'] == event_id]}

    def hif_event_ids(self, produce_id, *, kind=None, plan=None, pool_tag=None):
        """Explicit HIF-tagged activity/school rows, with stage/plan filtering."""
        if produce_id not in ('produce-007', 'produce-008'):
            raise ValueError('Expected HIF produce-007 or produce-008')
        tag = produce_id.replace('-', '_')
        rows = [r for r in self.details.rows if tag in r['id']]
        if kind:
            rows = [r for r in rows if r['eventType'] == f'ProduceEventType_{kind}']
        if plan:
            rows = [r for r in rows if not any(f'-plan{k}-' in r['id'] for k in (1, 2, 3))
                    or f'-{plan}-' in r['id']]
        if pool_tag:
            rows = [r for r in rows if pool_tag in r['id']]
        return [r['id'] for r in rows]

    def support_event_ids(self, support_card_id, level, *, completed=()):
        links = sorted((r for r in self.support_links.rows if r['supportCardId'] == support_card_id
                        and int(r['supportCardLevel']) <= level), key=lambda r: int(r['number']))
        return [r['produceStepEventDetailId'] for r in links
                if r['produceStepEventDetailId'] not in completed]

    def hif_fixed_event_catalog(self):
        """All HIF outing/class options, grouped by exact option-list aliases."""
        ids = [eid for produce_id in ('produce-007', 'produce-008')
               for kind in ('Activity', 'School')
               for eid in self.hif_event_ids(produce_id, kind=kind)]
        aliases = {}
        options = {}
        for eid in ids:
            event = self.event(eid)
            key = tuple(event.get('produceStepEventSuggestionIds') or ())
            aliases.setdefault(key, []).append(eid)
            for option in event['options']:
                options[option['id']] = option_contract(option)
        return {
            'schema_version': 'arena-hif-fixed-event-contracts/1',
            'event_count': len(ids), 'option_count': len(options),
            'always_successful_option_count': sum(bool(self.suggestions.first(s).get('alwaysSuccessful')) for s in options),
            'event_ids': ids,
            'alias_groups': [{'option_ids': list(key), 'event_ids': members} for key, members in aliases.items()],
            'options': options,
            'occurrence_weights': None,
            'note': 'Aliases merge narrative text only; pool bindings and option order remain distinct.',
        }

    def summary(self):
        missing = []
        for row in self.details.rows:
            for s in row.get('produceStepEventSuggestionIds') or ():
                if self.suggestions.first(s) is None:
                    missing.append({'from': row['id'], 'suggestion': s})
        for row in (*self.details.rows, *self.suggestions.rows):
            for field in ('produceEffectIds', 'successProduceEffectIds', 'failProduceEffectIds'):
                for effect_id in row.get(field) or ():
                    if self.repository.produce_effects.first(effect_id) is None:
                        missing.append({'from': row['id'], 'effect': effect_id})
        for row in self.suggestions.rows:
            if row.get('stepId') and str(row.get('stepType')).startswith('ProduceStepType_Event'):
                if self.details.first(row['stepId']) is None:
                    missing.append({'from': row['id'], 'next_event': row['stepId']})
            for branch in ('success', 'fail'):
                target = row.get(f'{branch}StepId')
                if target and self.details.first(target) is None:
                    missing.append({'from': row['id'], 'next_event': target})
        return {'events': len(self.details.rows), 'options': len(self.suggestions.rows),
                'support_event_links': len(self.support_links.rows),
                'support_cards_with_events': len({r['supportCardId'] for r in self.support_links.rows}),
                'event_types': dict(Counter(r['eventType'] for r in self.details.rows)),
                'hif_selection_explicit_events': len(self.hif_event_ids('produce-007')),
                'hif_final_explicit_events': len(self.hif_event_ids('produce-008')),
                'missing_references': missing,
                'occurrence_probability_source': None,
                'note': 'Tagged row counts are not unique stories or occurrence probabilities.'}

    def export(self, path):
        """Write a compact, reference-preserving catalogue for RL/offline inspection."""
        def compact(row):
            return {k: deepcopy(v) for k, v in row.items() if 'description' not in k.lower()}
        payload = {
            'schema_version': 'arena-produce-events/1', 'summary': self.summary(),
            'events': {r['id']: compact(r) for r in self.details.rows},
            'options': {r['id']: compact(r) for r in self.suggestions.rows},
            'produce_effects': {r['id']: compact(r) for r in self.repository.produce_effects.rows},
            'support_links': [compact(r) for r in self.support_links.rows],
            'support_cards': {r['id']: compact(r) for r in self.repository.load_table('SupportCard').rows},
            'stories': {r['id']: compact(r) for r in self.stories.rows},
            'story_groups': [compact(r) for r in self.groups.rows],
            'customize_items': {r['id']: compact(r) for r in self.repository.load_table('ProduceCustomizeItem').rows},
            'customize_item_relationships': [compact(r) for r in self.repository.load_table('ProduceCustomizeItemRelationship').rows],
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        payload['content_sha256'] = hashlib.sha256(encoded).hexdigest()
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return target


class ProduceEventSupport:
    def __init__(self, runtime):
        self.runtime = runtime
        self.library = ProduceEventLibrary(runtime.repository)
        self.completed: list[str] = []
        self.history: list[dict] = []
        self.occurrence_history: list[dict] = []

    def reset(self):
        self.completed = []
        self.history = []
        self.occurrence_history = []

    def sample_support_events(self, context):
        """One daily support event under an explicit, configurable planning model.

        Default: a global Bernoulli trial followed by weighted eligible selection.
        Per-event probabilities/modifiers opt into independent trials followed by
        at most one weighted winner. Neither competition rule is an official rate.
        """
        rt = self.runtime
        config = getattr(rt, 'hif_research_config', {})
        day = int(context['day_index'])
        eligible = self.eligible_support_events()
        allowed_days = config.get('support_event_days')
        if allowed_days is not None and day not in allowed_days:
            eligible = []
        base = config.get('support_event_probability', 0.25)
        adjustment = float(config.get('support_event_probability_up_permyriad', 0)) + float(
            rt.state.get('support_event_probability_up_permyriad', 0))
        chance = support_occurrence_probability(base, adjustment)
        overrides = config.get('support_event_probabilities', {})
        per_event = config.get('support_event_probability_up_permyriad_by_event', {})
        per_card = config.get('support_event_probability_up_permyriad_by_card', {})
        weight_config = config.get('support_event_weights', {})
        independent = bool(overrides or per_event or per_card)
        model = 'independent-events-choose-one/v1' if independent else 'global-then-weighted/v1'
        candidates, probabilities, weights = [], {}, {}
        for eid in eligible:
            card_id = self.library.details.first(eid).get('supportCardId', '')
            p = support_occurrence_probability(overrides.get(eid, base), adjustment +
                float(per_event.get(eid, 0)) + float(per_card.get(card_id, 0)))
            weight = float(weight_config.get(eid, weight_config.get(card_id, 1)))
            if not math.isfinite(weight) or weight < 0:
                raise ValueError(f'Invalid support event selection weight: {eid}')
            probabilities[eid], weights[eid] = p, weight
            if weight and (not independent or p == 1 or (p > 0 and rt.np_random.random() < p)):
                candidates.append(eid)
        selected = []
        passed = independent or chance == 1 or (chance > 0 and bool(candidates) and rt.np_random.random() < chance)
        if passed and candidates:
            total = sum(weights[eid] for eid in candidates)
            index = int(rt.np_random.choice(len(candidates), p=[weights[eid] / total for eid in candidates]))
            selected = [candidates[index]]
        self.occurrence_history.append({'day_index': day, 'model': model,
            'evidence': 'configured-planning-assumption', 'global_probability': chance,
            'eligible_event_ids': eligible, 'event_probabilities': probabilities,
            'selection_weights': weights, 'selected_event_ids': selected})
        return selected

    def eligible_support_events(self):
        result = []
        for support in self.runtime.selected_support_cards:
            ids = self.library.support_event_ids(support.support_card_id, support.support_card_level,
                                                 completed=self.completed)
            # Keep each support card's next unlocked event in sequence.
            if ids:
                result.append(ids[0])
        return result

    def _support_sources(self, event_id, *, repeat):
        """Check ownership, level and predecessor completion even for replay."""
        result = []
        for support in self.runtime.selected_support_cards:
            ids = self.library.support_event_ids(support.support_card_id, support.support_card_level)
            if event_id not in ids:
                continue
            predecessors = ids[:ids.index(event_id)]
            if any(eid not in self.completed for eid in predecessors):
                continue
            if event_id in self.completed and not repeat:
                continue
            result.append({'support_card_id': support.support_card_id,
                           'support_card_level': support.support_card_level})
        return result

    def execute(self, event_id, *, option_index=None, repeat=False, _ancestors=()):
        """Resolve an explicitly scheduled event without advancing the produce day."""
        rt = self.runtime
        if event_id in _ancestors or len(_ancestors) >= 32:
            raise ValueError(f'Cyclic or excessive event chain: {event_id}')
        event = self.library.event(event_id)
        support_sources = []
        if event['eventType'] == 'ProduceEventType_SupportCard':
            support_sources = self._support_sources(event_id, repeat=repeat)
            if not support_sources:
                raise ValueError(f'Support event locked, out of sequence, or already completed: {event_id}')
        elif event_id in self.completed and not repeat:
            raise ValueError(f'Event already completed: {event_id}')
        options = event['options']
        if options:
            costs = [event_option_costs(o, rt.state, event['eventType']) for o in options]
            legal = [i for i, o in enumerate(options)
                     if event_option_is_legal(o, rt.state, event['eventType'],
                         deck_count=len(rt.deck) if getattr(rt, 'hif_ruleset_version', None) else None)]
            if not legal:
                raise ValueError(f'No affordable event option: {event_id}')
            if option_index is None:
                option_index = legal[rt.choose_produce_option(
                    'event_option', [options[i] for i in legal], event_id=event_id)]
            if type(option_index) is not int or option_index not in legal:
                raise ValueError(f'Invalid event option: {option_index}')
            option = options[option_index]
            # Validate before any event effect can mutate the runtime.
            probability = option_success_probability(option)
            for type_key, id_key in (('stepType', 'stepId'), ('successStepType', 'successStepId'), ('failStepType', 'failStepId')):
                if option.get(id_key) and not str(option.get(type_key)).startswith('ProduceStepType_Event'):
                    raise ValueError(f'Event option needs a non-event stage runner: {option["id"]}/{option[type_key]}')
        elif option_index is not None:
            raise ValueError('This event has no choices')
        event_kind = event['eventType'].removeprefix('ProduceEventType_')
        source = {'SupportCard': 'support_event', 'School': 'school_class',
                  'Activity': 'activity', 'Business': 'business'}.get(event_kind, 'event')
        rt._apply_effect_rows(event.get('produceEffectIds') or [], source_action_type=source)
        success = True
        next_event_id = None
        if options:
            option = options[option_index]
            rt.state['stamina'] -= costs[option_index]['stamina']
            rt.state['produce_points'] -= costs[option_index]['produce_points']
            # Trouble is a header cost/acquisition, paid before the option's
            # Select Change or rewards; its GetProduceCard hooks fire here.
            if option.get('produceCardId'):
                rt._grant_resource('ProduceResourceType_ProduceCard', option['produceCardId'],
                                   int(option.get('produceCardUpgradeCount') or 0))
            rt._apply_effect_rows(option.get('produceEffectIds') or [], source_action_type=source)
            if 0.0 < probability < 1.0:
                success = rt.np_random.random() < probability
            else:
                success = probability == 1.0
            rt._apply_effect_rows(option.get('successProduceEffectIds' if success else 'failProduceEffectIds') or [],
                                  source_action_type=source)
            next_event_id = option.get('stepId') or option.get('successStepId' if success else 'failStepId')
        result = {'event_id': event_id, 'option_index': option_index, 'success': success,
                  'step': int(rt.state.get('step') or 0)}
        if support_sources:
            result['support_sources'] = support_sources
        if options:
            result['header_costs'] = deepcopy(costs[option_index])
            result['success_probability'] = probability
            result['option_contract'] = option_contract(options[option_index])
        self.completed.append(event_id)
        self.history.append(result)
        if next_event_id:
            result['next_event_id'] = next_event_id
            self.execute(next_event_id, _ancestors=(*_ancestors, event_id))
        if not _ancestors and event_kind in ('School', 'Activity', 'Business'):
            rt._dispatch_produce_item_phase(f'ProducePhaseType_EndStepEvent{event_kind}', action_type=source)
        rt._trim_drinks()
        rt._refresh_quality_scores()
        return deepcopy(result)
