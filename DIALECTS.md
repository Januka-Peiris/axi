# AXI SQL Dialect Support

AXI uses [sqlglot](https://github.com/tobymao/sqlglot) for SQL parsing.
This document defines exactly what AXI supports and refuses.

## Supported Dialects

| Dialect    | Status      | Notes                                              |
|------------|-------------|----------------------------------------------------|
| Snowflake  | ✅ Primary   | Full support: QUALIFY, FLATTEN, TRY_*, IFF         |
| PostgreSQL | ✅ Supported | Standard PostgreSQL 14+ syntax                     |
| Generic    | ✅ Supported | ANSI SQL-92 compatible SELECT statements           |

## Parsing Behavior

AXI attempts dialects in this fixed order:
1. Snowflake
2. PostgreSQL
3. Generic (None)
4. MySQL (fallback)
5. SQLite (fallback)

**Important:**
- AXI does NOT guess which dialect you intended
- If parsing fails with ALL dialects, AXI raises an exception
- The first successfully parsed result is used
- There is no `--dialect` flag to force a specific dialect

## Explicitly Unsupported

| Feature               | Status     | Reason                                    |
|-----------------------|------------|-------------------------------------------|
| Oracle PL/SQL         | ❌ Refused  | Not in sqlglot core                       |
| T-SQL (SQL Server)    | ❌ Refused  | Limited sqlglot support                   |
| Teradata              | ❌ Refused  | Not in sqlglot core                       |
| Procedural blocks     | ❌ Refused  | Not semantic SQL (BEGIN/END, DECLARE)     |
| DDL statements        | ⚠️ Ignored  | CREATE/ALTER/DROP not extracted           |
| DML statements        | ⚠️ Ignored  | INSERT/UPDATE/DELETE not extracted        |
| MERGE statements      | ⚠️ Ignored  | Not treated as semantic models            |

## What AXI Extracts

AXI ONLY processes SELECT statements. It extracts:

- **Metrics**: Aggregation expressions (SUM, COUNT, AVG, MIN, MAX, etc.)
- **Dimensions**: Columns in GROUP BY clause
- **Relationships**: FROM and JOIN clauses (table references)
- **Grain**: Inferred from GROUP BY or explicit `-- grain:` comment

## What AXI Ignores

These are parsed but not extracted as semantic elements:

- Comments (preserved but not analyzed for semantics)
- CTEs (traversed for relationships, not separately indexed)
- Subqueries in WHERE (not treated as relationships)
- Window functions (not treated as metrics)
- CASE expressions (not treated as separate dimensions)

## Dialect-Specific Handling

### Snowflake
- `QUALIFY` clauses parsed correctly
- `FLATTEN` table functions recognized as source tables
- `TRY_*` functions preserved in output SQL
- `IFF` recognized as conditional expression
- `::` cast syntax supported
- Semi-structured data access (`column:path`) supported

### PostgreSQL
- Array syntax `[]` supported
- `::` cast operator preserved
- `DISTINCT ON` parsed correctly
- `LATERAL` joins supported

### MySQL (Fallback Only)
- Backtick identifiers supported
- `LIMIT` without `OFFSET` supported

## When Parsing Fails

If SQL cannot be parsed by any dialect:

1. AXI raises an exception with the model name
2. The error message includes "Failed to parse"
3. The model is counted as "failed" in extraction summary
4. Other models continue processing
5. CLI returns exit code 5 (EXTRACTION_ERROR)

**AXI will never:**
- Silently skip unparseable SQL
- Infer meaning from malformed queries
- Attempt to "fix" broken syntax
- Guess which dialect was intended

## Debugging Parse Failures

Set `AXI_DEBUG=true` to:
- See which dialects were attempted
- Get the specific parse error for each dialect
- Have failing SQL dumped to `axi_debug_sql/<model>.sql`

```bash
AXI_DEBUG=true axi extract /path/to/project
```

## Feature Requests

If you need support for a dialect not listed here, please:
1. Check if sqlglot supports it: https://github.com/tobymao/sqlglot
2. Open an issue with a sample SQL file
3. Do NOT expect AXI to guess or infer dialect from file extensions
