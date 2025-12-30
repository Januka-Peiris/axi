# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import yaml
import os
import re
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, field_validator, SecretStr
from typing import List, Optional, Dict, Any, Literal
from pydantic import ValidationError

class PromotionRules(BaseModel):
    tags: List[str] = Field(default_factory=list)
    folders: List[str] = Field(default_factory=list)

class PromotionConfig(BaseModel):
    mode: str = "auto"  # strict, auto, hybrid (future)
    include: PromotionRules = Field(default_factory=PromotionRules)
    exclude: PromotionRules = Field(default_factory=PromotionRules)

class DbtConfig(BaseModel):
    """dbt project configuration."""
    
    compiled_path: Optional[str] = Field(
        default=None,
        description="Path to dbt compiled models directory"
    )
    
    @field_validator('compiled_path')
    @classmethod
    def validate_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate that compiled_path exists if provided."""
        if v:
            path = Path(v)
            if not path.exists():
                raise ValueError(f"dbt compiled_path does not exist: {v}")
            if not path.is_dir():
                raise ValueError(f"dbt compiled_path is not a directory: {v}")
        return v

class DimensionsConfig(BaseModel):
    keep: List[str] = Field(default_factory=list)
    drop: List[str] = Field(default_factory=list)

class SnowflakeConfig(BaseModel):
    """
    Snowflake connection configuration.

    Supports multiple authentication methods:
    - Password: username + password
    - Key Pair: username + private_key_path + private_key_passphrase
    - SSO: username + authenticator='externalbrowser'
    - OAuth: username + token
    """

    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)

    account: Optional[str] = Field(
        default=None,
        description="Snowflake account identifier (e.g., 'xy12345.us-east-1')"
    )
    user: Optional[str] = Field(
        default=None,
        description="Snowflake username"
    )

    # Password authentication
    password: Optional[SecretStr] = Field(
        default=None,
        description="Snowflake password (sensitive). Use for password-based auth."
    )

    # Key-pair authentication
    private_key_path: Optional[str] = Field(
        default=None,
        description="Path to private key file (.pem) for key-pair authentication"
    )
    private_key_passphrase: Optional[SecretStr] = Field(
        default=None,
        description="Passphrase for encrypted private key (if applicable)"
    )

    # SSO/OAuth authentication
    authenticator: Optional[str] = Field(
        default=None,
        description="Authentication method: 'externalbrowser' (SSO), 'oauth', 'snowflake' (default), or 'https://<okta_account>.okta.com' (Okta)"
    )
    token: Optional[SecretStr] = Field(
        default=None,
        description="OAuth token for OAuth authentication"
    )

    # Connection settings
    role: Optional[str] = Field(
        default=None,
        description="Snowflake role"
    )
    warehouse: Optional[str] = Field(
        default=None,
        description="Snowflake warehouse"
    )
    database: Optional[str] = Field(
        default=None,
        description="Snowflake database"
    )
    schema_name: Optional[str] = Field(
        default=None,
        alias="schema",
        description="Snowflake schema"
    )

    # Advanced connection options
    client_session_keep_alive: bool = Field(
        default=True,
        description="Keep session alive to prevent timeouts on long-running operations"
    )
    network_timeout: Optional[int] = Field(
        default=None,
        description="Network timeout in seconds (default: None = use connector default)"
    )
    login_timeout: Optional[int] = Field(
        default=60,
        description="Login timeout in seconds"
    )

    @field_validator('account', 'user', 'warehouse', 'database', 'schema_name')
    @classmethod
    def validate_identifier(cls, v: Optional[str]) -> Optional[str]:
        """Validate Snowflake identifier format."""
        if v:
            # Allow dots in account identifier (e.g., xy12345.us-east-1)
            # but still validate for SQL injection
            if not re.match(r'^[a-zA-Z0-9_.$-]+$', v):
                raise ValueError(f"Invalid Snowflake identifier: {v}")
        return v

    @field_validator('private_key_path')
    @classmethod
    def validate_private_key_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate that private key file exists if provided."""
        if v:
            path = Path(v).expanduser()
            if not path.exists():
                raise ValueError(f"Private key file does not exist: {v}")
            if not path.is_file():
                raise ValueError(f"Private key path is not a file: {v}")
        return v

    @property
    def schema(self) -> Optional[str]:
        """Get schema name."""
        return self.schema_name

    @schema.setter
    def schema(self, value: Optional[str]):
        """Set schema name."""
        self.schema_name = value

    def get_password(self) -> Optional[str]:
        """Get password as string (for backward compatibility)."""
        if self.password:
            return self.password.get_secret_value()
        return None

    def get_private_key_passphrase(self) -> Optional[str]:
        """Get private key passphrase as string."""
        if self.private_key_passphrase:
            return self.private_key_passphrase.get_secret_value()
        return None

    def get_token(self) -> Optional[str]:
        """Get OAuth token as string."""
        if self.token:
            return self.token.get_secret_value()
        return None

    def get_auth_method(self) -> str:
        """
        Determine which authentication method is configured.

        Returns:
            'key_pair', 'oauth', 'sso', 'password', or 'none'
        """
        if self.private_key_path:
            return 'key_pair'
        elif self.token:
            return 'oauth'
        elif self.authenticator == 'externalbrowser':
            return 'sso'
        elif self.password:
            return 'password'
        else:
            return 'none'

