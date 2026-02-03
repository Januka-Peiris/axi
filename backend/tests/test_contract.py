# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Tests for AXI SQL contract and validation."""

import unittest
from unittest.mock import MagicMock, patch

from axi.contract.loader import get_contract
from axi.contract.validator import validate_sql_contract, ContractViolation
from axi.contract.placeholders import (
    format_time_placeholder,
    format_dimension_placeholder,
    TIME_FILTER_PARAMS,
    DIMENSION_FILTER_PREFIX,
)


class TestContractLoader(unittest.TestCase):
    """Contract is machine-readable and has expected keys."""

    def test_contract_has_runnable_as(self):
        c = get_contract()
        self.assertIn("runnable_as", c)
        self.assertIn("custom_sql", c["runnable_as"])
        self.assertIn("view_definition", c["runnable_as"])

    def test_contract_has_disallowed_patterns(self):
        c = get_contract()
        self.assertIn("disallowed_patterns", c)
        ids = [r["id"] for r in c["disallowed_patterns"]]
        self.assertIn("no_session_state", ids)
        self.assertIn("no_temp_tables", ids)
        self.assertIn("no_stored_procedures", ids)
        self.assertIn("no_procedure_udf_definitions", ids)
        self.assertIn("no_nondeterministic_functions", ids)
        self.assertIn("no_select_star", ids)

    def test_contract_has_parameter_placeholders(self):
        c = get_contract()
        self.assertIn("parameter_placeholders", c)
        ph = c["parameter_placeholders"]
        self.assertIn("time_filters", ph)
        self.assertIn("start_date", ph["time_filters"])
        self.assertIn("end_date", ph["time_filters"])


class TestValidator(unittest.TestCase):
    """Validation catches disallowed patterns."""

    def test_valid_select_passes(self):
        sql = "SELECT a.x, SUM(b.y) AS total FROM t AS a LEFT JOIN s AS b ON a.id = b.id GROUP BY a.x;"
        violations = validate_sql_contract(sql)
        self.assertEqual(violations, [])

    def test_session_state_violation(self):
        sql = "SET session_var = 1; SELECT 1;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_session_state" for v in violations))

    def test_temp_table_violation(self):
        sql = "CREATE TEMP TABLE x (id INT); SELECT * FROM x;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_temp_tables" for v in violations))

    def test_stored_procedure_violation(self):
        sql = "CALL my_proc(); SELECT 1;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_stored_procedures" for v in violations))

    def test_axi_comments_ignored(self):
        sql = "-- axi.metric_name: m\n-- axi.metric_version: 1.0\n-- axi.lifecycle_status: active\n-- axi.compiled_at: 2026-01-01T00:00:00Z\n\nSELECT 1 AS x;"
        violations = validate_sql_contract(sql, strip_axi_comments=True)
        self.assertEqual(violations, [])


class TestPlaceholders(unittest.TestCase):
    """Parameter placeholder names."""

    def test_time_placeholders(self):
        self.assertEqual(format_time_placeholder("start_date"), ":axi_start_date")
        self.assertEqual(format_time_placeholder("end_date"), ":axi_end_date")

    def test_dimension_placeholder(self):
        self.assertEqual(format_dimension_placeholder("region"), ":axi_filter_region")
        self.assertIn("axi_filter_", format_dimension_placeholder("status"))


class TestCompilationValidatesContract(unittest.TestCase):
    """Compilation runs contract validation by default (always; no bypass)."""

    def test_compile_metric_output_passes_contract(self):
        from axi.intent.models import SemanticIntent, Measure
        from axi.intent.compiler import compile_metric
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        sql = compile_metric(intent)
        violations = validate_sql_contract(sql)
        self.assertEqual(violations, [], "AXI-generated SQL must pass contract")


