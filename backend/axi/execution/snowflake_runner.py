# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import snowflake.connector
from typing import List, Any, Dict, Tuple, Optional
import time
import yaml

from axi.config.loader import load_config, SnowflakeConfig


def _resolve_env_value(value: Optional[str]) -> Optional[str]:
    if isinstance(value, str) and value.startswith("env:"):
        env_key = value.split("env:", 1)[1]
        return os.getenv(env_key)
    return value


class SnowflakeRunner:
    """
    Thin wrapper around snowflake.connector with config/env loading,
    basic validation, and simple result shaping.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.getcwd(), "axi.yml")
        self.creds = self._load_credentials()

    def _load_credentials(self) -> SnowflakeConfig:
        cfg: Optional[SnowflakeConfig] = None
        if self.config_path and os.path.exists(self.config_path):
            try:
                config = load_config(self.config_path)
                cfg = config.snowflake
            except Exception:
                cfg = None

        # Fallback to env
        cfg = cfg or SnowflakeConfig(
            account=os.getenv("SNOWFLAKE_ACCOUNT"),
            user=os.getenv("SNOWFLAKE_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            role=os.getenv("SNOWFLAKE_ROLE"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
            database=os.getenv("SNOWFLAKE_DB"),
            schema=os.getenv("SNOWFLAKE_SCHEMA"),
        )

        # Resolve env: vars
        cfg.account = _resolve_env_value(cfg.account)
        cfg.user = _resolve_env_value(cfg.user)
        cfg.password = _resolve_env_value(cfg.password)
        cfg.role = _resolve_env_value(cfg.role)
        cfg.warehouse = _resolve_env_value(cfg.warehouse)
        cfg.database = _resolve_env_value(cfg.database)
        cfg.schema = _resolve_env_value(cfg.schema)
        return cfg

    def _validate_credentials(self):
        missing = [k for k, v in {
            "account": self.creds.account,
            "user": self.creds.user,
            "password": self.creds.password,
            "warehouse": self.creds.warehouse,
            "database": self.creds.database,
            "schema": self.creds.schema
        }.items() if not v]
        if missing:
            raise ValueError(f"MISSING_CREDENTIALS: {', '.join(missing)}")

    def test_connection(self) -> bool:
        try:
            self._validate_credentials()
            ctx = snowflake.connector.connect(
                user=self.creds.user,
                password=self.creds.password,
                account=self.creds.account,
                warehouse=self.creds.warehouse,
                database=self.creds.database,
                schema=self.creds.schema,
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
        ctx = snowflake.connector.connect(
            user=self.creds.user,
            password=self.creds.password,
            account=self.creds.account,
            warehouse=self.creds.warehouse,
            database=self.creds.database,
            schema=self.creds.schema,
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
