# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Database abstraction layer for AXI metadata storage.
Supports both SQLite (embedded) and PostgreSQL (server) databases.
"""

from .base import DatabaseAdapter
from .factory import create_database_adapter, get_database_adapter
from .sqlite_adapter import SQLiteAdapter
from .postgres_adapter import PostgreSQLAdapter

__all__ = [
    "DatabaseAdapter",
    "create_database_adapter",
    "get_database_adapter",
    "SQLiteAdapter",
    "PostgreSQLAdapter",
]
