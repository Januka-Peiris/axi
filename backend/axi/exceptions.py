# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Custom exception hierarchy for AXI application.
Provides structured error handling with context and hints.
All validation failures raise typed exceptions with: code, message, hint, context.
"""

from typing import Any, Dict, Optional, Type


class AXIBaseException(Exception):
    """Base exception for all AXI-specific errors. Includes code, message, hint, context."""

    default_http_status: int = 500

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.hint = hint
        self.context = context or {}

    @property
    def http_status(self) -> int:
        """HTTP status code for API responses. Override in subclasses."""
        return getattr(self.__class__, "default_http_status", 500)

    def to_dict(self) -> Dict[str, Any]:
        """Structured dict for API JSON: code, message, optional hint and context."""
        result: Dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.hint:
            result["hint"] = self.hint
        if self.context:
            result["context"] = self.context
        return result


class ValidationError(AXIBaseException):
    """Raised when input or semantic validation fails (generic)."""
    default_http_status = 400


class IntentValidationError(ValidationError):
    """Raised when semantic intent validation fails (grain, joins, dimensions, filters)."""
    default_http_status = 400


class ContractViolationError(ValidationError):
    """Raised when generated SQL violates the AXI SQL contract for BI tools."""
    default_http_status = 400


class MetadataError(AXIBaseException):
    """Raised when metadata operations fail."""
    default_http_status = 404


class QueryError(AXIBaseException):
    """Raised when query generation or execution fails."""
    default_http_status = 400


class MetricDisabledError(QueryError):
    """Raised when compilation is requested for a metric with status disabled."""
    default_http_status = 400


class DatabaseError(AXIBaseException):
    """Raised when database operations fail."""
    default_http_status = 500


class ConfigurationError(AXIBaseException):
    """Raised when configuration is invalid or missing."""
    default_http_status = 400


class DeploymentValidationError(AXIBaseException):
    """Raised when deployment validation fails (disabled metrics, version conflicts). Holds DeploymentValidationResult."""
    default_http_status = 422

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        hint: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
    ):
        super().__init__(message, code=code, hint=hint, context=context or {})
        self.result = result

    def to_dict(self) -> Dict[str, Any]:
        d = super().to_dict()
        if self.result is not None:
            r = self.result
            ctx = dict(d.get("context", {}))
            if hasattr(r, "errors") and r.errors:
                ctx["errors"] = r.errors
            if hasattr(r, "warnings") and r.warnings:
                ctx["warnings"] = r.warnings
            if hasattr(r, "disabled_metrics") and r.disabled_metrics:
                ctx["disabled_metrics"] = r.disabled_metrics
            if hasattr(r, "conflict_details") and r.conflict_details:
                ctx["conflict_details"] = r.conflict_details
            d["context"] = ctx
        return d
