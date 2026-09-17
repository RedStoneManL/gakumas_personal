#!/usr/bin/env python3
"""Do simulations reach a REAL terminal score, or do they bootstrap off the value head?

leaf() walks a greedy rollout up to `rollout_steps` and only then falls back to the
value head. Shortening rollout_steps makes roots cheaper but trades real terminal
returns for network estimates -- the opposite of what we want the labels built on.
"""
import json, sys
from pathlib import Path
def pct(xs,p):
    if not xs: return float('nan')
    xs=sorted(xs); return xs[max(0,min(len(xs)-1,int(round(p*(len(xs)-1)))))]
for run in sys.argv[1:]:
    p=Path(run)/'search-roots.jsonl'
    if not p.exists(): continue
    term=[]; boot=[]; tot=[]; n=0
    for line in p.open(encoding='utf-8',errors='replace'):
        try: r=json.loads(line)
        except Exception: continue
        s=r.get('search')
        if not s: continue
        c=s.get('cost') or {}
        t=c.get('terminal_evaluations',0); b=c.get('bootstrap_evaluations',0)
        if t+b==0: continue
        n+=1; term.append(t); boot.append(b); tot.append(t+b)
    if not n: print('%-16s no completed searches yet'%Path(run).name); continue
    st,sb=sum(term),sum(boot)
    print('%-16s roots=%d' % (Path(run).name, n))
    print('   real terminal scores : %7d  (%.1f%%)' % (st, 100.*st/(st+sb)))
    print('   value-head bootstrap : %7d  (%.1f%%)' % (sb, 100.*sb/(st+sb)))
    print('   per root: terminals p50=%s  bootstraps p50=%s' % (pct(term,.5), pct(boot,.5)))
