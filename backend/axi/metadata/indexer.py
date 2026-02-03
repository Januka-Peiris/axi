# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import sqlite3
import os
import json
import glob
import time
import logging
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from axi.utils.logging_config import get_logger
from axi.config.settings import get_settings
from axi.config.loader import load_config
from axi.metadata.db import create_database_adapter, DatabaseAdapter
from axi.metadata.db.sqlite_adapter import SQLiteAdapter

logger = get_logger(__name__)

class MetadataIndexer:
    def __init__(self, metadata_dir: str, db_adapter: Optional[DatabaseAdapter] = None):
        # metadata_dir is base dir (e.g. metadata_store)
        # We need to find models in metadata_dir/models/*.json
        self.metadata_dir = metadata_dir
        try:
            os.makedirs(self.metadata_dir, exist_ok=True)
        except Exception:
            # Best effort; open will fail later with a clearer path if not writable
            pass
        
        # Initialize database adapter
        if db_adapter:
            self.db = db_adapter
        else:
            self.db = self._create_db_adapter()
        
        self._init_db()
    
    def _create_db_adapter(self) -> DatabaseAdapter:
        """Create database adapter based on configuration."""
        settings = get_settings()

        # Try project config first, then fall back to settings
        try:
            config = load_config()
            if config.database:
                db_config = config.database
                return create_database_adapter(
                    db_type=db_config.db_type,
                    db_url=db_config.db_url,
                    db_host=db_config.db_host,
                    db_port=db_config.db_port,
                    db_name=db_config.db_name,
                    db_user=db_config.db_user,
                    db_password=db_config.get_password(),
                    db_schema=db_config.db_schema
                )
        except Exception:
            pass

        # Fall back to settings or default SQLite
        if settings.db_type == "postgres":
            return create_database_adapter(
                db_type="postgres",
                db_url=settings.db_url,
                db_host=settings.db_host,
                db_port=settings.db_port,
                db_name=settings.db_name,
                db_user=settings.db_user,
                db_password=settings.db_password,
                db_schema=getattr(settings, 'db_schema', None)
            )
        else:
            # Default to SQLite
            db_path = os.path.join(self.metadata_dir, "axi.db")
            return create_database_adapter(db_type="sqlite", db_path=db_path)
    
    def _get_conn(self):
        """
        Get database connection for backward compatibility with router code.
        Returns a context manager that provides the underlying connection.
        For SQLite, returns the sqlite3 connection wrapped in a context manager.
        For PostgreSQL, this method should not be used - use self.db directly.
        """
        if isinstance(self.db, SQLiteAdapter):
            # Return a context manager that provides the sqlite3 connection
            from contextlib import contextmanager
            @contextmanager
            def conn_manager():
                if self.db.conn is None:
                    self.db._connect()
                yield self.db.conn
            return conn_manager()
        else:
            # For PostgreSQL, routers should use self.db directly
            # But for backward compatibility, return a dummy context manager
            from contextlib import nullcontext
            logger.warning("_get_conn() called on non-SQLite adapter. Routers should use indexer.db directly.")
            return nullcontext(self.db)

    def _init_db(self):
        """Initialize database schema."""
        # Metrics Table
        self.db.execute('''CREATE TABLE IF NOT EXISTS metrics (
            name TEXT PRIMARY KEY,
            expression TEXT,
            model TEXT,
            grain TEXT,
            dimensions TEXT,
            filters TEXT,
            source_table TEXT,
            metric_type TEXT,
            aggregation TEXT,
            default_dimensions TEXT,
            default_filter TEXT,
            time_dimension TEXT,
            depends_on TEXT,
            numerator TEXT,
            denominator TEXT,
            semi_additive_method TEXT,
            semi_additive_dimension TEXT,
            tags TEXT,
            description TEXT,
            entity_name TEXT,
            dimension_entity_map TEXT
        )''')
        
        # Ensure column exists (migration) - SQLite specific
        if isinstance(self.db, SQLiteAdapter):
            try:
                result = self.db.fetchall("PRAGMA table_info(metrics)")
                m_cols = [row[1] for row in result] if result else []
                def _add_col(col_name: str):
                    if col_name not in m_cols:
                        self.db.execute(f"ALTER TABLE metrics ADD COLUMN {col_name} TEXT")
                _add_col("entity_name")
                _add_col("dimension_entity_map")
                _add_col("version")
                _add_col("status")
                _add_col("deprecation_date")
                _add_col("replacement_metric")
            except Exception:
                pass
        
        # Models Table
        self.db.execute('''CREATE TABLE IF NOT EXISTS models (
            name TEXT PRIMARY KEY,
            path TEXT,
            source_tables TEXT,
            dimensions TEXT
        )''')
        
        # Entities Table
        self.db.execute('''CREATE TABLE IF NOT EXISTS entities (
            name TEXT PRIMARY KEY,
            model TEXT,
            primary_key TEXT,
            columns TEXT
        )''')
        
        # Safe migrations for new columns - SQLite specific
        if isinstance(self.db, SQLiteAdapter):
            try:
                result = self.db.fetchall("PRAGMA table_info(entities)")
                cols = [row[1] for row in result] if result else []
                def _add_col(col_sql, name):
                    if name not in cols:
                        try:
                            self.db.execute(col_sql)
                        except Exception:
                            pass
                _add_col("ALTER TABLE entities ADD COLUMN type TEXT", "type")
                _add_col("ALTER TABLE entities ADD COLUMN is_read_only BOOLEAN", "is_read_only")
                _add_col("ALTER TABLE entities ADD COLUMN is_staging BOOLEAN", "is_staging")
                _add_col("ALTER TABLE entities ADD COLUMN physical_location TEXT", "physical_location")
                _add_col("ALTER TABLE entities ADD COLUMN source_name TEXT", "source_name")
                _add_col("ALTER TABLE entities ADD COLUMN schema_name TEXT", "schema_name")
                _add_col("ALTER TABLE entities ADD COLUMN database_name TEXT", "database_name")
            except Exception:
                pass
        
        # Relationships Table
        self.db.execute('''CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_model TEXT,
            child_model TEXT,
            fk_column TEXT,
            pk_column TEXT,
            join_type TEXT
        )''')
        
        # Snowflake Tables
        self.db.execute('''CREATE TABLE IF NOT EXISTS sf_tables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            database TEXT,
            schema TEXT,
            name TEXT,
            type TEXT,
            comment TEXT,
            created_at TEXT,
            last_altered TEXT,
            synced_at TEXT
        )''')
        
        self.db.execute('''CREATE TABLE IF NOT EXISTS sf_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            name TEXT,
            type TEXT,
            nullable BOOLEAN,
            default_val TEXT,
            comment TEXT,
            ordinal INTEGER,
            tags TEXT,
            FOREIGN KEY(table_id) REFERENCES sf_tables(id)
        )''')
        
        self.db.execute('''CREATE TABLE IF NOT EXISTS sf_constraints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            type TEXT,
            columns TEXT,
            referenced_table TEXT,
            referenced_columns TEXT,
            FOREIGN KEY(table_id) REFERENCES sf_tables(id)
        )''')

        self.db.execute('''CREATE TABLE IF NOT EXISTS sf_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            value TEXT,
            level TEXT,
            object_name TEXT
        )''')
        
        self.db.execute('''CREATE TABLE IF NOT EXISTS sf_masking_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            schema TEXT,
            table_name TEXT,
            column_name TEXT,
            body TEXT
        )''')
        
        self.db.execute('''CREATE TABLE IF NOT EXISTS sf_row_access_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            schema TEXT,
            table_name TEXT,
            body TEXT
        )''')
        
        self.db.execute('''CREATE TABLE IF NOT EXISTS sf_lineage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upstream_table TEXT,
            downstream_table TEXT,
            type TEXT
        )''')

        # dbt Tables
        self.db.execute('''CREATE TABLE IF NOT EXISTS dbt_models (
            model_name TEXT PRIMARY KEY,
            resource_type TEXT,
            database TEXT,
            schema TEXT,
            alias TEXT,
            relation_name TEXT,
            materialization TEXT,
            path TEXT,
            tags TEXT,
            description TEXT,
            depends_on TEXT
        )''')

        self.db.execute('''CREATE TABLE IF NOT EXISTS dbt_sources (
            unique_id TEXT PRIMARY KEY,
            source_name TEXT,
            table_name TEXT,
            database TEXT,
            schema TEXT,
            relation_name TEXT,
            freshness TEXT,
            tags TEXT,
            description TEXT
        )''')

        self.db.execute('''CREATE TABLE IF NOT EXISTS dbt_tests (
            test_name TEXT PRIMARY KEY,
            test_type TEXT,
            model_name TEXT,
            column_name TEXT,
            severity TEXT,
            config TEXT
        )''')

        self.db.execute('''CREATE TABLE IF NOT EXISTS axi_constraints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT,
            column_name TEXT,
            constraint_type TEXT,
            details TEXT
        )''')
        
        # Cache & Materialization
        self.db.execute('''CREATE TABLE IF NOT EXISTS cache_entries (
            cache_key TEXT PRIMARY KEY,
            metric TEXT,
            dimensions TEXT,
            filters TEXT,
            sql TEXT,
            created_at REAL,
            expires_at REAL,
            row_count INTEGER,
            storage_location TEXT
        )''')

        self.db.execute('''CREATE TABLE IF NOT EXISTS materializations (
            table_name TEXT PRIMARY KEY,
            metric TEXT,
            dimensions TEXT,
            refresh_mode TEXT,
            last_refresh_at REAL,
            row_count INTEGER,
            warehouse_location TEXT
        )''')

        self.db.execute('''CREATE TABLE IF NOT EXISTS semantic_marts (
            mart_name TEXT PRIMARY KEY,
            metrics TEXT,
            dimensions TEXT,
            table_name TEXT,
            last_refresh_at REAL
        )''')
        
        # Dimensions Table - for dimension browser UI
        self.db.execute('''CREATE TABLE IF NOT EXISTS dimensions (
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
        self.db.execute('''CREATE TABLE IF NOT EXISTS metric_dimensions (
            metric_name TEXT,
            dimension_id INTEGER,
            PRIMARY KEY (metric_name, dimension_id),
            FOREIGN KEY(metric_name) REFERENCES metrics(name),
            FOREIGN KEY(dimension_id) REFERENCES dimensions(id)
        )''')
        
        # Entity-Dimension join table (using entity name, not id)
        self.db.execute('''CREATE TABLE IF NOT EXISTS entity_dimensions (
            entity_name TEXT,
            dimension_id INTEGER,
            PRIMARY KEY (entity_name, dimension_id),
            FOREIGN KEY(entity_name) REFERENCES entities(name),
            FOREIGN KEY(dimension_id) REFERENCES dimensions(id)
        )''')
        
        # Promotion Results Table
        self.db.execute('''CREATE TABLE IF NOT EXISTS promotion_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            type TEXT,
            source TEXT,
            status TEXT NOT NULL,
            reason TEXT,
            matched_rule TEXT,
            error_message TEXT,
            entity_created BOOLEAN DEFAULT 0,
            dimensions_count INTEGER DEFAULT 0,
            metrics_count INTEGER DEFAULT 0,
            scanned_at TEXT,
            UNIQUE(name, path)
        )''')

        # Deployed Views (governed semantic views)
        self.db.execute('''CREATE TABLE IF NOT EXISTS deployed_views (
            view_name TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            metric_version TEXT NOT NULL,
            schema_name TEXT NOT NULL,
            deployed_at_utc TEXT NOT NULL,
            deprecated INTEGER NOT NULL DEFAULT 0,
            definition_hash TEXT
        )''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_deployed_views_metric ON deployed_views(metric_name)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_deployed_views_deprecated ON deployed_views(deprecated)''')

        # Query usage tracking: AXI SQL fingerprints (for matching warehouse query logs)
        self.db.execute('''CREATE TABLE IF NOT EXISTS axi_sql_fingerprints (
            fingerprint TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            metric_version TEXT NOT NULL,
            deprecated INTEGER NOT NULL DEFAULT 0,
            first_seen_utc TEXT
        )''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_axi_sql_fingerprints_metric ON axi_sql_fingerprints(metric_name)''')

        # Usage aggregation: metric_name, version, date -> counts (no PII)
        self.db.execute('''CREATE TABLE IF NOT EXISTS metric_usage (
            metric_name TEXT NOT NULL,
            metric_version TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0,
            deprecated_access_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (metric_name, metric_version, usage_date)
        )''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_metric_usage_metric ON metric_usage(metric_name)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_metric_usage_date ON metric_usage(usage_date)''')

        # Metric version history (append-only; never overwrite)
        self.db.execute('''CREATE TABLE IF NOT EXISTS metric_version_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            version TEXT NOT NULL,
            definition_snapshot TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            deprecated_at TEXT,
            replacement_metric TEXT
        )''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_metric_version_history_name ON metric_version_history(metric_name)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_metric_version_history_created ON metric_version_history(created_at DESC)''')

        # Create indexes for faster lookups
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_dimensions_name ON dimensions(name)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_dimensions_entity_name ON dimensions(entity_name)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_metric_dimensions_dim_id ON metric_dimensions(dimension_id)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_entity_dimensions_dim_id ON entity_dimensions(dimension_id)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_promotion_results_status ON promotion_results(status)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_promotion_results_name ON promotion_results(name)''')
        
        # Additional indexes for query optimization
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_metrics_entity_name ON metrics(entity_name)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_metrics_model ON metrics(model)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_entities_model ON entities(model)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_relationships_parent ON relationships(parent_model)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_relationships_child ON relationships(child_model)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_metric_dimensions_metric_name ON metric_dimensions(metric_name)''')
        self.db.execute('''CREATE INDEX IF NOT EXISTS idx_entity_dimensions_entity_name ON entity_dimensions(entity_name)''')

    def build_index(self):
        """
        Scans JSON files in <metadata_dir>/models/ and YAML files in axi/metrics/ and repopulates the index.
        Uses transactions for better performance and atomicity.
        """
        logger.info("Starting index rebuild")
        start_time = time.time()
        
        try:
            # Use transaction for atomicity
            self.db.begin_transaction()
            
            # Clear existing
            logger.debug("Clearing existing index data")
            self.db.execute('DELETE FROM metrics')
            self.db.execute('DELETE FROM models')
            self.db.execute('DELETE FROM entities')
            self.db.execute('DELETE FROM relationships')
            
            indexed_count = 0
            error_count = 0
            
            # Index extracted models from JSON files
            models_dir = os.path.join(self.metadata_dir, "models")
            if os.path.exists(models_dir):
                model_files = sorted(glob.glob(os.path.join(models_dir, "*.json")))
                logger.info(f"Found {len(model_files)} model files to index")
                for fpath in model_files:
                    try:
                        logger.debug(f"Indexing model file: {fpath}")
                        with open(fpath, "r") as f:
                            data = json.load(f)
                        self._index_model(data)
                        indexed_count += 1
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in {fpath}: {e}")
                        error_count += 1
                    except Exception as e:
                        logger.error(f"Error indexing {fpath}: {e}")
                        error_count += 1
            
            # Index user-defined metrics from YAML files
            logger.debug("Indexing user-defined metrics")
            self._index_user_defined_metrics()
            
            # Merge manifest-defined relationships (dbt dependencies) for graph completeness
            self._merge_manifest_relationships()
            
            # Populate dimensions table from indexed models
            logger.debug("Populating dimensions")
            self._populate_dimensions()
            
            # Commit transaction
            self.db.commit()
            
            elapsed = time.time() - start_time
            logger.info(f"Index rebuild completed in {elapsed:.2f}s. Indexed {indexed_count} models, {error_count} errors")
        except Exception as e:
            # Rollback on error
            self.db.rollback()
            logger.error(f"Error during index rebuild, rolling back: {e}")
            raise
    
    def _index_user_defined_metrics(self):
        """
        Load user-defined metrics from axi/metrics/*.yml files and index them.
        """
        import yaml
        
        # Find project root
        project_root = None
        current = os.path.dirname(self.metadata_dir) if self.metadata_dir else os.getcwd()
        while current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, "axi.yml")):
                project_root = current
                break
            current = os.path.dirname(current)
        
        if not project_root:
            # Fallback: try relative to metadata_dir
            project_root = os.path.dirname(self.metadata_dir) if self.metadata_dir else os.getcwd()
        
        metrics_dir = os.path.join(project_root, "axi", "metrics")
        if not os.path.exists(metrics_dir):
            return
        
        # Load entity model mappings first (need to query DB)
        entity_model_map = {}
        rows = self.db.fetchall('SELECT name, model FROM entities')
        for row in rows:
            entity_model_map[row[0]] = row[1]
        
        # Load all YAML metric files
        for fpath in sorted(glob.glob(os.path.join(metrics_dir, "*.yml")) + glob.glob(os.path.join(metrics_dir, "*.yaml"))):
            try:
                with open(fpath, "r") as f:
                    metric_data = yaml.safe_load(f)
                    if not metric_data:
                        continue
                    
                # Convert YAML format to index format
                m_name = metric_data.get("metric")
                if not m_name:
                    continue
                
                entity_name = metric_data.get("entity", "")
                expr = metric_data.get("expression", "")
                
                # Robust grain handling - use adapter's serialize_json for consistency
                raw_grain = metric_data.get("grain", [])
                if raw_grain and not isinstance(raw_grain, list):
                     # If string, wrap in list for consistency before serializing
                     grain = self.db.serialize_json([raw_grain])
                elif not raw_grain:
                     grain = "[]"
                else:
                     grain = self.db.serialize_json(raw_grain)

                dims = metric_data.get("dimensions", [])
                tags = metric_data.get("tags", [])
                desc = metric_data.get("description", "")
                m_type = metric_data.get("type", "custom")
                depends_on = metric_data.get("depends_on", [])
                dimension_entity_map = metric_data.get("dimension_entity_map", {})

                # Get entity's model name from pre-loaded map
                model_name = entity_model_map.get(entity_name) if entity_name else None

                # Versioning: explicit defaults for user-defined metrics
                metric_version = metric_data.get("version") or "1.0"
                metric_status = metric_data.get("status") or "active"
                deprecation_date = metric_data.get("deprecation_date") or None
                replacement_metric = metric_data.get("replacement_metric") or None

                self.db.insert_or_replace('metrics', {
                    'name': m_name,
                    'expression': expr,
                    'model': model_name,
                    'grain': grain,
                    'dimensions': self.db.serialize_json(dims),
                    'filters': self.db.serialize_json([]),
                    'source_table': "",
                    'metric_type': m_type,
                    'aggregation': m_type,
                    'default_dimensions': self.db.serialize_json(dims),
                    'default_filter': "",
                    'time_dimension': "",
                    'depends_on': self.db.serialize_json(depends_on),
                    'numerator': "",
                    'denominator': "",
                    'semi_additive_method': "",
                    'semi_additive_dimension': "",
                    'tags': self.db.serialize_json(tags),
                    'description': desc,
                    'entity_name': entity_name,
                    'dimension_entity_map': self.db.serialize_json(dimension_entity_map),
                    'version': metric_version,
                    'status': metric_status,
                    'deprecation_date': deprecation_date,
                    'replacement_metric': replacement_metric,
                })
            except Exception as e:
                # Log error but continue processing other metrics
                logger.warning(f"Failed to index metric from {fpath}: {e}")
                continue

    def _populate_dimensions(self):
        """
        Extract dimensions from indexed models/metrics/entities and populate dimensions table.
        This runs after build_index() to ensure dimensions are available.
        """
        # Clear existing dimension relationships (but keep dimensions themselves for now)
        # We'll repopulate all relationships
        self.db.execute('DELETE FROM metric_dimensions')
        self.db.execute('DELETE FROM entity_dimensions')
        
        # Optimize: Use single query with JOIN instead of multiple queries
        # Get all models, entities, and metrics in optimized queries
        models = self.db.fetchall("SELECT name, dimensions FROM models")
        
        # Get all entities with columns
        entities = self.db.fetchall("SELECT name, model, columns FROM entities")
        entity_map = {}
        for row in entities:
            try:
                columns_json = row[2] if len(row) > 2 else None
                columns = self.db.deserialize_json(columns_json) if columns_json else []
            except (json.JSONDecodeError, TypeError, ValueError):
                columns = []
            entity_map[row[0]] = {"model": row[1], "columns": columns}
        
        # Get all metrics and their dimensions
        metrics = self.db.fetchall("SELECT name, dimensions, model FROM metrics")
        
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
                # Handle both string dimensions and dict dimensions
                included = True
                if isinstance(dim_name, dict):
                    included = dim_name.get("included", True)
                    dim_name = dim_name.get("name", "")
                if not included:
                    continue
                if not dim_name or not isinstance(dim_name, str):
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
                    
                    # Insert dimension (use INSERT OR IGNORE to avoid duplicates)
                    # For SQLite: INSERT OR IGNORE, for PostgreSQL: use adapter's insert_or_replace
                    if isinstance(self.db, SQLiteAdapter):
                        self.db.execute('''INSERT OR IGNORE INTO dimensions 
                            (name, entity_name, data_type, is_primary, source_column, description)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                            (dim_name, entity_name, data_type, is_primary, source_column, None))
                    else:
                        # PostgreSQL: use insert_or_replace with ON CONFLICT
                        self.db.insert_or_replace('dimensions', {
                            'name': dim_name,
                            'entity_name': entity_name,
                            'data_type': data_type,
                            'is_primary': is_primary,
                            'source_column': source_column,
                            'description': None
                        })
                    
                    # Get dimension ID (use lastrowid if available, otherwise query)
                    dim_id = self.db.lastrowid()
                    if dim_id:
                        dimension_seen[dim_name] = dim_id
                    else:
                        dim_id_row = self.db.fetchone("SELECT id FROM dimensions WHERE name = ?", (dim_name,))
                        if dim_id_row:
                            dimension_seen[dim_name] = dim_id_row[0]
                    
                    # Link to entity
                    if entity_name and dim_name in dimension_seen:
                        if isinstance(self.db, SQLiteAdapter):
                            self.db.execute('''INSERT OR IGNORE INTO entity_dimensions (entity_name, dimension_id)
                                VALUES (?, ?)''', (entity_name, dimension_seen[dim_name]))
                        else:
                            self.db.insert_or_replace('entity_dimensions', {
                                'entity_name': entity_name,
                                'dimension_id': dimension_seen[dim_name]
                            })
        
        # Process dimensions from metrics
        for metric_row in metrics:
            metric_name = metric_row[0]
            dims_json = metric_row[1]
            if not dims_json:
                continue
            
            try:
                dims = self.db.deserialize_json(dims_json)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            
            for dim_name in dims:
                if isinstance(dim_name, dict):
                    dim_name = dim_name.get("name", "")
                if not dim_name or not isinstance(dim_name, str):
                    continue
                    
                # Ensure dimension exists
                if dim_name not in dimension_seen:
                    if isinstance(self.db, SQLiteAdapter):
                        self.db.execute('''INSERT OR IGNORE INTO dimensions 
                            (name, data_type, description)
                            VALUES (?, ?, ?)''',
                            (dim_name, "TEXT", None))
                    else:
                        self.db.insert_or_replace('dimensions', {
                            'name': dim_name,
                            'data_type': "TEXT",
                            'description': None
                        })
                    # Get dimension ID
                    dim_id = self.db.lastrowid()
                    if dim_id:
                        dimension_seen[dim_name] = dim_id
                    else:
                        dim_id_row = self.db.fetchone("SELECT id FROM dimensions WHERE name = ?", (dim_name,))
                        if dim_id_row:
                            dimension_seen[dim_name] = dim_id_row[0]
                
                # Link metric to dimension
                if dim_name in dimension_seen:
                    if isinstance(self.db, SQLiteAdapter):
                        self.db.execute('''INSERT OR IGNORE INTO metric_dimensions (metric_name, dimension_id)
                            VALUES (?, ?)''', (metric_name, dimension_seen[dim_name]))
                    else:
                        self.db.insert_or_replace('metric_dimensions', {
                            'metric_name': metric_name,
                            'dimension_id': dimension_seen[dim_name]
                        })

    def _merge_manifest_relationships(self) -> None:
        """
        Merge dependency edges from dbt manifest (dbt_models.depends_on) into relationships.
        These edges provide graph connectivity even when join keys are unknown.
        """
        try:
            existing = set(
                (row[0], row[1], row[2], row[3])
                for row in self.db.fetchall("SELECT parent_model, child_model, fk_column, pk_column FROM relationships")
            )
            existing_pairs = set(
                (row[0], row[1])
                for row in self.db.fetchall("SELECT parent_model, child_model FROM relationships")
            )
            manifest_rows = self.db.fetchall("SELECT model_name, depends_on FROM dbt_models")
            added = 0
            for row in manifest_rows:
                model_name = row[0]
                deps_raw = row[1]
                if not model_name or deps_raw is None:
                    continue
                try:
                    deps = self.db.deserialize_json(deps_raw) if hasattr(self.db, "deserialize_json") else json.loads(deps_raw)
                except Exception:
                    deps = []
                if not isinstance(deps, list):
                    continue
                for dep in deps:
                    if not dep or not isinstance(dep, str):
                        continue
                    # dbt nodes are like model.project.name or source.project.table
                    dep_name = dep.split(".")[-1]
                    if not dep_name or dep_name == model_name:
                        continue
                    edge = (dep_name, model_name, "", "")
                    edge_pair = (dep_name, model_name)
                    if edge in existing or edge_pair in existing_pairs:
                        continue
                    self.db.insert_or_replace('relationships', {
                        'parent_model': dep_name,
                        'child_model': model_name,
                        'fk_column': "",
                        'pk_column': "",
                        'join_type': "DEPENDS_ON"
                    })
                    existing.add(edge)
                    existing_pairs.add(edge_pair)
                    added += 1
            if added:
                logger.debug(f"Added {added} manifest-derived relationships")
        except Exception as exc:
            logger.warning(f"Failed to merge manifest relationships: {exc}")

    def _index_model(self, data: Dict[str, Any]):
        model_name = data.get("model")
        source_tables = data.get("source_tables", [])
        dimensions = data.get("dimensions", [])
        
        # Insert Model
        self.db.insert_or_replace('models', {
            'name': model_name,
            'path': "",
            'source_tables': self.db.serialize_json(source_tables),
            'dimensions': self.db.serialize_json(dimensions)
        })
        
        # Insert Entity
        entity = data.get("entity", {})
        if entity:
            # Serialize primary_key if it's a list
            pk = entity.get("pk")
            if isinstance(pk, list):
                pk = self.db.serialize_json(pk)
            elif pk is None:
                pk = None
            
            self.db.insert_or_replace('entities', {
                'name': entity.get("name", model_name),
                'model': model_name,
                'primary_key': pk,
                'columns': self.db.serialize_json(entity.get("columns", []))
            })
                           
        # Insert Relationships
        relationships = data.get("relationships", [])
        for rel in relationships:
            self.db.execute('INSERT INTO relationships (parent_model, child_model, fk_column, pk_column, join_type) VALUES (?, ?, ?, ?, ?)',
                           (rel.get("parent_model"), rel.get("child_model"), rel.get("fk_column"), rel.get("pk_column"), rel.get("join_type")))

        # Insert Metrics
        for metric in data.get("metrics", []):
            m_name = metric.get("name")
            expr = metric.get("expression")
            grain = metric.get("grain")
            
            # Model-wide dims/filters
            dims = data.get("dimensions", [])
            filters = data.get("filters", [])
            
            # Use model name as source table (CTEs are intermediate, model is the actual table)
            # If metric has explicit source_table, use it, otherwise use model name
            src_table = metric.get("source_table") or metric.get("model") or (source_tables[0] if source_tables else "")
            
            # Extended fields
            m_type = metric.get("metric_type", "aggregate")
            agg = metric.get("aggregation", "")
            def_dims = metric.get("default_dimensions", [])
            def_filt = metric.get("default_filter", "")
            time_dim = metric.get("time_dimension", "")
            deps = metric.get("depends_on", [])
            num = metric.get("numerator", "")
            denom = metric.get("denominator", "")
            sa_method = metric.get("semi_additive_method", "")
            sa_dim = metric.get("semi_additive_dimension", "")
            tags = metric.get("tags", [])
            desc = metric.get("description", "")

            # Normalize list fields before insert to avoid binding list params
            if isinstance(grain, list):
                grain = self.db.serialize_json(grain)
            grain_json = grain if isinstance(grain, str) else self.db.serialize_json(grain)
            dims_json = self.db.serialize_json(dims or [])
            filters_json = self.db.serialize_json(filters or [])
            def_dims_json = self.db.serialize_json(def_dims or [])
            deps_json = self.db.serialize_json(deps or [])
            tags_json = self.db.serialize_json(tags or [])
            def_filter_json = (
                def_filt if not isinstance(def_filt, (list, dict)) else self.db.serialize_json(def_filt)
            )
            
            logger.debug(f"Indexing metric {m_name}, grain type: {type(grain)}")
            
            
            # Versioning: explicit version and status; defaults for new metrics
            metric_version = metric.get("version") or "1.0"
            metric_status = metric.get("status") or "active"
            deprecation_date = metric.get("deprecation_date") or None
            replacement_metric = metric.get("replacement_metric") or None

            self.db.insert_or_replace('metrics', {
                'name': m_name,
                'expression': expr,
                'model': model_name,
                'grain': grain_json,
                'dimensions': dims_json,
                'filters': filters_json,
                'source_table': src_table,
                'metric_type': m_type,
                'aggregation': agg,
                'default_dimensions': def_dims_json,
                'default_filter': def_filter_json,
                'time_dimension': time_dim,
                'depends_on': deps_json,
                'numerator': num,
                'denominator': denom,
                'semi_additive_method': sa_method,
                'semi_additive_dimension': sa_dim,
                'tags': tags_json,
                'description': desc,
                'entity_name': entity.get("name", model_name) if entity else model_name,
                'version': metric_version,
                'status': metric_status,
                'deprecation_date': deprecation_date,
                'replacement_metric': replacement_metric,
            })

    def list_metrics(self) -> List[Dict[str, Any]]:
        rows = self.db.fetchall('SELECT * FROM metrics')
        if not rows:
            return []
        # Get column names - for now use fixed list, adapter should provide this
        cols = ['name', 'expression', 'model', 'grain', 'dimensions', 'filters', 'source_table',
                'metric_type', 'aggregation', 'default_dimensions', 'default_filter', 'time_dimension',
                'depends_on', 'numerator', 'denominator', 'semi_additive_method', 'semi_additive_dimension',
                'tags', 'description', 'entity_name', 'dimension_entity_map',
                'version', 'status', 'deprecation_date', 'replacement_metric']
        result = []
        for row in rows:
            # Pad row for backwards compatibility (DB may have fewer columns before migration)
            row_padded = tuple(row) + (None,) * max(0, len(cols) - len(row))
            d = dict(zip(cols, row_padded))
            # Deserialize JSON fields
            for json_field in ['dimensions', 'filters', 'default_dimensions', 'depends_on', 'tags', 'grain', 'dimension_entity_map']:
                if json_field in d:
                    d[json_field] = self.db.deserialize_json(d[json_field])
            # Default versioning fields if missing
            if d.get('version') is None:
                d['version'] = '1.0'
            if d.get('status') is None:
                d['status'] = 'active'
            result.append(d)
        return result

    def get_metric(self, name: str) -> Optional[Dict[str, Any]]:
        row = self.db.fetchone('SELECT * FROM metrics WHERE name = ?', (name,))
        if not row:
            return None
        cols = ['name', 'expression', 'model', 'grain', 'dimensions', 'filters', 'source_table',
                'metric_type', 'aggregation', 'default_dimensions', 'default_filter', 'time_dimension',
                'depends_on', 'numerator', 'denominator', 'semi_additive_method', 'semi_additive_dimension',
                'tags', 'description', 'entity_name', 'dimension_entity_map',
                'version', 'status', 'deprecation_date', 'replacement_metric']
        row_padded = tuple(row) + (None,) * max(0, len(cols) - len(row))
        d = dict(zip(cols, row_padded))
        # Deserialize JSON fields
        for json_field in ['dimensions', 'filters', 'default_dimensions', 'depends_on', 'tags', 'grain', 'dimension_entity_map']:
            if json_field in d:
                d[json_field] = self.db.deserialize_json(d[json_field])
        if d.get('version') is None:
            d['version'] = '1.0'
        if d.get('status') is None:
            d['status'] = 'active'
        return d

    def update_metric_version_status(
        self,
        name: str,
        version: Optional[str] = None,
        status: Optional[str] = None,
        deprecation_date: Optional[str] = None,
        replacement_metric: Optional[str] = None,
    ) -> None:
        """Update version, status, deprecation_date, or replacement_metric for a metric.
        Persists a new version record to metric_version_history before updating; never overwrites history.
        """
        existing = self.get_metric(name)
        if not existing:
            raise ValueError(f"Metric '{name}' not found")
        updates = []
        params = []
        if version is not None:
            updates.append("version = ?")
            params.append(version)
        if status is not None:
            if status not in ("active", "deprecated", "disabled"):
                raise ValueError("status must be active, deprecated, or disabled")
            updates.append("status = ?")
            params.append(status)
        if deprecation_date is not None:
            updates.append("deprecation_date = ?")
            params.append(deprecation_date)
        if replacement_metric is not None:
            updates.append("replacement_metric = ?")
            params.append(replacement_metric)
        if not updates:
            return
        created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record_version = version if version is not None else (existing.get("version") or "1.0")
        record_status = status if status is not None else (existing.get("status") or "active")
        deprecated_at_val = None
        if record_status == "deprecated":
            deprecated_at_val = deprecation_date or created_at[:10]
        replacement_val = replacement_metric if replacement_metric is not None else existing.get("replacement_metric")
        self.append_metric_version_history(
            metric_name=name,
            version=record_version,
            definition_snapshot=existing,
            status=record_status,
            created_at=created_at,
            deprecated_at=deprecated_at_val,
            replacement_metric=replacement_val,
        )
        params.append(name)
        sql = f"UPDATE metrics SET {', '.join(updates)} WHERE name = ?"
        self.db.execute(sql, tuple(params))
        self.db.commit()

    def list_models(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM models')
            rows = c.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                d['dimensions'] = json.loads(d['dimensions']) if d['dimensions'] else []
                d['source_tables'] = json.loads(d['source_tables']) if d['source_tables'] else []
                results.append(d)
            return results
        
    def list_entities(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM entities')
            rows = c.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                if d.get('columns'):
                    try:
                        d['columns'] = json.loads(d['columns']) if isinstance(d['columns'], str) else d['columns']
                    except (json.JSONDecodeError, TypeError, ValueError):
                        d['columns'] = []
                else:
                    d['columns'] = []
                # Normalize booleans
                d['is_read_only'] = bool(d.get('is_read_only'))
                d['is_staging'] = bool(d.get('is_staging'))
                results.append(d)
            return results
        
    def list_relationships(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM relationships')
            rows = c.fetchall()
            return [dict(row) for row in rows]
        
    def get_model(self, name: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM models WHERE name = ?', (name,))
            row = c.fetchone()
            if row:
                d = dict(row)
                d['source_tables'] = json.loads(d['source_tables']) if d['source_tables'] else []
                d['dimensions'] = json.loads(d['dimensions']) if d['dimensions'] else []
                return d
            return None
    
    def get_entity(self, name: str) -> Optional[Dict[str, Any]]:
        """Get entity by name."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM entities WHERE name = ?', (name,))
            row = c.fetchone()
            if row:
                d = dict(row)
                # Parse JSON columns
                if d.get('columns'):
                    try:
                        d['columns'] = json.loads(d['columns']) if isinstance(d['columns'], str) else d['columns']
                    except (json.JSONDecodeError, TypeError, ValueError):
                        d['columns'] = []
                else:
                    d['columns'] = []
                d['is_read_only'] = bool(d.get('is_read_only'))
                d['is_staging'] = bool(d.get('is_staging'))
                return d
            return None

    def get_entity_relationships(self, name: str) -> List[Dict[str, Any]]:
        """Return relationships where entity participates as parent or child model."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                '''SELECT * FROM relationships WHERE parent_model = ? OR child_model = ?''',
                (name, name)
            )
            return [dict(r) for r in c.fetchall()]

    def list_deployed_views(self, deprecated_only: bool = False) -> List[Dict[str, Any]]:
        """List deployed views. If deprecated_only=True, return only deprecated views."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if deprecated_only:
                c.execute(
                    '''SELECT view_name, metric_name, metric_version, schema_name, deployed_at_utc, deprecated, definition_hash
                       FROM deployed_views WHERE deprecated = 1 ORDER BY view_name'''
                )
            else:
                c.execute(
                    '''SELECT view_name, metric_name, metric_version, schema_name, deployed_at_utc, deprecated, definition_hash
                       FROM deployed_views ORDER BY view_name'''
                )
            return [dict(r) for r in c.fetchall()]

    def get_deployed_view(self, view_name: str) -> Optional[Dict[str, Any]]:
        """Get a single deployed view by view_name."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                '''SELECT view_name, metric_name, metric_version, schema_name, deployed_at_utc, deprecated, definition_hash
                   FROM deployed_views WHERE view_name = ?''',
                (view_name,)
            )
            row = c.fetchone()
            return dict(row) if row else None

    def record_deployed_view(
        self,
        view_name: str,
        metric_name: str,
        metric_version: str,
        schema_name: str,
        deployed_at_utc: str,
        deprecated: bool = False,
        definition_hash: Optional[str] = None,
    ) -> None:
        """Record or update deployment state for a view."""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute(
                '''INSERT OR REPLACE INTO deployed_views
                   (view_name, metric_name, metric_version, schema_name, deployed_at_utc, deprecated, definition_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (view_name, metric_name, metric_version, schema_name, deployed_at_utc, 1 if deprecated else 0, definition_hash),
            )
            conn.commit()

    def mark_view_deprecated(self, view_name: str) -> None:
        """Mark a deployed view as deprecated."""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute('''UPDATE deployed_views SET deprecated = 1 WHERE view_name = ?''', (view_name,))
            conn.commit()

    def remove_deployed_view(self, view_name: str) -> None:
        """Remove deployment record for a view (e.g. after DROP)."""
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute('''DELETE FROM deployed_views WHERE view_name = ?''', (view_name,))
            conn.commit()

    # --- Query usage tracking (read-only, no PII) ---

    def record_fingerprint(
        self,
        fingerprint: str,
        metric_name: str,
        metric_version: str,
        deprecated: bool = False,
        first_seen_utc: Optional[str] = None,
    ) -> None:
        """Register an AXI SQL fingerprint for a metric (used to match warehouse query logs)."""
        self.db.insert_or_replace("axi_sql_fingerprints", {
            "fingerprint": fingerprint,
            "metric_name": metric_name,
            "metric_version": metric_version,
            "deprecated": 1 if deprecated else 0,
            "first_seen_utc": first_seen_utc or "",
        })

    def get_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Look up metric info by SQL fingerprint. Returns None if unknown."""
        row = self.db.fetchone(
            """SELECT fingerprint, metric_name, metric_version, deprecated, first_seen_utc
               FROM axi_sql_fingerprints WHERE fingerprint = ?""",
            (fingerprint,),
        )
        if not row:
            return None
        return {
            "fingerprint": row[0],
            "metric_name": row[1],
            "metric_version": row[2],
            "deprecated": bool(row[3]),
            "first_seen_utc": row[4] or None,
        }

    def increment_usage(
        self,
        metric_name: str,
        metric_version: str,
        usage_date: str,
        deprecated_access: bool = False,
    ) -> None:
        """Increment usage counts for a metric/version/date (no PII)."""
        dep_inc = 1 if deprecated_access else 0
        # SQLite 3.24+ upsert; excluded = row that would have been inserted
        self.db.execute(
            """INSERT INTO metric_usage (metric_name, metric_version, usage_date, usage_count, deprecated_access_count)
               VALUES (?, ?, ?, 1, ?)
               ON CONFLICT(metric_name, metric_version, usage_date) DO UPDATE SET
                 usage_count = usage_count + excluded.usage_count,
                 deprecated_access_count = deprecated_access_count + excluded.deprecated_access_count""",
            (metric_name, metric_version, usage_date, dep_inc),
        )
        self.db.commit()

    def list_usage(
        self,
        metric_name: Optional[str] = None,
        usage_date_from: Optional[str] = None,
        usage_date_to: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List usage aggregation rows. Optional filters by metric and date range."""
        conditions: List[str] = []
        params: List[Any] = []
        if metric_name is not None:
            conditions.append("metric_name = ?")
            params.append(metric_name)
        if usage_date_from is not None:
            conditions.append("usage_date >= ?")
            params.append(usage_date_from)
        if usage_date_to is not None:
            conditions.append("usage_date <= ?")
            params.append(usage_date_to)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        sql = f"""SELECT metric_name, metric_version, usage_date, usage_count, deprecated_access_count
                  FROM metric_usage{where} ORDER BY usage_date DESC, metric_name, metric_version"""
        rows = self.db.fetchall(sql, tuple(params) if params else None)
        return [
            {
                "metric_name": r[0],
                "metric_version": r[1],
                "usage_date": r[2],
                "usage_count": r[3],
                "deprecated_access_count": r[4],
            }
            for r in rows
        ]

    # --- Metric version history (append-only; never overwrite) ---

    def append_metric_version_history(
        self,
        metric_name: str,
        version: str,
        definition_snapshot: Dict[str, Any],
        status: str,
        created_at: str,
        deprecated_at: Optional[str] = None,
        replacement_metric: Optional[str] = None,
    ) -> None:
        """Append a version record. Never overwrite history."""
        snapshot_json = json.dumps(definition_snapshot, sort_keys=True) if definition_snapshot else "{}"
        self.db.execute(
            """INSERT INTO metric_version_history
               (metric_name, version, definition_snapshot, status, created_at, deprecated_at, replacement_metric)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (metric_name, version, snapshot_json, status, created_at, deprecated_at or None, replacement_metric or None),
        )
        self.db.commit()

    def list_metric_version_history(self, metric_name: str) -> List[Dict[str, Any]]:
        """List version history for a metric, newest first."""
        rows = self.db.fetchall(
            """SELECT id, metric_name, version, definition_snapshot, status, created_at, deprecated_at, replacement_metric
               FROM metric_version_history WHERE metric_name = ? ORDER BY created_at DESC, id DESC""",
            (metric_name,),
        )
        result = []
        for r in rows:
            snap = r[3]
            try:
                snap = self.db.deserialize_json(snap) if hasattr(self.db, "deserialize_json") else json.loads(snap)
            except (TypeError, ValueError, json.JSONDecodeError):
                snap = {}
            result.append({
                "id": r[0],
                "metric_name": r[1],
                "version": r[2],
                "definition_snapshot": snap,
                "status": r[4],
                "created_at": r[5],
                "deprecated_at": r[6],
                "replacement_metric": r[7],
            })
        return result

    def get_metric_version_record(self, metric_name: str, version: str) -> Optional[Dict[str, Any]]:
        """Get a specific version record by metric name and version string."""
        row = self.db.fetchone(
            """SELECT id, metric_name, version, definition_snapshot, status, created_at, deprecated_at, replacement_metric
               FROM metric_version_history WHERE metric_name = ? AND version = ?
               ORDER BY created_at DESC LIMIT 1""",
            (metric_name, version),
        )
        if not row:
            return None
        snap = row[3]
        try:
            snap = self.db.deserialize_json(snap) if hasattr(self.db, "deserialize_json") else json.loads(snap)
        except (TypeError, ValueError, json.JSONDecodeError):
            snap = {}
        return {
            "id": row[0],
            "metric_name": row[1],
            "version": row[2],
            "definition_snapshot": snap,
            "status": row[4],
            "created_at": row[5],
            "deprecated_at": row[6],
            "replacement_metric": row[7],
        }

    def upsert_entity(self, entity: Dict[str, Any]) -> None:
        """
        Insert or update an entity record with extended fields.
        Expected keys: name (required), model, primary_key, columns, type,
        is_read_only, is_staging, physical_location, source_name, schema_name, database_name
        """
        required = entity.get("name")
        if not required:
            return
        cols = entity.get("columns") or []
        if not isinstance(cols, str):
            try:
                cols = json.dumps(cols)
            except Exception:
                cols = "[]"
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute(
                """INSERT OR REPLACE INTO entities
                (name, model, primary_key, columns, type, is_read_only, is_staging, physical_location, source_name, schema_name, database_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entity.get("name"),
                    entity.get("model"),
                    entity.get("primary_key"),
                    cols,
                    entity.get("type"),
                    1 if entity.get("is_read_only") else 0,
                    1 if entity.get("is_staging") else 0,
                    entity.get("physical_location"),
                    entity.get("source_name"),
                    entity.get("schema_name"),
                    entity.get("database_name"),
                ),
            )
            conn.commit()

    def update_entity_pk(self, entity_name: str, pk_column: str) -> None:
        """
        Update an entity's primary key column.
        Used by Snowflake extractor when it discovers PK constraints.
        """
        if not entity_name or not pk_column:
            return
        with self._get_conn() as conn:
            c = conn.cursor()
            # First check if entity exists
            c.execute('SELECT primary_key FROM entities WHERE name = ?', (entity_name,))
            row = c.fetchone()
            if row:
                existing_pk = row[0]
                # If already has a PK, append (composite key) or skip if same
                if existing_pk:
                    try:
                        existing = json.loads(existing_pk) if existing_pk.startswith('[') else [existing_pk]
                    except (json.JSONDecodeError, TypeError, ValueError):
                        existing = [existing_pk]
                    if pk_column not in existing:
                        existing.append(pk_column)
                        new_pk = json.dumps(existing)
                    else:
                        new_pk = existing_pk
                else:
                    new_pk = pk_column
                c.execute('UPDATE entities SET primary_key = ? WHERE name = ?', (new_pk, entity_name))
                conn.commit()

    def add_relationship(self, relationship: Dict[str, Any]) -> int:
        """
        Add a relationship to the relationships table.
        Used by Snowflake extractor to create relationships from FK constraints.

        Args:
            relationship: Dict with keys: parent_model, child_model, fk_column, pk_column, join_type

        Returns:
            The ID of the inserted relationship
        """
        parent = relationship.get("parent_model")
        child = relationship.get("child_model")
        fk = relationship.get("fk_column", "")
        pk = relationship.get("pk_column", "")
        join_type = relationship.get("join_type", "FK")

        if not parent or not child:
            return -1

        with self._get_conn() as conn:
            c = conn.cursor()
            # Check if relationship already exists
            c.execute('''
                SELECT id FROM relationships
                WHERE parent_model = ? AND child_model = ? AND fk_column = ? AND pk_column = ?
            ''', (parent, child, fk, pk))
            existing = c.fetchone()
            if existing:
                return existing[0]

            # Insert new relationship
            c.execute('''
                INSERT INTO relationships (parent_model, child_model, fk_column, pk_column, join_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (parent, child, fk, pk, join_type))
            conn.commit()
            return c.lastrowid or -1

    # Snowflake Metadata Methods
    def list_sf_tables(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM sf_tables')
            rows = c.fetchall()
            return [dict(row) for row in rows]

    def list_sf_columns(self, table_name: str) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            # Join to find table_id
            c.execute('''
                SELECT c.* FROM sf_columns c
                JOIN sf_tables t ON c.table_id = t.id
                WHERE t.name = ?
            ''', (table_name,))
            rows = c.fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d['tags'] = json.loads(d['tags']) if d['tags'] else {}
                res.append(d)
            return res

    def list_sf_policies(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute('SELECT * FROM sf_masking_policies')
            masking = [dict(r) for r in c.fetchall()]
            
            c.execute('SELECT * FROM sf_row_access_policies')
            rap = [dict(r) for r in c.fetchall()]
            
            return {"masking": masking, "row_access": rap}

    def list_sf_lineage(self, table_name: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if table_name:
                c.execute('SELECT * FROM sf_lineage WHERE upstream_table = ? OR downstream_table = ?', (table_name, table_name))
            else:
                c.execute('SELECT * FROM sf_lineage')
            rows = c.fetchall()
            return [dict(row) for row in rows]

    # dbt Metadata Methods
    def list_dbt_models(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM dbt_models')
            rows = c.fetchall()
            res = []
            for r in rows:
                 d = dict(r)
                 d['tags'] = json.loads(d['tags']) if d['tags'] else []
                 d['depends_on'] = json.loads(d['depends_on']) if d['depends_on'] else []
                 res.append(d)
            return res

    def get_dbt_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM dbt_models WHERE model_name = ?', (model_name,))
            row = c.fetchone()
            if row:
                d = dict(row)
                d['tags'] = json.loads(d['tags']) if d['tags'] else []
                d['depends_on'] = json.loads(d['depends_on']) if d['depends_on'] else []
                return d
            return None

    def list_dbt_sources(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM dbt_sources')
            rows = c.fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d['tags'] = json.loads(d['tags']) if d['tags'] else []
                res.append(d)
            return res

    def list_dbt_tests(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM dbt_tests')
            rows = c.fetchall()
            return [dict(r) for r in rows]
    
    def record_promotion_result(
        self,
        name: str,
        path: str,
        status: str,
        reason: str,
        source: str = "dbt",
        model_type: str = "model",
        matched_rule: Optional[str] = None,
        error_message: Optional[str] = None,
        entity_created: bool = False,
        dimensions_count: int = 0,
        metrics_count: int = 0
    ):
        """Record a promotion result for a model/table."""
        from datetime import datetime
        with self._get_conn() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR REPLACE INTO promotion_results 
                (name, path, type, source, status, reason, matched_rule, error_message, 
                 entity_created, dimensions_count, metrics_count, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name, path, model_type, source, status, reason, matched_rule, error_message,
                entity_created, dimensions_count, metrics_count, datetime.now().isoformat()
            ))
            conn.commit()
    
    def clear_promotion_results(self):
        """Clear all promotion results (called before new extraction)."""
        attempts = 0
        last_exc: Optional[Exception] = None
        while attempts < 4:
            try:
                with self._get_conn() as conn:
                    c = conn.cursor()
                    c.execute('DELETE FROM promotion_results')
                    conn.commit()
                return
            except sqlite3.OperationalError as exc:
                last_exc = exc
                if "locked" in str(exc).lower():
                    attempts += 1
                    time.sleep(0.25 * attempts)
                    # On lock, try cleaning leftover WAL/SHM and retry on next loop
                    try:
                        for suffix in (".wal", ".shm"):
                            wal_path = f"{self.db_path}{suffix}"
                            if os.path.exists(wal_path):
                                os.remove(wal_path)
                    except Exception:
                        pass
                    continue
                raise
        # final attempt: if still locked, raise with a helpful hint
        if last_exc and "locked" in str(last_exc).lower():
            logger.warning(
                "Metadata database is locked at %s; continuing without clearing promotion results. "
                "If this persists, move AXI_METADATA_DIR off /mnt/c or stop other AXI processes.",
                self.db_path,
            )
            return
        # otherwise re-raise the last error
        if last_exc:
            raise last_exc
    
    def list_promotion_results(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all promotion results, optionally filtered by status."""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if status:
                c.execute('SELECT * FROM promotion_results WHERE status = ? ORDER BY scanned_at DESC', (status,))
            else:
                c.execute('SELECT * FROM promotion_results ORDER BY scanned_at DESC')
            rows = c.fetchall()
            return [dict(r) for r in rows]
    
    def get_promotion_summary(self) -> Dict[str, Any]:
        """Get summary statistics of promotion results."""
        with self._get_conn() as conn:
            c = conn.cursor()
            
            # Get counts by status
            c.execute('SELECT status, COUNT(*) as count FROM promotion_results GROUP BY status')
            status_counts = {row[0]: row[1] for row in c.fetchall()}
            
            total_scanned = sum(status_counts.values())
            promoted = status_counts.get('promoted', 0)
            ignored = status_counts.get('ignored', 0)
            errors = status_counts.get('error', 0)
            
            # Determine extraction mode (check if any results have source='snowflake')
            c.execute('SELECT DISTINCT source FROM promotion_results LIMIT 1')
            row = c.fetchone()
            extraction_mode = row[0] if row else "dbt"
            
            return {
                "counts": {
                    "total_scanned": total_scanned,
                    "promoted": promoted,
                    "ignored": ignored,
                    "errors": errors
                },
                "extraction_mode": extraction_mode
            }

    def list_constraints(self, model_name: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if model_name:
                c.execute('SELECT * FROM axi_constraints WHERE model_name = ?', (model_name,))
            else:
                c.execute('SELECT * FROM axi_constraints')
            rows = c.fetchall()
            return [dict(r) for r in rows]
