"""Single-player public-history MCTS with Gumbel-style root allocation.

Worlds are drawn from an independently supplied conditional root distribution.
The planner never takes a live exam or its seed. The evaluator only receives
public views. Finite search is not an optimal-deck-quality certificate.
"""
import copy
import hashlib
import json
import math
import random
from collections import deque
from dataclasses import dataclass, field
from .best_of import empirical_best
from .value_distribution import mixture_best_of, sample_mean


def key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


@dataclass
class Evaluation:
    actions: list
    priors: list
    value: float
    terminal_return: float | None = None
    return_atoms: list | None = None

    def validate(self):
        if self.return_atoms is not None and (len(self.return_atoms)!=32 or
                any(not math.isfinite(v) for v in self.return_atoms)):
            raise ValueError('Invalid 32-atom return distribution')
        if not math.isfinite(self.value):
            raise ValueError('Nonfinite value')
        if self.terminal_return is not None:
            if not math.isfinite(self.terminal_return) or self.actions:
                raise ValueError('Invalid terminal result')
            return
        if (not self.actions or len(self.actions) != len(self.priors)
                or len({key(a) for a in self.actions}) != len(self.actions)
                or any(not math.isfinite(p) or p < 0 for p in self.priors)
                or not math.isclose(sum(self.priors), 1.0, abs_tol=1e-5)):
            raise ValueError('Invalid public action distribution')


@dataclass
class Node:
    evaluation: Evaluation
    objective_k: int = 1
    visits: list = field(init=False)
    totals: list = field(init=False)
    samples: list = field(init=False)

    def __post_init__(self):
        self.visits = [0] * len(self.evaluation.actions)
        self.totals = [0.] * len(self.visits)
        self.samples = [[] for _ in self.visits]

    def utility(self, index):
        if self.objective_k == 1:
            return self.totals[index]/self.visits[index] if self.visits[index] else self.evaluation.value
        if self.samples[index]:
            return mixture_best_of(self.samples[index],self.objective_k)
        atoms = self.evaluation.return_atoms
        return mixture_best_of([atoms],self.objective_k) if atoms else self.evaluation.value

    def select(self, rng, c_puct):
        # Visit legal options before letting a low prior exclude a key action.
        unseen = [i for i, n in enumerate(self.visits) if not n]
        if unseen:
            best_prior = max(self.evaluation.priors[i] for i in unseen)
            return rng.choice([i for i in unseen if self.evaluation.priors[i] == best_prior])
        q = [self.utility(i) for i in range(len(self.visits))]
        # Values already have an exogenous score scale. Stabilize PUCT's units
        # without clipping or changing the backed-up mean-return objective.
        spread = max(1.0, max(q)-min(q))
        scores = [q[i]/spread + c_puct*self.evaluation.priors[i]
                  * math.sqrt(sum(self.visits)+1)/(1+n)
                  for i, n in enumerate(self.visits)]
        best = max(scores)
        return rng.choice([i for i, v in enumerate(scores) if v == best])


