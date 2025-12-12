# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import APIRouter, HTTPException
import snowflake.connector
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional, Union, Literal
from datetime import datetime
import os
from axi.config.settings import get_settings
from axi.metadata.indexer import MetadataIndexer
from axi.query.engine import SemanticQueryEngine
from axi.execution.snowflake_runner import SnowflakeRunner

router = APIRouter(prefix="/api/query", tags=["query"])
settings = get_settings()

def _get_indexer():
    return MetadataIndexer(settings.AXI_METADATA_DIR)

class FilterItem(BaseModel):
    dimension: str
    op: Literal["=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN", "BETWEEN", "LIKE"]
    value: Union[str, int, float, List[str]]
    
    @field_validator('dimension')
    @classmethod
    def validate_dimension(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Dimension cannot be empty")
        # Basic validation - no SQL injection characters
        if any(char in v for char in [';', '--', '/*', '*/', 'DROP', 'DELETE', 'UPDATE', 'INSERT']):
            raise ValueError("Invalid dimension name")
        return v.strip()
    
    @field_validator('value')
    @classmethod
    def validate_value(cls, v: Any, info) -> Any:
        op = info.data.get('op')
        if op == 'IN' and not isinstance(v, list):
            raise ValueError("IN operator requires a list value")
        return v

class SemanticQueryRequest(BaseModel):
    metrics: List[str]
    dimensions: List[str] = []
    filters: List[FilterItem] = []
    limit: Optional[int] = None

class RunSqlRequest(BaseModel):
    sql: str
    limit: int = 500

def _validate_metrics(engine: SemanticQueryEngine, metric_names: List[str]) -> List[Dict[str, Any]]:
    """Validate that all metrics exist."""
    validated = []
    for metric_name in metric_names:
        metric = engine.indexer.get_metric(metric_name)
        if not metric:
            raise HTTPException(
                status_code=404,
                detail=f"Metric '{metric_name}' not found"
            )
        validated.append(metric)
    return validated

def _build_filter_strings(filters: List[FilterItem]) -> List[str]:
    """Convert filter objects to SQL filter strings."""
    filter_strings = []
    for f in filters:
        if f.op in {"IN", "NOT IN"}:
            if isinstance(f.value, list):
                # Escape single quotes in values to prevent SQL injection
                escaped_values = [str(v).replace("'", "''") for v in f.value]
                values = ", ".join([f"'{v}'" for v in escaped_values])
                filter_strings.append(f"{f.dimension} {f.op} ({values})")
            else:
                raise ValueError(f"IN operator requires list value, got {type(f.value)}")
        elif f.op == "BETWEEN":
            if isinstance(f.value, list) and len(f.value) == 2:
                v1 = str(f.value[0]).replace("'", "''")
                v2 = str(f.value[1]).replace("'", "''")
                filter_strings.append(f"{f.dimension} BETWEEN '{v1}' AND '{v2}'")
            else:
                raise ValueError("BETWEEN requires a two-value list")
        elif f.op == "LIKE":
            escaped_value = str(f.value).replace("'", "''")
            filter_strings.append(f"{f.dimension} LIKE '{escaped_value}'")
        elif f.op in ["=", "!=", ">", "<", ">=", "<="]:
            if isinstance(f.value, str):
                # Escape single quotes
                escaped_value = f.value.replace("'", "''")
                filter_strings.append(f"{f.dimension} {f.op} '{escaped_value}'")
            else:
                # Numeric values - validate they're actually numeric
                if isinstance(f.value, (int, float)):
                    filter_strings.append(f"{f.dimension} {f.op} {f.value}")
                else:
                    raise ValueError(f"Invalid value type for operator {f.op}: {type(f.value)}")
        else:
            raise ValueError(f"Unsupported operator: {f.op}")
    return filter_strings

def _validate_grain_compatibility(engine: SemanticQueryEngine, validated_metrics: List[Dict[str, Any]]) -> None:
    """
    Validate that all metrics have compatible grains.
    Raises HTTPException with INCOMPATIBLE_GRAIN code if incompatible.
    """
    if len(validated_metrics) <= 1:
        return  # Single metric or no metrics - no compatibility check needed
    
    # Get effective grain for each metric
    grain_map = {}
    for metric in validated_metrics:
        metric_name = metric['name']
        entity = None
        entity_name = metric.get('entity_name')
        if entity_name:
            entity = engine.indexer.get_entity(entity_name)
        
        effective_grain = engine.get_effective_grain(metric, entity)
        grain_set = frozenset(effective_grain)  # Use frozenset for hashability
        grain_map[metric_name] = {
            'grain_list': effective_grain,
            'grain_set': grain_set
        }
    
    # Check if all grains are compatible (same set)
    unique_grains = {}
    for metric_name, grain_info in grain_map.items():
        grain_set = grain_info['grain_set']
        if grain_set not in unique_grains:
            unique_grains[grain_set] = []
        unique_grains[grain_set].append(metric_name)
    
    # If more than one unique grain set, they're incompatible
    if len(unique_grains) > 1:
        # Build error details
        grain_details = {}
        for metric_name, grain_info in grain_map.items():
            grain_details[metric_name] = grain_info['grain_list']
        
        incompatible_metrics = []
        for grain_set, metric_names in unique_grains.items():
            incompatible_metrics.extend(metric_names)
        
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INCOMPATIBLE_GRAIN",
                "message": f"Metrics {incompatible_metrics} cannot be queried together due to incompatible grains.",
                "grains": grain_details
            }
        )

