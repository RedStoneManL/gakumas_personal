"""Produce 评分公式。

直接移植自外部参考实现：
- gakumas-tools/utils/produceRank.js
- gakumas-tools/utils/nia.js
"""

from __future__ import annotations

import math
from typing import Any

TARGET_RATING_BY_RANK: dict[str, int] = {
    'S4': 26000,
    'SSS+': 23000,
    'SSS': 20000,
    'SS+': 18000,
    'SS': 16000,
    'S+': 14500,
    'S': 13000,
    'A+': 11500,
    'A': 10000,
    'B+': 8000,
    'B': 6000,
    'C+': 4500,
    'C': 3000,
}


def get_produce_rank(rating: float) -> str | None:
    """按固定档位阈值返回 Produce Rank。"""
    numeric = float(rating)
    for rank, threshold in TARGET_RATING_BY_RANK.items():
        if numeric >= threshold:
            return rank
    return None


HAJIME_MAX_PARAMS_BY_DIFFICULTY: dict[str, int] = {
    'regular': 1000,
    'pro': 1500,
    'master': 1800,
    'legend': 2800,
}
PARAM_BONUS_BY_PLACE: dict[int, int] = {1: 30, 2: 20, 3: 10, 4: 0}
PARAM_BONUS_BY_PLACE_LEGEND: dict[int, int] = {1: 120, 2: 60, 3: 30, 4: 0}
RATING_BY_PLACE: dict[int, int] = {1: 1700, 2: 900, 3: 500, 4: 0}
REVERSE_RATING_REGIMES: list[dict[str, float]] = [
    {'threshold': 3650, 'base': 40000, 'multiplier': 0.01},
    {'threshold': 3450, 'base': 30000, 'multiplier': 0.02},
    {'threshold': 3050, 'base': 20000, 'multiplier': 0.04},
    {'threshold': 2250, 'base': 10000, 'multiplier': 0.08},
    {'threshold': 1500, 'base': 5000, 'multiplier': 0.15},
    {'threshold': 0, 'base': 0, 'multiplier': 0.3},
]
REVERSE_RATING_REGIMES_LEGEND_MIDTERM: list[dict[str, float]] = [
    {'base': 200000, 'multiplier': 0.0},
    {'base': 60000, 'multiplier': 0.001},
    {'base': 50000, 'multiplier': 0.002},
    {'base': 40000, 'multiplier': 0.003},
    {'base': 30000, 'multiplier': 0.008},
    {'base': 20000, 'multiplier': 0.05},
    {'base': 10000, 'multiplier': 0.08},
    {'base': 0, 'multiplier': 0.11},
]
REVERSE_RATING_REGIMES_LEGEND_FINAL: list[dict[str, float]] = [
    {'threshold': 8700, 'base': 2000000, 'multiplier': 0.0},
    {'threshold': 7300, 'base': 600000, 'multiplier': 0.001},
    {'threshold': 6500, 'base': 500000, 'multiplier': 0.008},
    {'threshold': 4500, 'base': 300000, 'multiplier': 0.01},
    {'threshold': 0, 'base': 0, 'multiplier': 0.015},
]
PARAM_RATING_MULTIPLIER = 2.3
PARAM_RATING_MULTIPLIER_LEGEND = 2.1


def calculate_hajime_rating_ex_exam_score(*, difficulty: str, place: int, params: tuple[float, float, float], midterm_score: float = 0.0) -> dict[str, Any]:
    difficulty_key = str(difficulty)
    if difficulty_key not in HAJIME_MAX_PARAMS_BY_DIFFICULTY:
        raise ValueError(f'Unsupported hajime difficulty: {difficulty}')
    max_params = HAJIME_MAX_PARAMS_BY_DIFFICULTY[difficulty_key]
    param_multiplier = PARAM_RATING_MULTIPLIER_LEGEND if difficulty_key == 'legend' else PARAM_RATING_MULTIPLIER
    place_bonus_map = PARAM_BONUS_BY_PLACE_LEGEND if difficulty_key == 'legend' else PARAM_BONUS_BY_PLACE
    clamped_place = min(max(int(place), 1), 4)
    place_param_bonus = int(place_bonus_map[clamped_place])
    place_rating = int(RATING_BY_PLACE[clamped_place])
    param_rating = math.floor(sum(min(float(v) + place_param_bonus, max_params) for v in params) * param_multiplier)
    midterm_rating = 0
    calc_midterm = float(midterm_score)
    if difficulty_key == 'legend':
        for regime in REVERSE_RATING_REGIMES_LEGEND_MIDTERM:
            base = float(regime['base'])
            multiplier = float(regime['multiplier'])
            if calc_midterm > base:
                midterm_rating += (calc_midterm - base) * multiplier
                calc_midterm = base
        midterm_rating = math.floor(midterm_rating)
    total = place_rating + param_rating + midterm_rating
    return {
        'difficulty': difficulty_key,
        'place': clamped_place,
        'max_params': max_params,
        'place_rating': place_rating,
        'param_rating': param_rating,
        'midterm_rating': midterm_rating,
        'rating_ex_exam_score': total,
    }


