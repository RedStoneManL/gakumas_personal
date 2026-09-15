"""Keep each exam stationary only while its own search decision is outstanding."""


class AsyncDecisions:
    def __init__(self, router):
        self.router = router
        self.pending = {}

    def submit(self, pool, items, proposals, policy_version):
        if len(items) != len(proposals):
            raise ValueError('Unaligned decision proposals')
        tasks, positions, extras = self.router.prepare(pool, items, policy_version)
        futures = self.router.service.submit(tasks)
        searched = dict(zip(positions, futures))
        ready = []
        for position, proposal in enumerate(proposals):
            worker = proposal[0]
            if worker in self.pending:
                raise ValueError('Cannot advance an exam with outstanding search')
            if position in searched:
                self.pending[worker] = (searched[position], proposal, items[position])
            else:
                ready.append((*proposal, extras[position]))
        if self.pending:
            self.router.service.stats['ordinary_actions_during_search'] += len(ready)
        return ready

    def poll(self, *, wait=False):
        self.router.service.pump(timeout=.01 if wait else 0., progress=self.router.progress)
        ready = []
        for worker, (future, proposal, item) in list(self.pending.items()):
            if not future.done():
                continue
            result = self.router.service.take(future)
            i, encoded, action, logp, value, setting, diagnostic = proposal
            action, logp, extra = self.router.finish(item, result, action, logp)
            ready.append((i, encoded, action, logp, value, setting, diagnostic, extra))
            del self.pending[worker]
        return ready

    def assert_drained(self):
        if self.pending or self.router.service.pending:
            raise RuntimeError('Unfinished search cannot cross a rollout/update boundary')

