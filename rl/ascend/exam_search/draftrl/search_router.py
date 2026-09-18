"""Joint-collector routing; all samples keep their true action mechanism."""
from collections import Counter
import json
import math
from .search_service import SearchService


class SearchRouter:
    def __init__(self, model, device, config, *, seed_counter=0, log_path=None, progress=None):
        self.config = dict(config)
        self.execution_mode = config.get('execution_mode', 'act')
        if self.execution_mode not in ('act', 'auxiliary'):
            raise ValueError('Unknown search execution mode')
        temperature = config.get('rollout_temperature', 0.)
        if (isinstance(temperature, bool) or not isinstance(temperature, (int, float))
                or not math.isfinite(temperature) or temperature < 0):
            raise ValueError('Search rollout temperature must be finite and nonnegative')
        minimum_visits = config.get('soft_min_visits', 2)
        if type(minimum_visits) is not int or not 2 <= minimum_visits <= 8:
            raise ValueError('Search minimum visits must be an integer between 2 and 8')
        self.counter = seed_counter
        self.log_path = log_path
        self._sink = progress
        # SearchService reports sum(f.done() for f in pending): roots that finished but
        # have not been harvested yet. The collector harvests on every poll, so that
        # number is ~always 0 and reads as "nothing is working". Attach the cumulative
        # outcome counts, which are what actually says whether search is producing.
        self.progress = self._report if progress is not None else None
        self.service = SearchService(model, device,
            parallel_roots=config['parallel_roots'], inference_batch=config['inference_batch'])
        self.counts = Counter()
        self.episode_roots = Counter()

    def select_episode(self, local_index):
        every = self.config['trajectory_every']
        # Rotate the selected position, avoiding a permanent correlation with
        # route, sleep, or HIF scene cycles; identical forks inherit this flag.
        return (local_index % every + local_index // every) % every == 0

    def prepare(self, pool, items, policy_version):
        extras = [{'loss_kind': 'ppo'} for _ in items]
        tasks, positions = [], []
        for position, item in enumerate(items):
            if not item['enabled'] or len(item['encoded'].submissions) <= 1:
                continue
            if self.config.get('soft_min_visits', 2)*len(item['encoded'].submissions) > self.config['simulations']:
                # Admission would necessarily reject this root even if all
                # simulations finished. Do not spend a full search on it.
                status='insufficient_search_budget'
                extras[position]['search_fallback_reason']=status
                for key in ('attempted_roots','status:'+status,'profile:'+item['profile'],
                            'ppo_fallbacks','fallback_profile:'+item['profile'],
                            'preflight_budget_rejections'):
                    self.counts[key]+=1
                if self.log_path:
                    with self.log_path.open('a',encoding='utf8') as stream:
                        stream.write(json.dumps({'profile':item['profile'],'episode_id':item['episode_id'],
                            'decision_version':item['observation']['decision_version'],
                            'status':status,'valid_training_target':False,'search':None,
                            'policy_version':policy_version,
                            'preflight_rejection':True,'elapsed_seconds':0.,
                            'action_count':len(item['encoded'].submissions)},ensure_ascii=False)+'\n')
                continue
            maximum = self.config.get('max_roots_per_episode')
            if maximum is not None and self.episode_roots[item['episode_id']] >= maximum:
                continue
            history = pool.public_history(item['worker'])
            observed = history['steps'][-1]['observation'] if history['steps'] else history['initial']['observation']
            if observed != item['observation']:
                raise ValueError('Recorder and collector public state differ')
            self.counter += 1
            if maximum is not None:
                self.episode_roots[item['episode_id']] += 1
            search_seed = (self.config['seed_base'] + self.counter) % 2**32
            tasks.append({'entry': item['entry'], 'history': history,
                'native_action_budget':self.config.get('native_action_budget',20000),
                'objective_k':self.config.get('objective_k',1),
                'root_selection':self.config.get('root_selection','gumbel_halving'),
                **{k:self.config[k] for k in ('soft_floor','soft_temperature','soft_min_visits','learning_target','require_terminal','rollout_temperature') if k in self.config},
                'score_scale': item['score_scale'], 'policy_version': policy_version,
                'search_seed': search_seed, 'partial_selection': item['partial_selection'],
                **{k: self.config[k] for k in ('simulations', 'particles', 'seconds',
                     'sampling_ms', 'max_depth', 'rollout_steps')}})
            positions.append(position)
        return tasks, positions, extras

    def finish(self, item, result, action, logp):
        extra = {'loss_kind': 'ppo'}
        self.counts['attempted_roots'] += 1
        self.counts['status:'+result['status']] += 1
        self.counts['profile:'+item['profile']] += 1
        if result['valid_training_target']:
            search = result['search']
            if search['actions'] != item['encoded'].submissions:
                raise ValueError('Collector/MCTS action order mismatch')
            if self.execution_mode == 'auxiliary':
                # Search is supervision from an isolated public snapshot. Its
                # suggested action must not change the real on-policy rollout.
                extra = {'loss_kind': 'ppo', 'search_aux': search,
                    'search_aux_sampler_version': result['search_version'],
                    'search_aux_seed': result['search_seed']}
                self.counts['auxiliary_targets'] += 1
            else:
                action = item['encoded'].submissions.index(search['selected_action'])
                logp = None
                extra = {'loss_kind': 'search', 'search': search,
                    'diagnostic_distribution': 'network_proposal_not_search_behavior',
                    'sampler_version': result['search_version'],
                    'search_seed': result['search_seed']}
            self.counts['accepted_targets'] += 1
            self.counts['accepted_profile:'+item['profile']] += 1
            self.counts['terminal_simulations'] += search['cost']['terminal_evaluations']
            self.counts['bootstrap_simulations'] += search['cost']['bootstrap_evaluations']
        else:
            extra['search_fallback_reason'] = result['status']
            self.counts['ppo_fallbacks'] += 1
            self.counts['fallback_profile:'+item['profile']] += 1
        self.counts['root_seconds'] += result['elapsed_seconds']
        if self.log_path:
            with self.log_path.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps({'profile': item['profile'], 'episode_id': item['episode_id'],
                    'decision_version': item['observation']['decision_version'],
                    'partial_selection': item['partial_selection'], **result}, ensure_ascii=False)+'\n')
        return action, logp, extra

    def route(self, pool, items, actions, logps, policy_version):
        tasks, positions, extras = self.prepare(pool, items, policy_version)
        results = self.service.search_many(tasks, progress=self.progress)
        for position, result in zip(positions, results):
            actions[position], logps[position], extras[position] = self.finish(
                items[position], result, actions[position], logps[position])
        return extras

    def _report(self, **details):
        self._sink(**details,
                   attempted=self.counts['attempted_roots'],
                   accepted=self.counts['accepted_targets'],
                   fallbacks=self.counts['ppo_fallbacks'])

    def diagnostics(self):
        return {'counts': dict(self.counts), 'inference': dict(self.service.stats),
                'seed_counter': self.counter, 'config': self.config}

    def delta(self, before):
        after = self.diagnostics()
        return {group: {key: value-before.get(group, {}).get(key, 0)
                       for key, value in after[group].items()}
                for group in ('counts', 'inference')}

    def close(self):
        self.service.close()
