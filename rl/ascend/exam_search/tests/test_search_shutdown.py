"""Expired inference payloads cannot hold a completed process pool open."""
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import queue
import time
import unittest

from draftrl.process_service import _initialize


def leave_orphan():
    from draftrl import process_service
    process_service._worker_requests.put(b'x' * (2 * 1024 * 1024))
    return {'status': 'complete', 'result': 71}


def shutdown_case(report):
    ctx = mp.get_context('spawn')
    requests = ctx.Queue()
    responses = [ctx.Queue()]
    counter = ctx.Value('i', 0)
    executor = ProcessPoolExecutor(max_workers=1, mp_context=ctx,
        initializer=_initialize, initargs=(requests, responses, counter))
    worker = None
    try:
        result = executor.submit(leave_orphan).result(timeout=8)
        worker = next(iter(executor._processes.values()))
        # Match normal shutdown: every result is consumed, no reader remains
        # for an inference request that arrived after the last root expired.
        executor.shutdown(wait=False)
        worker.join(3)
        report.put({'result': result, 'exited': not worker.is_alive(),
                    'exitcode': worker.exitcode})
    finally:
        if worker is not None and worker.is_alive():
            worker.terminate(); worker.join(3)
        executor.shutdown(wait=True)
        for pipe in [requests, *responses]:
            pipe.cancel_join_thread(); pipe.close()


class SearchShutdownTests(unittest.TestCase):
    def test_completed_result_preserved_when_orphan_exceeds_pipe_capacity(self):
        ctx = mp.get_context('spawn')
        report = ctx.Queue()
        process = ctx.Process(target=shutdown_case, args=(report,))
        process.start()
        try:
            result = report.get(timeout=15)
            process.join(5)
            self.assertEqual(result['result'], {'status': 'complete', 'result': 71})
            self.assertTrue(result['exited'], 'Worker hung flushing an orphaned inference request')
            self.assertEqual(result['exitcode'], 0)
            self.assertEqual(process.exitcode, 0)
        finally:
            if process.is_alive(): process.terminate(); process.join(3)
            report.close()


if __name__ == '__main__': unittest.main()
