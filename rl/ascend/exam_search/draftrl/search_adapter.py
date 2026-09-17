"""Versioned, weighted public-particle adapter for the MCTS prototype.

Import after configuring the isolated draftrl/shared/Arena paths. The real
recorder is never passed to this module. Timeout roots produce no labels.
"""
import copy
import math
import random
import time
from contextlib import nullcontext

from draftrl.choice import ChoiceState
from draftrl.encoding import collate, encode_exam
from gakumas_arena.engine.search import SearchBudget, SearchClient
from gakumas_arena.engine.training import TrainingError
from .public_mcts import Evaluation, search


class RejectedRoot(Exception):
    pass


def encoded_view(view):
    obs = view['observation']
    if obs.get('choice'):
        choice = ChoiceState(obs)
        choice.selected = list(view['partial_selection'])
        return choice.encode()
    if view['partial_selection']:
        raise ValueError('Partial selection without an active choice')
    return encode_exam(obs)


def native_command(view, command):
    if command['method'] == 'act':
        native = command['action']
    else:
        kind = command['method']
        options = [a for a in view['actions'] if a['type'] == kind
                   and (kind != 'choice_append' or a['index'] == command['index'])]
        if len(options) != 1:
            raise ValueError('Search/encoder subchoice mismatch')
        native = options[0]
    if native not in view['actions']:
        raise ValueError('Search/encoder action mismatch')
    return copy.deepcopy(native)


def validate_particles(sampled):
    if sampled.get('valid_for_search') is not True or sampled.get('status') != 'ok':
        raise RejectedRoot(sampled.get('status', 'invalid_sample'))
    weights = sampled.get('weights', [])
    if (len(weights) != len(sampled['worlds']) or len(weights) < 2
            or any(not math.isfinite(w) or w < 0 for w in weights)
            or not math.isclose(sum(weights), 1., abs_tol=1e-6)):
        raise ValueError('Invalid aligned posterior weights')
    ess = 1 / sum(w*w for w in weights)
    if not math.isclose(ess, sampled['effective_sample_size'], rel_tol=1e-6):
        raise ValueError('Posterior ESS does not match weights')
    if ess < .5*len(weights):
        raise RejectedRoot('degenerate')
    return weights


