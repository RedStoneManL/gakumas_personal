"""Allow exactly the requested KL relaxation and independent value completion."""
import copy

SETTINGS = {'enabled': True, 'minimum_passes': 1, 'actor_frozen': True}


def validate_config(source, target):
    old, new = copy.deepcopy(source), copy.deepcopy(target)
    source_kl, target_kl = old.pop('target_kl'), new.pop('target_kl')
    if (source_kl, target_kl) != (.015, .03):
        raise ValueError('Only target KL .015 -> .03 is authorized')
    if old.pop('critic_completion', None) is not None or new.pop('critic_completion', None) != SETTINGS:
        raise ValueError('Unexpected critic completion settings')
    if old != new:
        raise ValueError('KL/value continuation changed unrelated settings')
    return {'target_kl': target_kl, 'block_stop_kl': 2*target_kl, 'critic_completion': SETTINGS}
