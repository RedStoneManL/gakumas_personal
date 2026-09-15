"""Create NEW Ascend-run configurations from the imported algorithm settings."""
import argparse
from copy import deepcopy
import json
from pathlib import Path


def configurations(source, full_source):
    c = deepcopy(source)
    c.update(name='ascend-joint-search', resource_mode='cluster', device='npu:0',
             learner_world_size=8, workers=96, batch_decisions=32768, max_minutes=2880,
             parallelism={'workers': 96, 'parallel_roots': 24, 'inference_batch': 32,
                          'microbatch': 2, 'torch_threads': 2})
    c.pop('absolute_deadline', None)
    c['exploration_schedule']['origin_decisions'] = 0
    c['learning_rate_schedule'].update(origin_elapsed_minutes=0, hold_minutes=120)
    # This new run has no historical calibration directory. The same 32-atom
    # critic and distribution loss train online on new complete trajectories.
    c['value_calibration'] = {k: c['value_calibration'][k]
                             for k in ('quantiles', 'objective_k', 'distribution_coefficient')}
    one = deepcopy(c)
    one.update(learner_world_size=1, workers=8, batch_decisions=4096,
               parallelism={'workers': 8, 'parallel_roots': 2, 'inference_batch': 8,
                            'microbatch': 2, 'torch_threads': 2})
    smoke = deepcopy(one)
    smoke.update(batch_decisions=32, max_batches=1, eval_episodes=5, final_episodes=5,
                 effective_minibatch=32, workers=2,
                 parallelism={'workers': 2, 'parallel_roots': 2, 'inference_batch': 4,
                              'microbatch': 1, 'torch_threads': 1})
    smoke['practice']['play_evaluation']['enabled'] = False  # five games cannot populate every stratum
    smoke['practice']['keycard_focus']['enabled'] = False
    smoke['search'].update(simulations=8, particles=4, seconds=15., sampling_ms=2000)
    full = deepcopy(full_source)
    full.update(device='npu:0', workers=96, episodes_per_update=96)
    full['ppo'].update(minibatch_size=512, microbatch_size=1)
    return {'search_8npu.json': c, 'search_1npu.json': one, 'search_smoke.json': smoke,
            'full_produce_npu.json': full}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.source_root.resolve()
    exam = root / 'exam_search'
    if not exam.exists():
        exam = root / 'exam-search'
    source = json.loads((exam / 'training-config.json').read_text(encoding='utf-8'))
    full_path = root.parent/'training/colab/configs/full_produce_setup_mixed.json'
    if not full_path.exists():
        full_path = root/'configs/full_produce_setup_mixed.json'
    full_source = json.loads(full_path.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=True)
    for name, config in configurations(source, full_source).items():
        path = args.output / name
        if path.exists():
            raise FileExistsError(f'Refusing to overwrite config: {path}')
        path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
