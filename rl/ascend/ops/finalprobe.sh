#!/usr/bin/env bash
R=/mnt/local/gakumas/runs/prod-v3/search-roots.jsonl
L=/mnt/local/gakumas/logs/prod-v3.log
grep '\[PROGRESS\]' $L | tail -1
echo -n "roots: "; if [ -f $R ]; then wc -l < $R; else echo "0 (collection not started)"; exit 0; fi
python3 - "$R" <<'PY'
import json,sys
from collections import Counter
c=Counter(); el={}; term=0; boot=0; sims=[]; trunc=0; disc=[]
for line in open(sys.argv[1],encoding='utf-8',errors='replace'):
    try: r=json.loads(line)
    except Exception: continue
    st=r.get('status'); c[st]+=1; el.setdefault(st,[]).append(r.get('elapsed_seconds',0.))
    s=r.get('search')
    if s:
        cost=s.get('cost') or {}
        term+=cost.get('terminal_evaluations',0); boot+=cost.get('bootstrap_evaluations',0)
        sims.append(s.get('simulations_completed', s.get('cost',{}).get('worlds',0)))
        disc.append(cost.get('discarded_unterminated',0))
        if s.get('truncated_reason'): trunc+=1
n=sum(c.values())
for st,k in c.most_common():
    e=sorted(el[st]); print('  %-26s %5d  %5.1f%%  elapsed p50=%5.1fs'%(st,k,100.*k/n,e[len(e)//2]))
ok=c.get('ok',0)+c.get('ok_truncated',0)
print('  ACCEPTANCE: %.1f%%   (was 0.0%% at 60s/rollout8, 48.0%% at 60s/rollout2)'%(100.*ok/n))
if term+boot:
    print('  LABEL GROUNDING: %.1f%% real terminal scores, %.1f%% value-head (want ~99%%)'%(
        100.*term/(term+boot), 100.*boot/(term+boot)))
if sims:
    v=sorted(sims); print('  simulations completed per root: p50=%d p10=%d (of 64); %d roots salvaged by partial credit'%(
        v[len(v)//2], v[len(v)//10], trunc))
PY
