"""效果器访问运行时的显式接口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExamEffectContext:
    """效果器专用上下文，集中封装运行时内部操作。"""

    runtime: Any

    @property
    def resources(self):
        return self.runtime.resources

    @property
    def total_counters(self):
        return self.runtime.total_counters

    @property
    def turn_counters(self):
        return self.runtime.turn_counters

    @property
    def active_enchants(self):
        return self.runtime.active_enchants

    @property
    def forbidden_card_search_ids(self):
        return self.runtime.forbidden_card_search_ids

    @property
    def current_turn_color(self) -> str:
        return self.runtime.current_turn_color

    @property
    def score_per_color(self):
        return self.runtime.score_per_color

    @property
    def hand(self):
        return self.runtime.hand

    @property
    def grave(self):
        return self.runtime.grave

    @property
    def max_stamina(self) -> float:
        return self.runtime.max_stamina

    @property
    def stamina(self) -> float:
        return self.runtime.stamina

    @stamina.setter
    def stamina(self, value: float) -> None:
        self.runtime.stamina = value

    @property
    def score(self) -> float:
        return self.runtime.score

    @score.setter
    def score(self, value: float) -> None:
        self.runtime.score = value

    @property
    def extra_turns(self) -> int:
        return self.runtime.extra_turns

    @extra_turns.setter
    def extra_turns(self, value: int) -> None:
        self.runtime.extra_turns = value

    @property
    def stance_locked(self) -> bool:
        return self.runtime.stance_locked

    @stance_locked.setter
    def stance_locked(self, value: bool) -> None:
        self.runtime.stance_locked = value

    @property
    def start_turn_draw_penalty(self) -> int:
        return self.runtime.start_turn_draw_penalty

    @start_turn_draw_penalty.setter
    def start_turn_draw_penalty(self, value: int) -> None:
        self.runtime.start_turn_draw_penalty = value

    def raw_value(self, effect: dict[str, Any]) -> float:
        return self.runtime.raw_effect_value(effect)

    def direct_value(self, effect: dict[str, Any]) -> float:
        return self.runtime.direct_effect_value(effect)

    def ratio_value(self, effect: dict[str, Any]) -> float:
        return self.runtime.ratio_effect_value(effect)

    def count_value(self, effect: dict[str, Any]) -> float:
        return self.runtime.count_effect_value(effect)

    def positive_count(self, value: float) -> int:
        return self.runtime.positive_count(value)

    def ceil_positive(self, value: float) -> float:
        return self.runtime.ceil_positive(value)

    def compose_referenced_gain(self, *, base: float, referenced: float) -> float:
        return self.runtime.compose_referenced_gain(base=base, referenced=referenced)

    def search_count(self, search_id: str) -> int:
        return self.runtime.search_card_count(search_id)

    def adjust_direct_gain(self, value: float, *, add_grow_type: str = '', reduce_grow_type: str = '') -> float:
        return self.runtime.adjust_direct_gain(value, add_grow_type=add_grow_type, reduce_grow_type=reduce_grow_type)

    def current_card_grow_total(self, grow_effect_type: str) -> float:
        return self.runtime.current_card_grow_total(grow_effect_type)

    def current_card_ratio_bonus(self, grow_effect_type: str) -> float:
        return self.runtime.current_card_ratio_bonus(grow_effect_type)

    def parameter_buff_gain_value(self, effect: dict[str, Any]) -> float:
        return self.runtime.parameter_buff_gain_value(effect)

    def dispatch_status_change(self, delta: float, effect_types: list[str], *, origin: str) -> None:
        self.runtime.dispatch_status_change(delta, effect_types, origin=origin)

    def status_change_origin(self, source: str) -> str:
        return self.runtime._status_change_origin(source)

    def add_resource(self, key: str, delta: float) -> None:
        # Reacquiring an expired stack is a fresh lifetime, even if it existed at turn start.
        if key in ('review', 'parameter_buff') and self.resources[key] <= 0 < delta:
            self.runtime._resource_turn_start_snapshot[key] = False
        self.resources[key] += delta

    def consume_anti_debuff(self, effect_type: str) -> bool:
        return self.runtime.consume_anti_debuff(effect_type)

    def register_timed_effect(self, effect: dict[str, Any], source: str) -> None:
        self.runtime.register_timed_effect(effect, source)

    def apply_status_enchant(self, effect: dict[str, Any], source: str) -> None:
        self.runtime.apply_status_enchant(effect, source)

    def schedule_effect(self, effect: dict[str, Any], source: str = 'other') -> None:
        self.runtime.schedule_effect(effect, source)

    def add_grow_effect(self, effect: dict[str, Any]) -> None:
        self.runtime.add_grow_effect(effect)

    def apply_card_operation(self, effect: dict[str, Any]) -> None:
        self.runtime.apply_card_operation(effect)

    def spend_stamina(self, value: float, *, phase_type: str, status_change_origin: str, force_value: float = 0.0) -> None:
        self.runtime.spend_stamina(value, phase_type=phase_type, status_change_origin=status_change_origin, force_value=force_value)

    def has_timed_effect(self, effect_type: str) -> bool:
        return self.runtime.has_timed_effect(effect_type)

    @property
    def scoring_rules(self):
        return self.runtime.scoring_rules

    def gain_block(self, delta: float, *, effect_type: str, status_change_origin: str) -> None:
        self.runtime.gain_block(delta, effect_type=effect_type, status_change_origin=status_change_origin)

    def consume_parameter_buff_multiple(self, value: float) -> None:
        self.runtime.consume_parameter_buff_multiple(value)

    def discard_hand(self) -> None:
        self.runtime.discard_hand()

    def draw(self, count: int) -> None:
        self.runtime.draw(count)

    def enter_concentration(self, level: int) -> None:
        self.runtime.enter_concentration(level)

    def enter_preservation(self, level: int) -> None:
        self.runtime.enter_preservation(level)

    def enter_full_power(self) -> None:
        self.runtime.enter_full_power()

    def reset_stance(self) -> None:
        self.runtime.reset_stance()

    def clear_negative_effects(self, kinds: int | None = None) -> None:
        self.runtime.clear_negative_effects(kinds)

    def sync_forbidden_search_resources(self) -> None:
        self.runtime.sync_forbidden_search_resources()

    def score_gain(self, value: float) -> float:
        return self.runtime.score_gain(value)

    def resolve_lesson_effect_value(self, effect: dict[str, Any], *, from_card: bool = False) -> float:
        return self.runtime.resolve_lesson_effect_value(effect, from_card=from_card)

    def update_clear_state_after_score_change(self) -> None:
        self.runtime.update_clear_state_after_score_change()

    def focus_score_contribution(self) -> float:
        """Strength-adjusted concentration for ordinary and multiplied references."""
        return self.runtime._focus_score_contribution()

    def apply_score_value_modifiers(self, value: float) -> float:
        return self.runtime.apply_score_value_modifiers(value)

    # ---- 以下为 H.I.F 新增效果类型（再演 / 强制使用 / 指针强化 等）所需的运行时访问接口 ----

    @property
    def exam_setting(self) -> dict[str, Any]:
        return self.runtime.exam_setting

    @property
    def stance(self) -> str:
        return self.runtime.stance

    @property
    def stance_level(self) -> int:
        return self.runtime.stance_level

    @property
    def turn(self) -> int:
        return self.runtime.turn

    @property
    def terminated(self) -> bool:
        return bool(self.runtime.terminated)

    @property
    def active_effects(self):
        return self.runtime.active_effects

    @property
    def current_card(self):
        """当前正在结算出牌效果的卡；不在出牌流程中时为 None。"""

        return self.runtime.current_card

    @property
    def resolving_enchant_card(self):
        """正在发动的绑定型附魔（再演）所绑定的卡；不在附魔结算中时为 None。"""

        return getattr(self.runtime, 'resolving_enchant_card', None)

    def exam_status_enchant_row(self, enchant_id: str) -> dict[str, Any] | None:
        """按 id 读取 ProduceExamStatusEnchant 主数据行。"""

        return self.runtime.repository.exam_status_enchant_map.get(str(enchant_id or ''))

    def gain_enthusiastic(self, amount: float) -> float:
        """按热意修饰结算并增加热意，返回实际增量。"""

        return self.runtime._gain_enthusiastic(amount)

    def dispatch_interval_phase(
        self,
        phase_type: str,
        counter_value: int,
        acting_card: Any | None = None,
        effect_types: list[str] | None = None,
    ) -> None:
        """按主数据里出现过的间隔值分发间隔型 phase；可附带触发器 effectTypes 匹配用的效果类型。"""

        if counter_value <= 0:
            return
        runtime = self.runtime
        for interval in runtime.repository.interval_phase_values.get(phase_type, ()):
            if counter_value % interval != 0:
                continue
            runtime._dispatch_phase(phase_type, phase_value=interval, acting_card=acting_card, effect_types=effect_types or [])
            if runtime.terminated:
                return

    def search_cards(
        self,
        search_id: str,
        *,
        acting_card: Any | None = None,
        target_card: Any | None = None,
        limit_count: int | None = None,
        prefer_high_value: bool = False,
    ):
        """按 ProduceCardSearch 检索运行时卡，允许指定行动卡/目标卡以解析 `isSelf` 与 `Target` 区域。"""

        return self.runtime._search_cards(
            search_id,
            acting_card=acting_card,
            target_card=target_card,
            limit_count=limit_count,
            prefer_high_value=prefer_high_value,
        )

    def effect_pick_limit(self, effect: dict[str, Any]) -> int | None:
        """读取效果行的 pickCountMax/pickCountMin。"""

        return self.runtime._effect_pick_limit(effect)

    def rank_card_selection_pool(self, pool: list[Any]) -> list[Any]:
        """把候选卡按结构价值从高到低排序（复用运行时的自动选卡评分）。"""

        return self.runtime._rank_card_selection_pool(list(pool))

    def random_choice(self, pool: list[Any], count: int) -> list[Any]:
        """用运行时的随机源从候选里无放回抽取 count 张。"""

        if not pool or count <= 0:
            return []
        count = min(count, len(pool))
        indices = self.runtime.np_random.choice(len(pool), size=count, replace=False)
        return [pool[int(index)] for index in list(indices)]

    def card_cost_affordable(self, card: Any) -> bool:
        """判断当前体力/元气/资源是否足以支付这张卡的费用（不检查出牌窗口与禁卡）。"""

        runtime = self.runtime
        cost_stamina, cost_force = runtime._card_stamina_components(card)
        if runtime.stamina < cost_force:
            return False
        if runtime.stamina + runtime.resources['block'] < cost_stamina + cost_force:
            return False
        for resource_key, amount in runtime._card_resource_costs(card).items():
            if runtime.resources[resource_key] < amount:
                return False
        return True

    def force_play_card(self, card: Any, *, pay_cost: bool, source: str = 'effect') -> None:
        """Prepare an actual card use at the current effect-group boundary (R09)."""
        from ..resolution import prepare_play
        prepare_play(self.runtime, card, pay_cost=pay_cost, source=source)

    def has_bound_enchant(self, enchant_id: str, bound_card_uid: int) -> bool:
        """R08: remember lifetime registration even after the active enchant expires."""

        return (int(bound_card_uid), str(enchant_id)) in self.runtime.resolution.encore_registered or any(
            item.enchant_id == str(enchant_id) and item.bound_card_uid == int(bound_card_uid)
            for item in self.runtime.active_enchants
        )

    def register_bound_enchant(
        self,
        enchant_row: dict[str, Any],
        *,
        bound_card: Any,
        remaining_turns: int | None,
        remaining_count: int | None,
        once_per_turn: bool,
        source: str,
    ) -> None:
        """挂载一个绑定到具体运行时卡的状态附魔（再演）。"""

        from ..runtime import TriggeredEnchant

        runtime = self.runtime
        runtime.resolution.encore_registered.add((int(bound_card.uid), str(enchant_row.get('id'))))
        runtime.active_enchants.append(
            TriggeredEnchant(
                uid=runtime._next_uid(),
                enchant_id=str(enchant_row.get('id')),
                trigger_id=str(enchant_row.get('produceExamTriggerId') or ''),
                effect_ids=[str(value) for value in enchant_row.get('produceExamEffectIds', []) if value],
                remaining_turns=remaining_turns,
                remaining_count=remaining_count,
                source=source,
                source_identity=f'{source}:{bound_card.uid}',
                applied_turn=runtime.turn,
                bound_card_uid=int(bound_card.uid),
                once_per_turn=bool(once_per_turn),
            )
        )
