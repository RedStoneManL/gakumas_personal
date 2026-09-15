"""Independent Python search processes; one parent process owns all GPU inference."""
import multiprocessing as mp
from multiprocessing.util import Finalize
from concurrent.futures import ProcessPoolExecutor
import queue
import time
from .async_service import SearchService as CooperativeSearchService
from .search_adapter import RejectedRoot

_worker_client = None


def _close_worker():
    global _worker_client
    if _worker_client is not None:
        _worker_client.close()
        _worker_client = None


def _initialize(requests, responses, counter):
    global _worker_requests, _worker_responses, _worker_slot, _worker_sequence
    # Workers encode public observations and simulate; the parent owns inference.
    # Loading Torch here would allocate its DLLs in every Windows worker.
    with counter.get_lock():
        _worker_slot = counter.value
        counter.value += 1
    _worker_requests, _worker_responses = requests, responses[_worker_slot]
    _worker_sequence = 0
    from .source_stamp import install
    install()
    Finalize(None, _close_worker, exitpriority=10)


def _predict(encoded, deadline):
    global _worker_sequence
    _worker_sequence += 1
    sequence = _worker_sequence
    _worker_requests.put({'encoded':encoded, 'deadline':deadline,
                          'slot':_worker_slot, 'sequence':sequence,
                          'policy_version':_worker_policy_version})
    while True:
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise RejectedRoot('inference_deadline')
        try:
            answer = _worker_responses.get(timeout=remaining)
        except queue.Empty:
            raise RejectedRoot('inference_deadline') from None
        if answer['sequence'] < sequence:
            continue  # An earlier root's expired request cannot affect this root.
        if answer['sequence'] != sequence:
            raise RuntimeError('Crossed inference response ownership')
        if 'error' in answer:
            if answer['rejected']:
                raise RejectedRoot(answer['error'])
            raise RuntimeError('Parent inference failed: '+answer['error'])
        return answer['result']


def _root(task):
    global _worker_client, _worker_policy_version
    from gakumas_arena.engine.search import SearchClient
    from .search_adapter import root_search
    _worker_policy_version = task['policy_version']
    if _worker_client is None:
        _worker_client = SearchClient(max_worlds=130)
    result = root_search(None, predictor=_predict, shared_client=_worker_client, **task)
    if result['status'] in ('closed','worker_timeout','cancelled'):
        _close_worker()
    return result


class _Completion:
    def __init__(self, job, output):
        self.job, self.output = job, output

    def set(self):
        result = {'sequence':self.job['sequence']}
        if 'error' in self.job:
            error = self.job['error']
            result.update(error=str(error), rejected=isinstance(error,RejectedRoot))
        else:
            result['result'] = self.job['result']
        self.output.put(result)


class _Requests:
    def __init__(self, queue, outputs, owner):
        self.queue, self.outputs, self.owner = queue, outputs, owner

    def get(self, timeout=0.):
        job = self.queue.get(timeout=timeout)
        job['done'] = _Completion(job, self.outputs[job['slot']])
        job['key'] = self.owner.cache_key(job['encoded']) if self.owner.cache_limit else None
        if job['policy_version'] != self.owner.policy_version:
            job['deadline'] = 0.
        return job

    def get_nowait(self):
        return self.get(timeout=0.)


class _Executor:
    def __init__(self, executor):
        self.executor = executor

    def submit(self, unused_bound_method, task):
        # Never pickle the parent model, CUDA tensors, or recorder to a worker.
        return self.executor.submit(_root,task)

    def shutdown(self, wait=True):
        self.executor.shutdown(wait=wait)


class ProcessSearchService(CooperativeSearchService):
    worker_backend = 'process-v1'

    def __init__(self, model, device, *, parallel_roots=4, inference_batch=8,
                 inference_cache_bytes=0):
        super().__init__(model,device,parallel_roots=parallel_roots,
                         inference_batch=inference_batch,inference_cache_bytes=inference_cache_bytes)
        self.executor.shutdown()
        context = mp.get_context('spawn')
        self.request_queue = context.Queue()
        self.response_queues = [context.Queue() for _ in range(parallel_roots)]
        self.worker_counter = context.Value('i',0)
        executor = ProcessPoolExecutor(max_workers=parallel_roots,mp_context=context,
            initializer=_initialize,initargs=(self.request_queue,self.response_queues,self.worker_counter))
        self.executor = _Executor(executor)
        self.requests = _Requests(self.request_queue,self.response_queues,self)

    def close(self):
        if self.closed:
            return
        try:
            super().close()
        finally:
            for pipe in [self.request_queue,*self.response_queues]:
                pipe.cancel_join_thread()
                pipe.close()
