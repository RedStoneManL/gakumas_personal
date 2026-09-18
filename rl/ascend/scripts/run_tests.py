"""Portable backend and learner-math regression suite (does not launch training)."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
EXAM = ROOT/'exam-search' if (ROOT/'exam-search').is_dir() else ROOT/'exam_search'
TRAINING = ROOT/'training' if (ROOT/'training').is_dir() else ROOT.parent/'training'
TESTS = ROOT/'ascend/tests' if (ROOT/'ascend/tests').is_dir() else ROOT/'tests'

def run_group(label, paths, names):
    # Each task binds a different Arena snapshot. Do not import both engines in
    # one interpreter: their module names are identical but contracts differ.
    inherited = [str(Path(path).resolve()) for path in sys.path if path]
    program = (
        'import sys, unittest\n'
        f'sys.path[:0] = {[str(path) for path in paths] + inherited!r}\n'
        f'suite = unittest.defaultTestLoader.loadTestsFromNames({names!r})\n'
        'result = unittest.TextTestRunner(verbosity=2).run(suite)\n'
        'raise SystemExit(not result.wasSuccessful())\n'
    )
    print(f'=== {label} ===', flush=True)
    return subprocess.run([sys.executable, '-B', '-c', program], check=False).returncode


if __name__ == '__main__':
    core = run_group('training backend and PPO',
                     [TRAINING, TRAINING/'tests', ROOT/'arena'],
                     ['test_device', 'test_ppo', 'test_policy_batch', 'test_cuda_oom_recovery',
                      'test_runtime_execution', 'test_runtime_parallel', 'test_colab_notebook_session',
                      'test_colab_migration'])
    search = run_group('search algorithms and distributed learner math',
                       [TRAINING, TESTS, EXAM, EXAM/'tests',
                        EXAM/'runtime/shared', EXAM/'runtime/arena'],
                       ['test_scaling', 'test_portable_gru', 'test_distributed', 'test_best_of',
                        'test_best_of_search', 'test_search_budgets', 'test_search_bootstrap',
                        'test_soft_value', 'test_view_ownership', 'test_async_collectors',
                        'test_critic_completion', 'test_signed_learning', 'test_joint_search',
                        'test_native_semantics', 'test_prepare_relational',
                        'test_relational_encoding', 'test_relational_model',
                        'test_relational_runtime', 'test_relational_training',
                        'test_relational_bundle'])
    # This predecessor test is an executable script with process-global setup
    # and sys.exit. Keep it isolated from unittest's imported modules.
    print('=== sharded learner script ===', flush=True)
    sharded = subprocess.run([sys.executable, '-B', str(EXAM/'tests/test_sharded.py')], check=False).returncode
    raise SystemExit(bool(core or search or sharded))
