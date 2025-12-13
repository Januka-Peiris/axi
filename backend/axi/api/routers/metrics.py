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
                m.description
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
                m.updated_at
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
            rows, columns = runner.execute_query(f"{sql} LIMIT {limit}")
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

