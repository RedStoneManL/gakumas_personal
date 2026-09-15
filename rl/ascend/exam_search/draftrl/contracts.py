"""Hard experiment contract checked before every native opening."""
from collections import Counter
from .deck_size import counted_size
from .duplicate_limits import family_ids, validate as validate_copy_limit


def support_card_count(cards, spec):
    """Count physical support-granted copies, including preset coverage cards."""
    support_ids = set(spec['support_card_ids'])
    return sum(card['definition_id'] in support_ids for card in cards)


def validate_construction_sources(cards, spec):
    """Apply source restrictions independently of drafting or the finish gate."""
    limit = spec['support_card_limit']
    if type(limit) is not int or limit < 0:
        raise ValueError('support card limit must be a nonnegative integer')
    banned = set(spec['banned_card_ids'])
    if any(card['definition_id'] in banned for card in cards):
        raise ValueError('banned card in construction, including Prima Stella')
    if support_card_count(cards, spec) > limit:
        raise ValueError('support card total exceeds the physical-copy limit')


def validate_entry(entry, spec, catalog, drinks):
    validate_construction_sources(entry['cards'], spec)
    validate_copy_limit(entry['cards'], family_ids(catalog), spec.get('max_same_name'), spec.get('max_same_name_overrides'))
    defs={d['id']:d for d in catalog['cards']}
    rules=spec['guidance']['card_rules']
    ids=Counter(c['definition_id'] for c in entry['cards'])
    assert spec['min_cards']<=counted_size(entry['cards'],spec)<=spec['max_cards']
    assert len({c['instance_id'] for c in entry['cards']})==len(entry['cards'])
    assert entry['context']['plan']==spec['plan']
    for c in entry['cards']:
        d=defs[c['definition_id']]
        assert str(d['id']) in rules and rules[str(d['id'])]['required_level']<=76
        assert d['id'] not in (775,776) and d['plan'] in (spec['plan'],'free')
        assert not d.get('pIdolId') or d['pIdolId']==entry['context']['idol_id']
        assert not d['unique'] or ids[d['id']]==1
        assert sum(c['customizations'].values())<=rules[str(d['id'])]['max_guidance']
    assert not (Counter(c['definition_id'] for c in spec['fixed_cards'])-ids)
    chosen={r['key'] for r in spec['candidates'] if ids[r['card']['definition_id']]}
    assert all(len(chosen.intersection(g['candidate_keys']))<=1 for g in spec['mutual_exclusions'])
    assert sum(bool(c['customizations']) for c in entry['cards'])<=7
    capacity = spec.get('drink_capacity', 4)
    assert type(capacity) is int and 0 <= capacity <= 4
    assert len(entry['resources']['drinks'])<=capacity and set(entry['resources']['drinks'])<=set(drinks)
    memory_capacity = spec['memory']['capacity']
    assert spec['memory_mode'] in ('none', 'hif')
    assert type(memory_capacity) is int and memory_capacity == (0 if spec['memory_mode'] == 'none' else 4)
    assert len(entry['memory_abilities']) <= memory_capacity
    assert spec['memory_mode'] != 'none' or not spec['memory']['abilities']
    mids=[m['id'] for m in entry['memory_abilities']]
    assert len(mids)==len(set(mids)) and set(mids)<={m['id'] for m in spec['memory']['abilities']}
