"""Inspect the provider's ARM/Ascend environment without installing anything."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--expected-npus', type=int, default=8)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    report = {'passed': False, 'python': sys.version, 'system': platform.platform(),
              'architecture': platform.machine(), 'cpu_count': os.cpu_count(),
              'cpu_affinity_count': len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else None}
    try:
        if sys.version_info < (3, 11):
            raise RuntimeError('Python >= 3.11 required')
        if platform.system() != 'Linux' or platform.machine().lower() not in ('aarch64', 'arm64'):
            raise RuntimeError('This acceptance command targets Linux ARM64')
        node = shutil.which('node')
        if node is None:
            raise RuntimeError('Install an ARM64 Node.js >= 20 and add it to PATH')
        report['node'] = subprocess.check_output([node, '--version'], text=True, timeout=15).strip()
        if int(report['node'].lstrip('v').split('.')[0]) < 20:
            raise RuntimeError('Node.js >= 20 required')
        import torch
        import torch_npu
        report.update(torch=str(torch.__version__), torch_npu=str(torch_npu.__version__))
        versions = [re.match(r'(\d+)\.(\d+)\.(\d+)', v) for v in (str(torch.__version__), str(torch_npu.__version__))]
        if not all(versions) or versions[0].groups() != versions[1].groups():
            raise RuntimeError('Check PyTorch/torch_npu version pairing against the official compatibility matrix')
        if tuple(map(int, versions[0].groups()[:2])) < (2, 5):
            raise RuntimeError('This trainer requires PyTorch >= 2.5')
        if not torch.npu.is_available() or torch.npu.device_count() < args.expected_npus:
            raise RuntimeError(f'Expected at least {args.expected_npus} visible NPUs')
        report['npu_count'] = torch.npu.device_count()
        report['npu_names'] = [torch.npu.get_device_name(i) for i in range(torch.npu.device_count())]
        report['cann_version_files'] = {}
        for name in ('/usr/local/Ascend/ascend-toolkit/latest/version.cfg',
                     '/usr/local/Ascend/cann/version.info', '/usr/local/Ascend/ascend-toolkit/latest/version.info'):
            path = Path(name)
            if path.is_file():
                report['cann_version_files'][name] = path.read_text(errors='replace')[:8000]
        if shutil.which('npu-smi'):
            result = subprocess.run(['npu-smi', 'info'], capture_output=True, text=True, timeout=30)
            report['npu_smi'] = {'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
        report['passed'] = True
    except BaseException as error:
        report['error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
