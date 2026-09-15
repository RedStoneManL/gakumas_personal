"""Whole-produce orchestration with explicit event/scoring policies and golden exams.

The master data owns produce rewards; the pinned engine owns examination actions.
Unmapped content and missing scoring inputs are errors, never legacy fallbacks.
"""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
import json
import unicodedata
from pathlib import Path

from ..engine.training import TrainingError, TrainingExam, make_training_entry
from ..scoring import resolve_hif_produce_scoring
from gakumas_rl.simulation.produce.events import ProduceEventLibrary
from gakumas_rl.simulation.produce.event_templates import ProduceEventTemplates

DATA = Path(__file__).resolve().parents[1] / '_vendor/gakumas_tools/packages/gakumas-data/json'
PLAN = {'ProducePlanType_Common': 'free', 'ProducePlanType_Plan1': 'sense',
        'ProducePlanType_Plan2': 'logic', 'ProducePlanType_Plan3': 'anomaly'}


class ProduceBridgeError(ValueError):
    pass


class GoldenProduceBridge:
    """Translate identities and supported carry effects, without executing exam rules."""

    def __init__(self, repository, *, id_overrides=None, enchant_overrides=None):
        self.repository = repository
        self.id_overrides = deepcopy(id_overrides or {})
        self.enchant_overrides = deepcopy(enchant_overrides or {})
        self.catalogues = {kind: json.loads((DATA / f'{file}.json').read_text(encoding='utf-8'))
                           for kind, file in [('card', 'skill_cards'), ('item', 'p_items'), ('drink', 'p_drinks')]}
        self.by_id = {kind: {r['id']: r for r in rows} for kind, rows in self.catalogues.items()}

    def definition_id(self, kind, row):
        upgrade = int(row.get('upgradeCount') or 0) if kind == 'card' else int(bool(row.get('isUpgraded')))
        key = f"{row['id']}@{upgrade}" if kind == 'card' else row['id']
        override = self.id_overrides.get(kind, {}).get(key)
        if override is not None:
            if override not in self.by_id[kind]:
                raise ProduceBridgeError(f'Unknown golden override: {kind}/{override}')
            return override
        name = unicodedata.normalize('NFKC', row['name']).rstrip('+')
        plan = PLAN.get(row.get('planType'), 'free')
        matches = [r for r in self.catalogues[kind] if unicodedata.normalize('NFKC', r['name']).rstrip('+') == name
                   and r.get('plan', 'free') == plan
                   and (kind == 'drink' or bool(r.get('upgraded')) == bool(upgrade))]
        if len(matches) != 1:
            raise ProduceBridgeError(f'Need explicit {kind} mapping for {key}: {[r["id"] for r in matches]}')
        return matches[0]['id']

    def _grow(self, grow_id):
        row = self.repository.load_table('ProduceCardGrowEffect').first(grow_id)
        if row is None:
            raise ProduceBridgeError(f'Missing growth effect: {grow_id}')
        mapping = {'LessonAdd': ('g.score', 1), 'LessonCountAdd': ('g.scoreTimes', 1),
                   'CostReduce': ('g.cost', -1), 'CostPenetrateReduce': ('g.typedCost', -1),
                   'BlockAdd': ('g.genki', 1), 'LessonBuffAdd': ('g.concentration', 1),
                   'ParameterBuffAdd': ('g.goodConditionTurns', 1),
                   'ReviewAdd': ('g.goodImpressionTurns', 1), 'AggressiveAdd': ('g.motivation', 1),
                   'FullPowerPointAdd': ('g.fullPowerCharge', 1)}
        kind = row['effectType'].removeprefix('ProduceCardGrowEffectType_')
        if kind not in mapping:
            raise ProduceBridgeError(f'Unmapped growth effect: {grow_id} ({kind})')
        field, sign = mapping[kind]
        return field, sign * float(row['value'])

    def _effect(self, effect_id):
        effect = self.repository.exam_effects.first(effect_id)
        if effect is None:
            raise ProduceBridgeError(f'Missing exam effect: {effect_id}')
        kind = effect['effectType'].removeprefix('ProduceExamEffectType_')
        fields = {'ExamLessonBuff': ('concentration', 'effectValue1'),
                  'ExamParameterBuff': ('goodConditionTurns', 'effectTurn'),
                  'ExamBlockFix': ('genki', 'effectValue1'), 'ExamReview': ('goodImpressionTurns', 'effectValue1'),
                  'ExamCardPlayAggressive': ('motivation', 'effectValue1'),
                  'ExamFullPowerPoint': ('fullPowerCharge', 'effectValue1'),
                  'ExamCardPlayCount': ('cardUsesRemaining', 'effectValue1')}
        if kind in fields:
            field, value = fields[kind]
            return f'{field}+={effect.get(value, 0)}'
        if kind == 'ExamAddGrowEffect' and effect.get('produceCardSearchId') == 'p_card_search-deck_all':
            assignments = [f'{field}+={value:g}' for field, value in
                           (self._grow(gid) for gid in effect['produceCardGrowEffectIds'])]
            return 'target:all { ' + '; '.join(assignments) + ' }'
        raise ProduceBridgeError(f'Unmapped exam carry effect: {effect_id} ({kind})')

    def enchant(self, spec, index):
        override = self.enchant_overrides.get(spec.enchant_id)
        if override is not None:
            return {'id': f'produce:{index}:{spec.enchant_id}', 'effects': override, 'counters': {}}
        if spec.effect_turn not in (None, 0) or spec.effect_count not in (None, 0, 1):
            raise ProduceBridgeError(f'Need explicit golden DSL for carry duration/count: {spec.enchant_id}')
        row = self.repository.exam_status_enchants.first(spec.enchant_id)
        if row is None:
            raise ProduceBridgeError(f'Missing carried enchant: {spec.enchant_id}')
        trigger = self.repository.exam_triggers.first(row['produceExamTriggerId'])
        if not trigger or trigger.get('phaseTypes') != ['ProduceExamPhaseType_ExamStartExam']:
            raise ProduceBridgeError(f'Need explicit golden DSL for enchant: {spec.enchant_id}')
        for field in ('fieldStatusCheckTypes', 'fieldStatusTypes', 'fieldStatusValues',
                      'fieldStatusProduceCardSearchIds', 'produceCardSearchId', 'effectTypes'):
            if trigger.get(field):
                raise ProduceBridgeError(f'Unmapped carry trigger condition: {spec.enchant_id}/{field}')
        actions = '; '.join(self._effect(e) for e in row.get('produceExamEffectIds') or ())
        return {'id': f'produce:{index}:{spec.enchant_id}',
                'effects': f'at:startOfStage {{ {actions}; limit:1 }}', 'counters': {}}

    def resolve_scoring(self, runtime, stage_type, config):
        try:
            return resolve_hif_produce_scoring(
                {'produce_id': runtime.scenario.produce_id, 'stage_type': stage_type,
                 'state': runtime.state}, config,
            )
        except (ValueError, TypeError, KeyError) as error:
            raise ProduceBridgeError(f'HIF scoring configuration: {error}') from error

    def entry(self, runtime, stage_type, config):
        config = self.resolve_scoring(runtime, stage_type, config)
        if 'score_percents' not in config:
            raise ProduceBridgeError('HIF requires resolved score_percents from the configured scoring provider')
        if 'turn_types' not in config:
            raise ProduceBridgeError('Each exam needs its own explicit turn_types')
        cards = []
        for index, row in enumerate(runtime.deck):
            growth = defaultdict(float)
            # apply_card_customizations has already replaced earlier cumulative levels.
            if row.get('customizedProduceCardCustomizeIds') and not row.get('growEffectIds'):
                raise ProduceBridgeError('Card customization is missing its resolved growEffectIds')
            for gid in row.get('growEffectIds') or ():
                field, value = self._grow(gid)
                growth[field] += value
            cards.append({'instance_id': row.get('instance_id') or f'produce-card:{index}',
                          'definition_id': self.definition_id('card', row), 'customizations': {},
                          'growth': dict(growth), 'bindings': deepcopy(row.get('golden_bindings', []))})
        p_items, native_enchants, basic_pool = [], set(), []
        for item in runtime.active_produce_items:
            row = self.repository.produce_items.first(item.item_id)
            if not row or not item.spec.is_exam_effect:
                continue
            native_id = self.definition_id('item', row)
            p_items.append(native_id)
            for effect in item.spec.effects:
                if effect.effect_type == 'ProduceItemEffectType_ExamStatusEnchant':
                    native_enchants.add((item.item_id, effect.enchant_id))
                    enchant = self.repository.exam_status_enchants.first(effect.enchant_id)
                    for eid in enchant.get('produceExamEffectIds') or ():
                        eff = self.repository.exam_effects.first(eid)
                        if eff.get('effectType') != 'ProduceExamEffectType_ExamCardCreateSearch':
                            continue
                        search = self.repository.load_table('ProduceCardSearch').first(eff['produceCardSearchId'])
                        pool = self.repository.load_table('ProduceCardPool').first(search.get('produceCardPoolId', ''))
                        if pool:
                            for card in pool['produceCardRatios']:
                                card_row = self.repository.card_row_by_upgrade(card['id'], card['upgradeCount'])
                                basic_pool.append(self.definition_id('card', card_row))
        carry = [self.enchant(spec, i) for i, spec in enumerate(runtime.exam_status_enchant_specs)
                 if (spec.source_identity, spec.enchant_id) not in native_enchants]
        plan = PLAN.get(runtime.idol_loadout.stat_profile.plan_type, 'sense') if runtime.idol_loadout else 'sense'
        entry = make_training_entry(
            cards, plan=plan, score_percents=config['score_percents'],
            max_stamina=int(runtime.state['max_stamina']), stamina=int(runtime._audition_start_stamina()),
            drinks=[self.definition_id('drink', row) for row in runtime.drinks],
            p_items=list(dict.fromkeys(p_items)), turn_types=config['turn_types'],
            basic_card_pool=config.get('basic_card_pool', list(dict.fromkeys(basic_pool))),
            stage_effects=config.get('stage_effects', ''),
            persistent_effects=carry + deepcopy(config.get('persistent_effects', [])),
            memory_abilities=deepcopy(config.get('memory_abilities', [])),
            preset=f'produce:{runtime.scenario.produce_id}:{stage_type}', family='master-produce+golden/1',
        )
        if config.get('scoring_provenance'):
            entry['source']['hif_scoring'] = deepcopy(config['scoring_provenance'])
        return entry


