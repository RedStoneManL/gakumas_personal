"""Bounded pre-opening loadout reservoir, not an old-action PPO replay buffer."""
import copy
import hashlib
import json
import math
import random
from collections import Counter


class SampleBank:
    SCHEMA='arena-preopening-reservoir/2'
    # Old actions, likelihoods, RNG seeds and observations are never retained.
    FIELDS=('profile','plan','scenario','general_scenario','course_id','drink_capacity',
            'drink_supply','memory_mode','memory_capacity','condition_cell','benchmark_cell',
            'score_scale','drinks','selected_memories','initial_sleep_count','selected_cards',
            'deck_size','physical_deck_size','support_card_count','support_card_limit',
            'exclude_prima_stella','exempt_card_count','guidance_budget','policy_turn_visibility')

    def __init__(self, profiles, contract, capacity_per_profile=64, seed=911902, state=None):
        if type(capacity_per_profile) is not int or capacity_per_profile<1:
            raise ValueError('bank capacity must be a positive integer')
        self.profiles=list(profiles);self.contract=contract;self.capacity=capacity_per_profile
        self.rng=random.Random(seed);self.cursor=0;self.replay_counter=0
        self.rows={p:[] for p in self.profiles};self.seen=Counter();self.revisits=0
        self.sampling_config={};self.policy_version='unversioned';self.batch=0
        if state is not None:self.restore(state)

    @staticmethod
    def key(entry):
        return hashlib.sha256(json.dumps(entry,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

    def add(self, summary):
        if summary.get('sampling_source')!='joint':
            raise ValueError('Only freshly trained joint episodes may populate the bank')
        profile=summary['profile']
        if profile not in self.rows:raise ValueError('unknown bank profile')
        score=float(summary['normalized_score'])
        if not math.isfinite(score):raise ValueError('bank score must be finite')
        entry=copy.deepcopy(summary['entry'])
        allowed={'schema_version','preset','source','context','cards','resources','p_items','memory_abilities','persistent_effects'}
        if set(entry)-allowed:raise ValueError('bank only accepts a public pre-opening entry')
        key=self.key(entry);bucket=self.rows[profile]
        for existing in bucket:
            if existing['key']==key:
                self.feedback(key,score);return
        row={'key':key,'entry':entry,'metadata':{k:copy.deepcopy(summary[k]) for k in self.FIELDS},
             'mean_score':score,'observations':1}
        self._observe(row,score)
        # Per-profile reservoir admits newly encountered nonresident loadouts.
        self.seen[profile]+=1
        if len(bucket)<self.capacity:bucket.append(row)
        else:
            index=self.rng.randrange(self.seen[profile])
            if index<self.capacity:bucket[index]=row

    def sample(self,count):
        if type(count) is not int or count<0:raise ValueError('invalid bank draw count')
        available=[p for p in self.profiles if self.rows[p]]
        out=[]
        if not available:return out
        for _ in range(count):
            profile=available[self.cursor%len(available)];self.cursor+=1
            rows=self.rows[profile]
            # Balance available drink/memory conditions before selecting quality.
            conditions=sorted({r['metadata']['condition_cell'] for r in rows})
            condition=self.rng.choice(conditions)
            eligible=sorted((r for r in rows if r['metadata']['condition_cell']==condition),key=lambda r:r['mean_score'])
            # Half uniform, one quarter lower tail, one quarter upper tail.
            # These are within-profile sampled performance strata, not card tiers.
            stratum=self.rng.randrange(4);tail=max(1,(len(eligible)+3)//4)
            candidates=eligible if stratum<2 else eligible[:tail] if stratum==2 else eligible[-tail:]
            if self.sampling_config.get('enabled',False):
                if stratum<2:
                    selected=self.rng.choice(eligible)
                elif stratum==2:
                    weights=[1+max(0,self.batch-r.get('last_seen_batch',0)) for r in eligible]
                    selected=self.rng.choices(eligible,weights=weights,k=1)[0]
                else:
                    weights=[self.learning_priority(r) for r in eligible]
                    selected=(self.rng.choices(eligible,weights=weights,k=1)[0]
                              if any(weights) else self.rng.choice(eligible))
                row=copy.deepcopy(selected)
            else:
                row=copy.deepcopy(self.rng.choice(candidates))
            row['replay_seed']=1_500_000_000+self.replay_counter
            self.replay_counter+=1;self.revisits+=1;out.append(row)
        return out

    def configure(self,config,policy_version,batch):
        self.sampling_config=dict(config);self.policy_version=policy_version;self.batch=batch

    @staticmethod
    def learning_priority(row):
        windows=list(row.get('by_version',{}).values())
        reliable=[w for w in windows if w['count']>=2]
        if len(reliable)<2:return 0.0
        a,b=reliable[-2:]
        se=math.sqrt(a['m2']/max(1,a['count']-1)/a['count']+b['m2']/max(1,b['count']-1)/b['count'])
        return min(3.0,max(0.0,abs(a['mean']-b['mean'])-2*se)/max(0.1,abs(a['mean'])))

    def _observe(self,row,score):
        row['last_seen_batch']=self.batch
        versions=row.setdefault('by_version',{})
        stats=versions.setdefault(self.policy_version,{'count':0,'mean':0.0,'m2':0.0})
        stats['count']+=1;delta=score-stats['mean'];stats['mean']+=delta/stats['count']
        stats['m2']+=delta*(score-stats['mean'])
        while len(versions)>8:del versions[next(iter(versions))]

    def feedback(self,key,normalized_score):
        if not math.isfinite(normalized_score):raise ValueError('nonfinite bank feedback')
        for bucket in self.rows.values():
            for row in bucket:
                if row['key']==key:
                    row['observations']+=1
                    row['mean_score']+=(normalized_score-row['mean_score'])/row['observations']
                    self._observe(row,normalized_score)
                    return

    def describe(self):
        return {'size':sum(map(len,self.rows.values())),
                'per_profile':{k:len(v) for k,v in self.rows.items()},
                'capacity_per_profile':self.capacity,'revisits':self.revisits,
                'next_replay_seed':1_500_000_000+self.replay_counter,
                'versioned_entries':sum(bool(r.get('by_version')) for rows in self.rows.values() for r in rows),
                'learning_candidates':sum(self.learning_priority(r)>0 for rows in self.rows.values() for r in rows),
                'sampling':'uniform50-stale25-learning25' if self.sampling_config.get('enabled') else 'uniform50-low25-high25'}

    def state_dict(self):
        return copy.deepcopy({'schema':self.SCHEMA,'contract':self.contract,'profiles':self.profiles,
            'capacity':self.capacity,'rows':self.rows,'seen':dict(self.seen),'rng':self.rng.getstate(),
            'cursor':self.cursor,'replay_counter':self.replay_counter,'revisits':self.revisits})

    def restore(self,state):
        if state['schema'] not in (self.SCHEMA,'arena-preopening-reservoir/1') or (state['contract'],state['profiles'],state['capacity'])!=(self.contract,self.profiles,self.capacity):
            raise ValueError('bank contract, profiles or capacity mismatch')
        if set(state['rows'])!=set(self.profiles):raise ValueError('bank profiles mismatch')
        for profile,rows in state['rows'].items():
            if len(rows)>self.capacity:raise ValueError('bank exceeds capacity')
            for row in rows:
                if row['metadata']['profile']!=profile or self.key(row['entry'])!=row['key']:
                    raise ValueError('bank entry identity mismatch')
        self.rows=copy.deepcopy(state['rows']);self.seen=Counter(state['seen'])
        self.rng.setstate(state['rng']);self.cursor=state['cursor']
        self.replay_counter=state['replay_counter'];self.revisits=state['revisits']
