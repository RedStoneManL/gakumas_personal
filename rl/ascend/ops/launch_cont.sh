#!/usr/bin/env bash
# Versioned continuation prod-v3 -> prod-v4 with the rank-local-records code.
#
# Run ONLY after the source trainer has exited on its own (stop-after-batch.json ->
# final evaluation -> status=complete). The frozen-source hash changes the moment the
# patched files land in deploy/, and unchanged() would kill a live run at its next
# checkpoint, so step 1 is a hard gate, not a courtesy.
#
# What carries over (continuation.stage / prepare): weights, Adam moments, RNG, the
# sample bank, coverage rows, fork seed counter, batch/decision counters, validation
# history and the original baseline. What changes: the code, and search.seconds
# 300 -> 400 (in the continuation's permitted set; audited by the same-feature branch).
set -eu
G=/mnt/local/gakumas; D=$G/deploy; S=$G/scripts/stage4
SRC=$G/runs/prod-v3; OUT=$G/runs/prod-v4; CFG=$G/configs/prod/search-v4.json
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

echo "=== 2. deploy the patched files (frozen-source hash changes now) ==="
# keep the prod-v3 code for rollback (re-continue from prod-v3 with these restored)
B=$G/scripts/prod-v3-code
if [ -d "$B" ]; then echo "  backup $B already exists (from the first attempt); not overwriting"; else
  mkdir -p "$B"
  for f in ppo critic_completion practice distributed runner bank_rollout continuation; do
    cp "$D/exam-search/draftrl/$f.py" "$B/$f.py"; done
  cp "$D/exam-search/train.py" "$B/train.py"; echo "  prod-v3 code backed up to $B"
fi
for f in sharded ppo critic_completion practice distributed runner bank_rollout continuation; do
  cp "$S/$f.py" "$D/exam-search/draftrl/$f.py"; done
cp "$S/train.py" "$D/exam-search/train.py"
md5sum "$D"/exam-search/draftrl/{sharded,ppo,distributed,runner,continuation}.py "$D/exam-search/train.py" | cut -c1-10,33- | sed "s#$D/exam-search/##"

echo "=== 3. continuation config: source config + search.seconds 300 -> 400 ==="
python3 - <<PY
import json
c = json.load(open("$G/configs/prod/search.json", encoding="utf-8-sig"))
c["search"]["seconds"] = 400.0
json.dump(c, open("$CFG", "w", newline="\n"), indent=2)
print("  seconds:", c["search"]["seconds"], " parallel_roots:", c["parallelism"]["parallel_roots"], " workers:", c["parallelism"]["workers"])
PY

echo "=== 4. launch ==="
export OMP_NUM_THREADS=2
setsid nohup torchrun --standalone --nnodes=1 --nproc-per-node=8 --max-restarts=0 \
  exam-search/train.py --config "$CFG" --continue-from "$SRC" --output "$OUT" \
  > $G/logs/prod-v4.log 2>&1 < /dev/null &
echo "  launched pid=$! -> $OUT  log=$G/logs/prod-v4.log"
