from __future__ import annotations

from copy import deepcopy
import math
from typing import Callable

from ..contracts import DecisionContext, PolicySelection, Transition


class DecisionRecorder:
    """Stage callback trajectories until the owning Arena transaction commits."""

    def __init__(self, task: str, policy: Callable, policy_version: int):
        self.task, self.policy, self.policy_version = task, policy, policy_version
        self.transitions: list[Transition] = []

    def select(self, kind: str, observation: dict, candidates) -> dict:
        candidates = tuple(deepcopy(tuple(candidates)))
        if not candidates:
            raise ValueError(f'No legal candidates at {kind}')
        if len(candidates) == 1:
            return candidates[0]
        context = DecisionContext(self.task, kind, deepcopy(observation), candidates)
        # Policies cannot mutate the canonical trajectory or engine command.
        selection = self.policy(deepcopy(context))
        if not isinstance(selection, PolicySelection):
            raise TypeError('Policy must return PolicySelection')
        if type(selection.action_index) is not int or not 0 <= selection.action_index < len(candidates):
            raise ValueError('Policy chose an illegal candidate index')
        if selection.policy_version != self.policy_version:
            raise ValueError('Behavior policy version changed within the episode')
        if not all(math.isfinite(x) for x in (selection.log_prob, selection.value)):
            raise ValueError('Non-finite behavior probability/value')
        if selection.log_prob > 1e-6:
            raise ValueError('Behavior log probability must be <= 0')
        self.transitions.append(Transition(context, selection))
        return candidates[selection.action_index]

    def transaction(self, execute):
        boundary = len(self.transitions)
        try:
            return execute()
        except BaseException:
            del self.transitions[boundary:]
            raise


def choose_exam(recorder: DecisionRecorder, exam: dict, observation_factory: Callable) -> dict | list[int]:
    """Ordered card selection uses bounded autoregressive choices, not n! actions.

    Selection micro-decisions are committed only when the containing Arena action
    succeeds. A STOP candidate is present exactly when the engine permits it.
    """
    choice = exam.get('choice')
    if choice is None:
        return recorder.select('exam_action', observation_factory({}), exam['actions'])
    selected: list[int] = []
    items = choice['candidates']
    minimum, maximum = choice['min'], choice['max']
    while len(selected) < maximum:
        candidates = [dict(type='select', index=i, option=deepcopy(row))
                      for i, row in enumerate(items)
                      if choice.get('allow_duplicates', False) or i not in selected]
        if len(selected) >= minimum:
            candidates.append({'type': 'finish_selection'})
        resolution = {
            'kind': choice['type'], 'context': deepcopy(choice.get('context', {})),
            'selected_indices': list(selected), 'selected_targets': [deepcopy(items[i]) for i in selected],
            'min': minimum, 'max': maximum, 'ordered': choice.get('ordered', True),
        }
        action = recorder.select('exam_choice', observation_factory(resolution), candidates)
        if action['type'] == 'finish_selection':
            break
        selected.append(action['index'])
    if len(selected) < minimum:
        raise ValueError('Engine selection constraints cannot be satisfied')
    return selected
