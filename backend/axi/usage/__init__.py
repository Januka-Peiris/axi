# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Query usage tracking: fingerprinting and aggregation (read-only, no PII)."""

from axi.usage.fingerprint import normalize_sql_for_fingerprint, sql_fingerprint
from axi.usage.aggregator import (
    register_fingerprint,
    match_and_aggregate_usage,
    QueryLogRow,
)
from axi.usage.snowflake_logs import row_from_snowflake_log, rows_from_snowflake_logs

__all__ = [
    "normalize_sql_for_fingerprint",
    "sql_fingerprint",
    "register_fingerprint",
    "match_and_aggregate_usage",
    "QueryLogRow",
    "row_from_snowflake_log",
    "rows_from_snowflake_logs",
]