def calculate_hajime_actual_rating(*, difficulty: str, rating_ex_exam_score: float, final_score: float) -> dict[str, Any]:
    difficulty_key = str(difficulty)
    regimes = REVERSE_RATING_REGIMES_LEGEND_FINAL if difficulty_key == 'legend' else REVERSE_RATING_REGIMES
    calc_score = float(final_score)
    final_exam_rating = 0.0
    for regime in regimes:
        base = float(regime['base'])
        multiplier = float(regime['multiplier'])
        if calc_score > base:
            final_exam_rating += (calc_score - base) * multiplier
            calc_score = base
    final_exam_rating = math.floor(final_exam_rating)
    total_rating = int(final_exam_rating + float(rating_ex_exam_score))
    return {
        'difficulty': difficulty_key,
        'final_score': float(final_score),
        'final_exam_rating': int(final_exam_rating),
        'rating': total_rating,
        'rank': get_produce_rank(total_rating),
    }


def calculate_hajime_target_scores(*, difficulty: str, rating_ex_exam_score: float) -> list[dict[str, Any]]:
    difficulty_key = str(difficulty)
    regimes = REVERSE_RATING_REGIMES_LEGEND_FINAL if difficulty_key == 'legend' else REVERSE_RATING_REGIMES
    results: list[dict[str, Any]] = []
    for rank in TARGET_RATING_BY_RANK.keys():
        target_rating = TARGET_RATING_BY_RANK[rank] - float(rating_ex_exam_score)
        score = 0.0
        reachable = True
        for regime in regimes:
            threshold = float(regime['threshold'])
            base = float(regime['base'])
            multiplier = float(regime['multiplier'])
            if target_rating <= threshold:
                continue
            if multiplier == 0:
                score = math.inf
                reachable = False
            else:
                score = math.ceil(base + (target_rating - threshold) / multiplier)
            break
        results.append({'rank': rank, 'score': score, 'reachable': reachable})
    return results


def calculate_hajime_produce_rating(*, difficulty: str, place: int, params: tuple[float, float, float], final_score: float, midterm_score: float = 0.0) -> dict[str, Any]:
    ex = calculate_hajime_rating_ex_exam_score(difficulty=difficulty, place=place, params=params, midterm_score=midterm_score)
    actual = calculate_hajime_actual_rating(difficulty=difficulty, rating_ex_exam_score=float(ex['rating_ex_exam_score']), final_score=final_score)
    return {
        **ex,
        **actual,
        'target_scores_by_rank': calculate_hajime_target_scores(difficulty=difficulty, rating_ex_exam_score=float(ex['rating_ex_exam_score'])),
    }


NIA_MAX_PARAMS_BY_DIFFICULTY: dict[str, int] = {'pro': 2000, 'master': 2600}
MIN_VOTES_BY_STAGE: dict[str, int] = {'melobang': 9000, 'galaxy': 25000, 'quartet': 40000, 'finale': 57000}
PARAM_ORDER_BY_IDOL: dict[int, tuple[int, int, int]] = {
    1: (3, 2, 1), 2: (1, 2, 3), 3: (3, 1, 2), 4: (1, 3, 2), 5: (3, 2, 1), 6: (3, 1, 2), 7: (3, 1, 2), 8: (1, 2, 3), 9: (3, 2, 1), 10: (2, 1, 3), 11: (2, 3, 1), 12: (1, 3, 2), 13: (2, 1, 3), 14: (1, 2, 3),
}
BALANCE_BY_IDOL: dict[int, str] = {1:'flat',2:'skew',3:'skew',4:'skew',5:'flat',6:'skew',7:'skew',8:'flat',9:'flat',10:'flat',11:'flat',12:'skew',13:'skew',14:'flat'}
CHARACTER_TOKEN_TO_NIA_ID: dict[str, int] = {'amao':1,'fktn':2,'hmsz':3,'hrnm':4,'hski':5,'jkcj':6,'kcna':7,'kllj':8,'ssmk':9,'ttmr':10,'atbm':11,'cmnm':12,'shro':13,'ume':14}


def resolve_nia_idol_id(character_token: str) -> int:
    return int(CHARACTER_TOKEN_TO_NIA_ID.get(str(character_token or '').strip(), 1))


def infer_character_token_from_audition_difficulty_id(audition_difficulty_id: str) -> str:
    text = str(audition_difficulty_id or '').strip()
    prefix = 'p_step_audition_difficulty-'
    if text.startswith(prefix):
        tail = text[len(prefix):]
        return tail.split('-', 1)[0]
    return ''


def resolve_nia_idol_id_from_audition_difficulty_id(audition_difficulty_id: str) -> int:
    return resolve_nia_idol_id(infer_character_token_from_audition_difficulty_id(audition_difficulty_id))

