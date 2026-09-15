"""Evidence-backed effective catalogue; the pinned vendor remains untouched."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


OVERRIDES = Path(__file__).resolve().parents[1] / 'content/native_catalogue_overrides.json'
DATA = Path(__file__).resolve().parents[1] / '_vendor/gakumas_tools/packages/gakumas-data/json'


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def load_catalogue_overrides():
    data = json.loads(OVERRIDES.read_text(encoding='utf-8'))
    if data.get('schema_version') != 'arena-native-catalogue-overrides/1':
        raise ValueError('Unsupported effective catalogue override schema')
    if len({row['native_card_id'] for row in data['cards']}) != len(data['cards']):
        raise ValueError('Duplicate effective catalogue override card')
    return data


def apply_catalogue_overrides(cards):
    """Apply checked availability changes to copies of raw JSON card rows."""
    data = load_catalogue_overrides()
    result = deepcopy(cards)
    by_id = {row['id']: row for row in result}
    native_customizations = {row['id']: row for row in
        json.loads((DATA / 'customizations.json').read_text(encoding='utf-8'))}
    for patch in data['cards']:
        card = by_id.get(patch['native_card_id'])
        if (patch['field'] != 'availableCustomizations' or card is None
                or _digest(card) != patch['raw_card_sha256']
                or card['availableCustomizations'] != patch['before']):
            raise ValueError(f"Effective catalogue raw source mismatch: card {patch['native_card_id']}")
        custom = native_customizations.get(patch['effective_customization_id'])
        if custom is None or _digest(custom) != patch['effective_customization_sha256']:
            raise ValueError(f"Effective catalogue customization source mismatch: {patch['effective_customization_id']}")
        card['availableCustomizations'] = patch['after']
        if _digest(card) != patch['effective_card_sha256']:
            raise ValueError(f"Effective catalogue output mismatch: card {patch['native_card_id']}")
    return result


def catalogue_override_provenance(native_card_id):
    """Return raw/effective hashes and evidence for a corrected card, if any."""
    data = load_catalogue_overrides()
    patch = next((row for row in data['cards'] if row['native_card_id'] == native_card_id), None)
    if patch is None:
        return None
    return {'schema_version': data['schema_version'], 'rules_version': data['rules_version'],
            'manifest_sha256': sha256(OVERRIDES.read_bytes()).hexdigest(), **deepcopy(patch)}


__all__ = ['apply_catalogue_overrides', 'catalogue_override_provenance', 'load_catalogue_overrides']
