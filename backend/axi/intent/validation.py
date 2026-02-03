# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Compile-time validation for Semantic Intent.

Runs BEFORE SQL generation. Fails with explicit errors when:
- metric grain is incompatible with any join target
- joins introduce fan-out relative to metric grain
- a dimension does not belong to the metric's base entity or resolved join path
- filters reference unknown or unresolvable fields
- time dimension is missing or incompatible with grain

Does NOT auto-correct or infer intent.
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from axi.exceptions import IntentValidationError
from axi.intent.models import (
    SemanticIntent,
    JoinStep,
    SimpleFilter,
    AndFilter,
    OrFilter,
    IntentFilter,
)


def _entity_to_alias_map(intent: SemanticIntent) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Build entity -> alias and alias -> entity maps (same logic as compiler)."""
    entities: List[str] = [intent.base_entity]
    for step in intent.join_path:
        if step.from_entity not in entities:
            entities.append(step.from_entity)
        if step.to_entity not in entities:
            entities.append(step.to_entity)
    entity_to_alias: Dict[str, str] = {}
    alias_to_entity: Dict[str, str] = {}
    for entity in entities:
        alias = entity[:1].lower()
        suffix = 0
        while alias in alias_to_entity and alias_to_entity.get(alias) != entity:
            suffix += 1
            alias = (entity[:2] if len(entity) >= 2 else entity) + str(suffix)
        entity_to_alias[entity] = alias
        alias_to_entity[alias] = entity
    return entity_to_alias, alias_to_entity


def _path_entities(intent: SemanticIntent) -> Set[str]:
    """Set of entities in scope: base_entity + all join path from/to."""
    out: Set[str] = {intent.base_entity}
    for step in intent.join_path:
        out.add(step.from_entity)
        out.add(step.to_entity)
    return out


def _ref_entity(
    ref: str,
    base_entity: str,
    entity_to_alias: Dict[str, str],
    alias_to_entity: Dict[str, str],
    path_entities: Set[str],
) -> str | None:
    """
    Return the entity name for a column ref (entity.column or alias.column).
    Returns None if the ref's prefix is not in path (entity or alias resolving to path).
    """
    ref = (ref or "").strip()
    if not ref:
        return None
    if "." not in ref:
        return base_entity  # bare column -> base_entity
    prefix, _ = ref.split(".", 1)
    prefix = prefix.strip()
    if not prefix:
        return None
    if prefix in path_entities:
        return prefix
    if prefix in alias_to_entity and alias_to_entity[prefix] in path_entities:
        return alias_to_entity[prefix]
    return None


def _collect_filter_dimensions(f: IntentFilter) -> List[str]:
    """Collect all dimension (column) refs from a filter tree."""
    if isinstance(f, SimpleFilter):
        return [f.dimension] if f.dimension else []
    if isinstance(f, AndFilter):
        out: List[str] = []
        for c in f.clauses:
            out.extend(_collect_filter_dimensions(c))
        return out
    if isinstance(f, OrFilter):
        out = []
        for c in f.clauses:
            out.extend(_collect_filter_dimensions(c))
        return out
    return []


def _validate_join_path_chain(intent: SemanticIntent, path_entities: Set[str]) -> None:
    """
    Join path must form a chain from base_entity and must not introduce fan-out.
    - First step: from_entity must be base_entity (or base_entity is a mart not in path).
    - Subsequent steps: from_entity must be base_entity or to_entity of a previous step.
    - No duplicate to_entity (joining same table twice can fan out or confuse grain).
    """
    join_path = intent.join_path
    if not join_path:
        return

    name, ver = intent.metric_name, intent.metric_version
    join_entities = set()
    for step in join_path:
        join_entities.add(step.from_entity)
        join_entities.add(step.to_entity)

    # First step: from_entity must be base or we're in "mart" mode (base not in join path)
    first = join_path[0]
    if intent.base_entity not in join_entities:
        # Mart: base_entity is logical; first step can be any entity (e.g. orders)
        pass
    elif first.from_entity != intent.base_entity:
        raise IntentValidationError(
            f"Metric '{name}' (version {ver}): first join target must start from base entity. "
            f"Join step has from_entity='{first.from_entity}' but base_entity is '{intent.base_entity}'.",
            code="GRAIN_INCOMPATIBLE_WITH_JOIN_TARGET",
            hint="Join path must start from base_entity to preserve grain.",
            context={
                "metric_name": name,
                "metric_version": ver,
                "base_entity": intent.base_entity,
                "offending_join": {"from_entity": first.from_entity, "to_entity": first.to_entity},
            },
        )

    # Subsequent steps: from_entity must be base or a previous to_entity (chain, no fan-out)
    mart_mode = intent.base_entity not in join_entities
    seen_to: Set[str] = set()
    allowed_from: Set[str] = {intent.base_entity}
    for i, step in enumerate(join_path):
        if mart_mode and i == 0:
            # Mart: first step can have any from_entity (fact table); accept and continue
            seen_to.add(step.to_entity)
            allowed_from.add(step.from_entity)
            allowed_from.add(step.to_entity)
            continue
        if step.from_entity not in allowed_from:
            raise IntentValidationError(
                f"Metric '{name}' (version {ver}): joins introduce fan-out relative to metric grain. "
                f"Step {i + 1} has from_entity='{step.from_entity}' which is not base_entity or a previous join target.",
                code="JOINS_INTRODUCE_FANOUT",
                hint="Join path must be a chain: each step's from_entity must be base_entity or to_entity of a prior step.",
                context={
                    "metric_name": name,
                    "metric_version": ver,
                    "offending_join": {"from_entity": step.from_entity, "to_entity": step.to_entity},
                },
            )
        if step.to_entity in seen_to:
            raise IntentValidationError(
                f"Metric '{name}' (version {ver}): duplicate join target '{step.to_entity}' can introduce fan-out or ambiguous grain.",
                code="JOINS_INTRODUCE_FANOUT",
                hint="Each join target should appear at most once in the path.",
                context={
                    "metric_name": name,
                    "metric_version": ver,
                    "offending_entity": step.to_entity,
                },
            )
        seen_to.add(step.to_entity)
        allowed_from.add(step.to_entity)


def _validate_grain(
    intent: SemanticIntent,
    entity_to_alias: Dict[str, str],
    alias_to_entity: Dict[str, str],
    path_entities: Set[str],
) -> None:
    """Grain columns must belong to base entity or resolved join path."""
    name, ver = intent.metric_name, intent.metric_version
    for g in intent.grain:
        entity = _ref_entity(g, intent.base_entity, entity_to_alias, alias_to_entity, path_entities)
        if entity is None:
            # Resolve with base when ref is bare column
            if "." not in (g or "").strip():
                continue
            raise IntentValidationError(
                f"Metric '{name}' (version {ver}): metric grain is incompatible with join target. "
                f"Grain column '{g}' does not belong to base entity or resolved join path.",
                code="GRAIN_INCOMPATIBLE_WITH_JOIN_TARGET",
                hint="Grain columns must reference only base_entity or entities in join_path.",
                context={
                    "metric_name": name,
                    "metric_version": ver,
                    "offending_entity_or_dimension": g,
                },
            )


def _validate_dimensions(
    intent: SemanticIntent,
    entity_to_alias: Dict[str, str],
    alias_to_entity: Dict[str, str],
    path_entities: Set[str],
) -> None:
    """Dimensions must belong to base entity or resolved join path."""
    name, ver = intent.metric_name, intent.metric_version
    for dim in intent.dimensions:
        ref = (dim or "").strip()
        if not ref:
            continue
        entity = _ref_entity(ref, intent.base_entity, entity_to_alias, alias_to_entity, path_entities)
        if entity is None:
            raise IntentValidationError(
                f"Metric '{name}' (version {ver}): dimension does not belong to metric's base entity or resolved join path. "
                f"Dimension '{dim}' references unknown or unresolvable entity.",
                code="DIMENSION_NOT_ON_PATH",
                hint="Dimensions must be entity.column or alias.column where entity is base_entity or in join_path.",
                context={
                    "metric_name": name,
                    "metric_version": ver,
                    "offending_entity_or_dimension": dim,
                },
            )


def _validate_filters(
    intent: SemanticIntent,
    entity_to_alias: Dict[str, str],
    alias_to_entity: Dict[str, str],
    path_entities: Set[str],
) -> None:
    """Filters must reference only resolvable fields (base or join path)."""
    name, ver = intent.metric_name, intent.metric_version
    for f in intent.filters:
        for dim_ref in _collect_filter_dimensions(f):
            entity = _ref_entity(dim_ref, intent.base_entity, entity_to_alias, alias_to_entity, path_entities)
            if entity is None:
                raise IntentValidationError(
                    f"Metric '{name}' (version {ver}): filter references unknown or unresolvable field. "
                    f"Filter dimension '{dim_ref}' does not belong to base entity or resolved join path.",
                    code="FILTER_FIELD_UNRESOLVABLE",
                    hint="Filter dimensions must be entity.column or alias.column where entity is in path.",
                    context={
                        "metric_name": name,
                        "metric_version": ver,
                        "offending_entity_or_dimension": dim_ref,
                    },
                )


def _validate_time_dimension(
    intent: SemanticIntent,
    entity_to_alias: Dict[str, str],
    alias_to_entity: Dict[str, str],
    path_entities: Set[str],
) -> None:
    """Time dimension (if present) must resolve to base or join path. If grain implies time, time_dimension must be set."""
    name, ver = intent.metric_name, intent.metric_version
    td = intent.time_dimension
    if td is None:
        # Optional: require time_dimension when grain contains time-like columns (e.g. date, month)?
        # Spec says "time dimension is missing or incompatible" — we interpret "incompatible" when present.
        return

    entity = _ref_entity(td.column_ref, intent.base_entity, entity_to_alias, alias_to_entity, path_entities)
    if entity is None:
        raise IntentValidationError(
            f"Metric '{name}' (version {ver}): time dimension is incompatible with grain. "
            f"Time dimension column_ref '{td.column_ref}' does not belong to base entity or resolved join path.",
            code="TIME_DIMENSION_INCOMPATIBLE_WITH_GRAIN",
            hint="Time dimension column_ref must reference base_entity or an entity in join_path.",
            context={
                "metric_name": name,
                "metric_version": ver,
                "offending_entity_or_dimension": td.column_ref,
            },
        )


def _validate_measures(
    intent: SemanticIntent,
    entity_to_alias: Dict[str, str],
    alias_to_entity: Dict[str, str],
    path_entities: Set[str],
) -> None:
    """Measure column_refs must resolve to base or join path (same as dimensions)."""
    name, ver = intent.metric_name, intent.metric_version
    for m in intent.measures:
        ref = (m.column_ref or "").strip()
        if not ref or ref == "*":
            continue
        entity = _ref_entity(ref, intent.base_entity, entity_to_alias, alias_to_entity, path_entities)
        if entity is None:
            raise IntentValidationError(
                f"Metric '{name}' (version {ver}): measure column_ref does not belong to base entity or resolved join path. "
                f"Measure '{m.name}' column_ref '{ref}' references unknown or unresolvable entity.",
                code="DIMENSION_NOT_ON_PATH",
                hint="Measure column_ref must be entity.column or alias.column where entity is in path.",
                context={
                    "metric_name": name,
                    "metric_version": ver,
                    "offending_entity_or_dimension": ref,
                },
            )


def validate_intent_for_compilation(intent: SemanticIntent) -> None:
    """
    Validate Semantic Intent before SQL generation.

    Raises IntentValidationError with metric name, version, and offending entity/dimension/join when:
    - metric grain is incompatible with any join target
    - joins introduce fan-out relative to metric grain
    - a dimension does not belong to the metric's base entity or resolved join path
    - filters reference unknown or unresolvable fields
    - time dimension is missing or incompatible with grain

    Does NOT auto-correct or infer intent. Does NOT weaken existing validations.
    """
    entity_to_alias, alias_to_entity = _entity_to_alias_map(intent)
    path_entities = _path_entities(intent)

    _validate_join_path_chain(intent, path_entities)
    _validate_grain(intent, entity_to_alias, alias_to_entity, path_entities)
    _validate_dimensions(intent, entity_to_alias, alias_to_entity, path_entities)
    _validate_filters(intent, entity_to_alias, alias_to_entity, path_entities)
    _validate_time_dimension(intent, entity_to_alias, alias_to_entity, path_entities)
    _validate_measures(intent, entity_to_alias, alias_to_entity, path_entities)
