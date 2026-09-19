"""Transfer prepared inputs without eagerly unpickling their redundant raw graph.

The array input remains immediately available. Original immutable Python fields
are recovered losslessly only if a diagnostic or changed semantics needs them.
"""
import pickle
import zlib
from round2rl.encoding import Encoded


class CompactEncoded(Encoded):
    def __getattr__(self, name):
        state = object.__getattribute__(self, '__dict__')
        if name not in state.get('_deferred_fields', ()):
            raise AttributeError(name)
        restored = pickle.loads(zlib.decompress(state['_deferred_payload']))
        state.update(restored)
        del state['_deferred_fields'], state['_deferred_payload']
        return state[name]


def compact_prepared(encoded):
    """Copy metadata and prepared arrays; defer only the redundant raw fields."""
    if isinstance(encoded, CompactEncoded):
        return encoded
    if getattr(encoded, '_prepared_input', None) is None:
        return encoded
    immediate = {'phase', 'entity_count', 'action_entities', 'submissions', '_prepared_input'}
    state = vars(encoded)
    deferred = {key: value for key, value in state.items()
                if key not in immediate and key != '_relational_cached'}
    result = CompactEncoded.__new__(CompactEncoded)
    result.__dict__.update({key: value for key, value in state.items() if key in immediate})
    result._deferred_fields = tuple(deferred)
    result._deferred_payload = zlib.compress(pickle.dumps(deferred, protocol=5), level=1)
    return result
