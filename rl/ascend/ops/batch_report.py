#!/usr/bin/env python3
"""After a batch commits: where the time went, and whether the improvement loop is
turning. Reads metrics.jsonl (one row per committed batch) and the progress log.

Usage: batch_report.py <run_dir> <log>
"""
import json, re, sys
from pathlib import Path
from collections import OrderedDict

run, log = Path(sys.argv[1]), Path(sys.argv[2])

# ---- per-stage wall clock from the [PROGRESS] lines -----------------------
pat = re.compile(r'\[PROGRESS\] batch=(\d+) stage=(\S+)\s+\w+ ([\d.]+)/(\d+).*elapsed ([\d.]+)m')
peak, order = {}, OrderedDict()
for line in log.read_text(encoding='utf-8', errors='replace').splitlines():
    m = pat.search(line)
    if not m:
        continue
    k = (int(m.group(1)), m.group(2))
    order.setdefault(k, None)
    el, done, total = float(m.group(5)), float(m.group(3)), int(m.group(4))
    cur = peak.get(k, (0., 0., 0))
    peak[k] = (max(cur[0], el), max(cur[1], done), total)
print('=== per-stage wall clock (max over ranks) ===')
tot = {}
for k in order:
    el, done, total = peak[k]
    print('  batch %-3s %-18s %6.1f min   %s/%s' % (k[0], k[1], el, int(done), total))
    tot[k[0]] = tot.get(k[0], 0.) + el
for b, v in sorted(tot.items()):
    print('  batch %s stages sum: %.1f min' % (b, v))

# ---- the improvement-loop signals from metrics.jsonl ----------------------
m = run / 'metrics.jsonl'
if not m.exists():
    print('\n(no metrics.jsonl yet: no batch has committed)')
    sys.exit()
rows = [json.loads(l) for l in m.read_text(encoding='utf-8', errors='replace').splitlines() if l.strip()]
print('\n=== committed batches: %d ===' % len(rows))
for r in rows:
    print('\n--- batch %s ---' % r['batch'])
    print('  time      : collect %.1f min, update %.1f min' % (r.get('collection_seconds', 0)/60, r.get('update_seconds', 0)/60))
    print('  real actions: ppo=%s actor_search=%s  (actor-search share %.1f%%)' % (
        r.get('ppo_records'), r.get('search_records'),
        100. * (r.get('search_records') or 0) / max(1, (r.get('ppo_records') or 0) + (r.get('search_records') or 0))))
    sb = (r.get('search_batch') or {}).get('counts', {})
    att, acc = sb.get('attempted_roots', 0), sb.get('accepted_targets', 0)
    print('  router roots: attempted=%s budget_admitted=%s (%.1f%%)  [main router only; not extrapolated to other ranks]  statuses=%s' % (
        att, acc, 100. * acc / max(1, att),
        {k.split(':', 1)[1]: v for k, v in sb.items() if k.startswith('status:')}))
    sl = r.get('search_learning') or {}
    auxiliary = r.get('auxiliary_search') or {}
    if auxiliary or r.get('auxiliary_search_roots'):
        print('  auxiliary : global_raw_roots=%s quality_labels=%s positive_weight_labels=%s rejected_roots=%s' % (
            r.get('auxiliary_search_roots',0), r.get('auxiliary_search_records',0),
            auxiliary.get('weighted_roots',0), auxiliary.get('rejected_roots',0)))
        print('     Additional CE on the same real PPO records; not additional real actions. Reasons: %s' %
              auxiliary.get('rejected_reasons',{}))
    print('  SEARCH GAIN over prior (finite-search diagnostic, not independent improvement validation):')
    print('     mean_estimated_gain=%.4f  weighted_roots=%s/%s  mean_weight=%.3f' % (
        sl.get('mean_estimated_gain', 0), sl.get('weighted_roots'), sl.get('roots'), sl.get('mean_weight', 0)))
    print('     target entropy=%.3f  prior entropy=%.3f  behavior entropy=%.3f' % (
        sl.get('mean_target_entropy', 0), sl.get('mean_prior_entropy', 0), sl.get('mean_behavior_entropy', 0)))
    print('  PPO       : kl=%.4f stop=%s epochs=%s/%s steps=%s grad_norm=%.3f clip_frac=%.3f' % (
        r.get('kl', 0), r.get('ppo_stop_reason'), r.get('epochs_attempted'), r.get('epochs_max'),
        r.get('optimizer_steps'), r.get('grad_norm', 0), r.get('clip_fraction', 0)))
    print('  losses    : policy=%.4f value=%.4f search=%.4f dist=%.4f entropy_bonus=%.4f' % (
        r.get('policy_loss', 0), r.get('value_loss', 0), r.get('search_loss', 0),
        r.get('distribution_loss', 0), r.get('entropy_bonus', 0)))
    print('  train     : normalized_mean=%.4f raw_mean=%.0f' % (r.get('train_normalized_mean', 0), r.get('train_mean', 0)))
    ex = r.get('exploration_stats') or {}
    print('  EXPLORATION (behavior entropy fraction / max prob; collapse = entropy->0, max_p->1):')
    for phase in ('exam', 'draft', 'guidance', 'drink', 'memory'):
        e = ex.get(phase) or {}
        print('     %-9s entropy=%.3f  max_p=%.3f' % (phase, e.get('behavior_entropy_fraction', 0), e.get('behavior_max_probability', 0)))
    sc = r.get('signed_credit') or {}
    g = (sc.get('groups') or {}).get('all_exam') or {}
    if g:
        print('  signed credit (exam): +%s / -%s / 0:%s of %s' % (g.get('positive'), g.get('negative'), g.get('zero'), g.get('records')))

