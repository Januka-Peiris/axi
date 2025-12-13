# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import snowflake.connector
from typing import List, Any, Dict, Tuple, Optional
import time
from pathlib import Path

from axi.config.loader import load_config, SnowflakeConfig
from axi.config.secrets import validate_snowflake_credentials
from pydantic import SecretStr


class SnowflakeRunner:
    """
    Thin wrapper around snowflake.connector with config/env loading,
    basic validation, and simple result shaping.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._find_config_file()
        self.creds = self._load_credentials()

    def _find_config_file(self) -> Optional[str]:
        """Find config file in current directory or parent directories."""
        current = Path.cwd()
        for _ in range(5):
            config_file = current / "axi.yml"
            if config_file.exists():
                return str(config_file)
            if current.parent == current:
                break
            current = current.parent
        return None

    def _load_credentials(self) -> SnowflakeConfig:
        """Load Snowflake credentials from config file or environment variables."""
        cfg: Optional[SnowflakeConfig] = None
        
        # Try loading from config file
        if self.config_path and os.path.exists(self.config_path):
            try:
                config = load_config(config_path=self.config_path)
                cfg = config.snowflake
            except Exception:
                cfg = None

        # Fallback to environment variables (with AXI_ prefix for consistency)
        if cfg is None:
            # Support both AXI_SNOWFLAKE_* and SNOWFLAKE_* prefixes for backward compatibility
            password = os.getenv("AXI_SNOWFLAKE_PASSWORD") or os.getenv("SNOWFLAKE_PASSWORD")
            cfg = SnowflakeConfig(
                account=os.getenv("AXI_SNOWFLAKE_ACCOUNT") or os.getenv("SNOWFLAKE_ACCOUNT"),
                user=os.getenv("AXI_SNOWFLAKE_USER") or os.getenv("SNOWFLAKE_USER"),
                password=SecretStr(password) if password else None,
                role=os.getenv("AXI_SNOWFLAKE_ROLE") or os.getenv("SNOWFLAKE_ROLE"),
                warehouse=os.getenv("AXI_SNOWFLAKE_WAREHOUSE") or os.getenv("SNOWFLAKE_WAREHOUSE"),
                database=os.getenv("AXI_SNOWFLAKE_DB") or os.getenv("SNOWFLAKE_DB"),
                schema=os.getenv("AXI_SNOWFLAKE_SCHEMA") or os.getenv("SNOWFLAKE_SCHEMA"),
            )
        
        return cfg

    def _validate_credentials(self):
        """Validate Snowflake credentials using secrets validation."""
        errors = validate_snowflake_credentials(self.creds, required_for="connection")
        if errors:
            error_msg = "Missing or invalid Snowflake credentials:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

    def test_connection(self) -> bool:
        try:
            self._validate_credentials()
            password = self.creds.get_password() if self.creds.password else None
            ctx = snowflake.connector.connect(
                user=self.creds.user,
                password=password,
                account=self.creds.account,
                warehouse=self.creds.warehouse,
                database=self.creds.database,
                schema=self.creds.schema_name,
                role=self.creds.role,
            )
            cs = ctx.cursor()
            try:
                cs.execute("SELECT 1")
                cs.fetchone()
                return True
            finally:
                cs.close()
                ctx.close()
        except Exception:
            return False

    def execute_query(self, sql: str) -> Tuple[List[Dict[str, Any]], List[str], float]:
        """
        Executes query and returns (rows as dicts, column_names, execution_ms)
        """
        self._validate_credentials()
        password = self.creds.get_password() if self.creds.password else None
        ctx = snowflake.connector.connect(
            user=self.creds.user,
            password=password,
            account=self.creds.account,
            warehouse=self.creds.warehouse,
            database=self.creds.database,
            schema=self.creds.schema_name,
            role=self.creds.role,
        )
        cs = ctx.cursor()
        start = time.time()
        try:
            cs.execute(sql)
            results = cs.fetchall()
            col_names = [col[0] for col in cs.description]
            rows = [dict(zip(col_names, row)) for row in results]
            elapsed_ms = (time.time() - start) * 1000
            return rows, col_names, elapsed_ms
        finally:
            cs.close()
            ctx.close()
