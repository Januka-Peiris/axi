# AXI SQL Contract for BI Tools

Machine-readable contract: `contract_schema.json`.

## Goal

Ensure AXI-generated SQL works as:

- **Custom SQL** – ad-hoc query in a BI tool
- **Derived table** – subquery in `FROM ( ... )`
- **View definition** – `CREATE VIEW v AS ( ... )`

## Allowed SQL Patterns

- Single `SELECT` with optional `WHERE`, `GROUP BY`
- `FROM <table> [AS alias]` with optional `JOIN`s
- Aggregate expressions: `SUM`, `COUNT`, `AVG`, `MIN`, `MAX`
- Column references and aliases
- AXI metadata as **SQL comments only** (no executable impact)

## Disallowed Patterns (Validation)

| Rule | Description |
|------|-------------|
| **no_session_state** | No `USE`, `SET`, `ALTER SESSION`, session variables, or session-scoped options |
| **no_temp_tables** | No `CREATE TEMP TABLE`, `CREATE TEMP VIEW`, `#tables`, table variables |
| **no_stored_procedures** | No `CALL`, `EXEC`, `EXECUTE` (procedure/function execution) |
| **no_procedure_udf_definitions** | No `CREATE PROCEDURE`, `CREATE FUNCTION`, or `CREATE OR REPLACE` for procedures/UDFs |
| **no_nondeterministic_functions** | No non-deterministic functions (e.g. `RAND`, `NEWID`, `UUID`, `SYS_GUID`) except those on the schema whitelist |
| **no_select_star** | No `SELECT *` in metric output; columns must be listed explicitly |
| **no_transaction_control** | No `COMMIT`, `ROLLBACK`, `BEGIN TRANSACTION` |
| **no_ddl** | No `CREATE TABLE`, `ALTER`, `DROP` in the query body |

## Parameter Placeholders

BI tools can bind parameters for filters.

### Time filters

| Parameter   | Placeholder      |
|------------|------------------|
| Start date | `:axi_start_date` |
| End date   | `:axi_end_date`  |

### Dimension filters

Format: `:axi_filter_<dimension_name>` (e.g. `:axi_filter_region`).

Names are sanitized (e.g. dots → underscores).

## Validation During Compilation

SQL is validated against `contract_schema.json` on every compile. There is no bypass or silent downgrade.

- **compile_metric**: Always validates generated SQL before returning. On violation, `ContractViolationError` is raised (structured exception with rule id, message, snippet).
- **Governed view SQL**: `generate_create_view_sql` uses `compile_metric` for the view body, so the body is contract-validated before being embedded in `CREATE VIEW`.
