"""Explicit short courses for isolated full-pipeline throughput diagnostics."""
from collections import Counter
import copy


def shorten_course(entry, spec, metadata, config):
    turns = config.get('performance_probe_turns')
    if turns is None:
        return entry, spec, metadata
    if not config.get('performance_probe') or type(turns) is not int or not 3 <= turns <= 12:
        raise ValueError('Short courses require performance_probe and 3..12 turns')
    entry, spec, metadata = copy.deepcopy((entry, spec, metadata))
    colors = list(entry['context']['turn_types'][:turns])
    quotas = {color: colors.count(color) for color in ('vocal', 'dance', 'visual')}
    entry['context']['turn_types'] = colors
    entry['context']['stage']['turnCounts'] = quotas
    entry['context']['stage']['linkTurnCounts'] = []
    entry['context']['stage']['firstTurns'] = {color: float(color == colors[0]) for color in quotas}
    public = spec['generalist_task']
    public.update(base_turn_count=len(colors), turn_counts=dict(quotas), turn_types=list(colors))
    metadata.update(course_id=metadata['course_id'] + ':perf-%st' % len(colors),
                    turn_count=len(colors), turn_counts=dict(quotas), turn_types=list(colors),
                    public_context=copy.deepcopy(public), performance_probe=True)
    return entry, spec, metadata


def select_update_records(records, config):
    """Keep a short probe update full while covering every available phase/profile."""
    limit = config.get('performance_probe_update_records_per_rank')
    if limit is None:
        return records
    if (not config.get('performance_probe') or type(limit) is not int or limit < 1
            or config.get('sample_efficiency', {}).get('advantage_mode', 'mc') != 'mc'):
        raise ValueError('A bounded probe update requires explicit performance_probe and MC returns')
    from collections import defaultdict
    buckets = defaultdict(list)
    for record in records:
        buckets[(record['profile'], record['encoded'].phase)].append(record)
    selected = []
    for offset in range(max(map(len, buckets.values()), default=0)):
        for key in sorted(buckets):
            if offset < len(buckets[key]):
                selected.append(buckets[key][offset])
                if len(selected) == limit:
                    return selected
    return selected
