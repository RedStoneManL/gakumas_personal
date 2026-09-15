"""Real CPU/Gloo ranks compare mixed PPO/search updates to a single learner."""
import copy
import json
import os
from pathlib import Path
import random
import pickle
import socket
import tempfile
import unittest
from unittest.mock import patch
from contextlib import ExitStack

import torch
import torch.multiprocessing as mp

from draftrl.distributed import LearnerGroup
from draftrl.model import DraftPolicy
from draftrl.ppo import update
from test_joint_search import config, records


def full_fixture():
    from gakumas_training.models import ModelConfig, PolicyValueNet, PolicyRunner
    from gakumas_training.encoding import DecisionEncoder, Vocabulary
    from gakumas_training.contracts import DecisionContext, Episode, Transition
    from gakumas_training.algorithms import PPOConfig, PPOUpdater
    torch.set_num_threads(1)
    torch.manual_seed(67)
    model = PolicyValueNet(ModelConfig(width=8, layers=1, token_dim=4, vocab_capacity=256))
    runner = PolicyRunner(DecisionEncoder(Vocabulary(capacity=256)), model)
    episodes = []
    for i in range(5):
        context = DecisionContext('full_produce', 'outer', {'resources': {'hp': i+1}},
                                  ({'type': 'option', 'value': 0}, {'type': 'option', 'value': 1}))
        action = runner.act(context, policy_version=0)
        episodes.append(Episode('full_produce', i, [Transition(context, action)], 30.+i, 'normal'))
    updater = PPOUpdater(model, PPOConfig(epochs=1, minibatch_size=4, microbatch_size=1, target_kl=5.))
    return updater, episodes, dict(task='full_produce', policy_version=0, score_scale=10.)


def fixture(latest=False):
    torch.set_num_threads(1)
    torch.manual_seed(174)
    model = DraftPolicy(width=12, lexical=4, depth=2, quantiles=32)
    rows = records(model)
    rows.append(copy.deepcopy(rows[0]))  # uneven last block, one empty rank
    cfg = config()
    cfg.update(minibatch=1, target_kl=5.)
    if latest:
        from test_signed_learning import credit_rows
        from draftrl.learning_settings import SIGNED
        from draftrl.critic_completion import SETTINGS
        rows = credit_rows(model)*8
        rows.append(copy.deepcopy(rows[0]))
        cfg.update(signed_exam_credit=SIGNED, critic_completion=SETTINGS, target_kl=1e-9)
        return model, torch.optim.Adam(model.parameters(), lr=.001, eps=1e-5), rows, cfg
    return model, torch.optim.Adam(model.parameters(), lr=1e-4, eps=1e-5), rows, cfg


def run_rank(rank, port, output, pipes=None, full=False, latest=False):
    torch.set_num_threads(1)
    os.environ.update(RANK=str(rank), WORLD_SIZE='2', LOCAL_RANK=str(rank),
                      MASTER_ADDR='127.0.0.1', MASTER_PORT=str(port), USE_LIBUV='0')
    stack = ExitStack()
    from gakumas_training.distributed import TrainingLearners
    group_class = TrainingLearners if full else LearnerGroup
    if pipes is None:
        mesh = group_class('cpu')
        torch.set_num_threads(1)
    else:
        # Test-only transport for Windows wheels lacking Gloo. Real processes
        # execute production sharding/reduction/update code. This is explicitly
        # not a Gloo/HCCL acceptance result.
        connection = pipes[rank]
        def receive():
            if not connection.poll(30):
                raise TimeoutError('Peer did not reach the expected test collective')
            return pickle.loads(connection.recv_bytes())
        def send(value):
            # Match Gloo object serialization, never multiprocessing's shared
            # tensor-storage reducer (which would alias replica Adam moments).
            connection.send_bytes(pickle.dumps(value))
        def broadcast(box, src=0):
            if rank == 0:
                send(box[0])
            else:
                box[0] = receive()
        def reduce(tensor, op=None, group=None):
            if rank == 0:
                other = torch.tensor(receive(), dtype=tensor.dtype).reshape_as(tensor)
                if op == torch.distributed.ReduceOp.MAX:
                    tensor.copy_(torch.maximum(tensor, other))
                else:
                    tensor.add_(other)
                send(tensor.tolist())
            else:
                send(tensor.tolist())
                tensor.copy_(torch.tensor(receive(), dtype=tensor.dtype).reshape_as(tensor))
        def gather(results, values):
            if rank == 0:
                results[:] = [values, receive()]
                send(results)
            else:
                send(values)
                results[:] = receive()
        stack.enter_context(patch.object(torch.distributed, 'broadcast_object_list', broadcast))
        stack.enter_context(patch.object(torch.distributed, 'all_reduce', reduce))
        stack.enter_context(patch.object(torch.distributed, 'all_gather_object', gather))
        mesh = object.__new__(group_class)
        mesh.rank, mesh.size, mesh.device, mesh.data_group = rank, 2, torch.device('cpu'), None
    try:
        if rank:
            mesh.serve()
        else:
            if full:
                updater, episodes, arguments = full_fixture()
                random.seed(91)
                metrics = mesh.update(updater, episodes, arguments)
                model, optimizer = updater.model, updater.optimizer
            else:
                model, optimizer, rows, cfg = fixture(latest)
                random.seed(91)
                metrics = mesh.update(model, optimizer, rows, cfg)
                # A second dispatch exercises restored replica Adam state.
                if not latest:
                    random.seed(92)
                    mesh.update(model, optimizer, rows, cfg)
            torch.save({'model': model.state_dict(), 'optimizer': optimizer.state_dict()}, Path(output)/'actual.pt')
            (Path(output)/'metrics.json').write_text(json.dumps(metrics), encoding='utf-8')
            mesh.stop()
    finally:
        mesh.close()
        stack.close()


