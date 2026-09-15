"""Read-only, candidate-owned mechanisms before a produce runtime exists.

Arena resolves levels, memory customizations and scenario eligibility. This
module only binds those public definitions into trees for the existing encoder.
It never constructs ProduceRuntime, samples an event, or applies an effect.
"""
from __future__ import annotations

from copy import deepcopy
from collections import OrderedDict
from dataclasses import asdict, replace
from functools import lru_cache

from .mechanisms import MasterMechanisms, mechanical
from ..encoding.graph import SemanticCoverageError, _canonical, _compile_definition


SETUP_OBSERVATION_VERSION = "gakumas-public-setup/1"
_SCENARIOS = ("hif_selection", "hif_final")
_SUPPORT_FIELDS = frozenset({"id", "type", "planType", "rarity", "produceCardUpgradePermil",
    "upgradeProduceCardSearchId", "produceCardUpgradeLessonParameterType"})
_MEMORY_ABILITY_FIELDS = frozenset({"id", "level", "skillId", "evaluation", "rarity",
    "produceGroupIds", "isUniqueActivation"})
_COSMETIC = frozenset({"name", "description", "assetId", "voiceAssetId", "tag",
    "produceStoryIds", "produceStoryId", "produceStoryGroupId",
    "supportCardLevelId", "supportCardLevelLimitId", "characterIds",
    "displayPositionX", "displayPositionY", "displayScale", "exchangeReward", "isLimited",
    "gashaSupportAnimationNumber", "viewStartTime", "order"})


def _public(value):
    """Remove presentation only; preserve zero, missing, null and list order."""
    if isinstance(value, dict):
        return {k: _public(v) for k, v in mechanical(value).items()
                if k not in _COSMETIC and not k.endswith("Descriptions")}
    if isinstance(value, (list, tuple)):
        return [_public(v) for v in value]
    return value


