"""Typed structural input. No private snapshots, hash features or silent truncation.

Each leaf keeps its complete ordered tree path. Strings use UTF-8 bytes so a
new mechanism name does not collapse to UNK. References become graph edges;
arbitrary instance IDs and unordered deck positions are not numeric features.
"""
from __future__ import annotations

import copy
import json
import math
import itertools
from dataclasses import dataclass

ENCODING = "arena-typed-tree-entities/1"
MAX_DEPTH = 20
MAX_TEXT_BYTES = 1024
MAX_ENTITIES = 512
MAX_ATOMS = 40000
PRIVATE_KEYS = {"seed", "rng", "deckCards", "journal", "history", "logs", "private_debug"}


@dataclass
class Encoded:
    # atom: (entity, ordered path strings, type, value string, number)
    atoms: list
    edges: list
    entity_count: int
    action_entities: list
    submissions: list


def flatten(value, path=()):
    if len(path) > MAX_DEPTH:
        raise ValueError(f"structural depth exceeds {MAX_DEPTH}: {path}")
    if isinstance(value, dict):
        yield path, 0, "", float(len(value))
        for key in sorted(value):
            yield from flatten(value[key], path + ("key:" + key,))
    elif isinstance(value, list):
        yield path, 1, "", float(len(value))
        for i, item in enumerate(value):
            yield from flatten(item, path + (f"index:{i}",))
    elif value is None:
        yield path, 2, "", 0.0
    elif isinstance(value, bool):
        yield path, 3, "", float(value)
    elif isinstance(value, (int, float)):
        if not math.isfinite(value) or abs(value) > 1e25:
            raise ValueError(f"non-finite/out-of-range numeric input at {path}")
        yield path, 4, "", float(value)
    elif isinstance(value, str):
        yield path, 5, "value:" + value, 0.0
    else:
        raise TypeError(f"unsupported public value {type(value)} at {path}")


def candidates(obs):
    if obs["result"]["terminated"] or obs["result"]["truncated"]:
        return []
    choice = obs.get("choice")
    if choice is not None:
        indices = [c['index'] for c in choice['candidates']]
        low, high = choice['min'], choice['max']
        if not 0 <= low <= high <= len(indices):
            raise ValueError('invalid choice cardinality')
        ordered = choice.get('ordered', False)
        size = sum((math.perm if ordered else math.comb)(len(indices), k) for k in range(low, high + 1))
        if size > 384:
            raise ValueError(f'{size} atomic choices exceed this model capacity; use an autoregressive choice policy')
        factory = itertools.permutations if ordered else itertools.combinations
        return [{'method': 'choose', 'indices': list(group), 'decision_version': obs['decision_version']}
                for k in range(low, high + 1) for group in factory(indices, k)]
    return [{"method": "act", "action": copy.deepcopy(a)} for a in obs["actions"]]


