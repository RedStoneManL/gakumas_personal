#!/usr/bin/env python3
"""Per-stage wall clock from the [PROGRESS] lines + metrics.jsonl cost breakdown."""
import json, re, sys
from pathlib import Path
from collections import OrderedDict

log = Path(sys.argv[1]); run = Path(sys.argv[2])
pat = re.compile(r'\[PROGRESS\] batch=(\d+) stage=(\S+)\s+(\w+) ([\d.]+)/(\d+).*elapsed ([\d.]+)m')
# per (batch,stage) keep the max elapsed any rank reported = that stage's wall clock
peak, order = {}, OrderedDict()
for line in log.read_text(encoding='utf-8', errors='replace').splitlines():
    m = pat.search(line)
    if not m: continue
    b, stage, kind, done, total, el = m.group(1), m.group(2), m.group(3), float(m.group(4)), int(m.group(5)), float(m.group(6))
    k = (int(b), stage)
    order.setdefault(k, None)
    cur = peak.get(k, (0., 0., 0))
    peak[k] = (max(cur[0], el), max(cur[1], done), total)
print('%-6s %-20s %10s %12s' % ('batch', 'stage', 'wall_min', 'units'))
tot = {}
for k in order:
    el, done, total = peak[k]
    print('%-6s %-20s %10.1f %12s' % (k[0], k[1], el, f'{done:.0f}/{total}'))
    tot[k[0]] = tot.get(k[0], 0.) + el
print('\nsum of sharded-stage wall clock per batch (lower bound, stages are sequential):')
for b, v in sorted(tot.items()): print('  batch %s: %.1f min' % (b, v))

m = run/'metrics.jsonl'
if m.exists():
    print('\n--- metrics.jsonl ---')
    for line in m.read_text(encoding='utf-8', errors='replace').splitlines():
        r = json.loads(line)
        sb = r.get('search_batch', {}).get('counts', {})
        print('batch=%s decisions=%s/%s episodes=%s collect=%.1fm update=%.1fm' % (
            r['batch'], r.get('batch_decisions_actual'), r.get('batch_decisions_target'),
            r.get('episodes'), r.get('collection_seconds',0)/60, r.get('update_seconds',0)/60))
        print('   search roots attempted=%s accepted=%s fallbacks=%s root_seconds=%.0f' % (
            sb.get('attempted_roots'), sb.get('accepted_targets'), sb.get('ppo_fallbacks'), sb.get('root_seconds',0)))
        print('   statuses: %s' % {k.split(':',1)[1]: v for k, v in sb.items() if k.startswith('status:')})
        print('   episode mix: joint=%s fork=%s bank=%s' % (r.get('joint_episode_count'), r.get('fork_episode_count'), r.get('bank_episode_count')))
