import importlib.util
import json
from pathlib import Path

import pytest


def module():
    source = Path(__file__).resolve().parents[1] / 'colab/performance.py'
    if not source.is_file():
        source = Path(__file__).resolve().parents[2] / 'colab/performance.py'
    spec = importlib.util.spec_from_file_location('colab_performance', source)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_profile_changes_batching_only_and_is_pinned_across_hardware(tmp_path):
    perf = module()
    base = {'task': 'full_produce', 'workers': 1, 'ppo': {'microbatch_size': 2,
            'minibatch_size': 64, 'epochs': 2, 'gamma': 1.0}, 'task_config': {'idol': 'fixed'}}
    hardware = {'gpu_name': 'A100', 'gpu_memory_bytes': 40 * 2**30, 'available_cpu_count': 12}
    args = dict(manifest_sha256='sealed-bundle', run_name='test', persistent_root=tmp_path/'drive',
                output=tmp_path/'local/config.json')
    first = perf.prepare_config(base, hardware=hardware, **args)
    assert first['settings'] == {'workers': 10, 'microbatch_size': 8}
    written = json.loads((tmp_path/'local/config.json').read_text())
    assert written['task_config'] == base['task_config']
    assert written['ppo'] | {'microbatch_size': 2} == base['ppo']
    assert base['workers'] == 1
    second = perf.prepare_config(base, hardware={**hardware, 'gpu_name': 'L4',
                    'gpu_memory_bytes': 24 * 2**30, 'available_cpu_count': 2}, **args)
    assert second['reused_saved_profile'] and second['settings'] == first['settings']
    with pytest.raises(ValueError, match='fixed for this run'):
        perf.prepare_config(base, hardware=hardware, workers=2, **args)
    with pytest.raises(ValueError, match='differs'):
        perf.prepare_config({**base, 'task': 'exam_score'}, hardware=hardware, **args)


def test_smaller_gpu_defaults_and_corrupt_profile_rejected(tmp_path):
    perf = module()
    for memory, cores, expected in ((16, 2, (2, 2)), (24, 8, (6, 4)), (80, 1, (1, 16)),
                                    (80, 12, (10, 16)), (80, 24, (22, 16)), (80, 128, (126, 16))):
        hardware = {'gpu_memory_bytes': memory*2**30, 'available_cpu_count': cores}
        settings = perf.suggested_settings(hardware)
        assert (settings['workers'], settings['microbatch_size']) == expected
    folder = tmp_path/'_performance_configs'
    folder.mkdir()
    (folder/'bad.json').write_text('{}')
    with pytest.raises(ValueError, match='differs'):
        perf.prepare_config({}, manifest_sha256='x', run_name='bad', persistent_root=tmp_path,
                            output=tmp_path/'out.json', hardware=hardware)


def test_large_integer_initial_settings_seal_base_and_raise_minibatch(tmp_path):
    perf = module()
    base = {'task': 'full_produce', 'workers': 1, 'ppo': {'minibatch_size': 64, 'microbatch_size': 2}}
    args = dict(manifest_sha256='bundle', run_name='large', persistent_root=tmp_path,
                output=tmp_path/'config.json', hardware={'gpu_memory_bytes': 80*2**30, 'available_cpu_count': 12})
    result = perf.prepare_config(base, workers='1024', microbatch_size='16384', **args)
    config = json.loads((tmp_path/'config.json').read_text())
    assert config['workers'] == 1024
    assert config['ppo'] == {'minibatch_size': 16384, 'microbatch_size': 16384}
    assert result['initial_minibatch_size'] == 16384
    assert not result['runtime_control_changes_base_identity']
    assert perf.prepare_config(base, **args)['settings'] == result['settings']
    assert base['ppo']['minibatch_size'] == 64


@pytest.mark.parametrize('workers,micro', [('-1', '2'), ('0', '2'), ('1.5', '2'),
                                          ('1', '-1'), ('1', '0'), (True, '2'), ('1', 3.5)])
def test_invalid_manual_initial_values_fail_before_sealing(tmp_path, workers, micro):
    perf = module()
    with pytest.raises(ValueError):
        perf.prepare_config({'ppo': {'minibatch_size': 64}}, manifest_sha256='bundle', run_name='bad',
            persistent_root=tmp_path, output=tmp_path/'config.json', hardware={},
            workers=workers, microbatch_size=micro)
    assert not (tmp_path/'_performance_configs/bad.json').exists()
