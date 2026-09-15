"""Checkpoints are committed only after complete rollouts and PPO updates."""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import uuid

import numpy as np
import torch

from ..contracts import CONTRACT_VERSION
from ..device import accelerator_rng, restore_accelerator_rng
from .config import RunConfig, initial_execution_settings, validate_execution_settings

CHECKPOINT_SCHEMA = "gakumas-training-safe-batch-v1"


def capture_rng():
    numpy = np.random.get_state()
    return {"python": random.getstate(), "torch": torch.get_rng_state(),
            "numpy": {"generator": numpy[0], "keys": numpy[1].tolist(), "position": numpy[2],
                      "has_gauss": numpy[3], "cached_gaussian": numpy[4]},
            **accelerator_rng()}


def restore_rng(value):
    restore_accelerator_rng(value)
    random.setstate(value["python"])
    torch.set_rng_state(value["torch"].cpu())
    numpy = value["numpy"]
    np.random.set_state((numpy["generator"], np.asarray(numpy["keys"], dtype=np.uint32),
                         numpy["position"], numpy["has_gauss"], numpy["cached_gaussian"]))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def save_checkpoint(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("wb") as stream:
            torch.save(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def load_checkpoint(path, *, task, config, arena_version, model_schema, encoding_schema):
    from ..distributed import world_size
    value = torch.load(Path(path), map_location="cpu", weights_only=True)
    if value.get('learner_world_size', 1) != world_size():
        raise ValueError('Checkpoint learner world size differs; start a new run for topology changes')
    expected = {"checkpoint_schema": CHECKPOINT_SCHEMA, "contract_schema": CONTRACT_VERSION,
                "task": task, "config": config, "arena_version": arena_version,
                "model_schema": model_schema, "encoding_schema": encoding_schema}
    for name, wanted in expected.items():
        if value.get(name) != wanted:
            raise ValueError(f"Checkpoint {name} does not match this run")
    if value.get("boundary") != "after_complete_update":
        raise ValueError("Only completed rollout/update boundaries can be resumed")
    if value.get("policy_version") != value.get("iteration"):
        raise ValueError("Inconsistent checkpoint policy version/iteration")
    if type(value.get("episodes_seen")) is not int or value["episodes_seen"] < 0:
        raise ValueError("Inconsistent checkpoint episodes_seen")
    cursor = config["seed"] + value["episodes_seen"]
    if value.get("seed_cursor") != cursor:
        raise ValueError("Inconsistent checkpoint seed cursor")
    # Older safe-boundary checkpoints have fixed sizes and no override fields.
    value["execution_settings"] = validate_execution_settings(value.get(
        "execution_settings", initial_execution_settings(RunConfig.from_dict(config))))
    pending = value.get("pending_execution_settings", {})
    if not isinstance(pending, dict) or set(pending) - {"workers", "episodes_per_update"}:
        raise ValueError("Invalid pending execution settings")
    validate_execution_settings(pending, base=value["execution_settings"])
    value["pending_execution_settings"] = dict(pending)
    control_state = value.get("execution_control_state", {})
    if not isinstance(control_state, dict):
        raise ValueError("Invalid execution control state")
    value["execution_control_state"] = control_state
    for key in ("model_state", "optimizer_state", "encoder_state", "rng"):
        if key not in value:
            raise ValueError(f"Missing checkpoint {key}")
    if config["device"].startswith("npu") and not value["rng"].get("npu"):
        raise ValueError("NPU checkpoint is missing its NPU RNG state")
    return value
