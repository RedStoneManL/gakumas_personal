import os
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

HERE=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(HERE),str(HERE/'runtime/shared'),str(HERE/'runtime/arena')]
from draftrl.source_stamp import fresh_stamp, install
from gakumas_arena.engine import training
from gakumas_arena.engine.search import SearchClient


class FreshStampTests(unittest.TestCase):
    def test_same_stamp_detects_add_modify_rename_and_delete(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); packages=root/'packages'; packages.mkdir()
            extra=root/'bridge.py';extra.write_text('one')
            def original():
                paths=sorted(packages.rglob('*.js'))+sorted(packages.rglob('*.json'))+[extra]
                return tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in paths)
            def fast():return fresh_stamp(packages,[extra])
            previous=original();self.assertEqual(previous,fast())
            def changed():
                nonlocal previous
                current=original();self.assertEqual(current,fast());self.assertNotEqual(previous,current)
                previous=current
            card=packages/'card.js';card.write_text('one');changed()
            card.write_text('longer');changed()
            directory=packages/'empty'/'nested';directory.mkdir(parents=True)
            config=directory/('config.JSON' if os.name=='nt' else 'config.json')
            config.write_text('{}');changed()
            renamed=packages/'moved.js';card.rename(renamed);changed()
            renamed.unlink();changed()
            extra.write_text('modified adapter');changed()

    def test_native_search_gate_still_rejects_changed_source(self):
        install()
        path=training.VENDOR/'packages'/f'.stamp-guard-{uuid4().hex}.js'
        with SearchClient(max_worlds=2) as client:
            self.assertEqual(client.stats()['status'],'ok')
            try:
                path.write_text('// isolated gate probe',encoding='utf8')
                with self.assertRaisesRegex(training.TrainingError,'version_mismatch'):
                    client.stats()
            finally:
                path.unlink(missing_ok=True)
            self.assertEqual(client.stats()['status'],'ok')


if __name__=='__main__':unittest.main()
