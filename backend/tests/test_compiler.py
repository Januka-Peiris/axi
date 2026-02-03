# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Unit tests for AXI Metric SQL Compiler using real AXI-extracted models."""

import json
import os
import unittest
from datetime import datetime, timezone

from axi.intent.models import (
    SemanticIntent,
    Measure,
    TimeDimension,
    JoinStep,
    SimpleFilter,
)
from axi.intent.compiler import (
    compile_metric,
    resolve_plan,
    emit_sql,
    QueryPlan,
)


def _metadata_store_path() -> str:
    """Path to metadata_store from repo root (backend/../metadata_store)."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "metadata_store")


def _load_intent(name: str) -> SemanticIntent:
    """Load intent from metadata_store/intents/<name>_intent.json."""
    path = os.path.join(_metadata_store_path(), "intents", f"{name}_intent.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Intent file not found: {path}")
    with open(path) as f:
        return SemanticIntent.model_validate(json.load(f))


class TestCompileMetricRealModels(unittest.TestCase):
    """Compile intents generated from real AXI-extracted models (metadata_store)."""

    def setUp(self):
        self.fixed_ts = datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc)

    def test_mrr_intent_compiles_to_readable_sql(self):
        """mrr intent (revenue model, orders+customers) compiles to valid Snowflake SQL."""
        intent = _load_intent("mrr")
        sql = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)

        self.assertIn("axi.metric_name: mrr", sql)
        self.assertIn("axi.metric_version: 1.0", sql)
        self.assertIn("axi.lifecycle_status:", sql)
        self.assertIn("axi.compiled_at: 2026-02-03T12:00:00Z", sql)
        self.assertIn("SELECT", sql)
        self.assertIn("SUM(o.amount) AS", sql)
        self.assertIn("FROM orders AS o", sql)
        self.assertIn("INNER JOIN customers AS c ON o.customer_id = c.id", sql)
        self.assertIn("WHERE o.status = 'active'", sql)
        self.assertIn("GROUP BY", sql)
        self.assertIn("c.region", sql)
        self.assertNotIn("deprecated", sql)
        self.assertTrue(sql.strip().endswith(";"))

    def test_mrr_intent_deterministic(self):
        """Same intent + same generated_at produces identical SQL."""
        intent = _load_intent("mrr")
        sql1 = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)
        sql2 = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)
        self.assertEqual(sql1, sql2)

    def test_mrr_intent_deprecated_comment(self):
        """deprecated=True adds deprecated comment."""
        intent = _load_intent("mrr")
        sql = compile_metric(intent, warehouse="snowflake", deprecated=True, generated_at=self.fixed_ts)
        self.assertIn("axi.lifecycle_status: deprecated", sql)
        self.assertIn("axi.deprecated: true", sql)

    def test_order_count_intent_single_table(self):
        """order_count intent (orders model only) compiles to single-table query."""
        intent = _load_intent("order_count")
        sql = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)

        self.assertIn("axi.metric_name: order_count", sql)
        self.assertIn("COUNT(*) AS", sql)
        self.assertIn("FROM orders AS o", sql)
        self.assertNotIn("JOIN", sql)
        self.assertIn("GROUP BY", sql)

    def test_total_amount_intent_single_table(self):
        """total_amount intent compiles to single-table aggregate."""
        intent = _load_intent("total_amount")
        sql = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)

        self.assertIn("SUM(amount) AS", sql)
        self.assertIn("FROM orders AS o", sql)
        self.assertNotIn("JOIN", sql)

    def test_compile_does_not_execute(self):
        """compile_metric returns a string; no execution."""
        intent = _load_intent("mrr")
        result = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)
        self.assertIsInstance(result, str)
        self.assertNotIn("execute", result.lower())
        self.assertNotIn("cursor", result.lower())


class TestResolvePlan(unittest.TestCase):
    """Test query plan resolution (grain, joins, filters, time)."""

    def test_plan_has_joins_from_intent(self):
        intent = _load_intent("mrr")
        plan = resolve_plan(intent, "snowflake")
        self.assertEqual(plan.base_table, "orders")
        self.assertEqual(plan.base_alias, "o")
        self.assertEqual(len(plan.joins), 1)
        self.assertEqual(plan.joins[0][0], "customers")
        self.assertEqual(plan.joins[0][4], "inner")
        self.assertIn("o.status = 'active'", plan.where_clauses[0])

    def test_plan_single_table_no_joins(self):
        intent = _load_intent("order_count")
        plan = resolve_plan(intent, "snowflake")
        self.assertEqual(plan.base_table, "orders")
        self.assertEqual(len(plan.joins), 0)
        self.assertEqual(len(plan.where_clauses), 0)


class TestEmitSql(unittest.TestCase):
    """Test SQL emission from plan."""

    def test_emit_readable_and_copy_pasteable(self):
        intent = _load_intent("mrr")
        plan = resolve_plan(intent, "snowflake")
        sql = emit_sql(plan, "snowflake")
        self.assertIn("SELECT\n", sql)
        self.assertIn("FROM ", sql)
        self.assertIn("GROUP BY", sql)
        self.assertNotIn("  \n", sql)  # no double spaces from formatting


class TestCompileMetricInlineIntent(unittest.TestCase):
    """Test compile_metric with inline intent (no file)."""

    def test_minimal_intent_compiles(self):
        intent = SemanticIntent(
            metric_name="test_metric",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
            dimensions=["orders.status"],
        )
        sql = compile_metric(intent, warehouse="snowflake")
        self.assertIn("axi.metric_name: test_metric", sql)
        self.assertIn("SUM(o.amount)", sql)
        self.assertIn("FROM orders AS o", sql)
        self.assertIn("GROUP BY o.status", sql)

    def test_time_dimension_with_granularity(self):
        intent = SemanticIntent(
            metric_name="monthly_mrr",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="mrr", column_ref="orders.amount", aggregation="sum")],
            dimensions=[],
            time_dimension=TimeDimension(
                name="month",
                column_ref="orders.created_at",
                granularity="month",
            ),
        )
        sql = compile_metric(intent, warehouse="snowflake")
        self.assertIn("DATE_TRUNC('MONTH', o.created_at)", sql)
        self.assertIn("GROUP BY", sql)


if __name__ == "__main__":
    unittest.main()
