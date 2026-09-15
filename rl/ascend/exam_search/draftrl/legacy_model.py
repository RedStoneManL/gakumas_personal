import torch
from torch import nn
from r1rl.model import JointPolicy

MODEL_SCHEMA = 'hif-memory-draft-drink-exam-policy/1'


class DraftPolicy(JointPolicy):
    def __init__(self, width=96, lexical=16):
        super().__init__(width, lexical)
        self.draft_policy_head = nn.Sequential(nn.Linear(width * 2, width), nn.Tanh(), nn.Linear(width, 1))
        self.draft_value_head = nn.Linear(width, 1)
        self.guidance_policy_head = nn.Sequential(nn.Linear(width * 2, width), nn.Tanh(), nn.Linear(width, 1))
        self.guidance_value_head = nn.Linear(width, 1)
        nn.init.orthogonal_(self.guidance_policy_head[-1].weight, 0.01)
        nn.init.zeros_(self.guidance_policy_head[-1].bias)
        nn.init.orthogonal_(self.draft_policy_head[-1].weight, 0.01)
        nn.init.zeros_(self.draft_policy_head[-1].bias)
        self.memory_policy_head = nn.Sequential(nn.Linear(width * 2, width), nn.Tanh(), nn.Linear(width, 1))
        self.memory_value_head = nn.Linear(width, 1)
        nn.init.orthogonal_(self.memory_policy_head[-1].weight, 0.01)
        nn.init.zeros_(self.memory_policy_head[-1].bias)

    def policy(self, b):
        nodes, state = self.actor(b)
        selected = nodes[b['action_index']]
        features = torch.cat([selected, state[:, None].expand(-1, selected.shape[1], -1)], -1)
        logits = torch.where(b['drink_phase'][:, None], self.drink_policy_head(features).squeeze(-1),
                             self.policy_head(features).squeeze(-1))
        logits = torch.where((b['phase'] == 2)[:, None], self.draft_policy_head(features).squeeze(-1), logits)
        logits = torch.where((b['phase'] == 3)[:, None], self.guidance_policy_head(features).squeeze(-1), logits)
        logits = torch.where((b['phase'] == 4)[:, None], self.memory_policy_head(features).squeeze(-1), logits)
        return logits.masked_fill(~b['mask'], -torch.inf)

    def forward(self, b):
        logits = self.policy(b)
        _, state = self.critic(b)
        values = torch.where(b['drink_phase'], self.drink_value_head(state).squeeze(-1), self.value_head(state).squeeze(-1))
        values = torch.where(b['phase'] == 2, self.draft_value_head(state).squeeze(-1), values)
        values = torch.where(b['phase'] == 3, self.guidance_value_head(state).squeeze(-1), values)
        values = torch.where(b['phase'] == 4, self.memory_value_head(state).squeeze(-1), values)
        return logits, values
