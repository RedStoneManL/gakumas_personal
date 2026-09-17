#!/usr/bin/env python3
"""How the decision counter actually grows over wall-clock, for ONE rank.

Each rank logs a 'rollout' JSON event every ~30s with its own meaningful_decisions
count, its start_seed (which identifies the rank), and how many episodes are live.
Plot the deltas: a smooth process gives even deltas; episodes frozen on a 300s search
give stalls followed by bursts when a wave of searches expires together.
"""
import json, re, sys
from collections import defaultdict

log = sys.argv[1]
by_rank = defaultdict(list)
for line in open(log, encoding='utf-8', errors='replace'):
    if '"event": "rollout"' not in line or '"target_kind": "decisions"' not in line:
        continue
    try:
        r = json.loads(line[line.find('{'):])
    except Exception:
        continue
    by_rank[r['start_seed']].append((r['elapsed_minutes'], r['meaningful_decisions'], r['active'], r['completed']))

ranks = sorted(by_rank)
if not ranks:
    print('no collect rollout events yet'); sys.exit()
seed = ranks[0]
rows = by_rank[seed]
print('rank with start_seed=%s: %d samples over %.1f min' % (seed, len(rows), rows[-1][0]))
print()
print('  %7s %9s %8s %7s %6s  %s' % ('t(min)', 'decisions', 'delta', 'rate/m', 'live', 'bar (delta)'))
prev_t, prev_d = rows[0][0], rows[0][1]
stalls = bursts = 0
deltas = []
for t, d, live, done in rows:
    dt = t - prev_t
    dd = d - prev_d
    rate = dd / dt if dt > 0 else 0
    deltas.append(dd)
    bar = '#' * min(60, dd // 2)
    flag = ''
    if dt > 0.3 and dd == 0:
        flag = '  <- STALL'; stalls += 1
    elif dd >= 40:
        flag = '  <- BURST'; bursts += 1
    print('  %7.1f %9d %8d %7.0f %6d  %s%s' % (t, d, dd, rate, live, bar, flag))
    prev_t, prev_d = t, d
nz = [x for x in deltas if x]
print()
print('samples=%d  zero-growth samples=%d (%.0f%%)  stalls=%d  bursts=%d' % (
    len(deltas), deltas.count(0), 100. * deltas.count(0) / max(1, len(deltas)), stalls, bursts))
if nz:
    nz.sort()
    print('non-zero deltas: p50=%d p90=%d max=%d' % (nz[len(nz)//2], nz[9*len(nz)//10], nz[-1]))
