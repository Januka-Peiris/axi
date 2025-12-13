# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Custom exception hierarchy for AXI application.
Provides structured error handling with context and hints.
"""

from typing import Optional, Dict, Any


class AXIBaseException(Exception):
    """Base exception for all AXI-specific errors."""
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.hint = hint
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        result = {
            "code": self.code,
            "message": self.message
        }
        if self.hint:
            result["hint"] = self.hint
        if self.context:
            result["context"] = self.context
        return result


class ValidationError(AXIBaseException):
    """Raised when input validation fails."""
    pass


class MetadataError(AXIBaseException):
    """Raised when metadata operations fail."""
    pass


class QueryError(AXIBaseException):
    """Raised when query generation or execution fails."""
    pass


class DatabaseError(AXIBaseException):
    """Raised when database operations fail."""
    pass


class ConfigurationError(AXIBaseException):
    """Raised when configuration is invalid or missing."""
    pass