class TrainingProduce:
    """Drive a ProduceRuntime, executing examinations exclusively through TrainingExam.

    exam_config is a callable(state_context)->{score_percents,turn_types,rival_scores,...}.
    exam_policy sees public observations only; return a legal action or choice indices.
    Event scheduling and choice selection are supplied explicitly by the training caller.
    """

    def __init__(self, runtime, *, exam_config, exam_policy, event_schedule=None,
                 event_sampler=None, day_actions=None,
                 id_overrides=None, enchant_overrides=None, max_exam_decisions=2000):
        if runtime.scenario.hif is None:
            raise ProduceBridgeError('Whole-produce golden integration currently targets HIF')
        self.runtime = runtime
        self.exam_config = exam_config
        self.exam_policy = exam_policy
        self.event_schedule = deepcopy(event_schedule or {})
        self.event_sampler = event_sampler
        self.day_actions = deepcopy(day_actions or {})
        self.bridge = GoldenProduceBridge(runtime.repository, id_overrides=id_overrides,
                                           enchant_overrides=enchant_overrides)
        self.event_templates = ProduceEventTemplates(runtime.repository)
        self.max_exam_decisions = max_exam_decisions
        self.exam_history = []
        self.completed_scheduled_days = set()
        self.terminated = False
        self.fault = None
        self.revision = 0
        self._observation = None
        runtime.audition_executor = self._exam
        runtime.end_day_executor = self._schedule_events
        runtime.strict_produce_effects = True

    def _schedule_events(self, runtime):
        day = int(runtime.state['step'])
        if day in self.completed_scheduled_days:
            return
        event_ids = list(self.event_schedule.get(day, []))
        if self.event_sampler is not None:
            sampled = self.event_sampler({'day_index': day, 'state': deepcopy(runtime.state),
                                         'eligible_support_events': runtime.events.eligible_support_events()})
            event_ids.extend(sampled or [])
        for event in event_ids:
            if event == 'next_support':
                eligible = runtime.events.eligible_support_events()
                if eligible:
                    runtime.events.execute(eligible[0])
            else:
                runtime.events.execute(event)
        self.completed_scheduled_days.add(day)

    @property
    def event_library(self):
        return self.runtime.events.library

    def _exam(self, runtime, stage_type, *, apply_outcome):
        context = {'produce_id': runtime.scenario.produce_id, 'stage_type': stage_type,
                   'state': deepcopy(runtime.state), 'deck': deepcopy(runtime.deck),
                   'customize_item': runtime.customize_items.export()}
        config = self.bridge.resolve_scoring(runtime, stage_type, self.exam_config(context))
        if 'rival_scores' not in config:
            raise ProduceBridgeError('Provide rival_scores explicitly; no hidden legacy NPC simulation')
        entry = self.bridge.entry(runtime, stage_type, config)
        exam = TrainingExam(entry, seed=int(runtime.np_random.integers(0, 2**31 - 1)))
        obs = exam.observe()
        for _ in range(self.max_exam_decisions):
            if obs['result']['terminated']:
                break
            decision = self.exam_policy(deepcopy(obs))
            obs = (exam.choose(decision, decision_version=obs['decision_version']) if obs['choice']
                   else exam.act(decision))
        if not obs['result']['terminated'] or obs['result']['final_score'] is None:
            raise ProduceBridgeError('Golden exam did not terminate; no score/reward label was generated')
        score = obs['result']['final_score']
        rivals = list(config['rival_scores'])
        rank = 1 + sum(r > score for r in rivals)
        profile = runtime.repository.battle_profile(runtime.scenario, stage_type)
        rank_threshold = int(config.get('rank_threshold', profile['rank_threshold']))
        rival_ids = config.get('rival_ids', [f'rival:{i}' for i in range(len(rivals))])
        extra = runtime.hif.adjust_audition_result(stage_type=stage_type, effective_score=score,
            rival_scores=rivals, rival_character_ids=rival_ids, rank=rank, rank_threshold=rank_threshold)
        available_drinks = list(runtime.drinks)
        remaining_drinks = []
        for native_id in obs['drinks']:
            index = next((i for i, row in enumerate(available_drinks)
                          if self.bridge.definition_id('drink', row) == native_id), None)
            if index is None:
                raise ProduceBridgeError(f'Cannot reverse-map remaining drink {native_id}')
            remaining_drinks.append(available_drinks.pop(index))
        result = {'stage_type': stage_type, 'exam_score': score, 'effective_score': score,
                  'cleared': rank <= rank_threshold, 'rank': rank, 'rank_threshold': rank_threshold,
                  'rival_scores': rivals, 'rival_character_ids': rival_ids, 'turns': len(config['turn_types']),
                  'exam_backend': 'gakumas-tools', 'scoring_source': config.get('scoring_source', 'configured_percent'),
                  'exam_carry': {'stamina': obs['state']['stamina'], 'drinks': remaining_drinks}, **extra}
        if config.get('scoring_provenance'):
            result['scoring_provenance'] = deepcopy(config['scoring_provenance'])
        runtime.state['stamina'] = result['exam_carry']['stamina']
        runtime.drinks = deepcopy(remaining_drinks)
        runtime._dispatch_produce_item_phase('ProducePhaseType_EndAudition')
        result['exam_carry'] = {'stamina': runtime.state['stamina'], 'drinks': deepcopy(runtime.drinks)}
        if apply_outcome:
            runtime.state['stamina'] = result['exam_carry']['stamina']
            runtime.state['last_exam_score'] = score
        self.exam_history.append({'entry': entry, 'snapshot': exam.snapshot(), 'result': deepcopy(result)})
        return (1.0 if result['cleared'] else -1.0), result

    def observe(self):
        if self._observation is not None:
            return deepcopy(self._observation)
        rt = self.runtime
        actions = [] if self.terminated or self.fault else [
            {'index': i, 'decision_version': self.revision, **asdict(c)}
            for i, c in enumerate(rt.legal_actions()) if c.available]
        allowed = self.day_actions.get(int(rt.state['step'])) if rt.pre_audition_phase == 'weekly' else None
        if allowed is not None and not self.terminated and not self.fault:
            actions = [a for a in actions if a['action_type'] in allowed or a['auto_skip']]
            if not actions:
                raise ProduceBridgeError(f'Configured day has no legal action: {rt.state["step"]}')
        for action in actions:
            event_id = action.get('event_detail_id')
            if event_id and self.event_library.details.first(event_id):
                action['event_template_id'] = self.event_templates.template_id(event_id)
                action['event_family_id'] = self.event_templates.template_id(event_id, parameterize_hif_pools=True)
        self._observation = {'schema_version': 'arena-public-produce/1', 'decision_version': self.revision,
                'state': deepcopy(rt.state), 'actions': actions, 'phase': rt.pre_audition_phase,
                'deck': deepcopy(rt.deck), 'drinks': deepcopy(rt.drinks),
                'customize_item': rt.customize_items.export(),
                'eligible_support_events': rt.events.eligible_support_events(),
                'terminated': self.terminated, 'fault': deepcopy(self.fault), 'exam_backend': 'gakumas-tools',
                'sampling_scope': {'menu': 'configured' if self.day_actions else 'legacy_candidate_menu',
                    'events': 'configured', 'official_event_probabilities': False,
                    'hif_outing_reward_table': 'master_activity_templates',
                    'hif_outing_reward_pool_distribution': 'legacy_approximation',
                    'lesson_card_reward_distribution': 'legacy_approximation'}}
        return deepcopy(self._observation)

    def act(self, action):
        observation = self.observe()
        if self.terminated or action not in observation['actions']:
            raise ProduceBridgeError('Submit a current legal produce action')
        try:
            reward, self.terminated, info = self.runtime.step(action['index'])
        except Exception as error:
            self.fault = {'type': type(error).__name__, 'message': str(error), 'normal_terminal': False}
            self.revision += 1
            self._observation = None
            raise
        self.revision += 1
        self._observation = None
        return {'observation': self.observe(), 'reward': reward, 'info': info}

    def export_run(self):
        """Export records for diagnosis/replay; callbacks are not serialized as checkpoints."""
        return {'schema_version': 'arena-produce-run/1', 'produce_id': self.runtime.scenario.produce_id,
                'state': deepcopy(self.runtime.state), 'terminated': self.terminated, 'fault': deepcopy(self.fault),
                'choices': deepcopy(self.runtime.produce_choice_history),
                'events': deepcopy(self.runtime.events.history), 'exams': deepcopy(self.exam_history),
                'customize_item': self.runtime.customize_items.export()}


def create_training_produce(*, scenario='hif_final', loadout=None, seed=0,
                           exam_config, exam_policy, produce_choice_selector=None, selection_memory=None, **kwargs):
    from ..env import make_produce_env
    env = make_produce_env(scenario=scenario, loadout=loadout, seed=seed)
    runtime = env.runtime
    runtime.produce_choice_selector = produce_choice_selector
    if selection_memory is not None:
        if runtime.hif is None or not runtime.hif.is_final:
            raise ProduceBridgeError('Selection memory belongs to HIF final')
        runtime.hif.selection_memory = selection_memory
    runtime.reset()
    return TrainingProduce(runtime, exam_config=exam_config, exam_policy=exam_policy, **kwargs)


__all__ = ['TrainingProduce', 'create_training_produce', 'GoldenProduceBridge',
           'ProduceBridgeError', 'ProduceEventLibrary']
