"""考试阶段运行时，负责根据主数据解释卡牌、饮料、触发器与状态效果。"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from copy import copy, deepcopy
from dataclasses import dataclass, field
import logging
import math
from typing import Any, Iterable

import numpy as np

logger = logging.getLogger(__name__)

from ...constants.game.support_types import (
    SUPPORT_TYPE_ASSIST,
    SUPPORT_TYPE_DANCE,
    SUPPORT_TYPE_VISUAL,
    SUPPORT_TYPE_VOCAL,
)
from ...idol_config import build_initial_exam_deck
from ...loadout import IdolLoadout
from ...repository.master_data import MasterDataRepository, ScenarioSpec
from ...training.reward_config import RewardConfig, build_reward_config
from ..produce.items import RuntimeExamStatusEnchantSpec
from .constants import (
    ANTI_DEBUFF_EFFECT_TYPES,
    CARD_ZONE_MAP,
    COST_RESOURCE_MAP,
    DURATION_RESOURCE_TYPES,
    FULL_POWER_POINT_THRESHOLD,
    GROW_EFFECT_COST_RESOURCE_MAP,
    HOLD_CARD_LIMIT,
    LESSON_EFFECT_TYPES,
    MOVE_POSITION_MAP,
    NEGATIVE_TIMED_EFFECT_TYPES,
    PHASE_TURN_VALUE,
    SCALAR_RESOURCE_TYPES,
    STANCE_PHASES,
    STATUS_CHANGE_TRIGGER_ORIGINS,
)
from .effects import apply_exam_effect, resolve_lesson_effect_value
from .effects.context import ExamEffectContext
from .ids import ExamEffect, ExamPhase, FieldStatus, GrowEffect, TriggerCheck
from .replay import ReplayHooks, reorder_by_build_index
from .resolution import ResolutionState, collect_phase_batch, effect_group, execute_phase_batch
from .scoring import (
    DEFAULT_SCORING_RULES,
    PERMIL,
    ScoringRules,
    apply_permil_ceil,
    ceil_int,
    good_condition_permil,
    permil_from_ratio,
    round_genki,
    scale_by_permils,
    score_bonus_permil,
    stamina_consumption_permil,
    stance_lesson_permil,
    stance_stamina_permil,
)
from .triggers import (
    field_status_value,
    trigger_card_search_matches,
    trigger_field_status_matches,
    trigger_matches,
)
from .triggers.context import ExamTriggerContext

# 回合数型、同种叠加时按回合数相加的状态（§3.5 EOT_DECREMENT_FIELDS 中的 turns 型；好調/好印象是资源槽，另行处理）。
DURATION_STACKING_EFFECT_TYPES = {
    # 倉本千奈 SSR-2 录像 turn8：絶好調残6 + 応援4 = 10，合并持续回合而非层数。
    ExamEffect.PARAMETER_BUFF_MULTIPLE_PER_TURN,
    ExamEffect.STAMINA_CONSUMPTION_DOWN,
    ExamEffect.STAMINA_CONSUMPTION_ADD,
    ExamEffect.BLOCK_RESTRICTION,
    ExamEffect.BLOCK_ADD_DOWN,
    ExamEffect.GIMMICK_PARAMETER_DEBUFF,
    ExamEffect.STANCE_LOCK,
    ExamEffect.STAMINA_RECOVER_RESTRICTION,
}

EXAM_REWARD_MODES = ('score', 'clear')
TURN_COLOR_ORDER = ('vocal', 'dance', 'visual')
TURN_COLOR_INDEX = {color: index for index, color in enumerate(TURN_COLOR_ORDER)}
TURN_COLOR_LESSON_TYPES = {
    'vocal': 'ProduceStepLessonType_LessonVocal',
    'dance': 'ProduceStepLessonType_LessonDance',
    'visual': 'ProduceStepLessonType_LessonVisual',
}
TURN_COLOR_LABELS = {
    'vocal': 'Vocal',
    'dance': 'Dance',
    'visual': 'Visual',
}

PLAN_REWARD_FAMILY = {
    'ProducePlanType_Plan1': 'sense',
    'ProducePlanType_Plan2': 'logic',
    'ProducePlanType_Plan3': 'anomaly',
}
CARD_SELECTION_LESSON_SCORE = 6.0
CARD_SELECTION_FULL_POWER_POINT_SCORE = 3.0
CARD_SELECTION_FULL_POWER_SCORE = 4.0
CARD_SELECTION_UTILITY_SCORE = 1.2
CARD_SELECTION_RESOURCE_SCORE = 0.8

REWARD_PROFILE_CONFIGS: dict[str, dict[str, float]] = {
    'score': {
        'shape_scale': 1.85,
        'goal_weight': 0.95,
        'eval_weight': 1.55,
        'archetype_weight': 1.20,
        'risk_weight': 0.60,
        'efficiency_weight': 0.20,
        'turn_window_weight': 0.55,
        'efficiency_gate': 0.92,
        'efficiency_overshoot_penalty': 0.12,
        'terminal_pass_reward': 5.5,
        'terminal_eval_weight': 5.0,
        'terminal_stamina_weight': 0.45,
        'terminal_speed_weight': 0.40,
        'terminal_failure_weight': 5.0,
        'terminal_force_end_bonus': 1.2,
        'terminal_nia_bonus': 1.25,
        'lesson_clear_reward': 4.0,
        'lesson_perfect_reward': 6.5,
        'overshoot_penalty': 0.55,
    },
    'clear': {
        'shape_scale': 1.55,
        'goal_weight': 1.45,
        'eval_weight': 1.00,
        'archetype_weight': 0.75,
        'risk_weight': 1.10,
        'efficiency_weight': 0.45,
        'turn_window_weight': 0.30,
        'efficiency_gate': 0.75,
        'efficiency_overshoot_penalty': 1.10,
        'terminal_pass_reward': 7.2,
        'terminal_eval_weight': 3.8,
        'terminal_stamina_weight': 0.90,
        'terminal_speed_weight': 0.95,
        'terminal_failure_weight': 7.0,
        'terminal_force_end_bonus': 1.7,
        'terminal_nia_bonus': 1.10,
        'lesson_clear_reward': 5.4,
        'lesson_perfect_reward': 8.2,
        'overshoot_penalty': 2.20,
    },
}

@dataclass
class ExamActionCandidate:
    """环境包装层暴露出的一个考试动作。"""

    label: str
    kind: str
    payload: dict[str, Any]


@dataclass
class RuntimeCard:
    """考试运行时中的可变卡牌实例。"""

    uid: int
    card_id: str
    upgrade_count: int
    base_card: dict[str, Any]
    grow_effect_ids: list[str] = field(default_factory=list)
    card_status_enchant_id: str = ''
    transient_effect_ids: list[str] = field(default_factory=list)
    transient_trigger_ids: list[str] = field(default_factory=list)
    play_count_bonus: int = 0
    build_index: int = -1
    """在初始牌组里的构建下标（录像复现钩子用它指定山札顺序）；复制/生成的卡为 -1。"""

    def effect_ids(self) -> list[str]:
        """返回这张运行时卡当前生效的出牌效果 id 列表。"""

        effect_ids = [str(effect.get('produceExamEffectId') or '') for effect in self.base_card.get('playEffects', [])]
        effect_ids.extend(self.transient_effect_ids)
        return [value for value in effect_ids if value]

    def trigger_ids(self) -> list[str]:
        """返回这张运行时卡当前绑定的触发器 id 列表。"""

        trigger_ids = []
        if self.base_card.get('playProduceExamTriggerId'):
            trigger_ids.append(str(self.base_card['playProduceExamTriggerId']))
        trigger_ids.extend(self.transient_trigger_ids)
        return [value for value in trigger_ids if value]

    def clone(self, uid: int | None = None) -> 'RuntimeCard':
        """复制一张运行时卡，并可选替换 uid。"""

        return RuntimeCard(
            uid=self.uid if uid is None else uid,
            card_id=self.card_id,
            upgrade_count=self.upgrade_count,
            base_card=self.base_card,
            grow_effect_ids=list(self.grow_effect_ids),
            card_status_enchant_id=self.card_status_enchant_id,
            transient_effect_ids=list(self.transient_effect_ids),
            transient_trigger_ids=list(self.transient_trigger_ids),
            play_count_bonus=self.play_count_bonus,
            build_index=self.build_index if uid is None or uid == self.uid else -1,
        )


@dataclass
class TimedExamEffect:
    """带持续回合或次数限制的运行时考试效果。"""

    uid: int
    effect: dict[str, Any]
    remaining_turns: int | None
    remaining_count: int | None
    source: str
    applied_turn: int = 0
    """效果被挂上的回合号，用于ターン経過減免：本回合新挂的效果不当回合衰减。"""


@dataclass
class TriggeredEnchant:
    """已挂载到场上的状态附魔及其触发配置。"""

    uid: int
    enchant_id: str
    trigger_id: str
    effect_ids: list[str]
    remaining_turns: int | None
    remaining_count: int | None
    source: str
    applied_turn: int = 0
    """附魔被挂上的回合号，用于ターン経過減免：本回合新挂的附魔不当回合衰减。"""
    source_identity: str = ''
    bound_card_uid: int | None = None
    """再演（ExamStatusEnchantEncore）等绑定到具体运行时卡的附魔所对应的卡 uid；None 表示不绑定。"""
    once_per_turn: bool = False
    """是否受「ターン内1回まで」限制。"""
    last_fired_turn: int = -1
    """最近一次发动的回合号，配合 once_per_turn 使用。"""


@dataclass
class ScheduledEffect:
    """将在未来某个回合结算的延迟效果。"""

    effect_id: str
    fire_turn: int
    remaining_count: int | None
    source: str = 'other'
    source_card_uid: int | None = None


@dataclass
class ExamEvent:
    """运行时事件记录。"""

    turn: int
    event_type: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExamRankState:
    """考试排名与合格状态。

    从 ProduceStepAuditionDifficulty.rankThreshold、baseScore、forceEndScore 初始化。
    每回合通过 Rival 分数模拟更新 self_rank，最终判定合格/不合格。
    """

    self_rank: int = 0
    """玩家当前排名（1=最高分）。"""

    rival_scores: list[float] = field(default_factory=list)
    """各 Rival 当前累计分数。"""

    pass_condition: str = 'rank_threshold'
    """合格判定条件：'rank_threshold'（排名达标）/ 'score_threshold'（分数达标）/ 'force_end'（强制结束）。"""

    rank_threshold: int = 3
    """排名合格线：排名 <= rank_threshold 即合格。从 ProduceStepAuditionDifficulty.rankThreshold 读取。"""

    score_threshold: float = 0.0
    """分数达标阈值。从 ProduceStepAuditionDifficulty.baseScore 读取。"""

    force_end_score: float = 0.0
    """强制结束分数（0 表示无限制）。从 ProduceStepAuditionDifficulty.forceEndScore 读取。"""

    passed: bool = False
    """是否已通过合格判定。"""


@dataclass
class CardSelection:
    """检索结果，包含命中的卡牌和候选池大小。"""

    selected: list[RuntimeCard]
    pool_size: int


@dataclass
class ExamRuntimePreviewState:
    """考试运行时的一步前瞻快照。"""

    uid_counter: int
    random_state: dict[str, Any]
    turn: int
    max_turns: int
    terminated: bool
    last_info: dict[str, Any]
    deck: deque[RuntimeCard]
    hand: list[RuntimeCard]
    grave: list[RuntimeCard]
    hold: list[RuntimeCard]
    lost: list[RuntimeCard]
    playing: list[RuntimeCard]
    current_card: RuntimeCard | None
    drinks: list[dict[str, Any]]
    support_upgrade_original_rows: dict[int, dict[str, Any]]
    score: float
    score_per_color: dict[str, float]
    stamina: float
    max_stamina: float
    stance: str
    stance_level: int
    stance_locked: bool
    play_limit: int
    start_turn_draw_penalty: int
    extra_turns: int
    panic_cost_overrides: dict[int, float]
    current_turn_color: str
    turn_color_history: list[str]
    score_bonus_multiplier: float
    resources: defaultdict[str, float]
    turn_counters: Counter[str]
    total_counters: Counter[str]
    search_history: Counter[str]
    active_effects: list[TimedExamEffect]
    active_enchants: list[TriggeredEnchant]
    scheduled_effects: list[ScheduledEffect]
    gimmick_rows: list[dict[str, Any]]
    resolving_enchant_uids: set[int]
    resolved_gimmick_keys: set[tuple[str, int, int]]
    forbidden_card_search_ids: Counter[str]
    lesson_cleared: bool
    clear_state: str
    rank_state: ExamRankState
    event_log: list[ExamEvent]
    milestone_flags: dict[str, bool]
    consecutive_end_turns: int
    prev_score: float
    prev_resource_stock: float
    cached_reward_signal: float | None
    resolution: ResolutionState = field(default_factory=ResolutionState)
    lifecycle_state: dict[str, Any] = field(default_factory=dict)


def format_audition_row_selector(row: dict[str, Any] | None) -> str | None:
    """把考试主数据行格式化成 battle runtime 可消费的显式 selector。"""

    if not row:
        return None
    return f"{str(row.get('id') or '')}:{int(row.get('number') or 0)}"


def default_audition_row_selector(
    repository: MasterDataRepository,
    scenario: ScenarioSpec,
    stage_type: str | None = None,
    loadout: IdolLoadout | None = None,
    fan_votes: float | None = None,
) -> str | None:
    """为外层兼容调用提供一个稳定的默认 battle row selector。"""

    audition_difficulty_id = str(loadout.stat_profile.audition_difficulty_id or '') if loadout is not None else ''
    selected_row = repository.select_audition_row(
        scenario,
        stage_type or scenario.default_stage,
        audition_difficulty_id=audition_difficulty_id or None,
        fan_votes=fan_votes,
    )
    return format_audition_row_selector(selected_row)


class ExamRuntime:
    """数据驱动的考试战斗运行时。

    模型只看到结构化卡牌特征，卡名仅保留在调试标签里；实际逻辑依赖效果类型、
    触发 phase 和检索定义来推进。
    """

    def __init__(
        self,
        repository: MasterDataRepository,
        scenario: ScenarioSpec,
        stage_type: str | None = None,
        seed: int | None = None,
        deck: list[dict[str, Any]] | None = None,
        drinks: list[dict[str, Any]] | None = None,
        initial_status_enchant_ids: list[str] | None = None,
        initial_status_enchants: Iterable[RuntimeExamStatusEnchantSpec | dict[str, Any]] | None = None,
        loadout: IdolLoadout | None = None,
        starting_stamina: float | None = None,
        exam_score_bonus_multiplier: float | None = None,
        parameter_stats: tuple[float, float, float] | None = None,
        fan_votes: float | None = None,
        reward_mode: str = 'score',
        reward_config: RewardConfig | None = None,
        audition_row_id: str | None = None,
        battle_kind: str | None = None,
        lesson_type: str | None = None,
        lesson_types: Iterable[str] | None = None,
        lesson_post_clear_types: Iterable[str] | None = None,
        lesson_sequence: Iterable[str] | None = None,
        lesson_target_value: float | None = None,
        lesson_perfect_value: float | None = None,
        lesson_perfect_recovery_per_turn: float = 0.0,
        turn_limit: int | None = None,
        scoring_rules: ScoringRules | None = None,
        replay_hooks: ReplayHooks | None = None,
        observation_only: bool = False,
        max_stamina: float | None = None,
    ):
        """初始化考试运行时，并根据偶像卡选择难度 profile、初始 deck 与开场附魔。

        Args:
            scoring_rules: 取整/倍率规则开关（见 `scoring.ScoringRules`），默认社区共识。
            replay_hooks: 录像复现钩子（固定山札顺序、回合属性、スコアボーナス、応援），默认不使用。
        """

        if reward_mode not in EXAM_REWARD_MODES:
            raise ValueError(f'Unsupported exam reward mode: {reward_mode}')

        self.repository = repository
        self.observation_only = observation_only
        if max_stamina is not None and max_stamina <= 0:
            raise ValueError('max_stamina must be positive')
        self.configured_max_stamina = max_stamina
        self.scoring_rules: ScoringRules = scoring_rules or DEFAULT_SCORING_RULES
        self.replay_hooks: ReplayHooks | None = replay_hooks
        # 回合开始阶段（応援/Pアイテム/抽牌/発動予約）期间挂上的持续状态视为「回合开始时已存在」，
        # 下一回合开始就会递减；玩家行动期间挂上的则享受 ターン経過減免（§3.5）。
        self._turn_start_phase_active = False
        # 好印象/好調 在回合开始快照时是否存在（kjirou `modifierIdsAtTurnStart`）。
        self._resource_turn_start_snapshot: dict[str, bool] = {}
        self.scenario = scenario
        self.reward_config: RewardConfig = reward_config or build_reward_config(reward_mode)
        self.stage_type = stage_type or scenario.default_stage
        self.np_random = np.random.default_rng(seed)
        # 从 Produce 表的 examSettingId 字段读取 ExamSetting 行 ID，fallback 到默认值
        produce_row = repository.produces.first(scenario.produce_id) or {}
        exam_setting_id = str(produce_row.get('examSettingId') or 'p_exam_setting-1')
        self.exam_setting = repository.load_table('ExamSetting').first(exam_setting_id) or {}
        self.card_searches = repository.load_table('ProduceCardSearch')
        self.grow_effects = repository.load_table('ProduceCardGrowEffect')
        self.card_status_enchants = repository.load_table('ProduceCardStatusEnchant')
        self.exam_gimmicks = repository.load_table('ProduceExamGimmickEffectGroup')
        self.random_pools = repository.load_table('ProduceCardRandomPool')
        self.card_pools = repository.load_table('ProduceCardPool')
        self.loadout = loadout
        self.starting_stamina = float(starting_stamina) if starting_stamina is not None else None
        self.reward_mode = reward_mode
        self.audition_row_id = str(audition_row_id or '')
        self.battle_kind = self._resolve_battle_kind(battle_kind)
        self._initial_lesson_target_value = float(lesson_target_value) if lesson_target_value is not None else None
        self._initial_lesson_perfect_value = float(lesson_perfect_value) if lesson_perfect_value is not None else None
        self._initial_turn_limit = int(turn_limit) if turn_limit is not None else None
        self.explicit_fan_votes = (
            float(fan_votes)
            if fan_votes is not None and self._fan_vote_enabled_for_mode()
            else None
        )
        self.selected_battle_row = self._resolve_selected_battle_row()
        self.profile = self._build_battle_profile(self.selected_battle_row)
        self.fan_votes = self._resolve_initial_fan_votes(self.explicit_fan_votes)
        self.initial_deck_rows = [] if observation_only else list(deck if deck is not None else build_initial_exam_deck(repository, scenario, rng=self.np_random, loadout=loadout))
        self.initial_drinks = [] if observation_only else list(
            drinks if drinks is not None else repository.build_drink_inventory(
                scenario,
                rng=self.np_random,
                plan_type=loadout.stat_profile.plan_type if loadout is not None else None,
            )
        )
        self.default_lesson_type = str(lesson_type or self._infer_stage_lesson_type(self.stage_type))
        resolved_lesson_types = tuple(str(value) for value in (lesson_types or ()) if str(value or ''))
        if not resolved_lesson_types:
            resolved_lesson_types = (self.default_lesson_type,)
        self.default_lesson_types = resolved_lesson_types
        self.lesson_post_clear_types = tuple(
            str(value)
            for value in (lesson_post_clear_types or ())
            if str(value or '')
        )
        self.lesson_sequence = tuple(str(value) for value in (lesson_sequence or ()) if str(value or ''))
        self.lesson_target_value = (
            self._initial_lesson_target_value
            if self._initial_lesson_target_value is not None
            else (float(self.profile.get('base_score') or 0.0) if self._uses_clear_training_rules() else None)
        )
        self.lesson_perfect_value = self._initial_lesson_perfect_value
        self.lesson_perfect_recovery_per_turn = float(lesson_perfect_recovery_per_turn or 0.0)
        combined_enchants: dict[tuple[str, str, str], dict[str, Any]] = {}
        for enchant_id in initial_status_enchant_ids or []:
            if enchant_id:
                combined_enchants[(str(enchant_id), 'produce', '')] = {
                    'enchant_id': str(enchant_id),
                    'effect_turn': None,
                    'effect_count': None,
                    'source': 'produce',
                }
        for enchant_spec in initial_status_enchants or ():
            if isinstance(enchant_spec, RuntimeExamStatusEnchantSpec):
                payload = {
                    'enchant_id': str(enchant_spec.enchant_id),
                    'effect_turn': enchant_spec.effect_turn,
                    'effect_count': enchant_spec.effect_count,
                    'source': str(enchant_spec.source or 'produce'),
                    'source_identity': str(enchant_spec.source_identity or ''),
                }
            else:
                payload = {
                    'enchant_id': str(enchant_spec.get('enchant_id') or ''),
                    'effect_turn': enchant_spec.get('effect_turn'),
                    'effect_count': enchant_spec.get('effect_count'),
                    'source': str(enchant_spec.get('source') or 'produce'),
                    'source_identity': str(enchant_spec.get('source_identity') or ''),
                }
            if not payload['enchant_id']:
                continue
            key = (payload['enchant_id'], payload['source'], payload['source_identity'])
            combined_enchants[key] = payload
        if loadout is not None:
            loadout_specs = loadout.exam_status_enchant_specs
            if loadout_specs:
                for spec in loadout_specs:
                    if not spec.enchant_id:
                        continue
                    source_identity = str(spec.source_identity or loadout.produce_item_id or spec.enchant_id)
                    key = (str(spec.enchant_id), 'produce_item', source_identity)
                    combined_enchants[key] = {
                        'enchant_id': str(spec.enchant_id),
                        'effect_turn': spec.effect_turn,
                        'effect_count': spec.effect_count,
                        'source': 'produce_item',
                        'source_identity': source_identity,
                    }
            else:
                for enchant_id in loadout.exam_status_enchant_ids:
                    if enchant_id:
                        key = (str(enchant_id), 'produce_item', str(loadout.produce_item_id or enchant_id))
                        combined_enchants[key] = {
                            'enchant_id': str(enchant_id),
                            'effect_turn': None,
                            'effect_count': None,
                            'source': 'produce_item',
                            'source_identity': str(loadout.produce_item_id or enchant_id),
                        }
        self.initial_status_enchants = list(combined_enchants.values())

        self._uid_counter = 0
        self.turn = 0
        self.max_turns = int(self._initial_turn_limit or self.profile.get('turns') or scenario.exam_turns)
        self.terminated = False
        self.last_info: dict[str, Any] = {}

        self.deck: deque[RuntimeCard] = deque()
        self.hand: list[RuntimeCard] = []
        self.grave: list[RuntimeCard] = []
        self.hold: list[RuntimeCard] = []
        self.lost: list[RuntimeCard] = []
        self.playing: list[RuntimeCard] = []
        self.current_card: RuntimeCard | None = None
        self._current_play_uid_floor: int | None = None
        self.resolution = ResolutionState()
        self.drinks: list[dict[str, Any]] = []
        self.support_cards = tuple(loadout.support_cards) if loadout is not None else ()
        self._support_upgrade_original_rows: dict[int, dict[str, Any]] = {}

        self.score = 0.0
        # NIA 试镜按回合颜色分类累计得分（用于培育阶段返还对应参数）
        self.score_per_color: dict[str, float] = {'vocal': 0.0, 'dance': 0.0, 'visual': 0.0}
        self.stamina = 0.0
        self.max_stamina = 0.0
        self.stance = 'neutral'
        self.stance_level = 0
        self.stance_locked = False
        self.play_limit = 1
        self.start_turn_draw_penalty = 0
        self.extra_turns = 0
        self.panic_cost_overrides: dict[int, float] = {}
        if parameter_stats is not None:
            parameter_values = np.array(parameter_stats, dtype=np.float32)
        else:
            parameter_values = np.array(
                [
                    float(loadout.stat_profile.vocal) if loadout is not None else 0.0,
                    float(loadout.stat_profile.dance) if loadout is not None else 0.0,
                    float(loadout.stat_profile.visual) if loadout is not None else 0.0,
                ],
                dtype=np.float32,
            )
        parameter_limit = float(scenario.parameter_growth_limit or 0.0)
        if parameter_limit > 0:
            parameter_values = np.clip(parameter_values, 0.0, parameter_limit)
        else:
            parameter_values = np.clip(parameter_values, 0.0, None)
        self.parameter_stats = (float(parameter_values[0]), float(parameter_values[1]), float(parameter_values[2]))
        resolved_base_score_bonus = (
            float(exam_score_bonus_multiplier)
            if exam_score_bonus_multiplier is not None
            else self._default_score_bonus_multiplier()
        )
        if self.scenario.route_type == 'nia':
            resolved_base_score_bonus *= self._fan_vote_score_multiplier()
        self.base_score_bonus_multiplier = max(resolved_base_score_bonus, 0.25)
        self.current_turn_color = ''
        self.turn_color_history: list[str] = []
        self.score_bonus_multiplier = self.base_score_bonus_multiplier

        self.resources: dict[str, float] = defaultdict(float)
        self.turn_counters: Counter[str] = Counter()
        self.total_counters: Counter[str] = Counter()
        self.search_history: Counter[str] = Counter()
        self.active_effects: list[TimedExamEffect] = []
        self.active_enchants: list[TriggeredEnchant] = []
        self.scheduled_effects: list[ScheduledEffect] = []
        self.gimmick_rows: list[dict[str, Any]] = []
        self._resolving_enchant_uids: set[int] = set()
        self.resolving_enchant_card: RuntimeCard | None = None
        """正在结算效果的绑定型附魔（如再演）所绑定的卡，供效果器解析 `isSelf`/`Target` 检索。"""
        self._resolved_gimmick_keys: set[tuple[str, int, int]] = set()
        self.forbidden_card_search_ids: Counter[str] = Counter()
        self.lesson_cleared = False
        self.clear_state = 'ongoing'
        self.rank_state = ExamRankState(
            rank_threshold=int(self.profile.get('rank_threshold') or 3),
            score_threshold=float(self.profile.get('base_score') or 0.0),
            force_end_score=float(self.profile.get('force_end_score') or 0.0),
        )
        self._init_rival_scores()
        self.event_log: list[ExamEvent] = []

        # ── 奖励追踪状态 ──
        self._milestone_flags: dict[str, bool] = {
            '25': False, '50': False, '75': False, '100': False,
        }
        self._consecutive_end_turns: int = 0
        self._prev_score: float = 0.0
        self._prev_resource_stock: float = 0.0
        self._cached_reward_signal: float | None = None

    def _record_event(self, event_type: str, detail: dict[str, Any] | None = None) -> None:
        """记录一条运行时事件。"""

        self.event_log.append(ExamEvent(turn=self.turn, event_type=event_type, detail=detail or {}))

    def _clone_runtime_card(self, card: RuntimeCard) -> RuntimeCard:
        """复制一张运行时卡。"""

        return card.clone()

    def capture_preview_state(self) -> ExamRuntimePreviewState:
        """抓取一步前瞻所需的轻量快照。"""

        return ExamRuntimePreviewState(
            uid_counter=int(self._uid_counter),
            random_state=deepcopy(self.np_random.bit_generator.state),
            turn=int(self.turn),
            max_turns=int(self.max_turns),
            terminated=bool(self.terminated),
            last_info=dict(self.last_info),
            deck=deque(self._clone_runtime_card(card) for card in self.deck),
            hand=[self._clone_runtime_card(card) for card in self.hand],
            grave=[self._clone_runtime_card(card) for card in self.grave],
            hold=[self._clone_runtime_card(card) for card in self.hold],
            lost=[self._clone_runtime_card(card) for card in self.lost],
            playing=[self._clone_runtime_card(card) for card in self.playing],
            current_card=self._clone_runtime_card(self.current_card) if self.current_card is not None else None,
            drinks=[dict(drink) for drink in self.drinks],
            support_upgrade_original_rows={int(key): dict(value) for key, value in self._support_upgrade_original_rows.items()},
            score=float(self.score),
            score_per_color=dict(self.score_per_color),
            stamina=float(self.stamina),
            max_stamina=float(self.max_stamina),
            stance=str(self.stance),
            stance_level=int(self.stance_level),
            stance_locked=bool(self.stance_locked),
            play_limit=int(self.play_limit),
            start_turn_draw_penalty=int(self.start_turn_draw_penalty),
            extra_turns=int(self.extra_turns),
            panic_cost_overrides=dict(self.panic_cost_overrides),
            current_turn_color=str(self.current_turn_color),
            turn_color_history=list(self.turn_color_history),
            score_bonus_multiplier=float(self.score_bonus_multiplier),
            resources=defaultdict(float, self.resources),
            turn_counters=Counter(self.turn_counters),
            total_counters=Counter(self.total_counters),
            search_history=Counter(self.search_history),
            active_effects=[copy(item) for item in self.active_effects],
            active_enchants=[copy(item) for item in self.active_enchants],
            scheduled_effects=[copy(item) for item in self.scheduled_effects],
            gimmick_rows=[dict(row) for row in self.gimmick_rows],
            resolving_enchant_uids=set(self._resolving_enchant_uids),
            resolved_gimmick_keys=set(self._resolved_gimmick_keys),
            forbidden_card_search_ids=Counter(self.forbidden_card_search_ids),
            lesson_cleared=bool(self.lesson_cleared),
            clear_state=str(self.clear_state),
            rank_state=ExamRankState(
                self_rank=int(self.rank_state.self_rank),
                rival_scores=list(self.rank_state.rival_scores),
                pass_condition=str(self.rank_state.pass_condition),
                rank_threshold=int(self.rank_state.rank_threshold),
                score_threshold=float(self.rank_state.score_threshold),
                force_end_score=float(self.rank_state.force_end_score),
                passed=bool(self.rank_state.passed),
            ),
            event_log=[ExamEvent(turn=event.turn, event_type=event.event_type, detail=dict(event.detail)) for event in self.event_log],
            milestone_flags=dict(self._milestone_flags),
            consecutive_end_turns=int(self._consecutive_end_turns),
            prev_score=float(self._prev_score),
            prev_resource_stock=float(self._prev_resource_stock),
            cached_reward_signal=None if self._cached_reward_signal is None else float(self._cached_reward_signal),
            resolution=deepcopy(self.resolution),
            lifecycle_state=deepcopy({name: getattr(self, name, default) for name, default in (
                ('_current_play_uid_floor', None), ('_turn_start_phase_active', False),
                ('_resource_turn_start_snapshot', {}), ('_card_move_effect_depth', 0),
                ('resolving_enchant_card', None),
            )}),
        )

    def restore_preview_state(self, state: ExamRuntimePreviewState) -> None:
        """恢复一步前瞻快照。"""

        self._uid_counter = int(state.uid_counter)
        self.np_random.bit_generator.state = deepcopy(state.random_state)
        self.turn = int(state.turn)
        self.max_turns = int(state.max_turns)
        self.terminated = bool(state.terminated)
        self.last_info = dict(state.last_info)
        self.deck = deque(self._clone_runtime_card(card) for card in state.deck)
        self.hand = [self._clone_runtime_card(card) for card in state.hand]
        self.grave = [self._clone_runtime_card(card) for card in state.grave]
        self.hold = [self._clone_runtime_card(card) for card in state.hold]
        self.lost = [self._clone_runtime_card(card) for card in state.lost]
        self.playing = [self._clone_runtime_card(card) for card in state.playing]
        self.current_card = self._clone_runtime_card(state.current_card) if state.current_card is not None else None
        self.drinks = [dict(drink) for drink in state.drinks]
        self._support_upgrade_original_rows = {int(key): dict(value) for key, value in state.support_upgrade_original_rows.items()}
        self.score = float(state.score)
        self.score_per_color = dict(state.score_per_color)
        self.stamina = float(state.stamina)
        self.max_stamina = float(state.max_stamina)
        self.stance = str(state.stance)
        self.stance_level = int(state.stance_level)
        self.stance_locked = bool(state.stance_locked)
        self.play_limit = int(state.play_limit)
        self.start_turn_draw_penalty = int(state.start_turn_draw_penalty)
        self.extra_turns = int(state.extra_turns)
        self.panic_cost_overrides = dict(state.panic_cost_overrides)
        self.current_turn_color = str(state.current_turn_color)
        self.turn_color_history = list(state.turn_color_history)
        self.score_bonus_multiplier = float(state.score_bonus_multiplier)
        self.resources = defaultdict(float, state.resources)
        self.turn_counters = Counter(state.turn_counters)
        self.total_counters = Counter(state.total_counters)
        self.search_history = Counter(state.search_history)
        self.active_effects = [copy(item) for item in state.active_effects]
        self.active_enchants = [copy(item) for item in state.active_enchants]
        self.scheduled_effects = [copy(item) for item in state.scheduled_effects]
        self.gimmick_rows = [dict(row) for row in state.gimmick_rows]
        self._resolving_enchant_uids = set(state.resolving_enchant_uids)
        self._resolved_gimmick_keys = set(state.resolved_gimmick_keys)
        self.forbidden_card_search_ids = Counter(state.forbidden_card_search_ids)
        self.lesson_cleared = bool(state.lesson_cleared)
        self.clear_state = str(state.clear_state)
        self.rank_state = ExamRankState(
            self_rank=int(state.rank_state.self_rank),
            rival_scores=list(state.rank_state.rival_scores),
            pass_condition=str(state.rank_state.pass_condition),
            rank_threshold=int(state.rank_state.rank_threshold),
            score_threshold=float(state.rank_state.score_threshold),
            force_end_score=float(state.rank_state.force_end_score),
            passed=bool(state.rank_state.passed),
        )
        self.event_log = [ExamEvent(turn=event.turn, event_type=event.event_type, detail=dict(event.detail)) for event in state.event_log]
        self._milestone_flags = dict(state.milestone_flags)
        self._consecutive_end_turns = int(state.consecutive_end_turns)
        self._prev_score = float(state.prev_score)
        self._prev_resource_stock = float(state.prev_resource_stock)
        self._cached_reward_signal = None if state.cached_reward_signal is None else float(state.cached_reward_signal)
        self.resolution = deepcopy(state.resolution)
        for name, value in state.lifecycle_state.items():
            setattr(self, name, deepcopy(value))

    def _next_uid(self) -> int:
        """生成运行时对象使用的递增 uid。"""

        self._uid_counter += 1
        return self._uid_counter

    def _resolve_battle_kind(self, battle_kind: str | None) -> str:
        """解析当前战斗是考试/课程哪一类。"""

        normalized = str(battle_kind or '').strip().lower()
        if normalized in {'lesson', 'exam', 'audition'}:
            return normalized
        return 'lesson' if 'Lesson' in str(self.stage_type or '') else 'exam'

    def _infer_stage_lesson_type(self, stage_type: str | None) -> str:
        """从 stepType 推断固定课程类型；考试未提供序列时返回 Unknown。"""

        stage = str(stage_type or '')
        if 'LessonVocal' in stage:
            return 'ProduceStepLessonType_LessonVocal'
        if 'LessonDance' in stage:
            return 'ProduceStepLessonType_LessonDance'
        if 'LessonVisual' in stage:
            return 'ProduceStepLessonType_LessonVisual'
        if 'LessonSp' in stage:
            return 'ProduceStepLessonType_LessonSp'
        return 'ProduceStepLessonType_Unknown'

    def _resolve_selected_battle_row(self) -> dict[str, Any] | None:
        """按显式 row id 或偶像卡难度配置选择本局实际考试行。"""

        if self.battle_kind == 'lesson':
            return None
        all_rows = self.repository.audition_rows(self.scenario, self.stage_type)
        if self.audition_row_id:
            matched = []
            for row in all_rows:
                row_id = str(row.get('id') or '')
                row_number = int(row.get('number') or 0)
                row_selector = f'{row_id}:{row_number}'
                battle_config_id = str(row.get('produceExamBattleConfigId') or '')
                if self.audition_row_id in {row_selector, battle_config_id}:
                    matched.append(row)
                elif self.audition_row_id == row_id and len([item for item in all_rows if str(item.get('id') or '') == row_id]) == 1:
                    matched.append(row)
            if not matched:
                raise ValueError(f'Audition row not found for stage {self.stage_type}: {self.audition_row_id}')
            if len(matched) > 1:
                examples = ', '.join(
                    f"{str(row.get('id') or '')}:{int(row.get('number') or 0)}"
                    for row in matched[:5]
                )
                raise ValueError(
                    f'Audition selector matched multiple rows for stage {self.stage_type}: '
                    f'{self.audition_row_id}. use one of [{examples}]'
                )
            return matched[0]
        audition_difficulty_id = str(self.loadout.stat_profile.audition_difficulty_id or '') if self.loadout is not None else ''
        rows = self.repository.audition_rows(
            self.scenario,
            self.stage_type,
            audition_difficulty_id=audition_difficulty_id or None,
        )
        if not rows:
            return None
        if len(rows) == 1:
            return rows[0]
        if self.scenario.route_type == 'nia' and self.explicit_fan_votes is not None:
            selected = self.repository.select_audition_row(
                self.scenario,
                self.stage_type,
                audition_difficulty_id=audition_difficulty_id or None,
                fan_votes=self.explicit_fan_votes,
            )
            if selected is not None:
                return selected
        row_ids = ', '.join(str(format_audition_row_selector(row) or '') for row in rows[:5])
        raise ValueError(
            f'Ambiguous audition rows for stage {self.stage_type}; '
            f'provide loadout.audition_difficulty_id or audition_row_id. examples=[{row_ids}]'
        )

    def _build_lesson_battle_profile_from_master(self) -> dict[str, float]:
        """为课程战斗构造主数据库来源的基础 profile。"""

        audition_difficulty_id = str(self.loadout.stat_profile.audition_difficulty_id or '') if self.loadout is not None else ''
        profile = dict(
            self.repository.battle_profile(
                self.scenario,
                self.scenario.default_stage,
                audition_difficulty_id=audition_difficulty_id or None,
            )
        )
        if self._initial_lesson_target_value is not None:
            profile['base_score'] = self._initial_lesson_target_value
        if self._initial_lesson_perfect_value is not None:
            profile['force_end_score'] = self._initial_lesson_perfect_value
        if self._initial_turn_limit is not None:
            profile['turns'] = float(self._initial_turn_limit)
        return profile

    def _build_battle_profile(self, stage_row: dict[str, Any] | None) -> dict[str, Any]:
        """从显式关卡行或主数据库 profile 构造 battle profile。"""

        if stage_row is not None:
            config = self.repository.battle_config_map.get(str(stage_row.get('produceExamBattleConfigId') or '')) or {}
            weight_vector = np.array(
                [
                    float(config.get('vocal') or self.scenario.score_weights[0]),
                    float(config.get('dance') or self.scenario.score_weights[1]),
                    float(config.get('visual') or self.scenario.score_weights[2]),
                ],
                dtype=np.float32,
            )
            weight_sum = float(weight_vector.sum())
            if weight_sum > 0:
                weight_vector = weight_vector / weight_sum
            return {
                'base_score': float(stage_row.get('baseScore') or 0.0),
                'force_end_score': float(stage_row.get('forceEndScore') or 0.0),
                'rank_threshold': float(stage_row.get('rankThreshold') or 0.0),
                'parameter_baseline': float(stage_row.get('parameterBaseLine') or 0.0),
                'fan_vote_baseline': float(stage_row.get('voteCountBaseLine') or 0.0),
                'fan_vote_requirement': float(stage_row.get('voteCount') or 0.0),
                'turns': float(config.get('turn') or self.scenario.exam_turns),
                'vocal_weight': float(weight_vector[0]),
                'dance_weight': float(weight_vector[1]),
                'visual_weight': float(weight_vector[2]),
                # 审查基准相关字段
                'score_config_id': str(config.get('produceExamBattleScoreConfigId') or ''),
                'vocal_excellent': float(config.get('vocalExcellent') or 0),
                'dance_excellent': float(config.get('danceExcellent') or 0),
                'visual_excellent': float(config.get('visualExcellent') or 0),
                'vocal_bad': float(config.get('vocalBad') or 0),
                'dance_bad': float(config.get('danceBad') or 0),
                'visual_bad': float(config.get('visualBad') or 0),
                # NPC 组相关字段
                'npc_group_id': str(stage_row.get('produceExamBattleNpcGroupId') or ''),
            }
        if self.battle_kind == 'lesson':
            return self._build_lesson_battle_profile_from_master()
        profile = dict(self.repository.stage_thresholds.get((self.scenario.produce_id, self.stage_type), {}))
        if profile:
            return profile
        raise KeyError(
            'Battle profile not found in master database: '
            f'produce_id={self.scenario.produce_id}, stage_type={self.stage_type}, '
            f'audition_row_id={self.audition_row_id}'
        )

    def _fan_vote_enabled_for_mode(self) -> bool:
        """考试模式下始终保留 NIA fan vote 相关规则。"""

        return self.battle_kind != 'lesson' and self.scenario.route_type == 'nia'

    def _turn_color_enabled(self) -> bool:
        """仅 lesson 模式禁用考试回合颜色。"""

        return self.battle_kind != 'lesson'

    def _uses_clear_training_rules(self) -> bool:
        """lesson 与 clear reward 共享训练课目标规则。"""

        return self.battle_kind == 'lesson' or self.reward_mode == 'clear'

    def _current_clear_target(self) -> float:
        """返回当前训练课 clear 目标值。"""

        if not self._uses_clear_training_rules():
            return 0.0
        if self.lesson_target_value is not None:
            return max(float(self.lesson_target_value), 0.0)
        return max(float(self.profile.get('base_score') or 0.0), 0.0)

    def _current_perfect_target(self) -> float:
        """返回当前训练课 perfect 目标值。

        优先使用主数据 ProduceStepLessonLevel.resultTargetValueLimit 传入的值。
        仅在主数据未提供且 reward_mode=clear 时，使用 2x clear_target 作为
        兜底估算（非手册规定，仅用于缺少主数据时的回退）。
        """

        if not self._uses_clear_training_rules():
            return 0.0
        # 优先使用主数据 resultTargetValueLimit
        if self.lesson_perfect_value is not None:
            return max(float(self.lesson_perfect_value), 0.0)
        # 兜底：主数据缺失时用 2x clear_target 近似，但应通过 resolve_lesson_training_spec 传入
        clear_target = self._current_clear_target()
        if clear_target > 0:
            logger.warning(
                'Perfect 目标值未从主数据传入，使用 2x clear_target=%0.1f 近似。'
                '请通过 lesson_perfect_value 参数传入 ProduceStepLessonLevel.resultTargetValueLimit',
                clear_target * 2.0,
            )
            return clear_target * 2.0
        return 0.0

    def _reported_fan_vote_baseline(self) -> float:
        """返回当前考试的 fan vote 基准。"""

        if not self._fan_vote_enabled_for_mode():
            return 0.0
        return float(self.profile.get('fan_vote_baseline') or 0.0)

    def _reported_fan_vote_requirement(self) -> float:
        """返回当前考试的 fan vote 门槛。"""

        if not self._fan_vote_enabled_for_mode():
            return 0.0
        return float(self.profile.get('fan_vote_requirement') or 0.0)

    def _resolve_initial_fan_votes(self, explicit_fan_votes: float | None) -> float:
        """解析当前考试上下文的初始 fan vote。"""

        if not self._fan_vote_enabled_for_mode():
            return 0.0
        if explicit_fan_votes is not None:
            return max(float(explicit_fan_votes), 0.0)
        baseline = self._reported_fan_vote_baseline()
        if baseline > 0:
            return baseline
        requirement = self._reported_fan_vote_requirement()
        return max(requirement, 0.0)

    def _current_lesson_type(self) -> str:
        """返回当前战斗上下文中的课程类型。"""

        lesson_types = self._current_lesson_types()
        if lesson_types:
            return lesson_types[0]
        if self.lesson_sequence and 1 <= self.turn <= len(self.lesson_sequence):
            return self.lesson_sequence[self.turn - 1]
        return self.default_lesson_type

    def _current_lesson_types(self) -> tuple[str, ...]:
        """返回当前 lesson 上下文有效的课程类型集合。"""

        if self.lesson_sequence and 1 <= self.turn <= len(self.lesson_sequence):
            return (self.lesson_sequence[self.turn - 1],)
        if self.battle_kind == 'lesson' and self.clear_state in {'cleared', 'perfect'} and self.lesson_post_clear_types:
            return self.lesson_post_clear_types
        if self.battle_kind != 'lesson' and self.current_turn_color:
            # 考试的回合属性等价于「〇〇ターンのみ」条件（Pアイテム【ボーカルレッスン・ボーカルターンのみ】）。
            mapped = TURN_COLOR_LESSON_TYPES.get(self.current_turn_color)
            if mapped:
                return (mapped,)
        return self.default_lesson_types

    def _lesson_target_remaining(self) -> float:
        """课程模式下离清课目标还差多少。"""

        if not self._uses_clear_training_rules():
            return 0.0
        target = self._current_clear_target()
        return max(target - self.score, 0.0) if target > 0 else 0.0

    def _lesson_perfect_remaining(self) -> float:
        """课程模式下离 Perfect Lesson 还差多少。"""

        if not self._uses_clear_training_rules():
            return 0.0
        perfect = self._current_perfect_target()
        return max(perfect - self.score, 0.0) if perfect > 0 else 0.0

    def remaining_turns_including_current(self) -> int:
        """含当前回合与追加回合的剩余回合数（UI 里的「残りnターン」）。"""

        if self.turn > self.max_turns:
            return max(int(self.extra_turns), 0) + 1
        return max(self.max_turns - self.turn + 1, 0) + max(int(self.extra_turns), 0)

    def _remaining_turns_after_current_action(self) -> int:
        """当前动作结算后仍然剩余的回合数。"""

        return max(self.max_turns - self.turn, 0)

    def _perfect_finish_recovery_turns(self) -> int:
        """Perfect 结算时按手册返回应折算回体的剩余回合数。"""

        if self.battle_kind == 'lesson':
            return max(self.max_turns - self.turn + 1, 0)
        return self._remaining_turns_after_current_action()

    def _update_clear_state_after_score_change(self) -> None:
        """按课程目标/Perfect 门槛或考试最高分更新本局通关状态。

        帮助文档：試験に挑んだ際に、スコアが獲得できる最大値に到達すると、
        挑んだ試験は自動的に合格となり終了します。
        """

        # 考试模式下，达到 force_end_score 时自动合格结束
        if self.battle_kind != 'lesson' and not self._uses_clear_training_rules():
            force_end_score = float(self.profile.get('force_end_score') or 0.0)
            if force_end_score > 0 and self.score >= force_end_score:
                self._cap_score_to_force_end(force_end_score)
                if self.clear_state != 'force_end':
                    self.clear_state = 'force_end'
                    self.rank_state.passed = True
                    self._record_event('force_end_reached', {
                        'score': self.score,
                        'force_end_score': force_end_score,
                    })
                self.terminated = True
            # 更新排名合格判定
            self._update_self_rank()
            if not self.rank_state.passed and self.rank_state.self_rank <= self.rank_state.rank_threshold:
                self.rank_state.passed = True
                self._record_event('rank_passed', {
                    'self_rank': self.rank_state.self_rank,
                    'rank_threshold': self.rank_state.rank_threshold,
                })
            return

        if not self._uses_clear_training_rules():
            return
        target = self._current_clear_target()
        perfect = self._current_perfect_target()
        if perfect > 0 and self.score >= perfect:
            # 课程超过 PERFECT 的分数被截断（gakumas-core `remainingIncrementableScore`）。
            self._cap_score_to_force_end(perfect)
            self.lesson_cleared = True
            if self.clear_state != 'perfect':
                recovery = self._perfect_finish_recovery_turns() * self.lesson_perfect_recovery_per_turn
                if recovery > 0:
                    self.stamina = min(self.max_stamina, self.stamina + recovery)
            self.clear_state = 'perfect'
            self.terminated = True
            return
        if target > 0 and self.score >= target:
            self.lesson_cleared = True
            self.clear_state = 'cleared'
            if self.reward_mode == 'clear' and self.battle_kind != 'lesson':
                self.terminated = True

    def _cap_score_to_force_end(self, force_end_score: float) -> None:
        """达到考试最高分时把总分和当前颜色分数同步封顶。"""

        overshoot = max(float(self.score) - float(force_end_score), 0.0)
        if overshoot <= 0.0:
            return
        self.score = float(force_end_score)
        if self.current_turn_color in self.score_per_color:
            self.score_per_color[self.current_turn_color] = max(
                self.score_per_color[self.current_turn_color] - overshoot,
                0.0,
            )

    def reset(self) -> None:
        """重置考试战斗状态并进入第一个回合。"""

        if self.observation_only:
            raise RuntimeError('Observed runtime cannot reset; consume an absolute checkpoint')
        self.event_log = []
        self.resolution = ResolutionState()
        deck_cards = self._build_runtime_deck(self.initial_deck_rows)
        self.np_random.shuffle(deck_cards)
        if self.replay_hooks is not None and self.replay_hooks.initial_deck_order:
            deck_cards = reorder_by_build_index(
                deck_cards,
                self.replay_hooks.initial_deck_order,
                lambda card: card.build_index,
            )
        # 「レッスン開始時手札に入る」（ProduceCard.isInitial）的卡在第 1 回合抽牌前移到山札顶端，相对顺序不变。
        deck_cards = [card for card in deck_cards if self._is_innate_card(card)] + [
            card for card in deck_cards if not self._is_innate_card(card)
        ]
        self._turn_start_phase_active = False
        self._resource_turn_start_snapshot = {}
        self.turn = 0
        self.terminated = False
        self.last_info = {}
        self.deck = deque(deck_cards)
        self.hand = []
        self.grave = []
        self.hold = []
        self.lost = []
        self.playing = []
        self.current_card = None
        self._current_play_uid_floor = None
        self.drinks = [dict(row) for row in self.initial_drinks]
        self._support_upgrade_original_rows = {}

        self.score = 0.0
        self.score_per_color = {'vocal': 0.0, 'dance': 0.0, 'visual': 0.0}
        default_stamina = 12.0 if self.scenario.route_type == 'first_star' else 15.0
        loadout_stamina = float(self.loadout.stat_profile.stamina) if self.loadout is not None else 0.0
        self.max_stamina = (self.configured_max_stamina if self.configured_max_stamina is not None
                            else loadout_stamina if loadout_stamina > 0 else default_stamina)
        opening_stamina = self.max_stamina if self.starting_stamina is None else self.starting_stamina
        self.stamina = float(np.clip(opening_stamina, 0.0, self.max_stamina))
        self.stance = 'neutral'
        self.stance_level = 0
        self.stance_locked = False
        self.play_limit = self._base_play_limit()
        self.start_turn_draw_penalty = 0
        self.extra_turns = 0
        self.panic_cost_overrides = {}
        self.current_turn_color = ''
        self.turn_color_history = []
        self.score_bonus_multiplier = self.base_score_bonus_multiplier

        self.resources = defaultdict(float)
        self.resources['block'] = 0.0
        self.resources['full_power_point'] = 0.0
        self.resources['stamina_consumption_down'] = 0.0
        self.resources['parameter_buff_multiple_per_turn'] = 0.0
        self.resources['panic'] = 0.0
        self.resources['slump'] = 0.0
        self.resources['enthusiastic'] = 0.0

        self.turn_counters = Counter()
        self.total_counters = Counter()
        self.search_history = Counter()
        self.active_effects = []
        self.active_enchants = []
        self.scheduled_effects = []
        self.gimmick_rows = self._load_stage_gimmicks()
        self._resolving_enchant_uids = set()
        self.resolving_enchant_card = None
        self._resolved_gimmick_keys = set()
        self.forbidden_card_search_ids = Counter()
        self.lesson_cleared = False
        self.clear_state = 'ongoing'
        self.rank_state = ExamRankState(
            rank_threshold=int(self.profile.get('rank_threshold') or 3),
            score_threshold=float(self.profile.get('base_score') or 0.0),
            force_end_score=float(self.profile.get('force_end_score') or 0.0),
        )
        self._init_rival_scores()
        self._milestone_flags = {'25': False, '50': False, '75': False, '100': False}
        self._consecutive_end_turns = 0
        self._prev_score = 0.0
        self._prev_resource_stock = 0.0
        self._cached_reward_signal = None
        self._sync_stance_resources()
        self._sync_effect_resources()
        self._sync_forbidden_search_resources()

        for enchant_spec in self.initial_status_enchants:
            self._register_initial_enchant(
                str(enchant_spec['enchant_id']),
                source=str(enchant_spec.get('source') or 'produce'),
                remaining_turns=enchant_spec.get('effect_turn'),
                remaining_count=enchant_spec.get('effect_count'),
                source_identity=str(enchant_spec.get('source_identity') or ''),
            )

        self._dispatch_phase('ProduceExamPhaseType_ExamStartExam')
        self._start_turn()
        # 缓存 reset 后的基准 reward signal，避免 step 时重复计算动作前状态。
        self._cached_reward_signal = self._reward_signal()

    def legal_actions(self) -> list[ExamActionCandidate]:
        """枚举当前可执行的出牌、饮料和结束回合动作。"""

        if self.terminated:
            return [ExamActionCandidate(label='结束', kind='noop', payload={'kind': 'noop'})]

        candidates: list[ExamActionCandidate] = []
        for card in self.hand:
            if self._can_play_card(card):
                candidates.append(
                    ExamActionCandidate(
                        label=self._card_label(card),
                        kind='card',
                        payload={'kind': 'card', 'uid': card.uid},
                    )
                )
        for index, drink in enumerate(self.drinks):
            if self._can_use_drink(drink):
                candidates.append(
                    ExamActionCandidate(
                        label=self.repository.drink_name(drink),
                        kind='drink',
                        payload={'kind': 'drink', 'index': index},
                    )
                )
        end_turn_label = 'SKIP' if self.battle_kind == 'lesson' else '结束回合'
        candidates.append(ExamActionCandidate(label=end_turn_label, kind='end_turn', payload={'kind': 'end_turn'}))
        return candidates

    def step(self, action: ExamActionCandidate) -> tuple[float, dict[str, Any]]:
        """执行一个考试动作，并返回增量奖励与状态摘要。"""

        if self.observation_only:
            raise RuntimeError('Observed runtime cannot step; consume an actual result')
        rc = self.reward_config
        reward_before = self._cached_reward_signal
        if reward_before is None:
            reward_before = self._reward_signal()
        score_before = self.score
        resource_stock_before = self._resource_stock()

        # ── 执行动作 ──
        skipped_turn = False
        if action.kind == 'card':
            card = self._remove_hand_card(int(action.payload['uid']))
            if card is None:
                raise KeyError(f'Card uid {action.payload["uid"]} is not in hand')
            self._play_card(card)
            self._consecutive_end_turns = 0
            if not self.terminated and not self._has_remaining_play_window():
                self._end_turn(skipped=False)
        elif action.kind == 'drink':
            self._use_drink(int(action.payload['index']))
            self._consecutive_end_turns = 0
        elif action.kind == 'end_turn':
            # 仍有出牌次数时主动结束回合即为スキップ（gakumas-engine TurnManager.endTurn；本家录像里出过一张卡后
            # 再スキップ也回复 2 体力）。出牌次数用尽时回合会自动结束，不会走到这里。
            skipped_turn = self._has_remaining_play_window()
            self._consecutive_end_turns += 1
            if not self.terminated:
                self._end_turn(skipped=skipped_turn)
        else:
            self.terminated = True

        reward_after = self._reward_signal()
        self._cached_reward_signal = reward_after

        # ── 基础潜势差分奖励 ──
        reward = reward_after - reward_before

        # ── 动作类型微奖励 ──
        if action.kind == 'card' and rc.card_play_reward != 0.0:
            reward += rc.card_play_reward
        if action.kind == 'drink' and rc.drink_use_reward != 0.0:
            reward += rc.drink_use_reward

        # ── 分数差分密集奖励 ──
        if rc.score_delta_scale != 0.0:
            target = self._evaluation_goal_target()
            score_delta = (self.score - score_before) / max(target, 1.0)
            reward += score_delta * rc.score_delta_scale

        # ── 资源增量密集奖励 ──
        if rc.resource_gain_scale != 0.0:
            resource_delta = self._resource_stock() - resource_stock_before
            if resource_delta > 0:
                reward += self._resource_curve(resource_delta, 10.0) * rc.resource_gain_scale

        # ── 里程碑一次性奖励 ──
        reward += self._check_milestones()

        # ── 截断 / 惩罚 ──
        if action.kind == 'end_turn' and skipped_turn and rc.skip_turn_penalty != 0.0:
            reward += rc.skip_turn_penalty
        if rc.consecutive_end_turn_penalty != 0.0 and self._consecutive_end_turns >= 2:
            reward += rc.consecutive_end_turn_penalty * (self._consecutive_end_turns - 1)
        if self.terminated and self.stamina <= 0 and rc.stamina_death_penalty != 0.0:
            reward += rc.stamina_death_penalty

        # ── 全局缩放与裁剪 ──
        reward *= rc.reward_scale
        if rc.reward_clip > 0:
            reward = max(min(reward, rc.reward_clip), -rc.reward_clip)

        # ── 更新追踪 ──
        self._prev_score = self.score
        self._prev_resource_stock = self._resource_stock()

        target_score = self._target_score()
        info = {
            'action': action.label,
            'kind': action.kind,
            'reward_mode': self.reward_mode,
            'battle_kind': self.battle_kind,
            'score': self.score,
            'target_score': target_score,
            'score_ratio': self.score / max(target_score, 1.0),
            'evaluation_target_score': self._evaluation_goal_target(),
            'evaluation_score_ratio': self._evaluation_goal_ratio(),
            'stamina': self.stamina,
            'turn': self.turn,
            'stance': self.stance,
            'turn_color': self.current_turn_color,
            'turn_color_label': self.turn_color_label(),
            'fan_votes': self.fan_votes,
            'fan_vote_baseline': self._reported_fan_vote_baseline(),
            'fan_vote_requirement': self._reported_fan_vote_requirement(),
            'clear_state': self.clear_state,
            'rank': self.rank_state.self_rank,
            'passed': self.rank_state.passed,
            'rival_scores': list(self.rank_state.rival_scores),
            'deck': len(self.deck),
            'hand': len(self.hand),
            'grave': len(self.grave),
            'hold': len(self.hold),
            'lost': len(self.lost),
        }
        if self._uses_clear_training_rules():
            info['lesson_cleared'] = self.lesson_cleared
            info['lesson_target_remaining'] = self._lesson_target_remaining()
            info['lesson_perfect_remaining'] = self._lesson_perfect_remaining()
        self.last_info = info
        return reward, info

    def _check_milestones(self) -> float:
        """检查分数里程碑并返回一次性奖励。"""

        rc = self.reward_config
        primary_ratio = self._primary_goal_ratio()
        bonus = 0.0
        for threshold, key, reward_val in (
            (0.25, '25', rc.milestone_25_reward),
            (0.50, '50', rc.milestone_50_reward),
            (0.75, '75', rc.milestone_75_reward),
            (1.00, '100', rc.milestone_100_reward),
        ):
            if reward_val != 0.0 and not self._milestone_flags[key] and primary_ratio >= threshold:
                self._milestone_flags[key] = True
                bonus += reward_val
        return bonus

    def _target_score(self) -> float:
        """返回当前考试阶段的目标分数。"""

        if self._uses_clear_training_rules():
            clear_target = self._current_clear_target()
            perfect_target = self._current_perfect_target()
            if self.battle_kind == 'lesson' and self.lesson_cleared and perfect_target > 0:
                return max(perfect_target, 1.0)
            if clear_target > 0:
                return max(clear_target, 1.0)
        return float(self.profile.get('base_score') or 1.0)

    def _future_gimmick_count(self) -> int:
        """统计当前回合之后仍未触发的场地 gimmick 数量。"""

        return sum(1 for row in self.gimmick_rows if int(row.get('startTurn') or 0) > self.turn)

    def _resource_stock(self) -> float:
        """估算当前保留下来的正向资源库存，用于 clear 模式的节奏奖励。"""

        return (
            self.resources['review'] * 0.8
            + self.resources['aggressive'] * 0.8
            + self.resources['parameter_buff']
            + self.resources['lesson_buff']
            + self.resources['block'] * 0.3
            + self.resources['concentration'] * 0.4
            + self.resources['full_power_point'] * 0.3
        )

    def _reward_profile_config(self) -> RewardConfig:
        """返回当前生效的奖励配置对象。"""

        return self.reward_config

    def _plan_reward_family(self) -> str:
        """把偶像 plan type 归并成奖励层使用的资源流派。"""

        if self.loadout is None:
            return 'common'
        plan_type = str(self.loadout.stat_profile.plan_type or '')
        return PLAN_REWARD_FAMILY.get(plan_type, 'common')

    def _turn_progress_ratio(self) -> float:
        """返回当前局面已消耗的回合进度。"""

        return min(max(self.turn / max(self.max_turns, 1), 0.0), 1.0)

    def _remaining_turn_ratio(self) -> float:
        """返回当前局面剩余回合占比。"""

        return max(self.max_turns - self.turn + 1, 0) / max(self.max_turns, 1)

    def _stamina_ratio(self) -> float:
        """返回当前体力占比。"""

        return self.stamina / max(self.max_stamina, 1.0)

    def _primary_goal_ratio(self) -> float:
        """返回当前局面对主要通关目标的进度比。"""

        if self._uses_clear_training_rules():
            target = float(self._current_clear_target() or self._target_score() or 0.0)
        else:
            target = float(self.profile.get('base_score') or self._target_score() or 0.0)
        return self.score / max(target, 1.0)

    def _secondary_goal_ratio(self) -> float:
        """返回当前局面对次级终局目标的进度比。"""

        if self._uses_clear_training_rules():
            target = float(self._current_perfect_target() or self._current_clear_target() or self._target_score() or 0.0)
            return self.score / max(target, 1.0)
        force_end_score = float(self.profile.get('force_end_score') or 0.0)
        if force_end_score > 0:
            return self.score / max(force_end_score, 1.0)
        return self._primary_goal_ratio()

    def _evaluation_goal_target(self) -> float:
        """返回终局评价目标分数；高分模式优先对齐最高分/强制结束线。"""

        if self._uses_clear_training_rules():
            target = self._current_perfect_target() or self._current_clear_target() or self._target_score()
            return max(float(target), 1.0)
        pass_target = float(self.profile.get('base_score') or self._target_score() or 0.0)
        force_end_score = float(self.profile.get('force_end_score') or 0.0)
        return max(pass_target, force_end_score, 1.0)

    def _evaluation_goal_ratio(self) -> float:
        """返回当前局面对终局评价目标的进度比。"""

        return self.score / self._evaluation_goal_target()

    def _fan_vote_reference(self) -> float:
        """返回 NIA fan vote 的主数据基准值。"""

        if not self._fan_vote_enabled_for_mode():
            return 1.0
        baseline = self._reported_fan_vote_baseline()
        if baseline > 0:
            return baseline
        requirement = self._reported_fan_vote_requirement()
        if requirement > 0:
            return requirement
        return 1.0

    def _fan_vote_progress(self) -> float:
        """返回当前 fan vote 相对主数据基准的进度。"""

        if not self._fan_vote_enabled_for_mode():
            return 0.0
        return max(self.fan_votes, 0.0) / max(self._fan_vote_reference(), 1.0)

    def _fan_vote_score_multiplier(self) -> float:
        """把 fan vote 进度映射到 NIA 局内得分倍率。"""

        if not self._fan_vote_enabled_for_mode():
            return 1.0
        progress = max(self._fan_vote_progress(), 0.0)
        if progress <= 1.0:
            return 0.80 + 0.20 * math.sqrt(progress)
        bonus = 0.15 * math.log1p(progress - 1.0) / math.log(3.0)
        return min(1.0 + bonus, 1.20)

    def _fan_vote_gain_stage_scale(self) -> float:
        """估算当前 NIA 难度下 fan vote 奖励的量级。"""

        baseline = self._reported_fan_vote_baseline()
        requirement = self._reported_fan_vote_requirement()
        return max(requirement * 0.50, baseline * 0.15, 800.0)

    def estimate_fan_vote_gain(self, score: float | None = None) -> float:
        """按当前总分估算本场 NIA 结束时可获得的 fan vote。"""

        if not self._fan_vote_enabled_for_mode():
            return 0.0
        current_score = max(float(self.score if score is None else score), 0.0)
        base_score = float(self.profile.get('base_score') or 0.0)
        score_ratio = current_score / max(base_score, 1.0)
        quality = min(self._score_value_curve(score_ratio), 1.4)
        return self._fan_vote_gain_stage_scale() * (0.35 + 0.65 * quality)

    def _fan_vote_gain_value(self) -> float:
        """把 fan vote 奖励估算压成 reward 可用的有界值。"""

        if not self._fan_vote_enabled_for_mode():
            return 0.0
        return min(self.estimate_fan_vote_gain() / max(self._fan_vote_gain_stage_scale(), 1.0), 1.4)

    def _clear_finish_value(self) -> float:
        """clear 终止时动态估算 perfect 段的潜在补偿价值。"""

        if self.reward_mode != 'clear':
            return 0.0
        stock_value = self._resource_curve(self._resource_stock(), 26.0)
        stamina_value = self._stamina_ratio()
        turn_value = self._remaining_turn_ratio()
        if self.clear_state == 'perfect':
            return 0.90 + stock_value * 0.85 + stamina_value * 0.20 + turn_value * 0.25
        if self.clear_state == 'cleared':
            return stock_value * (0.70 + 0.30 * turn_value) + stamina_value * 0.35 + turn_value * 0.25
        return 0.0

    def _score_value_curve(self, ratio: float) -> float:
        """把原始得分比压成边际递减的终局价值近似。"""

        normalized = max(float(ratio), 0.0)
        progress = min(normalized, 1.0)
        overshoot = max(normalized - 1.0, 0.0)
        return progress + (math.log1p(overshoot * 3.0) / math.log(4.0)) * 0.35

    def _resource_curve(self, value: float, soft_cap: float) -> float:
        """对资源库存做边际递减压缩，避免囤积奖励线性膨胀。"""

        clipped = max(float(value), 0.0)
        if clipped <= 0.0:
            return 0.0
        return min(math.log1p(clipped) / math.log1p(max(soft_cap, 1.0)), 1.5)

    def _judging_alignment(self) -> float:
        """估算当前三维和审查权重的匹配程度。"""

        if self.battle_kind == 'lesson':
            return 1.0 / 3.0
        weights = np.array(
            [
                float(self.profile.get('vocal_weight') or 0.0),
                float(self.profile.get('dance_weight') or 0.0),
                float(self.profile.get('visual_weight') or 0.0),
            ],
            dtype=np.float32,
        )
        weight_sum = float(weights.sum())
        stats = np.clip(np.array(self.parameter_stats, dtype=np.float32), 0.0, None)
        stat_sum = float(stats.sum())
        if weight_sum <= 1e-6 or stat_sum <= 1e-6:
            return 1.0 / 3.0
        return float(np.dot(stats / stat_sum, weights / weight_sum))

    def _turn_window_value(self) -> float:
        """把当前回合颜色窗口转换成 reward 可用的局面价值。"""

        if self.battle_kind == 'lesson':
            return 0.0
        base_multiplier = max(self.base_score_bonus_multiplier, 0.25)
        color_ratio = self._effective_score_bonus_multiplier() / base_multiplier
        return float(np.clip(math.tanh((color_ratio - 1.0) * 1.4), -0.75, 0.75))

    def _phi_goal(self) -> float:
        """潜势函数：离真实目标还有多远。"""

        primary_ratio = self._primary_goal_ratio()
        secondary_ratio = self._evaluation_goal_ratio()
        progress = min(primary_ratio, 1.0)
        secondary_progress = min(secondary_ratio, 1.0)
        pace_gap = progress - self._turn_progress_ratio()
        finish_bonus = 0.0
        if self._uses_clear_training_rules():
            if self.clear_state == 'cleared':
                finish_bonus += 0.35 + self._clear_finish_value() * 0.15
            elif self.clear_state == 'perfect':
                finish_bonus += 0.80 + self._clear_finish_value() * 0.10
        else:
            if primary_ratio >= 1.0:
                finish_bonus += 0.25 + self._remaining_turn_ratio() * 0.35
            force_end_score = float(self.profile.get('force_end_score') or 0.0)
            if force_end_score > 0 and self.score >= force_end_score:
                finish_bonus += 0.55
        return progress * 1.15 + secondary_progress * 0.35 + pace_gap * 0.55 + finish_bonus

    def _phi_eval(self, config: RewardConfig) -> float:
        """潜势函数：当前局面的终局评价边际价值。"""

        evaluation_ratio = self._evaluation_goal_ratio()
        score_value = self._score_value_curve(evaluation_ratio)
        judging_alignment = self._judging_alignment()
        turn_window_value = self._turn_window_value()
        alignment_weight = float(config.judging_alignment_weight)
        value = score_value * (0.70 + judging_alignment * alignment_weight)
        value += turn_window_value * float(config.turn_window_weight)
        if self.reward_mode == 'clear':
            value += self._clear_finish_value() * 0.20
        if self._fan_vote_enabled_for_mode():
            value += self._fan_vote_gain_value() * 0.30
        return value

    def _phi_archetype(self) -> float:
        """潜势函数：按 plan 感知未来资源的可兑现价值。"""

        remaining_turn_ratio = self._remaining_turn_ratio()
        delayed_scale = 0.35 + 0.65 * remaining_turn_ratio
        window_scale = 1.0 if self.reward_mode == 'clear' else 0.65 + 0.35 * max(self._turn_window_value(), 0.0)
        family = self._plan_reward_family()
        family_scale = {
            'sense': self.reward_config.sense_resource_scale,
            'logic': self.reward_config.logic_resource_scale,
            'anomaly': self.reward_config.anomaly_resource_scale,
        }.get(family, 1.0)
        if family == 'sense':
            concentration_value = self._resource_curve(self.resources['concentration'], 16.0)
            aggressive_value = self._resource_curve(self.resources['aggressive'], 8.0)
            burst_readiness = min(concentration_value, 1.0) * min(aggressive_value, 1.0)
            return family_scale * (
                self._resource_curve(self.resources['parameter_buff'], 8.0) * (1.10 * window_scale)
                + self._resource_curve(self.resources['review'], 14.0) * (0.95 * delayed_scale)
                + concentration_value * (0.80 + 0.35 * delayed_scale)
                + aggressive_value * (0.35 + 0.45 * min(concentration_value, 1.0) + 0.20 * max(window_scale, 0.0))
                + burst_readiness * (0.65 + 0.35 * max(window_scale, delayed_scale))
                + self._resource_curve(self.resources['parameter_buff_multiple_per_turn'], 3.0) * delayed_scale
                + self._resource_curve(self.resources['lesson_buff'], 10.0) * 0.45
            )
        if family == 'logic':
            return family_scale * (
                self._resource_curve(self.resources['aggressive'], 18.0) * (1.05 * delayed_scale)
                + self._resource_curve(self.resources['block'], 18.0) * (0.90 * delayed_scale)
                + self._resource_curve(self.resources['lesson_buff'], 10.0) * 0.35
                + self._resource_curve(self.resources['stamina_consumption_down'], 6.0) * 0.25
            )
        if family == 'anomaly':
            full_power_progress = self._resource_curve(self.resources['full_power_point'], FULL_POWER_POINT_THRESHOLD)
            if self.resources['full_power_point'] >= FULL_POWER_POINT_THRESHOLD:
                full_power_progress += 0.25
            return family_scale * (
                self._resource_curve(self.resources['concentration'], 2.0) * (0.95 * window_scale)
                + self._resource_curve(self.resources['preservation'], 3.0) * (0.85 * delayed_scale)
                + self._resource_curve(self.resources['over_preservation'], 2.0) * delayed_scale
                + full_power_progress * 1.15
                + self._resource_curve(self.resources['enthusiastic'], 10.0) * (0.65 + 0.35 * max(window_scale, delayed_scale))
            )
        return (
            self._resource_curve(self.resources['parameter_buff'], 6.0) * 0.65
            + self._resource_curve(self.resources['review'], 10.0) * 0.55
            + self._resource_curve(self.resources['aggressive'], 10.0) * 0.55
            + self._resource_curve(self.resources['lesson_buff'], 10.0) * 0.40
        )

    def _phi_risk(self) -> float:
        """潜势函数：失败风险、负面状态和体力断线风险。"""
        negative_penalty = (
            self.resources['sleepy'] * 0.30
            + self.resources['panic'] * 0.28
            + self.resources['slump'] * 0.24
            + self.resources['active_skill_forbidden'] * 0.35
            + self.resources['mental_skill_forbidden'] * 0.35
        )
        tempo_pressure = max(self._turn_progress_ratio() - min(self._primary_goal_ratio(), 1.20), 0.0)
        low_stamina = max(0.35 - self._stamina_ratio(), 0.0) / 0.35
        future_gimmick_pressure = min(self._future_gimmick_count(), 3) * 0.08 * max(1.0 - self._primary_goal_ratio(), 0.0)
        remaining_drinks = sum(1 for drink in self.drinks if not drink.get('_consumed'))
        safety = self._stamina_ratio() * 0.75 + min(remaining_drinks, 2) * 0.12
        return safety - negative_penalty - tempo_pressure * 0.90 - low_stamina * 0.80 - future_gimmick_pressure

    def _phi_efficiency(self, config: RewardConfig) -> float:
        """潜势函数：在主要目标可达后，鼓励更高效地收官。"""

        efficiency_gate = float(config.efficiency_gate)
        gate = max(min((self._primary_goal_ratio() - efficiency_gate) / max(1.0 - efficiency_gate, 1e-6), 1.0), 0.0)
        if gate <= 0.0:
            return 0.0
        remaining_drinks = sum(1 for drink in self.drinks if not drink.get('_consumed'))
        spare_value = (
            self._stamina_ratio() * 0.70
            + self._remaining_turn_ratio() * 0.45
            + min(remaining_drinks, 2) * 0.18
            + min(self._resource_stock(), 12.0) / 12.0 * 0.15
        )
        overshoot = max(self._primary_goal_ratio() - 1.0, 0.0)
        if not self._uses_clear_training_rules():
            overshoot = max(self._evaluation_goal_ratio() - 1.0, 0.0)
        return gate * spare_value - overshoot * float(config.efficiency_overshoot_penalty)

    def _potential_value(self, config: RewardConfig) -> float:
        """统一潜势函数；step() 会对它做差分得到 shaping。"""

        return (
            float(config.goal_weight) * self._phi_goal()
            + float(config.eval_weight) * self._phi_eval(config)
            + float(config.archetype_weight) * self._phi_archetype()
            + float(config.risk_weight) * self._phi_risk()
            + float(config.efficiency_weight) * self._phi_efficiency(config)
        )

    def _terminal_utility(self, config: RewardConfig) -> float:
        """终局效用：只在回合真正结束时发放。"""

        if not self.terminated:
            return 0.0
        stamina_term = self._stamina_ratio() * float(config.terminal_stamina_weight)
        speed_term = self._remaining_turn_ratio() * float(config.terminal_speed_weight)
        overshoot_penalty = float(config.overshoot_penalty)
        if self._uses_clear_training_rules():
            clear_target = float(self._current_clear_target() or self._target_score() or 0.0)
            clear_ratio = self.score / max(clear_target, 1.0)
            perfect_ratio = self._secondary_goal_ratio()
            utility = self._score_value_curve(perfect_ratio) * float(config.terminal_eval_weight)
            if self.clear_state == 'perfect':
                utility += float(config.lesson_perfect_reward) + speed_term + self._clear_finish_value() * 0.25
            elif self.clear_state == 'cleared':
                utility += float(config.lesson_clear_reward) + self._clear_finish_value()
            else:
                utility -= float(config.terminal_failure_weight) * min(max(1.0 - clear_ratio, 0.0), 1.0)
            utility += stamina_term
            utility -= max(perfect_ratio - 1.0, 0.0) * overshoot_penalty
            return utility

        primary_ratio = self._primary_goal_ratio()
        evaluation_ratio = self._evaluation_goal_ratio()
        utility = self._score_value_curve(evaluation_ratio) * float(config.terminal_eval_weight)
        if primary_ratio >= 1.0:
            utility += float(config.terminal_pass_reward) + speed_term
        else:
            utility -= float(config.terminal_failure_weight) * min(max(1.0 - primary_ratio, 0.0), 1.0)
        utility += stamina_term
        utility -= max(evaluation_ratio - 1.0, 0.0) * overshoot_penalty
        force_end_score = float(self.profile.get('force_end_score') or 0.0)
        if force_end_score > 0 and self.score >= force_end_score:
            utility += float(config.terminal_force_end_bonus)
        if self._fan_vote_enabled_for_mode():
            utility += self._fan_vote_gain_value() * float(config.terminal_nia_bonus)
        return utility

    def _utility_reward_signal(self) -> float:
        """统一奖励信号：终局效用加 potential-based shaping。"""

        config = self._reward_profile_config()
        return self._terminal_utility(config) + float(config.shape_scale) * self._potential_value(config)

    def _score_reward_signal(self) -> float:
        """高分导向 reward，内部走统一终局效用 + shaping 框架。"""

        return self._utility_reward_signal()

    def _clear_reward_signal(self) -> float:
        """过线导向 reward，内部走统一终局效用 + shaping 框架。"""

        return self._utility_reward_signal()

    def _reward_signal(self) -> float:
        """按 reward mode 构造供训练使用的平滑奖励信号。"""

        if self.reward_mode == 'clear':
            return self._clear_reward_signal()
        return self._score_reward_signal()

    def _build_runtime_deck(self, card_rows: Iterable[dict[str, Any]]) -> list[RuntimeCard]:
        """把主数据卡行转换成可变的运行时卡实例。"""

        cards = []
        for build_index, row in enumerate(card_rows):
            grow_effect_ids = [
                str(value)
                for value in row.get('produceCardGrowEffectIds', []) or row.get('growEffectIds', [])
                if value
            ]
            runtime_card = RuntimeCard(
                uid=self._next_uid(),
                card_id=str(row.get('id')),
                upgrade_count=int(row.get('upgradeCount') or 0),
                base_card=row,
                grow_effect_ids=list(grow_effect_ids),
                card_status_enchant_id=str(row.get('produceCardStatusEnchantId') or ''),
                build_index=build_index,
            )
            cards.append(runtime_card)
            self._record_event('card_acquired', {
                'card_id': runtime_card.card_id,
                'card_name': self.repository.card_name(row),
                'upgrade_count': runtime_card.upgrade_count,
                'destination': 'deck',
                'source': 'initial_deck',
            })
            initial_add_count = 0
            for grow_effect_id in grow_effect_ids:
                grow_row = self.grow_effects.first(str(grow_effect_id))
                if grow_row and str(grow_row.get('effectType') or '') == 'ProduceCardGrowEffectType_InitialAdd':
                    initial_add_count += 1
            for _ in range(initial_add_count):
                duplicate = runtime_card.clone(uid=self._next_uid())
                cards.append(duplicate)
                self._record_event('card_acquired', {
                    'card_id': duplicate.card_id,
                    'card_name': self.repository.card_name(row),
                    'upgrade_count': duplicate.upgrade_count,
                    'destination': 'deck',
                    'source': 'initial_add',
                })
        return cards

    def _lookup_score_permil(self, parameter_value: float, stat_key: str) -> float:
        """从 ProduceExamBattleScoreConfig 分段函数中查表返回参数对应的千分率。

        Args:
            parameter_value: 当前参数值
            stat_key: 属性键名，如 'vocal'/'dance'/'visual'

        Returns:
            对应的千分率值；无分段数据时返回 1000.0（即 1.0 倍基准）
        """
        score_config_id = str(self.profile.get('score_config_id') or '')
        if not score_config_id:
            return 1000.0
        segments = self.repository.battle_score_config_segments.get(score_config_id)
        if not segments:
            return 1000.0
        permil_key = f'{stat_key}Permil'
        # 线性插值查找：在 parameter 分段之间做插值
        if parameter_value <= float(segments[0].get('parameter') or 0):
            return float(segments[0].get(permil_key) or 1000.0)
        for i in range(len(segments) - 1):
            low_param = float(segments[i].get('parameter') or 0)
            high_param = float(segments[i + 1].get('parameter') or 0)
            if parameter_value <= high_param:
                low_permil = float(segments[i].get(permil_key) or 1000.0)
                high_permil = float(segments[i + 1].get(permil_key) or 1000.0)
                if high_param <= low_param:
                    return high_permil
                ratio = (parameter_value - low_param) / (high_param - low_param)
                return low_permil + (high_permil - low_permil) * ratio
        return float(segments[-1].get(permil_key) or 1000.0)

    def _judging_trend_multiplier(self) -> float:
        """根据当前回合颜色和审查基准分段函数计算审查基准加成。

        手册规则：审查基准を満たしているとスコアボーナスが上昇しやすくなり、
        満たしていないと上昇しにくくなる。
        使用 ProduceExamBattleScoreConfig 的分段函数计算实际千分率与基准(1000)的比值。
        """
        if not self._turn_color_enabled():
            return 1.0
        color_index = TURN_COLOR_INDEX.get(self.current_turn_color)
        if color_index is None:
            return 1.0
        stat_keys = ['vocal', 'dance', 'visual']
        stat_key = stat_keys[color_index]
        selected_stat = float(np.array(self.parameter_stats, dtype=np.float32)[color_index])
        # 从分段函数查当前参数对应的千分率
        actual_permil = self._lookup_score_permil(selected_stat, stat_key)
        # 基准千分率为 1000（1.0倍），实际比值即为审查基准加成
        return max(actual_permil / 1000.0, 0.0)

    def _default_score_bonus_multiplier(self) -> float:
        """根据偶像属性与亲爱度估算默认分数倍率。"""

        if self.loadout is None:
            return 1.0
        weights = np.array(
            [
                float(self.profile.get('vocal_weight') or self.scenario.score_weights[0]),
                float(self.profile.get('dance_weight') or self.scenario.score_weights[1]),
                float(self.profile.get('visual_weight') or self.scenario.score_weights[2]),
            ],
            dtype=np.float32,
        )
        stats = np.array(self.parameter_stats, dtype=np.float32)
        weighted_parameter = float(np.dot(stats, weights))
        baseline = float(self.profile.get('parameter_baseline') or 0.0)
        if baseline <= 0.0:
            audition_difficulty_id = str(self.loadout.stat_profile.audition_difficulty_id or '') if self.loadout is not None else ''
            default_profile = self.repository.battle_profile(
                self.scenario,
                self.scenario.default_stage,
                audition_difficulty_id=audition_difficulty_id or None,
            )
            baseline = float(default_profile.get('parameter_baseline') or 0.0)
        if baseline <= 0.0:
            raise ValueError(
                'Battle parameter baseline is missing from master database: '
                f'produce_id={self.scenario.produce_id}, stage_type={self.stage_type}'
            )
        dearness_ratio = 1.0 + min(max(int(self.loadout.dearness_level), 0), 20) * 0.01
        return max((weighted_parameter / baseline) * dearness_ratio, 0.25)

    def _init_rival_scores(self) -> None:
        """从 ProduceExamBattleNpcGroup 初始化 Rival 分数列表。

        每个 NPC 的初始分数从 scoreMin~scoreMax 范围随机取值。
        """
        npc_group_id = str(self.profile.get('npc_group_id') or '')
        if not npc_group_id:
            self.rank_state.rival_scores = []
            return
        npc_rows = self.repository.npc_group_map.get(npc_group_id, [])
        self.rank_state.rival_scores = []
        for npc_row in npc_rows:
            score_min = float(npc_row.get('scoreMin') or 0)
            score_max = float(npc_row.get('scoreMax') or 0)
            if score_max > score_min:
                initial_score = float(self.np_random.uniform(score_min, score_max))
            else:
                initial_score = score_min
            self.rank_state.rival_scores.append(initial_score)

    def _simulate_rival_turn_scores(self) -> None:
        """每回合为每个 Rival 按阶段分配得分。

        从 ProduceExamBattleNpcGroup 读取：
        - scoreMin/scoreMax：NPC 分数范围（基础分）
        - opScorePermil/midScorePermil/edScorePermil：前/中/后期得分分布比例

        每回合 Rival 得分 = baseScore * phasePermil / 1000，
        baseScore 从 scoreMin~scoreMax 随机取值。
        """
        npc_group_id = str(self.profile.get('npc_group_id') or '')
        if not npc_group_id or not self.rank_state.rival_scores:
            return
        npc_rows = self.repository.npc_group_map.get(npc_group_id, [])
        if not npc_rows:
            return
        total_turns = self.max_turns
        if total_turns <= 0:
            return
        # 判断当前回合属于前/中/后期
        phase_ratio = (self.turn - 1) / total_turns
        for i, npc_row in enumerate(npc_rows):
            if i >= len(self.rank_state.rival_scores):
                break
            score_min = float(npc_row.get('scoreMin') or 0)
            score_max = float(npc_row.get('scoreMax') or 0)
            # 选择阶段得分比例
            if phase_ratio < 1.0 / 3.0:
                phase_permil = float(npc_row.get('opScorePermil') or 333)
            elif phase_ratio < 2.0 / 3.0:
                phase_permil = float(npc_row.get('midScorePermil') or 333)
            else:
                phase_permil = float(npc_row.get('edScorePermil') or 334)
            # 从 scoreMin~scoreMax 随机取基础分
            if score_max > score_min:
                base_score = float(self.np_random.uniform(score_min, score_max))
            else:
                base_score = score_min
            turn_score = base_score * phase_permil / 1000.0
            self.rank_state.rival_scores[i] += turn_score

    def _update_self_rank(self) -> None:
        """根据玩家分数和 Rival 分数计算当前排名。"""
        if not self.rank_state.rival_scores:
            self.rank_state.self_rank = 1
            return
        # 排名 = 比自己分数高的 Rival 数量 + 1
        rank = 1
        for rival_score in self.rank_state.rival_scores:
            if rival_score > self.score:
                rank += 1
        self.rank_state.self_rank = rank
        """根据偶像属性与亲爱度估算默认分数倍率。"""

        if self.loadout is None:
            return 1.0
        weights = np.array(
            [
                float(self.profile.get('vocal_weight') or self.scenario.score_weights[0]),
                float(self.profile.get('dance_weight') or self.scenario.score_weights[1]),
                float(self.profile.get('visual_weight') or self.scenario.score_weights[2]),
            ],
            dtype=np.float32,
        )
        stats = np.array(self.parameter_stats, dtype=np.float32)
        weighted_parameter = float(np.dot(stats, weights))
        baseline = float(self.profile.get('parameter_baseline') or 0.0)
        if baseline <= 0.0:
            audition_difficulty_id = str(self.loadout.stat_profile.audition_difficulty_id or '') if self.loadout is not None else ''
            default_profile = self.repository.battle_profile(
                self.scenario,
                self.scenario.default_stage,
                audition_difficulty_id=audition_difficulty_id or None,
            )
            baseline = float(default_profile.get('parameter_baseline') or 0.0)
        if baseline <= 0.0:
            raise ValueError(
                'Battle parameter baseline is missing from master database: '
                f'produce_id={self.scenario.produce_id}, stage_type={self.stage_type}'
            )
        dearness_ratio = 1.0 + min(max(int(self.loadout.dearness_level), 0), 20) * 0.01
        return max((weighted_parameter / baseline) * dearness_ratio, 0.25)

    def _turn_color_probabilities(self) -> np.ndarray:
        """根据当前培育属性计算考试回合颜色分布。"""

        stats = np.clip(np.array(self.parameter_stats, dtype=np.float32), 0.0, None)
        total = float(stats.sum())
        if total <= 0:
            return np.full(len(TURN_COLOR_ORDER), 1.0 / len(TURN_COLOR_ORDER), dtype=np.float32)
        return stats / total

    def _roll_turn_color(self) -> str:
        """按当前属性权重为新回合抽取颜色。"""

        probabilities = self._turn_color_probabilities()
        index = int(self.np_random.choice(len(TURN_COLOR_ORDER), p=probabilities))
        return TURN_COLOR_ORDER[index]

    def turn_color_label(self) -> str:
        """返回当前回合颜色的人类可读标签。"""

        return TURN_COLOR_LABELS.get(self.current_turn_color, '')

    def turn_color_one_hot(self) -> np.ndarray:
        """把当前回合颜色编码成 one-hot；无颜色时返回全零。"""

        encoded = np.zeros(len(TURN_COLOR_ORDER), dtype=np.float32)
        index = TURN_COLOR_INDEX.get(self.current_turn_color)
        if index is not None:
            encoded[index] = 1.0
        return encoded

    def _effective_score_bonus_multiplier(self) -> float:
        """根据当前回合颜色把局内基准倍率换算成实际得分倍率。

        合并三个因素的影响：
        1. 基准倍率（由参数/baseline/亲爱度决定）
        2. 回合颜色偏移（当回合颜色对应参数高于期望值时倍率上升）
        3. 审查基准加成（由 ProduceExamBattleScoreConfig 分段函数决定）
        """

        if not self._turn_color_enabled():
            return self.base_score_bonus_multiplier
        if self.replay_hooks is not None and self.replay_hooks.score_bonus_percent:
            percent = self.replay_hooks.score_bonus_percent.get(self.current_turn_color)
            if percent is not None:
                return max(float(percent) / 100.0, 0.0)
        color_index = TURN_COLOR_INDEX.get(self.current_turn_color)
        if color_index is None:
            return self.base_score_bonus_multiplier
        if self.repository.battle_score_config_segments.get(str(self.profile.get('score_config_id') or '')):
            # 考试的スコアボーナス% 就是 ProduceExamBattleScoreConfig 按当前属性查表得到的千分比（§5.3：
            # produce-001 最終 parameter 446 → vocalPermil 4402 ≈ 440.2%）。之前的实现在此之外又乘了
            # 「属性/基准线」与「属性/期望属性」两个比例，H.I.F 高属性下会得到 ×70 的倍率（docs/OPEN_ITEMS.md A8）。
            return max(self._judging_trend_multiplier(), 0.0)
        stats = np.clip(np.array(self.parameter_stats, dtype=np.float32), 0.0, None)
        if color_index >= len(stats):
            return self.base_score_bonus_multiplier
        expected_stat = float(np.dot(stats, self._turn_color_probabilities()))
        if expected_stat <= 1e-6:
            return self.base_score_bonus_multiplier
        selected_stat = float(stats[color_index])
        # 回合颜色偏移
        color_ratio = selected_stat / expected_stat
        # 审查基准加成
        trend_multiplier = self._judging_trend_multiplier()
        return max(self.base_score_bonus_multiplier * color_ratio * trend_multiplier, 0.0)

    def _refresh_turn_score_bonus_multiplier(self) -> None:
        """同步当前回合的实际得分倍率。"""

        self.score_bonus_multiplier = self._effective_score_bonus_multiplier()

    def _base_play_limit(self) -> int:
        """返回当前基础每回合可出牌次数。"""

        bonus = 0
        for timed in self.active_effects:
            if str(timed.effect.get('effectType') or '') == 'ProduceExamEffectType_ExamPlayableValueAdd':
                # 计数型：PlayableValueAdd 是每回合可出牌次数加成，整数语义
                bonus += max(int(timed.remaining_count or 0), 0)
        return 1 + max(bonus, 0)

    @property
    def score_bonus_permil(self) -> int:
        """当前回合的スコアボーナス整数千分比（1794% → 17940）。"""

        return score_bonus_permil(self.score_bonus_multiplier)

    def _score_gain(self, value: float) -> float:
        """最終スコア = ceil(パラメータ × スコアボーナス%)（§5.1 S3；课程倍率为 1 时恒等）。"""

        return float(apply_permil_ceil(ceil_int(value), self.score_bonus_permil))

    def _raw_effect_value(self, effect: dict[str, Any]) -> float:
        """读取效果主数值，不附带运行时修正。"""

        return float(effect.get('effectValue1') or 0)

    def _timed_effects_of_type(self, effect_type: str) -> list[TimedExamEffect]:
        """按效果类型筛选当前激活中的持续效果。"""

        return [item for item in self.active_effects if str(item.effect.get('effectType') or '') == effect_type]

    def _has_timed_effect(self, effect_type: str) -> bool:
        """判断某个持续效果当前是否在场。"""

        return any(str(item.effect.get('effectType') or '') == effect_type for item in self.active_effects)

    def _timed_effect_stack_value(self, effect_type: str, *, default_value: float = 1.0) -> float:
        """累加同类持续效果的主数值，供追加触发类效果复用。"""

        total = 0.0
        for timed in self._timed_effects_of_type(effect_type):
            value = self._raw_effect_value(timed.effect)
            total += value if value > 0 else default_value
        return total

    def _current_card_grow_total(self, grow_effect_type: str) -> float:
        """汇总当前出牌卡上某种成长效果的数值。"""

        if self.current_card is None:
            return 0.0
        total = 0.0
        for grow_effect in self._card_grow_rows(self.current_card):
            if str(grow_effect.get('effectType') or '') == grow_effect_type:
                total += float(grow_effect.get('value') or 0)
        return total

    def _current_card_ratio_bonus(self, grow_effect_type: str) -> float:
        """把当前卡的成长效果加成换算成千分比。"""

        return max(self._current_card_grow_total(grow_effect_type), 0.0) / 1000.0

    def _adjust_direct_gain(self, value: float, add_grow_type: str = '', reduce_grow_type: str = '') -> float:
        """把卡牌成长对直接收益的加减成统一折算出来。"""

        updated = float(value)
        if add_grow_type:
            updated += self._current_card_grow_total(add_grow_type)
        if reduce_grow_type:
            updated -= self._current_card_grow_total(reduce_grow_type)
        if value > 0:
            return max(updated, 1.0 if reduce_grow_type else 0.0)
        return max(updated, 0.0)

    def _card_matches_search(self, card: RuntimeCard, search_id: str) -> bool:
        """判断当前卡是否命中给定的检索条件。"""

        if not search_id:
            return False
        selection = self._search_cards(search_id, acting_card=card, target_card=card)
        return any(candidate.uid == card.uid for candidate in selection.selected)

    def _consume_timed_effect_uid(self, uid: int) -> None:
        """消费一层按次数生效的持续效果。"""

        next_effects: list[TimedExamEffect] = []
        for timed in self.active_effects:
            if timed.uid == uid and timed.remaining_count is not None:
                timed.remaining_count -= 1
            if timed.remaining_count is not None and timed.remaining_count <= 0:
                continue
            next_effects.append(timed)
        self.active_effects = next_effects
        self._sync_effect_resources()

    def _matched_play_count_buff_effects(self, card: RuntimeCard) -> list[TimedExamEffect]:
        """返回对当前卡生效的追加发动持续效果。"""

        matched: list[TimedExamEffect] = []
        for timed in self.active_effects:
            if str(timed.effect.get('effectType') or '') != 'ProduceExamEffectType_ExamCardSearchEffectPlayCountBuff':
                continue
            search_id = str(timed.effect.get('produceCardSearchId') or '')
            if self._card_matches_search(card, search_id):
                matched.append(timed)
        return matched

    def _matching_search_stamina_overrides(self, card: RuntimeCard) -> list[TimedExamEffect]:
        """返回对当前卡生效的消耗体力覆写效果。"""

        matched: list[TimedExamEffect] = []
        for timed in self.active_effects:
            if str(timed.effect.get('effectType') or '') != 'ProduceExamEffectType_ExamSearchPlayCardStaminaConsumptionChange':
                continue
            search_id = str(timed.effect.get('produceCardSearchId') or '')
            if self._card_matches_search(card, search_id):
                matched.append(timed)
        return matched

    def _card_repeat_bonus(self, card: RuntimeCard) -> int:
        """计算当前卡会被额外重复发动几次。"""

        if str(card.base_card.get('rarity') or '') == 'ProduceCardRarity_Legend':
            return 0
        bonus = 0
        for timed in self._matched_play_count_buff_effects(card):
            # 计数型：额外发动次数，整数语义
            bonus += int(round(self._raw_effect_value(timed.effect)))
        return max(bonus, 0)

    def _consume_card_play_buffs(self, card: RuntimeCard) -> None:
        """在卡牌结算后消费按次数触发的目标卡持续效果。"""

        # 仅在 `_play_card` 过程中按 uid 水位过滤：本次出牌新挂的「次に使用するスキルカード」类效果
        # 对当前这张卡不生效。非出牌路径（直接调用）不过滤。
        uid_floor = getattr(self, '_current_play_uid_floor', None)
        consume_uids = {
            timed.uid
            for timed in self._matched_play_count_buff_effects(card) + self._matching_search_stamina_overrides(card)
            if timed.remaining_count is not None and (uid_floor is None or timed.uid <= uid_floor)
        }
        for uid in sorted(consume_uids):
            self._consume_timed_effect_uid(uid)

    def _effective_card_trigger_ids(self, card: RuntimeCard) -> list[str]:
        """解析卡牌当前实际使用的出牌触发器。"""

        trigger_ids = []
        if card.base_card.get('playProduceExamTriggerId'):
            trigger_ids.append(str(card.base_card['playProduceExamTriggerId']))
        trigger_ids.extend(card.transient_trigger_ids)
        for grow_effect in self._card_grow_rows(card):
            if str(grow_effect.get('effectType') or '') != 'ProduceCardGrowEffectType_PlayTriggerChange':
                continue
            next_trigger = str(grow_effect.get('playProduceExamTriggerId') or '')
            if not next_trigger:
                continue
            target_ids = {str(value) for value in grow_effect.get('targetPlayEffectProduceExamTriggerIds', []) if value}
            if target_ids:
                if not trigger_ids or not any(trigger_id in target_ids for trigger_id in trigger_ids):
                    continue
            trigger_ids = [next_trigger]
        return [value for value in trigger_ids if value]

    def _resolved_card_play_effects(self, card: RuntimeCard) -> list[dict[str, str]]:
        """解析卡牌当前实际会结算的直接出牌效果与触发器。"""

        resolved = [
            {
                'effect_id': str(play_effect.get('produceExamEffectId') or ''),
                'trigger_id': str(play_effect.get('produceExamTriggerId') or ''),
            }
            for play_effect in card.base_card.get('playEffects', [])
            if play_effect.get('produceExamEffectId')
        ]
        resolved.extend({'effect_id': effect_id, 'trigger_id': ''} for effect_id in card.transient_effect_ids if effect_id)
        for grow_effect in self._card_grow_rows(card):
            effect_type = str(grow_effect.get('effectType') or '')
            if effect_type == 'ProduceCardGrowEffectType_EffectAdd' and grow_effect.get('playProduceExamEffectId'):
                resolved.append({'effect_id': str(grow_effect['playProduceExamEffectId']), 'trigger_id': ''})
            elif effect_type == 'ProduceCardGrowEffectType_EffectChange' and grow_effect.get('playProduceExamEffectId'):
                next_effect_id = str(grow_effect['playProduceExamEffectId'])
                target_ids = {str(value) for value in grow_effect.get('targetPlayProduceExamEffectIds', []) if value}
                if target_ids:
                    for item in resolved:
                        if item['effect_id'] in target_ids:
                            item['effect_id'] = next_effect_id
                elif resolved:
                    for item in resolved:
                        item['effect_id'] = next_effect_id
                else:
                    resolved.append({'effect_id': next_effect_id, 'trigger_id': ''})
            elif effect_type == 'ProduceCardGrowEffectType_PlayEffectTriggerChange' and grow_effect.get('playEffectProduceExamTriggerId'):
                next_trigger_id = str(grow_effect['playEffectProduceExamTriggerId'])
                target_ids = {str(value) for value in grow_effect.get('targetPlayEffectProduceExamTriggerIds', []) if value}
                for item in resolved:
                    if not target_ids or item['trigger_id'] in target_ids:
                        item['trigger_id'] = next_trigger_id
        return [item for item in resolved if item['effect_id']]

    def _grow_cost_resource_key(self, effect_type: str, fallback_cost_type: str) -> str:
        """把成长效果名称映射到对应的体力或资源消耗槽。"""

        mapped = GROW_EFFECT_COST_RESOURCE_MAP.get(effect_type)
        if mapped:
            return mapped
        return COST_RESOURCE_MAP.get(fallback_cost_type, fallback_cost_type)

    def _sync_effect_resources(self) -> None:
        """把持续效果投影到观测和 reward 使用的资源槽。"""

        self.resources['parameter_buff_multiple_per_turn'] = float(sum(
            timed.remaining_turns if timed.remaining_turns is not None else 1
            for timed in self._timed_effects_of_type(ExamEffect.PARAMETER_BUFF_MULTIPLE_PER_TURN)
        ))
        self.resources['panic'] = float(len(self._timed_effects_of_type('ProduceExamEffectType_ExamPanic')))
        self.resources['slump'] = float(len(self._timed_effects_of_type('ProduceExamEffectType_ExamGimmickSlump')))
        self.resources['stance_lock'] = float(len(self._timed_effects_of_type(ExamEffect.STANCE_LOCK)))
        self.resources['stamina_consumption_down'] = float(
            any(
                str(item.effect.get('effectType') or '')
                in {
                    'ProduceExamEffectType_ExamStaminaConsumptionDown',
                    'ProduceExamEffectType_ExamStaminaConsumptionDownFix',
                    'ProduceExamEffectType_ExamSearchPlayCardStaminaConsumptionChange',
                }
                for item in self.active_effects
            )
        )

    def _sync_forbidden_search_resources(self) -> None:
        """把搜索型禁卡状态压缩回观测资源槽。"""

        active = 0
        mental = 0
        for search_id, count in self.forbidden_card_search_ids.items():
            if count <= 0:
                continue
            search = self.card_searches.first(search_id)
            categories = {str(value) for value in (search or {}).get('cardCategories', []) if value}
            if categories and categories.issubset({'ProduceCardCategory_ActiveSkill'}):
                active += count
            if categories and categories.issubset({'ProduceCardCategory_MentalSkill'}):
                mental += count
        self.resources['active_skill_forbidden'] = float(active)
        self.resources['mental_skill_forbidden'] = float(mental)

    def _matches_forbidden_search(self, card: RuntimeCard) -> bool:
        """检查一张卡是否命中当前场上的禁卡搜索条件。"""

        return any(
            count > 0 and self._card_matches_search(card, search_id)
            for search_id, count in self.forbidden_card_search_ids.items()
        )

    def _status_change_origin(self, source: str | None) -> str:
        """把内部 effect source 归一化为状态变化来源。"""

        normalized = str(source or '')
        while normalized.startswith('scheduled:'):
            normalized = normalized.removeprefix('scheduled:')
        return normalized if normalized in STATUS_CHANGE_TRIGGER_ORIGINS else 'other'

    def _ceil_positive(self, value: float) -> float:
        """把正向浮点增量按帮助文档要求向上取整。"""

        numeric = float(value)
        if numeric <= 0:
            return 0.0
        return float(math.ceil(numeric - 1e-9))

    def _positive_count(self, value: float) -> int:
        """把正向增量转换为状态变化 phase 的整数值。"""

        return int(self._ceil_positive(value))

    def _dispatch_status_change(self, amount: float, effect_types: list[str], origin: str) -> None:
        """统一派发状态变化事件，并保留合法触发来源。"""

        phase_value = self._positive_count(amount)
        if phase_value <= 0:
            return
        self._dispatch_phase(
            'ProduceExamPhaseType_ExamStatusChange',
            phase_value=phase_value,
            effect_types=effect_types,
            status_change_origin=self._status_change_origin(origin),
        )

    def _compose_referenced_gain(self, base: float = 0.0, referenced: float = 0.0) -> float:
        """把参照值带来的增量按帮助文档规则向上取整，再叠加固定底值。"""

        return max(float(base), 0.0) + self._ceil_positive(referenced)

    def _sync_stance_resources(self) -> None:
        """把指针状态同步到观测中的数值槽。"""

        self.resources['concentration'] = float(self.stance_level if self.stance == 'concentration' else 0.0)
        self.resources['preservation'] = float(self.stance_level if self.stance == 'preservation' else 0.0)
        self.resources['over_preservation'] = 1.0 if self.stance == 'preservation' and self.stance_level >= 3 else 0.0

    def _parameter_buff_gain_value(self, effect: dict[str, Any]) -> float:
        """好调按持续回合数结算，而不是按 effectValue1。"""

        base_turns = float(effect.get('effectTurn') or 0)
        return self._apply_scalar_modifiers('ProduceExamEffectType_ExamParameterBuff', base_turns)

    def _consume_parameter_buff_multiple(self, amount: float) -> None:
        """消耗绝好调剩余回合，耗尽才移除实例。"""

        remaining = int(self._ceil_positive(amount))
        if remaining <= 0:
            return
        next_effects: list[TimedExamEffect] = []
        for timed in self.active_effects:
            effect_type = str(timed.effect.get('effectType') or '')
            if effect_type == 'ProduceExamEffectType_ExamParameterBuffMultiplePerTurn' and remaining > 0:
                if timed.remaining_turns is not None:
                    consumed = min(timed.remaining_turns, remaining)
                    timed.remaining_turns -= consumed
                    remaining -= consumed
                    if timed.remaining_turns <= 0:
                        continue
            next_effects.append(timed)
        self.active_effects = next_effects
        self._sync_effect_resources()

    def _consume_anti_debuff(self, effect_type: str) -> bool:
        """低下状态无效会抵消一次负面状态或场地 debuff。"""

        if effect_type not in ANTI_DEBUFF_EFFECT_TYPES:
            return False
        if self.resources['anti_debuff'] <= 0:
            return False
        self.resources['anti_debuff'] = max(self.resources['anti_debuff'] - 1.0, 0.0)
        return True

    def _gain_enthusiastic(self, amount: float) -> float:
        """结算热意增加量，并套用热意相关修饰。"""

        updated = max(float(amount), 0.0)
        for timed in self.active_effects:
            modifier_type = str(timed.effect.get('effectType') or '')
            if modifier_type == 'ProduceExamEffectType_ExamEnthusiasticAdditive':
                updated += self._raw_effect_value(timed.effect)
            elif modifier_type == 'ProduceExamEffectType_ExamEnthusiasticMultiple':
                updated *= 1.0 + self._ratio_value(timed.effect)
        updated = max(updated, 0.0)
        self.resources['enthusiastic'] += updated
        return updated

    def _gain_block(
        self,
        amount: float,
        effect_type: str = 'ProduceExamEffectType_ExamBlock',
        status_change_origin: str = 'other',
    ) -> float:
        """统一处理元气增长，固定元气不应用干劲、弱气和元气无效修正。"""

        if effect_type == ExamEffect.BLOCK_FIX:
            delta = float(round_genki(amount, self.scoring_rules))
        else:
            # 最終元気 = floor(元気上昇 × 元気上昇率 + 加算 − 減少)（§5.5，seesaawiki 転記：元気は切り捨て）
            delta = float(round_genki(self._apply_scalar_modifiers(ExamEffect.BLOCK, amount), self.scoring_rules))
        self.resources['block'] += delta
        if delta > 0:
            self._dispatch_status_change(delta, [effect_type], origin=status_change_origin)
        return delta

    def _panic_stamina_value(self, card: RuntimeCard) -> float:
        """在随机状态下，为当前回合缓存这张卡的随机体力消耗。"""

        if card.uid not in self.panic_cost_overrides:
            candidates = list(self.exam_setting.get('produceExamPanicStaminaCandidates') or [1, 2, 3])
            self.panic_cost_overrides[card.uid] = float(self.np_random.choice(candidates))
        return self.panic_cost_overrides[card.uid]

    def _selected_audition_row(self) -> dict[str, Any] | None:
        """按偶像卡对应难度组挑选当前考试配置行。"""

        return self.selected_battle_row

    def _load_stage_gimmicks(self) -> list[dict[str, Any]]:
        """读取当前考试关卡对应的 gimmick 列表。"""

        if self.battle_kind == 'lesson':
            return []
        if self.replay_hooks is not None and self.replay_hooks.disable_stage_gimmicks:
            return []
        stage_row = self._selected_audition_row()
        gimmick_id = str(stage_row.get('produceExamGimmickEffectGroupId') or '') if stage_row else ''
        rows = [row for row in self.exam_gimmicks.rows if str(row.get('id')) == gimmick_id] if gimmick_id else []
        rows.sort(key=lambda row: int(row.get('priority') or 0))
        return rows

    def _discard_hand_to_grave(self) -> None:
        """把回合结束后未使用的手牌全部弃到弃牌堆。"""

        if not self.hand:
            return
        self.grave.extend(self.hand)
        self.hand = []

    def _send_to_hand_or_top_deck(self, card: RuntimeCard) -> bool:
        """手牌已满时把新卡改为放到牌堆顶。"""

        hand_limit = int(self.exam_setting.get('handLimit') or 5)
        if len(self.hand) >= hand_limit:
            self.deck.appendleft(card)
            return False
        self.hand.append(card)
        self._apply_card_move_effects(card, 'hand')
        return True

    @effect_group
    def _apply_card_move_effects(self, card: RuntimeCard, destination: str) -> None:
        """Resolve a card's own arrival effects; moving is not playing the card.

        Native rows currently use Hand/Hold and have no conditional trigger list.
        Unknown conditions fail explicitly. Existing ambient phase dispatch is separate.
        """
        row = card.base_card
        effect_ids = row.get('moveProduceExamEffectIds') or []
        trigger_ids = row.get('moveProduceExamTriggerIds') or []
        if not effect_ids and not trigger_ids:
            return
        target = row.get('moveEffectTriggerType')
        if target not in {'ProduceCardMoveEffectTriggerType_Hand', 'ProduceCardMoveEffectTriggerType_Hold'}:
            raise ValueError('unsupported card move destination')
        if trigger_ids:
            raise ValueError('unsupported card move conditions')
        if target != 'ProduceCardMoveEffectTriggerType_' + destination.title():
            return
        depth = getattr(self, '_card_move_effect_depth', 0)
        if depth >= 32:
            raise ValueError('card move effects exceeded 32 nested arrivals')
        effects = []
        for key in effect_ids:
            effect = self.repository.exam_effect_map.get(key)
            if effect is None:
                raise ValueError('unknown card move effect: ' + key)
            effects.append(effect)
        previous_card = self.current_card
        previous_floor = getattr(self, '_current_play_uid_floor', None)
        self.current_card = card
        self._current_play_uid_floor = None
        self._card_move_effect_depth = depth + 1
        try:
            self._record_event('card_move_effect_triggered', {
                'card_uid': card.uid, 'card_id': card.card_id,
                'destination': destination, 'effect_ids': list(effect_ids),
            })
            for effect in effects:
                self._apply_exam_effect(effect, source='card_move')
                if self.terminated:
                    break
        finally:
            self.current_card = previous_card
            self._current_play_uid_floor = previous_floor
            self._card_move_effect_depth = depth

    def _is_offensive_card(self, card: RuntimeCard) -> bool:
        """判断一张卡是否属于可直接输出的主动技能。"""

        return str(card.base_card.get('category') or '') == 'ProduceCardCategory_ActiveSkill'

    def _start_turn(self) -> None:
        """推进到新回合，并处理开场抽牌与阶段效果。"""

        self.turn += 1
        self.turn_counters = Counter()
        self.play_limit = self._base_play_limit()
        self.panic_cost_overrides = {}
        self.forbidden_card_search_ids = Counter()
        self._sync_forbidden_search_resources()
        if self.turn > self.max_turns and self.extra_turns <= 0:
            self.current_turn_color = ''
            self._refresh_turn_score_bonus_multiplier()
            self.terminated = True
            return
        if self.extra_turns > 0 and self.turn > self.max_turns:
            self.extra_turns -= 1
        self._turn_start_phase_active = True
        if not self._turn_color_enabled():
            self.current_turn_color = ''
        else:
            forced_color = self.replay_hooks.turn_color(self.turn) if self.replay_hooks is not None else None
            self.current_turn_color = forced_color or (
                self.turn_color_history[-1] if self.turn > self.max_turns and self.turn_color_history
                else self._roll_turn_color()
            )
            self.turn_color_history.append(self.current_turn_color)
            self._record_event('turn_color_assigned', {
                'color': self.current_turn_color,
                'label': self.turn_color_label(),
            })
        self._refresh_turn_score_bonus_multiplier()

        # 考试模式下每回合模拟 Rival 得分并更新排名
        if self.battle_kind != 'lesson' and not self._uses_clear_training_rules():
            self._simulate_rival_turn_scores()
            self._update_self_rank()

        # 好印象和好调都会在新回合开始时自然衰减；上一回合开始时才获得（或回合中新获得）的不减（§3.5 ターン経過減免）。
        for resource_key in ('review', 'parameter_buff'):
            if self.resources[resource_key] <= 0:
                continue
            if self.scoring_rules.fresh_modifier_no_decay and not self._resource_turn_start_snapshot.get(resource_key, False):
                continue
            self.resources[resource_key] = max(self.resources[resource_key] - 1.0, 0.0)

        self._decay_turn_effects()
        full_power_ready = self.resolution.full_power_ready
        if full_power_ready is None:
            full_power_ready = self.resources['full_power_point'] >= FULL_POWER_POINT_THRESHOLD
        self.resolution.full_power_ready = False
        if self.stance == 'full_power':
            self._release_full_power()
            if self.terminated:
                return
        if (
            full_power_ready
            and self.stance != 'full_power'
            and not self._is_stance_change_locked()
        ):
            self.resources['full_power_point'] = max(self.resources['full_power_point'] - FULL_POWER_POINT_THRESHOLD, 0.0)
            self._enter_full_power()
        self._apply_gimmicks_for_turn(self.turn)
        if self.terminated:
            return
        if self.replay_hooks is not None:
            for hook in self.replay_hooks.turn_start_hooks.get(self.turn, []):
                hook(self)
                if self.terminated:
                    return
        self._dispatch_phase('ProduceExamPhaseType_ExamStartTurn', phase_value=self.turn)
        if self.terminated:
            return
        draw_count = int(self.exam_setting.get('turnStartDistribute') or 3) - self.start_turn_draw_penalty
        draw_count = max(draw_count, 0)
        if self.turn == 1:
            # 第 1 回合把山札顶端的「レッスン開始時手札に入る」卡全部抽入（不超过手牌上限）。
            hand_limit = int(self.exam_setting.get('handLimit') or 5)
            innate_top = 0
            for card in self.deck:
                if not self._is_innate_card(card):
                    break
                innate_top += 1
            draw_count = max(draw_count, min(innate_top, hand_limit))
        self.start_turn_draw_penalty = 0
        self._draw(draw_count)
        self._record_event('turn_draw_completed', {'hand_uids': [card.uid for card in self.hand]})
        if self.resolution.return_hold_after_draw:
            self.resolution.return_hold_after_draw = False
            self._move_hold_cards_to_hand()
        self._dispatch_phase(ExamPhase.START_PLAY, phase_value=self.turn)
        if self.terminated:
            return
        if self.turn == 1:
            self._dispatch_phase(ExamPhase.START_EXAM_PLAY, phase_value=self.turn)
        if self.turn == 1 and self.replay_hooks is not None:
            for hook in self.replay_hooks.memory_hooks:
                hook(self)
        if self.terminated:
            return
        # R02: start-after -> first-turn memory -> due reservations -> intervals.
        self._dispatch_phase(ExamPhase.TURN_TIMER, phase_value=self.turn)
        self._fire_scheduled_effects()
        if self.terminated:
            return
        self._dispatch_interval_phase(ExamPhase.TURN_INTERVAL, self.turn)
        if self.replay_hooks is None or not self.replay_hooks.disable_support_card_random_upgrade:
            self._apply_support_card_support()
        self._sync_effect_resources()
        self._sync_stance_resources()
        self._finish_turn_start_phase()

    def _finish_turn_start_phase(self) -> None:
        """回合开始阶段结束：记录此刻存在的好印象/好調（供下回合递减判定），关闭回合开始标记。"""

        self._turn_start_phase_active = False
        self._resource_turn_start_snapshot = {
            'review': self.resources['review'] > 0,
            'parameter_buff': self.resources['parameter_buff'] > 0,
        }

    def _effect_applied_turn(self) -> int:
        """新挂持续状态的「获得回合」：回合开始阶段挂上的算作上一回合（回合开始时已存在）。"""

        if self._turn_start_phase_active and self.scoring_rules.fresh_modifier_no_decay:
            return self.turn - 1
        return self.turn

    def apply_effect_as_turn_start(self, effect: dict[str, Any], source: str = 'memory') -> None:
        """以「回合开始阶段」语义应用一条效果（メモリー アビリティ / 応援 等测试注入用）。"""

        previous = self._turn_start_phase_active
        self._turn_start_phase_active = True
        try:
            self._apply_exam_effect(effect, source=source)
        finally:
            self._turn_start_phase_active = previous
        if not previous:
            self._finish_turn_start_phase()

    def _is_innate_card(self, card: RuntimeCard) -> bool:
        """「レッスン開始時手札に入る」判定（ProduceCard.isInitial）。"""

        return bool(card.base_card.get('isInitial'))

    def _support_card_matches_current_context(self, support_card) -> bool:
        """判断一张支援卡是否适用于当前课程或轮盘颜色。"""

        support_type = str(support_card.support_card_type or '')
        if support_type == SUPPORT_TYPE_ASSIST:
            return True
        if self.battle_kind == 'lesson':
            lesson_type = self._current_lesson_type()
            mapping = {
                SUPPORT_TYPE_VOCAL: 'ProduceStepLessonType_LessonVocal',
                SUPPORT_TYPE_DANCE: 'ProduceStepLessonType_LessonDance',
                SUPPORT_TYPE_VISUAL: 'ProduceStepLessonType_LessonVisual',
            }
            return mapping.get(support_type, '') == lesson_type
        mapping = {
            'SupportCardType_Vocal': 'vocal',
            'SupportCardType_Dance': 'dance',
            'SupportCardType_Visual': 'visual',
        }
        return mapping.get(support_type, '') == self.current_turn_color

    def _apply_support_card_upgrade(self, card: RuntimeCard) -> bool:
        """对一张手牌施加本回合有效的临时强化。"""

        original_row = self._support_upgrade_original_rows.get(card.uid)
        if original_row is None:
            original_row = card.base_card
            self._support_upgrade_original_rows[card.uid] = original_row
        original_upgrade = int(original_row.get('upgradeCount') or 0)
        current_upgrade = int(card.base_card.get('upgradeCount') or 0)
        if current_upgrade - original_upgrade >= 3:
            return False
        upgraded_row = self._lookup_card_upgrade_row(str(card.card_id), current_upgrade + 1)
        if upgraded_row is None:
            return False
        card.base_card = upgraded_row
        return True

    def _clear_support_card_upgrades(self) -> None:
        """回合结束时恢复所有临时支援强化。"""

        if not self._support_upgrade_original_rows:
            return
        for zone in (self.hand, self.grave, self.hold, self.lost, self.playing, self.deck):
            for card in zone:
                original_row = self._support_upgrade_original_rows.get(card.uid)
                if original_row is not None:
                    card.base_card = original_row
        self._support_upgrade_original_rows = {}

    def _apply_support_card_support(self) -> None:
        """按支援卡概率触发本回合的技能卡支援。"""

        if not self.support_cards or not self.hand:
            return
        for support_card in self._ordered_support_cards():
            if not self._support_card_matches_current_context(support_card):
                continue
            support_row = self.repository.support_cards.first(str(support_card.support_card_id or ''))
            if support_row is None:
                continue
            trigger_rate = float(support_row.get('produceCardUpgradePermil') or 0.0) / 1000.0
            if trigger_rate <= 0.0 or self.np_random.random() > trigger_rate:
                continue
            search_id = str(support_row.get('upgradeProduceCardSearchId') or '')
            search_row = self.card_searches.first(search_id) if search_id else None
            candidates = [
                card
                for card in self.hand
                if str(card.base_card.get('rarity') or '') != 'ProduceCardRarity_Legend'
                and (search_row is None or self._matches_card_search(card, search_row))
                if self._lookup_card_upgrade_row(str(card.card_id), int(card.base_card.get('upgradeCount') or 0) + 1) is not None
            ]
            if not candidates:
                continue
            weighted_candidates = []
            weights = []
            for card in candidates:
                weighted_candidates.append(card)
                weights.append(max(self._support_upgrade_target_priority(card, support_row), 1e-6))
            probabilities = np.array(weights, dtype=np.float64)
            probabilities = probabilities / max(probabilities.sum(), 1e-8)
            selected = weighted_candidates[int(self.np_random.choice(len(weighted_candidates), p=probabilities))]
            self._apply_support_card_upgrade(selected)

    def _ordered_support_cards(self):
        """按更接近原版的稳定顺序结算支援卡。"""

        def _sort_key(support_card):
            support_row = self.repository.support_cards.first(str(support_card.support_card_id or ''))
            base_rate = int((support_row or {}).get('produceCardUpgradePermil') or 0)
            display_order = int((support_row or {}).get('order') or 0)
            support_level = int(support_card.support_card_level or 0)
            support_id = str(support_card.support_card_id or '')
            return (-base_rate, -support_level, display_order, support_id)

        return tuple(sorted(self.support_cards, key=_sort_key))

    def _support_upgrade_target_priority(self, card: RuntimeCard, support_row: dict[str, Any]) -> float:
        """按支援卡类型与卡牌类别估算技能卡支援目标优先级。"""

        category = str(card.base_card.get('category') or '')
        support_type = str(support_row.get('type') or '')
        priority = 1.0
        original_row = self._support_upgrade_original_rows.get(card.uid)
        original_upgrade = int(original_row.get('upgradeCount') or card.base_card.get('upgradeCount') or 0) if original_row is not None else int(card.base_card.get('upgradeCount') or 0)
        current_upgrade = int(card.base_card.get('upgradeCount') or 0)
        temporary_upgrade_count = max(current_upgrade - original_upgrade, 0)
        priority -= temporary_upgrade_count * 0.28
        if support_type in {'SupportCardType_Vocal', 'SupportCardType_Dance', 'SupportCardType_Visual'}:
            if category == 'ProduceCardCategory_ActiveSkill':
                priority += 0.75
            elif category == 'ProduceCardCategory_MentalSkill':
                priority += 0.15
            elif category == 'ProduceCardCategory_Trouble':
                priority -= 0.45
        elif support_type == 'SupportCardType_Assist':
            if category == 'ProduceCardCategory_MentalSkill':
                priority += 0.65
            elif category == 'ProduceCardCategory_ActiveSkill':
                priority += 0.10
            elif category == 'ProduceCardCategory_Trouble':
                priority -= 0.45
        else:
            if category == 'ProduceCardCategory_ActiveSkill':
                priority += 0.25
            elif category == 'ProduceCardCategory_MentalSkill':
                priority += 0.20
            elif category == 'ProduceCardCategory_Trouble':
                priority -= 0.45
        evaluation = float(card.base_card.get('evaluation') or 0.0)
        priority += min(evaluation / 200.0, 0.35)
        return max(priority, 0.05)

    def _remove_hand_card(self, uid: int) -> RuntimeCard | None:
        """按 uid 从手牌中取出一张卡。"""

        for index, card in enumerate(self.hand):
            if card.uid == uid:
                return self.hand.pop(index)
        return None

    def _can_play_card(self, card: RuntimeCard) -> bool:
        """检查当前状态下这张卡是否允许打出。"""

        if not self._has_remaining_play_window():
            return False
        if self._matches_forbidden_search(card):
            return False
        if not self._card_play_condition_matches(card):
            return False
        cost_stamina, cost_force = self._card_stamina_components(card)
        if self.stamina < cost_force:
            return False
        if self.stamina + self.resources['block'] < cost_stamina + cost_force:
            return False
        for resource_key, amount in self._card_resource_costs(card).items():
            if self.resources[resource_key] < amount:
                return False
        return True

    def _has_remaining_play_window(self) -> bool:
        """当前回合是否仍允许继续行动。"""

        return self.turn_counters['play_count'] < self.play_limit

    def _can_use_drink(self, drink: dict[str, Any]) -> bool:
        """饮料只能在允许使用饮料且本回合仍有出牌窗口时使用。"""

        if drink.get('_consumed'):
            return False
        if str(self.stage_type or '').startswith('ProduceStepType_SelfLesson'):
            return False
        return self._has_remaining_play_window()

    def _refresh_play_limit(self) -> None:
        """把持续效果带来的额外出牌次数同步到当前回合。"""

        self.play_limit = max(self.play_limit, self._base_play_limit()
                              + self.turn_counters['automatic_play_count'])

    def _card_play_condition_matches(self, card: RuntimeCard) -> bool:
        """判断卡面触发条件是否允许当前出牌。"""

        trigger_ids = self._effective_card_trigger_ids(card)
        if not trigger_ids:
            return True
        for trigger_id in trigger_ids:
            trigger = self.repository.exam_trigger_map.get(trigger_id)
            if not trigger:
                continue
            phase_types = [str(value) for value in trigger.get('phaseTypes', []) if value]
            if not phase_types:
                continue
            for phase_type in phase_types:
                if phase_type == 'ProduceExamPhaseType_None':
                    event_phase_value = 0
                else:
                    event_phase_value = self.turn
                event = {
                    'phase_type': phase_type,
                    'phase_value': event_phase_value,
                    'acting_card': card,
                    'effect_types': self.repository.card_exam_effect_types(card.base_card),
                }
                if self._trigger_matches(trigger, event, acting_card=card, target_card=card):
                    return True
        return False

    @effect_group
    def _play_card(self, card: RuntimeCard, *, pay_cost: bool = True,
                   consume_play_window: bool = True, body_enabled: bool = True) -> None:
        """R04/R07/R09: pre-cost conditions, ordered body, post-use, then prepared uses.

        Automatic uses can fail their card condition yet still count as uses.
        Buff-cost versus after-use order is provisional U03: buff-cost first.
        Completed-use counters retain their old numeric-reference semantics; the
        before-body Nth-use event uses the upcoming ordinal.
        """
        self.current_card = card
        self.playing = [card]
        self._current_play_uid_floor = self._uid_counter
        resolved_effect_specs = []
        for play_effect in self._resolved_card_play_effects(card) if body_enabled else ():
            trigger_id = str(play_effect.get('trigger_id') or '')
            trigger = self.repository.exam_trigger_map.get(trigger_id) if trigger_id else None
            if trigger_id:
                # Card-body conditions reuse master predicate rows whose phase
                # labels describe passive timing. Evaluate their predicates now.
                matches = False
                for phase in (trigger or {}).get('phaseTypes', []) or [ExamPhase.NONE]:
                    event = {'phase_type': phase, 'phase_value': 0 if phase == ExamPhase.NONE else self.turn,
                             'acting_card': card, 'effect_types': self.repository.card_exam_effect_types(card.base_card)}
                    if trigger and self._trigger_matches(trigger, event, acting_card=card, target_card=card):
                        matches = True
                        break
                if not matches:
                    continue
            resolved_effect_specs.append(play_effect)
        self._record_event('card_conditions_resolved', {
            'card_uid': card.uid, 'body_enabled': body_enabled,
            'effect_ids': [e['effect_id'] for e in resolved_effect_specs],
            'before_cost': True,
        })

        resource_costs = self._card_resource_costs(card) if pay_cost else {}
        if pay_cost:
            cost_stamina, cost_force = self._card_stamina_components(card)
            # _spend_stamina emits the actual stamina-loss event exactly once.
            spent = self._spend_stamina(cost_stamina, cost_force,
                phase_type=ExamPhase.STAMINA_REDUCE_CARD, status_change_origin='card')
            self.total_counters['stamina_spent'] += int(round(spent))
            self.turn_counters['stamina_spent'] += int(round(spent))
            for key, value in resource_costs.items():
                if key == 'parameter_buff_multiple_per_turn':
                    self._consume_parameter_buff_multiple(value)
                else:
                    self.resources[key] = max(self.resources[key] - value, 0.0)

        self._dispatch_phase(ExamPhase.CARD_PLAY, acting_card=card)
        self._dispatch_interval_phase(ExamPhase.PLAY_TURN_COUNT_INTERVAL,
                                      self.turn_counters['play_count'] + 1, acting_card=card)
        self._dispatch_interval_phase(ExamPhase.PLAY_COUNT_INTERVAL,
                                      self.total_counters['play_count'] + 1, acting_card=card)
        card_repeat_total = 1 + self._card_repeat_bonus(card)
        for _ in range(max(card_repeat_total, 1)):
            for play_effect in resolved_effect_specs:
                effect = self.repository.exam_effect_map.get(str(play_effect['effect_id']))
                if effect:
                    self._apply_exam_effect(effect, source='card')
                if self.terminated:
                    break
            if self.terminated:
                break
        self._consume_card_play_buffs(card)
        if consume_play_window:
            self._consume_extra_action_unit()

        self.turn_counters['play_count'] += 1
        self.total_counters['play_count'] += 1
        if not consume_play_window:
            self.play_limit += 1
            self.turn_counters['automatic_play_count'] += 1
        self.search_history[str(card.card_id)] += 1
        self.resolution.last_played_card_uid = card.uid
        self._dispatch_phase(ExamPhase.SEARCH_CARD_PLAY, acting_card=card)
        if any(value > 0 for value in resource_costs.values()):
            self._dispatch_phase(ExamPhase.BUFF_CONSUME, acting_card=card)
        self._dispatch_phase(ExamPhase.CARD_PLAY_AFTER, acting_card=card,
                             effect_types=self.repository.card_exam_effect_types(card.base_card))
        self._dispatch_interval_phase(ExamPhase.PLAY_COUNT_INTERVAL_AFTER,
                                      self.total_counters['play_count'], acting_card=card)
        self._move_runtime_card(card, self._card_move_destination(card))
        self.playing = []
        self.current_card = None
        self._current_play_uid_floor = None

    @effect_group
    def _use_drink(self, index: int) -> None:
        """消耗一瓶饮料并应用其考试效果。"""

        drink = self.drinks[index]
        if not self._can_use_drink(drink):
            raise ValueError('Drink cannot be used without remaining play count')
        drink['_consumed'] = True
        self._record_event('drink_consumed', {
            'drink_index': index,
            'drink_name': self.repository.drink_name(drink),
        })
        for drink_effect_id in drink.get('produceDrinkEffectIds', []):
            drink_effect = self.repository.drink_effect_map.get(str(drink_effect_id))
            if not drink_effect:
                continue
            effect_id = str(drink_effect.get('produceExamEffectId') or '')
            effect = self.repository.exam_effect_map.get(effect_id)
            if effect:
                self._apply_exam_effect(effect, source='drink')
            if self.terminated:
                break
        self._refresh_play_limit()

    def _end_turn(self, skipped: bool = False) -> None:
        """结算回合末收益、弃手并进入下一回合。"""

        if skipped:
            self._dispatch_phase('ProduceExamPhaseType_ExamTurnSkip', phase_value=self.turn)
        if self.terminated:
            return
        self._dispatch_phase('ProduceExamPhaseType_ExamEndTurn', phase_value=self.turn)
        self._dispatch_interval_phase('ProduceExamPhaseType_ExamEndTurnInterval', self.turn)
        if self.terminated:
            return
        # 好印象结算（§5.4）：每次发动都走完整分数管线并各自取整，「好印象追加発動+n」重复 n 次。
        review_activation_count = max(1 + int(self._timed_effect_stack_value('ProduceExamEffectType_ExamReviewCountAdd')), 1)
        _review_delta = self._review_payout_total(review_activation_count)
        self.score += _review_delta
        if self.current_turn_color in self.score_per_color:
            self.score_per_color[self.current_turn_color] += _review_delta
        self._update_clear_state_after_score_change()
        self._clear_support_card_upgrades()
        self._discard_hand_to_grave()
        self.resources['enthusiastic'] = 0.0
        # R15: preserve unused action grants acquired during this action phase.
        if any(str(item.effect.get('effectType') or '') == ExamEffect.PLAYABLE_VALUE_ADD for item in self.active_effects):
            self.active_effects = [
                item for item in self.active_effects
                if str(item.effect.get('effectType') or '') != ExamEffect.PLAYABLE_VALUE_ADD
                or (item.applied_turn == self.turn and (item.remaining_count or 0) > 0)
            ]
            self._sync_effect_resources()
        # スキップ（出牌次数未用完就结束回合）回复 examTurnEndRecoveryStamina（§3.3）；
        # 考试并不会每回合自动回复（录像：最終試験 残り11→10 体力 31→26，只扣了卡费 5）。
        recovery = float(self.exam_setting.get('examTurnEndRecoveryStamina') or 0)
        if skipped and not self._has_timed_effect(ExamEffect.STAMINA_RECOVER_RESTRICTION):
            self.stamina = min(self.max_stamina, self.stamina + recovery)
        self.resolution.full_power_ready = self.resources['full_power_point'] >= FULL_POWER_POINT_THRESHOLD
        self._record_event('turn_end_eligibility', {'full_power_ready': self.resolution.full_power_ready})
        self.panic_cost_overrides = {}
        if self.terminated:
            return
        if skipped and self.turn >= self.max_turns and self.extra_turns <= 0:
            self.terminated = True
            return
        self._start_turn()

    def _card_stamina_components(self, card: RuntimeCard) -> tuple[float, float]:
        """计算卡牌的实际体力消耗和强制体力消耗。"""

        base_cost = float(card.base_card.get('stamina') or 0)
        force_cost = float(card.base_card.get('forceStamina') or 0)
        fallback_cost_type = str(card.base_card.get('costType') or 'ExamCostType_Unknown')
        for grow_effect in self._card_grow_rows(card):
            effect_type = str(grow_effect.get('effectType') or '')
            delta = float(grow_effect.get('value') or 0)
            resource_key = self._grow_cost_resource_key(effect_type, fallback_cost_type)
            if resource_key == 'stamina':
                if effect_type.endswith('Add'):
                    base_cost += delta
                elif effect_type.endswith('Reduce'):
                    base_cost -= delta
            elif resource_key == 'penetrate':
                if effect_type.endswith('Add'):
                    force_cost += delta
                elif effect_type.endswith('Reduce'):
                    force_cost -= delta
        for timed in self._matching_search_stamina_overrides(card):
            base_cost = float(timed.effect.get('effectValue1') or 0)
            force_cost = 0.0
        if self._has_timed_effect('ProduceExamEffectType_ExamPanic'):
            base_cost = self._panic_stamina_value(card)
            force_cost = 0.0
        # §4.3：cost' = max(ceil(cost × 指針倍率 × 減少/増加倍率) + Σ追加 − Σ削減, 0)，消耗量向上取整。
        has_down = False
        has_add = False
        fixed_delta = 0.0
        for timed in self.active_effects:
            effect_type = str(timed.effect.get('effectType') or '')
            if effect_type == ExamEffect.STAMINA_CONSUMPTION_ADD:
                has_add = True
            elif effect_type == ExamEffect.STAMINA_CONSUMPTION_DOWN:
                has_down = True
            elif effect_type == ExamEffect.STAMINA_CONSUMPTION_ADD_FIX:
                fixed_delta += self._raw_effect_value(timed.effect)
            elif effect_type == ExamEffect.STAMINA_CONSUMPTION_DOWN_FIX:
                fixed_delta -= self._raw_effect_value(timed.effect)
        consumption_permil = stamina_consumption_permil(has_down, has_add, self.exam_setting, self.scoring_rules)
        stance_permil = stance_stamina_permil(self.stance, self.stance_level, self.exam_setting)
        stance_force_cost = 0.0
        if self.stance == 'concentration':
            penetrate_key = f'examConcentrationStaminaPenetrateReduce{max(self.stance_level, 1)}'
            stance_force_cost = float(self.exam_setting.get(penetrate_key) or 0)
        permils = (stance_permil, consumption_permil)
        scaled_base = scale_by_permils(ceil_int(base_cost), permils) if base_cost > 0 else 0
        scaled_force = scale_by_permils(ceil_int(force_cost), permils) if force_cost > 0 else 0
        resolved_base = max(float(scaled_base) + fixed_delta, 0.0) if scaled_base > 0 or fixed_delta > 0 else 0.0
        resolved_force = max(float(scaled_force) + fixed_delta, 0.0) if scaled_force > 0 or fixed_delta > 0 else 0.0
        resolved_force += stance_force_cost
        return max(resolved_base, 0.0), max(resolved_force, 0.0)

    def _spend_stamina(
        self,
        amount: float,
        force_amount: float = 0.0,
        phase_type: str | None = None,
        status_change_origin: str = 'other',
    ) -> float:
        """先消耗护盾，再扣除实际体力。"""

        blocked = min(self.resources['block'], amount)
        if blocked > 0:
            self.resources['block'] -= blocked
            # 计数型：block_consumed 是整数计数量，非收益型
            self.total_counters['block_consumed'] += int(round(blocked))
        direct_damage = max(amount - blocked, 0.0) + force_amount
        if direct_damage > 0:
            self.stamina = max(self.stamina - direct_damage, 0.0)
            self._dispatch_phase(
                phase_type or 'ProduceExamPhaseType_ExamStaminaReduce',
                effect_types=['ProduceExamEffectType_ExamStaminaReduce'],
            )
            self._dispatch_status_change(direct_damage, ['ProduceExamEffectType_ExamStaminaReduce'], origin=status_change_origin)
        return blocked + direct_damage

    def _card_resource_costs(self, card: RuntimeCard) -> dict[str, float]:
        """计算卡牌在当前成长效果下的资源消耗。"""

        costs: dict[str, float] = defaultdict(float)
        cost_type = str(card.base_card.get('costType') or 'ExamCostType_Unknown')
        if cost_type != 'ExamCostType_Unknown':
            resource_key = COST_RESOURCE_MAP.get(cost_type, cost_type)
            if resource_key not in {'stamina', 'penetrate', 'ExamCostType_Unknown'}:
                costs[resource_key] += float(card.base_card.get('costValue') or 0)
        for grow_effect in self._card_grow_rows(card):
            effect_type = str(grow_effect.get('effectType') or '')
            value = float(grow_effect.get('value') or 0)
            if not effect_type.startswith('ProduceCardGrowEffectType_Cost'):
                continue
            resource_key = self._grow_cost_resource_key(effect_type, cost_type)
            if resource_key in {'stamina', 'penetrate', 'ExamCostType_Unknown', ''}:
                continue
            if effect_type.endswith('Add'):
                costs[resource_key] += value
            elif effect_type.endswith('Reduce'):
                costs[resource_key] -= value
        return {key: max(value, 0.0) for key, value in costs.items()}

    def _decay_turn_effects(self) -> None:
        """在回合推进时衰减持续效果和附魔回合数。

        手册规则：ターン経過減免 — 新規効果が付与されたターンは減免されない。
        即本回合新挂的效果（applied_turn == self.turn）不减少 remaining_turns。
        """

        # ターン経過減免（§3.5）：上一回合开始时已存在的状态才递减；回合开始阶段挂上的状态
        # 其 applied_turn 已被记为上一回合（见 _effect_applied_turn），因此这里统一用 `applied_turn < turn - 1`。
        decay_before_turn = self.turn - 1 if self.scoring_rules.fresh_modifier_no_decay else self.turn
        next_effects: list[TimedExamEffect] = []
        for timed in self.active_effects:
            remaining_turns = timed.remaining_turns
            if remaining_turns is not None and timed.applied_turn < decay_before_turn:
                remaining_turns -= 1
            if remaining_turns is not None and remaining_turns <= 0:
                continue
            timed.remaining_turns = remaining_turns
            next_effects.append(timed)
        self.active_effects = next_effects

        next_enchants: list[TriggeredEnchant] = []
        for enchant in self.active_enchants:
            remaining_turns = enchant.remaining_turns
            if remaining_turns is not None and enchant.applied_turn < decay_before_turn:
                remaining_turns -= 1
            if remaining_turns is not None and remaining_turns <= 0:
                continue
            enchant.remaining_turns = remaining_turns
            next_enchants.append(enchant)
        self.active_enchants = next_enchants
        self._sync_effect_resources()

    @effect_group
    def _dispatch_phase(
        self, phase_type: str, phase_value: int | None = None,
        acting_card: RuntimeCard | None = None, effect_types: list[str] | None = None,
        status_change_origin: str | None = None,
    ) -> None:
        """R01/R03: freeze eligibility, then execute in stable source order."""
        batch = collect_phase_batch(self, phase_type, phase_value, acting_card,
                                    effect_types, status_change_origin)
        execute_phase_batch(self, batch)

    def _dispatch_interval_phase(
        self,
        phase_type: str,
        counter_value: int,
        acting_card: RuntimeCard | None = None,
    ) -> None:
        """按间隔类条件逐次分发对应 phase。"""

        if counter_value <= 0:
            return
        for interval in self.repository.interval_phase_values.get(phase_type, ()):
            if counter_value % interval != 0:
                continue
            self._dispatch_phase(phase_type, phase_value=interval, acting_card=acting_card)
            if self.terminated:
                return

    def _trigger_matches(
        self,
        trigger: dict[str, Any],
        event: dict[str, Any],
        acting_card: RuntimeCard | None = None,
        target_card: RuntimeCard | None = None,
    ) -> bool:
        """判断某条触发器是否命中当前 phase 事件。"""
        return trigger_matches(
            ExamTriggerContext(self),
            trigger,
            event,
            acting_card=acting_card,
            target_card=target_card,
        )

    def _trigger_field_status_matches(self, trigger: dict[str, Any]) -> bool:
        """检查触发器里的场地状态条件是否成立。"""
        return trigger_field_status_matches(ExamTriggerContext(self), trigger)

    def _field_status_value(self, field_status_type: str, search_id: str) -> float:
        """读取指定场地状态类型在当前战斗中的数值。"""
        return field_status_value(ExamTriggerContext(self), field_status_type, search_id)

    def _trigger_card_search_matches(
        self,
        trigger: dict[str, Any],
        acting_card: RuntimeCard | None,
        target_card: RuntimeCard | None,
    ) -> bool:
        """检查触发器里的卡牌搜索条件是否成立。"""
        return trigger_card_search_matches(
            ExamTriggerContext(self),
            trigger,
            acting_card=acting_card,
            target_card=target_card,
        )

    def current_lesson_types(self) -> tuple[str, ...]:
        """公开给触发器读取的当前课程类型集合。"""

        return tuple(self._current_lesson_types())

    def search_cards(
        self,
        search_id: str,
        acting_card: RuntimeCard | None = None,
        target_card: RuntimeCard | None = None,
    ) -> CardSelection:
        """公开给效果器/触发器使用的卡牌检索接口。"""

        return self._search_cards(search_id, acting_card=acting_card, target_card=target_card)

    def search_card_count(self, search_id: str) -> int:
        """返回某个卡牌检索条件当前命中的候选数量。"""

        return int(self.search_cards(search_id).pool_size if search_id else 0)

    def _effect_pick_limit(self, effect: dict[str, Any]) -> int | None:
        """从效果行读取本次效果实际可选择的卡牌数量。"""

        pick_max = int(effect.get('pickCountMax') or 0)
        pick_min = int(effect.get('pickCountMin') or 0)
        if pick_max > 0:
            return pick_max
        if pick_min > 0:
            return pick_min
        return None

    def _card_move_prefers_high_value(self, effect: dict[str, Any]) -> bool:
        """判断移牌效果是否应按卡牌兑现价值自动挑选目标。"""

        search_id = str(effect.get('produceCardSearchId') or '')
        search = self.card_searches.first(search_id)
        if not search:
            return False
        source_position = str(search.get('cardPositionType') or '')
        destination = str(effect.get('movePositionType') or '')
        return (
            source_position != 'ProduceCardPositionType_Hand'
            and destination in {
                'ProduceCardMovePositionType_Hold',
                'ProduceCardMovePositionType_DeckFirst',
                'ProduceCardMovePositionType_DeckLast',
            }
        )

    def raw_effect_value(self, effect: dict[str, Any]) -> float:
        """读取效果原始数值。"""

        return self._raw_effect_value(effect)

    def direct_effect_value(self, effect: dict[str, Any]) -> float:
        """读取效果直接数值。"""

        return self._direct_value(effect)

    def ratio_effect_value(self, effect: dict[str, Any]) -> float:
        """读取效果比例数值。"""

        return self._ratio_value(effect)

    def count_effect_value(self, effect: dict[str, Any]) -> float:
        """读取效果次数数值。"""

        return self._count_value(effect)

    def positive_count(self, value: float) -> int:
        """把主数据次数值归一成正整数次数。"""

        return self._positive_count(value)

    def ceil_positive(self, value: float) -> float:
        """把正向收益向上取整，非正数归零。"""

        return self._ceil_positive(value)

    def compose_referenced_gain(self, *, base: float, referenced: float) -> float:
        """组合直接值和引用资源值。"""

        return self._compose_referenced_gain(base=base, referenced=referenced)

    def adjust_direct_gain(self, value: float, *, add_grow_type: str = '', reduce_grow_type: str = '') -> float:
        """应用当前卡牌成长效果对直接收益的修正。"""

        return self._adjust_direct_gain(value, add_grow_type=add_grow_type, reduce_grow_type=reduce_grow_type)

    def current_card_grow_total(self, grow_effect_type: str) -> float:
        """读取当前出牌卡的指定成长效果累计值。"""

        return self._current_card_grow_total(grow_effect_type)

    def current_card_ratio_bonus(self, grow_effect_type: str) -> float:
        """读取当前出牌卡的指定比例成长效果。"""

        return self._current_card_ratio_bonus(grow_effect_type)

    def parameter_buff_gain_value(self, effect: dict[str, Any]) -> float:
        """计算集中/好調等效果对好調回合的修正后收益。"""

        return self._parameter_buff_gain_value(effect)

    def dispatch_status_change(self, delta: float, effect_types: list[str], *, origin: str) -> None:
        """分发状态变化事件。"""

        self._dispatch_status_change(delta, effect_types, origin=origin)

    def consume_anti_debuff(self, effect_type: str) -> bool:
        """尝试消耗一次负面免疫。"""

        return self._consume_anti_debuff(effect_type)

    def register_timed_effect(self, effect: dict[str, Any], source: str) -> None:
        """注册持续型考试效果。"""

        self._register_timed_effect(effect, source)

    def apply_status_enchant(self, effect: dict[str, Any], source: str) -> None:
        """挂载状态附魔。"""

        self._apply_status_enchant(effect, source)

    def schedule_effect(self, effect: dict[str, Any], source: str = 'other') -> None:
        """登记延迟结算效果。"""

        self._schedule_effect(effect, source)

    def add_grow_effect(self, effect: dict[str, Any]) -> None:
        """给当前卡添加成长效果。"""

        self._add_grow_effect(effect)

    def apply_card_operation(self, effect: dict[str, Any]) -> None:
        """执行抽卡、生成、移动等卡牌操作。"""

        self._apply_card_operation(effect)

    def spend_stamina(self, value: float, *, phase_type: str, status_change_origin: str, force_value: float = 0.0) -> None:
        """扣除体力并按需要触发状态变化；`force_value` 为穿透元気的部分（体力消費）。"""

        self._spend_stamina(value, force_value, phase_type=phase_type, status_change_origin=status_change_origin)

    def has_timed_effect(self, effect_type: str) -> bool:
        """判断指定持续效果是否存在。"""

        return self._has_timed_effect(effect_type)

    def gain_block(self, delta: float, *, effect_type: str, status_change_origin: str) -> None:
        """获得或减少元气。"""

        self._gain_block(delta, effect_type=effect_type, status_change_origin=status_change_origin)

    def consume_parameter_buff_multiple(self, value: float) -> None:
        """消耗指定层数的参数强化倍率。"""

        self._consume_parameter_buff_multiple(value)

    def discard_hand(self) -> None:
        """公开给效果器：把当前手牌全部弃到捨札（手札入れ替え）。"""

        self._discard_hand_to_grave()

    def draw(self, count: int) -> None:
        """抽取指定张数卡牌。"""

        self._draw(count)

    def enter_concentration(self, level: int) -> None:
        """进入強気姿态。"""

        self._enter_concentration(level)

    def enter_preservation(self, level: int) -> None:
        """进入温存姿态。"""

        self._enter_preservation(level)

    def enter_full_power(self) -> None:
        """进入全力姿态。"""

        self._enter_full_power()

    def reset_stance(self) -> None:
        """重置当前姿态。"""

        self._reset_stance()

    def clear_negative_effects(self, kinds: int | None = None) -> None:
        """清理可解除的负面效果。"""

        self._clear_negative_effects(kinds)

    def sync_forbidden_search_resources(self) -> None:
        """同步卡牌禁用检索资源到观测资源。"""

        self._sync_forbidden_search_resources()

    def score_gain(self, value: float) -> float:
        """根据当前场地状态计算最终得分收益。"""

        return self._score_gain(value)

    def resolve_lesson_effect_value(self, effect: dict[str, Any], *, from_card: bool = False) -> float:
        """解析课程类效果的最终分数值。"""

        return self._resolve_lesson_effect_value(effect, from_card=from_card)

    def update_clear_state_after_score_change(self) -> None:
        """分数变化后刷新 clear/perfect 状态。"""

        self._update_clear_state_after_score_change()

    def apply_score_value_modifiers(self, value: float) -> float:
        """应用分数值倍率、低迷等修正。"""

        return self._apply_score_value_modifiers(value)

    def _apply_card_status_enchant(self, card: RuntimeCard, enchant_row: dict[str, Any]) -> None:
        """把卡牌状态附魔展开为临时附魔变更或成长效果。"""

        for grow_effect_id in enchant_row.get('produceCardGrowEffectIds', []):
            grow_effect = self.grow_effects.first(str(grow_effect_id))
            if not grow_effect:
                continue
            effect_type = str(grow_effect.get('effectType') or '')
            if effect_type == 'ProduceCardGrowEffectType_CardStatusEnchantChange':
                card.card_status_enchant_id = str(grow_effect.get('produceCardStatusEnchantId') or '')
                continue
            card.grow_effect_ids.append(str(grow_effect_id))

    def _card_selection_effect_types(self, card: RuntimeCard) -> list[str]:
        """返回卡牌当前实际出牌效果类型，用于自动选择目标卡。"""

        effect_types: list[str] = []
        for play_effect in self._resolved_card_play_effects(card):
            effect = self.repository.exam_effect_map.get(str(play_effect.get('effect_id') or ''))
            if effect is None:
                continue
            effect_type = str(effect.get('effectType') or '')
            if effect_type:
                effect_types.append(effect_type)
        return effect_types

    def _card_selection_score(self, card: RuntimeCard) -> float:
        """按当前考试资源估算检索选卡时的目标价值。"""

        effect_types = self._card_selection_effect_types(card)
        score = float(self.repository.card_play_priors.get(str(card.card_id), 0.0)) / 100000.0
        is_full_power_plan = self._plan_reward_family() == 'anomaly'
        full_power_ready = (
            self.stance == 'full_power'
            or float(self.resources.get('full_power_point') or 0.0) >= FULL_POWER_POINT_THRESHOLD * 0.5
        )
        for effect_type in effect_types:
            if effect_type in LESSON_EFFECT_TYPES:
                score += CARD_SELECTION_LESSON_SCORE
                if is_full_power_plan and full_power_ready:
                    score += 2.0
            elif effect_type == 'ProduceExamEffectType_ExamFullPowerPoint':
                score += CARD_SELECTION_FULL_POWER_POINT_SCORE if is_full_power_plan else CARD_SELECTION_RESOURCE_SCORE
            elif effect_type == 'ProduceExamEffectType_ExamFullPower':
                score += CARD_SELECTION_FULL_POWER_SCORE if is_full_power_plan else CARD_SELECTION_RESOURCE_SCORE
            elif effect_type in {
                'ProduceExamEffectType_ExamCardDraw',
                'ProduceExamEffectType_ExamCardMove',
                'ProduceExamEffectType_ExamPlayableValueAdd',
                'ProduceExamEffectType_ExamCardUpgrade',
                'ProduceExamEffectType_ExamStatusEnchant',
                'ProduceExamEffectType_ExamAddGrowEffect',
            }:
                score += CARD_SELECTION_UTILITY_SCORE
            elif effect_type in {
                'ProduceExamEffectType_ExamReview',
                'ProduceExamEffectType_ExamParameterBuff',
                'ProduceExamEffectType_ExamLessonBuff',
                'ProduceExamEffectType_ExamCardPlayAggressive',
                'ProduceExamEffectType_ExamBlock',
                'ProduceExamEffectType_ExamConcentration',
                'ProduceExamEffectType_ExamPreservation',
            }:
                score += CARD_SELECTION_RESOURCE_SCORE
        score -= float(card.base_card.get('stamina') or 0.0) * 0.05
        score -= float(card.base_card.get('forceStamina') or 0.0) * 0.08
        return score

    def _rank_card_selection_pool(self, pool: list[RuntimeCard]) -> list[RuntimeCard]:
        """把可手动选择的候选卡按结构价值从高到低排序。"""

        return sorted(pool, key=lambda card: (self._card_selection_score(card), -card.uid), reverse=True)

    def _search_cards(
        self,
        search_id: str,
        acting_card: RuntimeCard | None = None,
        target_card: RuntimeCard | None = None,
        limit_count: int | None = None,
        prefer_high_value: bool = False,
    ) -> CardSelection:
        """按 ProduceCardSearch 定义检索运行时卡牌。"""

        search = self.card_searches.first(search_id)
        if not search:
            return CardSelection(selected=[], pool_size=0)
        pool = self._pool_for_search(search, acting_card=acting_card, target_card=target_card)
        pool = [card for card in pool if self._matches_card_search(card, search)]
        pool_size = len(pool)
        resolved_limit = int(limit_count if limit_count is not None else int(search.get('limitCount') or 0))
        if resolved_limit <= 0:
            resolved_limit = pool_size
        order_type = str(search.get('orderType') or 'ProduceCardOrderType_Unknown')
        if order_type == 'ProduceCardOrderType_Random' and pool:
            count = min(pool_size, max(resolved_limit, 1))
            indices = self.np_random.choice(pool_size, size=count, replace=False)
            selected = [pool[int(index)] for index in np.atleast_1d(indices)]
        else:
            ordered_pool = self._rank_card_selection_pool(pool) if prefer_high_value and resolved_limit < pool_size else pool
            selected = ordered_pool[:resolved_limit]
        return CardSelection(selected=selected, pool_size=pool_size)

    def _pool_for_search(
        self,
        search: dict[str, Any],
        acting_card: RuntimeCard | None,
        target_card: RuntimeCard | None,
    ) -> list[RuntimeCard]:
        """根据搜索区域决定检索池来源。"""

        zone = CARD_ZONE_MAP.get(str(search.get('cardPositionType') or 'ProduceCardPositionType_DeckAll'), 'deck')
        if search.get('isSelf') and acting_card is not None:
            return [acting_card]
        if zone == 'deck':
            return list(self.deck)
        if zone == 'deck_grave':
            return list(self.deck) + list(self.grave)
        if zone == 'hand':
            return list(self.hand)
        if zone == 'hold':
            return list(self.hold)
        if zone == 'lost':
            return list(self.lost)
        if zone == 'not_lost':
            return list(self.deck) + list(self.hand) + list(self.grave) + list(self.hold)
        if zone == 'playing':
            return list(self.playing)
        if zone == 'target':
            return [target_card] if target_card is not None else ([acting_card] if acting_card is not None else [])
        return list(self.deck)

    def _matches_card_search(self, card: RuntimeCard, search: dict[str, Any]) -> bool:
        """判断单张运行时卡是否命中搜索条件。"""

        base_card = card.base_card
        rarities = {str(value) for value in search.get('cardRarities', []) if value}
        if rarities and str(base_card.get('rarity')) not in rarities:
            return False
        produce_card_ids = {str(value) for value in search.get('produceCardIds', []) if value}
        if produce_card_ids and card.card_id not in produce_card_ids:
            return False
        upgrade_counts = {int(value) for value in search.get('upgradeCounts', []) if value is not None}
        if upgrade_counts and card.upgrade_count not in upgrade_counts:
            return False
        categories = {str(value) for value in search.get('cardCategories', []) if value}
        if categories and str(base_card.get('category')) not in categories:
            return False
        plan_type = str(search.get('planType') or 'ProducePlanType_Unknown')
        if plan_type != 'ProducePlanType_Unknown' and str(base_card.get('planType')) != plan_type:
            return False
        search_tag = str(search.get('cardSearchTag') or '')
        if search_tag and search_tag != str(base_card.get('searchTag') or ''):
            return False
        cost_type = str(search.get('costType') or 'ExamCostType_Unknown')
        if cost_type != 'ExamCostType_Unknown' and str(base_card.get('costType')) != cost_type:
            return False
        exam_effect_type = str(search.get('examEffectType') or 'ProduceExamEffectType_Unknown')
        if exam_effect_type != 'ProduceExamEffectType_Unknown' and exam_effect_type not in set(self.repository.card_exam_effect_types(base_card)):
            return False
        effect_group_ids = {str(value) for value in search.get('effectGroupIds', []) if value}
        if effect_group_ids and not effect_group_ids.intersection({str(value) for value in base_card.get('effectGroupIds', []) if value}):
            return False
        if search.get('isCustomized') and not card.grow_effect_ids:
            return False
        return True

    def _apply_exam_effect(self, effect: dict[str, Any], source: str) -> None:
        """应用一条考试效果。"""

        apply_exam_effect(self, effect, source)

    def _register_initial_enchant(
        self,
        enchant_id: str,
        source: str,
        remaining_turns: int | None = None,
        remaining_count: int | None = None,
        source_identity: str = '',
    ) -> None:
        """注册开场自带的状态附魔，并保留来源提供的次数与回合数。"""

        enchant_row = self.repository.exam_status_enchant_map.get(str(enchant_id))
        if not enchant_row:
            return
        self.active_enchants.append(
            TriggeredEnchant(
                uid=self._next_uid(),
                enchant_id=str(enchant_row.get('id')),
                trigger_id=str(enchant_row.get('produceExamTriggerId') or ''),
                effect_ids=[str(value) for value in enchant_row.get('produceExamEffectIds', []) if value],
                remaining_turns=remaining_turns,
                remaining_count=remaining_count,
                source=source,
                source_identity=source_identity,
                applied_turn=self._effect_applied_turn(),
            )
        )

    def _register_timed_effect(self, effect: dict[str, Any], source: str) -> None:
        """把持续型考试效果挂入运行时效果列表。"""

        remaining_turns = int(effect.get('effectTurn') or 0)
        if remaining_turns < 0:
            remaining_turns = None
        elif remaining_turns == 0:
            remaining_turns = 1
        remaining_count = int(effect.get('effectCount') or 0)
        if remaining_count <= 0:
            remaining_count = None
        effect_type = str(effect.get('effectType') or '')
        if effect_type == ExamEffect.PLAYABLE_VALUE_ADD:
            remaining_count = max(int(self._count_value(effect)), 1)
        if effect_type in NEGATIVE_TIMED_EFFECT_TYPES:
            self.resolution.negative_order[(effect_type, '')] = self._next_uid()
        if remaining_turns is not None and remaining_count is None and effect_type in DURATION_STACKING_EFFECT_TYPES:
            # 同种回合数型状态叠加为回合数相加（§6：好調3 + 好調2 = 5 回合；录像：魅惑の視線+ 消費体力減少5 +
            # アイドル宣言+ 消費体力減少1 → 显示 6）。沿用既有实例的获得回合（kjirou 按 modifier id 递减）。
            for timed in self.active_effects:
                if (
                    str(timed.effect.get('effectType') or '') == effect_type
                    and timed.remaining_turns is not None
                    and timed.remaining_count is None
                    and float(timed.effect.get('effectValue1') or 0) == float(effect.get('effectValue1') or 0)
                ):
                    timed.remaining_turns += remaining_turns
                    self._sync_effect_resources()
                    return
        self.active_effects.append(
            TimedExamEffect(
                uid=self._next_uid(),
                effect=effect,
                remaining_turns=remaining_turns,
                remaining_count=remaining_count,
                source=source,
                applied_turn=self._effect_applied_turn(),
            )
        )
        self._sync_effect_resources()
        if str(effect.get('effectType') or '') == 'ProduceExamEffectType_ExamPlayableValueAdd':
            self.play_limit += int(remaining_count or 0)

    def _consume_extra_action_unit(self) -> None:
        """Consume the oldest available added window after the card body (R15).

        This preserves the base window while extra windows exist. New grants from
        this card are eligible; automatic uses never consume a player's window.
        """
        for timed in self.active_effects:
            if str(timed.effect.get('effectType') or '') == ExamEffect.PLAYABLE_VALUE_ADD and (timed.remaining_count or 0) > 0:
                timed.remaining_count -= 1
                self._record_event('extra_action_consumed', {'effect_uid': timed.uid, 'remaining': timed.remaining_count})
                break
        self.active_effects = [e for e in self.active_effects if e.remaining_count is None or e.remaining_count > 0]
        self._sync_effect_resources()

    def _apply_status_enchant(self, effect: dict[str, Any], source: str) -> None:
        """把考试效果转换成可触发的状态附魔实例。"""

        enchant_row = self.repository.exam_status_enchant_map.get(str(effect.get('produceExamStatusEnchantId') or ''))
        if not enchant_row:
            return
        remaining_turns = int(effect.get('effectTurn') or 0)
        if remaining_turns < 0:
            remaining_turns = None
        elif remaining_turns == 0:
            remaining_turns = 1
        remaining_count = int(effect.get('effectCount') or 0)
        if remaining_count <= 0:
            remaining_count = None
        self.active_enchants.append(
            TriggeredEnchant(
                uid=self._next_uid(),
                enchant_id=str(enchant_row.get('id')),
                trigger_id=str(enchant_row.get('produceExamTriggerId') or ''),
                effect_ids=[str(value) for value in enchant_row.get('produceExamEffectIds', []) if value],
                remaining_turns=remaining_turns,
                remaining_count=remaining_count,
                source=source,
                source_identity=source,
                applied_turn=self._effect_applied_turn(),
            )
        )

    def _schedule_effect(self, effect: dict[str, Any], source: str = 'other') -> None:
        """登记延迟触发的链式考试效果。"""

        chain_ids = [str(value) for value in effect.get('chainProduceExamEffectIds', []) if value]
        single_chain_id = str(effect.get('chainProduceExamEffectId') or '')
        if single_chain_id:
            chain_ids.insert(0, single_chain_id)
        if not chain_ids:
            return
        delay = max(int(effect.get('effectValue1') or 1), 1)
        for chain_id in chain_ids:
            self.scheduled_effects.append(
                ScheduledEffect(
                    effect_id=chain_id,
                    fire_turn=self.turn + delay,
                      remaining_count=int(effect.get('effectCount') or 1),
                      source=source,
                      source_card_uid=self.current_card.uid if self.current_card else self.resolution.scheduled_source_card_uid,
                )
            )
            self._record_event('effect_scheduled', {
                'effect_id': chain_id,
                'fire_turn': self.turn + delay,
            })

    def _add_grow_effect(self, effect: dict[str, Any]) -> None:
        """为检索到的运行时卡牌追加成长效果。"""

        selection = self._search_cards(str(effect.get('produceCardSearchId') or ''))
        grow_ids = [str(value) for value in effect.get('produceCardGrowEffectIds', []) if value]
        for card in selection.selected:
            card.grow_effect_ids.extend(grow_ids)
            initial_adds = 0
            for grow_id in grow_ids:
                grow_row = self.grow_effects.first(grow_id)
                if grow_row and str(grow_row.get('effectType') or '') == 'ProduceCardGrowEffectType_InitialAdd':
                    initial_adds += 1
            for _ in range(initial_adds):
                self._insert_card(card.clone(uid=self._next_uid()), 'deck_last')

    def _apply_card_operation(self, effect: dict[str, Any]) -> None:
        """执行造卡、复制、移动、升级、强制打出等卡牌操作。"""

        effect_type = str(effect.get('effectType') or '')
        pick_limit = self._effect_pick_limit(effect)
        if effect_type == 'ProduceExamEffectType_ExamCardCreateId':
            self._create_card_by_id(effect)
        elif effect_type == 'ProduceExamEffectType_ExamCardCreateSearch':
            self._create_card_by_search(effect)
        elif effect_type == 'ProduceExamEffectType_ExamCardDuplicate':
            selection = self._search_cards(
                str(effect.get('produceCardSearchId') or ''),
                limit_count=pick_limit,
                prefer_high_value=True,
            )
            destination = MOVE_POSITION_MAP.get(str(effect.get('movePositionType') or ''), 'deck_last')
            for card in selection.selected:
                self._insert_card(card.clone(uid=self._next_uid()), destination)
        elif effect_type == 'ProduceExamEffectType_ExamCardMove':
            selection = self._search_cards(
                str(effect.get('produceCardSearchId') or ''),
                limit_count=pick_limit,
                prefer_high_value=self._card_move_prefers_high_value(effect),
            )
            destination = MOVE_POSITION_MAP.get(str(effect.get('movePositionType') or ''), 'grave')
            for card in selection.selected:
                self._move_runtime_card(card, destination)
        elif effect_type == 'ProduceExamEffectType_ExamCardUpgrade':
            selection = self._search_cards(
                str(effect.get('produceCardSearchId') or ''),
                limit_count=pick_limit,
                prefer_high_value=True,
            )
            for card in selection.selected:
                self._apply_lesson_card_upgrade(card)
        # 强制使用类（ExamForcePlayCardSearch / ...WithCost）已迁移到 effects/card_operation.py。

    def _apply_lesson_card_upgrade(self, card: RuntimeCard) -> bool:
        """レッスン中強化：把一张未强化的卡在本局内升到 +。

        プロデュース中強化（+）与レッスン中強化互斥（§10）：已经是 + 的卡不再被レッスン中強化改写
        （录像：魅惑の視線+ 在「薄れゆく壁」的手札全强化后仍只是 +，叠加レッスンサポート后为 ++）。
        レッスンサポート（蓝色 +，回合内临时）可以叠在上面：若当前正带着临时强化，则把临时强化平移到新的永久等级上，
        并更新回合结束时的还原行。
        """

        if int(card.upgrade_count) >= 1:
            return False
        original_row = self._support_upgrade_original_rows.get(card.uid)
        temporary_upgrade = max(int(card.base_card.get('upgradeCount') or 0) - int(card.upgrade_count), 0)
        permanent_row = self._lookup_card_upgrade_row(card.card_id, card.upgrade_count + 1)
        if permanent_row is None:
            return False
        card.upgrade_count = int(permanent_row.get('upgradeCount') or card.upgrade_count + 1)
        if original_row is not None:
            self._support_upgrade_original_rows[card.uid] = permanent_row
        combined_row = self._lookup_card_upgrade_row(card.card_id, card.upgrade_count + temporary_upgrade) if temporary_upgrade else permanent_row
        card.base_card = combined_row if combined_row is not None else permanent_row
        return True

    def _create_card_by_id(self, effect: dict[str, Any]) -> None:
        """按显式卡牌 id 创建运行时卡并放入目标区域。"""

        target_id = str(effect.get('targetProduceCardId') or '')
        if not target_id:
            return
        card_row = self._lookup_card_row(target_id, int(effect.get('targetUpgradeCount') or 0))
        if card_row is None:
            return
        runtime_card = RuntimeCard(
            uid=self._next_uid(),
            card_id=target_id,
            upgrade_count=int(card_row.get('upgradeCount') or 0),
            base_card=card_row,
        )
        destination = MOVE_POSITION_MAP.get(str(effect.get('movePositionType') or ''), 'deck_last')
        self._record_event('card_acquired', {
            'card_id': target_id,
            'card_name': self.repository.card_name(card_row),
            'upgrade_count': runtime_card.upgrade_count,
            'destination': destination,
            'source': 'create_by_id',
        })
        self._insert_card(runtime_card, destination)

    def _create_card_by_search(self, effect: dict[str, Any]) -> None:
        """按检索配置随机生成卡牌并插入目标区域。"""

        search_row = self.card_searches.first(str(effect.get('produceCardSearchId') or ''))
        if not search_row:
            return
        destination = MOVE_POSITION_MAP.get(str(effect.get('movePositionType') or ''), 'deck_last')
        for card_row in self._sample_card_specs_from_search(search_row, effect):
            runtime_card = RuntimeCard(
                uid=self._next_uid(),
                card_id=str(card_row.get('id')),
                upgrade_count=int(card_row.get('upgradeCount') or 0),
                base_card=card_row,
            )
            self._record_event('card_acquired', {
                'card_id': runtime_card.card_id,
                'card_name': self.repository.card_name(card_row),
                'upgrade_count': runtime_card.upgrade_count,
                'destination': destination,
                'source': 'create_by_search',
            })
            self._insert_card(runtime_card, destination)

    @effect_group
    def _fire_scheduled_effects(self) -> None:
        """Resolve a stable due batch, retaining origin but excluding card growth."""
        pending = list(self.scheduled_effects)
        self.scheduled_effects = []
        for index, scheduled in enumerate(pending):
            if scheduled.fire_turn > self.turn:
                self.scheduled_effects.append(scheduled)
                continue
            effect = self.repository.exam_effect_map.get(scheduled.effect_id)
            previous = self.resolution.scheduled_source_card_uid
            self.resolution.scheduled_source_card_uid = scheduled.source_card_uid
            self._record_event('scheduled_effect_fired', {
                'effect_id': scheduled.effect_id, 'source': scheduled.source,
                'source_card_uid': scheduled.source_card_uid,
            })
            try:
                if effect:
                    self._apply_exam_effect(effect, source=f'scheduled:{scheduled.source}')
            finally:
                self.resolution.scheduled_source_card_uid = previous
            if scheduled.remaining_count is not None:
                scheduled.remaining_count -= 1
            if scheduled.remaining_count is None or scheduled.remaining_count > 0:
                scheduled.fire_turn = self.turn + 1
                self.scheduled_effects.append(scheduled)
            if self.terminated:
                self.scheduled_effects.extend(pending[index + 1:])
                break

    def _apply_gimmicks_for_turn(self, turn: int) -> None:
        """Freeze gimmick eligibility before full-power-release listeners (R02/R16)."""
        matching = sorted((r for r in self.gimmick_rows if int(r.get('startTurn') or 0) == turn),
                          key=lambda row: int(row.get('priority') or 0))
        selected = []
        for row in matching:
            key = (str(row.get('id') or ''), int(row.get('priority') or 0), int(row.get('startTurn') or 0))
            if key in self._resolved_gimmick_keys:
                continue
            self._resolved_gimmick_keys.add(key)
            if self._gimmick_condition_matches(row):
                selected.append(row)
        if self.resolution.deferred_full_power_release:
            self.resolution.deferred_full_power_release = False
            self._dispatch_phase(ExamPhase.STANCE_CHANGE_FROM_FULL_POWER)
        for row in selected:
            if self.terminated:
                break
            effect = self.repository.exam_effect_map.get(str(row.get('produceExamEffectId') or ''))
            if effect:
                self._record_event('gimmick_fired', {
                    'gimmick_id': str(row.get('id') or ''), 'start_turn': int(row.get('startTurn') or 0),
                    'effect_id': str(row.get('produceExamEffectId') or ''),
                })
                self._apply_exam_effect(effect, source='gimmick')

    def _gimmick_condition_matches(self, row: dict[str, Any]) -> bool:
        """判断考场机制的场地条件是否满足。"""

        field_status_type = str(row.get('fieldStatusType') or FieldStatus.UNKNOWN)
        if field_status_type == FieldStatus.UNKNOWN:
            return True
        current_value = self._field_status_value(field_status_type, str(row.get('fieldStatusProduceCardSearchId') or ''))
        expected_value = float(row.get('fieldStatusValue') or 1)
        check_type = str(row.get('fieldStatusCheckType') or TriggerCheck.UNKNOWN)
        reverse_threshold = field_status_type.endswith('MultipleDown') or 'LessMultiple' in field_status_type
        if check_type == TriggerCheck.NOT:
            return current_value > expected_value if reverse_threshold else current_value < expected_value
        return current_value <= expected_value if reverse_threshold else current_value >= expected_value

    def _clear_negative_effects(self, kinds: int | None = None) -> None:
        """Reference section 2.5: newest complete status kinds, not blanket removal."""
        from .resolution import clear_negative_states
        clear_negative_states(self, kinds)

    def _card_move_destination(self, card: RuntimeCard) -> str:
        """解析卡牌打出后的最终落点，包含成长效果修正。"""

        move_type = str(card.base_card.get('playMovePositionType') or 'ProduceCardMovePositionType_Grave')
        for grow_effect in self._card_grow_rows(card):
            if str(grow_effect.get('effectType') or '') == GrowEffect.PLAY_MOVE_POSITION_TYPE_CHANGE:
                move_type = str(grow_effect.get('playMovePositionType') or move_type)
        return MOVE_POSITION_MAP.get(move_type, 'grave')

    def _move_runtime_card(self, card: RuntimeCard, destination: str) -> None:
        """把一张运行时卡移动到指定区域，并触发对应 phase。"""

        # A request to remain in the same zone is not a new arrival.
        if destination in {'hand', 'hold', 'grave', 'lost'} and any(
            current.uid == card.uid for current in getattr(self, destination)
        ):
            return
        self._detach_card(card)
        if destination == 'hand':
            arrived = self._send_to_hand_or_top_deck(card)
            move_phase = ExamPhase.CARD_MOVE_HAND if arrived else None
        elif destination == 'hold':
            self._add_card_to_hold(card)
            move_phase = None
        elif destination == 'lost':
            self.lost.append(card)
            move_phase = ExamPhase.CARD_MOVE_LOST
        elif destination == 'deck_first':
            self.deck.appendleft(card)
            move_phase = None
        elif destination == 'deck_random':
            deck_list = list(self.deck)
            index = int(self.np_random.integers(0, len(deck_list) + 1))
            deck_list.insert(index, card)
            self.deck = deque(deck_list)
            move_phase = None
        elif destination == 'deck_last':
            self.deck.append(card)
            move_phase = None
        else:
            self.grave.append(card)
            move_phase = ExamPhase.CARD_MOVE_GRAVE
        if move_phase:
            self._dispatch_phase(move_phase, acting_card=card)

    def _card_by_uid(self, uid: int) -> RuntimeCard | None:
        """按 uid 在所有区域里查找运行时卡；不存在时返回 None。"""

        for zone in (self.hand, self.hold, self.deck, self.grave, self.lost, self.playing):
            for current in zone:
                if current.uid == uid:
                    return current
        return None

    def _detach_card(self, card: RuntimeCard) -> None:
        """把卡牌从当前所在区域摘除。"""

        for zone in (self.hand, self.grave, self.hold, self.lost, self.playing):
            for index, current in enumerate(zone):
                if current.uid == card.uid:
                    zone.pop(index)
                    return
        deck_list = list(self.deck)
        for index, current in enumerate(deck_list):
            if current.uid == card.uid:
                deck_list.pop(index)
                self.deck = deque(deck_list)
                return

    def _draw(self, count: int) -> None:
        """抽取指定数量的卡牌，并处理洗回牌堆。"""

        hand_limit = int(self.exam_setting.get('handLimit') or 5)
        for _ in range(count):
            if len(self.hand) >= hand_limit:
                return
            if not self.deck:
                if not self.grave:
                    return
                self._reshuffle_grave_into_deck()
            if not self.deck:
                return
            self._send_to_hand_or_top_deck(self.deck.popleft())
            if self.terminated:
                return

    def _reshuffle_grave_into_deck(self) -> None:
        """把弃牌区洗回牌堆，遵守主数据中的洗牌配置。"""

        cards = list(self.grave)
        self.grave = []
        if cards:
            if self.exam_setting.get('fixMoveCardShuffleDeckEnable'):
                self.np_random.shuffle(cards)
            forced_order = self.replay_hooks.next_reshuffle_order() if self.replay_hooks is not None else None
            if forced_order:
                cards = reorder_by_build_index(cards, forced_order, lambda card: card.build_index)
            self.deck = deque(cards)

    def _card_label(self, card: RuntimeCard) -> str:
        """生成调试日志使用的卡牌标签。"""

        return f'{self.repository.card_name(card.base_card)}[{card.upgrade_count}]'

    def _lookup_card_row(self, card_id: str, upgrade_count: int) -> dict[str, Any] | None:
        """按卡牌 id 和强化次数查找最匹配的主数据行。"""

        return self.repository.card_row_by_upgrade(card_id, upgrade_count, fallback_to_canonical=True)

    def _lookup_card_upgrade_row(self, card_id: str, upgrade_count: int) -> dict[str, Any] | None:
        """按卡牌 id 和强化次数精确查找强化后的主数据行。"""

        return self.repository.card_row_by_upgrade(card_id, upgrade_count, fallback_to_canonical=False)

    def _card_grow_rows(self, card: RuntimeCard) -> list[dict[str, Any]]:
        """解析当前运行时卡牌挂载的成长效果行。"""

        rows = []
        for effect_id in card.grow_effect_ids:
            row = self.grow_effects.first(str(effect_id))
            if row:
                rows.append(row)
        return rows

    def _insert_card(self, card: RuntimeCard, destination: str) -> None:
        """把新建或复制的卡牌插入指定区域。"""

        if destination == 'hand':
            self._send_to_hand_or_top_deck(card)
        elif destination == 'hold':
            self._add_card_to_hold(card)
        elif destination == 'lost':
            self.lost.append(card)
        elif destination == 'deck_first':
            self.deck.appendleft(card)
        elif destination == 'deck_random':
            deck_list = list(self.deck)
            index = int(self.np_random.integers(0, len(deck_list) + 1))
            deck_list.insert(index, card)
            self.deck = deque(deck_list)
        elif destination == 'deck_last':
            self.deck.append(card)
        else:
            self.grave.append(card)

    def _add_card_to_hold(self, card: RuntimeCard) -> None:
        """把卡牌加入保留区，并按手册限制保留区最多 2 张。"""

        self.hold.append(card)
        while len(self.hold) > HOLD_CARD_LIMIT:
            self.grave.append(self.hold.pop(0))
        self._apply_card_move_effects(card, 'hold')

    def _sample_card_specs_from_search(self, search: dict[str, Any], effect: dict[str, Any]) -> list[dict[str, Any]]:
        """根据检索定义抽样待创建的卡牌规格。"""

        card_rows: list[dict[str, Any]] = []
        explicit_ids = [str(value) for value in search.get('produceCardIds', []) if value]
        upgrade_counts = [int(value) for value in search.get('upgradeCounts', []) if value is not None]
        if explicit_ids:
            for card_id in explicit_ids:
                card_row = self._lookup_card_row(card_id, upgrade_counts[0] if upgrade_counts else 0)
                if card_row is not None:
                    card_rows.append(card_row)
        elif search.get('produceCardRandomPoolId'):
            ratios = self.random_pools.all(str(search.get('produceCardRandomPoolId')))
            weighted_rows = []
            weights = []
            for ratio in ratios:
                card_row = self._lookup_card_row(str(ratio.get('produceCardId')), int(ratio.get('upgradeCount') or 0))
                if card_row is None:
                    continue
                weighted_rows.append(card_row)
                weights.append(float(ratio.get('ratio') or 1.0))
            if weighted_rows:
                pick_count = max(int(effect.get('pickCountMax') or effect.get('pickCountMin') or 1), 1)
                probabilities = np.array(weights, dtype=np.float64) / max(sum(weights), 1.0)
                indices = self.np_random.choice(len(weighted_rows), size=pick_count, replace=True, p=probabilities)
                card_rows.extend(weighted_rows[int(index)] for index in np.atleast_1d(indices))
        elif search.get('produceCardPoolId'):
            pool_row = self.card_pools.first(str(search.get('produceCardPoolId')))
            if pool_row:
                weighted_rows = []
                weights = []
                for ratio in pool_row.get('produceCardRatios', []):
                    card_row = self._lookup_card_row(str(ratio.get('id')), int(ratio.get('upgradeCount') or 0))
                    if card_row is None:
                        continue
                    weighted_rows.append(card_row)
                    weights.append(float(ratio.get('ratio') or 1.0))
                if weighted_rows:
                    pick_count = max(int(effect.get('pickCountMax') or effect.get('pickCountMin') or 1), 1)
                    probabilities = np.array(weights, dtype=np.float64) / max(sum(weights), 1.0)
                    indices = self.np_random.choice(len(weighted_rows), size=pick_count, replace=True, p=probabilities)
                    card_rows.extend(weighted_rows[int(index)] for index in np.atleast_1d(indices))
        return card_rows

    def _resolve_lesson_effect_value(self, effect: dict[str, Any], from_card: bool = False) -> float:
        """按资源、检索数量和 stance 结算课程分数效果。"""

        return resolve_lesson_effect_value(ExamEffectContext(self), effect, from_card=from_card)

    def _focus_score_contribution(self) -> float:
        """R18: 集中強化 scales score contribution, never acquired concentration.

        Keep fractional contribution until the existing score rounding boundary.
        Mixed reference/strength rounding remains a documented provisional rule.
        """
        strength = sum(
            self._ratio_value(item.effect) for item in self.active_effects
            if str(item.effect.get('effectType') or '') == ExamEffect.LESSON_BUFF_MULTIPLE
        )
        return self.resources['lesson_buff'] * max(1.0 + strength, 0.0)

    def _apply_score_value_modifiers(self, value: float, *, include_additives: bool = True) -> float:
        """分数管线 S1→S2（§5.1）：集中/熱意 加算 → 各倍率合并一次 ceil。

        ```
        S1 = ceil(基础值 + 集中 + 熱意)            # 参照值部分已在效果器里各自 ceil
        S1 = max(S1 − 緊張(GimmickLessonDebuff), 0)
        S2 = ceil(S1 × 好調倍率 × 指針倍率(+強気強化/全力強化) × (1+Σ上昇量増加+プライド) × max(1−Σ減少,0) × (不調?0.667:1))
        スランプ → 0
        ```
        所有倍率用 `ExamSetting` 的整数千分比运算（好調用整数避免 `0.1×1.4` 浮点误差）。
        `include_additives=False` 时不加 集中/熱意（好印象结算的开关 §15-2）。
        """

        base = max(float(value), 0.0)
        if include_additives:
            base += self._focus_score_contribution() + self.resources['enthusiastic']
        stage_one = ceil_int(base)

        up_permil = PERMIL
        down_permil = PERMIL
        debuff_permil = PERMIL
        slump = False
        consumed_effects: list[TimedExamEffect] = []
        for timed in list(self.active_effects):
            modifier_type = str(timed.effect.get('effectType') or '')
            used = False
            if modifier_type == ExamEffect.LESSON_VALUE_MULTIPLE:
                up_permil += permil_from_ratio(self._ratio_value(timed.effect))
                used = True
            elif modifier_type == ExamEffect.LESSON_VALUE_MULTIPLE_DOWN:
                down_permil -= permil_from_ratio(self._ratio_value(timed.effect))
                used = True
            elif modifier_type == ExamEffect.LESSON_VALUE_MULTIPLE_DEPEND_REVIEW_OR_AGGRESSIVE:
                per_stack = int(self.exam_setting.get('examLessonValueMultipleDependReviewOrAggressiveMultiplePermil') or 20)
                max_permil = int(self.exam_setting.get('examLessonValueMultipleDependReviewOrAggressiveMaxPermil') or 500)
                stacks = int(min(self.resources['review'], self.resources['aggressive']))
                up_permil += min(stacks * per_stack, max_permil)
                used = True
            elif modifier_type == ExamEffect.GIMMICK_LESSON_DEBUFF:
                stage_one = max(stage_one - int(self._raw_effect_value(timed.effect)), 0)
                used = True
            elif modifier_type == ExamEffect.GIMMICK_PARAMETER_DEBUFF:
                debuff_permil = max(PERMIL - int(self.exam_setting.get('examGimmickParameterDebuffPermil') or 0), 0)
                used = True
            elif modifier_type == ExamEffect.GIMMICK_SLUMP:
                slump = True
                used = True
            if used and timed.remaining_count is not None:
                consumed_effects.append(timed)
        for timed in consumed_effects:
            timed.remaining_count -= 1
        self.active_effects = [item for item in self.active_effects if item.remaining_count is None or item.remaining_count > 0]
        self._sync_effect_resources()

        if slump:
            return 0.0
        good_permil = good_condition_permil(
            int(self.resources['parameter_buff']),
            self.resources['parameter_buff_multiple_per_turn'] > 0,
            self.exam_setting,
        )
        stance_permil = stance_lesson_permil(
            self.stance,
            self.stance_level,
            self.exam_setting,
            additive_permil=self._stance_lesson_multiple_additive_permil(),
        )
        stage_two = scale_by_permils(
            stage_one,
            (good_permil, stance_permil, up_permil, max(down_permil, 0), debuff_permil),
        )
        return float(max(stage_two, 0))

    def _stance_lesson_multiple_additive_permil(self) -> int:
        """当前指針对应的「強気強化 / 全力強化」持续效果加算（千分比）。"""

        if self.stance == 'concentration':
            effect_type = ExamEffect.CONCENTRATION_LESSON_MULTIPLE_ADDITIVE
        elif self.stance == 'full_power':
            effect_type = ExamEffect.FULL_POWER_LESSON_MULTIPLE_ADDITIVE
        else:
            return 0
        total = 0
        for timed in self.active_effects:
            if str(timed.effect.get('effectType') or '') == effect_type:
                total += permil_from_ratio(self._ratio_value(timed.effect))
        return total

    def _review_payout_total(self, activation_count: int) -> float:
        """回合结束的好印象结算总分：每次发动 = ceil(管线(好印象) × スコアボーナス)。"""

        strength = sum(
            self._ratio_value(item.effect) for item in self.active_effects
            if str(item.effect.get('effectType') or '') == ExamEffect.REVIEW_MULTIPLE
        )
        # R19: only natural impression payout receives 好印象強化. Card reference
        # effects still read the unchanged review resource through lesson_value.
        review = ceil_int(self.resources['review'] * max(1.0 + strength, 0.0))
        if review <= 0:
            return 0.0
        include_additives = self.scoring_rules.review_payout_uses_concentration
        times = max(int(activation_count), 1)
        if self.scoring_rules.review_activation_rounds_each:
            total = 0.0
            for _ in range(times):
                total += self._score_gain(self._apply_score_value_modifiers(float(review), include_additives=include_additives))
            return total
        single = self._apply_score_value_modifiers(float(review), include_additives=include_additives)
        return self._score_gain(single * times)

    def _apply_scalar_modifiers(self, effect_type: str, amount: float) -> float:
        """对好調、元気、やる気等资源应用场上修饰。

        主数据里「○○増加量増加」（ExamXxxAdditive，千分比）与「○○増加量追加」（ExamXxxAdditiveFix，固定值）
        是两套并存的修饰：先加固定值，再乘 (1 + Σ千分比)，与 gakumas-engine 的 `(v + Σbonus) × (1 + Σbuffs)` 一致。
        """

        updated = float(amount)
        if effect_type == 'ProduceExamEffectType_ExamBlock':
            if self._has_timed_effect('ProduceExamEffectType_ExamBlockRestriction'):
                return 0.0
            updated += self.resources['aggressive']
            updated -= self.resources['sleepy']
        fixed_bonus = 0.0
        ratio_multiple = 1.0
        for timed in self.active_effects:
            modifier_type = str(timed.effect.get('effectType') or '')
            if effect_type == 'ProduceExamEffectType_ExamCardPlayAggressive':
                if modifier_type == ExamEffect.AGGRESSIVE_ADDITIVE:
                    ratio_multiple += self._ratio_value(timed.effect)
                elif modifier_type == ExamEffect.AGGRESSIVE_ADDITIVE_FIX:
                    fixed_bonus += self._raw_effect_value(timed.effect)
                elif modifier_type == ExamEffect.AGGRESSIVE_VALUE_MULTIPLE:
                    ratio_multiple += self._ratio_value(timed.effect)
            elif effect_type == 'ProduceExamEffectType_ExamBlock':
                if modifier_type == 'ProduceExamEffectType_ExamBlockAddDown':
                    updated *= max(1.0 - float(self.exam_setting.get('examBlockAddDownPermil') or 0) / 1000.0, 0.0)
                elif modifier_type == 'ProduceExamEffectType_ExamBlockValueMultiple':
                    ratio_multiple += self._ratio_value(timed.effect)
            elif effect_type == 'ProduceExamEffectType_ExamReview':
                if modifier_type == ExamEffect.REVIEW_ADDITIVE:
                    ratio_multiple += self._ratio_value(timed.effect)
                elif modifier_type == ExamEffect.REVIEW_ADDITIVE_FIX:
                    fixed_bonus += self._raw_effect_value(timed.effect)
            elif effect_type == 'ProduceExamEffectType_ExamParameterBuff':
                if modifier_type == ExamEffect.PARAMETER_BUFF_ADDITIVE:
                    ratio_multiple += self._ratio_value(timed.effect)
                elif modifier_type == ExamEffect.PARAMETER_BUFF_ADDITIVE_FIX:
                    fixed_bonus += self._raw_effect_value(timed.effect)
            elif effect_type == 'ProduceExamEffectType_ExamLessonBuff':
                if modifier_type == ExamEffect.LESSON_BUFF_ADDITIVE:
                    ratio_multiple += self._ratio_value(timed.effect)
                elif modifier_type == ExamEffect.LESSON_BUFF_ADDITIVE_FIX:
                    fixed_bonus += self._raw_effect_value(timed.effect)
            elif effect_type == 'ProduceExamEffectType_ExamFullPowerPoint':
                if modifier_type == ExamEffect.FULL_POWER_POINT_ADDITIVE:
                    ratio_multiple += self._ratio_value(timed.effect)
                elif modifier_type == ExamEffect.FULL_POWER_POINT_ADDITIVE_FIX:
                    fixed_bonus += self._raw_effect_value(timed.effect)
        if updated > 0 or fixed_bonus > 0:
            updated = (updated + fixed_bonus) * ratio_multiple
        return max(updated, 0.0)

    def _apply_preservation_release(self, target_stance: str) -> None:
        """温存/悠闲解除时，根据阶段发放对应奖励。"""

        if self.stance != 'preservation' or self.stance_level <= 0:
            return
        if self.stance_level >= 3:
            self._gain_block(float(self.exam_setting.get('overPreservationReleaseBlockAdd') or 0), effect_type='ProduceExamEffectType_ExamBlockFix')
            # 计数型：play_limit 是出牌上限，整数语义
            self.play_limit += int(round(float(self.exam_setting.get('overPreservationReleasePlayableValueAdd') or 0)))
            if target_stance == 'full_power':
                self._add_lesson_grow_effect_to_all_cards(float(self.exam_setting.get('overPreservationReleaseToFullPowerGrowEffectLessonAdd') or 0))
            else:
                self._gain_enthusiastic(float(self.exam_setting.get('overPreservationReleaseEnthusiastic') or 0))
            return
        enthusiastic_key = f'preservationReleaseEnthusiastic{self.stance_level}'
        block_key = f'preservationReleaseBlockAdd{self.stance_level}'
        playable_key = f'preservationReleasePlayableValueAdd{self.stance_level}'
        self._gain_enthusiastic(float(self.exam_setting.get(enthusiastic_key) or 0))
        block_add = float(self.exam_setting.get(block_key) or 0)
        if block_add > 0:
            self._gain_block(block_add, effect_type='ProduceExamEffectType_ExamBlockFix')
        # 计数型：play_limit 是出牌上限，整数语义
        self.play_limit += int(round(float(self.exam_setting.get(playable_key) or 0)))

    def _move_hold_cards_to_hand(self) -> None:
        """全力进场时把保留区的卡尽量送回手牌。"""

        held_cards = list(self.hold)
        self.hold = []
        for card in held_cards:
            self._send_to_hand_or_top_deck(card)
            self._record_event('full_power_hold_returned', {
                'card_uid': card.uid, 'destination': 'hand' if card in self.hand else 'deck',
            })

    def _add_lesson_grow_effect_to_all_cards(self, value: float) -> None:
        """给所有运行时技能卡追加固定打分成长效果。"""

        # 计数型：成长效果值为整数，用于构造 grow_effect_id
        amount = int(round(value))
        if amount <= 0:
            return
        grow_effect_id = f'g_effect-lesson_add-{amount}'
        if self.grow_effects.first(grow_effect_id) is None:
            return
        seen: set[int] = set()
        for zone in (self.deck, self.hand, self.grave, self.hold, self.lost, self.playing):
            for card in zone:
                if card.uid in seen:
                    continue
                seen.add(card.uid)
                if grow_effect_id not in card.grow_effect_ids:
                    card.grow_effect_ids.append(grow_effect_id)

    def _enter_concentration(self, level: int) -> None:
        """进入强气指针；重复进入时提升到更高阶段。"""

        if self._is_stance_change_locked():
            return
        if self.stance == 'full_power' and self.stance_locked:
            return
        target_level = min(max(int(level), 1), 2)
        if self.stance == 'concentration':
            if target_level <= 1 and self.stance_level == 1:
                target_level = 2
            else:
                target_level = max(self.stance_level, target_level)
            self._set_stance('concentration', target_level)
            return
        if self.stance == 'preservation':
            self._apply_preservation_release('concentration')
        self._set_stance('concentration', target_level)

    def _enter_preservation(self, level: int) -> None:
        """进入温存/悠闲指针；重复进入时提升到更高阶段。"""

        if self._is_stance_change_locked():
            return
        if self.stance == 'full_power' and self.stance_locked:
            return
        target_level = 3 if int(level) >= 3 else min(max(int(level), 1), 2)
        if self.stance == 'preservation':
            if self.stance_level >= 3 and target_level < 3:
                return
            if target_level >= 3:
                self._set_stance('preservation', 3)
                return
            if target_level <= 1 and self.stance_level == 1:
                target_level = 2
            else:
                target_level = max(self.stance_level, target_level)
            self._set_stance('preservation', target_level)
            return
        self._set_stance('preservation', target_level)

    def _enter_full_power(self) -> None:
        """进入全力，结算温存解除奖励并移动保留区。"""

        if self._is_stance_change_locked():
            return
        if self.stance == 'full_power':
            return
        if self.stance == 'preservation':
            self._apply_preservation_release('full_power')
        if not self._set_stance('full_power', 1):
            return
        self.stance_locked = True
        # 计数型：play_limit 是出牌上限，整数语义
        self.play_limit += int(round(float(self.exam_setting.get('fullPowerPlayableValueAdd') or 0)))
        if getattr(self, '_turn_start_phase_active', False):
            self.resolution.return_hold_after_draw = True
        else:
            self._move_hold_cards_to_hand()

    def _release_full_power(self) -> None:
        """在下一回合开始时解除全力锁定。"""

        if self.stance != 'full_power':
            return
        self.stance_locked = False
        self._set_stance('neutral', 0)

    def _reset_stance(self) -> None:
        """手动解除当前指针状态。"""

        if self.stance == 'full_power' and self.stance_locked:
            return
        if self.stance == 'preservation':
            self._apply_preservation_release('neutral')
        self._set_stance('neutral', 0)

    def _set_stance(self, stance: str, level: int = 1) -> bool:
        """切换当前指针状态，并补发相关触发 phase。"""

        if self.stance_locked and self.stance != stance:
            return False
        normalized_level = 0 if stance == 'neutral' else max(int(level), 1)
        previous = self.stance
        previous_level = self.stance_level
        if previous == stance and previous_level == normalized_level:
            return False
        self.stance = stance
        self.stance_level = normalized_level
        self.total_counters['stance_changes'] += 1
        if stance == 'concentration':
            self.total_counters['stance_concentration'] += 1
        elif stance == 'full_power':
            self.total_counters['stance_full_power'] += 1
        elif stance == 'preservation':
            self.total_counters['stance_preservation'] += 1
        self._dispatch_interval_phase('ProduceExamPhaseType_ExamStanceChangeCountInterval', self.total_counters['stance_changes'])
        phase = next((phase for phase, mapped in STANCE_PHASES.items() if mapped == stance), None)
        if phase:
            self._dispatch_phase(phase)
        if previous == 'concentration' and stance != 'concentration':
            self._dispatch_phase('ProduceExamPhaseType_ExamStanceChangeFromConcentration')
        if previous == 'full_power' and stance != 'full_power':
            if getattr(self, '_turn_start_phase_active', False):
                self.resolution.deferred_full_power_release = True
            else:
                self._dispatch_phase('ProduceExamPhaseType_ExamStanceChangeFromFullPower')
        self._sync_stance_resources()
        return True

    def _is_stance_change_locked(self) -> bool:
        """判断当前是否存在会阻止进入强气、温存或全力的指针固定状态。"""

        return self._has_timed_effect(ExamEffect.STANCE_LOCK)

    def _lesson_type_for_card(self, card: RuntimeCard | None) -> str:
        """兼容旧调用，统一返回战斗上下文中的课程类型。"""

        return self._current_lesson_type()

    def _direct_value(self, effect: dict[str, Any]) -> float:
        """解析效果的直接数值，并套用标量资源修正。"""

        effect_type = str(effect.get('effectType') or '')
        base_value = self._raw_effect_value(effect)
        if effect_type in DURATION_RESOURCE_TYPES:
            return self._parameter_buff_gain_value(effect)
        if effect_type in SCALAR_RESOURCE_TYPES or effect_type in {
            'ProduceExamEffectType_ExamStaminaDamage',
            'ProduceExamEffectType_ExamStaminaRecover',
            'ProduceExamEffectType_ExamStaminaRecoverFix',
            'ProduceExamEffectType_ExamStaminaReduce',
            'ProduceExamEffectType_ExamBlock',
            'ProduceExamEffectType_ExamBlockFix',
            'ProduceExamEffectType_ExamCardDraw',
        }:
            return self._apply_scalar_modifiers(effect_type, base_value)
        if base_value == 0:
            base_value = float(effect.get('effectCount') or 0)
        if base_value == 0:
            base_value = 1.0
        return max(base_value, 0.0)

    def _ratio_value(self, effect: dict[str, Any]) -> float:
        """把千分比字段转换成 0-1 浮点比例。"""

        value = float(effect.get('effectValue1') or effect.get('effectValue2') or 0)
        return max(value, 0.0) / 1000.0 if value > 0 else 0.0

    def _count_value(self, effect: dict[str, Any]) -> float:
        """解析效果次数字段，缺省时按 1 处理。"""

        return float(effect.get('effectCount') or effect.get('effectValue1') or 1)
