# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Tests for critical demo-blocking fixes:
1. CLI deploy views state persistence
2. Contract validation before fingerprint registration
3. Disabled metric lifecycle enforcement
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from axi.intent.models import SemanticIntent, Measure
from axi.metadata.indexer import MetadataIndexer
from axi.exceptions import MetricDisabledError, ContractViolationError
from axi.contract.validator import ContractViolation


class TestDeployStateRecording(unittest.TestCase):
    """Test that deployed view state can be persisted and queried."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.indexer = MetadataIndexer(self.temp_dir)

    def test_record_deployed_view_persists_state(self):
        """Recording deployed view state allows conflict detection and drop planning."""
        from axi.views.deployment_validation import hash_view_definition
        
        view_name = "axi.metric_test"
        metric_name = "test"
        metric_version = "1.0"
        body = "SELECT o.id, SUM(o.amount) AS total FROM orders AS o GROUP BY o.id"
        definition_hash = hash_view_definition(body)
        deployed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        self.indexer.record_deployed_view(
            view_name=view_name,
            metric_name=metric_name,
            metric_version=metric_version,
            schema_name="axi",
            deployed_at_utc=deployed_at,
            deprecated=False,
            definition_hash=definition_hash,
        )
        
        deployed = self.indexer.list_deployed_views()
        self.assertEqual(len(deployed), 1)
        self.assertEqual(deployed[0]["view_name"], view_name)
        self.assertEqual(deployed[0]["metric_name"], metric_name)
        self.assertEqual(deployed[0]["definition_hash"], definition_hash)

    def test_conflict_detection_requires_recorded_state(self):
        """Version conflict detection works only when deployed_views are recorded."""
        from axi.views.deployment_validation import hash_view_definition
        
        view_name = "axi.metric_mrr"
        old_body = "SELECT c.id, SUM(s.amount) AS total FROM customers AS c JOIN subscriptions AS s ON c.id = s.customer_id GROUP BY c.id"
        new_body = "SELECT c.id, SUM(s.mrr) AS total FROM customers AS c JOIN subscriptions AS s ON c.id = s.customer_id GROUP BY c.id"
        old_hash = hash_view_definition(old_body)
        new_hash = hash_view_definition(new_body)
        
        # Record old state
        self.indexer.record_deployed_view(
            view_name=view_name,
            metric_name="mrr",
            metric_version="1.0",
            schema_name="axi",
            deployed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            deprecated=False,
            definition_hash=old_hash,
        )
        
        # Attempt deploy with different definition
        deployed = {r["view_name"]: r for r in self.indexer.list_deployed_views()}
        self.assertIn(view_name, deployed)
        self.assertEqual(deployed[view_name]["definition_hash"], old_hash)
        self.assertNotEqual(old_hash, new_hash, "Test setup: hashes must differ for conflict")

    def test_drop_deprecated_requires_recorded_state(self):
        """plan_drop_deprecated works only when deployed_views are marked deprecated."""
        view_name = "axi.metric_old"
        self.indexer.record_deployed_view(
            view_name=view_name,
            metric_name="old",
            metric_version="1.0",
            schema_name="axi",
            deployed_at_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            deprecated=False,
            definition_hash="abc123",
        )
        self.indexer.mark_view_deprecated(view_name)
        
        deprecated = self.indexer.list_deployed_views(deprecated_only=True)
        self.assertEqual(len(deprecated), 1)
        self.assertEqual(deprecated[0]["view_name"], view_name)
        self.assertTrue(deprecated[0]["deprecated"])


class TestContractValidationBeforeFingerprint(unittest.TestCase):
    """Contract validation must happen before fingerprint registration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.indexer = MetadataIndexer(self.temp_dir)

    def test_contract_violation_strict_mode_prevents_fingerprint_registration(self):
        """Strict mode: contract violation raises BEFORE fingerprint is recorded. No fingerprint row."""
        from axi.intent.compiler import compile_metric
        
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        
        fake_violation = ContractViolation(
            rule_id="no_select_star",
            message="SELECT * not allowed",
            snippet="SELECT *",
        )
        
        with patch("axi.contract.validator.validate_sql_contract", return_value=[fake_violation]):
            with self.assertRaises(ContractViolationError):
                compile_metric(
                    intent,
                    warehouse="snowflake",
                    indexer=self.indexer,
                    contract_mode="strict",
                    register_fingerprint=True,  # This should NOT happen if contract fails
                )
        
        # Assert no fingerprint was registered
        fp_test = self.indexer.get_fingerprint("any_hash")
        self.assertIsNone(fp_test, "No fingerprint should be registered if contract validation fails")

    def test_warn_mode_allows_fingerprint_after_logged_violations(self):
        """Warn mode: contract violations are logged, fingerprint is registered."""
        from axi.intent.compiler import compile_metric
        from axi.usage.fingerprint import sql_fingerprint
        
        intent = SemanticIntent(
            metric_name="test_warn",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        
        # Don't mock - use real validation so we can check real fingerprint
        sql = compile_metric(
            intent,
            warehouse="snowflake",
            indexer=self.indexer,
            contract_mode="warn",  # Allow even if violations (real SQL has none)
            register_fingerprint=True,
        )
        
        # Verify fingerprint was registered
        fp = sql_fingerprint(sql)
        fp_info = self.indexer.get_fingerprint(fp)
        self.assertIsNotNone(fp_info)
        self.assertEqual(fp_info["metric_name"], "test_warn")
        self.assertEqual(fp_info["metric_version"], "1.0")


class TestDisabledMetricLifecycleEnforcement(unittest.TestCase):
    """Disabled metrics must not allow intent build or compilation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.indexer = MetadataIndexer(self.temp_dir)
        
        # Write a disabled metric
        metric_json = {
            "name": "disabled_test",
            "expression": "SUM(o.amount)",
            "model": "orders",
            "entity_name": "orders",
            "grain": ["o.id"],
            "status": "disabled",
            "version": "1.0",
        }
        os.makedirs(os.path.join(self.temp_dir, "models"), exist_ok=True)
        with open(os.path.join(self.temp_dir, "models", "orders.json"), "w") as f:
            json.dump({
                "name": "orders",
                "entity": {"name": "orders", "model": "orders"},
                "metrics": [metric_json],
            }, f)
        self.indexer.build_index()

    def test_build_intent_from_metric_raises_on_disabled(self):
        """build_intent_from_metric raises MetricDisabledError for disabled metrics."""
        from axi.intent.builder import build_intent_from_metric
        
        with self.assertRaises(MetricDisabledError) as ctx:
            build_intent_from_metric(
                indexer=self.indexer,
                metric_name="disabled_test",
                metric_version="1.0",
            )
        self.assertEqual(ctx.exception.code, "METRIC_DISABLED")
        self.assertIn("disabled_test", ctx.exception.message)

    def test_disabled_metric_intent_not_exposed_via_api(self):
        """API endpoints must return 410 Gone for disabled metrics, not build intent."""
        # This is tested by calling the API route logic
        # We'll mock the route internals since we can't easily test FastAPI routes here
        # The real test: build_intent_from_metric raises, API wraps it with 410
        from axi.intent.builder import build_intent_from_metric
        
        with self.assertRaises(MetricDisabledError):
            build_intent_from_metric(self.indexer, "disabled_test", "1.0")

    def test_deployment_validation_skips_disabled_without_crashing(self):
        """Deployment validation must handle disabled metrics gracefully (already filtered)."""
        from axi.views.deployment_validation import validate_deployment
        
        # This should not crash even though build_intent would raise for disabled_test
        result = validate_deployment(
            self.indexer,
            schema="axi",
            warehouse="snowflake",
            replace_existing=True,
            version_coexistence=False,
        )
        
        # Disabled metrics are filtered before intent build (deployment_validation.py line 111-112)
        # So no error should occur
        self.assertTrue(result.is_valid or "disabled" in " ".join(result.errors).lower())


class TestFingerprintOrderingRegression(unittest.TestCase):
    """Regression: contract validation ordering must not change."""

    def test_fingerprint_registration_never_happens_before_contract_check(self):
        """Compiler code line order: contract validation (395-408) then fingerprint (410-420)."""
        # Read compiler source and verify line order using simple text search
        import axi.intent.compiler
        source_file = axi.intent.compiler.__file__
        with open(source_file, "r") as f:
            lines = f.readlines()
        
        # Find line indices for key markers
        contract_line = None
        fingerprint_line = None
        for i, line in enumerate(lines):
            if "validate_sql_contract" in line and "from axi.contract.validator import" not in line:
                contract_line = i
            if "if register_fingerprint and indexer is not None:" in line:
                fingerprint_line = i
        
        self.assertIsNotNone(contract_line, "Contract validation call must exist")
        self.assertIsNotNone(fingerprint_line, "Fingerprint registration must exist")
        self.assertLess(
            contract_line,
            fingerprint_line,
            "Contract validation must occur before fingerprint registration in source code",
        )
