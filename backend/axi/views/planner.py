# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Deployment planner for governed semantic views.

Produces a plan: create, replace, drop (no execution). Uses AXI metadata for view state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TYPE_CHECKING

from axi.views.view_sql import view_full_name, generate_create_view_sql

ContractMode = Literal["warn", "strict"]

if TYPE_CHECKING:
    from axi.metadata.indexer import MetadataIndexer
    from axi.intent.models import SemanticIntent


@dataclass
class PlanAction:
    """Single deployment action (create, replace, or drop). No execution."""
    action: str  # "create" | "replace" | "drop"
    view_name: str
    metric_name: str
    metric_version: str
    sql: Optional[str] = None  # CREATE VIEW / DROP VIEW SQL; None for drop if not generated here
    deprecated: bool = False
    reason: str = ""


@dataclass
class DeploymentPlan:
    """Full deployment plan: list of actions. No execution engine."""
    create: List[PlanAction] = field(default_factory=list)
    replace: List[PlanAction] = field(default_factory=list)
    drop: List[PlanAction] = field(default_factory=list)
    schema: str = "axi"
    generated_at: str = ""
    warnings: List[str] = field(default_factory=list)

    def all_actions(self) -> List[PlanAction]:
        return self.create + self.replace + self.drop


class DeploymentPlanner:
    """
    Plan deployment of metric views: create, replace, drop deprecated.

    Uses indexer for metrics and deployed_views state. Does NOT execute SQL.
    """

    def __init__(
        self,
        indexer: "MetadataIndexer",
        schema: str = "axi",
        warehouse: str = "snowflake",
        replace_existing: bool = True,
        version_coexistence: bool = False,
        contract_mode: Optional[ContractMode] = None,
    ):
        self.indexer = indexer
        self.schema = schema or "axi"
        self.warehouse = warehouse or "snowflake"
        self.replace_existing = replace_existing
        self.version_coexistence = version_coexistence
        self.contract_mode = contract_mode

    def plan(self) -> DeploymentPlan:
        """
        Produce deployment plan from current metrics and deployed_views state.

        - Validates first: disabled metrics -> fail; deprecated -> warnings; version conflicts -> fail with diff.
        - No deployment side effects before full validation passes.
        - create: metrics that have no deployed view (or new version if version_coexistence)
        - replace: metrics that already have a view and replace_existing is True
        - drop: deployed views that are marked deprecated (for drop deprecated)

        No execution.
        """
        from axi.intent.builder import build_intent_from_metric
        from axi.views.deployment_validation import validate_deployment
        from axi.exceptions import MetricDisabledError, DeploymentValidationError

        validation = validate_deployment(
            self.indexer,
            schema=self.schema,
            warehouse=self.warehouse,
            replace_existing=self.replace_existing,
            version_coexistence=self.version_coexistence,
        )
        if not validation.is_valid:
            msg = "; ".join(validation.errors)
            if validation.conflict_details:
                for d in validation.conflict_details:
                    msg += f"\n--- Version conflict: {d['view_name']} ---\nNew definition:\n{d.get('new_definition', '')[:2000]}"
            raise DeploymentValidationError(
                msg,
                code="DEPLOYMENT_VALIDATION_FAILED",
                hint="Fix disabled metrics or version conflicts before deploying.",
                context={
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                    "disabled_metrics": validation.disabled_metrics,
                    "conflict_details": validation.conflict_details,
                },
                result=validation,
            )

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan = DeploymentPlan(schema=self.schema, generated_at=generated_at, warnings=validation.warnings)

        metrics = self.indexer.list_metrics() or []
        deployed = {r["view_name"]: r for r in self.indexer.list_deployed_views()}

        for m in metrics:
            metric_name = m.get("name")
            if not metric_name:
                continue
            status = (m.get("status") or "active").strip().lower()
            if status == "disabled":
                continue  # Skip disabled metrics; do not include in plan
            intent = build_intent_from_metric(self.indexer, metric_name)
            if not intent:
                continue
            metric_version = getattr(intent, "metric_version", None) or "1.0"
            include_version = self.version_coexistence
            full_name = view_full_name(metric_name, schema=self.schema, version=metric_version if include_version else None)
            replacement_metric = m.get("replacement_metric") or None
            in_deployed = full_name in deployed
            use_replace = in_deployed and self.replace_existing
            try:
                sql = generate_create_view_sql(
                    intent,
                    schema=self.schema,
                    warehouse=self.warehouse,
                    replace=use_replace,
                    include_version_in_name=include_version,
                    status=status,
                    replacement_metric=replacement_metric,
                    contract_mode=self.contract_mode,
                )
            except MetricDisabledError:
                continue

            if in_deployed and self.replace_existing:
                plan.replace.append(PlanAction(
                    action="replace",
                    view_name=full_name,
                    metric_name=metric_name,
                    metric_version=metric_version,
                    sql=sql,
                    deprecated=bool(deployed[full_name].get("deprecated")),
                    reason="view exists, replace requested",
                ))
            else:
                plan.create.append(PlanAction(
                    action="create",
                    view_name=full_name,
                    metric_name=metric_name,
                    metric_version=metric_version,
                    sql=sql,
                    reason="new metric view",
                ))

        for view_name, rec in deployed.items():
            if rec.get("deprecated"):
                plan.drop.append(PlanAction(
                    action="drop",
                    view_name=view_name,
                    metric_name=rec.get("metric_name", ""),
                    metric_version=rec.get("metric_version", ""),
                    sql=f"DROP VIEW IF EXISTS {view_name};",
                    deprecated=True,
                    reason="deprecated view",
                ))

        return plan

    def plan_drop_deprecated(self) -> DeploymentPlan:
        """Plan only: drop deprecated views. No execution."""
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        plan = DeploymentPlan(schema=self.schema, generated_at=generated_at)
        for rec in self.indexer.list_deployed_views(deprecated_only=True):
            view_name = rec.get("view_name")
            if not view_name:
                continue
            plan.drop.append(PlanAction(
                action="drop",
                view_name=view_name,
                metric_name=rec.get("metric_name", ""),
                metric_version=rec.get("metric_version", ""),
                sql=f"DROP VIEW IF EXISTS {view_name};",
                deprecated=True,
                reason="deprecated",
            ))
        return plan
