"""Paired fixed-loadout development probe, isolated from PPO and model selection."""
import copy
import hashlib
import json
import random
import statistics
from pathlib import Path
import torch
from gakumas_training.device import preserve_rng
from .checkpoint import json_write
from .practice import retained_metadata
from .bank_rollout import rollout_bank
from . import keycard_focus as focus


def check(pool, model, config, catalog, device, output, batches, rollout, choose, checkpoint, publish):
    if config.get('skip_keycard_diagnostic', False):
        return
    cfg = focus.settings(config)
    if not cfg.get('enabled'):
        return
    start, end = cfg['start_batch'], cfg['start_batch'] + cfg['batches']
    output = Path(output)
    before_path, after_path = output/'keycard-before.json', output/'keycard-after.json'
    if before_path.exists() and (batches < end or after_path.exists()):
        return
    if not before_path.exists() and batches != start:
        raise ValueError('Missing pre-practice baseline; cannot compare a later policy as the before policy')
    label = 'keycard-before' if not before_path.exists() else 'keycard-after'
    publish('keycard_probe', keycard_stage=label)
    probe_config = {**config, '_policy_version': config['_policy_version'],
                    '_keycard_probe': True, 'workers': min(config['workers'], 10),
                    '_profiles': [p for p in config['_profiles'] if p['id'] == focus.PROFILE]}
    saved_random = random.getstate()
    try:
        with preserve_rng():
            suite_path = output/'keycard-suite.json'
            if suite_path.exists():
                suite = json.loads(suite_path.read_text(encoding='utf8'))
                # Same inference grouping for before and after, including if the
                # user changed the resource preset between measurements.
                if config['workers'] < suite['workers']:
                    raise ValueError('Keycard paired probe needs its original worker count')
                probe_config['workers'] = suite['workers']
            else:
                _, rows, _, _ = rollout(pool, model, None, catalog, probe_config, device,
                    1_870_000_000, count=12, greedy=True, keep_entries=True,
                    log_path=output/'keycard-suite-construction.jsonl')
                tasks = []
                for i, row in enumerate(rows):
                    if not row['keycard_usage']['forced_present']:
                        raise ValueError('Diagnostic loadout lacks the nominated card')
                    for j in range(4):
                        meta = retained_metadata(row)
                        meta.update(exploration_mode='normal', keycard_loadout_id=i)
                        tasks.append({'key': row['entry_sha256'], 'entry': copy.deepcopy(row['entry']),
                                      'metadata': meta, 'replay_seed': 1_875_000_000 + i*4+j})
                suite = {'schema': 'arena-keycard-suite/1', 'split': 'development-only',
                         'selection': '12 current-policy constructed loadouts; no score selection',
                         'loadouts': 12, 'workers': probe_config['workers'], 'replicas': 4, 'tasks': tasks}
                json_write(suite_path, suite)
            records, rows, _ = rollout_bank(pool, model, None, probe_config, device, len(suite['tasks']),
                None, choose, log_path=output/(label+'-episodes.jsonl'),
                tasks=suite['tasks'], greedy=True, source='validation_keycard')
            if records:
                raise ValueError('Keycard probe created PPO samples')
            result = {'batch': batches, 'summary': focus.summarize(rows),
                      'policy_version': config['_policy_version'], 'split': 'development-only',
                      'suite_sha256': hashlib.sha256(suite_path.read_bytes()).hexdigest(),
                      'episodes': rows}
            json_write(output/(label+'.json'), result)
    finally:
        random.setstate(saved_random)
    checkpoint(label+'.pt')
    if label == 'keycard-after':
        before = json.loads(before_path.read_text(encoding='utf8'))
        if before['suite_sha256'] != result['suite_sha256']:
            raise ValueError('Paired diagnostic suite changed')
        old = {(r['seed'], r['entry_sha256']): r for r in before['episodes']}
        new = {(r['seed'], r['entry_sha256']): r for r in result['episodes']}
        if set(old) != set(new) or len(old) != len(suite['tasks']):
            raise ValueError('Paired diagnostic exam set changed')
        differences = [new[k]['score'] - old[k]['score'] for k in sorted(old)]
        # Four seed replicas per deck are clustered, not 48 independent decks.
        clustered = {}
        for k in old:
            clustered.setdefault(old[k]['keycard_loadout_id'], []).append(new[k]['score']-old[k]['score'])
        cluster_means = [statistics.mean(v) for v in clustered.values()]
        report = {'status': 'complete', 'start_batch': start, 'end_batch': batches,
                  'before': before['summary'], 'after': result['summary'],
                  'paired_mean_score_change': statistics.mean(differences),
                  'loadout_cluster_mean_se': statistics.stdev(cluster_means)/len(cluster_means)**0.5,
                  'wins': sum(d > 0 for d in differences), 'ties': sum(d == 0 for d in differences),
                  'losses': sum(d < 0 for d in differences),
                  'limitation': 'Short development probe, mixed-profile updates, no untreated branch; not causal proof or convergence.',
                  'forced_setup_ended': True, 'ordinary_training_continues': True}
        json_write(output/'keycard-result.json', report)
        publish('keycard_practice_complete', keycard_result=report)
    else:
        publish('keycard_baseline', keycard_baseline=result['summary'])
