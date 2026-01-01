# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import sqlite3
import json
import hashlib
from axi.config.settings import get_settings
from axi.metadata.indexer import MetadataIndexer
from axi.utils.logging_config import get_logger
from axi.exceptions import DatabaseError, MetadataError, ValidationError

router = APIRouter(prefix="/api/dimensions", tags=["dimensions"])
settings = get_settings()
logger = get_logger(__name__)

def _get_indexer():
    return MetadataIndexer(settings.AXI_METADATA_DIR)

def _init_dimensions_tables(conn: sqlite3.Connection):
    """Initialize dimensions, metric_dimensions, and entity_dimensions tables if they don't exist."""
    c = conn.cursor()
    
    # Dimensions table - using INTEGER id for compatibility with frontend
    c.execute('''CREATE TABLE IF NOT EXISTS dimensions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        entity_name TEXT,
        data_type TEXT,
        cardinality INTEGER,
        is_primary BOOLEAN DEFAULT 0,
        description TEXT,
        source_table TEXT,
        source_column TEXT
    )''')
    
    # Metric-Dimension join table (using metric name, not id)
    c.execute('''CREATE TABLE IF NOT EXISTS metric_dimensions (
        metric_name TEXT,
        dimension_id INTEGER,
        PRIMARY KEY (metric_name, dimension_id),
        FOREIGN KEY(metric_name) REFERENCES metrics(name),
        FOREIGN KEY(dimension_id) REFERENCES dimensions(id)
    )''')
    
    # Entity-Dimension join table (using entity name, not id)
    c.execute('''CREATE TABLE IF NOT EXISTS entity_dimensions (
        entity_name TEXT,
        dimension_id INTEGER,
        PRIMARY KEY (entity_name, dimension_id),
        FOREIGN KEY(entity_name) REFERENCES entities(name),
        FOREIGN KEY(dimension_id) REFERENCES dimensions(id)
    )''')
    
    # Create indexes for faster lookups
    c.execute('''CREATE INDEX IF NOT EXISTS idx_dimensions_name ON dimensions(name)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_dimensions_entity_name ON dimensions(entity_name)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_metric_dimensions_dim_id ON metric_dimensions(dimension_id)''')
    c.execute('''CREATE INDEX IF NOT EXISTS idx_entity_dimensions_dim_id ON entity_dimensions(dimension_id)''')
    
    conn.commit()