def _generate_sql_for_metrics(
    engine: SemanticQueryEngine,
    metrics: List[str],
    dimensions: List[str],
    filters: List[str],
    dialect: str = "snowflake"
) -> str:
    """Generate SQL for multiple metrics by joining them."""
    if len(metrics) == 0:
        raise ValueError("At least one metric is required")
    
    if len(metrics) == 1:
        # Single metric - use existing logic
        return engine.generate_sql(metrics[0], dimensions, filters, dialect=dialect, optimize=True)
    
    # Multiple metrics - join them using CTEs
    # This is a simplified approach - assumes all metrics can be joined on dimensions
    ctes = []
    selects = []
    
    # Build CTE for each metric
    for i, metric_name in enumerate(metrics):
        metric_sql = engine.generate_sql(metric_name, dimensions, filters, dialect=dialect, optimize=True)
        # Remove semicolon if present
        metric_sql = metric_sql.strip().rstrip(';')
        cte_name = f"metric_{i}"
        ctes.append(f"{cte_name} AS ({metric_sql})")
        
        if i == 0:
            # First metric - use its dimensions and metric
            for dim in dimensions:
                selects.append(f"{cte_name}.{dim}")
            selects.append(f"{cte_name}.{metric_name} AS {metric_name}")
        else:
            # Subsequent metrics - join on dimensions
            selects.append(f"{cte_name}.{metric_name} AS {metric_name}")
    
    # Build final query
    sql = f"WITH {', '.join(ctes)}\n"
    sql += f"SELECT {', '.join(selects)}\n"
    sql += f"FROM metric_0\n"
    
    # Add joins for additional metrics
    for i in range(1, len(metrics)):
        cte_name = f"metric_{i}"
        join_conditions = [f"metric_0.{dim} = {cte_name}.{dim}" for dim in dimensions]
        sql += f"LEFT JOIN {cte_name} ON {' AND '.join(join_conditions)}\n"
    
    return sql

