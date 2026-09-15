"""Validated content packs -> isolated native master tables + explicit flow graphs."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from gakumas_rl.repository.master_data import MasterDataRepository, TableIndex
from gakumas_rl.simulation.exam.effects.registry import EXAM_EFFECT_REGISTRY
from gakumas_rl.simulation.exam.ids import ExamEffect, FieldStatus, GrowEffect

from .models import ContentPack
from .operations import PRODUCE_GAINS, Mechanisms, builtins

TABLES = {
    "cards": "ProduceCard",
    "effects": "ProduceExamEffect",
    "triggers": "ProduceExamTrigger",
    "passives": "ProduceExamStatusEnchant",
    "searches": "ProduceCardSearch",
    "drinks": "ProduceDrink",
    "items": "ProduceItem",
    "growth": "ProduceCardGrowEffect",
}
CATEGORIES = {"active": "ActiveSkill", "mental": "MentalSkill", "trouble": "Trouble"}
PHASES = {
    "condition": "None",
    "exam_start": "ExamStartExam",
    "exam_start_after": "StartExamPlay",
    "turn_start": "ExamStartTurn",
    "turn_start_after": "StartPlay",
    "turn_end": "ExamEndTurn",
    "card_used": "ExamCardPlay",
    "after_card": "ExamCardPlayAfter",
    "status_change": "ExamStatusChange",
    "stamina_cost": "ExamStaminaReduceCard",
    "stamina_loss": "ExamStaminaReduce",
    "buff_cost": "ExamBuffConsume",
    "every_turn": "ExamTurnInterval",
    "every_card": "ExamPlayCountInterval",
}
INITIAL_FIELDS = {
    "stamina",
    "max_stamina",
    "vocal",
    "dance",
    "visual",
    "produce_points",
    "vocal_growth",
    "dance_growth",
    "visual_growth",
}
CONTENT_RULES_VERSION = "arena-content-rules/4"


@dataclass(frozen=True)
class ContentIssue:
    path: str
    message: str
    category: str = "contract"


class ContentError(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__("\n".join(f"{i.category}: {i.path}: {i.message}" for i in self.issues))


class ContentRepository(MasterDataRepository):
    """Own caches; base tables and the process-wide repository are never mutated."""

    def __init__(self, base: MasterDataRepository, rows: dict[str, list[dict]], *, digest: str):
        super().__init__(base.root_dir, base.assets_dir, base.localization_dir)
        self._base = base
        self._content_rows = copy.deepcopy(rows)
        self.content_digest = digest
        self.content_audition_rows: dict[str, dict] = {}
        self.content_handlers: dict = {}

    def load_table(self, table_name: str) -> TableIndex:
        if table_name not in self._table_cache:
            rows = copy.deepcopy(self._base.load_table(table_name).rows)
            rows.extend(copy.deepcopy(self._content_rows.get(table_name, [])))
            groups = defaultdict(list)
            for row in rows:
                if row.get("id") is not None:
                    groups[str(row["id"])].append(row)
            self._table_cache[table_name] = TableIndex(table_name, rows, dict(groups))
        return self._table_cache[table_name]

    def audition_rows(self, scenario, stage_type=None, **kwargs):
        if stage_type in self.content_audition_rows:
            return [self.content_audition_rows[stage_type]]
        return super().audition_rows(scenario, stage_type, **kwargs)


@dataclass(frozen=True)
class CompiledContent:
    pack: ContentPack
    repository: ContentRepository
    mechanisms: Mechanisms
    digest: str

    @property
    def rules_version(self):
        return CONTENT_RULES_VERSION

    def create_exam(self, audition_id: str, *, seed: int = 0):
        from .exam import ContentExam

        return ContentExam(self, audition_id, seed=seed)

    def create_scenario(self, scenario_id: str, *, seed: int = 0):
        from .flow import ContentSession

        return ContentSession(self, scenario_id, seed=seed)


def read_pack(path: str | Path) -> ContentPack:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    value = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    return ContentPack.model_validate(value)


def compile_pack(
    pack: ContentPack | dict | str | Path,
    base: MasterDataRepository | None = None,
    mechanisms: Mechanisms | None = None,
) -> CompiledContent:
    if isinstance(pack, (str, Path)):
        pack = read_pack(pack)
    if not isinstance(pack, ContentPack):
        pack = ContentPack.model_validate(pack)
    if base is None:
        from gakumas_arena.env import get_repository

        base = get_repository()
    mechanisms = copy.deepcopy(mechanisms or builtins())
    issues: list[ContentIssue] = []
    sections = {
        name: {i.id: i for i in getattr(pack, name)}
        for name in (*TABLES, "events", "training", "auditions", "scenarios")
    }
    condition_fields = INITIAL_FIELDS | {key for s in pack.scenarios for key in s.resources}
    rows: dict[str, list[dict]] = defaultdict(list)
    native_roots = set()

    def problem(path, message, category="contract"):
        issues.append(ContentIssue(path, message, category))

    def ref(section, value, path):
        if value in sections[section]:
            return True
        table = TABLES.get(section)
        if table and base.load_table(table).first(value) is not None:
            if section in {"drinks", "items"}:
                from .native import inspect_native_exam

                for issue in inspect_native_exam(base, table, base.load_table(table).first(value)):
                    problem(path + "." + issue.path, issue.mechanism, "unsupported")
            if section in {"effects", "triggers", "passives"}:
                native_roots.add(
                    (
                        {"effects": "effect", "triggers": "trigger", "passives": "enchant"}[
                            section
                        ],
                        value,
                    )
                )
            return True
        problem(path, f"unknown {section} reference {value}")
        return False

    def flow_effects(effects, path):
        for j, effect in enumerate(effects):
            op = mechanisms.flow.get(effect.operation)
            ep = f"{path}.{j}"
            if op is None:
                problem(ep, f"unknown flow operation {effect.operation}", "unsupported")
                continue
            try:
                params = op.parameters.model_validate(effect.arguments)
                for key, section in op.references:
                    ref(section, getattr(params, key), ep + "." + key)
                if effect.operation == "card_reward":
                    for card in params.cards:
                        ref("cards", card, ep + ".cards")
                        card_variant(card, 0, ep + ".cards")
                if effect.operation == "grant_card":
                    card_variant(params.id, params.upgrade, ep)
            except ValidationError as exc:
                problem(ep, str(exc))

    def card_variant(card, upgrade, path):
        from .native import inspect_native_exam

        own = [c for c in pack.cards if c.id == card and c.upgrade == upgrade]
        external = [
            c for c in base.produce_cards.all(card) if int(c.get("upgradeCount", 0)) == upgrade
        ]
        if not own and not external:
            problem(path, f"card variant missing: {card} upgrade={upgrade}")
        for row in external:
            for issue in inspect_native_exam(base, "ProduceCard", row):
                problem(path + "." + issue.path, issue.mechanism, "unsupported")
            for effect in row.get("playEffects", []):
                for key, kind in (
                    ("produceExamEffectId", "effect"),
                    ("produceExamTriggerId", "trigger"),
                ):
                    if effect.get(key):
                        native_roots.add((kind, effect[key]))
            if row.get("playProduceExamTriggerId"):
                native_roots.add(("trigger", row["playProduceExamTriggerId"]))

    for section, table in TABLES.items():
        for item in getattr(pack, section):
            if base.load_table(table).first(item.id):
                problem(section + "." + item.id, "cannot overwrite base master data")

    for search in pack.searches:
        for card in search.card_ids:
            ref("cards", card, search.id)
        zone = {"deck_grave": "DeckGrave", "not_lost": "NotLost"}.get(
            search.zone, search.zone.title()
        )
        rows["ProduceCardSearch"].append(
            {
                "id": search.id,
                "cardPositionType": "ProduceCardPositionType_" + zone,
                "produceCardIds": list(search.card_ids),
                "isSelf": search.self_only,
                "cardCategories": []
                if search.card_kind == "any"
                else ["ProduceCardCategory_" + CATEGORIES[search.card_kind]],
                "orderType": "ProduceCardOrderType_Unknown",
            }
        )
    fields = {v for k, v in vars(FieldStatus).items() if k.isupper()}
    for trigger in pack.triggers:
        if trigger.phase not in PHASES:
            problem(trigger.id, f"unsupported phase {trigger.phase}", "unsupported")
            continue
        if trigger.field not in fields and trigger.field != "ProduceExamFieldStatusType_Unknown":
            problem(trigger.id, f"unsupported field {trigger.field}", "unsupported")
        if trigger.search:
            ref("searches", trigger.search, trigger.id + ".search")
        if (trigger.every is not None) != trigger.phase.startswith("every_"):
            problem(trigger.id, "every is required only for every_turn/every_card phases")
        phase = PHASES[trigger.phase]
        rows["ProduceExamTrigger"].append(
            {
                "id": trigger.id,
                "phaseTypes": ["ProduceExamPhaseType_" + phase] if phase else [],
                "phaseValues": [trigger.every or 0] if phase else [],
                "fieldStatusTypes": [] if trigger.field.endswith("_Unknown") else [trigger.field],
                "fieldStatusValues": [] if trigger.field.endswith("_Unknown") else [trigger.value],
                "fieldStatusCheckTypes": [],
                "fieldStatusProduceCardSearchIds": [],
                "produceCardSearchId": trigger.search,
                "lowerSearchCount": 1 if trigger.search else 0,
                "upperSearchCount": 0,
                "effectTypes": [],
            }
        )
    for passive in pack.passives:
        ref("triggers", passive.trigger, passive.id + ".trigger")
        for effect in passive.effects:
            ref("effects", effect, passive.id + ".effects")
        rows["ProduceExamStatusEnchant"].append(
            {
                "id": passive.id,
                "produceExamTriggerId": passive.trigger,
                "produceExamEffectIds": list(passive.effects),
            }
        )
    supported_growth = {
        GrowEffect.LESSON_ADD,
        GrowEffect.LESSON_REDUCE,
        GrowEffect.BLOCK_ADD,
        GrowEffect.COST_ADD,
        GrowEffect.COST_REDUCE,
        GrowEffect.REVIEW_ADD,
        GrowEffect.AGGRESSIVE_ADD,
        GrowEffect.LESSON_BUFF_ADD,
        GrowEffect.PARAMETER_BUFF_TURN_ADD,
        GrowEffect.PARAMETER_BUFF_MULTIPLE_PER_TURN_ADD,
        GrowEffect.FULL_POWER_POINT_ADD,
    }
    for growth in pack.growth:
        if growth.effect_type not in supported_growth:
            problem(
                growth.id, f"unsupported scalar growth type {growth.effect_type}", "unsupported"
            )
        rows["ProduceCardGrowEffect"].append(
            {"id": growth.id, "effectType": growth.effect_type, "value": growth.value}
        )
    for effect in pack.effects:
        op = mechanisms.exam.get(effect.operation)
        if op is None:
            problem(effect.id, f"unknown exam operation {effect.operation}", "unsupported")
            continue
        try:
            params = op.parameters.model_validate(effect.arguments)
            for key, section in op.references:
                ref(section, getattr(params, key), effect.id + ".arguments." + key)
            row = {"id": effect.id, **op.compile(params)}
            if effect.operation == "native_scalar":
                complex_types = {
                    ExamEffect.STATUS_ENCHANT,
                    ExamEffect.STATUS_ENCHANT_ENCORE,
                    ExamEffect.EFFECT_TIMER,
                    ExamEffect.ADD_GROW_EFFECT,
                    ExamEffect.CARD_CREATE_ID,
                    ExamEffect.CARD_CREATE_SEARCH,
                    ExamEffect.CARD_DUPLICATE,
                    ExamEffect.CARD_MOVE,
                    ExamEffect.CARD_UPGRADE,
                    ExamEffect.FORCE_PLAY_CARD_SEARCH,
                    ExamEffect.FORCE_PLAY_CARD_SEARCH_WITH_COST,
                }
                known = {v for k, v in vars(ExamEffect).items() if k.isupper()}
                if (
                    params.effect_type in complex_types
                    or params.effect_type not in known
                    or "Search" in params.effect_type
                    or "Gimmick" in params.effect_type
                ):
                    problem(
                        effect.id,
                        "use a typed operation for effects requiring references/targets",
                        "unsupported",
                    )
            if row.get(
                "effectType"
            ) not in mechanisms.handlers and not EXAM_EFFECT_REGISTRY.is_registered(
                row.get("effectType", "")
            ):
                problem(effect.id, "compiler returned an unsupported effectType", "unsupported")
            if effect.operation == "passive":
                passive = sections["passives"].get(params.id)
                if passive is None:
                    problem(
                        effect.id,
                        "installing base-master passives needs an explicit authored duration/count definition",
                    )
                else:
                    row.update(effectTurn=passive.turns or -1, effectCount=passive.uses or 0)
            rows["ProduceExamEffect"].append(row)
        except (ValidationError, ValueError) as exc:
            problem(effect.id, str(exc))
    for card in pack.cards:
        play_effects = []
        for use in card.effects:
            effect = use if isinstance(use, str) else use.effect
            trigger = "" if isinstance(use, str) else use.condition
            ref("effects", effect, card.id + ".effects")
            if trigger:
                ref("triggers", trigger, card.id + ".effects.condition")
            play_effects.append({"produceExamEffectId": effect, "produceExamTriggerId": trigger})
        if card.condition:
            ref("triggers", card.condition, card.id + ".condition")
        if card.on_move is not None:
            for effect in card.on_move.effects:
                ref("effects", effect, card.id + ".on_move.effects")
        cost_type = {
            "concentration": "ExamLessonBuff",
            "good_condition": "ExamParameterBuff",
            "excellent_condition": "ExamParameterBuffMultiplePerTurn",
            "good_impression": "ExamReview",
            "motivation": "ExamCardPlayAggressive",
            "full_power": "ExamFullPowerPoint",
        }.get(card.cost.resource, "Unknown")
        rows["ProduceCard"].append(
            {
                "id": card.id,
                "name": card.name or card.id,
                "upgradeCount": card.upgrade,
                "category": "ProduceCardCategory_" + CATEGORIES[card.kind],
                "rarity": "ProduceCardRarity_"
                + {"N": "N", "R": "R", "SR": "Sr", "SSR": "Ssr"}[card.rarity],
                "planType": "ProducePlanType_"
                + {"common": "Common", "sense": "Plan1", "logic": "Plan2", "anomaly": "Plan3"}[
                    card.plan
                ],
                "stamina": card.cost.amount if card.cost.resource == "stamina" else 0,
                "forceStamina": card.cost.amount if card.cost.resource == "penetrate" else 0,
                "costType": "ExamCostType_" + cost_type,
                "costValue": card.cost.amount if cost_type != "Unknown" else 0,
                "playProduceExamTriggerId": card.condition,
                "playEffects": play_effects,
                "playMovePositionType": "ProduceCardMovePositionType_"
                + {
                    "discard": "Grave",
                    "exhaust": "Lost",
                    "hold": "Hold",
                    "deck_bottom": "DeckLast",
                }[card.after_play],
                "isInitial": card.opening,
                "produceCardStatusEnchantId": "",
                **(
                    {
                        "moveEffectTriggerType": "ProduceCardMoveEffectTriggerType_"
                        + card.on_move.destination.title(),
                        "moveProduceExamEffectIds": list(card.on_move.effects),
                        "moveProduceExamTriggerIds": [],
                    }
                    if card.on_move is not None
                    else {}
                ),
            }
        )
    for drink in pack.drinks:
        ids = []
        for i, effect in enumerate(drink.effects):
            ref("effects", effect, drink.id)
            did = f"{drink.id}__effect_{i}"
            ids.append(did)
            rows["ProduceDrinkEffect"].append({"id": did, "produceExamEffectId": effect})
        rows["ProduceDrink"].append(
            {
                "id": drink.id,
                "name": drink.name or drink.id,
                "planType": "ProducePlanType_Common",
                "rarity": "ProduceDrinkRarity_R",
                "produceDrinkEffectIds": ids,
            }
        )
    for item in pack.items:
        ids = []
        for i, passive in enumerate(item.passives):
            if passive not in sections["passives"]:
                problem(item.id, "items require authored passives with explicit duration/count")
                continue
            p = sections["passives"][passive]
            ids.append(f"{item.id}__effect_{i}")
            rows["ProduceItemEffect"].append(
                {
                    "id": ids[-1],
                    "produceExamStatusEnchantId": passive,
                    "effectTurn": p.turns or -1,
                    "effectCount": p.uses or 0,
                }
            )
        rows["ProduceItem"].append(
            {"id": item.id, "name": item.name or item.id, "produceItemEffectIds": ids}
        )
    for audition in pack.auditions:
        for c in audition.deck:
            card_variant(c.card, c.upgrade, audition.id + ".deck")
        for section in ("drinks", "items", "passives"):
            for value in getattr(audition, section):
                if value not in sections[section]:
                    if section == "passives":
                        problem(audition.id, f"{section} requires an authored definition: {value}")
                    else:
                        ref(section, value, audition.id)
        for label in ("success_effects", "failure_effects"):
            flow_effects(getattr(audition, label), audition.id + "." + label)
        rows["ProduceExamBattleConfig"].append(
            {
                "id": audition.id,
                "turn": audition.turns,
                "vocal": audition.weights[0],
                "dance": audition.weights[1],
                "visual": audition.weights[2],
            }
        )
    for event in pack.events:
        for option in event.options:
            flow_effects(option.effects, event.id + "." + option.id)
            for condition in option.conditions:
                if condition.field not in condition_fields:
                    problem(
                        event.id, f"unsupported condition field {condition.field}", "unsupported"
                    )
    for training in pack.training:
        if training.audition:
            ref("auditions", training.audition, training.id)
        flow_effects(training.effects, training.id)
        flow_effects(training.failure_effects, training.id)
        for condition in training.conditions:
            if condition.field not in condition_fields:
                problem(
                    training.id, f"unsupported condition field {condition.field}", "unsupported"
                )
    for scenario in pack.scenarios:
        base.build_scenario(scenario.base)
        nodes = {n.id: n for n in scenario.nodes}
        if len(nodes) != len(scenario.nodes):
            problem(scenario.id, "duplicate node id")
        if scenario.start not in nodes:
            problem(scenario.id, "start node does not exist")
        for field, value in scenario.initial.items():
            if field not in INITIAL_FIELDS or value < 0:
                problem(scenario.id + ".initial", f"unsupported field or negative value: {field}")
        maximum = scenario.initial.get("max_stamina", 30)
        if maximum <= 0 or scenario.initial.get("stamina", 30) > maximum:
            problem(scenario.id + ".initial", "stamina must be within [0, positive max_stamina]")
        for field in scenario.resources:
            if not re.fullmatch(r"scenario\.[a-z][a-z0-9_]*", field):
                problem(
                    scenario.id + ".resources",
                    "custom resource names must match scenario.[a-z][a-z0-9_]*",
                )
        for c in scenario.deck:
            card_variant(c.card, c.upgrade, scenario.id + ".deck")
        for drink in scenario.drinks:
            ref("drinks", drink, scenario.id)
        edges = {}
        for node in scenario.nodes:
            nexts = [n for n in (node.next_node, node.failure_node) if n is not None]
            nexts += [branch.next_node for branch in node.branches]
            for branch in node.branches:
                for condition in branch.conditions:
                    if condition.field not in INITIAL_FIELDS | scenario.resources.keys():
                        problem(
                            scenario.id + "." + node.id,
                            f"undeclared condition resource {condition.field}",
                        )
            if node.content:
                section = {"event": "events", "training": "training", "audition": "auditions"}[
                    node.kind
                ]
                ref(section, node.content, scenario.id + "." + node.id)
                if node.kind == "event" and node.content in sections["events"]:
                    nexts += [
                        o.next_node for o in sections["events"][node.content].options if o.next_node
                    ]
            # Check every effect reachable from this scenario against its declared resource scope.
            scoped = list(node.effects)
            conditions = []
            if node.kind == "event" and node.content in sections["events"]:
                for option in sections["events"][node.content].options:
                    scoped.extend(option.effects)
                    conditions.extend(option.conditions)
            elif node.kind == "training" and node.content in sections["training"]:
                training = sections["training"][node.content]
                scoped.extend((*training.effects, *training.failure_effects))
                conditions.extend(training.conditions)
                if training.audition in sections["auditions"]:
                    audition = sections["auditions"][training.audition]
                    scoped.extend((*audition.success_effects, *audition.failure_effects))
            elif node.kind == "audition" and node.content in sections["auditions"]:
                audition = sections["auditions"][node.content]
                scoped.extend((*audition.success_effects, *audition.failure_effects))
            for effects in scenario.hooks.values():
                scoped.extend(effects)
            for effect in scoped:
                if (
                    effect.operation == "resource"
                    and effect.arguments.get("field") not in scenario.resources
                ):
                    problem(scenario.id + "." + node.id, "undeclared scenario resource in effect")
            for condition in conditions:
                if condition.field not in INITIAL_FIELDS | scenario.resources.keys():
                    problem(
                        scenario.id + "." + node.id, "undeclared scenario resource in condition"
                    )
            for dest in nexts:
                if dest not in nodes:
                    problem(scenario.id + "." + node.id, f"unknown next node {dest}")
            if node.kind != "end" and node.next_node is None:
                problem(scenario.id + "." + node.id, "non-end node requires next_node")
            edges[node.id] = nexts
            flow_effects(node.effects, scenario.id + "." + node.id)
        _check_cycles(edges, scenario.id, problem)
        for hook, effects in scenario.hooks.items():
            flow_effects(effects, scenario.id + ".hooks." + hook)
    # Reject recursive definition dependencies before any runtime can install them.
    effect_edges = {}
    for effect in pack.effects:
        if effect.operation == "delay":
            effect_edges[effect.id] = [effect.arguments.get("id")]
        elif effect.operation == "passive":
            passive = sections["passives"].get(effect.arguments.get("id"))
            effect_edges[effect.id] = list(passive.effects) if passive else []
    _check_cycles(effect_edges, "effects", problem)
    if issues:
        raise ContentError(issues)
    master_revision = subprocess.check_output(
        ["git", "-C", str(base.assets_dir), "rev-parse", "HEAD"], text=True
    ).strip()
    digest = hashlib.sha256(
        json.dumps(
            {
                "pack": pack.model_dump(mode="json"),
                "master_revision": master_revision,
                "rules": CONTENT_RULES_VERSION,
                "mechanisms": mechanisms.catalog(),
                "tables": rows,
            },
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    repository = ContentRepository(base, rows, digest=digest)
    repository.content_handlers = dict(mechanisms.handlers)
    from .capabilities import inspect_definition

    roots = (
        native_roots
        | {("effect", e.id) for e in pack.effects}
        | {("trigger", t.id) for t in pack.triggers}
        | {("enchant", p.id) for p in pack.passives}
    )
    for kind, key in sorted(roots):
        for issue in inspect_definition(repository, kind, key):
            problem(issue.path, issue.mechanism, "unsupported")
    if issues:
        raise ContentError(issues)
    for a in pack.auditions:
        repository.content_audition_rows[a.id] = {
            "id": a.id,
            "number": 1,
            "produceExamBattleConfigId": a.id,
            "baseScore": a.clear_score,
            "forceEndScore": a.perfect_score or 0,
            "rankThreshold": 0,
            "parameterBaseLine": 1,
        }
    return CompiledContent(pack.model_copy(deep=True), repository, mechanisms, digest)


def _check_cycles(edges, path, problem):
    active, done = set(), set()

    def visit(node):
        if node in active:
            problem(path, f"cyclic dependency at {node}")
            return
        if node in done:
            return
        active.add(node)
        for dest in edges.get(node, []):
            visit(dest)
        active.remove(node)
        done.add(node)

    for node in edges:
        visit(node)


def produce_gain_row(arguments):
    """Use the same ProduceEffect field units and effects as official event rewards."""
    return {
        "produceEffectType": "ProduceEffectType_" + PRODUCE_GAINS[arguments["field"]],
        "effectValueMin": arguments["amount"],
        "effectValueMax": arguments["amount"],
    }
