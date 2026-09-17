#!/usr/bin/env bash
# One picture of where the work is, from four angles, at this instant.
source /mnt/local/gakumas/deploy/.venv/bin/activate
L=/mnt/local/gakumas/logs/prod-v3.log
echo "=== stage ==="; grep '\[PROGRESS\]' $L | tail -1 | cut -c1-120
echo; echo "=== 1. CPU: who is busy ==="
top -bn2 -d 2 | grep "^%Cpu" | tail -1
ps -eo pcpu,args --no-headers | awk '
  /exam-search\/train.py/ {r+=$1; nr++; next}
  /multiprocessing.spawn/  {s+=$1; ns++; next}
  /search_worker.mjs/      {n+=$1; nn++; next}
  END{printf "  collectors %4.0f%% (%d)   search procs %5.0f%% (%d, %.0f%% each)   node %5.0f%% (%d)   = %.0f cores\n", r,nr,s,ns,s/ns,n,nn,(r+s+n)/100}'
echo; echo "=== 2. one collector thread: where its time goes (15s) ==="
P=$(ps -eo pid,args --sort=pid | grep '[e]xam-search/train.py' | sed -n 3p | awk '{print $1}')
py-spy record --pid "$P" --duration 15 --rate 200 --format raw --output /tmp/w.raw >/dev/null 2>&1
TOT=$(awk '{s+=$NF} END{print s}' /tmp/w.raw)
awk -v t="$TOT" '{n=$NF; l=$0; sub(/ [0-9]+$/,"",l); k=split(l,a,";"); delete seen; for(i=1;i<=k;i++){f=a[i]; if(!(f in seen)){c[f]+=n; seen[f]=1}}} END{for(f in c) printf "%6.1f%%  %s\n", c[f]*100/t, f}' /tmp/w.raw | sort -rn | grep -E "pump |merge|collate |choose |search_forward|learning_forward|queues.py|get \(|poll |receive|flatten|encode " | head -10
echo; echo "=== 3. search processes: what are they waiting on ==="
: > /tmp/cls
for k in $(pgrep -P "$P" | head -60); do
  grep -aq multiprocessing /proc/$k/cmdline 2>/dev/null || continue
  S=$(py-spy dump --pid "$k" 2>/dev/null | grep -E '^\s+\S+ \(' | head -3 | tr '\n' '|')
  case "$S" in
    *_predict*)          echo "waiting_for_collector_inference" ;;
    *sample_public*|*_submit*|*clone*|*observe*|*step*) echo "in_node_arena_call" ;;
    *_process_worker*|*_recv*) echo "idle_no_root_assigned" ;;
    *) echo "other: $(echo "$S" | cut -c1-60)" ;;
  esac >> /tmp/cls
done
sort /tmp/cls | uniq -c | sort -rn
echo; echo "=== 4. roots so far ==="
bash /mnt/local/gakumas/scripts/finalprobe.sh 2>&1 | grep -E "roots:|ACCEPTANCE|GROUNDING|simulations per root" 
