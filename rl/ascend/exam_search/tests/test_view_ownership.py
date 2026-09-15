"""Native public responses cannot be mutated by a planner's encoder callback."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(HERE), str(HERE/'runtime/shared'), str(HERE/'runtime/arena')]
from draftrl import search_adapter
from gakumas_arena.engine.search import SearchClient, SearchWorld
from gakumas_arena.engine.training import make_training_entry


class ViewOwnershipTest(unittest.TestCase):
    def test_encoder_cannot_modify_borrowed_native_views(self):
        entry = make_training_entry([647]*8, turn_types=['vocal']*2)
        original_observe, original_step = SearchWorld.observe, SearchWorld.step
        original_encode = search_adapter.encoded_view
        captured = []

        def capture(view):
            captured.append((view, copy.deepcopy(view)))
            return view

        def observe(world, **kwargs):
            return capture(original_observe(world, **kwargs))

        def step(world, command, **kwargs):
            result = original_step(world, command, **kwargs)
            if 'view' in result:
                capture(result['view'])
            return result

        def encode_and_mutate(view):
            result = original_encode(view)
            # An encoder that retains or mutates its argument must not change
            # the native response, tree key, subsequent simulation or recorder.
            view['observation'].clear()
            view['partial_selection'].append(-999)
            view['actions'].clear()
            return result

        def predict(encoded, deadline):
            return [1/len(encoded.submissions)]*len(encoded.submissions), 0.

        kwargs = dict(score_scale=150000., policy_version='ownership-test:0',
                      search_seed=55382, simulations=16, particles=4,
                      seconds=20., sampling_ms=2000, max_depth=8,
                      rollout_steps=8, predictor=predict)
        with SearchClient(max_worlds=2) as recorder:
            real = recorder.create_recorded_exam(entry, seed=31)
            history = real.export_public_history()
            reference = search_adapter.root_search(None, entry, history, **kwargs)
            with patch.object(SearchWorld, 'observe', observe), patch.object(SearchWorld, 'step', step), \
                    patch.object(search_adapter, 'encoded_view', encode_and_mutate):
                actual = search_adapter.root_search(None, entry, history, **kwargs)
            self.assertTrue(reference['valid_training_target'])
            self.assertTrue(actual['valid_training_target'])
            self.assertEqual(actual['search'], reference['search'])
            self.assertGreater(len(captured), 16)
            for view, saved in captured:
                self.assertEqual(view, saved)
            self.assertEqual(real.export_public_history(), history)
            real.close()


if __name__ == '__main__':
    unittest.main()