@router.post("/semantic")
def run_semantic_query(req: SemanticQueryRequest):
    """
    Run a semantic query and return generated SQL with results.
    
    Input:
    {
      "metrics": ["total_revenue"],
      "dimensions": ["date", "country"],
      "filters": [{"dimension": "country", "op": "=", "value": "UK"}]
    }
    
    Output:
    {
      "sql": "SELECT ...",
      "columns": ["date", "country", "total_revenue"],
      "rows": [...],
      "generated_at": "timestamp",
      "error": null
    }
    """
    indexer = _get_indexer()
    engine = SemanticQueryEngine(indexer)
    
    try:
        # Validate metrics
        validated_metrics = _validate_metrics(engine, req.metrics)
        
        # Validate grain compatibility for multi-metric queries
        _validate_grain_compatibility(engine, validated_metrics)
        
        # Validate dimensions are compatible with metrics
        # Get effective grain for each metric and check dimension compatibility
        for metric in validated_metrics:
            entity = None
            entity_name = metric.get('entity_name')
            if entity_name:
                entity = indexer.get_entity(entity_name)
            
            effective_grain = engine.get_effective_grain(metric, entity)
            allowed_dims = engine.get_allowed_dimensions_for_metric(metric['name'])
            
            # Check if selected dimensions are in allowed list
            for dim in req.dimensions:
                if allowed_dims and dim not in allowed_dims:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "INVALID_DIMENSION",
                            "message": f"Dimension '{dim}' is not valid for metric '{metric['name']}'",
                            "dimension": dim,
                            "metric": metric['name'],
                            "allowed_dimensions": allowed_dims
                        }
                    )
        
        # Pass filter objects directly for validation in engine
        filter_strings = req.filters or []
        
        # Generate SQL
        sql = _generate_sql_for_metrics(
            engine,
            req.metrics,
            req.dimensions,
            filter_strings,
            dialect="snowflake"
        )
        
        # Execute via Snowflake with structured errors
        runner = SnowflakeRunner()
        limit_val = req.limit or 500
        try:
            rows, cols, elapsed = runner.execute_query(f"{sql} LIMIT {limit_val}")
            # rows is list[dict]
            columns = cols
            rows_list = [[row.get(c) for c in cols] for row in rows]
            return {
                "sql": sql,
                "columns": columns,
                "rows": rows_list,
                "generated_at": datetime.utcnow().isoformat(),
                "execution_ms": elapsed,
                "entity": entity_name,
                "metrics": req.metrics
            }
        except ValueError as ve:
            raise HTTPException(status_code=400, detail={"code": "NO_SNOWFLAKE_CREDENTIALS", "message": str(ve)})
        except snowflake.connector.errors.ProgrammingError as pe:  # type: ignore
            raise HTTPException(status_code=400, detail={"code": "SQL_SYNTAX_ERROR", "message": str(pe)})
        except snowflake.connector.errors.DatabaseError as de:  # type: ignore
            raise HTTPException(status_code=401, detail={"code": "SNOWFLAKE_AUTH_FAILED", "message": str(de)})
        except Exception as e:
            raise HTTPException(status_code=500, detail={"code": "SNOWFLAKE_CONNECTION_ERR", "message": str(e)})
    except SemanticQueryEngine.SemanticError as se:  # type: ignore
        raise HTTPException(status_code=400, detail={"code": se.code, "message": str(se), "hint": se.hint})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "METRIC_INVALID", "message": str(e)})

