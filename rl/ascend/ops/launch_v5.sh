#!/usr/bin/env bash
# Versioned continuation prod-v4 -> prod-v5, per the user: 精神統一 same-name hard cap 2 -> 4
# with the validation lineage KEPT (practice.duplicates.keep_benchmark_history), and the root
# search budget/timeout x1.5 (seconds 400 -> 600, simulations 64 -> 96, sampling_ms 10000 -> 15000).
#
# Run inside the container only after the prod-v4 trainer has exited on its own
# (stop-after-batch.json -> final evaluation -> status=complete): the only code change
# is continuation.py, and deploying it under a live trainer would trip unchanged().
#
# What carries over (continuation.stage / prepare): weights, Adam, RNG, sample bank,
# coverage rows, fork seed counter, counters, validation history and baseline.
set -eu
G=/mnt/local/gakumas; D=$G/deploy; S=$G/scripts/stage4
SRC=$G/runs/prod-v4; OUT=$G/runs/prod-v5; CFG=$G/configs/prod/search-v5.json
cd $D && source .venv/bin/activate

echo "=== 1. source must be complete and its trainer gone ==="
python3 - <<PY
import json, sys
p = json.load(open("$SRC/progress.json", encoding="utf-8"))
print("  status:", p.get("status"), " batches:", p.get("batches"), " trainer_pid:", p.get("trainer_pid"))
sys.exit(0 if p.get("status") == "complete" else 1)
PY
if pgrep -f "[e]xam-search/train.py" >/dev/null; then echo "  trainer still alive; refusing"; exit 1; fi
[ -e "$OUT" ] && { echo "  $OUT already exists; refusing"; exit 1; }

echo "=== 2. deploy continuation.py (the only changed file); keep prod-v4's copy ==="
B=$G/scripts/prod-v4-code
if [ -d "$B" ]; then echo "  backup $B exists; not overwriting"; else
  mkdir -p "$B"; cp "$D/exam-search/draftrl/continuation.py" "$B/continuation.py"; echo "  prod-v4 continuation.py backed up to $B"; fi
cp "$S/continuation.py" "$D/exam-search/draftrl/continuation.py"
md5sum "$D/exam-search/draftrl/continuation.py" | cut -c1-10,33- | sed "s#$D/exam-search/##"

echo "=== 3. config: search-v4.json + 精神統一 cap 4 + keep_benchmark_history ==="
python3 - <<PY
import json
c = json.load(open("$G/configs/prod/search-v4.json", encoding="utf-8-sig"))
d = c["practice"]["duplicates"]
name = "精神統一"          # 精神統一 (family also covers 精神統一+)
assert d["max_same_name_overrides"].get(name) == 2, d["max_same_name_overrides"]
d["max_same_name_overrides"][name] = 4
d["keep_benchmark_history"] = True
# user 2026-09-17: search budget and timeout x1.5 so long (ume-campus) roots can finish
s = c["search"]
assert (s["seconds"], s["simulations"], s["sampling_ms"]) == (400.0, 64, 10000), s
s["seconds"], s["simulations"], s["sampling_ms"] = 600.0, 96, 15000
json.dump(c, open("$CFG", "w", encoding="utf-8", newline="\n"), indent=2, ensure_ascii=False)
print("  duplicates:", json.dumps(d, ensure_ascii=False))
print("  search: seconds", c["search"]["seconds"], "simulations", c["search"]["simulations"], "sampling_ms", c["search"]["sampling_ms"], " parallel_roots:", c["parallelism"]["parallel_roots"])
PY

echo "=== 4. launch ==="
export OMP_NUM_THREADS=2
setsid nohup torchrun --standalone --nnodes=1 --nproc-per-node=8 --max-restarts=0 \
  exam-search/train.py --config "$CFG" --continue-from "$SRC" --output "$OUT" \
  > $G/logs/prod-v5.log 2>&1 < /dev/null &
echo "  launched pid=$! -> $OUT  log=$G/logs/prod-v5.log"
