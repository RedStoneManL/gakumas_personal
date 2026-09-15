"""Seeded rollouts of gakumas_rl environments with a policy, returning a structured result.

    >>> from gakumas_arena.sim import run_exam
    >>> r = run_exam("first_star", seed=0)              # random policy
    >>> r.score, r.turns, r.log[0]
    >>> run_exam("nia", seed=0, policy="heuristic")     # gakumas_rl's ProduceExamAutoEvaluation-prior + 1-ply lookahead

Policies: ``'random'`` (seeded uniform over legal slots), ``'heuristic'`` (gakumas_rl's built-in
exam / planning heuristic, which uses the official ``ProduceExamAutoEvaluation`` priors for exams),
``'end_turn'`` (always skip), or any callable ``policy(obs, info, env) -> int``.
"""
from __future__ import annotations

import dataclasses
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np

from gakumas_rl.interfaces import service as _service
from gakumas_rl.simulation.envs import GakumasExamEnv, GakumasPlanningEnv
from gakumas_rl.simulation.produce.runtime import ProduceRuntime
from gakumas_rl.training.reward_config import build_produce_reward_config

from ..env import AUTO, DEFAULT_IDOL, legal_actions, make_exam_env, make_produce_env, resolve_preset, resolve_scenario_id

__all__ = [
    "Policy",
    "RolloutResult",
    "run_exam",
    "run_produce",
    "random_policy",
    "end_turn_policy",
    "heuristic_exam_policy",
    "heuristic_produce_policy",
    "dump_version",
]

Policy = Callable[[dict[str, Any], dict[str, Any], Any], int]


@dataclass
class RolloutResult:
    """Outcome of one seeded rollout."""

    kind: str  # 'exam' | 'produce'
    scenario: str
    idol: str | None
    seed: int | None
    policy: str
    score: float
    total_reward: float
    steps: int
    turns: int
    terminated: bool
    truncated: bool
    stage_type: str | None = None
    summary: dict[str, Any] = field(default_factory=dict)  # final step info / produce final_summary
    log: list[dict[str, Any]] = field(default_factory=list)  # one entry per env step
    events: list[dict[str, Any]] = field(default_factory=list)  # ExamRuntime.event_log (exam only)
    data_version: dict[str, Any] = field(default_factory=dict)
    loadout: str | None = None  # preset name from gakumas_arena.loadouts, if one was used

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=_json_default, **kwargs)


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (set, tuple)):
        return list(value)
    return str(value)