PARAM_REGIMES_BY_DIFF_STAGE_BALANCE_ORDER: dict[str, Any] = {
    'pro': {
        'melobang': {
            1: [{'threshold': 2550, 'multiplier': 0.0, 'constant': 92}, {'threshold': 1300, 'multiplier': 0.0055, 'constant': 77}, {'threshold': 0, 'multiplier': 0.0654, 'constant': 0}],
            2: [{'threshold': 2050, 'multiplier': 0.0, 'constant': 76}, {'threshold': 1060, 'multiplier': 0.0055, 'constant': 63.5}, {'threshold': 0, 'multiplier': 0.0654, 'constant': 0}],
            3: [{'threshold': 1600, 'multiplier': 0.0, 'constant': 62}, {'threshold': 860, 'multiplier': 0.0055, 'constant': 52.25}, {'threshold': 0, 'multiplier': 0.0654, 'constant': 0}],
        },
        'galaxy': {
            1: [{'threshold': 24500, 'multiplier': 0.0, 'constant': 119}, {'threshold': 12400, 'multiplier': 0.0008, 'constant': 98}, {'threshold': 0, 'multiplier': 0.00875, 'constant': 0}],
            2: [{'threshold': 20400, 'multiplier': 0.0, 'constant': 98}, {'threshold': 10200, 'multiplier': 0.0008, 'constant': 81}, {'threshold': 0, 'multiplier': 0.00875, 'constant': 0}],
            3: [{'threshold': 16400, 'multiplier': 0.0, 'constant': 80}, {'threshold': 8400, 'multiplier': 0.0008, 'constant': 66.25}, {'threshold': 0, 'multiplier': 0.00875, 'constant': 0}],
        },
        'quartet': {
            1: [{'threshold': 41600, 'multiplier': 0.0, 'constant': 145}, {'threshold': 20000, 'multiplier': 0.000578, 'constant': 120}, {'threshold': 0, 'multiplier': 0.00661, 'constant': 0}],
            2: [{'threshold': 34000, 'multiplier': 0.0, 'constant': 120}, {'threshold': 16500, 'multiplier': 0.000578, 'constant': 99.5}, {'threshold': 0, 'multiplier': 0.00661, 'constant': 0}],
            3: [{'threshold': 27700, 'multiplier': 0.0, 'constant': 98}, {'threshold': 13400, 'multiplier': 0.000578, 'constant': 81}, {'threshold': 0, 'multiplier': 0.00661, 'constant': 0}],
        },
        'finale': {
            1: [{'threshold': 79000, 'multiplier': 0.0, 'constant': 172}, {'threshold': 38400, 'multiplier': 0.000367, 'constant': 142.5}, {'threshold': 0, 'multiplier': 0.004072, 'constant': 1.5}],
            2: [{'threshold': 65000, 'multiplier': 0.0, 'constant': 142}, {'threshold': 31800, 'multiplier': 0.000367, 'constant': 117.5}, {'threshold': 0, 'multiplier': 0.004072, 'constant': 1}],
            3: [{'threshold': 55000, 'multiplier': 0.0, 'constant': 116}, {'threshold': 26000, 'multiplier': 0.000367, 'constant': 95.5}, {'threshold': 0, 'multiplier': 0.004072, 'constant': 1}],
        },
    },
    'master': {
        'quartet': {
            'flat': {
                1: [{'threshold': 70300, 'multiplier': 0.0, 'constant': 145}, {'threshold': 34210, 'multiplier': 0.001194, 'constant': 61.08}, {'threshold': 0, 'multiplier': 0.002965, 'constant': 0.5}],
                2: [{'threshold': 32870, 'multiplier': 0.0, 'constant': 120}, {'threshold': 16050, 'multiplier': 0.00213, 'constant': 50}, {'threshold': 0, 'multiplier': 0.00512, 'constant': 2}],
                3: [{'threshold': 18670, 'multiplier': 0.0, 'constant': 98}, {'threshold': 9120, 'multiplier': 0.00308, 'constant': 40.5}, {'threshold': 0, 'multiplier': 0.00741, 'constant': 1}],
            },
            'skew': {
                1: [{'threshold': 70750, 'multiplier': 0.0, 'constant': 182}, {'threshold': 34133, 'multiplier': 0.00148, 'constant': 77.3}, {'threshold': 0, 'multiplier': 0.00373, 'constant': 0.5}],
                2: [{'threshold': 32900, 'multiplier': 0.0, 'constant': 109}, {'threshold': 15970, 'multiplier': 0.0019, 'constant': 46.5}, {'threshold': 0, 'multiplier': 0.00475, 'constant': 1}],
                3: [{'threshold': 19570, 'multiplier': 0.0, 'constant': 73}, {'threshold': 9000, 'multiplier': 0.0023, 'constant': 30}, {'threshold': 0, 'multiplier': 0.0056, 'constant': 0}],
            },
        },
        'finale': {
            'flat': {
                1: [{'threshold': 134210, 'multiplier': 0.0, 'constant': 172}, {'threshold': 66600, 'multiplier': 0.000756, 'constant': 70}, {'threshold': 0, 'multiplier': 0.0018, 'constant': 0.5}],
                2: [{'threshold': 63750, 'multiplier': 0.0, 'constant': 142}, {'threshold': 31350, 'multiplier': 0.001276, 'constant': 61}, {'threshold': 0, 'multiplier': 0.00325, 'constant': 0}],
                3: [{'threshold': 36500, 'multiplier': 0.0, 'constant': 116}, {'threshold': 17600, 'multiplier': 0.00182, 'constant': 50}, {'threshold': 0, 'multiplier': 0.00465, 'constant': 0}],
            },
            'skew': {
                1: [{'threshold': 136070, 'multiplier': 0.0, 'constant': 215}, {'threshold': 65350, 'multiplier': 0.000915, 'constant': 90.5}, {'threshold': 0, 'multiplier': 0.0023, 'constant': 0}],
                2: [{'threshold': 63250, 'multiplier': 0.0, 'constant': 129}, {'threshold': 30900, 'multiplier': 0.00117, 'constant': 55}, {'threshold': 0, 'multiplier': 0.00295, 'constant': 0}],
                3: [{'threshold': 36100, 'multiplier': 0.0, 'constant': 86}, {'threshold': 17800, 'multiplier': 0.00136, 'constant': 37}, {'threshold': 0, 'multiplier': 0.003465, 'constant': 0}],
            },
        },
    },
}
VOTE_REGIMES_BY_DIFF_STAGE: dict[str, Any] = {
    'pro': {
        'melobang': [{'threshold': 10710, 'multiplier': 0.0, 'constant': 8000}, {'threshold': 5360, 'multiplier': 0.0976, 'constant': 6955}, {'threshold': 0, 'multiplier': 1.299, 'constant': 522.5}],
        'galaxy': [{'threshold': 258000, 'multiplier': 0.0, 'constant': 10666}, {'threshold': 64500, 'multiplier': 0.00361, 'constant': 9739}, {'threshold': 0, 'multiplier': 0.12028, 'constant': 2240.5}],
        'quartet': [{'threshold': 207900, 'multiplier': 0.0, 'constant': 20000}, {'threshold': 103970, 'multiplier': 0.01339, 'constant': 17216}, {'threshold': 0, 'multiplier': 0.14868, 'constant': 3150.5}],
        'finale': [{'threshold': 798000, 'multiplier': 0.0, 'constant': 25334}, {'threshold': 200000, 'multiplier': 0.0032025, 'constant': 22783}, {'threshold': 0, 'multiplier': 0.1067045, 'constant': 2165}],
    },
    'master': {
        'quartet': [{'threshold': 239970, 'multiplier': 0.0, 'constant': 25334}, {'threshold': 180000, 'multiplier': 0.02800776858, 'constant': 18612.6}, {'threshold': 119982, 'multiplier': 0.08399651702, 'constant': 8534.93}, {'threshold': 0, 'multiplier': 0.1289162297, 'constant': 3145.5}],
        'finale': [{'threshold': 1200582, 'multiplier': 0.0, 'constant': 32668}, {'threshold': 640882, 'multiplier': 0.004126232489, 'constant': 27714.07}, {'threshold': 260417, 'multiplier': 0.01821637749, 'constant': 18683.95}, {'threshold': 0, 'multiplier': 0.07592333987, 'constant': 3656.17}],
    },
}
VOTE_RANKS: list[dict[str, Any]] = [
    {'rank': 'SSS', 'threshold': 140000}, {'rank': 'SS+', 'threshold': 120000}, {'rank': 'SS', 'threshold': 100000},
    {'rank': 'S+', 'threshold': 80001}, {'rank': 'S', 'threshold': 60001}, {'rank': 'A+', 'threshold': 40001}, {'rank': 'A', 'threshold': 20001},
]
FAN_RATING_BY_VOTE_RANK: dict[str, dict[str, float]] = {
    'A': {'base': 300, 'multiplier': 0.085}, 'A+': {'base': 900, 'multiplier': 0.07}, 'S': {'base': 1200, 'multiplier': 0.065},
    'S+': {'base': 1600, 'multiplier': 0.06}, 'SS': {'base': 2600, 'multiplier': 0.05}, 'SS+': {'base': 3800, 'multiplier': 0.04}, 'SSS': {'base': 5200, 'multiplier': 0.03},
}


