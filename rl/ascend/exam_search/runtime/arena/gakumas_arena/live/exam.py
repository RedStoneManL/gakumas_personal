"""HIF センス考试：只装配绝对事实，复用引擎合法性和编码，不推进游戏。"""

from __future__ import annotations

import hashlib
import math
from collections import Counter, deque
from typing import Any

import numpy as np
from pydantic import Field, TypeAdapter, ValidationError

from gakumas_rl.idol_config import build_idol_loadout
from gakumas_rl.simulation.envs import ActionView, GakumasExamEnv
from gakumas_rl.simulation.exam.choice_boundary import UnsupportedSelection, card_selection_boundary
from gakumas_rl.simulation.exam.ids import ExamEffect, FieldStatus
from gakumas_rl.simulation.exam.observed_encoding import (
    encode_exam_observation,
    exam_encoder_manifest,
)
from gakumas_rl.simulation.exam.runtime import ExamRuntime, RuntimeCard, TimedExamEffect

from .contracts import EntityRef, Observation, RunSetup, WireModel
from .passive import prepare_passives
from .planning import PlanningBackend
from .session import MissingFields, PreparedDecision, ProtocolError


class ExamCardState(WireModel):
    """局内变化单独声明；成长列表不重复包含永久自定义。"""

    grow_effect_ids: tuple[str, ...]
    transient_effect_ids: tuple[str, ...]
    transient_trigger_ids: tuple[str, ...]
    card_status_enchant_id: str
    play_count_bonus: int = Field(ge=0, strict=True)


class ExamTimedEffect(WireModel):
    """已发生的持续效果；不限持续/次数用明确 null。"""

    effect_id: str
    remaining_turns: int | None = Field(ge=1, strict=True)
    remaining_count: int | None = Field(ge=1, strict=True)
    applied_turn: int = Field(ge=0, strict=True)


class ExamSelection(WireModel):
    """当前补选提示对应的确切主数据效果。"""

    effect_id: str = Field(min_length=1)


REQUIRED_NUMBERS = ('turn', 'max_turns', 'extra_turns', 'plays_used', 'plays_remaining',
                    'stamina', 'max_stamina', 'block', 'lesson_buff', 'parameter_buff',
                    'parameter_buff_multiple_per_turn')
SUPPORTED_EFFECTS = {
    ExamEffect.STAMINA_CONSUMPTION_DOWN, ExamEffect.STAMINA_CONSUMPTION_ADD,
    ExamEffect.STAMINA_CONSUMPTION_DOWN_FIX, ExamEffect.STAMINA_CONSUMPTION_ADD_FIX,
    ExamEffect.LESSON_VALUE_MULTIPLE, ExamEffect.LESSON_VALUE_MULTIPLE_DOWN,
    ExamEffect.LESSON_BUFF_MULTIPLE, ExamEffect.PARAMETER_BUFF_ADDITIVE,
}
TRIGGER_FIELDS = {
    FieldStatus.BLOCK_UP: 'block', FieldStatus.NO_BLOCK: 'block',
    FieldStatus.LESSON_BUFF_UP: 'lesson_buff', FieldStatus.PARAMETER_BUFF: 'parameter_buff',
    FieldStatus.PARAMETER_BUFF_UP: 'parameter_buff',
    FieldStatus.PARAMETER_BUFF_MULTIPLE_PER_TURN_UP: 'parameter_buff_multiple_per_turn',
    FieldStatus.STAMINA_LESS_MULTIPLE: 'stamina', FieldStatus.STAMINA_UP_MULTIPLE: 'stamina',
    FieldStatus.REMAINING_TURN: 'turn', FieldStatus.TURN_PROGRESS_UP: 'turn',
    FieldStatus.PLAY_CARD_SKILL: 'plays_used', FieldStatus.NO_STANCE: 'stance',
    FieldStatus.STAMINA_CONSUMPTION_DOWN: 'stamina_consumption_down',
    FieldStatus.REVIEW_UP: 'review', FieldStatus.CARD_PLAY_AGGRESSIVE_UP: 'aggressive',
}
ZONES = {'hand': 'hand', 'deck': 'deck', 'discard': 'grave', 'hold': 'hold',
         'lost': 'lost', 'playing': 'playing'}


def observed_value(observation: Observation, name: str) -> Any:
    """未知与已知零分开；结构化事实的证据覆盖整个值。"""
    fact = observation.facts.get(name)
    if fact is None or fact.status != 'observed':
        raise MissingFields(f'facts.{name}')
    return fact.value


