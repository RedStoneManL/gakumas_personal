#!/usr/bin/env bash
# Who owns the zombies, and are they still accumulating?
echo "=== zombies by parent (top 6) ==="
ps -eo ppid,stat,comm --no-headers | awk '$2 ~ /^Z/ {print $1, $3}' | sort | uniq -c | sort -rn | head -6
echo "=== zombies by parent liveness ==="
ps -eo ppid,stat --no-headers | awk '$2 ~ /^Z/ {print $1}' | sort -u | while read -r p; do
  if [ "$p" = 1 ]; then echo init; elif kill -0 "$p" 2>/dev/null; then echo live_parent; else echo dead_parent; fi
done | sort | uniq -c
echo "=== zombie comm ==="
ps -eo stat,comm --no-headers | awk '$1 ~ /^Z/ {print $2}' | sort | uniq -c | sort -rn | head -4
echo "=== counts ==="
echo "zombies=$(ps -eo stat --no-headers | grep -c '^Z')  procs=$(ps -e --no-headers | wc -l)  pids.current=$(cat /sys/fs/cgroup/pids.current 2>/dev/null)  $(date +%H:%M:%S)"
