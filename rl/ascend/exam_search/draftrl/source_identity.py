"""Source fingerprints for the waiting supervisor without importing torch."""
import hashlib
import json
from pathlib import Path


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def source_version():
    root=Path(__file__).resolve().parents[1]
    files=sorted((root/'draftrl').glob('*.py'))+[root/'train.py']
    files+=sorted((root/'draftrl').glob('*.mjs'))
    files+=sorted((root/'runtime/shared').rglob('*.py'))
    hashes = {p.relative_to(root).as_posix(): digest(p) for p in files}
    for candidate in (root.parents[1]/'training', root.parent/'training'):
        backend = candidate/'gakumas_training'
        if (backend/'device.py').is_file():
            for name in ('device.py', 'collectives.py'):
                hashes['shared_backend/'+name] = digest(backend/name)
            break
    else:
        raise FileNotFoundError('Cannot fingerprint the shared training backend')
    return hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
