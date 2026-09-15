"""Bounded fresh-engine integration test; never writes the active run."""
import copy, json, random, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena')]


def main():
    import torch
    from draftrl.checkpoint import load, digest, save
    from draftrl.migration import groups
    from draftrl.bank_rollout import rollout_bank
    from draftrl.runner import choose
    from draftrl.distribution import schedule
    from draftrl.duplicate_limits import family_ids
    from draftrl.best_of import apply_bank_returns
    from draftrl.search_router import SearchRouter
    from draftrl.ppo import update
    from r1rl.environment import Workers
    torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.15)
    out=ROOT/'rl/experiments/kl-value-20260915';out.mkdir(exist_ok=True)
    source=ROOT/'rl/generalist/runs/joint-mcts-soft-value-20260915-121503'
    checkpoint=source/'snapshot-0013.pt';model,info=load(checkpoint,'cuda')
    cfg=json.loads((HERE/'training-config.json').read_text(encoding='utf-8'))
    cfg.update(workers=4,minibatch=8,_profiles=json.loads((HERE/'setup/profiles.json').read_text()),
               _card_families=family_ids(json.loads((HERE/'setup/catalog.json').read_text())),
               _completed_batches=13,_policy_version='kl-value-probe:'+digest(checkpoint))
    search_cfg={**cfg['search'],'parallel_roots':2,'inference_batch':4,'max_roots_per_episode':1,'objective_k':4}
    manifest=json.loads((source/'value-calibration/data-manifest.json').read_text(encoding='utf-8'))
    picked={}
    for task in manifest['tasks']['fit']:
        picked.setdefault(task['metadata']['profile'],task)
    tasks=[]
    for i,(profile,task) in enumerate(sorted(picked.items())):
        for branch in range(4):
            t=copy.deepcopy(task);t['replay_seed']=3_800_000_000+i*100+branch
            t['metadata'].update(search_enabled=True,prefix_id='probe:'+profile,branch_id=branch,
                                 fork_replicas=4,exploration_mode='normal')
            tasks.append(t)
    (out/'tasks.json').write_text(json.dumps(tasks,ensure_ascii=False,indent=2),encoding='utf-8')
    router=SearchRouter(model,'cuda',search_cfg,log_path=out/'search-roots.jsonl')
    cfg['_search_router']=router;pool=Workers(4,HERE/'runtime/arena',info['arena_sha256'])
    start=time.monotonic();random.seed(712);torch.manual_seed(713)
    try:
        rows,episodes,decisions=rollout_bank(pool,model,None,cfg,'cuda',len(tasks),
            schedule(cfg,info['decisions']),choose,log_path=out/'episodes.jsonl',tasks=tasks)
        result_groups=apply_bank_returns(rows,episodes,tasks)
        search=router.diagnostics()
    finally:
        router.close();pool.close();cfg.pop('_search_router',None)
    collection=time.monotonic()-start
    if len(episodes)!=20 or len(result_groups)!=5 or not any(r['loss_kind']=='search' for r in rows):
        raise ValueError('Probe lacks complete four-game groups or real search records')
    truths=[r['return'] for r in rows]
    trials={}
    for label in ('old_guard','new_guard_and_value'):
        candidate=copy.deepcopy(model)
        rates={name:info['optimizer_state']['param_groups'][i]['lr']
               for i,name in enumerate(('exam','drink','draft','guidance','memory'))}
        optimizer=groups(candidate,rates);optimizer.load_state_dict(info['optimizer_state'])
        c=copy.deepcopy(cfg)
        if label=='old_guard':c.pop('critic_completion');c['target_kl']=.015
        random.seed(918);torch.manual_seed(919);begin=time.monotonic()
        result=update(candidate,optimizer,rows,c,'cuda')
        assert [r['return'] for r in rows]==truths
        trials[label]={'seconds':time.monotonic()-begin,**result}
        if label=='new_guard_and_value':
            if result['critic_update_coverage']['accepted_fraction']!=1. or not result['critic_completion']['actor_unchanged']:
                raise ValueError('Critic coverage or actor freeze failed')
            save(out/'probe-updated.pt',candidate,optimizer)
            loaded,restored=load(out/'probe-updated.pt','cpu')
            assert loaded.config==candidate.config
            assert all(torch.equal(v.detach().cpu(),loaded.state_dict()[k]) for k,v in candidate.state_dict().items())
        del candidate,optimizer
    report={'status':'passed','source_checkpoint_sha256':digest(checkpoint),'games':len(episodes),
            'four_game_groups':len(result_groups),'records':len(rows),'meaningful_decisions':decisions,
            'collection_seconds':collection,'search':search,'trials':trials,'checkpoint_roundtrip':True,
            'scope':'20 fresh real Arena exams, one root per game; frozen source13 with same records for old/new update checks. Not a full production speed or score-improvement comparison.'}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','games':len(episodes),'records':len(rows),'search_targets':search['counts'].get('accepted_targets'),
        'trials':{k:{'joint_coverage':v['update_coverage']['accepted_fraction'],
                     'critic_coverage':v['critic_update_coverage']['accepted_fraction'],
                     'steps':v['optimizer_steps'],'completion_steps':(v['critic_completion'] or {}).get('optimizer_steps')}
                  for k,v in trials.items()}}),flush=True)


if __name__=='__main__':main()
