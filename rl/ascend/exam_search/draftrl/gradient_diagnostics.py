"""Small, observational task-gradient probe; never changes parameters or optimizer."""
from itertools import combinations
import torch
from .encoding import collate
from .distribution import distributions


def inspect_gradients(model,records,config,device):
    if config.get('signed_exam_credit'):
        from .signed_credit import prepare
        prepare(records,config['signed_exam_credit'])
    cfg=config.get('practice',{}).get('gradient_diagnostics',{})
    count=cfg.get('examples_per_profile',2)
    params=list(model.actor.parameters());vectors={}
    if hasattr(model, 'actor_relational'):
        params += list(model.actor_relational.parameters())
    for profile in sorted({r['profile'] for r in records}):
        rows=[r for r in records if r['profile']==profile and r['encoded'].phase==0
              and len(r['encoded'].submissions)>1][:count]
        if not rows:continue
        batch=collate([r['encoded'] for r in rows],device)
        logits=model.policy(batch)
        dist,_=distributions(logits,batch['mask'],[r['exploration'] for r in rows])
        actions=torch.tensor([r['action'] for r in rows],device=device)
        adv=logits.new_tensor([r.get('policy_advantage',r['return']-r['old_value']) for r in rows])
        adv=adv/adv.square().mean().sqrt().clamp_min(1e-5)
        grads=torch.autograd.grad(-(dist.log_prob(actions)*adv).mean(),params,allow_unused=True)
        vectors[profile]=torch.cat([(g.detach().flatten().cpu() if g is not None else torch.zeros(p.numel()))
                                   for g,p in zip(grads,params)])
    pairs={}
    for a,b in combinations(vectors,2):
        x,y=vectors[a],vectors[b];den=float(x.norm()*y.norm())
        pairs[a+'|'+b]=float(x.dot(y)/den) if den>1e-12 else None
    return {'scope':'shared actor, sampled exam policy gradients; diagnostic only',
            'signed_credit':bool(config.get('signed_exam_credit')),
            'examples_per_profile':count,'cosine_similarity':pairs,
            'negative_pairs':sum(v is not None and v<0 for v in pairs.values())}
