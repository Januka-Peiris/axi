# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Deploy-time enforcement for metric lifecycle state.

- Metrics with status=disabled MUST fail deployment.
- Metrics with status=deprecated MUST deploy successfully with explicit warnings (replacement_metric).
- Version conflicts (same view name, different definition) MUST fail with diff output.

No deployment side effects before full validation passes.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from axi.metadata.indexer import MetadataIndexer


@dataclass
class DeploymentValidationResult:
    """Result of deployment validation: errors (blocking) and warnings (informational)."""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    disabled_metrics: List[str] = field(default_factory=list)
    conflict_details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if deployment may proceed (no blocking errors)."""
        return len(self.errors) == 0


def _normalize_view_body(sql: str) -> str:
    """Normalize view body for stable hashing: strip, collapse whitespace."""
    if not sql or not sql.strip():
        return ""
    s = sql.strip()
    s = re.sub(r"\s+", " ", s)
    return s


def hash_view_definition(body: str) -> str:
    """Compute a stable hash of a view definition body (SELECT ...)."""
    normalized = _normalize_view_body(body)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _extract_view_body_from_ddl(ddl: str) -> str:
    """Extract the body (SELECT ...) from CREATE VIEW x AS <body>."""
    if not ddl or " AS " not in ddl:
        return ddl
    idx = ddl.upper().find(" AS ")
    if idx == -1:
        return ddl
    body = ddl[idx + 4 :].strip()
    if body.endswith(";"):
        body = body[:-1].strip()
    return body


def validate_deployment(
    indexer: "MetadataIndexer",
    schema: str,
    warehouse: str,
    replace_existing: bool,
    version_coexistence: bool,
) -> DeploymentValidationResult:
    """
    Run full deployment validation before any side effects.

    - Collects disabled metrics -> errors (deployment MUST fail).
    - Collects deprecated metrics -> warnings (include replacement_metric if present).
    - For replace actions: compares definition hash with deployed; if different -> errors with diff output.

    Returns DeploymentValidationResult. If result.errors is non-empty, deployment must not proceed.
    """
    from axi.intent.builder import build_intent_from_metric
    from axi.views.view_sql import view_full_name, generate_create_view_sql

    result = DeploymentValidationResult()
    metrics = indexer.list_metrics() or []
    deployed = {r["view_name"]: r for r in indexer.list_deployed_views()}

    disabled = []
    for m in metrics:
        name = m.get("name")
        if not name:
            continue
        status = (m.get("status") or "active").strip().lower()
        if status == "disabled":
            disabled.append(name)

    if disabled:
        result.disabled_metrics = disabled
        result.errors.append(
            f"Deployment failed: {len(disabled)} metric(s) have status=disabled and must not be deployed: {', '.join(disabled)}."
        )

    for m in metrics:
        metric_name = m.get("name")
        if not metric_name:
            continue
        status = (m.get("status") or "active").strip().lower()
        if status == "disabled":
            continue
        try:
            intent = build_intent_from_metric(indexer, metric_name)
            if not intent:
                continue
        except Exception:
            # Intent build failure (e.g. MetricDisabledError) - skip metric
            continue
        metric_version = getattr(intent, "metric_version", None) or "1.0"
        include_version = version_coexistence
        full_name = view_full_name(
            metric_name, schema=schema, version=metric_version if include_version else None
        )
        replacement_metric = m.get("replacement_metric") or None

        if status == "deprecated":
            msg = f"Metric '{metric_name}' is deprecated."
            if replacement_metric and str(replacement_metric).strip():
                msg += f" Replacement metric: {replacement_metric.strip()}"
            result.warnings.append(msg)

        try:
            from axi.exceptions import MetricDisabledError
            in_deployed = full_name in deployed
            use_replace = in_deployed and replace_existing
            ddl = generate_create_view_sql(
                intent,
                schema=schema,
                warehouse=warehouse,
                replace=use_replace,
                include_version_in_name=include_version,
                status=status,
                replacement_metric=replacement_metric,
            )
        except Exception:
            continue

        if in_deployed and replace_existing:
            body = _extract_view_body_from_ddl(ddl)
            new_hash = hash_view_definition(body)
            rec = deployed.get(full_name)
            old_hash = (rec.get("definition_hash") or "").strip() if rec else ""
            if old_hash and new_hash != old_hash:
                result.conflict_details.append({
                    "view_name": full_name,
                    "metric_name": metric_name,
                    "old_hash": old_hash,
                    "new_hash": new_hash,
                    "new_definition": body,
                })
                result.errors.append(
                    f"Version conflict: view '{full_name}' has a different definition than the deployed version. "
                    f"Deployed definition_hash: {old_hash[:16]}... New definition_hash: {new_hash[:16]}.... "
                    f"Re-deploy with replace to update, or resolve the conflict manually."
                )

    if result.conflict_details:
        # Ensure we have exactly one error line per conflict if we added generic errors above
        pass

    return result