def search(root_view, sample_world, evaluate, *, simulations=64, max_depth=8,
           rollout_steps=64, c_puct=1.5, search_seed=9171,
           root_selection='gumbel_halving', objective_k=1, recoverable=None,
           require_terminal=False,
           soft_floor=.25, soft_temperature=.8, soft_min_visits=2, learning_target=None,
           rollout_temperature=0.):
    """sample_world() returns a fresh compatible hypothetical world.

    A world exposes observe() and step(public_command), and may expose an opaque
    particle_index for diagnostics only. This identity never reaches the public
    tree keys or evaluator. Missing identities remain unknown, not independent.
    evaluate(view) returns Evaluation; terminal_return is the full normalized
    terminal score. Intermediate cumulative scores are not added again.
    max_depth counts policy decisions, including pending choice substeps.
    """
    if (type(simulations) is not int or simulations < 1 or type(max_depth) is not int
            or max_depth < 1 or type(rollout_steps) is not int or rollout_steps < 0
            or not math.isfinite(c_puct) or c_puct <= 0):
        raise ValueError('Invalid search budget')
    if root_selection not in ('puct', 'gumbel_halving', 'soft_budget'):
        raise ValueError('Unknown root selection')
    if (not 0 < soft_floor < 1 or soft_temperature <= 0 or
            type(soft_min_visits) is not int or not 2 <= soft_min_visits <= 8):
        raise ValueError('Invalid soft allocation settings')
    if type(objective_k) is not int or objective_k not in (1,4):
        raise ValueError('Supported search objectives are mean or empirical Best-of-4')
    if (isinstance(rollout_temperature, bool) or
            not isinstance(rollout_temperature, (int, float)) or
            not math.isfinite(rollout_temperature) or rollout_temperature < 0):
        raise ValueError('Rollout temperature must be finite and nonnegative')
    rng = random.Random(search_seed)
    # An opt-in continuation experiment must not consume the tree allocator's
    # random stream. Zero temperature is the exact historical greedy policy.
    rollout_rng = random.Random(search_seed ^ 0x6C656166)
    counters = {'worlds': 0, 'policy_evaluations': 0, 'world_steps': 0,
                'terminal_evaluations': 0, 'bootstrap_evaluations': 0,
                'discarded_unterminated': 0}
    root_signature = key(root_view)
    cache = {}

    def assess(view, *, with_signature=False):
        signature = key(view)
        if signature not in cache:
            value = evaluate(copy.deepcopy(view))
            value.validate()
            cache[signature] = value
            counters['policy_evaluations'] += 1
        return (cache[signature], signature) if with_signature else cache[signature]

    first = assess(root_view)
    if first.terminal_return is not None:
        raise ValueError('Search root is already terminal')
    tree = {root_signature: Node(first,objective_k)}
    root = tree[root_signature]
    root_attempts = [0] * len(first.actions)
    root_sample_groups = [[] for _ in first.actions]
    root_sample_grounded = [[] for _ in first.actions]
    root_sample_path_ids = [[] for _ in first.actions]
    prior_logits = [math.log(max(p, 1e-12)) for p in first.priors]
    gumbels = [-math.log(-math.log(max(1e-12, rng.random()))) for _ in first.actions]
    contenders = sorted(range(len(first.actions)),
                        key=lambda i: gumbels[i]+prior_logits[i], reverse=True)
    rounds_left = max(1, math.ceil(math.log2(len(contenders))))
    root_schedule = deque()
    round_started = False
    debt = [0.] * len(first.actions)

    def soft_probabilities():
        q = [root.utility(i) for i in range(len(root.visits))]
        spread = max(1., max(q)-min(q))
        # Once all actions have evidence, a tiny old policy prior must not
        # outweigh that evidence and starve a newly discovered combination.
        logits = [(v-max(q))/spread/soft_temperature for v in q]
        weights = [math.exp(v-max(logits)) for v in logits]
        return [soft_floor/len(weights)+(1-soft_floor)*v/sum(weights) for v in weights]

    def transformed_q():
        # Gumbel-style root improvement, using sampled mean returns. The
        # exact-value improvement theorem is not claimed for this POMDP adapter.
        q = [root.utility(i) for i in range(len(root.visits))]
        low, high = min([first.value]+q), max([first.value]+q)
        scale = .1 * (50 + max(root.visits))
        return [scale*(v-low)/max(high-low, 1e-8) for v in q]

    def root_ranking(i):
        return gumbels[i] + prior_logits[i] + transformed_q()[i]

    def leaf(world, view, trace):
        # Trace describes the complete public trajectory, regardless of where
        # this search split it between explicit tree decisions and the rollout.
        previous_action = None
        for step in range(rollout_steps + 1):
            current, signature = assess(view, with_signature=True)
            if step > 0:
                trace = key([trace, previous_action, signature])
            if current.terminal_return is not None:
                counters['terminal_evaluations'] += 1
                return current.terminal_return, True, trace
            if step == rollout_steps:
                counters['bootstrap_evaluations'] += 1
                return (tuple(current.return_atoms) if current.return_atoms else current.value), False, trace
            if rollout_temperature == 0:
                action_index = max(range(len(current.actions)), key=lambda i: current.priors[i])
            else:
                # Retain zero policy probabilities and stabilize very small
                # temperatures by subtracting the maximum before division.
                log_priors = [math.log(p) if p > 0 else -math.inf for p in current.priors]
                largest = max(log_priors)
                weights = [math.exp((v-largest)/rollout_temperature) for v in log_priors]
                action_index = rollout_rng.choices(range(len(weights)), weights=weights, k=1)[0]
            action = current.actions[action_index]
            previous_action = action
            view = world.step(copy.deepcopy(action))
            counters['world_steps'] += 1

    truncated = None
    completed = simulations

    def salvageable():
        # Partial credit is only worth taking if the tree can survive everything that
        # still runs after the loop: the admission rule, and the learning-target
        # estimator, which needs two samples per action to form its jackknife.
        if not sum(root.visits):
            return False
        if learning_target is not None and any(len(s) < 2 for s in root.samples):
            return False
        return True
    for simulation in range(simulations):
        forced_root = None
        if root_selection == 'soft_budget':
            if min(root.visits) < soft_min_visits:
                # Successful visits are the evidence threshold, but attempts
                # allocate work. A long unterminated action must not repeatedly
                # win warmup while preventing other actions from being tried.
                missing = [i for i in contenders if root.visits[i] < soft_min_visits]
                forced_root = min(missing, key=lambda i: root_attempts[i])
            else:
                probabilities = soft_probabilities()
                for i,p in enumerate(probabilities): debt[i] += p
                forced_root = max(range(len(debt)),key=lambda i:debt[i])
                debt[forced_root] -= 1.
        elif root_selection == 'gumbel_halving':
            if not root_schedule:
                if round_started:
                    contenders = sorted(contenders, key=root_ranking, reverse=True)[:
                        max(1, math.ceil(len(contenders)/2))]
                    rounds_left = max(1, rounds_left-1)
                remaining = simulations-simulation
                per_action = max(1, remaining//rounds_left//len(contenders))
                root_schedule.extend((contenders*per_action)[:remaining])
                round_started = True
            forced_root = root_schedule.popleft()
        try:
            world = sample_world()
            counters['worlds'] += 1
            view = world.observe()
            if key(view) != root_signature:
                raise ValueError('Sampled world contradicts the public root')
            particle_index = getattr(world, 'particle_index', None)
            if particle_index is not None and type(particle_index) not in (int, str):
                raise ValueError('Particle identity must be an opaque integer/string or None')
            history = root_signature
            trace = root_signature
            path = []
            value = None
            grounded = False
            for depth in range(max_depth):
                node = tree[history]
                action_index = forced_root if depth == 0 and forced_root is not None else node.select(rng, c_puct)
                action = node.evaluation.actions[action_index]
                path.append((node, action_index))
                if depth == 0:
                    root_attempts[action_index] += 1
                view = world.step(copy.deepcopy(action))
                counters['world_steps'] += 1
                # No true-world ID in a node key. Identical public histories share
                # decisions even when their hypothetical hidden decks differ.
                history = key([history, action, view])
                current, signature = assess(view, with_signature=True)
                trace = key([trace, action, signature])
                if current.terminal_return is not None:
                    value = current.terminal_return
                    grounded = True
                    counters['terminal_evaluations'] += 1
                    break
                if history not in tree:
                    tree[history] = Node(current,objective_k)
                    value, grounded, trace = leaf(world, view, trace)
                    break
                if depth + 1 == max_depth:
                    value, grounded, trace = leaf(world, view, trace)
            if value is None or not math.isfinite(sample_mean(value)):
                raise ValueError('Incomplete simulation is not a zero-score sample')
            if require_terminal and not grounded:
                # The rollout never played the game out. Keep it out of the label entirely
                # rather than letting the value head vote on its own target.
                counters['discarded_unterminated'] += 1
            else:
                for node, index in path:
                    node.visits[index] += 1
                    node.totals[index] += sample_mean(value)
                    node.samples[index].append(value)
                root_index = path[0][1]
                root_sample_groups[root_index].append(particle_index)
                root_sample_grounded[root_index].append(grounded)
                root_sample_path_ids[root_index].append(trace)
            # Resident Arena branches must be released before the next simulation.
            # On exceptions their owning adapter retains cleanup responsibility.
            release = getattr(world, 'release', None)
            if release is not None:
                release()
        except Exception as error:
            # A partial tree is still a usable label if it cleared the admission bar;
            # the incomplete simulation contributed no visits, so the tree is coherent.
            if recoverable is None or not recoverable(error) or not salvageable():
                raise
            truncated = error
            completed = simulation
            break

    total = sum(root.visits)
    # Public consumers may pair or cluster these samples. Fail loudly if any
    # provenance field becomes detached from its backed-up return.
    for i, count in enumerate(root.visits):
        assert (count == len(root.samples[i]) == len(root_sample_groups[i])
                == len(root_sample_grounded[i]) == len(root_sample_path_ids[i]))
    root_terminal_counts = [sum(flags) for flags in root_sample_grounded]
    # improve() forms a delete-one jackknife and so needs two samples for every action.
    # With require_terminal a root can finish under that bar, and the ValueError it
    # raises here would escape root_search's budget handlers and kill the search worker.
    supported = learning_target is None or all(len(s) >= 2 for s in root.samples)
    learning = None
    behavior = None
    if root_selection == 'soft_budget':
        policy = soft_probabilities()
        selected = rng.choices(range(len(policy)),weights=policy,k=1)[0]
        behavior = policy[:]
        if learning_target is not None and supported:
            from .search_learning import improve, entropy
            policy, learning = improve(first.priors,root.samples,objective_k,learning_target)
            learning['behavior_entropy'] = entropy(behavior)
    elif root_selection == 'gumbel_halving':
        improved_logits = [p+q for p, q in zip(prior_logits, transformed_q())]
        weights = [math.exp(v-max(improved_logits)) for v in improved_logits]
        policy = [v/sum(weights) for v in weights]
        visited_contenders = [i for i in contenders if root.visits[i]]
        if not visited_contenders:
            # Halving can retire every contender this truncated run actually visited.
            if truncated is not None:
                raise truncated
            raise ValueError('No visited root contender remains')
        selected = max(visited_contenders, key=root_ranking)
    else:
        policy = ([n/total for n in root.visits] if total else
                  [1./len(root.visits)]*len(root.visits))
        selected = max(range(len(policy)), key=lambda i: (policy[i],
                        root.utility(i)))
    return {'schema': 'arena-public-history-mcts/0', 'root_selection': root_selection,
            'selected_action': copy.deepcopy(first.actions[selected]),
            'actions': copy.deepcopy(first.actions), 'target_policy': policy,
            'root_priors': first.priors[:],
            'behavior_policy':behavior, 'learning_target':learning,
            'root_visits': root.visits,
            'root_attempts': root_attempts,
            'root_return_samples': [[list(v) if isinstance(v, tuple) else v for v in samples]
                                    for samples in root.samples],
            'root_sample_groups': root_sample_groups,
            'root_sample_grounded': root_sample_grounded,
            'root_sample_path_ids': root_sample_path_ids,
            'root_terminal_counts': root_terminal_counts,
            'root_distinct_particles': [len(set(g for g in groups if g is not None))
                                        for groups in root_sample_groups],
            'root_unknown_particle_samples': [sum(g is None for g in groups)
                                              for groups in root_sample_groups],
            'root_distinct_paths': [len(set(paths)) for paths in root_sample_path_ids],
            'particle_identity_semantics': 'Opaque root-sampler slot, not an independent world guarantee; duplicate slots may represent the same hidden state. Unknown identities stay null.',
            'root_value_mean': first.value,
            'root_value_best4': mixture_best_of([first.return_atoms],4) if first.return_atoms else None,
            'value_semantics': '32-quantile behavioral distribution; Best4 once' if first.return_atoms else 'legacy scalar',
            'root_mean_returns': [v/n if n else None for v, n in zip(root.totals, root.visits)],
            'root_objective_returns':[root.utility(i) if n else None for i,n in enumerate(root.visits)],
            'objective_k':objective_k,
            'objective':'mean' if objective_k==1 else 'empirical_best_of_4',
            'objective_scope':'Best-of-4 applied once to equally weighted simulation distributions. Learned atoms remain behavioral estimates, not optimal-value bounds.',
            'soft_allocation': {'floor':soft_floor,'temperature':soft_temperature,
                'minimum_visits':soft_min_visits,'permanently_eliminated_actions':0} if root_selection=='soft_budget' else None,
            'root_action_coverage': sum(n > 0 for n in root.visits)/len(root.visits),
            'root_attempted_action_coverage': sum(n > 0 for n in root_attempts)/len(root_attempts),
            'tree_decision_nodes': len(tree), 'cost': counters,
            'simulations_requested': simulations, 'simulations_completed': completed,
            'require_terminal': require_terminal,
            'terminal_grounded_simulations': sum(root_terminal_counts),
            'continuation_contract': {'policy': 'greedy' if rollout_temperature == 0 else 'policy_temperature',
                'temperature': rollout_temperature, 'rng_stream': 'separate_seeded_rollout',
                'terminal_only_samples': require_terminal,
                'scope': 'Current-policy continuation, not optimal play; particle/path repetition is not independent evidence.'},
            'truncated_reason': None if truncated is None else str(truncated),
            'teacher_qualified': False,
            'target_budget_eligible': (all(n > 0 for n in root.visits)
                                       and total >= 2*len(root.visits) and supported),
            'limitation': 'Finite-budget conditional-world search; rollout/value blind spots remain.'}
