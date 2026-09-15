"""Arena adapter for the user-approved HIF research pack (2026-09-09).

The adjacent reference implementation and data are preserved byte-for-byte.
Only resolved display percentages enter the golden engine. Provenance records
the internal values and assumptions, so no second star/dearness factor applies.
"""

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from numbers import Real
from pathlib import Path

from . import _hif_reference as reference


@lru_cache(maxsize=1)
def _research():
    data = reference.load_data()
    hashes = {
        'data_sha256': sha256(reference.DATA_PATH.read_bytes()).hexdigest(),
        'reference_code_sha256': sha256(Path(reference.__file__).read_bytes()).hexdigest(),
    }
    return data, hashes


def _integer(value, name):
    # ProduceRuntime stores integer game stats in float fields. Accept 915.0,
    # but never silently truncate a fractional curriculum input such as 915.9.
    if isinstance(value, bool) or not isinstance(value, Real) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    try:
        integer = int(value)
    except (ValueError, OverflowError) as error:
        raise ValueError(f'{name} must be a finite integer') from error
    if value != integer:
        raise ValueError(f'{name} must be an integer; fractional values are not rounded')
    return integer


def calculate_hif_multiplier(*, family, stage, stats, star, **options):
    """Return percent inputs plus every intermediate and research evidence flag.

    family is the fixed exam curve family, never the descending order of stats.
    stage: selection1/selection2/selection3/round1/round2. stats: Vo/Da/Vi.
    Options follow the supplied model: judging_icons or all_qualified,
    dearness_factor (default 1.5), and explicit experimental penalty/star options.
    """
    if len(stats) != 3:
        raise ValueError('stats must contain Vo / Da / Vi')
    stats = [_integer(x, f'stats[{i}]') for i, x in enumerate(stats)]
    star = _integer(star, 'star')
    data, hashes = _research()
    result = reference.predict(data, family=family, stage=stage, stats=stats, star=star, **options)
    result.update(deepcopy(hashes))
    result['scoring_source'] = data['model_version']
    result['arena_score_input'] = 'display_percent'
    result['all_qualified_assumption'] = bool(options.get('all_qualified', False))
    result['experimental_options_enabled'] = bool(options.get('allow_experimental', False))
    result['dearness_factor_source'] = (
        'explicit' if 'dearness_factor' in options else 'research_pack_default_1.5'
    )
    result['exam_config_id'] = data['families'][family]['config_ids'][stage]
    result['configured_turn_count'] = data['stages'][stage]['turn_count']
    result['evidence_flags'].append(
        'ARENA APPROXIMATION: displayed integer percentages feed the golden score engine; '
        'the pack does not identify client card-score rounding'
    )
    return deepcopy(result)


_PRODUCE_STAGES = {
    ('produce-007', 'ProduceStepType_AuditionMid1'): 'selection1',
    ('produce-007', 'ProduceStepType_AuditionMid2'): 'selection2',
    ('produce-007', 'ProduceStepType_AuditionFinal'): 'selection3',
    ('produce-008', 'ProduceStepType_AuditionMid1'): 'round1',
    ('produce-008', 'ProduceStepType_AuditionFinal'): 'round2',
}


def resolve_hif_produce_scoring(context, config):
    """Resolve an exam_config's hif_scoring from the current entrance state.

    Keep explicit score_percents backward compatible. hif_scoring requires a
    family and qualification policy; stage/stats/star always come from produce.
    dearness_factor follows the pack unless explicitly supplied by the caller.
    """
    config = deepcopy(config)
    if 'hif_scoring' not in config:
        return config
    if 'score_percents' in config or 'scoring' in config:
        raise ValueError('choose hif_scoring or explicit scoring, not both')
    options = config.pop('hif_scoring')
    if any(k in options for k in ('stage', 'stats', 'star')):
        raise ValueError('Whole-produce hif_scoring binds stage/stats/star to the current entrance')
    stage = _PRODUCE_STAGES.get((context['produce_id'], context['stage_type']))
    if stage is None:
        raise ValueError('Unknown HIF produce/stage pair')
    state = context['state']
    result = calculate_hif_multiplier(
        stage=stage, stats=[state[k] for k in ('vocal', 'dance', 'visual')],
        star=state['star_quality'], **options,
    )
    config['score_percents'] = result['score_percents']
    config['scoring_source'] = result['scoring_source']
    config['scoring_provenance'] = result
    return config
