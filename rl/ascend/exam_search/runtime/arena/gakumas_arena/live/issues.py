"""公共补读分类；不改变 arena-live/1 的 Decision/SessionReport 字段。"""

from __future__ import annotations

from typing import Literal

from pydantic import ValidationError

from .contracts import WireModel


class LiveIssue(WireModel):
    """adapter 可按类别分流，unsupported 不应循环重新截图。"""
    version: Literal['arena-issues/1'] = 'arena-issues/1'
    category: Literal['observation', 'unsupported', 'resolution', 'contract']
    path: str
    next_action: Literal['collect_evidence', 'wait_engine_update', 'resolve_original_command', 'fix_contract']


def classify_issue(value: str | Exception) -> LiveIssue:
    """路径和协议异常的稳定分类；不进行截图、重试或恢复。"""
    path = str(value)
    if isinstance(value, Exception):
        category = 'contract'
    elif path.startswith('action_result.'):
        category = 'resolution'
    elif path.startswith(('contract.', 'run_setup.rules_revision', 'run_setup.masterdata_revision')):
        category = 'contract'
    elif path.startswith(('unsupported.', 'policy.')) or (path.startswith('arena.') and path != 'arena.legal_actions'):
        category = 'unsupported'
    else:
        category = 'observation'
    action = {'observation': 'collect_evidence', 'unsupported': 'wait_engine_update',
              'resolution': 'resolve_original_command', 'contract': 'fix_contract'}[category]
    return LiveIssue(category=category, path=path, next_action=action)


def classify_issues(value, *, command_state: str | None = None) -> tuple[LiveIssue, ...]:
    """接受 report/decision、MissingFields、异常或路径列表；submitted 可用公共状态补充分流。"""
    if command_state in {'submitted', 'uncertain'}:
        return (classify_issue('action_result.resolution'),)
    if isinstance(value, ValidationError):
        return tuple(classify_issue('contract.' + '.'.join(map(str, e['loc'])) + '.' + e['type'])
                     for e in value.errors(include_url=False))
    if hasattr(value, 'fields'):
        paths = value.fields
    elif isinstance(value, Exception):
        return (classify_issue(value),)
    elif hasattr(value, 'missing'):
        conflicts = getattr(value, 'conflicts', ()) or getattr(value, 'reasons', ())
        paths = (*value.missing, *(f'contract.conflict.{c}' for c in conflicts))
    else:
        paths = (value,) if isinstance(value, str) else value
    return tuple(classify_issue(p) for p in dict.fromkeys(paths))