def dump_version() -> dict[str, Any]:
    """Commit / date of the master-data dump the repository is reading (for result provenance)."""
    from gakumas_rl.repository.master_data import ASSETS_DIR

    info: dict[str, Any] = {"path": str(ASSETS_DIR)}
    try:
        info["commit"] = subprocess.check_output(
            ["git", "-C", str(ASSETS_DIR), "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        info["commit_date"] = subprocess.check_output(
            ["git", "-C", str(ASSETS_DIR), "log", "-1", "--format=%cI"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    meta = Path(ASSETS_DIR).parent / "masterdata_json" / "_meta.json"
    if meta.exists():
        try:
            info["cache_meta"] = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return info


# ------------------------------------------------------------------------------------------
# policies
# ------------------------------------------------------------------------------------------
def random_policy(seed: int | None = None) -> Policy:
    rng = np.random.default_rng(seed)

    def act(obs: dict[str, Any], info: dict[str, Any], env: Any) -> int:
        return int(rng.choice(legal_actions(obs)))

    return act


def end_turn_policy(obs: dict[str, Any], info: dict[str, Any], env: Any) -> int:
    """Always pick the last legal slot (end_turn for exam envs)."""
    return int(legal_actions(obs)[-1])


def heuristic_exam_policy(env: GakumasExamEnv, seed: int | None = None) -> Policy:
    """gakumas_rl's built-in exam heuristic (``ProduceRuntime._choose_exam_action``): official
    ``ProduceExamAutoEvaluation`` priors + one-step lookahead, mapped back to env slots."""
    planner = ProduceRuntime(
        env.repository,
        env.scenario,
        seed=seed,
        idol_loadout=env.current_loadout,
        produce_reward_config=build_produce_reward_config(),
    )

    def act(obs: dict[str, Any], info: dict[str, Any], env: GakumasExamEnv) -> int:
        chosen = planner._choose_exam_action(env.runtime)
        legal = legal_actions(obs)
        if chosen is not None:
            for index in legal:
                view = env._candidates[int(index)]
                if view.kind != chosen.kind:
                    continue
                if chosen.kind == "card" and int(view.payload.get("uid", -1)) != int(chosen.payload["uid"]):
                    continue
                if chosen.kind == "drink" and int(view.payload.get("index", -1)) != int(chosen.payload["index"]):
                    continue
                return int(index)
        return int(legal[-1])

    return act


def heuristic_produce_policy(obs: dict[str, Any], info: dict[str, Any], env: GakumasPlanningEnv) -> int:
    """gakumas_rl's planning heuristic (``interfaces.service._choose_planning_action``)."""
    runtime_index = _service._choose_planning_action(env.runtime)
    legal = legal_actions(obs)
    if runtime_index is not None:
        for index in legal:
            if int(env._candidates[int(index)].payload.get("index", -1)) == int(runtime_index):
                return int(index)
    return int(legal[0])


def _resolve_policy(policy: str | Policy, env: Any, seed: int | None) -> tuple[str, Policy]:
    if callable(policy):
        return getattr(policy, "__name__", "custom"), policy
    name = str(policy)
    if name == "random":
        return name, random_policy(seed)
    if name == "end_turn":
        return name, end_turn_policy
    if name == "heuristic":
        if isinstance(env, GakumasExamEnv):
            return name, heuristic_exam_policy(env, seed)
        return name, heuristic_produce_policy
    raise ValueError(f"unknown policy {policy!r}; use 'random' | 'heuristic' | 'end_turn' | callable")


# ------------------------------------------------------------------------------------------
# rollouts
# ------------------------------------------------------------------------------------------
def _rollout(env: Any, policy: Policy, seed: int | None, max_steps: int) -> tuple[list[dict[str, Any]], float, dict[str, Any], bool, bool]:
    obs, info = env.reset(seed=seed)
    log: list[dict[str, Any]] = []
    total = 0.0
    terminated = truncated = False
    for step in range(max_steps):
        action = int(policy(obs, info, env))
        labels = info.get("action_labels") or [view.label for view in env._candidates]
        label = labels[action] if action < len(labels) else str(action)
        obs, reward, terminated, truncated, info = env.step(action)
        total += float(reward)
        entry = {"step": step, "action": action, "label": label, "reward": float(reward)}
        for key in ("kind", "score", "turn", "stamina", "stance", "action_type", "step_index", "invalid_action"):
            if key in info:
                entry[key] = info[key]
        log.append(entry)
        if terminated or truncated:
            break
    else:
        truncated = True
    return log, total, info, terminated, truncated


def run_exam(
    scenario: str = "first_star",
    idol: str | None = AUTO,
    seed: int | None = 0,
    policy: str | Policy = "random",
    *,
    loadout: Any = None,
    stage_type: str | None = None,
    max_steps: int = 5000,
    env: GakumasExamEnv | None = None,
    **env_kwargs: Any,
) -> RolloutResult:
    """Run one exam to completion with ``policy`` and return score + per-step log.

    Same ``seed`` (and same dump / loadout) -> identical result.  Pass ``env`` to reuse an
    already-built environment (it is reset with ``seed``)."""
    env = env or make_exam_env(scenario, idol, loadout, seed=seed, stage_type=stage_type, **env_kwargs)
    preset = resolve_preset(scenario, idol, loadout)
    policy_name, act = _resolve_policy(policy, env, seed)
    log, total, info, terminated, truncated = _rollout(env, act, seed, max_steps)
    runtime = env.runtime
    return RolloutResult(
        kind="exam",
        scenario=env.scenario.scenario_id,
        idol=env.current_loadout.idol_card_id if env.current_loadout is not None else None,
        seed=seed,
        policy=policy_name,
        score=float(runtime.score),
        total_reward=total,
        steps=len(log),
        turns=int(runtime.turn),
        terminated=terminated,
        truncated=truncated,
        stage_type=env.current_stage_type,
        summary={k: v for k, v in info.items() if k != "action_labels"},
        log=log,
        events=[{"turn": e.turn, "type": e.event_type, **e.detail} for e in runtime.event_log],
        data_version=dump_version(),
        loadout=preset.name if preset is not None else None,
    )


def run_produce(
    scenario: str = "first_star",
    idol: str | None = AUTO,
    seed: int | None = 0,
    policy: str | Policy = "random",
    *,
    loadout: Any = None,
    max_steps: int = 5000,
    env: GakumasPlanningEnv | None = None,
    **env_kwargs: Any,
) -> RolloutResult:
    """Run a whole produce (planning) episode with ``policy``; exams inside are auto-played.

    ``score`` is the final audition score; ``summary`` carries gakumas_rl's ``final_summary``
    (rank, produce_result rating, audition history) when the run completed.  ``loadout`` may be a
    preset name (``gakumas_arena.loadouts.list_loadouts()``); H.I.F defaults to ``hif_sense_default``."""
    env = env or make_produce_env(scenario, idol, loadout, seed=seed, **env_kwargs)
    preset = resolve_preset(scenario, idol, loadout)
    policy_name, act = _resolve_policy(policy, env, seed)
    log, total, info, terminated, truncated = _rollout(env, act, seed, max_steps)
    runtime = env.runtime
    final = dict(getattr(runtime, "final_summary", None) or info.get("final_summary") or {})
    state = dict(getattr(runtime, "state", {}) or {})
    summary = {k: v for k, v in info.items() if k != "action_labels"}
    summary["final_summary"] = final
    summary["state"] = {k: state[k] for k in ("vocal", "dance", "visual", "stamina", "max_stamina", "fan_votes") if k in state}
    return RolloutResult(
        kind="produce",
        scenario=env.scenario.scenario_id,
        idol=env.current_loadout.idol_card_id if env.current_loadout is not None else None,
        seed=seed,
        policy=policy_name,
        score=float(final.get("final_score") or state.get("last_exam_score") or 0.0),
        total_reward=total,
        steps=len(log),
        turns=int(state.get("step_index", len(log)) or len(log)),
        terminated=terminated,
        truncated=truncated,
        summary=summary,
        log=log,
        data_version=dump_version(),
        loadout=preset.name if preset is not None else None,
    )
