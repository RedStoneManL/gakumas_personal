"""Runnable HIF report-3 profile: deterministic rules plus declared planning assumptions."""
from copy import deepcopy
from dataclasses import replace

RULESET_VERSION = 'hif-report3/2'
STATS = ('vocal','dance','visual')
SCHOOL = tuple('school_class_'+s for s in STATS)
OPEN = tuple('lesson_'+s+'_open' for s in STATS)
STAR = tuple('lesson_'+s+'_open_star' for s in STATS)


def hif_day_actions(final=False, *, enable_step_skip=False):
    """Zero-based runtime day mapping; examination days are automatic boundary actions."""
    selection = {
        1:('consult','activity_supply','hif_special_training'),2:STAR,3:SCHOOL,4:OPEN,
        5:('outing','consult'),6:SCHOOL,7:('refresh',),8:('outing','activity_supply'),9:STAR,
        10:SCHOOL,11:OPEN,12:('consult','hif_special_training'),13:('refresh',),
        14:('outing','activity_supply'),15:STAR,16:('outing','consult','activity_supply'),
        17:SCHOOL,18:OPEN,19:('consult','hif_special_training'),20:('refresh',)}
    main = {1:SCHOOL,2:STAR,3:('outing','activity_supply'),4:SCHOOL,5:OPEN,
            6:('consult',),7:('refresh',),8:('hif_interval',),9:('refresh',)}
    result = main if final else selection
    menu = {day-1: list(actions if day in ({7,9} if final else {7,13,20}) else (*actions,'refresh'))
            for day,actions in result.items()}
    if enable_step_skip:
        for day, actions in menu.items():
            if day not in ({6,7,8} if final else {6,12,19}):
                actions.append('step_skip')
    return menu


def install_hif_research_profile(runtime, config=None):
    from .sampling import HifSamplingKernel
    from gakumas_rl.simulation.produce.hif_interval import HifIntervalShop, HifSpecialTraining
    config = deepcopy(config or {})
    runtime.hif_ruleset_version = RULESET_VERSION
    runtime.hif_research_config = config
    from .card_switches import install_card_switches
    install_card_switches(runtime, config.get('card_switches'))
    runtime.hif_step_skip_days = tuple(day for day, actions in hif_day_actions(
        runtime.hif.is_final, enable_step_skip=True).items() if 'step_skip' in actions)
    if config.get('enable_step_skip', False):
        runtime.scenario = replace(runtime.scenario, action_types=tuple(dict.fromkeys(
            (*runtime.scenario.action_types, 'step_skip'))))
        config['step_skip_availability_model'] = 'opt-in-non-exam-non-interval-days/planning-v1'
    else:
        config['step_skip_availability_model'] = 'disabled-no-HIF-menu-evidence'
    runtime.hif.config = replace(runtime.hif.config,
        open_lesson_sp_base_rate=float(config.get('sp_base_rate',0.10)),
        open_lesson_sub_parameter_policy=config.get('sub_stat_policy','lowest'),
        growth_panel_levels=deepcopy(config.get('growth_panel_levels',runtime.hif.config.growth_panel_levels)))
    runtime.hif_sampling_kernel = HifSamplingKernel(runtime, config.get('pools'))
    runtime.customize_item_reward_selector = runtime.hif_sampling_kernel
    runtime.hif_interval_shop = HifIntervalShop(runtime)
    runtime.hif_special_training = HifSpecialTraining(runtime)
    runtime.hif_interval_refresh_prices = tuple(config.get('interval_refresh_prices',(10,10,20,30,40,50)))
    if not runtime.hif_interval_refresh_prices or any(p<0 for p in runtime.hif_interval_refresh_prices):
        raise ValueError('Invalid interval refresh price profile')


def create_hif_training_produce(*, research_config=None, **kwargs):
    """Recommended RL entry. Pass exam_policy and a produce-choice selector.

    exam_config is optional: omission selects the five default HIF courses.
    research_config overrides pools, SP assumptions, growth panels and interval prices.
    A support-event sampler can be supplied; default daily selection is explicitly a
    planning assumption and only chooses legally unlocked support events.
    """
    from .golden import create_training_produce
    if kwargs.get('produce_choice_selector') is None:
        raise ValueError('RL HIF profile requires produce_choice_selector for internal player choices')
    config = deepcopy(research_config or {})
    if kwargs.get('selection_memory') is not None and 'card_switches' not in config:
        config['card_switches'] = deepcopy(kwargs['selection_memory'].metadata.get('card_switches', {}))
    if 'event_sampler' not in kwargs:
        probability = float(config.get('support_event_probability',0.25))
        if not 0 <= probability <= 1:
            raise ValueError('Support event probability must be between 0 and 1')
        # Install after runtime construction so all environmental randomness uses its RNG.
        config['_install_support_sampler'] = True
    run = create_training_produce(research_profile=config, **kwargs)
    if config.get('_install_support_sampler'):
        run.event_sampler = run.runtime.events.sample_support_events
        run.runtime.hif_research_config['support_event_model'] = 'configured-occurrence-with-permyriad-adjustments/v1'
    if config.get('enable_step_skip') and 'day_actions' not in kwargs:
        run.day_actions = hif_day_actions(run.runtime.hif.is_final, enable_step_skip=True)
    return run
