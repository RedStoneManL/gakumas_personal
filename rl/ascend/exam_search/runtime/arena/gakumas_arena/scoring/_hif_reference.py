"""HIF displayed score multipliers: empirical model v0.3, 2026-09-09.

Inputs and outputs always use Vo / Da / Vi order. This models the displayed
percentages, not the rounding of individual card score events.
Requires hif_multiplier_research_2026-09-09.json beside this file, or --data.

Judging icons are explicit inputs; triangle/cross penalties affect all colors.
The settings-prior penalty is an UNVALIDATED HIF hypothesis, enabled explicitly.
Round 1/2 star ramps are empirical candidates. Selection ramps and below-star-
baseline interpolation require --allow-experimental. See the report for limits.
"""

import argparse
import json
from fractions import Fraction
from pathlib import Path

DATA_PATH = Path(__file__).with_name('hif_multiplier_research_2026-09-09.json')
STAGES = ('selection1', 'selection2', 'selection3', 'round1', 'round2')


def ceil_fraction(value):
    value = Fraction(value)
    return -(-value.numerator // value.denominator)


def load_data(path=DATA_PATH):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def base_percents(data, family, stage, stats):
    if stage not in STAGES:
        raise ValueError('Unknown HIF stage')
    if family not in data['families']:
        raise ValueError('Unknown curve family')
    if len(stats) != 3 or any(type(p) is not int or p < 0 for p in stats):
        raise ValueError('stats must be three nonnegative integers, Vo / Da / Vi')
    config_id = data['families'][family]['config_ids'][stage]
    nodes = data['curves'][config_id]['nodes']
    result, interpolated = [], []
    for color, parameter in enumerate(stats, 1):
        if parameter > nodes[-1][0]:
            raise ValueError('Stat exceeds the supplied curve table')
        for left, right in zip(nodes, nodes[1:]):
            if left[0] <= parameter <= right[0]:
                permil = Fraction(left[color]) + Fraction(
                    (right[color] - left[color]) * (parameter - left[0]),
                    right[0] - left[0])
                interpolated.append(permil)
                result.append(ceil_fraction(100 + permil / 10))
                break
    return result, interpolated


def star_permil(data, stage, star, allow_experimental=False):
    if type(star) is not int or star < 0:
        raise ValueError('star must be a nonnegative entrance star value')
    config = data['stages'][stage]
    baseline = config['star_baseline']
    if star < baseline:
        if not allow_experimental:
            raise ValueError('Below-baseline star behavior is unvalidated; '
                             'use --allow-experimental only for the stated assumption')
        return ceil_fraction(1850 + Fraction(150 * star, baseline)), [
            'UNVALIDATED: linear star interpolation from 1.85 at S=0 to 2 at baseline']
    if stage.startswith('selection'):
        observed_plateau = config['lowest_observed_near_3_star']
        if star >= observed_plateau:
            return 3000, ['Selection plateau: assumes monotonicity and the 3x cap; '
                          'this is not an identified saturation threshold']
        if not allow_experimental:
            raise ValueError('Selection star ramp is unidentified; '
                             'use --allow-experimental to use the explicit endpoint assumption')
        quality = ['UNVALIDATED: selection ramp uses an observed plateau endpoint; '
                   'its slope is not estimated from unsaturated samples']
    else:
        quality = ['EMPIRICAL CANDIDATE: capped linear star ramp with 0.001 upward quantization']
    denominator = config['candidate_star_denominator']
    value = min(3000, 2000 + ceil_fraction(Fraction(1000 * (star - baseline), denominator)))
    return value, quality


def normalize_icons(judging_icons):
    if judging_icons is None:
        return None
    aliases = {'◯': '○', '〇': '○', 'o': '○', 'O': '○',
               '✕': '×', '☓': '×', 'x': '×', 'X': '×'}
    icons = [aliases.get(x, x) for x in judging_icons]
    if len(icons) != 3 or any(x not in ('◎', '○', '△', '×') for x in icons):
        raise ValueError('judging_icons must contain three of ◎ / ○ / △ / ×, Vo / Da / Vi')
    return icons


def penalty_correction(data, *, family, stage, stats, judging_icons,
                       all_qualified, mode, thresholds, combination,
                       allow_experimental):
    icons = normalize_icons(judging_icons)
    deficient = None if icons is None else [x in ('△', '×') for x in icons]
    if all_qualified and deficient is not None and any(deficient):
        raise ValueError('all_qualified contradicts the supplied △ / × icons')
    if mode not in ('none', 'settings-prior'):
        raise ValueError('Unknown penalty mode')
    if combination not in ('additive', 'multiplicative'):
        raise ValueError('Unknown penalty combination')
    if all_qualified or (deficient is not None and not any(deficient)):
        return Fraction(1), {'judging_icons': icons, 'mode': 'none',
                             'per_stat_penalty_permil': [0, 0, 0]}, []
    if deficient is None:
        raise ValueError('Provide observed --judging-icons or explicitly confirm --all-qualified; '
                         'icons are not inferred from unvalidated baseline thresholds')
    if mode == 'none' or not allow_experimental:
        raise ValueError('HIF △ / × penalty magnitudes are uncalibrated. To evaluate the '
                         'explicit hypothesis, use --penalty-mode settings-prior --allow-experimental')
    flags = ['UNVALIDATED HIF PENALTY: 100..250 permil settings + a Contest-like deficit prior; '
             'no complete HIF △ / × multiplier tuple was obtained to fit this branch']
    if thresholds is None:
        family_data = data['families'][family]
        key = family_data['classification'] + '_stat_baseline_T1_T2_T3'
        by_color = dict(zip(family_data['priority_order'], data['stages'][stage][key]))
        thresholds = [by_color[c] for c in ('Vo', 'Da', 'Vi')]
        flags.append('UNVALIDATED: using master stat baselines as penalty scale thresholds; '
                     'these are not established ○ boundaries')
    if len(thresholds) != 3 or any(type(x) is not int or x <= 0 for x in thresholds):
        raise ValueError('penalty thresholds must be three positive integers')
    penalties = []
    for p, threshold, active in zip(stats, thresholds, deficient):
        ratio = min(Fraction(1), Fraction(p, threshold))
        raw = 250 - 150 * ratio
        penalties.append(raw.numerator // raw.denominator if active else 0)
    if combination == 'additive':
        factor = 1 - Fraction(sum(penalties), 1000)
    else:
        factor = Fraction(1)
        for penalty in penalties:
            factor *= 1 - Fraction(penalty, 1000)
        flags.append('ALTERNATIVE HYPOTHESIS: multiply the per-stat remaining factors')
    return factor, {'judging_icons': icons, 'mode': mode,
                    'thresholds_used_Vo_Da_Vi': thresholds,
                    'per_stat_penalty_permil': penalties,
                    'combination': combination}, flags


def infer_penalty_from_A(data, *, family, stage, stats, observed_A):
    """Conditional interval for Q in A=ceil(100 + (L/10)*Q).

    This is an inference helper, not proof of penalty placement. The untruncated
    lower endpoint is strict. A missing intersection rejects this shared-Q form.
    """
    if len(observed_A) != 3 or any(type(x) is not int for x in observed_A):
        raise ValueError('observed_A must contain three integer displayed percentages')
    _, interpolated = base_percents(data, family, stage, stats)
    intervals = [(Fraction(a - 101) * 10 / l, Fraction(a - 100) * 10 / l)
                 for a, l in zip(observed_A, interpolated)]
    raw_lower = max(a for a, _ in intervals)
    raw_upper = min(b for _, b in intervals)
    lower, upper = max(Fraction(0), raw_lower), min(Fraction(1), raw_upper)
    lower_inclusive = raw_lower < 0
    feasible = lower < upper or (lower == upper and lower_inclusive)
    return {'hypothesis': 'A = ceil(100 + curve_bonus_percent * Q)',
            'feasible_shared_factor': feasible,
            'lower': float(lower), 'lower_inclusive': lower_inclusive,
            'upper': float(upper), 'upper_inclusive': True,
            'per_color_intervals_lower_exclusive_upper_inclusive':
                [[float(a), float(b)] for a, b in intervals]}


def predict(data, *, family, stage, stats, star, all_qualified=False,
            judging_icons=None, dearness_factor=Fraction(3, 2),
            penalty_mode='none', penalty_thresholds=None,
            penalty_combination='additive', penalty_placement='curve-bonus',
            allow_experimental=False):
    dearness_factor = Fraction(str(dearness_factor))
    if dearness_factor <= 0:
        raise ValueError('dearness_factor must be positive')
    a_without_penalty, interpolated = base_percents(data, family, stage, stats)
    q, penalty_details, penalty_flags = penalty_correction(
        data, family=family, stage=stage, stats=stats, judging_icons=judging_icons,
        all_qualified=all_qualified, mode=penalty_mode, thresholds=penalty_thresholds,
        combination=penalty_combination, allow_experimental=allow_experimental)
    if penalty_placement not in ('curve-bonus', 'after-A'):
        raise ValueError('Unknown penalty placement')
    if penalty_placement == 'curve-bonus':
        a = [ceil_fraction(100 + l / 10 * q) for l in interpolated]
        b_internal = [Fraction(x) * dearness_factor for x in a]
    else:
        a = a_without_penalty
        b_internal = [Fraction(x) * dearness_factor * q for x in a]
        if q != 1:
            penalty_flags.append('ALTERNATIVE HYPOTHESIS: the penalty multiplies the whole '
                                 'rounded A value in the A-to-B step')
    k, flags = star_permil(data, stage, star, allow_experimental)
    final_internal = [x * Fraction(k, 1000) for x in b_internal]
    final = [ceil_fraction(x) for x in final_internal]
    return {
        'model_version': data['model_version'],
        'order': ['Vo', 'Da', 'Vi'], 'family': family, 'stage': stage,
        'stats': stats, 'entrance_star': star,
        'judging_icons': normalize_icons(judging_icons),
        'base_curve_bonus_permil_unrounded': [float(x) for x in interpolated],
        'no_penalty_stage_A_percents': a_without_penalty,
        'stage_A_percents': a,
        'cross_stat_penalty': {**penalty_details, 'remaining_factor': float(q),
                               'placement': penalty_placement},
        'dearness_factor': float(dearness_factor),
        'stage_B_percents_unrounded': [float(x) for x in b_internal],
        'stage_B_display_percents': [ceil_fraction(x) for x in b_internal],
        'star_factor_permil': k, 'star_factor': k / 1000,
        'final_percents_unrounded': [float(x) for x in final_internal],
        'score_percents': final,
        'display_multipliers': [x / 100 for x in final],
        'scope': ('Displayed multipliers; penalty is an unvalidated hypothesis' if q != 1
                  else 'Displayed multipliers; no cross-stat penalty assumed'),
        'evidence_flags': penalty_flags + flags,
    }


def audit(data):
    rows = []
    for sample in data['samples']:
        result = predict(data, family=sample['curve_family_for_analysis'],
                         stage=sample['stage'], stats=sample['stats'],
                         star=sample['entrance_star'],
                         judging_icons=sample.get('judging_icons'),
                         all_qualified=sample.get('judging_icons') is None,
                         allow_experimental=True)
        actual = sample['score_percents']
        errors = [p - o for p, o in zip(result['score_percents'], actual)]
        rows.append({'id': sample['id'], 'observed': actual,
                     'predicted': result['score_percents'], 'errors_percentage_points': errors,
                     'all_three_match': errors == [0, 0, 0],
                     'source_quality': sample['source_quality']})
    return {'sample_count': len(rows),
            'matching_complete_triples': sum(r['all_three_match'] for r in rows),
            'matching_final_percent_fields': sum(x == 0 for r in rows for x in r['errors_percentage_points']),
            'total_final_percent_fields': len(rows) * 3,
            'note': 'Descriptive reconstruction of the assembled corpus; not a blind validation set.',
            'rows': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=DATA_PATH)
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--family')
    parser.add_argument('--stage', choices=STAGES)
    parser.add_argument('--stats', nargs=3, type=int, metavar=('VO', 'DA', 'VI'))
    parser.add_argument('--star', type=int)
    parser.add_argument('--dearness-factor', default='1.5')
    parser.add_argument('--all-qualified', action='store_true',
                        help='Explicitly confirm that this sample has no cross-stat penalty')
    parser.add_argument('--judging-icons', nargs=3, metavar=('VO_ICON', 'DA_ICON', 'VI_ICON'))
    parser.add_argument('--penalty-mode', choices=('none', 'settings-prior'), default='none')
    parser.add_argument('--penalty-thresholds', nargs=3, type=int, metavar=('VO_T', 'DA_T', 'VI_T'))
    parser.add_argument('--penalty-combination', choices=('additive', 'multiplicative'), default='additive')
    parser.add_argument('--penalty-placement', choices=('curve-bonus', 'after-A'), default='curve-bonus')
    parser.add_argument('--allow-experimental', action='store_true')
    args = parser.parse_args()
    data = load_data(args.data)
    if args.audit:
        result = audit(data)
    else:
        if any(x is None for x in (args.family, args.stage, args.stats, args.star)):
            parser.error('--family, --stage, --stats and --star are required')
        try:
            result = predict(data, family=args.family, stage=args.stage, stats=args.stats,
                             star=args.star, all_qualified=args.all_qualified,
                             judging_icons=args.judging_icons,
                             dearness_factor=args.dearness_factor,
                             penalty_mode=args.penalty_mode,
                             penalty_thresholds=args.penalty_thresholds,
                             penalty_combination=args.penalty_combination,
                             penalty_placement=args.penalty_placement,
                             allow_experimental=args.allow_experimental)
        except ValueError as error:
            parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