class DatabaseConfig(BaseModel):
    """Database configuration for metadata storage."""

    model_config = ConfigDict(populate_by_name=True)

    db_type: Literal["sqlite", "postgres"] = Field(
        default="sqlite",
        description="Database type: sqlite (embedded) or postgres (server)"
    )
    db_url: Optional[str] = Field(
        default=None,
        description="Database connection URL (for PostgreSQL, overrides individual settings)"
    )
    db_host: Optional[str] = Field(
        default=None,
        description="Database host (for PostgreSQL)"
    )
    db_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="Database port (for PostgreSQL)"
    )
    db_name: Optional[str] = Field(
        default="axi",
        description="Database name (for PostgreSQL)"
    )
    db_user: Optional[str] = Field(
        default=None,
        description="Database user (for PostgreSQL)"
    )
    db_password: Optional[SecretStr] = Field(
        default=None,
        alias="password",
        description="Database password (for PostgreSQL, supports env: syntax)"
    )
    db_schema: Optional[str] = Field(
        default=None,
        alias="schema",
        description="PostgreSQL schema for multi-tenancy (creates if not exists)"
    )

    def get_password(self) -> Optional[str]:
        """Get password as string (for backward compatibility)."""
        if self.db_password:
            return self.db_password.get_secret_value()
        return None

class Config(BaseModel):
    include: PromotionRules = Field(default_factory=PromotionRules)
    exclude: PromotionRules = Field(default_factory=PromotionRules)
    promotion: PromotionConfig = Field(default_factory=PromotionConfig)
    dbt: Optional[DbtConfig] = None
    dimensions: DimensionsConfig = Field(default_factory=DimensionsConfig)
    snowflake: Optional[SnowflakeConfig] = None
    database: Optional[DatabaseConfig] = None

def _substitute_env_vars(value: Any) -> Any:
    """
    Recursively substitute environment variables in config values.
    Supports 'env:VAR_NAME' syntax.
    """
    if isinstance(value, str):
        # Check for env: prefix
        if value.startswith("env:"):
            env_key = value[4:].strip()
            env_value = os.getenv(env_key)
            if env_value is None:
                raise ValueError(f"Environment variable '{env_key}' not found (referenced as 'env:{env_key}')")
            return env_value
        # Also support ${VAR_NAME} syntax
        pattern = r'\$\{([^}]+)\}'
        matches = re.findall(pattern, value)
        if matches:
            result = value
            for var_name in matches:
                env_value = os.getenv(var_name)
                if env_value is None:
                    raise ValueError(f"Environment variable '{var_name}' not found (referenced as ${{{var_name}}})")
                result = result.replace(f"${{{var_name}}}", env_value)
            return result
        return value
    elif isinstance(value, dict):
        return {k: _substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_substitute_env_vars(item) for item in value]
    else:
        return value


def find_config_file(base_path: Optional[str] = None, env: Optional[str] = None) -> Optional[Path]:
    """
    Find config file based on environment.
    
    Priority:
    1. axi.{env}.yml (if env is set)
    2. axi.yml
    
    Args:
        base_path: Base directory to search. If None, uses current directory.
        env: Environment name. If None, uses AXI_ENV env var.
    
    Returns:
        Path to config file or None if not found
    """
    if base_path is None:
        base_path = os.getcwd()
    
    base = Path(base_path)
    
    if env is None:
        env = os.getenv("AXI_ENV")
    
    # Try environment-specific config first
    if env:
        env_config = base / f"axi.{env}.yml"
        if env_config.exists():
            return env_config
    
    # Fallback to default config
    default_config = base / "axi.yml"
    if default_config.exists():
        return default_config
    
    return None


def load_config(config_path: Optional[str] = None, env: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file with environment variable substitution.
    
    Args:
        config_path: Path to config file. If None, auto-detects based on env.
        env: Environment name. If None, uses AXI_ENV env var.
    
    Returns:
        Config instance
    
    Raises:
        ValidationError: If config validation fails
        FileNotFoundError: If config file is specified but doesn't exist
        ValueError: If environment variable substitution fails
    """
    # Auto-detect config file if not provided
    if config_path is None:
        config_file = find_config_file(env=env)
        if config_file is None:
            # Return default config if no file found
            return Config()
        config_path = str(config_file)
    
    config_path_obj = Path(config_path)
    if not config_path_obj.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file {config_path}: {e}")
    
    if not data:
        return Config()
    
    # Substitute environment variables
    try:
        data = _substitute_env_vars(data)
    except ValueError as e:
        raise ValueError(f"Error substituting environment variables in {config_path}: {e}")
    
    # Handle password fields - convert to SecretStr if they're strings
    if "snowflake" in data and isinstance(data["snowflake"], dict):
        if "password" in data["snowflake"] and isinstance(data["snowflake"]["password"], str):
            # If it's an env: reference, it's already been substituted
            data["snowflake"]["password"] = SecretStr(data["snowflake"]["password"])
    
    # Handle database password field
    if "database" in data and isinstance(data["database"], dict):
        if "password" in data["database"] and isinstance(data["database"]["password"], str):
            data["database"]["password"] = SecretStr(data["database"]["password"])
    
    # Validate and create config
    try:
        return Config(**data)
    except ValidationError as e:
        raise ValueError(f"Config validation failed in {config_path}: {e}")
