"""Bounded, user-nominated loadout practice; never a scripted play teacher."""
import copy
import statistics
from collections import Counter
from .deck_size import counted_size
from .guidance import Guidance

PROFILE = 'saki-hif'
CARD = 591
CUSTOM = '37'
INSTANCE = 'focus:card:591'


def settings(config):
    return config.get('practice', {}).get('keycard_focus', {})


def active(config, profile, *, training=True):
    cfg = settings(config)
    if not cfg.get('enabled') or profile != PROFILE:
        return False
    if (cfg.get('profile_id'), cfg.get('card_id'), str(cfg.get('customization_id'))) != (PROFILE, CARD, CUSTOM):
        raise ValueError('This focused trial is specifically Saki HIF / card 591 / guidance 37')
    if config.get('_keycard_probe'):
        if training:
            raise ValueError('A diagnostic configuration cannot create training samples')
        return True
    if not training:
        return False
    start, count = cfg['start_batch'], cfg['batches']
    if type(start) is not int or type(count) is not int or start < 0 or count < 1:
        raise ValueError('Focus requires a bounded completed-batch interval')
    return start <= config['_completed_batches'] < start + count


def prepare(entry, spec, config, profile, *, training):
    if not active(config, profile, training=training):
        return entry, spec
    entry, spec = copy.deepcopy(entry), copy.deepcopy(spec)
    if any(c['instance_id'] == INSTANCE for c in entry['cards']):
        raise ValueError('Focus card was injected twice')
    candidate = next(r for r in spec['candidates'] if r['card']['definition_id'] == CARD)
    if candidate['unique'] or candidate['required_level'] > spec['producer_level']:
        raise ValueError('Focused card differs from the verified native definition')
    card = copy.deepcopy(candidate['card'])
    card['instance_id'] = INSTANCE
    entry['cards'].append(card)
    # Select an ordinary legal budget action, not an extra unaccounted upgrade.
    guidance = Guidance(entry, spec)
    action = next(a for a in guidance.actions() if a.get('instance_id') == INSTANCE
                  and a.get('customization_id') == CUSTOM and a['use_free_first'])
    guidance.apply(action)
    entry = guidance.entry
    spec['fixed_cards'] = copy.deepcopy(entry['cards'])
    fixed = counted_size(entry['cards'], spec)
    spec['min_free_slots'] = max(0, spec['min_cards'] - fixed)
    spec['max_free_slots'] = spec['max_cards'] - fixed
    if spec['max_free_slots'] < 1:
        raise ValueError('No free construction slots remain')
    spec['required_initial_guidance'] = [copy.deepcopy(action)]
    spec['guidance']['precommitted_budget'] = guidance.public_budget()
    return entry, spec


def filter_bank_tasks(tasks, config):
    # Do not retrofit old loadouts or teach a contradictory absence of the card.
    return [t for t in tasks if not active(config, t['metadata']['profile'])]


def tracker(entry):
    cards = {c['instance_id']: c for c in entry['cards'] if c['definition_id'] == CARD}
    return {'cards': cards, 'legal_turns': set(), 'hand_turns': set(), 'plays': []}


def observe(tracking, obs, command):
    if not tracking['cards']:
        return
    turn = obs['state']['turnsElapsed'] + 1
    for iid in set(obs['zones']['hand']).intersection(tracking['cards']):
        tracking['hand_turns'].add((iid, turn))
    for action in obs['actions']:
        if action.get('type') == 'play' and action.get('instance_id') in tracking['cards']:
            tracking['legal_turns'].add((action['instance_id'], turn))
    action = command.get('action', {})
    if action.get('type') == 'play' and action.get('instance_id') in tracking['cards']:
        if (action['instance_id'], turn) not in tracking['legal_turns']:
            raise ValueError('Recorded keycard play is not legal in the public observation')
        tracking['plays'].append({'instance_id': action['instance_id'], 'turn': turn,
            'stance': obs['state'].get('stance'), 'fullPowerCharge': obs['state'].get('fullPowerCharge'),
            'score_before': obs['state'].get('score')})


def finish(tracking):
    per_copy = Counter(p['instance_id'] for p in tracking['plays'])
    return {'copies': len(tracking['cards']), 'forced_present': INSTANCE in tracking['cards'],
            'limit_removed_copies': sum(c['customizations'].get(CUSTOM, 0) > 0 for c in tracking['cards'].values()),
            'plays': tracking['plays'], 'play_count': len(tracking['plays']),
            'forced_play_count': per_copy[INSTANCE],
            'max_uses_same_copy': max(per_copy.values(), default=0),
            'legal_card_turns': len(tracking['legal_turns']), 'hand_card_turns': len(tracking['hand_turns']),
            'forced_legal_turns': sum(i == INSTANCE for i, _ in tracking['legal_turns'])}


def summarize(rows):
    rows = [r for r in rows if r.get('keycard_usage', {}).get('forced_present')]
    if not rows:
        return {'games': 0}
    usages = [r['keycard_usage'] for r in rows]
    opportunities = [u for u in usages if u['forced_legal_turns']]
    return {'games': len(rows), 'score_mean': statistics.mean(r['score'] for r in rows),
            'normalized_mean': statistics.mean(r['normalized_score'] for r in rows),
            'forced_legal_games': len(opportunities),
            'forced_used_games': sum(u['forced_play_count'] > 0 for u in usages),
            'forced_reused_games': sum(u['forced_play_count'] > 1 for u in usages),
            'legal_but_unused_games': sum(u['forced_play_count'] == 0 for u in opportunities),
            'mean_forced_uses': statistics.mean(u['forced_play_count'] for u in usages),
            'max_forced_uses': max(u['forced_play_count'] for u in usages),
            'play_turn_counts': dict(Counter(str(p['turn']) for u in usages for p in u['plays'] if p['instance_id'] == INSTANCE))}
