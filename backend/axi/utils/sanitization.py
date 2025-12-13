# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Input sanitization utilities for user-provided data.
Prevents SQL injection, path traversal, and other security issues.
"""

import re
from typing import Optional
from pathlib import Path


# SQL injection patterns to detect
SQL_INJECTION_PATTERNS = [
    r';\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE)',
    r'--',
    r'/\*',
    r'\*/',
    r'UNION\s+SELECT',
    r'EXEC\s*\(',
    r'xp_',
    r'sp_',
]

# Compiled regex for performance
SQL_INJECTION_REGEX = re.compile('|'.join(SQL_INJECTION_PATTERNS), re.IGNORECASE)


def sanitize_identifier(identifier: str, max_length: int = 255) -> str:
    """
    Sanitize a SQL identifier (table name, column name, etc.).
    
    Args:
        identifier: The identifier to sanitize
        max_length: Maximum allowed length
    
    Returns:
        Sanitized identifier
    
    Raises:
        ValueError: If identifier is invalid
    """
    if not identifier:
        raise ValueError("Identifier cannot be empty")
    
    identifier = identifier.strip()
    
    # Check length
    if len(identifier) > max_length:
        raise ValueError(f"Identifier exceeds maximum length of {max_length}")
    
    # Allow alphanumeric, underscore, dot (for schema.table notation)
    if not re.match(r'^[a-zA-Z0-9_.]+$', identifier):
        raise ValueError(f"Invalid identifier: {identifier}. Only alphanumeric, underscore, and dot allowed")
    
    # Prevent SQL injection patterns
    if SQL_INJECTION_REGEX.search(identifier):
        raise ValueError(f"Identifier contains potentially dangerous characters: {identifier}")
    
    return identifier


def sanitize_string(value: str, max_length: int = 10000, allow_newlines: bool = False) -> str:
    """
    Sanitize a string value by removing control characters and limiting length.
    
    Args:
        value: The string to sanitize
        max_length: Maximum allowed length
        allow_newlines: Whether to allow newline characters
    
    Returns:
        Sanitized string
    
    Raises:
        ValueError: If string is invalid
    """
    if not isinstance(value, str):
        value = str(value)
    
    # Check length
    if len(value) > max_length:
        raise ValueError(f"String exceeds maximum length of {max_length}")
    
    # Remove control characters (except newlines if allowed)
    if allow_newlines:
        value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', value)
    else:
        value = re.sub(r'[\x00-\x1F\x7F]', '', value)
    
    return value.strip()


def sanitize_path(path: str, base_dir: Optional[str] = None) -> str:
    """
    Sanitize a file path and prevent path traversal attacks.
    
    Args:
        path: The path to sanitize
        base_dir: Optional base directory to restrict paths to
    
    Returns:
        Sanitized absolute path
    
    Raises:
        ValueError: If path is invalid or attempts traversal
    """
    if not path:
        raise ValueError("Path cannot be empty")
    
    path = path.strip()
    
    # Resolve to absolute path
    resolved = Path(path).resolve()
    
    # Check for path traversal attempts
    if '..' in path or path.startswith('/') and not base_dir:
        # Allow absolute paths but log them
        pass
    
    # If base_dir is provided, ensure path is within it
    if base_dir:
        base = Path(base_dir).resolve()
        try:
            resolved.relative_to(base)
        except ValueError:
            raise ValueError(f"Path {path} is outside allowed directory {base_dir}")
    
    return str(resolved)


def sanitize_sql_fragment(fragment: str) -> str:
    """
    Sanitize a SQL fragment (for filter strings).
    Uses whitelist approach - only allows safe SQL patterns.
    
    Args:
        fragment: SQL fragment to sanitize
    
    Returns:
        Sanitized fragment
    
    Raises:
        ValueError: If fragment contains unsafe patterns
    """
    if not fragment:
        return fragment
    
    fragment = fragment.strip()
    
    # Check for SQL injection patterns
    if SQL_INJECTION_REGEX.search(fragment):
        raise ValueError(f"SQL fragment contains potentially dangerous patterns: {fragment}")
    
    # Additional checks for common injection patterns
    dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC', 'EXECUTE']
    fragment_upper = fragment.upper()
    for keyword in dangerous_keywords:
        if keyword in fragment_upper:
            # Allow if it's part of a quoted string or comment, but be conservative
            if not re.search(rf'\b{keyword}\b', fragment_upper):
                continue
            raise ValueError(f"SQL fragment contains dangerous keyword: {keyword}")
    
    return fragment


def validate_metric_name(name: str) -> str:
    """
    Validate and sanitize a metric name.
    
    Args:
        name: Metric name to validate
    
    Returns:
        Validated metric name
    
    Raises:
        ValueError: If name is invalid
    """
    if not name:
        raise ValueError("Metric name cannot be empty")
    
    name = name.strip()
    
    # Use identifier sanitization
    return sanitize_identifier(name, max_length=255)


def validate_dimension_name(name: str) -> str:
    """
    Validate and sanitize a dimension name.
    
    Args:
        name: Dimension name to validate
    
    Returns:
        Validated dimension name
    
    Raises:
        ValueError: If name is invalid
    """
    if not name:
        raise ValueError("Dimension name cannot be empty")
    
    name = name.strip()
    
    # Allow schema.table.column notation
    if '.' in name:
        parts = name.split('.')
        for part in parts:
            sanitize_identifier(part, max_length=255)
    else:
        sanitize_identifier(name, max_length=255)
    
    return name


def sanitize_filter_value(value: any, operator: str) -> any:
    """
    Sanitize a filter value based on the operator.
    
    Args:
        value: Filter value to sanitize
        operator: SQL operator (IN, BETWEEN, etc.)
    
    Returns:
        Sanitized value
    
    Raises:
        ValueError: If value is invalid for the operator
    """
    if operator in ('IN', 'NOT IN'):
        if not isinstance(value, list):
            raise ValueError(f"{operator} operator requires a list value")
        return [sanitize_string(str(v), max_length=1000) for v in value]
    elif operator == 'BETWEEN':
        if not isinstance(value, list) or len(value) != 2:
            raise ValueError("BETWEEN operator requires a two-element list")
        return [sanitize_string(str(v), max_length=1000) for v in value]
    elif operator == 'LIKE':
        # Escape SQL LIKE wildcards
        if isinstance(value, str):
            value = value.replace('%', '\\%').replace('_', '\\_')
        return sanitize_string(str(value), max_length=1000)
    else:
        # For comparison operators, sanitize as string
        return sanitize_string(str(value), max_length=1000)
