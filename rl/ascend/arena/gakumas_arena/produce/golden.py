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
CARD_ID_ALIASES = {'p_card-00-sup-2_028':242, 'p_card-00-sup-3_155':586,
                   'p_card-02-ido-3_086':464, 'p_card-02-ido-3_165':729}
# The pinned native catalogue spells this support item 測定器, while master
# data calls it 測定機. Both define Dance-turn start + Preservation -> recover
# 5 stamina once per exam; this is an identity alias, not an effect override.
ITEM_ID_ALIASES = {'pitem_03-3-068-0': 174,
                   # Master ぴったし / native ぴったり: Visual active-card use,
                   # good condition >=3 -> concentration+2 and score+4, once.
                   'pitem_01-3-305-0': 380}


class ProduceBridgeError(ValueError):
    pass


def _check_carry_fields(row, allowed):
    """Do not translate the supported part while silently dropping a chain/count.

    Master rows contain many inactive defaults. Active fields outside the exact
    carry translation must be implemented explicitly or rejected at this bridge.
    """
    cosmetic = {'id', 'assetId', 'effectGroupIds'}
    for key, value in row.items():
        if key in allowed or key in cosmetic or 'description' in key.lower():
            continue
        if value in (None, '', 0, False) or value == []:
            continue
        if isinstance(value, str) and value.endswith('_Unknown'):
            continue
        raise ProduceBridgeError(f'Unmapped active carry field: {row.get("id")}/{key}: {value!r}')