def calculate_nia_gained_params(param_regimes_by_order: dict[int, list[dict[str, float]]], param_order: tuple[int, int, int], scores: tuple[float, float, float]) -> list[int]:
    results: list[int] = []
    for i, order in enumerate(param_order):
        regimes = param_regimes_by_order[int(order)]
        gained = 0
        for regime in regimes:
            threshold = float(regime['threshold'])
            multiplier = float(regime['multiplier'])
            constant = float(regime['constant'])
            if float(scores[i]) > threshold:
                gained = math.floor(float(scores[i]) * multiplier + constant)
                break
        results.append(gained)
    return results


def calculate_nia_max_scores(
    param_regimes_by_order: dict[int, list[dict[str, float]]],
    max_params: int,
    param_order: tuple[int, int, int],
    params: tuple[float, float, float],
    param_bonuses: tuple[float, float, float],
) -> list[int]:
    """按外部逻辑反推每项 score 的大致上限。"""
    max_scores: list[int] = []
    for i, order in enumerate(param_order):
        regimes = param_regimes_by_order[int(order)]
        max_gain = math.ceil((max_params - float(params[i])) / (1 + float(param_bonuses[i]) / 100.0))
        selected = regimes[0]
        for j in range(1, len(regimes)):
            constant = float(regimes[j]['constant'])
            multiplier = float(regimes[j]['multiplier'])
            if multiplier == 0:
                selected = regimes[j]
                continue
            if (max_gain - constant) / multiplier > float(regimes[j - 1]['threshold']):
                break
            selected = regimes[j]
        threshold = float(selected['threshold'])
        constant = float(selected['constant'])
        multiplier = float(selected['multiplier'])
        if multiplier == 0:
            max_scores.append(int(threshold))
        else:
            max_scores.append(math.floor((max_gain - constant) / multiplier))
    return max_scores


