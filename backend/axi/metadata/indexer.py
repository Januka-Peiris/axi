# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import sqlite3
import os
import json
import glob
import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class MetadataIndexer:
    def __init__(self, metadata_dir: str):
        # metadata_dir is base dir (e.g. metadata_store)
        # We need to find models in metadata_dir/models/*.json
        self.metadata_dir = metadata_dir
        try:
            os.makedirs(self.metadata_dir, exist_ok=True)
        except Exception:
            # Best effort; open will fail later with a clearer path if not writable
            pass
        self.db_path = os.path.join(metadata_dir, "axi.db")
        self._init_db()

    def _is_remote_fs(self) -> bool:
        """Detect WSL / Windows mount paths that dislike WAL."""
        path = os.path.abspath(self.db_path)
        return path.startswith("/mnt/") or ":" in path.split(os.sep)[0]

    def _configure_conn(self, conn: sqlite3.Connection) -> None:
        try:
            conn.execute("PRAGMA busy_timeout = 7000")
            # WAL can be problematic on Windows/WSL mounts; fall back to DELETE there.
            if self._is_remote_fs():
                conn.execute("PRAGMA journal_mode = DELETE")
            else:
                conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA locking_mode = NORMAL")
        except Exception:
            # Best-effort only
            pass

    def _get_conn(self):
        # Use a small timeout and pragmas to mitigate "database is locked".
        conn = sqlite3.connect(self.db_path, timeout=7, check_same_thread=False)
        self._configure_conn(conn)
        return conn

    def _init_db(self):
        conn = sqlite3.connect(self.db_path, timeout=7, check_same_thread=False)
        self._configure_conn(conn)
        c = conn.cursor()
    
        # Metrics Table
        c.execute('''CREATE TABLE IF NOT EXISTS metrics (
            name TEXT PRIMARY KEY,
            expression TEXT,
            model TEXT,
            grain TEXT,
            dimensions JSON,
            filters JSON,
            source_table TEXT,
            metric_type TEXT,
            aggregation TEXT,
            default_dimensions JSON,
            default_filter TEXT,
            time_dimension TEXT,
            depends_on JSON,
            numerator TEXT,
            denominator TEXT,
            semi_additive_method TEXT,
            semi_additive_dimension TEXT,
            tags JSON,
            description TEXT,
            entity_name TEXT
        )''')
        
        # Ensure column exists (migration)
        c.execute("PRAGMA table_info(metrics)")
        m_cols = [row[1] for row in c.fetchall()]
        if 'entity_name' not in m_cols:
            try:
                c.execute("ALTER TABLE metrics ADD COLUMN entity_name TEXT")
            except Exception:
                pass
        
        # Models Table
        c.execute('''CREATE TABLE IF NOT EXISTS models (
            name TEXT PRIMARY KEY,
            path TEXT,
            source_tables JSON,
            dimensions JSON
        )''')
        
        # Entities Table
        c.execute('''CREATE TABLE IF NOT EXISTS entities (
            name TEXT PRIMARY KEY,
            model TEXT,
            primary_key TEXT,
            columns JSON
        )''')
        # Safe migrations for new columns
        c.execute("PRAGMA table_info(entities)")
        cols = [row[1] for row in c.fetchall()]
        def _add_col(col_sql, name):
            if name not in cols:
                try:
                    c.execute(col_sql)
                except Exception:
                    pass
        _add_col("ALTER TABLE entities ADD COLUMN type TEXT", "type")
        _add_col("ALTER TABLE entities ADD COLUMN is_read_only BOOLEAN", "is_read_only")
        _add_col("ALTER TABLE entities ADD COLUMN is_staging BOOLEAN", "is_staging")
        _add_col("ALTER TABLE entities ADD COLUMN physical_location TEXT", "physical_location")
        _add_col("ALTER TABLE entities ADD COLUMN source_name TEXT", "source_name")
        _add_col("ALTER TABLE entities ADD COLUMN schema_name TEXT", "schema_name")
        _add_col("ALTER TABLE entities ADD COLUMN database_name TEXT", "database_name")
        
        # Relationships Table
        c.execute('''CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_model TEXT,
            child_model TEXT,
            fk_column TEXT,
            pk_column TEXT,
            join_type TEXT
        )''')
        
        # Snowflake Tables
        c.execute('''CREATE TABLE IF NOT EXISTS sf_tables (
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
        
        c.execute('''CREATE TABLE IF NOT EXISTS sf_columns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            name TEXT,
            type TEXT,
            nullable BOOLEAN,
            default_val TEXT,
            comment TEXT,
            ordinal INTEGER,
            tags JSON,
            FOREIGN KEY(table_id) REFERENCES sf_tables(id)
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sf_constraints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id INTEGER,
            type TEXT,
            columns JSON,
            referenced_table TEXT,
            referenced_columns JSON,
            FOREIGN KEY(table_id) REFERENCES sf_tables(id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS sf_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            value TEXT,
            level TEXT,
            object_name TEXT
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS sf_masking_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            schema TEXT,
            table_name TEXT,
            column_name TEXT,
            body TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS sf_row_access_policies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            schema TEXT,
            table_name TEXT,
            body TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS sf_lineage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upstream_table TEXT,
            downstream_table TEXT,
            type TEXT
        )''')

        # dbt Tables
        c.execute('''CREATE TABLE IF NOT EXISTS dbt_models (
            model_name TEXT PRIMARY KEY,
            resource_type TEXT,
            database TEXT,
            schema TEXT,
            alias TEXT,
            relation_name TEXT,
            materialization TEXT,
            path TEXT,
            tags JSON,
            description TEXT,
            depends_on JSON
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS dbt_sources (
            unique_id TEXT PRIMARY KEY,
            source_name TEXT,
            table_name TEXT,
            database TEXT,
            schema TEXT,
            relation_name TEXT,
            freshness JSON,
            tags JSON,
            description TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS dbt_tests (
            test_name TEXT PRIMARY KEY,
            test_type TEXT,
            model_name TEXT,
            column_name TEXT,
            severity TEXT,
            config JSON
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS axi_constraints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_name TEXT,
            column_name TEXT,
            constraint_type TEXT,
            details JSON
        )''')
        
        # Cache & Materialization
        c.execute('''CREATE TABLE IF NOT EXISTS cache_entries (
            cache_key TEXT PRIMARY KEY,
            metric TEXT,
            dimensions JSON,
            filters JSON,
            sql TEXT,
            created_at REAL,
            expires_at REAL,
            row_count INTEGER,
            storage_location JSON
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS materializations (
            table_name TEXT PRIMARY KEY,
            metric TEXT,
            dimensions JSON,
            refresh_mode TEXT,
            last_refresh_at REAL,
            row_count INTEGER,
            warehouse_location TEXT
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS semantic_marts (
            mart_name TEXT PRIMARY KEY,
            metrics JSON,
            dimensions JSON,
            table_name TEXT,
            last_refresh_at REAL
        )''')
        
        # Dimensions Table - for dimension browser UI
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
        
        # Promotion Results Table
        c.execute('''CREATE TABLE IF NOT EXISTS promotion_results (
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
        
        # Create indexes for faster lookups
        c.execute('''CREATE INDEX IF NOT EXISTS idx_dimensions_name ON dimensions(name)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_dimensions_entity_name ON dimensions(entity_name)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_metric_dimensions_dim_id ON metric_dimensions(dimension_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_entity_dimensions_dim_id ON entity_dimensions(dimension_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_promotion_results_status ON promotion_results(status)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_promotion_results_name ON promotion_results(name)''')
        
        conn.commit()
        conn.close()

    def build_index(self):
        """
        Scans JSON files in <metadata_dir>/models/ and YAML files in axi/metrics/ and repopulates the index.
        """
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Clear existing
        c.execute('DELETE FROM metrics')
        c.execute('DELETE FROM models')
        c.execute('DELETE FROM entities')
        c.execute('DELETE FROM relationships')
        
        # Index extracted models from JSON files
        models_dir = os.path.join(self.metadata_dir, "models")
        if os.path.exists(models_dir):
            for fpath in glob.glob(os.path.join(models_dir, "*.json")):
                with open(fpath, "r") as f:
                    data = json.load(f)
                    self._index_model(c, data)
        
        # Index user-defined metrics from YAML files
        self._index_user_defined_metrics(c)
        
        # Populate dimensions table from indexed models
        self._populate_dimensions(c)
        
        conn.commit()
        conn.close()
    
    def _index_user_defined_metrics(self, cursor):
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
        cursor.execute('SELECT name, model FROM entities')
        for row in cursor.fetchall():
            entity_model_map[row[0]] = row[1]
        
        # Load all YAML metric files
        for fpath in glob.glob(os.path.join(metrics_dir, "*.yml")) + glob.glob(os.path.join(metrics_dir, "*.yaml")):
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
                
                # Robust grain handling
                raw_grain = metric_data.get("grain", [])
                grain = json.dumps(raw_grain) if raw_grain else "[]"
                if raw_grain and not isinstance(raw_grain, list):
                     # If string, wrap in list for consistency before dumping
                     grain = json.dumps([raw_grain])
                elif not raw_grain:
                     grain = "[]"
                else:
                     grain = json.dumps(raw_grain)

                dims = metric_data.get("dimensions", [])
                tags = metric_data.get("tags", [])
                desc = metric_data.get("description", "")
                m_type = metric_data.get("type", "custom")
                
                # Get entity's model name from pre-loaded map
                model_name = entity_model_map.get(entity_name) if entity_name else None
                
                # Insert or replace metric
                cursor.execute('''INSERT OR REPLACE INTO metrics 
                                  (name, expression, model, grain, dimensions, filters, source_table,
                                   metric_type, aggregation, default_dimensions, default_filter, time_dimension,
                                   depends_on, numerator, denominator, semi_additive_method, semi_additive_dimension,
                                   tags, description, entity_name) 
                                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                              (m_name, expr, model_name, grain, json.dumps(dims), json.dumps([]), "",
                               m_type, m_type, json.dumps(dims), "", "",
                               json.dumps([]), "", "", "", "",
                               json.dumps(tags), desc, entity_name))
            except Exception as e:
                # Log error but continue processing other metrics
                print(f"Warning: Failed to index metric from {fpath}: {e}")
                continue

    def _populate_dimensions(self, cursor):
        """
        Extract dimensions from indexed models/metrics/entities and populate dimensions table.
        This runs after build_index() to ensure dimensions are available.
        """
        # Clear existing dimension relationships (but keep dimensions themselves for now)
        # We'll repopulate all relationships
        cursor.execute('DELETE FROM metric_dimensions')
        cursor.execute('DELETE FROM entity_dimensions')
        
        # Get all models and their dimensions
        cursor.execute("SELECT name, dimensions FROM models")
        models = cursor.fetchall()
        
        # Get all entities
        cursor.execute("SELECT name, model, columns FROM entities")
        entities = cursor.fetchall()
        entity_map = {}
        for row in entities:
            try:
                columns = json.loads(row[2]) if row[2] else []
            except (json.JSONDecodeError, TypeError, ValueError):
                columns = []
            entity_map[row[0]] = {"model": row[1], "columns": columns}
        
        # Get all metrics and their dimensions
        cursor.execute("SELECT name, dimensions, model FROM metrics")
        metrics = cursor.fetchall()
        
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
                    
                    # Insert dimension
                    cursor.execute('''INSERT OR IGNORE INTO dimensions 
                        (name, entity_name, data_type, is_primary, source_column, description)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                        (dim_name, entity_name, data_type, is_primary, source_column, None))
                    
                    cursor.execute("SELECT id FROM dimensions WHERE name = ?", (dim_name,))
                    dim_id_row = cursor.fetchone()
                    if dim_id_row:
                        dimension_seen[dim_name] = dim_id_row[0]
                    
                    # Link to entity
                    if entity_name and dim_name in dimension_seen:
                        cursor.execute('''INSERT OR IGNORE INTO entity_dimensions (entity_name, dimension_id)
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
                if isinstance(dim_name, dict):
                    dim_name = dim_name.get("name", "")
                if not dim_name or not isinstance(dim_name, str):
                    continue
                    
                # Ensure dimension exists
                if dim_name not in dimension_seen:
                    cursor.execute('''INSERT OR IGNORE INTO dimensions 
                        (name, data_type, description)
                        VALUES (?, ?, ?)''',
                        (dim_name, "TEXT", None))
                    cursor.execute("SELECT id FROM dimensions WHERE name = ?", (dim_name,))
                    dim_id_row = cursor.fetchone()
                    if dim_id_row:
                        dimension_seen[dim_name] = dim_id_row[0]
                
                # Link metric to dimension
                if dim_name in dimension_seen:
                    cursor.execute('''INSERT OR IGNORE INTO metric_dimensions (metric_name, dimension_id)
                        VALUES (?, ?)''', (metric_name, dimension_seen[dim_name]))

    def _index_model(self, cursor, data: Dict[str, Any]):
        model_name = data.get("model")
        source_tables = data.get("source_tables", [])
        dimensions = data.get("dimensions", [])
        
        # Insert Model
        cursor.execute('INSERT OR REPLACE INTO models (name, path, source_tables, dimensions) VALUES (?, ?, ?, ?)',
                       (model_name, "", json.dumps(source_tables), json.dumps(dimensions))) 
        
        # Insert Entity
        entity = data.get("entity", {})
        if entity:
            cursor.execute('INSERT OR REPLACE INTO entities (name, model, primary_key, columns) VALUES (?, ?, ?, ?)',
                           (entity.get("name", model_name), model_name, entity.get("pk"), json.dumps(entity.get("columns", []))))
                           
        # Insert Relationships
        relationships = data.get("relationships", [])
        for rel in relationships:
            cursor.execute('INSERT INTO relationships (parent_model, child_model, fk_column, pk_column, join_type) VALUES (?, ?, ?, ?, ?)',
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

            # Serialize grain if it is a list
            if isinstance(grain, list):
                grain = json.dumps(grain)
            
            print(f"DEBUG: Indexing metric {m_name}, grain type: {type(grain)}")
            
            
            cursor.execute('''INSERT OR REPLACE INTO metrics 
                              (name, expression, model, grain, dimensions, filters, source_table,
                               metric_type, aggregation, default_dimensions, default_filter, time_dimension,
                               depends_on, numerator, denominator, semi_additive_method, semi_additive_dimension,
                               tags, description, entity_name) 
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                           (m_name, expr, model_name, grain, json.dumps(dims), json.dumps(filters), src_table,
                            m_type, agg, json.dumps(def_dims), def_filt, time_dim, json.dumps(deps),
                            num, denom, sa_method, sa_dim, json.dumps(tags), desc, entity.get("name", model_name)))

    def list_metrics(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM metrics')
            rows = c.fetchall()
            return [dict(row) for row in rows]

    def get_metric(self, name: str) -> Optional[Dict[str, Any]]:
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM metrics WHERE name = ?', (name,))
            row = c.fetchone()
            if row:
                d = dict(row)
                # Parse JSON fields
                d['dimensions'] = json.loads(d['dimensions']) if d['dimensions'] else []
                d['filters'] = json.loads(d['filters']) if d['filters'] else []
                d['default_dimensions'] = json.loads(d['default_dimensions']) if d['default_dimensions'] else []
                d['depends_on'] = json.loads(d['depends_on']) if d['depends_on'] else []
                d['tags'] = json.loads(d['tags']) if d['tags'] else []
                return d
            return None

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