class GoldenProduceBridge:
    """Translate identities and supported carry effects, without executing exam rules."""

    def __init__(self, repository, *, id_overrides=None, enchant_overrides=None):
        self.repository = repository
        self.id_overrides = deepcopy(id_overrides or {})
        self.enchant_overrides = deepcopy(enchant_overrides or {})
        self.catalogues = {kind: json.loads((DATA / f'{file}.json').read_text(encoding='utf-8'))
                           for kind, file in [('card', 'skill_cards'), ('item', 'p_items'), ('drink', 'p_drinks')]}
        from ..engine.catalogue_overrides import apply_catalogue_overrides
        self.catalogues['card'] = apply_catalogue_overrides(self.catalogues['card'])
        self.by_id = {kind: {r['id']: r for r in rows} for kind, rows in self.catalogues.items()}
        self.native_customizations = {r['id']: r for r in
                                      json.loads((DATA / 'customizations.json').read_text(encoding='utf-8'))}
        self.last_customization_provenance = []

    def definition_id(self, kind, row):
        upgrade = int(row.get('upgradeCount') or 0) if kind == 'card' else int(bool(row.get('isUpgraded')))
        key = f"{row['id']}@{upgrade}" if kind == 'card' else row['id']
        override = self.id_overrides.get(kind, {}).get(key)
        if override is not None:
            if override not in self.by_id[kind]:
                raise ProduceBridgeError(f'Unknown golden override: {kind}/{override}')
            return override
        if kind == 'card' and row['id'] in CARD_ID_ALIASES:
            return CARD_ID_ALIASES[row['id']] + int(bool(upgrade))
        if kind == 'item' and row['id'] in ITEM_ID_ALIASES:
            return ITEM_ID_ALIASES[row['id']]
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
                   'CostReduce': ('g.cost', 1), 'CostPenetrateReduce': ('g.typedCost', 1),
                   # Native typed costs subtract positive growth from the cost
                   # RHS (matching customization IDs 30-35 and 104).
                   'CostParameterBuffReduce': ('g.typedCost', 1),
                   'CostLessonBuffReduce': ('g.typedCost', 1),
                   'CostReviewReduce': ('g.typedCost', 1),
                   'CostAggressiveReduce': ('g.typedCost', 1),
                   'CostFullPowerPointReduce': ('g.typedCost', 1),
                   'CostParameterBuffMultiplePerTurnReduce': ('g.typedCost', 1),
                   'BlockAdd': ('g.genki', 1), 'LessonBuffAdd': ('g.concentration', 1),
                   'ParameterBuffAdd': ('g.goodConditionTurns', 1),
                   'ParameterBuffTurnAdd': ('g.goodConditionTurns', 1),
                   'ParameterBuffMultiplePerTurnAdd': ('g.perfectConditionTurns', 1),
                   'StaminaConsumptionDownTurnAdd': ('g.halfCostTurns', 1),
                   'ReviewAdd': ('g.goodImpressionTurns', 1), 'AggressiveAdd': ('g.motivation', 1),
                   'FullPowerPointAdd': ('g.fullPowerCharge', 1)}
        kind = row['effectType'].removeprefix('ProduceCardGrowEffectType_')
        if kind not in mapping:
            raise ProduceBridgeError(f'Unmapped growth effect: {grow_id} ({kind})')
        field, sign = mapping[kind]
        return field, sign * float(row['value'])

    def _native_growth_customization(self, grow_id, card_id):
        """Structural additions use actual native customizations, not scalar growth."""
        if grow_id != 'g_effect-effect_add-e_effect-exam_lesson-0006-01':
            return None
        grow = self.repository.load_table('ProduceCardGrowEffect').first(grow_id) or {}
        effect = self.repository.exam_effects.first('e_effect-exam_lesson-0006-01') or {}
        if (grow.get('effectType') != 'ProduceCardGrowEffectType_EffectAdd'
                or grow.get('playProduceExamEffectId') != effect.get('id')
                or grow.get('playMovePositionType') != 'ProduceCardMovePositionType_Unknown'
                or effect.get('effectType') != 'ProduceExamEffectType_ExamLesson'
                or effect.get('effectValue1') != 6 or effect.get('effectCount') != 1
                or any(grow.get(k) for k in ('value', 'playProduceExamTriggerId',
                    'playEffectProduceExamTriggerId', 'targetPlayEffectProduceExamTriggerIds',
                    'targetPlayProduceExamEffectIds', 'produceCardStatusEnchantId'))
                or any(effect.get(k) for k in ('effectValue2', 'effectTurn', 'targetProduceCardId',
                    'produceCardSearchId', 'produceCardSearchId2', 'chainProduceExamEffectId',
                    'chainProduceExamEffectIds', 'produceExamStatusEnchantId',
                    'produceCardStatusEnchantId', 'produceCardGrowEffectIds'))):
            raise ProduceBridgeError(f'Structural customization master mismatch: {grow_id}')
        native = self.native_customizations.get(3, {})
        if (native.get('actions') != 'score+=6' or native.get('max') != 1
                or any(native.get(k) != '' for k in ('forceInitialHand', 'conditions', 'cost', 'limit', 'effects'))):
            raise ProduceBridgeError(f'Structural customization native mismatch: {grow_id}/3')
        available = str(self.by_id['card'][card_id].get('availableCustomizations', '')).split(',')
        if '3' not in available:
            raise ProduceBridgeError(f'Native card {card_id} does not support score-add customization 3')
        return 3

    def _effect(self, effect_id):
        effect = self.repository.exam_effects.first(effect_id)
        if effect is None:
            raise ProduceBridgeError(f'Missing exam effect: {effect_id}')
        kind = effect['effectType'].removeprefix('ProduceExamEffectType_')
        fields = {'ExamLessonBuff': ('concentration', 'effectValue1'),
                  'ExamParameterBuff': ('goodConditionTurns', 'effectTurn'),
                  'ExamBlockFix': ('fixedGenki', 'effectValue1'), 'ExamReview': ('goodImpressionTurns', 'effectValue1'),
                  'ExamCardPlayAggressive': ('motivation', 'effectValue1'),
                  'ExamFullPowerPoint': ('fullPowerCharge', 'effectValue1'),
                  'ExamCardPlayCount': ('cardUsesRemaining', 'effectValue1')}
        if kind in fields:
            field, value = fields[kind]
            _check_carry_fields(effect, {'effectType', value})
            return f'{field}+={effect.get(value, 0)}'
        if kind == 'ExamAddGrowEffect' and effect.get('produceCardSearchId') == 'p_card_search-deck_all':
            _check_carry_fields(effect, {'effectType', 'produceCardSearchId', 'produceCardGrowEffectIds', 'pickRangeType'})
            if effect.get('pickRangeType') not in (None, '', 'ProducePickRangeType_Unknown', 'ProducePickRangeType_All'):
                raise ProduceBridgeError(f'Unmapped carry pickRangeType: {effect_id}')
            assignments = [f'{field}+={value:g}' for field, value in
                           (self._grow(gid) for gid in effect['produceCardGrowEffectIds'])]
            return 'target:all { ' + '; '.join(assignments) + ' }'
        raise ProduceBridgeError(f'Unmapped exam carry effect: {effect_id} ({kind})')

    def enchant(self, spec, index):
        override = self.enchant_overrides.get(spec.enchant_id)
        if override is not None:
            return {'id': f'produce:{index}:{spec.enchant_id}', 'effects': override, 'counters': {}}
        from .memory_bridge import try_hif_memory_enchant, HifMemoryBridgeError
        try:
            declaration = try_hif_memory_enchant(self.repository, spec, self.definition_id)
        except HifMemoryBridgeError as error:
            raise ProduceBridgeError(str(error)) from error
        if declaration is not None:
            return declaration
        if spec.effect_turn not in (None, 0) or spec.effect_count not in (None, 0, 1):
            raise ProduceBridgeError(f'Need explicit golden DSL for carry duration/count: {spec.enchant_id}')
        row = self.repository.exam_status_enchants.first(spec.enchant_id)
        if row is None:
            raise ProduceBridgeError(f'Missing carried enchant: {spec.enchant_id}')
        _check_carry_fields(row, {'produceExamTriggerId', 'produceExamEffectIds'})
        trigger = self.repository.exam_triggers.first(row['produceExamTriggerId'])
        if not trigger or trigger.get('phaseTypes') != ['ProduceExamPhaseType_ExamStartExam']:
            raise ProduceBridgeError(f'Need explicit golden DSL for enchant: {spec.enchant_id}')
        _check_carry_fields(trigger, {'phaseTypes'})
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
        runtime.ensure_deck_instance_ids()
        cards = []
        self.last_customization_provenance = []
        from .customization_bridge import resolve_customizations
        for index, row in enumerate(runtime.deck):
            growth = defaultdict(float)
            native_id = self.definition_id('card', row)
            try:
                customizations, residual_growth, provenance = resolve_customizations(
                    self.repository, row, self.by_id['card'][native_id], self.native_customizations)
            except ValueError as error:
                raise ProduceBridgeError(f"Card {row['id']}: {error}") from error
            self.last_customization_provenance.extend(
                {'instance_id': row['instance_id'], **record} for record in provenance)
            # Applied green levels are evaluated by the golden card compiler.
            # Only unrelated permanent growth remains in the scalar channel.
            for gid in residual_growth:
                native_custom = self._native_growth_customization(gid, native_id)
                if native_custom is not None:
                    if str(native_custom) in customizations:
                        raise ProduceBridgeError(f'Duplicate structural customization: {gid}')
                    customizations[str(native_custom)] = 1
                    continue
                field, value = self._grow(gid)
                growth[field] += value
            cards.append({'instance_id': row['instance_id'],
                          'definition_id': native_id, 'customizations': customizations,
                          'growth': dict(growth), 'bindings': deepcopy(row.get('golden_bindings', []))})
        p_items, native_enchants, basic_pool = [], set(), []
        baton_ids = {427, 428, 429, 430, 440, 441}
        baton_pools = {}
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
                        if native_id in baton_ids:
                            random_pool_id = search.get('produceCardRandomPoolId', '')
                            pool_rows = self.repository.load_table('ProduceCardRandomPool').all(random_pool_id)
                            if not pool_rows:
                                raise ProduceBridgeError(f'Missing HIF baton weighted pool: {item.item_id}/{random_pool_id}')
                            weighted = {}
                            for card in pool_rows:
                                card_row = self.repository.card_row_by_upgrade(card['produceCardId'], card['upgradeCount'])
                                native_card_id = self.definition_id('card', card_row)
                                weighted[native_card_id] = weighted.get(native_card_id, 0) + card['ratio']
                            if native_id in baton_pools and baton_pools[native_id] != weighted:
                                raise ProduceBridgeError(f'Conflicting HIF baton pools: {item.item_id}')
                            baton_pools[native_id] = weighted
                            continue
                        pool = self.repository.load_table('ProduceCardPool').first(search.get('produceCardPoolId', ''))
                        if pool:
                            for card in pool['produceCardRatios']:
                                card_row = self.repository.card_row_by_upgrade(card['id'], card['upgradeCount'])
                                basic_pool.append(self.definition_id('card', card_row))
        if len(set(p_items) & baton_ids) > 1:
            raise ProduceBridgeError('Multiple HIF baton colors are not a legal loadout')
        if 'basic_card_pool' in config:
            resolved_basic_pool = config['basic_card_pool']
            # Explicit custom pools never inherit unrelated master weights.
            resolved_basic_weights = config.get('basic_card_weights')
        elif baton_pools:
            weighted = next(iter(baton_pools.values()))
            resolved_basic_pool = list(weighted)
            resolved_basic_weights = config.get('basic_card_weights', list(weighted.values()))
        else:
            resolved_basic_pool = list(dict.fromkeys(basic_pool))
            resolved_basic_weights = config.get('basic_card_weights')
        carry = [self.enchant(spec, i) for i, spec in enumerate(runtime.exam_status_enchant_specs)
                 if (spec.source_identity, spec.enchant_id) not in native_enchants]
        from .memory_bridge import deduplicate_hif_memory_declarations
        carry = deduplicate_hif_memory_declarations(carry)
        plan = PLAN.get(runtime.idol_loadout.stat_profile.plan_type, 'sense') if runtime.idol_loadout else 'sense'
        from .support_bridge import build_skill_card_support
        skill_support = build_skill_card_support(runtime, self.definition_id, config.get('skill_card_support_settings'))
        entry = make_training_entry(
            cards, plan=plan, score_percents=config['score_percents'],
            max_stamina=int(runtime.state['max_stamina']), stamina=int(runtime._audition_start_stamina()),
            drinks=[self.definition_id('drink', row) for row in runtime.drinks],
            p_items=list(dict.fromkeys(p_items)), turn_types=config['turn_types'],
            basic_card_pool=resolved_basic_pool, basic_card_weights=resolved_basic_weights,
            skill_card_support=skill_support if skill_support['sources'] else None,
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
        from .lifecycle import HifProduceLifecycle
        self.lifecycle = HifProduceLifecycle(self, getattr(runtime, 'hif_research_config', {}).get('lifecycle'))
        runtime.hif_lifecycle = self.lifecycle

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
        customization_provenance = deepcopy(self.bridge.last_customization_provenance)
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
                  'rival_scores': rivals, 'rival_character_ids': rival_ids,
                  'configured_turns': len(config['turn_types']), 'turns': int(obs['state']['turnsElapsed']),
                  'extra_turns': max(0, int(obs['state']['turnsElapsed'])-len(config['turn_types'])),
                  'exam_backend': 'gakumas-tools', 'scoring_source': config.get('scoring_source', 'configured_percent'),
                  'exam_carry': {'stamina': obs['state']['stamina'], 'drinks': remaining_drinks}, **extra}
        if customization_provenance:
            result['customization_bridge'] = customization_provenance
        if getattr(runtime, 'hif_ruleset_version', None):
            from .courses import audition_rewards
            by_color = obs['result']['score_by_color']
            if abs(sum(by_color.values())-score) > 1e-6:
                raise ProduceBridgeError('Golden color ledger does not reconcile with raw score')
            result.update(audition_rewards(runtime, stage_type, score, by_color))
        if config.get('course_provenance'):
            result['course_provenance'] = deepcopy(config['course_provenance'])
        if config.get('scoring_provenance'):
            result['scoring_provenance'] = deepcopy(config['scoring_provenance'])
        runtime.state['stamina'] = result['exam_carry']['stamina']
        runtime.drinks = deepcopy(remaining_drinks)
        runtime.customize_items.complete_audition()
        runtime._dispatch_produce_item_phase('ProducePhaseType_EndAudition')
        result['exam_carry'] = {'stamina': runtime.state['stamina'], 'drinks': deepcopy(runtime.drinks)}
        if apply_outcome:
            runtime.state['stamina'] = result['exam_carry']['stamina']
            runtime.state['last_exam_score'] = score
        self.lifecycle.after_attempt(result)
        self.exam_history.append({'entry': entry, 'snapshot': exam.snapshot(), 'result': deepcopy(result)})
        return (1.0 if result['cleared'] else -1.0), result

    def observe(self):
        if self._observation is not None:
            return deepcopy(self._observation)
        rt = self.runtime
        actions = [] if self.terminated or self.fault else [
            {'index': i, 'decision_version': self.revision, **asdict(c)}
            for i, c in enumerate(rt.legal_actions()) if c.available]
        if not self.lifecycle.can_retry():
            actions = [a for a in actions if a['action_type'] != 'audition_retry']
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
        if getattr(rt, 'hif_sampling_kernel', None) is not None:
            self._observation['sampling_scope'] = {**rt.hif_sampling_kernel.public_contract(),
                'menu':'report3-V-fixed-schedule', 'support_event_model':rt.hif_research_config.get('support_event_model','configured'),
                'sp_joint_model':'independent-marginals-placeholder', 'sp_base_rate':rt.hif.config.open_lesson_sp_base_rate,
                'sub_stat_model':rt.hif.config.open_lesson_sub_parameter_policy,
                'numeric_model':'floor-parameter-per-gain; floor-hp-points-at-decision/v1-planning',
                'rollout_ruleset':rt.hif_ruleset_version}
            self._observation['sampling_scope']['step_skip_availability_model'] = rt.hif_research_config.get('step_skip_availability_model')
        self._observation['lifecycle'] = self.lifecycle.public_state()
        self._observation['produce_items'] = [asdict(item) for item in rt.active_produce_items]
        self._observation['support_skills'] = [asdict(item) for item in rt.active_produce_skills]
        self._observation['exam_enchants'] = [asdict(spec) for spec in rt.exam_status_enchant_specs]
        if self.terminated and getattr(rt, 'hif_ruleset_version', None):
            self._observation['memory_products'] = self.memory_products()
        return deepcopy(self._observation)

    def act(self, action):
        observation = self.observe()
        if self.terminated or action not in observation['actions']:
            raise ProduceBridgeError('Submit a current legal produce action')
        try:
            with self.lifecycle.atomic_step():
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
                'customize_item': self.runtime.customize_items.export(),
                'lifecycle': self.lifecycle.public_state(),
                'memory_products': self.memory_products() if self.terminated and getattr(self.runtime, 'hif_ruleset_version', None) else None,
                'courses': deepcopy(getattr(self.runtime, 'hif_course_history', [])),
                'support_occurrence': deepcopy(getattr(self.runtime.events, 'occurrence_history', [])),
                'ruleset': getattr(self.runtime, 'hif_ruleset_version', 'legacy-produce'),
                'sampling': deepcopy(getattr(getattr(self.runtime, 'hif_sampling_kernel', None), 'history', []))}

    def memory_products(self):
        """Deterministic terminal products. Does not consume the produce RNG."""
        from .memory_generation import generate_hif_memory_products
        if not self.terminated or self.fault:
            raise ProduceBridgeError('Memory products require a normal terminal produce')
        return generate_hif_memory_products(self.runtime,
            seed=getattr(self.runtime, 'hif_memory_seed', 0),
            config=getattr(self.runtime, 'hif_research_config', {}).get('memory_generation'))

    def abandon(self, reason='policy_abandon'):
        self.lifecycle.abandon(reason=reason)
        return self.observe()

    def snapshot(self):
        """JSON-safe decision checkpoint for workers; contains hidden RNG, not policy input."""
        from .checkpoint import snapshot
        return snapshot(self)

    def restore_snapshot(self, data):
        """Restore into a run constructed with the same configuration and callbacks."""
        from .checkpoint import restore_into
        return restore_into(self, data)


