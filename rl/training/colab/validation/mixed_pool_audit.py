"""Every configured profile through a natural terminal with public encoding.

Deterministic first-play/accept policy; diagnostic only, never PPO training data.
No game scores, rivals, turns, initialization stats, or resources are overridden.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

TRAINING = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TRAINING))
from gakumas_training.contracts import PolicySelection
from gakumas_training.encoding import DecisionEncoder
from gakumas_training.tasks import FullProduceConfig, FullProduceTask


def main():
    config_file = TRAINING / 'colab/configs/full_produce_mixed.json'
    config = json.loads(config_file.read_text(encoding='utf8'))
    task = FullProduceTask(FullProduceConfig(**config['task_config']))
    before = deepcopy(asdict(task.config))
    encoder = DecisionEncoder(max_nodes=config['model']['max_nodes'])
    result = {'schema': 'gakumas-mixed-pool-natural-audit/1', 'not_training': True,
              'seed_selection': 'seed_mod_pool_size_v1', 'profiles': []}
    output = Path(__file__).with_name('mixed-pool-audit.json')
    try:
        for index, entry in enumerate(task.config.loadout_pool):
            seed = config['seed'] + index
            expected = task.select_profile(seed)[0]
            assert expected == entry['name']
            assert task.select_profile(seed) == task.select_profile(seed)
            counts, peak, first = Counter(), 0, None
            def policy(decision):
                nonlocal peak, first
                counts[decision.kind] += 1
                encoded = encoder.encode(decision)
                peak = max(peak, encoded.node_count)
                if first is None:
                    public = decision.observation['produce']
                    first = {'state': {key: public['state'][key] for key in (
                        'vocal', 'dance', 'visual', 'vocal_growth', 'dance_growth', 'visual_growth',
                        'stamina', 'max_stamina', 'producer_level', 'idol_rank')},
                        'card_ids': [card['id'] for card in public['deck']],
                        'support_skills': deepcopy(public['support_skills']),
                        'produce_items': deepcopy(public['produce_items']),
                        'character_id': public['rules']['idol_exam_profile']['character_id'],
                        'mechanism_count': len(decision.observation['mechanisms']),
                        'encoded_nodes': encoded.node_count}
                chosen = 0
                if decision.kind == 'outer':
                    for kind in ('special_finish', 'interval_finish', 'consult_finish', 'audition_accept'):
                        match = next((i for i, candidate in enumerate(decision.candidates)
                                      if candidate.get('action_type') == kind), None)
                        if match is not None:
                            chosen = match
                            break
                elif decision.kind == 'exam_action':
                    chosen = next((i for i, candidate in enumerate(decision.candidates)
                                   if candidate['type'] == 'play'), 0)
                return PolicySelection(chosen, 0, 0, 0)
            started = time.perf_counter()
            record = {'name': expected, 'seed': seed, 'idol_card_id': entry['loadout']['idol_card_id']}
            try:
                episode = task.run_episode(policy, seed=seed, policy_version=0)
                assert episode.metadata['loadout_profile'] == expected
                assert asdict(task.config) == before
                record.update(ok=True, termination=episode.termination, raw_score=episode.raw_score,
                    accepted_exam_count=episode.metadata['accepted_exam_count'],
                    rating_provenance=episode.metadata['rating_provenance'])
            except Exception as error:
                record.update(ok=False, error_type=type(error).__name__, error=str(error))
            record.update(first_public=first, decision_kinds=dict(counts), peak_encoded_nodes=peak,
                          seconds=time.perf_counter()-started)
            result['profiles'].append(record)
            output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
            print(json.dumps({k: v for k, v in record.items() if k not in ('first_public', 'rating_provenance')}, ensure_ascii=False), flush=True)
        result['all_natural_terminals_encoded'] = all(row['ok'] for row in result['profiles'])
        result['configuration_unchanged'] = asdict(task.config) == before
        result['arena_version'] = task.arena_version
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf8')
        return int(not result['all_natural_terminals_encoded'])
    finally:
        task.close()


if __name__ == '__main__':
    raise SystemExit(main())
