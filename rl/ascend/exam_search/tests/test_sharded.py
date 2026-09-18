#!/usr/bin/env python3
"""sharded.py against the single-learner reference, with K ranks simulated as threads.

A FakeMesh gives each thread a rank view; every collective (sum_values, gather_lists)
is a barrier exchange, so a rank that makes one collective call more or fewer than the
others deadlocks the test instead of silently passing -- exactly the property the real
job depends on. Reductions are done in float32 like the real Gloo/HCCL path.

  T1  sharded.profile_weights(mesh=None) is bit-identical to practice.profile_weights
  T2  K-way sharded.profile_weights == single-rank reference on the concatenation
      (advantages rescaled in place, policy/value weights) to float32 tolerance
  T3  block_plan: same num_blocks on every rank; each rank's blocks partition its own
      records into near-equal chunks (<= ceil(eff/K)); sum of block_length == n_global;
      every rank with >= num_blocks records is present in EVERY block (no ragged tail)
  T4  search_totals and reduce_nested sum correctly across ranks with disjoint keys
  T5  a rank with far fewer records still completes (empty tail blocks)
"""
import os, sys, math, random, threading, importlib.util, types
from pathlib import Path
import torch

ROOT = Path(os.environ.get('GK_EXAM', str(Path(__file__).resolve().parents[1])))
sys.path[:0] = [str(ROOT), str(ROOT / 'runtime/shared'), str(ROOT / 'runtime/arena')]
pkg = types.ModuleType('draftrl'); pkg.__path__ = [str(ROOT / 'draftrl')]; sys.modules['draftrl'] = pkg


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m


sharded = load('draftrl.sharded', os.environ.get('GK_SHARDED', str(ROOT / 'draftrl/sharded.py')))
from draftrl.practice import profile_weights as reference_profile_weights


class Shared:
    def __init__(self, k):
        self.k, self.slots, self.calls = k, [None] * k, 0
        self.barrier = threading.Barrier(k)
        self.lock = threading.Lock()


class RankView:
    """What one thread sees as `mesh`."""
    def __init__(self, shared, rank):
        self.shared, self.rank, self.size, self.device = shared, rank, shared.k, 'cpu'

    def _exchange(self, value):
        s = self.shared
        s.slots[self.rank] = value
        s.barrier.wait(timeout=30)
        snapshot = list(s.slots)
        s.barrier.wait(timeout=30)
        with s.lock:
            s.calls += 1
        return snapshot

    def sum_values(self, values):
        names = sorted(values)
        rows = self._exchange(torch.tensor([float(values[k]) for k in names], dtype=torch.float32))
        total = torch.stack(rows).sum(0)
        return dict(zip(names, total.tolist()))

    def gather_lists(self, values):
        rows = self._exchange(list(values))
        return [item for row in rows for item in row]


PROFILES = ['hiro-hif', 'liliya-xmas', 'saki-hif', 'saki-wild', 'ume-campus']


def make_records(n, seed):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        marginal = rng.random() < 0.6
        out.append({'profile': rng.choice(PROFILES),
                    'loss_weight': rng.choice([1.0, 1.0, 0.25]) if marginal else 1.0,
                    'policy_advantage_kind': 'best_of_k_state_contribution' if marginal else None,
                    'contribution_rms_floor': 0.1 if marginal else 1e-5,
                    'meaningful': rng.random() < 0.85})
    return out


def run_ranks(k, fn):
    """Run fn(rank_view, rank) on k threads; return results in rank order; re-raise."""
    shared = Shared(k); results = [None] * k; errors = [None] * k

    def body(r):
        try:
            results[r] = fn(RankView(shared, r), r)
        except BaseException as e:      # noqa
            errors[r] = e
            try: shared.barrier.abort()
            except Exception: pass

    threads = [threading.Thread(target=body, args=(r,)) for r in range(k)]
    for t in threads: t.start()
    for t in threads: t.join(timeout=120)
    for e in errors:
        if e is not None: raise e
    return results, shared.calls


