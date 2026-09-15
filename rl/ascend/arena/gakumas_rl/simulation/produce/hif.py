"""H.I.F（Hatsuboshi IDOL FESTIVAL）培育外循环的专用逻辑。

本模块把 `docs/scenarios/hif.md` 中与 初/NIA 不同的部分集中在一起：
スター性 资源、公開レッスン、インターバル、本戦 两轮合计与 一番星 判定、
選抜試験メモリー 交接，以及 HIF 版最终评价。`ProduceRuntime` 在 `scenario.hif` 存在时
委托给 `HifRuntimeSupport`，其余流程（考试运行时、P 道具、支援卡事件）沿用通用实现。

凡是主数据未覆盖、依据网络攻略或推断实现的数值，均在 `HifScenarioConfig` 中暴露为可配置项，
并以 `# TODO(HIF-verify)` 标注。
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from ...constants.game.action_types import ACTION_ACTIVITY_SUPPLY, ACTION_SCHOOL_CLASS, ACTION_OUTING
from ...produce_score import (
    HIF_STAR_QUALITY_CAP,
    calculate_hif_produce_rating,
    calculate_hif_round2_star_gain,
    calculate_hif_selection_rating,
)
from ...repository.master_data import HIF_ROUTE_FINAL, HIF_ROUTE_SELECTION, HifScenarioConfig

if TYPE_CHECKING:
    from .runtime import ProduceActionCandidate, ProduceRuntime


HIF_OPEN_LESSON_ACTION_TYPES: tuple[str, ...] = (
    'lesson_vocal_open',
    'lesson_dance_open',
    'lesson_visual_open',
    'lesson_vocal_open_star',
    'lesson_dance_open_star',
    'lesson_visual_open_star',
)
HIF_SCHOOL_ACTION_TYPES: tuple[str, ...] = ('school_class_vocal', 'school_class_dance', 'school_class_visual')
HIF_INTERVAL_ACTION_TYPES: tuple[str, ...] = ('hif_interval', 'hif_interval_recover')
HIF_ACTION_LABELS: dict[str, str] = {
    'lesson_vocal_open': '公开课(声乐)',
    'lesson_dance_open': '公开课(舞蹈)',
    'lesson_visual_open': '公开课(形象)',
    'lesson_vocal_open_star': '☆公开课(声乐)',
    'lesson_dance_open_star': '☆公开课(舞蹈)',
    'lesson_visual_open_star': '☆公开课(形象)',
    'school_class_vocal': '授业(声乐)',
    'school_class_dance': '授业(舞蹈)',
    'school_class_visual': '授业(形象)',
    'hif_interval': '间歇(强化)',
    'hif_interval_recover': '间歇(强化+回复)',
}
STAT_KEYS: tuple[str, str, str] = ('vocal', 'dance', 'visual')
STAT_TO_SUB_TAG: dict[str, str] = {'vocal': 'sub_vo', 'dance': 'sub_da', 'visual': 'sub_vi'}
STAT_ADDITION_EFFECT_TYPES: dict[str, str] = {
    'vocal': 'ProduceEffectType_VocalAddition',
    'dance': 'ProduceEffectType_DanceAddition',
    'visual': 'ProduceEffectType_VisualAddition',
}
PLAN_TYPE_TO_TAG: dict[str, str] = {
    'ProducePlanType_Plan1': 'plan1',
    'ProducePlanType_Plan2': 'plan2',
    'ProducePlanType_Plan3': 'plan3',
}


def is_hif_open_lesson_action(action_type: str) -> bool:
    """判断动作是否为 HIF 公開レッスン。"""

    return action_type in HIF_OPEN_LESSON_ACTION_TYPES


def is_hif_school_action(action_type: str) -> bool:
    """判断动作是否为 HIF 授業（按属性拆分的三个动作）。"""

    return action_type in HIF_SCHOOL_ACTION_TYPES


def is_hif_interval_action(action_type: str) -> bool:
    """判断动作是否为 本戦 インターバル 动作。"""

    return action_type in HIF_INTERVAL_ACTION_TYPES


@dataclass(frozen=True)
class HifSelectionMemory:
    """選抜試験メモリー：選抜試験 结束后交给 本戦 的继承数据。

    字段含义见 `HifMemoryHandoffConfig`；`deck_cards` 保存卡 id 与强化次数，
    `produce_item_fire_counts` 保存 P 道具（如 H.I.Fワッペン）已触发次数以便本戦继续计数。
    """

    source_produce_id: str
    idol_card_id: str
    vocal: float
    dance: float
    visual: float
    max_stamina: float
    star_quality: float
    dearness_level: int
    deck_cards: tuple[tuple[str, int], ...] = ()
    drink_ids: tuple[str, ...] = ()
    produce_item_fire_counts: tuple[tuple[str, int], ...] = ()
    customize_item_tier: int = 0
    selection_scores: tuple[float, ...] = ()
    selection_rating: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    #: 与 deck_cards 逐项对齐；旧记录留空仍可导入。
    deck_customizations: tuple[tuple[str, ...], ...] = ()
    deck_memory_sources: tuple[tuple[str, str], ...] = ()
    customize_item_state: dict[str, Any] = field(default_factory=dict)
    produce_item_cooldowns: tuple[tuple[str, int], ...] = ()
    exam_enchant_specs: tuple[dict[str, Any], ...] = ()
    completed_event_ids: tuple[str, ...] = ()
    deck_instances: tuple[dict[str, Any], ...] = ()
    support_skill_states: tuple[dict[str, Any], ...] = ()
    support_card_states: tuple[dict[str, Any], ...] = ()
    modifier_state: dict[str, Any] = field(default_factory=dict)


class HifRuntimeSupport:
    """挂在 `ProduceRuntime` 上的 H.I.F 专用行为集合。"""

    def __init__(self, runtime: 'ProduceRuntime', config: HifScenarioConfig, selection_memory: HifSelectionMemory | None = None):
        """绑定运行时与场景配置。

        Args:
            runtime: 宿主培育运行时。
            config: 由主数据装配的 HIF 配置。
            selection_memory: 本戦 使用的選抜試験メモリー；選抜 场景忽略。
        """

        self.runtime = runtime
        self.config = config
        self.selection_memory = selection_memory
        self.open_lessons = runtime.repository.load_table('ProduceStepOpenLesson')
        self.growth_panels = runtime.repository.load_table('ProduceGrowthPanel')
        self.dearness_levels = runtime.repository.load_table('CharacterDearnessLevel')
        self.produce_skills = runtime.repository.load_table('ProduceSkill')

    # ── 基础属性 ─────────────────────────────────────────────

    @property
    def is_final(self) -> bool:
        """是否为 本戦（produce-008）。"""

        return self.runtime.scenario.route_type == HIF_ROUTE_FINAL

    @property
    def is_selection(self) -> bool:
        """是否为 選抜試験（produce-007）。"""

        return self.runtime.scenario.route_type == HIF_ROUTE_SELECTION

    def base_state_fields(self) -> dict[str, Any]:
        """返回 HIF 需要追加到 `ProduceRuntime.state` 的字段。"""

        return {
            'star_quality': 0.0,
            'star_gain_rate': 0.0,
            'star_quality_cap': float(self.config.star_quality_cap),
            'customize_item_tier': 0.0,
            'customize_point_discount': 0.0,
            'drink_limit_bonus': 0.0,
            'hif_round1_score': 0.0,
            'hif_round1_adjusted_score': 0.0,
            'hif_round1_rival_scores': [],
            'hif_round1_rival_character_ids': [],
            'hif_round2_score': 0.0,
            'hif_combined_score': 0.0,
            'hif_combined_rank': 0,
            'hif_prima_stella': False,
            'hif_star_before_round2': 0.0,
            'hif_selection_scores': [],
            'hif_interval_used': False,
        }

    # ── 日程判定 ─────────────────────────────────────────────

    def is_interval_day(self) -> bool:
        """当前是否处于 本戦 的インターバル（Round1 与 Round2 之间）。"""

        if not self.is_final or self.config.interval_step <= 0:
            return False
        if self.runtime.pre_audition_phase != 'weekly' or self.runtime.pending_audition_stage is not None:
            return False
        return int(self.runtime.state.get('step') or 0) + 1 == int(self.config.interval_step)

    def next_audition_index(self) -> int:
        """返回下一场试验在 `config.auditions` 中的下标（超出时钳到最后一场）。"""

        index = int(self.runtime.state.get('audition_index') or 0)
        return min(max(index, 0), max(len(self.config.auditions) - 1, 0))

    def next_audition_spec(self):
        """返回下一场试验的配置。"""

        return self.config.auditions[self.next_audition_index()]

    # ── スター性 ─────────────────────────────────────────────

    def star_cap(self) -> float:
        """返回当前阶段的スター性上限（Round2 前为 1110，之后为 1335）。"""

        state = self.runtime.state
        if self.is_final and float(state.get('hif_round2_score') or 0.0) <= 0.0 and not bool(state.get('hif_round2_started')):
            return float(min(self.config.star_quality_cap_before_round2, self.config.star_quality_cap))
        if self.is_selection:
            return float(min(self.config.star_quality_cap_before_round2, self.config.star_quality_cap))
        return float(self.config.star_quality_cap)

    def gain_star(self, base_value: float, *, apply_rate: bool = True) -> int:
        """按「基础值 × (1 + star_permil_up) 向下取整」累加スター性，并按上限截断。

        Args:
            base_value: 未乘倍率的基础获得量。
            apply_rate: 是否套用亲爱度等来源的 `StarPermilUp` 倍率。

        Returns:
            实际写入状态的增量。
        """

        state = self.runtime.state
        rate = float(state.get('star_gain_rate') or 0.0) if apply_rate else 0.0
        gained = int(math.floor(max(float(base_value), 0.0) * (1.0 + rate) + 1e-9))
        before = float(state.get('star_quality') or 0.0)
        after = min(before + gained, self.star_cap())
        state['star_quality'] = float(max(after, before))
        return int(round(state['star_quality'] - before))

    def star_score_bonus_ratio(self) -> float:
        """スター性 → 试验スコアボーナス 的线性加成比例（hif.md §6.6 [推断]）。"""

        # TODO(HIF-verify): 真实公式未知，按线性到 star_quality_cap 封顶实现。
        star = float(self.runtime.state.get('star_quality') or 0.0)
        cap = max(float(self.config.star_quality_cap), 1.0)
        return float(np.clip(star / cap, 0.0, 1.0)) * float(self.config.star_score_bonus_max_ratio)

    def star_gain_from_audition(self, stage_type: str, score: float) -> int:
        """按试验分数换算スター性基础获得量（未乘倍率、未截断）。

        - 選抜試験：`floor(starScoreBonusBaseLine × clamp(score / cap, 0, 1))`。TODO(HIF-verify)
        - 本戦：使用社区实测的 R2 分段表；Round1 按配置改用 ×1.2 后的分数。
        """

        if getattr(self.runtime, 'hif_ruleset_version', None):
            from gakumas_arena.produce.courses import audition_star_base
            return audition_star_base(self.runtime.scenario.produce_id, stage_type, score)
        spec = self.config.audition_for_stage(stage_type)
        if spec is None:
            return 0
        if self.is_final:
            effective = float(score)
            if stage_type == 'ProduceStepType_AuditionMid1' and self.config.round1_star_gain_uses_adjusted_score:
                effective = math.floor(float(score) * float(self.config.round1_score_multiplier) + 1e-9)
            return int(calculate_hif_round2_star_gain(effective))
        cap = max(float(spec.star_score_cap), 1.0)
        ratio = float(np.clip(float(score) / cap, 0.0, 1.0))
        return int(math.floor(float(spec.star_score_bonus_baseline) * ratio + 1e-9))

    # ── 重置 / 交接 ──────────────────────────────────────────

    def on_reset(self) -> None:
        """在 `ProduceRuntime.reset()` 末尾应用メモリー继承、成长面板与开场事件。"""

        if self.is_final and self.selection_memory is not None:
            self._apply_selection_memory(self.selection_memory)
        self._apply_dearness_hif_skills()
        self._apply_growth_panel()
        if self.is_final and self.selection_memory is not None:
            self.runtime.state.update(deepcopy(self.selection_memory.modifier_state))
        if self.config.opening_event_detail_id:
            detail = self.runtime.event_details.first(self.config.opening_event_detail_id) or {}
            effect_ids = [str(value) for value in detail.get('produceEffectIds', []) or [] if value]
            self.runtime._apply_effect_rows(effect_ids, source_action_type='hif_story')

    def _apply_selection_memory(self, memory: HifSelectionMemory) -> None:
        """把選抜試験メモリー写入本戦初始状态。"""

        runtime = self.runtime
        handoff = self.config.memory_handoff
        state = runtime.state
        state['dearness_level'] = memory.dearness_level
        if handoff.carry_parameters:
            for key, value in (('vocal', memory.vocal), ('dance', memory.dance), ('visual', memory.visual)):
                state[key] = runtime._clamp_parameter_value(float(value))
        if handoff.carry_max_stamina and float(memory.max_stamina) > 0.0:
            state['max_stamina'] = float(memory.max_stamina)
            state['stamina'] = float(memory.max_stamina)
        if handoff.carry_star_quality:
            state['star_quality'] = float(min(max(memory.star_quality, 0.0), self.config.star_quality_cap_before_round2))
        if handoff.carry_customize_item:
            state['customize_item_tier'] = float(memory.customize_item_tier)
            if memory.customize_item_state:
                runtime.customize_items.restore(memory.customize_item_state)
        if handoff.carry_deck and memory.deck_cards:
            from ...idol_config import apply_card_customizations

            for details in (memory.deck_customizations, memory.deck_memory_sources):
                if details and len(details) != len(memory.deck_cards):
                    raise ValueError('HIF deck variant/provenance count mismatch')
            deck: list[dict[str, Any]] = []
            for index, (card_id, upgrade_count) in enumerate(memory.deck_cards):
                row = runtime.repository.card_row_by_upgrade(str(card_id), int(upgrade_count), fallback_to_canonical=True)
                if row is not None:
                    customizes = memory.deck_customizations[index] if memory.deck_customizations else ()
                    card = deepcopy(apply_card_customizations(runtime.repository, row, customizes))
                    if memory.deck_memory_sources:
                        card['sourceMemoryId'], card['sourceMemoryIdolCardId'] = memory.deck_memory_sources[index]
                    deck.append(card)
            if deck:
                runtime.deck = deck
                runtime.initial_deck_card_ids = {str(card.get('id') or '') for card in deck if str(card.get('id') or '')}
        if handoff.carry_drinks and memory.drink_ids:
            drinks: list[dict[str, Any]] = []
            for drink_id in memory.drink_ids:
                row = runtime.repository.produce_drinks.first(str(drink_id))
                if row is not None:
                    drinks.append(dict(row))
            runtime.drinks = drinks
        if handoff.carry_deck and memory.deck_instances:
            runtime.deck = [deepcopy(card) for card in memory.deck_instances]
        if memory.support_skill_states:
            from .runtime import ActiveProduceSkillState
            runtime.active_produce_skills = [ActiveProduceSkillState(**row) for row in memory.support_skill_states]
        if memory.support_card_states:
            from ...loadout import SupportCardSelection
            runtime.selected_support_cards = tuple(SupportCardSelection(**row) for row in memory.support_card_states)
        if handoff.carry_produce_items and memory.produce_item_fire_counts:
            owned = {item.item_id: item for item in runtime.active_produce_items}
            for item_id, fire_count in memory.produce_item_fire_counts:
                active = owned.get(str(item_id))
                if active is None:
                    runtime._register_produce_item(str(item_id), source='hif_memory')
                    active = next((item for item in runtime.active_produce_items if item.item_id == str(item_id)), None)
                if active is not None:
                    active.fire_count = max(int(active.fire_count), int(fire_count))
                    active.cooldown_remaining = dict(memory.produce_item_cooldowns).get(str(item_id), 0)
        if memory.exam_enchant_specs:
            from .items import RuntimeExamStatusEnchantSpec
            runtime.exam_status_enchant_specs = [RuntimeExamStatusEnchantSpec(**data)
                                                 for data in memory.exam_enchant_specs]
            runtime.exam_status_enchant_ids = [s.enchant_id for s in runtime.exam_status_enchant_specs]
        runtime.events.completed = list(memory.completed_event_ids)
        state['hif_selection_scores'] = [float(value) for value in memory.selection_scores]

    def _apply_dearness_hif_skills(self) -> None:
        """应用 `CharacterDearnessLevel.produceSkills` 里的 H.I.F 专用亲爱度技能。

        通用 loadout 只把亲爱度折算成分数倍率，没有读取 `produceSkills`；这里只补
        `star_permil_up`（Lv28~36：獲得スター性 +5%…+50%）与 `produce_drink_possess_limit_up`（Lv37：饮料上限+1），
        避免与已按亲爱度估算的 `audition_parameter_bonus` 重复计算。
        """

        if not self.config.apply_dearness_hif_skills:
            return
        loadout = self.runtime.idol_loadout
        if loadout is None:
            return
        character_id = str(loadout.stat_profile.character_id or '')
        dearness_level = (self.selection_memory.dearness_level if self.is_final and self.selection_memory is not None
                          else int(loadout.dearness_level or 0))
        matched_row: dict[str, Any] | None = None
        for row in self.dearness_levels.rows:
            if str(row.get('characterId') or '') != character_id:
                continue
            level = int(row.get('dearnessLevel') or 0)
            if level <= dearness_level and (matched_row is None or level > int(matched_row.get('dearnessLevel') or 0)):
                matched_row = row
        if matched_row is None:
            return
        for skill in matched_row.get('produceSkills', []) or []:
            skill_id = str(skill.get('id') or '')
            if not any(tag in skill_id for tag in self.config.dearness_skill_id_tags):
                continue
            skill_level = int(skill.get('level') or 1)
            candidates = [row for row in self.produce_skills.all(skill_id) if int(row.get('level') or 1) == skill_level]
            skill_row = candidates[0] if candidates else None
            if skill_row is None:
                continue
            effect_ids = [
                str(skill_row.get(key) or '')
                for key in ('produceEffectId1', 'produceEffectId2', 'produceEffectId3')
                if skill_row.get(key)
            ]
            self.runtime._apply_effect_rows(effect_ids, source_action_type='idol_skill')

    def _apply_growth_panel(self) -> None:
        """按配置等级应用 H.I.F ボーナス 成长面板（`ProduceGrowthPanel`）的 ProduceEffect。"""

        levels = dict(self.config.growth_panel_levels or {})
        if not levels:
            return
        split_type = 'ProduceSplitType_Selection' if self.is_selection else 'ProduceSplitType_Final'
        # 主数据里 `produceGrowthPanelSheetId` 是整张面板（produce_growth_panel_sheet-hif），
        # `id` 才是单个面板项（…-hif-01 ~ -09），同一 id 下按 `level` 分多行；
        # 每级的数值是「总量」（上限值 +50 → +80 → … → +200），因此只应用已解锁的最高一级。
        selected_rows: dict[str, dict[str, Any]] = {}
        for row in self.growth_panels.rows:
            if str(row.get('produceGrowthPanelSheetId') or '') != self.config.growth_panel_sheet_id:
                continue
            panel_id = str(row.get('id') or '')
            panel_key = panel_id.rsplit('-', 1)[-1]
            unlocked_level = int(levels.get(panel_key, levels.get(panel_id, 0)) or 0)
            row_level = int(row.get('level') or 0)
            if row_level > unlocked_level:
                continue
            row_split = str(row.get('produceSplitType') or 'ProduceSplitType_Unknown')
            if row_split not in {'ProduceSplitType_Unknown', split_type}:
                continue
            current = selected_rows.get(panel_id)
            if current is None or int(current.get('level') or 0) < row_level:
                selected_rows[panel_id] = row
        for panel_id in sorted(selected_rows):
            effect_ids = [str(value) for value in selected_rows[panel_id].get('produceEffectIds', []) or [] if value]
            self.runtime._apply_effect_rows(effect_ids, source_action_type='hif_growth_panel')

    def export_selection_memory(self) -> HifSelectionMemory:
        """把当前（通常是選抜試験结束后的）状态导出为選抜試験メモリー。"""

        from dataclasses import asdict
        runtime = self.runtime
        state = runtime.state
        idol_card_id = runtime.idol_loadout.idol_card_id if runtime.idol_loadout is not None else ''
        selection_scores = tuple(float(item.get('exam_score') or 0.0) for item in runtime.audition_history)
        rating = calculate_hif_selection_rating(
            params=(float(state.get('vocal') or 0.0), float(state.get('dance') or 0.0), float(state.get('visual') or 0.0)),
            star_quality=float(state.get('star_quality') or 0.0),
        )
        return HifSelectionMemory(
            source_produce_id=str(runtime.scenario.produce_id),
            idol_card_id=str(idol_card_id),
            vocal=float(state.get('vocal') or 0.0),
            dance=float(state.get('dance') or 0.0),
            visual=float(state.get('visual') or 0.0),
            max_stamina=float(state.get('max_stamina') or 0.0),
            star_quality=float(state.get('star_quality') or 0.0),
            dearness_level=int(state.get('dearness_level') or 0),
            deck_cards=tuple((str(card.get('id') or ''), int(card.get('upgradeCount') or 0)) for card in runtime.deck if str(card.get('id') or '')),
            drink_ids=tuple(str(drink.get('id') or '') for drink in runtime.drinks if str(drink.get('id') or '')),
            produce_item_fire_counts=tuple((str(item.item_id), int(item.fire_count)) for item in runtime.active_produce_items),
            customize_item_tier=int(state.get('customize_item_tier') or 0),
            selection_scores=selection_scores,
            selection_rating=int(rating.get('rating') or 0),
            metadata={'route_clear': bool(runtime.final_summary.get('route_clear')) if runtime.final_summary else False,
                      'loadout_config':deepcopy(getattr(runtime,'hif_loadout_config',None)),
                      'card_switches':deepcopy(getattr(runtime,'hif_card_switch_settings',{})),
                      'growth_panel_levels':deepcopy(self.config.growth_panel_levels)},
            deck_customizations=tuple(tuple(card.get('customizedProduceCardCustomizeIds') or ()) for card in runtime.deck if card.get('id')),
            deck_memory_sources=tuple((str(card.get('sourceMemoryId') or ''), str(card.get('sourceMemoryIdolCardId') or '')) for card in runtime.deck if card.get('id')),
            customize_item_state=runtime.customize_items.export(),
            produce_item_cooldowns=tuple((item.item_id, item.cooldown_remaining) for item in runtime.active_produce_items),
            exam_enchant_specs=tuple(asdict(spec) for spec in runtime.exam_status_enchant_specs),
            completed_event_ids=tuple(runtime.events.completed),
            deck_instances=tuple(deepcopy(runtime.deck)),
            support_skill_states=tuple(asdict(skill) for skill in runtime.active_produce_skills),
            support_card_states=tuple(asdict(card) for card in runtime.selected_support_cards),
            modifier_state={key:deepcopy(value) for key,value in state.items() if key in {
                'vocal_growth','dance_growth','visual_growth','generic_sp_rate_bonus','vocal_sp_rate_bonus',
                'dance_sp_rate_bonus','visual_sp_rate_bonus','star_gain_rate','drink_limit_bonus',
                'shop_reroll_count_bonus','shop_rerolls_used','card_select_reroll_count_bonus','card_reward_rerolls_used',
                'exclude_count_bonus','excluded_card_ids','excludes_used','card_instance_serial','event_school_stamina_permil',
                'support_event_point_bonus','support_event_stat_bonus','support_event_stamina_bonus','support_event_probability_up_permyriad',
                'card_upgrade_probability_bonus','shop_upgrade_discount','shop_delete_discount',
                'shop_card_discount','shop_drink_discount','shop_discount','customize_point_discount',
                'shop_card_upgrade_count','shop_card_delete_count','shop_upgrade_count','shop_delete_count'}},
        )

    # ── 动作采样 ─────────────────────────────────────────────

    def _current_pool_tag(self, tags: tuple[str, ...]) -> str:
        """按下一场试验的下标取事件池标签。"""

        if not tags:
            return ''
        index = min(self.next_audition_index(), len(tags) - 1)
        return str(tags[index])

    def _plan_tag(self) -> str:
        """返回当前偶像流派对应的事件池标签（plan1/plan2/plan3）。"""

        loadout = self.runtime.idol_loadout
        plan_type = str(loadout.stat_profile.plan_type) if loadout is not None else ''
        return PLAN_TYPE_TO_TAG.get(plan_type, 'plan1')

    def _open_lesson_row(self, *, stage_id: str, lesson_kind: str, is_sp: bool, sub_stat: str) -> dict[str, Any] | None:
        """按阶段/型/SP/副属性拼出 `ProduceStepOpenLesson` 行 id 并查表。"""

        sp_tag = '-sp' if is_sp else ''
        row_id = f'p_step_open_lesson-{stage_id}-{lesson_kind}{sp_tag}-{STAT_TO_SUB_TAG[sub_stat]}'
        return self.open_lessons.first(row_id)

    def _pick_sub_stat(self, main_stat: str) -> str:
        """按配置策略选择公開レッスン的副属性。"""

        others = [key for key in STAT_KEYS if key != main_stat]
        policy = str(self.config.open_lesson_sub_parameter_policy or 'lowest')
        if policy == 'random':
            return str(others[int(self.runtime.np_random.integers(0, len(others)))])
        # 默认：另两项中较低者，与「授業选最低属性」的社区习惯一致。TODO(HIF-verify)
        return min(others, key=lambda key: float(self.runtime.state.get(key) or 0.0))

    def sample_action(self, action_type: str) -> 'ProduceActionCandidate | None':
        """为 HIF 专用动作类型采样候选；非 HIF 动作返回 None 交由通用流程处理。"""

        if is_hif_open_lesson_action(action_type):
            return self._sample_open_lesson(action_type)
        if is_hif_school_action(action_type):
            return self._sample_school(action_type)
        if action_type == ACTION_OUTING:
            return self._sample_outing()
        if action_type == ACTION_ACTIVITY_SUPPLY:
            from .runtime import ProduceActionCandidate
            # HIF fixed 差し入れ; reward selectors run only after this action is chosen.
            return ProduceActionCandidate(label='差し入れ', action_type=ACTION_ACTIVITY_SUPPLY,
                effect_types=[], produce_effect_ids=[], produce_point_delta=80,
                source_row_id='hif-fixed-supply/wiki-2026-09-09')
        if is_hif_interval_action(action_type):
            return self._sample_interval(action_type)
        return None

    def _sample_open_lesson(self, action_type: str) -> 'ProduceActionCandidate':
        """采样一次公開レッスン：主属性/副属性/パラメータ型或スター型，SP 在排程时预先掷定。"""

        from .runtime import ProduceActionCandidate

        parts = action_type.split('_')
        main_stat = parts[1]
        lesson_kind = 'star' if action_type.endswith('_star') else 'parameter'
        stage_id = self._current_pool_tag(self.config.open_lesson_stage_ids)
        sub_stat = self._pick_sub_stat(main_stat)
        sp_probability = float(np.clip(float(self.config.open_lesson_sp_base_rate) + self.runtime._sp_rate_bonus(f'lesson_{main_stat}_sp'), 0.0, 1.0))
        is_sp = bool(self.runtime.np_random.random() < sp_probability)
        row = self._open_lesson_row(stage_id=stage_id, lesson_kind=lesson_kind, is_sp=is_sp, sub_stat=sub_stat)
        if row is None and is_sp:
            is_sp = False
            row = self._open_lesson_row(stage_id=stage_id, lesson_kind=lesson_kind, is_sp=False, sub_stat=sub_stat)
        if row is None:
            raise KeyError(f'HIF open lesson row missing from master database: stage={stage_id}, kind={lesson_kind}, sub={sub_stat}')
        state = self.runtime.state
        main_gain = float(row.get('mainParameter') or 0.0) * (1.0 + float(state.get(f'{main_stat}_growth') or 0.0))
        sub_base = float(row.get('subParameter') or 0.0)
        sub_gain = sub_base * (1.0 + float(state.get(f'{sub_stat}_growth') or 0.0)) if self.config.open_lesson_growth_applies_to_sub else sub_base
        deltas = {main_stat: main_gain, sub_stat: sub_gain}
        stat_deltas = tuple(float(deltas.get(key, 0.0)) for key in STAT_KEYS)
        label = HIF_ACTION_LABELS.get(action_type, action_type)
        if is_sp:
            label = f'SP{label}'
        return ProduceActionCandidate(
            label=label,
            action_type=action_type,
            effect_types=[STAT_ADDITION_EFFECT_TYPES[main_stat], STAT_ADDITION_EFFECT_TYPES[sub_stat]],
            produce_effect_ids=[],
            stamina_delta=-float(row.get('stamina') or 0.0),
            produce_point_delta=(50.0 if self.is_final else 30.0) if getattr(self.runtime,'hif_ruleset_version',None) else 0.0,
            success_probability=1.0,
            stat_deltas=stat_deltas,
            star_delta=float(row.get('star') or 0.0),
            source_row_id=str(row.get('id') or ''),
        )

    def _sample_school(self, action_type: str) -> 'ProduceActionCandidate':
        """Sample the event; defer its exact option until the player chooses this action."""

        from .runtime import ProduceActionCandidate

        stat = action_type.rsplit('_', 1)[-1]
        pool_tag = self._current_pool_tag(self.config.school_pool_tags)
        plan_tag = self._plan_tag()
        if self.is_selection:
            prefix = f'event-detail-school-{stat}-003-produce_007-{plan_tag}-{pool_tag}-'
        else:
            prefix = f'event-detail-school-{stat}-003-produce_008-{plan_tag}-'
        details = [row for row in self.runtime.event_details.rows if str(row.get('id') or '').startswith(prefix)]
        if not details:
            raise KeyError(f'HIF school event pool missing from master database: prefix={prefix}')
        detail = details[int(self.runtime.np_random.integers(0, len(details)))]
        suggestion_ids = [str(value) for value in detail.get('produceStepEventSuggestionIds', []) or [] if value]
        chosen_ids = suggestion_ids
        if not chosen_ids:
            raise KeyError(f'HIF school suggestions missing: detail={detail.get("id")}')
        suggestion_id = chosen_ids[0]
        suggestion = self.runtime.event_suggestions.first(suggestion_id) or {}
        produce_effect_ids = [str(value) for value in suggestion.get('produceEffectIds', []) or [] if value]
        effect_types = self.runtime._effect_types_for_ids(produce_effect_ids)
        stamina = float(suggestion.get('stamina') or 0.0)
        if stamina <= 0.0:
            stamina = 5.0  # hif.md §4.2：授業体力 5
        return ProduceActionCandidate(
            label=HIF_ACTION_LABELS.get(action_type, action_type),
            action_type=action_type,
            effect_types=effect_types,
            produce_effect_ids=produce_effect_ids,
            stamina_delta=-stamina,
            produce_point_delta=float(suggestion.get('producePoint') or 0.0),
            produce_card_id=str(suggestion.get('produceCardId') or ''),
            resource_level=int(suggestion.get('produceCardUpgradeCount') or 0),
            success_probability=1.0,
            source_row_id=str(suggestion.get('id') or ''),
            event_option_ids=tuple(chosen_ids),
            event_detail_id=detail['id'],
        )

    def _sample_outing(self) -> 'ProduceActionCandidate':
        """HIF おでかけ is master EventActivity, with three fixed cost/reward options."""

        from .runtime import ProduceActionCandidate

        pool_tag = self._current_pool_tag(self.config.activity_pool_tags)
        library = self.runtime.events.library
        event_ids = library.hif_event_ids(self.runtime.scenario.produce_id, kind='Activity',
                                          pool_tag=pool_tag if self.is_selection else None)
        if not event_ids:
            raise KeyError(f'HIF activity events missing: {self.runtime.scenario.produce_id}/{pool_tag}')
        # Sample one event, then offer only that event's options. The legacy
        # uniform event sampler is configurable separately from player choices.
        event_id = event_ids[int(self.runtime.np_random.integers(0, len(event_ids)))]
        detail = self.runtime.event_details.first(event_id)
        suggestions = [self.runtime.event_suggestions.first(sid)
                       for sid in detail['produceStepEventSuggestionIds']]
        legal = [s for s in suggestions if float(s.get('producePoint') or 0) <= self.runtime.state['produce_points']]
        suggestion = legal[0]
        produce_effect_ids = [str(value) for value in suggestion.get('produceEffectIds', []) or [] if value]
        effect_types = self.runtime._effect_types_for_ids(produce_effect_ids)
        # 主数据里 producePoint=50 是「上段」选项的代价（hif.md §4.3），这里按支出记录。
        point_cost = float(suggestion.get('producePoint') or 0.0)
        return ProduceActionCandidate(
            label='外出',
            action_type=ACTION_OUTING,
            effect_types=effect_types,
            produce_effect_ids=produce_effect_ids,
            stamina_delta=0.0,
            produce_point_delta=-point_cost,
            produce_card_id=str(suggestion.get('produceCardId') or ''),
            resource_level=int(suggestion.get('produceCardUpgradeCount') or 0),
            success_probability=1.0,
            source_row_id=str(suggestion.get('id') or ''),
            event_option_ids=tuple(s['id'] for s in suggestions),
            event_detail_id=event_id,
        )

    def grant_selected_reward(self, *, drink=False, upgraded=False, sr_drink=False):
        """Select one of three sampled offers; pool probabilities remain an explicit approximation."""
        rt = self.runtime
        if getattr(rt,'hif_sampling_kernel',None) is not None:
            if not drink and len(rt.deck)>=99:
                return
            pool_id = f'{rt.scenario.produce_id}:supply:{"drink" if drink else "card"}'
            candidates = rt.hif_sampling_kernel.candidates(pool_id,kind='drink' if drink else 'card',
                upgraded=1 if upgraded else None,rarity={'ProduceDrinkRarity_Sr','ProduceDrinkRarity_Ssr'} if sr_drink else None)
            if not candidates:
                return
            if drink:
                index = rt.choose_produce_option('drink_reward',candidates+[{'skip':True}],pool_id=pool_id)
                if index == len(candidates):
                    return
                row = candidates[index]
            else:
                row = rt.hif_sampling_kernel.choose_reward(pool_id,candidates,
                    resample=lambda:rt.hif_sampling_kernel.candidates(pool_id,kind='card',upgraded=1 if upgraded else None))
                if row is None:
                    return
            rt._grant_resource('ProduceResourceType_ProduceDrink' if drink else 'ProduceResourceType_ProduceCard',row['id'],int(row.get('upgradeCount') or 0))
            return
        if drink:
            pool = rt.repository.build_drink_inventory(rt.scenario, max_items=1000, rng=rt.np_random,
                plan_type=rt.idol_loadout.stat_profile.plan_type if rt.idol_loadout else None)
            if sr_drink:
                pool = [r for r in pool if r.get('rarity') in ('ProduceDrinkRarity_Sr', 'ProduceDrinkRarity_Ssr')]
        else:
            pool = rt._selection_card_pool()
        if not pool:
            raise ValueError('HIF selected reward has no candidates')
        indices = rt.np_random.choice(len(pool), size=min(3, len(pool)), replace=False)
        candidates = []
        for i in indices:
            row = pool[int(i)]
            if not drink:
                row = (rt._lookup_card_upgrade_row(row['id'], 1) if upgraded else
                       rt._sample_capped_card_variant(row['id'], max_upgrade_count=1))
                if row is None:
                    raise ValueError('HIF reward card has no requested upgrade variant')
            candidates.append(row)
        index = rt.choose_produce_option('drink_reward' if drink else 'card_reward', candidates,
                                         origin='hif_outing_or_supply', guaranteed_upgrade=upgraded)
        selected = candidates[index]
        rt._grant_resource('ProduceResourceType_ProduceDrink' if drink else 'ProduceResourceType_ProduceCard',
                           selected['id'], int(selected.get('upgradeCount') or 0))

    def grant_supply_rewards(self):
        self.grant_selected_reward(drink=True, sr_drink=True)
        self.grant_selected_reward()

    def _sample_interval(self, action_type: str) -> 'ProduceActionCandidate':
        """采样インターバル动作：强化 1 张卡，可选用 P 点回复体力。"""

        from .runtime import ProduceActionCandidate

        state = self.runtime.state
        recover_points = 0.0
        recover_stamina = 0.0
        if action_type == 'hif_interval_recover':
            cost = max(float(self.config.interval_recover_point_cost), 1.0)
            per_unit = max(float(self.config.interval_recover_stamina), 0.0)
            missing = max(float(state.get('max_stamina') or 0.0) - float(state.get('stamina') or 0.0), 0.0)
            affordable_units = int(float(state.get('produce_points') or 0.0) // cost)
            needed_units = int(math.ceil(missing / per_unit)) if per_unit > 0 else 0
            units = max(min(affordable_units, needed_units), 0)
            recover_points = -cost * units
            recover_stamina = per_unit * units
        return ProduceActionCandidate(
            label=HIF_ACTION_LABELS.get(action_type, action_type),
            action_type=action_type,
            effect_types=['ProduceEffectType_ProduceCardUpgrade'],
            produce_effect_ids=[],
            stamina_delta=recover_stamina,
            produce_point_delta=recover_points,
            success_probability=1.0,
        )

    def apply_interval(self, candidate: 'ProduceActionCandidate') -> None:
        """执行インターバル：按 `ProduceSetting.stepIntervalUpgradeProduceCardCount` 强化随机卡。"""

        upgrade_count = int(self.runtime.produce_setting.get('stepIntervalUpgradeProduceCardCount') or 1)
        self.runtime._upgrade_matching_cards('', max(upgrade_count, 0), source_action_type=candidate.action_type,
                                             select_targets=True, minimum_count=max(upgrade_count, 0))
        self.runtime.state['hif_interval_used'] = True

    def effect_source_action_type(self, action_type: str) -> str:
        """把 HIF 专用动作映射到通用效果来源类型（用于事件加成倍率判断）。"""

        if is_hif_school_action(action_type):
            return ACTION_SCHOOL_CLASS
        return action_type

    def action_available(self, candidate: 'ProduceActionCandidate') -> bool | None:
        """HIF 专用可用性规则；返回 None 表示交由通用规则判断。"""

        if is_hif_interval_action(candidate.action_type):
            return self.is_interval_day()
        if self.is_interval_day():
            return False
        return None

    # ── 试验结果 ─────────────────────────────────────────────

    def on_audition_cleared(self, stage_type: str) -> None:
        """试验通过后应用主数据里的 after_audition 剧情事件效果（删基本卡 / カスタムPアイテム 等）。"""

        detail_id = self.config.after_audition_event_detail_ids.get(stage_type, '')
        if not detail_id:
            return
        detail = self.runtime.event_details.first(detail_id) or {}
        effect_ids = [str(value) for value in detail.get('produceEffectIds', []) or [] if value]
        self.runtime._apply_effect_rows(effect_ids, source_action_type='hif_story')

    def rival_score_multiplier_mode(self) -> str:
        """返回 本戦 静态对手分数的采样模式。"""

        return str(self.config.static_npc_score_mode or 'sample')

    def adjust_audition_result(
        self,
        *,
        stage_type: str,
        effective_score: float,
        rival_scores: list[float],
        rival_character_ids: list[str],
        rank: int,
        rank_threshold: int,
    ) -> dict[str, Any]:
        """在通用排名之上叠加 HIF 规则，返回需要合并进考试结果的附加字段。

        - 選抜試験：名次 ≤ rankThreshold（2）即通过；平分按 ≥ 判定（hif.md §6.2 [推断]）。
        - 本戦 Round1：名次 ≤ 3（3 人赛，不淘汰），记录 ×1.2 的登记分。
        - 本戦 Round2：合计分（R1×1.2 + R2）最高者为 一番星；rankThreshold=1。
        """

        state = self.runtime.state
        star_gain_base = self.star_gain_from_audition(stage_type, effective_score)
        result: dict[str, Any] = {
            'hif_star_gain_base': int(star_gain_base),
            'hif_star_quality_before': float(state.get('star_quality') or 0.0),
        }
        if not self.is_final:
            result.update({'rank': int(rank), 'cleared': int(rank) <= int(rank_threshold)})
            return result
        multiplier = float(self.config.round1_score_multiplier)
        if stage_type == 'ProduceStepType_AuditionMid1':
            adjusted = float(math.floor(float(effective_score) * multiplier + 1e-9))
            result.update(
                {
                    'hif_round': 1,
                    'hif_round1_score': float(effective_score),
                    'hif_round1_adjusted_score': adjusted,
                    'hif_round1_rival_scores': [float(value) for value in rival_scores],
                    'hif_round1_rival_character_ids': list(rival_character_ids),
                    'rank': int(rank),
                    'cleared': int(rank) <= int(rank_threshold),
                }
            )
            return result
        round1_adjusted = float(state.get('hif_round1_adjusted_score') or 0.0)
        round1_rivals = [float(value) for value in state.get('hif_round1_rival_scores') or []]
        round1_rival_ids = [str(value) for value in state.get('hif_round1_rival_character_ids') or []]
        combined = round1_adjusted + float(effective_score)
        rival_totals: list[float] = []
        for index, round2_rival in enumerate(rival_scores):
            round1_rival = 0.0
            character_id = rival_character_ids[index] if index < len(rival_character_ids) else ''
            if character_id and character_id in round1_rival_ids:
                round1_rival = round1_rivals[round1_rival_ids.index(character_id)]
            elif index < len(round1_rivals):
                round1_rival = round1_rivals[index]
            rival_totals.append(float(math.floor(round1_rival * multiplier + 1e-9)) + float(round2_rival))
        combined_rank = 1 + sum(total > combined for total in rival_totals)
        result.update(
            {
                'hif_round': 2,
                'hif_round2_score': float(effective_score),
                'hif_combined_score': float(combined),
                'hif_rival_combined_scores': rival_totals,
                'hif_combined_rank': int(combined_rank),
                'hif_prima_stella': bool(combined_rank == 1),
                'hif_star_before_round2': float(state.get('star_quality') or 0.0),
                'rank': int(combined_rank),
                'cleared': int(combined_rank) <= int(rank_threshold),
            }
        )
        return result

    def apply_accepted_result(self, result: dict[str, Any]) -> None:
        """把已接受的试验结果写回 HIF 状态（スター性获得、轮次记录、剧情事件）。"""

        state = self.runtime.state
        stage_type = str(result.get('stage_type') or '')
        if self.is_final and int(result.get('hif_round') or 0) == 2:
            state['hif_star_before_round2'] = float(result.get('hif_star_before_round2') or state.get('star_quality') or 0.0)
            state['hif_round2_started'] = True
        star_gain_base = int(result.get('hif_star_gain_base') or 0)
        if result.get('cleared'):
            state['produce_points'] += int(result.get('hif_audition_point_gain') or 0)
        if star_gain_base > 0 and (self.is_final or bool(result.get('cleared'))):
            self.gain_star(star_gain_base)
        if self.is_selection:
            scores = list(state.get('hif_selection_scores') or [])
            scores.append(float(result.get('exam_score') or 0.0))
            state['hif_selection_scores'] = scores
        if self.is_final:
            if int(result.get('hif_round') or 0) == 1:
                state['hif_round1_score'] = float(result.get('hif_round1_score') or 0.0)
                state['hif_round1_adjusted_score'] = float(result.get('hif_round1_adjusted_score') or 0.0)
                state['hif_round1_rival_scores'] = list(result.get('hif_round1_rival_scores') or [])
                state['hif_round1_rival_character_ids'] = list(result.get('hif_round1_rival_character_ids') or [])
            elif int(result.get('hif_round') or 0) == 2:
                state['hif_round2_score'] = float(result.get('hif_round2_score') or 0.0)
                state['hif_combined_score'] = float(result.get('hif_combined_score') or 0.0)
                state['hif_combined_rank'] = int(result.get('hif_combined_rank') or 0)
                state['hif_prima_stella'] = bool(result.get('hif_prima_stella'))
        if bool(result.get('cleared')):
            self.on_audition_cleared(stage_type)

    # ── 终局 ─────────────────────────────────────────────────

    def produce_result(self, *, cleared: bool) -> dict[str, Any]:
        """构造 HIF 终局摘要里的 `produce_result`。"""

        state = self.runtime.state
        params = (float(state.get('vocal') or 0.0), float(state.get('dance') or 0.0), float(state.get('visual') or 0.0))
        if self.is_final:
            star_before_round2 = float(state.get('hif_star_before_round2') or state.get('star_quality') or 0.0)
            if getattr(self.runtime, 'hif_ruleset_version', None):
                from gakumas_arena.produce.courses import final_rating
                detail = final_rating(params, state.get('star_quality', 0),
                    state.get('hif_round1_score', 0), state.get('hif_round2_score', 0))
            else:
                detail = calculate_hif_produce_rating(
                params=params,
                star_quality_before_round2=star_before_round2,
                round1_score=float(state.get('hif_round1_score') or 0.0),
                round2_score=float(state.get('hif_round2_score') or 0.0),
                star_gain_multiplier=1.0 + float(state.get('star_gain_rate') or 0.0),
                parameter_cap=float(self.runtime._parameter_growth_limit() or HIF_STAR_QUALITY_CAP),
            )
            return {
                'score': float(detail.get('rating') or 0.0),
                'rank': str(detail.get('rank') or 'F'),
                'parameter_total': float(detail.get('parameter_total') or 0.0),
                'fan_votes': 0.0,
                'star_quality': float(state.get('star_quality') or 0.0),
                'prima_stella': bool(state.get('hif_prima_stella')),
                'combined_score': float(state.get('hif_combined_score') or 0.0),
                'formula_source': detail.get('formula_source', 'hif_community_formula_v1'),
                'formula_detail': detail,
            }
        detail = calculate_hif_selection_rating(params=params, star_quality=float(state.get('star_quality') or 0.0))
        return {
            'score': float(detail.get('rating') or 0.0),
            'rank': str(detail.get('rank') or 'F'),
            'parameter_total': float(detail.get('parameter_total') or 0.0),
            'fan_votes': 0.0,
            'star_quality': float(state.get('star_quality') or 0.0),
            'selection_scores': [float(value) for value in state.get('hif_selection_scores') or []],
            'formula_source': 'hif_selection_partial_formula',
            'formula_detail': detail,
        }

    def ending_type(self, *, cleared: bool, final_rank: int | None) -> str:
        """HIF 结局类型。"""

        if not cleared:
            return 'failed'
        if self.is_selection:
            return 'hif_selection_clear'
        if bool(self.runtime.state.get('hif_prima_stella')):
            return 'hif_prima_stella'
        return 'hif_final_clear'
