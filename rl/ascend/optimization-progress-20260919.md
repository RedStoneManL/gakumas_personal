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


## Latest framework and full-pipeline profiling (2026-09-19)
- Preserved old optimization at edba11b; latest remote framework cff87da merged at 04f168e on codex/npu-utilization-v6-credit.
- Original production remains stopped. User now authorizes starting a NEW production run after optimization validation, using the preserved production checkpoint, never short-course perf weights.
- Reused lexical caches, static type indices, bucket pooling, six-profile operational fixes. Added worker input preparation, bounded asynchronous auxiliary labels and a fresh bank replay controller fix.
- Full regression r2: 53 core + 177 search tests, distributed sharded script passed. Additional bank/perf precheck: 22 tests passed.
- 8-NPU full-pipeline perf r2 completed one update: collect 2.8m, forks 1.3m, bank 0.7m, PPO 3.6m; total run 9.55m. Launcher hit its 10-minute timeout during cleanup (exit124); completed checkpoint/result preserved.
- Actual NPU AICore mean was only ~0.2% collection and 1.1% PPO; 80% target NOT met. CPU mean ~19.6% collection /7.6% PPO. py-spy identifies IPC/serialization plus portable GRU, with steady sample dominated by unrolled GRU.
- Native NPU fused FP32 GRU is unsupported by DynamicGRUV2. Separate CPU-packed GRU bridge probe preserves outputs within 2.1e-7 and input gradients within 2.4e-7. Parameter gradients differ up to 1.4e-5 (FP32 backend reduction order); larger case failed the original 2e-6 absolute tolerance, so explicit cross-device tolerance validation is pending.
- LOCAL changes not yet deployed/fully verified: compact int32 worker arrays, return prepared arrays instead of duplicate Encoded objects, scoped normal-rollout lexical cache, CPU packed GRU with differentiable copies, bounded phase/profile-balanced perf update and perf scene coverage for drinks/HIF memory.
- Evidence: /mnt/local/gakumas/evidence/v7-opt; isolated code /mnt/local/gakumas/deploy-v6-credit-opt. Preserve all evidence; do not overwrite baseline deployments or production checkpoints.


## Pending full-model GRU gate
- Added ascend/scripts/verify_gru_backend.py (deployed as ascend/verify_gru_backend.py). It uses real inputs from every profile and all five public phases, the preserved full model, nonzero relational heads, all parameter gradients, and one Adam update. Portable and CPU-packed paths use identical initial weights/inputs; output, gradient norm/max error, optimizer parameter ownership, and parameter-update error are checked. It records timings but is not a throughput or quality claim.
- The script is bounded to one forward/backward/update per backend and refuses CPU-only verification, output/checkpoint aliasing, or overwriting an existing report. Run it with an external 180-second bound before the next saturated full-pipeline probe. Current local checks are syntax and CLI only: no local torch installation is available. NPU numerical success remains unproven.
- Suggested remote invocation after the pending credential-method approval: timeout 180s python ascend/verify_gru_backend.py --root /mnt/local/gakumas/deploy-v6-credit-opt --initial /mnt/local/gakumas/runs/prod-v7/latest.pt --device npu:0 --output /mnt/local/gakumas/evidence/v7-opt/gru-full-model-r3.json
- This is the second goal turn encountering the same credential-method approval blocker. The first and second turns still made local progress. Remote credentials have not been retried or accessed since the rejected operation; wait for explicit user approval before further remote actions.
