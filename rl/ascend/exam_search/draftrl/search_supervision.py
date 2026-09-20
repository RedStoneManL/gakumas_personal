"""Conservative, training-only search supervision for real Best-of-four games.

The other three REAL returns supply an action-independent threshold. A root
action is valued by mean(max(terminal_return - peer_max, 0)), never by taking
Best-of-four separately for each action. Search is adaptive and its continuation
policy is not necessarily the behavior policy: these are auxiliary CE labels,
not an unbiased policy-gradient advantage or an independent validation result.

Simulation means retain the adapter's posterior sampling frequencies. Opaque
root-particle identities only cluster uncertainty and gate evidence. Repeating
clones of a particle does not create additional independent particle evidence.
"""
import copy
import math
from collections import Counter, defaultdict


SCHEMA = 'arena-peer-marginal-search/1'
DEFAULT_AUXILIARY_CREDIT = {
    'schema': SCHEMA, 'temperature': .25, 'noise_floor': .05,
    'uncertainty_multiplier': 1., 'min_distinct_particles': 3,
    'max_logit_change': 2.,
}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _settings(search_config):
    supplied = search_config.get('auxiliary_credit')
    if not isinstance(supplied, dict) or supplied.get('schema') != SCHEMA:
        raise ValueError('Auxiliary search requires an explicit supported credit schema')
    if set(supplied) - set(DEFAULT_AUXILIARY_CREDIT):
        raise ValueError('Unknown auxiliary credit settings')
    result = {**DEFAULT_AUXILIARY_CREDIT, **supplied}
    for key in ('temperature', 'noise_floor', 'max_logit_change'):
        if not _finite(result[key]) or result[key] <= 0:
            raise ValueError('Invalid auxiliary credit ' + key)
    if (not _finite(result['uncertainty_multiplier']) or result['uncertainty_multiplier'] < 0
            or type(result['min_distinct_particles']) is not int
            or result['min_distinct_particles'] < 3):
        raise ValueError('Auxiliary credit requires at least three particle clusters')
    return result


def validate_training_config(config):
    """Validate the opt-in contract; legacy acting-search configs remain intact."""
    search = config.get('search', {})
    mode = search.get('execution_mode', 'act')
    if mode not in ('act', 'auxiliary'):
        raise ValueError('Unknown search execution mode')
    if mode != 'auxiliary':
        if 'auxiliary_credit' in search:
            raise ValueError('Auxiliary credit requires auxiliary search execution')
        return {'enabled': False}
    settings = _settings(search)
    forks = config.get('practice', {}).get('forks', {})
    if (search.get('enabled') is not True or search.get('require_terminal') is not True
            or search.get('objective_k', 4) != 4
            or config.get('gamma') != 1
            or config.get('sample_efficiency', {}).get('advantage_mode', 'mc') != 'mc'
            or forks.get('enabled') is not True or forks.get('replicas') != 4
            or forks.get('objective') != 'best_of_k'
            or forks.get('exam_credit') != 'leave_one_out_max'
            or forks.get('every_n_per_profile', 1) != 1):
        raise ValueError('Auxiliary credit requires pure-policy complete four-game MC returns and terminal search')
    return {'enabled': True, **settings}


class _Rejected(ValueError):
    pass


def _entropy(probabilities):
    if len(probabilities) < 2:
        return 0.
    return -math.fsum(p * math.log(p) for p in probabilities if p > 0) / math.log(len(probabilities))


def _probabilities(value, count):
    if (not isinstance(value, list) or len(value) != count
            or any(not _finite(p) or p < 0 for p in value)
            or not math.isclose(math.fsum(value), 1., abs_tol=1e-6)):
        raise _Rejected('invalid_prior_policy')
    return [float(p) / math.fsum(value) for p in value]


def _particle_key(label):
    # Opaque identifiers are compared only, never parsed as seeds or world state.
    if label is None:
        return None
    if type(label) not in (str, int):
        raise _Rejected('invalid_particle_identity')
    return type(label).__name__, label