def encode(obs):
    if obs.get("schema_version") != "arena-public-exam/1" or obs.get("observation_scope") != "public":
        raise ValueError("only arena-public-exam/1 public observations are admitted")
    # Version metadata remains outside all neural input.
    def forbid(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in PRIVATE_KEYS:
                    raise ValueError(f"private input rejected: {k}")
                forbid(v)
        elif isinstance(x, list):
            for v in x:
                forbid(v)
    forbid(obs)
    allowed = {"schema_version", "observation_scope", "preset", "decision_version", "context", "knowledge",
               "state", "cards", "definitions", "zones", "drinks", "choice", "actions", "result", "version"}
    if set(obs) - allowed:
        raise ValueError(f"unmapped public observation fields: {sorted(set(obs) - allowed)}")
    submissions = candidates(obs)
    if not submissions:
        raise ValueError("encode is for live decision states with legal candidates")
    card_rows = obs["cards"]
    ids = {c["instance_id"]: i + 1 for i, c in enumerate(card_rows)}
    if len(ids) != len(card_rows):
        raise ValueError("duplicate card instance IDs")
    nodes = [{}] + [{} for _ in card_rows]
    edges = []

    def ref(owner, target, label):
        edges.append((owner, target, "out:" + label))
        edges.append((target, owner, "in:" + label))

    def clean(x, owner, path=()):
        if isinstance(x, dict):
            out = {}
            for key, value in x.items():
                if key == "idx" and x.get("type") in {"card", "skillCard", "skillCardEffect"}:
                    if not isinstance(value, int) or not 0 <= value < len(card_rows):
                        raise ValueError("bad source card reference")
                    ref(owner, value + 1, "/".join(path + (key,)))
                    out[key] = "card_reference"
                elif key in {"usedCard", "lastUsedCard", "movedCard"} and isinstance(value, int) and value >= 0:
                    if value >= len(card_rows):
                        raise ValueError("bad public card index")
                    ref(owner, value + 1, "/".join(path + (key,)))
                    out[key] = "card_reference"
                else:
                    out[key] = clean(value, owner, path + (key,))
            return out
        if isinstance(x, list):
            return [clean(v, owner, path + (str(i),)) for i, v in enumerate(x)]
        if isinstance(x, str) and x in ids:
            ref(owner, ids[x], "/".join(path))
            return "card_reference"
        return x

    # Only top-level keys are popped below, and `clean` is pure: it reads its input
    # and returns freshly-built dicts/lists, never mutating them. A shallow copy is
    # therefore enough to keep obs["state"] intact, and avoids deep-copying the whole
    # observation on every decision of every episode.
    state = dict(obs["state"])
    effects = state.pop("effects", [])
    counters = state.pop("effectCounters", {})
    current_effect = state.pop("currentEffectInstanceId", None)
    # Next effect ID is an allocator, not a gameplay magnitude.
    state.pop("effectInstanceId", None)
    definitions = obs['definitions']
    if set(definitions) - {'cards', 'p_items', 'drinks', 'configured_abilities'}:
        raise ValueError('unmapped definition category')
    abilities = definitions.get('configured_abilities', {})
    if set(abilities) - {'bindings', 'memory_abilities', 'persistent_effects'}:
        raise ValueError('unmapped configured ability category')
    bindings = {r['instance_id']: r['bindings'] for r in abilities.get('bindings', [])}
    choice_context = None
    if obs.get("choice") is not None:
        choice_context = {k: v for k, v in obs["choice"].items() if k not in {"candidates", "decision_version"}}
    nodes[0] = clean({"entity_type": "global", "context": obs["context"],
                      "knowledge": obs["knowledge"], "state": state,
                      "choice_context": choice_context,
                      "configured_abilities": {k: v for k, v in abilities.items() if k != 'bindings'}}, 0)
    zones = obs["zones"]
    memberships = {uid: {} for uid in ids}
    for zone in ("hand", "held", "discarded", "removed"):
        for i, uid in enumerate(zones[zone]):
            memberships[uid][zone] = i if zone in {"hand", "held"} else True
    for uid in zones["deck"]["members"]:
        memberships[uid]["deck"] = True
    for i, uid in enumerate(zones["deck"].get("known_top", [])):
        memberships[uid]["known_top_position"] = i
    for order in zones["deck"].get("known_relative_orders", []):
        for first, second in zip(order, order[1:]):
            ref(ids[first], ids[second], "known_precedes")
    card_defs = {c["id"]: c for c in obs["definitions"]["cards"]}
    for c in card_rows:
        index = ids[c["instance_id"]]
        payload = {k: v for k, v in c.items() if k != "instance_id"}
        # Effective AST replaces the corresponding original lines. Keep all other
        # definition metadata, including active/mental, limits and initial-hand rules.
        definition = {k: v for k, v in card_defs[c["definition_id"]].items() if k not in c["effective"]}
        nodes[index] = clean({"entity_type": "card", "zone": memberships[c["instance_id"]],
                              "bindings": bindings.get(c['instance_id'], []),
                              "definition_metadata": definition, **payload}, index)
    relation_groups, scope_names = {}, {}
    for order, effect in enumerate(effects):
        effect = dict(effect)   # top-level pop only; `clean` below does not mutate.
        eid = effect.pop("effectInstanceId", None)
        count = counters.get(str(eid)) if isinstance(counters, dict) else (counters[eid] if isinstance(eid, int) and 0 <= eid < len(counters) else None)
        index = len(nodes)
        if eid is not None:
            # Opaque joins for the optional RL relation view, never scalar input.
            scope_names.setdefault(str(eid), 'scope:' + str(len(scope_names)))
            relation_groups[str(index)] = scope_names[str(eid)]
        nodes.append(clean({"entity_type": "effect", "resolution_order": order,
                            "counter": count, "is_current": eid is not None and eid == current_effect,
                            "effect": effect}, index))
    for order, item in enumerate(obs["definitions"]["p_items"]):
        index = len(nodes)
        nodes.append(clean({"entity_type": "p_item", "resolution_order": order, "definition": item}, index))
    drink_defs = {d["id"]: d for d in obs["definitions"]["drinks"]}
    drink_nodes = []
    for did in obs["drinks"]:
        index = len(nodes)
        drink_nodes.append(index)
        nodes.append(clean({"entity_type": "drink", "definition": drink_defs[did]}, index))
    action_entities = []
    for pos, submission in enumerate(submissions):
        index = len(nodes)
        action_entities.append(index)
        if submission["method"] == "choose":
            options = {c['index']: c for c in obs['choice']['candidates']}
            ordered = obs['choice'].get('ordered', False)
            payload = {'type': 'choose', 'count': len(submission['indices']), 'ordered': ordered}
            for order, candidate_index in enumerate(submission['indices']):
                target = ids[options[candidate_index]['instance_id']]
                ref(index, target, f'choice_target:{order}' if ordered else 'choice_target')
        else:
            payload = {k: v for k, v in submission["action"].items() if k != "decision_version"}
            if payload["type"] == "drink":
                slot = payload.pop("slot")
                ref(index, drink_nodes[slot], "drink_target")
        nodes.append(clean({"entity_type": "candidate", "action": payload}, index))
    if len(nodes) > MAX_ENTITIES:
        raise ValueError(f"{len(nodes)} entities exceed pilot capacity {MAX_ENTITIES}")
    atoms = [(i, path, kind, text, num) for i, node in enumerate(nodes)
             for path, kind, text, num in flatten(node)]
    if len(atoms) > MAX_ATOMS:
        raise ValueError(f"{len(atoms)} atoms exceed pilot capacity {MAX_ATOMS}")
    encoded = Encoded(atoms, edges, len(nodes), action_entities, submissions)
    encoded.relation_context = {'effect_groups': relation_groups}
    return encoded


def collate(examples, device="cpu"):
    import torch
    lexemes = [""]
    lookup = {"": 0}
    def word(text):
        if text not in lookup:
            if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
                raise ValueError("lexical token exceeds explicit byte capacity")
            lookup[text] = len(lexemes)
            lexemes.append(text)
        return lookup[text]
    paths, kinds, values, numbers, entities = [], [], [], [], []
    edge_src, edge_dst, edge_word, batches, actions = [], [], [], [], []
    offset = 0
    for batch, e in enumerate(examples):
        batches.extend([batch] * e.entity_count)
        actions.append([offset + i for i in e.action_entities])
        for ent, path, kind, text, number in e.atoms:
            paths.append([word(p) for p in path] + [0] * (MAX_DEPTH - len(path)))
            kinds.append(kind); values.append(word(text)); entities.append(ent + offset)
            numbers.append([math.copysign(math.log1p(abs(number)), number),
                            number / (1 + abs(number)), number / 10000, float(number != 0)])
        for src, dst, text in e.edges:
            edge_src.append(src + offset); edge_dst.append(dst + offset); edge_word.append(word(text))
        offset += e.entity_count
    byte_rows = [[b + 1 for b in text.encode("utf-8")] or [0] for text in lexemes]
    lengths = torch.tensor([len(row) for row in byte_rows], dtype=torch.long)
    byte_tensor = torch.zeros((len(byte_rows), int(lengths.max())), dtype=torch.long)
    for i, row in enumerate(byte_rows):
        byte_tensor[i, :len(row)] = torch.tensor(row)
    tensor = lambda x, dtype=torch.long: torch.tensor(x, dtype=dtype, device=device)
    max_actions = max(map(len, actions))
    action_index = torch.zeros((len(examples), max_actions), dtype=torch.long, device=device)
    mask = torch.zeros_like(action_index, dtype=torch.bool)
    for i, row in enumerate(actions):
        action_index[i, :len(row)] = tensor(row); mask[i, :len(row)] = True
    return {"bytes": byte_tensor.to(device), "lengths": lengths,
            "paths": tensor(paths), "kinds": tensor(kinds), "values": tensor(values),
            "numbers": tensor(numbers, torch.float32), "entities": tensor(entities),
            "edge_src": tensor(edge_src), "edge_dst": tensor(edge_dst), "edge_word": tensor(edge_word),
            "batches": tensor(batches), "action_index": action_index, "mask": mask,
            "entity_count": offset, "batch_size": len(examples)}
