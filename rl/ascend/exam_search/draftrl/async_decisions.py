"""Overlap auxiliary labels with real on-policy actions on a frozen policy."""
import time


class AsyncDecisions:
    def __init__(self, router):
        self.router = router
        self.pending = {}
        self.auxiliary = (getattr(router, 'execution_mode', 'act') == 'auxiliary'
                          and router.config.get('auxiliary_async', True))
        self._auxiliary = {}
        self._unbound = {}

    def submit(self, pool, items, proposals, policy_version):
        if len(items) != len(proposals):
            raise ValueError('Unaligned decision proposals')
        if self.auxiliary:
            # Keep the process pool bounded. Busy slots skip this candidate,
            # without pausing behavior or spending a root seed/episode budget.
            capacity = max(0, self.router.config['parallel_roots'] - len(self._auxiliary))
            tasks, positions, extras = self.router.prepare(pool, items, policy_version, capacity=capacity)
        else:
            tasks, positions, extras = self.router.prepare(pool, items, policy_version)
        futures = self.router.service.submit(tasks)
        searched = dict(zip(positions, futures))
        ready = []
        for position, proposal in enumerate(proposals):
            worker = proposal[0]
            if worker in self.pending:
                raise ValueError('Cannot advance an exam with outstanding search')
            if position in searched and self.auxiliary:
                attachment = {'proposal': proposal, 'item': items[position], 'record': None}
                self._auxiliary[searched[position]] = attachment
                self._unbound[id(extras[position])] = attachment
                ready.append((*proposal, extras[position]))
            elif position in searched:
                self.pending[worker] = (searched[position], proposal, items[position])
            else:
                ready.append((*proposal, extras[position]))
        if self.pending or self._auxiliary:
            self.router.service.stats['ordinary_actions_during_search'] += len(ready)
        if self._auxiliary:
            self.router.service.stats['auxiliary_actions_overlapped'] += len(ready)
            self.router.service.stats['peak_auxiliary_roots'] = max(
                self.router.service.stats['peak_auxiliary_roots'], len(self._auxiliary))
        return ready

    def bind(self, record, extra):
        """Attach a result to this exact record, even after its worker is reused."""
        attachment = self._unbound.pop(id(extra), None)
        if attachment is not None:
            attachment['record'] = record

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
        for future, attachment in list(self._auxiliary.items()):
            if not future.done():
                continue
            record = attachment['record']
            if record is None:
                raise RuntimeError('Auxiliary search has no bound on-policy record')
            proposal = attachment['proposal']
            action, logp = proposal[2:4]
            result = self.router.service.take(future)
            selected, probability, extra = self.router.finish(attachment['item'], result, action, logp)
            if (selected, probability) != (action, logp) or extra['loss_kind'] != 'ppo':
                raise RuntimeError('Auxiliary search changed the behavior policy')
            if (record['action'], record['old_logp']) != (action, logp):
                raise RuntimeError('Auxiliary search was bound to a different decision')
            record.update(extra)
            del self._auxiliary[future]
        return ready

    def drain(self):
        """Finish labels before serialization, peer credit, or any weight update."""
        started = time.monotonic()
        while self._auxiliary:
            self.poll(wait=True)
        self.router.service.stats['auxiliary_drain_seconds'] += time.monotonic() - started
        self.assert_drained()

    def assert_drained(self):
        if self.pending or self._auxiliary or self._unbound or self.router.service.pending:
            raise RuntimeError('Unfinished search cannot cross a rollout/update boundary')
