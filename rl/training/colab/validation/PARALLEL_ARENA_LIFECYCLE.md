# Arena spawn / Pipe lifecycle audit

Checked 2026-09-11. Read-only review of training/Arena production sources; the
adjacent probe is CPU-only and produces no PPO training samples.

## Existing guarantees and boundaries

- `gakumas_arena/engine/training.py:85` defines one `_Transport` singleton per
  Python process. Its `owner_pid` guard at line 128 prevents a forked child from
  using or killing its parent's Node process. Use **spawn** anyway, so no parent
  CUDA context, inherited pipe ends, thread locks, or imported singleton state
  enter environment workers.
- `TrainingExam` stores each exam's seed and private action history in its own
  Python instance. `training_worker.mjs:122` calls `resetRand(seed)` when recreating
  a replay. Full-produce runtime state is similarly instance-local. Interleaving
  distinct tasks does not make one task consume another task's RNG sequence.
- Public observations exclude private snapshot/hidden order. Send only
  `DecisionContext` over the inference pipe, never `TrainingExam.snapshot()` or
  `inspect_private()`.
- `close_training_worker()` calls `_transport.close()` (training.py:157–174):
  clear the current process reference, kill a live Node process, wait up to five
  seconds, then close stdin/stdout. `Task.close()` reaches this API. Closing one
  task closes the **process-wide** worker; it is not a per-exam destructor.
- `_transport.process` is either `None` or the Node `Popen`; its `.pid` is the
  current Node PID. Full-produce can reach outer callbacks before starting Node,
  so PID diagnostics must permit `None`. A restart can change that PID.
- Native transport EOF/timeout kills the failed transport and raises
  `TrainingError`; a native semantic error also raises. Neither is a zero-score
  terminal. Keep errors visible and discard the unfinished collection batch.

## Collector integration requirements

1. Construct `Task` inside a top-level spawn target. Use an importable script and
   an `if __name__ == '__main__'` guard. Pass JSON configs and an absolute explicit
   Arena root; do not pickle a constructed task or a model into the environment.
2. Child `try/finally` must call `task.close()` and close its connection. Parent
   must close its duplicate **child-side** connection immediately after spawn;
   otherwise parent disconnection may not produce EOF in the child. Explicit
   cleanup is required even if Python registered an `atexit` hook.
3. Parent inference failures should close/send cancellation to every active
   worker, then join with a bound. A child blocked awaiting a selection detects
   pipe EOF and enters its cleanup. Request IDs and policy versions must match;
   do not return `encoded` CUDA tensors to CPU workers. Keep encoded state in the
   parent and send only action index/log probability/value/version if possible.
4. Watch both connections and worker sentinels. Use bounded waits and propagate
   worker exit/error; do not wait forever for a decision from a dead worker.
5. Linux: call `os.setsid()` before constructing Arena in each child, acknowledge
   its PID/process-group ID, then retain cooperative shutdown first. The parent's
   last-resort termination can target **that owned group** using
   `os.killpg(pgid, SIGTERM)` and, after a bound, `SIGKILL`. This also covers a
   native worker stuck before its first callback/PID report. This Linux fallback
   is source-reviewed here, not locally executed on this Windows host.
6. Windows: a possible fallback is hidden `taskkill /PID <owned_python_pid> /T /F`
   **before** killing/reaping the Python parent; terminating Python first can
   lose the descendant tree. Check return status and actual termination. This
   host's sandbox returned code 1, `拒绝访问`, for that operation on a probe-owned
   child, so forced tree termination is **not validated** here. Both failed probe
   attempts subsequently cleaned their own Python/Node processes by closing the
   inference pipes. No unrelated process was inspected or terminated.

Native RNG isolation does not by itself guarantee bit-identical stochastic
neural rollouts when concurrent inference arrival order changes. A shared Torch
generator is consumed in scheduling order. Frozen behavior parameters and exact
logged probabilities preserve on-policy correctness; exact rerun reproducibility
would additionally require a stable sampling/order scheme. Keep episode output
ordered by assigned seed for logging and profile accounting.

## Bounded experiment

`parallel_arena_lifecycle_probe.py` uses two spawned processes and parent-side
deterministic selection through `multiprocessing.Pipe`. Each runs the same full
produce seed and two exam seeds, in different task orders. It checks:

- same seed: identical hash of **all public decision contexts**, final score,
  termination and transition count across processes;
- distinct seeds: different decision trace hashes;
- one distinct persistent Node process per Python worker;
- cancelled inference: no returned Episode;
- normal stop and parent pipe disconnect: both Python and their Node exit.

`parallel-arena-lifecycle-probe.json` records the successful normal/EOF run.
The force-stop field is explicitly unavailable; `--skip-force` does not claim
coverage of forced termination. No throughput or GPU scaling claim follows from
this correctness experiment.
