#!/usr/bin/env bash
echo "=== whole box (192 cores) ==="
top -bn2 -d 2 | grep "^%Cpu" | tail -1
echo -n "load avg: "; cat /proc/loadavg | cut -d' ' -f1-3
echo
echo "=== who is using it (sum of %CPU by role) ==="
ps -eo pcpu,comm,args --no-headers | awk '
  /exam-search\/train.py/ {rank+=$1; nr++; next}
  /multiprocessing.spawn/ {sp+=$1; nsp++; if($1>20) busy++; next}
  /search_worker.mjs/    {node+=$1; nn++; if($1>20) nbusy++; next}
  /node/                 {other_node+=$1; non++; next}
  END {
    printf "  8 rank mains        : %6.0f%%  (%d procs, %.0f%% each)\n", rank, nr, rank/nr
    printf "  search+arena python : %6.0f%%  (%d procs, %d above 20%%)\n", sp, nsp, busy
    printf "  node search workers : %6.0f%%  (%d procs, %d above 20%%)\n", node, nn, nbusy
    printf "  other node          : %6.0f%%  (%d procs)\n", other_node, non
    printf "  TOTAL               : %6.0f%%  = %.0f cores of 192\n", rank+sp+node+other_node, (rank+sp+node+other_node)/100
  }'
echo
echo "=== search processes: running vs waiting ==="
n=0; run=0; slp=0
for p in $(pgrep -f multiprocessing.spawn | head -400); do
  st=$(awk '{print $3}' /proc/$p/stat 2>/dev/null)
  n=$((n+1)); [ "$st" = "R" ] && run=$((run+1)) || slp=$((slp+1))
done
echo "  sampled $n: RUNNING=$run  SLEEPING/WAITING=$slp"
echo
echo "=== stage ==="; grep '\[PROGRESS\]' /mnt/local/gakumas/logs/prod-v3.log | tail -1 | cut -c1-110
