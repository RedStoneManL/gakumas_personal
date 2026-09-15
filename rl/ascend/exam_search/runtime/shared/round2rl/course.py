"""First production curriculum: Shro Round2, editable v2 API, before opening.

This bounded training distribution is not a claim about natural produce reachability.
The Arena remains the sole executor of refill, buffs, drinks and scores.
"""
import random
import json
from pathlib import Path

COURSE_CONFIG = json.loads((Path(__file__).resolve().parents[1] / 'configs/course.json').read_text(encoding='utf-8'))


def entry_for(api, card_count, seed):
    d = COURSE_CONFIG['distribution']
    if card_count not in d['card_counts']:
        raise ValueError('card count is outside the configured curriculum')
    rng = random.Random(seed + 11000000)
    # Preserve a core while exposing both retained and missing support combinations.
    core, options = d['core_cards'], d['support_card_copies']
    need = card_count - len(core)
    cards = core + rng.sample(options, min(need, len(options)))
    cards += [rng.choice(d['overflow_card_pool']) for _ in range(max(0, need - len(options)))]
    drinks = rng.sample(d['drink_pool'], rng.randint(d['drink_count_min'], d['drink_count_max']))
    entry = api.hif_round2_entry(cards=cards, stamina=rng.choice(d['stamina_choices']),
                               drinks=drinks, family=COURSE_CONFIG['name'], **COURSE_CONFIG['entry'])
    entry['source']['kind'] = 'constrained_curriculum'
    return entry
