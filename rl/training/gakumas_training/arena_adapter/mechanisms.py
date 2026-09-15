"""Read-only master-definition closure for public produce state and candidates.

Only presentation metadata is dropped. Runtime effects are not simulated here.
Native examinations already expose their effective AST in observation.definitions.
"""
from __future__ import annotations

from copy import deepcopy
import json

PRESENTATION = frozenset({'produceDescriptions', 'descriptions', 'description', 'name',
    'assetId', 'voiceAssetId', 'isCharacterAsset', 'viewConditionSetId', 'unlockConditionSetId'})
TABLES = ('ProduceEffect', 'ProduceTrigger', 'ProduceExamEffect', 'ProduceExamTrigger',
    'ProduceExamStatusEnchant', 'ProduceCardStatusEnchant', 'ProduceCardGrowEffect',
    'ProduceCardSearch', 'ProduceCard', 'ProduceDrink', 'ProduceItem', 'ProduceItemEffect',
    'ProduceSkill', 'ProduceCardCustomize', 'ProduceStepEventDetail', 'ProduceStepEventSuggestion',
    'ProduceCustomizeItem', 'ProduceCustomizeItemRelationship', 'ProduceCustomizeItemEffect', 'ProduceCustomizeItemStep',
    'ProduceCustomizeItemProduceCardReward', 'ProduceCustomizeItemProduceDrinkReward')


def mechanical(value):
    if isinstance(value, dict):
        return {k: mechanical(v) for k, v in value.items() if k not in PRESENTATION}
    if isinstance(value, (list, tuple)):
        return [mechanical(v) for v in value]
    return value


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from strings(child)


class MasterMechanisms:
    def __init__(self, repository):
        self.repository = repository
        self.index = {}
        for table in TABLES:
            if not (repository.assets_dir / f'{table}.yaml').exists():
                continue  # Optional tables differ between pinned releases.
            for row in repository.load_table(table).rows:
                if table == 'ProduceCustomizeItemRelationship':
                    parent = row['parentProduceCustomizeItemId']
                    child = row['childProduceCustomizeItemId']
                    self.index.setdefault(parent, []).append((table, {'id': f'{parent}->{child}', **row}))
                elif row.get('id'):
                    self.index.setdefault(str(row['id']), []).append((table, row))
        self.cache = {}

    def closure(self, public, candidates=()):
        root = mechanical([public, candidates])
        # Active runtime skill records already contain the exact level's trigger,
        # effect IDs, probability, fire limit and current counter. Expanding the
        # master ID would incorrectly add every inactive historical level and
        # make an ID-only graph edge ambiguous. Follow the bound effect IDs.
        bound_skill_ids = {str(skill['skill_id']) for skill in public.get('support_skills', [])
                           if skill.get('skill_id')}
        pending = set(strings(root)) & self.index.keys()
        result, seen = [], set()
        while pending:
            identity = pending.pop()
            if identity in seen:
                continue
            seen.add(identity)
            for table, original in self.index[identity]:
                if table == 'ProduceSkill' and identity in bound_skill_ids:
                    continue
                data = mechanical(original)
                key = (table, json.dumps(data, sort_keys=True, ensure_ascii=False))
                if key not in self.cache:
                    self.cache[key] = {'table': table, 'id': str(data['id']), 'data': data}
                result.append(self.cache[key])
                pending.update((set(strings(data)) & self.index.keys()) - seen)
        result.sort(key=lambda row: (row['table'], row['id'], json.dumps(row['data'], sort_keys=True)))
        return deepcopy(result)
