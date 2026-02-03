# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Optional, Dict, Any, Set
from axi.metadata.indexer import MetadataIndexer
from axi.query.graph import SemanticGraph
from axi.query.reachability import SemanticReachability
from collections import deque
import logging
import re
from axi.utils.logging_config import get_logger
from axi.utils.sanitization import sanitize_identifier, validate_dimension_name
from axi.exceptions import QueryError

logger = get_logger(__name__)

class SemanticQueryEngine:
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer
        self.graph = SemanticGraph(indexer)
        self.reachability = SemanticReachability(indexer)

    # SemanticError removed - use QueryError from axi.exceptions instead

    def resolve_entity_physical_location(self, entity_name: str) -> Optional[str]:
        ent = self.indexer.get_entity(entity_name)
        if not ent:
            return None
        if ent.get("physical_location"):
            return ent["physical_location"]
        db = ent.get("database_name")
        schema = ent.get("schema_name")
        table = ent.get("model") or ent.get("name")
        if db and schema and table:
            return f"{db}.{schema}.{table}"
        return None

    def resolve_entity(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """Return entity with a resolved physical location if possible."""
        ent = self.indexer.get_entity(entity_name)
        if not ent:
            return None
        ent["physical_location"] = self.resolve_entity_physical_location(entity_name)
        return ent

    def _build_relationship_graph(self) -> Dict[str, List[Dict[str, Any]]]:
        """Build adjacency list from relationships table."""
        graph: Dict[str, List[Dict[str, Any]]] = {}
        rels = self.indexer.list_relationships()
        for r in rels:
            parent = r.get("parent_model")
            child = r.get("child_model")
            if not parent or not child:
                continue
            fk = r.get("fk_column") or ""
            pk = r.get("pk_column") or ""
            # Edge: source -> target. We need to know which column belongs to source.
            # Parent -> Child: source=parent (PK), target=child (FK)
            graph.setdefault(parent, []).append({
                "source": parent, 
                "target": child, 
                "source_col": pk, 
                "target_col": fk
            })
            # Child -> Parent: source=child (FK), target=parent (PK)
            graph.setdefault(child, []).append({
                "source": child, 
                "target": parent, 
                "source_col": fk, 
                "target_col": pk
            })
        return graph

    def _resolve_join_path(self, metric_entity: str, dim_entity: str) -> List[Dict[str, Any]]:
        """Find shortest path of join edges between metric_entity and dim_entity using BFS."""
        graph = self._build_relationship_graph()
        if metric_entity == dim_entity:
            return []
        visited = set([metric_entity])
        queue = deque([(metric_entity, [])])
        paths = []
        while queue:
            node, path = queue.popleft()
            for edge in graph.get(node, []):
                nxt = edge["target"]
                if nxt in visited:
                    continue
                new_path = path + [edge]
                if nxt == dim_entity:
                    paths.append(new_path)
                visited.add(nxt)
                queue.append((nxt, new_path))
        if not paths:
            raise QueryError(f"No join path from {metric_entity} to {dim_entity}", code="JOIN_NOT_FOUND", hint="Add relationship or adjust dimensions.")
        if len(paths) > 1:
            raise QueryError(f"Multiple join paths from {metric_entity} to {dim_entity}", code="JOIN_AMBIGUOUS", hint="Narrow relationships or specify explicit path.")
        return paths[0]
    
    def get_effective_grain_with_source(self, metric: Dict[str, Any], entity: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve effective grain for a metric with explicit source tracking.

        Sources (in priority order):
        - "metric_yaml": Explicitly defined in metric YAML file
        - "entity_default": Explicitly defined in entity definition
        - "entity_pk": INFERRED from entity primary key (use with caution)
        - "model_dimensions": INFERRED from model dimensions (use with caution)
        - "none": No grain could be determined

        Returns:
            Dict with 'grain' (list of columns), 'source' (string), and 'inferred' (bool)
        """
        import json

        # Priority 1: Metric YAML grain (EXPLICIT)
        metric_grain = metric.get('grain')
        if metric_grain:
            grain_list = self._parse_grain_value(metric_grain)
            if grain_list:
                return {"grain": grain_list, "source": "metric_yaml", "inferred": False}

        # Priority 2: Load entity if not provided
        if not entity:
            entity_name = metric.get('entity_name')
            if entity_name:
                entity = self.indexer.get_entity(entity_name)

        # Priority 3: Entity default grain (EXPLICIT)
        if entity:
            entity_grain = entity.get('default_grain')
            if entity_grain:
                grain_list = self._parse_grain_value(entity_grain)
                if grain_list:
                    return {"grain": grain_list, "source": "entity_default", "inferred": False}

            # Priority 4: Entity primary key (INFERRED - not reliable as semantic grain)
            primary_key = entity.get('primary_key')
            if primary_key:
                grain_list = self._parse_grain_value(primary_key)
                if grain_list:
                    return {"grain": grain_list, "source": "entity_pk", "inferred": True}

        # Priority 5: Model dimensions (INFERRED - fallback only)
        model_name = metric.get('model')
        if not model_name and entity:
            model_name = entity.get('model')

        if model_name:
            model = self.indexer.get_model(model_name)
            if model:
                dimensions = model.get('dimensions', [])
                grain_list = self._parse_grain_value(dimensions)
                if grain_list:
                    return {"grain": grain_list, "source": "model_dimensions", "inferred": True}

        # Final fallback: no grain
        return {"grain": [], "source": "none", "inferred": False}

    def _parse_grain_value(self, value) -> List[str]:
        """Parse grain value from various formats to list of strings."""
        import json
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [str(d) for d in parsed if d]
                elif parsed:
                    return [str(parsed)]
            except (json.JSONDecodeError, TypeError):
                return [value] if value.strip() else []
        elif isinstance(value, list):
            return [str(d) for d in value if d]
        return []

    def get_effective_grain(self, metric: Dict[str, Any], entity: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Resolve effective grain for a metric.

        WARNING: This may return INFERRED grain from PK or model dimensions.
        Use get_effective_grain_with_source() to check if grain is explicit.

        Returns:
            List of dimension names representing the metric's grain
        """
        result = self.get_effective_grain_with_source(metric, entity)
        return result["grain"]

    def get_reachable_dimensions(self, metric_name: str) -> Dict[str, Any]:
        """
        Grain-safe, fan-out-safe reachability for a metric.
        Returns visible and excluded items with reasons.
        """
        return self.reachability.reachable_from_metric(metric_name)

    def plan_sqlrunner_context(self, metrics: List[str], entities: List[str]) -> Dict[str, Any]:
        """
        Generalized context planning: compatible metrics, dimensions, and joinable entities.
        """
        return self.reachability.plan_context(metrics, entities)
    
    def get_allowed_dimensions_for_metric(self, metric_name: str) -> List[str]:
        """
        Get list of dimensions allowed for a metric based on its grain.
        - If metric has explicit dimensions list, use that (whitelist)
        - Otherwise, return all entity dimensions
        - Filter out dimensions incompatible with grain (future enhancement)
        """
        metric = self.indexer.get_metric(metric_name)
        if not metric:
            raise ValueError(f"Metric '{metric_name}' not found")
        
        # If metric has explicit dimensions list, use that as whitelist
        metric_dimensions = metric.get('dimensions', [])
        if metric_dimensions:
            import json
            if isinstance(metric_dimensions, str):
                try:
                    dim_list = json.loads(metric_dimensions)
                    if isinstance(dim_list, list):
                        return [str(d) for d in dim_list if d]
                except (json.JSONDecodeError, TypeError):
                    pass
            elif isinstance(metric_dimensions, list):
                return [str(d) for d in metric_dimensions if d]
        
        # Otherwise, get all reachable dimensions
        reachable = self.get_reachable_dimensions(metric_name)
        all_dims = []
        for model_name, dims in reachable.items():
            for dim in dims:
                if isinstance(dim, str):
                    all_dims.append(dim)
                elif isinstance(dim, dict):
                    dim_name = dim.get('name') or dim.get('dimension_name')
                    if dim_name:
                        all_dims.append(dim_name)
        
        return sorted(list(set(all_dims)))



    def generate_sql(self, metric_name: str, dimensions: List[str] = [], filters: List[Any] = [], dialect: str = "postgres", compare: str = None, window: str = None, optimize: bool = True) -> str:
        """
        Generates SQL for a given metric and context.
        Supports:
        - Defaults (dims, filters)
        - Metric Types: Aggregate, Ratio, Semi-Additive
        - Derived Metrics (Basic Expansion)
        - Time Intelligence (Compare, Window)
        """
        logger.debug(f"Generating SQL for metric: {metric_name}, dimensions: {dimensions}, filters: {len(filters)}")
        dimensions = dimensions or []
        filters = filters or []
        
        metric = self.indexer.get_metric(metric_name)
        if not metric:
            logger.warning(f"Metric not found: {metric_name}")
            raise QueryError(f"Metric '{metric_name}' not found", code="UNSUPPORTED_METRIC")
        
        # 1. Resolve effective grain
        entity = None
        entity_name = metric.get('entity_name')
        if entity_name:
            entity = self.resolve_entity(entity_name)
        
        effective_grain = self.get_effective_grain(metric, entity)
        logger.debug(f"Effective grain for {metric_name}: {effective_grain}")
            
        # 2. Apply Defaults
        if not dimensions:
             # Try default_dimensions, then grain, then inference
             default_dims = metric.get('default_dimensions', [])
             if default_dims:
                 # Deserialize if it's a JSON string
                 import json
                 if isinstance(default_dims, str):
                     try:
                         default_dims = json.loads(default_dims)
                     except (json.JSONDecodeError, TypeError):
                         default_dims = []
                 # Validate it's a list and extract string values
                 if isinstance(default_dims, list):
                     dimensions = [str(d) for d in default_dims if d]
                 else:
                     dimensions = []
                 logger.debug(f"Using default dimensions: {dimensions}")
             elif effective_grain:
                 # Use effective grain as default dimensions
                 dimensions = [str(d) for d in effective_grain if d]
                 logger.debug(f"Using effective grain as dimensions: {dimensions}")
        
        default_filter = metric.get('default_filter')
        if default_filter:
            filters.append(default_filter)
            
        # 3. Resolve Metric Expression
        # Handles Ratio and Derived (Inline Expansion)
        final_expr = self._resolve_expression(metric, dialect)
        metric_alias = metric_name
        
        source_model = metric.get('model')
        # Resolve physical location if available
        physical = None
        if entity_name:
            physical = self.resolve_entity_physical_location(entity_name)
        source_table = physical or metric.get('source_table') or source_model
        if not source_table:
            raise QueryError(f"Cannot resolve physical location for entity '{entity_name or source_model}'", code="ENTITY_UNRESOLVED")
        base_filters = metric.get('filters') or []
        
        # 3. Time Intelligence Prep
        time_dim = metric.get('time_dimension')
        if (compare or window) and not time_dim:
             # Try to find time dim in dimensions if not in metadata
             # Fallback
             pass
        
        # 4. Join Logic and dimension resolution
        target_models = set()
        clean_dims = []
        joins_sql = []
        aliases: Dict[str, str] = {}

        def sanitize_ident(s: str):
            try:
                return sanitize_identifier(s)
            except ValueError as e:
                raise QueryError(str(e), code="INVALID_IDENTIFIER")

        def get_alias(model: str) -> str:
            if model in aliases:
                return aliases[model]
            base = model[:1].lower()
            suffix = 1
            alias = base
            while alias in aliases.values():
                suffix += 1
                alias = f"{base}{suffix}"
            aliases[model] = alias
            return alias

        base_alias = get_alias(source_model)

        # NEW: Detect entities from referenced metrics in expression
        expr = metric.get('expression', '')
        metric_refs = self._extract_metric_references(expr)
        for ref_name in metric_refs:
            ref_metric = self.indexer.get_metric(ref_name)
            if ref_metric:
                ref_entity = ref_metric.get('entity_name')
                ref_model = ref_metric.get('model')
                # If referenced metric is from a different entity, we need to join
                if ref_entity and ref_entity != entity_name:
                    target_models.add(ref_model or ref_entity)
                    logger.debug(f"Added target model '{ref_model or ref_entity}' from referenced metric '{ref_name}'")
                elif ref_model and ref_model != source_model:
                    target_models.add(ref_model)
                    logger.debug(f"Added target model '{ref_model}' from referenced metric '{ref_name}'")

        # Parse dimensions, detect target entities and validate existence
        for dim in dimensions:
            # Validate dimension name
            try:
                validate_dimension_name(dim)
            except ValueError as e:
                logger.warning(f"Invalid dimension name: {dim} - {e}")
                raise QueryError(f"Invalid dimension name: {dim}", code="INVALID_DIMENSION")

            sanitize_ident(dim)
            if "." in dim:
                # Explicit model.dimension format
                model, col = dim.split(".", 1)
                target_models.add(model)
                clean_dims.append((model, col))
            else:
                # Auto-detect which entity this dimension belongs to
                detected_entity = self._detect_dimension_entity(dim, metric)
                if detected_entity and detected_entity != entity_name:
                    # Dimension is from a different entity - need to join
                    # Get the model for this entity
                    dim_entity_obj = self.indexer.get_entity(detected_entity)
                    if dim_entity_obj:
                        dim_model = dim_entity_obj.get('model') or detected_entity
                        target_models.add(dim_model)
                        clean_dims.append((dim_model, dim))
                        logger.debug(f"Dimension '{dim}' detected from entity '{detected_entity}', will join to '{dim_model}'")
                    else:
                        # Entity not found, use dimension as-is
                        dim_model = entity_name or source_model
                        clean_dims.append((dim_model, dim))
                else:
                    # Dimension is from base entity or detection failed
                    dim_model = entity_name or source_model
                    clean_dims.append((dim_model, dim))

        # Resolve joins for each target model
        for tgt in target_models:
            path = self._resolve_join_path(source_model, tgt)
            for edge in path:
                left = edge["source"]
                right = edge["target"]
                l_alias = get_alias(left)
                r_alias = get_alias(right)
                
                l_col = edge.get("source_col")
                r_col = edge.get("target_col")
                
                if not l_col or not r_col:
                    raise QueryError(f"Join keys missing between {left} and {right}", code="JOIN_NOT_FOUND")
                
                # Cartesian risk check can be improved by checking if join keys are PKs
                # For now, we trust the relationship definition
                
                join_sql = f"LEFT JOIN {right} AS {r_alias} ON {l_alias}.{l_col} = {r_alias}.{r_col}"
                if join_sql not in joins_sql:
                    joins_sql.append(join_sql)

        # Validate filters (structured objects) and map to aliases
        validated_filters = []
        allowed_ops = {"=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN", "BETWEEN", "LIKE"}

        def _dimension_exists(model: str, col: str) -> bool:
            # Try entity name first, then model name
            ent = self.indexer.get_entity(model)
            if not ent:
                # If model is actually a model name, try to find entity by model
                model_obj = self.indexer.get_model(model)
                if model_obj:
                    # Find entity with this model
                    entities = self.indexer.list_entities()
                    for e in entities:
                        if e.get("model") == model:
                            ent = e
                            break
            if ent and ent.get("columns"):
                for c in ent["columns"]:
                    if isinstance(c, dict) and c.get("name") == col:
                        return True
            return True  # if unknown, allow

        def _dimension_type(model: str, col: str) -> Optional[str]:
            # Try entity name first, then model name
            ent = self.indexer.get_entity(model)
            if not ent:
                # If model is actually a model name, try to find entity by model
                model_obj = self.indexer.get_model(model)
                if model_obj:
                    # Find entity with this model
                    entities = self.indexer.list_entities()
                    for e in entities:
                        if e.get("model") == model:
                            ent = e
                            break
            if ent and ent.get("columns"):
                for c in ent["columns"]:
                    if isinstance(c, dict) and c.get("name") == col:
                        return c.get("type") or c.get("data_type")
            return None

        for f in filters:
            if isinstance(f, dict):
                dim = f.get("dimension")
                op = f.get("op")
                val = f.get("value")
                if not dim:
                    raise QueryError("Filter missing dimension", code="DIMENSION_NOT_FOUND")
                if op not in allowed_ops:
                    raise QueryError(f"Operator {op} not allowed", code="INVALID_FILTER_OPERATOR")
                if "." in dim:
                    m, c = dim.split(".", 1)
                else:
                    # Use entity_name if available, fallback to source_model
                    m, c = (entity_name or source_model), dim
                if not _dimension_exists(m, c):
                    raise QueryError(f"Dimension '{dim}' not found", code="DIMENSION_NOT_FOUND")
                dtype = (_dimension_type(m, c) or "").lower()
                if dtype:
                    if "date" in dtype or "time" in dtype:
                        # allow comparisons but ensure value convertible
                        if op in {"LIKE"}:
                            raise QueryError(f"Cannot use LIKE on date dimension {dim}", code="TYPE_MISMATCH")
                    if "int" in dtype or "number" in dtype or "decimal" in dtype:
                        if op == "LIKE":
                            raise QueryError(f"Cannot use LIKE on numeric dimension {dim}", code="TYPE_MISMATCH")
                alias = get_alias(m)
                if op in {"IN", "NOT IN"}:
                    if isinstance(val, list):
                        vals = ", ".join([f"'{sanitize_ident(str(v))}'" for v in val])
                        validated_filters.append(f"{alias}.{c} {op} ({vals})")
                    else:
                        raise QueryError(f"Operator {op} requires a list value", code="INVALID_FILTER_VALUE")
                elif op == "BETWEEN" and isinstance(val, list) and len(val) == 2:
                    validated_filters.append(f"{alias}.{c} BETWEEN '{sanitize_ident(str(val[0]))}' AND '{sanitize_ident(str(val[1]))}'")
                else:
                    validated_filters.append(f"{alias}.{c} {op} '{sanitize_ident(str(val))}'")
            elif isinstance(f, str):
                if ";" in f or "--" in f or "/*" in f:
                    raise QueryError("Unsafe filter", code="INVALID_FILTER_OPERATOR")
                validated_filters.append(f)
            else:
                raise QueryError(f"Unsupported filter format: {f}", code="INVALID_FILTER_OPERATOR")

        # 5. Core Query Construction
        # Validate grain availability (tolerant to missing metadata)
        valid_grain = []
        if effective_grain:
            grain_entity_name = entity_name or source_model
            for g in effective_grain:
                if not g or str(g).lower() == "unknown":
                    continue
                if "." in g:
                    gm, gc = g.split(".", 1)
                else:
                    gm, gc = grain_entity_name, g
                ent = self.indexer.get_entity(gm)
                if not ent:
                    logger.warning(f"Skipping grain validation: entity '{gm}' not found for metric '{metric_name}'")
                    continue
                cols = ent.get("columns") or []
                if cols and not any((isinstance(c, dict) and c.get("name") == gc) for c in cols):
                    logger.warning(f"Skipping grain column '{gc}' on entity '{gm}' (not found); continuing without strict grain enforcement")
                    continue
                valid_grain.append(g)

        grain_for_sql = valid_grain or [g for g in effective_grain if g and str(g).lower() != "unknown"]

        # GROUP BY: combine selected dimensions and grain
        grain_dims_clean = []
        for grain_dim in grain_for_sql:
            if "." in grain_dim:
                model, col = grain_dim.split(".", 1)
                grain_dims_clean.append((model, col))
            else:
                grain_dims_clean.append((source_model, grain_dim))

        # Filter out placeholders
        grain_dims_clean = [(m, d) for m, d in grain_dims_clean if d and d.lower() != "unknown"]
        clean_dims = [(m, d) for m, d in clean_dims if d and d.lower() != "unknown"]

        all_group = {(m, d) for m, d in clean_dims} | {(m, d) for m, d in grain_dims_clean}
        group_by_str = ", ".join([f"{get_alias(m)}.{d}" for m, d in all_group]) if all_group else ""

        # SELECT with aliases
        select_dim_sql = [f"{get_alias(m)}.{d} AS {d}" for m, d in all_group]
        if metric_alias in [d for _, d in all_group]:
            raise QueryError(f"Metric '{metric_alias}' conflicts with dimension name", code="ALIAS_COLLISION")
        select_cols = select_dim_sql + [f"{final_expr} AS {metric_alias}"]

        # FROM
        from_str = f"{source_table} AS {base_alias}"

        # WHERE
        all_filters = base_filters + validated_filters
        where_str = " AND ".join(all_filters) if all_filters else ""

        joins_clause = "\n".join(joins_sql)
        core_sql = f"SELECT\n  {', '.join(select_cols)}\nFROM {from_str}"
        if joins_clause:
            core_sql += f"\n{joins_clause}"
        if where_str:
            core_sql += f"\nWHERE {where_str}"
        if group_by_str:
            core_sql += f"\nGROUP BY {group_by_str}"
            
        # 6. Time Intelligence (Wrapping)
        if compare and time_dim:
             return self._apply_time_compare(core_sql, metric_alias, time_dim, compare, clean_dims, dialect)
        
        if window and time_dim:
             # Window functions usually applied usually need the window logic inside the projection.
             # But here we wrapped core query.
             # Simplified: just return core query for now if window implementation is complex self-join.
             # Or use Snowflake QUALIFY / Window functions if not aggregated yet? 
             # For aggregated metrics, windowing is over the result set.
             pass
             
        if clean_dims:
             core_sql += f"\nORDER BY {clean_dims[0]}"
             
        final_sql = core_sql + ";"
        
        # Optimization
        if optimize:
            logger.debug(f"Optimizing SQL for dialect: {dialect}")
            # Lazy load
            from axi.optimizer.core import Optimizer, OptimizationContext
            from axi.optimizer.rules import get_default_rules
            
            # Context could include config
            # MVP: empty config or basic
            ctx = OptimizationContext(config={"optimizer.rules.snowflake_hints": dialect == "snowflake"})
            opt = Optimizer(ctx)
            for rule in get_default_rules():
                 opt.add_rule(rule)
            
            final_sql = opt.optimize(final_sql, dialect=dialect)
            logger.debug("SQL optimization completed")
        
        # Hooks: Before Execute (actually before return of SQL string)
        from axi.plugins.registry import HOOKS_REGISTRY
        for hook in HOOKS_REGISTRY["before_execute"]:
             # Hook might mutate context or just log
             try:
                 hook({"metric": metric_name, "sql": final_sql})
             except Exception as e:
                 print(f"Hook error: {e}")

        return final_sql

    def _extract_metric_references(self, expr: str) -> List[str]:
        """Extract all {metric_name} patterns from expression.

        Args:
            expr: SQL expression potentially containing {metric_name} references

        Returns:
            List of metric names referenced in the expression

        Example:
            "{total_revenue} / {total_orders}" -> ["total_revenue", "total_orders"]
        """
        if not expr:
            return []
        pattern = r'\{([a-z_][a-z0-9_]*)\}'
        return re.findall(pattern, expr, re.IGNORECASE)

    def _detect_dimension_entity(self, dim_name: str, metric: Dict) -> Optional[str]:
        """
        Find which entity a dimension belongs to.

        First checks dimension_entity_map in metric metadata, then uses reachability.

        Args:
            dim_name: Name of the dimension
            metric: Metric definition dictionary

        Returns:
            Entity name that owns this dimension, or None if not found
        """
        # Check dimension_entity_map first (stored in metric metadata)
        dim_entity_map = metric.get("dimension_entity_map") or {}
        if dim_name in dim_entity_map:
            return dim_entity_map[dim_name]

        # Fallback to reachability API
        base_entity = metric.get('entity_name') or metric.get('model')
        if not base_entity:
            return None

        try:
            # Use reachability to find dimension
            context = self.reachability.plan_context([], [base_entity])
            for visible_dim in context.get('visible_dimensions', []):
                if visible_dim['name'] == dim_name:
                    return visible_dim['entity']
        except Exception as e:
            logger.warning(f"Failed to detect entity for dimension '{dim_name}': {e}")

        return None

    def _resolve_expression(self, metric: Dict, dialect: str, _visited: Optional[Set[str]] = None) -> str:
        """Resolve metric expression, recursively expanding {metric_name} references.

        Args:
            metric: Metric definition dictionary
            dialect: SQL dialect (postgres, snowflake, etc.)
            _visited: Set of metric names already visited (for circular dependency detection)

        Returns:
            Fully resolved SQL expression

        Raises:
            QueryError: If circular dependency detected or referenced metric not found
        """
        if _visited is None:
            _visited = set()

        # Circular dependency check
        metric_name = metric.get('name')
        if metric_name and metric_name in _visited:
            raise QueryError(
                f"Circular dependency detected: metric '{metric_name}' references itself",
                code="CIRCULAR_DEPENDENCY"
            )

        # Add current metric to visited set
        if metric_name:
            _visited = _visited | {metric_name}

        m_type = metric.get('metric_type', 'aggregate')
        expr = metric.get('expression', '')

        # Extract and resolve metric references
        metric_refs = self._extract_metric_references(expr)
        if metric_refs:
            logger.debug(f"Resolving metric references in '{metric_name}': {metric_refs}")

            for ref_name in metric_refs:
                ref_metric = self.indexer.get_metric(ref_name)
                if not ref_metric:
                    raise QueryError(
                        f"Referenced metric '{ref_name}' not found in expression of metric '{metric_name}'",
                        code="METRIC_NOT_FOUND"
                    )

                # Recursively resolve the referenced metric's expression
                try:
                    resolved_expr = self._resolve_expression(ref_metric, dialect, _visited)
                    # Replace {metric_name} with (resolved_expression)
                    # Wrap in parentheses to preserve operator precedence
                    expr = expr.replace(f"{{{ref_name}}}", f"({resolved_expr})")
                    logger.debug(f"Resolved {{" + ref_name + f"}} -> ({resolved_expr[:50]}...)")
                except Exception as e:
                    raise QueryError(
                        f"Failed to resolve metric reference '{ref_name}' in '{metric_name}': {str(e)}",
                        code="METRIC_RESOLUTION_ERROR"
                    ) from e

        # Check Plugin Registry
        from axi.plugins.registry import METRIC_TYPES_REGISTRY
        if m_type in METRIC_TYPES_REGISTRY:
             plugin_metric = METRIC_TYPES_REGISTRY[m_type]
             # For MVP, assume it's a class with static to_sql or instantiated
             # If static method:
             try:
                 return plugin_metric.to_sql(metric) # Pass metric definition
             except Exception as e:
                 return f"ERROR_PLUGIN_METRIC: {e}"

        if m_type == 'ratio':
            num = metric.get('numerator')
            denom = metric.get('denominator')
            
            # Fallback to expression split if fields empty
            if not num or not denom:
                parts = expr.split('/')
                if len(parts) >= 2:
                    num = parts[0].strip()
                    denom = "/".join(parts[1:]).strip() # Handle multiple slashes recursively? or just split once?
                    # Ideally, should not rely on split.
                else:
                     num = expr # Error state or single col?
                     denom = "1"
            
            # Resolve recursive (assuming simple column or agg for now, or another metric?)
            # Validating if num/denom are metrics or columns is needed. 
            # Assuming raw expressions for MVP or columns.
            
            if dialect == 'snowflake':
                return f"TRY_DIVIDE({num}, {denom})"
            else:
                return f"CAST({num} AS FLOAT) / NULLIF({denom}, 0)"
                
        elif m_type == 'semi_additive':
            # LAST_VALUE(val) OVER (ORDER BY time_dim) mechanism
            # Requires knowing time dim context.
            # Simplified:
            method = metric.get('semi_additive_method', 'last_value')
            sa_dim = metric.get('semi_additive_dimension', 'date')
            if method == 'last_value':
                return f"LAST_VALUE({expr} IGNORE NULLS) OVER (ORDER BY {sa_dim})"
                
        elif dialect == 'snowflake':
             # General Snowflake optimizations
             if "CASE WHEN" in expr:
                 expr = expr.replace("CASE WHEN", "IFF(").replace("THEN", ",").replace("ELSE", ",").replace("END", ")")
        
        return expr

    def _build_joins(self, source_model: str, target_models: set) -> str:
        joins = []
        aliases = {source_model: source_model}
        for target in target_models:
            if target == source_model: continue
            path = self.graph.find_path(source_model, target)
            if not path: continue # Skip if unreachable
            
            for edge in path:
                rel = edge['rel']
                p_alias = rel['parent_model']
                c_alias = rel['child_model']
                aliases[p_alias], aliases[c_alias] = p_alias, c_alias
                
                # Assume Left Joins for safety or Inner? Inner for now.
                if edge['type'] == 'child_to_parent':
                     joins.append(f"JOIN {p_alias} {p_alias} ON {c_alias}.{rel['fk_column']} = {p_alias}.{rel['pk_column']}")
                else:
                     joins.append(f"JOIN {c_alias} {c_alias} ON {p_alias}.{rel['pk_column']} = {c_alias}.{rel['fk_column']}")
        
        # Dedupe
        return "\n".join(sorted(list(set(joins))))

    def _apply_time_compare(self, base_sql: str, metric_alias: str, time_dim: str, compare: str, dims: List[str], dialect: str) -> str:
        # CTE Approach
        # WITH current AS (base_sql), past AS (base_sql_with_filter_shift)
        # Verify dialect for Date Math
        
        date_func = "DATEADD" if dialect == "snowflake" else "DATE_ADD" 
        # ANSI/Spark usually date_add(col, days). Snowflake DATEADD(unit, val, col)
        
        shift = ""
        if compare == "previous_period":
            # Hard without knowing period grain. Assuming Month?
            # Or assume we shift the JOIN condition.
            # Easiest: LAG over the result set if time_dim is in dims.
            
            # Check if time_dim is in dims
            has_time = any(time_dim in d for d in dims)
            if has_time:
                 # Use Window Function
                 return f"""
                 WITH base AS ({base_sql})
                 SELECT *,
                   LAG({metric_alias}) OVER (ORDER BY {time_dim}) as {metric_alias}_prev
                 FROM base
                 """
        
        return base_sql # Fallback
