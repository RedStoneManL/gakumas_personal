"""Construction slots are separate from the physical deck given to Arena.

Only explicit Prima Stella registry IDs are exempt. In particular, rarity L,
idol originals, forced-hand cards and sleepiness are not implicit exemptions.
An old spec without this rule retains its original physical-card count.
"""


def slot_cost(card, spec):
    return int(card['definition_id'] not in spec.get('deck_size_exempt_ids', ()))


def exempt_count(cards, spec):
    return sum(not slot_cost(card, spec) for card in cards)


def counted_size(cards, spec):
    return sum(slot_cost(card, spec) for card in cards)
