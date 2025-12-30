# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Semantic join reachability (grain-safe, fan-out aware).

Given a starting metric or dimension, return only joinable metrics/dimensions
that do not introduce fan-out or grain breakage. No SQL parsing at runtime;
uses indexed semantic metadata only.
"""

import json
import os
from collections import deque, defaultdict
from typing import Dict, List, Set, Any, Tuple

from axi.metadata.indexer import MetadataIndexer


def _normalize_list(value: Any) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed if v]
        except Exception:
            return [value]
    return []


class SemanticReachability:
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer
        self.model_grains = self._load_model_grains()
        self.adj, self.paths = self._build_safe_adjacency()
        self.entity_by_model = {e.get("model"): e.get("name") for e in indexer.list_entities()}
        self.dimensions_by_entity = self._load_dimensions()
        self.metrics = indexer.list_metrics() or []
        # Simple metric lookup for reuse
        self.metric_by_name = {m.get("name"): m for m in self.metrics}

    def _load_model_grains(self) -> Dict[str, List[str]]:
        """Read grain_columns from metadata JSON files (written by extractor)."""
        grains: Dict[str, List[str]] = {}
        models_dir = os.path.join(self.indexer.metadata_dir, "models")
        if not os.path.exists(models_dir):
            return grains
        for fname in os.listdir(models_dir):
            if not fname.endswith(".json"):
                continue
            path = os.path.join(models_dir, fname)
            try:
                with open(path, "r") as fh:
                    data = json.load(fh)
                    name = data.get("model")
                    if name and data.get("grain_columns"):
                        grains[name] = _normalize_list(data.get("grain_columns"))
            except Exception:
                continue
        return grains

    def _load_dimensions(self) -> Dict[str, List[str]]:
        """Map entity_name -> dimension names."""
        mapping: Dict[str, List[str]] = defaultdict(list)
        try:
            with self.indexer._get_conn() as conn:
                conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
                cur = conn.cursor()
                cur.execute(
                    """SELECT ed.entity_name AS entity, d.name AS dim
                       FROM entity_dimensions ed
                       JOIN dimensions d ON ed.dimension_id = d.id"""
                )
                for row in cur.fetchall():
                    if row.get("entity") and row.get("dim"):
                        mapping[row["entity"]].append(row["dim"])
        except Exception:
            pass
        return mapping

    def _build_safe_adjacency(self) -> Tuple[Dict[str, List[str]], Dict[str, Dict[str, Any]]]:
        """
        Build adjacency allowing only child->parent edges (many-to-one).

        Two categories of edges:
        1. Explicit: Have FK/PK columns from JOIN parsing (safe for query building)
        2. Inferred: DEPENDS_ON relationships without keys (safe for reachability, not for auto-join)

        Returns adjacency list and edge metadata map.
        """
        adj: Dict[str, List[str]] = defaultdict(list)
        edge_meta: Dict[str, Dict[str, Any]] = {}  # "child->parent" -> metadata

        rels = self.indexer.list_relationships() or []
        for rel in rels:
            parent = rel.get("parent_model")
            child = rel.get("child_model")
            fk = rel.get("fk_column") or ""
            pk = rel.get("pk_column") or ""
            join_type = rel.get("join_type") or "UNKNOWN"

            if not parent or not child:
                continue
            if parent == child:
                continue  # Skip self-references

            edge_key = f"{child}->{parent}"

            # Explicit relationships (have FK/PK) take priority
            if fk and pk:
                if parent not in adj[child]:
                    adj[child].append(parent)
                edge_meta[edge_key] = {
                    "type": "explicit",
                    "fk": fk,
                    "pk": pk,
                    "join_type": join_type,
                    "joinable": True
                }
            # DEPENDS_ON relationships (no FK/PK) - still allow reachability
            elif join_type == "DEPENDS_ON":
                # Only add if no explicit relationship exists
                if edge_key not in edge_meta:
                    if parent not in adj[child]:
                        adj[child].append(parent)
                    edge_meta[edge_key] = {
                        "type": "inferred",
                        "fk": None,
                        "pk": None,
                        "join_type": "DEPENDS_ON",
                        "joinable": False,  # Can't auto-generate JOIN SQL
                        "note": "Relationship detected from model dependency; manual join key required"
                    }

        self.edge_meta = edge_meta
        return adj, edge_meta

    def _bfs(self, start: str) -> Dict[str, List[str]]:
        """BFS over safe edges returning path of models for each reachable node."""
        paths: Dict[str, List[str]] = {start: []}
        visited: Set[str] = {start}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            for nxt in self.adj.get(node, []):
                if nxt in visited:
                    continue
                visited.add(nxt)
                paths[nxt] = paths[node] + [f"{node} -> {nxt}"]
                queue.append(nxt)
        return paths

    def _metric_grain(self, metric: Dict[str, Any]) -> List[str]:
        grain = _normalize_list(metric.get("grain"))
        if grain:
            return grain
        model = metric.get("model")
        if model and model in self.model_grains:
            return self.model_grains[model]
        return []

    def _entity_grain(self, entity_name: str) -> List[str]:
        # Use model grain for the entity's model
        ent = self.indexer.get_entity(entity_name)
        if not ent:
            return []
        model = ent.get("model")
        if model and model in self.model_grains:
            return self.model_grains[model]
        return []

    def _get_path_metadata(self, path: List[str]) -> Dict[str, Any]:
        """Get metadata for a path including relationship types."""
        if not path:
            return {"hops": 0, "all_explicit": True, "join_keys": []}

        join_keys = []
        all_explicit = True

        for hop in path:
            # hop format: "child -> parent"
            parts = hop.split(" -> ")
            if len(parts) == 2:
                edge_key = f"{parts[0]}->{parts[1]}"
                meta = getattr(self, 'edge_meta', {}).get(edge_key, {})
                if meta.get("type") == "inferred":
                    all_explicit = False
                if meta.get("fk") and meta.get("pk"):
                    join_keys.append({
                        "from": f"{parts[0]}.{meta['fk']}",
                        "to": f"{parts[1]}.{meta['pk']}",
                        "type": meta.get("type", "unknown")
                    })

        return {
            "hops": len(path),
            "all_explicit": all_explicit,
            "join_keys": join_keys
        }

    def reachable_from_metric(self, metric_name: str) -> Dict[str, Any]:
        metric = self.indexer.get_metric(metric_name)
        if not metric:
            return {"visible_dimensions": [], "visible_metrics": [], "excluded_dimensions": [], "excluded_metrics": []}
        base_model = metric.get("model")
        base_grain = set(self._metric_grain(metric))
        if not base_model:
            return {"visible_dimensions": [], "visible_metrics": [], "excluded_dimensions": [], "excluded_metrics": []}

        paths = self._bfs(base_model)
        reachable_models = set(paths.keys())

        visible_dims = []
        excluded_dims = []

        # Track all dimensions to find unreachable ones
        all_dims_seen = set()

        # Dimensions reachable through entities on reachable models
        for model in reachable_models:
            entity = self.indexer.get_entity(model) or {}
            ent_name = entity.get("name")
            dim_grain = set(self.model_grains.get(model, []))
            dims = self.dimensions_by_entity.get(ent_name, [])

            path = paths[model]
            path_meta = self._get_path_metadata(path)

            for d in dims:
                all_dims_seen.add(d)
                if not base_grain:
                    excluded_dims.append({
                        "name": d,
                        "reason": "metric_grain_unknown",
                        "entity": ent_name,
                        "model": model
                    })
                    continue
                if dim_grain and not dim_grain.issubset(base_grain):
                    excluded_dims.append({
                        "name": d,
                        "reason": "grain_incompatible",
                        "entity": ent_name,
                        "model": model,
                        "dim_grain": list(dim_grain),
                        "metric_grain": list(base_grain)
                    })
                    continue

                visible_dims.append({
                    "name": d,
                    "entity": ent_name,
                    "model": model,
                    "via": path,
                    "via_description": " → ".join([base_model] + [p.split(" -> ")[1] for p in path]) if path else base_model,
                    "hops": path_meta["hops"],
                    "relationship_type": "explicit" if path_meta["all_explicit"] else "inferred",
                    "join_keys": path_meta["join_keys"],
                    "grain_relation": "compatible"
                })

        # Find dimensions that are not reachable at all (no path exists)
        for ent_name, dims in self.dimensions_by_entity.items():
            for d in dims:
                if d not in all_dims_seen:
                    excluded_dims.append({
                        "name": d,
                        "reason": "no_relationship_path",
                        "entity": ent_name
                    })

        visible_metrics = []
        excluded_metrics = []
        for m in self.metrics:
            m_name = m.get("name")
            m_model = m.get("model")
            if m_model not in reachable_models:
                excluded_metrics.append({
                    "name": m_name,
                    "reason": "no_relationship_path",
                    "model": m_model
                })
                continue
            cand_grain = set(self._metric_grain(m))
            if not base_grain or not cand_grain:
                excluded_metrics.append({
                    "name": m_name,
                    "reason": "grain_unknown",
                    "model": m_model
                })
                continue
            if not cand_grain.issubset(base_grain):
                excluded_metrics.append({
                    "name": m_name,
                    "reason": "grain_incompatible",
                    "model": m_model,
                    "metric_grain": list(cand_grain),
                    "base_grain": list(base_grain)
                })
                continue

            path = paths[m_model]
            path_meta = self._get_path_metadata(path)

            visible_metrics.append({
                "name": m_name,
                "model": m_model,
                "shared_grain": cand_grain == base_grain,
                "grain_relation": "shared_grain" if cand_grain == base_grain else "rollup_safe",
                "via": path,
                "hops": path_meta["hops"],
                "relationship_type": "explicit" if path_meta["all_explicit"] else "inferred"
            })

        return {
            "visible_dimensions": visible_dims,
            "visible_metrics": visible_metrics,
            "excluded_dimensions": excluded_dims,
            "excluded_metrics": excluded_metrics,
        }

    # --- Generalized context planning ---

    def _metric_model_and_grain(self, metric_name: str) -> Tuple[str, Set[str]]:
        m = self.metric_by_name.get(metric_name) or {}
        return m.get("model"), set(self._metric_grain(m))

    def _join_path(self, start: str, target: str) -> List[Dict[str, Any]]:
        """
        Return path of models from start to target following safe child->parent edges.
        """
        if start == target:
            return []
        queue = deque([(start, [])])
        visited = {start}
        while queue:
            node, path = queue.popleft()
            for nxt in self.adj.get(node, []):
                if nxt in visited:
                    continue
                new_path = path + [{"from": node, "to": nxt}]
                if nxt == target:
                    return new_path
                visited.add(nxt)
                queue.append((nxt, new_path))
        return []

    def joinable_entities(self, base_entity: str) -> Dict[str, Any]:
        """
        Return entities that can be safely joined from base_entity using safe edges.
        """
        paths = self._bfs(base_entity)
        joinable = []
        for model, hops in paths.items():
            if model == base_entity:
                continue
            ent = self.indexer.get_entity(model)
            if not ent:
                continue
            # Build join key hints from relationship table
            path_edges = []
            prev = base_entity
            valid = True
            for hop in hops:
                src, _, dst = hop.partition(" -> ")
                rel = next((r for r in self.indexer.list_relationships() if r.get("parent_model") == dst and r.get("child_model") == src), None)
                if not rel:
                    valid = False
                    break
                if not rel.get("fk_column") or not rel.get("pk_column"):
                    valid = False
                    break
                path_edges.append({
                    "from": f"{src}.{rel.get('fk_column')}",
                    "to": f"{dst}.{rel.get('pk_column')}",
                    "join_type": "many_to_one"
                })
                prev = dst
            if not valid:
                continue
            joinable.append({
                "entity": ent.get("name") or model,
                "model": model,
                "via": hops,
                "join_type": "many_to_one",
                "keys": path_edges
            })
        return {"joinable_entities": joinable}

    def _entity_context(self, entity_name: str) -> Dict[str, Any]:
        """
        Return all reachable dimensions and joinable entities from a base entity.
        Used for metric creation mode when no metrics are selected yet.

        Args:
            entity_name: Name of the base entity

        Returns:
            Dictionary containing:
                - visible_dimensions: List of dimensions reachable from entity (with join metadata)
                - joinable_entities: List of entities that can be joined
                - base_entity: The base entity name
                - base_model: The base model name
        """
        entity = self.indexer.get_entity(entity_name)
        if not entity:
            return {
                "error": f"Entity '{entity_name}' not found",
                "visible_dimensions": [],
                "joinable_entities": [],
                "base_entity": entity_name,
                "base_model": None
            }

        model = entity.get("model")
        if not model:
            return {
                "warning": f"Entity '{entity_name}' has no associated model",
                "visible_dimensions": [],
                "joinable_entities": [],
                "base_entity": entity_name,
                "base_model": None
            }

        # Get direct dimensions from the entity
        direct_dims = self.entity_dimensions.get(entity_name, [])

        # Get joinable entities with paths
        joinables_result = self.joinable_entities(model)
        joinable_entities = joinables_result.get("joinable_entities", [])

        # Collect all reachable dimensions with metadata
        visible_dimensions = []

        # Add direct dimensions (0 hops)
        for dim in direct_dims:
            visible_dimensions.append({
                "name": dim,
                "entity": entity_name,
                "model": model,
                "hops": 0,
                "via": [],
                "via_description": "Direct",
                "relationship_type": "direct",
                "join_keys": [],
                "grain_relation": "compatible"
            })

        # Add dimensions from joinable entities
        for joinable in joinable_entities:
            j_entity = joinable.get("entity")
            j_model = joinable.get("model")
            j_dims = self.entity_dimensions.get(j_entity, [])

            for dim in j_dims:
                via_list = joinable.get("via", [])
                visible_dimensions.append({
                    "name": dim,
                    "entity": j_entity,
                    "model": j_model,
                    "hops": len(via_list),
                    "via": via_list,
                    "via_description": " → ".join(via_list) if via_list else "Direct",
                    "relationship_type": "explicit",
                    "join_keys": joinable.get("keys", []),
                    "grain_relation": "compatible"
                })

        return {
            "visible_dimensions": visible_dimensions,
            "joinable_entities": joinable_entities,
            "base_entity": entity_name,
            "base_model": model
        }

    def plan_context(self, selected_metrics: List[str], selected_entities: List[str]) -> Dict[str, Any]:
        """
        Given current context (metrics/entities), return safe expansions:
        - compatible metrics (with reasons)
        - compatible dimensions (with relationship paths)
        - excluded dimensions (with reasons why not available)
        - joinable entities
        """
        # NEW: Handle entity-only mode (for metric creation)
        if not selected_metrics and selected_entities:
            base_entity = selected_entities[0]
            return self._entity_context(base_entity)

        if not selected_metrics:
            return {
                "visible_metrics": [],
                "visible_dimensions": [],
                "excluded_dimensions": [],
                "joinable_entities": [],
                "base_metric": None,
                "base_model": None
            }

        base_metric = selected_metrics[0]
        base_model, base_grain = self._metric_model_and_grain(base_metric)

        if not base_model:
            return {
                "visible_metrics": [],
                "visible_dimensions": [],
                "excluded_dimensions": [],
                "joinable_entities": [],
                "base_metric": base_metric,
                "base_model": None,
                "error": "Base metric has no associated model"
            }

        if not base_grain:
            return {
                "visible_metrics": [],
                "visible_dimensions": [],
                "excluded_dimensions": [],
                "joinable_entities": [],
                "base_metric": base_metric,
                "base_model": base_model,
                "warning": "Base metric has no defined grain; dimension filtering may be incomplete"
            }

        # Determine allowed additional metrics
        visible_metrics = []
        excluded_metrics = []
        for name, m in self.metric_by_name.items():
            if name == base_metric:
                continue
            m_model = m.get("model")
            m_grain = set(self._metric_grain(m))

            if not m_grain:
                excluded_metrics.append({
                    "name": name,
                    "reason": "grain_unknown",
                    "model": m_model
                })
                continue

            if m_grain and m_grain.issubset(base_grain):
                reason = "shared_grain" if m_grain == base_grain else "rollup_safe"
                visible_metrics.append({
                    "name": name,
                    "reason": reason,
                    "model": m_model,
                    "grain": list(m_grain)
                })
            else:
                excluded_metrics.append({
                    "name": name,
                    "reason": "grain_incompatible",
                    "model": m_model,
                    "metric_grain": list(m_grain),
                    "base_grain": list(base_grain)
                })

        # Dimensions: reuse reachable_from_metric (now returns rich data)
        reachable = self.reachable_from_metric(base_metric)
        visible_dimensions = reachable.get("visible_dimensions", [])
        excluded_dimensions = reachable.get("excluded_dimensions", [])

        # Joinable entities from base model
        joinables = self.joinable_entities(base_model).get("joinable_entities", [])

        return {
            "visible_metrics": visible_metrics,
            "excluded_metrics": excluded_metrics,
            "visible_dimensions": visible_dimensions,
            "excluded_dimensions": excluded_dimensions,
            "joinable_entities": joinables,
            "base_metric": base_metric,
            "base_model": base_model,
            "base_grain": list(base_grain)
        }
