# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Usage aggregation from warehouse query logs.

Matches query log rows to AXI SQL fingerprints and updates metric_usage.
Read-only access to logs; no PII; no query interception.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from axi.usage.fingerprint import sql_fingerprint

if TYPE_CHECKING:
    from axi.metadata.indexer import MetadataIndexer


@dataclass
class QueryLogRow:
    """
    Single row from a warehouse query log (e.g. Snowflake QUERY_HISTORY).

    Only fields needed for matching and date bucketing; no PII.
    """

    query_text: str
    """Raw SQL text (used for fingerprinting only; not stored)."""

    executed_at_utc: Optional[str] = None
    """
    Execution time in UTC (ISO datetime or date string).
    Used to bucket usage by date (YYYY-MM-DD). If missing, today UTC is used.
    """


def _usage_date_from_row(row: QueryLogRow) -> str:
    """Return YYYY-MM-DD for usage bucketing."""
    if row.executed_at_utc:
        try:
            # Accept ISO datetime or date-only
            s = row.executed_at_utc.strip()
            if "T" in s:
                s = s.split("T")[0]
            elif " " in s:
                s = s.split(" ")[0]
            if len(s) >= 10 and s[4] == "-" and s[7] == "-":
                return s[:10]
        except Exception:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def register_fingerprint(
    indexer: "MetadataIndexer",
    fingerprint: str,
    metric_name: str,
    metric_version: str,
    deprecated: bool = False,
    first_seen_utc: Optional[str] = None,
) -> None:
    """
    Register an AXI SQL fingerprint for a metric.

    Call this when compiling a metric (or when building a fingerprint catalog)
    so that warehouse query logs can be matched to this metric.
    """
    indexer.record_fingerprint(
        fingerprint=fingerprint,
        metric_name=metric_name,
        metric_version=metric_version,
        deprecated=deprecated,
        first_seen_utc=first_seen_utc,
    )


def match_and_aggregate_usage(
    indexer: "MetadataIndexer",
    query_log_rows: List[QueryLogRow],
) -> int:
    """
    Match query log rows to AXI fingerprints and update metric_usage.

    - Fingerprints each row's query_text.
    - Looks up fingerprint in axi_sql_fingerprints.
    - For each match, increments usage for (metric_name, metric_version, usage_date)
      and optionally deprecated_access_count.

    Returns the number of rows that matched an AXI metric.
    """
    matched = 0
    for row in query_log_rows:
        if not row.query_text or not row.query_text.strip():
            continue
        fp = sql_fingerprint(row.query_text)
        info = indexer.get_fingerprint(fp)
        if not info:
            continue
        usage_date = _usage_date_from_row(row)
        indexer.increment_usage(
            metric_name=info["metric_name"],
            metric_version=info["metric_version"],
            usage_date=usage_date,
            deprecated_access=info.get("deprecated", False),
        )
        matched += 1
    return matched
