"""Opt-in public semantic side-view, shared by learners and spawned search workers.

The hot path only reads an offline, source-bound catalogue. No Node process,
engine step, private snapshot or random draw is permitted during enhancement.
"""
import copy
import os
import threading
from functools import lru_cache
from pathlib import Path

from .relational_training import validate_config

ENV = 'GAKUMAS_RELATIONAL_SEMANTICS'
_LOCK = threading.RLock()


def configure(config, setup):
    if not validate_config(config):
        os.environ.pop(ENV, None)
        return None
    path = Path(config['relational'].get('semantics_path', 'relational_semantics.json'))
    if not path.is_absolute():
        path = Path(setup) / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Prepare semantic catalogue before training: {path}; run prepare_relational.py')
    # Validate on every rank before learner startup. Spawn inherits this path.
    _compiler(str(path))
    os.environ[ENV] = str(path)
    return path


@lru_cache(maxsize=2)
def _compiler(path):
    from .native_semantics import NativeSemantics
    return NativeSemantics(cache_path=path)


def enabled():
    return bool(os.environ.get(ENV))


def _card(row):
    definition = row.get('definition', row.get('definition_metadata', {}))
    cid = row.get('definition_id', definition.get('id'))
    kind = row.get('entity_type')
    if kind != 'card' and not (kind == 'candidate' and row.get('action') == 'select_card'):
        return None
    if type(cid) is not int:
        raise ValueError('Public card has no native definition identity')
    return {'definition_id': cid, 'customizations': row.get('customizations', {}),
            'growth': row.get('growth', {})}


def program_strings(value):
    """Only explicit native-program fields; never parse display text as code."""
    if isinstance(value, dict):
        for key, part in value.items():
            if key in ('conditions', 'cost', 'actions', 'effects', 'declaration') and isinstance(part, str):
                yield part
            elif isinstance(part, (dict, list)):
                yield from program_strings(part)
    elif isinstance(value, list):
        for part in value:
            yield from program_strings(part)


def view(encoded):
    """Enhance once per immutable observation; never mutate legacy atoms/edges."""
    path = os.environ.get(ENV)
    if not path:
        return getattr(encoded, 'relational_view', None)
    cached = getattr(encoded, '_relational_cached', None)
    if cached is not None and cached[0] == path:
        return cached[1]
    from .relational_encoding import reconstruct_nodes, enhance, SCHEMA
    compiler = _compiler(path)
    rows = reconstruct_nodes(encoded)
    context = copy.deepcopy(getattr(encoded, 'relation_context', {}))
    context.update(schema=SCHEMA, native_semantics_version=compiler.version)
    previews = {}
    for index, row in enumerate(rows):
        card = _card(row)
        if card is not None:
            # Temporary support can change both programs and traits. Its public
            # runtime effective program is authoritative; static traits are not.
            if not row.get('temporary_support'):
                previews[str(index)] = compiler.card(card)
    context['card_previews'] = previews
    context['program_asts'] = {text: compiler.program(text)
                               for text in dict.fromkeys(program_strings(rows))}
    guidance = {}
    for position, command in enumerate(encoded.submissions):
        if command.get('method') != 'guide_card':
            continue
        action_entity = encoded.action_entities[position]
        targets = {dst for src, dst, label in encoded.edges
                   if src == action_entity and label == 'out:target_card'}
        if len(targets) != 1:
            raise ValueError('Guidance action must have exactly one public target')
        target = targets.pop()
        before = _card(rows[target])
        if before is None:
            raise ValueError('Guidance target is not a card')
        after = copy.deepcopy(before)
        after['customizations'][str(command['customization_id'])] = command['level']
        guidance[str(position)] = {'before': compiler.card(before), 'after': compiler.card(after)}
    context['guidance_previews'] = guidance
    # Keep provenance context small on the original record/cache key. A shallow
    # observation copy supplies the fully resolved tree only to this side-view.
    shadow = copy.copy(encoded)
    shadow.relation_context = context
    result = enhance(shadow)
    with _LOCK:
        encoded._relational_cached = (path, result)
    return result
