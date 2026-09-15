"""Optional draft regularization. Exam scores and other phase targets stay raw."""
import math
import statistics
from collections import Counter
from .duplicate_limits import family_ids, counts as family_counts


def duplicate_stats(cards, fixed_cards, catalog, config):
    cfg = config.get('practice', {}).get('duplicates', {})
    free = cfg.get('free_copies', 3)
    coefficient, cap = cfg.get('coefficient', .01), cfg.get('cap', .75)
    if type(free) is not int or free < 1 or not all(
            math.isfinite(x) and x >= 0 for x in (coefficient, cap)):
        raise ValueError('Invalid duplicate soft penalty')
    # Plus and guidance variants of the same named card share a family. Do not
    # merge Switch forms with different names, or collapse ordered effects.
    families = family_ids(catalog)
    counts = family_counts(cards, families)
    fixed = family_counts(fixed_cards, families)
    excess = sum(max(0, n - free) ** 2 - max(0, fixed[k] - free) ** 2
                 for k, n in counts.items())
    if excess < 0 or any(fixed[k] > counts[k] for k in fixed):
        raise ValueError('Forced cards disappeared before draft reward')
    penalty = min(cap, coefficient * excess) if cfg.get('enabled', False) else 0.
    return {'penalty': penalty, 'excess_squared': excess,
            'max_copies': max(counts.values(), default=0), 'hard_limit': cfg.get('max_same_name'),
            'hard_limit_overrides': cfg.get('max_same_name_overrides',{}),
            'distinct_families': len(counts),
            'over_threshold': {k: n for k, n in counts.items() if n > free}}


def apply_draft_penalty(records, summaries):
    """Run AFTER prefix return averaging. Never penalize exam/drink/memory play."""
    penalties = {f"joint:{s['seed']}": s['duplicate_stats']['penalty']
                 for s in summaries if s.get('sampling_source') == 'joint'}
    changed = 0
    for r in records:
        if r['encoded'].phase != 2:
            continue
        if 'draft_duplicate_penalty' in r:
            raise ValueError('Duplicate shaping was already applied')
        penalty = penalties[r['episode_id']]
        r['unregularized_return'] = r['return']
        r['draft_duplicate_penalty'] = penalty
        r['return'] -= penalty
        changed += 1
    values = list(penalties.values())
    return {'mean_penalty': statistics.mean(values) if values else 0.,
            'max_penalty': max(values, default=0.), 'penalized_decks': sum(v > 0 for v in values),
            'joint_decks': len(values), 'draft_records': changed,
            'scope': 'draft_only', 'raw_exam_score_preserved': True}
