"""Thin adapters over gakumas_rl's Gymnasium environments.

``make_exam_env`` returns a ``gakumas_rl.simulation.envs.GakumasExamEnv`` (one exam / lesson:
play cards, use drinks, end turn) and ``make_produce_env`` a ``GakumasPlanningEnv`` (the whole
produce run: weekly actions, shop, auditions).  Both are configured from a scenario id, an idol
card, a loadout and a seed; everything else is gakumas_rl's own machinery
(``gakumas_rl/simulation/envs.py``, ``gakumas_rl/interfaces/service.py``).

Observation / action contract (unchanged from gakumas_rl):
    obs = {"global": float32[global_dim], "action_features": float32[max_actions, feat_dim],
           "action_mask": float32[max_actions]}      action = Discrete(max_actions) slot index
Use ``legal_actions(obs)`` to get the currently valid slot indices.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

import numpy as np

from gakumas_rl.interfaces import service as _service
from gakumas_rl.interfaces.service import LoadoutConfig
from gakumas_rl.loadout import IdolLoadout
from gakumas_rl.repository.master_data import MasterDataRepository, ScenarioSpec
from gakumas_rl.simulation.envs import GakumasExamEnv, GakumasPlanningEnv

from ..loadouts import LoadoutPreset, apply_preset_to_scenario, default_loadout_name, get_loadout

__all__ = [
    "AUTO",
    "DEFAULT_IDOL",
    "LoadoutPreset",
    "SCENARIOS",
    "STAGE_TYPES",
    "LoadoutConfig",
    "IdolLoadout",
    "GakumasExamEnv",
    "GakumasPlanningEnv",
    "get_repository",
    "resolve_scenario_id",
    "get_scenario",
    "make_loadout_config",
    "resolve_preset",
    "build_loadout",
    "make_exam_env",
    "make_produce_env",
    "legal_actions",
]

# 剧本别名映射到主数据 Produce.id；HIF 的選抜和本戦分别由 HifRuntimeSupport 实现。
SCENARIOS: dict[str, str] = {
    "first_star": "produce-001",
    "hajime": "produce-001",
    "初": "produce-001",
    "first_star_regular": "produce-001",
    "first_star_pro": "produce-002",
    "first_star_master": "produce-003",
    "first_star_legend": "produce-006",
    "hajime_legend": "produce-006",
    "nia": "produce-005",
    "nia_pro": "produce-004",
    "nia_master": "produce-005",
    "hif": "produce-007",
    "hif_selection": "produce-007",
    "hif_final": "produce-008",
}

STAGE_TYPES: dict[str, str] = {
    "mid1": "ProduceStepType_AuditionMid1",
    "mid": "ProduceStepType_AuditionMid1",
    "mid2": "ProduceStepType_AuditionMid2",
    "final": "ProduceStepType_AuditionFinal",
}

#: 有村麻央 R (``amao``) — the stable fallback idol card also used by the upstream test-suite fixtures.
#: Scenarios with a preset in ``gakumas_arena.loadouts.DEFAULT_PRESET_BY_SCENARIO`` (H.I.F) use that
#: preset's idol instead when ``idol`` is left at ``AUTO``.
DEFAULT_IDOL = "i_card-amao-1-000"

#: Sentinel for ``idol``: "use the scenario's default preset idol if one exists, else DEFAULT_IDOL".
AUTO = "auto"


def get_repository() -> MasterDataRepository:
    """Process-wide cached ``MasterDataRepository`` (reads data/raw/gakumasu-diff)."""
    return _service.get_repository()


def resolve_scenario_id(scenario: str) -> str:
    key = str(scenario).strip()
    if key in SCENARIOS:
        return SCENARIOS[key]
    return _service.SCENARIO_ALIASES.get(key, key)


def get_scenario(scenario: str) -> ScenarioSpec:
    return _service.get_scenario(resolve_scenario_id(scenario))


def resolve_stage_type(stage_type: str | None) -> str | None:
    if stage_type is None:
        return None
    return STAGE_TYPES.get(str(stage_type).strip().lower(), str(stage_type))


def resolve_preset(
    scenario: str | None,
    idol: str | None,
    loadout: Any,
) -> LoadoutPreset | None:
    """Which named preset (``gakumas_arena.loadouts``) applies, if any.

    ``loadout`` may be a preset name (``"hif_sense_default"``) or a ``LoadoutPreset``; with
    ``loadout=None`` and ``idol=AUTO`` the scenario's default preset (H.I.F only) is used.
    """
    if isinstance(loadout, LoadoutPreset):
        return loadout
    if isinstance(loadout, str):
        return get_loadout(loadout)
    if loadout is None and idol == AUTO and scenario is not None:
        name = default_loadout_name(resolve_scenario_id(scenario))
        return get_loadout(name) if name else None
    return None


def make_loadout_config(
    idol: str | None = AUTO,
    loadout: LoadoutConfig | IdolLoadout | LoadoutPreset | dict[str, Any] | str | None = None,
    scenario: str | None = None,
    **overrides: Any,
) -> LoadoutConfig:
    """Normalise ``loadout`` (None / preset name / LoadoutPreset / dict / LoadoutConfig / IdolLoadout)
    into a ``LoadoutConfig``.  ``idol=AUTO`` resolves to the preset's idol (or ``DEFAULT_IDOL``);
    an explicit ``idol`` overrides the preset's idol card."""
    preset = resolve_preset(scenario, idol, loadout)
    if preset is not None:
        if idol and idol != AUTO and idol != preset.idol_card_id:
            # 显式偶像覆盖：ポテンシャル / プリマステラ 上限按覆盖后的偶像卡查主数据
            cfg = preset.to_loadout_config(idol_card_id=idol)
        else:
            cfg = preset.to_loadout_config()
        return replace(cfg, **overrides) if overrides else cfg
    if idol == AUTO:
        idol = DEFAULT_IDOL
    if isinstance(loadout, LoadoutConfig):
        cfg = loadout
    elif isinstance(loadout, IdolLoadout):
        cfg = LoadoutConfig(
            idol_card_id=loadout.idol_card_id,
            producer_level=int(loadout.producer_level),
            idol_rank=int(loadout.idol_rank),
            dearness_level=int(loadout.dearness_level),
            use_after_item=bool(loadout.use_after_item),
            exam_score_bonus_multiplier=getattr(loadout, "exam_score_bonus_multiplier", None),
            support_card_levels=tuple(card.support_card_level for card in loadout.support_cards),
            auto_support_cards=False,
            support_card_ids=tuple(
                str(card.support_card_id) for card in getattr(loadout, "support_cards", ()) or ()
            ),
            challenge_item_ids=tuple(getattr(loadout, "extra_produce_item_ids", ()) or ()),
            potential_level=int(getattr(loadout, "potential_level", 0) or 0),
            prima_stella_level=int(getattr(loadout, "prima_stella_level", 0) or 0),
            memories=tuple(getattr(loadout, "memories", ()) or ()),
        )
    elif isinstance(loadout, dict):
        cfg = LoadoutConfig(**{"idol_card_id": idol or "", **loadout})
    elif loadout is None:
        cfg = LoadoutConfig(idol_card_id=idol or "")
    else:
        raise TypeError(f"unsupported loadout spec: {type(loadout).__name__}")
    if overrides:
        cfg = replace(cfg, **overrides)
    if idol and not cfg.idol_card_id:
        cfg = replace(cfg, idol_card_id=idol)
    return cfg


