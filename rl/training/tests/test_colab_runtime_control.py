import contextlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch

sys.path.insert(0, str(Path(__file__).parents[1] / 'colab'))
from runtime_control import RuntimeControl
from preflight import probe_batch_capacity
from persistence import atomic_json
from test_runtime import make_trainer


def test_file_updates_pending_and_invalid_edits_leave_training_usable(tmp_path):
    trainer = make_trainer(tmp_path / 'local')
    control = RuntimeControl(tmp_path / 'drive/run')
    trainer.execution_control = control
    atomic_json(control.path, {'workers': 2, 'episodes_per_update': 7,
                             'minibatch_size': 8, 'microbatch_size': 4})
    with contextlib.redirect_stdout(io.StringIO()):
        trainer._execution_boundary('update')
    assert trainer.execution_settings['workers'] == 1
    assert trainer.execution_settings['microbatch_size'] == 4
    assert trainer.pending_execution_settings == {'workers': 2, 'episodes_per_update': 7}
    with contextlib.redirect_stdout(io.StringIO()):
        trainer._execution_boundary('collection')
    assert trainer.execution_settings['workers'] == 2
    assert trainer.pending_execution_settings == {}
    expected = trainer.execution_settings
    control.path.write_text('{"microbatch_size":')
    with contextlib.redirect_stdout(io.StringIO()):
        control('update', trainer)
        atomic_json(control.path, {'workers': 500})
        control('collection', trainer)
        control.path.write_text('{"workers":2,"workers":3}')
        control('collection', trainer)
    assert trainer.execution_settings == expected
    assert 'Duplicate' in json.loads(control.status_path.read_text())['last_error']
    assert (trainer.output / 'training/runtime-controls.jsonl').is_file()


def test_control_hash_survives_checkpoint_and_does_not_undo_oom_reduction(tmp_path):
    trainer = make_trainer(tmp_path / 'local')
    control = RuntimeControl(tmp_path / 'drive/run')
    atomic_json(control.path, {'microbatch_size': 4})
    with contextlib.redirect_stdout(io.StringIO()):
        control('collection', trainer)
    trainer.apply_execution_settings({'microbatch_size': 1}, stage='update')
    trainer.checkpoint()
    restored = make_trainer(tmp_path / 'local').resume()
    new_control = RuntimeControl(tmp_path / 'drive/run')
    with contextlib.redirect_stdout(io.StringIO()):
        new_control('collection', restored)
    assert restored.execution_settings['microbatch_size'] == 1
    # A genuinely edited request can raise the value again deliberately.
    atomic_json(control.path, {'microbatch_size': 3})
    with contextlib.redirect_stdout(io.StringIO()):
        new_control('update', restored)
    assert restored.execution_settings['microbatch_size'] == 3


def test_live_file_changes_rollout_size_without_restarting_or_reusing_seeds(tmp_path):
    trainer = make_trainer(tmp_path / 'local')
    control = RuntimeControl(tmp_path / 'drive/run')
    trainer.execution_control = control
    atomic_json(control.path, {'episodes_per_update': 3})
    with contextlib.redirect_stdout(io.StringIO()):
        trainer.train(1)
        atomic_json(control.path, {'episodes_per_update': 5, 'microbatch_size': 1})
        trainer.train(1)
    assert trainer.seed_cursor == 109
    assert trainer.episodes_seen == 8
    rows = [json.loads(x) for x in (trainer.output / 'training/episodes.jsonl').read_text().splitlines()]
    assert [x['seed'] for x in rows] == list(range(101, 109))
    restored = make_trainer(tmp_path / 'local').resume()
    assert restored.execution_settings['episodes_per_update'] == 5


class CapacityModel(torch.nn.Module):
    def __init__(self, limit, error_type=torch.cuda.OutOfMemoryError):
        super().__init__()
        self.weight = torch.nn.Parameter(torch.tensor(1.))
        self.limit, self.error_type = limit, error_type

    def evaluate(self, states, actions):
        if len(states) > self.limit:
            raise self.error_type('injected capacity error')
        value = self.weight.expand(len(states))
        return SimpleNamespace(log_probs=-value, values=value, entropy=value)


def test_preflight_large_request_is_bounded_and_cuda_oom_is_retried():
    model = CapacityModel(2)
    with contextlib.redirect_stdout(io.StringIO()):
        result = probe_batch_capacity(model, SimpleNamespace(node_count=12), 1024, 'cpu')
    assert result['requested_graphs'] == 1024 and result['graphs'] == 2
    assert result['oom_attempts'] == [32, 16, 8, 4]
    assert model.weight.item() == 1.
    with pytest.raises(RuntimeError, match='injected'):
        probe_batch_capacity(CapacityModel(1, RuntimeError), SimpleNamespace(node_count=12), 2, 'cpu')
