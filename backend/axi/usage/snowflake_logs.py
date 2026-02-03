# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Snowflake query log shape for usage tracking.

Maps Snowflake QUERY_HISTORY (or equivalent) rows to QueryLogRow for
match_and_aggregate_usage. Read-only; no execution; no PII.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from axi.usage.aggregator import QueryLogRow


# Snowflake QUERY_HISTORY columns used for usage (no PII)
QUERY_TEXT_COLUMN = "QUERY_TEXT"
START_TIME_COLUMN = "START_TIME"


def row_from_snowflake_log(raw: Dict[str, Any]) -> QueryLogRow:
    """
    Build a QueryLogRow from one Snowflake query history row.

    Expects QUERY_TEXT and START_TIME (or equivalent). Other columns
    are ignored. START_TIME should be ISO or parseable to date.
    """
    query_text = raw.get(QUERY_TEXT_COLUMN) or raw.get("query_text") or ""
    start = raw.get(START_TIME_COLUMN) or raw.get("start_time")
    executed_at: Optional[str] = None
    if start is not None:
        executed_at = str(start) if not isinstance(start, str) else start
    return QueryLogRow(query_text=query_text, executed_at_utc=executed_at)


def rows_from_snowflake_logs(raw_rows: List[Dict[str, Any]]) -> List[QueryLogRow]:
    """Convert a list of Snowflake query history rows to QueryLogRow list."""
    return [row_from_snowflake_log(r) for r in raw_rows]
