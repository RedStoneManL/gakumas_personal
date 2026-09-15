from __future__ import annotations
import copy
import hashlib
import json
import math
import random
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import torch
from .encoding import encode_drinks, encode_exam, collate
from .checkpoint import transfer, load, save, digest, json_write, source_version
from .environment import Workers, arena_module
from .ppo import update


def append(path, row):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


def hash_entry(entry):
    return hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def choose(model, examples, device, greedy=False, driver='policy', rngs=None):
    with torch.no_grad():
        logits, values = model(collate(examples, device))
        distribution = torch.distributions.Categorical(logits=logits)
        if driver == 'random':
            selected = torch.tensor([rng.randrange(len(e.submissions)) for rng, e in zip(rngs, examples)], device=device)
        else:
            selected = logits.argmax(-1) if greedy else distribution.sample()
        logp = distribution.log_prob(selected)
        if not torch.isfinite(logp).all() or not torch.isfinite(values).all():
            raise FloatingPointError('invalid policy output')
    return selected.tolist(), logp.tolist(), values.tolist()


def rollout(pool, model, entry, catalog, config, device, start_seed, *, count=None,
            target_decisions=None, greedy=False, fixed_drinks=None, driver='policy', log_path=None):
    """One frozen behavior policy for whole drink-prefix + exam episodes."""
    assert (count is None) != (target_decisions is None)
    active, records, summaries = {}, [], []
    next_seed, started, meaningful = start_seed, 0, 0
    last_log = time.monotonic()

    def can_start():
        return started < count if count is not None else meaningful < target_decisions

    def begin_exam(i, row):
        row['entry'] = copy.deepcopy(entry)
        row['entry']['resources']['drinks'] = list(row['drinks'])
        pool.send(i, 'reset', (row['entry'], row['seed']))
        row['obs'] = pool.receive(i)['observation']
        row['phase'] = 'exam'
        if row['obs']['result']['terminated'] or row['obs']['result']['truncated']:
            raise RuntimeError('invalid opening boundary')

    while active or can_start():
        for i in range(config['workers']):
            if i not in active and can_start():
                row = {'seed': next_seed, 'drinks': [], 'phase': 'drinks', 'records': [], 'submissions': [],
                       'drink_choices': [], 'rng': random.Random(next_seed + 40000000), 'steps': 0}
                next_seed += 1; started += 1
                active[i] = row
                if fixed_drinks is not None:
                    row['drinks'] = list(fixed_drinks)
                    begin_exam(i, row)
        ids = list(active)
        examples = [encode_drinks(entry, active[i]['drinks'], catalog, config['drink_pool'], config['drink_capacity'])
                    if active[i]['phase'] == 'drinks' else encode_exam(active[i]['obs']) for i in ids]
        actions, logps, values = choose(model, examples, device, greedy, driver, [active[i]['rng'] for i in ids])
        awaiting = []
        for i, e, action, logp, value in zip(ids, examples, actions, logps, values):
            row = active[i]
            command = e.submissions[action]
            row['records'].append({'encoded': e, 'action': action, 'old_logp': logp, 'old_value': value})
            row['steps'] += 1
            meaningful += len(e.submissions) > 1
            if row['phase'] == 'drinks':
                row['drink_choices'].append(command)
                if command['method'] == 'select_drink':
                    row['drinks'].append(command['drink_id'])
                if command['method'] == 'finish_drinks' or len(row['drinks']) == config['drink_capacity']:
                    begin_exam(i, row)
            else:
                row['submissions'].append(command)
                pool.send(i, 'step', command)
                awaiting.append(i)
        for i in awaiting:
            row = active[i]
            row['obs'] = pool.receive(i)['observation']
            result = row['obs']['result']
            if result['truncated']:
                raise RuntimeError('truncated episode; no terminal reward fabricated')
            if result['terminated']:
                score = result['final_score']
                if score is None or not math.isfinite(score):
                    raise RuntimeError('no authoritative terminal score')
                for r in row['records']:
                    r['return'] = score / config['score_scale']
                # Evaluation records need not retain the (large) neural inputs.
                if target_decisions is not None:
                    records.extend(row['records'])
                summary = {k: row[k] for k in ('seed', 'drinks', 'drink_choices', 'submissions', 'entry')}
                summary.update(score=score, decisions=row['steps'], entry_sha256=hash_entry(row['entry']),
                               turns_elapsed=row['obs']['state']['turnsElapsed'],
                               final_stamina=row['obs']['state']['stamina'])
                if log_path:
                    append(log_path, summary)
                summaries.append({k: v for k, v in summary.items() if k not in ('entry', 'submissions')})
                del active[i]
        if any(r['steps'] >= config['max_episode_decisions'] for r in active.values()):
            raise RuntimeError('decision guard reached, not a game terminal')
        if time.monotonic() - last_log > 30:
            print(json.dumps({'event': 'rollout', 'completed': len(summaries), 'active': len(active),
                              'meaningful_decisions': meaningful, 'start_seed': start_seed}), flush=True)
            last_log = time.monotonic()
    return records, summaries, meaningful, next_seed


