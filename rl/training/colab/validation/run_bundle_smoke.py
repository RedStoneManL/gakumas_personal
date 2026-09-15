"""Local bounded integration acceptance; never launches a long training run."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--microbatch', type=int, default=4)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[4]
    colab = workspace / 'rl/training/colab'
    sys.path.insert(0, str(colab))
    from bootstrap import extract_verified_bundle
    target = workspace / 'rl/training/artifacts/colab'
    archive = target / 'gakumas-colab-training.zip'
    root, manifest, manifest_hash = extract_verified_bundle(archive, target)
    run_root = target / ('acceptance-' + root.name)
    run_root.mkdir()
    persistent = run_root / 'mounted-drive'
    persistent.mkdir()
    effective = json.loads((root / 'configs/full_produce_setup_mixed.json').read_text(encoding='utf8'))
    effective['workers'] = args.workers
    effective['ppo']['microbatch_size'] = args.microbatch
    config_path = run_root / 'effective-config.json'
    config_path.write_text(json.dumps(effective, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    report = {'schema': 'gakumas-colab-local-acceptance/1', 'passed': False,
              'actual_colab_tested': False, 'platform': sys.platform,
              'bundle_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'manifest_sha256': manifest_hash, 'relocated_root': str(root),
              'run_root': str(run_root), 'workers': args.workers,
              'microbatch_size': args.microbatch, 'steps': []}
    report_path = colab / 'validation/relocated-training.json'
    environment = dict(os.environ, PYTHONUTF8='1', PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1')
    python = workspace / 'third_party/gakumas_arena/.venv/Scripts/python.exe'
    dependencies = workspace / 'rl/round2/.venv/Lib/site-packages'
    def invoke(label, script, args):
        # Source and Arena are imported only from the relocated verified bundle.
        execute = ('runpy.run_module("gakumas_training",run_name="__main__")' if script.name == '__main__.py'
                   else f'runpy.run_path({str(script)!r},run_name="__main__")')
        code = ('import sys,runpy; '
                f'sys.path.append({str(dependencies)!r}); '
                f'sys.path.insert(0,{str(root / "colab")!r}); '
                f'sys.path.insert(0,{str(root / "training")!r}); '
                f'sys.argv=[{str(script)!r}]+{args!r}; '
                + execute)
        logfile = run_root / (label + '.log')
        started = time.monotonic()
        print(label, 'started', str(logfile), flush=True)
        with logfile.open('w', encoding='utf-8') as stream:
            result = subprocess.run([str(python), '-B', '-c', code], cwd=root,
                                    env=environment, stdout=stream, stderr=subprocess.STDOUT,
                                    timeout=1800)
        report['steps'].append({'name': label, 'exit_code': result.returncode,
                                'seconds': time.monotonic() - started, 'log': str(logfile)})
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
        if result.returncode:
            print(logfile.read_text(encoding='utf-8')[-7000:])
            raise RuntimeError(f'{label} failed with {result.returncode}')
        print(label, 'passed', flush=True)
    try:
        for index in (1, 2):
            invoke(f'gpu-session-{index}', root / 'colab/run_training.py', [
                '--bundle-root', str(root), '--config', str(config_path),
                '--task', 'full_produce', '--run-name', 'setup-mixed-gpu-smoke',
                '--local-root', str(run_root / f'local-session-{index}'),
                '--persistent-root', str(persistent), '--total-hours', '24', '--session-hours', '8',
                '--max-updates', '1'])
        checkpoint = run_root / 'local-session-2/setup-mixed-gpu-smoke/checkpoints/latest.pt'
        invoke('held-out-evaluation', root / 'training/gakumas_training/__main__.py', [
            '--task', 'full_produce', '--config', str(config_path),
            '--output', str(run_root / 'held-out'), '--arena-root', str(root / 'arena'),
            '--evaluate', '--checkpoint', str(checkpoint), '--episodes', '10'])
        # Final proof reads metadata only; torch weights were validated by resume.
        run = persistent / 'setup-mixed-gpu-smoke'
        latest = json.loads((run / 'latest.json').read_text())
        state = json.loads((run / 'snapshots' / latest['snapshot'] / 'colab-state.json').read_text())
        assert state['iteration'] == 2 and state['episodes_seen'] == 20
        assert state['seed_cursor'] == 92000020 and state['active_wall_seconds'] > 0
        evaluation = json.loads((run_root / 'held-out/full_produce/evaluation/metrics.jsonl').read_text().splitlines()[-1])
        assert len(evaluation['loadout_profiles']) == 5
        assert set(evaluation['setup_modes']) == {'given', 'select'}
        for profile in evaluation['loadout_profiles'].values():
            assert set(profile['setup_modes']) == {'given', 'select'}
        report.update(passed=True, final_state=state, evaluation=evaluation,
                      restored_into_fresh_local_directory=True, checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())
    finally:
        report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
