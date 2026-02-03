# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Centralized SQL comment emission for traceability and fingerprinting.

Every compiled SQL statement MUST include comments for:
- axi.metric_name
- axi.metric_version
- axi.lifecycle_status
- axi.compiled_at (UTC ISO8601)

Metadata is emitted deterministically (fixed order). Fingerprinting must occur
AFTER metadata insertion; SQL text equality implies fingerprint equality.
"""

from __future__ import annotations

from typing import List, Optional


def emit_axi_sql_metadata(
    metric_name: str,
    metric_version: str,
    lifecycle_status: str,
    compiled_at_utc_iso8601: str,
    *,
    replacement_metric: Optional[str] = None,
    include_deprecation_warning: bool = False,
) -> List[str]:
    """
    Emit AXI metadata comment lines in deterministic order for SQL traceability.

    - metric_name: metric identifier
    - metric_version: version string (e.g. 1.0)
    - lifecycle_status: "active" | "deprecated" | "disabled"
    - compiled_at_utc_iso8601: UTC timestamp in ISO8601 (e.g. 2026-02-03T12:00:00Z)
    - replacement_metric: optional; emitted when lifecycle_status is deprecated
    - include_deprecation_warning: if True, append human-readable deprecation line

    Returns list of comment lines (without trailing newline). Order is fixed so
    same inputs produce identical output for deterministic fingerprinting.
    """
    status = (lifecycle_status or "active").strip().lower()
    if status not in ("active", "deprecated", "disabled"):
        status = "active"

    lines: List[str] = [
        f"-- axi.metric_name: {metric_name}",
        f"-- axi.metric_version: {metric_version}",
        f"-- axi.lifecycle_status: {status}",
        f"-- axi.compiled_at: {compiled_at_utc_iso8601}",
    ]
    if status == "deprecated":
        lines.append("-- axi.deprecated: true")
        if replacement_metric and replacement_metric.strip():
            lines.append(f"-- axi.replacement_metric: {replacement_metric.strip()}")
        if include_deprecation_warning:
            lines.append("-- WARNING: This metric is deprecated. Prefer the replacement if specified.")
    return lines


def format_axi_sql_header(
    metric_name: str,
    metric_version: str,
    lifecycle_status: str,
    compiled_at_utc_iso8601: str,
    *,
    replacement_metric: Optional[str] = None,
    include_deprecation_warning: bool = False,
) -> str:
    """
    Return a complete AXI metadata header (comment block + blank line) to prepend to SQL body.

    Deterministic: same inputs => same string. Use this before concatenating the SQL body
    so fingerprinting runs on the final string after metadata insertion.
    """
    lines = emit_axi_sql_metadata(
        metric_name=metric_name,
        metric_version=metric_version,
        lifecycle_status=lifecycle_status,
        compiled_at_utc_iso8601=compiled_at_utc_iso8601,
        replacement_metric=replacement_metric,
        include_deprecation_warning=include_deprecation_warning,
    )
    return "\n".join(lines) + "\n\n"
