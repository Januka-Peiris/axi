# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Semantic grain diagnostics (advisory, read-only).

Inspects extracted metadata to surface grain candidates, dimension participation,
join fan-out risk, metric compatibility, and ambiguity reasons per model.
No AI, no mutations.
"""

import json
import os
from collections import defaultdict
from typing import List, Dict, Any, Optional, Tuple

from axi.metadata.indexer import MetadataIndexer
from axi.config.settings import get_settings


def _normalize_columns(value: Any) -> List[str]:
    """Normalize primary key or column list values into a list of strings."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if v]
        except Exception:
            pass
        return [value]
    return []


def _collect_models(indexer: MetadataIndexer, only_model: Optional[str] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """Gather models enriched with entities, relationships, and metrics."""
    models = indexer.list_models() or []
    entities = { (e.get("model") or e.get("name")): e for e in indexer.list_entities() }
    relationships = indexer.list_relationships() or []
    metrics = indexer.list_metrics() or []

    rels_by_model: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for rel in relationships:
        parent = rel.get("parent_model")
        child = rel.get("child_model")
        if parent:
            rels_by_model[parent].append(rel)
        if child:
            rels_by_model[child].append(rel)

    metrics_by_model: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in metrics:
        metrics_by_model[m.get("model")].append(m)

    enriched = []
    for m in models:
        name = m.get("name")
        if only_model and name != only_model:
            continue
        base = {
            "name": name,
            "dimensions": m.get("dimensions") or [],
            "source_tables": m.get("source_tables") or [],
            "entity": entities.get(name) or {},
            "relationships": rels_by_model.get(name, []),
            "metrics": metrics_by_model.get(name, []),
        }
        # Merge any additional fields from raw metadata JSON (grain columns/status)
        meta_path = os.path.join(indexer.metadata_dir, "models", f"{name}.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r") as fh:
                    raw_meta = json.load(fh)
                    for key in ["grain_columns", "grain_status", "grain_detection", "semantic_intent", "dimension_details", "semantic_node", "grain_scope"]:
                        if key in raw_meta:
                            base[key] = raw_meta[key]
            except Exception:
                pass
        enriched.append(base)
    return enriched, entities


def _grain_candidates(model: Dict[str, Any], entities: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    explicit = model.get("grain_columns") or []
    if explicit:
        candidates.append({"columns": _normalize_columns(explicit), "reason": "extracted grain columns"})
    entity = model.get("entity") or {}
    base_pk = _normalize_columns(entity.get("primary_key") or entity.get("pk"))
    if base_pk:
        candidates.append({"columns": base_pk, "reason": "entity primary key"})

    for rel in model.get("relationships", []):
        parent = rel.get("parent_model")
        child = rel.get("child_model")
        fk = rel.get("fk_column")
        if model.get("name") == parent:
            # Parent joined to children → potential grain expansion
            child_entity = entities.get(child, {})
            child_pk = _normalize_columns(child_entity.get("primary_key") or child_entity.get("pk"))
            if base_pk and child_pk:
                cols = list(dict.fromkeys(base_pk + child_pk))
                reason = f"one-to-many to {child}; grain may expand if joined to child rows"
                candidates.append({"columns": cols, "reason": reason})
            elif base_pk and fk:
                cols = list(dict.fromkeys(base_pk + [fk]))
                reason = f"child join via {fk}; grain may expand"
                candidates.append({"columns": cols, "reason": reason})
        elif model.get("name") == child and not base_pk and fk:
            # Child without PK; fallback to FK as candidate
            candidates.append({"columns": [fk], "reason": f"foreign key to {parent} (no primary key detected)"})

    unique = []
    seen = set()
    for cand in candidates:
        key = tuple(cand["columns"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(cand)
    return unique


def _dimension_analysis(
    model: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    entities: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    dims = model.get("dimensions") or []
    entity_cols = set(model.get("entity", {}).get("columns") or [])
    results = []
    candidate_sets = [set(c["columns"]) for c in candidates]

    for d in dims:
        dependency = "attribute"
        if any(d in c for c in candidate_sets):
            dependency = "part_of_candidate_grain"
        elif d in entity_cols:
            dependency = "on_entity"

        source = "model"
        for rel in model.get("relationships", []):
            if rel.get("child_model") == model.get("name") and d == rel.get("fk_column"):
                source = f"join_key_to_{rel.get('parent_model')}"
                dependency = "join_key"
            elif rel.get("parent_model") == model.get("name"):
                child_entity = entities.get(rel.get("child_model"), {})
                child_pk = _normalize_columns(child_entity.get("primary_key") or child_entity.get("pk"))
                if d in child_pk:
                    source = f"child_{rel.get('child_model')}_key"
                    dependency = "join_key"

        results.append({
            "dimension": d,
            "grouped": None,  # grouping not retained in indexed metadata
            "source": source,
            "dependency": dependency,
            "risk": "grouping unknown; verify grouping and joins for this dimension"
        })
    return results


def _join_analysis(model: Dict[str, Any]) -> List[Dict[str, Any]]:
    joins = []
    model_name = model.get("name")
    seen = set()
    for rel in model.get("relationships", []) or []:
        parent = rel.get("parent_model")
        child = rel.get("child_model")
        fk = rel.get("fk_column") or ""
        pk = rel.get("pk_column") or ""
        key = (parent, child, fk, pk)
        if key in seen:
            continue
        seen.add(key)
        direction = "unknown"
        cardinality = "ambiguous"
        impact = "unknown"

        if model_name == parent:
            direction = "parent_to_child"
            if fk:
                cardinality = "one-to-many"
                impact = f"joining {child} may multiply rows along {fk}"
        elif model_name == child:
            direction = "child_to_parent"
            if fk:
                cardinality = "many-to-one"
                impact = f"joining {parent} should not expand grain if {fk} is unique on parent"

        joins.append({
            "join": f"{parent} -> {child}",
            "direction": direction,
            "cardinality": cardinality,
            "fk_column": fk or None,
            "pk_column": pk or None,
            "join_type": rel.get("join_type") or "unknown",
            "impact": impact,
        })
    return joins


def _metric_analysis(metrics: List[Dict[str, Any]], candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    analyses = []
    candidate_sets = [set(c["columns"]) for c in candidates]

    for m in metrics or []:
        declared = _normalize_columns(m.get("grain"))
        agg = m.get("aggregation") or m.get("metric_type")
        safe = None
        note = ""
        suggested_grain = declared or (candidates[0]["columns"] if candidates else [])

        if declared:
            aligned = any(set(declared).issubset(cand) for cand in candidate_sets) if candidate_sets else False
            safe = aligned
            note = "declared grain aligns with candidate" if aligned else "declared grain not aligned with inferred candidates"
        elif not candidates:
            safe = False
            note = "no grain candidates inferred; aggregation safety unknown"
        elif len(candidates) > 1:
            safe = None
            note = "multiple grain candidates; choose explicit grain before aggregating"
        else:
            safe = True
            note = "uses inferred grain from entity primary key"

        analyses.append({
            "metric": m.get("name"),
            "aggregation": agg,
            "declared_grain": declared,
            "suggested_grain": suggested_grain,
            "safe": safe,
            "risk": note
        })
    return analyses


def _grain_status(model: Dict[str, Any], candidates: List[Dict[str, Any]], joins: List[Dict[str, Any]]) -> Dict[str, Any]:
    reasons = []
    status = "clear"

    dims = model.get("dimensions") or []
    metrics = model.get("metrics") or []
    explicit_status = model.get("grain_status")
    if explicit_status == "not_detected":
        return {
            "grain_status": "not_applicable",
            "reasons": ["no grouping or aggregation detected; model treated as non-semantic"],
        }
    if explicit_status in ("ambiguous", "unsafe", "clear"):
        status = explicit_status
        reasons = model.get("grain_reasons", []) or []
    if not candidates and not dims and not metrics and explicit_status is None:
        return {
            "grain_status": "not_applicable",
            "reasons": ["no grouping or aggregation detected; model treated as non-semantic"],
        }

    if not candidates:
        status = "unsafe"
        reasons.append("no grain candidate detected")
    elif len(candidates) > 1:
        status = "ambiguous"
        reasons.append("multiple plausible grains")

    if any(j.get("cardinality") == "one-to-many" for j in joins):
        status = "unsafe"
        reasons.append("fan-out risk from child joins")
    if any(j.get("cardinality") == "ambiguous" for j in joins):
        if status == "clear":
            status = "ambiguous"
        reasons.append("join cardinality unknown")

    return {"grain_status": status, "reasons": reasons}


def model_report(model: Dict[str, Any], entities: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    candidates = _grain_candidates(model, entities)
    dims = _dimension_analysis(model, candidates, entities)
    joins = _join_analysis(model)
    metrics = _metric_analysis(model.get("metrics"), candidates)
    status = _grain_status(model, candidates, joins)
    return {
        "model": model.get("name"),
        "semantic_node": model.get("semantic_node") or model.get("name"),
        "grain_scope": model.get("grain_scope") or "outer",
        "grain_reasons": model.get("grain_reasons") or [],
        "grain_candidates": candidates,
        "dimensions": dims,
        "joins": joins,
        "metrics": metrics,
        **status,
    }


def full_report(model_name: Optional[str] = None) -> Dict[str, Any]:
    settings = get_settings()
    indexer = MetadataIndexer(settings.metadata_dir)
    models, entities = _collect_models(indexer, model_name)
    reports = [model_report(m, entities) for m in models]

    status_counts = defaultdict(int)
    for r in reports:
        status_counts[r["grain_status"]] += 1

    total = len(reports)
    summary = {
        "total_models": total,
        "clear": status_counts.get("clear", 0),
        "ambiguous": status_counts.get("ambiguous", 0),
        "unsafe": status_counts.get("unsafe", 0),
        "not_applicable": status_counts.get("not_applicable", 0),
        "ambiguous_percent": (status_counts.get("ambiguous", 0) / total * 100) if total else 0,
        "unsafe_percent": (status_counts.get("unsafe", 0) / total * 100) if total else 0,
        "not_applicable_percent": (status_counts.get("not_applicable", 0) / total * 100) if total else 0,
    }
    return {"summary": summary, "models": reports}
