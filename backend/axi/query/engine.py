# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Optional, Dict, Any
from axi.metadata.indexer import MetadataIndexer
from axi.query.graph import SemanticGraph

class SemanticQueryEngine:
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer
        self.graph = SemanticGraph(indexer)
    
    def get_effective_grain(self, metric: Dict[str, Any], entity: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Resolve effective grain for a metric in priority order:
        1. Metric YAML grain (if present)
        2. Entity default grain (if defined)
        3. Entity primary key dimensions
        4. All non-aggregated dimensions from model
        
        Returns:
            List of dimension names representing the metric's grain
        """
        import json
        
        # Priority 1: Metric YAML grain
        metric_grain = metric.get('grain')
        if metric_grain:
            if isinstance(metric_grain, str):
                # Parse JSON string if needed
                try:
                    grain_list = json.loads(metric_grain)
                    if isinstance(grain_list, list):
                        return [str(d) for d in grain_list if d]
                    elif grain_list:
                        return [str(grain_list)]
                except (json.JSONDecodeError, TypeError):
                    # Not JSON, treat as single dimension
                    return [metric_grain] if metric_grain.strip() else []
            elif isinstance(metric_grain, list):
                return [str(d) for d in metric_grain if d]
        
        # Priority 2: Load entity if not provided
        if not entity:
            entity_name = metric.get('entity_name')
            if entity_name:
                entity = self.indexer.get_entity(entity_name)
        
        # Priority 3: Entity default grain (if we add this field in future)
        if entity:
            entity_grain = entity.get('default_grain')
            if entity_grain:
                if isinstance(entity_grain, str):
                    try:
                        grain_list = json.loads(entity_grain)
                        if isinstance(grain_list, list):
                            return [str(d) for d in grain_list if d]
                    except (json.JSONDecodeError, TypeError):
                        return [entity_grain] if entity_grain.strip() else []
                elif isinstance(entity_grain, list):
                    return [str(d) for d in entity_grain if d]
            
            # Priority 4: Entity primary key
            primary_key = entity.get('primary_key')
            if primary_key:
                if isinstance(primary_key, str):
                    return [primary_key]
                elif isinstance(primary_key, list):
                    return [str(pk) for pk in primary_key if pk]
        
        # Priority 5: Model dimensions (fallback)
        model_name = metric.get('model')
        if not model_name and entity:
            model_name = entity.get('model')
        
        if model_name:
            model = self.indexer.get_model(model_name)
            if model:
                dimensions = model.get('dimensions', [])
                if dimensions:
                    if isinstance(dimensions, str):
                        try:
                            dim_list = json.loads(dimensions)
                            if isinstance(dim_list, list):
                                return [str(d) for d in dim_list if d]
                        except (json.JSONDecodeError, TypeError):
                            pass
                    elif isinstance(dimensions, list):
                        return [str(d) for d in dimensions if d]
        
        # Final fallback: empty list (no grain constraint)
        return []

    def get_reachable_dimensions(self, metric_name: str) -> Dict[str, List[str]]:
        """
        Returns a dictionary of reachable dimensions for a given metric.
        grouped by model name.
        """
        metric = self.indexer.get_metric(metric_name)
        if not metric:
            raise ValueError(f"Metric '{metric_name}' not found")
        
        source_model = metric.get('model')
        if not source_model:
            return {}
        
        reachable = {}
        
        # 1. Local dimensions
        # Logic: get model for metric, list dimensions
        model_def = self.indexer.get_model(source_model)
        if model_def:
            reachable[source_model] = model_def.get('dimensions', [])
            
        # 2. Related dimensions (BFS)
        # Find all reachable models in the graph from source_model
        # Use queue for BFS
        
        # We need a list of ALL models, then check reachability? or traverse?
        # Graph has adj list.
        
        # Traverse
        seen = set([source_model])
        queue = [source_model]
        
        while queue:
            curr = queue.pop(0)
            
            # If current model is not source, get its dims
            if curr != source_model:
                m_def = self.indexer.get_model(curr)
                if m_def:
                    reachable[curr] = m_def.get('dimensions', [])
            
            # Find neighbors
            if curr in self.graph.adj:
                for edge in self.graph.adj[curr]:
                    target = edge['target']
                    if target not in seen:
                        seen.add(target)
                        queue.append(target)
                        
        return reachable
    
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



    def generate_sql(self, metric_name: str, dimensions: List[str] = [], filters: List[str] = [], dialect: str = "ansi", compare: str = None, window: str = None, optimize: bool = True) -> str:
        """
        Generates SQL for a given metric and context.
        Supports:
        - Defaults (dims, filters)
        - Metric Types: Aggregate, Ratio, Semi-Additive
        - Derived Metrics (Basic Expansion)
        - Time Intelligence (Compare, Window)
        """
        dimensions = dimensions or []
        filters = filters or []
        
        metric = self.indexer.get_metric(metric_name)
        if not metric:
            raise ValueError(f"Metric '{metric_name}' not found")
        
        # 1. Resolve effective grain
        entity = None
        entity_name = metric.get('entity_name')
        if entity_name:
            entity = self.indexer.get_entity(entity_name)
        
        effective_grain = self.get_effective_grain(metric, entity)
            
        # 2. Apply Defaults
        if not dimensions:
             # Try default_dimensions, then grain, then inference
             default_dims = metric.get('default_dimensions', [])
             if default_dims:
                 # Validate it's a list
                 dimensions = default_dims if isinstance(default_dims, list) else []
             elif effective_grain:
                 # Use effective grain as default dimensions
                 dimensions = effective_grain.copy()
        
        default_filter = metric.get('default_filter')
        if default_filter:
            filters.append(default_filter)
            
        # 3. Resolve Metric Expression
        # Handles Ratio and Derived (Inline Expansion)
        final_expr = self._resolve_expression(metric, dialect)
        metric_alias = metric_name
        
        source_model = metric.get('model')
        # Use model name as table if source_table is not set or is a CTE alias
        source_table = metric.get('source_table') or ''
        # If source_table looks like a CTE alias (common CTE names like 'final', 'base', etc.)
        # or if it's empty, use the model name as the table name
        cte_aliases = {'final', 'base', 'cte', 'intermediate', 'staged', 'prepared'}
        if not source_table or source_table.lower() in cte_aliases:
            source_table = source_model
        base_filters = metric.get('filters') or []
        
        # 3. Time Intelligence Prep
        time_dim = metric.get('time_dimension')
        if (compare or window) and not time_dim:
             # Try to find time dim in dimensions if not in metadata
             # Fallback
             pass
        
        # 4. Join Logic (Same as before)
        target_models = set()
        clean_dims = []
        
        # helper for basic sanitization (naive but better then nothing)
        def sanitize_ident(s: str):
            if not all(c.isalnum() or c in "_." for c in s):
                 # basic check to prevent obvious injection like "; DROP TABLE"
                 # In production, use sqlglot.exp.Identifier or similar to build robust AST
                 if not any(x in s for x in [";", "--", "/*"]):
                     return s # allow complex exprs if not obviously malicious
                 raise ValueError(f"Invalid identifier/expression: {s}")
            return s

        for dim in dimensions:
            sanitize_ident(dim)
            
            if "." in dim:
                model, col = dim.split(".", 1)
                target_models.add(model)
                clean_dims.append(f"{model}.{col}") 
            else:
                clean_dims.append(dim)
                
        for f in filters:
            # Filters are strings that come from _build_filter_strings
            # Additional validation: check for semicolon and other dangerous patterns
            if isinstance(f, str):
                if ";" in f or "--" in f or "/*" in f:
                    raise ValueError("Filters cannot contain SQL injection patterns (;, --, /*)")
            else:
                raise ValueError(f"Filter must be a string, got {type(f)}")
                
        joins = self._build_joins(source_model, target_models)

        # 5. Core Query Construction
        # GROUP BY
        # Must include grain dimensions even if not explicitly selected
        # Combine selected dimensions with effective grain
        grain_dims_clean = []
        for grain_dim in effective_grain:
            sanitize_ident(grain_dim)
            if "." in grain_dim:
                model, col = grain_dim.split(".", 1)
                grain_dims_clean.append(f"{model}.{col}")
            else:
                grain_dims_clean.append(grain_dim)
        
        # Filter out "unknown" from dimensions (it's a placeholder, not a real dimension)
        grain_dims_clean = [d for d in grain_dims_clean if d and d.lower() != "unknown"]
        clean_dims = [d for d in clean_dims if d and d.lower() != "unknown"]
        
        # Union of selected dimensions and grain dimensions for GROUP BY
        all_group_by_dims = list(set(clean_dims + grain_dims_clean))
        group_by_str = ", ".join(all_group_by_dims) if all_group_by_dims else ""
        
        # SELECT
        # Must include grain dimensions in SELECT if they're in GROUP BY but not in selected dimensions
        # This ensures SQL is valid (all GROUP BY columns must be in SELECT)
        select_dims = list(set(clean_dims + grain_dims_clean))
        select_cols = select_dims + [f"{final_expr} AS {metric_alias}"]
        
        # FROM
        # If source_table and source_model are the same, just use one
        if source_table == source_model or not source_table:
            from_str = source_model
        else:
            from_str = f"{source_table} AS {source_model}"
        
        # WHERE
        all_filters = base_filters + filters
        where_str = " AND ".join(all_filters) if all_filters else ""
        
        core_sql = f"SELECT\n  {', '.join(select_cols)}\nFROM {from_str}"
        if joins:
            core_sql += f"\n{joins}"
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
        
        # Hooks: Before Execute (actually before return of SQL string)
        from axi.plugins.registry import HOOKS_REGISTRY
        for hook in HOOKS_REGISTRY["before_execute"]:
             # Hook might mutate context or just log
             try:
                 hook({"metric": metric_name, "sql": final_sql})
             except Exception as e:
                 print(f"Hook error: {e}")

        return final_sql

    def _resolve_expression(self, metric: Dict, dialect: str) -> str:
        m_type = metric.get('metric_type', 'aggregate')
        expr = metric.get('expression', '')
        
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
