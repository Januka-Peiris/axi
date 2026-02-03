# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Generate CREATE VIEW statements for AXI metrics.

Naming: axi.metric_<name> or axi.metric_<name>_v<version> for version coexistence.
Governance metadata embedded as SQL comments. Views are safe to query directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from axi.intent.models import SemanticIntent
from axi.intent.compiler import compile_metric

ContractMode = Literal["warn", "strict"]


def view_full_name(
    metric_name: str,
    schema: str = "axi",
    version: Optional[str] = None,
) -> str:
    """
    Full view name: schema.metric_<name> or schema.metric_<name>_v<version>.

    - metric_name: metric identifier (sanitized for identifier)
    - schema: schema/database prefix (default axi)
    - version: if set, append _v<version> for version coexistence
    """
    safe = metric_name.strip().replace("-", "_").replace(".", "_")
    base = f"metric_{safe}"
    if version and str(version).strip():
        v = str(version).strip().replace(".", "_")
        base = f"{base}_v{v}"
    if schema and schema.strip():
        return f"{schema.strip()}.{base}"
    return base


def generate_create_view_sql(
    intent: SemanticIntent,
    schema: str = "axi",
    warehouse: str = "snowflake",
    replace: bool = False,
    include_version_in_name: bool = False,
    deprecated: bool = False,
    status: Optional[str] = None,
    replacement_metric: Optional[str] = None,
    generated_at: Optional[datetime] = None,
    contract_mode: Optional[ContractMode] = None,
) -> str:
    """
    Generate CREATE [OR REPLACE] VIEW ... AS <metric SQL> with governance comments.

    - intent: Semantic Intent for the metric
    - schema: schema name (e.g. axi)
    - warehouse: snowflake (initial)
    - replace: if True, emit CREATE OR REPLACE VIEW; else CREATE VIEW
    - include_version_in_name: if True, view name is metric_<name>_v<version> for coexistence
    - deprecated: if True, add deprecated flag in comments
    - status: active | deprecated | disabled; disabled raises (caller should skip)
    - replacement_metric: optional; emitted when deprecated
    - generated_at: timestamp for comments (default now UTC)

    Embeds governance metadata as SQL comments. Does NOT execute.
    """
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    compiled_at_iso8601 = generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    version_suffix = intent.metric_version if include_version_in_name else None
    full_name = view_full_name(intent.metric_name, schema=schema, version=version_suffix)

    effective_deprecated = deprecated or (status or "").strip().lower() == "deprecated"
    lifecycle_status = "deprecated" if effective_deprecated else (status or "active").strip().lower()
    if lifecycle_status not in ("active", "deprecated", "disabled"):
        lifecycle_status = "active"

    # Metric SQL (SELECT ... ;) includes standard AXI metadata comments; strip for view body
    metric_sql = compile_metric(
        intent,
        warehouse=warehouse,
        deprecated=effective_deprecated,
        status=status,
        replacement_metric=replacement_metric,
        generated_at=generated_at,
        contract_mode=contract_mode,
    )
    # Remove leading comment block and trailing semicolon for view body (keep body only for AS)
    lines = metric_sql.strip().split("\n")
    body_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        body_lines.append(line)
    body_sql = "\n".join(body_lines).strip()
    if body_sql.endswith(";"):
        body_sql = body_sql[:-1].strip()

    # DDL comment block: same standard keys (axi.metric_name, axi.metric_version, axi.lifecycle_status, axi.compiled_at)
    from axi.sql_metadata import emit_axi_sql_metadata
    comments = emit_axi_sql_metadata(
        metric_name=intent.metric_name,
        metric_version=intent.metric_version,
        lifecycle_status=lifecycle_status,
        compiled_at_utc_iso8601=compiled_at_iso8601,
        replacement_metric=replacement_metric,
        include_deprecation_warning=False,
    )
    comments.append(f"-- axi.view_name: {full_name}")
    comments.append("")

    create_keyword = "CREATE OR REPLACE VIEW" if replace else "CREATE VIEW"
    ddl = "\n".join(comments) + f"{create_keyword} {full_name} AS\n" + body_sql + "\n;"
    return ddl