def root_search(model, entry, history, *, score_scale, policy_version,
                search_seed, partial_selection=(), simulations=32, particles=8,
                seconds=8., sampling_ms=2000, max_depth=8, rollout_steps=4,
                predictor=None, shared_client=None, objective_k=1, native_action_budget=20000,
                root_selection='gumbel_halving', soft_floor=.25, soft_temperature=.8, soft_min_visits=2,
                learning_target=None, require_terminal=False):
    if score_scale <= 0 or not math.isfinite(score_scale):
        raise ValueError('Positive exogenous score scale required')
    if type(native_action_budget) is not int or native_action_budget not in (20000, 60000):
        raise ValueError('Unaudited native action budget')
    started = time.monotonic()
    deadline = started + seconds
    report = {'schema': 'arena-search-root-record/1', 'policy_version': policy_version,
              'search_seed': search_seed, 'score_scale': score_scale,
              'valid_training_target': False, 'search': None, 'objective_k':objective_k,
              'budgets': {'root_seconds':seconds, 'sampling_ms':sampling_ms,
                          'native_action_budget':native_action_budget,
                          'require_terminal':require_terminal}}
    roots, branches = [], []
    # A separate client owns only hypothetical worlds; hard cancellation can
    # never invalidate the actual recorder owned by the collector.
    with (nullcontext(shared_client) if shared_client is not None else SearchClient(max_worlds=particles+2)) as client:
        initial_cost = dict(client.total_cost)
        report['search_version'] = client.version
        caps = {'native_actions': native_action_budget, 'rule_operations': 100000,
                'rng_calls': 200000, 'replay_entries': 10000, 'candidates': 512}

        def budget(request_ms=None):
            remaining_ms = int((deadline-time.monotonic())*1000)
            limits = {k: max(0, cap-int(client.total_cost.get(k, 0)-initial_cost.get(k, 0)))
                      for k, cap in caps.items()}
            # Candidate quota applies only to sampling; 0 candidates is valid
            # for later clone/observe/step requests.
            if remaining_ms <= 0 or any(limits[k] <= 0 for k in caps if k != 'candidates'):
                raise RejectedRoot('root_budget_exhausted')
            return SearchBudget(milliseconds=min(60000, remaining_ms, request_ms or 60000), **limits)

        class World:
            def __init__(self, world, view):
                self.world, self.view = world, view
            def observe(self):
                # This private wrapper belongs to public_mcts only. Each
                # native response is a fresh JSON tree; step replaces it.
                # The planner reads it and makes its own defensive copy at
                # the evaluator boundary (public_mcts.assess). Borrowing here
                # avoids copying the whole public state twice per evaluation.
                return self.view
            def step(self, command):
                action = native_command(self.view, command)
                result = self.world.step(action, budget=budget())
                if result['status'] not in ('ok', 'terminal'):
                    raise RejectedRoot(result['status'])
                self.view = result['view']
                # Legacy policy factorization commits automatically at max.
                # Arena search intentionally requires an explicit finish; do
                # it here within the same policy decision and shared budget.
                pending = self.view['observation'].get('choice')
                if (action['type'] == 'choice_append' and pending
                        and len(self.view['partial_selection']) == pending['max']):
                    finish = next(a for a in self.view['actions'] if a['type'] == 'choice_finish')
                    result = self.world.step(finish, budget=budget())
                    if result['status'] not in ('ok', 'terminal'):
                        raise RejectedRoot(result['status'])
                    self.view = result['view']
                return self.observe()
            def release(self):
                if self.world is not None:
                    self.world.release()
                    self.world = None

        def evaluate(view):
            budget()
            result = view['observation']['result']
            if result['truncated']:
                raise RejectedRoot('truncated_hypothetical')
            if result['terminated']:
                value = result['final_score']/score_scale
                return Evaluation([], [], value, value)
            encoded = encoded_view(view)
            if predictor is None:
                import torch
                with torch.no_grad():
                    logits, values, atoms = model.search_forward(collate([encoded], next(model.parameters()).device))
                priors = logits[0, :len(encoded.submissions)].softmax(-1).tolist()
                value = float(values[0])
                atoms = atoms[0].tolist() if atoms is not None else None
            else:
                prediction = predictor(encoded, deadline)
                priors, value = prediction[:2]
                atoms = prediction[2] if len(prediction)>2 else None
            budget()
            return Evaluation(encoded.submissions, priors, value, return_atoms=atoms)

        try:
            sampled = client.sample_public_worlds(entry, history, search_seed=search_seed,
                particles=particles, partial_selection=partial_selection, budget=budget(sampling_ms))
            roots = sampled['worlds']
            report['sampling'] = {k: v for k, v in sampled.items() if k in (
                'status', 'valid_for_search', 'weights', 'effective_sample_size',
                'distinct_particles', 'duplicate_particles', 'resampled',
                'diagnostics', 'attempts', 'accepted', 'cost')}
            weights = validate_particles(sampled)
            rng = random.Random(search_seed ^ 0x57392)
            root = roots[0].observe(budget=budget())
            expected = history['steps'][-1]['observation'] if history['steps'] else history['initial']['observation']
            if root['observation'] != expected or root['partial_selection'] != list(partial_selection):
                raise ValueError('Sample root differs from recorded public history')
            def sample_world():
                # Sampling proportional to posterior weights makes backed-up
                # arithmetic means estimate the weighted chance expectation.
                parent = rng.choices(roots, weights=weights, k=1)[0]
                native = parent.clone(budget=budget())
                wrapped = World(native, None)
                branches.append(wrapped)
                wrapped.view = native.observe(budget=budget())
                return wrapped
            def spent_budget(error):
                # RejectedRoot covers the wall-clock deadline and the native action caps.
                # TrainingError counts only for the kinds this adapter already treats as
                # a budget outcome; anything else stays a hard failure.
                if isinstance(error, RejectedRoot):
                    return True
                return (isinstance(error, TrainingError) and error.kind in
                        ('deadline', 'budget_exhausted', 'cancelled', 'worker_timeout', 'closed'))

            result = search(root, sample_world, evaluate, simulations=simulations,
                            max_depth=max_depth, rollout_steps=rollout_steps, search_seed=search_seed,
                            objective_k=objective_k, root_selection=root_selection,
                            recoverable=spent_budget, require_terminal=require_terminal,
                            soft_floor=soft_floor,soft_temperature=soft_temperature,soft_min_visits=soft_min_visits,
                            learning_target=learning_target)
            # Only re-check the budget for a root that finished inside it. A truncated
            # root is over budget by definition; calling budget() here would raise and
            # throw away the very simulations this path exists to keep.
            if result.get('truncated_reason') is None:
                budget()
            report['search'] = result
            report['valid_training_target'] = result['target_budget_eligible']
            if report['valid_training_target']:
                report['status'] = 'ok' if result.get('truncated_reason') is None else 'ok_truncated'
            else:
                report['status'] = 'insufficient_search_budget'
        except RejectedRoot as error:
            report['status'] = str(error)
            report['search'] = None
        except TrainingError as error:
            if error.kind not in ('deadline', 'budget_exhausted', 'cancelled', 'worker_timeout', 'closed'):
                raise
            report['status'] = error.kind
            report['search'] = None
        finally:
            for world in branches:
                world.release()
            for world in roots:
                world.release()
            report['cost'] = {k: v-initial_cost.get(k, 0) for k, v in client.total_cost.items()}
    report['elapsed_seconds'] = time.monotonic()-started
    return report
