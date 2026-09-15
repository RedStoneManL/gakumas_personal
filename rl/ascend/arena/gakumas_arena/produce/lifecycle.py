"""HIF produce attempts, retries, terminal outcomes and transaction boundaries.

Ranking and score conversion belong to the exam/scoring adapter. This module
only consumes its rank/cleared result. Internal anchors contain hidden RNG and
must never be included in a policy observation.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import asdict

from . import checkpoint as cp


class HifLifecycleError(ValueError):
    pass


_CALLABLE = '__arena_in_process_callable__'


def _separate_callables(value, references):
    if callable(value):
        references.append(value)
        return {_CALLABLE: len(references) - 1}
    if isinstance(value, dict):
        result = copy(value)
        result.clear()
        result.update({k: _separate_callables(v, references) for k, v in value.items()})
        return result
    if isinstance(value, (list, tuple)):
        return type(value)(_separate_callables(v, references) for v in value)
    return value


def _reattach_callables(value, references):
    if isinstance(value, dict):
        if set(value) == {_CALLABLE}:
            return references[value[_CALLABLE]]
        result = copy(value)
        result.clear()
        result.update({k: _reattach_callables(v, references) for k, v in value.items()})
        return result
    if isinstance(value, (list, tuple)):
        return type(value)(_reattach_callables(v, references) for v in value)
    return value


def _capture_execution(run, *, include_lifecycle=False, include_run=False):
    """In-process transaction image; unlike public snapshot it never samples UI."""
    rt = run.runtime
    helpers = {}
    for name, excluded in cp._HELPERS.items():
        if name == 'hif_lifecycle' and not include_lifecycle:
            continue
        helper = getattr(rt, name, None)
        if helper is not None:
            helpers[name] = {k: v for k, v in vars(helper).items() if k not in excluded}
    state = {'runtime': {k: v for k, v in vars(rt).items() if k not in cp._STATIC_RUNTIME},
             'helpers': helpers, 'customize_item': rt.customize_items.export(),
             'rng': rt.np_random.bit_generator.state}
    if include_run:
        state['run'] = {key: getattr(run, key) for key in cp._RUN_FIELDS}
    # In-process fault recovery must keep monkeypatched/test callbacks by
    # reference. They are deliberately not made serializable: public snapshot
    # still rejects arbitrary callbacks in execution state.
    callbacks = []
    separated = _separate_callables(state, callbacks)
    return {'execution': cp._encode(separated), 'external_callables': callbacks}


def _restore_execution(run, encoded, *, keep_rng=False):
    # Only called with this module's own already-validated capture or a public
    # checkpoint whose complete structure was validated before restoration.
    data = _reattach_callables(cp._decode(deepcopy(encoded['execution'])), encoded.get('external_callables', []))
    rt = run.runtime
    for key in set(vars(rt)) - cp._STATIC_RUNTIME - set(data['runtime']):
        delattr(rt, key)
    for key, value in data['runtime'].items():
        setattr(rt, key, value)
    for name, state in data['helpers'].items():
        for key in set(vars(getattr(rt, name))) - cp._HELPERS[name] - set(state):
            delattr(getattr(rt, name), key)
        for key, value in state.items():
            setattr(getattr(rt, name), key, value)
    rt.customize_items.restore(data['customize_item'])
    # Empty custom-item restore must not drop its diagnostic history.
    rt.customize_items.history = deepcopy(data['customize_item'].get('history', []))
    if not keep_rng:
        rt.np_random.bit_generator.state = data['rng']
    for key, value in data.get('run', {}).items():
        setattr(run, key, value)


class HifProduceLifecycle:
    """One produce's three (selection) or two (finals) accepted exam slots.

    ``retry_ticket_count=None`` explicitly models sufficient external tickets.
    A finite wallet and ``free_retries_remaining`` model account limits without
    consuming anything outside this local simulator. Three per-produce retries
    come from master data; the same budget is shared by all slots in this run.
    """
    SCHEMA_VERSION = 'arena-hif-lifecycle/1'
    TERMINAL = frozenset({'failed', 'abandoned', 'selection_clear', 'final_clear', 'prima_stella'})

    def __init__(self, run, config=None):
        self.run = run
        self.runtime = run.runtime
        if self.runtime.hif is None:
            raise HifLifecycleError('HIF lifecycle requires an HIF scenario')
        self.config = deepcopy(config or {})
        for key in ('retry_ticket_count', 'free_retries_remaining'):
            value = self.config.get(key, 0 if key == 'free_retries_remaining' else None)
            if key == 'free_retries_remaining' and value is None:
                raise HifLifecycleError('free_retries_remaining must be a nonnegative integer')
            if value is not None and (type(value) is not int or value < 0):
                raise HifLifecycleError(f'{key} must be a nonnegative integer or null')
        self.config.setdefault('retry_ticket_count', None)
        self.config.setdefault('free_retries_remaining', 0)
        self.ticket_count = self.config['retry_ticket_count']
        self.free_retries_remaining = self.config['free_retries_remaining']
        self.initial_continue_count = int(self.runtime.produce_setting.get('continueCount') or 0)
        self.status = 'active'
        self.pending_result = None
        self.pending_stage = None
        self.attempts = []
        self.accepted_results = []
        self.retries_used = 0
        self._anchor = None
        self._last_continue_remaining = self.remaining_retries
        self._terminal_artifact = None
        self.runtime.hif_lifecycle = self
        run.lifecycle = self

    @property
    def remaining_retries(self):
        return max(0, int(self.runtime.state.get('continue_remaining') or 0))

    @property
    def terminal(self):
        return self.status in self.TERMINAL

    def can_retry(self):
        return (self.status == 'pending_result' and self.pending_result is not None
                and self.remaining_retries > 0
                and (self.free_retries_remaining > 0 or self.ticket_count is None or self.ticket_count > 0))

    def before_exam(self, stage_type):
        """Hook before *all* audition phase effects; runtime already charges retry.

        A retry restores its own exam's initial gameplay state (including drink
        inventory, one-shot buffs and activation counters), retains the newly
        consumed retry and advances the existing RNG stream. Round 2's anchor is
        after the interval: retrying it cannot reset Round 1 or interval buys.
        """
        if self.terminal or self.status == 'running_exam':
            raise HifLifecycleError('Cannot start an exam in this lifecycle state')
        if stage_type not in self.runtime.scenario.audition_sequence:
            raise HifLifecycleError(f'Unknown HIF exam stage: {stage_type}')
        sequence = self.runtime.scenario.audition_sequence
        slot = int(self.runtime.state.get('audition_index') or 0)
        if slot >= len(sequence) or slot < 0 or stage_type != sequence[slot]:
            raise HifLifecycleError('Exam stage does not match the next unaccepted HIF slot')
        if self._anchor is None:
            if self.pending_result is not None:
                raise HifLifecycleError('An unaccepted attempt must have its retry anchor')
            self._anchor = _capture_execution(self.run)
            self.pending_stage = stage_type
            self._last_continue_remaining = self.remaining_retries
        else:
            if self.status != 'pending_result' or stage_type != self.pending_stage:
                raise HifLifecycleError('Accept the pending exam before starting another stage')
            remaining = self.remaining_retries
            if self._last_continue_remaining <= 0 or remaining != self._last_continue_remaining - 1:
                raise HifLifecycleError('Retry must consume exactly one remaining continue')
            if self.free_retries_remaining <= 0 and self.ticket_count is not None and self.ticket_count <= 0:
                raise HifLifecycleError('No free retry or retry ticket remains')
            # _run_audition's caller still reads these to write the replacement
            # pending result. Do not restore the first-attempt control envelope.
            envelope = {name: deepcopy(getattr(self.runtime, name)) for name in
                        ('pending_audition_stage', 'pending_audition_result', 'pre_audition_phase')}
            _restore_execution(self.run, self._anchor, keep_rng=True)
            for name, value in envelope.items():
                setattr(self.runtime, name, value)
            self.runtime.state['continue_remaining'] = float(remaining)
            self._last_continue_remaining = remaining
            if self.free_retries_remaining > 0:
                self.free_retries_remaining -= 1
            elif self.ticket_count is not None:
                self.ticket_count -= 1
            self.retries_used += 1
            self.attempts[-1]['resolution'] = 'replaced_by_retry'
        self.status = 'running_exam'
        self.pending_result = None

    def after_attempt(self, result):
        if self.status != 'running_exam' or result.get('stage_type') != self.pending_stage:
            raise HifLifecycleError('Attempt result does not match the running exam')
        if type(result.get('cleared')) is not bool or int(result.get('rank') or 0) < 1:
            raise HifLifecycleError('Exam adapter must provide rank and boolean cleared')
        self.pending_result = deepcopy(result)
        self.status = 'pending_result'
        self.attempts.append({'attempt_id': len(self.attempts), 'stage_type': self.pending_stage,
                              'result': deepcopy(result), 'resolution': 'pending'})

    def accepted(self, result):
        """Hook after runtime has applied exactly one accepted exam outcome."""
        if (self.status != 'pending_result' or self.pending_result is None
                or result.get('stage_type') != self.pending_stage):
            raise HifLifecycleError('There is no matching pending result to accept')
        for key in ('exam_score', 'effective_score', 'rank', 'cleared'):
            if result.get(key) != self.pending_result.get(key):
                raise HifLifecycleError(f'Accepted result differs from latest attempt: {key}')
        self.attempts[-1]['resolution'] = 'accepted'
        self.accepted_results.append(deepcopy(self.pending_result))
        self.pending_result = None
        self.pending_stage = None
        self._anchor = None
        if not result['cleared']:
            self.status = 'failed'
        elif len(self.runtime.audition_history) >= len(self.runtime.scenario.audition_sequence):
            if self.runtime.hif.is_selection:
                self.status = 'selection_clear'
            else:
                self.status = 'prima_stella' if self.runtime.state.get('hif_prima_stella') else 'final_clear'
        else:
            self.status = 'active'
        if self.terminal:
            self._terminal_artifact = self._build_artifact()

    @contextmanager
    def atomic_step(self):
        """Rollback environment/RNG/audits on faults; callback-owned state is external."""
        before = _capture_execution(self.run, include_lifecycle=True, include_run=True)
        try:
            yield
        except Exception:
            _restore_execution(self.run, before)
            raise

    def abandon(self, *, reason='agent_retire'):
        """Explicit retire at a produce decision boundary, without game rewards."""
        if self.terminal or self.run.fault or self.status == 'running_exam':
            raise HifLifecycleError('Retire requires an active produce decision boundary')
        rt = self.runtime
        if rt._ability_chain_guard_depth:
            raise HifLifecycleError('Cannot retire in an effect chain')
        with self.atomic_step():
            if self.pending_result is not None:
                self.attempts[-1]['resolution'] = 'discarded_by_retire'
            self.status = 'abandoned'
            self.pending_result = None
            self.pending_stage = None
            self._anchor = None
            rt.pending_audition_result = None
            rt.pending_audition_stage = None
            rt.pre_audition_phase = 'terminal'
            rt.state['failed'] = True
            rt.state['retired'] = True
            rt._set_final_summary(cleared=False)
            rt.final_summary.update({'ending_type': 'abandoned', 'retire_reason': str(reason),
                                     'memory_generated': False, 'counts_as_produce_attempt': False})
            rt.final_summary['ending']['type'] = 'abandoned'
            self.run.terminated = True
            self._terminal_artifact = self._build_artifact()
            self.run.revision += 1
            self.run._observation = None
        return deepcopy(self._terminal_artifact)

    def require_selection_memory(self):
        """Use at the public export gate; checkpoint/debug captures remain separate."""
        if (not self.runtime.hif.is_selection or self.status != 'selection_clear'
                or not self.runtime.final_summary.get('route_clear')):
            raise HifLifecycleError('Selection memory requires all three accepted exams to clear')

    def _build_artifact(self):
        rt = self.runtime
        return {'schema_version': 'arena-hif-terminal-artifact/1', 'produce_id': rt.scenario.produce_id,
                'outcome': self.status, 'normal_terminal': True,
                'selection_memory_eligible': self.status == 'selection_clear',
                'counts_as_produce_attempt': self.status != 'abandoned',
                'game_memory_reward_on_retire': False,
                'state': deepcopy(rt.state), 'deck': deepcopy(rt.deck), 'drinks': deepcopy(rt.drinks),
                'produce_items': [asdict(item) for item in rt.active_produce_items],
                'customize_item': rt.customize_items.export(),
                'summary': deepcopy(rt.final_summary), 'accepted_exams': deepcopy(self.accepted_results),
                'attempts': deepcopy(self.attempts), 'retries_used': self.retries_used,
                'purpose': 'RL terminal result and retained diagnostics; not a generated game memory'}

    def terminal_artifact(self):
        if not self.terminal:
            raise HifLifecycleError('No terminal artifact before completion or retire')
        return deepcopy(self._terminal_artifact)

    def public_state(self):
        return {'schema_version': self.SCHEMA_VERSION, 'status': self.status,
                'remaining_retries': self.remaining_retries, 'retries_used': self.retries_used,
                'retry_available': self.can_retry(), 'free_retries_remaining': self.free_retries_remaining,
                'retry_ticket_count': self.ticket_count,
                'ticket_model': 'external-sufficient-tickets' if self.ticket_count is None else 'configured-wallet',
                'accepted_exam_count': len(self.accepted_results), 'attempt_count': len(self.attempts),
                'pending_result': deepcopy(self.pending_result),
                'retire_available': not self.terminal and not self.run.fault and self.status != 'running_exam',
                'selection_memory_eligible': self.status == 'selection_clear',
                'retry_resource_model': 'restore-pre-exam-gameplay; advance-RNG/v1',
                'account_achievement_aggregation': 'attempt-log-only; no external account mutation'}

    def validate_checkpoint_state(self, state):
        """Validate without changing this live object; used before restore commits."""
        if set(state) != set(vars(self)) - {'run', 'runtime'}:
            raise HifLifecycleError('Incomplete lifecycle checkpoint fields')
        if state.get('config') != self.config:
            raise HifLifecycleError('Lifecycle checkpoint configuration mismatch')
        if state.get('status') not in self.TERMINAL | {'active', 'pending_result'}:
            raise HifLifecycleError('Lifecycle checkpoint is not a decision boundary')
        for key in ('initial_continue_count', 'retries_used', 'free_retries_remaining', '_last_continue_remaining'):
            if type(state[key]) is not int or state[key] < 0:
                raise HifLifecycleError(f'Invalid lifecycle checkpoint {key}')
        if state['initial_continue_count'] != self.initial_continue_count or state['retries_used'] > self.initial_continue_count:
            raise HifLifecycleError('Lifecycle checkpoint exceeds continue budget')
        if state['ticket_count'] is not None and (type(state['ticket_count']) is not int or state['ticket_count'] < 0):
            raise HifLifecycleError('Invalid lifecycle checkpoint ticket count')
        if not isinstance(state['attempts'], list) or not isinstance(state['accepted_results'], list):
            raise HifLifecycleError('Invalid lifecycle checkpoint result log')
        if state['status'] == 'pending_result':
            if not state['_anchor'] or not state['pending_result'] or not state['attempts']:
                raise HifLifecycleError('Pending retry checkpoint requires its original exam anchor')
        elif state['_anchor'] is not None or state['pending_result'] is not None:
            raise HifLifecycleError('Non-pending lifecycle checkpoint retains an exam anchor')


__all__ = ['HifLifecycleError', 'HifProduceLifecycle']
