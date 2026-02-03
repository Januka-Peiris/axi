# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
CLI error formatting: AXI exceptions → human-readable, non-JSON output.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _format_context(context: Dict[str, Any], indent: str = "  ") -> str:
    """Format context dict as indented key: value lines."""
    if not context:
        return ""
    lines: List[str] = []
    for k, v in context.items():
        if isinstance(v, (list, dict)):
            import json
            lines.append(f"{indent}{k}:")
            lines.append(indent + "  " + json.dumps(v, indent=2).replace("\n", "\n" + indent + "  "))
        else:
            lines.append(f"{indent}{k}: {v}")
    return "\n".join(lines)


def format_axi_error(exc: Any) -> str:
    """
    Format an AXI exception for CLI: human-readable, non-JSON.
    Expects exc to have: message, code, optional hint, optional context.
    """
    code = getattr(exc, "code", None) or getattr(exc.__class__, "__name__", "Error")
    message = getattr(exc, "message", None) or str(exc)
    hint = getattr(exc, "hint", None)
    context = getattr(exc, "context", None) or {}

    parts: List[str] = []
    parts.append(f"Error ({code})")
    parts.append(f"  {message}")
    if hint:
        parts.append(f"Hint: {hint}")
    if context:
        parts.append("Details:")
        parts.append(_format_context(context, indent="  "))
    return "\n".join(parts)


def format_deployment_validation_error(exc: Any) -> str:
    """
    Format DeploymentValidationError for CLI: errors, warnings, conflict_details.
    Falls back to format_axi_error if no result attached.
    """
    result = getattr(exc, "result", None)
    if not result:
        return format_axi_error(exc)

    parts: List[str] = ["Deployment validation failed"]
    if getattr(result, "errors", None):
        parts.append("Errors:")
        for err in result.errors:
            parts.append(f"  • {err}")
    if getattr(result, "warnings", None):
        parts.append("Warnings:")
        for w in result.warnings:
            parts.append(f"  • {w}")
    if getattr(result, "conflict_details", None):
        for d in result.conflict_details:
            view_name = d.get("view_name", "")
            parts.append(f"\n--- Version conflict: {view_name} ---")
            new_def = d.get("new_definition", "")
            if new_def:
                parts.append("New definition (first 2000 chars):")
                parts.append(new_def[:2000])
    return "\n".join(parts)