def build_loadout(
    scenario: str = "first_star",
    idol: str | None = AUTO,
    loadout: LoadoutConfig | IdolLoadout | LoadoutPreset | dict[str, Any] | str | None = None,
    **overrides: Any,
) -> IdolLoadout | None:
    """Resolve an ``IdolLoadout`` (stats, deck archetype, P-item, support cards) for a scenario."""
    if isinstance(loadout, IdolLoadout) and not overrides:
        return loadout
    cfg = make_loadout_config(idol, loadout, scenario=scenario, **overrides)
    return _service.build_loadout_from_config(resolve_scenario_id(scenario), cfg)


def _base_loadout_config(scenario_id: str, cfg: LoadoutConfig) -> dict[str, Any]:
    """The per-episode loadout context gakumas_rl envs re-resolve on every ``reset``.

    Mirrors ``gakumas_rl.interfaces.service.build_env_from_config``; without it the env would
    rebuild the loadout with library defaults (idol_rank=0, ...) instead of ours.
    """
    return {
        "scenario": scenario_id,
        "idol_card_id": cfg.idol_card_id,
        "idol_card_ids": (cfg.idol_card_id,) if cfg.idol_card_id else (),
        "producer_level": cfg.producer_level,
        "idol_rank": cfg.idol_rank,
        "dearness_level": cfg.dearness_level,
        "use_after_item": cfg.use_after_item,
        "produce_card_conversion_after_ids": cfg.produce_card_conversion_after_ids,
        "exam_score_bonus_multiplier": cfg.exam_score_bonus_multiplier,
        "fan_votes": cfg.fan_votes,
        "auto_support_cards": cfg.auto_support_cards,
        "support_card_ids": cfg.support_card_ids,
        "support_card_level": cfg.support_card_level,
        "support_card_levels": cfg.support_card_levels,
        "challenge_item_ids": cfg.challenge_item_ids,
        "potential_level": cfg.potential_level,
        "prima_stella_level": cfg.prima_stella_level,
        "memories": tuple(cfg.memories or ()),
    }


