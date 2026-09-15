from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math

from ...contracts import Episode
from ...arena_adapter import DecisionRecorder, choose_exam


@dataclass
class ExamScoreConfig:
    entry: dict | None = None
    max_decisions: int = 2000


class ExamScoreTask:
    name = 'exam_score'

    def __init__(self, config: ExamScoreConfig | None = None, *, arena_root=None):
        from ...arena_adapter.environment import ensure_arena
        self.arena_root = ensure_arena(arena_root)
        self.config = config or ExamScoreConfig()
        if self.config.max_decisions < 1:
            raise ValueError('max_decisions must be positive')

    @property
    def arena_version(self):
        from ...arena_adapter.environment import arena_version
        return arena_version(self.arena_root)

    def close(self):
        from ...arena_adapter.environment import close_arena
        close_arena()

    def run_episode(self, policy, *, seed: int, policy_version: int) -> Episode:
        from gakumas_arena.engine.training import TrainingExam, hif_round2_entry
        entry = deepcopy(self.config.entry) if self.config.entry is not None else hif_round2_entry()
        exam = TrainingExam(entry, seed=seed)
        recorder = DecisionRecorder(self.name, policy, policy_version)
        observation = exam.observe()
        for _ in range(self.config.max_decisions):
            if observation['result']['terminated']:
                break
            def execute():
                def context(resolution):
                    return {'produce': None, 'exam': deepcopy(observation), 'resolution': resolution,
                            'mechanisms': []}
                action = choose_exam(recorder, observation, context)
                return (exam.choose(action, decision_version=observation['decision_version'])
                        if observation['choice'] else exam.act(action))
            observation = recorder.transaction(execute)
        result = observation['result']
        if not result['terminated'] or result.get('truncated'):
            raise RuntimeError('Exam exceeded decision limit; no terminal sample generated')
        score = result['final_score']
        if score is None or not math.isfinite(score):
            raise ValueError('Arena did not produce a finite final exam score')
        return Episode(self.name, seed, recorder.transitions, float(score), 'normal', {
            'objective': 'raw_final_exam_score/1', 'policy_version': policy_version,
            'arena_version': deepcopy(observation['version']), 'entry_preset': entry.get('preset'),
            'result': deepcopy(result), 'terminal_observation': deepcopy(observation),
        })
