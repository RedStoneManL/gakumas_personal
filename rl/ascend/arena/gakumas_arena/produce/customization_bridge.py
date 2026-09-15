"""Resolve master customizations to the pinned native engine's full patches.

The checked registry is produced by semantic matching, never array position or
price. It includes all cumulative levels and recursively fingerprints their
source effects. Unknown or changed content fails closed. Ordinary non-custom
growth remains separate so it is not applied twice by native prestage patches.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re

from ..engine.catalogue_overrides import catalogue_override_provenance


class CustomizationBridgeError(ValueError):
    pass


_REGISTRY = Path(__file__).with_name('data') / 'customization_registry.json'
_DESCRIPTION_FIELDS = {'produceDescriptions', 'customizeProduceDescriptions',
                       'playProduceDescriptions', 'playEffectProduceDescriptions'}


def _canonical(value):
    if isinstance(value, dict):
        return {k:_canonical(v) for k,v in sorted(value.items()) if k not in _DESCRIPTION_FIELDS}
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    return value


def _digest(value):
    return sha256(json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def _levels(repository, customize_id):
    levels = sorted(repository.load_table('ProduceCardCustomize').all(customize_id),
                    key=lambda row: int(row['customizeCount']))
    if not levels or [int(row['customizeCount']) for row in levels] != list(range(1,len(levels)+1)):
        raise CustomizationBridgeError(f'Invalid customization levels: {customize_id}')
    return levels


_REFERENCES = {
    'produceCardGrowEffectIds':'ProduceCardGrowEffect',
    'playProduceExamEffectId':'ProduceExamEffect',
    'targetPlayProduceExamEffectIds':'ProduceExamEffect',
    'produceExamEffectIds':'ProduceExamEffect',
    'chainProduceExamEffectId':'ProduceExamEffect',
    'chainProduceExamEffectIds':'ProduceExamEffect',
    'playProduceExamTriggerId':'ProduceExamTrigger',
    'playEffectProduceExamTriggerId':'ProduceExamTrigger',
    'targetPlayEffectProduceExamTriggerIds':'ProduceExamTrigger',
    'produceExamTriggerId':'ProduceExamTrigger',
    'produceExamStatusEnchantId':'ProduceExamStatusEnchant',
    'produceCardStatusEnchantId':'ProduceCardStatusEnchant',
    'produceCardSearchId':'ProduceCardSearch',
    'produceCardSearchId2':'ProduceCardSearch',
    'fieldStatusProduceCardSearchIds':'ProduceCardSearch',
    'pickCountReferenceProduceCardSearchId':'ProduceCardSearch',
    'pickCountReferenceProduceCardSearchId2':'ProduceCardSearch',
}


def source_payload(repository, customize_id):
    """Complete mechanics-bearing source closure used by the checked registry."""
    levels = _levels(repository, customize_id)
    nodes = {}
    def visit(row):
        for field, table in _REFERENCES.items():
            values = row.get(field) or []
            if isinstance(values, str):
                values = [values]
            for value in values:
                key = f'{table}/{value}'
                if not value or key in nodes:
                    continue
                target = repository.load_table(table).first(value)
                if target is None:
                    raise CustomizationBridgeError(f'Missing customization source: {key}')
                nodes[key] = _canonical(target)
                visit(target)
    for level in levels:
        visit(level)
    return {'levels':_canonical(levels), 'references':nodes}


@lru_cache(maxsize=1)
def _registry():
    data = json.loads(_REGISTRY.read_text(encoding='utf-8'))
    if data.get('schema_version') != 'arena-native-customizations/1':
        raise CustomizationBridgeError('Unsupported customization registry schema')
    return data


def resolve_customizations(repository, master_card_row, native_card_row, native_customizations):
    """Return ``(native levels, residual grow IDs, source provenance)``.

    Repeated master IDs select their last cumulative level. Exactly that level's
    grow multiset is consumed; independent growth is returned in original order.
    """
    applied = list(master_card_row.get('customizedProduceCardCustomizeIds') or [])
    residual = list(master_card_row.get('growEffectIds') or [])
    if not applied:
        return {}, residual, []
    card_id = master_card_row['id']
    upgrade = int(master_card_row.get('upgradeCount') or 0)
    canonical = repository.card_row_by_upgrade(card_id, upgrade, fallback_to_canonical=False)
    if canonical is None:
        raise CustomizationBridgeError(f'Missing master card: {card_id}@{upgrade}')
    if len(applied) > int(canonical.get('maxCustomizeCount') or 0):
        raise CustomizationBridgeError(f'Customization limit exceeded: {card_id}@{upgrade}')
    allowed = set(canonical.get('produceCardCustomizeIds') or [])
    if any(custom not in allowed for custom in applied):
        raise CustomizationBridgeError(f'Customization not allowed on {card_id}@{upgrade}')
    record = _registry()['cards'].get(f'{card_id}@{upgrade}')
    if record is None:
        raise CustomizationBridgeError(f'Unmapped native customization card: {card_id}@{upgrade}')
    if _digest(canonical) != record['master_card_sha256']:
        raise CustomizationBridgeError(f'Customization master card changed: {card_id}@{upgrade}')
    if _digest(native_card_row) != record['native_card_sha256']:
        raise CustomizationBridgeError(f'Customization native card changed: {card_id}@{upgrade}')
    native_allowed = set(str(native_card_row.get('availableCustomizations') or '').split(','))
    resolved, provenance = {}, []
    for custom_id, count in Counter(applied).items():
        levels = _levels(repository, custom_id)
        if count > len(levels):
            raise CustomizationBridgeError(f'Customization level exceeded: {custom_id} x {count}')
        mapping = record['customizations'].get(custom_id)
        if mapping is None:
            raise CustomizationBridgeError(f'Unmapped native customization: {card_id}/{custom_id}')
        source = _registry()['sources'][custom_id]
        if _digest(source_payload(repository, custom_id)) != source['master_sha256']:
            raise CustomizationBridgeError(f'Customization master source changed: {custom_id}')
        native_id = str(mapping['native_id'])
        native = native_customizations.get(int(native_id), native_customizations.get(native_id))
        if native is None or _digest(native) != mapping['native_sha256']:
            raise CustomizationBridgeError(f'Customization native source changed: {custom_id}/{native_id}')
        if native_id not in native_allowed or count > int(native['max']):
            raise CustomizationBridgeError(f'Native customization not allowed: {card_id}/{native_id} x {count}')
        if native_id in resolved:
            raise CustomizationBridgeError(f'Distinct master customizations collide on native {native_id}')
        final_grows = list(levels[count-1].get('produceCardGrowEffectIds') or [])
        for grow in final_grows:
            if grow not in residual:
                raise CustomizationBridgeError(f'Missing resolved cumulative grow: {custom_id}/{grow}')
            residual.remove(grow)
        resolved[native_id] = count
        provenance.append({'schema_version':'arena-native-customization-source/1',
            'master_card_id':card_id, 'master_customize_id':custom_id,
            'native_card_id':native_card_row['id'], 'native_customization_id':int(native_id),
            'level':count, 'consumed_grow_ids':final_grows,
            'master_source_sha256':source['master_sha256'], 'native_source_sha256':mapping['native_sha256'],
            'mapping':mapping.get('mapping','semantic-equivalence'),
            'differences':mapping.get('differences',[])})
        overlay = catalogue_override_provenance(native_card_row['id'])
        if overlay is not None:
            provenance[-1]['catalogue_override'] = overlay
    return resolved, residual, provenance


# Registry compiler helpers. Runtime resolution uses the checked manifest above.
# These finite translations deliberately reject fields or mechanics not examined.
def _mechanics(row):
    return {k:v for k,v in row.items() if k not in _DESCRIPTION_FIELDS | {'id','effectGroupIds'}
            and v not in ('',0,None,False,[]) and not (isinstance(v,str) and v.endswith('_Unknown'))}


def _expect(row, expected):
    actual = _mechanics(row)
    if actual != expected:
        raise CustomizationBridgeError(f'Unexamined customization mechanics: {row.get("id")}: {actual}')


def _number(value):
    return f'{float(value):g}'


def _effect_action(repository, effect_id):
    effect = repository.load_table('ProduceExamEffect').first(effect_id)
    if not effect:
        raise CustomizationBridgeError(f'Missing effect: {effect_id}')
    kind = effect['effectType'].removeprefix('ProduceExamEffectType_')
    expected = {'effectType':effect['effectType']}
    field = {'ExamLesson':'score','ExamBlock':'genki','ExamLessonBuff':'concentration',
             'ExamParameterBuff':'goodConditionTurns',
             'ExamParameterBuffMultiplePerTurn':'perfectConditionTurns',
             'ExamReview':'goodImpressionTurns','ExamCardPlayAggressive':'motivation',
             'ExamFullPowerPoint':'fullPowerCharge'}.get(kind)
    if field:
        value_field = 'effectTurn' if kind in ('ExamParameterBuff','ExamParameterBuffMultiplePerTurn') else 'effectValue1'
        expected[value_field] = effect[value_field]
        if kind == 'ExamLesson': expected['effectCount'] = 1
        _expect(effect, expected)
        return f'{field}+={_number(effect[value_field])}'
    dependent = {'ExamLessonDependExamReview':'goodImpressionTurns',
                 'ExamLessonDependExamCardPlayAggressive':'motivation', 'ExamLessonDependBlock':'genki'}
    if kind in dependent:
        expected.update(effectValue1=effect['effectValue1'], effectCount=1)
        _expect(effect, expected)
        return f'score+={dependent[kind]}*{_number(effect["effectValue1"]/1000)}'
    if kind == 'ExamPlayableValueAdd':
        expected['effectCount'] = 1; _expect(effect, expected)
        return 'cardUsesRemaining+=1'
    if kind == 'ExamCardUpgrade':
        expected.update(produceCardSearchId='p_card_search-hand',pickRangeType='ProducePickRangeType_All')
        _expect(effect, expected)
        return 'upgradeHand'
    if kind == 'ExamConcentration':
        expected['effectValue1'] = 1; _expect(effect, expected)
        return 'setStance(strength)'
    if kind == 'ExamCardMove':
        expected.update(produceCardSearchId='p_card_search-deck',movePositionType='ProduceCardMovePositionType_Hold',
                        pickRangeType='ProducePickRangeType_Select',pickCountMin=1,pickCountMax=1)
        _expect(effect, expected)
        return 'holdSelected[deck]'
    if kind == 'ExamEffectTimer':
        expected.update(effectValue1=1,effectCount=1,chainProduceExamEffectId='e_effect-exam_preservation-0001')
        _expect(effect, expected)
        _expect(repository.exam_effects.first(expected['chainProduceExamEffectId']),
                {'effectType':'ProduceExamEffectType_ExamPreservation','effectValue1':1})
        return 'at:turn { setStance(preservation); limit:1 }'
    if kind == 'ExamAddGrowEffect':
        target = {'p_card_search-deck_all':'all','p_card_search-hand':'hand','p_card_search-hold':'held'}.get(effect.get('produceCardSearchId'))
        if target is None or len(effect.get('produceCardGrowEffectIds',[])) != 1:
            raise CustomizationBridgeError(f'Unexamined target growth: {effect_id}')
        expected.update(produceCardSearchId=effect['produceCardSearchId'],pickRangeType='ProducePickRangeType_All',
                        produceCardGrowEffectIds=effect['produceCardGrowEffectIds'])
        _expect(effect, expected)
        child = repository.load_table('ProduceCardGrowEffect').first(effect['produceCardGrowEffectIds'][0])
        _expect(child,{'effectType':'ProduceCardGrowEffectType_LessonAdd','value':child['value']})
        return f'target:{target} {{ g.score+={_number(child["value"])} }}'
    raise CustomizationBridgeError(f'Unexamined added effect: {effect_id}')


_SCALARS = {
    'LessonAdd':('score',1),'LessonCountAdd':('scoreTimes',1),'CostReduce':('cost',1),
    'BlockAdd':('genki',1),'LessonBuffAdd':('concentration',1),
    'ParameterBuffTurnAdd':('goodConditionTurns',1),'ParameterBuffMultiplePerTurnAdd':('perfectConditionTurns',1),
    'ReviewAdd':('goodImpressionTurns',1),'AggressiveAdd':('motivation',1),
    'FullPowerPointAdd':('fullPowerCharge',1),'StaminaConsumptionDownTurnAdd':('halfCostTurns',1),
    'LessonDependBlockAdd':('scoreByGenki',.001),
    'LessonDependExamReviewAdd':('scoreByGoodImpressionTurns',.001),
    'LessonDependExamCardPlayAggressiveAdd':('scoreByMotivation',.001),
}
_TYPED_COST = {'CostPenetrateReduce':30,'CostParameterBuffReduce':31,'CostLessonBuffReduce':32,
               'CostReviewReduce':33,'CostAggressiveReduce':34,'CostFullPowerPointReduce':35,
               'CostParameterBuffMultiplePerTurnReduce':104}


def _grow_patch(repository, grow_id):
    grow = repository.load_table('ProduceCardGrowEffect').first(grow_id)
    kind = grow['effectType'].removeprefix('ProduceCardGrowEffectType_')
    expected = {'effectType':grow['effectType']}
    if kind in _SCALARS or kind in _TYPED_COST:
        expected['value'] = grow['value']; _expect(grow, expected)
        field, scale = _SCALARS.get(kind,('typedCost',1))
        return 'effects', f'at:prestage {{ target:this {{ g.{field}+={_number(grow["value"]*scale)} }} }}', _TYPED_COST.get(kind)
    if kind == 'InitialAdd':
        _expect(grow, expected); return 'forceInitialHand', True, 36
    if kind == 'PlayMovePositionTypeChange':
        expected['playMovePositionType'] = 'ProduceCardMovePositionType_Grave'
        _expect(grow, expected); return 'limit', 0, 37
    if kind == 'EffectAdd':
        expected['playProduceExamEffectId'] = grow['playProduceExamEffectId']; _expect(grow, expected)
        return 'actions', _effect_action(repository, grow['playProduceExamEffectId']), None
    if kind == 'EffectChange' and grow_id in (
            'g_effect-effect_change-e_effect-exam_concentration-0001-e_effect-exam_concentration-0002',
            'g_effect-effect_change-e_effect-exam_preservation-0001-e_effect-exam_preservation-0002'):
        strength = 'concentration' in grow_id
        stem = 'concentration' if strength else 'preservation'
        expected.update(playProduceExamEffectId=f'e_effect-exam_{stem}-0002',
                        targetPlayProduceExamEffectIds=[f'e_effect-exam_{stem}-0001'])
        _expect(grow, expected)
        return 'effects','at:prestage { target:this { g.stanceLevel+=1 } }',40 if strength else 41
    raise CustomizationBridgeError(f'Unexamined grow patch: {grow_id}')


_COMPLEX_CUSTOMS = {
    'p_card_custom-070-g_effect-play_trigger_change-e_trigger-none-block_up-30-e_trigger-none-block_up-15':85,
    'p_card_custom-040_040_070-g_effect-p_card-02-act-1_037-enc_1-g_effect-p_card-02-act-1_037-enc_2-g_effect-p_card-02-act-1_037-enc_3':86,
    'p_card_custom-100-g_effect-p_card-02-act-3_050-enc_1':46,
    'p_card_custom-070-g_effect-play_trigger_change-e_trigger-none-preservation_change_count_up-2-e_trigger-none-preservation_change_count_up-1':87,
    'p_card_custom-070-g_effect-play_effect_trigger_change-e_trigger-none-review_up-15-e_trigger-none-review_up-10':88,
    'p_card_custom-wrapper-p_card-01-act-2_061-a-01':97,
    'p_card_custom-040_070-g_effect-card_status_enchant_change-card_enchant-e_trigger-exam_stance_change_concentration-g_effect-lesson_add-2-g_effect-card_status_enchant_change-card_enchant-e_trigger-exam_stance_change_concentration-g_effect-lesson_add-5':63,
    'p_card_custom-070-g_effect-card_status_enchant_change-card_enchant-e_trigger-exam_stance_change_full_power-g_effect-lesson_add-3':81,
    'p_card_custom-wrapper-p_card-02-act-3_187-a-01':105,
    'p_card_custom-wrapper-p_card-02-act-3_187-b-01':106,
}


def _signature(payload):
    def normalized(value):
        return re.sub(r'\s+','',value).replace(';}', '}') if isinstance(value,str) else value
    return {k:normalized(payload.get(k,'')) for k in
            ('forceInitialHand','conditions','cost','actions','limit','effects','max')}


def semantic_candidates(repository, customize_id, native_customizations):
    """Offline compiler: exact complete-level candidates for examined mechanics."""
    levels = _levels(repository, customize_id)
    if customize_id in _COMPLEX_CUSTOMS:
        return [_COMPLEX_CUSTOMS[customize_id]]
    expected = {'max':len(levels)}
    preferred = set()
    for level in levels:
        patches = [_grow_patch(repository,gid) for gid in level.get('produceCardGrowEffectIds',[])]
        if len(patches) != 1:
            raise CustomizationBridgeError(f'Unexamined compound customization: {customize_id}')
        column, text, native_id = patches[0]
        if native_id is not None: preferred.add(native_id)
        if column in ('forceInitialHand','limit'):
            if len(levels) != 1: raise CustomizationBridgeError(f'Unexpected scalar property levels: {customize_id}')
            expected[column] = text
        else:
            if len(levels)>1: text = f'level:{level["customizeCount"]} {{ {text} }}'
            expected[column] = expected.get(column,'') + ' ' + text
    return [int(cid) for cid,native in native_customizations.items()
            if (not preferred or int(cid) in preferred) and _signature(native)==_signature(expected)]


__all__ = ['CustomizationBridgeError','resolve_customizations']
