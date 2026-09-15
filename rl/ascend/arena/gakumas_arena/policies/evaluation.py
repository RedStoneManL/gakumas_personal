"""批量评估：固定种子跑 N 局，输出逐局记录 + 汇总统计（mean / median / p10 / p90）。

被 ``scripts/eval_exam.py`` 与 ``scripts/eval_produce.py`` 调用，也可直接 import：

    >>> from gakumas_arena.policies.evaluation import evaluate_exam, summarize
    >>> rows = evaluate_exam("初", policy="search", seeds=range(10), stage="mid1")
    >>> summarize([r["score"] for r in rows])
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

from ..env import DEFAULT_IDOL, make_exam_env, make_produce_env
from ..sim import RolloutResult, run_exam, run_produce
from .base import Policy
from .basic import HeuristicPolicy, RandomPolicy
from .search import SearchPolicy

POLICY_NAMES = ("random", "heuristic", "search")

#: 培育中会触发考试的 step type；``exam_policy`` 会按这些 key 注册为 ``exam_action_selectors``
AUDITION_STAGE_TYPES = (
    "ProduceStepType_AuditionMid1",
    "ProduceStepType_AuditionMid2",
    "ProduceStepType_AuditionFinal",
)

EXAM_COLUMNS = ("seed", "policy", "score", "passed", "rank", "turns", "steps", "wall_s")
PRODUCE_COLUMNS = (
    "seed", "label", "policy", "exam_policy", "rating", "rank", "final_score", "ending_type",
    "route_clear", "auditions", "auditions_passed", "auditions_total",
    "vocal", "dance", "visual", "stamina", "steps", "wall_s",
)


# ----------------------------------------------------------------------------- 工厂
def make_policy(name: str, seed: int | None = None, *, depth: int = 2, samples: int = 2, **kwargs: Any) -> Policy:
    """按名字构造策略：``random`` / ``heuristic`` / ``search``（可带 ``depth`` / ``samples``）。

    也接受 ``search:d3k2`` 这种简写覆盖深度与采样数。
    """
    key = str(name).strip().lower()
    if key == "random":
        return RandomPolicy(seed)
    if key == "heuristic":
        return HeuristicPolicy(seed)
    if key.startswith("search"):
        spec = key.split(":", 1)[1] if ":" in key else ""
        if spec:
            import re

            m = re.fullmatch(r"d(\d+)k(\d+)", spec)
            if not m:
                raise ValueError(f"bad search spec {name!r}; use search:d<depth>k<samples>")
            depth, samples = int(m.group(1)), int(m.group(2))
        return SearchPolicy(depth=depth, samples=samples, seed=seed, **kwargs)
    raise ValueError(f"unknown policy {name!r}; choose from {POLICY_NAMES}")


def parse_loadout(spec: str | None) -> dict[str, Any] | str | None:
    """``--loadout``：预设名（``gakumas_arena.loadouts.list_loadouts()``）、JSON 字符串，或 .json / .yaml 文件路径；
    文件/JSON 内容是 ``LoadoutConfig`` 的字段字典。"""
    if not spec:
        return None
    text = spec.strip()
    if text.startswith("{"):
        return dict(json.loads(text))
    # 预设名（gakumas_arena.loadouts，如 hif_sense_default）直接透传给 make_produce_env
    from ..loadouts import list_loadouts

    if text in list_loadouts():
        return text
    path = Path(text)
    if not path.exists():
        raise FileNotFoundError(f"loadout file not found: {path}")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        return dict(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    return dict(json.loads(path.read_text(encoding="utf-8")))


def resolve_seeds(seeds: int | Iterable[int], start: int = 0) -> list[int]:
    if isinstance(seeds, int):
        return list(range(start, start + seeds))
    return [int(s) for s in seeds]


# ----------------------------------------------------------------------------- 考试
def exam_row(result: RolloutResult, policy_name: str, wall_s: float) -> dict[str, Any]:
    s = result.summary
    passed = s.get("passed")
    if passed is None:
        passed = s.get("competitive_pass")
    rank = s.get("rank")
    if rank is None:
        rank = s.get("competitive_rank")
    return {
        "seed": result.seed,
        "policy": policy_name,
        "score": round(float(result.score), 3),
        "passed": int(bool(passed)),
        "rank": int(rank) if rank is not None else -1,
        "turns": int(result.turns),
        "steps": int(result.steps),
        "wall_s": round(wall_s, 3),
    }


def evaluate_exam(
    scenario: str = "first_star",
    idol: str | None = DEFAULT_IDOL,
    loadout: Any = None,
    stage: str | None = "mid1",
    policy: str | Policy = "heuristic",
    seeds: int | Iterable[int] = 10,
    *,
    seed_start: int = 0,
    depth: int = 2,
    samples: int = 2,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """同一环境、逐个 seed 跑完整考试。每个 seed 重建策略（``reset(seed)``），保证互不影响。"""
    env = make_exam_env(scenario, idol, loadout, stage_type=stage)
    rows: list[dict[str, Any]] = []
    for seed in resolve_seeds(seeds, seed_start):
        pol = policy if isinstance(policy, Policy) else make_policy(policy, seed, depth=depth, samples=samples)
        pol.reset(seed)
        t0 = time.perf_counter()
        result = run_exam(scenario, idol, seed=seed, policy=pol, env=env)
        row = exam_row(result, pol.name, time.perf_counter() - t0)
        rows.append(row)
        if verbose:
            print(f"  seed={seed:<4d} {pol.name:<14s} score={row['score']:>10.1f} passed={row['passed']} "
                  f"rank={row['rank']} turns={row['turns']} ({row['wall_s']:.2f}s)", flush=True)
    return rows


# ----------------------------------------------------------------------------- 培育
def produce_row(result: RolloutResult, policy_name: str, exam_policy: str, wall_s: float) -> dict[str, Any]:
    final = result.summary.get("final_summary") or {}
    state = result.summary.get("state") or {}
    produce_result = final.get("produce_result") or {}
    history = final.get("audition_history") or []
    tags = []
    for item in history:
        stage = str(item.get("stage_type", "")).replace("ProduceStepType_Audition", "").lower()
        tags.append(f"{stage}:{'pass' if item.get('passed') else 'fail'}({float(item.get('exam_score') or 0):.0f})")
    return {
        "seed": result.seed,
        "label": f"{policy_name}/{exam_policy}",  # 外层策略 / 考试内策略，用于分组
        "policy": policy_name,
        "exam_policy": exam_policy,
        "rating": round(float(produce_result.get("score") or 0.0), 1),
        "rank": str(produce_result.get("rank") or ""),
        "final_score": round(float(result.score), 1),
        "ending_type": str(final.get("ending_type") or ("truncated" if result.truncated else "")),
        "route_clear": int(bool(final.get("route_clear"))),
        "auditions": " ".join(tags),
        "auditions_passed": sum(1 for item in history if item.get("passed")),
        "auditions_total": len(history),
        "vocal": round(float(state.get("vocal") or 0.0), 1),
        "dance": round(float(state.get("dance") or 0.0), 1),
        "visual": round(float(state.get("visual") or 0.0), 1),
        "stamina": round(float(state.get("stamina") or 0.0), 1),
        "steps": int(result.steps),
        "wall_s": round(wall_s, 3),
    }


def evaluate_produce(
    scenario: str = "first_star",
    idol: str | None = DEFAULT_IDOL,
    loadout: Any = None,
    policy: str | Policy = "heuristic",
    seeds: int | Iterable[int] = 10,
    *,
    seed_start: int = 0,
    exam_policy: str | None = None,
    depth: int = 2,
    samples: int = 2,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """跑完整培育。``policy`` 是外层（每周动作）策略；``exam_policy='search'`` 时，
    培育里的每场考试改由 ``SearchPolicy.select_action`` 打牌（默认用 gakumas_rl 内置启发式）。"""
    rows: list[dict[str, Any]] = []
    for seed in resolve_seeds(seeds, seed_start):
        env_kwargs: dict[str, Any] = {}
        exam_name = "builtin"
        inner: Policy | None = None
        if exam_policy and exam_policy != "builtin":
            inner = make_policy(exam_policy, seed, depth=depth, samples=samples)
            if not hasattr(inner, "select_action"):
                raise ValueError(f"exam_policy {exam_policy!r} has no select_action(runtime); use 'search'")
            inner.reset(seed)
            exam_name = inner.name
            env_kwargs["exam_action_selectors"] = {stage: inner for stage in AUDITION_STAGE_TYPES}
        env = make_produce_env(scenario, idol, loadout, seed=seed, **env_kwargs)
        pol = policy if isinstance(policy, Policy) else make_policy(policy, seed, depth=depth, samples=samples)
        pol.reset(seed)
        t0 = time.perf_counter()
        result = run_produce(scenario, idol, seed=seed, policy=pol, env=env)
        row = produce_row(result, pol.name, exam_name, time.perf_counter() - t0)
        rows.append(row)
        if verbose:
            print(f"  seed={seed:<4d} {pol.name:<10s}/{exam_name:<12s} rating={row['rating']:>8.0f} {row['rank']:<4s} "
                  f"final={row['final_score']:>9.0f} {row['ending_type']:<14s} {row['auditions']} ({row['wall_s']:.1f}s)",
                  flush=True)
    return rows


# ----------------------------------------------------------------------------- 统计 / 输出
def summarize(values: Sequence[float]) -> dict[str, float]:
    arr = np.asarray([float(v) for v in values], dtype=float)
    if arr.size == 0:
        return {"n": 0, "mean": float("nan"), "median": float("nan"), "p10": float("nan"), "p90": float("nan"),
                "min": float("nan"), "max": float("nan")}
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "p10": float(np.percentile(arr, 10)),
        "p90": float(np.percentile(arr, 90)),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }


def group_by_policy(rows: Iterable[dict[str, Any]], key: str = "policy") -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row[key]), []).append(row)
    return groups


def format_table(
    rows: Sequence[dict[str, Any]], metric: str, extra: Sequence[str] = (), *, key: str = "policy"
) -> str:
    """按 ``key`` 分组，每组一行：n / mean / median / p10 / p90 / min / max，
    外加 ``extra`` 列（0/1 列得到比例，其余得到均值）。"""
    groups = group_by_policy(rows, key)
    header = [key, "n", "mean", "median", "p10", "p90", "min", "max", *extra, "wall_s/ep"]
    first = max(12, *(len(str(k)) for k in groups)) if groups else 12  # 只有分组列自适应宽度

    def fmt(cells: Sequence[str]) -> str:
        return " | ".join(f"{c:>{first if i == 0 else 12}s}" for i, c in enumerate(cells))

    lines = [fmt(header), "-|-".join("-" * (first if i == 0 else 12) for i in range(len(header)))]
    for name, group in groups.items():
        st = summarize([r[metric] for r in group])
        cells = [name, str(st["n"])] + [f"{st[k]:.1f}" for k in ("mean", "median", "p10", "p90", "min", "max")]
        for col in extra:
            vals = [float(r.get(col) or 0.0) for r in group]
            cells.append(f"{np.mean(vals):.2f}" if vals else "nan")
        cells.append(f"{np.mean([r['wall_s'] for r in group]):.2f}")
        lines.append(fmt(cells))
    return "\n".join(lines)


def format_head_to_head(
    rows: Sequence[dict[str, Any]], metric: str, baseline: str, *, key: str = "policy"
) -> str:
    """相同 seed 下各策略对 ``baseline`` 的胜/平/负与平均差。"""
    groups = group_by_policy(rows, key)
    if baseline not in groups:
        return ""
    base = {r["seed"]: float(r[metric]) for r in groups[baseline]}
    lines = [f"head-to-head vs {baseline} on identical seeds ({metric}):"]
    for name, group in groups.items():
        if name == baseline:
            continue
        diffs = [float(r[metric]) - base[r["seed"]] for r in group if r["seed"] in base]
        if not diffs:
            continue
        wins = sum(d > 0 for d in diffs)
        ties = sum(d == 0 for d in diffs)
        lines.append(f"  {name:<24s} win {wins:>3d} / tie {ties:>3d} / lose {len(diffs) - wins - ties:>3d}   "
                     f"mean diff {np.mean(diffs):+.1f}   median diff {np.median(diffs):+.1f}")
    return "\n".join(lines)


def write_csv(rows: Sequence[dict[str, Any]], path: str | Path, columns: Sequence[str] | None = None) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    cols = list(columns or rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


__all__ = [
    "POLICY_NAMES", "AUDITION_STAGE_TYPES", "EXAM_COLUMNS", "PRODUCE_COLUMNS",
    "make_policy", "parse_loadout", "resolve_seeds",
    "evaluate_exam", "evaluate_produce", "exam_row", "produce_row",
    "summarize", "group_by_policy", "format_table", "format_head_to_head", "write_csv",
]
