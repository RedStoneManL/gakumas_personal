"""Cooperative public-history search with one GPU owner and bounded inference reuse."""
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
import pickle
import queue
import threading
import time
from .encoding import collate
from .search_adapter import root_search, RejectedRoot


class SearchService:
    def __init__(self, model, device, *, parallel_roots=4, inference_batch=8,
                 inference_cache_bytes=64*1024*1024):
        if any(type(value) is not int or value < 1 for value in (parallel_roots, inference_batch)):
            raise ValueError('Search parallelism and inference batch must be positive integers')
        from .source_stamp import install
        install()
        self.model, self.device = model, device
        self.inference_batch = inference_batch
        self.executor = ThreadPoolExecutor(max_workers=parallel_roots, thread_name_prefix='arena-search')
        self.requests, self.local = queue.Queue(), threading.local()
        self.clients, self.lock = [], threading.Lock()
        self.stats, self.pending = Counter(), set()
        self.closed, self.policy_version = False, None
        self.lexical_caches = ({}, {})
        self.cache, self.cache_lock = OrderedDict(), threading.Lock()
        self.cache_limit, self.cache_bytes = inference_cache_bytes, 0
        self.busy_started = None
        self.last_progress = time.monotonic()

    @staticmethod
    def cache_key(encoded):
        # Full ordered public network input. No state abstractions, hidden
        # seeds, effect merging, or hash-only identity. Preserve signed zeros.
        return pickle.dumps((encoded.atoms, encoded.edges, encoded.entity_count,
                             encoded.action_entities, encoded.phase,
                             len(encoded.submissions)), protocol=5)

    def _get_cached(self, key):
        if key is None:
            return None
        with self.cache_lock:
            value = self.cache.get(key)
            if value is not None:
                self.cache.move_to_end(key)
                self.stats['inference_cache_hits'] += 1
                return (list(value[0]), value[1], list(value[2])) if len(value)>2 else (list(value[0]), value[1])
        return None

    def _put_cached(self, key, value):
        if key is None:
            return
        size = len(key)+128+8*len(value[0])+(8*len(value[2]) if len(value)>2 else 0)
        if size > self.cache_limit:
            return
        with self.cache_lock:
            if key in self.cache:
                return
            while self.cache and self.cache_bytes+size > self.cache_limit:
                old_key, old_value = self.cache.popitem(last=False)
                self.cache_bytes -= len(old_key)+128+8*len(old_value[0])+(8*len(old_value[2]) if len(old_value)>2 else 0)
                self.stats['inference_cache_evictions'] += 1
            self.cache[key] = (tuple(value[0]), value[1], tuple(value[2])) if len(value)>2 else (tuple(value[0]), value[1])
            self.cache_bytes += size
            self.stats['inference_cache_peak_bytes'] = max(
                self.stats['inference_cache_peak_bytes'], self.cache_bytes)

    def _predict(self, encoded, deadline):
        if time.monotonic() >= deadline:
            raise RejectedRoot('inference_deadline')
        key = self.cache_key(encoded) if self.cache_limit else None
        cached = self._get_cached(key)
        if cached is not None:
            return cached
        job = {'encoded': encoded, 'deadline': deadline, 'done': threading.Event(), 'key': key}
        self.requests.put(job)
        if not job['done'].wait(max(0., deadline-time.monotonic())):
            raise RejectedRoot('inference_deadline')
        if 'error' in job:
            raise job['error']
        return job['result']

    def _root(self, task):
        from gakumas_arena.engine.search import SearchClient
        client = getattr(self.local, 'client', None)
        if client is None:
            client = SearchClient(max_worlds=130)
            self.local.client = client
            with self.lock:
                self.clients.append(client)
        result = root_search(self.model, predictor=self._predict, shared_client=client, **task)
        if result['status'] in ('closed', 'worker_timeout', 'cancelled'):
            client.close()
            self.local.client = None
        return result

    def submit(self, tasks):
        if self.closed:
            raise RuntimeError('Search service already closed')
        if not tasks:
            return []
        versions = {task['policy_version'] for task in tasks}
        if len(versions) != 1:
            raise ValueError('One search batch cannot mix policy versions')
        version = next(iter(versions))
        if version != self.policy_version:
            if self.pending:
                raise ValueError('Cannot replace weights with outstanding search roots')
            self.policy_version = version
            for cache in self.lexical_caches:
                cache.clear()
            with self.cache_lock:
                self.cache.clear()
                self.cache_bytes = 0
        if not self.pending:
            self.busy_started = time.monotonic()
        futures = [self.executor.submit(self._root, task) for task in tasks]
        self.pending.update(futures)
        self.stats['roots_submitted'] += len(futures)
        return futures

    def pump(self, *, timeout=0., progress=None):
        """Perform at most one inference batch on the caller/GPU owner thread."""
        import torch
        try:
            first = self.requests.get(timeout=timeout)
        except queue.Empty:
            self._progress(progress)
            return
        jobs = [first]
        until = time.monotonic()+.006
        while len(jobs) < self.inference_batch:
            try:
                jobs.append(self.requests.get(timeout=max(0., until-time.monotonic())))
            except queue.Empty:
                break
        active, unique, by_key = [], [], {}
        for job in jobs:
            if time.monotonic() >= job['deadline']:
                job['error'] = RejectedRoot('inference_deadline')
                job['done'].set()
                self.stats['expired_inference_requests'] += 1
                continue
            cached = self._get_cached(job['key'])
            if cached is not None:
                job['result'] = cached
                job['done'].set()
                continue
            active.append(job)
            key = job['key']
            if key is not None and key in by_key:
                job['prediction_index'] = by_key[key]
                self.stats['inference_cache_coalesced'] += 1
            else:
                job['prediction_index'] = len(unique)
                if key is not None:
                    by_key[key] = len(unique)
                unique.append(job)
        if unique:
            tick = time.monotonic()
            try:
                batch = collate([job['encoded'] for job in unique], self.device)
                assembled = time.monotonic()
                encoders = (self.model.actor, self.model.critic)
                try:
                    for encoder, cache in zip(encoders, self.lexical_caches):
                        encoder._search_lex_cache = cache
                    with torch.inference_mode():
                        logits, values, atoms = self.model.search_forward(batch)
                        probabilities = logits.softmax(-1).cpu().tolist()
                        predictions = values.cpu().tolist()
                        distributions = atoms.cpu().tolist() if atoms is not None else None
                finally:
                    for encoder in encoders:
                        encoder._search_lex_cache = None
                self.stats['assembly_seconds'] += assembled-tick
                self.stats['forward_seconds'] += time.monotonic()-assembled
                for i,(job, prior, value) in enumerate(zip(unique, probabilities, predictions)):
                    result = (prior[:len(job['encoded'].submissions)], value)
                    if distributions is not None:result += (distributions[i],)
                    self._put_cached(job['key'], result)
                for job in active:
                    k = job['prediction_index']
                    job['result'] = (probabilities[k][:len(job['encoded'].submissions)], predictions[k])
                    if distributions is not None:job['result'] += (distributions[k],)
                self.stats['inference_batches'] += 1
                self.stats['inference_examples'] += len(unique)
                self.stats['inference_requests_served'] += len(active)
                self.stats['inference_seconds'] += time.monotonic()-tick
                self.stats[f'batch_size_{len(unique)}'] += 1
            except Exception as error:
                for job in active:
                    job['error'] = error
            finally:
                for job in active:
                    job['done'].set()
        self._progress(progress)

    def _progress(self, callback):
        if callback and time.monotonic()-self.last_progress >= 30:
            callback(completed_roots=sum(f.done() for f in self.pending), roots=len(self.pending))
            self.last_progress = time.monotonic()

    def take(self, future):
        if future not in self.pending or not future.done():
            raise ValueError('Search result is not ready or was already consumed')
        try:
            result = future.result()
            self.stats['roots'] += 1
            self.stats['eligible_targets'] += bool(result['valid_training_target'])
            return result
        finally:
            self.pending.remove(future)
            if not self.pending:
                # Timed-out roots can leave an orphaned inference request.
                # Never carry it into the next policy version or update.
                while True:
                    try:
                        orphan = self.requests.get_nowait()
                    except queue.Empty:
                        break
                    orphan['error'] = RejectedRoot('root_closed')
                    orphan['done'].set()
                self.stats['search_many_seconds'] += time.monotonic()-self.busy_started
                self.busy_started = None

    def search_many(self, tasks, progress=None):
        futures = self.submit(tasks)
        while any(not f.done() for f in futures):
            self.pump(timeout=.01, progress=progress)
        return [self.take(f) for f in futures]

    def close(self):
        if self.closed:
            return
        # Drain requests before joining roots: roots may be waiting for the
        # only GPU owner. Closing must not deadlock on a queued prediction.
        while self.pending:
            self.pump(timeout=.01)
            for future in list(self.pending):
                if future.done():
                    try:
                        self.take(future)
                    except Exception:
                        pass
        self.closed = True
        self.executor.shutdown(wait=True)
        for client in self.clients:
            client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
