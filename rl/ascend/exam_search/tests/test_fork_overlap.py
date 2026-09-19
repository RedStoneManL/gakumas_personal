"""Real two-rank rendezvous with controlled search completion and replay ownership."""
import copy
from collections import Counter
from datetime import timedelta
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch
import torch.distributed as dist
import torch.multiprocessing as mp

from draftrl.fork_overlap import ForkOverlap, enabled, seed_interval, signatures
from draftrl.distributed import LearnerGroup, seed_rank
from draftrl.practice import make_fork_tasks, apply_fork_returns, auxiliary_controller
from test_joint_search import example


def config():
    return dict(seed=133,search=dict(enabled=True,execution_mode='auxiliary',fork_episodes=False),
                practice={'forks':dict(enabled=True,replicas=4,every_n_per_profile=1,objective='best_of_k')},
                _policy_version='overlap:0',_profiles=[{}],train_seed_base=100)


def parents(rank, cfg):
    return [dict(seed=100+rank*10+i,profile='test',sampling_source='joint',policy_version='overlap:0',
                 normalized_score=2.,action_rng_seed=200+rank*10+i,score=2.,entry={'cards':[]},
                 entry_sha256='same',score_scale=1.,search_enabled=True,origin_rank=rank,
                 controller_contract=auxiliary_controller(cfg)) for i in range(rank+1)]


def records(summaries):
    return [dict(encoded=example(phase),episode_id='joint:'+str(s['seed']),
                 action=0,old_logp=-.75,old_value=.5,**{'return':2.}) for s in summaries for phase in [2,0]]


class Flow:
    auxiliary=True
    def __init__(self, rows):
        self.pending={};self._unbound={};self._auxiliary={1:True}
        self.rows=rows;self.release=False;self.polls=0
    def poll(self,wait=False):
        self.polls+=1
        if self.release:
            self.rows[1]['search_aux']={'ownership_marker':'original-exam'}
            self._auxiliary.clear()
        if wait:time.sleep(.001)
        return []
    def drain(self):
        self.release=True;self.poll()
    def assert_drained(self):
        if self._auxiliary:raise RuntimeError('Unfinished search')


def fake_replay(*args,tasks,background=None,**kwargs):
    if background is not None:
        assert background.__self__.flow._auxiliary
        assert '_search_router' not in args[3]
        background()
    rows=[];summaries=[]
    for task in tasks:
        meta=task['metadata'];score=3.+float(torch.rand(()))
        summaries.append({**meta,'seed':task['replay_seed'],'normalized_score':score,'score':score,
                          'entry_sha256':'same'})
        rows.append(dict(encoded=example(0),prefix_id=meta['prefix_id'],branch_id=meta['branch_id'],
                         episode_id='fork_exam:'+str(task['replay_seed']),action=0,old_logp=-.2,
                         old_value=.5,**{'return':score}))
    return rows,summaries,len(rows)


def plain(rows):
    return [{**{k:v for k,v in r.items() if k!='encoded'},'phase':r['encoded'].phase} for r in rows]


def run_rank(rank,rendezvous):
    torch.set_num_threads(1)
    dist.init_process_group('gloo',init_method='file://'+rendezvous,rank=rank,world_size=2,timeout=timedelta(seconds=20))
    try:
        mesh=object.__new__(LearnerGroup);mesh.rank=rank;mesh.size=2;mesh.device=torch.device('cpu')
        cfg=config();own=parents(rank,cfg);rows=records(own);flow=Flow(rows)
        router=SimpleNamespace(service=SimpleNamespace(stats=Counter()),progress=None)
        overlap=ForkOverlap(mesh,None,None,cfg,None,1000,None,router)
        torch.manual_seed(771+rank);rng=torch.get_rng_state()
        if rank:time.sleep(.08)
        with patch('draftrl.bank_rollout.rollout_bank',side_effect=fake_replay):
            overlap.before_drain(rows,own,flow)
        assert flow._auxiliary,'Replay must precede search completion in this fixture'
        try:overlap.credit(rows,own)
        except RuntimeError:pass
        else:raise AssertionError('Peer credit ran before labels completed')
        flow.drain();overlap.credit(rows,own);result=overlap.gather()
        after=torch.get_rng_state()
        all_parents=parents(0,cfg)+parents(1,cfg)
        global_tasks,next_seed=make_fork_tasks(all_parents,cfg,1000)
        assert result['signatures']==signatures(global_tasks) and result['next_seed']==next_seed
        # Compare unchanged peer credit and exact action RNG against serial replay.
        torch.set_rng_state(rng)
        if rank:seed_rank(cfg,'cpu',rank,'fork')
        reference=records(own);reference[1]['search_aux']={'ownership_marker':'original-exam'}
        rr,ss,_=fake_replay(None,None,None,cfg,tasks=overlap.tasks)
        stats=apply_fork_returns(reference,own,rr,ss,expected_tasks=overlap.tasks,objective='best_of_k')
        assert plain(rows)==plain(reference) and stats==overlap.stats
        assert torch.equal(after,torch.get_rng_state())
        assert rows[1]['action']==0 and rows[1]['old_logp']==-.75
        if rank==0:
            mesh.overlap_forks=result
            with patch.object(mesh,'broadcast',side_effect=AssertionError('Replayed forks twice')):
                answer=mesh.fork_rollout(None,None,None,cfg,global_tasks,None,records=rows,summaries=all_parents,objective='best_of_k')
            assert answer[2]==9 and mesh.overlap_forks is None
            mesh.overlap_forks={**result,'policy_version':'stale'}
            try:mesh.fork_rollout(None,None,None,cfg,global_tasks,None,records=rows,summaries=all_parents,objective='best_of_k')
            except RuntimeError:pass
            else:raise AssertionError('Stale prefetched policy accepted')
        dist.barrier()
        # A failed collector still matches the count collective on every peer.
        overlap=ForkOverlap(mesh,None,None,cfg,None,1000,None,None)
        if rank:
            overlap.ensure_handshake()
        else:
            try:overlap.before_drain(records(own),own,Flow(records(own)))
            except RuntimeError:pass
            else:raise AssertionError('Failed peer admitted to fork replay')
        assert overlap.handshake
    finally:
        dist.destroy_process_group()


class ForkOverlapTests(unittest.TestCase):
    def test_rank_intervals_include_empty_ranks(self):
        self.assertEqual(seed_interval(71,[3,0,6],0),(71,80))
        self.assertEqual(seed_interval(71,[3,0,6],1),(74,80))
        self.assertEqual(seed_interval(71,[3,0,6],2),(74,80))
        with self.assertRaises(ValueError):seed_interval(1,[True],0)
    def test_only_auxiliary_without_fork_search_is_eligible(self):
        cfg=config()
        with patch.dict(os.environ,{'GAKUMAS_FORK_OVERLAP':'1'}):
            self.assertTrue(enabled(cfg,10))
            for field,value in [('execution_mode','act'),('fork_episodes',True),('enabled',False),('auxiliary_async',False)]:
                other=copy.deepcopy(cfg);other['search'][field]=value;self.assertFalse(enabled(other,10))
        with patch.dict(os.environ,{'GAKUMAS_FORK_OVERLAP':'0'}):self.assertFalse(enabled(cfg,10))
    def test_actual_two_rank_ownership_rng_and_failed_rendezvous(self):
        with tempfile.TemporaryDirectory(prefix='fork-overlap-') as folder:
            mp.spawn(run_rank,args=(str(Path(folder)/'rendezvous'),),nprocs=2,join=True)


if __name__=='__main__':unittest.main()
