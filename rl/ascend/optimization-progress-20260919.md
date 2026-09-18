# Ascend optimization checkpoint — 2026-09-19

Base: 65663b7 (relational-v6-sena). Working branch: codex/npu-utilization.
Production prod-v7 was stopped by explicit user request before its first update.
Its latest.pt, logs, and unfinished-rollout evidence remain intact.
The user subsequently requested carrying this work onto the latest remote framework.

## Implemented and measured

- Independent frozen-policy lexical caches for relational actor/critic, cleared with the existing policy-version boundary; gradient-enabled forward bypasses the cache.
- CPU-prepared type/scope indices remove repeated NPU nonzero shape synchronizations.
- CPU-prepared count-bucketed max-pooling plans avoid global size*widest padding, integer device sorting, and index_reduce CPU fallback in prepared paths.
- Three focused tests pass, including tied maxima and sparse/empty groups with exact CPU forward/backward agreement.
- Before pooling change, 30 cache/relational model/training/runtime tests passed.
- Real public inputs for six production profiles, 910B3, same checkpoint with nonzero relational output heads, 3 timed repetitions after warmup:
  - batch 1: 9.07 -> 14.82 examples/s
  - batch 16: 111.74 -> 216.89 examples/s
  - batch 32: 166.35 -> 368.08 examples/s
  - batch 48: 181.82 -> 459.91 examples/s
- Maximum finite output difference across these comparisons: 1.43e-6.
- These are forward-only, warm-cache microbenchmarks; they do not establish end-to-end throughput or policy quality.

## Latest unvalidated implementation

- Existing Arena workers now prepare immutable relational inputs in parallel.
- Plain exam steps can return prepared encoded inputs directly.
- Construction and subchoice inputs use a new encode RPC on those same workers.
- Compact numpy pre-collations are attached to immutable examples and reused by PPO; the duplicate Python relational graph is removed after preparation.
- This last CPU offload/cache change has not yet been uploaded or tested. Preserve it as WIP and reassess against the updated framework.

## Live bounded diagnostic

- Original deployment remains /mnt/local/gakumas/deploy-v7.
- Isolated candidate: /mnt/local/gakumas/deploy-v7-opt.
- Evidence: /mnt/local/gakumas/evidence/v7-opt/.
- Single-card full pipeline baseline: /mnt/local/gakumas/runs/v7-perf-baseline.
- Baseline config: 24 environment workers/search slots, inference batch 24, microbatch 32, one epoch/one batch, soft batch target 128 decisions; six eval episodes; 16 simulations and one searched root per episode; true-terminal quality gates preserved.
- Production candidate config /mnt/local/gakumas/configs/prod/search-v7-opt.json sets search.seconds=1200, preserving other search quality settings.
- py-spy 30-second sample (2775 stacks): flatten leaf frames ~21%; reconstruct_nodes ~10%; additional semantic walks and copies. CPU graph preparation is a significant pipeline bottleneck, beyond NPU forward performance.
- Files: baseline.json, cache-types.json, bucket-pool.json, associated logs; baseline-initial.raw; tests-cache-types.log, tests-pool.log; pipeline-baseline.log; prod-stop-request.json.
- Local collection scripts/evidence are under D:/gakumas/diagnostics.

## Next steps

Fetch/identify the updated framework branch, preserve this commit, compare changed module contracts, port only compatible optimizations into a fresh branch, rerun CPU equivalence and actual NPU/pipeline tests. Keep the full production job stopped while profiling as the user requested.
