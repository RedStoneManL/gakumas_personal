"""Read-only dashboard adapter for the separately frozen generalist experiment.

Replay is a bounded, independent CPU process. No model is loaded and no training
file is written. Only the active run and named log/episode files are accessible.
"""
from __future__ import annotations

from collections import OrderedDict, Counter
from datetime import datetime, timezone
import ctypes
import hashlib
import json
import math
import os
import statistics
from pathlib import Path
import subprocess
import sys
import threading
import time

SCHEMA = 'arena-generalist-dashboard/1'
REPLAY_REVISIONS = ('generalist', 'generalist-memory', 'generalist-support', 'generalist-explore', 'generalist-explore2', 'generalist-extra', 'generalist-keycard', 'generalist-keycard-long', 'generalist-duplicate4', 'generalist-duplicate3', 'generalist-lr0005', 'generalist-repeats', 'generalist-batch512', 'generalist-search', 'generalist-search-faststamp', 'generalist-search-viewref', 'generalist-search-best4', 'generalist-search-async', 'generalist-search-decisions', 'generalist-search-ultra', 'generalist-search-ultra-scale', 'generalist-search-soft-value', 'generalist-search-kl-value','generalist-search-signed-credit')


def replay_runtime(root, candidate):
    """Only explicitly supported, workspace-local frozen revisions are executable."""
    root = Path(root).resolve()
    path = Path(candidate).resolve()
    allowed = {root / 'rl' / revision / 'runtime/arena'
               for revision in REPLAY_REVISIONS}
    allowed.update({root/'exam_search/runtime/arena', root/'exam-search/runtime/arena'})
    if path not in allowed:
        raise ValueError('Replay runtime is not an allowed frozen generalist revision')
    return path


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {} if default is None else default


def profile_spec(manifest, row):
    profile = row.get('profile', row.get('profile_id'))
    if isinstance(profile, dict):
        profile = profile.get('id')
    return next((p.get('spec', {}) for p in manifest.get('profiles', []) if p.get('id') == profile), {})


def support_card_ids(spec):
    ids = {str(i) for i in spec.get('support_card_ids', [])}
    ids.update(str(c['card']['definition_id']) for c in spec.get('candidates', [])
               if c.get('source_type') == 'support' and c.get('card', {}).get('definition_id') is not None)
    return ids


def pool_rules(manifest):
    specs = [p.get('spec', {}) for p in manifest.get('profiles', [])]
    registry = manifest.get('provenance', {}).get('prima_stella_registry', {})
    registry_rows = registry.get('cards', registry.get('entries', [])) if isinstance(registry, dict) else registry
    prima_ids = {str(r['native_card_id']) for r in registry_rows if 'native_card_id' in r}
    def excludes_prima(spec):
        return bool(spec.get('exclude_prima_stella')) or bool(
            prima_ids and prima_ids.issubset({str(i) for i in spec.get('banned_card_ids', [])}))
    no_prima = bool(specs) and all(excludes_prima(s) for s in specs)
    limits = [s.get('support_card_limit') for s in specs]
    support_limit = limits[0] if limits and all(isinstance(n, int) and n == limits[0] for n in limits) else None
    rule = '不含一番星' if no_prima else '一番星不计入构筑张数'
    if support_limit is not None:
        rule += f' · 支援专属卡最多 {support_limit} 张'
    cap = manifest.get('config',{}).get('practice',{}).get('duplicates',{}).get('max_same_name')
    if cap is not None:
        rule += f' · 同名卡最多 {cap} 张（强化／绿豆合并计数）'
    for name,limit in manifest.get('config',{}).get('practice',{}).get('duplicates',{}).get('max_same_name_overrides',{}).items():
        rule += f' · {name}单独最多 {limit} 张'
    return {'exclude_prima_stella': no_prima, 'support_card_limit': support_limit,
            'description': rule,
            'count_note': ('构筑与实际入场均为 18–25 张；支援专属卡占其中槽位。' if no_prima else
                           '一番星不占这 18–25 个槽位，实际入场张数可能更多。')}


