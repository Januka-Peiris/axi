# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import pathlib
from typing import Optional, Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from axi.config.env_loader import find_project_root


class AXISettings(BaseSettings):
    """
    Application-level settings for AXI.
    Loads from environment variables with AXI_ prefix or .env files.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="AXI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_ignore_empty=True,
    )
    
    # Metadata directory
    metadata_dir: str = Field(
        default="",
        description="Directory for storing metadata (models, entities, metrics). "
                   "If not set, auto-detected from project structure."
    )
    
    # Environment
    env: Literal["dev", "staging", "prod", "local"] = Field(
        default="local",
        description="Environment name (dev, staging, prod, local)"
    )
    
    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level"
    )
    log_file: Optional[str] = Field(
        default=None,
        description="Path to log file. If None, logs only to console."
    )
    log_json: bool = Field(
        default=False,
        description="Use JSON format for structured logging"
    )
    
    # API settings
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API server port"
    )
    
    # Feature flags
    demo_mode: bool = Field(
        default=False,
        description="Enable demo mode (restricted features)"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode (verbose output)"
    )
    
    # Database configuration
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
    db_password: Optional[str] = Field(
        default=None,
        description="Database password (for PostgreSQL, use env: syntax in config)"
    )

    # ROI / usage (config-driven; no BI-tool logic)
    roi_hours_saved_per_query: float = Field(
        default=0.1,
        ge=0.0,
        description="Estimated analyst hours saved per AXI-matched query (for ROI summary)"
    )

    # Contract enforcement: strict (hard-fail on violations) or warn (emit warnings, allow compile)
    contract_enforcement_mode: Literal["warn", "strict"] = Field(
        default="strict",
        description="Contract enforcement: strict (fail compile/deploy on violation) or warn (log and allow)"
    )
    
    @field_validator('metadata_dir', mode='before')
    @classmethod
    def resolve_metadata_dir(cls, v: Optional[str]) -> str:
        """Auto-detect metadata directory if not provided."""
        if v and v.strip():
            return v.strip()
        
        # Prefer project root relative to the current working directory
        project_root = find_project_root()
        if project_root:
            return str(project_root / "metadata_store")
        
        # Fallback: use metadata_store under the current working directory
        return str(pathlib.Path.cwd() / "metadata_store")
    
    @field_validator('log_file')
    @classmethod
    def validate_log_file(cls, v: Optional[str]) -> Optional[str]:
        """Validate log file path."""
        if v:
            log_path = Path(v)
            # Create parent directory if it doesn't exist
            log_path.parent.mkdir(parents=True, exist_ok=True)
            return str(log_path.resolve())
        return v
    
    @property
    def AXI_METADATA_DIR(self) -> str:
        """Backward compatibility property."""
        return self.metadata_dir
    
    @property
    def AXI_DEMO_MODE(self) -> bool:
        """Backward compatibility property."""
        return self.demo_mode
    
    @property
    def LOG_LEVEL(self) -> str:
        """Backward compatibility property."""
        return self.log_level
    
    def reload(self) -> None:
        """Reload settings from environment."""
        # Create new instance to reload
        global _settings_instance
        _settings_instance = None
        get_settings()


# Singleton instance
_settings_instance: Optional[AXISettings] = None


def get_settings() -> AXISettings:
    """
    Get the singleton settings instance.
    
    Returns:
        AXISettings instance
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = AXISettings()
    return _settings_instance


# Backward compatibility alias
Settings = AXISettings