class _SetupCompiler:
    def __init__(self, repository):
        self.repository = repository
        self.master = MasterMechanisms(repository)
        self.tree_cache, self.support_cache, self.memory_cache, self.base_cache = (OrderedDict() for _ in range(4))
        self.identities = {}

    @staticmethod
    def remember(cache, key, value, limit):
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > limit:
            cache.popitem(last=False)
        return value

    def identity(self, table, identifier):
        ref = f"setup-definition:{table}:{identifier}"
        self.identities[ref] = {"id": ref, "definition_kind": table}
        return ref

    def exact_row(self, table, identifier, level=None, level_field="level"):
        rows = self.repository.load_table(table).all(identifier)
        if level is not None:
            rows = [r for r in rows if r.get(level_field) == level]
        if len(rows) != 1:
            raise SemanticCoverageError(f"Missing/ambiguous setup definition {table}:{identifier}@{level}")
        return rows[0]

    def _validated(self, table, raw):
        data = _public(raw)
        if table == "MemoryAbility":
            unknown = set(data) - _MEMORY_ABILITY_FIELDS
            if unknown:
                raise SemanticCoverageError(f"Unsupported MemoryAbility fields: {sorted(unknown)}")
            return {"table": table, "data": data}
        return _compile_definition(_canonical({"table": table, "id": str(raw["id"]), "data": data}))

    def tree(self, table, raw, ancestors=()):
        """Compile strong references below their exact owner before GNN passes.

        Search-card identities denote matching sets, so they remain nominal
        relations instead of recursively expanding the effects of every target.
        A recursive program retains an explicit back reference, never disappears.
        """
        key = (table, _canonical(_public(raw)))
        identity = self.identity(table, raw["id"])
        if key in ancestors:
            return {"recursive_ref": identity, "definition_kind": table}
        if not ancestors and key in self.tree_cache:
            self.tree_cache.move_to_end(key)
            return self.tree_cache[key]
        validated = self._validated(table, raw)
        data = validated["data"]
        ancestors = (*ancestors, key)

        def bind(value, field="", container=None):
            if isinstance(value, dict):
                return {k: bind(v, k, value) for k, v in value.items()}
            if isinstance(value, list):
                return [bind(v, field, container) for v in value]
            if not isinstance(value, str) or not value:
                return value
            nominal_table = {"supportCardId": "SupportCard", "originIdolCardId": "IdolCard",
                             "idolCardId": "IdolCard"}.get(field)
            if nominal_table:
                return {"definition_ref": self.identity(nominal_table, value)}
            matches = self.master.index.get(value, ())
            if not matches:
                return value
            # All upgrade versions match a card search; effect bodies are not
            # part of the predicate. Applied customization IDs likewise refer
            # to provenance; their effective grow effects are already bound.
            nominal = (table == "ProduceCardSearch" and field == "produceCardIds"
                       or field == "customizedProduceCardCustomizeIds")
            if nominal:
                refs = dict.fromkeys(self.identity(child_table, child["id"]) for child_table, child in matches)
                return {"bindings": [{"definition_ref": ref} for ref in refs]}
            bound = []
            for child_table, child in matches:
                if child_table == "ProduceSkill":
                    # A skill's current level is bound explicitly by listeners.
                    continue
                if (child_table == "ProduceCard" and isinstance(container, dict)
                        and container.get("resourceType") == "ProduceResourceType_ProduceCard"
                        and "resourceLevel" in container
                        and child.get("upgradeCount") != container["resourceLevel"]):
                    continue
                bound.append(self.tree(child_table, child, ancestors))
            if not bound:
                return {"definition_ref": self.identity(matches[0][0], value)}
            return {"bindings": bound}

        result = {"definition_ref": identity, "definition_kind": table,
                  "parameters": bind({k: v for k, v in data.items() if k != "id"})}
        if "semantic" in validated:
            result["semantic"] = validated["semantic"]
        if not ancestors[:-1]:
            self.remember(self.tree_cache, key, result, 8192)
        return result

    def skill(self, skill):
        """Bind all three slots, not ProduceSkillEffect's first-trigger shortcut."""
        raw = self.exact_row("ProduceSkill", skill.skill_id, skill.level)
        listeners = []
        for slot in (1, 2, 3):
            effect = raw.get(f"produceEffectId{slot}")
            if not effect:
                continue
            trigger = raw.get(f"produceTriggerId{slot}")
            listeners.append({
                "slot": slot,
                "activation_rate_permille": raw.get(f"activationRatePermil{slot}"),
                "fire_limit": raw.get("activationCount"),
                "registration": "listener" if trigger else "immediate_on_registration",
                "trigger": self.tree("ProduceTrigger", self.exact_row("ProduceTrigger", trigger)) if trigger else None,
                "effect": self.tree("ProduceEffect", self.exact_row("ProduceEffect", effect)),
            })
        return {"definition_ref": self.identity("ProduceSkill", skill.skill_id),
                "level": skill.level, "source": skill.source,
                "eligibility": {k: raw[k] for k in ("planType", "produceType", "produceSplitType") if k in raw},
                "listeners": listeners}

    def support(self, record):
        from gakumas_rl.idol_config import _load_support_card_produce_skills, _resolve_support_card_level
        from gakumas_rl.loadout import SupportCardSelection
        sid, level = record["support_card_id"], record["level"]
        key = (sid, level)
        if key not in self.support_cache:
            raw = self.exact_row("SupportCard", sid)
            if type(level) is not int or _resolve_support_card_level(raw, level) != level:
                raise SemanticCoverageError(f"Invalid setup support level: {sid}@{level}")
            unknown = set(_public(raw)) - _SUPPORT_FIELDS
            if unknown:
                raise SemanticCoverageError(f"Unsupported SupportCard fields: {sorted(unknown)}")
            selected = SupportCardSelection(sid, level, raw["type"], 0.)
            skills = _load_support_card_produce_skills(self.repository, (selected,))
            links = sorted((r for r in self.repository.load_table("ProduceEventSupportCard").rows
                            if r["supportCardId"] == sid and r["supportCardLevel"] <= level),
                           key=lambda r: r["number"])
            self.remember(self.support_cache, key, {
                "entity_kind": "support_option", "level": level,
                "support": self.tree("SupportCard", raw),
                "current_skills": [self.skill(s) for s in skills],
                "event_sequence": [{"number": link["number"], "required_level": link["supportCardLevel"],
                    "event": self.tree("ProduceStepEventDetail", self.exact_row(
                        "ProduceStepEventDetail", link["produceStepEventDetailId"]))} for link in links],
            }, 1024)
        self.support_cache.move_to_end(key)
        return {"id": record["id"], "borrowed": bool(record.get("borrowed", False)), **self.support_cache[key]}

    def memory(self, record):
        from gakumas_arena.env import get_scenario
        from gakumas_arena.produce.loadout_handoff import _memory_from_wire
        from gakumas_rl.idol_config import _load_memory_skills, apply_card_customizations
        spec = _memory_from_wire(record["spec"])
        # Instance identity is outside the cached mechanism. Assembled memories
        # must not allocate an immortal cache entry per episode or combination.
        key = _canonical({k: v for k, v in asdict(spec).items() if k != "memory_id"})
        if key not in self.memory_cache:
            if len(spec.ability_levels) > len(spec.ability_ids):
                raise SemanticCoverageError("Memory ability_levels exceeds ability_ids")
            levels = tuple(spec.ability_levels) + (1,) * (len(spec.ability_ids) - len(spec.ability_levels))
            abilities = []
            for aid, level in zip(spec.ability_ids, levels):
                raw = self.exact_row("MemoryAbility", aid, level)
                ability = self._validated("MemoryAbility", raw)["data"]
                self.exact_row("ProduceSkill", ability["skillId"], level)
                single = replace(spec, ability_ids=(aid,), ability_levels=(level,))
                stages = {}
                for scenario in _SCENARIOS:
                    stages[scenario] = [self.skill(s) for s in _load_memory_skills(
                        self.repository, get_scenario(scenario), (single,))]
                programs = {}
                for scenario, skills in stages.items():
                    program_key = _canonical(skills)
                    entry = programs.setdefault(program_key, {"active_scenarios": [], "skills": skills})
                    entry["active_scenarios"].append(scenario)
                abilities.append({"definition_ref": self.identity("MemoryAbility", aid),
                    "level": level, "parameters": {k: v for k, v in ability.items() if k not in ("id", "skillId")},
                    "unique_activation_group_ref": self.identity("ProduceSkill", ability["skillId"])
                        if ability["isUniqueActivation"] else None,
                    "stage_skills": list(programs.values())})
            inherited = None
            if spec.produce_card is not None:
                card = spec.produce_card
                raw = self.repository.card_row_by_upgrade(card.card_id, card.upgrade_count, fallback_to_canonical=False)
                if raw is None:
                    raise SemanticCoverageError(f"Missing inherited card {card.card_id}@{card.upgrade_count}")
                effective = apply_card_customizations(self.repository, raw, tuple(card.customize_ids))
                inherited = {"acquisition_phase": card.phase_type, "upgrade_count": card.upgrade_count,
                    "customize_order": [self.identity("ProduceCardCustomize", cid) for cid in card.customize_ids],
                    "effective_card": self.tree("ProduceCard", effective)}
            self.remember(self.memory_cache, key, {"entity_kind": "memory_option", "grade": spec.grade,
                "allowed_character_ids": list(spec.allowed_character_ids),
                "origin_idol_ref": self.identity("IdolCard", spec.idol_card_id) if spec.idol_card_id else None,
                "contest_only_statistics": {k: getattr(spec, k) for k in ("vocal", "dance", "visual", "stamina")},
                "abilities": abilities, "inherited_card": inherited}, 512)
        self.memory_cache.move_to_end(key)
        return {"id": record["id"], "borrowed": bool(record.get("borrowed", False)),
                "assembly": {key: record[key] for key in ("assembly_phase", "assembly_complete", "slot",
                             "gold_factors_selected", "hif_ability_selected", "variant_count") if key in record},
                **self.memory_cache[key]}

    def base(self, base_loadout):
        from gakumas_arena.env import get_scenario
        from gakumas_arena.produce.initial_deck import build_hif_initial_deck
        from gakumas_arena.produce.loadout_handoff import thaw_loadout
        from gakumas_rl.interfaces.service import build_loadout_from_config
        from types import SimpleNamespace
        key = _canonical(base_loadout)
        if key not in self.base_cache:
            # Partial equipment must never be passed to the six-card resolver.
            config = {**deepcopy(base_loadout), "auto_support_cards": False,
                      "support_card_ids": [], "support_card_levels": [], "memories": []}
            result = {}
            for scenario in _SCENARIOS:
                resolved = build_loadout_from_config(get_scenario(scenario).produce_id, thaw_loadout(config))
                if resolved is None:
                    raise SemanticCoverageError("Setup requires a known fixed idol loadout")
                deck = build_hif_initial_deck(SimpleNamespace(repository=self.repository,
                    idol_loadout=resolved, scenario=get_scenario(scenario)))
                profile = asdict(resolved.stat_profile)
                for field in ("idol_card_id", "character_id", "initial_exam_deck_id", "audition_difficulty_id", "unique_produce_card_id"):
                    profile.pop(field, None)
                result[scenario] = {"stat_profile": profile,
                    "idol_skills": [self.skill(s) for s in resolved.produce_skills],
                    "initial_cards": [self.tree("ProduceCard", row) for row in deck],
                    "initial_items": [self.tree("ProduceItem", self.exact_row("ProduceItem", pid))
                        for pid in (resolved.produce_item_id, *resolved.extra_produce_item_ids) if pid]}
            self.remember(self.base_cache, key, result, 64)
        self.base_cache.move_to_end(key)
        return self.base_cache[key]