def calculate_nia_bonus_params(gained_params: list[int], param_bonuses: tuple[float, float, float]) -> list[int]:
    return [math.floor(float(param) * float(param_bonuses[i]) / 100.0) for i, param in enumerate(gained_params)]


def calculate_nia_challenge_params(gained_params: list[int], bonus_params: list[int], challenge_param_bonus: float) -> list[int]:
    return [
        math.floor(float(param) * challenge_param_bonus / 100.0)
        + math.floor(float(bonus_params[i]) * challenge_param_bonus / 100.0)
        for i, param in enumerate(gained_params)
    ]


def calculate_nia_post_audition_params(max_params: int, params: tuple[float, float, float], gained_params: list[int], challenge_params: list[int], bonus_params: list[int]) -> list[float]:
    return [
        min(
            float(params[i]) + float(gained_params[i]) + float(challenge_params[i]) + float(bonus_params[i]),
            float(max_params),
        )
        for i in range(3)
    ]


def calculate_nia_gained_votes(vote_regimes: list[dict[str, float]], affection: int, total_score: float) -> int:
    for regime in vote_regimes:
        threshold = float(regime['threshold'])
        multiplier = float(regime['multiplier'])
        constant = float(regime['constant'])
        if float(total_score) > threshold:
            return math.floor(
                math.ceil(float(total_score) * multiplier + constant) * (1 + 0.05 * (int(affection) - 10))
            )
    return 0


def calculate_score_for_votes(vote_regimes: list[dict[str, float]], affection: int, votes: float) -> int:
    """按外部逻辑反推达到指定票数大致需要多少总分。"""
    for regime in vote_regimes:
        threshold = float(regime['threshold'])
        multiplier = float(regime['multiplier'])
        constant = float(regime['constant'])
        if float(votes) > constant:
            if multiplier == 0:
                return int(threshold)
            return math.floor(
                (math.ceil(float(votes) / (1 + 0.05 * (int(affection) - 10))) - constant)
                / multiplier
            )
    return 0


def get_vote_rank(votes: float) -> str | None:
    numeric = float(votes)
    for item in VOTE_RANKS:
        if numeric >= float(item['threshold']):
            return str(item['rank'])
    return None


def calculate_vote_rating(votes: float, vote_rank: str | None) -> int | None:
    if not vote_rank:
        return None
    data = FAN_RATING_BY_VOTE_RANK[vote_rank]
    return int(float(data['base']) + math.floor(float(votes) * float(data['multiplier'])))


