# Snowflake Integration

AXI integrates directly with Snowflake to sync metadata and execute optimized queries.

<br>

---

## Features

<br>

- **Metadata Sync** - Import tables, columns, and constraints from Snowflake
<br>

- **View Parsing** - Extract metrics and dimensions from VIEW definitions
<br>

- **Relationship Detection** - Infer foreign keys from naming conventions
<br>

- **Optimized SQL** - Generate Snowflake-specific SQL with hints
<br>

- **Policy Awareness** - Track masking and row access policies

<br>

---

## Quick Start

<br>

### 1. Configure Credentials

Set environment variables:

```bash
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export SNOWFLAKE_USER=your_user
export SNOWFLAKE_PASSWORD=your_password
export SNOWFLAKE_WAREHOUSE=compute_wh
export SNOWFLAKE_DATABASE=analytics
export SNOWFLAKE_SCHEMA=marts
```

Or use key-pair authentication:

```bash
export SNOWFLAKE_PRIVATE_KEY_PATH=~/.ssh/snowflake_key.pem
```

<br>

### 2. Sync Metadata

```bash
# Full sync
axi snowflake sync

# Sync specific schemas
axi snowflake sync --schemas MARTS,ANALYTICS

# Filter views for semantic extraction
axi snowflake sync --views "mart_%,fact_%"
```

<br>

### 3. Explore Data

```bash
# List synced tables
axi snowflake tables

# View columns
axi snowflake columns my_table

# Check constraints
axi snowflake constraints

# View lineage
axi snowflake lineage my_table
```

<br>

---

## CLI Commands

<br>

| Command | Description |
|---------|-------------|
| `axi snowflake sync` | Sync metadata from Snowflake |
| `axi snowflake tables` | List synced tables and views |
| `axi snowflake columns <table>` | Show columns for a table |
| `axi snowflake constraints` | List PK/FK constraints |
| `axi snowflake policies` | Show masking and access policies |
| `axi snowflake lineage [table]` | View table lineage |

<br>

---

## Sync Options

<br>

| Option | Description |
|--------|-------------|
| `--schemas` | Comma-separated list of schemas |
| `--views` | View name patterns (SQL LIKE syntax) |
| `--skip-constraints` | Skip PK/FK detection (faster) |
| `--skip-inferred` | Skip relationship inference |
| `--skip-semantic` | Skip VIEW parsing for metrics |

<br>

---

## Generated SQL

When executing queries, AXI generates Snowflake-optimized SQL:

<br>

- Uses `TRY_DIVIDE` for safe division
<br>

- Uses `IFF` instead of `CASE` where appropriate
<br>

- Applies `QUALIFY` for window functions
<br>

- Adds warehouse hints when configured

<br>

---

## Configuration

In `axi.yml`:

```yaml
snowflake:
  account: xy12345.us-east-1
  warehouse: compute_wh
  database: analytics
  schema: marts

snowflake_promotion:
  schemas:
    - MARTS
    - ANALYTICS
  view_patterns:
    - "mart_%"
    - "fact_%"
```

<br>

---

## Troubleshooting

<br>

### Permission Issues

Ensure your user has:

<br>

- `SELECT` on `INFORMATION_SCHEMA`
<br>

- `USAGE` on target schemas
<br>

- `SELECT` on views to extract

<br>

### Views Not Detected

<br>

- Schema names must be UPPERCASE
<br>

- View patterns use SQL LIKE syntax (`mart_%` not `mart_*`)
<br>

- Views without aggregations are skipped (staging tables)
