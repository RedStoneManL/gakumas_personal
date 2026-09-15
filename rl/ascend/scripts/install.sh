#!/usr/bin/env bash
set -euo pipefail
bundle_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-python3}"
"${python_bin}" -c 'import sys,torch,torch_npu; assert sys.version_info >= (3,11); print("Inherited:",sys.version,torch.__version__,torch_npu.__version__)'
node --version
# Inherit the provider's matched torch/CANN installation. No torch or driver
# replacement is performed. Dependency installation is an explicit user command.
"${python_bin}" -m venv --system-site-packages "${bundle_root}/.venv"
training_python="${bundle_root}/.venv/bin/python"
"${training_python}" -m pip install 'setuptools>=68' 'gymnasium>=0.29' 'numpy>=1.26' 'pyyaml>=6.0' 'orjson>=3.9' 'pydantic>=2.6'
"${training_python}" -m pip install --no-deps --no-build-isolation -e "${bundle_root}/arena" -e "${bundle_root}/training"
"${training_python}" -m pip check
printf 'Ready. Activate with: source "%s/.venv/bin/activate"\n' "${bundle_root}"