def calculate_nia_recommended_scores(
    *,
    difficulty: str,
    idol_id: int,
    stage: str,
    params: tuple[float, float, float],
    param_bonuses: tuple[float, float, float],
    challenge_param_bonus: float,
    votes: float,
    affection: int,
) -> dict[str, list[int]]:
    """移植外部的推荐分数搜索算法。"""
    difficulty_key = str(difficulty)
    stage_key = str(stage)
    max_params = NIA_MAX_PARAMS_BY_DIFFICULTY[difficulty_key]
    param_order = PARAM_ORDER_BY_IDOL[int(idol_id)]
    balance = BALANCE_BY_IDOL[int(idol_id)]
    if difficulty_key == 'pro':
        param_regimes_by_order = PARAM_REGIMES_BY_DIFF_STAGE_BALANCE_ORDER[difficulty_key][stage_key]
    else:
        param_regimes_by_order = PARAM_REGIMES_BY_DIFF_STAGE_BALANCE_ORDER[difficulty_key][stage_key][balance]
    vote_regimes = VOTE_REGIMES_BY_DIFF_STAGE[difficulty_key][stage_key]

    sft = 0
    max_scores = calculate_nia_max_scores(param_regimes_by_order, max_params, param_order, params, param_bonuses)
    recommended_scores: dict[str, list[int]] = {}
    current_scores = [0, 0, 0]
    produce_ranks = list(TARGET_RATING_BY_RANK.keys())[:8]
    rank_index = len(produce_ranks) - 1

    while True:
        target_rank = produce_ranks[rank_index]
        target_rating = TARGET_RATING_BY_RANK[target_rank]

        gained_params = calculate_nia_gained_params(param_regimes_by_order, param_order, tuple(current_scores))
        bonus_params = calculate_nia_bonus_params(gained_params, param_bonuses)
        challenge_params = calculate_nia_challenge_params(gained_params, bonus_params, challenge_param_bonus)
        post_params = calculate_nia_post_audition_params(max_params, params, gained_params, challenge_params, bonus_params)

        total_score = sum(current_scores)
        gained_votes = calculate_nia_gained_votes(vote_regimes, affection, total_score)
        post_votes = float(votes) + float(gained_votes)

        current_param_rating = math.floor(sum(post_params) * 2.3)
        vote_rank = get_vote_rank(post_votes)
        current_vote_rating = calculate_vote_rating(post_votes, vote_rank) or 0

        if current_param_rating + current_vote_rating >= target_rating:
            recommended_scores[target_rank] = list(current_scores)
            rank_index -= 1
            if rank_index < 0:
                break
            continue

        multipliers: list[float] = []
        for i, order in enumerate(param_order):
            regimes = param_regimes_by_order[int(order)]
            selected_multiplier = 0.0
            for regime in regimes:
                if current_scores[i] >= float(regime['threshold']):
                    selected_multiplier = float(regime['multiplier'])
                    break
            multipliers.append(selected_multiplier)
        max_multiplier = max(multipliers)
        selected_param = -1
        for i, order in enumerate(param_order):
            if multipliers[i] != max_multiplier:
                continue
            if selected_param == -1 or order < param_order[selected_param]:
                selected_param = i
        if selected_param < 0:
            break

        score_to_next_vote_rank = math.inf
        vote_rank_index = next((i for i, item in enumerate(VOTE_RANKS) if item['rank'] == vote_rank), -1)
        if vote_rank_index == -1:
            vote_rank_index = len(VOTE_RANKS)
        if vote_rank_index > 0:
            votes_to_next_vote_rank = float(VOTE_RANKS[vote_rank_index - 1]['threshold']) - float(votes)
            score_to_next_vote_rank = calculate_score_for_votes(vote_regimes, affection, votes_to_next_vote_rank) - total_score

        score_to_max_param = max_scores[selected_param] - current_scores[selected_param]
        if score_to_max_param <= 0:
            score_to_max_param = math.inf

        param_regimes = param_regimes_by_order[int(param_order[selected_param])]
        current_param_regime_index = next((i for i, regime in enumerate(param_regimes) if float(regime['multiplier']) == max_multiplier), -1)
        current_vote_regime_index = next((i for i, regime in enumerate(vote_regimes) if total_score >= float(regime['threshold'])), -1)

        score_to_next_param_regime = math.inf
        if current_param_regime_index > 0:
            next_param_regime = param_regimes[current_param_regime_index - 1]
            score_to_next_param_regime = float(next_param_regime['threshold']) - current_scores[selected_param]

        score_to_next_vote_regime = math.inf
        if current_vote_regime_index > 0:
            next_vote_regime = vote_regimes[current_vote_regime_index - 1]
            score_to_next_vote_regime = float(next_vote_regime['threshold']) - total_score

        current_param_regime = param_regimes[current_param_regime_index]
        current_vote_regime = vote_regimes[current_vote_regime_index]
        current_vote_rank_cfg = FAN_RATING_BY_VOTE_RANK.get(vote_rank) if vote_rank else None
        remaining_rating = target_rating - current_param_rating - current_vote_rating
        vote_multiplier_term = 0.0
        if current_vote_rank_cfg is not None:
            vote_multiplier_term = (
                float(current_vote_regime['multiplier'])
                * (1 + 0.05 * (int(affection) - 10))
                * float(current_vote_rank_cfg['multiplier'])
            )
        denominator = (
            2.3 * float(current_param_regime['multiplier']) * (1 + float(param_bonuses[selected_param]) / 100.0)
            + vote_multiplier_term
        )
        remaining_score = math.floor(remaining_rating / denominator) if denominator > 0 else math.inf

        target_scores = [
            score_to_next_vote_rank,
            score_to_max_param,
            score_to_next_param_regime,
            score_to_next_vote_regime,
            remaining_score,
        ]
        target_scores = [score for score in target_scores if score != math.inf and score > 0]
        if not target_scores:
            break
        current_scores[selected_param] += int(min(target_scores))
        sft += 1
        if sft > 1000:
            break

    return recommended_scores


def calculate_nia_produce_rating(*, difficulty: str, idol_id: int, stage: str, pre_params: tuple[float, float, float], param_bonuses: tuple[float, float, float], challenge_param_bonus: float, pre_votes: float, affection: int, scores: tuple[float, float, float]) -> dict[str, Any]:
    difficulty_key = str(difficulty)
    stage_key = str(stage)
    max_params = NIA_MAX_PARAMS_BY_DIFFICULTY[difficulty_key]
    param_order = PARAM_ORDER_BY_IDOL[int(idol_id)]
    balance = BALANCE_BY_IDOL[int(idol_id)]
    if difficulty_key == 'pro':
        param_regimes_by_order = PARAM_REGIMES_BY_DIFF_STAGE_BALANCE_ORDER[difficulty_key][stage_key]
    else:
        param_regimes_by_order = PARAM_REGIMES_BY_DIFF_STAGE_BALANCE_ORDER[difficulty_key][stage_key][balance]
    vote_regimes = VOTE_REGIMES_BY_DIFF_STAGE[difficulty_key][stage_key]
    gained_params = calculate_nia_gained_params(param_regimes_by_order, param_order, scores)
    bonus_params = calculate_nia_bonus_params(gained_params, param_bonuses)
    challenge_params = calculate_nia_challenge_params(gained_params, bonus_params, challenge_param_bonus)
    post_params = calculate_nia_post_audition_params(max_params, pre_params, gained_params, challenge_params, bonus_params)
    param_rating = math.floor(sum(post_params) * 2.3)
    total_score = sum(float(v) for v in scores)
    gained_votes = calculate_nia_gained_votes(vote_regimes, affection, total_score)
    total_votes = float(pre_votes) + float(gained_votes)
    vote_rank = get_vote_rank(total_votes)
    vote_rating = calculate_vote_rating(total_votes, vote_rank)
    total_rating = None if vote_rating is None else int(param_rating + vote_rating)
    produce_rank = None if total_rating is None else get_produce_rank(total_rating)
    return {
        'difficulty': difficulty_key,
        'idol_id': int(idol_id),
        'stage': stage_key,
        'max_params': max_params,
        'param_order': param_order,
        'balance': balance,
        'scores': tuple(float(v) for v in scores),
        'gained_params': gained_params,
        'bonus_params': bonus_params,
        'challenge_params': challenge_params,
        'post_params': post_params,
        'param_rating': int(param_rating),
        'gained_votes': int(gained_votes),
        'total_votes': int(total_votes),
        'vote_rank': vote_rank,
        'vote_rating': vote_rating,
        'rating': total_rating,
        'rank': produce_rank,
    }


