"""Budgeted pre-exam guidance. Hard legality, no hand-written score bonuses."""
import copy


class Guidance:
    def __init__(self, entry, spec):
        self.entry = copy.deepcopy(entry)
        self.spec = spec
        self.rules = spec['guidance']
        self.spent = 0
        self.free_used = 0
        self.free_green_used = 0
        self.free_by_card = {}
        self.done = False
        self.history = []
        required = spec.get('required_initial_guidance', [])
        if required:
            # Only this trial's single, verified initial green is admitted. Replay
            # it through native budget legality; no general pre-upgrade bypass.
            expected = {'method': 'guide_card', 'instance_id': 'focus:card:591',
                        'customization_id': '37', 'level': 1, 'use_free_first': True,
                        'list_price': 40, 'p_cost': 0, 'free_card_slots_cost': 1}
            if required != [expected] or spec['profile_id'] != 'saki-hif':
                raise ValueError('Unsupported precommitted guidance receipt')
            cards = [c for c in self.entry['cards'] if c['instance_id'] == expected['instance_id']]
            if len(cards) != 1 or cards[0]['definition_id'] != 591 or cards[0]['customizations'] != {'37': 1}:
                raise ValueError('Precommitted card does not match its guidance receipt')
            cards[0]['customizations'] = {}
        if any(c['customizations'] for c in self.entry['cards']):
            raise ValueError('guidance must start at zero; pre-attached green upgrades bypass the budget')
        for action in required:
            self.apply(action)
            self.history[-1]['forced_environment_setup'] = True

    @property
    def guided_cards(self):
        return sum(bool(c['customizations']) for c in self.entry['cards'])

    def public_budget(self):
        return {'p_spent': self.spent, 'p_remaining': self.rules['p_budget'] - self.spent,
                'free_first_used': self.free_used, 'free_first_remaining': self.rules['free_first_cards'] - self.free_used,
                'free_guidance_steps_used': self.free_green_used,
                'guided_cards': self.guided_cards, 'guided_cards_remaining': self.rules['max_guided_cards'] - self.guided_cards}

    def free_eligibility(self, card, price):
        """Return (eligible, newly consumed card slots) for the next green.

        The optional white-card rule must be explicitly configured. A card's
        second free green requires its first green to have used the offer, so
        a paid high-price first green cannot be followed by a free second one.
        """
        count = sum(card['customizations'].values())
        claimed = self.free_by_card.get(card['instance_id'], 0)
        rule = self.rules['card_rules'][str(card['definition_id'])]
        white = self.rules.get('white_card_free')
        if white and rule['rarity'] in white['rarities']:
            if price != white['list_price'] or count >= white['max_green_count'] or claimed != count:
                return False, 0
            slot_cost = int(not count and white['uses_free_card_slot'])
            return self.free_used + slot_cost <= self.rules['free_first_cards'], slot_cost
        return not count and self.free_used < self.rules['free_first_cards'], 1

    def card_budget(self, card):
        return {'free_guidance_steps_used': self.free_by_card.get(card['instance_id'], 0)}

    def actions(self):
        if self.done:
            return []
        actions = []
        for card in self.entry['cards']:
            current = card['customizations']
            count = sum(current.values())
            rule = self.rules['card_rules'][str(card['definition_id'])]
            if count >= rule['max_guidance'] or (not count and self.guided_cards >= self.rules['max_guided_cards']):
                continue
            for key, track in rule['tracks'].items():
                level = current.get(key, 0)
                if level >= track['max']:
                    continue
                price = track['prices'][level]
                for free in (False, True):
                    eligible, slot_cost = self.free_eligibility(card, price)
                    if free and not eligible:
                        continue
                    paid = 0 if free else price
                    if self.spent + paid > self.rules['p_budget']:
                        continue
                    actions.append({'method': 'guide_card', 'instance_id': card['instance_id'],
                                    'customization_id': key, 'level': level + 1,
                                    'use_free_first': free, 'list_price': price, 'p_cost': paid,
                                    'free_card_slots_cost': slot_cost if free else 0})
        actions.append({'method': 'finish_guidance'})
        return actions

    def apply(self, action):
        if action not in self.actions():
            raise ValueError('illegal guidance action: budget, free-first eligibility, seven-card limit, or level prerequisite')
        if action['method'] == 'finish_guidance':
            self.done = True
        else:
            card = next(c for c in self.entry['cards'] if c['instance_id'] == action['instance_id'])
            card['customizations'][action['customization_id']] = action['level']
            self.spent += action['p_cost']
            self.free_used += action['free_card_slots_cost']
            if action['use_free_first']:
                self.free_green_used += 1
                self.free_by_card[card['instance_id']] = self.free_by_card.get(card['instance_id'], 0) + 1
        self.history.append({'action': copy.deepcopy(action), 'budget_after': self.public_budget()})
