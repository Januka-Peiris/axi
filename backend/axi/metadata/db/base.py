# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Abstract base class for database adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import json


class DatabaseAdapter(ABC):
    """
    Abstract base class for database operations.
    Provides a unified interface for SQLite and PostgreSQL.
    """
    
    @abstractmethod
    def execute(self, sql: str, params: Optional[Tuple] = None) -> Any:
        """
        Execute a SQL statement.
        
        Args:
            sql: SQL statement
            params: Optional parameters for parameterized queries
        
        Returns:
            Cursor or result object
        """
        pass
    
    @abstractmethod
    def fetchone(self, sql: str, params: Optional[Tuple] = None) -> Optional[Tuple]:
        """
        Execute a query and return a single row.
        
        Args:
            sql: SQL query
            params: Optional parameters
        
        Returns:
            Single row as tuple, or None
        """
        pass
    
    @abstractmethod
    def fetchall(self, sql: str, params: Optional[Tuple] = None) -> List[Tuple]:
        """
        Execute a query and return all rows.
        
        Args:
            sql: SQL query
            params: Optional parameters
        
        Returns:
            List of rows as tuples
        """
        pass
    
    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        pass
    
    @abstractmethod
    def commit(self) -> None:
        """Commit the current transaction."""
        pass
    
    @abstractmethod
    def rollback(self) -> None:
        """Rollback the current transaction."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""
        pass
    
    @abstractmethod
    def insert_or_replace(self, table: str, data: Dict[str, Any]) -> None:
        """
        Insert or replace a row in a table.
        Handles SQL dialect differences (INSERT OR REPLACE vs INSERT ... ON CONFLICT).
        
        Args:
            table: Table name
            data: Dictionary of column names to values
        """
        pass
    
    @abstractmethod
    def lastrowid(self) -> Optional[int]:
        """
        Get the last inserted row ID.
        
        Returns:
            Last row ID or None
        """
        pass
    
    def serialize_json(self, value: Any) -> str:
        """
        Serialize a Python object to JSON string.
        
        Args:
            value: Python object (dict, list, etc.)
        
        Returns:
            JSON string
        """
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return json.dumps(value)
    
    def deserialize_json(self, value: Any) -> Any:
        """
        Deserialize a JSON string to Python object.
        
        Args:
            value: JSON string or Python object
        
        Returns:
            Python object (dict, list, etc.)
        """
        if value is None:
            return None
        if isinstance(value, str):
            if not value.strip():
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value
    
    @abstractmethod
    def create_table_sql(self, table_name: str, columns: List[Dict[str, str]]) -> str:
        """
        Generate CREATE TABLE SQL for the specific database dialect.
        
        Args:
            table_name: Name of the table
            columns: List of column definitions with 'name' and 'type' keys
        
        Returns:
            CREATE TABLE SQL statement
        """
        pass
