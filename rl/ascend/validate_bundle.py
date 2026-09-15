"""Local, bounded relocation/training/resume acceptance for the exported bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--extra-site-packages', type=Path)
    p.add_argument('--skip-search-training', action='store_true')
    args = p.parse_args()
    here = Path(__file__).resolve().parent
    workspace = here.parents[1]
    archive = workspace/'rl/training/artifacts/ascend/gakumas-ascend-training.zip'
    sys.path.insert(0, str(workspace/'rl/training/colab'))
    from bootstrap import extract_verified_bundle
    root, manifest, digest = extract_verified_bundle(archive, here/'artifacts')
    output = here/'artifacts'/('validation-'+root.name)
    output.mkdir()
    persistent = output/'persistent'
    persistent.mkdir()
    report = {'passed': False, 'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
              'manifest_sha256': digest, 'bundle_root': str(root), 'output': str(output), 'steps': []}
    evidence = here/'artifacts/relocated-validation.json'

    def invoke(label, script, arguments):
        program = 'import sys,runpy; '
        if args.extra_site_packages:
            program += f'sys.path.append({str(args.extra_site_packages.resolve())!r}); '
        program += f'sys.argv={[str(script), *arguments]!r};runpy.run_path({str(script)!r},run_name="__main__")'
        started = time.monotonic()
        log = output/(label+'.log')
        print(label, 'started', flush=True)
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', program], cwd=root,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=1200)
        report['steps'].append({'name': label, 'exit_code': result.returncode,
                               'seconds': time.monotonic()-started, 'log': str(log)})
        evidence.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        if result.returncode:
            print(log.read_text(encoding='utf-8')[-4500:], flush=True)
            raise RuntimeError(label+' failed')
        print(label, 'passed', flush=True)

    try:
        invoke('portable-regressions', root/'ascend/run_tests.py', [])
        invoke('dashboard-regressions', root/'dashboard/test_portable.py', [])
        invoke('native-search', root/'ascend/preflight_search.py',
               ['--device', 'cpu', '--output', str(output/'native-search.json')])
        config = json.loads((root/'training/gakumas_training/configs/full_produce.json').read_text())
        config.update(workers=2, episodes_per_update=2, eval_episodes=1)
        config['model'].update(width=16, token_dim=4)
        config['ppo'].update(epochs=1, minibatch_size=16, microbatch_size=1)
        config_path = output/'full-config.json'
        config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
        for session in (1, 2):
            invoke(f'full-session-{session}', root/'ascend/train_full.py', [
                '--world-size', '1', '--bundle-root', str(root), '--config', str(config_path),
                '--task', 'full_produce', '--run-name', 'full-smoke',
                '--local-root', str(output/f'scratch-{session}'), '--persistent-root', str(persistent),
                '--max-updates', '1', '--allow-cpu-smoke'])
        import torch
        checkpoint = output/'scratch-2/full-smoke/checkpoints/latest.pt'
        state = torch.load(checkpoint, map_location='cpu', weights_only=True)
        if state['iteration'] != 2 or state['episodes_seen'] != 4 or state['seed_cursor'] != config['seed']+4:
            raise ValueError('Restored full-produce checkpoint cursor differs')
        report['full_produce'] = {k: state[k] for k in ('iteration', 'episodes_seen', 'seed_cursor', 'learner_world_size')}
        if not args.skip_search_training:
            c = json.loads((root/'ascend/configs/search_smoke.json').read_text())
            c['device'] = 'cpu'
            path = output/'search-config.json'
            path.write_text(json.dumps(c), encoding='utf-8')
            invoke('search-training', root/'exam-search/train.py', ['--config', str(path), '--initial', str(root/'checkpoints/latest.pt'), '--output', str(output/'search-run')])
            # Same source/config and completed checkpoint; no further update
            # because the intentionally bounded max_batches is already reached.
            invoke('search-resume', root/'exam-search/train.py', ['--config', str(path), '--output', str(output/'search-run'), '--resume'])
            info = torch.load(output/'search-run/latest.pt', map_location='cpu', weights_only=True)
            if info['batches'] != 1:
                raise ValueError('Unexpected search update count after resume')
            report['search'] = {k: info[k] for k in ('batches', 'decisions', 'next_episode_index')}
        report['passed'] = True
    finally:
        evidence.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