@lru_cache(maxsize=4)
def _compiler(repository):
    return _SetupCompiler(repository)


def prepare_setup_observation(repository, *, base_loadout, support_options, memory_options,
                              selected_supports, selected_memories, phase, slot, rules):
    """Return public setup state; callers alone determine legal candidates.

    Records have stable ``id`` references. Support records additionally carry
    ``support_card_id/level``; memory records carry the full resolved ``spec``.
    Selected equipment is ordered because Arena uses loadout listener order.
    """
    compiler = _compiler(repository)
    supports = {row["id"]: row for row in [*support_options, *selected_supports]}
    memories = {row["id"]: row for row in [*memory_options, *selected_memories]}
    support_entities = [compiler.support(row) for key, row in sorted(supports.items())]
    memory_entities = [compiler.memory(row) for key, row in sorted(memories.items())]
    base = compiler.base(base_loadout)
    # Include only identity records reachable in THIS observation. A prior run's
    # compiler-cache insertion order cannot change the state or checkpoint replay.
    payload = {"support_options": support_entities, "memory_options": memory_entities, "base_loadout": base}
    def references(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from references(child)
        elif isinstance(value, (tuple, list)):
            for child in value:
                yield from references(child)
    used_refs = set(references(payload))
    identities = [value for key, value in sorted(compiler.identities.items()) if key in used_refs]
    return deepcopy({
        "context": {"schema_version": SETUP_OBSERVATION_VERSION, "phase": phase, "slot": slot,
                    "selected_support_refs": [row["id"] for row in selected_supports],
                    "selected_memory_refs": [row["id"] for row in selected_memories]},
        "entities": {**payload, "definition_identities": identities},
        "rules": rules,
    })


__all__ = ["SETUP_OBSERVATION_VERSION", "prepare_setup_observation"]
