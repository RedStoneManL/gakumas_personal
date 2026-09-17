#!/usr/bin/env bash
pkill -KILL -f '[e]xam-search/train.py' 2>/dev/null
pkill -KILL -f '[s]earch_worker.mjs' 2>/dev/null
sleep 6
cd /mnt/local/gakumas/deploy && source .venv/bin/activate
RUN=/mnt/local/gakumas/runs/prod-v3
rm -rf "$RUN"
export OMP_NUM_THREADS=2
setsid nohup torchrun --standalone --nnodes=1 --nproc-per-node=8 --max-restarts=0 \
  exam-search/train.py --config /mnt/local/gakumas/configs/prod/search.json \
  --initial checkpoints/latest.pt --output "$RUN" \
  > /mnt/local/gakumas/logs/prod-v3.log 2>&1 < /dev/null &
echo "launched pid=$! run=$RUN"
