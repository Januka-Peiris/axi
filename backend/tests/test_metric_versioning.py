# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Tests for metric versioning and deprecation."""

import unittest

from axi.metrics.versioning import version_compare, is_breaking_change, diff_metrics
from axi.intent.compiler import compile_metric
from axi.intent.models import SemanticIntent, Measure
from axi.exceptions import MetricDisabledError


class TestVersionCompare(unittest.TestCase):
    """Version comparison: explicit, never inferred."""

    def test_equal(self):
        self.assertEqual(version_compare("1.0", "1.0"), 0)
        self.assertEqual(version_compare("2", "2"), 0)
        self.assertEqual(version_compare("1.0.0", "1.0.0"), 0)

    def test_less(self):
        self.assertEqual(version_compare("1.0", "1.1"), -1)
        self.assertEqual(version_compare("1", "2"), -1)
        self.assertEqual(version_compare("1.0.0", "1.0.1"), -1)

    def test_greater(self):
        self.assertEqual(version_compare("1.1", "1.0"), 1)
        self.assertEqual(version_compare("2", "1"), 1)
        self.assertEqual(version_compare("1.0.1", "1.0.0"), 1)


class TestIsBreakingChange(unittest.TestCase):
    """Breaking change detection."""

    def test_no_breaking(self):
        m = {"expression": "SUM(x)", "grain": ["a"], "dimensions": ["a"], "aggregation": "sum", "model": "t"}
        is_breaking, reasons = is_breaking_change(m, m)
        self.assertFalse(is_breaking)
        self.assertEqual(reasons, [])

    def test_expression_change(self):
        old = {"expression": "SUM(x)", "grain": [], "dimensions": [], "aggregation": "sum", "model": "t"}
        new = {"expression": "SUM(y)", "grain": [], "dimensions": [], "aggregation": "sum", "model": "t"}
        is_breaking, reasons = is_breaking_change(old, new)
        self.assertTrue(is_breaking)
        self.assertIn("expression changed", reasons)

    def test_grain_change(self):
        old = {"expression": "SUM(x)", "grain": ["a"], "dimensions": ["a"], "aggregation": "sum", "model": "t"}
        new = {"expression": "SUM(x)", "grain": ["b"], "dimensions": ["b"], "aggregation": "sum", "model": "t"}
        is_breaking, reasons = is_breaking_change(old, new)
        self.assertTrue(is_breaking)
        self.assertIn("grain changed", reasons)


class TestDiffMetrics(unittest.TestCase):
    """Human-readable diff."""

    def test_no_diff(self):
        m = {"name": "m", "expression": "SUM(x)", "model": "t"}
        out = diff_metrics(m, m, name_a="m", name_b="m")
        self.assertIn("no differences", out)

    def test_diff_expression(self):
        a = {"name": "m", "expression": "SUM(x)", "model": "t", "version": "1.0"}
        b = {"name": "m", "expression": "SUM(y)", "model": "t", "version": "1.0"}
        out = diff_metrics(a, b, name_a="m", name_b="m")
        self.assertIn("expression", out)
        self.assertIn("SUM(x)", out)
        self.assertIn("SUM(y)", out)


class TestCompileMetricStatus(unittest.TestCase):
    """Compiler: warn deprecated, fail disabled."""

    def test_disabled_raises(self):
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        with self.assertRaises(MetricDisabledError) as ctx:
            compile_metric(intent, status="disabled")
        self.assertIn("disabled", str(ctx.exception).lower())

    def test_deprecated_adds_warning(self):
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        sql = compile_metric(intent, status="deprecated", replacement_metric="new_metric")
        self.assertIn("axi.lifecycle_status: deprecated", sql)
        self.assertIn("axi.deprecated: true", sql)
        self.assertIn("axi.replacement_metric", sql)
        self.assertIn("new_metric", sql)
        self.assertIn("WARNING", sql)
