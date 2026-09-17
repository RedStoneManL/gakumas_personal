"""One sampler/coordinator and synchronous sharded learners under torchrun.

Control traffic uses CPU Gloo; NPU gradients use HCCL (CUDA: NCCL). Every
microbatch loss is divided by the GLOBAL optimizer block size. Gradients are
summed, not averaged again, preserving the single-learner objective exactly.

Evaluation rollouts are additionally sharded: every rank simulates a disjoint,
contiguous slice of the episode indices and the summaries are gathered. The
shard is index-exact, so describe() -- which sorts by seed and aggregates
order-independently -- sees the identical episode set a single learner produces.
"""
from datetime import timedelta
import os
import random

import torch
import torch.distributed as dist

ACTIVE = None


def cpu_copy(value):
    if torch.is_tensor(value):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {k: cpu_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [cpu_copy(v) for v in value]
    if isinstance(value, tuple):
        return tuple(cpu_copy(v) for v in value)
    return value


from gakumas_training.collectives import CollectiveGroup


def shard(count, size, rank):
    """Contiguous slice [start, start+length) of `count` items for `rank`.

    Contiguous rather than strided: rollout derives an episode's profile from
    `index % len(profiles)`, so a contiguous block keeps each rank's profile
    cycle identical to the single-learner sequence over those same indices.
    """
    base, extra = divmod(count, size)
    start = base * rank + min(rank, extra)
    return start, base + (1 if rank < extra else 0)


# Per-rank search-seed block. Wide enough that a rank cannot walk into the next rank's
# range within a batch; the coordinator advances the base past all of them afterwards.
_SEARCH_SEED_BLOCK = 1_000_000


def seed_rank(config, device, rank, stage):
    """Seed this rank's RNGs deterministically, and differently from every other rank.

    rollout() samples non-greedy actions with distribution.sample(), which draws from the
    GLOBAL torch generator -- the per-episode random.Random objects serve driver='random'
    only. runner.train() calls seed_device once, but it runs on the coordinator alone, so
    without this the seven worker ranks sampled the PPO collection from a generator
    PyTorch had seeded from OS entropy at process start: not reproducible, and outside the
    checkpoint's RNG save and restore.

    The stage name is mixed in so the collection and fork stages of one batch do not
    replay the same stream, and the rank so no two ranks ever sample in lockstep.
    """
    import random as _random
    from gakumas_training.device import seed_device
    base = int(config.get('seed', 0))
    mixed = (base + 1_000_003 * (rank + 1) + 7_919 * (sum(map(ord, stage)) + 1)) % (2 ** 31 - 1)
    _random.seed(mixed)
    seed_device(mixed, str(device))
    return mixed


def worker_search_config(config, size):
    """Build a worker rank's search config so it matches the coordinator's exactly.

    objective_k is the trap: runner.apply_resources() sets it on the coordinator's router
    from practice.forks.objective, but it is NOT a key of config['search'], so a worker
    that only spreads config['search'] silently falls back to SearchRouter's default of 1.
    That made rank 0 optimise empirical Best-of-4 while ranks 1-7 optimised the mean --
    no error, and cheaper on the workers, so it never showed up as a slowdown.
    """
    parallel = config.get('parallelism', {}) or {}
    roots = max(1, int(parallel.get('parallel_roots', 1)) // size)
    forks = (config.get('practice', {}) or {}).get('forks', {}) or {}
    return {**config['search'],
            'parallel_roots': roots,
            # inference_batch above parallel_roots is unreachable: each search process
            # blocks on its own reply, so only that many are ever in flight.
            'inference_batch': min(int(parallel.get('inference_batch', roots)), roots),
            'objective_k': 4 if forks.get('objective') == 'best_of_k' else 1}


class _BankRows:
    """Stands in for the sample bank inside a sharded rollout.

    rollout() only ever calls bank.add(summary). The real bank lives on the coordinator
    and dedupes by loadout key, so each rank just records what it would have added and
    the coordinator replays the gathered rows into the one real bank, in seed order.
    """

    def __init__(self):
        self.rows = []

    def add(self, summary):
        self.rows.append(summary)


def shard_log(log_path, rank):
    """Per-rank episode log; merged back into log_path once every rank has finished."""
    if log_path is None:
        return None
    from pathlib import Path
    log_path = Path(log_path)
    return log_path.with_name(f'{log_path.stem}.rank{rank}{log_path.suffix}')


def merge_shard_logs(log_path, size):
    """APPEND the per-rank episode logs to the shared log, ordered by seed.

    Append, never replace. rollout() and rollout_bank() only ever append to these files,
    and three things depend on that:
      - train-episodes.jsonl is written by the collection stage AND the fork stage AND the
        bank stage of the SAME batch, and accumulates across every batch. Replacing it
        would leave only whichever stage merged last.
      - checkpoint.save_committed records each log's size as a resume offset and
        recovery.prepare rejects a log shorter than its recorded offset, so the file must
        never shrink.
      - the dashboard reads validation-*-episodes.jsonl incrementally.

    Sorting by seed keeps the file order deterministic, which matters because
    play_evaluation.prepare_suite selects strata with eligible[0] / eligible[-1].
    """
    import json
    from pathlib import Path
    if log_path is None:
        return
    log_path = Path(log_path)
    parts = [shard_log(log_path, r) for r in range(size)]
    present = [p for p in parts if p.exists()]
    if not present:
        return
    rows = []
    for part in present:
        with part.open(encoding='utf-8') as stream:
            rows += [json.loads(line) for line in stream if line.strip()]
    rows.sort(key=lambda row: row.get('seed', 0))
    with log_path.open('a', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    for part in present:
        part.unlink()


class LearnerGroup(CollectiveGroup):
    def update(self, model, optimizer, records, config, progress=None):
        from .ppo import update
        if self.size > 1:
            names = {id(p): name for name, p in model.named_parameters()}
            groups = [[names[id(p)] for p in g['params']] for g in optimizer.param_groups]
            # After a sharded collection every rank holds the records it produced and
            # trains on them (serve's update branch); the payload is then ~75 MB of
            # weights and Adam state instead of ~1 GB of Encoded objects. A group that
            # never collected (direct update() callers, the two-process tests) still
            # receives the full record list and uses the original strided layout.
            self.shared_records = not getattr(self, 'local_summaries', None)
            payload = {'command': 'update', 'model_config': model.config,
                       'model': cpu_copy(model.state_dict()), 'optimizer': cpu_copy(optimizer.state_dict()),
                       'groups': groups,
                       'config': {k: v for k, v in config.items() if k not in ('_search_router', '_coverage')}}
            if self.shared_records:
                payload['records'] = records
            # One broadcast_object_list carries weights, Adam state and every record:
            # a single-threaded pickle on this rank, then seven single-threaded
            # unpickles. Measured once at ~18 silent minutes before the first PPO
            # block; report it every batch so the cost stays visible.
            import time as _time, json as _json
            _t0 = _time.monotonic()
            self.broadcast(payload)
            print(_json.dumps({'event': 'records_broadcast', 'records': len(records),
                               'seconds': round(_time.monotonic() - _t0, 1),
                               'ranks': self.size}), flush=True)
        return update(model, optimizer, records, config, self.device, progress=progress, mesh=self)

    # ---- sharded evaluation rollout -------------------------------------------------

    def evaluate_rollout(self, pool, model, setup, catalog, config, start_seed, count, *,
                         log_path=None, keep_entries=False):
        """Greedy evaluation rollout spread over every rank; returns all summaries.

        `pool` is the coordinator's own Arena pool, already sized and owned by
        apply_resources(); worker ranks build their own share in pool_for(). Only the
        coordinator calls this -- worker ranks reach the matching collectives through
        serve(). With size == 1 this is exactly the previous local rollout.
        """
        from .runner import rollout
        if self.size == 1:
            _, summaries, _, _ = rollout(pool, model, None, catalog, config,
                                         self.device, start_seed, count=count, greedy=True,
                                         log_path=log_path, keep_entries=keep_entries)
            return summaries
        # The coordinator keeps its full pool, so its config['workers'] is already correct.
        payload = {'command': 'rollout', 'model_config': model.config,
                   'model': cpu_copy(model.state_dict()),
                   'setup': str(setup), 'catalog': catalog, 'start_seed': start_seed,
                   'count': count, 'keep_entries': keep_entries,
                   'log_path': None if log_path is None else str(log_path),
                   'config': {k: v for k, v in config.items() if k not in ('_search_router', '_coverage')}}
        self.broadcast(payload)
        offset, mine = shard(count, self.size, self.rank)
        summaries = []
        try:
            if mine:
                # Each rank streams to its own shard file. The episode log carries fields the
                # gathered summaries drop (submissions, entry), so it cannot be rebuilt from
                # the gather; and eight processes appending to one file would interleave.
                _, summaries, _, _ = rollout(pool, model, None, catalog, config,
                                             self.device, start_seed + offset, count=mine, greedy=True,
                                             log_path=shard_log(log_path, self.rank),
                                             keep_entries=keep_entries, index_offset=offset)
        finally:
            # Always reach the gather. A rank that raised before it would hang every other
            # rank until the 72h Gloo timeout instead of failing the job now.
            gathered = self.gather_lists(summaries)
        # The gather is a barrier, so every shard file is complete and closed by here.
        merge_shard_logs(log_path, self.size)
        return gathered

    def pool_for(self, config, setup):
        """This rank's Arena worker pool, sized to its share of the configured workers.

        Returns (pool, size). Callers MUST set config['workers'] to the returned size:
        rollout() and rollout_bank() index worker slots with range(config['workers']),
        so a config claiming more workers than the pool holds would address slots that
        do not exist as soon as the slice is large enough to reach them.
        """
        import json
        from pathlib import Path
        from r1rl.environment import Workers, arena_module
        setup = Path(setup)
        want = max(1, int(config['parallelism']['workers']) // self.size)
        state = getattr(self, 'pool_state', None)
        if state is not None and state[0] == want:
            return state[1], want
        if state is not None:
            state[1].close()
            self.pool_state = None
        arena = setup.parent / 'runtime/arena'
        arena_hash = json.loads((setup / 'provenance.json').read_text(encoding='utf-8'))[
            'arena_version']['effective_sha256']
        if arena_module(arena).content_version()['effective_sha256'] != arena_hash:
            raise RuntimeError('Frozen Arena differs from prepared inputs')
        pool = Workers(want, arena, arena_hash)
        self.pool_state = (want, pool)
        return pool, want

    def serve_rollout(self, payload):
        import json
        from pathlib import Path
        from .model import DraftPolicy
        from .runner import rollout
        setup = Path(payload['setup'])
        config = {**payload['config'],
                  '_profiles': json.loads((setup / 'profiles.json').read_text(encoding='utf-8'))}
        torch.set_num_threads(config.get('parallelism', {}).get('torch_threads', 2))
        model = DraftPolicy(**payload['model_config']).to(self.device)
        model.load_state_dict(payload['model'], strict=True)
        offset, mine = shard(payload['count'], self.size, self.rank)
        summaries = []
        try:
            if mine:
                pool, workers = self.pool_for(config, setup)
                config = {**config, 'workers': workers}
                # Stream to this rank's own shard file; the coordinator merges them into
                # the single episode log after the gather barrier.
                _, summaries, _, _ = rollout(pool, model, None,
                                             payload['catalog'], config, self.device,
                                             payload['start_seed'] + offset, count=mine,
                                             greedy=True,
                                             log_path=shard_log(payload['log_path'], self.rank),
                                             keep_entries=payload['keep_entries'],
                                             index_offset=offset)
        finally:
            self.gather_lists(summaries)
        del model

    # ---- sharded training collection ------------------------------------------------

    def collect_rollout(self, pool, model, setup, catalog, config, episode_index,
                        target_decisions, exploration, *, log_path=None, keep_entries=False,
                        search_log=None, search_seed_base=0):
        """PPO collection spread over every rank.

        Rank r walks the seed stream episode_index + r, +size, +2*size ... so no two ranks
        can simulate the same episode, and rollout derives the scenario/coverage schedule
        from that seed, keeping each episode's identity exactly what it would have been.
        target_decisions is a SOFT budget (episodes always finish), so each rank takes an
        equal share of it.

        Unlike evaluation this cannot be checked against a single-learner run bit for bit:
        the ranks stop at slightly different episode counts, so the union of visited
        indices has gaps and a few scheduled coverage events are skipped. That is the same
        class of change as altering `workers`, which the project already requires a new run
        for. The episode data itself is unaffected -- each episode is still generated from
        its own seed by the unmodified rollout.
        """
        from .runner import rollout
        from . import sharded
        offset, share = shard(target_decisions, self.size, self.rank)
        if self.size > 1:
            payload = {'command': 'collect', 'model_config': model.config,
                       'model': cpu_copy(model.state_dict()), 'setup': str(setup),
                       'catalog': catalog, 'episode_index': episode_index,
                       'target_decisions': target_decisions, 'exploration': exploration,
                       'keep_entries': keep_entries, 'search_seed_base': search_seed_base,
                       'log_path': None if log_path is None else str(log_path),
                       'search_log': None if search_log is None else str(search_log),
                       'config': {k: v for k, v in config.items()
                                  if k not in ('_search_router', '_coverage')}}
            self.broadcast(payload)
        bank = _BankRows()
        start = episode_index + self.rank
        records, summaries, meaningful, next_seed = [], [], 0, start
        try:
            records, summaries, meaningful, next_seed = rollout(
                pool, model, None, catalog, config, self.device, start,
                target_decisions=max(1, share), seed_stride=self.size, exploration=exploration,
                scenario_bank=bank, keep_entries=keep_entries,
                log_path=shard_log(log_path, self.rank) if self.size > 1 else log_path)
        finally:
            # The other coordinators guard their work the same way. Without this, a raise
            # here (decision guard, Arena failure, search error) would skip all four gathers
            # while seven ranks are already blocked inside serve_collect's matching ones.
            if self.size > 1:
                # Records stay here. Summaries carry their origin so fork replays can be
                # routed back to the rank that holds the parent records.
                for row in summaries:
                    row['origin_rank'] = self.rank
                gathered_episodes = self.gather_lists(summaries)
                gathered_bank = self.gather_lists(bank.rows)
                counts = self.gather_lists([
                    {'rank': self.rank, 'started': (next_seed - start) // self.size,
                     'meaningful': meaningful}])
        if self.size == 1:
            return records, summaries, meaningful, next_seed, bank.rows
        merge_shard_logs(log_path, self.size)
        merge_shard_logs(search_log, self.size)
        # Advance past every rank's highest used seed. Ranks stop at different episode
        # counts, so this leaves at most size-1 unused indices; reusing them instead would
        # let a later batch replay an episode some rank already produced.
        widest = max(row['started'] for row in counts) if counts else 0
        total_meaningful = sum(row['meaningful'] for row in counts)
        # Bank order must not depend on which rank happened to report first.
        gathered_bank.sort(key=lambda row: row['seed'])
        self.local_summaries = summaries
        return (records, gathered_episodes, total_meaningful,
                episode_index + max(widest, 1) * self.size, gathered_bank)

    def serve_collect(self, payload):
        import json
        from pathlib import Path
        from .model import DraftPolicy
        from .runner import rollout
        from .search_router import SearchRouter
        setup = Path(payload['setup'])
        config = {**payload['config'],
                  '_profiles': json.loads((setup / 'profiles.json').read_text(encoding='utf-8'))}
        torch.set_num_threads(config.get('parallelism', {}).get('torch_threads', 2))
        model = DraftPolicy(**payload['model_config']).to(self.device)
        model.load_state_dict(payload['model'], strict=True)
        offset, share = shard(payload['target_decisions'], self.size, self.rank)
        seed_rank(config, self.device, self.rank, 'collect')
        router = None
        records, summaries, bank = [], [], _BankRows()
        started, meaningful = 0, 0
        try:
            pool, workers = self.pool_for(config, setup)
            search_cfg = worker_search_config(config, self.size)
            roots = search_cfg['parallel_roots']
            # Disjoint seed blocks: a shared counter would hand two ranks the same search seed.
            router = SearchRouter(model, self.device, search_cfg,
                                  seed_counter=payload['search_seed_base'] + self.rank * _SEARCH_SEED_BLOCK,
                                  log_path=shard_log(payload['search_log'], self.rank))
            config = {**config, 'workers': workers, '_search_router': router}
            start = payload['episode_index'] + self.rank
            records, summaries, meaningful, next_seed = rollout(
                pool, model, None, payload['catalog'], config, self.device, start,
                target_decisions=max(1, share), seed_stride=self.size,
                exploration=payload['exploration'], scenario_bank=bank,
                keep_entries=payload['keep_entries'],
                log_path=shard_log(payload['log_path'], self.rank))
            started = (next_seed - start) // self.size
        finally:
            # Every gather must be reached in the same order as the coordinator, or the
            # whole job blocks until the 72h Gloo timeout instead of failing here.
            for row in summaries:
                row['origin_rank'] = self.rank
            self.local_records, self.local_summaries = records, summaries
            self.gather_lists(summaries)
            self.gather_lists(bank.rows)
            self.gather_lists([{'rank': self.rank, 'started': started,
                                'meaningful': meaningful}])
            if router is not None:
                router.close()
        del model

    # ---- sharded fork / continuation rollout ----------------------------------------

    def fork_rollout(self, pool, model, setup, config, tasks, exploration, *,
                     records, summaries, objective='mean',
                     log_path=None, source='fork_exam', search_seed_base=0):
        """PPO-producing replay of an explicit task list, spread over every rank.

        Used for the per-episode fork continuations, which are the largest remaining
        rank0-only stage (measured: 3246 tasks at 4/min on one rank). The task list is
        explicit so the shard is a plain slice, and practice.apply_fork_returns groups by
        prefix_id and compares multisets, so gather order does not matter. It also already
        raises on a missing, duplicate or unexpected continuation, which is exactly the
        assertion a wrong shard would trip.
        """
        from .bank_rollout import rollout_bank
        from .runner import choose
        from .practice import apply_fork_returns
        from . import sharded
        if self.size == 1 or not tasks:
            fork_records, fork_summaries, meaningful = rollout_bank(
                pool, model, None, config, self.device, len(tasks),
                exploration, choose, tasks=tasks, source=source, log_path=log_path)
            stats = apply_fork_returns(records, summaries, fork_records, fork_summaries,
                                       expected_tasks=tasks, objective=objective)
            return fork_records, fork_summaries, meaningful, stats
        # Every replica of a joint episode goes to the rank that produced it, so the
        # group is whole there and apply_fork_returns needs no gather of records.
        sharded.stamp_shards(tasks, self.size, key=lambda t: t['metadata']['prefix_id'],
                             rank_of=lambda t: t['metadata']['origin_rank'])
        payload = {'command': 'fork', 'model_config': model.config,
                   'model': cpu_copy(model.state_dict()), 'setup': str(setup),
                   'tasks': tasks, 'source': source, 'exploration': exploration,
                   'objective': objective, 'search_seed_base': search_seed_base,
                   'log_path': None if log_path is None else str(log_path),
                   'config': {k: v for k, v in config.items()
                              if k not in ('_search_router', '_coverage')}}
        self.broadcast(payload)
        slice_tasks = sharded.mine(tasks, self.rank)
        fork_records, fork_summaries, meaningful, stats = [], [], 0, []
        try:
            if slice_tasks:
                fork_records, fork_summaries, meaningful = rollout_bank(
                    pool, model, None, config, self.device, len(slice_tasks), exploration,
                    choose, tasks=slice_tasks, source=source,
                    log_path=shard_log(log_path, self.rank))
            own = [row for row in summaries if row.get('origin_rank', 0) == self.rank]
            stats = apply_fork_returns(records, own, fork_records, fork_summaries,
                                       expected_tasks=slice_tasks, objective=objective)
        finally:
            gathered_summaries = self.gather_lists(fork_summaries)
            gathered_stats = self.gather_lists(stats)
            counts = self.gather_lists([{'rank': self.rank, 'meaningful': meaningful}])
        merge_shard_logs(log_path, self.size)
        return fork_records, gathered_summaries, sum(r['meaningful'] for r in counts), gathered_stats

    def serve_fork(self, payload):
        import json
        from pathlib import Path
        from .model import DraftPolicy
        from .bank_rollout import rollout_bank
        from .runner import choose
        from .search_router import SearchRouter
        setup = Path(payload['setup'])
        config = {**payload['config'],
                  '_profiles': json.loads((setup / 'profiles.json').read_text(encoding='utf-8'))}
        torch.set_num_threads(config.get('parallelism', {}).get('torch_threads', 2))
        model = DraftPolicy(**payload['model_config']).to(self.device)
        model.load_state_dict(payload['model'], strict=True)
        from .practice import apply_fork_returns
        from . import sharded
        tasks = payload['tasks']
        seed_rank(config, self.device, self.rank, 'fork')
        router = None
        records, summaries, meaningful, stats = [], [], 0, []
        try:
            slice_tasks = sharded.mine(tasks, self.rank)
            if slice_tasks:
                pool, workers = self.pool_for(config, setup)
                config = {**config, 'workers': workers}
                search = config.get('search', {})
                if search.get('enabled') and search.get('fork_episodes', True):
                    search_cfg = worker_search_config(config, self.size)
                    # Disjoint seed blocks; a shared counter would repeat search seeds.
                    router = SearchRouter(model, self.device, search_cfg,
                                          seed_counter=payload['search_seed_base'] + self.rank * _SEARCH_SEED_BLOCK)
                    config['_search_router'] = router
                records, summaries, meaningful = rollout_bank(
                    pool, model, None, config, self.device, len(slice_tasks),
                    payload['exploration'], choose, tasks=slice_tasks,
                    source=payload['source'], log_path=shard_log(payload['log_path'], self.rank))
            own = [row for row in self.local_summaries if row.get('origin_rank', 0) == self.rank]
            # apply_fork_returns extends self.local_records with the fork records itself
            # (practice.py: `records.extend(fork_records)`); keeping a second list here
            # would count every fork record twice at update time.
            stats = apply_fork_returns(self.local_records, own, records, summaries,
                                       expected_tasks=slice_tasks, objective=payload['objective'])
        finally:
            # Same gather order as the coordinator, or the job blocks until the Gloo timeout.
            self.gather_lists(summaries)
            self.gather_lists(stats)
            self.gather_lists([{'rank': self.rank, 'meaningful': meaningful}])
            if router is not None:
                router.close()
        del model

    # ---- sharded training bank replay -----------------------------------------------

    def bank_replay(self, pool, model, setup, config, tasks, exploration, *, log_path=None):
        """Replay of sampled bank loadouts (already replica-expanded), spread over ranks.

        Replica groups stay whole on one rank so apply_bank_returns can credit them
        there; only summaries and the group diagnostics are gathered. The caller feeds
        the sample bank from the gathered summaries.
        """
        from .bank_rollout import rollout_bank
        from .best_of import apply_bank_returns
        from .runner import choose
        from . import sharded
        if self.size == 1 or not tasks:
            bank_records, bank_summaries, meaningful = rollout_bank(
                pool, model, None, config, self.device, len(tasks),
                exploration, choose, tasks=tasks, source='bank_exam', log_path=log_path)
            groups = apply_bank_returns(bank_records, bank_summaries, tasks) if tasks else []
            return bank_records, bank_summaries, meaningful, groups
        sharded.stamp_shards(tasks, self.size, key=lambda t: t['metadata']['prefix_id'])
        payload = {'command': 'bank_replay', 'model_config': model.config,
                   'model': cpu_copy(model.state_dict()), 'setup': str(setup),
                   'tasks': tasks, 'exploration': exploration,
                   'log_path': None if log_path is None else str(log_path),
                   'config': {k: v for k, v in config.items()
                              if k not in ('_search_router', '_coverage')}}
        self.broadcast(payload)
        slice_tasks = sharded.mine(tasks, self.rank)
        bank_records, bank_summaries, meaningful, groups = [], [], 0, []
        try:
            if slice_tasks:
                bank_records, bank_summaries, meaningful = rollout_bank(
                    pool, model, None, config, self.device, len(slice_tasks), exploration,
                    choose, tasks=slice_tasks, source='bank_exam',
                    log_path=shard_log(log_path, self.rank))
                groups = apply_bank_returns(bank_records, bank_summaries, slice_tasks)
        finally:
            gathered_summaries = self.gather_lists(bank_summaries)
            gathered_groups = self.gather_lists(groups)
            counts = self.gather_lists([{'rank': self.rank, 'meaningful': meaningful}])
        merge_shard_logs(log_path, self.size)
        return bank_records, gathered_summaries, sum(r['meaningful'] for r in counts), gathered_groups

    def serve_bank_replay(self, payload):
        import json
        from pathlib import Path
        from .model import DraftPolicy
        from .bank_rollout import rollout_bank
        from .best_of import apply_bank_returns
        from .runner import choose
        from . import sharded
        setup = Path(payload['setup'])
        config = {**payload['config'],
                  '_profiles': json.loads((setup / 'profiles.json').read_text(encoding='utf-8'))}
        torch.set_num_threads(config.get('parallelism', {}).get('torch_threads', 2))
        model = DraftPolicy(**payload['model_config']).to(self.device)
        model.load_state_dict(payload['model'], strict=True)
        seed_rank(config, self.device, self.rank, 'bank')
        records, summaries, meaningful, groups = [], [], 0, []
        try:
            slice_tasks = sharded.mine(payload['tasks'], self.rank)
            if slice_tasks:
                pool, workers = self.pool_for(config, setup)
                # Bank replays never open search roots (the bank keeps no search flag).
                config = {**config, 'workers': workers}
                records, summaries, meaningful = rollout_bank(
                    pool, model, None, config, self.device, len(slice_tasks),
                    payload['exploration'], choose, tasks=slice_tasks, source='bank_exam',
                    log_path=shard_log(payload['log_path'], self.rank))
                groups = apply_bank_returns(records, summaries, slice_tasks)
            self.local_bank_records = records
        finally:
            self.gather_lists(summaries)
            self.gather_lists(groups)
            self.gather_lists([{'rank': self.rank, 'meaningful': meaningful}])
        del model

    # ---- sharded explicit-task (bank) rollout ---------------------------------------

    def bank_rollout(self, pool, model, setup, config, tasks, *, log_path=None, source='bank_exam'):
        """Greedy replay of an explicit task list, spread over every rank.

        Only used for evaluation replays (greedy, bank=None), where rollout_bank keeps
        no search router and writes no PPO records. The task list is explicit, so the
        shard is a plain slice; the caller's own grouping is keyed by parent seed and is
        order-independent, and it already asserts that every task came back.
        """
        from .bank_rollout import rollout_bank
        from .runner import choose
        if self.size == 1:
            records, summaries, _ = rollout_bank(pool, model, None, config, self.device,
                                                 len(tasks), None, choose, tasks=tasks,
                                                 greedy=True, source=source, log_path=log_path)
            return records, summaries
        payload = {'command': 'bank_rollout', 'model_config': model.config,
                   'model': cpu_copy(model.state_dict()), 'setup': str(setup),
                   'tasks': tasks, 'source': source,
                   'log_path': None if log_path is None else str(log_path),
                   'config': {k: v for k, v in config.items() if k not in ('_search_router', '_coverage')}}
        self.broadcast(payload)
        offset, mine = shard(len(tasks), self.size, self.rank)
        records, summaries = [], []
        try:
            slice_tasks = tasks[offset:offset + mine]
            if slice_tasks:
                records, summaries, _ = rollout_bank(pool, model, None, config, self.device,
                                                     len(slice_tasks), None, choose, tasks=slice_tasks,
                                                     greedy=True, source=source,
                                                     log_path=shard_log(log_path, self.rank))
        finally:
            gathered = self.gather_lists(summaries)
        merge_shard_logs(log_path, self.size)
        return records, gathered

    def serve_bank_rollout(self, payload):
        import json
        from pathlib import Path
        from .model import DraftPolicy
        from .bank_rollout import rollout_bank
        from .runner import choose
        setup = Path(payload['setup'])
        config = {**payload['config'],
                  '_profiles': json.loads((setup / 'profiles.json').read_text(encoding='utf-8'))}
        torch.set_num_threads(config.get('parallelism', {}).get('torch_threads', 2))
        model = DraftPolicy(**payload['model_config']).to(self.device)
        model.load_state_dict(payload['model'], strict=True)
        tasks = payload['tasks']
        offset, mine = shard(len(tasks), self.size, self.rank)
        summaries = []
        try:
            slice_tasks = tasks[offset:offset + mine]
            if slice_tasks:
                pool, workers = self.pool_for(config, setup)
                config = {**config, 'workers': workers}
                _, summaries, _ = rollout_bank(pool, model, None, config, self.device,
                                               len(slice_tasks), None, choose, tasks=slice_tasks,
                                               greedy=True, source=payload['source'],
                                               log_path=shard_log(payload['log_path'], self.rank))
        finally:
            self.gather_lists(summaries)
        del model

    # ---- learner loop ---------------------------------------------------------------

    def serve(self):
        from .model import DraftPolicy
        from .ppo import update
        from gakumas_training.device import optimizer_options, load_optimizer_state
        while True:
            payload = self.broadcast()
            if payload['command'] == 'stop':
                return
            if payload['command'] == 'rollout':
                self.serve_rollout(payload)
                del payload
                continue
            if payload['command'] == 'bank_rollout':
                self.serve_bank_rollout(payload)
                del payload
                continue
            if payload['command'] == 'collect':
                self.serve_collect(payload)
                del payload
                continue
            if payload['command'] == 'fork':
                self.serve_fork(payload)
                del payload
                continue
            if payload['command'] == 'bank_replay':
                self.serve_bank_replay(payload)
                del payload
                continue
            if payload['command'] != 'update':
                raise ValueError('Unknown learner command')
            torch.set_num_threads(payload['config'].get('torch_threads', 2))
            model = DraftPolicy(**payload['model_config']).to(self.device)
            model.load_state_dict(payload['model'], strict=True)
            named = dict(model.named_parameters())
            optimizer = torch.optim.Adam([{'params': [named[n] for n in names]} for names in payload['groups']],
                                         **optimizer_options(model))
            load_optimizer_state(optimizer, payload['optimizer'], self.device)
            # Train on the records this rank produced. The draft duplicate penalty is the
            # one per-record step rank 0 applies after the bank stage; it needs only this
            # rank's own joint summaries, so it is reproduced here in the same order.
            from .construction_reward import apply_draft_penalty
            # local_records already holds the fork records (apply_fork_returns appended
            # them); bank replays are credited without appending, so they join here.
            self.shared_records = 'records' in payload
            if self.shared_records:
                records = payload['records']
            else:
                records = getattr(self, 'local_records', []) + getattr(self, 'local_bank_records', [])
                apply_draft_penalty(records, getattr(self, 'local_summaries', []))
            update(model, optimizer, records, payload['config'], self.device, mesh=self)
            self.local_records, self.local_bank_records, self.local_summaries = [], [], []
            del model, optimizer, payload, records

    def stop(self):
        if self.rank == 0 and self.size > 1:
            self.broadcast({'command': 'stop'})

    def close(self):
        state = getattr(self, 'pool_state', None)
        if state is not None:
            state[1].close()
            self.pool_state = None
        if dist.is_initialized():
            dist.destroy_process_group()


def update_distributed(model, optimizer, records, config, device, progress=None):
    if ACTIVE is not None:
        return ACTIVE.update(model, optimizer, records, config, progress)
    from .ppo import update
    return update(model, optimizer, records, config, device, progress)
