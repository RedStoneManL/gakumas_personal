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
    """Concatenate the per-rank episode logs into one file ordered by seed.

    The dashboard reads validation-*-episodes.jsonl (generalist_data.py), so the merged
    file must hold every episode, not just the coordinator's slice. Written to a
    temporary file and renamed so a reader never sees a half-merged log.
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
    temporary = log_path.with_suffix(log_path.suffix + '.merging')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    temporary.replace(log_path)
    for part in present:
        part.unlink()


class LearnerGroup(CollectiveGroup):
    def update(self, model, optimizer, records, config, progress=None):
        from .ppo import update
        if self.size > 1:
            names = {id(p): name for name, p in model.named_parameters()}
            groups = [[names[id(p)] for p in g['params']] for g in optimizer.param_groups]
            payload = {'command': 'update', 'model_config': model.config,
                       'model': cpu_copy(model.state_dict()), 'optimizer': cpu_copy(optimizer.state_dict()),
                       'groups': groups, 'records': records,
                       'config': {k: v for k, v in config.items() if k not in ('_search_router', '_coverage')}}
            self.broadcast(payload)
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
        records, summaries, meaningful, next_seed = rollout(
            pool, model, None, catalog, config, self.device, episode_index + self.rank,
            target_decisions=max(1, share), seed_stride=self.size, exploration=exploration,
            scenario_bank=bank, keep_entries=keep_entries,
            log_path=shard_log(log_path, self.rank) if self.size > 1 else log_path)
        started = (next_seed - (episode_index + self.rank)) // self.size
        if self.size == 1:
            return records, summaries, meaningful, next_seed, bank.rows
        gathered_records = self.gather_lists(records)
        gathered_episodes = self.gather_lists(summaries)
        gathered_bank = self.gather_lists(bank.rows)
        counts = self.gather_lists([{'rank': self.rank, 'started': started,
                                     'meaningful': meaningful}])
        merge_shard_logs(log_path, self.size)
        merge_shard_logs(search_log, self.size)
        # Advance past every rank's highest used seed. Ranks stop at different episode
        # counts, so this leaves at most size-1 unused indices; reusing them instead would
        # let a later batch replay an episode some rank already produced.
        widest = max(row['started'] for row in counts) if counts else 0
        total_meaningful = sum(row['meaningful'] for row in counts)
        # Bank order must not depend on which rank happened to report first.
        gathered_bank.sort(key=lambda row: row['seed'])
        return (gathered_records, gathered_episodes, total_meaningful,
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
        router = None
        records, summaries, bank = [], [], _BankRows()
        started, meaningful = 0, 0
        try:
            pool, workers = self.pool_for(config, setup)
            parallel = config.get('parallelism', {})
            roots = max(1, int(parallel.get('parallel_roots', 1)) // self.size)
            search_cfg = {**config['search'], 'parallel_roots': roots,
                          'inference_batch': min(int(parallel.get('inference_batch', roots)), roots)}
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
            self.gather_lists(records)
            self.gather_lists(summaries)
            self.gather_lists(bank.rows)
            self.gather_lists([{'rank': self.rank, 'started': started,
                                'meaningful': meaningful}])
            if router is not None:
                router.close()
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
            if payload['command'] != 'update':
                raise ValueError('Unknown learner command')
            torch.set_num_threads(payload['config'].get('torch_threads', 2))
            model = DraftPolicy(**payload['model_config']).to(self.device)
            model.load_state_dict(payload['model'], strict=True)
            named = dict(model.named_parameters())
            optimizer = torch.optim.Adam([{'params': [named[n] for n in names]} for names in payload['groups']],
                                         **optimizer_options(model))
            load_optimizer_state(optimizer, payload['optimizer'], self.device)
            update(model, optimizer, payload['records'], payload['config'], self.device, mesh=self)
            del model, optimizer, payload

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
