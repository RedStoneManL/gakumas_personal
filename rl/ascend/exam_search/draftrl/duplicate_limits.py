"""Construction copy limits; opening and in-exam card generation are native rules."""
from collections import Counter


def family_ids(catalog):
    result = {}
    for row in catalog['cards']:
        name = row['name']
        if row.get('upgraded') and name.endswith(('+', '＋')):
            name = name[:-1]
        result[row['id']] = name
    return result


def limit(config):
    value = config.get('practice', {}).get('duplicates', {}).get('max_same_name')
    if value is not None and (type(value) is not int or value < 1):
        raise ValueError('Same-name copy limit must be a positive integer')
    return value


def counts(cards, families):
    return Counter(families[c['definition_id']] for c in cards)


def validate_overrides(value, families=None):
    value = {} if value is None else value
    if not isinstance(value, dict) or any(not isinstance(k,str) or not k or type(v) is not int or v < 1 for k,v in value.items()):
        raise ValueError('Same-name overrides require nonempty names and positive integer limits')
    if families is not None and not set(value).issubset(set(families.values())):
        raise ValueError('Unknown card family in same-name override')
    return dict(value)


def overrides(config):
    result = validate_overrides(config.get('practice',{}).get('duplicates',{}).get('max_same_name_overrides'))
    if result and limit(config) is None:
        raise ValueError('Named overrides require a default copy limit')
    return result


def family_limit(name, maximum, exceptions=None):
    return (exceptions or {}).get(name, maximum)


def within_limits(actual, maximum, exceptions=None):
    return all(family_limit(name, maximum, exceptions) is None or n <= family_limit(name, maximum, exceptions)
               for name,n in actual.items())


def validate(cards, families, maximum, exceptions=None):
    exceptions = validate_overrides(exceptions, families)
    actual = counts(cards, families)
    if not within_limits(actual, maximum, exceptions):
        raise ValueError('Same-name construction copy limit exceeded')
    return actual


def prepare_spec(spec, config):
    # assign/augment already provide a fresh per-episode spec.
    spec['max_same_name'] = limit(config)
    spec['max_same_name_overrides'] = overrides(config)
    return spec


def prune_bank(bank, catalog, config):
    """Preserve source checkpoints, but do not rehearse forbidden old loadouts."""
    maximum = limit(config)
    removed = {}
    if bank is None or maximum is None:
        return removed
    families = family_ids(catalog)
    exceptions = validate_overrides(overrides(config), families)
    for profile, rows in bank.rows.items():
        kept = [r for r in rows if within_limits(counts(r['entry']['cards'], families), maximum, exceptions)]
        removed[profile] = len(rows) - len(kept)
        bank.rows[profile] = kept
    return removed
