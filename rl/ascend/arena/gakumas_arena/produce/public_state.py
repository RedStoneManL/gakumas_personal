"""Fresh, read-only produce observations at synchronous nested decision points.

This projection never enumerates menus, samples RNG, or exports retry anchors.
Execution frames contain public rule identities and progress, not Python locals.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict


@contextmanager
def public_resolution_frame(runtime, **frame):
    frames = getattr(runtime, '_public_resolution_frames', None)
    if frames is None:
        frames = runtime._public_resolution_frames = []
    frames.append(frame)
    try:
        yield frame
    finally:
        frames.pop()


def public_resolution(runtime):
    return {
        'frames': deepcopy(getattr(runtime, '_public_resolution_frames', [])),
        'blocked_source_classes': ['support_skill', 'memory_skill']
            if runtime._ability_chain_guard_depth > 0 else [],
    }


def live_public_state(runtime):
    """The resources here include costs already paid before a nested callback."""
    lifecycle = getattr(runtime, 'hif_lifecycle', None)
    events = runtime.events
    return {
        'schema_version': 'arena-public-produce-context/1',
        'produce_id': runtime.scenario.produce_id,
        'phase': runtime.pre_audition_phase,
        'state': deepcopy(runtime.state),
        'deck': deepcopy(runtime.deck),
        'drinks': deepcopy(runtime.drinks),
        'customize_item': runtime.customize_items.export(),
        'produce_items': [asdict(item) for item in runtime.active_produce_items],
        'support_skills': [asdict(skill) for skill in runtime.active_produce_skills],
        'exam_enchants': [asdict(spec) for spec in runtime.exam_status_enchant_specs],
        'lifecycle': lifecycle.public_state() if lifecycle else None,
        'eligible_support_events': events.eligible_support_events(),
        'completed_events': deepcopy(events.completed),
        'resolution': public_resolution(runtime),
    }


__all__ = ['live_public_state', 'public_resolution', 'public_resolution_frame']
