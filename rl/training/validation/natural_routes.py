"""Read-only six-support natural route probe; never feeds trajectories to PPO.

The guide controls outer choices. Examinations use actual native first-play
actions or an explicitly supplied old score actor. No scores/rivals/turns or
gameplay resource grants are replaced. Failures are useful coverage results.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

TRAINING = Path(__file__).resolve().parents[1]
WORKSPACE = TRAINING.parents[1]
sys.path.insert(0, str(TRAINING))
from gakumas_training.contracts import PolicySelection
from gakumas_training.tasks import FullProduceConfig, FullProduceTask


def run(seed, checkpoint=None, encode_public=False):
    task = FullProduceTask()
    sys.path.insert(0, str(task.arena_root / 'scripts'))
    from hif_s4_guide_policy import GuidePolicy, loadout_config
    from gakumas_arena.env import get_repository
    from gakumas_arena.loadouts import hif_growth_panel_max_levels
    repository = get_repository()
    config = FullProduceConfig(loadout=loadout_config(),
        research_config={'growth_panel_levels': hif_growth_panel_max_levels()})
    task = FullProduceTask(config)
    guide = GuidePolicy(repository)
    old_model = None
    if checkpoint is not None:
        sys.path.insert(0, str(WORKSPACE / 'rl' / 'round2'))
        import torch
        from round2rl.checkpoint import load
        from round2rl.encoding import encode, collate
        torch.set_num_threads(2)
        old_model, _ = load(checkpoint, 'cpu')
        old_model.eval()
    peaks = {'mechanisms': 0, 'json_characters': 0, 'support_skills': 0, 'encoded_nodes': 0}
    encoder = None
    if encode_public:
        from gakumas_training.encoding import DecisionEncoder
        encoder = DecisionEncoder()
    kinds = Counter()
    selected_by_exam_revision = {}

    def names(value):
        # Restore display-only card names for the pre-existing diagnostic guide.
        if isinstance(value, dict):
            out = {k: names(v) for k, v in value.items()}
            identity = value.get('id', '')
            if identity and 'name' not in out:
                for table in ('ProduceCard', 'ProduceDrink', 'ProduceCustomizeItem'):
                    row = repository.load_table(table).first(identity)
                    if row:
                        out['name'] = row.get('name', '')
                        break
            return out
        if isinstance(value, (list, tuple)):
            return [names(v) for v in value]
        return value

    def policy(decision):
        kinds[decision.kind] += 1
        observation = decision.observation
        peaks['mechanisms'] = max(peaks['mechanisms'], len(observation['mechanisms']))
        peaks['json_characters'] = max(peaks['json_characters'], len(json.dumps(observation, ensure_ascii=False)))
        peaks['support_skills'] = max(peaks['support_skills'], len(observation['produce']['support_skills']))
        if encoder is not None:
            encoded = encoder.encode(decision)
            peaks['encoded_nodes'] = max(peaks['encoded_nodes'], encoded.node_count)
        if decision.kind == 'outer':
            public = names(observation['produce'])
            public['actions'] = list(decision.candidates)
            run_view = SimpleNamespace(runtime=SimpleNamespace(scenario=SimpleNamespace(
                produce_id=public['produce_id'])))
            selected = guide.action(run_view, public)
            index = decision.candidates.index(selected)
        elif decision.kind == 'produce_choice':
            request = {'options': [names(c['option']) for c in decision.candidates],
                'kind': observation['resolution']['kind'], 'context': observation['resolution']['context'],
                'public_state': names(observation['produce'])}
            index = guide.choose(request)
        elif old_model is not None:
            # This independent diagnostic uses a deterministic old score actor;
            # its values/log probabilities are NOT claimed as full-task PPO data.
            exam = observation['exam']
            key = (observation['produce']['scenario'], observation['produce']['state']['audition_index'],
                   observation['produce']['lifecycle']['attempt_count'], exam['decision_version'])
            if key not in selected_by_exam_revision:
                encoded = encode(exam)
                with torch.no_grad():
                    action_index = int(old_model.policy(collate([encoded])).argmax(-1)[0])
                selected_by_exam_revision[key] = encoded.submissions[action_index]
            command = selected_by_exam_revision[key]
            if decision.kind == 'exam_action':
                index = decision.candidates.index(command['action'])
            else:
                count = len(observation['resolution']['selected_indices'])
                desired = command['indices'][count] if count < len(command['indices']) else None
                index = next(i for i, c in enumerate(decision.candidates)
                    if (c['type'] == 'finish_selection' if desired is None else c.get('index') == desired))
        else:
            index = next((i for i, c in enumerate(decision.candidates) if c.get('type') == 'play'), 0)
        return PolicySelection(index, 0, 0, 0)

    started = time.perf_counter()
    try:
        episode = task.run_episode(policy, seed=seed, policy_version=0)
        return {'schema': 'gakumas-natural-route-probe/1', 'seed': seed, 'not_training': True,
            'driver': 'guide_plus_old_exam_actor' if checkpoint else 'guide_plus_native_first_play',
            'old_checkpoint_sha256': sha256(Path(checkpoint).read_bytes()).hexdigest() if checkpoint else None,
            'config': {'loadout': config.loadout, 'research_config': config.research_config},
            'score': episode.raw_score, 'termination': episode.termination,
            'rating_provenance': episode.metadata['rating_provenance'],
            'completed_scenarios': episode.metadata['completed_scenarios'],
            'accepted_exam_count': episode.metadata['accepted_exam_count'],
            'decision_kinds': dict(kinds), 'peaks': peaks,
            'every_policy_observation_encoded': encode_public,
            'actual_exam_results': [{'scenario': run['scenario'], 'exams': run['terminal']['accepted_exams']}
                                   for run in episode.metadata['runs']],
            'arena_version': task.arena_version, 'seconds': time.perf_counter()-started,
            'five_natural_exams_completed': episode.metadata['accepted_exam_count'] == 5}
    finally:
        task.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=91001)
    parser.add_argument('--old-checkpoint', type=Path)
    parser.add_argument('--encode', action='store_true')
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('natural-route.json'))
    args = parser.parse_args()
    result = run(args.seed, args.old_checkpoint, args.encode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: result[k] for k in ('score', 'termination', 'accepted_exam_count', 'decision_kinds', 'peaks', 'seconds')}, ensure_ascii=False))