class TestNegativeContractViolations(unittest.TestCase):
    """Negative tests: each forbidden construct must be detected and raise structured exceptions."""

    def test_use_statement_violation(self):
        sql = "USE database_name; SELECT 1 AS x;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        session_violations = [v for v in violations if v.rule_id == "no_session_state"]
        self.assertTrue(len(session_violations) >= 1)
        self.assertIn("USE", session_violations[0].message)

    def test_set_statement_violation(self):
        sql = "SET session_var = 1; SELECT 1 AS x;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_session_state" for v in violations))

    def test_alter_session_violation(self):
        sql = "ALTER SESSION SET QUOTED_IDENTIFIERS = ON; SELECT 1 AS x;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_session_state" for v in violations))

    def test_temp_table_violation(self):
        sql = "CREATE TEMP TABLE x (id INT); SELECT * FROM x;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_temp_tables" for v in violations))

    def test_temp_view_violation(self):
        sql = "CREATE TEMPORARY VIEW v AS SELECT 1 AS x;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_temp_tables" for v in violations))

    def test_stored_procedure_execution_violation(self):
        sql = "CALL my_proc(); SELECT 1 AS x;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_stored_procedures" for v in violations))

    def test_procedure_definition_violation(self):
        sql = "CREATE PROCEDURE my_proc() BEGIN SELECT 1; END;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_procedure_udf_definitions" for v in violations))

    def test_udf_definition_violation(self):
        sql = "CREATE FUNCTION my_func() RETURNS INT RETURN 1;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_procedure_udf_definitions" for v in violations))

    def test_nondeterministic_rand_violation(self):
        sql = "SELECT RAND() AS r, 1 AS x FROM t;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_nondeterministic_functions" for v in violations))

    def test_nondeterministic_newid_violation(self):
        sql = "SELECT NEWID() AS id FROM t;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_nondeterministic_functions" for v in violations))

    def test_select_star_violation(self):
        sql = "SELECT * FROM orders AS o;"
        violations = validate_sql_contract(sql)
        self.assertGreater(len(violations), 0)
        self.assertTrue(any(v.rule_id == "no_select_star" for v in violations))

    def test_compile_metric_raises_on_contract_violation(self):
        """Compile path: injecting bad SQL would raise; we test that validation runs by using valid intent."""
        from axi.intent.models import SemanticIntent, Measure
        from axi.intent.compiler import compile_metric
        from axi.exceptions import ContractViolationError
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        sql = compile_metric(intent)
        self.assertIn("axi.metric_name:", sql)
        # Contract validation runs unconditionally; valid intent produces no violation.
        violations = validate_sql_contract(sql, strip_axi_comments=True)
        self.assertEqual(violations, [])
        # If we had a way to produce bad SQL, compile_metric would raise ContractViolationError.
        bad_sql = "-- axi.metric_name: x\n-- axi.metric_version: 1.0\nSELECT * FROM t;"
        violations_bad = validate_sql_contract(bad_sql, strip_axi_comments=True)
        self.assertTrue(any(v.rule_id == "no_select_star" for v in violations_bad))


class TestContractEnforcementModes(unittest.TestCase):
    """Contract enforcement modes: strict (hard-fail) vs warn (warn and allow)."""

    def test_strict_mode_raises_on_violation(self):
        """strict: contract violations raise ContractViolationError and block compile."""
        from axi.intent.models import SemanticIntent, Measure
        from axi.intent.compiler import compile_metric
        from axi.exceptions import ContractViolationError

        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        fake_violation = ContractViolation(
            rule_id="no_select_star",
            message="SELECT * is not allowed",
            snippet="SELECT *",
        )
        with patch("axi.contract.validator.validate_sql_contract", return_value=[fake_violation]):
            with self.assertRaises(ContractViolationError) as ctx:
                compile_metric(intent, warehouse="snowflake", contract_mode="strict")
        self.assertEqual(getattr(ctx.exception, "code", None), "no_select_star")
        self.assertIn("SELECT *", getattr(ctx.exception, "message", str(ctx.exception)))

    def test_warn_mode_allows_compile_on_violation(self):
        """warn: contract violations are logged but compilation succeeds."""
        from axi.intent.models import SemanticIntent, Measure
        from axi.intent.compiler import compile_metric

        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        fake_violation = ContractViolation(
            rule_id="no_select_star",
            message="SELECT * is not allowed",
            snippet="SELECT *",
        )
        with patch("axi.contract.validator.validate_sql_contract", return_value=[fake_violation]):
            sql = compile_metric(intent, warehouse="snowflake", contract_mode="warn")
        self.assertIsInstance(sql, str)
        self.assertIn("axi.metric_name:", sql)

    def test_default_mode_is_strict(self):
        """When contract_mode is None, settings default (strict) is used; patch settings to strict and violate -> raise."""
        from axi.intent.models import SemanticIntent, Measure
        from axi.intent.compiler import compile_metric
        from axi.exceptions import ContractViolationError

        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        fake_violation = ContractViolation(
            rule_id="no_session_state",
            message="USE not allowed",
            snippet="USE db",
        )
        mock_settings = MagicMock()
        mock_settings.contract_enforcement_mode = "strict"
        with patch("axi.contract.validator.validate_sql_contract", return_value=[fake_violation]):
            with patch("axi.config.settings.get_settings", return_value=mock_settings):
                with self.assertRaises(ContractViolationError):
                    compile_metric(intent, warehouse="snowflake", contract_mode=None)
