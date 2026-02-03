# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Snowflake QUERY_HISTORY ingestion for usage tracking.

Read-only: fetches query log rows, matches to AXI fingerprints, updates metric_usage.
No PII; no query interception. Call from CLI or scheduler.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from axi.usage.aggregator import match_and_aggregate_usage
from axi.usage.snowflake_logs import rows_from_snowflake_logs

if TYPE_CHECKING:
    from axi.metadata.indexer import MetadataIndexer
    from axi.execution.snowflake_runner import SnowflakeRunner


def _query_history_sql(days: int, limit: int) -> str:
    """Build read-only QUERY_HISTORY query (INFORMATION_SCHEMA: last 7 days max)."""
    return f"""
SELECT QUERY_TEXT, START_TIME
FROM TABLE(
  INFORMATION_SCHEMA.QUERY_HISTORY(
    END_TIME_RANGE_START => DATEADD('day', -{days}, CURRENT_TIMESTAMP()),
    END_TIME_RANGE_END => CURRENT_TIMESTAMP(),
    RESULT_LIMIT => {limit}
  )
)
WHERE QUERY_TEXT IS NOT NULL AND TRIM(QUERY_TEXT) != ''
ORDER BY START_TIME DESC
"""


def fetch_snowflake_query_history(
    runner: "SnowflakeRunner",
    days_back: int = 7,
    result_limit: int = 10_000,
) -> List[Dict[str, Any]]:
    """
    Fetch QUERY_TEXT and START_TIME from Snowflake QUERY_HISTORY (read-only).

    - days_back: last N days (max 7 for INFORMATION_SCHEMA).
    - result_limit: max rows to return.

    Returns list of dicts with QUERY_TEXT and START_TIME (no PII beyond query text for fingerprinting).
    """
    days = min(max(1, days_back), 7)
    sql = _query_history_sql(days, result_limit)
    rows, columns, _ = runner.execute_query(sql)
    if not rows or not columns:
        return []
    # execute_query returns list of dicts keyed by column name
    out: List[Dict[str, Any]] = []
    for row in rows:
        q = row.get("QUERY_TEXT") or row.get("query_text") or ""
        s = row.get("START_TIME") or row.get("start_time")
        out.append({"QUERY_TEXT": q, "START_TIME": s})
    return out


def ingest_snowflake_usage(
    indexer: "MetadataIndexer",
    runner: "SnowflakeRunner",
    days_back: int = 7,
    result_limit: int = 10_000,
) -> int:
    """
    Fetch Snowflake QUERY_HISTORY, match to AXI fingerprints, update metric_usage.

    Read-only warehouse access. Returns number of query log rows matched to an AXI metric.
    """
    raw_rows = fetch_snowflake_query_history(runner, days_back=days_back, result_limit=result_limit)
    query_log_rows = rows_from_snowflake_logs(raw_rows)
    return match_and_aggregate_usage(indexer, query_log_rows)
