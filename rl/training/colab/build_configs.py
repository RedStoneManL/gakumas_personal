"""Materialize reviewed Colab starting configurations; never start training."""
from copy import deepcopy
import json
from pathlib import Path


def main(here=None):
    here = Path(here).resolve() if here is not None else Path(__file__).resolve().parent
    training = here.parent
    target = here / 'configs'
    target.mkdir(exist_ok=True)
    full = json.loads((training / 'configs/full_produce.json').read_text(encoding='utf-8'))
    full.update(device='cuda', episodes_per_update=8, eval_every_updates=5, eval_episodes=8)
    full['ppo']['microbatch_size'] = 2
    full['ppo']['setup_entropy_coefficient'] = 0.05
    loadout = {
        'idol_card_id': 'i_card-shro-3-018', 'producer_level': 76,
        'idol_rank': 6, 'dearness_level': 37, 'auto_support_cards': False,
        'support_card_ids': ['s_card-2-0007', 's_card-3-0030', 's_card-3-0064',
                             's_card-3-0069', 's_card-3-0070', 's_card-3-0077'],
        'support_card_levels': [50, 60, 60, 60, 60, 60],
    }
    research = {'growth_panel_levels': {
        '01': 5, '02': 5, '03': 5, '04': 5, '05': 6, '06': 6, '07': 6, '08': 6, '09': 6}}
    full['task_config'].update(loadout=loadout, research_config=research, setup_mode='given')
    mixed = deepcopy(full)
    mixed.update(episodes_per_update=10, eval_episodes=10)
    supports = {
        1: loadout['support_card_ids'],
        2: ['s_card-2-0007', 's_card-3-0009', 's_card-3-0024',
            's_card-3-0069', 's_card-3-0026', 's_card-3-0035'],
        3: ['s_card-2-0007', 's_card-3-0032', 's_card-3-0021',
            's_card-3-0069', 's_card-3-0043', 's_card-3-0047'],
    }
    mixed['task_config']['loadout_pool'] = [
        {'name': name, 'loadout': {**deepcopy(loadout), 'idol_card_id': idol,
                                  'support_card_ids': deepcopy(supports[plan])},
         'research_config': deepcopy(research)}
        for name, idol, plan in (
            ('saki-wild', 'i_card-hski-3-017', 2),
            ('saki-hif', 'i_card-hski-3-018', 3),
            ('hiro-hif', 'i_card-shro-3-018', 1),
            ('ume-campus', 'i_card-hume-3-006', 3),
            ('liliya-xmas', 'i_card-kllj-3-005', 2),
        )]
    exam = json.loads((training / 'configs/exam_score.json').read_text(encoding='utf-8'))
    exam.update(device='cuda', episodes_per_update=16, eval_every_updates=5, eval_episodes=8)
    exam['ppo']['microbatch_size'] = 2
    exam['ppo']['setup_entropy_coefficient'] = 0.05
    configurations = [('full_produce', full), ('full_produce_mixed', mixed), ('exam_score', exam)]
    inventory_path = target / 'research_inventory.json'
    if inventory_path.is_file():
        inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
        if inventory.get('schema_version') != 'gakumas-setup-inventory/1':
            raise ValueError('Research inventory schema is not supported')
        if not isinstance(inventory.get('supports'), list) or not isinstance(inventory.get('memories'), list):
            raise ValueError('Research inventory must explicitly list supports and memories')
        for name, mode in (('full_produce_select', 'select'), ('full_produce_setup_mixed', 'mixed')):
            value = deepcopy(mixed)
            value['task_config'].update(setup_mode=mode, setup_inventory=deepcopy(inventory))
            configurations.append((name, value))
    else:
        print('Research inventory is not present; selectable setup configurations are not generated.')
    for name, value in configurations:
        (target / f'{name}.json').write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
