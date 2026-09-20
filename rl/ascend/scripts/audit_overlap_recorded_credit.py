"""Replay label attachment and fork credit using committed normal-course evidence.

This CPU-only audit never runs a game, model or optimizer. It verifies routing
and credit math, not the quality/throughput of new deadline-limited searches.
Unavailable old likelihoods remain None, so these audit rows cannot be trained.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import Future
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path, policy):
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('policy_version') == policy:
                yield row


def plain(rows):
    return [{**{k: v for k, v in row.items() if k != 'encoded'},
             'encoded': vars(row['encoded'])} for row in rows]


class ReplayService:
    def __init__(self):
        self.pending = {}
        self.stats = Counter()
        self.released = 0

    def pump(self, **_):
        for future, root in list(self.pending.items())[:self.released]:
            if not future.done():
                future.set_result(root)

    def take(self, future):
        self.pending.pop(future)
        return future.result()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--batch', type=int, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    assert not args.report.exists(), 'Preserve existing evidence'
    exam = args.root / 'exam-search'
    sys.path[:0] = list(map(str, [exam, exam / 'runtime/shared', exam / 'runtime/arena', args.root / 'training']))
    import torch
    from draftrl.async_decisions import AsyncDecisions
    from draftrl.fork_overlap import ForkOverlap, signatures, seed_interval
    from draftrl.practice import apply_fork_returns, make_fork_tasks
    from draftrl.search_router import SearchRouter
    from draftrl.search_supervision import prepare_auxiliary
    from draftrl.source_identity import source_version
    torch.set_num_threads(1)
    started = time.monotonic()
    metric = next(row for row in map(json.loads, (args.run / 'metrics.jsonl').read_text().splitlines())
                  if row['batch'] == args.batch)
    policy = metric['source_sha256'] + ':' + str(args.batch - 1)
    config = json.loads((args.root / 'ascend/configs/prod/search-v6-credit-throughput.json').read_text())
    config.update(_policy_version=policy, _profiles=[{}] * len(metric['profiles']))
    all_episodes = list(read_rows(args.run / 'train-episodes.jsonl', policy))
    parents = [row for row in all_episodes if row['sampling_source'] == 'joint']
    forks = [row for row in all_episodes if row['sampling_source'] == 'fork_exam']
    assert len(parents) == metric['joint_episode_count'] and len(forks) == metric['fork_episode_count']
    assert len(forks) == 3 * len(parents)
    by_prefix = defaultdict(list)
    for row in forks:
        by_prefix[row['prefix_id']].append(row)
    for parent in parents:
        branches = by_prefix['joint:' + str(parent['seed'])]
        ranks = {row['origin_rank'] for row in branches}
        assert len(ranks) == 1
        parent['origin_rank'] = ranks.pop()
    # The persisted environment seeds identify the original global task order.
    parents.sort(key=lambda p: min(row['seed'] for row in by_prefix['joint:' + str(p['seed'])]))
    assert [p['origin_rank'] for p in parents] == sorted(p['origin_rank'] for p in parents)
    seed_base = min(row['seed'] for row in forks)
    tasks, next_seed = make_fork_tasks(parents, config, seed_base)
    actual = {(row['prefix_id'], row['branch_id']): row for row in forks}
    for task in tasks:
        meta = task['metadata']
        row = actual[(meta['prefix_id'], meta['branch_id'])]
        assert task['replay_seed'] == row['seed']
        assert meta['action_rng_seed'] == row['action_rng_seed']
        assert meta['parent_entry_sha256'] == row['entry_sha256']
        assert task['entry'] == row['entry']
    roots = {}
    for file in args.run.glob('search-roots*.jsonl'):
        for row in read_rows(file, policy):
            if row.get('valid_training_target'):
                key = (row['search_seed'], row['episode_id'], row['decision_version'])
                assert key not in roots or roots[key] == row
                roots[key] = row
    assert len(roots) == metric['auxiliary_search_roots']
    parent_lookup = {'joint:' + str(row['seed']): row for row in parents}
    records, attachments = [], []
    changed_selection_logs = 0
    for root in roots.values():
        parent = parent_lookup[root['episode_id']]
        selection = root['partial_selection']
        steps = [row for row in parent['choice_steps'] if
                 row['native_decision_version'] == root['decision_version']]
        if steps:
            # Legacy recovery logged the mutable choice list after the action.
            # A chosen index disappears from all subsequent ChoiceState action
            # lists. Thus the first recorded substep still present in this root's
            # action list is its actual behavior step, independently of that log.
            compatible = [step for step in steps if step['command'] in root['search']['actions']]
            assert compatible
            step = compatible[0]
            available = {action['index'] for action in root['search']['actions'] if action['method'] == 'choice_append'}
            assert not set(step['selected_before']).intersection(available)
            changed_selection_logs += selection != step['selected_before']
            selection = step['selected_before']
            command = step['command']
        else:
            commands = [command for command in parent['submissions'] if
                        command.get('decision_version', command.get('action', {}).get('decision_version')) == root['decision_version']]
            assert len(commands) == 1 and not selection
            command = commands[0]
        encoded = SimpleNamespace(phase=0, submissions=copy.deepcopy(root['search']['actions']))
        action = encoded.submissions.index(command)
        row = dict(encoded=encoded, episode_id=root['episode_id'], profile=root['profile'],
                   action=action, old_logp=None, loss_kind='ppo', policy_version=policy,
                   search_seed=root['search_seed'], **{'return': parent['normalized_score']})
        records.append(row)
        attachments.append((row, {**root, '_audited_selection': list(selection)}))
    # Structural probes check construction credit and one true return per branch.
    for parent in parents:
        records.append(dict(encoded=SimpleNamespace(phase=2, submissions=[]),
                            episode_id='joint:' + str(parent['seed']), **{'return': parent['normalized_score']}))
    fork_rows = [dict(encoded=SimpleNamespace(phase=0, submissions=[]),
                     prefix_id=row['prefix_id'], branch_id=row['branch_id'],
                     episode_id='fork_exam:' + str(row['seed']), **{'return': row['normalized_score']}) for row in forks]
    reference = copy.deepcopy(records)
    for row, (_, root) in zip(reference, attachments):
        row.update(search_aux=copy.deepcopy(root['search']),
                   search_aux_sampler_version=root['search_version'], search_aux_seed=root['search_seed'])
    reference_stats = apply_fork_returns(reference, parents, copy.deepcopy(fork_rows), copy.deepcopy(forks),
                                        expected_tasks=tasks, objective='best_of_k')
    expected = prepare_auxiliary(reference, config['search'])
    counts = [sum(p['origin_rank'] == rank for p in parents) * 3 for rank in range(8)]
    combined, combined_stats, task_hashes, ranks = [], [], [], []
    for rank in range(8):
        own = [p for p in parents if p['origin_rank'] == rank]
        prefixes = {'joint:' + str(p['seed']) for p in own}
        rows = [r for r in records if r['episode_id'] in prefixes]
        branch_rows = [r for r in fork_rows if r['prefix_id'] in prefixes]
        results = [r for r in forks if r['prefix_id'] in prefixes]
        service = ReplayService()
        with patch('draftrl.search_router.SearchService', return_value=service):
            router = SearchRouter(None, 'cpu', config['search'])
        flow = AsyncDecisions(router)
        for row, root in attachments:
            if row['episode_id'] not in prefixes:
                continue
            future = Future()
            service.pending[future] = root
            item = dict(encoded=row['encoded'], profile=root['profile'], episode_id=root['episode_id'],
                        observation={'decision_version': root['decision_version']}, partial_selection=root['_audited_selection'])
            attachment = dict(item=item, proposal=(None, row['encoded'], row['action'], None), record=None)
            flow._auxiliary[future] = attachment
            extra = {}
            flow._unbound[id(extra)] = attachment
            flow.bind(row, extra)
        overlap = ForkOverlap(SimpleNamespace(rank=rank, size=8, device='cpu'), None, None, config,
                              None, seed_base, None, router)

        def replay(*_, tasks, background, **kwargs):
            assert len(tasks) == len(results) and flow._auxiliary
            service.released = max(1, len(service.pending) // 2)
            background()
            assert flow._auxiliary
            return branch_rows, results, sum(r['decisions'] for r in results)

        def counts_ready(count, ready):
            overlap.handshake = True
            assert ready and count == counts[rank]
            return counts, True

        with patch.object(overlap, '_counts', side_effect=counts_ready), patch(
                'draftrl.bank_rollout.rollout_bank', side_effect=replay):
            overlap.before_drain(rows, own, flow)
        try:
            overlap.credit(rows, own)
        except RuntimeError as error:
            assert 'Unfinished search' in str(error)
        else:
            raise AssertionError('Credit ran before all original roots were attached')
        service.released = len(service.pending)
        flow.drain()
        overlap.credit(rows, own)
        assert overlap.next_seed == next_seed
        task_hashes.extend(signatures(overlap.tasks))
        combined.extend(rows)
        combined_stats.extend(overlap.stats)
        ranks.append(dict(rank=rank, parents=len(own), forks=len(results),
                          accepted_roots=router.counts['accepted_targets'],
                          interval=seed_interval(seed_base, counts, rank)))
    got = prepare_auxiliary(combined, config['search'])
    key = lambda row: (row['episode_id'], row.get('search_seed', -1), row['encoded'].phase)
    assert plain(sorted(reference, key=key)) == plain(sorted(combined, key=key))
    by_key = lambda rows: {row['prefix_id']: row for row in rows}
    assert by_key(reference_stats) == by_key(combined_stats)
    persisted = [{k: v for k, v in row.items() if k != 'batch'}
                 for row in read_rows(args.run / 'fork-returns.jsonl', policy)]
    assert by_key(persisted) == by_key(combined_stats)
    assert signatures(tasks) == task_hashes and expected == got
    for field in ('roots', 'accepted_roots', 'weighted_roots', 'rejected_roots', 'rejected_reasons'):
        assert got[field] == metric['auxiliary_search'][field], (field, got[field], metric['auxiliary_search'][field])
    assert math.isclose(got['mean_weight'], metric['auxiliary_search']['mean_weight'], rel_tol=1e-6, abs_tol=1e-8)
    positive = [row['search_aux_target']['weight'] for row in combined
                if row.get('search_aux_target', {}).get('weight', 0.) > 0]
    assert len(positive) > 0 and max(positive) > .01
    report = dict(passed=True, policy_version=policy, batch=args.batch, source_sha256=source_version(),
                  scope='CPU replay of recorded normal-course actions, raw roots and real four-game returns; no new search/game/model/optimizer',
                  limitations=['Eight rank partitions simulated; real Gloo and full NPU pipeline covered by separate evidence',
                               'Encoded proxy includes only recorded action list and phase; old likelihood unavailable and left None',
                               'Does not measure root quality under new concurrent search deadlines'],
                  parents=len(parents), forks=len(forks), ranks=ranks, auxiliary=got,
                  legacy_selection_logs_changed_after_action=changed_selection_logs,
                  positive_weight_range=[min(positive), max(positive)],
                  checks=dict(actual_actor_actions_found=True, exact_global_task_seeds=True,
                              labels_bound_before_credit=True, premature_credit_rejected=True,
                              serial_records_and_targets_identical=True, persisted_credit_identical=True,
                              production_label_metrics_identical=True, meaningful_positive_labels=True),
                  evidence={name: sha(args.run / name) for name in
                            ('metrics.jsonl', 'train-episodes.jsonl', 'fork-returns.jsonl', 'search-roots.jsonl')},
                  elapsed_seconds=time.monotonic() - started)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
