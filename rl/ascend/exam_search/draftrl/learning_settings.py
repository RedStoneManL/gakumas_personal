"""Versioned settings; no changes to the real score or exploration budget."""
import copy
from .kl_value_migration import SETTINGS as COMPLETION

SIGNED = {'mode': 'state_best4_contribution', 'baseline': 'frozen_pre_action_quantiles',
          'quantiles': 32, 'rms_floor': .1}
SEARCH = {'mode': 'prior_advantage', 'temperature': .25, 'noise_floor': .05,
          'uncertainty_multiplier': 1., 'max_logit_change': 4.}


def validate_config(source, target):
    old, new = copy.deepcopy(source), copy.deepcopy(target)
    if new.pop('signed_exam_credit', None) != SIGNED or old.pop('signed_exam_credit', None) is not None:
        raise ValueError('Unexpected signed credit settings')
    if new['search'].pop('learning_target', None) != SEARCH or old['search'].pop('learning_target', None) is not None:
        raise ValueError('Unexpected search learning settings')
    if old['target_kl'] == .015 and old.get('critic_completion') is None:
        old.update(target_kl=.03, critic_completion=copy.deepcopy(COMPLETION))
    if old.get('target_kl') != .03 or old.get('critic_completion') != COMPLETION or old != new:
        raise ValueError('Signed continuation changed unrelated configuration')
    return {'target_kl': .03, 'signed_exam_credit': SIGNED, 'search_learning_target': SEARCH}