def tail_text(path, count=200, limit=131072):
    result = {'available': False, 'text': '', 'version': None, 'modified_at': None,
              'line_count': 0, 'truncated': False}
    try:
        with Path(path).open('rb') as stream:
            info = os.fstat(stream.fileno())
            start = max(0, info.st_size - limit)
            stream.seek(start)
            data = stream.read(limit)
    except OSError:
        return result
    if start:
        data = data.partition(b'\n')[2]
    lines = data.decode('utf-8-sig', errors='replace').splitlines()
    result.update(available=True, text='\n'.join(lines[-count:]),
                  line_count=min(count, len(lines)), truncated=bool(start or len(lines) > count),
                  modified_at=datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
                  version=f'{Path(path).name}:{info.st_mtime_ns}:{info.st_size}')
    return result


def tail_rows(path, count=200, limit=16 * 1024 * 1024):
    text = tail_text(path, count=count + 1, limit=limit)['text']
    rows = []
    for line in text.splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        except ValueError:
            pass  # A concurrently written final line is not a complete record yet.
    return rows[-count:]


def alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return None
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return None
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None if ctypes.get_last_error() == 5 else False
    try:
        code = ctypes.c_ulong()
        return code.value == 259 if kernel.GetExitCodeProcess(handle, ctypes.byref(code)) else None
    finally:
        kernel.CloseHandle(handle)


def completed_validation(folder, baseline):
    """Read final DEVELOPMENT validation only, never held-out test scores.

    Frozen trainers save this JSON but omit its history row. Only an exited,
    completed run supplies its checkpoint coordinates; copied final files in a
    running continuation must never be stamped with the new run's batch.
    """
    progress = read_json(folder / 'progress.json')
    if progress.get('status') != 'complete':
        return None
    result = read_json(folder / 'validation-final.json')
    if not result or result.get('schema') != baseline.get('schema'):
        return None
    try:
        def signature(value):
            return [(e['seed'], e['benchmark_cell'], e['score_scale']) for e in value['episodes']]
        if not result.get('episodes') or signature(result) != signature(baseline):
            return None
        cells, initial = result['benchmark_cells'], baseline['benchmark_cells']
        if not cells or cells.keys() != initial.keys():
            return None
        index = math.exp(statistics.mean(math.log(
            (v['normalized_mean'] + .25) / (initial[k]['normalized_mean'] + .25))
            for k, v in cells.items()))
        if not math.isfinite(index):
            return None
        row = {k: result[k] for k in ('mean', 'normalized_mean', 'profiles',
                                      'memory_modes', 'condition_cells') if k in result}
        row.update(batch=progress['batches'], decisions=progress['decisions'],
                   validation_index=index, best_index=progress.get('best_validation_index'),
                   source='completed_development_validation', source_run=folder.name)
        return row
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


