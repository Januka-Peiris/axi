# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Factory for creating database adapters based on configuration.
"""

from typing import Optional
from .base import DatabaseAdapter
from .sqlite_adapter import SQLiteAdapter
from .postgres_adapter import PostgreSQLAdapter


def create_database_adapter(
    db_type: str = "sqlite",
    db_path: Optional[str] = None,
    db_url: Optional[str] = None,
    db_host: Optional[str] = None,
    db_port: int = 5432,
    db_name: Optional[str] = None,
    db_user: Optional[str] = None,
    db_password: Optional[str] = None,
    db_schema: Optional[str] = None,
    **kwargs
) -> DatabaseAdapter:
    """
    Create a database adapter based on configuration.

    Args:
        db_type: Database type ("sqlite" or "postgres")
        db_path: Path to SQLite database file (for SQLite)
        db_url: PostgreSQL connection URL (for PostgreSQL)
        db_host: PostgreSQL host (alternative to db_url)
        db_port: PostgreSQL port
        db_name: PostgreSQL database name
        db_user: PostgreSQL user
        db_password: PostgreSQL password
        db_schema: PostgreSQL schema for multi-tenancy (for PostgreSQL)
        **kwargs: Additional adapter-specific parameters

    Returns:
        DatabaseAdapter instance

    Raises:
        ValueError: If db_type is not supported or required parameters are missing
    """
    db_type_lower = db_type.lower()

    if db_type_lower == "sqlite":
        if not db_path:
            raise ValueError("db_path is required for SQLite")
        return SQLiteAdapter(db_path=db_path, **kwargs)

    elif db_type_lower == "postgres" or db_type_lower == "postgresql":
        if db_url:
            return PostgreSQLAdapter(db_url=db_url, schema=db_schema, **kwargs)
        elif db_host and db_name and db_user:
            return PostgreSQLAdapter(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password or "",
                schema=db_schema,
                **kwargs
            )
        else:
            raise ValueError(
                "For PostgreSQL, either db_url or (db_host, db_name, db_user) must be provided"
            )

    else:
        raise ValueError(f"Unsupported database type: {db_type}. Use 'sqlite' or 'postgres'.")


# Global adapter instance (singleton pattern)
_adapter_instance: Optional[DatabaseAdapter] = None


def get_database_adapter(**kwargs) -> DatabaseAdapter:
    """
    Get or create the global database adapter instance.
    Uses singleton pattern to ensure one adapter per process.
    
    Args:
        **kwargs: Configuration parameters (same as create_database_adapter)
    
    Returns:
        DatabaseAdapter instance
    """
    global _adapter_instance
    
    if _adapter_instance is None:
        _adapter_instance = create_database_adapter(**kwargs)
    
    return _adapter_instance


def reset_database_adapter() -> None:
    """Reset the global database adapter (useful for testing)."""
    global _adapter_instance
    if _adapter_instance:
        _adapter_instance.close()
    _adapter_instance = None