# ---------------------------------------------------------------------------
# H.I.F（Hatsuboshi IDOL FESTIVAL）評価値
#
# 公式来源：docs/research/existing_engines.md §6.1
#   huraru7/gakumas_HIF_Rating_Calculation/js/formulas.js
#   与 gakumas-tools/utils/hif.js、happyMilleFeuille/gakumas/calcModals.js 三方一致。
# 与 docs/scenarios/hif.md §7.2 社区推定
#   評価値 = 合計パラメータ×2 + スター性×7.5 + R1換算 + R2換算 − 2000
# 结构一致；§6.1 额外给出 R2 分数→スター性 换算表与 R1/R2 分段系数，本文件以 §6.1 为准。
# 等级阈值来源：主数据 ProduceGrade（produce_group-003）= hif.md §7.1。
# ---------------------------------------------------------------------------

HIF_TARGET_RATING_BY_RANK: dict[str, int] = {
    'S5': 35000,
    'S4+': 30000,
    'S4': 26000,
    'SSS+': 23000,
    'SSS': 20000,
    'SS+': 18000,
    'SS': 16000,
    'S+': 14500,
    'S': 13000,
    'A+': 11500,
    'A': 10000,
    'B+': 8000,
    'B': 6000,
    'C+': 4500,
    'C': 3000,
    'D': 2000,
    'E': 1000,
    'F': 0,
}
"""HIF 评价等级阈值（`ProduceGrade` produce_group-003，上限 `ResultGrade_Sssss`）。"""

HIF_PARAM_RATING_MULTIPLIER = 2.0
HIF_STAR_RATING_MULTIPLIER = 7.5
HIF_RATING_BASE_OFFSET = 2000
HIF_STAR_QUALITY_CAP_BEFORE_ROUND2 = 1110
HIF_STAR_QUALITY_CAP = 1335
HIF_ROUND2_STAR_GAIN_DEARNESS_MULTIPLIER = 1.5
HIF_PARAMETER_CAP_FOR_RATING = 3200
HIF_ROUND1_SCORE_MULTIPLIER = 1.2

# R2 分数 → スター性 基础获得量（未乘亲爱度倍率）。分段：(分数上限, 段起始值, 斜率)
HIF_ROUND2_STAR_GAIN_SEGMENTS: tuple[tuple[float, float, float], ...] = (
    (400000.0, 0.0, 0.0001875),
    (600000.0, 75.0, 0.000225),
    (1000000.0, 120.0, 0.000075),
)
HIF_ROUND2_STAR_GAIN_MAX = 150.0

# R1 分数（原始分，未乘 1.2）→ 評価値 分段：(分数上限, 段起始评价, 斜率)
HIF_ROUND1_RATING_SEGMENTS: tuple[tuple[float, float, float], ...] = (
    (300000.0, 0.0, 0.0),
    (700000.0, 0.0, 0.01),
    (1000000.0, 4000.0, 0.003),
    (1200000.0, 4900.0, 0.002),
    (1400000.0, 5300.0, 0.001),
)
HIF_ROUND1_RATING_MAX = 5500.0

# R2 分数 → 評価値 分段
HIF_ROUND2_RATING_SEGMENTS: tuple[tuple[float, float, float], ...] = (
    (600000.0, 0.0, 0.0),
    (900000.0, 0.0, 0.004),
    (1500000.0, 1200.0, 0.008),
    (2000000.0, 6000.0, 0.002),
    (2400000.0, 7000.0, 0.001),
)
HIF_ROUND2_RATING_MAX = 7400.0


def _piecewise_linear(score: float, segments: tuple[tuple[float, float, float], ...], maximum: float) -> float:
    """按「(上限, 段起始值, 斜率)」分段表计算未取整的分段线性值。

    Args:
        score: 输入分数。
        segments: 分段表，每段给出该段的分数上限、段起始值与斜率；段的下限是上一段的上限（首段为 0）。
        maximum: 超过最后一段上限后的封顶值。

    Returns:
        分段线性插值结果（未取整）。
    """

    value = max(float(score), 0.0)
    lower = 0.0
    for upper, base, slope in segments:
        if value <= upper:
            return float(base) + (value - lower) * float(slope)
        lower = float(upper)
    return float(maximum)


def get_hif_produce_rank(rating: float) -> str:
    """按 HIF 等级阈值返回评价等级（最低为 F）。"""

    numeric = float(rating)
    for rank, threshold in HIF_TARGET_RATING_BY_RANK.items():
        if numeric >= threshold:
            return rank
    return 'F'


