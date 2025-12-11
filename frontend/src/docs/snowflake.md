# Snowflake Integration

AXI can sync Snowflake metadata and generate Snowflake-optimized SQL.

## Commands

- Full sync into the metadata store: `axi snowflake sync`
- List objects from the local index:
  - Tables: `axi snowflake tables`
  - Columns for a table: `axi snowflake columns <table>`
  - Policies: `axi snowflake policies`
  - Lineage: `axi snowflake lineage <table>`
- Generate Snowflake SQL: `axi snowflake explain --metric <metric> --dimensions <dims>`

## Configuration

- Configure Snowflake credentials in your environment (see `axi.config.settings` for env var names).
- Extraction output is stored under `AXI_METADATA_DIR` (defaults to `metadata_store/`).

## Notes

- Generated SQL uses the optimizer with Snowflake hints when `dialect="snowflake"`.
- Metadata sync populates local SQLite tables so the UI can browse tables/columns and lineage without hitting Snowflake on every request.
