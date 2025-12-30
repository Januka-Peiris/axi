# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import os.path
from typing import Optional

from axi.config.settings import get_settings
from axi.utils.logging_config import get_logger
from .base import SemanticStore

logger = get_logger(__name__)


def get_semantic_store(
    *,
    storage_backend: Optional[str] = None,
    sqlite_path: Optional[str] = None,
    postgres_url: Optional[str] = None,
) -> SemanticStore:
    """
    Return a semantic store instance based on configuration.
    Defaults to SQLite and metadata_dir/semantic_state.db.
    """
    settings = get_settings()
    backend = (storage_backend or os.getenv("AXI_STORAGE") or settings.db_type).lower()

    if backend == "postgres":
        from .postgres_store import PostgresSemanticStore  # Lazy import to keep psycopg2 optional

        url = postgres_url or os.getenv("DATABASE_URL") or settings.db_url
        if not url:
            # Assemble from discrete env vars if needed
            user = os.getenv("AXI_DB_USER") or settings.db_user
            password = os.getenv("AXI_DB_PASSWORD") or (settings.db_password or "")
            host = os.getenv("AXI_DB_HOST") or settings.db_host or "localhost"
            port = os.getenv("AXI_DB_PORT") or settings.db_port
            name = os.getenv("AXI_DB_NAME") or settings.db_name or "axi"
            if not user:
                raise ValueError("Postgres selected but DATABASE_URL/AXI_DB_USER not provided.")
            url = f"postgres://{user}:{password}@{host}:{port}/{name}"
        logger.info(f"[SemanticStore] Using Postgres backend")
        return PostgresSemanticStore(url)

    # Default: SQLite
    from .sqlite_store import SQLiteSemanticStore  # Lazy import

    db_path = sqlite_path or os.path.join(settings.metadata_dir, "semantic_state.db")
    logger.debug(f"[SemanticStore] Using SQLite backend at {db_path}")
    return SQLiteSemanticStore(db_path)
