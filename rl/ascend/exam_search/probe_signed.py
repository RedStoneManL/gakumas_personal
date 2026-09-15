"""Fresh five-profile construction/repeat/bank integration; isolated from active."""
import copy,json,random,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena')]


def main():
    import torch
    from draftrl.checkpoint import load,digest,save
    from draftrl.migration import groups
    from draftrl.runner import choose,rollout
    from draftrl.bank_rollout import rollout_bank
    from draftrl.practice import make_fork_tasks,apply_fork_returns
    from draftrl.best_of import apply_bank_returns
    from draftrl.construction_reward import apply_draft_penalty
    from draftrl.distribution import schedule
    from draftrl.duplicate_limits import family_ids
    from draftrl.search_router import SearchRouter
    from draftrl.ppo import update
    from r1rl.environment import Workers
    torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.15)
    out=ROOT/'rl/experiments/signed-credit-20260915';out.mkdir(exist_ok=True)
    if (out/'report.json').exists():raise ValueError('Existing probe report must not be overwritten')
    source=ROOT/'rl/generalist/runs/joint-mcts-soft-value-20260915-121503'
    checkpoint=source/'snapshot-0014.pt';model,info=load(checkpoint,'cuda')
    cfg=json.loads((HERE/'training-config.json').read_text(encoding='utf-8'))
    catalog=json.loads((HERE/'setup/catalog.json').read_text(encoding='utf-8'))
    cfg.update(workers=5,minibatch=8,train_seed_base=3_700_000_000,
        _profiles=json.loads((HERE/'setup/profiles.json').read_text(encoding='utf-8')),
        _card_families=family_ids(catalog),_completed_batches=14,_policy_version='signed-probe:'+digest(checkpoint))
    search_cfg={**cfg['search'],'parallel_roots':2,'inference_batch':4,'max_roots_per_episode':1,'objective_k':4}
    router=SearchRouter(model,'cuda',search_cfg,log_path=out/'search-roots.jsonl')
    cfg['_search_router']=router;pool=Workers(5,HERE/'runtime/arena',info['arena_sha256'])
    random.seed(951);torch.manual_seed(952);start=time.monotonic()
    try:
        exploration=schedule(cfg,info['decisions'])
        rows,parents,decisions,_=rollout(pool,model,None,catalog,cfg,'cuda',cfg['train_seed_base'],
            target_decisions=1,exploration=exploration,keep_entries=True,log_path=out/'episodes.jsonl')
        tasks,_=make_fork_tasks(parents,cfg,3_760_000_000)
        extra,episodes,more=rollout_bank(pool,model,None,cfg,'cuda',len(tasks),exploration,choose,
            tasks=tasks,source='fork_exam',log_path=out/'episodes.jsonl')
        fork_groups=apply_fork_returns(rows,parents,extra,episodes,expected_tasks=tasks,objective='best_of_k')
        # apply_fork_returns appends extra records itself.
        all_episodes=parents+episodes;decisions+=more
        manifest=json.loads((source/'value-calibration/data-manifest.json').read_text(encoding='utf-8'))
        picked={}
        for t in manifest['tasks']['fit']:picked.setdefault(t['metadata']['profile'],t)
        bank_tasks=[]
        for i,(profile,t) in enumerate(sorted(picked.items())):
            for branch in range(4):
                task=copy.deepcopy(t);task['replay_seed']=3_820_000_000+i*100+branch
                task['metadata'].update(search_enabled=True,prefix_id='probe-bank:'+profile,
                    branch_id=branch,fork_replicas=4,exploration_mode='normal')
                bank_tasks.append(task)
        bank_rows,bank_episodes,more=rollout_bank(pool,model,None,cfg,'cuda',len(bank_tasks),exploration,choose,
            tasks=bank_tasks,log_path=out/'episodes.jsonl')
        bank_groups=apply_bank_returns(bank_rows,bank_episodes,bank_tasks)
        rows.extend(bank_rows);all_episodes.extend(bank_episodes);decisions+=more
        penalty=apply_draft_penalty(rows,all_episodes)
        diagnostics=router.diagnostics()
    finally:
        router.close();pool.close();cfg.pop('_search_router',None)
    collection=time.monotonic()-start
    if len({r['profile'] for r in rows})!=5 or not fork_groups or len(bank_groups)!=5:
        raise ValueError('Incomplete joint/bank five-profile integration')
    truths=[r['return'] for r in rows]
    rates={name:info['optimizer_state']['param_groups'][i]['lr'] for i,name in enumerate(('exam','drink','draft','guidance','memory'))}
    optimizer=groups(model,rates);optimizer.load_state_dict(info['optimizer_state'])
    begin=time.monotonic();result=update(model,optimizer,rows,cfg,'cuda')
    if [r['return'] for r in rows]!=truths:raise ValueError('Real value targets changed')
    counts=result['signed_credit']['groups']['all_exam']
    if not counts.get('ppo_negative') or not counts.get('ppo_positive'):raise ValueError('No real signed learning evidence')
    if result['critic_update_coverage']['accepted_fraction']!=1. or not result['critic_completion']['actor_unchanged']:
        raise ValueError('Value completion failed')
    if not result['search_learning']['weighted_roots']:raise ValueError('No useful search learning directions')
    save(out/'probe-updated.pt',model,optimizer)
    loaded,_=load(out/'probe-updated.pt','cpu')
    assert all(torch.equal(v.cpu(),loaded.state_dict()[k]) for k,v in model.state_dict().items())
    report={'status':'passed','source_checkpoint_sha256':digest(checkpoint),'games':len(all_episodes),
        'joint_groups':len(fork_groups),'bank_groups':len(bank_groups),'records':len(rows),'decisions':decisions,
        'collection_seconds':collection,'update_seconds':time.monotonic()-begin,'search':diagnostics,
        'update':result,'checkpoint_roundtrip':True,'real_targets_preserved':True,
        'scope':'Fresh construction plus four-game continuations and fixed bank entries; one search root per game. Functional and gradient acceptance, not production score improvement.'}
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('status','games','joint_groups','bank_groups','records','collection_seconds','update_seconds')}
        | {'signs':counts,'search_learning':result['search_learning']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
