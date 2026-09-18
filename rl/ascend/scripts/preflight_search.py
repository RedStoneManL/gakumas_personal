"""Real native Arena, public MCTS, model backward, Adam, RNG and HCCL probe.

Run with torchrun for multi-card acceptance. Writes evidence from this machine;
the result does not claim policy strength or exhaustive operator coverage.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
EXAM = ROOT/'exam-search' if (ROOT/'exam-search').is_dir() else ROOT/'exam_search'
TRAINING = ROOT/'training' if (ROOT/'training').is_dir() else ROOT.parent/'training'
sys.path[:0] = [str(TRAINING), str(EXAM), str(EXAM/'runtime/shared'), str(EXAM/'runtime/arena')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=('cpu', 'npu', 'cuda'), default='npu')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--initial', type=Path, default=ROOT/'checkpoints/latest.pt')
    parser.add_argument('--relational', action='store_true',
                        help='Warm-start and exercise the complete opt-in relational architecture')
    parser.add_argument('--semantics-path', type=Path, default=EXAM/'setup/relational_semantics.json',
                        help='Offline native semantics catalogue, required with --relational')
    args = parser.parse_args()
    mesh = None
    rank = int(os.environ.get('RANK', '0'))
    report = {'passed': False, 'platform': platform.platform(), 'architecture': platform.machine(),
              'world_size': int(os.environ.get('WORLD_SIZE', '1')),
              'scope': 'native/MCTS/update/connectivity; no policy-quality claim'}
    try:
        import torch
        from draftrl.distributed import LearnerGroup
        from gakumas_training.device import device_report, seed_device, capture_retry_rng, restore_retry_rng
        from draftrl.relational_runtime import configure
        from draftrl.relational_training import SCHEMA as RELATIONAL_SCHEMA, parameter_groups
        from draftrl import learning_rates
        relational_config = {'relational': {
            'enabled': True, 'schema': RELATIONAL_SCHEMA,
            'semantics_path': str(args.semantics_path.resolve()),
            'legacy_lr_ratio': .25, 'adaptation_batches': 8, 'new_lr_multiplier': 1.,
        }} if args.relational else {}
        # Every torchrun rank validates the same catalogue BEFORE entering the
        # learner service. Spawned search processes inherit the opt-in path.
        semantic_path = configure(relational_config, EXAM/'setup')
        report['relational'] = bool(args.relational)
        report['semantics_path'] = str(semantic_path) if semantic_path else None
        mesh = LearnerGroup(args.device)
        total = mesh.sum_values({'rank_sum': mesh.rank+1})['rank_sum']
        if total != mesh.size*(mesh.size+1)/2:
            raise ValueError('Collective sum failed')
        if mesh.rank:
            mesh.serve()
            return
        report['hardware'] = device_report(mesh.device)
        report['collective'] = 'hccl' if args.device == 'npu' and mesh.size > 1 else 'single' if mesh.size == 1 else 'gloo/nccl'
        seed_device(456, mesh.device)
        from gakumas_arena.engine.training import make_training_entry, content_version
        from gakumas_arena.engine.search import SearchClient
        from draftrl.model import DraftPolicy
        from draftrl.encoding import encode_exam
        from draftrl.runner import choose
        from draftrl.search_service import SearchService
        from gakumas_training.device import optimizer_options
        from draftrl.checkpoint import transfer
        from draftrl.learning_settings import SIGNED, SEARCH
        from draftrl.critic_completion import SETTINGS as COMPLETION
        model, reference = transfer(args.initial, '', mesh.device, relational=args.relational)
        report['initial_checkpoint'] = reference['sha256']
        report['model_config'] = model.config
        report['model_parameters'] = sum(p.numel() for p in model.parameters())
        entry = make_training_entry([647]*8, turn_types=['vocal']*2)
        report['arena'] = content_version()
        with SearchClient(max_worlds=2) as recorder:
            exam = recorder.create_recorded_exam(entry, seed=31)
            history = exam.export_public_history()
            tasks = [{'entry': entry, 'history': history, 'score_scale': 150000.,
                      'policy_version': 'preflight:0', 'search_seed': 731+i,
                      'simulations': 16, 'particles': 4, 'seconds': 60., 'sampling_ms': 10000,
                      'max_depth': 8, 'rollout_steps': 8, 'objective_k': 4,
                      'root_selection': 'soft_budget', 'soft_floor': .25, 'soft_temperature': .8,
                      'soft_min_visits': 2, 'learning_target': SEARCH} for i in range(2)]
            with SearchService(model, str(mesh.device), parallel_roots=2, inference_batch=4) as service:
                roots = service.search_many(tasks)
                report['valid_search_roots'] = sum(bool(r['valid_training_target']) for r in roots)
                report['search_stats'] = service.stats
                if report['valid_search_roots'] != 2:
                    raise ValueError('Public-search preflight did not obtain both valid targets')
            if exam.export_public_history() != history:
                raise ValueError('Search changed the real recorder')
            rows, games, scores = [], [], []
            for replica in range(4):
                if replica:
                    exam = recorder.create_recorded_exam(entry, seed=31+replica)
                game = []
                observation = exam.observe()
                while not observation['result']['terminated']:
                    encoded = encode_exam(observation)
                    action, logp, values, settings, diagnostics = choose(model, [encoded], str(mesh.device))
                    row = {'encoded': encoded, 'action': action[0], 'old_logp': logp[0],
                           'old_value': values[0], 'profile': 'preflight', 'loss_kind': 'ppo',
                           'exploration': settings[0], 'policy_version': 'preflight:0', **diagnostics[0]}
                    if not game and replica == 0:
                        search = roots[0]['search']
                        if search['actions'] != encoded.submissions:
                            raise ValueError('Preflight search/action alignment differs')
                        row.update(action=encoded.submissions.index(search['selected_action']),
                                   old_logp=None, loss_kind='search', search=search)
                    game.append(row)
                    command = encoded.submissions[row['action']]
                    observation = (exam.choose(command['indices'], decision_version=command['decision_version'])
                                   if command['method'] == 'choose' else exam.act(command['action']))
                    if len(game) > 100:
                        raise RuntimeError('Preflight exceeded the decision bound')
                score = observation['result']['final_score']
                scores.append(score/150000.)
                for row in game:
                    row['return'] = score/150000.
                games.append(game)
                exam.close()
            from draftrl.best_of import group_credit, apply_exam_credit
            _, credits = group_credit(scores)
            for i, game in enumerate(games):
                apply_exam_credit(game, scores[i], credits[i], 4, 'preflight', i,
                                  max(scores[:i]+scores[i+1:]))
                rows.extend(game)
            report['native_scores'] = [value*150000. for value in scores]
        cfg = {'_policy_version': 'preflight:0', 'sample_efficiency': {'advantage_mode': 'mc', 'ppo_epochs_max': 1},
               'search': {'loss_coefficient': .1, 'learning_target': SEARCH},
               'signed_exam_credit': SIGNED, 'critic_completion': COMPLETION, 'practice': {}, 'epochs': 1, 'effective_minibatch': 32,
               'minibatch': 1, 'clip': .2, 'target_kl': .05, 'value_coefficient': .5, 'max_grad': .5}
        cfg.update({key: 1e-5 for key in learning_rates.PHASE_KEYS.values()})
        cfg.update(relational_config)
        groups = parameter_groups(model, dict.fromkeys(learning_rates.PHASE_KEYS, 1e-5))
        optimizer = torch.optim.Adam(groups, eps=1e-5, **optimizer_options(model))
        report['optimizer_schedule'] = learning_rates.apply(optimizer, cfg, 0., completed_batches=0)
        report['optimizer_groups'] = [group['name'] for group in optimizer.param_groups]
        before = {n: p.detach().cpu().clone() for n, p in model.named_parameters()}
        report['update'] = mesh.update(model, optimizer, rows, cfg)
        report['changed_parameters'] = sum(not torch.equal(before[n], p.detach().cpu()) for n, p in model.named_parameters())
        if args.relational:
            report['changed_relational_parameters'] = {
                role: sum(not torch.equal(before[n], p.detach().cpu())
                          for n, p in model.named_parameters() if n.startswith(role + '_relational.'))
                for role in ('actor', 'critic')}
        if not report['changed_parameters']:
            raise ValueError('Preflight produced no parameter update')
        state = capture_retry_rng()
        expected = torch.rand(8, device=mesh.device)
        restore_retry_rng(state)
        if not torch.equal(expected, torch.rand(8, device=mesh.device)):
            raise ValueError('Device RNG roundtrip failed')
        report.update(passed=True, native_final_score=score, decisions=len(rows), rng_roundtrip=True)
        mesh.stop()
    except BaseException as error:
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        if rank == 0:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
        if mesh is not None:
            mesh.close()


if __name__ == '__main__':
    main()
