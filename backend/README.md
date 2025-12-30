# AXI Semantic Backend

Core semantic engine for AXI - extracts, stores, and serves semantic metadata from SQL.

## Features

- **Semantic Extraction**: Parse SQL to extract metrics, dimensions, entities, and relationships
- **Query Engine**: Generate optimized, join-aware SQL from semantic queries
- **Metadata Store**: SQLite or PostgreSQL storage for semantic state
- **REST API**: FastAPI server for all semantic operations
- **dbt Integration**: Load and enrich metadata from dbt manifests
- **Snowflake Integration**: Direct metadata extraction from Snowflake

## Installation

```bash
# Install in editable mode
pip install -e .

# Or via the project Makefile
make install
```

## Usage

### As a Library

```python
from axi.extractor.core import extract_metadata
from axi.query.engine import SemanticQueryEngine

# Extract metadata from SQL
sql = "SELECT region, SUM(amount) as revenue FROM orders GROUP BY region"
metadata = extract_metadata(sql, "revenue_by_region")

# Generate queries
engine = SemanticQueryEngine()
query = engine.generate_query(metric="revenue", dimensions=["region"])
```

### As an API Server

```bash
# Start the API server
axi-api

# Or via uvicorn
uvicorn axi.api.main:app --reload
```

API available at http://localhost:8000

## Configuration

### Storage Backends

**SQLite (default)**:
```bash
# No configuration needed - uses metadata_store/axi.db
```

**PostgreSQL**:
```bash
export AXI_DB_TYPE=postgres
export AXI_DB_HOST=localhost
export AXI_DB_PORT=5432
export AXI_DB_NAME=axi
export AXI_DB_USER=axi
export AXI_DB_PASSWORD=secret
```

### Migration

```bash
# Migrate from SQLite to PostgreSQL
axi migrate --from sqlite --to postgres
```

See `axi/config/README.md` for full configuration options.

## Project Structure

```
axi/
├── api/              # FastAPI routes and server
├── config/           # Configuration and settings
├── dbt/              # dbt manifest integration
├── execution/        # Query execution (Snowflake runner)
├── extractor/        # SQL parsing and metadata extraction
├── glossary/         # Business glossary
├── materialization/  # Metric materialization
├── metadata/         # Metadata storage and indexing
├── metrics/          # Metrics validation and store
├── query/            # Semantic query engine
├── snowflake/        # Snowflake direct integration
└── utils/            # Shared utilities
```

## License

Business Source License 1.1 (BSL). See LICENSE.

Free for commercial use, modification, and redistribution. Prohibits offering AXI as a competing hosted service. Converts to MIT on 2027-01-01.