def close(a, b, tol=2e-5):
    a, b = torch.as_tensor(a, dtype=torch.float64), torch.as_tensor(b, dtype=torch.float64)
    if a.shape != b.shape: return False
    return bool(((a - b).abs() <= tol * (1 + b.abs())).all())


failures = []
def check(name, ok, detail=''):
    print('  %-58s %s %s' % (name, 'ok' if ok else 'FAIL', detail))
    if not ok: failures.append(name)


print('=== T1: mesh=None is bit-identical to practice.profile_weights ===')
recs = make_records(600, 1)
meaningful = torch.tensor([r['meaningful'] for r in recs])
adv0 = torch.randn(600, generator=torch.Generator().manual_seed(1))
a_ref, a_new = adv0.clone(), adv0.clone()
p_ref, v_ref = reference_profile_weights(a_ref, recs, meaningful)
p_new, v_new, profiles, n = sharded.profile_weights(a_new, recs, meaningful, None)
check('advantages identical', torch.equal(a_ref, a_new))
check('policy weights identical', torch.equal(p_ref, p_new))
check('value weights identical', torch.equal(v_ref, v_new))
check('profiles/n', profiles == sorted(set(r['profile'] for r in recs)) and n == 600)

print('\n=== T2: K-way sharded == single-rank reference on the concatenation ===')
for K, sizes in ((2, [400, 200]), (8, [70, 90, 110, 130, 50, 60, 200, 40]), (8, [125] * 8)):
    parts = [make_records(m, 100 + i) for i, m in enumerate(sizes)]
    allrec = [r for part in parts for r in part]
    gen = torch.Generator().manual_seed(7)
    advs = [torch.randn(len(part), generator=gen) for part in parts]
    a_ref = torch.cat(advs).clone()
    mean_ref = torch.tensor([r['meaningful'] for r in allrec])
    p_ref, v_ref = reference_profile_weights(a_ref, allrec, mean_ref)

    def rank_fn(mesh, r):
        a = advs[r].clone()
        m = torch.tensor([x['meaningful'] for x in parts[r]])
        p, v, prof, ntot = sharded.profile_weights(a, parts[r], m, mesh)
        return a, p, v, prof, ntot

    results, calls = run_ranks(K, rank_fn)
    a_cat = torch.cat([x[0] for x in results]); p_cat = torch.cat([x[1] for x in results]); v_cat = torch.cat([x[2] for x in results])
    check('K=%d sizes=%s advantages' % (K, sizes[:3] + (['...'] if K > 3 else [])), close(a_cat, a_ref))
    check('K=%d policy weights' % K, close(p_cat, p_ref))
    check('K=%d value weights' % K, close(v_cat, v_ref))
    check('K=%d every rank agrees on profiles and n' % K,
          all(x[3] == results[0][3] for x in results) and all(x[4] == len(allrec) for x in results))
    check('K=%d collective calls per rank identical' % K, calls % K == 0, '(%d total)' % calls)

