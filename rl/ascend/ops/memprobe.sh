#!/usr/bin/env bash
echo "=== host memory ==="; free -g | awk 'NR<=2'
echo; echo "=== NPU memory + AICore (npu-smi) ==="
npu-smi info 2>/dev/null | grep -E "^\| [0-9] +[0-9]+ +\| |HBM|AICore|Memory-Usage" | head -12 || echo "(npu-smi unavailable)"
npu-smi info 2>/dev/null | awk '/NPU +Name/{p=1} p' | grep -E "^\|" | head -20
echo; echo "=== rank main RSS (GB) ==="
ps -eo rss,args --no-headers | grep '[e]xam-search/train.py' | awk '{s+=$1; n++} END{printf "  %d procs, total %.1f GB, avg %.1f GB\n", n, s/1048576, s/1048576/n}'
echo "=== search+arena RSS (GB) ==="
ps -eo rss,args --no-headers | grep 'multiprocessing.spawn' | awk '{s+=$1; n++} END{printf "  %d procs, total %.1f GB, avg %.0f MB\n", n, s/1048576, s/1024/n}'
echo "=== node RSS (GB) ==="
ps -eo rss,args --no-headers | grep -E 'node' | awk '{s+=$1; n++} END{printf "  %d procs, total %.1f GB\n", n, s/1048576}'
