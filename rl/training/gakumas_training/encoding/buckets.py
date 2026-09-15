"""Read-only effect aggregation, never an alternative game-rule executor.

The Arena adapter must explicitly certify settlement equivalence. Source ledgers
remain here for delta maintenance; ordinary network buckets omit source IDs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from typing import Any


@dataclass(frozen=True)
class BuffContribution:
    contribution_id: str
    trigger: Any
    operation: str
    target: Any
    value: float
    predicate: Any = None
    lifetime: Any = field(default_factory=lambda: {"scope": "produce", "expiry": "permanent"})
    settlement: Any = field(default_factory=dict)
    probability: float | None = 1.0
    remaining_uses: int | None = None
    counter_group: str | None = None
    cooldown_remaining: int = 0
    source_sensitive: bool = False
    emits_per_contribution: bool = False
    equivalent_settlement: bool = False

    def __post_init__(self):
        if self.operation not in {"add", "multiply", "max"}:
            raise ValueError(f"No aggregation operator for {self.operation!r}")
        if not math.isfinite(self.value):
            raise ValueError("Non-finite buff contribution")
        if self.probability is not None and not 0 <= self.probability <= 1:
            raise ValueError("Probability must be an explicit fraction or None")
        if self.remaining_uses is not None and self.remaining_uses < 0:
            raise ValueError("Remaining uses cannot be negative")

    @property
    def mergeable(self):
        return (self.equivalent_settlement and self.probability == 1.0
                and self.remaining_uses is None and self.counter_group is None
                and self.cooldown_remaining == 0 and not self.source_sensitive
                and not self.emits_per_contribution)


class BuffLedger:
    """Idempotent source replacement supports upgrade, removal and expiry.

    Expiry itself is reported by Arena. This class deliberately does not tick
    turns or decide whether a trigger fires. Only touched buckets are rebuilt.
    """
    def __init__(self):
        self._sources: dict[str, BuffContribution] = {}
        self._keys: dict[str, str] = {}
        self._groups: dict[str, dict[str, BuffContribution]] = {}
        self._cache: dict[str, dict] = {}

    @staticmethod
    def _key(c):
        fields = asdict(c)
        fields.pop("value")
        if c.mergeable:
            fields.pop("contribution_id")
        return json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def upsert(self, contribution: BuffContribution):
        c = contribution
        if self._sources.get(c.contribution_id) == c:
            return
        self.remove(c.contribution_id)
        key = self._key(c)
        self._sources[c.contribution_id] = c
        self._keys[c.contribution_id] = key
        self._groups.setdefault(key, {})[c.contribution_id] = c
        self._cache.pop(key, None)

    def remove(self, contribution_id: str):
        key = self._keys.pop(contribution_id, None)
        self._sources.pop(contribution_id, None)
        if key is not None:
            self._groups[key].pop(contribution_id)
            if not self._groups[key]:
                del self._groups[key]
            self._cache.pop(key, None)

    def synchronize(self, contributions):
        rows = list(contributions)
        ids = [c.contribution_id for c in rows]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate buff contribution identity")
        for old in set(self._sources) - set(ids):
            self.remove(old)
        for c in rows:
            self.upsert(c)

    def project(self):
        result = []
        for key in sorted(self._groups):
            group = self._groups[key]
            if key not in self._cache:
                rows = list(group.values())
                c = rows[0]
                values = [r.value for r in rows]
                value = {"add": math.fsum, "multiply": math.prod, "max": max}[c.operation](values)
                data = asdict(c)
                data.pop("contribution_id")
                data["value"] = value
                data["aggregated"] = c.mergeable
                # An exhausted or source-sensitive rule is still public state.
                # No count/expectation shortcut may remove its independent budget.
                if not c.mergeable:
                    data["source_ref"] = c.contribution_id
                self._cache[key] = data
            result.append(dict(self._cache[key]))
        return result
