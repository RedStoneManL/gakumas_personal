from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
import math

from ...contracts import Episode
from ...arena_adapter import DecisionRecorder, MasterMechanisms, choose_exam
from ...arena_adapter.mechanisms import mechanical


@dataclass
class FullProduceConfig:
    loadout: dict = field(default_factory=lambda: {
        'idol_card_id': 'i_card-amao-1-000', 'idol_rank': 4, 'auto_support_cards': False})
    research_config: dict = field(default_factory=dict)
    max_outer_decisions: int = 1000
    max_exam_decisions: int = 2000
    early_terminal_policy: str = 'final_formula_zero_unplayed_v1'
    # Each entry owns its COMPLETE loadout/research config. There is no nested
    # merge with the single-loadout fields. Consecutive seeds rotate evenly.
    loadout_pool: list[dict] | None = None
    setup_mode: str = 'given'
    setup_inventory: dict | None = None


def terminal_rating(artifact: dict, *, scenario: str, early_terminal_policy: str) -> tuple[float, dict]:
    """Read actual final evaluation; early failure mapping is explicitly named.

    The zero-unplayed policy is a training-contract extension to Arena's final
    formula, NOT a claim that the game awards this rating on selection failure.
    """
    if not artifact.get('normal_terminal'):
        raise ValueError('Engine faults cannot become terminal rewards')
    summary = artifact['summary']
    if scenario == 'hif_final':
        result = summary['produce_result']
        value = result['formula_detail']['rating']
        if float(value) != float(result['score']):
            raise ValueError('Final rating fields disagree')
        provenance = {'field': 'summary.produce_result.formula_detail.rating',
                      'formula_source': result.get('formula_source'), 'early_terminal_mapping': False}
    else:
        if early_terminal_policy != 'final_formula_zero_unplayed_v1':
            raise ValueError('Selection failure requires an explicit supported early_terminal_policy')
        from gakumas_arena.produce.courses import final_rating
        state = artifact['state']
        # Selection exams are never substituted for either final-round score.
        detail = final_rating([state[c] for c in ('vocal', 'dance', 'visual')],
                              state['star_quality'], 0, 0)
        value = detail['rating']
        provenance = {'field': 'explicit_early_terminal_mapping',
                      'formula_source': detail['formula_source'], 'early_terminal_mapping': True,
                      'policy': early_terminal_policy, 'formula_detail': detail,
                      'game_awarded_rating_verified': False}
    if not math.isfinite(value):
        raise ValueError('Non-finite final produce evaluation')
    return float(value), provenance


