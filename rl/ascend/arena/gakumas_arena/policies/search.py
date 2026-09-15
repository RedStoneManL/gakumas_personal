"""考试用深度受限穷举搜索（expectimax）策略。

思路来自 katabami83/gakumas_contest_simulator 的 ``ContestAI``（全动作枚举 + 期望估值），
但状态复制用的是 gakumas_rl ``ExamRuntime`` 自带的 ``capture_preview_state`` /
``restore_preview_state``（已验证：抓取 → 改 RNG → step → 恢复 后，真实回放与不搜索完全一致）。

- 决策节点：枚举 ``runtime.legal_actions()``（出牌 / 饮料 / 结束回合），取最大值。
- 机会节点：一个动作若消耗了运行时 RNG（回合末抽牌、回合颜色、随机检索……），就用 K 个不同的
  RNG 状态各执行一次取平均；未消耗 RNG 的动作只算一次（检查 ``bit_generator.state`` 是否变化）。
- 叶子估值 = 当前分数 + 剩余资源的启发式价值（元気/集中/好調/好印象/やる気/体力，按剩余回合折算）
  + 手牌先验（``MasterDataRepository.card_play_priors``，即官方 ``ProduceExamAutoEvaluation`` 的均值）。
- 确定性：搜索内部的 RNG 状态由 ``(seed, 决策序号, 路径, k)`` 派生；搜索结束后恢复快照（含 RNG），
  因此真实环境的随机流不受搜索影响。同一 seed + 同一局面 → 同一动作。
"""
from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np

from gakumas_rl.simulation.exam.runtime import ExamActionCandidate, ExamRuntime

from ..env import GakumasExamEnv, legal_actions
from .base import Policy

#: 默认资源权重（单位：每点资源折合多少“基础分”，再乘剩余回合与分数倍率）。
#: 只是先验，欢迎在 CLI/构造函数里覆盖后用 scripts/eval_exam.py --compare 实测。
DEFAULT_RESOURCE_WEIGHTS: dict[str, float] = {
    "block": 0.25,              # 元気：可被 元気→分数 卡转化；也抵消体力消耗
    "concentration": 1.2,       # 集中：每张属性卡额外 +集中，按剩余出牌次数折算
    "parameter_buff": 4.0,      # 好調：+50% 分数，按持续回合数折算（上限剩余回合）
    "enthusiastic": 6.0,        # 絶好調：好調基础上再加成
    "aggressive": 1.0,          # やる気：每张精神卡额外元気
    "lesson_buff": 4.0,         # 课程用同类加成
    "full_power_point": 0.8,    # 全力值
    "preservation": 0.5,        # 温存
    "stamina": 0.35,            # 剩余体力（还能打更多卡）
    "hand_prior": 0.02,         # 手牌先验（card_play_priors，/100 后再乘此权重）
}

# 负面资源：直接扣减
NEGATIVE_RESOURCES: dict[str, float] = {"sleepy": 2.0, "panic": 2.0, "slump": 2.0}

EvalFn = Callable[[ExamRuntime], float]


