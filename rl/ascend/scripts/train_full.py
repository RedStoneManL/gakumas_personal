"""torchrun front end for the existing persistent full-produce/exam trainer."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT/'training' if (ROOT/'training').is_dir() else ROOT.parent/'training'
COLAB = ROOT/'colab' if (ROOT/'colab').is_dir() else TRAINING/'colab'
sys.path[:0] = [str(TRAINING), str(COLAB)]


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--world-size', type=int, required=True)
    options, rest = parser.parse_known_args()
    import run_training
    args = run_training.parser().parse_args(rest)
    path = args.config if args.config.is_absolute() else args.bundle_root/args.config
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    from gakumas_training import distributed
    requested = 'cpu' if args.allow_cpu_smoke else args.device or config['device']
    mesh = distributed.TrainingLearners(requested, torch_threads=config.get('torch_threads', 2))
    distributed.ACTIVE = mesh
    if mesh.size != options.world_size:
        raise ValueError('--world-size differs from torchrun WORLD_SIZE')
    try:
        if mesh.rank:
            mesh.serve()
        else:
            result = run_training.main([*rest, '--device', str(mesh.device)])
            mesh.stop()
            return result
    finally:
        mesh.close()


if __name__ == '__main__':
    raise SystemExit(main())