def describe(episodes):
    scores = sorted(r['score'] for r in episodes)
    sd = statistics.stdev(scores) if len(scores) > 1 else 0
    return {'mean': statistics.mean(scores), 'std': sd, 'mean_se': sd / math.sqrt(len(scores)),
            'minimum': scores[0], 'maximum': scores[-1],
            'drinks_selected': dict(Counter(str(d) for r in episodes for d in r['drinks'])),
            'mean_drink_count': statistics.mean(len(r['drinks']) for r in episodes),
            'episodes': sorted(episodes, key=lambda r: r['seed'])}


def scenario_gain(candidate, baseline):
    a, b = candidate['episodes'], baseline['episodes']
    if [x['seed'] for x in a] != [x['seed'] for x in b]:
        raise ValueError('scenario comparison seed mismatch')
    gains = [x['score'] - y['score'] for x, y in zip(a, b)]
    return {'mean': statistics.mean(gains), 'mean_se': statistics.stdev(gains) / math.sqrt(len(gains)) if len(gains) > 1 else 0,
            'positive_scenarios': sum(x > 0 for x in gains), 'count': len(gains),
            'comparison': 'same exogenous seed list; selected drinks may change entry and subsequent RNG consumption'}


def train(root, setup, config, initial, output):
    if config['gamma'] != 1 or config['drink_capacity'] != 4:
        raise ValueError('this experiment requires undiscounted score and four drink slots')
    if config['device'] != 'cuda' or not torch.cuda.is_available():
        raise RuntimeError('CUDA is required, no implicit CPU fallback')
    torch.set_num_threads(2)
    random.seed(config['seed']); torch.manual_seed(config['seed'])
    device = config['device']
    arena = root / 'third_party/gakumas_arena'
    api = arena_module(arena)
    entry = json.loads((setup / 'entry.json').read_text(encoding='utf-8'))
    catalog = json.loads((setup / 'catalog.json').read_text(encoding='utf-8'))
    provenance = json.loads((setup / 'provenance.json').read_text(encoding='utf-8'))
    arena_hash = provenance['arena_version']['effective_sha256']
    if api.content_version()['effective_sha256'] != arena_hash:
        raise ValueError('Arena changed since preparation')
    source_hash = source_version()
    setup_hashes = {p.name: digest(p) for p in (setup / 'entry.json', setup / 'catalog.json', setup / 'provenance.json')}
    model, reference = transfer(initial, arena_hash, device)
    drink_params = [p for n, p in model.named_parameters() if n.startswith('drink_')]
    exam_params = [p for n, p in model.named_parameters() if not n.startswith('drink_')]
    optimizer = torch.optim.Adam([
        {'params': exam_params, 'lr': config['learning_rate']},
        {'params': drink_params, 'lr': config['drink_learning_rate']}], eps=config['adam_eps'])
    output.mkdir(parents=True, exist_ok=False)
    manifest = {'config': config, 'entry': entry, 'provenance': provenance, 'setup_sha256': setup_hashes,
        'arena_sha256': arena_hash, 'rl_source_sha256': source_hash, 'transfer': reference,
        'torch': str(torch.__version__), 'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(),
        'objective': 'Round 1 final score / fixed scale, gamma=1; terminal return shared by drink prefix and exam',
        'scope': 'fixed deck; policy chooses 0..4 drinks and uses public exam actions; no produce or Round 2 carry value'}
    json_write(output / 'manifest.json', manifest)
    json_write(output / 'entry-base.json', entry)
    started = time.monotonic()
    batches, decisions, episode_index, best = 0, 0, 100000, -math.inf
    state = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(), 'run_dir': str(output)}

    def publish(event, **details):
        state.update(event=event, batches=batches, decisions=decisions,
                     updated_at=datetime.now(timezone.utc).isoformat(),
                     elapsed_minutes=(time.monotonic() - started) / 60, **details)
        json_write(output / 'progress.json', state)
        line = f'[{datetime.now():%H:%M:%S}] {event} | batch={batches} decisions={decisions} elapsed={state["elapsed_minutes"]:.1f}m'
        for k in ('train_mean', 'validation_mean', 'best_validation_mean', 'baseline_mean'):
            if k in details:
                line += f' | {k}={details[k]:.0f}'
        append(output / 'events.jsonl', copy.deepcopy(state))
        with (output / 'progress.log').open('a', encoding='utf-8') as f:
            f.write(line + '\n')
        print(line, flush=True)

    def unchanged():
        if source_version() != source_hash or api.content_version()['effective_sha256'] != arena_hash:
            raise RuntimeError('effective trainer/Arena changed during run; preserving last completed checkpoint')
        if any(digest(setup / name) != sha for name, sha in setup_hashes.items()):
            raise RuntimeError('setup changed during run')

    def checkpoint(name):
        unchanged()
        save(output / name, model, optimizer, arena_sha256=arena_hash, training_config=config,
             setup_sha256=setup_hashes, decisions=decisions, batches=batches, next_episode_index=episode_index,
             best_validation_mean=best, transfer=reference)

    pool = Workers(config['workers'], arena, arena_hash)
    def evaluate(label, *, fixed=None, driver='policy', policy=None, base=None):
        _, episodes, _, _ = rollout(pool, policy or model, entry, catalog, config, device,
            config['eval_seed_base'] if base is None else base, count=config['eval_episodes'],
            greedy=True, fixed_drinks=fixed, driver=driver, log_path=output / f'{label}-episodes.jsonl')
        result = describe(episodes)
        json_write(output / f'{label}.json', result)
        return result

    try:
        checkpoint('initial.pt'); checkpoint('latest.pt')
        publish('baseline_running')
        baseline = evaluate('baseline-joint')
        fixed_baseline = evaluate('baseline-fixed', fixed=config['diagnostic_drinks'])
        random_baseline = evaluate('baseline-random', driver='random')
        best = baseline['mean']; checkpoint('best.pt')
        publish('baseline', baseline_mean=baseline['mean'], baseline_fixed_mean=fixed_baseline['mean'],
                random_mean=random_baseline['mean'], best_validation_mean=best,
                selected_drinks=baseline['episodes'][0]['drinks'])
        while decisions < config['target_decisions'] and time.monotonic() - started < config['max_minutes'] * 60:
            before = time.monotonic()
            records, episodes, added, episode_index = rollout(pool, model, entry, catalog, config, device,
                episode_index, target_decisions=config['batch_decisions'], log_path=output / 'train-episodes.jsonl')
            collection_seconds = time.monotonic() - before
            unchanged(); before = time.monotonic()
            losses = update(model, optimizer, records, config, device)
            decisions += added; batches += 1
            summary = describe(episodes)
            row = {'batch': batches, 'decisions': decisions, 'train_mean': summary['mean'],
                   'drinks_selected': summary['drinks_selected'], 'mean_drink_count': summary['mean_drink_count'],
                   'drink_decisions': sum(r['encoded'].phase == 1 for r in records),
                   'collection_seconds': collection_seconds, 'update_seconds': time.monotonic() - before, **losses}
            append(output / 'metrics.jsonl', row)
            checkpoint('latest.pt')
            publish('update', train_mean=summary['mean'], losses=losses, drinks_selected=summary['drinks_selected'])
            del records
            if batches % config['eval_every_batches'] == 0 or decisions >= config['target_decisions']:
                evaluation = evaluate(f'validation-{batches:04d}')
                gain = scenario_gain(evaluation, baseline)
                if evaluation['mean'] > best:
                    best = evaluation['mean']; checkpoint('best.pt')
                checkpoint('latest.pt')
                append(output / 'validation-history.jsonl', {'batch': batches, 'decisions': decisions,
                    'mean': evaluation['mean'], 'best_mean': best, 'gain_vs_start': gain,
                    'drinks': evaluation['episodes'][0]['drinks']})
                publish('validation', validation_mean=evaluation['mean'], best_validation_mean=best,
                        gain_vs_start=gain, selected_drinks=evaluation['episodes'][0]['drinks'])
        # Last batch might fall between scheduled validations: include it in selection.
        last = evaluate('validation-final')
        if last['mean'] > best:
            best = last['mean']; checkpoint('best.pt')
        checkpoint('latest.pt')
        best_model, best_info = load(output / 'best.pt', device)
        initial_model, _ = load(output / 'initial.pt', device)
        fixed_final = evaluate('final-fixed', fixed=config['diagnostic_drinks'], policy=best_model)
        final = evaluate('test-best', policy=best_model, base=config['final_seed_base'])
        initial_test = evaluate('test-initial', policy=initial_model, base=config['final_seed_base'])
        report = {'baseline_validation_mean': baseline['mean'], 'best_validation_mean': best,
            'best_checkpoint_decisions': best_info['decisions'], 'total_training_decisions': decisions,
            'test_best': final, 'test_initial': initial_test,
            'test_gain': scenario_gain(final, initial_test), 'fixed_drink_diagnostic_gain': scenario_gain(fixed_final, fixed_baseline),
            'note': 'small first trial; final seeds used only after checkpoint selection; not full HIF performance'}
        json_write(output / 'result.json', report)
        publish('complete', status='complete', best_validation_mean=best, test_mean=final['mean'],
                test_gain=report['test_gain'], selected_drinks=final['episodes'][0]['drinks'])
    except BaseException as error:
        publish('failed', status='failed', error=f'{type(error).__name__}: {error}')
        raise
    finally:
        pool.close(); api.close_training_worker()