def _target(row, settings):
    encoded = row.get('encoded')
    if getattr(encoded, 'phase', None) != 0 or row.get('loss_kind') != 'ppo':
        raise _Rejected('not_real_policy_exam')
    peer, own, gain = row.get('peer_max_return'), row.get('return'), row.get('group_marginal_gain')
    if (row.get('fork_replicas') != 4 or not all(_finite(x) for x in (peer, own, gain))
            or not _finite(row.get('own_terminal_return'))
            or not math.isclose(row['own_terminal_return'], own, abs_tol=1e-6)
            or not math.isclose(max(own-peer, 0.), gain, abs_tol=1e-6)):
        raise _Rejected('invalid_real_four_game_credit')
    raw = row['search_aux']
    if not isinstance(raw, dict):
        raise _Rejected('invalid_search_evidence')
    if raw.get('require_terminal') is not True:
        raise _Rejected('terminal_search_contract_missing')
    actions = raw.get('actions')
    if (not isinstance(actions, list) or len(actions) < 2
            or actions != encoded.submissions):
        raise _Rejected('unaligned_root_actions')
    count = len(actions)
    if raw.get('target_budget_eligible') is not True:
        raise _Rejected('ineligible_search_budget')
    coverage = raw.get('root_action_coverage')
    if not _finite(coverage) or not math.isclose(coverage, 1., abs_tol=1e-9):
        raise _Rejected('incomplete_root_action_coverage')
    if raw.get('objective_k', 4) != 4:
        raise _Rejected('wrong_search_objective')
    population = raw.get('root_particle_population')
    if not isinstance(population, dict):
        raise _Rejected('missing_particle_population')
    if (any(type(population.get(k)) is not int for k in ('requested', 'distinct', 'duplicate'))
            or population['requested'] < 1 or population['distinct'] < 1
            or population['duplicate'] < 0
            or population['distinct'] + population['duplicate'] != population['requested']
            or not _finite(population.get('ess'))
            or not 0 < population['ess'] <= population['requested'] + 1e-6):
        raise _Rejected('invalid_particle_population')
    # Slots are not canonical hidden-world IDs. If the sampler reports duplicate
    # particles, no slot-to-canonical mapping exists to cluster them correctly.
    if population['duplicate']:
        raise _Rejected('duplicate_population_without_canonical_groups')
    if (population['distinct'] < settings['min_distinct_particles']
            or population['ess'] + 1e-6 < settings['min_distinct_particles']):
        raise _Rejected('insufficient_particle_population')
    priors = [raw[key] for key in ('root_priors', 'priors') if key in raw]
    previous = raw.get('learning_target')
    if isinstance(previous, dict) and 'prior_policy' in previous:
        priors.append(previous['prior_policy'])
    if not priors:
        raise _Rejected('missing_root_prior')
    priors = [_probabilities(p, count) for p in priors]
    prior = priors[0]
    if any(any(not math.isclose(a, b, abs_tol=1e-7) for a, b in zip(prior, other))
           for other in priors[1:]):
        raise _Rejected('conflicting_root_priors')
    samples, groups, grounded = [raw.get(key) for key in
        ('root_return_samples', 'root_sample_groups', 'root_sample_grounded')]
    if any(not isinstance(values, list) or len(values) != count for values in (samples, groups, grounded)):
        raise _Rejected('missing_or_unaligned_sample_metadata')
    clusters, values, raw_counts = [], [], []
    for outcomes, labels, terminals in zip(samples, groups, grounded):
        if (not all(isinstance(x, list) for x in (outcomes, labels, terminals))
                or len(outcomes) != len(labels) or len(outcomes) != len(terminals)):
            raise _Rejected('unaligned_action_samples')
        raw_counts.append(len(outcomes))
        action_clusters, action_values = defaultdict(list), []
        for outcome, label, terminal in zip(outcomes, labels, terminals):
            if type(terminal) is not bool:
                raise _Rejected('invalid_grounded_flag')
            group = _particle_key(label)
            if not terminal:
                raise _Rejected('nonterminal_sample_in_terminal_contract')
            if not _finite(outcome):
                raise _Rejected('invalid_terminal_sample')
            if group is None:
                raise _Rejected('unknown_root_particle')
            value = max(float(outcome) - peer, 0.)
            action_values.append(value)
            action_clusters[group].append(value)
        if len(action_clusters) < settings['min_distinct_particles']:
            raise _Rejected('insufficient_distinct_root_particles')
        clusters.append(action_clusters)
        values.append(action_values)
    # Do not equal-weight clusters here: samples were drawn according to the
    # adapter's posterior weights, and equal groups would change that measure.
    qs = [math.fsum(v) / len(v) for v in values]
    reference = math.fsum(p*q for p, q in zip(prior, qs))
    keys = set().union(*(set(c) for c in clusters))
    if len(keys) > population['distinct']:
        raise _Rejected('particle_groups_exceed_population')
    influences = [{g: math.fsum(x-q for x in members) / len(outcomes)
                   for g, members in grouped.items()}
                  for grouped, outcomes, q in zip(clusters, values, qs)]
    baseline = {g: math.fsum(p * influence.get(g, 0.) for p, influence in zip(prior, influences))
                for g in keys}
    # Cluster sandwich-style noise scale. Shared particles are kept aligned
    # across actions. This is a heuristic, not a CI or a cure for adaptive bias.
    correction = len(keys)/(len(keys)-1)
    delta_ses = [math.sqrt(correction * math.fsum((influence.get(g, 0.)-baseline[g])**2
                                                 for g in keys)) for influence in influences]
    action_ses = [math.sqrt(len(grouped)/(len(grouped)-1)*math.fsum(v*v for v in influence.values()))
                  for grouped, influence in zip(clusters, influences)]
    deltas = [q-reference for q in qs]
    margins = [settings['noise_floor'] + settings['uncertainty_multiplier']*se for se in delta_ses]
    shifts = [max(-settings['max_logit_change'], min(settings['max_logit_change'],
              math.copysign(max(abs(delta)-margin, 0.), delta) / settings['temperature']))
              for delta, margin in zip(deltas, margins)]
    # Preserve zero prior support; no uniform exploration floor enters the CE.
    logits = [math.log(p)+shift if p > 0 else -math.inf for p, shift in zip(prior, shifts)]
    weights = [math.exp(logit-max(logits)) for logit in logits]
    target = [value / math.fsum(weights) for value in weights]
    estimated_gain = math.fsum((p-old)*q for p, old, q in zip(target, prior, qs))
    conservative_gain = estimated_gain - math.fsum(abs(p-old)*margin for p, old, margin in zip(target, prior, margins))
    weight = min(1., max(0., conservative_gain)/settings['noise_floor'])
    if not any(shifts) or weight <= 0:
        target, estimated_gain, conservative_gain, weight = prior[:], 0., 0., 0.
    behavior = raw.get('behavior_policy')
    # Search allocation is only diagnostic; it never becomes the live behavior.
    behavior = prior if behavior is None else _probabilities(behavior, count)
    detail = {
        'schema': SCHEMA, 'mode': 'peer_marginal', 'weight': weight,
        'prior_policy': prior, 'action_values': qs, 'reference_value': reference,
        'estimated_gain': estimated_gain, 'conservative_gain': conservative_gain,
        'peer_max_return': peer, 'objective_k': 4,
        'target_entropy': _entropy(target), 'prior_entropy': _entropy(prior),
        'behavior_entropy': _entropy(behavior),
        'clustered_action_noise': action_ses, 'clustered_delta_noise': delta_ses,
        'regularization_margins': margins, 'logit_changes': shifts,
        'root_exploration_counts': raw_counts,
        'terminal_samples_used': [len(v) for v in values],
        'distinct_root_particles': [len(c) for c in clusters],
        'distinct_root_particles_union': len(keys),
        'root_particle_population': copy.deepcopy(population),
        'particle_frequency_effective_counts': [len(v)**2/math.fsum(len(m)**2 for m in c.values())
                                              for v, c in zip(values, clusters)],
        'excluded_samples': {},
        'uncertainty_scope': 'Particle-cluster noise heuristic, not a confidence interval; adaptive search and continuation-policy bias remain.',
        'independent_heldout_validation': False,
        'value_estimator': 'terminal simulation mean of positive excess over three real peer returns',
        'no_evidence_keeps_prior': True, 'exploration_floor_in_target': 0.,
    }
    return {'actions': copy.deepcopy(actions), 'target_policy': target, 'weight': weight,
            'learning_target': detail, 'target_budget_eligible': True, 'root_action_coverage': coverage}