def make_exam_env(
    scenario: str = "first_star",
    idol: str | None = AUTO,
    loadout: LoadoutConfig | IdolLoadout | LoadoutPreset | dict[str, Any] | str | None = None,
    seed: int | None = None,
    stage_type: str | None = None,
    *,
    battle_kind: str = "exam",
    reward_mode: str = "score",
    include_action_labels: bool = True,
    **env_kwargs: Any,
) -> GakumasExamEnv:
    """Build a ``GakumasExamEnv`` for one exam (or lesson with ``battle_kind='lesson'``).

    ``stage_type``: ``'mid1' | 'mid2' | 'final'`` or a raw ``ProduceStepType_*`` (default: the
    scenario's first audition).  ``reward_mode``: ``'score'`` (dense score delta) or ``'clear'``.
    Extra keyword arguments go straight to ``GakumasExamEnv``.
    """
    scenario_id = resolve_scenario_id(scenario)
    spec = apply_preset_to_scenario(_service.get_scenario(scenario_id), resolve_preset(scenario_id, idol, loadout))
    cfg = make_loadout_config(idol, loadout, scenario=scenario_id)
    idol_loadout = build_loadout(scenario_id, cfg.idol_card_id or None, cfg)
    return GakumasExamEnv(
        get_repository(),
        spec,
        battle_kind=battle_kind,
        stage_type=resolve_stage_type(stage_type),
        seed=seed,
        idol_loadout=idol_loadout,
        base_loadout_config=_base_loadout_config(scenario_id, cfg),
        exam_reward_mode=reward_mode,
        include_action_labels_in_step_info=include_action_labels,
        **env_kwargs,
    )


def make_produce_env(
    scenario: str = "first_star",
    idol: str | None = AUTO,
    loadout: LoadoutConfig | IdolLoadout | LoadoutPreset | dict[str, Any] | str | None = None,
    seed: int | None = None,
    *,
    include_action_labels: bool = True,
    **env_kwargs: Any,
) -> GakumasPlanningEnv:
    """Build a ``GakumasPlanningEnv`` for a whole produce run (exams inside are auto-played by
    gakumas_rl's heuristic unless ``exam_action_selectors`` is given).

    ``loadout`` accepts a preset name from ``gakumas_arena.loadouts`` (e.g. ``"hif_sense_default"``);
    for H.I.F scenarios the default preset is used when ``loadout`` is None and ``idol`` is ``AUTO``.
    Preset scenario overrides (H.I.F growth panel levels) are applied to the ``ScenarioSpec``."""
    scenario_id = resolve_scenario_id(scenario)
    spec = apply_preset_to_scenario(_service.get_scenario(scenario_id), resolve_preset(scenario_id, idol, loadout))
    cfg = make_loadout_config(idol, loadout, scenario=scenario_id)
    idol_loadout = build_loadout(scenario_id, cfg.idol_card_id or None, cfg)
    return GakumasPlanningEnv(
        get_repository(),
        spec,
        seed=seed,
        idol_loadout=idol_loadout,
        base_loadout_config=_base_loadout_config(scenario_id, cfg),
        include_action_labels_in_step_info=include_action_labels,
        force_lowest_audition_route=bool(cfg.force_lowest_audition_route),
        **env_kwargs,
    )


def legal_actions(obs: dict[str, Any]) -> np.ndarray:
    """Indices of currently valid action slots."""
    return np.flatnonzero(np.asarray(obs["action_mask"]) > 0.5)
