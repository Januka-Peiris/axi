# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import sqlglot
from sqlglot import exp
from typing import Dict, List, Any, Optional, Set
import warnings

import os
from pathlib import Path
from axi.config.loader import Config

# Suppress sqlglot warnings about unsupported dialect features
warnings.filterwarnings('ignore', category=UserWarning, module='sqlglot')

def extract_metadata(sql: str, model_name: str, config: Optional[Config] = None) -> Dict[str, Any]:
    debug = os.environ.get("AXI_DEBUG") == "true"
    
    # 0. auto-wrap SELECT if needed (simple heuristic)
    # Some dbt files might be "select * from x" without closing semicolon, which is fine
    # But if it's "x" (table name only for snapshot?), sqlglot might fail if dialact is strict
    
    if debug:
        print(f"[DEBUG] Attempting sqlglot parse... Model: {model_name}")
        
    try:
        # Try parsing with different dialects if default fails
        parsed = None
        for dialect in [None, "snowflake", "postgres", "mysql", "sqlite"]:
            try:
                if dialect:
                    parsed = sqlglot.parse_one(sql, dialect=dialect)
                else:
                    parsed = sqlglot.parse_one(sql)
                break
            except Exception:
                continue
        
        if not parsed:
            raise Exception("Failed to parse with any dialect")
            
        if debug:
            print(f"[DEBUG] sqlglot parse SUCCESS: {model_name}")
            
    except Exception as e:
         print(f"[ERROR] sqlglot failed to parse {model_name}: {e}")
         
         # Dump failing SQL
         if debug:
             debug_dir = Path("axi_debug_sql")
             debug_dir.mkdir(exist_ok=True)
             dump_path = debug_dir / f"{model_name}.sql"
             with open(dump_path, "w") as f:
                 f.write(sql)
             print(f"[DEBUG] Saved failing SQL to {dump_path}")
         
         # Re-raise to fail the extraction for this model
         raise e
         
    metrics = []
    dimensions: List[str] = []
    filters = []
    source_tables = []
    grain = "unknown"
    relationships = []
    entity = {"name": model_name, "pk": None, "columns": []}

    # Dimension candidates with roles
    dim_roles: Dict[str, Set[str]] = {}
    dim_reasons: Dict[str, str] = {}
    metric_ref_columns: Set[str] = set()
    keep_overrides = set(config.dimensions.keep) if config and config.dimensions else set()
    drop_overrides = set(config.dimensions.drop) if config and config.dimensions else set()

    def _add_role(name: str, role: str, reason_hint: Optional[str] = None):
        if not name:
            return
        if name not in dim_roles:
            dim_roles[name] = set()
        dim_roles[name].add(role)
        if reason_hint:
            dim_reasons[name] = reason_hint
    
    # 1. Source Tables (FROM / JOIN) and Relationships
    alias_map = {}
    model_refs = []  # Track model references (from ref(), source(), etc.)
    
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
    for join in parsed.find_all(exp.Join):
        # Join target table (Parent Candidate)
        if isinstance(join.this, exp.Table):
            joined_table = join.this.name
            
            # Extract ON condition
            on_condition = join.args.get("on")
            if on_condition:
                if isinstance(on_condition, exp.EQ):
                    left = on_condition.left
                    right = on_condition.right
                    
                    if isinstance(left, exp.Column) and isinstance(right, exp.Column):
                      left_table = left.table
                      left_col = left.name
                      right_table = right.table
                      right_col = right.name
                      
                      # Resolve real table names
                      # If table is empty, assume local table or handled elsewhere? 
                      # Usually `col` vs `tab.col`. If `col` -> assume local?
                      
                      # DEBUG
                      
                      l_tab_real = alias_map.get(left_table, left_table) if left_table else model_name
                      r_tab_real = alias_map.get(right_table, right_table) if right_table else model_name
                      
                      # Identify Parent vs Child
                      # If joined_table matches one side, that side is Parent side.
                      # Ideally joined_table (table name) matches l_tab_real or r_tab_real
                      
                      parent_model = "unknown"
                      child_model = "unknown"
                      pk_col = "unknown"
                      fk_col = "unknown"
  
                      if l_tab_real == joined_table:
                          parent_model = joined_table
                          pk_col = left_col
                          
                          child_model = r_tab_real
                          fk_col = right_col
                      elif r_tab_real == joined_table:
                          parent_model = joined_table
                          pk_col = right_col
                          
                          child_model = l_tab_real
                          fk_col = left_col
                      
                      if parent_model != "unknown" and parent_model != child_model:
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
                               if fk_col:
                                   _add_role(fk_col, "join_key", "join_key")
                               if pk_col:
                                   _add_role(pk_col, "join_key", "join_key")
    
    # Extract relationships from FROM clauses (model dependencies)
    # If a model references another model in FROM, create a dependency relationship
    for from_clause in parsed.find_all(exp.From):
        if isinstance(from_clause.this, exp.Table):
            ref_table = from_clause.this.name
            if ref_table and ref_table != model_name and ref_table not in ["unknown", ""]:
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
        # If parsed is not a Select, try to find one
        if hasattr(parsed, 'find'):
            main_select = parsed.find(exp.Select)
            if not main_select:
                main_select = parsed

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

    # 3. Dimensions Extraction (Priority Order)
    # Priority 1: GROUP BY expressions (highest confidence - these ARE the grain)
    def extract_dimensions_from_group_by(select_stmt: exp.Select):
        """Extract dimensions from GROUP BY clause - highest priority"""
        if not isinstance(select_stmt, exp.Select):
            return
        
        group = select_stmt.find(exp.Group)
        if group:
            for expression in group.expressions:
                dim_name = extract_column_name_from_expression(expression)
                if dim_name:
                    _add_role(dim_name, "group_by", "group_by")
                
                # Check for DATE_TRUNC to infer grain
                if isinstance(expression, exp.DateTrunc):
                    try:
                        unit_arg = expression.args.get('unit')
                        if unit_arg and isinstance(unit_arg, exp.Literal):
                            grain = unit_arg.this.lower() 
                        elif expression.expressions and isinstance(expression.expressions[0], exp.Literal):
                             grain = expression.expressions[0].this.lower()
                    except:
                        pass
    
    # Priority 2: WHERE clause column references (filterable dimensions)
    def extract_dimensions_from_where(select_stmt: exp.Select):
        """Extract column references from WHERE clause - medium priority"""
        if not isinstance(select_stmt, exp.Select):
            return
        
        where_clause = select_stmt.find(exp.Where)
        if where_clause:
            columns = where_clause.find_all(exp.Column)
            for col in columns:
                dim_name = col.alias_or_name or col.sql()
                if dim_name:
                    _add_role(dim_name, "where_filter", "where_filter")
    
    # Priority 3: Non-aggregate SELECT columns (filtered)
    def extract_dimensions_from_select(select_stmt: exp.Select, group_by_cols: set):
        """Extract dimensions from non-aggregate SELECT columns - lowest priority
        
        Args:
            select_stmt: The SELECT statement to process
            group_by_cols: Set of column names already in GROUP BY (to avoid duplicates)
        """
        if not isinstance(select_stmt, exp.Select):
            return
        
        for expression in select_stmt.expressions:
            alias = expression.alias_or_name
            if alias:
                entity["columns"].append(alias)
                
            # Infer PK from naming convention 'id' or explicit alias 'id'
            if alias and alias.lower() == 'id':
                entity["pk"] = alias
            elif alias and alias.lower() == f"{model_name}_id":
                 entity["pk"] = alias
            
            # Get the underlying expression node
            expr_node = expression.this if isinstance(expression, exp.Alias) else expression
            
            # Skip if it's a metric (has aggregations or is a known metric name)
            aggregations = list(expr_node.find_all((exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)))
            if aggregations or (alias and alias in metric_names_global):
                continue
            
            # Skip '*' (star) expressions
            if isinstance(expr_node, exp.Star):
                continue
            
            # Skip constants/literals
            if is_constant_or_literal(expr_node):
                continue
            
            # Only include simple column references (not complex expressions)
            if not is_simple_column_reference(expr_node):
                continue
            
            # Get dimension name - prefer alias, fallback to column name
            dim_name = alias or extract_column_name_from_expression(expr_node)
            
            # Normalize: check if the underlying column (without alias) is already in group_by_cols
            underlying_col = extract_column_name_from_expression(expr_node)
            if underlying_col in group_by_cols:
                continue
            
            if dim_name and dim_name != '*' and dim_name not in metric_names_global:
                _add_role(dim_name, "select_only", "select_only")
    
    # 4. Metrics (Aggregates) - Extract FIRST so we can exclude them from dimensions
    # Extract metrics from CTEs first (where most aggregations happen)
    # Then extract from main SELECT
    def extract_metrics_from_select(select_stmt: exp.Select, cte_name: str = None):
        """Helper function to extract metrics from a SELECT statement (CTE or main)"""
        if not isinstance(select_stmt, exp.Select):
            return
        
        for i, expression in enumerate(select_stmt.expressions):
            alias = expression.alias_or_name
            if not alias:
                alias = f"metric_{i}" 
            
            # Use expression as exp_obj for consistency with the provided snippet
            exp_obj = expression

            # Get alias and real expression
            m_name = exp_obj.alias_or_name
            if not m_name:
                m_name = f"metric_{i}" # Fallback if no alias

            # The expression itself, unaliased if it was an alias
            m_expr_node = exp_obj.this if isinstance(exp_obj, exp.Alias) else exp_obj
            m_expr = m_expr_node.sql()

            # Track columns referenced inside metric expression so they are not pruned
            for col_ref in m_expr_node.find_all(exp.Column):
                col_name = col_ref.alias_or_name or col_ref.sql()
                if col_name:
                    metric_ref_columns.add(col_name)
            
            # Find aggregations recursively in the expression (handles nested cases)
            aggregations = list(m_expr_node.find_all((exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)))
            
            # Inference: Metric Type
            m_type = "aggregate"
            numerator = ""
            denominator = ""
            
            if "/" in m_expr or "DIV" in m_expr.upper():
                m_type = "ratio"
                # Naive split for demo
                if "/" in m_expr:
                    parts = m_expr.split("/")
                    if len(parts) == 2:
                        numerator = parts[0].strip()
                        denominator = parts[1].strip()
            
            # Inference: Time Dimension
            # Scan dimensions for date-like things
            time_dim = ""
            for d in dimensions:
                if "date" in d.lower() or "time" in d.lower() or "month" in d.lower() or "year" in d.lower():
                    time_dim = d
                    break
            
            # Inference: Aggregation from sqlglot
            # Check if expression itself is an aggregation OR contains aggregations
            agg_type = "custom"
            if aggregations:
                # Use the first aggregation found to determine type
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
            
            # Only add as a metric if it's an aggregate or ratio
            if m_type == "ratio" or agg_type != "custom":
                # Check if metric already exists (avoid duplicates)
                metric_exists = any(m.get("name") == m_name for m in metrics)
                if not metric_exists:
                    metric_names_global.add(m_name)  # Track metric name
                    # Determine source table - use model name, not CTE alias
                    # CTEs are intermediate results, the actual table is the model itself
                    source_table = model_name  # Use the actual model name, not CTE alias
                    metrics.append({
                        "name": m_name,
                        "expression": m_expr,
                        "model": model_name,  # Ensure model is set
                        "source_table": source_table,  # Set to model name, not CTE alias
                        "grain": grain,
                        "metric_type": m_type,
                        "aggregation": agg_type,
                        "default_dimensions": [], # Configurable manually ideally
                        "default_filter": "",
                        "time_dimension": time_dim,
                        "depends_on": [], # Logic for derived metrics needing AST analysis
                        "numerator": numerator,
                        "denominator": denominator,
                        "semi_additive_method": "",
                        "semi_additive_dimension": "",
                        "tags": [],
                        "description": ""
                    })
    
    # Extract metrics FIRST (before dimensions) so we can exclude them
    if isinstance(main_select, exp.Select):
        # Extract from CTEs first (where aggregations typically happen)
        if main_select.ctes:
            for cte in main_select.ctes:
                if isinstance(cte.this, exp.Select):
                    extract_metrics_from_select(cte.this, cte.alias)
        
        # Also extract metrics from main SELECT (in case there are aggregations there too)
        extract_metrics_from_select(main_select)
    
    # 3. Dimensions Extraction (Priority Order) - AFTER metrics so we can exclude them
    # Extract dimensions from all SELECT statements (main + CTEs)
    # First pass: Extract GROUP BY columns from all SELECTs
    group_by_cols = set()
    if isinstance(main_select, exp.Select):
        extract_dimensions_from_group_by(main_select)
        # Collect GROUP BY column names for filtering SELECT columns
        group = main_select.find(exp.Group)
        if group:
            for expr in group.expressions:
                col_name = extract_column_name_from_expression(expr)
                if col_name:
                    group_by_cols.add(col_name)
        
        # Also check CTEs
        if main_select.ctes:
            for cte in main_select.ctes:
                if isinstance(cte.this, exp.Select):
                    extract_dimensions_from_group_by(cte.this)
                    group = cte.this.find(exp.Group)
                    if group:
                        for expr in group.expressions:
                            col_name = extract_column_name_from_expression(expr)
                            if col_name:
                                group_by_cols.add(col_name)
    
    # Second pass: Extract WHERE clause columns
    if isinstance(main_select, exp.Select):
        extract_dimensions_from_where(main_select)
        if main_select.ctes:
            for cte in main_select.ctes:
                if isinstance(cte.this, exp.Select):
                    extract_dimensions_from_where(cte.this)
    
    # Third pass: Extract from SELECT columns (filtered)
    if isinstance(main_select, exp.Select):
        extract_dimensions_from_select(main_select, group_by_cols)
        if main_select.ctes:
            for cte in main_select.ctes:
                if isinstance(cte.this, exp.Select):
                    extract_dimensions_from_select(cte.this, group_by_cols)

    # Add metric reference roles after metric parsing
    for col in metric_ref_columns:
        _add_role(col, "metric_ref", "metric_ref")

    # Mark grain (entity pk) if available
    if entity.get("pk"):
        _add_role(entity["pk"], "grain", "grain")

    # Apply user keep/drop overrides to candidate list
    for keep_dim in keep_overrides:
        _add_role(keep_dim, "user_keep", "user_keep")
    # Drop overrides handled in pruning step

    dimension_details = []
    for dim_name, roles in dim_roles.items():
        roles_set = set(roles)
        included = False
        reason = "pruned"

        if dim_name in drop_overrides:
            included = False
            reason = "drop_override"
        elif dim_name in keep_overrides:
            included = True
            roles_set.add("user_keep")
            reason = "user_keep"
        elif "group_by" in roles_set:
            included = True
            reason = "group_by"
        elif "where_filter" in roles_set:
            included = True
            reason = "where_filter"
        elif "join_key" in roles_set:
            included = True
            reason = "join_key"
        elif "grain" in roles_set:
            included = True
            reason = "grain"
        elif "metric_ref" in roles_set:
            included = True
            reason = "metric_ref"
        else:
            included = False
            reason = "pruned"

        if included:
            dimensions.append(dim_name)

        dim_detail = {
            "name": dim_name,
            "included": included,
            "reason": reason,
            "roles": sorted(list(roles_set))
        }
        dimension_details.append(dim_detail)

        if debug:
            log_reason = reason
            print(f"[DIM] {'Kept' if included else 'Pruned'}: {dim_name} (reason: {log_reason})")

    return {
        "model": model_name,
        "metrics": metrics,
        "dimensions": dimensions,
        "dimension_details": dimension_details,
        "filters": filters,
        "source_tables": source_tables,
        "entity": entity,
        "relationships": relationships
    }
