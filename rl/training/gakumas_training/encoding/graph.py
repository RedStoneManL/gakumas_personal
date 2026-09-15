"""Typed mechanism trees and explicit reference relations; no string/ID hashes.

Native effects already expose executable ASTs. Their node kinds, argument roles,
operators, identifiers and calls are validated against a pinned semantic manifest.
Master effects gain the reviewed operation/family/target labels while retaining
every original parameter and ordered child. This compiler observes; Arena executes.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import OrderedDict
from functools import lru_cache
import json
import math
import weakref
from pathlib import Path
from typing import Any

from .buckets import BuffContribution, BuffLedger
from .projection import build_buff_projection

ENCODING_VERSION = "gakumas-typed-mechanism-graph/1"
_MANIFEST = json.loads(Path(__file__).with_name("semantic_manifest.json").read_text(encoding="utf-8"))
PRIVATE_KEYS = {"seed", "rng", "rng_state", "random_state", "deckCards", "private_debug", "snapshot"}
METADATA_KEYS = {"decision_version", "schema_version", "version", "preset", "exam_backend",
                 "effective_sha256", "source_sha256", "reference_key", "display_name", "description",
                 "image", "image_path", "fault", "sampling_scope", "event_template_id", "event_family_id",
                 "produceDescriptions", "examDescriptions", "customizeProduceDescriptions"}
IDENTITY_KEYS = {"instance_id", "definition_id", "source_identity", "source_ref", "entity_id", "id",
                 "card_id", "produce_card_id", "produce_item_id", "produce_skill_id", "item_id"}
AST_FIELDS = {"engine_ast", "effective", "conditions", "cost", "actions", "effects"}


class SemanticCoverageError(ValueError):
    pass


class Vocabulary:
    """Explicit append-only token manifest; checkpoint it alongside weights."""
    def __init__(self, tokens=None, capacity=65536):
        self.tokens = list(tokens or ["<pad>"])
        if not self.tokens or self.tokens[0] != "<pad>" or len(set(self.tokens)) != len(self.tokens):
            raise ValueError("Invalid vocabulary manifest")
        self.lookup = {t: i for i, t in enumerate(self.tokens)}
        self.capacity = capacity

    def intern(self, token):
        if token not in self.lookup:
            if len(self.tokens) >= self.capacity:
                raise SemanticCoverageError(f"Vocabulary capacity {self.capacity} exhausted; migrate explicitly")
            self.lookup[token] = len(self.tokens)
            self.tokens.append(token)
        return self.lookup[token]

    def state_dict(self):
        return {"tokens": list(self.tokens), "capacity": self.capacity}


@dataclass(frozen=True)
class EncodedDecision:
    # Per node, each feature binds a semantic field/value token to numeric data.
    # numeric tuple: present, raw/1000, signed-log, numeric-kind, null-kind.
    features: tuple[tuple[tuple[int, tuple[float, ...]], ...], ...]
    edges: tuple[tuple[int, int, int, float], ...]
    action_nodes: tuple[int, ...]
    tree_edges: tuple[tuple[int, int, int, float], ...] = ()
    depths: tuple[int, ...] = ()
    schema_version: str = ENCODING_VERSION

    @property
    def node_count(self):
        return len(self.features)


def _canonical(value):
    # Static Arena definitions are JSON-shaped. Dynamic integer-key dictionaries
    # bypass this cache and retain their distinct key type in the graph below.
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _validate_native(value, path="AST"):
    if isinstance(value, dict):
        kind = value.get("type")
        if kind is not None:
            schema = _MANIFEST["native_node_fields"].get(kind)
            if schema is None:
                raise SemanticCoverageError(f"Unsupported native node {kind!r} at {path}")
            unknown = set(value) - set(schema)
            if unknown:
                raise SemanticCoverageError(f"Unsupported {kind} fields {sorted(unknown)} at {path}")
            for key in ("op", "lhs", "name"):
                symbol = value.get(key)
                if isinstance(symbol, str) and symbol not in _MANIFEST["native_symbols"].get(key, []):
                    raise SemanticCoverageError(f"Unsupported native {key}={symbol!r} at {path}")
        for key, child in value.items():
            _validate_native(child, f"{path}.{key}")
    elif isinstance(value, list):
        for child in value:
            _validate_native(child, path + "[]")


def _exam_projection(data):
    """Bind runtime counters to effects and name fresh-field flags explicitly."""
    state = dict(data.get("state", {}))
    state.pop("effectInstanceId", None)  # allocator only
    counters = state.pop("effectCounters", {})
    current = state.pop("currentEffectInstanceId", None)
    effects = []
    counter_refs = {}
    for effect in state.get("effects", []):
        row = dict(effect)
        identity = row.pop("effectInstanceId", None)
        if identity is not None:
            reference = "runtime_effect:" + str(identity)
            counter_reference = "runtime_counter:" + str(identity)
            row["instance_id"] = reference
            row["counter_ref"] = counter_reference
            row["is_current"] = identity == current
            if isinstance(counters, dict):
                counter = counters.get(str(identity), counters.get(identity))
            else:
                counter = counters[identity] if isinstance(identity, int) and 0 <= identity < len(counters) else None
            counter_refs[counter_reference] = {"instance_id": counter_reference, "counter_state": counter}
        for key in ("actions", "conditions"):
            if key in row:
                _validate_native(row[key], "runtime_effect." + key)
        effects.append(row)
    if "effects" in state:
        state["effects"] = effects
    state["counter_bindings"] = list(counter_refs.values())
    fresh = state.get("freshBuffs")
    if isinstance(fresh, dict):
        fields = _MANIFEST.get("native_state_fields", [])
        named = {}
        for key, value in fresh.items():
            try:
                index = int(key)
            except (ValueError, TypeError):
                raise SemanticCoverageError(f"Unknown fresh buff field reference {key!r}")
            if not 0 <= index < len(fields):
                raise SemanticCoverageError(f"Unknown fresh buff field index {index}")
            named[fields[index]] = value
        state["freshBuffs"] = named
    return {**data, "state": state}


@lru_cache(maxsize=8192)
def _compile_definition(canonical):
    """Static validation/normalization cache contains no learned tensors."""
    row = json.loads(canonical)
    if "table" in row and "data" in row:
        table, data = row["table"], row["data"]
        if not isinstance(data, dict):
            raise SemanticCoverageError(f"Non-object master row in {table}")
        if table in {"ProduceEffect", "ProduceExamEffect"}:
            namespace, type_key = (("produce", "produceEffectType") if table == "ProduceEffect"
                                   else ("exam", "effectType"))
            kind = data.get(type_key)
            semantic = _MANIFEST[namespace].get(kind)
            if semantic is None:
                raise SemanticCoverageError(f"Unsupported {table} type {kind!r}")
            allowed = set(semantic["fields"]) | {"id"}
            unknown = set(data) - allowed - METADATA_KEYS
            if unknown:
                raise SemanticCoverageError(f"Unknown {kind} fields: {sorted(unknown)}")
            row["semantic"] = {k: v for k, v in semantic.items() if k != "fields"}
        elif not table.startswith(("Produce", "Support", "Idol", "Character", "Research")):
            raise SemanticCoverageError(f"Unregistered master table {table!r}")
    # AST data is validated separately from arbitrary public state dictionaries.
    def find_ast(x):
        if isinstance(x, dict):
            if x.get("type") in _MANIFEST["native_node_fields"]:
                _validate_native(x)
                return
            for key, value in x.items():
                if key in AST_FIELDS:
                    _validate_native(value)
                else:
                    find_ast(value)
        elif isinstance(x, list):
            for value in x:
                find_ast(value)
    find_ast(row)
    return row


class DecisionEncoder:
    def __init__(self, vocabulary=None, max_nodes=32768):
        self.vocabulary = vocabulary or Vocabulary()
        self.max_nodes = max_nodes
        self._ledger = BuffLedger()
        self.last_report = {}

    def state_dict(self):
        return {"schema_version": ENCODING_VERSION, "semantic_version": _MANIFEST["version"],
                "vocabulary": self.vocabulary.state_dict(), "max_nodes": self.max_nodes}

    def load_state_dict(self, state):
        if state.get("schema_version") != ENCODING_VERSION or state.get("semantic_version") != _MANIFEST["version"]:
            raise SemanticCoverageError("Encoder checkpoint semantic/schema mismatch")
        self.vocabulary = Vocabulary(**state["vocabulary"])
        self.max_nodes = state["max_nodes"]

    def encode(self, decision):
        if not decision.candidates:
            raise ValueError("A decision requires at least one legal candidate")
        nodes, edges, tree_edges, depths, identities, pending_refs = [], [], [], [], {}, []
        identity_values, pending_card_indices = set(), []
        def collect_identities(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if isinstance(key, str) and (key in IDENTITY_KEYS or key.endswith(("Id", "_id", "_ref"))):
                        if isinstance(child, str) and child:
                            identity_values.add(child)
                    collect_identities(child)
            elif isinstance(value, (list, tuple)):
                for child in value:
                    collect_identities(child)
        collect_identities(decision.observation)
        collect_identities(decision.candidates)
        vocab = self.vocabulary

        def node(depth=0):
            if len(nodes) >= self.max_nodes:
                raise SemanticCoverageError(f"State exceeds {self.max_nodes} graph nodes; no truncation")
            nodes.append([])
            depths.append(depth)
            return len(nodes) - 1

        def feature(owner, key, value):
            if isinstance(value, bool):
                token, numeric = f"{key}:bool", (1., float(value), float(value), 1., 0.)
            elif isinstance(value, (int, float)):
                if not math.isfinite(value) or abs(value) > 1e25:
                    raise SemanticCoverageError(f"Invalid numeric value at {key}")
                token = f"{key}:number"
                numeric = (1., value / 1000., math.copysign(math.log1p(abs(value)), value), 1., 0.)
            elif value is None:
                token, numeric = f"{key}:null", (1., 0., 0., 0., 1.)
            elif isinstance(value, str):
                token = f"{key}:reference" if value in identity_values else f"{key}:symbol:{value}"
                numeric = (1., 0., 0., 0., 0.)
            else:
                raise TypeError(f"Unsupported semantic scalar at {key}: {type(value)}")
            nodes[owner].append((vocab.intern(token), numeric))

        def link(src, dst, role, position=-1):
            edges.append((src, dst, vocab.intern("relation:" + role), float(position)))
            edges.append((dst, src, vocab.intern("inverse:" + role), float(position)))

        def add(value, role, parent=None, position=-1, static=False, identity_namespace=""):
            if static:
                value = _compile_definition(_canonical(value))
            owner = node(0 if parent is None else depths[parent] + 1)
            feature(owner, "node_role", role)
            if parent is not None:
                link(parent, owner, role, position)
                tree_edges.append((owner, parent, vocab.intern("relation:" + role), float(position)))
            if isinstance(value, dict):
                feature(owner, "structure", "record")
                for original_key, child in sorted(value.items(), key=lambda item: (type(item[0]).__name__, str(item[0]))):
                    if not isinstance(original_key, (str, int)):
                        raise SemanticCoverageError(f"Unsupported dictionary key type {type(original_key)}")
                    key = original_key if isinstance(original_key, str) else "integer_key:" + str(original_key)
                    if key in PRIVATE_KEYS:
                        raise SemanticCoverageError(f"Private policy input rejected: {role}.{key}")
                    if key in METADATA_KEYS or key == "name" and value.get("type") not in {"identifier", "call"}:
                        continue
                    if identity_namespace.startswith("exam") and key == "effectInstanceId":
                        # Runtime allocator IDs are not game magnitudes.
                        feature(owner, key, "effect_reference")
                        continue
                    if identity_namespace.startswith("exam") and isinstance(child, int) and (
                            key in {"usedCard", "lastUsedCard", "movedCard"} or
                            key == "idx" and value.get("type") in {"card", "skillCard", "skillCardEffect"}):
                        if child >= 0:
                            pending_card_indices.append((owner, child, key))
                            feature(owner, key, "card_reference")
                        else:
                            feature(owner, key, "no_card_reference")
                        continue
                    if key in IDENTITY_KEYS and isinstance(child, (str, int)):
                        # Identity is a reference relation, never a numeric magnitude.
                        ref = (identity_namespace, str(child))
                        is_definition = (key in {"instance_id", "id", "entity_id"} and role != "candidate"
                                         and not (key == "id" and "instance_id" in value))
                        if is_definition:
                            identities.setdefault(ref, owner)
                            if child != "":
                                pending_refs.append((owner, ref, key))
                        else:
                            if key == "definition_id" and identity_namespace == "exam":
                                ref = ("exam:cards", str(child))
                            pending_refs.append((owner, ref, key))
                        feature(owner, key, "reference")
                    elif isinstance(child, (dict, list, tuple)):
                        add(child, key, owner, static=False, identity_namespace=identity_namespace)
                    else:
                        feature(owner, key, child)
                        if isinstance(child, str) and child and (key.endswith(("Id", "_id", "_ref")) or key == "instance_id"):
                            pending_refs.append((owner, (identity_namespace, child), key))
            elif isinstance(value, (list, tuple)):
                feature(owner, "structure", "sequence")
                feature(owner, "length", len(value))
                for index, child in enumerate(value):
                    add(child, "element", owner, index, identity_namespace=identity_namespace)
            else:
                feature(owner, "value", value)
                if isinstance(value, str) and value in identity_values:
                    pending_refs.append((owner, (identity_namespace, value), "reference"))
            return owner

        root = add({"task": decision.task, "decision_kind": decision.kind}, "global")
        observation = decision.observation
        if not isinstance(observation, dict):
            raise TypeError("Decision observation must be a public dictionary")
        # Full Arena public observations are accepted directly for independent exam use.
        if observation.get("schema_version") == "arena-public-exam/1":
            observation = {"exam": observation}
        observation, projection_report = build_buff_projection(observation, decision.candidates)
        allowed = {"produce", "exam", "resolution", "mechanisms", "buff_contributions", "context", "resources", "entities", "rules", "relations"}
        if set(observation) - allowed:
            raise SemanticCoverageError(f"Unmapped observation roots: {sorted(set(observation) - allowed)}")
        exam_card_nodes, exam_drink_nodes = [], []
        for scope, data in observation.items():
            if scope == "buff_contributions":
                self._ledger.synchronize(BuffContribution(**row) for row in data)
                add(self._ledger.project(), "buff_buckets", root)
            elif scope == "mechanisms":
                # Definition identity matches master references across produce entities.
                for row in data or []:
                    definition_node = add(row, "mechanism", root, static=True, identity_namespace="produce")
                    # Canonical master definitions take priority over the same
                    # definition ID repeated as metadata on a physical deck copy.
                    if row.get("id") is not None:
                        identities[("produce", str(row["id"]))] = definition_node
            elif scope == "exam" and data is not None:
                if data.get("observation_scope") != "public" or data.get("schema_version") != "arena-public-exam/1":
                    raise SemanticCoverageError("Only Arena public exam observations are admitted")
                data = _exam_projection(data)
                collect_identities(data)
                exam = {k: v for k, v in data.items() if k not in {"actions", "definitions", "cards"}}
                exam_root = add(exam, "exam", root, identity_namespace="exam")
                for category, definitions in data.get("definitions", {}).items():
                    rows = definitions if isinstance(definitions, list) else [definitions]
                    for definition in rows:
                        add(definition, "definition:" + category, exam_root, static=True,
                            identity_namespace="exam:" + category)
                for card in data.get("cards", []):
                    exam_card_nodes.append(add(card, "card", exam_root, static=True, identity_namespace="exam"))
                for slot, drink_id in enumerate(data.get("drinks", [])):
                    drink_node = add({"slot": slot}, "drink_instance", exam_root)
                    exam_drink_nodes.append(drink_node)
                    pending_refs.append((drink_node, ("exam:drinks", str(drink_id)), "definition_id"))
            elif scope == "produce" and data is not None:
                add({k: v for k, v in data.items() if k != "actions"}, scope, root, identity_namespace="produce")
            else:
                add(data, scope, root, identity_namespace="produce")
        actions = tuple(add(candidate, "candidate", root,
                            identity_namespace="exam" if decision.kind.startswith("exam") else "produce")
                        for candidate in decision.candidates)
        for action_node, candidate in zip(actions, decision.candidates):
            if candidate.get("type") == "drink":
                slot = candidate["slot"]
                if not isinstance(slot, int) or not 0 <= slot < len(exam_drink_nodes):
                    raise SemanticCoverageError("Illegal public drink slot reference")
                link(action_node, exam_drink_nodes[slot], "action_target")
        for owner, card_index, role in pending_card_indices:
            if not 0 <= card_index < len(exam_card_nodes):
                raise SemanticCoverageError(f"Invalid public card index {card_index} for {role}")
            link(owner, exam_card_nodes[card_index], "references:" + role)
        unresolved = []
        for owner, ref, role in pending_refs:
            target = identities.get(ref)
            if target is not None:
                if target != owner:
                    link(owner, target, "references:" + role)
            elif ref[1] != "":
                unresolved.append({"scope": ref[0], "identity": ref[1], "role": role})
        self.last_report = {"nodes": len(nodes), "edges": len(edges), "candidates": len(actions),
                            "vocabulary": len(vocab.tokens), "unresolved_symbol_references": len(unresolved),
                            "unresolved_reference_examples": unresolved[:20],
                            "static_cache": _compile_definition.cache_info()._asdict(),
                            "buff_projection": projection_report,
                            "semantic_support": "native_typed_ast_and_reviewed_master_operation_projection",
                            "execution_equivalence": "not_claimed"}
        return EncodedDecision(tuple(tuple(row) for row in nodes), tuple(edges), actions,
                               tuple(tree_edges), tuple(depths))


# Pure CPU tensorization is reused by PPO epochs. The cache neither holds an
# EncodedDecision alive nor stores device tensors/learned activations, and has a
# hard byte bound independent of rollout length. It is deliberately not serialized.
_COLLATE_CACHE_LIMIT_BYTES = 128 * 1024 * 1024
_COLLATE_CACHE_MAX_ENTRIES = 512
_COLLATE_CACHE = OrderedDict()
_COLLATE_CACHE_BYTES = 0


def _clear_collate_cache():
    global _COLLATE_CACHE_BYTES
    _COLLATE_CACHE.clear()
    _COLLATE_CACHE_BYTES = 0


def _collate_cache_info():
    return {"entries": len(_COLLATE_CACHE), "bytes": _COLLATE_CACHE_BYTES,
            "limit_bytes": _COLLATE_CACHE_LIMIT_BYTES, "max_entries": _COLLATE_CACHE_MAX_ENTRIES}


def _cpu_graph(example):
    import torch
    global _COLLATE_CACHE_BYTES
    if example.schema_version != ENCODING_VERSION:
        raise SemanticCoverageError("Mixed encoded schema versions")
    identity = id(example)
    cached = _COLLATE_CACHE.get(identity)
    if cached is not None and cached[0]() is example:
        _COLLATE_CACHE.move_to_end(identity)
        return cached[1]
    if cached is not None:
        _COLLATE_CACHE_BYTES -= _COLLATE_CACHE.pop(identity)[2]
    tokens, numbers, owners = [], [], []
    for index, features in enumerate(example.features):
        for token, numeric in features:
            tokens.append(token); numbers.append(numeric); owners.append(index)
    tensor = lambda values, dtype=torch.long: torch.tensor(values, dtype=dtype)
    values = {"feature_tokens": tensor(tokens), "feature_numbers": tensor(numbers, torch.float32),
              "feature_nodes": tensor(owners), "actions": tensor(example.action_nodes),
              "max_feature_token": max(tokens, default=0)}
    for prefix, edges in (("edge", example.edges), ("tree", example.tree_edges)):
        src, dst, roles, pos = zip(*edges) if edges else ((), (), (), ())
        values.update({prefix + "_src": tensor(src), prefix + "_dst": tensor(dst),
                       prefix + "_roles": tensor(roles), prefix + "_positions": tensor(pos, torch.float32)})
    depths = [example.depths[src] for src, _, _, _ in example.tree_edges]
    values.update(tree_depths=tensor(depths), max_depth=max(depths, default=0))
    # Topology is fixed data, not a result of GPU computation. Preserve the
    # original edge order and torch.unique's sorted parent order exactly.
    by_depth = {}
    for index, ((src, dst, _, _), depth) in enumerate(zip(example.tree_edges, depths, strict=True)):
        if depth > 0:
            by_depth.setdefault(depth, []).append((index, src, dst))
    groups = []
    for depth, rows in sorted(by_depth.items(), reverse=True):
        edge_ids, children, destinations = zip(*rows)
        parents = sorted(set(destinations))
        lookup = {parent: index for index, parent in enumerate(parents)}
        groups.append((depth, tensor(edge_ids), tensor(children), tensor(parents),
                       tensor([lookup[parent] for parent in destinations])))
    values["tree_groups"] = tuple(groups)
    size = sum(value.numel() * value.element_size() for value in values.values() if torch.is_tensor(value))
    size += sum(value.numel() * value.element_size() for row in groups for value in row[1:])
    if size <= _COLLATE_CACHE_LIMIT_BYTES:
        def release(reference):
            global _COLLATE_CACHE_BYTES
            present = _COLLATE_CACHE.get(identity)
            if present is not None and present[0] is reference:
                _COLLATE_CACHE_BYTES -= _COLLATE_CACHE.pop(identity)[2]
        _COLLATE_CACHE[identity] = (weakref.ref(example, release), values, size)
        _COLLATE_CACHE_BYTES += size
        while (_COLLATE_CACHE_BYTES > _COLLATE_CACHE_LIMIT_BYTES
               or len(_COLLATE_CACHE) > _COLLATE_CACHE_MAX_ENTRIES):
            _COLLATE_CACHE_BYTES -= _COLLATE_CACHE.popitem(last=False)[1][2]
    return values


def collate(examples, device="cpu"):
    import torch
    if not examples:
        raise ValueError("Empty graph batch")
    cpu = [_cpu_graph(example) for example in examples]
    names = ("feature_tokens", "feature_numbers", "feature_nodes", "edge_src", "edge_dst", "edge_roles",
             "edge_positions", "tree_src", "tree_dst", "tree_roles", "tree_positions", "tree_depths")
    shifted = {"feature_nodes", "edge_src", "edge_dst", "tree_src", "tree_dst"}
    columns = {name: [] for name in names}
    indices = torch.zeros((len(examples), max(len(example.action_nodes) for example in examples)), dtype=torch.long)
    mask = torch.zeros_like(indices, dtype=torch.bool)
    batches, offset, edge_offset = [], 0, 0
    node_slices, tree_groups, parent_counts = [], {}, {}
    for batch, (example, tensors) in enumerate(zip(examples, cpu, strict=True)):
        for name in names:
            value = tensors[name]
            columns[name].append(value + offset if name in shifted else value)
        count = len(example.action_nodes)
        indices[batch, :count] = tensors["actions"] + offset
        mask[batch, :count] = True
        batches.append(torch.full((example.node_count,), batch, dtype=torch.long))
        node_slices.append((offset, offset + example.node_count))
        for depth, edge_ids, children, parents, inverse in tensors["tree_groups"]:
            columns_at_depth = tree_groups.setdefault(depth, [[], [], [], []])
            parent_offset = parent_counts.get(depth, 0)
            for column, value in zip(columns_at_depth, (edge_ids + edge_offset, children + offset,
                                                       parents + offset, inverse + parent_offset), strict=True):
                column.append(value)
            parent_counts[depth] = parent_offset + len(parents)
        offset += example.node_count
        edge_offset += len(example.tree_edges)
    # Concatenation makes fresh storage even for singleton CPU batches: callers
    # may enable input gradients or edit a returned batch without poisoning cache.
    result = {name: torch.cat(values).to(device=device) for name, values in columns.items()}
    # One transfer for all integer topology plans; device-side sections are
    # fixed-length views, so no boolean nonzero/unique needs to synchronize.
    pieces, sections, cursor = [], [], 0
    for depth, group in sorted(tree_groups.items(), reverse=True):
        bounds = []
        for parts in group:
            value = torch.cat(parts)
            pieces.append(value)
            bounds.append((cursor, cursor + len(value)))
            cursor += len(value)
        sections.append(bounds)
    topology = torch.cat(pieces).to(device=device) if pieces else torch.empty(0, dtype=torch.long, device=device)
    result["tree_levels"] = tuple(tuple(topology[start:end] for start, end in bounds) for bounds in sections)
    result["node_slices"] = tuple(node_slices)
    result.update(node_batches=torch.cat(batches).to(device=device),
                  action_indices=indices.to(device=device), mask=mask.to(device=device),
                  max_depth=max(row["max_depth"] for row in cpu),
                  max_feature_token=max(row["max_feature_token"] for row in cpu),
                  node_count=offset, batch_size=len(examples))
    return result