class SearchPolicy(Policy):
    """深度受限 expectimax。

    参数
    ----
    depth: 前瞻的动作数（ply，而非回合数）。2–3 为宜；每增加 1 大约 ×4 开销。
    samples: 机会节点采样数 K（只对消耗 RNG 的动作生效）。
    seed: 搜索内部 RNG 的种子。
    leaf: 叶子估值方式。
        - ``'rollout'``（默认）：从叶子起用官方先验贪心（``card_play_priors`` + ``exam_effect_priors``）
          打到考试结束，取终局分数。RNG 沿用该路径已采样的状态，因此仍然确定。
        - ``'heuristic'``：当前分数 + 剩余资源的手工权重估值（``resource_weights`` × ``resource_scale``）。
        - ``'score'``：只看当前分数（纯短视）。
    resource_weights / resource_scale: 仅 ``leaf='heuristic'`` 使用；覆盖 ``DEFAULT_RESOURCE_WEIGHTS``
        的部分键，或整体缩放。
    rollout_steps: rollout 最多执行的动作数。
    evaluate: 自定义叶子估值 ``f(runtime) -> float``；给定后忽略 ``leaf``。
    """

    name = "search"

    def __init__(
        self,
        depth: int = 2,
        samples: int = 2,
        seed: int | None = 0,
        *,
        leaf: str = "rollout",
        resource_weights: dict[str, float] | None = None,
        resource_scale: float = 1.0,
        rollout_steps: int = 64,
        evaluate: EvalFn | None = None,
    ) -> None:
        if depth < 1:
            raise ValueError("depth must be >= 1")
        if samples < 1:
            raise ValueError("samples must be >= 1")
        self.depth = int(depth)
        self.samples = int(samples)
        self.seed = 0 if seed is None else int(seed)
        if leaf not in ("rollout", "heuristic", "score"):
            raise ValueError("leaf must be 'rollout' | 'heuristic' | 'score'")
        self.leaf = leaf
        self.weights = {**DEFAULT_RESOURCE_WEIGHTS, **(resource_weights or {})}
        self.resource_scale = float(resource_scale)
        self.rollout_steps = int(rollout_steps)
        self._evaluate = evaluate
        self._decision_index = 0
        self.name = f"search_d{self.depth}_k{self.samples}_{leaf}"
        # 统计信息（最近一次决策）
        self.last_stats: dict[str, Any] = {}

    def reset(self, seed: int | None = None) -> None:
        if seed is not None:
            self.seed = int(seed)
        self._decision_index = 0

    # ------------------------------------------------------------------ 公共入口
    def select_action(self, runtime: ExamRuntime) -> ExamActionCandidate | None:
        """``ExamActionSelector`` 协议：可直接塞进 ``GakumasPlanningEnv(exam_action_selectors=...)``。"""
        candidates = [c for c in runtime.legal_actions() if c.kind != "noop"]
        return self._choose(runtime, candidates)

    def act(self, env: GakumasExamEnv, obs: dict[str, Any], info: dict[str, Any]) -> int:
        runtime: ExamRuntime = env.runtime
        legal = [int(i) for i in legal_actions(obs)]
        # 只搜索能映射回环境动作槽的候选（手牌溢出 max_hand_cards 的卡环境本身也打不出）
        slot_by_key: dict[tuple[str, int], int] = {}
        for index in legal:
            view = env._candidates[index]
            if view.kind == "card":
                slot_by_key[("card", int(view.payload["uid"]))] = index
            elif view.kind == "drink":
                slot_by_key[("drink", int(view.payload["index"]))] = index
            else:
                slot_by_key[("end_turn", 0)] = index
        candidates = [c for c in runtime.legal_actions() if self._key(c) in slot_by_key]
        chosen = self._choose(runtime, candidates)
        if chosen is None:
            return legal[-1]
        return slot_by_key[self._key(chosen)]

    # ------------------------------------------------------------------ 搜索
    @staticmethod
    def _key(candidate: ExamActionCandidate) -> tuple[str, int]:
        if candidate.kind == "card":
            return ("card", int(candidate.payload["uid"]))
        if candidate.kind == "drink":
            return ("drink", int(candidate.payload["index"]))
        return ("end_turn", 0)

    def _choose(self, runtime: ExamRuntime, candidates: list[ExamActionCandidate]) -> ExamActionCandidate | None:
        if not candidates:
            return None
        if runtime.terminated or len(candidates) == 1:
            self._decision_index += 1
            return candidates[0]
        decision = self._decision_index
        self._decision_index += 1
        root = runtime.capture_preview_state()
        nodes = 0
        values: list[float] = []
        try:
            for index, candidate in enumerate(candidates):
                value, visited = self._action_value(runtime, candidate, self.depth, (decision, index))
                values.append(value)
                nodes += visited
        finally:
            runtime.restore_preview_state(root)
        best = int(np.argmax(np.asarray(values)))  # 并列取靠前者（手牌顺序），保证确定性
        self.last_stats = {
            "decision": decision,
            "nodes": nodes,
            "values": [round(v, 3) for v in values],
            "labels": [c.label for c in candidates],
            "chosen": candidates[best].label,
        }
        return candidates[best]

    def _action_value(
        self,
        runtime: ExamRuntime,
        candidate: ExamActionCandidate,
        depth: int,
        path: tuple[int, ...],
    ) -> tuple[float, int]:
        """执行 ``candidate`` 后的期望价值（机会节点按 K 采样），返回 (value, 访问节点数)。"""
        snapshot = runtime.capture_preview_state()
        total = 0.0
        count = 0
        nodes = 0
        try:
            for k in range(self.samples):
                if k > 0:
                    runtime.restore_preview_state(snapshot)
                seed_state = np.random.default_rng([self.seed, *path, k]).bit_generator.state
                runtime.np_random.bit_generator.state = seed_state
                try:
                    runtime.step(
                        ExamActionCandidate(
                            label=candidate.label, kind=candidate.kind, payload=dict(candidate.payload)
                        )
                    )
                except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError):
                    # 前瞻失败：视为极差动作
                    return -math.inf, nodes + 1
                used_rng = runtime.np_random.bit_generator.state["state"] != seed_state["state"]
                value, visited = self._search(runtime, depth - 1, (*path, k))
                nodes += visited + 1
                total += value
                count += 1
                if not used_rng:
                    break  # 确定性转移，无需再采样
        finally:
            runtime.restore_preview_state(snapshot)
        return total / max(count, 1), nodes

    def _search(self, runtime: ExamRuntime, depth: int, path: tuple[int, ...]) -> tuple[float, int]:
        if runtime.terminated or depth <= 0:
            return self.evaluate(runtime), 0
        candidates = [c for c in runtime.legal_actions() if c.kind != "noop"]
        if not candidates:
            return self.evaluate(runtime), 0
        best = -math.inf
        nodes = 0
        for index, candidate in enumerate(candidates):
            value, visited = self._action_value(runtime, candidate, depth, (*path, index))
            nodes += visited
            if value > best:
                best = value
        return best, nodes

    # ------------------------------------------------------------------ 估值
    def evaluate(self, runtime: ExamRuntime) -> float:
        """叶子估值：分数 + 剩余资源启发式价值。终局只看分数。"""
        if self._evaluate is not None:
            return float(self._evaluate(runtime))
        score = float(runtime.score)
        if runtime.terminated or self.leaf == "score":
            return score
        if self.leaf == "rollout":
            return self._rollout(runtime)
        remaining = max(int(runtime.max_turns) - int(runtime.turn) + 1 + int(runtime.extra_turns), 0)
        if remaining <= 0:
            return score
        w = self.weights
        res = runtime.resources
        multiplier = max(float(getattr(runtime, "score_bonus_multiplier", 1.0) or 1.0), 0.0)
        # 每回合大致的“基础分”规模：用已得分数估计，没有则用目标分/回合数兜底
        turns_done = max(int(runtime.turn) - 1, 1)
        target = float(runtime.profile.get("base_score") or 0.0) or 1.0
        per_turn = max(score / turns_done, target / max(int(runtime.max_turns), 1) * 0.3, 1.0)

        value = 0.0
        # 好印象：每回合末得分 = 当前值，且每回合 -1 → 等差数列（katabami 的做法）
        review = float(res.get("review", 0.0))
        if review > 0:
            n = min(int(review), remaining)
            value += (review * n - n * (n - 1) / 2.0) * multiplier
        # 好調 / 絶好調：按剩余生效回合折算成“每回合基础分”的比例
        buff_turns = min(float(res.get("parameter_buff", 0.0)), remaining)
        value += buff_turns * 0.5 * per_turn * w["parameter_buff"] / 4.0
        enth_turns = min(float(res.get("enthusiastic", 0.0)), remaining)
        value += enth_turns * 0.5 * per_turn * w["enthusiastic"] / 6.0
        lesson_turns = min(float(res.get("lesson_buff", 0.0)), remaining)
        value += lesson_turns * 0.5 * per_turn * w["lesson_buff"] / 4.0
        # 集中 / やる気 / 元気 / 全力 / 温存：线性，乘剩余回合的衰减系数
        horizon = min(remaining, 4) / 4.0
        value += float(res.get("concentration", 0.0)) * w["concentration"] * remaining * multiplier * horizon
        value += float(res.get("aggressive", 0.0)) * w["aggressive"] * remaining * horizon
        value += float(res.get("block", 0.0)) * w["block"] * multiplier * horizon
        value += float(res.get("full_power_point", 0.0)) * w["full_power_point"] * horizon
        value += float(res.get("preservation", 0.0)) * w["preservation"] * horizon
        # 体力：只有剩余回合还多时才值钱
        value += float(runtime.stamina) * w["stamina"] * horizon
        # 负面状态
        for key, penalty in NEGATIVE_RESOURCES.items():
            value -= float(res.get(key, 0.0)) * penalty * remaining
        # 手牌先验（官方自动打牌权重）
        priors = runtime.repository.card_play_priors
        hand_prior = sum(priors.get(str(card.card_id), 0.0) for card in runtime.hand) / 100.0
        value += hand_prior * w["hand_prior"] * per_turn
        return score + value * self.resource_scale

    # ------------------------------------------------------------------ rollout 叶子
    def _prior(self, runtime: ExamRuntime, card: Any, remaining: int) -> float:
        repo = runtime.repository
        effect_types = repo.card_exam_effect_types(card.base_card)
        effect_prior = sum(repo.exam_effect_priors.get((t, remaining), 0.0) for t in effect_types)
        return repo.card_play_priors.get(str(card.card_id), 0.0) + effect_prior / max(len(effect_types), 1)

    def _rollout(self, runtime: ExamRuntime) -> float:
        """官方先验贪心打到结束（会改写 runtime；调用方负责恢复快照）。不使用饮料——饮料留给搜索层决策。"""
        for _ in range(self.rollout_steps):
            if runtime.terminated:
                break
            candidates = runtime.legal_actions()
            cards = [c for c in candidates if c.kind == "card"]
            if cards:
                remaining = max(int(runtime.max_turns) - int(runtime.turn) + 1, 1)
                by_uid = {card.uid: card for card in runtime.hand}
                action = max(cards, key=lambda c: self._prior(runtime, by_uid[int(c.payload["uid"])], remaining))
            else:
                action = next((c for c in candidates if c.kind == "end_turn"), None)
                if action is None:
                    break
            try:
                runtime.step(ExamActionCandidate(label=action.label, kind=action.kind, payload=dict(action.payload)))
            except (AttributeError, IndexError, KeyError, RuntimeError, TypeError, ValueError):
                break
        return float(runtime.score)


__all__ = ["SearchPolicy", "DEFAULT_RESOURCE_WEIGHTS", "NEGATIVE_RESOURCES"]