class FullProduceTask:
    name = 'full_produce'

    def __init__(self, config: FullProduceConfig | None = None, *, arena_root=None):
        from ...arena_adapter.environment import ensure_arena
        self.arena_root = ensure_arena(arena_root)
        self.config = config or FullProduceConfig()
        if min(self.config.max_outer_decisions, self.config.max_exam_decisions) < 1:
            raise ValueError('Decision limits must be positive')
        if self.config.setup_mode not in ('given', 'select', 'mixed'):
            raise ValueError('setup_mode must be given, select or mixed')
        if self.config.setup_mode != 'given' and not isinstance(self.config.setup_inventory, dict):
            raise ValueError('Selectable setup requires an explicit setup_inventory')
        pool = self.config.loadout_pool
        if pool is not None:
            if not isinstance(pool, list) or not pool:
                raise ValueError('loadout_pool must be a nonempty list or null')
            names = set()
            for entry in pool:
                if not isinstance(entry, dict) or set(entry) - {'name', 'loadout', 'research_config'}:
                    raise ValueError('Invalid loadout_pool entry fields')
                if not isinstance(entry.get('name'), str) or not entry['name'] or entry['name'] in names:
                    raise ValueError('loadout_pool names must be nonempty and unique')
                if not isinstance(entry.get('loadout'), dict) or not entry['loadout'].get('idol_card_id'):
                    raise ValueError('Every loadout_pool entry requires a complete loadout with idol_card_id')
                if not isinstance(entry.get('research_config', {}), dict):
                    raise ValueError('Pool research_config must be a dictionary')
                names.add(entry['name'])
        self._mechanisms = None
        self._setup_catalog = None

    def select_profile(self, seed):
        """Pure deterministic sampling; never consumes training or Arena RNG."""
        if self.config.loadout_pool is None:
            return ('single_loadout', deepcopy(self.config.loadout),
                    deepcopy(self.config.research_config))
        entry = self.config.loadout_pool[seed % len(self.config.loadout_pool)]
        return entry['name'], deepcopy(entry['loadout']), deepcopy(entry.get('research_config', {}))

    def select_setup_mode(self, seed):
        """Alternate whole profile cycles so each idol sees both setup modes."""
        if self.config.setup_mode != 'mixed':
            return self.config.setup_mode
        count = len(self.config.loadout_pool) if self.config.loadout_pool is not None else 1
        return 'select' if (seed // count) % 2 else 'given'

    @property
    def arena_version(self):
        from ...arena_adapter.environment import arena_version
        return arena_version(self.arena_root)

    def close(self):
        from ...arena_adapter.environment import close_arena
        close_arena()

    def run_episode(self, policy, *, seed: int, policy_version: int) -> Episode:
        from gakumas_arena.env import get_repository
        from gakumas_arena.produce import create_hif_training_produce
        from gakumas_arena.produce.public_state import live_public_state
        from gakumas_arena.produce.courses import exam_profiles
        from gakumas_arena.produce.research import hif_day_actions
        from gakumas_arena.produce.loadout_handoff import thaw_loadout
        if self._mechanisms is None:
            self._mechanisms = MasterMechanisms(get_repository())
        profile_name, loadout, research_config = self.select_profile(seed)
        recorder = DecisionRecorder(self.name, policy, policy_version)
        runs, memory, current = [], None, {'run': None, 'parent_action': None, 'scenario': 'hif_selection'}
        profiles = exam_profiles()
        idol = get_repository().load_table('IdolCard').first(loadout['idol_card_id'])
        if idol is None:
            raise ValueError(f'Unknown idol_card_id in profile {profile_name}: {loadout["idol_card_id"]}')
        course_options = research_config.get('courses', {})
        character_id = course_options.get('character_id', idol['characterId'])
        idol_profile = next((row for row in profiles['idols'] if row['character_id'] == character_id), None)
        if idol_profile is None and course_options.get('profile_character_id'):
            idol_profile = next((row for row in profiles['idols']
                                 if row['character_id'] == course_options['profile_character_id']), None)
        if idol_profile is None:
            raise ValueError(f'No pinned HIF course profile for {character_id}')
        rules = {
            'courses': [{k: v for k, v in row.items() if k not in ('source_ids', 'day_note', 'label')}
                        for row in profiles['stages']],
            'idol_exam_profile': idol_profile,
            'final_rating': profiles['production_rating_model'],
            'selection_schedule': hif_day_actions(False, enable_step_skip=research_config.get('enable_step_skip', False)),
            'final_schedule': hif_day_actions(True, enable_step_skip=research_config.get('enable_step_skip', False)),
            'research_config': deepcopy(research_config),
        }
        setup_mode = self.select_setup_mode(seed)
        setup_metadata = {'mode': 'given'}
        if setup_mode == 'select':
            from .setup import select_setup_loadout, resolve_setup_catalog
            if self._setup_catalog is None:
                self._setup_catalog = resolve_setup_catalog(get_repository(), self.config.setup_inventory)
            loadout, setup_metadata = select_setup_loadout(loadout, self.config.setup_inventory,
                recorder, get_repository(), rules=rules, resolved_catalog=self._setup_catalog)
        # Resolve the policy's complete kit before any opening effects execute.
        # JSON arrays are normalized into Arena's hashable typed input.
        normalized_loadout = thaw_loadout(loadout)

        def context(produce, *, exam=None, resolution=None, candidates=()):
            public = mechanical(produce)
            public['scenario'] = current['scenario']
            public['rules'] = rules
            resolution = deepcopy(resolution or {})
            resolution['parent_action'] = deepcopy(current['parent_action'])
            return {'produce': public, 'exam': deepcopy(exam), 'resolution': resolution,
                    'mechanisms': self._mechanisms.closure(public, candidates)}

        def produce_choice(request):
            candidates = [dict(index=i, option=mechanical(option))
                          for i, option in enumerate(request['options'])]
            observation = context(request['public_state'], resolution={
                'kind': request['kind'], 'context': request['context'],
                'execution': request['public_state'].get('resolution', {})}, candidates=candidates)
            return recorder.select('produce_choice', observation, candidates)['index']

        def exam_policy(observation):
            run = current['run']
            if run is None:
                raise RuntimeError('Exam callback fired before produce construction completed')
            produce = live_public_state(run.runtime)
            return choose_exam(recorder, observation, lambda resolution: context(
                produce, exam=observation, resolution=resolution))

        for stage, scenario in enumerate(('hif_selection', 'hif_final')):
            current.update(run=None, parent_action=None, scenario=scenario)
            run = recorder.transaction(lambda: create_hif_training_produce(
                scenario=scenario, loadout=deepcopy(normalized_loadout), seed=(seed + stage) % (2**32),
                selection_memory=memory, research_config=deepcopy(research_config),
                exam_policy=exam_policy, produce_choice_selector=produce_choice,
                max_exam_decisions=self.config.max_exam_decisions))
            current['run'] = run
            for _ in range(self.config.max_outer_decisions):
                outer = run.observe()
                if outer['terminated']:
                    break
                def execute_outer():
                    produce = {**live_public_state(run.runtime),
                               'sampling_scope': deepcopy(outer['sampling_scope'])}
                    action = recorder.select('outer', context(produce, candidates=outer['actions']), outer['actions'])
                    current['parent_action'] = deepcopy(action)
                    try:
                        return run.act(action)
                    finally:
                        current['parent_action'] = None
                recorder.transaction(execute_outer)
            if not run.terminated or run.fault:
                raise RuntimeError('Produce exceeded decision limit or faulted; no terminal sample generated')
            artifact = run.lifecycle.terminal_artifact()
            runs.append({'scenario': scenario, 'terminal': artifact,
                         'sampling_scope': deepcopy(run.observe()['sampling_scope'])})
            if scenario == 'hif_selection':
                if run.lifecycle.status != 'selection_clear':
                    break
                memory = run.runtime.export_hif_selection_memory()
        last = runs[-1]
        score, provenance = terminal_rating(last['terminal'], scenario=last['scenario'],
                                            early_terminal_policy=self.config.early_terminal_policy)
        from gakumas_rl.idol_config import memory_spec_from_gift
        final_memory_specs = [asdict(memory_spec_from_gift(get_repository(), m) if isinstance(m, str) else m)
                              for m in normalized_loadout.memories]
        return Episode(self.name, seed, recorder.transitions, score, last['terminal']['outcome'], {
            'objective': 'raw_final_produce_rating/1', 'policy_version': policy_version,
            'loadout_profile': profile_name,
            'setup_mode': setup_mode, 'setup': setup_metadata,
            'selected_support_ids': list(loadout.get('support_card_ids', ())),
            'selected_memory_ids': [m.memory_id if not isinstance(m, str) else m
                                    for m in normalized_loadout.memories],
            'selected_memory_specs': final_memory_specs,
            'rating_provenance': provenance, 'runs': runs,
            'completed_scenarios': [r['scenario'] for r in runs],
            'accepted_exam_count': sum(len(r['terminal']['accepted_exams']) for r in runs),
        })
