"""Five HIF courses translated from the pinned research/master-data snapshot.

The reference JSON is evidence, not a drop-in exam config. This adapter supplies
the golden interface and names every probability/numeric approximation.
"""
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path

COLORS = ('vocal', 'dance', 'visual')
DATA_PATH = Path(__file__).with_name('data') / 'hif_exam_profiles.json'


@lru_cache(maxsize=1)
def exam_profiles():
    return json.loads(DATA_PATH.read_text(encoding='utf-8'))


def stage_profile(produce_id, stage_type):
    return next(s for s in exam_profiles()['stages']
                if s['produce_id'] == produce_id and s['step_type'] == stage_type)


def piecewise(score, segments):
    value = max(Fraction(str(score)), 0)
    for row in segments:
        if row['upper_inclusive'] is None or value <= row['upper_inclusive']:
            return Fraction(row['base']) + (value-row['lower']) * Fraction(row['slope'])
    raise ValueError('Incomplete piecewise curve')


def audition_star_base(produce_id, stage_type, score):
    return math.ceil(piecewise(score, stage_profile(produce_id, stage_type)['star_reward_model']['segments']))


def _allocate(total, weights):
    """Largest remainder, stable Vo/Da/Vi ties; preserves the integer pool."""
    if sum(weights) == 0:
        weights = [1, 1, 1]
    raw = [Fraction(total)*w/sum(weights) for w in weights]
    out = [math.floor(x) for x in raw]
    order = sorted(range(3), key=lambda i: (-(raw[i]-out[i]), i))
    for i in order[:total-sum(out)]:
        out[i] += 1
    return out


def audition_rewards(runtime, stage_type, score, score_by_color):
    """Post-exam rewards; rates are applied once, acceptance commits once.

    Exact low-score stat/P-point curves were not recovered. The configurable
    linear-to-cap model keeps the known caps and actual color score allocation.
    """
    row = stage_profile(runtime.scenario.produce_id, stage_type)
    config = getattr(runtime, 'hif_research_config', {}).get('exam_rewards', {})
    result = {'score_by_color': deepcopy(score_by_color), 'parameter_bonus_by_type': {},
              'hif_audition_point_gain': 0, 'reward_provenance': {
                  'version': 'hif-five-exam-rewards/1', 'stage_id': row['stage_id'],
                  'star': 'community-piecewise-ceil; actual-StarPerMil-floor',
                  'stat_curve': 'linear-to-configured-cap/approximation',
                  'allocation': 'actual-color-score; largest-remainder/approximation'}}
    stats = row['per_color_parameter_reward_at_total_reward_cap']
    if stats is not None:
        cap_score = config.get('stat_cap_scores', {}).get(row['stage_id'], row['safe_star_cap_target_score'])
        if cap_score <= 0:
            raise ValueError('stat_cap_scores must be positive')
        fraction = min(Fraction(str(score))/Fraction(str(cap_score)), 1)
        fraction = max(fraction, 0)
        fixed = math.floor(stats['fixed_per_color']*fraction)
        pool = math.floor(stats['shared_pool']*fraction)
        weights = [max(Fraction(str(score_by_color.get(c, 0))), 0) for c in COLORS]
        for c, share in zip(COLORS, _allocate(pool, weights)):
            growth = Fraction(str(runtime.state.get(c+'_growth', 0)))
            result['parameter_bonus_by_type'][c] = math.floor((fixed+share)*(1+growth))
    elif row['stage_id'] == 'final_1':
        cap_score = config.get('round1_point_cap_score', 400000)
        if cap_score <= 0:
            raise ValueError('round1_point_cap_score must be positive')
        result['hif_audition_point_gain'] = math.floor(200*min(max(Fraction(str(score)), 0)/cap_score, 1))
        result['reward_provenance']['point_curve'] = 'linear-200-at-400000-raw/approximation'
    return result


def final_rating(params, star, raw_round1, raw_round2):
    model = exam_profiles()['production_rating_model']
    total = sum(Fraction(str(x)) for x in params)
    base = math.floor(2*total + Fraction(15, 2)*Fraction(str(star)))
    r1 = math.floor(piecewise(raw_round1, model['raw_score_segments']['final_1']))
    r2 = math.floor(piecewise(raw_round2, model['raw_score_segments']['final_2']))
    rating = base+r1+r2-2000
    rank = 'F'
    for row in model['grade_thresholds_raw']:
        if rating >= row['threshold']:
            rank = row['grade'].removeprefix('ResultGrade_').replace('Plus', '+').upper()
    rank = {'SSSS':'S4', 'SSSS+':'S4+', 'SSSSS':'S5'}.get(rank, rank)
    return {'rating': rating, 'rank': rank, 'parameter_total': float(total),
            'star_quality_after_round2': star, 'base': base, 'round1_component': r1,
            'round2_component': r2, 'formula_source': 'hif-five-exam-research/1'}


