"""Only the user's soft-budget search and distributional value calibration."""
import copy

SEARCH_SETTINGS={'root_selection':'soft_budget','soft_floor':.25,'soft_temperature':.8,'soft_min_visits':2}


def validate_config(source,target):
    old=copy.deepcopy(source);new=copy.deepcopy(target)
    cfg=new.pop('value_calibration',None)
    old_cfg=old.pop('value_calibration',None)
    if old_cfg is not None and old_cfg!=cfg:raise ValueError('Calibration configuration drift')
    if not isinstance(cfg,dict) or cfg.get('quantiles')!=32 or cfg.get('objective_k')!=4:
        raise ValueError('Explicit 32-quantile Best4 calibration required')
    for key,value in SEARCH_SETTINGS.items():
        if new.get('search',{}).get(key)!=value:raise ValueError('Unaudited soft allocation parameter')
        new['search'].pop(key)
        old['search'].pop(key,None)
    if old!=new:raise ValueError('Soft-value continuation changed unrelated settings')
    return {'soft_search':SEARCH_SETTINGS,'value_calibration':cfg}
