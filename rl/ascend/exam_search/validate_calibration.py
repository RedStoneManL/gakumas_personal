"""Bounded live-data calibration rehearsal on a frozen checkpoint."""
import argparse
import copy
import json
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena')]


def settings():
    return {'quantiles':32,'objective_k':4,'distribution_coefficient':1.,
            'research_manifest':str(ROOT/'rl/experiments/research-playgrounds-20260915/manifest.json'),
            'train_replicas':12,'eval_replicas':8,'states_per_game':8,
            'epochs':10,'steps_per_epoch':24,'batch_per_profile':16,'learning_rate':.0005}


def main():
    import torch
    from draftrl.checkpoint import load,save,digest,source_version
    from draftrl.runner import choose
    from draftrl.migration import groups
    from draftrl.duplicate_limits import family_ids
    from draftrl.value_calibration import calibrate
    from r1rl.environment import Workers
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--checkpoint',default='snapshot-0009.pt');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2);torch.cuda.set_per_process_memory_fraction(.25)
    model,info=load(args.source/args.checkpoint,'cuda');model.eval()
    cfg=copy.deepcopy(info['training_config'])
    cfg.update(workers=8,value_calibration=settings(),_calibration_source_info=info,
               _policy_version='critic-rehearsal:'+digest(args.source/args.checkpoint),
               _profiles=json.loads((HERE/'setup/profiles.json').read_text(encoding='utf-8')))
    cfg['_card_families']=family_ids(json.loads((HERE/'setup/catalog.json').read_text(encoding='utf-8')))
    optimizer=groups(model,dict.fromkeys(('exam','drink','draft','guidance','memory'),.0005))
    optimizer.load_state_dict(info['optimizer_state'])
    model.enable_quantiles(32,optimizer)
    def publish(event,**details):
        text={'event':event,**details};print(json.dumps(text,ensure_ascii=False),flush=True)
        (args.output/'progress.json').write_text(json.dumps(text,ensure_ascii=False,indent=2),encoding='utf-8')
    pool=Workers(8,HERE/'runtime/arena',info['arena_sha256'])
    try:
        report=calibrate(pool,model,optimizer,cfg,'cuda',args.source,args.output,choose,publish)
        metadata={k:v for k,v in info.items() if k not in ('model_state','model_config','model_schema','encoding',
                    'optimizer_state','python_rng','torch_rng','cuda_rng','created_at','rl_source_sha256')}
        metadata['calibration_report']=report
        save(args.output/'calibrated.pt',model,optimizer,**metadata)
        print(json.dumps({'status':report['status'],'actor_unchanged':report['actor_unchanged'],
            'before':report['before']['macro_best4_mae'],'after':report['after']['macro_best4_mae'],
            'output':str(args.output)},ensure_ascii=False),flush=True)
    finally:pool.close()


if __name__=='__main__':main()
