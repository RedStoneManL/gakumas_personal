"""Check v3's packaged CLI against an existing real full-produce checkpoint.

The tiny time budget is already exhausted by the source run, so no new game or
optimizer update is launched. The source is only read, and target paths are new.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

workspace = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(workspace / 'rl/training/colab'))
from bootstrap import extract_verified_bundle

artifacts = workspace / 'rl/training/artifacts/colab'
archive = artifacts / 'gakumas-colab-training-v3.zip'
root, manifest, manifest_hash = extract_verified_bundle(archive, artifacts)
output = Path(tempfile.mkdtemp(prefix='v3-migration-check-', dir=artifacts))
persistent = artifacts / 'acceptance-hif-training-muhx3bu0/mounted-drive'
source_name = 'setup-mixed-gpu-smoke'
target_name = output.name
source_dir = persistent / source_name
hashes = lambda: {p.relative_to(source_dir).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in source_dir.rglob('*') if p.is_file()}
before = hashes()
config = json.loads((root / 'configs/full_produce_setup_mixed.json').read_text())
config['workers'] = 10
config['ppo']['microbatch_size'] = 16
config_path = output / 'config.json'
config_path.write_text(json.dumps(config))
arguments = ['--bundle-root', str(root), '--config', str(config_path), '--task', 'full_produce',
             '--run-name', target_name, '--migrate-from-run', source_name,
             '--local-root', str(output / 'scratch'), '--persistent-root', str(persistent),
             '--total-hours', '.00001', '--session-hours', '.00001']
script = root / 'colab/run_training.py'
code = ('import sys,runpy; '
        f'sys.path.append({str(workspace / "rl/round2/.venv/Lib/site-packages")!r}); '
        f'sys.path[:0]=[{str(root / "colab")!r},{str(root / "training")!r}]; '
        f'sys.argv=[{str(script)!r}]+{arguments!r}; '
        f'runpy.run_path({str(script)!r},run_name="__main__")')
environment = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1')
passes = []
for attempt in (1, 2):
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=root, env=environment,
                            text=True, encoding='utf8', stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=90)
    (output / f'attempt-{attempt}.log').write_text(result.stdout, encoding='utf8')
    if result.returncode:
        print(result.stdout[-8000:])
        result.check_returncode()
    passes.append({'attempt': attempt, 'exit_code': result.returncode})
    print('Packaged real-checkpoint migration/resume passed:', attempt, flush=True)
if hashes() != before:
    raise AssertionError('Source run files changed')
report = {'passed': True, 'actual_colab_tested': False, 'new_episodes_or_updates': 0,
          'bundle_manifest_sha256': manifest_hash, 'source_run_name': source_name,
          'target_run_name': target_name, 'source_files_unchanged': True,
          'attempts': passes, 'output': str(output)}
(workspace / 'rl/training/colab/validation/v3-packaged-migration.json').write_text(
    json.dumps(report, indent=2) + '\n', encoding='utf8')
print(json.dumps(report, indent=2))
