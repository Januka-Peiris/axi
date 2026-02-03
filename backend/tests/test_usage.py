# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Tests for query usage tracking: fingerprinting and aggregation."""

import os
import tempfile
import unittest

from axi.usage.fingerprint import normalize_sql_for_fingerprint, sql_fingerprint
from axi.usage.aggregator import (
    QueryLogRow,
    match_and_aggregate_usage,
    register_fingerprint,
)
from axi.usage.snowflake_logs import row_from_snowflake_log, rows_from_snowflake_logs
from axi.metadata.indexer import MetadataIndexer


class TestNormalizeSql(unittest.TestCase):
    """Normalization: comments stripped, literals replaced."""

    def test_strip_comments(self):
        sql = "SELECT 1 -- foo\nFROM t"
        out = normalize_sql_for_fingerprint(sql)
        self.assertNotIn("foo", out)
        self.assertIn("SELECT", out)
        self.assertIn("FROM", out)

    def test_strip_block_comment(self):
        sql = "SELECT /* comment */ 1 FROM t"
        out = normalize_sql_for_fingerprint(sql)
        self.assertNotIn("comment", out)
        self.assertIn(":literal", out)

    def test_replace_string_literal(self):
        sql = "SELECT * FROM t WHERE d = '2024-01-01'"
        out = normalize_sql_for_fingerprint(sql)
        self.assertIn(":literal", out)
        self.assertNotIn("2024-01-01", out)

    def test_replace_numeric_literal(self):
        sql = "SELECT SUM(amount) FROM t WHERE n = 42"
        out = normalize_sql_for_fingerprint(sql)
        self.assertIn(":literal", out)
        self.assertNotIn("42", out)

    def test_replace_null_true_false(self):
        sql = "SELECT * FROM t WHERE a IS NULL AND b = TRUE"
        out = normalize_sql_for_fingerprint(sql)
        self.assertIn(":literal", out)

    def test_same_shape_same_normalized(self):
        a = "SELECT * FROM t WHERE d = '2024-01-01'"
        b = "SELECT * FROM t WHERE d = '2024-06-15'"
        na = normalize_sql_for_fingerprint(a)
        nb = normalize_sql_for_fingerprint(b)
        self.assertEqual(na, nb)


class TestSqlFingerprint(unittest.TestCase):
    """Fingerprint is deterministic and matches by shape."""

    def test_deterministic(self):
        sql = "SELECT * FROM t WHERE x = 1"
        self.assertEqual(sql_fingerprint(sql), sql_fingerprint(sql))

    def test_same_shape_same_fingerprint(self):
        a = "SELECT * FROM t WHERE d = '2024-01-01'"
        b = "SELECT * FROM t WHERE d = '2024-06-15'"
        self.assertEqual(sql_fingerprint(a), sql_fingerprint(b))

    def test_different_shape_different_fingerprint(self):
        a = "SELECT * FROM t WHERE d = '2024-01-01'"
        b = "SELECT * FROM t WHERE d = '2024-01-01' AND e = 1"
        self.assertNotEqual(sql_fingerprint(a), sql_fingerprint(b))

    def test_whitespace_collapsed(self):
        a = "SELECT   *   FROM   t"
        b = "SELECT * FROM t"
        self.assertEqual(sql_fingerprint(a), sql_fingerprint(b))


class TestUsageAggregation(unittest.TestCase):
    """Match query log rows to fingerprints and aggregate usage."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.metadata_dir = os.path.join(self.tmp, "metadata")
        os.makedirs(self.metadata_dir, exist_ok=True)
        self.indexer = MetadataIndexer(self.metadata_dir)

    def tearDown(self):
        import shutil
        if os.path.isdir(self.tmp):
            shutil.rmtree(self.tmp, ignore_errors=True)

    def test_register_and_lookup_fingerprint(self):
        fp = sql_fingerprint("SELECT 1 FROM t")
        self.indexer.record_fingerprint(
            fingerprint=fp,
            metric_name="m1",
            metric_version="1.0",
            deprecated=False,
            first_seen_utc="2026-02-03T12:00:00Z",
        )
        info = self.indexer.get_fingerprint(fp)
        self.assertIsNotNone(info)
        self.assertEqual(info["metric_name"], "m1")
        self.assertEqual(info["metric_version"], "1.0")
        self.assertFalse(info["deprecated"])

    def test_match_and_aggregate_increments_usage(self):
        sql = "SELECT * FROM t WHERE d = '2024-01-01'"
        fp = sql_fingerprint(sql)
        self.indexer.record_fingerprint(
            fingerprint=fp,
            metric_name="m1",
            metric_version="1.0",
            deprecated=False,
        )
        rows = [
            QueryLogRow(query_text=sql, executed_at_utc="2026-02-03T10:00:00Z"),
            QueryLogRow(query_text=sql, executed_at_utc="2026-02-03T11:00:00Z"),
        ]
        matched = match_and_aggregate_usage(self.indexer, rows)
        self.assertEqual(matched, 2)
        usage = self.indexer.list_usage(metric_name="m1")
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0]["usage_count"], 2)
        self.assertEqual(usage[0]["deprecated_access_count"], 0)

    def test_deprecated_access_counted(self):
        sql = "SELECT * FROM t"
        fp = sql_fingerprint(sql)
        self.indexer.record_fingerprint(
            fingerprint=fp,
            metric_name="m_dep",
            metric_version="1.0",
            deprecated=True,
        )
        rows = [QueryLogRow(query_text=sql, executed_at_utc="2026-02-03T10:00:00Z")]
        matched = match_and_aggregate_usage(self.indexer, rows)
        self.assertEqual(matched, 1)
        usage = self.indexer.list_usage(metric_name="m_dep")
        self.assertEqual(usage[0]["deprecated_access_count"], 1)

    def test_unknown_fingerprint_not_matched(self):
        self.indexer.record_fingerprint(
            fingerprint=sql_fingerprint("SELECT 1 FROM a"),
            metric_name="m1",
            metric_version="1.0",
            deprecated=False,
        )
        rows = [QueryLogRow(query_text="SELECT 1 FROM b", executed_at_utc="2026-02-03T10:00:00Z")]
        matched = match_and_aggregate_usage(self.indexer, rows)
        self.assertEqual(matched, 0)
        usage = self.indexer.list_usage()
        self.assertEqual(len(usage), 0)


class TestSnowflakeLogAdapter(unittest.TestCase):
    """Snowflake query history row -> QueryLogRow."""

    def test_row_from_snowflake_log(self):
        raw = {"QUERY_TEXT": "SELECT 1", "START_TIME": "2026-02-03T10:00:00Z"}
        row = row_from_snowflake_log(raw)
        self.assertEqual(row.query_text, "SELECT 1")
        self.assertEqual(row.executed_at_utc, "2026-02-03T10:00:00Z")

    def test_rows_from_snowflake_logs(self):
        raw = [
            {"QUERY_TEXT": "SELECT 1", "START_TIME": "2026-02-03T10:00:00Z"},
            {"query_text": "SELECT 2", "start_time": "2026-02-04T11:00:00"},
        ]
        rows = rows_from_snowflake_logs(raw)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].query_text, "SELECT 1")
        self.assertEqual(rows[1].query_text, "SELECT 2")
