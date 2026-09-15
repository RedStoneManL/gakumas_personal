from pathlib import Path
import tempfile
import unittest

from gakumas_training.arena_adapter.environment import _produce_rules_digest, ensure_arena


class PortabilityTests(unittest.TestCase):
    def make_tree(self, root):
        files = {'gakumas_arena/scoring/hif.py': b'python rules',
                 'gakumas_arena/scoring/reference.json': b'{"value": 1}',
                 'gakumas_arena/scenarios/hif.yaml': b'scenario: hif',
                 'gakumas_rl/configs/reward.json': b'{"value": 1}',
                 'raw/ProduceEffect.yaml': b'effect: x'}
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return files

    def test_rule_hash_is_relocation_invariant_and_covers_runtime_dependencies(self):
        with tempfile.TemporaryDirectory(prefix='gakumas-hash-a-') as first, \
             tempfile.TemporaryDirectory(prefix='gakumas-hash-b-') as second:
            first, second = Path(first), Path(second)
            files = self.make_tree(first)
            self.make_tree(second)
            reference = _produce_rules_digest(first, first / 'raw')
            self.assertEqual(reference, _produce_rules_digest(second, second / 'raw'))
            for name, content in files.items():
                with self.subTest(path=name):
                    (second / name).write_bytes(content + b'changed')
                    self.assertNotEqual(reference, _produce_rules_digest(second, second / 'raw'))
                    (second / name).write_bytes(content)

    def test_explicit_wrong_arena_root_cannot_fall_back_to_installed_package(self):
        with tempfile.TemporaryDirectory(prefix='gakumas-missing-arena-') as directory:
            with self.assertRaisesRegex(FileNotFoundError, 'Explicit Arena root'):
                ensure_arena(directory)


if __name__ == '__main__':
    unittest.main()