def create_training_produce(*, scenario='hif_final', loadout=None, seed=0,
                           exam_config=None, exam_policy, produce_choice_selector=None, selection_memory=None,
                           research_profile=None, **kwargs):
    from ..env import make_produce_env
    from .loadout_handoff import freeze_loadout, handoff_loadout
    loadout = handoff_loadout(scenario, loadout, selection_memory)
    env = make_produce_env(scenario=scenario, loadout=loadout, seed=seed)
    runtime = env.runtime
    runtime.hif_loadout_config = freeze_loadout(scenario, loadout, runtime.idol_loadout)
    runtime.produce_choice_selector = produce_choice_selector
    if research_profile is not None:
        from .research import install_hif_research_profile, hif_day_actions
        research_profile = deepcopy(research_profile)
        if selection_memory is not None and 'growth_panel_levels' not in research_profile:
            research_profile['growth_panel_levels'] = deepcopy(selection_memory.metadata.get('growth_panel_levels',{}))
        if selection_memory is not None and 'card_switches' not in research_profile:
            research_profile['card_switches'] = deepcopy(selection_memory.metadata.get('card_switches',{}))
        install_hif_research_profile(runtime, research_profile)
        kwargs.setdefault('day_actions',hif_day_actions(runtime.hif.is_final,
            enable_step_skip=research_profile.get('enable_step_skip',False)))
        if research_profile.get('_install_support_sampler'):
            runtime.hif_research_config['support_event_model'] = 'configured-occurrence-with-permyriad-adjustments/v1'
            kwargs['event_sampler'] = runtime.events.sample_support_events
    if selection_memory is not None:
        if runtime.hif is None or not runtime.hif.is_final:
            raise ProduceBridgeError('Selection memory belongs to HIF final')
        runtime.hif.selection_memory = selection_memory
    runtime.strict_produce_effects = True
    runtime.reset()
    runtime.hif_memory_seed = int(seed)
    if research_profile is not None and selection_memory is None:
        from .card_switches import normalize_initial_deck
        normalize_initial_deck(runtime)
    if exam_config is None:
        if research_profile is None:
            raise ProduceBridgeError('Legacy produce requires exam_config; recommended HIF profile supplies five courses')
        from .courses import default_exam_config
        exam_config = lambda context: default_exam_config(runtime, context)
    return TrainingProduce(runtime, exam_config=exam_config, exam_policy=exam_policy, **kwargs)


__all__ = ['TrainingProduce', 'create_training_produce', 'GoldenProduceBridge',
           'ProduceBridgeError', 'ProduceEventLibrary']
