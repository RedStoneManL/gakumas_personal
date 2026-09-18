"""Actual five-profile public pipeline smoke; bounded native exams, CPU only."""
import copy
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE / "runtime/shared"), str(HERE / "runtime/arena")]
for training_root in (HERE.parents[1] / "training", HERE.parent / "training"):
    if (training_root / "gakumas_training").is_dir():
        sys.path.insert(0, str(training_root))
        break
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import torch
from prepare_relational import semantic_requests
from draftrl.native_semantics import NativeSemantics
from draftrl.encoding import DraftEncoder, DraftState, encode_guidance, encode_drink_inventory, encode_exam
from draftrl.guidance import Guidance
from draftrl.drinks import DrinkInventory
from draftrl.memory import MemoryState
from draftrl.choice import ChoiceState
from draftrl.model import DraftPolicy
from draftrl import fast_collate, relational_runtime
from draftrl.relational_encoding import reconstruct_nodes
from gakumas_arena.engine.training import TrainingExam, close_training_worker


def short_entry(entry):
    entry = copy.deepcopy(entry)
    entry["context"]["turn_types"] = ["vocal", "dance", "visual"]
    entry["context"]["stage"]["turnCounts"] = {"vocal": 1, "dance": 1, "visual": 1}
    return entry


def public_encoding(observation):
    return ChoiceState(observation).encode() if observation.get("choice") else encode_exam(observation)


def spawned_precollate(encoded):
    """Spawn must reconstruct semantics from its inherited offline path."""
    torch.set_num_threads(1)
    with patch("draftrl.native_semantics.subprocess.run", side_effect=AssertionError("worker inference launched Node")):
        return fast_collate.precollate(encoded)


