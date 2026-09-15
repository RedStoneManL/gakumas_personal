"""Actual calibrated checkpoint + isolated public-history search acceptance."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena')]


def main():
    import torch
    from draftrl.checkpoint import load,digest
    from draftrl.search_service import SearchService
    from gakumas_arena.engine.search import SearchClient
    torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.15)
    checkpoint=ROOT/'rl/experiments/soft-value-20260915/calibration9/calibrated.pt'
    model,_=load(checkpoint,'cuda')
    manifest=json.loads((ROOT/'rl/experiments/research-playgrounds-20260915/manifest.json').read_text())
    tasks=[]
    with SearchClient(max_worlds=4) as client:
        lives=[];histories=[]
        for i,did in enumerate(('A01','A04')):
            task=next(t for t in manifest['tasks'] if t['metadata']['research_deck_id']==did)
            exam=client.create_recorded_exam(task['entry'],seed=3_700_000_000+i)
            history=exam.export_public_history();lives.append(exam);histories.append(history)
            tasks.append({'entry':task['entry'],'history':history,'score_scale':task['metadata']['score_scale'],
                'policy_version':'calibrated-probe:'+digest(checkpoint),'search_seed':3_710_000_000+i,
                'simulations':32,'particles':8,'seconds':60.,'sampling_ms':10000,'native_action_budget':60000,
                'max_depth':12,'rollout_steps':8,'objective_k':4,'root_selection':'soft_budget',
                'soft_floor':.25,'soft_temperature':.8,'soft_min_visits':2})
        with SearchService(model,'cuda',parallel_roots=2,inference_batch=4) as service:
            results=service.search_many(tasks)
        for exam,history in zip(lives,histories):
            assert exam.export_public_history()==history
            exam.close()
    passed=all(r['valid_training_target'] and r['search']['root_value_best4'] is not None
               and min(r['search']['root_visits'])>=2 for r in results)
    report={'status':'passed' if passed else 'failed','checkpoint_sha256':digest(checkpoint),
            'recorder_unchanged':True,'actual_calibrated_model':True,'roots':results}
    (ROOT/'rl/experiments/soft-value-20260915/calibrated-search.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'roots':[{'status':r['status'],
        'visits':(r.get('search') or {}).get('root_visits'),'cost':(r.get('search') or {}).get('cost')} for r in results]}),flush=True)
    if not passed:raise RuntimeError('Calibrated search probe failed')


if __name__=='__main__':main()
