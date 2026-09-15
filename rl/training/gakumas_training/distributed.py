"""Replicated full-produce/exam PPO learners; rank zero owns all Arena games."""
from dataclasses import asdict
import torch
from .collectives import CollectiveGroup, cpu_copy
from .device import load_optimizer_state

ACTIVE = None


def world_size():
    return ACTIVE.size if ACTIVE is not None else 1


class TrainingLearners(CollectiveGroup):
    def update(self, updater, episodes, arguments):
        self.broadcast({'command': 'update', 'config': asdict(updater.config),
            'model_config': asdict(updater.model.config), 'model': cpu_copy(updater.model.state_dict()),
            'optimizer': cpu_copy(updater.optimizer.state_dict()), 'episodes': episodes, 'arguments': arguments})
        return updater.update(episodes, **arguments, mesh=self)

    def serve(self):
        from .models import ModelConfig, PolicyValueNet
        from .algorithms.ppo import PPOConfig, PPOUpdater
        while True:
            payload = self.broadcast()
            if payload['command'] == 'stop':
                return
            if payload['command'] != 'update':
                raise ValueError('Unknown learner command')
            model = PolicyValueNet(ModelConfig(**payload['model_config'])).to(self.device)
            model.load_state_dict(payload['model'], strict=True)
            updater = PPOUpdater(model, PPOConfig(**payload['config']))
            load_optimizer_state(updater.optimizer, payload['optimizer'], self.device)
            updater.update(payload['episodes'], **payload['arguments'], mesh=self)
            del model, updater, payload

    def stop(self):
        if self.size > 1:
            self.broadcast({'command': 'stop'})

    def close(self):
        if torch.distributed.is_initialized():
            torch.distributed.destroy_process_group()