class GeneralistData:
    def __init__(self, root, *, card=None, drink=None, memory=None, custom_names=None, run_dir=None):
        self.root = Path(root).resolve()
        self.base = self.root / 'rl/generalist'
        self.run_dir = Path(run_dir).resolve() if run_dir is not None else None
        if self.run_dir is not None:
            self.base = self.run_dir
        self.card = card or (lambda row: row)
        self.drink = drink or (lambda value: {'id': value})
        self.memory = memory or (lambda value: {'id': value})
        self.custom_names = custom_names or {}
        self.replay_lock = threading.Lock()
        self.cache = OrderedDict()
        self.search_window_lock = threading.Lock()
        self.search_window_cache = (None, {})
        self.rollout_window_cache = (None, {})

    def recent_search_window(self, folder, source, batch):
        """Bounded in-flight diagnostics, never added to committed metrics."""
        path = folder / 'search-roots.jsonl'
        try:
            info = path.stat()
        except OSError:
            return {}
        key = (str(folder), source, batch, info.st_mtime_ns, info.st_size)
        with self.search_window_lock:
            if key == self.search_window_cache[0]:
                return self.search_window_cache[1]
            version = f'{source}:{batch}'
            rows = [r for r in tail_rows(path, 256, limit=1_048_576)
                    if r.get('policy_version') == version]
            result = {'policy_version': version, 'points': len(rows),
                      'valid_targets': sum(bool(r.get('valid_training_target')) for r in rows),
                      'statuses': dict(Counter(r.get('status') for r in rows)),
                      'max_points': 256, 'committed': False,
                      'modified_at': datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()}
            self.search_window_cache = (key, result)
            return result

    def current_rollout(self, job, progress):
        if progress.get('event') not in ('search_progress', 'collecting') or not job.get('stdout'):
            return {}
        path = Path(job['stdout']).resolve()
        if not path.is_relative_to(self.base.resolve()):
            return {}
        try:
            info = path.stat()
        except OSError:
            return {}
        key = (str(path), info.st_mtime_ns, info.st_size)
        with self.search_window_lock:
            if key == self.rollout_window_cache[0]:
                return self.rollout_window_cache[1]
            result = {}
            for row in tail_rows(path, count=4096, limit=262144):
                event = row.get('event')
                if event == 'rollout_begin':
                    result = {'kind':'joint' if row.get('training') else 'evaluation',
                              'target_decisions':row.get('target_decisions')}
                elif event == 'bank_rollout_begin':
                    result = {'kind':'exam_group', 'total_games':row.get('count')}
                elif event in ('rollout', 'bank_rollout'):
                    kind = 'joint' if event == 'rollout' else 'exam_group'
                    if result.get('kind') != kind:
                        result = {'kind':kind}
                    result.update({k:row[k] for k in ('completed','active','meaningful_decisions') if k in row})
            result['committed'] = False
            self.rollout_window_cache = (key, result)
            return result

    def job(self):
        if self.run_dir is not None:
            manifest = read_json(self.run_dir/'manifest.json')
            progress = read_json(self.run_dir/'progress.json')
            return {'output': str(self.run_dir), 'code_root': manifest.get('arena_path', ''),
                    'started_at': progress.get('started_at'),
                    'expected_training_end': manifest.get('config', {}).get('absolute_deadline'),
                    'profiles': [p['id'] for p in manifest.get('profiles', [])]}, self.run_dir
        value = read_json(self.base / 'active.json')
        if not value.get('output'):
            return {}, None
        folder = Path(value['output']).resolve()
        if not folder.is_relative_to((self.base / 'runs').resolve()):
            raise ValueError('Active generalist run must be inside its runs directory')
        return value, folder

    def available(self):
        return self.job()[1] is not None

    def logs(self, source='progress'):
        job, folder = self.job()
        allowed = {'progress': folder / 'progress.log' if folder else None,
                   'stdout': job.get('stdout'), 'stderr': job.get('stderr'),
                   'monitor': folder / 'monitor-history.jsonl' if folder else None}
        if source not in allowed:
            raise ValueError('Unknown generalist log source')
        path = allowed[source]
        if not path:
            return {'source': source, **tail_text(self.base / '_unavailable')}
        path = Path(path).resolve()
        if not path.is_relative_to(self.base.resolve()):
            raise ValueError('Log path must remain within generalist experiment')
        return {'source': source, **tail_text(path)}

    def state(self):
        job, folder = self.job()
        now = datetime.now(timezone.utc).isoformat()
        result = {'schema': SCHEMA, 'server_pid': os.getpid(), 'checked_at': now,
                  'available': folder is not None}
        if folder is None:
            return result
        progress = read_json(folder / 'progress.json')
        manifest = read_json(folder / 'manifest.json')
        baseline = read_json(folder / 'validation-initial.json')
        metrics = tail_rows(folder / 'metrics.jsonl', 1000)
        history = tail_rows(folder / 'validation-history.jsonl', 1000)
        # Supplement display only. Do not rewrite immutable training histories.
        origins = [folder]
        if job.get('source_run'):
            source = Path(job['source_run']).resolve()
            if source.is_relative_to((self.base / 'runs').resolve()):
                origins.append(source)
        # Resource continuations can have a paused immediate parent. Preserve
        # completed ancestor validation at its original coordinates as well.
        for audit in manifest.get('continuations', [])[-32:]:
            if audit.get('source_run'):
                source = Path(audit['source_run']).resolve()
                if source.parent == (self.base / 'runs').resolve() and source not in origins:
                    origins.append(source)
        for origin in origins:
            # Continuation manifests contain large scenario catalogs. Reuse
            # each one within this response instead of parsing it four times.
            origin_manifest = manifest if origin == folder else read_json(origin/'manifest.json')
            current_cap = manifest.get('config',{}).get('practice',{}).get('duplicates',{}).get('max_same_name')
            origin_cap = origin_manifest.get('config',{}).get('practice',{}).get('duplicates',{}).get('max_same_name')
            current_overrides = manifest.get('config',{}).get('practice',{}).get('duplicates',{}).get('max_same_name_overrides',{})
            origin_overrides = origin_manifest.get('config',{}).get('practice',{}).get('duplicates',{}).get('max_same_name_overrides',{})
            if origin_manifest.get('arena_sha256') != manifest.get('arena_sha256'):
                continue
            if origin_manifest.get('schema') != manifest.get('schema'):
                continue
            if (origin_cap,origin_overrides) != (current_cap,current_overrides):
                continue
            final = completed_validation(origin, baseline)
            if final and not any(r.get('batch') == final['batch'] for r in history):
                history.append(final)
        history.sort(key=lambda r: (r.get('decisions', 0), r.get('batch', 0)))
        play_history = tail_rows(folder / 'play-validation-history.jsonl', 1000)
        best4_history = tail_rows(folder / 'best4-validation-history.jsonl', 1000)
        last = metrics[-1] if metrics else {}
        validation = history[-1] if history else {}
        monitor = read_json(folder / 'monitor.json')
        check_paths = [folder / 'progress.json', folder / 'progress.log']
        check_paths += [Path(job[k]) for k in ('stdout', 'stderr') if job.get(k)]
        modified = max((p.stat().st_mtime for p in check_paths if p.exists()), default=time.time())
        process_alive = alive(progress.get('trainer_pid'))
        status = progress.get('status', 'starting')
        if status == 'running' and process_alive is False:
            status = 'stopped'
        config = manifest.get('config', {})
        pool = pool_rules(manifest)
        profile_meta = {p['id']: p for p in manifest.get('profiles', [])}
        profiles = []
        for profile in job.get('profiles', list(profile_meta)):
            profiles.append({'id': profile, 'name': profile_meta.get(profile, {}).get('name', profile),
                             'baseline': baseline.get('profiles', {}).get(profile, {}),
                             'validation': validation.get('profiles', {}).get(profile, {}),
                             'training': last.get('profiles', {}).get(profile, {})})
        raw_baseline = baseline.get('mean')
        normalized_baseline = baseline.get('normalized_mean')
        memory_split = (bool(config.get('memory_mode_weights'))
                        or bool(baseline.get('memory_modes'))
                        or bool(last.get('memory_mode_counts')))
        memory_status = ('环境条件：无 HIF 回忆 / HIF 回忆可用各 50%'
                         if memory_split else '旧任务：仅 HIF 回忆可用')
        validation_series = []
        construction_reference = read_json(folder/'construction-benchmark.json')
        if raw_baseline is not None and not construction_reference:
            validation_series.append({'batch': 0, 'decisions': 0, 'raw_mean': raw_baseline,
                                      'normalized_mean': normalized_baseline,
                                      'validation_index': 1.0, 'best_index': 1.0,
                                      'profiles': baseline.get('profiles', {}),
                                      'memory_modes': baseline.get('memory_modes', {}),
                                      'condition_cells': baseline.get('condition_cells', {})})
        validation_series += [{'batch': r.get('batch'), 'decisions': r.get('decisions'),
                              'raw_mean': r.get('mean'), 'normalized_mean': r.get('normalized_mean'),
                              'validation_index': r.get('validation_index'), 'best_index': r.get('best_index'),
                              'profiles': r.get('profiles', {}),
                              'memory_modes': r.get('memory_modes', {}),
                              'condition_cells': r.get('condition_cells', {})}
                             for r in history]
        result.update(
            search={'enabled':bool(config.get('search',{}).get('enabled')),
                    'objective':config.get('practice',{}).get('forks',{}).get('objective','mean'),
                    'replicas':config.get('practice',{}).get('forks',{}).get('replicas',2),
                    'best4_training':last.get('build_best_of_k'),
                    'best4_validation':best4_history[-1] if best4_history else None,
                    'config':config.get('search',{}), 'batch':last.get('batch'),
                    'latest':last.get('search_batch',{}),
                    'current_progress':progress.get('search_progress'),
                    'current_rollout':self.current_rollout(job, progress),
                    'inflight_recent': (self.recent_search_window(folder, manifest.get('rl_source_sha256'),
                                        progress.get('batches', 0))
                                        if config.get('search', {}).get('enabled') else {}),
                    'collection_seconds':last.get('collection_seconds'),
                    'update_seconds':last.get('update_seconds'),
                    'batch_decisions_actual':last.get('batch_decisions_actual'),
                    'loss':last.get('search_loss'), 'search_records':last.get('search_records'),
                    'ppo_records':last.get('ppo_records'),
                    'version':manifest.get('search_version')},
            practice={'enabled':bool(config.get('practice')), 'config':config.get('practice',{}),
                      'committed_objective':last.get('construction_objective','mean'),
                      'construction_reference':construction_reference,
                      'modes':last.get('practice_modes',{}),'fork_prefixes':last.get('fork_prefix_count'),
                      'fork_exams':last.get('fork_episode_count'),'bank':last.get('sample_bank',{}),
                      'fork_coverage':last.get('fork_coverage'),
                      'update_coverage':last.get('update_coverage'),
                      'critic_update_coverage':last.get('critic_update_coverage'),
                      'critic_completion':last.get('critic_completion'),
                      'signed_credit':last.get('signed_credit'),'search_learning':last.get('search_learning'),
                      'target_kl':config.get('target_kl'),
                      'stopping_block':last.get('stopping_block'),
                      'post_update_kl':last.get('post_update_kl'),
                      'optimizer_steps':last.get('optimizer_steps'),
                      'duplicates':last.get('duplicate_regularization',{}),
                      'joint_deck_sizes':last.get('joint_deck_size_counts',{}),
                      'batch_decisions_target':config.get('batch_decisions'),
                      'coverage':last.get('coverage_summary',{}),'latest_play':play_history[-1] if play_history else None},
            run={'id': folder.name, 'output': str(folder), 'started_at': job.get('started_at'),
                 'expected_training_end': job.get('expected_training_end'),
                 'source_sha256': manifest.get('rl_source_sha256'), 'arena_sha256': manifest.get('arena_sha256')},
            status=status, trainer_alive=process_alive, trainer_pid=progress.get('trainer_pid'),
            stale_seconds=max(0, round(time.time() - modified)), updated_at=progress.get('updated_at'),
            progress={k: (config.get(k, progress.get(k)) if k == 'batch_decisions'
                          else progress.get(k, config.get(k))) for k in
                      ('batches', 'decisions', 'event', 'elapsed_minutes', 'batch_decisions', 'max_minutes')},
            metrics={'train_raw_mean': last.get('train_mean'),
                     'validation_batch': validation.get('batch'),
                     'validation_from_current_revision': bool(validation) and (
                         validation.get('reference_reset') or not manifest.get('continuations') or validation.get('batch', 0) >
                         manifest['continuations'][-1].get('checkpoint_batch', 0)),
                     'train_normalized_mean': last.get('train_normalized_mean'),
                     'validation_raw_mean': validation.get('mean', raw_baseline),
                     'validation_normalized_mean': validation.get('normalized_mean', normalized_baseline),
                     'validation_index': validation.get('validation_index', 1.0 if raw_baseline is not None else None),
                     'best_validation_index': progress.get('best_validation_index'),
                     'baseline_raw_mean': raw_baseline, 'baseline_normalized_mean': normalized_baseline},
            series={'validation': validation_series,'play_validation':play_history,
                    'best4_validation':[{**r,'validation_index':r['index']} for r in best4_history],
                    'training': [{'batch': r.get('batch'), 'decisions': r.get('decisions'),
                                  'raw_mean': r.get('train_mean'), 'normalized_mean': r.get('train_normalized_mean'),
                                  'episodes': r.get('episodes'), 'collection_seconds': r.get('collection_seconds'),
                                  'update_seconds': r.get('update_seconds')} for r in metrics]},
            profiles=profiles,
            memory_conditions={'enabled': memory_split, 'status': memory_status,
                'target_weights': config.get('memory_mode_weights', {'none': .5, 'hif': .5} if memory_split else {'hif': 1.0}),
                'baseline': baseline.get('memory_modes', {}),
                'validation': validation.get('memory_modes', baseline.get('memory_modes', {})),
                'condition_baseline': baseline.get('condition_cells', {}),
                'condition_validation': validation.get('condition_cells', baseline.get('condition_cells', {}))},
            distributions={k: last.get(k, {}) for k in
                           ('drink_capacity_counts', 'deck_size_counts', 'course_counts', 'supply_mode_counts',
                            'memory_mode_counts', 'condition_counts')},
            exploration=progress.get('active_exploration', last.get('exploration_settings', {})),
            optimizer={'actual':progress.get('optimizer_schedule',last.get('optimizer_schedule',{})),
                       'schedule':config.get('learning_rate_schedule'),
                       'exploration_schedule':config.get('exploration_schedule')},
            phase_decisions=last.get('phase_decisions', {}),
            losses={k: last.get(k) for k in ('loss', 'policy_loss', 'value_loss', 'kl', 'grad_norm', 'clip_fraction')},
            monitor=monitor, errors={'stderr_tail': self.logs('stderr')['text'], 'alert': progress.get('error') or monitor.get('alert')},
            setup={'card_count_range': [18, 25], 'drink_capacity_range': [0, 4],
                   'profiles': job.get('profiles', []), 'turn_counts': [9, 10, 12],
                   'workers': config.get('workers'), 'max_minutes': config.get('max_minutes'),
                   'eval_episodes': config.get('eval_episodes'), 'memory_status': memory_status,
                   'pool_rules': pool,
                   'description': 'Synthetic generalist construction + exam courses. ' + pool['description']},
            metric_notes={'validation_index': 'Matched profile/course/capacity cells against initial policy; baseline = 1.',
                          'normalized_mean': 'Raw score divided by profile score scale and global multiplier; extra turns are not normalized away.',
                          'raw_mean': 'Actual simulator score. Training batches mix changing scenarios and exploration; compare fixed validation for progress.'})
        return result

    def sources(self, mode='train'):
        if mode not in ('train', 'eval'):
            raise ValueError('Mode must be train or eval')
        _, folder = self.job()
        if folder is None:
            return []
        if mode == 'train':
            return [folder / 'train-episodes.jsonl']
        return sorted(folder.glob('validation-*-episodes.jsonl'),
                      key=lambda p: p.stat().st_mtime, reverse=True)[:3]

    def summary(self, row, filename, mode, manifest=None):
        if manifest is None:
            _, folder = self.job()
            manifest = read_json(folder / 'manifest.json') if folder else {}
        spec = profile_spec(manifest, row)
        support_ids = support_card_ids(spec)
        limit = spec.get('support_card_limit')
        support_count = sum(str(c.get('definition_id')) in support_ids for c in row['entry']['cards']) if isinstance(limit, int) else None
        return {'seed': row['seed'], 'file': filename, 'mode': mode, 'profile': row.get('profile'),
                'score': row.get('score'), 'normalized_score': row.get('normalized_score'),
                'score_scale': row.get('score_scale'), 'deck_size': row.get('deck_size'),
                'physical_deck_size': row.get('physical_deck_size', len(row['entry']['cards'])),
                'drink_capacity': row.get('drink_capacity'), 'drinks': [self.drink(d) for d in row.get('drinks', [])],
                'memory_mode': row.get('memory_mode'), 'memory_capacity': row.get('memory_capacity'),
                'memory_status': ('无 HIF 回忆' if row.get('memory_mode') == 'none' else
                                  'HIF 回忆可用' if row.get('memory_mode') == 'hif' else '旧任务：仅 HIF 回忆可用'),
                'selected_memory_count': len(row.get('selected_memories', row['entry'].get('memory_abilities', []))),
                'support_card_count': support_count, 'support_card_limit': limit,
                'course_id': row.get('course_id'), 'decisions': row.get('decisions'),
                'sampling_source': row.get('sampling_source'), 'exploration_mode':row.get('exploration_mode','normal'),
                'prefix_id':row.get('prefix_id'),
                'turns': row.get('turns_elapsed'), 'scenario': row.get('scenario')}

    def episodes(self, mode='train'):
        rows = []
        _, folder = self.job()
        manifest = read_json(folder / 'manifest.json') if folder else {}
        for path in self.sources(mode):
            rows += [self.summary(row, path.name, mode, manifest) for row in reversed(tail_rows(path, 120))]
        return rows[:120]

    def episode(self, mode, filename, seed, replay=True):
        allowed = {p.name: p for p in self.sources(mode)}
        if filename not in allowed:
            raise ValueError('Episode file is not among the active run recent files; refresh the list')
        row = next((r for r in tail_rows(allowed[filename], 300) if r.get('seed') == seed), None)
        if row is None:
            raise ValueError('Episode is no longer in the recent window; refresh the list')
        _, folder = self.job()
        manifest = read_json(folder / 'manifest.json')
        support_ids = support_card_ids(profile_spec(manifest, row))
        def display_card(card):
            result = dict(self.card(card))
            if str(card.get('definition_id', card.get('id'))) in support_ids:
                result['source_type'] = 'support'
            return result
        result = self.summary(row, filename, mode, manifest)
        result.update(initial_cards=[display_card(c) for c in row['entry']['cards']],
                      initial_drinks=[self.drink(d) for d in row.get('drinks', [])],
                      initial_memories=[self.memory(m['id']) for m in row['entry'].get('memory_abilities', [])],
                      memory_effects_note=('该环境禁用 HIF 回忆能力：容量 0、无回忆选择、入场不携带 HIF 回忆效果。'
                          if row.get('memory_mode') == 'none' else
                          'HIF 回忆能力可选；下方显示本局实际携带效果，0 个表示策略未选。'
                          if row.get('memory_mode') == 'hif' else
                          '旧任务：HIF 回忆能力可用，未记录独立的环境模式字段。'),
                      turn_types=row.get('resolved_turn_types', row['entry']['context'].get('turn_types')),
                      context=row['entry']['context'], resources=row['entry']['resources'],
                      general_scenario=row.get('general_scenario'), drink_supply=row.get('drink_supply'),
                      guidance_budget=row.get('guidance_budget'), draft_choices=row.get('draft_choices', []),
                      guidance_choices=row.get('guidance_choices', []), drink_choices=row.get('drink_choices', []),
                      memory_choices=row.get('memory_choices', []), submissions=row.get('submissions', []),
                      initial_sleep_count=row.get('initial_sleep_count'), removed_sleep_count=row.get('removed_sleep_count'),
                      customization_names=self.custom_names, verified=False, frames=[],
                      policy_turn_visibility=row.get('policy_turn_visibility'))
        if not replay:
            return result
        frozen = replay_runtime(self.root, manifest.get('arena_path') or self.base / 'runtime/arena')
        key = hashlib.sha256(json.dumps([row, str(frozen), manifest.get('arena_sha256')], sort_keys=True).encode()).hexdigest()
        with self.replay_lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key]
            env = dict(os.environ, CUDA_VISIBLE_DEVICES='', PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1')
            command = [sys.executable, '-B', '-X', 'utf8',
                       str(Path(__file__).resolve()), '--replay']
            completed = subprocess.run(command, input=json.dumps({'row': row, 'arena_path': str(frozen),
                                       'arena_sha256': manifest.get('arena_sha256'), 'root': str(self.root)}),
                                       capture_output=True, text=True, encoding='utf-8', timeout=60, env=env,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if completed.returncode:
                raise ValueError('Frozen replay failed: ' + completed.stderr[-1800:])
            replayed = json.loads(completed.stdout)
            for frame in replayed['frames']:
                frame['drinks'] = [self.drink(d) for d in frame['drinks']]
                for zone in ('hand', 'hand_before', 'deck', 'discarded', 'removed', 'all_cards'):
                    for card in frame[zone]:
                        if str(card['id']) in support_ids:
                            card['source_type'] = 'support'
                        card['icon'] = self.card({'instance_id': card['uid'], 'definition_id': card['id'],
                                                  'customizations': card.get('customizations', {}),
                                                  'growth': card.get('growth', {})}).get('icon')
            result.update(replayed)
            self.cache[key] = result
            while len(self.cache) > 12:
                self.cache.popitem(last=False)
        return result


def _frame(obs, previous=None, command=None, index=0):
    definitions = {c['id']: c for c in obs['definitions']['cards']}
    cards = {}
    for c in obs['cards']:
        definition = definitions[c['definition_id']]
        cards[c['instance_id']] = {'uid': c['instance_id'], 'id': c['definition_id'],
            'name': definition.get('name'), 'customizations': c.get('customizations', {}),
            'growth': c.get('growth', {}), 'effective': c.get('effective'), 'type': definition.get('type')}
    state = obs['state']
    prev = previous['state'] if previous else state
    label = '入场效果结算后'
    action_card = None
    if command:
        if command['method'] == 'choose':
            candidates = {c['index']: c for c in previous['choice']['candidates']}
            label = '选择：' + '、'.join(cards.get(candidates[i].get('instance_id'), {}).get('name', str(i))
                                      for i in command['indices'])
        else:
            action = command['action']
            if action['type'] == 'play':
                action_card = cards.get(action['instance_id'])
                label = '使用 ' + (action_card.get('name', action['instance_id']) if action_card else action['instance_id'])
            elif action['type'] == 'drink':
                label = '饮用 ' + str(previous['drinks'][action['slot']])
            elif action['type'] == 'end_turn':
                label = '结束回合'
            else:
                label = action['type']
    turns = obs['context']['turn_types']
    buffs = []
    for key, value in state.items():
        if key.endswith('Turns') and isinstance(value, (int, float)) and value > 0:
            buffs.append({'name': key, 'field': key, 'turns': value})
        elif ('Buffs' in key or 'Debuffs' in key) and isinstance(value, list):
            buffs += [{'name': key, 'field': key, **(b if isinstance(b, dict) else {'value': b})} for b in value]
    return {'index': index, 'action': label, 'action_card': action_card,
            'turn': min(state['turnsElapsed'] + 1, len(turns)),
            'turn_type': turns[min(state['turnsElapsed'], len(turns) - 1)],
            'action_turn': min(prev['turnsElapsed'] + 1, len(turns)),
            'pending_choice': obs.get('choice') is not None,
            'score': state['score'], 'score_delta': state['score'] - prev['score'],
            'stamina': state['stamina'], 'stamina_delta': state['stamina'] - prev['stamina'],
            'max_stamina': obs['context']['max_stamina'],
            'genki': state.get('genki'), 'concentration': state.get('concentration'),
            'goodConditionTurns': state.get('goodConditionTurns'),
            'perfectConditionTurns': state.get('perfectConditionTurns'),
            'cardUsesRemaining': state.get('cardUsesRemaining'), 'buffs': buffs,
            'effects': state.get('effects', []), 'drinks': obs['drinks'],
            'hand': [cards[x] for x in obs['zones']['hand']],
            'hand_before': [cards[x] for x in previous['zones']['hand']] if previous else [],
            'deck': [cards[x] for x in obs['zones']['deck']['members']],
            'discarded': [cards[x] for x in obs['zones']['discarded']],
            'removed': [cards[x] for x in obs['zones']['removed']],
            'all_cards': list(cards.values()) if index == 0 else [],
            'terminal': obs['result']['terminated'], 'raw_state': state}


def replay_main():
    request = json.load(sys.stdin)
    path = replay_runtime(Path(__file__).resolve().parent.parent, request['arena_path'])
    sys.path.insert(0, str(path))
    from gakumas_arena.engine import training
    try:
        version = training.content_version()['effective_sha256']
        if version != request['arena_sha256']:
            raise ValueError('Frozen Arena hash differs from run manifest')
        row = request['row']
        if len(row['submissions']) > 2048:
            raise ValueError('Replay submission bound exceeded')
        exam = training.create_training_exam(row['entry'], seed=row['seed'])
        current = exam.observe()
        frames = [_frame(current)]
        for i, command in enumerate(row['submissions'], 1):
            previous = current
            current = (exam.choose(command['indices'], decision_version=command['decision_version'])
                       if command['method'] == 'choose' else exam.act(command['action']))
            frames.append(_frame(current, previous, command, i))
        if not current['result']['terminated'] or current['result']['final_score'] != row['score']:
            raise ValueError('Replay score/termination mismatch')
        if row.get('resolved_turn_types') != current['context']['turn_types']:
            raise ValueError('Replay course order mismatch')
        json.dump({'verified': True, 'replay_arena_sha256': version, 'frames': frames}, sys.stdout, ensure_ascii=False)
    finally:
        training.close_training_worker()


if __name__ == '__main__' and sys.argv[1:] == ['--replay']:
    replay_main()
