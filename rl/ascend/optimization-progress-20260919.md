# Ascend optimization checkpoint — 2026-09-19

Base: 65663b7 (relational-v6-sena). Working branch: codex/npu-utilization.
Production prod-v7 was stopped by explicit user request before its first update.
Its latest.pt, logs, and unfinished-rollout evidence remain intact.
The user subsequently requested carrying this work onto the latest remote framework.

## Fixed-play evaluation sharding (2026-09-19)

- Production batch1 committed124878 meaningful decisions at13:30:53. Actual
  collection/fork/bank wall time34.07m and PPO69.60m. Ordinary fixed-play evaluation
  then took5.5m on rank0 while the other7 learners waited in their serving loop.
- Route the unchanged fixed-loadout/seed task list through the existing distributed
  greedy bank-rollout path already used by construction Best-of-4 evaluation.
  Gather all ranks before Best-of-4 grouping; reject missing/duplicate seeds,
  including a lost whole four-seed group, and reject generated training records.
- Both focused sharding tests passed: serial/eight-shard summary identity even
  when groups cross ranks and completion order changes; missing/duplicate tasks
  and training records rejected. All5 existing Best-of-4 tests also passed.
  Two existing distributed math tests passed; a third signed-credit math test
  did not finish within the45s bound. That broader suite is NOT claimed passed;
  no distributed optimizer math was changed. No extra production/perf run.
- The fixed-play speedup has not yet been measured in production. The GRU model,
  gradient and Adam gates below remain applicable; this routing change does not
  alter model computation, tasks, seeds, replicas or reduction grouping.

## Latest: buffered CPU GRU backward (2026-09-19 13:03 CST)

This section supersedes the historical status and approval notes below. Production
is running at 8ad87e6, not stopped. Existing SSH credential use is authorized.

- Live Python sampling attributed about 60.6% of PPO time to backward, with CPU
  packed GRU forward another 10.6%. Native stacks show composite CPU GRU and
  slice_backward zero-fill/gradient accumulation. Native sampling lagged and
  perturbed one PPO block; its percentages are not unbiased. Do not repeat it.
- Added an analytical first-order packed GRU backward. It writes each time step's
  gate gradients into one allocated buffer and reduces weight gradients in batched
  matrix multiplies, eliminating repeated full packed-tensor slice gradients.
  Parameter leaves, FP32, ragged packing, model architecture and objective stay intact.
  Higher-order derivatives are explicitly unsupported. Native CPU inference remains
  unchanged; `GAKUMAS_LEXICAL_GRU_BACKEND=cpu` selects the prior training backend.
- CPU finite-difference, ragged lengths, padding, bias/no-bias, input and parameter
  gradients, leaf identity, and one Adam update passed. Real 30-example six-profile,
  five-phase vocabularies took 18.1 seconds to check with one CPU thread: total GRU
  forward/backward speedups 2.39x (1149 words) and 3.11x (2287 words), max byte length234.
  Forward outputs were bit-identical; parameter gradient max error4.66e-10 for the
  normalized diagnostic loss. Evidence: buffered-gru-real-cpu.json.
- Full production-checkpoint NPU gate passed in19.1s, six profiles/five phases,
  662 gradient-bearing tensors/4563708 parameters. Output max error5.72e-6 (passes
  combined abs/relative limit), gradient max3.81e-6, relativeL2 2.89e-7, one Adam
  parameter max1.26e-6. One full forward/backward pair: cpu3.475s -> buffered2.350s,
  a32.4% reduction. This is a bounded numerical/timing gate, not an end-to-end claim.
  Evidence: /mnt/local/gakumas/evidence/v7-opt/gru-buffered-full-model.json.
- At13:02:47 production batch0 remained in PPO epoch3/4, step317,36201/61188 record
  passes (59.2%). It must finish and commit before switching source. All eight
  learners were live. Cumulative decisions0 remains expected until commit;
  global collection target is32768,4096 per rank.
- Aggregate root result was379/391 accepted (96.9%), all379 ok_truncated. Include
  merged search-roots.jsonl as well as rank files and deduplicate policy/seed;
  do not confuse truncated accepted roots with completion of96 simulations.
