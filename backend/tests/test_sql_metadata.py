# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Tests for centralized SQL metadata emission: deterministic output and fingerprint equality."""

import unittest
from datetime import datetime, timezone

from axi.sql_metadata import emit_axi_sql_metadata, format_axi_sql_header
from axi.intent.models import SemanticIntent, Measure
from axi.intent.compiler import compile_metric
from axi.usage.fingerprint import sql_fingerprint


class TestSqlMetadataEmitter(unittest.TestCase):
    """Centralized SQL comment emitter: required keys and deterministic order."""

    def test_emit_includes_required_keys(self):
        lines = emit_axi_sql_metadata(
            metric_name="mrr",
            metric_version="1.0",
            lifecycle_status="active",
            compiled_at_utc_iso8601="2026-02-03T12:00:00Z",
        )
        flat = " ".join(lines)
        self.assertIn("axi.metric_name: mrr", flat)
        self.assertIn("axi.metric_version: 1.0", flat)
        self.assertIn("axi.lifecycle_status: active", flat)
        self.assertIn("axi.compiled_at: 2026-02-03T12:00:00Z", flat)
        self.assertEqual(len(lines), 4)

    def test_emit_deprecated_includes_replacement(self):
        lines = emit_axi_sql_metadata(
            metric_name="old_mrr",
            metric_version="1.0",
            lifecycle_status="deprecated",
            compiled_at_utc_iso8601="2026-02-03T12:00:00Z",
            replacement_metric="mrr_v2",
        )
        flat = " ".join(lines)
        self.assertIn("axi.lifecycle_status: deprecated", flat)
        self.assertIn("axi.deprecated: true", flat)
        self.assertIn("axi.replacement_metric: mrr_v2", flat)

    def test_emit_deterministic_order(self):
        lines1 = emit_axi_sql_metadata(
            metric_name="x", metric_version="1.0", lifecycle_status="active",
            compiled_at_utc_iso8601="2026-01-01T00:00:00Z",
        )
        lines2 = emit_axi_sql_metadata(
            metric_name="x", metric_version="1.0", lifecycle_status="active",
            compiled_at_utc_iso8601="2026-01-01T00:00:00Z",
        )
        self.assertEqual(lines1, lines2)
        self.assertEqual(lines1[0], "-- axi.metric_name: x")
        self.assertEqual(lines1[1], "-- axi.metric_version: 1.0")
        self.assertEqual(lines1[2], "-- axi.lifecycle_status: active")
        self.assertEqual(lines1[3], "-- axi.compiled_at: 2026-01-01T00:00:00Z")

    def test_format_header_ends_with_blank_line(self):
        header = format_axi_sql_header(
            metric_name="m",
            metric_version="1.0",
            lifecycle_status="active",
            compiled_at_utc_iso8601="2026-01-01T00:00:00Z",
        )
        self.assertTrue(header.endswith("\n\n"))
        self.assertIn("axi.metric_name: m", header)
        self.assertIn("axi.compiled_at: 2026-01-01T00:00:00Z", header)


class TestCompiledSqlDeterminism(unittest.TestCase):
    """Compiled SQL and fingerprint: deterministic output, equality implies fingerprint equality."""

    def setUp(self):
        self.fixed_ts = datetime(2026, 2, 3, 12, 0, 0, tzinfo=timezone.utc)

    def test_same_inputs_same_sql(self):
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        sql1 = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)
        sql2 = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)
        self.assertEqual(sql1, sql2)

    def test_sql_equality_implies_fingerprint_equality(self):
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        sql1 = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)
        sql2 = compile_metric(intent, warehouse="snowflake", generated_at=self.fixed_ts)
        self.assertEqual(sql1, sql2)
        fp1 = sql_fingerprint(sql1)
        fp2 = sql_fingerprint(sql2)
        self.assertEqual(fp1, fp2, "SQL text equality must imply fingerprint equality")

    def test_different_compiled_at_different_sql_same_body_fingerprint(self):
        """Fingerprint normalizes comments; different compiled_at => different full SQL but same fingerprint (body only)."""
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        ts1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        sql1 = compile_metric(intent, warehouse="snowflake", generated_at=ts1)
        sql2 = compile_metric(intent, warehouse="snowflake", generated_at=ts2)
        self.assertNotEqual(sql1, sql2, "Different compiled_at must produce different SQL (metadata differs)")
        fp1 = sql_fingerprint(sql1)
        fp2 = sql_fingerprint(sql2)
        self.assertEqual(fp1, fp2, "Same body => same fingerprint (comments stripped for matching)")


if __name__ == "__main__":
    unittest.main()
