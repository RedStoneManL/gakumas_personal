"""Generate new search/full-produce configs with explicit, uncapped scale."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re


FIELDS = ('learners', 'workers', 'search_workers', 'inference_batch', 'batch_decisions',
          'episodes_per_update', 'minibatch_size', 'microbatch_size', 'torch_threads')


def positive_integer(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError('expected a positive integer') from None
    if str(number) != str(value) or number < 1:
        raise argparse.ArgumentTypeError('expected a positive integer')
    return number


def configurations(search, full, **settings):
    """Pure config transform; does not allocate workers, threads or devices."""
    unknown = set(settings) - set(FIELDS) - {'device'}
    if unknown:
        raise ValueError(f'Unknown scale fields: {sorted(unknown)}')
    settings = {k: v for k, v in settings.items() if v is not None}
    for name in FIELDS:
        if name in settings and (type(settings[name]) is not int or settings[name] < 1):
            raise ValueError(f'{name} must be a positive integer')
    device = settings.get('device', search.get('device', 'npu:0'))
    if not isinstance(device, str) or not re.fullmatch(r'(cpu|cuda|npu)(:[0-9]+)?', device):
        raise ValueError('device must be cpu, cuda[:index] or npu[:index]')
    search, full = deepcopy(search), deepcopy(full)
    search.update(resource_mode='cluster', device=device)
    full['device'] = device
    parallel = search.setdefault('parallelism', {})
    for name, target in (('workers', 'workers'), ('search_workers', 'parallel_roots'),
                         ('inference_batch', 'inference_batch'), ('microbatch_size', 'microbatch'),
                         ('torch_threads', 'torch_threads')):
        if name in settings:
            parallel[target] = settings[name]
    for name, target in (('learners', 'learner_world_size'), ('workers', 'workers'),
                         ('batch_decisions', 'batch_decisions'), ('minibatch_size', 'effective_minibatch')):
        if name in settings:
            search[target] = settings[name]
    for name in ('workers', 'episodes_per_update', 'torch_threads'):
        if name in settings:
            full[name] = settings[name]
    for name in ('minibatch_size', 'microbatch_size'):
        if name in settings:
            full['ppo'][name] = settings[name]
    if parallel['microbatch'] > search['effective_minibatch']:
        raise ValueError('Search microbatch_size must not exceed minibatch_size')
    if full['ppo']['microbatch_size'] > full['ppo']['minibatch_size']:
        raise ValueError('Full-produce microbatch_size must not exceed minibatch_size')
    return {'search.json': search, 'full_produce.json': full}


def write_configs(output, configs):
    output = Path(output)
    for name in configs:
        if (output / name).exists():
            raise FileExistsError(f'Refusing to overwrite config: {output / name}')
    output.mkdir(parents=True, exist_ok=True)
    for name, config in configs.items():
        with (output / name).open('x', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(config, ensure_ascii=False, indent=2) + '\n')


def main(argv=None):
    here = Path(__file__).resolve().parent
    defaults = here / 'configs' if (here / 'configs').is_dir() else here.parent / 'configs'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--search-base', type=Path, default=defaults / 'search_8npu.json')
    parser.add_argument('--full-base', type=Path, default=defaults / 'full_produce_npu.json')
    parser.add_argument('--device', help='cpu, cuda[:index] or npu[:index]; defaults to search base')
    for name in FIELDS:
        parser.add_argument('--' + name.replace('_', '-'), type=positive_integer,
                            help='positive integer, no application upper bound; defaults to base config')
    args = parser.parse_args(argv)
    search = json.loads(args.search_base.read_text(encoding='utf-8-sig'))
    full = json.loads(args.full_base.read_text(encoding='utf-8-sig'))
    configs = configurations(search, full, **{name: getattr(args, name) for name in (*FIELDS, 'device')})
    write_configs(args.output_dir, configs)
    print(json.dumps({'directory': str(args.output_dir.resolve()),
                      'learners': configs['search.json']['learner_world_size'],
                      'configs': list(configs)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
