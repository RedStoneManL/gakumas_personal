"""Separate broad search behavior from evidence-weighted policy improvement."""
import math
import statistics
from .learning_settings import SEARCH
from .value_distribution import mixture_best_of


def entropy(probabilities):
    return -sum(p*math.log(p) for p in probabilities if p>0)/math.log(len(probabilities)) if len(probabilities)>1 else 0.


def improve(priors, samples, objective_k, settings):
    if settings != SEARCH or objective_k not in (1,4):
        raise ValueError('Unvalidated search learning settings')
    if len(priors)!=len(samples) or any(len(s)<2 for s in samples):
        raise ValueError('Learning target requires all actions sampled at least twice')
    if any(not math.isfinite(p) or p<0 for p in priors) or not math.isclose(sum(priors),1.,abs_tol=1e-5):
        raise ValueError('Invalid policy prior')
    # Tiny numerical support avoids log(0), not an exploration mixture target.
    prior=[max(p,1e-12) for p in priors]; prior=[p/sum(prior) for p in prior]
    qs=[mixture_best_of(s,objective_k) for s in samples]
    ses=[]
    for outcomes in samples:
        leave=[mixture_best_of(outcomes[:i]+outcomes[i+1:],objective_k) for i in range(len(outcomes))]
        mean=statistics.mean(leave)
        ses.append(math.sqrt((len(leave)-1)/len(leave)*sum((v-mean)**2 for v in leave)))
    reference=sum(p*q for p,q in zip(prior,qs))
    reference_se=math.sqrt(sum((p*se)**2 for p,se in zip(prior,ses)))
    margins=[settings['noise_floor']+settings['uncertainty_multiplier']*math.hypot(se,reference_se) for se in ses]
    deltas=[q-reference for q in qs]
    shifts=[max(-settings['max_logit_change'],min(settings['max_logit_change'],
        math.copysign(max(abs(d)-margin,0.),d)/settings['temperature'])) for d,margin in zip(deltas,margins)]
    logits=[math.log(p)+shift for p,shift in zip(prior,shifts)]
    values=[math.exp(x-max(logits)) for x in logits]; target=[x/sum(values) for x in values]
    gain=sum((p-old)*q for p,old,q in zip(target,prior,qs))
    if not any(shifts) or gain<=1e-12:
        target=prior[:];gain=0.
    weight=min(1.,gain/settings['noise_floor'])
    return target, {'mode':'prior_advantage','prior_policy':prior,'weight':weight,
        'estimated_gain':gain,'reference_value':reference,'action_values':qs,
        'simulation_standard_errors':ses,'regularization_margins':margins,'logit_changes':shifts,
        'target_entropy':entropy(target),'prior_entropy':entropy(prior),
        'uncertainty_scope':'Delete-one simulation jackknife is a heuristic, not a confidence interval; learned-value bias is not measured.',
        'no_evidence_keeps_prior':True,'exploration_floor_in_target':0.}