def prepare_auxiliary(records, search_config):
    """Attach CE-only targets, preserving raw evidence and every real PPO field.

    Invalid/missing evidence rejects that root (with a reason), never becomes a
    fabricated zero return. Configuration mistakes raise before any mutation.
    Calling repeatedly rebuilds targets and removes any stale rejected target.
    """
    mode = search_config.get('execution_mode', 'act')
    if mode != 'auxiliary':
        if mode != 'act' or 'auxiliary_credit' in search_config or any(
                'search_aux' in row or 'search_aux_target' in row for row in records):
            raise ValueError('Auxiliary targets require auxiliary execution mode')
        return {'enabled': False, 'roots': 0, 'accepted_roots': 0, 'weighted_roots': 0}
    settings = _settings(search_config)
    plans, rejected = [], Counter()
    roots = 0
    for row in records:
        if 'search_aux' not in row:
            plans.append((row, None))
            continue
        roots += 1
        try:
            target = _target(row, settings)
        except _Rejected as error:
            target = None
            rejected[str(error)] += 1
        plans.append((row, target))
    accepted = []
    for row, target in plans:
        row.pop('search_aux_target', None)
        if target is not None:
            row['search_aux_target'] = target
            accepted.append(target['learning_target'])
    return {'enabled': True, 'schema': SCHEMA, 'mode': 'peer_marginal',
            'roots': roots, 'accepted_roots': len(accepted),
            'weighted_roots': sum(d['weight'] > 0 for d in accepted),
            'rejected_roots': sum(rejected.values()), 'rejected_reasons': dict(rejected),
            'mean_weight': math.fsum(d['weight'] for d in accepted)/max(1, len(accepted)),
            'exploration_samples': sum(sum(d['root_exploration_counts']) for d in accepted),
            'distinct_particle_action_pairs': sum(sum(d['distinct_root_particles']) for d in accepted),
            'independent_heldout_validation': False,
            'own_returns_actions_likelihoods_and_values_preserved': True}