@unittest.skipUnless(shutil.which("node"), "Node required for native public pipeline smoke")
class RelationalRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.temporary = tempfile.TemporaryDirectory(prefix="arena-relational-runtime-")
        cls.cache = Path(cls.temporary.name) / "semantics.json"
        cls.catalog = json.loads((HERE / "setup/catalog.json").read_text(encoding="utf-8"))
        cls.profiles = json.loads((HERE / "setup/profiles.json").read_text(encoding="utf-8"))
        bridge = NativeSemantics()
        cards, programs = semantic_requests(cls.catalog, cls.profiles)
        cls.choice_program = "at:afterStartOfTurn { holdSelected[hand](1); limit:1 }"
        bridge.prepare(cards=cards, programs=programs + [cls.choice_program])
        bridge.dump(cls.cache)
        cls.previous_env = os.environ.get(relational_runtime.ENV)
        os.environ[relational_runtime.ENV] = str(cls.cache)
        cls.examples, cls.entries, cls.initial_observations = {}, {}, {}
        for profile in cls.profiles:
            entry, spec = copy.deepcopy(profile["entry"]), copy.deepcopy(profile["spec"])
            spec["memory_mode"] = "hif"
            draft = DraftState(DraftEncoder(entry, cls.catalog, spec))
            examples = [draft.encode()]
            picks = 0
            while not draft.done:
                commands = draft.commands()
                stop = next((c for c in commands if c["method"] == "finish_draft"), None)
                if stop:
                    draft.apply(stop)
                else:
                    draft.apply(commands[picks % len(commands)])
                    picks += 1
            entry = draft.complete()
            guidance = Guidance(entry, spec)
            examples.append(encode_guidance(guidance, cls.catalog))
            guide = next((a for a in guidance.actions() if a["method"] == "guide_card"), None)
            if guide is not None:
                guidance.apply(guide)
            guidance.apply({"method": "finish_guidance"})
            entry = guidance.entry
            inventory = DrinkInventory(profile["drink_pool"], 91822, capacity=4)
            examples.append(encode_drink_inventory(inventory, entry, cls.catalog, spec))
            inventory.apply(inventory.commands()[0])
            inventory.apply({"method": "finish_drinks"})
            entry["resources"]["drinks"] = list(inventory.selected)
            memories = MemoryState(entry, cls.catalog, spec)
            examples.append(memories.encode())
            memories.apply(memories.commands()[0])
            memories.apply({"method": "finish_memory"})
            entry = short_entry(memories.entry)
            native = TrainingExam(entry, seed=91823)
            observation = native.observe()
            examples.append(public_encoding(observation))
            cls.examples[profile["id"]] = examples
            cls.entries[profile["id"]] = entry
            cls.initial_observations[profile["id"]] = observation

    @classmethod
    def tearDownClass(cls):
        close_training_worker()
        relational_runtime._compiler.cache_clear()
        if cls.previous_env is None:
            os.environ.pop(relational_runtime.ENV, None)
        else:
            os.environ[relational_runtime.ENV] = cls.previous_env
        cls.temporary.cleanup()

    def test_every_actual_profile_and_phase_has_cache_only_relational_view(self):
        with patch("draftrl.native_semantics.subprocess.run", side_effect=AssertionError("semantic inference launched Node")):
            for profile_id, examples in self.examples.items():
                self.assertEqual({e.phase for e in examples}, {0, 1, 2, 3, 4})
                for encoded in examples:
                    original = (copy.deepcopy(encoded.atoms), copy.deepcopy(encoded.edges))
                    side = relational_runtime.view(encoded)
                    self.assertEqual(side.diagnostics["unresolved_programs"], 0, (profile_id, encoded.phase))
                    self.assertEqual(side.diagnostics["unresolved_card_semantics"], 0, (profile_id, encoded.phase))
                    self.assertEqual(side.submissions, encoded.submissions)
                    self.assertEqual((encoded.atoms, encoded.edges), original)

    def assert_batch_equal(self, expected, actual, path=""):
        self.assertEqual(set(expected), set(actual), path)
        for key, value in expected.items():
            name = path + "/" + key
            other = actual[key]
            if isinstance(value, dict):
                self.assert_batch_equal(value, other, name)
            elif isinstance(value, torch.Tensor):
                self.assertEqual(value.dtype, other.dtype, name)
                self.assertTrue(torch.equal(value, other), name)
            else:
                self.assertEqual(value, other, name)

    def test_nested_worker_precollate_merge_matches_direct_heterogeneous_collate(self):
        examples = self.examples["saki-hif"]
        direct = fast_collate.collate(examples)
        merged = fast_collate.merge([fast_collate.precollate(e) for e in examples])
        self.assertIn("relational", direct)
        self.assert_batch_equal(direct, merged)

    def test_spawned_worker_inherits_offline_semantics_and_matches_local_batch(self):
        examples = [copy.deepcopy(self.examples["saki-hif"][-1]), copy.deepcopy(self.examples["hiro-hif"][-1])]
        for encoded in examples:
            encoded.__dict__.pop("_relational_cached", None)
        context = multiprocessing.get_context("spawn")
        with context.Pool(1) as pool:
            prepared = pool.map_async(spawned_precollate, examples).get(timeout=45)
        self.assert_batch_equal(fast_collate.collate(examples), fast_collate.merge(prepared))

    def test_real_heterogeneous_phases_forward_backward_one_cpu_step(self):
        torch.manual_seed(918)
        batch = fast_collate.collate(self.examples["saki-hif"])
        model = DraftPolicy(width=16, lexical=4, depth=2, quantiles=32, relational=True)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
        logits, values, quantiles = model.learning_forward(batch)
        self.assertTrue(torch.isfinite(logits[batch["mask"]]).all())
        self.assertTrue(torch.isfinite(values).all())
        loss = -torch.log_softmax(logits, -1)[:, 0].mean() + values.square().mean() + quantiles.square().mean()
        loss.backward()
        self.assertTrue(all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None))
        self.assertGreater(sum(float(p.grad.abs().sum()) for name, p in model.named_parameters()
                               if "relational" in name and p.grad is not None), 0)
        optimizer.step()

    def test_joint_update_accepts_real_views_and_nonzero_detached_search_ce(self):
        # The detached target here is a plumbing fixture, not a claim that an
        # actual search discovered this distribution or that a policy improved.
        from draftrl.distribution import distributions
        from draftrl.ppo import update
        from draftrl.relational_training import parameter_groups
        torch.manual_seed(919)
        model = DraftPolicy(width=16, lexical=4, depth=2, quantiles=32, relational=True)
        settings = {"temperature": 1., "uniform_mix": 0., "entropy_coefficient": 0.}
        examples = self.examples["saki-hif"]
        records = []
        for i, encoded in enumerate(examples + [examples[-1]]):
            kind = "search" if i == len(examples) else "ppo"
            with torch.no_grad():
                batch = fast_collate.collate([encoded])
                logits, values = model(batch)
                distribution, _ = distributions(logits, batch["mask"], [settings])
                logp = float(distribution.log_prob(torch.tensor([0]))[0])
            row = {"encoded": encoded, "action": 0, "old_logp": logp if kind == "ppo" else None,
                   "old_value": float(values[0]), "return": 1. + i * .1,
                   "profile": "saki-hif", "loss_kind": kind, "exploration": settings,
                   "policy_version": "relational-smoke:0"}
            if kind == "search":
                probability = [0.] * len(encoded.submissions)
                probability[-1] = 1.
                row["search"] = {"actions": copy.deepcopy(encoded.submissions), "target_policy": probability,
                                 "target_budget_eligible": True, "root_action_coverage": 1.}
            records.append(row)
        config = {"_policy_version": "relational-smoke:0", "sample_efficiency": {"advantage_mode": "mc", "ppo_epochs_max": 1},
                  "search": {"loss_coefficient": .1}, "practice": {}, "epochs": 1, "effective_minibatch": 6,
                  "minibatch": 2, "clip": .2, "target_kl": .05, "value_coefficient": .5, "max_grad": .5}
        rates = dict.fromkeys(("exam", "drink", "draft", "guidance", "memory"), 1e-4)
        optimizer = torch.optim.Adam(parameter_groups(model, rates))
        before = {name: p.detach().clone() for name, p in model.named_parameters() if "actor_relational.policy_heads.exam" in name}
        result = update(model, optimizer, records, config, "cpu")
        self.assertGreater(result["search_loss"], 0)
        changed = any(not torch.equal(before[name], parameter) for name, parameter in model.named_parameters() if name in before)
        self.assertTrue(changed)

    def test_all_five_native_short_exams_finish_through_public_only_actions(self):
        for number, (profile_id, entry) in enumerate(self.entries.items()):
            native = TrainingExam(entry, seed=72001 + number)
            observation = native.observe()
            steps = 0
            played_turns = set()
            used_drink = False
            while not observation["result"]["terminated"]:
                side = relational_runtime.view(public_encoding(observation))
                self.assertEqual(side.diagnostics["unresolved_programs"], 0, profile_id)
                for time_node in (n for n in reconstruct_nodes(side) if n["entity_type"] == "time"):
                    self.assertEqual(time_node["current_turn_raw"], observation["state"]["turnsElapsed"])
                    self.assertEqual(time_node["relative_position"], time_node["position"] - observation["state"]["turnsElapsed"])
                if observation.get("choice"):
                    selection = ChoiceState(observation)
                    command = None
                    while not selection.done:
                        command = selection.apply(selection.commands()[0])
                    observation = native.choose(command["indices"], decision_version=command["decision_version"])
                else:
                    turn = observation["state"]["turnsElapsed"]
                    drink = next((a for a in observation["actions"] if a["type"] == "drink"), None)
                    play = next((a for a in observation["actions"] if a["type"] == "play"), None)
                    if drink is not None and not used_drink:
                        command, used_drink = drink, True
                    elif play is not None and turn not in played_turns:
                        command = play
                        played_turns.add(turn)
                    else:
                        command = next(a for a in observation["actions"] if a["type"] == "end_turn")
                    observation = native.act(command)
                steps += 1
                self.assertLess(steps, 40)
            self.assertFalse(observation["result"]["truncated"])
            self.assertTrue(played_turns, profile_id)
            self.assertTrue(used_drink, profile_id)

    def test_program_string_collection_ignores_display_labels_and_targets(self):
        value = {"name": "do:score+=999", "description": "effects is not code here",
                 "action": "select_card", "payment": "native_card_cost",
                 "effects": "at:turn { score+=1 }", "target": {"type": "identifier", "name": "cost"}}
        self.assertEqual(list(relational_runtime.program_strings(value)), [value["effects"]])

    def test_native_pending_choice_preserves_shared_counter_joins_under_renaming(self):
        entry = copy.deepcopy(self.entries["ume-campus"])
        entry["persistent_effects"].append({"id": "choice-probe", "effects": self.choice_program, "counters": {}})
        observation = TrainingExam(entry, seed=91871).observe()
        self.assertIsNotNone(observation["choice"])
        encoded = public_encoding(observation)
        side = relational_runtime.view(encoded)
        nodes = reconstruct_nodes(side)
        active = next(n for n in nodes if n.get("symbol") == "triggeredEffect")
        self.assertEqual(active["value"]["source"], observation["state"]["triggeredEffect"]["source"])
        self.assertEqual(active["value"]["phase"], "afterStartOfTurn")
        self.assertTrue(any(n.get("is_current") for n in nodes))
        self.assertTrue(any(label == "out:source_p_item" for _, _, label in side.edges))
        renamed = copy.deepcopy(observation)
        def rename(value):
            if isinstance(value, dict):
                for key, item in list(value.items()):
                    if key in {"effectInstanceId", "currentEffectInstanceId"} and type(item) is int:
                        value[key] = item + 17000
                    elif key == "effectCounters":
                        value[key] = {str(int(k) + 17000): v for k, v in item.items()}
                    else:
                        rename(item)
            elif isinstance(value, list):
                for item in value:
                    rename(item)
        rename(renamed)
        other = relational_runtime.view(public_encoding(renamed))
        self.assertEqual(side.atoms, other.atoms)
        self.assertEqual(side.edges, other.edges)
        counter_targets = {dst for _, dst, label in side.edges if label == "out:uses_counter"}
        scopes = encoded.relation_context["effect_groups"]
        self.assertGreater(len(scopes), 0)
        self.assertEqual(len(counter_targets), len(set(scopes.values())))


if __name__ == "__main__":
    unittest.main()
