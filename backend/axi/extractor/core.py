# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import sqlglot
from sqlglot import exp
from typing import Dict, List, Any, Optional, Set
import warnings
import logging

import os
from pathlib import Path
from axi.config.loader import Config
from axi.utils.logging_config import get_logger

logger = get_logger(__name__)

# Suppress sqlglot warnings about unsupported dialect features
# Suppress noisy sqlglot warnings (e.g., ToChar format) that don't impact parsing
warnings.filterwarnings('ignore', category=UserWarning, module='sqlglot')
warnings.filterwarnings('ignore', message="Argument 'format' is not supported for expression 'ToChar'.*", category=UserWarning)

def extract_metadata(sql: str, model_name: str, config: Optional[Config] = None) -> Dict[str, Any]:
    # Honor debug flag early to avoid UnboundLocalError when logging later
    debug = os.environ.get("AXI_DEBUG", "").lower() == "true"
    logger.debug(f"Extracting metadata for model: {model_name}")
    
    # 0. auto-wrap SELECT if needed (simple heuristic)
    # Some dbt files might be "select * from x" without closing semicolon, which is fine
    # But if it's "x" (table name only for snapshot?), sqlglot might fail if dialact is strict
        
    try:
        # Try parsing with different dialects if default fails
        parsed = None
        # Try a few dialects in tolerant mode; default to Snowflake/Postgres first
        for dialect in ["snowflake", "postgres", None, "mysql", "sqlite"]:
            try:
                parsed = sqlglot.parse_one(sql, read=dialect, error_level="ignore")
                break
            except Exception:
                continue
        
        if not parsed:
            raise Exception("Failed to parse with any dialect")
            
        logger.debug(f"Successfully parsed SQL for model: {model_name}")
            
    except Exception as e:
         logger.error(f"Failed to parse SQL for model {model_name}: {e}")
         
         # Dump failing SQL for debugging
         if debug:
             debug_dir = Path("axi_debug_sql")
             debug_dir.mkdir(exist_ok=True)
             dump_path = debug_dir / f"{model_name}.sql"
             with open(dump_path, "w") as f:
                 f.write(sql)
             logger.debug(f"Saved failing SQL to {dump_path}")
         
         # Re-raise to fail the extraction for this model
         raise e
         
    metrics = []
    dimensions: List[str] = []
    filters = []
    source_tables = []
    relationships = []
    entity = {"name": model_name, "pk": None, "columns": []}

    keep_overrides = set(config.dimensions.keep) if config and config.dimensions else set()
    drop_overrides = set(config.dimensions.drop) if config and config.dimensions else set()
    
    # 1. Source Tables (FROM / JOIN) and Relationships
    alias_map = {}
    model_refs = []  # Track model references (from ref(), source(), etc.)
    cte_aliases: Set[str] = set()

    # Track CTE aliases to avoid emitting relationships against internal CTE names
    if isinstance(parsed, exp.Select) and parsed.ctes:
        for cte in parsed.ctes:
            alias = getattr(cte, "alias", None) or getattr(cte, "alias_or_name", None)
            if alias and isinstance(alias, str):
                cte_aliases.add(alias)
    
    # Identifies all source tables and aliases
    
    # 1. Scan Tables (Captures name->name AND Table(alias=...) cases)
    for tbl in parsed.find_all(exp.Table):
        name = tbl.name
        if name:
            alias_map[name] = name
            if name not in source_tables:
                source_tables.append(name)
            
            # If Table has internal alias property
            if tbl.alias_or_name != name:
                alias_map[tbl.alias_or_name] = name
    
    # 2. Scan Alias Nodes (Captures Alias(Table, ...) cases)
    for alias_node in parsed.find_all(exp.Alias):
        if isinstance(alias_node.this, exp.Table):
            tname = alias_node.this.name
            alias = alias_node.alias
            if alias:
                 alias_map[alias] = tname

    # 3. Extract relationships from CTEs (CTEs often reference other models)
    if isinstance(parsed, exp.Select) and parsed.ctes:
        for cte in parsed.ctes:
            if isinstance(cte.this, exp.Select):
                # Recursively extract relationships from CTE
                cte_tables = []
                for tbl in cte.this.find_all(exp.Table):
                    if tbl.name and tbl.name not in cte_tables:
                        cte_tables.append(tbl.name)
                # Create relationships: CTE references these tables
                for ref_table in cte_tables:
                    if ref_table in cte_aliases:
                        # Skip internal CTE names; we only want actual tables/views
                        continue
                    if ref_table != model_name and ref_table not in [r.get('child_model') for r in relationships]:
                        relationships.append({
                            "parent_model": ref_table,
                            "child_model": model_name,
                            "fk_column": "",
                            "pk_column": "",
                            "join_type": "DEPENDS_ON"
                        })

    # 4. Parse JOINs for relationships
    # We look for explicit JOIN ... ON ...
    # Now handles composite keys (multiple AND conditions)

    def extract_join_conditions(on_condition) -> List[tuple]:
        """
        Extract all equality conditions from a JOIN ON clause.
        Handles composite keys with AND conditions.
        Returns list of (left_table, left_col, right_table, right_col) tuples.
        """
        conditions = []

        if isinstance(on_condition, exp.EQ):
            # Simple equality: a.col = b.col
            left = on_condition.left
            right = on_condition.right
            if isinstance(left, exp.Column) and isinstance(right, exp.Column):
                conditions.append((left.table, left.name, right.table, right.name))

        elif isinstance(on_condition, exp.And):
            # Composite key: a.col1 = b.col1 AND a.col2 = b.col2
            # Recursively extract from left and right
            conditions.extend(extract_join_conditions(on_condition.left))
            conditions.extend(extract_join_conditions(on_condition.right))

        elif isinstance(on_condition, exp.Paren):
            # Parenthesized expression
            conditions.extend(extract_join_conditions(on_condition.this))

        return conditions

    for join in parsed.find_all(exp.Join):
        # Join target table (Parent Candidate)
        if isinstance(join.this, exp.Table):
            joined_table = join.this.name

            # Extract ON condition
            on_condition = join.args.get("on")
            if on_condition:
                join_conditions = extract_join_conditions(on_condition)

                # Process each condition
                fk_columns = []
                pk_columns = []
                parent_model = None
                child_model = None

                for left_table, left_col, right_table, right_col in join_conditions:
                    # Resolve real table names
                    l_tab_real = alias_map.get(left_table, left_table) if left_table else model_name
                    r_tab_real = alias_map.get(right_table, right_table) if right_table else model_name

                    # Identify Parent vs Child
                    # If joined_table matches one side, that side is Parent side.
                    if l_tab_real == joined_table:
                        if parent_model is None:
                            parent_model = joined_table
                            child_model = r_tab_real
                        pk_columns.append(left_col)
                        fk_columns.append(right_col)
                    elif r_tab_real == joined_table:
                        if parent_model is None:
                            parent_model = joined_table
                            child_model = l_tab_real
                        pk_columns.append(right_col)
                        fk_columns.append(left_col)

                if parent_model and child_model and parent_model != child_model:
                    # For composite keys, store as comma-separated
                    fk_col = ",".join(fk_columns) if fk_columns else ""
                    pk_col = ",".join(pk_columns) if pk_columns else ""

                    # Check if relationship already exists
                    existing = any(
                        r.get("parent_model") == parent_model and
                        r.get("child_model") == child_model
                        for r in relationships
                    )
                    if not existing:
                        relationships.append({
                            "parent_model": parent_model,
                            "child_model": child_model,
                            "fk_column": fk_col,
                            "pk_column": pk_col,
                            "join_type": join.kind if join.kind else "INNER"
                        })
                        # Also relate the joined table to the current model
                        model_edge_exists = any(
                            r.get("parent_model") == parent_model and
                            r.get("child_model") == model_name
                            for r in relationships
                        )
                        if not model_edge_exists and fk_col and pk_col:
                            relationships.append({
                                "parent_model": parent_model,
                                "child_model": model_name,
                                "fk_column": fk_col,
                                "pk_column": pk_col,
                                "join_type": join.kind if join.kind else "INNER"
                            })

    # 5. Infer FK relationships from column naming conventions
    # This helps when JOINs don't have explicit ON conditions or are implicit
    def infer_fk_from_column_name(col_name: str, source_tables_set: set) -> Optional[tuple]:
        """
        Infer FK relationship from column naming conventions.
        E.g., customer_id -> customers table, user_id -> users table
        Returns (target_table, target_column) or None
        """
        col_lower = col_name.lower()
        if not col_lower.endswith('_id') or col_lower == 'id':
            return None

        base_name = col_lower[:-3]  # Remove '_id'

        # Try common plural/singular variations
        candidates = [
            base_name + 's',      # customer -> customers
            base_name + 'es',     # box -> boxes
            base_name,            # customer -> customer
        ]
        if base_name.endswith('s'):
            candidates.append(base_name[:-1])  # customers -> customer

        for candidate in candidates:
            for table in source_tables_set:
                if table.lower() == candidate:
                    return (table, 'id')

        return None

    # Extract relationships from FROM clauses (model dependencies)
    # If a model references another model in FROM, create a dependency relationship
    for from_clause in parsed.find_all(exp.From):
        if isinstance(from_clause.this, exp.Table):
            ref_table = from_clause.this.name
            if ref_table and ref_table not in cte_aliases and ref_table != model_name and ref_table not in ["unknown", ""]:
                # Check if relationship already exists
                existing = any(
                    r.get("parent_model") == ref_table and 
                    r.get("child_model") == model_name
                    for r in relationships
                )
                if not existing:
                    relationships.append({
                        "parent_model": ref_table,
                        "child_model": model_name,
                        "fk_column": "",
                        "pk_column": "",
                        "join_type": "DEPENDS_ON"
                    })

    # 2. Filters (WHERE)
    where = parsed.find(exp.Where)
    if where:
        filters.append(where.this.sql())

    # Handle CTEs: Get the main SELECT (outermost one, not CTE inner SELECTs)
    # sqlglot parses CTEs correctly - the parsed object IS the main SELECT with CTEs
    main_select = parsed
    if not isinstance(parsed, exp.Select):
        if hasattr(parsed, 'find'):
            main_select = parsed.find(exp.Select)
            if not main_select:
                main_select = parsed

    # Get all columns from the SELECT list to infer FK relationships
    if isinstance(main_select, exp.Select):
        source_tables_set = set(source_tables)
        for column in main_select.find_all(exp.Column):
            col_name = column.name
            col_table = column.table
            if col_name:
                fk_info = infer_fk_from_column_name(col_name, source_tables_set)
                if fk_info:
                    target_table, target_col = fk_info
                    # Determine the source model (the model containing the FK column)
                    source_model = alias_map.get(col_table, col_table) if col_table else model_name

                    if source_model and target_table and source_model != target_table:
                        # Check if relationship already exists
                        existing = any(
                            r.get("parent_model") == target_table and
                            r.get("child_model") == source_model and
                            r.get("fk_column") == col_name
                            for r in relationships
                        )
                        if not existing:
                            relationships.append({
                                "parent_model": target_table,
                                "child_model": source_model,
                                "fk_column": col_name,
                                "pk_column": target_col,
                                "join_type": "INFERRED_FK"
                            })

    # Track metric names globally to avoid adding them as dimensions
    # Must be defined before functions that use it
    metric_names_global = set()
    
    def extract_column_name_from_expression(expr) -> str:
        """Extract column name from an expression, handling Column, Alias, etc."""
        if isinstance(expr, exp.Column):
            return expr.alias_or_name or expr.sql()
        elif isinstance(expr, exp.Alias):
            # For aliases, get the underlying column name if it's a Column
            if isinstance(expr.this, exp.Column):
                return expr.this.alias_or_name or expr.this.sql()
            # Otherwise use the alias
            return expr.alias_or_name or expr.sql()
        elif isinstance(expr, exp.Identifier):
            return expr.this or expr.sql()
        elif isinstance(expr, exp.DateTrunc):
            # For DATE_TRUNC, extract the column being truncated
            if expr.expressions:
                first_expr = expr.expressions[0]
                if isinstance(first_expr, exp.Column):
                    return first_expr.alias_or_name or first_expr.sql()
                elif isinstance(first_expr, exp.Identifier):
                    return first_expr.this or first_expr.sql()
            # Fallback to SQL representation
            return expr.sql()
        else:
            # For complex expressions, try to find a Column inside
            columns = list(expr.find_all(exp.Column)) if hasattr(expr, 'find_all') else []
            if columns:
                # Use the first column found
                return columns[0].alias_or_name or columns[0].sql()
            # Last resort: SQL representation
            return expr.sql()
    
    def is_simple_column_reference(expr) -> bool:
        """Check if expression is a simple column reference (not a function call, literal, etc.)"""
        if isinstance(expr, exp.Column):
            return True
        elif isinstance(expr, exp.Alias):
            return is_simple_column_reference(expr.this)
        elif isinstance(expr, exp.Identifier):
            return True
        # Exclude function calls, literals, casts, etc.
        elif isinstance(expr, (exp.Literal, exp.Cast)):
            return False
        # Check for function calls - sqlglot uses various function types
        elif hasattr(expr, 'expressions') and len(expr.expressions) > 0:
            # If it has expressions, it might be a function call
            # Check if it's a simple column by looking for function-like patterns
            if hasattr(expr, 'sql'):
                sql_str = expr.sql()
                # Simple heuristic: if it contains parentheses and isn't just a column, it's likely a function
                if '(' in sql_str and not isinstance(expr, exp.Column):
                    return False
        # For other types, check if it contains functions or literals
        try:
            functions = list(expr.find_all(exp.Literal)) if hasattr(expr, 'find_all') else []
            # If it's just a column reference without functions/literals, it's simple
            return len(functions) == 0 or isinstance(expr, exp.Column)
        except:
            # If we can't determine, assume it's not simple to be safe
            return False
    
    def is_constant_or_literal(expr) -> bool:
        """Check if expression is a constant or literal value"""
        if isinstance(expr, exp.Literal):
            return True
        elif isinstance(expr, exp.Alias):
            return is_constant_or_literal(expr.this)
        # Check for string literals (StringLiteral), numeric literals
        # sqlglot uses Literal for both strings and numbers
        return isinstance(expr, exp.Literal)

    # Helpers for extraction in the new grain-first pipeline
    def extract_column_name_from_expression(expr) -> str:
        """Extract column name from an expression, handling Column, Alias, etc."""
        if isinstance(expr, exp.Column):
            return expr.alias_or_name or expr.sql()
        elif isinstance(expr, exp.Alias):
            if isinstance(expr.this, exp.Column):
                return expr.this.alias_or_name or expr.this.sql()
            return expr.alias_or_name or expr.sql()
        elif isinstance(expr, exp.Identifier):
            return expr.this or expr.sql()
        elif isinstance(expr, exp.DateTrunc):
            if expr.expressions:
                first_expr = expr.expressions[0]
                if isinstance(first_expr, exp.Column):
                    return first_expr.alias_or_name or first_expr.sql()
                elif isinstance(first_expr, exp.Identifier):
                    return first_expr.this or first_expr.sql()
            return expr.sql()
        else:
            columns = list(expr.find_all(exp.Column)) if hasattr(expr, 'find_all') else []
            if columns:
                return columns[0].alias_or_name or columns[0].sql()
            return expr.sql()

    def is_constant_or_literal(expr) -> bool:
        if isinstance(expr, exp.Literal):
            return True
        if isinstance(expr, exp.Alias):
            return is_constant_or_literal(expr.this)
        return False

    # Build CTE map for dependency resolution
    cte_map: Dict[str, exp.Select] = {}
    if isinstance(main_select, exp.Select) and main_select.ctes:
        for cte in main_select.ctes:
            if isinstance(cte.this, exp.Select):
                cte_map[cte.alias] = cte.this

    def _select_sources(select_stmt: exp.Select) -> List[exp.Expression]:
        sources: List[exp.Expression] = []
        if not isinstance(select_stmt, exp.Select):
            return sources
        from_clause = select_stmt.args.get("from") or select_stmt.args.get("from_")
        if from_clause and getattr(from_clause, "this", None):
            sources.append(from_clause.this)
        for join in select_stmt.args.get("joins") or []:
            if getattr(join, "this", None):
                sources.append(join.this)
        return sources

    def _source_kind(expr_node: exp.Expression) -> str:
        if isinstance(expr_node, exp.Table):
            if expr_node.name in cte_map:
                return "cte"
            return "table"
        if isinstance(expr_node, exp.Subquery):
            return "subquery"
        if isinstance(expr_node, exp.Select):
            return "subquery"
        return "unknown"

    def _has_group_or_distinct(select_stmt: exp.Select) -> bool:
        if not isinstance(select_stmt, exp.Select):
            return False
        if select_stmt.args.get("group"):
            return True
        if select_stmt.args.get("distinct"):
            return True
        # Check for aggregates in this select only (not inside subqueries or CTEs)
        def _has_aggregate_excluding_subqueries(node) -> bool:
            """Walk tree looking for aggregates, but don't descend into subqueries."""
            if isinstance(node, (exp.Subquery, exp.Select)):
                # Don't descend into subqueries - aggregates there don't affect outer grain
                return False
            if isinstance(node, (exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)):
                return True
            # Check children
            for child in node.iter_expressions():
                if _has_aggregate_excluding_subqueries(child):
                    return True
            return False

        for expr in select_stmt.expressions or []:
            if _has_aggregate_excluding_subqueries(expr):
                return True
        return False

    def _find_grouped_cte_recursive(cte_name: str, visited: Set[str]) -> Optional[str]:
        """
        Recursively walk CTE chain to find the first CTE with GROUP BY or DISTINCT.
        Returns the CTE name if found, None otherwise.
        """
        if cte_name in visited or cte_name not in cte_map:
            return None
        visited.add(cte_name)

        cte_select = cte_map[cte_name]
        if _has_group_or_distinct(cte_select):
            return cte_name

        # Walk through sources of this CTE
        sources = _select_sources(cte_select)
        for src in sources:
            if isinstance(src, exp.Table) and src.name in cte_map:
                result = _find_grouped_cte_recursive(src.name, visited)
                if result:
                    return result
        return None

    # Decide semantic-producing node
    semantic_select = main_select
    semantic_node = model_name
    grain_scope = "outer"
    grain_reasons: List[str] = []

    main_sources = _select_sources(main_select) if isinstance(main_select, exp.Select) else []
    main_has_grouping = _has_group_or_distinct(main_select)
    cte_refs_in_main = set()
    for src in main_sources:
        if isinstance(src, exp.Table) and src.name in cte_map:
            cte_refs_in_main.add(src.name)

    if not main_has_grouping and main_sources:
        kinds = [_source_kind(src) for src in main_sources]
        if len(main_sources) == 1 and kinds[0] == "cte" and isinstance(main_sources[0], exp.Table):
            cte_name = main_sources[0].name
            if cte_name in cte_map:
                semantic_select = cte_map[cte_name]
                semantic_node = cte_name
                grain_scope = "cte"
        elif len(cte_refs_in_main) > 1 or (len(main_sources) > 1 and all(k in ("cte", "subquery") for k in kinds)):
            # Multiple semantic-producing inputs with no aggregation: ambiguous
            grain_reasons.append("multiple semantic-producing sources detected")
            return {
                "model": model_name,
                "metrics": [],
                "dimensions": [],
                "dimension_details": [],
                "filters": filters,
                "source_tables": source_tables,
                "entity": entity,
                "relationships": relationships,
                "grain_status": "ambiguous",
                "grain_detection": "none",
                "grain_columns": [],
                "semantic_intent": "aggregation_like",
                "semantic_node": "unknown",
                "grain_scope": "cte",
                "grain_reasons": grain_reasons,
            }

    # If the semantic_select is still pass-through (no group/distinct) and points to a single CTE source,
    # walk down one hop to find the first grouped/distinct CTE (common in dbt compiled SQL).
    visited = set()
    while isinstance(semantic_select, exp.Select) and not _has_group_or_distinct(semantic_select):
        sources = _select_sources(semantic_select)
        if len(sources) != 1 or not isinstance(sources[0], exp.Table):
            break
        next_name = sources[0].name
        if not next_name or next_name in visited or next_name not in cte_map:
            break
        visited.add(next_name)
        semantic_select = cte_map[next_name]
        semantic_node = next_name
        grain_scope = "cte"

    # If still no grouping, but the select joins a grouped/distinct CTE plus dimension tables, pick that grouped CTE.
    # Use recursive search to find grouped CTEs even through intermediate pass-through CTEs.
    if isinstance(semantic_select, exp.Select) and not _has_group_or_distinct(semantic_select):
        sources = _select_sources(semantic_select)
        grouped_ctes = []
        for src in sources:
            if isinstance(src, exp.Table) and src.name in cte_map:
                # Recursively find the grouped CTE in the chain
                grouped_cte_name = _find_grouped_cte_recursive(src.name, set())
                if grouped_cte_name:
                    grouped_ctes.append(grouped_cte_name)
        # Deduplicate in case multiple paths lead to the same CTE
        grouped_ctes = list(dict.fromkeys(grouped_ctes))
        if len(grouped_ctes) == 1:
            semantic_select = cte_map[grouped_ctes[0]]
            semantic_node = grouped_ctes[0]
            grain_scope = "cte"
        elif len(grouped_ctes) > 1:
            grain_reasons.append("multiple grouped CTE sources detected without regrouping")
            return {
                "model": model_name,
                "metrics": [],
                "dimensions": [],
                "dimension_details": [],
                "filters": filters,
                "source_tables": source_tables,
                "entity": entity,
                "relationships": relationships,
                "grain_status": "ambiguous",
                "grain_detection": "none",
                "grain_columns": [],
                "semantic_intent": "aggregation_like",
                "semantic_node": "unknown",
                "grain_scope": "cte",
                "grain_reasons": grain_reasons,
            }

    # Grain-first detection on semantic-producing select
    group_by_cols: List[str] = []
    distinct_cols: List[str] = []
    if isinstance(semantic_select, exp.Select):
        group = semantic_select.find(exp.Group)
        if group:
            for expression in group.expressions:
                dim_name = extract_column_name_from_expression(expression)
                if dim_name:
                    group_by_cols.append(dim_name)
        if semantic_select.args.get("distinct"):
            for expression in semantic_select.expressions:
                if is_constant_or_literal(expression):
                    continue
                dim_name = extract_column_name_from_expression(expression)
                if dim_name:
                    distinct_cols.append(dim_name)

    group_by_cols = list(dict.fromkeys(group_by_cols))
    distinct_cols = list(dict.fromkeys(distinct_cols))

    aggregates_present = _has_group_or_distinct(semantic_select)

    grain_detection = "none"
    grain_columns: List[str] = []
    if group_by_cols:
        grain_detection = "group_by"
        grain_columns = group_by_cols
    elif distinct_cols:
        grain_detection = "distinct"
        grain_columns = distinct_cols

    fanout_risk = any(
        rel.get("parent_model") == model_name and rel.get("fk_column")
        for rel in relationships
    )

    grain_status = "not_detected"
    if grain_columns:
        grain_status = "unsafe" if fanout_risk else "clear"
        if fanout_risk:
            grain_reasons.append("fan-out risk from joins")
    elif main_sources and len(main_sources) > 1 and any(_source_kind(s) in ("cte", "subquery") for s in main_sources):
        grain_status = "ambiguous"
        grain_reasons.append("multiple sources without aggregation")

    semantic_intent = "raw_like"
    if grain_status == "clear":
        semantic_intent = "semantic_candidate"
    elif grain_detection in ("group_by", "distinct") or aggregates_present:
        semantic_intent = "aggregation_like"

    # Dimensions: only grain columns when grain is clear
    dimension_details = []
    if grain_columns:
        for col in grain_columns:
            included = grain_status == "clear" and col not in drop_overrides
            reason = "group_by" if grain_detection == "group_by" else "distinct"
            if col in drop_overrides:
                included = False
                reason = "drop_override"
            elif col in keep_overrides:
                included = True
                reason = "user_keep"
            elif grain_status != "clear":
                included = False
                reason = "grain_unsafe"
            if included:
                dimensions.append(col)
            dimension_details.append({
                "name": col,
                "included": included,
                "reason": reason,
                "roles": ["grain"]
            })
    else:
        # Explicitly record the absence of dimensions for transparency
        dimension_details.append({
            "name": None,
            "included": False,
            "reason": "no_grouping_detected",
            "roles": []
        })

    # Metrics: only when grain is clear
    metric_names_global: Set[str] = set()
    metric_ref_columns: Set[str] = set()

    def extract_metrics_from_select(select_stmt: exp.Select):
        if grain_status != "clear":
            return
        if not isinstance(select_stmt, exp.Select):
            return
        for i, expression in enumerate(select_stmt.expressions):
            m_name = expression.alias_or_name or f"metric_{i}"
            m_expr_node = expression.this if isinstance(expression, exp.Alias) else expression
            m_expr = m_expr_node.sql()

            for col_ref in m_expr_node.find_all(exp.Column):
                col_name = col_ref.alias_or_name or col_ref.sql()
                if col_name:
                    metric_ref_columns.add(col_name)

            aggregations = list(m_expr_node.find_all((exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)))
            m_type = "aggregate"
            numerator = ""
            denominator = ""

            if "/" in m_expr or "DIV" in m_expr.upper():
                m_type = "ratio"
                if "/" in m_expr:
                    parts = m_expr.split("/")
                    if len(parts) == 2:
                        numerator = parts[0].strip()
                        denominator = parts[1].strip()

            agg_type = "custom"
            if aggregations:
                first_agg = aggregations[0]
                if isinstance(first_agg, exp.Sum): agg_type = "sum"
                elif isinstance(first_agg, exp.Count): agg_type = "count"
                elif isinstance(first_agg, exp.Avg): agg_type = "avg"
                elif isinstance(first_agg, exp.Min): agg_type = "min"
                elif isinstance(first_agg, exp.Max): agg_type = "max"
            elif isinstance(m_expr_node, exp.Sum): agg_type = "sum"
            elif isinstance(m_expr_node, exp.Count): agg_type = "count"
            elif isinstance(m_expr_node, exp.Avg): agg_type = "avg"
            elif isinstance(m_expr_node, exp.Min): agg_type = "min"
            elif isinstance(m_expr_node, exp.Max): agg_type = "max"

            if (m_type == "ratio" and aggregations) or agg_type != "custom":
                if any(m.get("name") == m_name for m in metrics):
                    continue
                metric_names_global.add(m_name)
                metrics.append({
                    "name": m_name,
                    "expression": m_expr,
                    "model": model_name,
                    "source_table": model_name,
                    "grain": grain_columns,
                    "metric_type": m_type,
                    "aggregation": agg_type,
                    "default_dimensions": [],
                    "default_filter": "",
                    "time_dimension": "",
                    "depends_on": [],
                    "numerator": numerator,
                    "denominator": denominator,
                    "semi_additive_method": "",
                    "semi_additive_dimension": "",
                    "tags": [],
                    "description": ""
                })

    if isinstance(main_select, exp.Select):
        if main_select.ctes:
            for cte in main_select.ctes:
                if isinstance(cte.this, exp.Select):
                    extract_metrics_from_select(cte.this)
        extract_metrics_from_select(main_select)

    # Entity pk: only accept single-column clear grain
    if grain_status == "clear" and len(grain_columns) == 1:
        entity["pk"] = grain_columns[0]

    return {
        "model": model_name,
        "metrics": metrics,
        "dimensions": dimensions,
        "dimension_details": dimension_details,
        "filters": filters,
        "source_tables": source_tables,
        "entity": entity,
        "relationships": relationships,
        "grain_status": grain_status,
        "grain_detection": grain_detection,
        "grain_columns": grain_columns,
        "semantic_intent": semantic_intent,
        "semantic_node": semantic_node,
        "grain_scope": grain_scope,
        "grain_reasons": grain_reasons
    }
