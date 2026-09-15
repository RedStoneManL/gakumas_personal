"""Opportunity denominators for public legal actions; no private observations."""
import copy
import json
from collections import Counter


def identity(command, row):
    command=copy.deepcopy(command)
    command.pop('decision_version',None)
    cards={c['instance_id']:c for c in (row.get('obs',{}).get('cards',[]))}
    if row.get('phase')=='guidance':
        cards.update({c['instance_id']:c for c in row['guidance'].entry['cards']})
    def normalize(x):
        if isinstance(x,dict):return {k:normalize(v) for k,v in x.items()}
        if isinstance(x,list):return [normalize(v) for v in x]
        if isinstance(x,str) and x in cards:
            c=cards[x]
            return {k:c[k] for k in ('definition_id','customizations','growth') if k in c}
        return x
    return json.dumps(normalize(command),sort_keys=True,ensure_ascii=False,separators=(',',':'))


class Coverage:
    def __init__(self,state=None):
        self.rows=copy.deepcopy(state or {})

    def observe(self,row,encoded,selected):
        group=row['profile']+'|'+row['phase']
        bucket=self.rows.setdefault(group,{})
        keys=[identity(c,row) for c in encoded.submissions]
        for key,count in Counter(keys).items():
            stat=bucket.setdefault(key,{'legal_opportunities':0,'selected':0})
            stat['legal_opportunities']+=count
        bucket[keys[selected]]['selected']+=1

    def summary(self):
        return {k:{'action_forms_seen':len(v),'never_selected':sum(s['selected']==0 for s in v.values()),
                   'legal_opportunities':sum(s['legal_opportunities'] for s in v.values())} for k,v in self.rows.items()}
