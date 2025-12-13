# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
AXI Configuration Module

Provides application settings and project configuration management.
"""

from .settings import get_settings, AXISettings, Settings
from .loader import (
    load_config,
    Config,
    SnowflakeConfig,
    PromotionConfig,
    PromotionRules,
    DbtConfig,
    DimensionsConfig,
    find_config_file,
)
from .env_loader import load_env_file, find_project_root
from .secrets import validate_snowflake_credentials, check_snowflake_credentials

__all__ = [
    "get_settings",
    "AXISettings",
    "Settings",  # Backward compatibility
    "load_config",
    "Config",
    "SnowflakeConfig",
    "PromotionConfig",
    "PromotionRules",
    "DbtConfig",
    "DimensionsConfig",
    "find_config_file",
    "load_env_file",
    "find_project_root",
    "validate_snowflake_credentials",
    "check_snowflake_credentials",
]
