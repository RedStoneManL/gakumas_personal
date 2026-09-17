#!/usr/bin/env python3
"""Per-run search root statistics + stage timeline. Usage: search_stats.py <run_dir> [<run_dir>...]"""
import json, sys, statistics
from collections import Counter, defaultdict
from pathlib import Path

def pct(xs, p):
    if not xs: return float('nan')
    xs = sorted(xs); k = max(0, min(len(xs)-1, int(round(p*(len(xs)-1))))); return xs[k]

for run in sys.argv[1:]:
    run = Path(run); print('#'*10, run.name)
    roots = run/'search-roots.jsonl'
    if roots.exists():
        status, elapsed, actions, ok_el, cost = Counter(), defaultdict(list), [], [], defaultdict(list)
        sims_done = []; n = 0; bad = 0; versions = Counter()
        with roots.open(encoding='utf-8', errors='replace') as f:
            for line in f:
                try: r = json.loads(line)
                except Exception: bad += 1; continue
                n += 1; st = r.get('status'); status[st] += 1
                elapsed[st].append(r.get('elapsed_seconds', 0.)); versions[r.get('policy_version')] += 1
                if r.get('action_count') is not None: actions.append(r['action_count'])
                s = r.get('search')
                if s:
                    sims_done.append(sum(s.get('root_visits', [])))
                    actions.append(len(s.get('actions', [])))
                    for k, v in (s.get('cost') or {}).items(): cost[k].append(v)
                    ok_el.append(r.get('elapsed_seconds', 0.))
        print('roots=%d bad_lines=%d versions=%s' % (n, bad, dict(versions)))
        for st, c in status.most_common():
            e = elapsed[st]
            print('  %-28s n=%-6d elapsed p50=%6.1fs p90=%6.1fs max=%6.1fs mean=%6.1fs' % (st, c, pct(e,.5), pct(e,.9), max(e) if e else 0, statistics.fmean(e) if e else 0))
        if actions: print('  action_count p50=%d p90=%d max=%d' % (pct(actions,.5), pct(actions,.9), max(actions)))
        if sims_done: print('  simulations completed (ok roots) p50=%d min=%d' % (pct(sims_done,.5), min(sims_done)))
        for k, v in cost.items(): print('  cost.%-22s p50=%8.0f p90=%8.0f' % (k, pct(v,.5), pct(v,.9)))
    ev = run/'events.jsonl'
    if ev.exists():
        print('--- stage timeline (rollout_ready / bank_rollout_ready / update) ---')
        with ev.open(encoding='utf-8', errors='replace') as f:
            for line in f:
                try: r = json.loads(line)
                except Exception: continue
                e = r.get('event')
                if e in ('rollout_ready', 'bank_rollout_ready'):
                    print('  t=%6.1fm batch=%s %-18s eps=%-5s dec=%-6s took=%sm src=%s' % (r.get('elapsed_minutes',0), r.get('batches'), e, r.get('episodes'), r.get('meaningful_decisions'), r.get('elapsed_minutes_stage', r.get('stage_minutes', '?')), r.get('source','')))
                elif e == 'update':
                    print('  t=%6.1fm batch=%s UPDATE records=%s collect_s=%s update_s=%s' % (r.get('elapsed_minutes',0), r.get('batches'), r.get('records'), r.get('collection_seconds'), r.get('update_seconds')))
        # config snapshot
        with ev.open(encoding='utf-8', errors='replace') as f:
            first = json.loads(f.readline())
        for k in ('batch_decisions', 'workers', 'resource_mode'):
            print('  cfg.%s=%s' % (k, first.get(k)))
    pl = run/'progress.log'
    if pl.exists():
        lines = pl.read_text(encoding='utf-8', errors='replace').splitlines()
        print('--- progress.log: %d lines; distinct events: %s' % (len(lines), Counter(l.split()[1] for l in lines if len(l.split())>1).most_common(12)))
