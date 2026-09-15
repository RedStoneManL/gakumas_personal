from __future__ import annotations

import hashlib
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
import torch

from .encoding import ENCODING
from .model import MODEL_SCHEMA, PolicyValue


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_replace(source, destination):
    """Windows dashboard/checkpoint readers may briefly deny delete-sharing."""
    for attempt in range(16):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == 15:
                raise
            time.sleep(min(.01 * 2 ** attempt, .2))


def json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f'.{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        atomic_replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def source_version():
    root = Path(__file__).parent
    files = {p.name: digest(p) for p in sorted(root.glob("*.py"))}
    files['configs/course.json'] = digest(root.parent / 'configs/course.json')
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def save(path, model, optimizer=None, **metadata):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    value = {"model_schema": MODEL_SCHEMA, "encoding": ENCODING,
             "model_config": model.config, "model_state": model.state_dict(),
             "optimizer_state": optimizer.state_dict() if optimizer else None,
             "torch_rng": torch.get_rng_state(), "python_rng": random.getstate(),
             "cuda_rng": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
             "created_at": datetime.now(timezone.utc).isoformat(),
             "rl_source_sha256": source_version(), **metadata}
    temp = path.with_suffix(path.suffix + ".tmp")
    torch.save(value, temp)
    atomic_replace(temp, path)
    return value


def load(path, device="cpu"):
    value = torch.load(path, map_location="cpu", weights_only=True)
    if value.get("model_schema") != MODEL_SCHEMA or value.get("encoding") != ENCODING:
        raise ValueError("checkpoint schema/encoding mismatch")
    # Loading an evaluation model must not advance the training RNG stream.
    with torch.random.fork_rng(devices=[]):
        model = PolicyValue(**value["model_config"])
        model.load_state_dict(value["model_state"], strict=True)
    return model.to(device), value
