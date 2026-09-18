"""Full real-profile semantic coverage, including legal guidance previews."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from prepare_relational import collect_programs, guidance_variants, prepare_catalogue, semantic_requests
from draftrl.native_semantics import NativeSemantics
from draftrl.guidance import Guidance
from draftrl import keycard_focus


@unittest.skipUnless(shutil.which("node"), "Node is needed to prepare the offline semantic catalogue")
class PrepareRelationalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((HERE / "setup/catalog.json").read_text(encoding="utf-8"))
        cls.profiles = json.loads((HERE / "setup/profiles.json").read_text(encoding="utf-8"))
        cls.requests, cls.programs = semantic_requests(cls.catalog, cls.profiles)
        cls.bridge = NativeSemantics()
        cls.bridge.prepare(cards=cls.requests, programs=cls.programs)

    def test_all_five_profiles_fixed_candidate_and_declaration_inputs_are_cached(self):
        self.assertEqual(len(self.profiles), 5)
        with patch("draftrl.native_semantics.subprocess.run", side_effect=AssertionError("inference launched Node")):
            for profile in self.profiles:
                for card in profile["entry"]["cards"] + profile["spec"]["fixed_cards"]:
                    self.bridge.card(card)
                for candidate in profile["spec"]["candidates"]:
                    self.bridge.card(candidate["card"])
                for program in collect_programs(profile):
                    self.bridge.program(program)
            for definition in self.catalog["cards"]:
                self.bridge.card({"definition_id": definition["id"]})

    def test_every_legal_next_guidance_preview_is_prepared(self):
        checked = 0
        with patch("draftrl.native_semantics.subprocess.run", side_effect=AssertionError("guidance preview launched Node")):
            for profile in self.profiles:
                spec = profile["spec"]
                for definition_id, rule in spec["guidance"]["card_rules"].items():
                    # Reach each variant through the real budget/mask code,
                    # independently of the compiler's Cartesian enumeration.
                    for variant in guidance_variants(definition_id, rule):
                        entry = copy.deepcopy(profile["entry"])
                        entry["cards"] = [{"instance_id": "probe", "definition_id": int(definition_id),
                                           "customizations": {}, "growth": {}, "bindings": []}]
                        state = Guidance(entry, spec)
                        for key, level in sorted(variant["customizations"].items()):
                            for next_level in range(1, level + 1):
                                actions = [a for a in state.actions() if a.get("customization_id") == key and a["level"] == next_level]
                                self.assertTrue(actions, (profile["id"], definition_id, variant))
                                # Prefer an available free allowance; subsequent
                                # legal choices still come from Guidance.actions.
                                state.apply(max(actions, key=lambda action: action["use_free_first"]))
                        current = state.entry["cards"][0]
                        self.bridge.card(current)
                        for action in state.actions():
                            if action["method"] != "guide_card":
                                continue
                            after = copy.deepcopy(current)
                            after["customizations"][action["customization_id"]] = action["level"]
                            self.bridge.card(after)
                            checked += 1
        self.assertGreater(checked, 1000)

    def test_runtime_forced_saki_card_and_its_successors_are_cached(self):
        profile = next(p for p in self.profiles if p["id"] == "saki-hif")
        config = {"practice": {"keycard_focus": {"enabled": True, "profile_id": "saki-hif",
                  "card_id": 591, "customization_id": "37", "start_batch": 0, "batches": 1}},
                  "_completed_batches": 0}
        entry, spec = keycard_focus.prepare(profile["entry"], profile["spec"], config, "saki-hif", training=True)
        guidance = Guidance(entry, spec)
        with patch("draftrl.native_semantics.subprocess.run", side_effect=AssertionError("forced preview launched Node")):
            for card in guidance.entry["cards"]:
                self.bridge.card(card)
            for action in guidance.actions():
                if action["method"] != "guide_card":
                    continue
                card = copy.deepcopy(next(c for c in guidance.entry["cards"] if c["instance_id"] == action["instance_id"]))
                card["customizations"][action["customization_id"]] = action["level"]
                self.bridge.card(card)

    def test_incremental_prepare_and_extra_public_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "semantics.json"
            self.bridge.dump(output)
            with patch("draftrl.native_semantics.subprocess.run", side_effect=AssertionError("compatible preparation launched Node")):
                report = prepare_catalogue(output)
            self.assertEqual(report["native_batches"], 0)
            self.assertTrue(report["reused_compatible_cache"])
            self.assertEqual(report["card_variants"], len(self.requests))
            extra = {"cards": [{"definition_id": 591, "customizations": {"37": 1},
                               "bindings": [{"id": "probe", "effects": "at:cardUsed { do:score+=17 }", "counters": {}}]}]}
            path = Path(directory) / "extra.json"
            path.write_text(json.dumps(extra), encoding="utf-8")
            report = prepare_catalogue(output, extra_paths=[path])
            self.assertEqual(report["native_batches"], 1)
            loaded = NativeSemantics(cache_path=output)
            self.assertTrue(loaded.program(extra["cards"][0]["bindings"][0]["effects"]))


class ProgramCollectionTests(unittest.TestCase):
    def test_descriptions_identifiers_and_migration_metadata_are_not_dsl(self):
        data = {"description": "score += 999", "old": "old-model", "name": "drawCard",
                "effect": {"type": "identifier", "name": "score"},
                "effects": "at:turn { do:score+=1; limit:1 }",
                "patches": {"actions": [{"old": "do:score+=1", "new": "do:score+=2"}]}}
        self.assertEqual(collect_programs(data), ["at:turn { do:score+=1; limit:1 }", "do:score+=1", "do:score+=2"])


if __name__ == "__main__":
    unittest.main()