def _idol_profile(runtime, options):
    loadout = runtime.idol_loadout
    character = (loadout.stat_profile.character_id if loadout is not None
                 else runtime._default_idol_card_row().get('characterId'))
    character = options.get('character_id', character)
    rows = exam_profiles()['idols']
    matched = next((r for r in rows if r['character_id'] == character), None)
    if matched is None and options.get('profile_character_id'):
        matched = next((r for r in rows if r['character_id'] == options['profile_character_id']), None)
    if matched is None:
        raise ValueError(f'No pinned HIF profile for {character}; configure courses.profile_character_id or exam_config')
    return matched


def default_exam_config(runtime, context):
    options = getattr(runtime, 'hif_research_config', {}).get('courses', {})
    data = exam_profiles()
    stage = stage_profile(context['produce_id'], context['stage_type'])
    idol = _idol_profile(runtime, options)
    exam = next(r for r in idol['exams'] if r['stage_id'] == stage['stage_id'])
    primary, secondary, third = idol['attribute_priority']
    counts = dict(exam['turn_counts_by_color'])
    probability = float(options.get('secondary_first_probability', .15 if idol['judgement_shape']=='balanced' else 0))
    if not 0 <= probability <= 1:
        raise ValueError('secondary_first_probability must be in [0,1]')
    first = secondary if runtime.np_random.random() < probability else primary
    tail = [third, secondary, primary]
    for c in [first, *tail]:
        counts[c] -= 1
    middle = [c for c in COLORS for _ in range(counts[c])]
    runtime.np_random.shuffle(middle)
    turns = [first, *middle, *tail]
    extra = max(0, int(runtime.state.get('audition_turn_modifier', 0)))
    turns.extend([primary]*extra)
    npcs = [r for r in data['raw_npc_groups'] if r['id'] == exam['npc_group_id']]
    npc_model = options.get('npc_model', 'midpoint' if exam['is_static_npc_score_config'] else 'uniform-integer')
    if npc_model not in ('midpoint', 'uniform-integer'):
        raise ValueError('npc_model must be midpoint or uniform-integer')
    scores = [(r['scoreMin']+r['scoreMax'])//2 if npc_model=='midpoint'
              else int(runtime.np_random.integers(r['scoreMin'], r['scoreMax']+1)) for r in npcs]
    criteria = data['battle_configs'][exam['battle_config_id']]['raw_config']
    thresholds = [int(criteria[c]) for c in COLORS]
    icons = ['○' if context['state'][c] >= threshold else '△' for c, threshold in zip(COLORS, thresholds)]
    scoring = {'family': idol['profile_family'], 'judging_icons': icons,
               'dearness_factor': options.get('dearness_factor', 1.5),
               'penalty_mode': 'settings-prior', 'penalty_thresholds': thresholds, 'allow_experimental': True}
    scoring.update(deepcopy(options.get('scoring', {})))
    if scoring.get('all_qualified'):
        scoring.pop('judging_icons', None)
    provenance = {'version': 'hif-five-course/1', 'research_sha256': sha256(DATA_PATH.read_bytes()).hexdigest(),
                  'stage_id': stage['stage_id'], 'character_id': idol['character_id'],
                  'battle_config_id': exam['battle_config_id'], 'npc_group_id': exam['npc_group_id'],
                  'npc_model': npc_model+'/approximation', 'first_turn_secondary_probability': probability,
                  'qualification_model': 'master-stat-threshold/approximation',
                  'dearness_model': 'configured-factor-default-1.5/approximation',
                  'extra_turn_color': primary, 'gimmick_note': data['gimmick_note']}
    result = {'turn_types': turns, 'rival_scores': scores,
              'rival_ids': [r.get('characterId') or r['produceExamBattleNpcMobId'] for r in npcs],
              'rank_threshold': exam['rank_threshold_config'], 'hif_scoring': scoring,
              'course_provenance': provenance}
    runtime.hif_course_history = [*getattr(runtime, 'hif_course_history', []), deepcopy(result)]
    return result
