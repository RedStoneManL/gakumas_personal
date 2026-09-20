"""Portable joint search trainer; torchrun enables synchronous multi-card updates."""
from pathlib import Path
import argparse
import json
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE / 'runtime/shared'), str(HERE / 'runtime/arena')]
for candidate in (HERE.parents[1] / 'training', HERE.parent / 'training'):
    if (candidate / 'gakumas_training').is_dir():
        sys.path.insert(0, str(candidate))
        break


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--config', type=Path, required=True)
    start = p.add_mutually_exclusive_group()
    start.add_argument('--initial', type=Path, help='Optional compatible weights/Adam checkpoint for a NEW run')
    start.add_argument('--resume', action='store_true', help='Continue an audited complete checkpoint with its optimizer, RNG and original baseline')
    start.add_argument('--continue-from', type=Path, dest='continue_from',
                   help='Versioned continuation from a COMPLETED run directory into a new --output: weights, Adam, RNG, sample bank, coverage and history carry over; the source code may differ')
    args = p.parse_args(argv)
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    from draftrl.search_supervision import validate_training_config
    validate_training_config(config)
    from draftrl.relational_runtime import configure
    configure(config, HERE/'setup')
    from draftrl import distributed
    mesh = distributed.LearnerGroup(config['device'],
        torch_threads=config.get('parallelism', {}).get('torch_threads', config.get('torch_threads', 2)))
    distributed.ACTIVE = mesh
    if config.get('learner_world_size', 1) != mesh.size:
        raise ValueError('Config learner_world_size differs from torchrun WORLD_SIZE')
    try:
        if mesh.rank != 0:
            mesh.serve()
        else:
            from draftrl.runner import train
            config['device'] = str(mesh.device)
            print(json.dumps({'event': 'learner_ready', 'world_size': mesh.size,
                'device': str(mesh.device), 'sampling_owner_rank': 0,
                'update': 'global-block-normalized gradient SUM'}), flush=True)
            train(HERE, HERE/'setup', config, args.initial, args.output.resolve(), resume=args.resume,
                  continuation=args.continue_from)
            mesh.stop()
    finally:
        mesh.close()


if __name__ == '__main__':
    main()