# ---- validation trajectory ------------------------------------------------
print('\n=== VALIDATION INDEX (best-of-4 vs baseline; should rise) ===')
for name in ('best4-validation-history.jsonl', 'play-validation-history.jsonl'):
    p = run / name
    if not p.exists():
        continue
    print('  ' + name)
    for l in p.read_text(encoding='utf-8', errors='replace').splitlines()[-6:]:
        try:
            v = json.loads(l)
        except Exception:
            continue
        keys = [k for k in ('batch', 'index', 'validation_index', 'normalized_mean', 'mean', 'normalized_macro_best', 'label') if k in v]
        print('     ' + '  '.join('%s=%s' % (k, round(v[k], 4) if isinstance(v[k], float) else v[k]) for k in keys))

# ---- per-profile ABSOLUTE validation scores -----------------------------------------
# The validation index is a geometric mean of ratios to the initial policy, so a profile
# whose ceiling is 3x its start and one whose ceiling is 5x its start look the same at
# +10%. Show the raw means so progress can be read against each profile's own range.
print('\n=== PER-PROFILE ABSOLUTE VALIDATION SCORE (raw mean; each profile has its own ceiling) ===')
vfiles = [p for p in run.glob('validation-*.json') if not p.name.endswith('-repeats.json')]
rows = []
for p in sorted(vfiles, key=lambda q: q.stat().st_mtime):
    try:
        v = json.loads(p.read_text(encoding='utf-8', errors='replace'))
    except Exception:
        continue
    prof = v.get('profiles') or v.get('profile_scores') or {}
    scores = {k: (x.get('mean') if isinstance(x, dict) else x) for k, x in prof.items()}
    if scores:
        rows.append((p.stem.replace('validation-', ''), scores))
if rows:
    profiles = sorted(set().union(*[set(r[1]) for r in rows]))
    print('  %-22s' % 'validation' + ''.join('%13s' % q[:12] for q in profiles))
    for name, scores in rows:
        print('  %-22s' % name[:22] + ''.join('%13s' % ('%.0f' % scores[q] if scores.get(q) is not None else '-') for q in profiles))
    first, last = rows[0][1], rows[-1][1]
    print('  %-22s' % 'delta first->last' + ''.join(
        '%13s' % ('%+.0f' % (last[q] - first[q]) if last.get(q) is not None and first.get(q) is not None else '-') for q in profiles))
    print('  %-22s' % 'ratio last/first' + ''.join(
        '%13s' % ('%.3f' % (last[q] / first[q]) if last.get(q) and first.get(q) else '-') for q in profiles))
else:
    print('  (no validation-*.json with per-profile means found)')
