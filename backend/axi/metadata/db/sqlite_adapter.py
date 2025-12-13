# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
SQLite database adapter implementation.
"""

import sqlite3
import os
from typing import Any, Dict, List, Optional, Tuple
from .base import DatabaseAdapter


class SQLiteAdapter(DatabaseAdapter):
    """SQLite database adapter."""
    
    def __init__(self, db_path: str, timeout: int = 7, check_same_thread: bool = False):
        """
        Initialize SQLite adapter.
        
        Args:
            db_path: Path to SQLite database file
            timeout: Connection timeout in seconds
            check_same_thread: Allow connections from different threads
        """
        self.db_path = db_path
        self.timeout = timeout
        self.check_same_thread = check_same_thread
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None
        self._is_remote_fs = self._detect_remote_fs()
        self._connect()
    
    def _detect_remote_fs(self) -> bool:
        """Detect WSL / Windows mount paths that dislike WAL."""
        path = os.path.abspath(self.db_path)
        return path.startswith("/mnt/") or ":" in path.split(os.sep)[0]
    
    def _connect(self) -> None:
        """Establish database connection."""
        # Create directory if it doesn't exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self.conn = sqlite3.connect(
            self.db_path,
            timeout=self.timeout,
            check_same_thread=self.check_same_thread
        )
        self._configure_connection()
        self.cursor = self.conn.cursor()
    
    def _configure_connection(self) -> None:
        """Configure SQLite connection with pragmas."""
        if self.conn is None:
            return
        
        try:
            self.conn.execute("PRAGMA busy_timeout = 7000")
            # WAL can be problematic on Windows/WSL mounts; fall back to DELETE there.
            if self._is_remote_fs:
                self.conn.execute("PRAGMA journal_mode = DELETE")
            else:
                self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA locking_mode = NORMAL")
        except Exception:
            # Best-effort only
            pass
    
    def execute(self, sql: str, params: Optional[Tuple] = None) -> sqlite3.Cursor:
        """Execute a SQL statement."""
        if self.cursor is None:
            self._connect()
        if params:
            return self.cursor.execute(sql, params)
        return self.cursor.execute(sql)
    
    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Tuple]:
        """Execute a query and return a single row."""
        self.execute(sql, params)
        return self.cursor.fetchone() if self.cursor else None
    
    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """Execute a query and return all rows."""
        self.execute(sql, params)
        return self.cursor.fetchall() if self.cursor else []
    
    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        if self.conn:
            self.conn.execute("BEGIN TRANSACTION")
    
    def commit(self) -> None:
        """Commit the current transaction."""
        if self.conn:
            self.conn.commit()
    
    def rollback(self) -> None:
        """Rollback the current transaction."""
        if self.conn:
            self.conn.rollback()
    
    def close(self) -> None:
        """Close the database connection."""
        if self.cursor:
            self.cursor.close()
            self.cursor = None
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def insert_or_replace(self, table: str, data: Dict[str, Any]) -> None:
        """
        Insert or replace a row using SQLite's INSERT OR REPLACE syntax.
        
        Args:
            table: Table name
            data: Dictionary of column names to values
        """
        if not data:
            return
        
        columns = list(data.keys())
        placeholders = ", ".join(["?" for _ in columns])
        column_names = ", ".join(columns)
        values = tuple(data.values())
        
        sql = f"INSERT OR REPLACE INTO {table} ({column_names}) VALUES ({placeholders})"
        self.execute(sql, values)
    
    def lastrowid(self) -> Optional[int]:
        """Get the last inserted row ID."""
        return self.cursor.lastrowid if self.cursor else None
    
    def create_table_sql(self, table_name: str, columns: List[Dict[str, str]]) -> str:
        """
        Generate CREATE TABLE SQL for SQLite.
        
        Args:
            table_name: Name of the table
            columns: List of column definitions with 'name', 'type', and optionally 'constraints' keys
        
        Returns:
            CREATE TABLE SQL statement
        """
        col_defs = []
        for col in columns:
            col_def = f"{col['name']} {col['type']}"
            if 'constraints' in col:
                col_def += f" {col['constraints']}"
            col_defs.append(col_def)
        
        return f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)})"
