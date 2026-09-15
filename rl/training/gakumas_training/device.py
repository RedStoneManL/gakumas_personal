"""Explicit CPU/CUDA/Ascend selection and accelerator state handling.

torch_npu is optional and is imported only when NPU execution is requested.
Arena workers remain CPU processes; only the learner owns an accelerator.
"""
from __future__ import annotations

import importlib
import random
import re
from contextlib import contextmanager

import torch


def device_kind(value):
    value = str(value)
    if not re.fullmatch(r"cpu|(?:cuda|npu)(?::[0-9]+)?", value):
        raise ValueError("Device must be cpu, cuda[:N], or npu[:N]")
    return value.split(":", 1)[0]


def resolve_device(value):
    """Register the requested backend before parsing its torch.device string."""
    kind = device_kind(value)
    if kind == "npu":
        try:
            importlib.import_module("torch_npu")
        except (ImportError, OSError) as error:
            raise RuntimeError(
                "NPU requested: install matching PyTorch/torch_npu/CANN versions "
                "and source the CANN set_env.sh before starting training"
            ) from error
    if kind != "cpu":
        backend = getattr(torch, kind, None)
        if backend is None or not backend.is_available():
            raise RuntimeError(f"{kind.upper()} requested but unavailable; no CPU fallback")
        index = int(str(value).split(":")[1]) if ":" in str(value) else backend.current_device()
        if not 0 <= index < backend.device_count():
            raise ValueError(f"{value} is outside the {backend.device_count()} visible {kind.upper()} devices")
        backend.set_device(index)
    return torch.device(value)


def seed_device(seed, device):
    kind = device_kind(device)
    if kind == 'npu':
        # Each rank owns one NPU. Avoid torch.manual_seed's custom-device
        # manual_seed_all hook, which touches all visible devices.
        torch.random.default_generator.manual_seed(seed)
        torch.npu.manual_seed(seed)
    else:
        torch.manual_seed(seed)
    if kind == "cuda":
        getattr(torch, kind).manual_seed_all(seed)


def accelerator_rng():
    """Do not initialize an unused accelerator just to save a CPU checkpoint."""
    result = {}
    for kind in ("cuda", "npu"):
        backend = getattr(torch, kind, None)
        if backend is None or not backend.is_initialized():
            result[kind] = []
        elif kind == 'npu':
            index = backend.current_device()
            result[kind] = {'device_index': index, 'visible_devices': backend.device_count(),
                            'state': backend.get_rng_state(index)}
        else:
            result[kind] = backend.get_rng_state_all()
    return result


def restore_accelerator_rng(value):
    # Check every saved topology before changing any generator.
    for kind in ("cuda", "npu"):
        states = value.get(kind, [])
        backend = getattr(torch, kind, None)
        if kind == 'npu' and states:
            if (not isinstance(states, dict) or backend is None or not backend.is_available()
                    or states.get('visible_devices') != backend.device_count()
                    or states.get('device_index') != backend.current_device()):
                raise ValueError('Resume NPU topology differs from the saved RNG state')
            continue
        if states and (backend is None or not backend.is_available()
                       or len(states) != backend.device_count()):
            raise ValueError(f"Resume {kind.upper()} topology differs from the saved RNG state")
    for kind in ("cuda", "npu"):
        if value.get(kind):
            if kind == 'npu':
                torch.npu.set_rng_state(value[kind]['state'].cpu(), value[kind]['device_index'])
            else:
                getattr(torch, kind).set_rng_state_all([s.cpu() for s in value[kind]])


def capture_retry_rng():
    return random.getstate(), torch.get_rng_state(), accelerator_rng()


def restore_retry_rng(state):
    restore_accelerator_rng(state[2])
    random.setstate(state[0])
    torch.set_rng_state(state[1].cpu())


@contextmanager
def preserve_rng():
    state = capture_retry_rng()
    try:
        yield
    finally:
        restore_retry_rng(state)


def empty_accelerator_cache():
    for kind in ("cuda", "npu"):
        backend = getattr(torch, kind, None)
        if backend is not None and backend.is_initialized():
            backend.empty_cache()


def is_accelerator_oom(error, device):
    if isinstance(error, torch.OutOfMemoryError):
        return True
    # Older torch_npu versions report allocator OOM as RuntimeError. Do not
    # retry unsupported operators, host-memory failures or arbitrary ACL errors.
    return device_kind(device) == "npu" and "NPU out of memory" in str(error)


def model_device(model):
    return next(model.parameters()).device


def optimizer_options(model):
    # Avoid CUDA-oriented foreach/fused implementations on PrivateUse1 devices.
    return {"foreach": False} if model_device(model).type == "npu" else {}


def load_optimizer_state(optimizer, state, device):
    # load_state_dict replaces constructor options with checkpoint options.
    # A CUDA checkpoint must not re-enable foreach/fused/capture on the NPU.
    if device_kind(device) == 'npu':
        state = {**state, 'param_groups': [
            {**group, 'foreach': False, 'fused': False, 'capturable': False}
            for group in state['param_groups']]}
    optimizer.load_state_dict(state)


def synchronize(device):
    kind = device_kind(device)
    if kind != "cpu":
        getattr(torch, kind).synchronize(device)


def device_report(device):
    kind = device_kind(device)
    report = {"device": str(device), "torch": str(torch.__version__),
              "cuda_runtime": torch.version.cuda}
    if kind != "cpu":
        backend = getattr(torch, kind)
        report.update(device_name=backend.get_device_name(device),
                      visible_devices=backend.device_count())
    if kind == "npu":
        report["torch_npu"] = str(importlib.import_module("torch_npu").__version__)
    return report
