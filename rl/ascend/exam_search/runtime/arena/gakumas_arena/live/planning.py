"""首个可联调绑定：真实课程奖励与咨询购买，复用引擎候选、合法性和编码。"""

from __future__ import annotations

import subprocess
from typing import Any

from gakumas_rl.idol_config import apply_card_customizations, build_idol_loadout
from gakumas_rl.repository.master_data import MasterDataRepository
from gakumas_rl.simulation.encoding import encoder_manifest, mask_planning_observation
from gakumas_rl.simulation.envs import GakumasPlanningEnv
from gakumas_rl.simulation.produce.runtime import ProduceActionCandidate

from .contracts import EntityRef, Observation, RunSetup
from .session import MissingFields, PreparedDecision, ProtocolError


class PlanningBackend:
    """支持 card_reward / consult；其他页面在有正确规则绑定前返回 Inspect。"""
    rules_revision = 'arena-rules/2'

    def __init__(self, repository: MasterDataRepository | None = None) -> None:
        """只装配数据，既不 reset 也不触发模拟随机事件。"""
        self.repository = repository or MasterDataRepository()
        self.masterdata_revision = subprocess.check_output(
            ['git', '-C', str(self.repository.assets_dir), 'rev-parse', 'HEAD'], text=True,
        ).strip()
        if getattr(self.repository, 'content_digest', None):
            self.masterdata_revision += ':content:' + self.repository.content_digest
        self.last_env: GakumasPlanningEnv | None = None

    def _card_row(self, entity: EntityRef) -> dict[str, Any]:
        """拒绝只按名称、加号或屏幕槽位解析卡变体。"""
        if entity.kind != 'card' or not entity.definition_id or entity.upgrade_count is None or entity.customize_ids is None:
            raise MissingFields(f'entities.{entity.instance_id}.definition_and_variant')
        row = self.repository.card_row_by_upgrade(entity.definition_id, entity.upgrade_count, fallback_to_canonical=False)
        if row is None:
            raise MissingFields(f'entities.{entity.instance_id}.catalog_mapping')
        row = apply_card_customizations(self.repository, row, entity.customize_ids)
        row['instance_id'] = entity.instance_id
        return row

    def prepare(self, setup: RunSetup, observation: Observation) -> PreparedDecision:
        """以当前绝对事实构建只供编码的模型视图，实际结果从下一观察消费。"""
        pending = observation.pending_decision
        if pending.kind not in {'card_reward', 'consult'}:
            raise MissingFields(f'arena.binding.{pending.kind}')
        if setup.masterdata_revision is None:
            raise MissingFields('run_setup.masterdata_revision')
        if setup.masterdata_revision != self.masterdata_revision:
            raise ProtocolError('masterdata revision mismatch')
        if setup.rules_revision != self.rules_revision:
            raise MissingFields('run_setup.rules_revision=arena-rules/2')
        if not setup.loadout.idol_card_id:
            raise MissingFields('run_setup.loadout.idol_card_id')
        deck = observation.inventories.get('deck')
        if deck is None or deck.coverage != 'complete':
            raise MissingFields('inventories.deck.complete')
        scenario = self.repository.build_scenario(setup.scenario_id)
        # 此处只取定义流派和静态卡效果，不执行 loadout 开局技能。
        loadout = build_idol_loadout(self.repository, scenario, setup.loadout.idol_card_id)
        env = GakumasPlanningEnv(self.repository, scenario, idol_loadout=loadout)
        rt = env.runtime
        rt.state = rt._base_state()
        rt.deck = [self._card_row(entity) for entity in deck.entities]
        rt.initial_deck_card_ids = set()
        rt.pre_audition_phase = pending.kind
        known = {'loadout.idol_card_id', 'inventory.deck'}
        for key, fact in observation.facts.items():
            if (fact.status == 'observed' and key in rt.state
                    and isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool)):
                rt.state[key] = fact.value
                known.add(key)
        drinks = observation.inventories.get('drinks')
        if drinks is not None and drinks.coverage == 'complete':
            for entity in drinks.entities:
                row = self.repository.produce_drinks.first(entity.definition_id or '')
                if entity.kind != 'drink' or row is None:
                    raise MissingFields(f'entities.{entity.instance_id}.catalog_mapping')
                rt.drinks.append({**row, 'instance_id': entity.instance_id})
            known.add('inventory.drinks')
        candidates = []
        for choice in pending.choices:
            kind = choice.action_type
            if kind not in self.repository.taxonomy.action_index:
                raise MissingFields(f'arena.action.{kind}')
            is_reward = kind in {'card_reward_pick_1', 'card_reward_pick_2', 'card_reward_pick_3'}
            is_card = is_reward or kind.startswith('shop_buy_card_')
            is_drink = kind.startswith('shop_buy_drink_')
            allowed = (is_reward or kind in {'card_reward_skip', 'card_reward_reroll'}) if pending.kind == 'card_reward' else (
                kind.startswith(('shop_buy_card_', 'shop_buy_drink_')) or kind in {'consult_finish', 'shop_reroll'}
            )
            if not allowed:
                raise MissingFields(f'arena.action.{kind}')
            if choice.ui_enabled is False:
                candidates.append(ProduceActionCandidate(
                    label=choice.label, action_type=kind, effect_types=[],
                    produce_effect_ids=[], available=False,
                ))
                continue
            required: set[str] = set()
            if kind.startswith('shop_buy_'):
                required.add('produce_points')
            if is_drink:
                required.update({'inventory.drinks', 'drink_limit_bonus'})
            if kind == 'card_reward_reroll':
                required.update({'card_reward_rerolls_used', 'card_select_reroll_count_bonus'})
            if kind == 'shop_reroll':
                required.update({'shop_rerolls_used', 'shop_reroll_count_bonus'})
            if required - known:
                raise MissingFields(*(f'facts.{key}' for key in sorted(required - known)))
            if is_card or is_drink:
                if len(choice.targets) != 1:
                    raise MissingFields(f'choices.{choice.choice_id}.one_target')
                entity = choice.targets[0]
                if is_card:
                    candidate = rt.choices.card_candidate(self._card_row(entity), kind)
                else:
                    row = self.repository.produce_drinks.first(entity.definition_id or '')
                    if entity.kind != 'drink' or row is None:
                        raise MissingFields(f'entities.{entity.instance_id}.catalog_mapping')
                    candidate = ProduceActionCandidate(
                        label=choice.label, action_type=kind, effect_types=[], produce_effect_ids=[],
                        resource_type='ProduceResourceType_ProduceDrink', resource_id=entity.definition_id,
                        **rt._candidate_drink_metadata(row),
                    )
                candidate.instance_id = entity.instance_id
                if kind.startswith('shop_buy_'):
                    price = choice.parameters.get('price')
                    if isinstance(price, bool) or not isinstance(price, (int, float)) or price < 0:
                        raise MissingFields(f'choices.{choice.choice_id}.parameters.price')
                    candidate.produce_point_delta = -float(price)
            else:
                if choice.targets:
                    raise ProtocolError(f'{kind} cannot have entity targets')
                candidate = ProduceActionCandidate(label=choice.label, action_type=kind, effect_types=[], produce_effect_ids=[])
            candidate.available = choice.ui_enabled is True
            candidates.append(candidate)
        rt.choices.external_candidates = candidates
        # 所有默认模型字段都被缺失掩码排除；完整隐藏牌序从未构造或提供给 policy。
        raw = env._build_observation()
        encoded = mask_planning_observation(env, raw, known)
        self.last_env = env
        return PreparedDecision(
            env=None, observation=encoded,
            info={'partial_observation': True, 'choice_ids': [choice.choice_id for choice in pending.choices]},
            choices=dict(enumerate(pending.choices)), encoder_manifest=encoder_manifest(env, observed=True),
        )
