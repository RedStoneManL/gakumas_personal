"""Permit only the requested Ultra preset and the pending decision schedule."""
import copy
from .exploration_migration import make_decision_config, validate_change


def make_config(source, decisions, snapshot, decay_decisions):
    target=(make_decision_config(source,decisions,snapshot,decay_decisions)
            if source.get('exploration_schedule',{}).get('basis')=='elapsed_minutes'
            else copy.deepcopy(source))
    target['resource_mode']='ultra'
    validate_config(source,target,decisions=decisions,snapshot=snapshot)
    return target


def validate_config(source,target,*,decisions=None,snapshot=None):
    if target.get('resource_mode') != source.get('resource_mode') and target.get('resource_mode')!='ultra':
        raise ValueError('Only the requested Ultra default is authorized')
    aligned=copy.deepcopy(target)
    if 'resource_mode' in source:aligned['resource_mode']=source['resource_mode']
    else:aligned.pop('resource_mode',None)
    result=validate_change(source,aligned,decisions=decisions,snapshot=snapshot)
    return {'exploration_change':result,'resource_mode':{'old':source.get('resource_mode'),'new':target.get('resource_mode')}}
