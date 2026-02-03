# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Build SemanticIntent from AXI metadata (indexer + optional query engine).

Resolves join path from relationships; no raw SQL.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from axi.intent.models import (
    SemanticIntent,
    Measure,
    TimeDimension,
    JoinStep,
    SimpleFilter,
    IntentFilter,
)

if TYPE_CHECKING:
    from axi.metadata.indexer import MetadataIndexer
    from axi.query.engine import SemanticQueryEngine


# Map AXI aggregation names to intent AggregationType
_AGGREGATION_MAP = {
    "sum": "sum",
    "count": "count",
    "avg": "avg",
    "min": "min",
    "max": "max",
    "count_distinct": "count_distinct",
}


def _load_model_json(metadata_dir: str, model_name: str) -> Optional[Dict[str, Any]]:
    """Load full model JSON from metadata_store/models/<model>.json."""
    path = os.path.join(metadata_dir, "models", f"{model_name}.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _expression_to_column_ref(expression: str, source_tables: List[str]) -> str:
    """
    Extract column reference from expression like SUM(o.amount), COUNT(*), COUNT(DISTINCT x.id).
    Returns entity.column or column; warehouse-agnostic.
    """
    if not expression or not isinstance(expression, str):
        return ""
    expr = expression.strip()
    # Strip aggregate: SUM(...), COUNT(...), AVG(...), MIN(...), MAX(...)
    m = re.match(r"(?:SUM|COUNT|AVG|MIN|MAX)\s*\(\s*(?:DISTINCT\s+)?(.+?)\s*\)", expr, re.IGNORECASE)
    if m:
        inner = m.group(1).strip()
        if inner == "*":
            return "*"
        # inner may be "o.amount" or "amount"
        return inner
    return expr


def _normalize_aggregation(agg: Optional[str]) -> str:
    """Map AXI aggregation to intent aggregation type."""
    if not agg:
        return "sum"
    a = (agg or "").strip().lower()
    return _AGGREGATION_MAP.get(a, "sum")


def _parse_filter_string(s: str) -> Optional[SimpleFilter]:
    """
    Parse a filter string like "o.status = 'active'" or "region = 'EU'" into SimpleFilter.
    Best-effort; returns None if unparseable.
    """
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    # Match: col = value, col != value, col > value, etc.
    for op in ["!=", ">=", "<=", "=", ">", "<"]:
        if op in s:
            parts = s.split(op, 1)
            if len(parts) == 2:
                dim = parts[0].strip()
                val = parts[1].strip()
                # Strip quotes from value for JSON
                if (val.startswith("'") and val.endswith("'")) or (val.startswith('"') and val.endswith('"')):
                    val = val[1:-1]
                return SimpleFilter(type="simple", dimension=dim, op=op if op != "=" else "=", value=val)
    if "IS NULL" in s.upper():
        dim = s.upper().split("IS NULL")[0].strip()
        return SimpleFilter(type="simple", dimension=dim, op="IS NULL", value=None)
    if "IS NOT NULL" in s.upper():
        dim = s.upper().split("IS NOT NULL")[0].strip()
        return SimpleFilter(type="simple", dimension=dim, op="IS NOT NULL", value=None)
    return None


def _resolve_join_path_from_relationships(
    base_entity: str,
    target_entities: List[str],
    relationships: List[Dict[str, Any]],
) -> List[JoinStep]:
    """
    Build ordered join path from base_entity to each target using BFS.
    Returns list of JoinStep (order matters).
    """
    from collections import deque

    # Build adjacency: model -> [(neighbor, rel)]
    adj: Dict[str, List[tuple]] = {}
    for r in relationships:
        parent = (r.get("parent_model") or "").strip()
        child = (r.get("child_model") or "").strip()
        if not parent or not child:
            continue
        fk = (r.get("fk_column") or "").strip()
        pk = (r.get("pk_column") or "").strip()
        join_type = (r.get("join_type") or "left").strip().lower()
        if join_type not in ("left", "inner", "right", "full"):
            join_type = "left"
        # Child -> Parent: join child on child.fk = parent.pk
        if child not in adj:
            adj[child] = []
        adj[child].append((parent, ("child", "parent", child, parent, fk, pk, join_type)))
        if parent not in adj:
            adj[parent] = []
        adj[parent].append((child, ("parent", "child", parent, child, pk, fk, join_type)))

    needed = set(t for t in target_entities if t != base_entity)
    if not needed:
        return []

    # BFS from base_entity to collect path to each target
    visited = {base_entity}
    queue = deque([(base_entity, [])])
    paths: Dict[str, List[Dict]] = {}  # entity -> list of edge dicts

    while queue and len(paths) < len(needed):
        node, path = queue.popleft()
        for neighbor, edge in adj.get(node, []):
            from_ent, to_ent = edge[2], edge[3]
            from_col, to_col = edge[4], edge[5]
            jt = edge[6]
            step = {"from_entity": from_ent, "to_entity": to_ent, "from_column": from_col, "to_column": to_col, "join_type": jt}
            new_path = path + [step]
            if neighbor not in visited:
                visited.add(neighbor)
                if neighbor in needed:
                    paths[neighbor] = new_path
                queue.append((neighbor, new_path))

    # Flatten: order by first occurrence along BFS (already in order per path)
    # Merge paths: we need a single ordered list of JoinStep. If we have path to A and path to B,
    # the steps might overlap. Simple approach: concatenate path to entity1, then path to entity2
    # but avoid duplicate steps. So collect all steps in order (visited order of edges).
    ordered_steps: List[Dict] = []
    seen: set = set()
    for ent in needed:
        for step in paths.get(ent, []):
            key = (step["from_entity"], step["to_entity"], step["from_column"], step["to_column"])
            if key not in seen:
                seen.add(key)
                ordered_steps.append(step)
    return [
        JoinStep(
            from_entity=s["from_entity"],
            to_entity=s["to_entity"],
            from_column=s["from_column"],
            to_column=s["to_column"],
            join_type=s["join_type"],
        )
        for s in ordered_steps
    ]


def build_intent_from_metric(
    indexer: "MetadataIndexer",
    metric_name: str,
    metric_version: str = "1.0",
    dimensions_override: Optional[List[str]] = None,
    filters_override: Optional[List[IntentFilter]] = None,
    engine: Optional["SemanticQueryEngine"] = None,
) -> Optional[SemanticIntent]:
    """
    Build a SemanticIntent from AXI metadata for the given metric.

    - indexer: MetadataIndexer (metadata_dir, get_metric, get_entity, get_model, list_relationships).
    - metric_name: Name of the metric.
    - metric_version: Version string for deterministic diffing (default "1.0").
    - dimensions_override: If provided, use these dimensions instead of default.
    - filters_override: If provided, use these typed filters instead of parsing model filters.
    - engine: If provided, use engine to resolve join path; else resolve from model relationships.

    Returns SemanticIntent or None if metric not found.
    """
    metric = indexer.get_metric(metric_name)
    if not metric:
        return None
    
    # Enforce lifecycle: disabled metrics must not allow intent build
    status = (metric.get("status") or "active").strip().lower()
    if status == "disabled":
        from axi.exceptions import MetricDisabledError
        raise MetricDisabledError(
            f"Metric '{metric_name}' is disabled and cannot be used for intent building or compilation.",
            code="METRIC_DISABLED",
            hint="Re-enable the metric or use a different metric.",
            context={"metric_name": metric_name, "status": status},
        )

    model_name = metric.get("model") or metric_name
    entity_name = metric.get("entity_name") or model_name
    base_entity = entity_name

    # Load full model JSON for relationships, dimensions, filters
    model_json = _load_model_json(indexer.metadata_dir, model_name)
    # Prefer model JSON source_tables for join path (physical tables); metric may have model name only
    raw_sources = model_json.get("source_tables") if model_json else None
    if not raw_sources:
        raw_sources = metric.get("source_table") or model_name
    source_tables = raw_sources if isinstance(raw_sources, list) else [raw_sources] if raw_sources else [model_name]
    relationships = list(model_json.get("relationships") or []) if model_json else []
    if not relationships:
        relationships = list(indexer.list_relationships() or [])

    # Measures
    expr = metric.get("expression") or ""
    col_ref = _expression_to_column_ref(expr, source_tables)
    if not col_ref:
        col_ref = "*"
    agg = _normalize_aggregation(metric.get("aggregation"))
    measures = [Measure(name=metric_name, column_ref=col_ref, aggregation=agg)]

    # Grain
    grain_raw = metric.get("grain") or []
    if isinstance(grain_raw, str):
        try:
            grain_raw = json.loads(grain_raw) if grain_raw else []
        except (json.JSONDecodeError, TypeError):
            grain_raw = [grain_raw] if grain_raw else []
    grain = [str(x).strip() for x in grain_raw if x]

    # Dimensions
    if dimensions_override is not None:
        dimensions = [str(d).strip() for d in dimensions_override if d]
    else:
        dims_raw = metric.get("default_dimensions") or (model_json.get("dimensions") if model_json else [])
        if isinstance(dims_raw, str):
            try:
                dims_raw = json.loads(dims_raw) if dims_raw else []
            except (json.JSONDecodeError, TypeError):
                dims_raw = [dims_raw] if dims_raw else []
        dimensions = [str(d).strip() for d in dims_raw if d]

    # Filters
    if filters_override is not None:
        filters = list(filters_override)
    else:
        filter_strs = model_json.get("filters", []) if model_json else []
        if isinstance(filter_strs, str):
            filter_strs = [filter_strs] if filter_strs else []
        filters = []
        for fs in filter_strs:
            pf = _parse_filter_string(fs)
            if pf:
                filters.append(pf)

    # Time dimension
    time_dim = None
    td_name = metric.get("time_dimension")
    if td_name and isinstance(td_name, str) and td_name.strip():
        time_dim = TimeDimension(name=td_name.strip(), column_ref=td_name.strip(), granularity=None)

    # Physical base for join path: use base_entity if it appears in relationships, else first source_table (mart case)
    all_rels = relationships or []
    base_in_graph = any(
        (r.get("parent_model") or "").strip() == base_entity or (r.get("child_model") or "").strip() == base_entity
        for r in all_rels
    )
    physical_base = base_entity if base_in_graph else (source_tables[0] if source_tables else base_entity)
    target_entities = list(dict.fromkeys([physical_base] + [d.split(".", 1)[0].strip() for d in dimensions if "." in d]))
    if source_tables and len(source_tables) > 1:
        target_entities = list(dict.fromkeys([physical_base] + [t for t in source_tables if t != physical_base]))

    # Join path
    if engine:
        try:
            join_path: List[JoinStep] = []
            for target in target_entities:
                if target == physical_base:
                    continue
                path_edges = engine._resolve_join_path(physical_base, target)
                for e in path_edges:
                    join_path.append(
                        JoinStep(
                            from_entity=e.get("source", ""),
                            to_entity=e.get("target", ""),
                            from_column=e.get("source_col", ""),
                            to_column=e.get("target_col", ""),
                            join_type="left",
                        )
                    )
            # Deduplicate by (from_entity, to_entity) while preserving order
            seen_join = set()
            join_path_dedup = []
            for step in join_path:
                key = (step.from_entity, step.to_entity)
                if key not in seen_join:
                    seen_join.add(key)
                    join_path_dedup.append(step)
            join_path = join_path_dedup
        except Exception:
            join_path = _resolve_join_path_from_relationships(physical_base, target_entities, relationships)
    else:
        join_path = _resolve_join_path_from_relationships(physical_base, target_entities, relationships)

    return SemanticIntent(
        metric_name=metric_name,
        metric_version=metric_version,
        base_entity=base_entity,
        grain=grain,
        measures=measures,
        dimensions=dimensions,
        time_dimension=time_dim,
        filters=filters,
        join_path=join_path,
    )
