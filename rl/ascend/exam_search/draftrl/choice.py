"""Sequential public card selection; commit to Arena only when selection ends.

The policy factorizes ordered choices into conditional picks. For unordered
choices a canonical increasing order gives each subset exactly one path.
Neither Arena state nor RNG advances between these policy substeps.
"""
import copy
from r1rl.encoding import encode_exam


class ChoiceState:
    def __init__(self, observation):
        self.obs=observation
        self.choice=observation['choice']
        self.selected=[]
        self.done=False
        self.options={r['index']:r for r in self.choice['candidates']}
        if not 0<=self.choice['min']<=self.choice['max']<=len(self.options):
            raise ValueError('Invalid choice cardinality')

    def remaining(self):
        options=sorted(set(self.options)-set(self.selected))
        if not self.choice.get('ordered',False):
            options=[i for i in options if not self.selected or i>self.selected[-1]]
            need=max(0,self.choice['min']-len(self.selected)-1)
            if need:options=options[:-need]
        return options

    def commands(self):
        if self.done:return []
        out=[]
        if len(self.selected)<self.choice['max']:
            out=[{'method':'choice_append','index':i} for i in self.remaining()]
        if len(self.selected)>=self.choice['min']:out.append({'method':'choice_finish'})
        if not out:raise ValueError('Choice factorization produced a dead end')
        return out

    def encode(self):
        view=copy.deepcopy(self.obs)
        c=view['choice']
        c['candidates']=[self.options[i] for i in self.remaining()]
        c['original_min']=self.choice['min'];c['original_max']=self.choice['max']
        c['policy_selected_cards']=[self.options[i]['instance_id'] for i in self.selected]
        c['selection_protocol']='sequential_public_selection'
        c['min']=0 if len(self.selected)>=self.choice['min'] else 1
        c['max']=1 if len(self.selected)<self.choice['max'] and c['candidates'] else 0
        e=encode_exam(view)
        e.submissions=[({'method':'choice_append','index':cmd['indices'][0]} if cmd['indices']
                        else {'method':'choice_finish'}) for cmd in e.submissions]
        assert all(cmd in self.commands() for cmd in e.submissions)
        return e

    def apply(self,command):
        if command not in self.commands():raise ValueError('Illegal partial card selection')
        if command['method']=='choice_append':self.selected.append(command['index'])
        if command['method']=='choice_finish' or len(self.selected)==self.choice['max']:
            self.done=True
            return {'method':'choose','indices':list(self.selected),'decision_version':self.obs['decision_version']}
        return None