def calculate_hif_round2_star_gain(round2_score: float) -> int:
    """按 §6.1 的 starGainR2 表计算 R2 分数换算的基础スター性（向上取整，未乘亲爱度倍率）。"""

    return int(math.ceil(_piecewise_linear(round2_score, HIF_ROUND2_STAR_GAIN_SEGMENTS, HIF_ROUND2_STAR_GAIN_MAX) - 1e-9))


def calculate_hif_round1_rating(round1_score: float) -> int:
    """R1 原始分数（未乘 1.2）→ 評価値 贡献（向下取整）。"""

    return int(math.floor(_piecewise_linear(round1_score, HIF_ROUND1_RATING_SEGMENTS, HIF_ROUND1_RATING_MAX) + 1e-9))


def calculate_hif_round2_rating(round2_score: float) -> int:
    """R2 分数 → 評価値 贡献（向下取整）。"""

    return int(math.floor(_piecewise_linear(round2_score, HIF_ROUND2_RATING_SEGMENTS, HIF_ROUND2_RATING_MAX) + 1e-9))


def calculate_hif_produce_rating(
    *,
    params: tuple[float, float, float],
    star_quality_before_round2: float,
    round1_score: float,
    round2_score: float,
    star_gain_multiplier: float = HIF_ROUND2_STAR_GAIN_DEARNESS_MULTIPLIER,
    parameter_cap: float = HIF_PARAMETER_CAP_FOR_RATING,
) -> dict[str, Any]:
    """计算 H.I.F 本戦 的最终評価値与等级。

    公式（existing_engines.md §6.1，三方计算器一致）：
        r2StarGain = floor(starGainR2(round2) × 亲爱度倍率)
        statStar   = floor(Σmin(param, 3200) × 2 + (r2StarGain + min(star, 1110)) × 7.5)
        評価値     = statStar + r1Eval(round1) + r2Eval(round2) − 2000

    Args:
        params: 本戦结束时的三维属性。
        star_quality_before_round2: Round2 开始前的スター性（上限 1110）。
        round1_score: Round1 原始分数（未乘 1.2；gakumas-tools 输入的是 ×1.2 后的显示分再除回来）。
        round2_score: Round2 分数。
        star_gain_multiplier: R2 スター性获得倍率；社区计算器固定按亲爱度 37（+50%）计算。
        parameter_cap: 单项属性参与评价的上限（3000 + 面板 +200）。

    Returns:
        含各分项与等级的字典。
    """

    param_total = sum(min(max(float(value), 0.0), float(parameter_cap)) for value in params)
    round2_star_base = calculate_hif_round2_star_gain(round2_score)
    round2_star_gain = int(math.floor(round2_star_base * float(star_gain_multiplier) + 1e-9))
    star_before = min(max(float(star_quality_before_round2), 0.0), float(HIF_STAR_QUALITY_CAP_BEFORE_ROUND2))
    stat_star_rating = int(math.floor(param_total * HIF_PARAM_RATING_MULTIPLIER + (round2_star_gain + star_before) * HIF_STAR_RATING_MULTIPLIER + 1e-9))
    round1_rating = calculate_hif_round1_rating(round1_score)
    round2_rating = calculate_hif_round2_rating(round2_score)
    total = stat_star_rating + round1_rating + round2_rating - HIF_RATING_BASE_OFFSET
    return {
        'parameter_total': float(param_total),
        'star_quality_before_round2': float(star_before),
        'round2_star_gain_base': int(round2_star_base),
        'round2_star_gain': int(round2_star_gain),
        'final_star_quality': float(min(star_before + round2_star_gain, HIF_STAR_QUALITY_CAP)),
        'stat_star_rating': int(stat_star_rating),
        'round1_score': float(round1_score),
        'round1_adjusted_score': int(math.floor(float(round1_score) * HIF_ROUND1_SCORE_MULTIPLIER + 1e-9)),
        'round1_rating': int(round1_rating),
        'round2_score': float(round2_score),
        'round2_rating': int(round2_rating),
        'rating': int(total),
        'rank': get_hif_produce_rank(total),
    }


def calculate_hif_selection_rating(
    *,
    params: tuple[float, float, float],
    star_quality: float,
    parameter_cap: float = HIF_PARAMETER_CAP_FOR_RATING,
) -> dict[str, Any]:
    """計算 選抜試験（produce-007）结束时的暂定評価值。

    主数据与社区资料只给出本戦的評価値公式，選抜試験本身的结算画面公式未取得。
    这里沿用同一骨架（属性×2 + スター性×7.5 − 2000）但不含任何试验分数换算，
    作为训练奖励和结果摘要的稳定代理。
    # TODO(HIF-verify): 選抜試験 结算公式待实测确认。
    """

    param_total = sum(min(max(float(value), 0.0), float(parameter_cap)) for value in params)
    star = min(max(float(star_quality), 0.0), float(HIF_STAR_QUALITY_CAP))
    total = int(math.floor(param_total * HIF_PARAM_RATING_MULTIPLIER + star * HIF_STAR_RATING_MULTIPLIER + 1e-9)) - HIF_RATING_BASE_OFFSET
    return {
        'parameter_total': float(param_total),
        'star_quality': float(star),
        'rating': int(total),
        'rank': get_hif_produce_rank(total),
    }
