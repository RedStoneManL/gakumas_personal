"""自动打牌 / 自动培育的策略与评估工具。

    from gakumas_arena.policies import SearchPolicy, HeuristicPolicy, RandomPolicy, make_policy
    from gakumas_arena.sim import run_exam
    run_exam("初", seed=0, policy=SearchPolicy(depth=2, samples=2, seed=0), stage_type="mid1")

批量评估见 ``gakumas_arena.policies.evaluation`` 与 ``scripts/eval_exam.py`` / ``scripts/eval_produce.py``。
"""
from .base import Policy
from .basic import HeuristicPolicy, RandomPolicy
from .search import DEFAULT_RESOURCE_WEIGHTS, SearchPolicy
from .evaluation import (
    evaluate_exam,
    evaluate_produce,
    format_head_to_head,
    format_table,
    make_policy,
    parse_loadout,
    summarize,
    write_csv,
)

__all__ = [
    "Policy",
    "RandomPolicy",
    "HeuristicPolicy",
    "SearchPolicy",
    "DEFAULT_RESOURCE_WEIGHTS",
    "make_policy",
    "parse_loadout",
    "evaluate_exam",
    "evaluate_produce",
    "summarize",
    "format_table",
    "format_head_to_head",
    "write_csv",
]
