#!/usr/bin/env bash
# Keep the dashboard alive and pointed at the run the TRAINER is actually writing.
#
# The old supervisor picked the newest directory by mtime, and nothing restarted it
# after a container-wide pkill, so the dashboard sat on runs/smoke2 for hours while
# training wrote to prod-v3. Reading --output off the live trainer command line is
# exact: it cannot drift to a stale directory, and it follows every relaunch.
cd /mnt/local/gakumas/deploy && source .venv/bin/activate
PORT="${PORT:-8900}"
STATE=/mnt/local/gakumas/logs/.dash_run

target() {
  # rank 0's command line carries the authoritative --output path
  local line
  line=$(ps -eo args | grep '[e]xam-search/train.py' | head -1)
  if [ -n "$line" ]; then
    echo "$line" | sed -n 's/.*--output \([^ ]*\).*/\1/p'
    return
  fi
  # no trainer running: fall back to the most recently written run
  local newest
  newest=$(ls -1dt /mnt/local/gakumas/runs/*/ 2>/dev/null | head -1)
  echo "${newest%/}"
}

while true; do
  RUN=$(target)
  if [ -n "$RUN" ] && [ -d "$RUN" ]; then
    CUR=$(cat "$STATE" 2>/dev/null)
    UP=$(pgrep -f "[d]ashboard/server.py" | head -1)
    if [ -z "$UP" ] || [ "$CUR" != "$RUN" ]; then
      [ -n "$UP" ] && { echo "[$(date +%H:%M:%S)] target -> $RUN, restarting"; pkill -f "[d]ashboard/server.py"; sleep 3; }
      echo "[$(date +%H:%M:%S)] dashboard on $RUN"
      setsid nohup python dashboard/server.py --run "$RUN" --port "$PORT" \
        >> /mnt/local/gakumas/logs/dashboard.log 2>&1 < /dev/null &
      echo "$RUN" > "$STATE"
      sleep 6
    fi
  fi
  sleep 15
done