class DistributedTests(unittest.TestCase):
    def run_comparison(self, pipe_transport=False, full=False, latest=False):
        if full:
            updater, episodes, arguments = full_fixture()
            random.seed(91)
            updater.update(episodes, **arguments)
            model, optimizer = updater.model, updater.optimizer
        else:
            model, optimizer, rows, cfg = fixture(latest)
            for seed in ((91,) if latest else (91, 92)):
                random.seed(seed)
                update(model, optimizer, rows, cfg, 'cpu')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as tmp:
            pipes = mp.get_context('spawn').Pipe() if pipe_transport else None
            try:
                mp.spawn(run_rank, args=(port, tmp, pipes, full, latest), nprocs=2, join=True)
            finally:
                if pipes:
                    for connection in pipes:
                        connection.close()
            actual = torch.load(Path(tmp)/'actual.pt', weights_only=True)
            differences = sorted(((float((actual['model'][name]-value).abs().max()), name)
                                  for name, value in model.state_dict().items()), reverse=True)
            print('FP32 reduction comparison:', differences[:5], flush=True)
            for name, expected in model.state_dict().items():
                torch.testing.assert_close(actual['model'][name], expected, rtol=3e-5, atol=3e-6, msg=name)
            expected = optimizer.state_dict()['state']
            for pid, values in expected.items():
                for name, value in values.items():
                    torch.testing.assert_close(actual['optimizer']['state'][pid][name], value, rtol=4e-5, atol=4e-6)
            metrics = json.loads((Path(tmp)/'metrics.json').read_text())
            self.assertEqual(metrics['learner_world_size'], 2)
            if latest:
                self.assertTrue(metrics['kl_early_stop'])
                self.assertGreater(metrics['critic_completion']['optimizer_steps'], 0)
                self.assertEqual(metrics['critic_update_coverage']['accepted_fraction'], 1.)
                self.assertGreater(metrics['signed_credit']['groups']['all_exam']['negative'], 0)
            elif not full:
                self.assertEqual(metrics['optimizer_steps'], 2)
                self.assertEqual(metrics['update_coverage']['accepted_unique'], 5)
            else:
                self.assertEqual(metrics['decision_kinds']['outer']['optimization_samples'], 5)

    def test_full_produce_two_process_update_math(self):
        self.run_comparison(pipe_transport=True, full=True)

    def test_two_process_update_math_with_pipe_test_transport(self):
        self.run_comparison(pipe_transport=True)

    def test_signed_credit_and_critic_completion_two_process_adam_parity(self):
        self.run_comparison(pipe_transport=True, latest=True)

    @unittest.skipIf(os.name == 'nt', 'Local Windows PyTorch wheel cannot initialize Gloo; run on Linux')
    def test_native_gloo_two_ranks(self):
        self.run_comparison()