def number(observation: Observation, name: str, *, integer: bool = True) -> float | int:
    """整数计数不接受 bool、浮点猜测或负数。"""
    value = observed_value(observation, name)
    if (isinstance(value, bool) or not isinstance(value, int if integer else (int, float))
            or not math.isfinite(value) or value < 0):
        raise MissingFields(f'facts.{name}.nonnegative_{"integer" if integer else "number"}')
    return value


def validate_value(kind: Any, value: Any, path: str) -> Any:
    """嵌套结构错位以补读路径报告。"""
    try:
        return TypeAdapter(kind).validate_python(value)
    except ValidationError as exc:
        raise MissingFields(path) from exc


def entity_key(entity: EntityRef) -> tuple:
    """证据/标签可不同，但身份和实际变体必须相同。"""
    return (entity.instance_id, entity.kind, entity.definition_id, entity.upgrade_count,
            entity.customize_ids, entity.variant_fingerprint)


class ExamBackend(PlanningBackend):
    """每帧全量重建决策视图，UID 由 run/exam/instance 稳定导出。"""

    def prepare(self, setup: RunSetup, observation: Observation) -> PreparedDecision:
        """已结算观察 → 引擎费用/条件 → 共用 encoder → 原始 Choice。"""
        if observation.pending_decision.kind not in {'exam', 'search', 'discard'}:
            raise MissingFields(f'arena.exam.binding.{observation.pending_decision.kind}')
        if setup.masterdata_revision != self.masterdata_revision:
            if setup.masterdata_revision is None:
                raise MissingFields('run_setup.masterdata_revision')
            raise ProtocolError('masterdata revision mismatch')
        if setup.rules_revision != self.rules_revision:
            raise MissingFields('run_setup.rules_revision=arena-rules/2')
        scenario = self.repository.build_scenario(setup.scenario_id)
        if setup.scenario_id not in {'produce-007', 'produce-008'}:
            raise MissingFields('arena.exam.hif_scenario')
        if not setup.loadout.idol_card_id:
            raise MissingFields('run_setup.loadout.idol_card_id')
        loadout = build_idol_loadout(self.repository, scenario, setup.loadout.idol_card_id)
        if loadout.stat_profile.plan_type != 'ProducePlanType_Plan1':
            raise MissingFields('arena.exam.sense_plan')
        exam_id = observed_value(observation, 'exam_id')
        stage = observed_value(observation, 'exam_stage_type')
        if not isinstance(exam_id, str) or not exam_id:
            raise MissingFields('facts.exam_id.nonempty_string')
        if stage not in scenario.audition_sequence:
            raise MissingFields('facts.exam_stage_type.scenario_stage')
        # 基础缺值和独立被动条目一次报告；版本/场景握手仍优先处理。
        missing = []
        values = {}
        for name in REQUIRED_NUMBERS:
            try:
                values[name] = number(observation, name)
            except MissingFields as exc:
                missing.extend(exc.fields)
        for name in ('current_turn_color', 'exam_effects', 'forbidden_card_search_ids', 'exam_card_state'):
            try:
                observed_value(observation, name)
            except MissingFields as exc:
                missing.extend(exc.fields)
        try:
            passives = prepare_passives(self.repository, setup, observation, self._card_row)
        except MissingFields as exc:
            missing.extend(exc.fields)
        if missing:
            raise MissingFields(*dict.fromkeys(missing))
        if (not values['turn'] or not values['max_turns'] or not values['max_stamina']
                or values['stamina'] > values['max_stamina']):
            raise ProtocolError('inconsistent turn/stamina checkpoint')
        if values['turn'] > values['max_turns']:
            granted = number(observation, 'extra_turns_granted')
            if granted != values['turn'] - values['max_turns'] + values['extra_turns']:
                raise ProtocolError('inconsistent granted/remaining extra turns')
        elif (grant_fact := observation.facts.get('extra_turns_granted')) is not None and grant_fact.status == 'observed':
            if number(observation, 'extra_turns_granted') != values['extra_turns']:
                raise ProtocolError('inconsistent granted/remaining extra turns')
        color = observed_value(observation, 'current_turn_color')
        if color not in {'vocal', 'dance', 'visual'}:
            raise MissingFields('facts.current_turn_color')
        effects = validate_value(list[ExamTimedEffect], observed_value(observation, 'exam_effects'), 'facts.exam_effects')
        # 无初始牌组、饮料抽样和开场效果，loadout 仅用于确定规则流派/考试行。
        rt = ExamRuntime(self.repository, scenario, stage_type=stage, loadout=loadout,
                         observation_only=True, battle_kind='exam')
        rt.active_enchants = passives
        for name in ('turn', 'max_turns', 'extra_turns', 'stamina', 'max_stamina'):
            setattr(rt, name, values[name])
        rt.current_turn_color = color
        rt.turn_counters['play_count'] = values['plays_used']
        rt.play_limit = values['plays_used'] + values['plays_remaining']
        known = set(REQUIRED_NUMBERS) | {'stance', 'exam_stage_type', 'exam_effects',
                                      'exam_enchants', 'current_turn_color', 'loadout.idol_card_id'}
        for name in ('block', 'lesson_buff', 'parameter_buff', 'parameter_buff_multiple_per_turn'):
            rt.resources[name] = values[name]
        for name in ('review', 'aggressive', 'enthusiastic', 'score', 'target_score', 'score_bonus_multiplier'):
            fact = observation.facts.get(name)
            if fact is not None and fact.status == 'observed':
                val = number(observation, name, integer=name != 'score_bonus_multiplier')
                known.add(name)
                if name == 'target_score':
                    if val <= 0:
                        raise MissingFields('facts.target_score.positive')
                    rt.profile['base_score'] = val
                elif name in {'score', 'score_bonus_multiplier'}:
                    setattr(rt, name, val)
                else:
                    rt.resources[name] = val
        for index, effect in enumerate(effects):
            row = self.repository.exam_effect_map.get(effect.effect_id)
            if row is None or row['effectType'] not in SUPPORTED_EFFECTS:
                raise MissingFields(f'arena.exam.effects.{effect.effect_id}')
            if effect.applied_turn > rt.turn:
                raise ProtocolError('effect applied_turn is in the future')
            rt.active_effects.append(TimedExamEffect(index + 1, row, effect.remaining_turns,
                                                    effect.remaining_count, 'observed', effect.applied_turn))
        rt.resources['stamina_consumption_down'] = sum(
            (e.remaining_turns or 1) for e in rt.active_effects if e.effect['effectType'] == ExamEffect.STAMINA_CONSUMPTION_DOWN)
        known.add('stamina_consumption_down')
        forbidden = validate_value(list[str], observed_value(observation, 'forbidden_card_search_ids'),
                                   'facts.forbidden_card_search_ids')
        for search_id in forbidden:
            if self.repository.load_table('ProduceCardSearch').first(search_id) is None:
                raise MissingFields(f'arena.exam.forbidden_search.{search_id}')
        rt.forbidden_card_search_ids = Counter(forbidden)
        hand = observation.inventories.get('hand')
        if hand is None or hand.coverage != 'complete':
            raise MissingFields('inventories.hand.complete')
        dynamic = observed_value(observation, 'exam_card_state')
        if not isinstance(dynamic, dict):
            raise MissingFields('facts.exam_card_state')
        entities: dict[str, EntityRef] = {}
        cards: dict[str, RuntimeCard] = {}
        for zone, attribute in ZONES.items():
            inventory = observation.inventories.get(zone)
            if inventory is None or inventory.coverage != 'complete':
                continue
            zone_cards = []
            for entity in inventory.entities:
                if entity.instance_id in entities:
                    raise ProtocolError('card instance occupies multiple zones')
                if entity.instance_id.startswith('unresolved:'):
                    raise MissingFields(f'entities.{entity.instance_id}.identity')
                row = self._card_row(entity)
                state = validate_value(ExamCardState, dynamic.get(entity.instance_id),
                                       f'facts.exam_card_state.{entity.instance_id}')
                if state.card_status_enchant_id:
                    raise MissingFields(f'arena.exam.card_enchant.{entity.instance_id}')
                for effect_id in state.grow_effect_ids:
                    if self.repository.load_table('ProduceCardGrowEffect').first(effect_id) is None:
                        raise MissingFields(f'arena.exam.grow_effect.{effect_id}')
                for effect_id in state.transient_effect_ids:
                    if effect_id not in self.repository.exam_effect_map:
                        raise MissingFields(f'arena.exam.card_effect.{effect_id}')
                uid = int.from_bytes(hashlib.sha256(f'{setup.run_id}\0{exam_id}\0{entity.instance_id}'.encode()).digest()[:8], 'big')
                if any(c.uid == uid for c in cards.values()):
                    raise ProtocolError('internal card identity collision')
                card = RuntimeCard(uid, entity.definition_id, entity.upgrade_count, row,
                                   list(row.get('growEffectIds') or []) + list(state.grow_effect_ids),
                                   transient_effect_ids=list(state.transient_effect_ids),
                                   transient_trigger_ids=list(state.transient_trigger_ids),
                                   play_count_bonus=state.play_count_bonus)
                self._validate_triggers(rt, card, known)
                for resource in rt._card_resource_costs(card):
                    if resource not in known:
                        raise MissingFields(f'facts.{resource}')
                entities[entity.instance_id], cards[entity.instance_id] = entity, card
                zone_cards.append(card)
            setattr(rt, attribute, deque(zone_cards) if zone == 'deck' else zone_cards)
            known.add(f'inventory.{zone}')
        drinks = observation.inventories.get('drinks')
        drink_entities = {}
        if drinks is not None and drinks.coverage == 'complete':
            for entity in drinks.entities:
                row = self.repository.produce_drinks.first(entity.definition_id or '')
                if (entity.kind != 'drink' or row is None or entity.instance_id in entities
                        or entity.instance_id.startswith('unresolved:')):
                    raise MissingFields(f'entities.{entity.instance_id}.drink_mapping')
                drink_entities[entity.instance_id] = entity
                rt.drinks.append(dict(row))
            known.add('inventory.drinks')
        env = GakumasExamEnv(self.repository, scenario, idol_loadout=loadout, observed_runtime=rt,
                             stage_type=scenario.default_stage, max_hand_cards=48)
        # 词表顺序与场景默认训练环境一致，换考试只改变当前舞台 one-hot。
        env.current_stage_type = stage
        if len(rt.hand) > env.max_hand_cards or len(rt.drinks) > env.max_drinks:
            raise MissingFields('arena.exam.encoder_capacity')
        if observation.pending_decision.kind in {'search', 'discard'}:
            return self._prepare_selection(env, observation, known, entities, cards)
        raw = env._build_observation()
        mapping = {}
        pending = observation.pending_decision
        if pending.kind != 'exam':
            raise MissingFields(f'arena.exam.binding.{pending.kind}')
        seen = set()
        for choice in pending.choices:
            if choice.action_type == 'card':
                if len(choice.targets) != 1:
                    raise ProtocolError('card requires one target')
                target = choice.targets[0]
                card = cards.get(target.instance_id)
                if card is None or card not in rt.hand:
                    raise MissingFields(f'choices.{choice.choice_id}.hand_instance')
                if entity_key(target) != entity_key(entities[target.instance_id]):
                    raise ProtocolError('target card variant mismatch')
                slot = rt.hand.index(card)
            elif choice.action_type == 'drink':
                if drinks is None or drinks.coverage != 'complete':
                    raise MissingFields('inventories.drinks.complete')
                if len(choice.targets) != 1:
                    raise ProtocolError('drink requires one target')
                target = choice.targets[0]
                if target.instance_id not in drink_entities or entity_key(target) != entity_key(drink_entities[target.instance_id]):
                    raise ProtocolError('target drink mismatch')
                slot = env.max_hand_cards + list(drink_entities).index(target.instance_id)
            elif choice.action_type == 'end_turn':
                if choice.targets:
                    raise ProtocolError('end_turn cannot target an entity')
                slot = env.max_actions - 1
            else:
                raise MissingFields(f'arena.exam.action.{choice.action_type}')
            if choice.parameters:
                raise ProtocolError('unexpected exam action parameters')
            if slot in seen:
                raise ProtocolError('duplicate semantic exam choice')
            seen.add(slot)
            mapping[slot] = choice
        # 屏幕未给出的动作不能由环境的默认 end_turn/饮料槽自行补出。
        for slot, candidate in enumerate(env._candidates):
            allowed = slot in mapping and mapping[slot].ui_enabled and raw['action_mask'][slot] > 0.5
            candidate.payload['available'] = bool(allowed)
            raw['action_mask'][slot] = float(bool(allowed))
        profile = observation.facts.get('exam_passive_version')
        env.structural_passives = profile is not None and profile.value == 'arena-passive/2'
        encoded = encode_exam_observation(env, known, raw=raw)
        self.last_env, self.instance_to_uid, self.known_fields = env, {key: c.uid for key, c in cards.items()}, known
        return PreparedDecision(env=None, observation=encoded,
            info={'partial_observation': True, 'exam_id': exam_id,
                  'choice_ids': {slot: choice.choice_id for slot, choice in mapping.items()}},
            choices=mapping, encoder_manifest=exam_encoder_manifest(env))

    def _prepare_selection(self, env, observation, known, entities, cards) -> PreparedDecision:
        """检索/弃牌不调用出牌；合法目标由主数据边界解析。"""
        selection = validate_value(ExamSelection, observed_value(observation, 'exam_selection'),
                                   'facts.exam_selection.effect_id')
        try:
            boundary = card_selection_boundary(env.runtime, selection.effect_id)
        except UnsupportedSelection as exc:
            raise MissingFields(f'arena.exam.selection.{selection.effect_id}') from exc
        for zone in boundary.required_zones:
            if f'inventory.{zone}' not in known:
                raise MissingFields(f'inventories.{zone}.complete')
        pending = observation.pending_decision
        expected_kind = 'discard' if boundary.destination == 'grave' else 'search'
        if pending.kind != expected_kind:
            raise ProtocolError('selection page does not match effect destination')
        if len(pending.choices) > env.max_actions:
            raise MissingFields('arena.exam.selection_capacity')
        eligible = {card.uid for card in boundary.cards}
        raw = env._build_observation()
        raw['action_features'][:] = 0
        raw['action_mask'][:] = 0
        candidates, mapping, seen = [], {}, set()
        shared = env._candidate_shared_metrics()
        for index, choice in enumerate(pending.choices):
            if choice.action_type != 'card_select' or len(choice.targets) != 1 or choice.parameters:
                raise MissingFields(f'choices.{choice.choice_id}.card_select_one_target')
            target = choice.targets[0]
            card = cards.get(target.instance_id)
            if card is None or entity_key(target) != entity_key(entities[target.instance_id]):
                raise MissingFields(f'choices.{choice.choice_id}.selection_instance')
            if card.uid in seen:
                raise ProtocolError('duplicate selection target')
            seen.add(card.uid)
            available = bool(choice.ui_enabled and card.uid in eligible)
            feature = env._card_feature(card, index, available, shared)
            raw['action_features'][index] = feature
            raw['action_mask'][index] = float(available)
            candidates.append(ActionView(choice.label, 'card_select', feature, {'available': available}))
            mapping[index] = choice
        while len(candidates) < env.max_actions:
            candidates.append(ActionView('empty', 'padding', np.zeros(env.action_feature_dim), {'available': False}))
        env._candidates = candidates
        profile = observation.facts.get('exam_passive_version')
        env.structural_passives = profile is not None and profile.value == 'arena-passive/2'
        encoded = encode_exam_observation(env, known, raw=raw, decision_kind=pending.kind)
        self.last_env, self.instance_to_uid, self.known_fields = env, {key: c.uid for key, c in cards.items()}, known
        return PreparedDecision(env=None, observation=encoded,
            info={'partial_observation': True, 'exam_id': observed_value(observation, 'exam_id'),
                  'choice_ids': {slot: choice.choice_id for slot, choice in mapping.items()}},
            choices=mapping, encoder_manifest=exam_encoder_manifest(env))

    def _validate_triggers(self, rt: ExamRuntime, card: RuntimeCard, known: set[str]) -> None:
        """只允许已提供全部依赖的出牌条件；未知检索/历史计数不落入默认值。"""
        for trigger_id in rt._effective_card_trigger_ids(card):
            trigger = self.repository.exam_trigger_map.get(trigger_id)
            if trigger is None or trigger.get('produceCardSearchId'):
                raise MissingFields(f'arena.exam.trigger.{trigger_id}')
            for field in trigger.get('fieldStatusTypes') or []:
                dependency = TRIGGER_FIELDS.get(field)
                if dependency is None:
                    raise MissingFields(f'arena.exam.trigger.{trigger_id}.{field}')
                if dependency not in known:
                    raise MissingFields(f'facts.{dependency}')


class LiveBackend:
    """兼容既有规划接口，按当前 PendingDecision 分发。"""

    def __init__(self, repository=None) -> None:
        """两个 backend 共用同一主数据实例。"""
        self.planning = PlanningBackend(repository)
        self.exam = ExamBackend(self.planning.repository)

    def prepare(self, setup: RunSetup, observation: Observation) -> PreparedDecision:
        """每次从页面选择绑定，不沿用上一考试运行时。"""
        kind = observation.pending_decision.kind
        backend = self.planning if kind in {'card_reward', 'consult'} else self.exam
        return backend.prepare(setup, observation)
