"""Replay owned forks while auxiliary roots finish on the same frozen policy.

Only an asynchronous CPU count rendezvous precedes replay. Its rank prefix
offsets reproduce make_fork_tasks over the existing rank-ordered summary gather.
The caller still drains every root before applying peer credit or returning.
"""
import hashlib
import json
import os
import time

import torch
import torch.distributed as dist


def enabled(config, fork_seed_base):
    search = config.get('search', {})
    return (fork_seed_base is not None and os.environ.get('GAKUMAS_FORK_OVERLAP', '1') == '1'
            and config.get('practice', {}).get('forks', {}).get('enabled', False)
            and search.get('enabled', False) and search.get('execution_mode') == 'auxiliary'
            and search.get('auxiliary_async', True) and not search.get('fork_episodes', True))


def signatures(tasks):
    return [hashlib.sha256(json.dumps(t, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            for t in tasks]


def seed_interval(base, counts, rank):
    if any(type(n) is not int or n < 0 for n in counts) or not 0 <= rank < len(counts):
        raise ValueError('Invalid fork count rendezvous')
    return base + sum(counts[:rank]), base + sum(counts)


class ForkOverlap:
    def __init__(self, mesh, pool, model, config, exploration, seed_base, log_path, router):
        self.mesh, self.pool, self.model = mesh, pool, model
        self.config, self.exploration = config, exploration
        self.seed_base, self.log_path, self.router = seed_base, log_path, router
        self.handshake = False
        self.flow = None
        self.tasks, self.records, self.summaries, self.stats = [], [], [], []
        self.meaningful, self.next_seed = 0, seed_base
        self.credited = False

    def pump(self):
        if self.flow is not None and self.flow._auxiliary:
            ready = self.flow.poll(wait=True)
            if ready:
                raise RuntimeError('Deferred auxiliary search returned an acting decision')
        elif self.router is not None and self.router.service.pending:
            self.router.service.pump(timeout=.01, progress=self.router.progress)
        else:
            time.sleep(.001)

    def _counts(self, count, ready):
        self.handshake = True
        local = torch.tensor([count, int(ready)], dtype=torch.int64)
        if self.mesh.size == 1:
            rows = [local]
        else:
            rows = [torch.empty_like(local) for _ in range(self.mesh.size)]
            # The default group is CPU Gloo. Inference and all NPU operations
            # remain on this owning thread while other ranks finish collection.
            work = dist.all_gather(rows, local, async_op=True)
            while not work.is_completed():
                self.pump()
            work.wait()
        values = [row.tolist() for row in rows]
        return [int(row[0]) for row in values], all(row[1] == 1 for row in values)

    def ensure_handshake(self):
        # A failed collector must still match its peers' first collective.
        # Normal ranks observe the failure flag before starting any forks.
        if not self.handshake:
            self._counts(0, False)

    def before_drain(self, records, summaries, flow):
        from .practice import make_fork_tasks
        from .bank_rollout import rollout_bank
        from .runner import choose
        from .distributed import seed_rank
        self.flow = flow
        error = None
        try:
            if flow is None or not flow.auxiliary or flow.pending or flow._unbound:
                raise ValueError('Fork overlap requires bound auxiliary-only roots')
            for summary in summaries:
                summary['origin_rank'] = self.mesh.rank
            tasks, _ = make_fork_tasks(summaries, self.config, self.seed_base)
        except Exception as exc:
            error, tasks = exc, []
        counts, ready = self._counts(len(tasks), error is None)
        if not ready:
            raise RuntimeError('A rank could not complete joint collection for fork overlap') from error
        begin, self.next_seed = seed_interval(self.seed_base, counts, self.mesh.rank)
        self.tasks, end = make_fork_tasks(summaries, self.config, begin)
        if end != begin + counts[self.mesh.rank]:
            raise RuntimeError('Fork ownership changed after the count rendezvous')
        if not self.tasks:
            return
        if self.mesh.rank:
            # Matches serve_fork exactly. Rank0 previously continued its RNG
            # after joint collection, and must not acquire a new reset here.
            seed_rank(self.config, self.mesh.device, self.mesh.rank, 'fork')
        cfg = {k:v for k,v in self.config.items() if k != '_search_router'}
        before = time.monotonic()
        roots = len(flow._auxiliary)
        self.records, self.summaries, self.meaningful = rollout_bank(
            self.pool, self.model, None, cfg, self.mesh.device, len(self.tasks),
            self.exploration, choose, tasks=self.tasks, source='fork_exam',
            log_path=self.log_path, background=self.pump)
        elapsed = time.monotonic() - before
        self.router.service.stats['fork_replay_with_auxiliary_tail_seconds'] += elapsed
        self.router.service.stats['fork_roots_inflight_at_replay_start'] += roots
        print(json.dumps(dict(event='fork_search_overlap', rank=self.mesh.rank,
            policy_version=self.config['_policy_version'], tasks=len(self.tasks),
            seconds=elapsed, roots_at_start=roots, roots_remaining=len(flow._auxiliary))), flush=True)

    def credit(self, records, summaries):
        from .practice import apply_fork_returns
        if self.flow is None:
            raise RuntimeError('Missing auxiliary ownership boundary')
        self.flow.assert_drained()
        self.stats = apply_fork_returns(records, summaries, self.records, self.summaries,
            expected_tasks=self.tasks,
            objective=self.config.get('practice', {}).get('forks', {}).get('objective', 'mean'))
        self.credited = True

    def gather(self):
        # Same rank ordering as the pre-existing joint metadata gather. Large
        # encoded records remain local, exactly as in the ordinary fork path.
        rows = self.mesh.gather_lists([dict(rank=self.mesh.rank, credited=self.credited,
            signatures=signatures(self.tasks), next_seed=self.next_seed,
            summaries=self.summaries, stats=self.stats, meaningful=self.meaningful)])
        if len(rows) != self.mesh.size or not all(row['credited'] for row in rows):
            raise RuntimeError('A rank failed the overlapped fork/search boundary')
        rows.sort(key=lambda row: row['rank'])
        if [row['rank'] for row in rows] != list(range(self.mesh.size)):
            raise RuntimeError('Duplicate or missing fork ownership rank')
        if len({row['next_seed'] for row in rows}) != 1:
            raise RuntimeError('Fork seed counters disagree')
        return dict(records=self.records, policy_version=self.config['_policy_version'],
            objective=self.config.get('practice', {}).get('forks', {}).get('objective', 'mean'),
            signatures=[value for row in rows for value in row['signatures']],
            summaries=[value for row in rows for value in row['summaries']],
            stats=[value for row in rows for value in row['stats']],
            meaningful=sum(row['meaningful'] for row in rows), next_seed=rows[0]['next_seed'])
