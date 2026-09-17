#!/usr/bin/env python3
"""How far must a rollout run to actually finish an exam from a mid-game root?

A simulation only yields a real terminal score if tree depth + rollout steps covers the
turns remaining in the exam. Measure the real exam lengths, then size rollout_steps so
the rollout can play the game out instead of handing back a value-head estimate.
"""
import json, sys
from pathlib import Path
def pct(xs,p):
    xs=sorted(xs); return xs[max(0,min(len(xs)-1,int(round(p*(len(xs)-1)))))]
lens=[]
for run in sys.argv[1:]:
    p=Path(run)/'train-episodes.jsonl'
    if not p.exists(): continue
    with p.open(encoding='utf-8',errors='replace') as f:
        for line in f:
            try: r=json.loads(line)
            except Exception: continue
            n=len(r.get('submissions') or [])
            if n: lens.append(n)
if not lens:
    print('no episodes logged yet'); sys.exit()
print('exam decisions per episode over %d episodes:' % len(lens))
for q in (.1,.5,.9,.99):
    print('   p%-4s %d' % (int(q*100), pct(lens,q)))
print('   max  %d' % max(lens))
print()
MAXD = 12
print('lookahead needed = exam length - tree depth (max_depth=%d)' % MAXD)
for q,label in ((.5,'median exam'),(.9,'p90 exam'),(.99,'p99 exam'),(1.0,'longest exam')):
    n = max(lens) if q==1.0 else pct(lens,q)
    print('   %-14s %2d decisions -> rollout_steps >= %d to reach a terminal from turn 1'
          % (label, n, max(0, n-MAXD)))
print()
print('leaf() stops the moment it hits a terminal, so rollout_steps is a CAP, not a cost:')
print('a short exam still costs only its own length.')
