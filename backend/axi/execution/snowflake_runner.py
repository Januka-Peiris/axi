# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import snowflake.connector
from typing import List, Any, Dict, Tuple, Optional
import time
from pathlib import Path
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from axi.config.loader import load_config, SnowflakeConfig
from axi.config.secrets import validate_snowflake_credentials
from axi.utils.logging_config import get_logger
from pydantic import SecretStr

logger = get_logger(__name__)


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
            private_key_path = os.getenv("AXI_SNOWFLAKE_PRIVATE_KEY_PATH") or os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
            private_key_passphrase = os.getenv("AXI_SNOWFLAKE_PRIVATE_KEY_PASSPHRASE") or os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
            authenticator = os.getenv("AXI_SNOWFLAKE_AUTHENTICATOR") or os.getenv("SNOWFLAKE_AUTHENTICATOR")
            token = os.getenv("AXI_SNOWFLAKE_TOKEN") or os.getenv("SNOWFLAKE_TOKEN")

            cfg = SnowflakeConfig(
                account=os.getenv("AXI_SNOWFLAKE_ACCOUNT") or os.getenv("SNOWFLAKE_ACCOUNT"),
                user=os.getenv("AXI_SNOWFLAKE_USER") or os.getenv("SNOWFLAKE_USER"),
                password=SecretStr(password) if password else None,
                private_key_path=private_key_path,
                private_key_passphrase=SecretStr(private_key_passphrase) if private_key_passphrase else None,
                authenticator=authenticator,
                token=SecretStr(token) if token else None,
                role=os.getenv("AXI_SNOWFLAKE_ROLE") or os.getenv("SNOWFLAKE_ROLE"),
                warehouse=os.getenv("AXI_SNOWFLAKE_WAREHOUSE") or os.getenv("SNOWFLAKE_WAREHOUSE"),
                database=os.getenv("AXI_SNOWFLAKE_DB") or os.getenv("SNOWFLAKE_DATABASE") or os.getenv("SNOWFLAKE_DB"),
                schema=os.getenv("AXI_SNOWFLAKE_SCHEMA") or os.getenv("SNOWFLAKE_SCHEMA"),
            )

        return cfg

    def _validate_credentials(self):
        """Validate Snowflake credentials using secrets validation."""
        errors = validate_snowflake_credentials(self.creds, required_for="connection")
        if errors:
            error_msg = "Missing or invalid Snowflake credentials:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)

    def _load_private_key(self) -> bytes:
        """
        Load and decode private key from file.

        Returns:
            Private key bytes in DER format
        """
        if not self.creds.private_key_path:
            raise ValueError("Private key path not configured")

        key_path = Path(self.creds.private_key_path).expanduser()

        try:
            with open(key_path, "rb") as key_file:
                private_key_pem = key_file.read()

            # Get passphrase if provided
            passphrase = None
            if self.creds.private_key_passphrase:
                passphrase = self.creds.get_private_key_passphrase().encode()

            # Load private key
            private_key = serialization.load_pem_private_key(
                private_key_pem,
                password=passphrase,
                backend=default_backend()
            )

            # Convert to DER format (required by Snowflake connector)
            private_key_der = private_key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            return private_key_der

        except Exception as e:
            raise ValueError(f"Failed to load private key from {key_path}: {e}")

    def _get_connection_params(self) -> Dict[str, Any]:
        """
        Build connection parameters based on configured authentication method.

        Returns:
            Dict of connection parameters for snowflake.connector.connect()
        """
        params = {
            "user": self.creds.user,
            "account": self.creds.account,
            "warehouse": self.creds.warehouse,
            "database": self.creds.database,
            "schema": self.creds.schema_name,
            "role": self.creds.role,
            "client_session_keep_alive": self.creds.client_session_keep_alive,
        }

        # Add timeout settings if configured
        if self.creds.network_timeout:
            params["network_timeout"] = self.creds.network_timeout
        if self.creds.login_timeout:
            params["login_timeout"] = self.creds.login_timeout

        # Determine auth method and add appropriate parameters
        auth_method = self.creds.get_auth_method()

        if auth_method == 'key_pair':
            logger.debug("Using key-pair authentication")
            params["private_key"] = self._load_private_key()
            # Note: password should not be set when using key-pair auth

        elif auth_method == 'oauth':
            logger.debug("Using OAuth authentication")
            params["token"] = self.creds.get_token()
            params["authenticator"] = "oauth"

        elif auth_method == 'sso':
            logger.debug("Using SSO authentication (will open browser)")
            params["authenticator"] = "externalbrowser"
            # Note: password should not be set when using SSO

        elif auth_method == 'password':
            logger.debug("Using password authentication")
            params["password"] = self.creds.get_password()
            if self.creds.authenticator and self.creds.authenticator != 'snowflake':
                params["authenticator"] = self.creds.authenticator

        else:
            raise ValueError(
                f"No valid authentication method configured. "
                f"Please provide one of: password, private_key_path, token, or authenticator='externalbrowser'"
            )

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        return params

    def test_connection(self) -> bool:
        """
        Test Snowflake connection using configured authentication method.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._validate_credentials()
            params = self._get_connection_params()

            logger.debug(f"Testing connection to {self.creds.account} as {self.creds.user}")
            ctx = snowflake.connector.connect(**params)
            cs = ctx.cursor()
            try:
                cs.execute("SELECT 1")
                cs.fetchone()
                logger.info("Snowflake connection test successful")
                return True
            finally:
                cs.close()
                ctx.close()
        except Exception as e:
            logger.error(f"Snowflake connection test failed: {e}")
            return False

    def execute_query(self, sql: str) -> Tuple[List[Dict[str, Any]], List[str], float]:
        """
        Execute query and return results using configured authentication method.

        Args:
            sql: SQL query to execute

        Returns:
            Tuple of (rows as list of dicts, column names, execution time in ms)
        """
        self._validate_credentials()
        params = self._get_connection_params()

        ctx = snowflake.connector.connect(**params)
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