- Candidate contains the previously validated compact IPC transport. Initial
  best-of-four reference reuse affects fresh starts only; actual initial/boundary
  scores differ and the reason is unresolved. Do not claim score equivalence.
- Safe adoption uses the existing audited paused/complete continuation boundary,
  preserving weights, Adam, RNG, bank, coverage and history. No hot-patching or
  discarding this first batch. The80% utilization goal is still unmet.

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


## Verified progress after VPN recovery

- Existing Claude-record SSH authorization was explicitly confirmed. The later command-tool approval timeouts were transient and recovered; they are no longer the credential blocker.
- Deployed and hash-verified revision 8ad87e6 to deploy-v6-credit-opt. Regression r3: 53 core +183 search tests and sharded learner script passed. Full NPU model gate passed over 30 real inputs/six profiles/five phases: gradient max7.15e-6, relativeL2 5.57e-7, Adam delta4.30e-6. Isolated GRU FP32 probes passed; large CPU GRU case was slower, so no uniform speedup claim.
- Eight-NPU perf-r3 completed1update and launcher EXIT=0: 4.572min,17851 meaningful decisions; collect1.8m/fork0.9m/bank0.5m/PPO0.5m. PPO was intentionally capped; total time is NOT an apples-to-apples production speedup versus r2. Actual six-profile forward/back batch64 rate154.69/s versus previous144.95/s.
- NPU AICore means remained very low (collect0.16%,fork/bank0.08%; coarse sampled PPO0%). The80% utilization objective remains unmet. Detailed evidence is in /mnt/local/gakumas/evidence/v7-opt/pipeline-r3-*.
- Production started from ORIGINAL /mnt/local/gakumas/runs/prod-v7/latest.pt, never perf weights. Run /mnt/local/gakumas/runs/prod-v6-credit-throughput, torchrunPID900947, learnerPIDs900968..900975; 8NPUs,384environmentworkers/searchslots,inference48,micro64,roots1200s,simulations96/particles8,auxiliary contract and quality gates preserved. Live source is8ad87e6, runtime digest26f3b354249a83381782c9e9537de668f1803fea17d8270e50d4ff062931f005. At27.4min it was healthy in collection, rank0 around4054/4096 decisions with48active roots. Most roots were still running; a few Sena roots failed posterior particle generation. No improved acceptance claim yet.
- User explicitly prioritizes server cost and major bottlenecks; no more NPU-only micro-tests or repeated full pipeline runs for small changes. Further verification below used one CPU thread while production continued.

### Next revision (local and isolated candidate; NOT hot-patched into production)

1. Main measured bank/fork bottleneck is deserializing complete Encoded objects: recv(connection.py:251)58.7%/64.3%, mostly bank_rollout.py:125 post-step receive, not serial reset. CompactEncoded transfers prepared arrays immediately and retains the redundant original graph in compressed bytes, decoding it only on actual diagnostic/fallback access. No precision/schema/action changes. All30profile/phase inputs remain bit-identical, including semantic-cache invalidation and original atom/edge restoration. Two actual spawned worker replies passed parity. Representative message decode fell from1.13-1.88ms to0.62-0.85ms,1.8-2.3x faster; this is isolated CPU decode, not end-to-end training speed. Evidence ipc-cpu-equivalence.log (21.4s), ipc-payload-report.json. Candidate /mnt/local/gakumas/deploy-v6-credit-ipc-next.
2. Confirmed redundant startup best-of-4 evaluation: fresh baseline already calls construction_evaluation with identical fixed seeds, but did not establish best4-reference; boundary then repeats the whole evaluation. Fresh-run code now calls best4_check on the already computed initial baseline. Existing resumed-run fallback remains. Initial/boundary suites cost roughly4-5minutes each in the live run. This reuses the same quality evaluation instead of removing it. Syntax and control flow reviewed; not exercised in a new production startup because the user requested avoiding another expensive run.

Do not alter live deployment while its frozen-policy run is active. Retain these follow-up changes as the next revision, and adopt at a clean checkpoint/explicit migration boundary. Initial production startup also spends about5min on rank0-only keycard development diagnostics; potential later sharding target, not changed here. Baseline quality gates remain intact.
