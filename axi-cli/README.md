# AXI CLI

Command-line interface for the AXI semantic layer.

## Installation

```bash
# Install in editable mode
pip install -e .

# Or via the project Makefile
make install
```

## Quick Start

```bash
# Extract metadata from dbt project
axi extract

# List all metrics
axi metrics list

# Generate a semantic query
axi query --metric revenue --dims region,date

# Start the UI
axi ui
```

## Commands

### Extraction

```bash
# Extract from current directory (auto-detects dbt)
axi extract

# Extract from specific path
axi extract /path/to/dbt/project

# Debug mode - see what's being scanned
axi extract --debug
```

### Metrics

```bash
# List all metrics
axi metrics list

# Describe a specific metric
axi metrics describe revenue

# Generate SQL for a metric
axi metrics sql revenue --dims region,date
```

### Queries

```bash
# Generate semantic SQL
axi query --metric revenue --dims region

# Execute against Snowflake
axi query --metric revenue --dims region --run

# With filters
axi query --metric revenue --dims region --filters "region=US"
```

### dbt Integration

```bash
# Scan dbt project (compile + extract)
axi dbt scan

# Load manifest only
axi dbt manifest target/manifest.json

# Describe a model
axi dbt describe orders
```

### Snowflake Direct

```bash
# Sync metadata from Snowflake
axi snowflake sync

# Sync specific schemas
axi snowflake sync --schemas MARTS,ANALYTICS

# List tables
axi snowflake tables
```

### UI

```bash
# Start backend API + frontend
axi ui

# Backend only
axi ui --no-frontend

# Custom ports
axi ui --port 9000 --frontend-port 3001
```

### Glossary

```bash
# Generate glossary
axi glossary generate

# Search terms
axi glossary search "revenue"
```

### Cache

```bash
# Show cache status
axi cache show

# Clear cache
axi cache clear

# Clear specific metric
axi cache clear --metric revenue
```

## Configuration

The CLI uses `axi.yml` for project configuration. See the main documentation for details.

```yaml
project: my_project

dbt:
  compiled_path: target/compiled/my_project/models

promotion:
  include:
    folders: ["models/marts/**"]
```

## Environment Variables

```bash
AXI_DEBUG=true          # Enable debug logging
AXI_METADATA_DIR=./     # Metadata storage location
AXI_LOG_LEVEL=INFO      # Log level
```

## License

MIT. See LICENSE.
