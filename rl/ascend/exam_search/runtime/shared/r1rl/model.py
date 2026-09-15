import torch
from torch import nn
from round2rl.model import PolicyValue

MODEL_SCHEMA = 'hif-round1-joint-drink-exam-policy/1'


class JointPolicy(PolicyValue):
    def __init__(self, width=96, lexical=16):
        super().__init__(width, lexical)
        self.drink_policy_head = nn.Sequential(nn.Linear(width * 2, width), nn.Tanh(), nn.Linear(width, 1))
        self.drink_value_head = nn.Linear(width, 1)
        nn.init.orthogonal_(self.drink_policy_head[-1].weight, 0.01)
        nn.init.zeros_(self.drink_policy_head[-1].bias)

    def policy(self, b):
        nodes, state = self.actor(b)
        selected = nodes[b['action_index']]
        features = torch.cat([selected, state[:, None].expand(-1, selected.shape[1], -1)], -1)
        logits = torch.where(b['drink_phase'][:, None],
            self.drink_policy_head(features).squeeze(-1), self.policy_head(features).squeeze(-1))
        return logits.masked_fill(~b['mask'], -torch.inf)

    def forward(self, b):
        logits = self.policy(b)
        _, state = self.critic(b)
        values = torch.where(b['drink_phase'], self.drink_value_head(state).squeeze(-1),
                             self.value_head(state).squeeze(-1))
        return logits, values