@router.post("/semantic/sql-only")
def generate_sql_only(req: SemanticQueryRequest):
    """
    Generate SQL without executing.
    """
    try:
        indexer = _get_indexer()
        engine = SemanticQueryEngine(indexer)
        
        # Validate metrics exist
        validated_metrics = _validate_metrics(engine, req.metrics)
        
        # Validate grain compatibility for multi-metric queries
        _validate_grain_compatibility(engine, validated_metrics)
        
        # Validate dimensions are compatible with metrics
        for metric in validated_metrics:
            entity = None
            entity_name = metric.get('entity_name')
            if entity_name:
                entity = indexer.get_entity(entity_name)
            
            effective_grain = engine.get_effective_grain(metric, entity)
            allowed_dims = engine.get_allowed_dimensions_for_metric(metric['name'])
            
            # Check if selected dimensions are in allowed list
            for dim in req.dimensions:
                if allowed_dims and dim not in allowed_dims:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "INVALID_DIMENSION",
                            "message": f"Dimension '{dim}' is not valid for metric '{metric['name']}'",
                            "dimension": dim,
                            "metric": metric['name'],
                            "allowed_dimensions": allowed_dims
                        }
                    )
        
        # Convert filter objects to strings
        filter_strings = _build_filter_strings(req.filters) if req.filters else []
        
        # Generate SQL
        try:
            sql = _generate_sql_for_metrics(
                engine,
                req.metrics,
                req.dimensions,
                filter_strings,
                dialect="snowflake"
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"METRIC_INVALID: {e}")
        
        return {
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "entity": entity_name,
            "metrics": req.metrics,
            "grain": effective_grain,
            "execution_ms": 0,
            "generated_at": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        # Return more detailed error message
        error_detail = str(e)
        if "ENTITY_UNRESOLVED" in error_detail:
            raise HTTPException(status_code=400, detail=error_detail)
        if "not found" in error_detail.lower():
            raise HTTPException(status_code=404, detail=error_detail)
        raise HTTPException(status_code=400, detail=f"Failed to generate SQL: {error_detail}")

@router.post("/semantic/plan")
def get_query_plan(req: SemanticQueryRequest):
    """
    Return join graph debug output for query planning.
    """
    indexer = _get_indexer()
    engine = SemanticQueryEngine(indexer)
    
    try:
        validated_metrics = _validate_metrics(engine, req.metrics)
        
        # Get reachable dimensions for each metric
        plan = {
            "metrics": [],
            "dimensions": req.dimensions,
            "join_paths": []
        }
        
        for metric in validated_metrics:
            metric_name = metric['name']
            reachable = engine.get_reachable_dimensions(metric_name)
            plan["metrics"].append({
                "name": metric_name,
                "model": metric.get('model'),
                "reachable_dimensions": reachable
            })
        
        return {
            "plan": plan,
            "generated_at": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/semantic/reachable-dimensions")
def get_reachable_dimensions(req: SemanticQueryRequest):
    """
    Get reachable dimensions for the given metrics.
    Returns a flat list of dimension names that can be joined to the metrics.
    """
    indexer = _get_indexer()
    engine = SemanticQueryEngine(indexer)
    
    try:
        validated_metrics = _validate_metrics(engine, req.metrics)
        
        # Collect all reachable dimensions across all metrics
        all_reachable_dims = set()
        
        for metric in validated_metrics:
            metric_name = metric['name']
            reachable = engine.get_reachable_dimensions(metric_name)
            
            # Flatten the reachable dimensions (they're grouped by model)
            for model_name, dims in reachable.items():
                for dim in dims:
                    if isinstance(dim, str):
                        all_reachable_dims.add(dim)
                    elif isinstance(dim, dict):
                        dim_name = dim.get('name') or dim.get('dimension_name')
                        if dim_name:
                            all_reachable_dims.add(dim_name)
        
        return {
            "dimensions": sorted(list(all_reachable_dims)),
            "generated_at": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/run")
def run_sql(req: RunSqlRequest):
    """
    Execute SQL against Snowflake with credential validation and error mapping.
    """
    if not req.sql or not req.sql.strip():
        raise HTTPException(status_code=400, detail="SQL_REQUIRED")

    sql = req.sql.strip()
    if req.limit and req.limit > 0 and "limit" not in sql.lower():
        sql = f"{sql.rstrip(';')} LIMIT {req.limit}"

    runner = SnowflakeRunner()
    try:
        rows, cols, elapsed = runner.execute_query(sql)
        row_list = [[row.get(c) for c in cols] for row in rows]
        return {
            "sql": sql,
            "columns": cols,
            "rows": row_list,
            "row_count": len(row_list),
            "execution_ms": elapsed
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"MISSING_CREDENTIALS: {ve}")
    except snowflake.connector.errors.ProgrammingError as pe:  # type: ignore
        raise HTTPException(status_code=400, detail=f"SQL_SYNTAX_ERROR: {pe}")
    except snowflake.connector.errors.DatabaseError as de:  # type: ignore
        raise HTTPException(status_code=401, detail=f"SNOWFLAKE_AUTH_FAILED: {de}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CONNECTION_ERROR: {e}")
