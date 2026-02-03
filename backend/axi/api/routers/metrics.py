# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
import sqlite3
import json
from datetime import datetime
from axi.config.settings import get_settings
from axi.metadata.indexer import MetadataIndexer
from axi.query.engine import SemanticQueryEngine
from axi.execution.snowflake_runner import SnowflakeRunner
from axi.metrics.store import MetricStore
from axi.metrics.validator import MetricValidator
from axi.utils.logging_config import get_logger
from axi.exceptions import DatabaseError, MetadataError, ValidationError

router = APIRouter(prefix="/api/metrics", tags=["metrics"])
settings = get_settings()
logger = get_logger(__name__)

def _get_indexer():
    return MetadataIndexer(settings.AXI_METADATA_DIR)

def _init_metrics_tables(conn: sqlite3.Connection):
    """Ensure metrics table has all required columns."""
    c = conn.cursor()
    
    # Check if columns exist, add if missing
    c.execute("PRAGMA table_info(metrics)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'default_dimensions' not in columns:
        c.execute("ALTER TABLE metrics ADD COLUMN default_dimensions JSON")
    if 'tags' not in columns:
        c.execute("ALTER TABLE metrics ADD COLUMN tags JSON")
    if 'grain' not in columns:
        c.execute("ALTER TABLE metrics ADD COLUMN grain TEXT")
    if 'source_model' not in columns:
        c.execute("ALTER TABLE metrics ADD COLUMN source_model TEXT")
    if 'entity_name' not in columns:
        c.execute("ALTER TABLE metrics ADD COLUMN entity_name TEXT")
    if 'updated_at' not in columns:
        c.execute("ALTER TABLE metrics ADD COLUMN updated_at TEXT")
    if 'created_at' not in columns:
        c.execute("ALTER TABLE metrics ADD COLUMN created_at TEXT")
    if 'type' not in columns:
        c.execute("ALTER TABLE metrics ADD COLUMN type TEXT")
    
    # Create metrics_id table for ID mapping (since metrics uses name as PK)
    c.execute('''CREATE TABLE IF NOT EXISTS metrics_id_map (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric_name TEXT NOT NULL UNIQUE,
        FOREIGN KEY(metric_name) REFERENCES metrics(name)
    )''')
    
    # Populate ID map if needed
    c.execute("SELECT COUNT(*) FROM metrics_id_map")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO metrics_id_map (metric_name) SELECT name FROM metrics")
    
    # Backfill entity_name from entities based on model or source_model
    # This fixes issues where metrics don't show up in entity-filtered lists
    c.execute("""
        UPDATE metrics 
        SET entity_name = (
            SELECT name 
            FROM entities 
            WHERE entities.model = COALESCE(metrics.model, metrics.source_model)
        ) 
        WHERE entity_name IS NULL 
          AND COALESCE(metrics.model, metrics.source_model) IS NOT NULL
    """)
    
    conn.commit()

def _get_metric_id(conn: sqlite3.Connection, metric_name: str) -> Optional[int]:
    """Get metric ID from name."""
    c = conn.cursor()
    c.execute("SELECT id FROM metrics_id_map WHERE metric_name = ?", (metric_name,))
    row = c.fetchone()
    return row[0] if row else None

def _get_metric_name(conn: sqlite3.Connection, metric_id: int) -> Optional[str]:
    """Get metric name from ID."""
    c = conn.cursor()
    c.execute("SELECT metric_name FROM metrics_id_map WHERE id = ?", (metric_id,))
    row = c.fetchone()
    return row[0] if row else None

@router.get("")
def list_metrics():
    """
    List all metrics with entity information.
    Returns: List of metrics with id, name, entity_name, type, expression, default_dimensions, description
    """
    logger.debug("Listing all metrics")
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_metrics_tables(conn)
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = """
            SELECT
                mi.id,
                m.name,
                m.entity_name,
                COALESCE(m.type, m.metric_type, m.aggregation, 'custom') AS type,
                m.expression,
                m.default_dimensions,
                m.description,
                COALESCE(m.version, '1.0') AS version,
                COALESCE(m.status, 'active') AS status,
                m.deprecation_date,
                m.replacement_metric
            FROM metrics m
            LEFT JOIN metrics_id_map mi ON mi.metric_name = m.name
            ORDER BY m.entity_name, m.name
            """
            
            try:
                c.execute(query)
                rows = c.fetchall()
                result = []
                for row in rows:
                    row_dict = dict(row)
                    # Parse JSON fields
                    if row_dict.get('default_dimensions'):
                        try:
                            row_dict['default_dimensions'] = json.loads(row_dict['default_dimensions']) if isinstance(row_dict['default_dimensions'], str) else row_dict['default_dimensions']
                        except (json.JSONDecodeError, TypeError, ValueError):
                            row_dict['default_dimensions'] = []
                    else:
                        row_dict['default_dimensions'] = []
                    result.append(row_dict)
                return result
            except sqlite3.OperationalError as e:
                logger.warning(f"Database error listing metrics: {e}")
                raise DatabaseError(f"Database error listing metrics: {e}", code="DATABASE_ERROR")
    except DatabaseError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing metrics: {e}")
        raise MetadataError(f"Failed to list metrics: {e}", code="METRICS_LIST_ERROR")

@router.get("/{metric_id}")
def get_metric(metric_id: str):
    """
    Get a single metric by ID (integer) or name (string) with full metadata.
    """
    logger.debug(f"Getting metric: {metric_id}")
    # Validate metric_id input
    from axi.utils.sanitization import validate_metric_name, sanitize_string
    try:
        # If it's numeric, it's an ID, otherwise validate as metric name
        int(metric_id)  # Try to parse as int
    except ValueError:
        # It's a metric name, validate it
        try:
            metric_id = validate_metric_name(metric_id)
        except ValueError as ve:
            raise ValidationError(str(ve), code="INVALID_METRIC_NAME")
    
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_metrics_tables(conn)
            
            # Try to parse as integer ID first
            try:
                metric_id_int = int(metric_id)
                metric_name = _get_metric_name(conn, metric_id_int)
                if not metric_name:
                    raise HTTPException(status_code=404, detail="Metric not found")
            except (ValueError, TypeError):
                # If not an integer, treat as metric name
                metric_name = metric_id
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = """
            SELECT
                m.name,
                m.entity_name,
                m.entity_name AS entity,
                COALESCE(m.type, m.metric_type, m.aggregation, 'custom') AS type,
                m.expression,
                m.default_dimensions,
                m.description,
                m.tags,
                m.source_model,
                m.grain,
                m.created_at,
                m.updated_at,
                COALESCE(m.version, '1.0') AS version,
                COALESCE(m.status, 'active') AS status,
                m.deprecation_date,
                m.replacement_metric
            FROM metrics m
            WHERE m.name = ?
            """
            
            c.execute(query, (metric_name,))
            row = c.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Metric not found")
            
            result = dict(row)
            # Parse JSON fields
            if result.get('default_dimensions'):
                try:
                    result['default_dimensions'] = json.loads(result['default_dimensions']) if isinstance(result['default_dimensions'], str) else result['default_dimensions']
                except (json.JSONDecodeError, TypeError, ValueError):
                    result['default_dimensions'] = []
            else:
                result['default_dimensions'] = []
            
            if result.get('tags'):
                try:
                    result['tags'] = json.loads(result['tags']) if isinstance(result['tags'], str) else result['tags']
                except (json.JSONDecodeError, TypeError, ValueError):
                    result['tags'] = []
            else:
                result['tags'] = []
            
            # Parse grain field (can be JSON string or already parsed)
            if result.get('grain'):
                try:
                    if isinstance(result['grain'], str):
                        grain_data = json.loads(result['grain'])
                        result['grain'] = grain_data if isinstance(grain_data, list) else [grain_data] if grain_data else []
                    elif isinstance(result['grain'], list):
                        result['grain'] = result['grain']
                    else:
                        result['grain'] = [result['grain']]
                except (json.JSONDecodeError, TypeError, ValueError):
                    # Keep as string if not JSON
                    if isinstance(result['grain'], str):
                        result['grain'] = [result['grain']]
            
            # Try to get the ID for this metric name
            metric_id_from_name = _get_metric_id(conn, metric_name)
            result['id'] = metric_id_from_name if metric_id_from_name else None
            return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _resolve_metric_name(metric_id: str) -> str:
    """Resolve metric_id (id or name) to metric name. Raises HTTPException if not found."""
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_metrics_tables(conn)
            try:
                metric_id_int = int(metric_id)
                metric_name = _get_metric_name(conn, metric_id_int)
                if not metric_name:
                    raise HTTPException(status_code=404, detail="Metric not found")
                return metric_name
            except (ValueError, TypeError):
                pass
    except HTTPException:
        raise
    return metric_id


@router.get("/{metric_id}/versions")
def list_metric_versions(metric_id: str):
    """
    List server-backed version history for a metric (newest first).
    """
    metric_name = _resolve_metric_name(metric_id)
    indexer = _get_indexer()
    metric = indexer.get_metric(metric_name)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    history = indexer.list_metric_version_history(metric_name)
    return {"metric_name": metric_name, "versions": history}


@router.get("/{metric_id}/current")
def get_metric_current(metric_id: str):
    """
    Get current version of a metric (same as GET /api/metrics/{metric_id} with version/status).
    """
    return get_metric(metric_id)


@router.get("/{metric_id}/intent")
def get_metric_intent(metric_id: str):
    """
    Get the Semantic Intent for a metric (deterministic, JSON-serializable).
    Includes metric, grain, dimensions, filters, joins. No raw SQL; transparency only.
    """
    from axi.intent.builder import build_intent_from_metric
    metric_name = _resolve_metric_name(metric_id)
    indexer = _get_indexer()
    metric = indexer.get_metric(metric_name)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    metric_version = metric.get("version") or "1.0"
    intent = build_intent_from_metric(
        indexer=indexer,
        metric_name=metric_name,
        metric_version=metric_version,
        dimensions_override=None,
        filters_override=None,
        engine=None,
    )
    if not intent:
        raise HTTPException(status_code=404, detail="Metric not found or intent could not be built")
    return intent.model_dump()


@router.get("/{metric_id}/compiled-sql")
def get_metric_compiled_sql(
    metric_id: str,
    warehouse: str = "snowflake",
):
    """
    Get AXI compiled SQL from the metric's Semantic Intent (governed, intent-based).
    Includes AXI metadata comments; fingerprintable. No execution; transparency only.
    """
    from axi.intent.builder import build_intent_from_metric
    from axi.intent.compiler import compile_metric
    from axi.exceptions import MetricDisabledError, ContractViolationError
    metric_name = _resolve_metric_name(metric_id)
    indexer = _get_indexer()
    metric = indexer.get_metric(metric_name)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    metric_version = metric.get("version") or "1.0"
    status = (metric.get("status") or "active").strip().lower()
    
    try:
        intent = build_intent_from_metric(
            indexer=indexer,
            metric_name=metric_name,
            metric_version=metric_version,
            dimensions_override=None,
            filters_override=None,
            engine=None,
        )
        if not intent:
            raise HTTPException(status_code=404, detail="Metric not found or intent could not be built")
        
        sql = compile_metric(
            intent=intent,
            warehouse=warehouse,
            indexer=indexer,
            deprecated=(status == "deprecated"),
            status=status,
            replacement_metric=metric.get("replacement_metric"),
            generated_at=None,
            validate_contract=True,
            register_fingerprint=False,
        )
        return {"sql": sql, "metric_name": metric_name, "version": metric_version, "warehouse": warehouse}
    except MetricDisabledError as e:
        raise HTTPException(
            status_code=410,
            detail=e.to_dict(),
        )
    except ContractViolationError as e:
        raise HTTPException(
            status_code=400,
            detail={"code": "CONTRACT_VIOLATION", "message": str(e), "snippet": getattr(e, "context", {}).get("snippet")},
        )


@router.get("/{metric_id}/usage")
def get_metric_usage(metric_id: str):
    """
    Get usage summary for a metric: total count, deprecated access, first_seen, last_seen, by version.
    """
    metric_name = _resolve_metric_name(metric_id)
    indexer = _get_indexer()
    metric = indexer.get_metric(metric_name)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    rows = indexer.list_usage(metric_name=metric_name)
    if not rows:
        return {
            "metric_name": metric_name,
            "total_usage_count": 0,
            "total_deprecated_access_count": 0,
            "first_seen": None,
            "last_seen": None,
            "by_version": [],
        }
    total_usage = sum(r["usage_count"] for r in rows)
    total_deprecated = sum(r["deprecated_access_count"] for r in rows)
    dates = [r["usage_date"] for r in rows]
    first_seen = min(dates) if dates else None
    last_seen = max(dates) if dates else None
    by_version: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        v = r["metric_version"]
        if v not in by_version:
            by_version[v] = {"version": v, "usage_count": 0, "deprecated_access_count": 0, "first_seen": r["usage_date"], "last_seen": r["usage_date"]}
        by_version[v]["usage_count"] += r["usage_count"]
        by_version[v]["deprecated_access_count"] += r["deprecated_access_count"]
        by_version[v]["first_seen"] = min(by_version[v]["first_seen"], r["usage_date"])
        by_version[v]["last_seen"] = max(by_version[v]["last_seen"], r["usage_date"])
    return {
        "metric_name": metric_name,
        "total_usage_count": total_usage,
        "total_deprecated_access_count": total_deprecated,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "by_version": list(by_version.values()),
    }


@router.get("/{metric_id}/usage/timeseries")
def get_metric_usage_timeseries(
    metric_id: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """
    Get usage timeseries for a metric (daily buckets). Optional date_from / date_to (YYYY-MM-DD).
    """
    metric_name = _resolve_metric_name(metric_id)
    indexer = _get_indexer()
    metric = indexer.get_metric(metric_name)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    rows = indexer.list_usage(metric_name=metric_name, usage_date_from=date_from, usage_date_to=date_to)
    by_date: Dict[str, Dict[str, int]] = {}
    for r in rows:
        d = r["usage_date"]
        if d not in by_date:
            by_date[d] = {"date": d, "usage_count": 0, "deprecated_access_count": 0}
        by_date[d]["usage_count"] += r["usage_count"]
        by_date[d]["deprecated_access_count"] += r["deprecated_access_count"]
    series = sorted(by_date.values(), key=lambda x: x["date"])
    return {"metric_name": metric_name, "series": series}


@router.get("/{metric_id}/dependencies")
def get_metric_dependencies(metric_id: str):
    """
    Get upstream/downstream metadata for lineage visualization.
    """
    logger.debug(f"Getting metric dependencies: {metric_id}")
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_metrics_tables(conn)
            
            # Resolve metric name from ID if needed
            try:
                metric_id_int = int(metric_id)
                metric_name = _get_metric_name(conn, metric_id_int)
                if not metric_name:
                    raise HTTPException(status_code=404, detail="Metric not found")
            except (ValueError, TypeError):
                metric_name = metric_id

        metric = indexer.get_metric(metric_name)
        if not metric:
            raise HTTPException(status_code=404, detail="Metric not found")

        source_model = metric.get("model") or metric.get("source_model")
        entity = metric.get("entity_name") or metric.get("entity")

        source_tables: List[str] = []
        if source_model:
            model = indexer.get_model(source_model)
            if model:
                source_tables = model.get("source_tables") or []

        dims = metric.get("default_dimensions") or metric.get("dimensions") or []
        if isinstance(dims, str):
            try:
                parsed_dims = json.loads(dims)
                dims = parsed_dims if isinstance(parsed_dims, list) else [parsed_dims]
            except (json.JSONDecodeError, TypeError, ValueError):
                dims = [dims]

        downstream_metrics: List[str] = []
        try:
            for m in indexer.list_metrics():
                deps = m.get("depends_on") or []
                if isinstance(deps, str):
                    try:
                        deps = json.loads(deps)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        deps = []
                if isinstance(deps, list) and metric_name in deps:
                    downstream_metrics.append(m.get("name") or m.get("metric"))
        except Exception as e:
            logger.warning(f"Error computing downstream metrics for {metric_name}: {e}")

        return {
            "dependencies": metric.get("depends_on") or [],
            "source_model": source_model,
            "entity": entity,
            "source_tables": source_tables,
            "dimensions": dims,
            "downstream_metrics": downstream_metrics
        }
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.warning(f"Database error getting metric dependencies: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error getting metric dependencies: {e}")
        raise HTTPException(
            status_code=500,
            detail=MetadataError(f"Failed to get metric dependencies: {e}", code="METRIC_DEPENDENCIES_ERROR").to_dict()
        )

@router.get("/{metric_id}/dimensions")
def get_metric_dimensions(metric_id: str):
    """
    Get all dimensions linked to a metric.
    """
    logger.debug(f"Getting dimensions for metric: {metric_id}")
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_metrics_tables(conn)
            
            # Try to parse as integer ID first
            try:
                metric_id_int = int(metric_id)
                metric_name = _get_metric_name(conn, metric_id_int)
                if not metric_name:
                    raise HTTPException(status_code=404, detail="Metric not found")
            except (ValueError, TypeError):
                # If not an integer, treat as metric name
                metric_name = metric_id
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Get dimensions from metric_dimensions join table
            query = """
            SELECT
                d.id,
                d.name,
                d.data_type AS type,
                d.cardinality,
                d.description
            FROM dimensions d
            JOIN metric_dimensions md ON md.dimension_id = d.id
            WHERE md.metric_name = ?
            """
            
            try:
                c.execute(query, (metric_name,))
                rows = c.fetchall()
                result = [dict(row) for row in rows]
                return result
            except sqlite3.OperationalError as e:
                logger.warning(f"Database error getting metric dimensions: {e}")
                # Fallback: get dimensions from metrics.dimensions JSON
                c.execute("SELECT dimensions FROM metrics WHERE name = ?", (metric_name,))
                row = c.fetchone()
                if row and row[0]:
                    dims_json = row[0]
                    try:
                        dims = json.loads(dims_json) if isinstance(dims_json, str) else dims_json
                    except (json.JSONDecodeError, TypeError, ValueError):
                        dims = []
                    # Return simplified structure
                    result = [{"name": d, "type": "TEXT", "cardinality": None, "description": None} for d in dims if isinstance(d, str)]
                    return result
                return []
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.warning(f"Database error getting metric dimensions: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error getting metric dimensions: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to get metric dimensions: {e}", code="METRIC_DIMENSIONS_ERROR").to_dict())

@router.get("/{metric_id}/entities")
def get_metric_entities(metric_id: str):
    """
    Get all entities linked to a metric.
    """
    logger.debug(f"Getting entities for metric: {metric_id}")
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_metrics_tables(conn)
            
            metric_name = _get_metric_name(conn, metric_id)
            if not metric_name:
                raise HTTPException(status_code=404, detail="Metric not found")
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Get primary entity from metric
            c.execute("SELECT entity_name, model FROM metrics WHERE name = ?", (metric_name,))
            metric_row = c.fetchone()
            
            result = []
            if metric_row:
                metric_data = dict(metric_row)
                entity_name = metric_data.get('entity_name')
                model = metric_data.get('model')
                
                if entity_name:
                    result.append({"name": entity_name, "model": model})
                
                # Get entities from model's source_tables
                if model:
                    c.execute("SELECT source_tables FROM models WHERE name = ?", (model,))
                    model_row = c.fetchone()
                    if model_row and model_row[0]:
                        try:
                            source_tables = json.loads(model_row[0]) if isinstance(model_row[0], str) else model_row[0]
                        except (json.JSONDecodeError, TypeError, ValueError):
                            source_tables = []
                        for table in source_tables:
                            # Check if table is an entity
                            c.execute("SELECT name, model FROM entities WHERE name = ? OR model = ?", (table, table))
                            entity_row = c.fetchone()
                            if entity_row:
                                entity_data = dict(entity_row)
                                if entity_data['name'] not in [e['name'] for e in result]:
                                    result.append({"name": entity_data['name'], "model": entity_data.get('model')})
            
            return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

class SemanticQueryRequest(BaseModel):
    metrics: List[str]
    dimensions: List[str] = []
    filters: List[str] = []

@router.post("/query/semantic")
def run_semantic_query(req: SemanticQueryRequest):
    """
    Run a semantic query and return generated SQL with preview.
    """
    logger.info(f"Running semantic query for metrics: {req.metrics}")
    indexer = _get_indexer()
    engine = SemanticQueryEngine(indexer)
    
    try:
        # Generate SQL
        sql = engine.generate_sql(
            req.metrics[0] if req.metrics else "",
            req.dimensions,
            req.filters,
            dialect="snowflake"
        )
        
        # Try to execute and get preview
        preview = []
        try:
            runner = SnowflakeRunner()
            rows, columns = runner.execute_query(f"{sql} LIMIT 20")
            preview = rows
        except ValueError:
            # If Snowflake not configured, just return SQL
            logger.debug("Snowflake not configured, returning SQL only")
        except Exception as e:
            logger.debug(f"Snowflake execution error (non-fatal): {e}")
        
        return {
            "sql": sql,
            "preview": preview
        }
    except QueryError as e:
        logger.warning(f"Query error in semantic query: {e}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error in semantic query: {e}")
        raise HTTPException(status_code=400, detail=QueryError(f"Failed to run semantic query: {e}", code="SEMANTIC_QUERY_ERROR").to_dict())

@router.get("/{metric_id}/sample")
def get_metric_sample(metric_id: str, limit: int = 20):
    """
    Get sample values for a metric with default dimensions.
    """
    logger.debug(f"Getting sample for metric: {metric_id}, limit: {limit}")
    # Validate limit
    if limit < 1 or limit > 1000:
        raise ValidationError("Limit must be between 1 and 1000", code="INVALID_LIMIT")
    
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_metrics_tables(conn)
            
            # Try to parse as integer ID first
            try:
                metric_id_int = int(metric_id)
                metric_name = _get_metric_name(conn, metric_id_int)
                if not metric_name:
                    raise HTTPException(status_code=404, detail="Metric not found")
            except (ValueError, TypeError):
                # If not an integer, treat as metric name
                metric_name = metric_id
            
            # Get default dimensions
            c = conn.cursor()
            c.execute("SELECT default_dimensions FROM metrics WHERE name = ?", (metric_name,))
            row = c.fetchone()
            default_dims = []
            if row and row[0]:
                try:
                    default_dims = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                except (json.JSONDecodeError, TypeError, ValueError):
                    default_dims = []
            
        # Generate SQL and execute (outside connection context)
        try:
            engine = SemanticQueryEngine(indexer)
            sql = engine.generate_sql(metric_name, default_dims, [], dialect="snowflake")
            
            runner = SnowflakeRunner()
            rows, columns, _ = runner.execute_query(f"{sql} LIMIT {limit}")
            return {
                "columns": columns,
                "rows": rows
            }
        except ValueError:
            # If Snowflake not configured, return empty
            logger.debug("Snowflake not configured for metric sample")
            return {
                "columns": [],
                "rows": []
            }
        except Exception as e:
            logger.debug(f"Snowflake execution error for sample (non-fatal): {e}")
            return {
                "columns": [],
                "rows": []
            }
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.warning(f"Database error getting metric sample: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error getting metric sample: {e}")
        # Return empty on error to prevent breaking UI
        return {
            "columns": [],
            "rows": []
        }

# User-Defined Metrics CRUD

class CreateMetricRequest(BaseModel):
    metric: str = Field(..., description="Metric name")
    description: Optional[str] = Field(None, description="Metric description")
    entity: str = Field(..., description="Entity this metric belongs to")
    expression: str = Field(..., description="SQL expression (must contain exactly one aggregation)")
    type: Optional[str] = Field(None, description="Metric type (sum, count, avg, min, max)")
    grain: Optional[List[str]] = Field(None, description="Fixed grain override (list of dimension names)")
    dimensions: Optional[List[str]] = Field(None, description="Allowed dimensions for slicing")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")
    
    @field_validator('metric')
    @classmethod
    def validate_metric(cls, v: str) -> str:
        from axi.utils.sanitization import validate_metric_name
        return validate_metric_name(v)
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v:
            from axi.utils.sanitization import sanitize_string
            return sanitize_string(v, max_length=1000)
        return v
    
    @field_validator('dimensions')
    @classmethod
    def validate_dimensions(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v:
            from axi.utils.sanitization import validate_dimension_name
            validated = []
            for dim in v:
                validated.append(validate_dimension_name(dim))
            return validated
        return v

class UpdateMetricRequest(BaseModel):
    description: Optional[str] = None
    entity: Optional[str] = None
    expression: Optional[str] = None
    type: Optional[str] = None
    grain: Optional[List[str]] = None
    dimensions: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        if v:
            from axi.utils.sanitization import sanitize_string
            return sanitize_string(v, max_length=1000)
        return v
    
    @field_validator('dimensions')
    @classmethod
    def validate_dimensions(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v:
            from axi.utils.sanitization import validate_dimension_name
            validated = []
            for dim in v:
                validated.append(validate_dimension_name(dim))
            return validated
        return v

class MetricJoinPlanRequest(BaseModel):
    """Request model for previewing join plan for a metric."""
    entity: str
    expression: str
    dimensions: Optional[List[str]] = Field(default_factory=list)

def _get_metric_store():
    """Get metric store instance."""
    # Find project root
    import os
    current = os.getcwd()
    project_root = None
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "axi.yml")):
            project_root = current
            break
        current = os.path.dirname(current)
    
    if not project_root:
        project_root = os.getcwd()
    
    return MetricStore(project_root)

@router.post("", status_code=201)
def create_metric(req: CreateMetricRequest):
    """
    Create a new user-defined metric.
    """
    logger.info(f"Creating metric: {req.metric}")
    # Validate metric name
    from axi.utils.sanitization import validate_metric_name
    try:
        validated_name = validate_metric_name(req.metric)
    except ValueError as ve:
        raise ValidationError(str(ve), code="INVALID_METRIC_NAME")
    
    indexer = _get_indexer()
    validator = MetricValidator(indexer)
    store = _get_metric_store()
    
    # Convert request to dict
    metric_data = req.dict(exclude_none=True)
    metric_data["metric"] = validated_name  # Use validated name
    metric_data["created_at"] = datetime.utcnow().isoformat()
    metric_data["updated_at"] = datetime.utcnow().isoformat()
    
    # Validate
    is_valid, errors = validator.validate(metric_data)
    if not is_valid:
        logger.warning(f"Validation failed for metric {req.metric}: {errors}")
        raise HTTPException(status_code=400, detail=ValidationError("Metric validation failed", code="VALIDATION_ERROR", context={"errors": errors}).to_dict())
    
    # Infer type from expression if not provided
    if not metric_data.get("type"):
        try:
            import sqlglot
            from sqlglot import exp
            parsed = sqlglot.parse_one(metric_data["expression"])
            if list(parsed.find_all(exp.Sum)):
                metric_data["type"] = "sum"
            elif list(parsed.find_all(exp.Count)):
                metric_data["type"] = "count"
            elif list(parsed.find_all(exp.Avg)):
                metric_data["type"] = "avg"
            elif list(parsed.find_all(exp.Min)):
                metric_data["type"] = "min"
            elif list(parsed.find_all(exp.Max)):
                metric_data["type"] = "max"
            else:
                metric_data["type"] = "custom"
        except:
            metric_data["type"] = "custom"

    # Build dimension_entity_map for cross-entity dimensions
    if metric_data.get("dimensions") and metric_data.get("entity"):
        from axi.query.reachability import SemanticReachability
        reachability = SemanticReachability(indexer)

        try:
            # Get reachability context for the entity
            entity_name = metric_data["entity"]
            context = reachability.plan_context([], [entity_name])

            # Build dimension -> entity mapping
            dimension_entity_map = {}
            for dim_name in metric_data["dimensions"]:
                # Find which entity this dimension belongs to
                for visible_dim in context.get("visible_dimensions", []):
                    if visible_dim["name"] == dim_name:
                        dimension_entity_map[dim_name] = visible_dim["entity"]
                        break

            # Store the mapping if it has entries
            if dimension_entity_map:
                metric_data["dimension_entity_map"] = dimension_entity_map
                logger.debug(f"Built dimension_entity_map for {req.metric}: {dimension_entity_map}")
        except Exception as e:
            logger.warning(f"Failed to build dimension_entity_map: {e}")
            # Continue without the map - it's optional

    try:
        # Create metric
        created = store.create(metric_data)
        logger.info(f"Successfully created metric: {req.metric}")
        
        # Rebuild metadata index to include new metric
        indexer.build_index()
        
        return created
    except ValueError as e:
        logger.warning(f"Validation error creating metric: {e}")
        raise HTTPException(status_code=400, detail=ValidationError(str(e), code="VALIDATION_ERROR").to_dict())
    except MetadataError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error creating metric: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to create metric: {e}", code="METRIC_CREATE_ERROR").to_dict())

@router.post("/preview-join-plan")
def preview_join_plan(req: MetricJoinPlanRequest):
    """
    Preview what JOINs will be required for a metric definition.
    Returns join paths, involved entities, and dimension-to-entity mappings.
    """
    logger.info(f"Previewing join plan for entity: {req.entity}")

    indexer = _get_indexer()
    engine = SemanticQueryEngine(indexer)

    try:
        # Extract metric references from expression
        metric_refs = engine._extract_metric_references(req.expression)

        # Determine involved entities
        involved_entities = {req.entity}

        # Add entities from referenced metrics
        for ref_name in metric_refs:
            ref_metric = indexer.get_metric(ref_name)
            if ref_metric:
                ref_entity = ref_metric.get('entity_name')
                if ref_entity:
                    involved_entities.add(ref_entity)

        # Map dimensions to entities using reachability
        dimension_entity_map = {}
        if req.dimensions:
            context = engine.reachability.plan_context([], [req.entity])
            for dim_name in req.dimensions:
                # Find which entity this dimension belongs to
                for visible_dim in context.get('visible_dimensions', []):
                    if visible_dim['name'] == dim_name:
                        dimension_entity_map[dim_name] = visible_dim['entity']
                        involved_entities.add(visible_dim['entity'])
                        break

        # Compute join paths for all involved entities (except base)
        join_paths = {}
        warnings = []

        # Get base entity's model
        base_entity_obj = indexer.get_entity(req.entity)
        if not base_entity_obj:
            return {
                "error": f"Entity '{req.entity}' not found",
                "base_entity": req.entity,
                "involved_entities": list(involved_entities),
                "join_paths": {},
                "dimension_entity_map": dimension_entity_map,
                "metric_references": metric_refs,
                "warnings": [f"Entity '{req.entity}' not found"]
            }

        base_model = base_entity_obj.get('model') or req.entity

        for entity_name in involved_entities:
            if entity_name != req.entity:
                # Get model for this entity
                entity_obj = indexer.get_entity(entity_name)
                if not entity_obj:
                    warnings.append(f"Entity '{entity_name}' not found")
                    continue

                target_model = entity_obj.get('model') or entity_name

                try:
                    # Get join path
                    path = engine._resolve_join_path(base_model, target_model)
                    join_paths[entity_name] = [
                        {
                            "from": edge.get("source"),
                            "to": edge.get("target"),
                            "fk": edge.get("source_col"),
                            "pk": edge.get("target_col")
                        }
                        for edge in path
                    ]
                except Exception as e:
                    warnings.append(f"Cannot join to {entity_name}: {str(e)}")

        return {
            "base_entity": req.entity,
            "base_model": base_model,
            "involved_entities": list(involved_entities),
            "join_paths": join_paths,
            "dimension_entity_map": dimension_entity_map,
            "metric_references": metric_refs,
            "warnings": warnings
        }

    except Exception as e:
        logger.error(f"Error previewing join plan: {e}")
        raise HTTPException(
            status_code=500,
            detail=MetadataError(f"Failed to preview join plan: {e}", code="JOIN_PLAN_ERROR").to_dict()
        )

@router.put("/{metric_name}")
def update_metric(metric_name: str, req: UpdateMetricRequest):
    """
    Update an existing user-defined metric.
    """
    logger.info(f"Updating metric: {metric_name}")
    # Validate metric name
    from axi.utils.sanitization import validate_metric_name
    try:
        validated_name = validate_metric_name(metric_name)
    except ValueError as ve:
        raise ValidationError(str(ve), code="INVALID_METRIC_NAME")
    
    indexer = _get_indexer()
    validator = MetricValidator(indexer)
    store = _get_metric_store()
    
    # Get existing metric
    existing = store.get(validated_name)
    if not existing:
        raise HTTPException(status_code=404, detail=MetadataError(f"Metric '{validated_name}' not found", code="METRIC_NOT_FOUND").to_dict())
    
    # Merge updates
    updates = req.dict(exclude_none=True)
    updated_data = {**existing, **updates}
    updated_data["metric"] = metric_name
    updated_data["updated_at"] = datetime.utcnow().isoformat()
    
    # Validate
    is_valid, errors = validator.validate(updated_data)
    if not is_valid:
        logger.warning(f"Validation failed for metric update {validated_name}: {errors}")
        raise HTTPException(status_code=400, detail=ValidationError("Metric validation failed", code="VALIDATION_ERROR", context={"errors": errors}).to_dict())

    # Build dimension_entity_map if dimensions or entity changed
    if updated_data.get("dimensions") and updated_data.get("entity"):
        from axi.query.reachability import SemanticReachability
        reachability = SemanticReachability(indexer)

        try:
            # Get reachability context for the entity
            entity_name = updated_data["entity"]
            context = reachability.plan_context([], [entity_name])

            # Build dimension -> entity mapping
            dimension_entity_map = {}
            for dim_name in updated_data["dimensions"]:
                # Find which entity this dimension belongs to
                for visible_dim in context.get("visible_dimensions", []):
                    if visible_dim["name"] == dim_name:
                        dimension_entity_map[dim_name] = visible_dim["entity"]
                        break

            # Store the mapping in updates if it has entries
            if dimension_entity_map:
                updates["dimension_entity_map"] = dimension_entity_map
                logger.debug(f"Built dimension_entity_map for {validated_name}: {dimension_entity_map}")
        except Exception as e:
            logger.warning(f"Failed to build dimension_entity_map: {e}")
            # Continue without the map - it's optional

    try:
        # Update metric
        updated = store.update(validated_name, updates)
        logger.info(f"Successfully updated metric: {validated_name}")
        
        # Rebuild metadata index
        indexer.build_index()
        
        return updated
    except ValueError as e:
        logger.warning(f"Validation error updating metric: {e}")
        raise HTTPException(status_code=400, detail=ValidationError(str(e), code="VALIDATION_ERROR").to_dict())
    except MetadataError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error updating metric: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to update metric: {e}", code="METRIC_UPDATE_ERROR").to_dict())

@router.delete("/{metric_name}")
def delete_metric(metric_name: str):
    """
    Delete a user-defined metric.
    """
    logger.info(f"Deleting metric: {metric_name}")
    # Validate metric name
    from axi.utils.sanitization import validate_metric_name
    try:
        validated_name = validate_metric_name(metric_name)
    except ValueError as ve:
        raise ValidationError(str(ve), code="INVALID_METRIC_NAME")
    
    store = _get_metric_store()
    indexer = _get_indexer()
    
    if not store.get(validated_name):
        raise HTTPException(status_code=404, detail=MetadataError(f"Metric '{validated_name}' not found", code="METRIC_NOT_FOUND").to_dict())
    
    try:
        store.delete(validated_name)
        logger.info(f"Successfully deleted metric: {validated_name}")
        
        # Rebuild metadata index
        indexer.build_index()
        
        return {"status": "deleted", "metric": validated_name}
    except HTTPException:
        raise
    except MetadataError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error deleting metric: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to delete metric: {e}", code="METRIC_DELETE_ERROR").to_dict())

@router.get("/{metric_name}/allowed-dimensions")
def get_allowed_dimensions(metric_name: str):
    """
    Get allowed dimensions for a metric based on grain.
    Returns: {"dimensions": ["dim1", "dim2", ...], "grain": ["grain1", ...]}
    """
    logger.debug(f"Getting allowed dimensions for metric: {metric_name}")
    # Validate metric name
    from axi.utils.sanitization import validate_metric_name
    try:
        validated_name = validate_metric_name(metric_name)
    except ValueError as ve:
        raise ValidationError(str(ve), code="INVALID_METRIC_NAME")
    
    indexer = _get_indexer()
    engine = SemanticQueryEngine(indexer)
    
    metric = indexer.get_metric(validated_name)
    if not metric:
        raise HTTPException(status_code=404, detail=MetadataError(f"Metric '{validated_name}' not found", code="METRIC_NOT_FOUND").to_dict())
    
    # Get effective grain
    entity = None
    entity_name = metric.get('entity_name')
    if entity_name:
        entity = indexer.get_entity(entity_name)
    
    effective_grain = engine.get_effective_grain(metric, entity)
    allowed_dims = engine.get_allowed_dimensions_for_metric(validated_name)
    
    return {
        "dimensions": allowed_dims,
        "grain": effective_grain,
        "metric": validated_name
    }
