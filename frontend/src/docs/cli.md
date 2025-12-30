# CLI Reference

The `axi` command-line tool provides full access to AXI's semantic layer capabilities.

<br>

---

## Installation

```bash
pip install axi-cli
```

<br>

---

## Quick Reference

<br>

| Command | Description |
|---------|-------------|
| `axi extract` | Extract metadata from SQL models |
| `axi metrics list` | List all metrics |
| `axi query` | Generate and run semantic queries |
| `axi ui` | Start the web interface |

<br>

---

## Commands

<br>

### Project Setup

```bash
# Initialize a new AXI project
axi scaffold

# This creates:
# - axi.yml (configuration)
# - metadata_store/ (extracted metadata)
# - glossary/ (business terms)
# - overrides/ (customizations)
```

<br>

### Extraction

```bash
# Extract from current directory
axi extract

# Extract from specific path
axi extract /path/to/project

# Debug mode - see what's being scanned
axi extract --debug

# List discovered models without extracting
axi extract --debug-models
```

<br>

### dbt Integration

```bash
# Compile and extract dbt project
axi dbt scan

# Load manifest directly
axi dbt manifest target/manifest.json

# Describe a model
axi dbt describe orders
```

<br>

### Metrics

```bash
# List all metrics
axi metrics list

# Describe a specific metric
axi metrics describe revenue

# Generate SQL for a metric
axi metrics sql revenue --dims region,date

# With time intelligence
axi metrics sql revenue --compare previous_period

# View metric dependencies
axi metrics deps revenue
```

<br>

### Querying

```bash
# Generate semantic SQL
axi query --metric revenue --dims region,date

# Add filters
axi query --metric revenue --dims region --filters "region=US"

# Execute against Snowflake
axi query --metric revenue --dims region --run

# Set result limit
axi query --metric revenue --dims region --limit 100
```

<br>

### Snowflake

```bash
# Sync metadata from Snowflake
axi snowflake sync

# Sync specific schemas
axi snowflake sync --schemas MARTS,ANALYTICS

# List tables
axi snowflake tables

# View columns
axi snowflake columns my_table

# Check constraints
axi snowflake constraints

# View lineage
axi snowflake lineage my_table
```

<br>

### Glossary

```bash
# Generate glossary from extracted metadata
axi glossary generate

# Search for terms
axi glossary search "revenue"
```

<br>

### Cache

```bash
# Show cache status
axi cache show

# Clear all cache
axi cache clear

# Clear specific metric
axi cache clear --metric revenue
```

<br>

### UI

```bash
# Start backend and frontend
axi ui

# Backend only (API server)
axi ui --no-frontend

# Custom ports
axi ui --port 9000 --frontend-port 3001
```

<br>

---

## Environment Variables

<br>

| Variable | Default | Description |
|----------|---------|-------------|
| `AXI_DEBUG` | `false` | Enable debug logging |
| `AXI_METADATA_DIR` | `./metadata_store` | Metadata storage location |
| `AXI_LOG_LEVEL` | `INFO` | Log level |

<br>

---

## Configuration File

AXI uses `axi.yml` for project settings:

```yaml
project: my_project

dbt:
  compiled_path: target/compiled/my_project/models

promotion:
  include:
    folders: ["models/marts/**"]
    tags: ["axi"]
  exclude:
    folders: ["models/staging/**"]

snowflake:
  account: xy12345.us-east-1
  warehouse: compute_wh
  database: analytics
```

<br>

---

## Getting Help

```bash
# General help
axi --help

# Command-specific help
axi extract --help
axi query --help
```
