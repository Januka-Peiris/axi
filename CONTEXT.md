# AXI - AI Context File (v1.0)

> The semantic layer product in the msh ecosystem

## Product Name

**AXI** - A semantic layer built from SQL.

The name is inspired by "axiom" - a fundamental truth.

## Product Purpose

AXI extracts meaning from SQL models to create:
- A business-friendly semantic layer
- A metric glossary
- A dimension model
- A no-SQL metric query engine

All powered by existing SQL, without requiring YAML, LookML, Semantic DSLs, or proprietary modeling.

AXI works independently OR inside the msh ecosystem, but is not part of msh itself.

## High-Level Description

AXI:
- Reads SQL from dbt Core, Snowflake, msh, or raw `.sql` files
- Extracts metrics, dimensions, grains, filters, and source tables
- Stores them in metadata JSON + SQLite index
- Provides a FastAPI backend for semantic querying
- Generates SQL dynamically and executes it in Snowflake
- Supports a React UI for business-friendly exploration
- Only extracts models that are promoted

## Promotion Model

AXI only extracts metadata from **promoted** models/tables, using:

### 1. Tag-based Promotion

Works in dbt, Snowflake, and msh:

**dbt:**
```yaml
tags: ["axi"]
```

Or SQL comment:
```sql
-- axi: true
```

**Snowflake:**
```sql
ALTER TABLE analytics.mrr SET TAG axi = 'true';
```

**msh:**
```yaml
axi: true
```

### 2. Folder-based Promotion (dbt only)

Any model inside included folders is promoted:

```yaml
include:
  folders:
    - models/axi
    - models/business
```

### 3. Include/Exclude Rules

Main config file: `axi.yml`

```yaml
include:
  tags: ["axi"]
  folders: ["models/axi"]
exclude:
  folders: ["raw/", "staging/"]
  tags: ["ignore"]
```

**Promotion logic:**
```
PROMOTED IF:
  (dbt/msh/Snowflake tag == axi)
  OR folder matches include rule
EXCEPT WHEN:
  file or folder matches exclusion rule
```

This ensures clean, intentional semantic modeling.

## Architecture Overview

### Repo Structure

```
axi/
├── backend/
│   └── axi/
│       ├── config/
│       ├── extractor/
│       ├── metadata/
│       └── api/
├── frontend/
│   └── src/
└── axi-cli/
```

## Backend Components

### 1. Config Loader

Loads `axi.yml` and exposes:
- `include.tags`
- `include.folders`
- `exclude.tags`
- `exclude.folders`

### 2. Promotion Engine

Determines whether a model should be extracted:
- Checks tags
- Checks folder inclusion
- Checks exclude rules

### 3. SQL Scanner

Scans directories and finds `.sql` models. Supports dbt compiled folder, msh assets, and Snowflake extraction.

### 4. Metadata Extractor

Uses sqlglot to parse SQL and extract:
- **Metrics**: SUM, COUNT, AVG
- **Dimensions**: GROUP BY columns
- **Filters**: WHERE clauses
- **Grain**: DATE_TRUNC patterns
- **Source tables**: FROM/JOIN references

**Output example:**
```json
{
  "model": "mrr",
  "metrics": [
    {
      "name": "mrr",
      "expression": "SUM(amount)",
      "grain": "month"
    }
  ],
  "dimensions": ["customer_id", "month"],
  "filters": ["status = 'active'"],
  "source_tables": ["subscription_charges"]
}
```

### 5. Metadata Storage

Two layers:

**A) JSON files** stored under:
```
metadata_store/models/<model_name>.json
```

**B) SQLite index** for fast lookup with tables:
- metrics
- models
- dimensions
- relationships

### 6. Semantic Query Engine

Generates SQL dynamically from metadata.

**Input:**
```json
{
  "metric": "mrr",
  "dimensions": ["month"],
  "filters": ["region = 'EU'"]
}
```

**Output:**
```sql
SELECT
  month,
  SUM(amount) AS mrr
FROM subscription_charges
WHERE status = 'active'
  AND region = 'EU'
GROUP BY month;
```

Executes in Snowflake via connector.

## FastAPI Backend

**Endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| POST | /extract | Run metadata extraction |
| GET | /metrics | List metrics |
| GET | /metrics/:id | Metric detail |
| POST | /query | Run semantic query |
| GET | /models | List promoted models |

## CLI Tool: `axi`

```bash
axi extract
axi metrics list
axi query --metric mrr --dims month
```

## Frontend (React)

MVP Pages:
- Metrics List
- Metric Detail
- Explore Metric
- Query Result Table

## Design Principles

- AXI does not require dbt Cloud
- AXI works with dbt Core OR Snowflake OR msh OR raw SQL
- AXI reads SQL as the source of truth
- No YAML modeling
- No new DSL
- No manual dimension/metric definitions
- Promotion controls what enters the semantic layer
- Separation from msh but optional integration

## Non-Goals (MVP)

- No lineage graphs yet
- No natural language interface
- No role-based access control
- No joins across models
- No materialization
- No time-travel SQL

Those come later.

---

*This is an AI Context File. Drop it into Cursor AI, Bolt.new, v1/dev, GitHub Copilot workspace, or any agent environment and the assistant will understand exactly what AXI is and how to develop it.*
