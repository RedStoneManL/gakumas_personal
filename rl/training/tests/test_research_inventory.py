"""Audit the actual research pool rather than a handful of toy memories."""
import importlib.util
import json
from pathlib import Path


def test_research_pool_is_reproducible_and_obeys_user_budget():
    import sys
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root / 'third_party/gakumas_arena'))
    from gakumas_arena.env import get_repository
    path = Path(__file__).resolve().parents[1] / 'colab/build_research_inventory.py'
    spec = importlib.util.spec_from_file_location('research_inventory_builder', path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    repository = get_repository()
    inventory, audit = builder.build_inventory(repository)
    on_disk = json.loads((path.parent / 'configs/research_inventory.json').read_text(encoding='utf8'))
    assert inventory == on_disk
    assert len(inventory['supports']) == len(repository.support_cards.rows)
    components = inventory['memory_components']
    assert audit['card_variant_count'] == len(components['cards']) > audit['card_identity_count']
    seen = set()
    for item in components['gold_factors']:
        wire = item['spec']
        ability = repository.load_table('MemoryAbility').first(wire['ability_ids'][0])
        skill = next(row for row in repository.load_table('ProduceSkill').all(ability['skillId'])
                     if row['level'] == wire['ability_levels'][0])
        assert skill['rarity'] == 'SkillRarity_Sr'
        assert skill['id'] not in seen
        seen.add(skill['id'])
    # HIF mechanics use another rarity classification and must not disappear.
    assert len(components['hif_abilities']) == 105
    for item in components['cards']:
        card = item['spec']['produce_card']
        row = repository.card_row_by_upgrade(card['card_id'], card['upgrade_count'])
        budget = 2 if row['rarity'] == 'ProduceCardRarity_R' else 1
        assert len(card['customize_ids']) + int(card['phase_type'] == builder.START) <= budget
        assert not row['originIdolCardId'] and not row['originSupportCardId']
        assert row['unlockProducerLevel'] <= 76
        assert card['upgrade_count'] == 1