def _populate_dimensions_from_metadata(conn: sqlite3.Connection):
    """
    Extract dimensions from existing models/metrics/entities and populate dimensions table.
    This runs once to bootstrap the dimensions table from existing metadata.
    """
    c = conn.cursor()
    
    # Always repopulate to ensure dimensions are up-to-date after extraction
    # Clear existing dimension relationships first
    c.execute('DELETE FROM metric_dimensions')
    c.execute('DELETE FROM entity_dimensions')
    
    # Get all models and their dimensions
    c.execute("SELECT name, dimensions FROM models")
    models = c.fetchall()
    
    # Get all entities
    c.execute("SELECT name, model, columns FROM entities")
    entities = c.fetchall()
    entity_map = {}
    for row in entities:
        try:
            columns = json.loads(row[2]) if row[2] else []
        except (json.JSONDecodeError, TypeError, ValueError):
            columns = []
        entity_map[row[0]] = {"model": row[1], "columns": columns}
    
    # Get all metrics and their dimensions
    c.execute("SELECT name, dimensions, model FROM metrics")
    metrics = c.fetchall()
    
    dimension_seen = {}  # name -> dimension_id
    
    # Process dimensions from models
    for model_row in models:
        model_name = model_row[0]
        dims_json = model_row[1]
        if not dims_json:
            continue
        
        try:
            dims = json.loads(dims_json) if isinstance(dims_json, str) else dims_json
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        
        # Find entity for this model
        entity_name = None
        for ent_name, ent_data in entity_map.items():
            if ent_data["model"] == model_name:
                entity_name = ent_name
                break
        
        for dim_name in dims:
            if isinstance(dim_name, dict):
                dim_name = dim_name.get("name", "")
            if not dim_name:
                continue
                
            if dim_name not in dimension_seen:
                # Infer data type from entity columns if available
                data_type = "TEXT"  # default
                is_primary = False
                source_column = dim_name
                
                if entity_name and entity_name in entity_map:
                    cols = entity_map[entity_name]["columns"]
                    for col in cols:
                        if isinstance(col, dict):
                            col_name = col.get("name", "")
                            if col_name == dim_name:
                                data_type = col.get("data_type", "TEXT")
                                is_primary = col.get("is_pk", False)
                                source_column = col.get("source_column", dim_name)
                                break
                        elif col == dim_name:
                            # Simple string match
                            break
                
                # Insert dimension
                c.execute('''INSERT OR IGNORE INTO dimensions 
                    (name, entity_name, data_type, is_primary, source_column, description)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (dim_name, entity_name, data_type, is_primary, source_column, None))
                
                c.execute("SELECT id FROM dimensions WHERE name = ?", (dim_name,))
                dim_id_row = c.fetchone()
                if dim_id_row:
                    dimension_seen[dim_name] = dim_id_row[0]
                    
                    # Link to entity
                    if entity_name:
                        c.execute('''INSERT OR IGNORE INTO entity_dimensions (entity_name, dimension_id)
                            VALUES (?, ?)''', (entity_name, dimension_seen[dim_name]))
    
    # Process dimensions from metrics
    for metric_row in metrics:
        metric_name = metric_row[0]
        dims_json = metric_row[1]
        if not dims_json:
            continue
        
        try:
            dims = json.loads(dims_json) if isinstance(dims_json, str) else dims_json
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        
        for dim_name in dims:
            # Handle both string dimensions and dict dimensions
            if isinstance(dim_name, dict):
                dim_name = dim_name.get("name", "")
            if not dim_name or not isinstance(dim_name, str):
                continue
                
            # Ensure dimension exists
            if dim_name not in dimension_seen:
                c.execute('''INSERT OR IGNORE INTO dimensions 
                    (name, data_type, description)
                    VALUES (?, ?, ?)''',
                    (dim_name, "TEXT", None))
                c.execute("SELECT id FROM dimensions WHERE name = ?", (dim_name,))
                dim_id_row = c.fetchone()
                if dim_id_row:
                    dimension_seen[dim_name] = dim_id_row[0]
            
            # Link metric to dimension
            if dim_name in dimension_seen:
                c.execute('''INSERT OR IGNORE INTO metric_dimensions (metric_name, dimension_id)
                    VALUES (?, ?)''', (metric_name, dimension_seen[dim_name]))
    
    conn.commit()

@router.get("")
def list_dimensions():
    """
    List all dimensions with entity information.
    Returns: List of dimensions with id, dimension_name, entity_name, data_type, cardinality, is_primary, description
    """
    try:
        indexer = _get_indexer()
        with indexer._get_conn() as conn:
            _init_dimensions_tables(conn)
            _populate_dimensions_from_metadata(conn)
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Query as specified in requirements
            query = """
            SELECT
                d.id,
                d.name AS dimension_name,
                d.entity_name AS entity_name,
                d.data_type,
                d.cardinality,
                d.is_primary,
                d.description
            FROM dimensions d
            ORDER BY d.entity_name, d.name
            """
            
            try:
                c.execute(query)
                rows = c.fetchall()
                result = [dict(row) for row in rows]
                return result
            except sqlite3.OperationalError as e:
                logger.warning(f"Database error listing dimensions: {e}")
                raise DatabaseError(f"Database error listing dimensions: {e}", code="DATABASE_ERROR")
    except DatabaseError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error listing dimensions: {e}")
        # Return empty list on any error to prevent 422
        return []

@router.get("/{dimension_id}")
def get_dimension(dimension_id: int):
    """
    Get a single dimension by ID.
    """
    logger.debug(f"Getting dimension: {dimension_id}")
    # Validate dimension_id
    if dimension_id < 1:
        raise ValidationError("Dimension ID must be positive", code="INVALID_DIMENSION_ID")
    
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_dimensions_tables(conn)
            _populate_dimensions_from_metadata(conn)
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = """
            SELECT
                d.id,
                d.name,
                d.entity_name AS entity_name,
                d.data_type,
                d.cardinality,
                d.is_primary,
                d.description
            FROM dimensions d
            WHERE d.id = ?
            """
            
            c.execute(query, (dimension_id,))
            row = c.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail=MetadataError(f"Dimension {dimension_id} not found", code="DIMENSION_NOT_FOUND").to_dict())
            
            return dict(row)
    except HTTPException:
        raise
    except DatabaseError as e:
        logger.warning(f"Database error getting dimension: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error getting dimension: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to get dimension: {e}", code="DIMENSION_GET_ERROR").to_dict())

@router.get("/{dimension_id}/metrics")
def get_dimension_metrics(dimension_id: int):
    """
    Get all metrics linked to a dimension.
    """
    logger.debug(f"Getting metrics for dimension: {dimension_id}")
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_dimensions_tables(conn)
            _populate_dimensions_from_metadata(conn)
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = """
            SELECT
                m.name,
                COALESCE(m.metric_type, m.aggregation, 'custom') AS type,
                m.description
            FROM metrics m
            JOIN metric_dimensions md ON md.metric_name = m.name
            WHERE md.dimension_id = ?
            """
            
            try:
                c.execute(query, (dimension_id,))
                rows = c.fetchall()
                # Add id field (using name as id for compatibility)
                result = []
                for row in rows:
                    row_dict = dict(row)
                    # Use a hash of name as id, or just use name
                    result.append({
                        "id": 0,  # Force frontend to use name for navigation
                        "name": row_dict["name"],
                        "type": row_dict["type"],
                        "description": row_dict.get("description")
                    })
                return result
            except sqlite3.OperationalError:
                return []
    except Exception as e:
        return []

@router.get("/{dimension_id}/entities")
def get_dimension_entities(dimension_id: int):
    """
    Get all entities linked to a dimension.
    """
    logger.debug(f"Getting entities for dimension: {dimension_id}")
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_dimensions_tables(conn)
            _populate_dimensions_from_metadata(conn)
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            query = """
            SELECT
                e.name
            FROM entities e
            JOIN entity_dimensions ed ON ed.entity_name = e.name
            WHERE ed.dimension_id = ?
            """
            
            try:
                c.execute(query, (dimension_id,))
                rows = c.fetchall()
                # Add id field (using name as id for compatibility)
                result = []
                for row in rows:
                    row_dict = dict(row)
                    # Use deterministic hash (hashlib instead of built-in hash which has random seed)
                    stable_id = int(hashlib.sha256(row_dict["name"].encode()).hexdigest()[:8], 16)
                    result.append({
                        "id": stable_id,
                        "name": row_dict["name"]
                    })
                return result
            except sqlite3.OperationalError:
                return []
    except Exception as e:
        return []

@router.get("/{dimension_id}/sample")
def get_dimension_samples(dimension_id: int, limit: int = 50):
    """
    Get sample values for a dimension from the warehouse.
    Returns first N values (default 50).
    """
    logger.debug(f"Getting samples for dimension: {dimension_id}, limit: {limit}")
    # Validate limit
    if limit < 1 or limit > 1000:
        raise ValidationError("Limit must be between 1 and 1000", code="INVALID_LIMIT")
    
    indexer = _get_indexer()
    try:
        with indexer._get_conn() as conn:
            _init_dimensions_tables(conn)
            _populate_dimensions_from_metadata(conn)
            
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Get dimension details
            c.execute("SELECT name, entity_name, source_table, source_column FROM dimensions WHERE id = ?", (dimension_id,))
            dim_row = c.fetchone()
            
            if not dim_row:
                raise HTTPException(status_code=404, detail=MetadataError(f"Dimension {dimension_id} not found", code="DIMENSION_NOT_FOUND").to_dict())
            
            dim_data = dict(dim_row)
            dim_name = dim_data['name']
            source_table = dim_data.get('source_table')
            source_column = dim_data.get('source_column') or dim_name
            entity_name = dim_data.get('entity_name')
            
            # Try to find source table from entity if not set
            if not source_table and entity_name:
                c.execute("SELECT model FROM entities WHERE name = ?", (entity_name,))
                entity_row = c.fetchone()
                if entity_row:
                    source_table = dict(entity_row).get('model')
        
        # If we have Snowflake connection, try to query actual values (outside connection context)
        try:
            from axi.execution.snowflake_runner import SnowflakeRunner
            runner = SnowflakeRunner()
            
            if source_table:
                # Use parameterized query to prevent SQL injection
                # Note: Table and column names need to be validated/sanitized
                # For now, basic validation
                # Sanitize table and column names
                from axi.utils.sanitization import sanitize_identifier
                try:
                    safe_table = sanitize_identifier(source_table)
                    safe_column = sanitize_identifier(source_column)
                except ValueError as ve:
                    raise ValidationError(str(ve), code="INVALID_IDENTIFIER")
                
                sql = f"SELECT DISTINCT {safe_column} as value FROM {safe_table} WHERE {safe_column} IS NOT NULL LIMIT {limit}"
                rows, _ = runner.execute_query(sql)
                logger.debug(f"Retrieved {len(rows)} sample values for dimension {dimension_id}")
                return [{"value": str(row.get("value", ""))} for row in rows]
            else:
                return []
        except ValueError:
            # If Snowflake is not configured, return empty
            logger.debug("Snowflake not configured for dimension samples")
            return []
        except Exception as e:
            logger.debug(f"Snowflake execution error for samples (non-fatal): {e}")
            return []
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except DatabaseError as e:
        logger.warning(f"Database error getting dimension samples: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error getting dimension samples: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to get dimension samples: {e}", code="DIMENSION_SAMPLES_ERROR").to_dict())
