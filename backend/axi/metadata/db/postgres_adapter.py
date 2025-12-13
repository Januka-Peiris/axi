# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
PostgreSQL database adapter implementation.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from .base import DatabaseAdapter

try:
    import psycopg2
    from psycopg2 import pool, sql
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class PostgreSQLAdapter(DatabaseAdapter):
    """PostgreSQL database adapter with connection pooling."""
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "axi",
        user: str = "axi",
        password: str = "",
        connection_pool_min: int = 1,
        connection_pool_max: int = 10,
        db_url: Optional[str] = None
    ):
        """
        Initialize PostgreSQL adapter.
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            connection_pool_min: Minimum pool size
            connection_pool_max: Maximum pool size
            db_url: Alternative connection string (overrides other params)
        """
        if not PSYCOPG2_AVAILABLE:
            raise ImportError(
                "psycopg2 is required for PostgreSQL support. "
                "Install it with: pip install psycopg2-binary"
            )
        
        self.connection_pool: Optional[pool.ThreadedConnectionPool] = None
        self.current_conn: Optional[Any] = None
        self.current_cursor: Optional[Any] = None
        
        if db_url:
            # Parse connection string
            self._init_from_url(db_url, connection_pool_min, connection_pool_max)
        else:
            self._init_pool(
                host, port, database, user, password,
                connection_pool_min, connection_pool_max
            )
    
    def _init_from_url(self, db_url: str, pool_min: int, pool_max: int) -> None:
        """Initialize connection pool from URL."""
        try:
            self.connection_pool = pool.ThreadedConnectionPool(
                pool_min, pool_max, db_url
            )
        except Exception as e:
            raise ConnectionError(f"Failed to create PostgreSQL connection pool: {e}")
    
    def _init_pool(
        self,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
        pool_min: int,
        pool_max: int
    ) -> None:
        """Initialize connection pool."""
        try:
            self.connection_pool = pool.ThreadedConnectionPool(
                pool_min,
                pool_max,
                host=host,
                port=port,
                database=database,
                user=user,
                password=password
            )
        except Exception as e:
            raise ConnectionError(f"Failed to create PostgreSQL connection pool: {e}")
    
    def _get_connection(self):
        """Get a connection from the pool."""
        if self.connection_pool is None:
            raise RuntimeError("Connection pool not initialized")
        return self.connection_pool.getconn()
    
    def _return_connection(self, conn) -> None:
        """Return a connection to the pool."""
        if self.connection_pool:
            self.connection_pool.putconn(conn)
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """Execute a SQL statement."""
        if self.current_conn is None:
            self.current_conn = self._get_connection()
            self.current_cursor = self.current_conn.cursor()
        
        if params:
            return self.current_cursor.execute(sql, params)
        return self.current_cursor.execute(sql)
    
    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Tuple]:
        """Execute a query and return a single row."""
        self.execute(sql, params)
        return self.current_cursor.fetchone() if self.current_cursor else None
    
    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """Execute a query and return all rows."""
        self.execute(sql, params)
        return self.current_cursor.fetchall() if self.current_cursor else []
    
    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        if self.current_conn is None:
            self.current_conn = self._get_connection()
            self.current_cursor = self.current_conn.cursor()
        # PostgreSQL starts in autocommit=False by default, but explicit is better
        self.current_conn.autocommit = False
    
    def commit(self) -> None:
        """Commit the current transaction."""
        if self.current_conn:
            self.current_conn.commit()
            # Return connection to pool after commit
            if self.current_cursor:
                self.current_cursor.close()
                self.current_cursor = None
            self._return_connection(self.current_conn)
            self.current_conn = None
    
    def rollback(self) -> None:
        """Rollback the current transaction."""
        if self.current_conn:
            self.current_conn.rollback()
            # Return connection to pool after rollback
            if self.current_cursor:
                self.current_cursor.close()
                self.current_cursor = None
            self._return_connection(self.current_conn)
            self.current_conn = None
    
    def close(self) -> None:
        """Close the database connection pool."""
        if self.current_cursor:
            self.current_cursor.close()
            self.current_cursor = None
        if self.current_conn:
            self._return_connection(self.current_conn)
            self.current_conn = None
        if self.connection_pool:
            self.connection_pool.closeall()
            self.connection_pool = None
    
    def insert_or_replace(self, table: str, data: Dict[str, Any]) -> None:
        """
        Insert or replace a row using PostgreSQL's INSERT ... ON CONFLICT syntax.
        
        Args:
            table: Table name
            data: Dictionary of column names to values
        """
        if not data:
            return
        
        columns = list(data.keys())
        placeholders = ", ".join(["%s" for _ in columns])
        column_names = ", ".join(columns)
        values = tuple(data.values())
        
        # Get primary key column (assume first column or 'name' for most tables)
        pk_column = columns[0] if columns else "id"
        if "name" in columns:
            pk_column = "name"
        
        sql = f"""
            INSERT INTO {table} ({column_names})
            VALUES ({placeholders})
            ON CONFLICT ({pk_column}) DO UPDATE SET
            {', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col != pk_column])}
        """
        self.execute(sql, values)
    
    def lastrowid(self) -> Optional[int]:
        """Get the last inserted row ID (PostgreSQL uses RETURNING)."""
        # PostgreSQL doesn't use lastrowid the same way
        # We'd need to use RETURNING clause in INSERT statements
        # For now, return None - callers should use RETURNING if needed
        return None
    
    def create_table_sql(self, table_name: str, columns: List[Dict[str, str]]) -> str:
        """
        Generate CREATE TABLE SQL for PostgreSQL.
        Uses JSONB for JSON columns instead of TEXT.
        
        Args:
            table_name: Name of the table
            columns: List of column definitions with 'name', 'type', and optionally 'constraints' keys
        
        Returns:
            CREATE TABLE SQL statement
        """
        col_defs = []
        for col in columns:
            col_type = col['type']
            # Convert TEXT to JSONB for JSON columns in PostgreSQL
            if col_type.upper() == 'TEXT' and 'json' in col.get('name', '').lower():
                col_type = 'JSONB'
            elif col_type.upper() == 'TEXT' and any(
                json_keyword in col.get('name', '').lower()
                for json_keyword in ['dimensions', 'filters', 'tags', 'columns', 'depends_on', 'source_tables']
            ):
                col_type = 'JSONB'
            
            col_def = f"{col['name']} {col_type}"
            if 'constraints' in col:
                col_def += f" {col['constraints']}"
            col_defs.append(col_def)
        
        return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)})"
    
    def serialize_json(self, value: Any) -> Any:
        """
        Serialize a Python object for PostgreSQL JSONB.
        Returns the object as-is (PostgreSQL handles JSONB natively).
        
        Args:
            value: Python object (dict, list, etc.)
        
        Returns:
            Python object (PostgreSQL will serialize to JSONB)
        """
        if value is None:
            return None
        if isinstance(value, str):
            try:
                # If it's already a JSON string, parse it to ensure it's valid
                json.loads(value)
                return value
            except (json.JSONDecodeError, TypeError):
                return value
        # Return as-is - psycopg2 will handle JSONB serialization
        return json.dumps(value) if not isinstance(value, (str, int, float, bool, type(None))) else value
    
    def deserialize_json(self, value: Any) -> Any:
        """
        Deserialize a PostgreSQL JSONB value to Python object.
        PostgreSQL JSONB is already a Python dict/list when fetched.
        
        Args:
            value: JSONB value from PostgreSQL
        
        Returns:
            Python object (dict, list, etc.)
        """
        if value is None:
            return None
        # PostgreSQL JSONB returns as dict/list already via psycopg2
        return value
