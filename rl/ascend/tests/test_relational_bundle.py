"""Source/deployment layout and v6 archive inventory checks; no training."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ASCEND = Path(__file__).resolve().parents[1]
PROJECT = ASCEND.parents[1]
EXAM = ASCEND / 'exam_search' if (ASCEND / 'exam_search').is_dir() else ASCEND.parent / 'exam-search'
PACKAGER = PROJECT / 'rl/hif-colab/build_training_bundle.py'


def load_packager():
    sys.path.insert(0, str(PACKAGER.parent))
    spec = importlib.util.spec_from_file_location('_relational_bundle_builder', PACKAGER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RelationalDeploymentLayoutTests(unittest.TestCase):
    def test_search_entrypoints_are_present(self):
        names = ('prepare_relational.py', 'draftrl/native_semantics.py', 'draftrl/native_semantics.mjs',
                 'draftrl/relational_encoding.py', 'draftrl/relational_model.py',
                 'draftrl/relational_runtime.py', 'draftrl/relational_training.py')
        self.assertTrue(all((EXAM / name).is_file() for name in names))

    def test_precompiler_resolves_both_repository_and_archive_names(self):
        # The bridge resolves native paths lazily, so importing these two small
        # source files proves entrypoint layout without copying a simulator or
        # invoking Node. ROOT must follow the containing directory's actual name.
        with tempfile.TemporaryDirectory() as tmp:
            for folder in ('exam_search', 'exam-search'):
                root = Path(tmp) / folder
                (root / 'draftrl').mkdir(parents=True)
                shutil.copy2(EXAM / 'prepare_relational.py', root / 'prepare_relational.py')
                shutil.copy2(EXAM / 'draftrl/native_semantics.py', root / 'draftrl/native_semantics.py')
                program = ("import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);"
                           "import prepare_relational as p;import draftrl.native_semantics as n;"
                           "assert p.HERE==Path(sys.argv[1]);assert n.ROOT==p.HERE;"
                           "assert n.ARENA==p.HERE/'runtime/arena/gakumas_arena'")
                result = subprocess.run([sys.executable, '-B', '-c', program, str(root)],
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless(PACKAGER.is_file(), 'source packager is intentionally absent from deployment bundles')
class RelationalSourceBundleTests(unittest.TestCase):
    def test_reviewed_rules_include_all_relational_files(self):
        packager = load_packager()
        sources = packager.collect_training_sources(PROJECT, packager.bundle_rules('ascend'))
        self.assertFalse(packager.RELATIONAL_REQUIRED - set(sources))
        self.assertNotIn(packager.RELATIONAL_CACHE, sources)

    def test_generated_semantics_cache_is_excluded_even_when_present(self):
        packager = load_packager()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / 'exam'
            (source / 'setup').mkdir(parents=True)
            (source / 'setup/relational_semantics.json').write_text('{}', encoding='utf-8')
            (source / 'prepare_relational.py').write_text('# precompiler\n', encoding='utf-8')
            rules = (packager.base.IncludeRule('exam', 'exam-search', ('.py', '.json')),)
            sources = packager.collect_training_sources(workspace, rules)
            self.assertEqual(set(sources), {'exam-search/prepare_relational.py'})

    def test_unknown_bundle_target_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Unknown bundle target'):
            load_packager().bundle_rules('accidental-target')


if __name__ == '__main__':
    unittest.main()
