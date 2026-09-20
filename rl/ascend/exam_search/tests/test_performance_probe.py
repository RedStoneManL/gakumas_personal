"""Short probes must keep visible course metadata aligned and production unchanged."""
import copy
import unittest
from draftrl.performance_probe import shorten_course


class PerformanceProbeTests(unittest.TestCase):
    def fixture(self):
        colors = ['vocal', 'dance', 'visual'] * 3
        return ({'context': {'turn_types': colors, 'stage': {}}},
                {'generalist_task': {'turn_types': colors}},
                {'course_id': 'research-9t'})

    def test_probe_course_and_public_input_agree_without_mutating_source(self):
        values = self.fixture()
        original = copy.deepcopy(values)
        entry, spec, meta = shorten_course(*values, {'performance_probe': True, 'performance_probe_turns': 3})
        self.assertEqual(values, original)
        self.assertEqual(entry['context']['stage']['turnCounts'], dict(vocal=1, dance=1, visual=1))
        self.assertEqual(entry['context']['turn_types'], spec['generalist_task']['turn_types'])
        self.assertEqual(meta['public_context'], spec['generalist_task'])
        self.assertEqual(meta['turn_count'], 3)
        self.assertTrue(meta['course_id'].endswith(':perf-3t'))

    def test_production_is_unchanged_and_shortening_requires_explicit_probe(self):
        values = self.fixture()
        unchanged = shorten_course(*values, {})
        self.assertTrue(all(a is b for a, b in zip(values, unchanged)))
        for cfg in ({'performance_probe_turns': 3},
                    {'performance_probe': True, 'performance_probe_turns': True},
                    {'performance_probe': True, 'performance_probe_turns': 1}):
            with self.assertRaises(ValueError):
                shorten_course(*values, cfg)

    def test_bounded_update_covers_profiles_and_phases_and_never_limits_production(self):
        from types import SimpleNamespace
        from draftrl.performance_probe import select_update_records
        records = [{'profile': p, 'encoded': SimpleNamespace(phase=phase), 'return': 1.}
                   for p in ('a', 'b') for phase in range(5) for _ in range(5)]
        self.assertIs(select_update_records(records, {}), records)
        cfg = {'performance_probe': True, 'performance_probe_update_records_per_rank': 20}
        selected = select_update_records(records, cfg)
        self.assertEqual(len(selected), 20)
        self.assertEqual({(r['profile'], r['encoded'].phase) for r in selected},
                         {(p, phase) for p in ('a', 'b') for phase in range(5)})
        self.assertTrue(all(any(r is original for original in records) for r in selected))
        with self.assertRaises(ValueError):
            select_update_records(records, {'performance_probe_update_records_per_rank': 20})
