"""Scenario config loader. All scenario-specific numbers live in gakumas_arena/scenarios/*.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"


class WeekSpec(BaseModel):
    model_config = {"extra": "allow"}
    week: int
    kind: str = "free"  # free | exam | event | festival ...
    actions: list[str] = Field(default_factory=list)
    exam: str | None = None


class ScenarioConfig(BaseModel):
    model_config = {"extra": "allow"}
    id: str
    name: str = ""
    weeks: list[WeekSpec]
    lesson: dict[str, Any] = Field(default_factory=dict)
    exams: dict[str, Any] = Field(default_factory=dict)
    evaluate: dict[str, Any] = Field(default_factory=dict)
    plugin: str | None = None  # dotted module path for scenario-specific hooks


def load_scenario(name_or_path: str | Path) -> ScenarioConfig:
    p = Path(name_or_path)
    if not p.exists():
        p = SCENARIO_DIR / f"{name_or_path}.yaml"
    with p.open(encoding="utf-8") as f:
        return ScenarioConfig.model_validate(yaml.safe_load(f))
