# Query usage tracking (read-only, no PII)

Identify warehouse queries that originated from AXI metrics and aggregate usage in the AXI index.

## Inputs

- **Warehouse query logs** (Snowflake first): e.g. `QUERY_HISTORY` with `QUERY_TEXT` and `START_TIME` (read-only; no PII).
- **AXI-generated SQL fingerprints**: registered when compiling metrics or building a catalog.

## Flow

1. **Fingerprint** AXI SQL via `sql_fingerprint(sql)` (normalizes comments, whitespace, literals → deterministic hash).
2. **Register** fingerprints with the indexer: `register_fingerprint(indexer, fp, metric_name, metric_version, deprecated)` or compile with `register_fingerprint=True` and an indexer.
3. **Ingest** query log rows (e.g. from Snowflake): convert to `QueryLogRow(query_text=..., executed_at_utc=...)` via `rows_from_snowflake_logs(raw_rows)`.
4. **Match and aggregate**: `match_and_aggregate_usage(indexer, query_log_rows)` updates `metric_usage` (usage count, deprecated access count per metric/version/date).

## Tables (AXI index)

- **axi_sql_fingerprints**: `fingerprint` → `metric_name`, `metric_version`, `deprecated`, `first_seen_utc`.
- **metric_usage**: `(metric_name, metric_version, usage_date)` → `usage_count`, `deprecated_access_count`.

## Constraints

- Read-only access to warehouse logs.
- No PII stored.
- No query interception; matching is done by fingerprinting log text.
