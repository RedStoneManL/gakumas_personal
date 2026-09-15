"""A clean search worker must never load neural libraries for remote inference."""
import subprocess
import sys
import unittest
from pathlib import Path


class SearchBootstrapTests(unittest.TestCase):
    def test_fresh_worker_import_and_initializer_do_not_load_torch(self):
        code=Path(__file__).resolve().parents[1]
        program='''
import sys,multiprocessing as mp
from pathlib import Path
p=Path(sys.argv[1]);sys.path[:0]=[str(p),str(p/'runtime/shared'),str(p/'runtime/arena')]
from draftrl.process_service import _initialize
assert 'torch' not in sys.modules
ctx=mp.get_context('spawn');requests=ctx.Queue();responses=[ctx.Queue()];counter=ctx.Value('i',0)
try:
    _initialize(requests,responses,counter)
    assert counter.value==1
    assert 'torch' not in sys.modules
finally:
    requests.close();responses[0].close()
print('torch-free initializer passed')
'''
        result=subprocess.run([sys.executable,'-B','-X','utf8','-c',program,str(code)],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('torch-free initializer passed',result.stdout)


if __name__=='__main__':unittest.main()