print('\n=== T3: block plan lockstep and coverage ===')
for K, sizes, eff in ((8, [700, 690, 720, 650, 710, 705, 698, 300], 1024), (2, [10, 3], 8), (4, [1, 1, 1, 50], 64)):
    def plan_fn(mesh, r):
        bounds, num_blocks, n_global = sharded.block_plan(mesh, sizes[r], eff)
        order = list(range(sizes[r])); random.Random(r).shuffle(order)
        seen, lengths, local = [], [], []
        for b in range(num_blocks):
            s, e = bounds[b]
            block = order[s:e]
            lengths.append(sharded.block_length(mesh, len(block)))
            seen.extend(block); local.append(len(block))
        return len(bounds), num_blocks, n_global, sorted(seen), lengths, local
    results, calls = run_ranks(K, plan_fn)
    per_rank = math.ceil(eff / K)
    num_blocks, n_global = results[0][1:3]
    check('K=%d num_blocks == max ceil(n_r/%d) = %d' % (K, per_rank, num_blocks),
          num_blocks == max(math.ceil(m / per_rank) for m in sizes) and all(x[0] == num_blocks for x in results))
    check('K=%d num_blocks identical on all ranks (%d)' % (K, num_blocks), all(x[1] == num_blocks for x in results))
    check('K=%d n_global == sum(sizes)' % K, all(x[2] == sum(sizes) for x in results))
    check('K=%d each rank covers its own records exactly once' % K, all(x[3] == list(range(sizes[r])) for r, x in enumerate(results)))
    check('K=%d block lengths identical on all ranks' % K, all(x[4] == results[0][4] for x in results))
    check('K=%d sum of global block lengths == n_global' % K, sum(results[0][4]) == sum(sizes))
    check('K=%d no rank chunk exceeds per_rank=%d' % (K, per_rank), all(max(x[5], default=0) <= per_rank for x in results))
    check('K=%d chunks near-equal on every rank (max-min <= 1)' % K, all(max(x[5]) - min(x[5]) <= 1 for x in results if x[5]))
    check('K=%d every rank with >= num_blocks records is in every block' % K,
          all(min(x[5]) >= 1 for r, x in enumerate(results) if sizes[r] >= num_blocks))
    check('K=%d global blocks near-equal (max-min <= K)' % K, max(results[0][4]) - min(results[0][4]) <= K)

b1, nb1, ng1 = sharded.block_plan(None, 1000, 64)
check('mesh=None keeps range(0,n,effective) (16 blocks, tail 40)',
      b1 == [(i * 64, min((i + 1) * 64, 1000)) for i in range(16)] and nb1 == 16 and ng1 == 1000)
b0, nb0, ng0 = sharded.block_plan(None, 0, 64)
check('mesh=None with no records -> no blocks', b0 == [] and nb0 == 0 and ng0 == 0)

print('\n=== T4: search_totals / reduce_nested across disjoint keys ===')
def tot_fn(mesh, r):
    recs = [{'profile': PROFILES[(r + i) % 5], 'loss_weight': 0.25} for i in range(4)]
    searched = torch.tensor([True, False, True, True])
    prof = sharded.gather_union(mesh, [x['profile'] for x in recs])
    st = sharded.search_totals(mesh, recs, searched, prof)
    nested = sharded.reduce_nested(mesh, {'g': {'rank%d' % r: {'x': r + 1, 'y': 2.5}}, 'flat': r})
    return st, nested
results, _ = run_ranks(3, tot_fn)
st0 = results[0][0]
check('search_totals identical on all ranks', all(x[0] == st0 for x in results))
check('search_totals sums 0.25 per searched record', abs(sum(st0.values()) - 3 * 3 * 0.25) < 1e-6, str(st0))
n0 = results[0][1]
check('reduce_nested unions keys and sums leaves',
      n0['flat'] == 3 and set(n0['g']) == {'rank0', 'rank1', 'rank2'} and n0['g']['rank2']['x'] == 3 and n0['g']['rank0']['y'] == 2.5)

print('\n=== T5: reduce_coverage ===')
def cov_fn(mesh, r):
    cov = {'record_count': 10 * (r + 1), 'accepted_unique': 5, 'attempted_unique': 8,
           'accepted_fraction': 0.5, 'groups': {'phase:exam': {'records': 4, 'accepted_unique': 2, 'attempted_unique': 3, 'accepted_fraction': .5},
                                                 'rank%d' % r: {'records': 1, 'accepted_unique': 1, 'attempted_unique': 1, 'accepted_fraction': 1.}},
           'note': 'n'}
    return sharded.reduce_coverage(mesh, cov)
results, _ = run_ranks(2, cov_fn)
c = results[0]
check('coverage totals summed', c['record_count'] == 30 and c['accepted_unique'] == 10)
check('coverage fraction recomputed', abs(c['accepted_fraction'] - 10 / 30) < 1e-9)
check('coverage group union + sums', c['groups']['phase:exam']['records'] == 8 and 'rank1' in c['groups'] and c['groups']['phase:exam']['accepted_fraction'] == 0.5)

print('\n%s' % ('ALL PASSED' if not failures else 'FAILURES: %s' % failures))
sys.exit(1 if failures else 0)
