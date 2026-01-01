# AXI

A semantic compiler for analytics.

AXI extracts semantic metadata (metrics, dimensions, entities, relationships, grain) from SQL models. It is SQL-first, dbt-first, and requires no DSL. Warehouses are optional.

## What AXI Is

AXI is a **semantic compiler**, not a BI tool. It:

- Parses SELECT statements from dbt compiled SQL or raw `.sql` files
- Extracts metrics (aggregations), dimensions (GROUP BY columns), entities, and relationships (JOINs)
- Generates join-aware SQL for downstream consumption
- Produces deterministic, versioned metadata artifacts

**Primary input**: Compiled SQL from dbt projects (or raw SQL files)
**Primary output**: JSON metadata files with schema versioning

## What AXI Is NOT

- **Not a BI tool** — AXI does not visualize data. Use Looker, Tableau, or Metabase for dashboards.
- **Not an AI analyst** — AXI does not interpret business intent or generate insights.
- **Not an inference engine** — AXI does not guess semantics. Ambiguous structures are flagged, not resolved.
- **Not a warehouse scanner** — AXI reads SQL files, not database catalogs. Warehouse connections are optional enrichment only.
- **Not a metric store** — AXI extracts metadata; it does not execute queries or cache results.

## Core Guarantees

### Determinism

Same inputs produce byte-identical outputs. AXI guarantees:
- Sorted iteration of files and data structures
- No random IDs or timestamps in semantic artifacts
- Reproducible metadata across runs and environments

### No Silent Inference

AXI does not guess semantics. When relationships or grain cannot be explicitly determined from SQL:
- The condition is flagged (e.g., `grain_status: "not_detected"`)
- The model may be skipped with an explicit reason
- No default values are silently applied

### CI-Safe Exit Codes

AXI uses strict exit codes for CI/CD integration:

| Code | Name | Meaning |
|------|------|---------|
| 0 | SUCCESS | All items processed without error |
| 1 | GENERAL_ERROR | Unexpected runtime failure |
| 2 | CONFIG_ERROR | Invalid configuration |
| 3 | VALIDATION_ERROR | Invalid input (bad SQL syntax) |
| 4 | NOT_FOUND | Required resource not found |
| 5 | EXTRACTION_ERROR | One or more items failed |
| 6 | CONNECTION_ERROR | Database/warehouse connection failed |

**Important**: Exit code 5 includes partial success scenarios. If 95 of 100 models succeed and 5 fail, AXI returns exit code 5. CI/CD should treat this as failure—the metadata may be incomplete.

### Explicit Failure Reporting

Every extraction run produces a summary with explicit counts:
- `scanned`: Total models found
- `processed`: Successfully extracted
- `skipped`: Excluded by rules or lacking semantic content
- `failed`: Parse errors or extraction failures

Use `--summary <file>` to write machine-readable JSON for CI/CD integration.

## Inferred Semantics

AXI performs limited inference in specific cases. All inferred semantics are:

1. **Explicitly marked** — Inferred relationships have `join_type: "INFERRED_FK"`. Inferred grain has `source: "entity_pk"` or `source: "model_dimensions"`.
2. **Non-default** — Inferred semantics are not used in query generation unless explicitly requested.
3. **Opt-in to use** — Query operations that would rely on inferred relationships require explicit acknowledgment.

Inference occurs only for:
- FK relationships from `_id` column naming conventions (marked `INFERRED_FK`)
- Grain from entity primary keys when not explicitly defined (marked `inferred: true`)

**AXI will never**:
- Infer metric definitions
- Guess business meaning from column names
- Auto-generate joins without explicit SQL evidence
- Silently act on inferred relationships

## Typical Workflow

```
dbt project
    │
    ▼
dbt compile
    │
    ▼
target/compiled/*.sql
    │
    ▼
axi extract
    │
    ▼
metadata_store/models/*.json
```

No warehouse connection is required for extraction. The workflow is:

1. Write dbt models with SQL aggregations and JOINs
2. Run `dbt compile` to generate compiled SQL
3. Run `axi extract` to parse SQL and produce metadata
4. Optionally run `axi ui` to explore the semantic graph

## Quick Start

```bash
# Install
pip install axi-cli

# Extract from a dbt project (after dbt compile)
cd /path/to/dbt/project
axi extract

# Or extract from raw SQL
axi extract /path/to/sql/files

# View results
axi metrics list
axi ui
```

## CLI Reference

```bash
# Extraction
axi extract [path]              # Extract metadata from SQL
axi extract --dry-run           # Validate without writing
axi extract --debug             # Verbose logging
axi extract --summary out.json  # Write machine-readable summary
axi extract --quiet             # Suppress non-error output

# Inspection
axi metrics list                # List extracted metrics
axi query --metric <name>       # Generate SQL for a metric

# UI
axi ui                          # Start Semantic Explorer
```

## SQL Dialect Support

AXI uses sqlglot for SQL parsing. See [DIALECTS.md](DIALECTS.md) for:
- Supported dialects (Snowflake, PostgreSQL, generic SQL)
- Explicitly unsupported features
- Parse failure behavior

## Configuration

Create `axi.yml` in your project root:

```yaml
# Promotion rules (which models to extract)
include:
  folders: ["models/marts/**"]
  tags: ["axi"]

exclude:
  folders: ["models/staging/**"]
  tags: []

# dbt integration
dbt:
  compiled_path: "./target/compiled"
```

See [backend/axi/config/README.md](backend/axi/config/README.md) for full configuration reference.

## Project Structure

```
backend/    # Semantic engine (BSL 1.1)
axi-cli/    # CLI tool (MIT)
frontend/   # Semantic Explorer UI (MIT)
examples/   # Demo project
```

## Development

```bash
# Install all packages
make install

# Run backend + frontend
make dev

# Run tests
make test
```

## Licensing

- **Backend** (`axi-semantic`): Business Source License 1.1. Free for use; prohibits offering AXI as a competing hosted service. Converts to MIT on 2027-01-01.
- **CLI, UI, examples**: MIT.
