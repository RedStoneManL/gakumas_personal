"""The explicitly authorized search-time extension, without changing label quality gates."""
import copy


def validate_timeout_change(previous, current):
    if previous == current:
        return {}
    if not isinstance(previous, dict) or not isinstance(current, dict):
        raise ValueError('Missing search budget configuration')
    if previous.get('sampling_ms') != 2000 or previous.get('native_action_budget', 20000) != 20000:
        raise ValueError('Unaudited source search budget')
    expected = copy.deepcopy(previous)
    expected.update(sampling_ms=10000, native_action_budget=60000)
    if current != expected:
        raise ValueError('Only the authorized 2s/20k to 10s/60k sampling budget change is allowed')
    return {'sampling_ms': {'old': 2000, 'new': 10000},
            'native_action_budget': {'old': 20000, 'new': 60000}}
