# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Tests for governed semantic views (view SQL generator, deployment planner)."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from axi.intent.models import SemanticIntent, Measure, JoinStep
from axi.views.view_sql import view_full_name, generate_create_view_sql
from axi.views.planner import DeploymentPlanner, DeploymentPlan, PlanAction
from axi.metadata.indexer import MetadataIndexer


def _metadata_store_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "metadata_store")


def _load_intent(name: str) -> SemanticIntent:
    path = os.path.join(_metadata_store_path(), "intents", f"{name}_intent.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path) as f:
        return SemanticIntent.model_validate(json.load(f))


class TestViewFullName(unittest.TestCase):
    """Test view naming: axi.metric_<name>[_v<version>]."""

    def test_basic_name(self):
        self.assertEqual(view_full_name("mrr", schema="axi"), "axi.metric_mrr")
        self.assertEqual(view_full_name("order_count", schema="axi"), "axi.metric_order_count")

    def test_with_version_coexistence(self):
        self.assertEqual(
            view_full_name("mrr", schema="axi", version="1.0"),
            "axi.metric_mrr_v1_0",
        )
        self.assertEqual(
            view_full_name("mrr", schema="axi", version="2"),
            "axi.metric_mrr_v2",
        )

    def test_no_schema(self):
        self.assertEqual(view_full_name("mrr", schema=""), "metric_mrr")


class TestGenerateCreateViewSql(unittest.TestCase):
    """Test CREATE VIEW SQL generation with governance comments."""

    def test_create_view_has_governance_comments(self):
        intent = _load_intent("mrr")
        ddl = generate_create_view_sql(intent, schema="axi", replace=False)
        self.assertIn("axi.metric_name: mrr", ddl)
        self.assertIn("axi.metric_version: 1.0", ddl)
        self.assertIn("axi.lifecycle_status:", ddl)
        self.assertIn("axi.compiled_at:", ddl)
        self.assertIn("axi.view_name: axi.metric_mrr", ddl)
        self.assertIn("CREATE VIEW axi.metric_mrr AS", ddl)
        self.assertIn("SELECT", ddl)
        self.assertIn("GROUP BY", ddl)
        self.assertNotIn("CREATE OR REPLACE", ddl)

    def test_replace_view(self):
        intent = _load_intent("mrr")
        ddl = generate_create_view_sql(intent, schema="axi", replace=True)
        self.assertIn("CREATE OR REPLACE VIEW axi.metric_mrr AS", ddl)

    def test_deprecated_flag(self):
        intent = _load_intent("mrr")
        ddl = generate_create_view_sql(intent, schema="axi", deprecated=True)
        self.assertIn("axi.lifecycle_status: deprecated", ddl)
        self.assertIn("axi.deprecated: true", ddl)

    def test_version_coexistence_in_name(self):
        intent = _load_intent("mrr")
        ddl = generate_create_view_sql(
            intent, schema="axi", include_version_in_name=True
        )
        self.assertIn("axi.metric_mrr_v1_0", ddl)
        self.assertIn("CREATE VIEW", ddl)

    def test_governed_view_body_passes_contract(self):
        """Governed view SQL is generated via compile_metric; body must pass contract (no bypass)."""
        from axi.contract.validator import validate_sql_contract
        intent = _load_intent("mrr")
        ddl = generate_create_view_sql(intent, schema="axi", replace=False)
        # Body is between "AS\n" and final "\n;"
        self.assertIn(" AS\n", ddl)
        body_start = ddl.index(" AS\n") + 4
        body_end = ddl.rfind("\n;")
        body = ddl[body_start:body_end].strip() if body_end > body_start else ddl[body_start:].strip()
        violations = validate_sql_contract(body, strip_axi_comments=False)
        self.assertEqual(violations, [], "Governed view body must comply with contract")

    def test_contract_mode_warn_allows_view_sql_on_violation(self):
        """generate_create_view_sql with contract_mode=warn succeeds when contract would be violated (e.g. mocked)."""
        from axi.contract.validator import ContractViolation
        fake_violation = ContractViolation(
            rule_id="no_select_star",
            message="SELECT * not allowed",
            snippet="SELECT *",
        )
        with patch("axi.contract.validator.validate_sql_contract", return_value=[fake_violation]):
            ddl = generate_create_view_sql(
                _load_intent("mrr"),
                schema="axi",
                contract_mode="warn",
            )
        self.assertIn("CREATE VIEW", ddl)
        self.assertIn("axi.metric_name: mrr", ddl)

    def test_contract_mode_strict_raises_on_violation_in_view_sql(self):
        """generate_create_view_sql with contract_mode=strict raises on contract violation."""
        from axi.contract.validator import ContractViolation
        from axi.exceptions import ContractViolationError
        fake_violation = ContractViolation(
            rule_id="no_select_star",
            message="SELECT * not allowed",
            snippet="SELECT *",
        )
        with patch("axi.contract.validator.validate_sql_contract", return_value=[fake_violation]):
            with self.assertRaises(ContractViolationError):
                generate_create_view_sql(
                    _load_intent("mrr"),
                    schema="axi",
                    contract_mode="strict",
                )


class TestDeploymentPlanner(unittest.TestCase):
    """Test deployment planner (create/replace/drop plan; no execution)."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.models_dir = os.path.join(self.temp_dir, "models")
        os.makedirs(self.models_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_model_json(self, name: str, data: dict):
        path = os.path.join(self.models_dir, f"{name}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def test_plan_creates_for_new_metrics(self):
        self._write_model_json("orders", {
            "model": "orders",
            "metrics": [
                {
                    "name": "order_count",
                    "expression": "COUNT(*)",
                    "aggregation": "count",
                    "grain": [],
                    "metric_type": "aggregate",
                }
            ],
            "dimensions": ["id", "status"],
            "filters": [],
            "source_tables": ["raw_orders"],
            "entity": {"name": "orders", "pk": "id", "columns": ["id", "status"]},
            "relationships": [],
        })
        indexer = MetadataIndexer(self.temp_dir)
        indexer.build_index()
        planner = DeploymentPlanner(indexer, schema="axi")
        plan = planner.plan()
        self.assertIsInstance(plan, DeploymentPlan)
        self.assertGreaterEqual(len(plan.create), 1)
        create_mrr = [a for a in plan.create if a.metric_name == "order_count"]
        self.assertEqual(len(create_mrr), 1)
        self.assertIn("CREATE VIEW axi.metric_order_count", create_mrr[0].sql or "")

    def test_plan_drop_deprecated_empty_without_state(self):
        indexer = MetadataIndexer(self.temp_dir)
        planner = DeploymentPlanner(indexer, schema="axi")
        plan = planner.plan_drop_deprecated()
        self.assertEqual(len(plan.drop), 0)


class TestDeploymentValidation(unittest.TestCase):
    """Deploy-time enforcement: disabled fails, deprecated warns, version conflict fails with diff."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.models_dir = os.path.join(self.temp_dir, "models")
        os.makedirs(self.models_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_model_json(self, name: str, data: dict):
        path = os.path.join(self.models_dir, f"{name}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def test_disabled_metric_fails_deployment(self):
        """Metrics with status=disabled MUST fail deployment."""
        from axi.exceptions import DeploymentValidationError
        self._write_model_json("orders", {
            "model": "orders",
            "metrics": [
                {
                    "name": "order_count",
                    "expression": "COUNT(*)",
                    "aggregation": "count",
                    "grain": [],
                    "metric_type": "aggregate",
                    "status": "disabled",
                }
            ],
            "dimensions": ["id", "status"],
            "filters": [],
            "entity": {"name": "orders", "pk": "id", "columns": ["id", "status"]},
            "relationships": [],
        })
        indexer = MetadataIndexer(self.temp_dir)
        indexer.build_index()
        planner = DeploymentPlanner(indexer, schema="axi")
        with self.assertRaises(DeploymentValidationError) as ctx:
            planner.plan()
        self.assertIn("disabled", str(ctx.exception).lower())
        result = getattr(ctx.exception, "result", None)
        self.assertIsNotNone(result)
        self.assertIn("order_count", result.disabled_metrics)
        self.assertFalse(result.is_valid)

    def test_deprecated_metric_deploys_with_warning(self):
        """Metrics with status=deprecated MUST deploy successfully and emit explicit warnings (replacement_metric)."""
        self._write_model_json("orders", {
            "model": "orders",
            "metrics": [
                {
                    "name": "legacy_mrr",
                    "expression": "SUM(amount)",
                    "aggregation": "sum",
                    "grain": [],
                    "metric_type": "aggregate",
                    "status": "deprecated",
                    "replacement_metric": "mrr_v2",
                }
            ],
            "dimensions": ["status"],
            "filters": [],
            "entity": {"name": "orders", "pk": "id", "columns": ["id", "amount", "status"]},
            "relationships": [],
        })
        indexer = MetadataIndexer(self.temp_dir)
        indexer.build_index()
        planner = DeploymentPlanner(indexer, schema="axi")
        plan = planner.plan()
        self.assertGreaterEqual(len(plan.create), 1)
        self.assertTrue(
            any("deprecated" in w.lower() and "legacy_mrr" in w for w in plan.warnings),
            f"Expected deprecated warning in {plan.warnings}",
        )
        self.assertTrue(
            any("mrr_v2" in w or "replacement" in w.lower() for w in plan.warnings),
            f"Expected replacement_metric in warnings: {plan.warnings}",
        )

    def test_version_conflict_fails_with_diff_output(self):
        """Version conflicts (same view name, different definition) MUST fail with diff output."""
        from axi.views.deployment_validation import hash_view_definition
        from axi.exceptions import DeploymentValidationError
        self._write_model_json("orders", {
            "model": "orders",
            "metrics": [
                {
                    "name": "order_count",
                    "expression": "COUNT(*)",
                    "aggregation": "count",
                    "grain": [],
                    "metric_type": "aggregate",
                }
            ],
            "dimensions": ["id", "status"],
            "filters": [],
            "entity": {"name": "orders", "pk": "id", "columns": ["id", "status"]},
            "relationships": [],
        })
        indexer = MetadataIndexer(self.temp_dir)
        indexer.build_index()
        # Record a deployed view with a different definition hash (simulating an older version)
        indexer.record_deployed_view(
            view_name="axi.metric_order_count",
            metric_name="order_count",
            metric_version="1.0",
            schema_name="axi",
            deployed_at_utc="2026-02-03T12:00:00Z",
            deprecated=False,
            definition_hash="old_hash_12345",
        )
        planner = DeploymentPlanner(indexer, schema="axi", replace_existing=True)
        with self.assertRaises(DeploymentValidationError) as ctx:
            planner.plan()
        result = getattr(ctx.exception, "result", None)
        self.assertIsNotNone(result)
        self.assertFalse(result.is_valid)
        self.assertTrue(
            any("conflict" in e.lower() or "different definition" in e.lower() for e in result.errors),
            f"Expected version conflict in errors: {result.errors}",
        )
        self.assertGreater(len(result.conflict_details), 0)
        self.assertIn("view_name", result.conflict_details[0])
        self.assertIn("new_definition", result.conflict_details[0])


class TestDeployedViewsState(unittest.TestCase):
    """Test deployed_views table and accessors."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.temp_dir, "models"), exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_record_and_list_deployed_views(self):
        indexer = MetadataIndexer(self.temp_dir)
        indexer.record_deployed_view(
            view_name="axi.metric_mrr",
            metric_name="mrr",
            metric_version="1.0",
            schema_name="axi",
            deployed_at_utc="2026-02-03T12:00:00Z",
            deprecated=False,
        )
        listed = indexer.list_deployed_views()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["view_name"], "axi.metric_mrr")
        self.assertEqual(listed[0]["metric_name"], "mrr")
        self.assertFalse(listed[0]["deprecated"])

    def test_mark_deprecated_and_drop_record(self):
        indexer = MetadataIndexer(self.temp_dir)
        indexer.record_deployed_view(
            view_name="axi.metric_old",
            metric_name="old",
            metric_version="1.0",
            schema_name="axi",
            deployed_at_utc="2026-02-03T12:00:00Z",
            deprecated=False,
        )
        indexer.mark_view_deprecated("axi.metric_old")
        deprecated = indexer.list_deployed_views(deprecated_only=True)
        self.assertEqual(len(deprecated), 1)
        self.assertTrue(deprecated[0]["deprecated"])
        indexer.remove_deployed_view("axi.metric_old")
        self.assertEqual(len(indexer.list_deployed_views()), 0)
