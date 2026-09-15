"""Effect/choice based event identities, independent of story text and character art."""
from copy import deepcopy
import hashlib
import json
import re
from pathlib import Path

from .events import ProduceEventLibrary
from .event_rules import effect_pool_reference


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


class ProduceEventTemplates:
    def __init__(self, repository):
        self.repository = repository
        self.library = ProduceEventLibrary(repository)
        self._cache = {}

    def effect(self, effect_id, *, parameterize_hif_pools=False):
        row = self.repository.produce_effects.first(effect_id)
        if row is None:
            raise KeyError(effect_id)
        result = {k: deepcopy(v) for k, v in row.items()
                  if k != 'id' and 'description' not in k.lower()}
        # These rows encode the reward-set reference only in their own ID.
        # Never merge different reward pools merely because their numeric fields match.
        if row['produceEffectType'] == 'ProduceEffectType_ProduceRewardSet':
            result['reward_pool_reference'] = effect_id
            if parameterize_hif_pools and '-event_activity-' in effect_id and any(
                    code in effect_id for code in ('produce_007', 'produce_008')):
                role = re.sub(r'^before_(?:2nd|3rd)-', '', effect_id.split('-event_activity-', 1)[1])
                result['reward_pool_reference'] = '$hif_outing_pool:' + role
        elif effect_pool_reference(row):
            # Select Change also stores its destination reward pool in its ID.
            # Omitting it wrongly merges the later Sense/Logic/Anomaly classes.
            result['reward_pool_reference'] = effect_pool_reference(row)
        return result

    def program(self, event_id, *, parameterize_hif_pools=False, _ancestors=()):
        key = event_id, parameterize_hif_pools
        if event_id in _ancestors:
            raise ValueError(f'Cyclic event definition: {event_id}')
        if key in self._cache:
            return deepcopy(self._cache[key])
        row = self.library.details.first(event_id)
        if row is None:
            raise KeyError(event_id)
        def effects(ids):
            return [self.effect(e, parameterize_hif_pools=parameterize_hif_pools) for e in ids or ()]
        options = []
        for sid in row.get('produceStepEventSuggestionIds') or ():
            source = self.library.suggestions.first(sid)
            option = {k: deepcopy(v) for k, v in source.items() if k != 'id' and 'description' not in k.lower()}
            for field in ('produceEffectIds', 'successProduceEffectIds', 'failProduceEffectIds'):
                option[field] = effects(source.get(field))
            for type_key, id_key in (('stepType', 'stepId'), ('successStepType', 'successStepId'), ('failStepType', 'failStepId')):
                if source.get(id_key) and str(source.get(type_key)).startswith('ProduceStepType_Event'):
                    option[id_key] = self.program(source[id_key], parameterize_hif_pools=parameterize_hif_pools,
                                                 _ancestors=(*_ancestors, event_id))
            options.append(option)
        result = {'event_type': row['eventType'], 'suggestion_type': row.get('suggestionType'),
                  'business_excellent': row.get('isBusinessExcellent', False),
                  'effects': effects(row.get('produceEffectIds')), 'options': options}
        self._cache[key] = deepcopy(result)
        return result

    def groups(self, event_ids=None, *, parameterize_hif_pools=False):
        """Preserve numeric effects, option order, branching and reward-pool identity."""
        groups = {}
        for eid in event_ids if event_ids is not None else [r['id'] for r in self.library.details.rows]:
            program = self.program(eid, parameterize_hif_pools=parameterize_hif_pools)
            tid = 'event-mechanism:' + _hash(program)
            group = groups.setdefault(tid, {'template_id': tid, 'program': program, 'members': []})
            source = self.library.details.first(eid)
            group['members'].append({'event_id': eid, 'story_id': source.get('produceStoryId', ''),
                'story_group_id': source.get('produceStoryGroupId', ''),
                'support_requirements': [deepcopy(x) for x in self.library.support_links.rows
                                         if x['produceStepEventDetailId'] == eid],
                'option_ids': list(source.get('produceStepEventSuggestionIds') or ())})
        return list(groups.values())

    def template_id(self, event_id, *, parameterize_hif_pools=False):
        return 'event-mechanism:' + _hash(self.program(event_id, parameterize_hif_pools=parameterize_hif_pools))

    def hif_outings(self):
        ids = self.library.hif_event_ids('produce-007', kind='Activity') + self.library.hif_event_ids('produce-008', kind='Activity')
        strict = self.groups(ids)
        families = self.groups(ids, parameterize_hif_pools=True)
        # Exact source effects remain the execution authority after abstraction.
        for group in strict:
            eid = group['members'][0]['event_id']
            group['family_id'] = 'event-mechanism:' + _hash(self.program(eid, parameterize_hif_pools=True))
            group['reward_bindings'] = {e: self.effect(e) for option in self.library.event(eid)['options']
                                       for e in option['produceEffectIds']
                                       if self.repository.produce_effects.first(e)['produceEffectType'] == 'ProduceEffectType_ProduceRewardSet'}
        return {'schema_version': 'arena-hif-outing-templates/1', 'source_events': len(ids),
                'mechanism_families': families, 'stage_variants': strict,
                'source': 'local master Activity rows; HIF wiki outing section',
                'source_url': 'https://seesaawiki.jp/gakumasu/d/H.I.F',
                'occurrence_weights': None,
                'note': 'Stage reward pools remain bound explicitly; member counts are not probabilities.'}

    def hif_classes(self):
        """Collapse class narrative aliases while retaining plan/stage choices."""
        ids = [eid for produce_id in ('produce-007', 'produce-008')
               for eid in self.library.hif_event_ids(produce_id, kind='School')]
        return {
            'schema_version': 'arena-hif-class-templates/1',
            'source_events': len(ids),
            'stage_variants': self.groups(ids),
            'plan_directions': {
                'plan1': ['exam_parameter_buff', 'exam_lesson_buff'],
                'plan2': ['exam_review', 'exam_card_play_aggressive'],
                'plan3': ['exam_concentration', 'exam_full_power'],
            },
            'occurrence_weights': None,
            'note': 'Plan3 exam_concentration denotes strong stance, not Sense concentration. '
                    'Early directional branches acquire; later branches Select Change. '
                    'Every Trouble branch has its own unsuffixed pool.',
        }

    def export(self, path):
        groups = self.groups()
        payload = {'schema_version': 'arena-event-templates/1',
                   'source_events': sum(len(g['members']) for g in groups),
                   'template_count': len(groups), 'templates': groups,
                   'hif_outings': self.hif_outings(),
                   'hif_classes': self.hif_classes(),
                   'hif_fixed_event_contracts': self.library.hif_fixed_event_catalog()}
        payload['content_sha256'] = _hash(payload)
        target = Path(path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        return target
