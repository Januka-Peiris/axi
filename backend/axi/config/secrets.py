# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Secrets validation and management utilities.
"""

from typing import List, Optional
from axi.config.loader import SnowflakeConfig


def validate_snowflake_credentials(config: SnowflakeConfig, required_for: str = "connection") -> List[str]:
    """
    Validate Snowflake credentials and return list of missing/invalid fields.
    
    Args:
        config: SnowflakeConfig instance
        required_for: Context for validation (e.g., "connection", "sync")
    
    Returns:
        List of error messages. Empty list if all required fields are valid.
    """
    errors = []
    
    # Required fields for connection
    required_fields = {
        "account": config.account,
        "user": config.user,
        "password": config.get_password() if config.password else None,
        "warehouse": config.warehouse,
        "database": config.database,
        "schema": config.schema_name,
    }
    
    # Check for missing required fields
    for field_name, field_value in required_fields.items():
        if not field_value:
            errors.append(f"Missing required Snowflake credential: {field_name}")
        elif isinstance(field_value, str):
            # Check for placeholder values
            placeholder_patterns = [
                "your_", "example_", "placeholder", "changeme", "TODO", "FIXME",
                "xxx", "yyy", "zzz", "<", ">"
            ]
            field_lower = field_value.lower()
            if any(pattern in field_lower for pattern in placeholder_patterns):
                errors.append(
                    f"Snowflake {field_name} appears to be a placeholder value. "
                    f"Please set a real value."
                )
            # Check for empty strings
            if not field_value.strip():
                errors.append(f"Snowflake {field_name} is empty")
    
    return errors


def check_snowflake_credentials(config: Optional[SnowflakeConfig]) -> tuple[bool, List[str]]:
    """
    Check if Snowflake credentials are configured and valid.
    
    Args:
        config: SnowflakeConfig instance or None
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    if config is None:
        return False, ["Snowflake configuration not provided"]
    
    errors = validate_snowflake_credentials(config)
    return len(errors) == 0, errors
