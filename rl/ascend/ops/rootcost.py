#!/usr/bin/env python3
"""Where does a root's wall-clock go? Correlate elapsed_seconds against the cost counters."""
import json, sys, statistics
from pathlib import Path
from collections import Counter
def pct(xs,p):
    if not xs: return float('nan')
    xs=sorted(xs); return xs[max(0,min(len(xs)-1,int(round(p*(len(xs)-1)))))]
for run in sys.argv[1:]:
    p=Path(run)/'search-roots.jsonl'
    if not p.exists(): print(run,'no search-roots.jsonl'); continue
    print('#'*12, Path(run).name)
    ok=[]; dead=[]; n=0
    with p.open(encoding='utf-8',errors='replace') as f:
        for line in f:
            try: r=json.loads(line)
            except Exception: continue
            n+=1
            s=r.get('search'); c=(s or {}).get('cost') or {}
            row={'el':r.get('elapsed_seconds',0.),'status':r.get('status'),
                 'ev':c.get('policy_evaluations'),'ws':c.get('world_steps'),
                 'worlds':c.get('worlds'),'term':c.get('terminal_evaluations'),
                 'acts':len((s or {}).get('actions') or []) or r.get('action_count'),
                 'sampling_ms':(r.get('sampling') or {}).get('cost',{}).get('milliseconds')}
            (ok if r.get('status')=='ok' else dead).append(row)
    print('roots=%d ok=%d failed=%d'%(n,len(ok),len(dead)))
    if ok:
        el=[r['el'] for r in ok]; ev=[r['ev'] for r in ok if r['ev'] is not None]
        ws=[r['ws'] for r in ok if r['ws'] is not None]; ac=[r['acts'] for r in ok if r['acts']]
        print('  OK roots  elapsed p50=%.1fs p90=%.1fs'%(pct(el,.5),pct(el,.9)))
        print('            policy_evaluations p50=%s p90=%s max=%s'%(pct(ev,.5),pct(ev,.9),max(ev) if ev else '-'))
        print('            world_steps        p50=%s p90=%s max=%s'%(pct(ws,.5),pct(ws,.9),max(ws) if ws else '-'))
        print('            actions at root    p50=%s p90=%s max=%s'%(pct(ac,.5),pct(ac,.9),max(ac) if ac else '-'))
        # per-unit wall clock: how long ONE sequential step actually costs
        per=[r['el']/max(1,(r['ev'] or 0)+(r['ws'] or 0)) for r in ok if r['ev'] is not None]
        print('            seconds per sequential step (eval+worldstep): p50=%.3f p90=%.3f'%(pct(per,.5),pct(per,.9)))
    if dead:
        print('  FAILED roots by status:')
        for st,c in Counter(r['status'] for r in dead).most_common():
            el=[r['el'] for r in dead if r['status']==st]
            ac=[r['acts'] for r in dead if r['status']==st and r['acts']]
            print('    %-26s n=%-6d elapsed p50=%5.1fs   actions p50=%s'%(st,c,pct(el,.5),pct(ac,.5) if ac else '-'))
