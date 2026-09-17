#!/usr/bin/env python3
"""Do failed roots do MORE work than successful ones, or are they starved?

`report['cost']` is filled in a finally block, so it survives a failure even though
`report['search']` is None. It counts the Arena client's native work, which is the
part a root actually performed before its deadline expired.
"""
import json, sys
from collections import Counter
from pathlib import Path
def pct(xs,p):
    if not xs: return float('nan')
    xs=sorted(xs); return xs[max(0,min(len(xs)-1,int(round(p*(len(xs)-1)))))]
for run in sys.argv[1:]:
    p=Path(run)/'search-roots.jsonl'
    if not p.exists(): continue
    print('#'*10, Path(run).name)
    by={}
    for line in p.open(encoding='utf-8',errors='replace'):
        try: r=json.loads(line)
        except Exception: continue
        st=r.get('status'); c=r.get('cost') or {}
        by.setdefault(st,[]).append((r.get('elapsed_seconds',0.), c.get('native_actions',0),
                                     c.get('rule_operations',0), (r.get('sampling') or {}).get('cost',{}).get('milliseconds',0)))
    print('  %-26s %6s %10s %12s %12s' % ('status','n','elapsed p50','native_acts p50','rule_ops p50'))
    for st,rows in sorted(by.items(), key=lambda kv:-len(kv[1])):
        print('  %-26s %6d %10.1fs %12.0f %12.0f' % (st, len(rows), pct([r[0] for r in rows],.5),
              pct([r[1] for r in rows],.5), pct([r[2] for r in rows],.5)))
    ok=by.get('ok'); bad=by.get('inference_deadline')
    if ok and bad:
        a=pct([r[1] for r in ok],.5); b=pct([r[1] for r in bad],.5)
        print('\n  VERDICT: failed roots performed %.2fx the native work of successful ones.' % (b/max(1,a)))
        print('  %s' % ('-> they are genuinely doing MORE work than 60s allows'
                        if b > 1.3*a else
                        '-> they are NOT doing more work; they are STARVED waiting for the shared accelerator'))
