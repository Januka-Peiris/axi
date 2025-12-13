AXI: The Open Source Semantic Layer
SQL -> Metrics | Dimensions | Entities | Relationships | Glossary | Semantic SQL

AXI is a headless, open-source semantic layer that turns SQL models into business-ready concepts (metrics, dimensions, entities, relationships, and a business glossary) and generates optimized, join-aware SQL for any downstream tool. It is warehouse-native, dbt-aware, Snowflake-friendly, and requires zero DSL.

## Why AXI
- Repeated SQL logic across BI tools, notebooks, and apps.
- Metric inconsistency between teams.
- No single semantic truth across dbt models and BI definitions.

## What AXI Does
- Extracts metrics, dimensions, entities, relationships, filters, tags, and descriptions from SQL.
- Infers join paths and generates optimized, join-aware SQL (Snowflake-aware).
- Builds a business glossary and materialized semantic marts with caching.
- Integrates deeply with dbt Core and ships a Semantic Explorer UI.
- Result: define once, query everywhere.

## Architecture
```
graph LR
    DW[(Warehouse\nSnowflake/PG)] --> AXI[AXI Core\nSemantic Engine]
    AXI --> API[FastAPI Server]
    AXI --> CLI[CLI Tool]
    API --> UI[Semantic Explorer]
    API --> BI[BI Tools]
    API --> NB[Notebooks]
    AXI --> Docs[Glossary & Semantic Output]
```

## Quick Start
1) Install the CLI
`pip install axi-cli`

2) Run the demo project
```
axi extract examples/demo
axi metrics list
axi query --metric total_revenue --dims customer_id
axi ui
```
Then open http://localhost:5173.

## Feature Highlights
- Semantic extraction (no DSL): metrics, dimensions, grain, entities, relationships, filters, tags, descriptions.
- Metrics layer: simple, ratios (safe TRY_DIVIDE), semi-additive, derived, time intelligence (previous period, rolling, to-date).
- Semantic query engine: join-aware SQL generation (`axi query --metric mrr --dims customers.region`), optimized JOINs, group-by logic, Snowflake SQL (IFF, TRY_DIVIDE, QUALIFY).
- dbt integration: loads manifest.json, ingests models/sources/tests, extracts constraints from unique/not_null, enriches the semantic graph with lineage.
- Snowflake integration: table/column metadata, PK/FK constraints, tags, masking/row access policies, ACCOUNT_USAGE lineage, Snowflake-optimized SQL.
- Business glossary: entities, attributes, metrics, dimensions, relationships derived from SQL plus dbt metadata.
- Caching and semantic marts: query caching, materialized metric tables, multi-metric marts, full and incremental refresh.
- Semantic Explorer UI: React UI for metrics, dimensions, entities, models, semantic graph, glossary, SQL preview, and query runner.

## Project Structure
- backend/  - Semantic Engine (BSL)
- axi-cli/  - CLI tools (MIT)
- frontend/ - UI (MIT)
- examples/ - Demo project
- docker/   - Docker Compose support

## Run with Docker
```
docker-compose up --build
```
Starts API (FastAPI), UI (Vite/React), PostgreSQL database, and demo metadata.

**Database Options:**
- **SQLite (default)**: Embedded database, no setup required. Perfect for local development.
- **PostgreSQL**: Server database for production. Configure via environment variables in `docker/compose.yaml`.

See `backend/axi/config/README.md` for detailed database configuration options.

## Documentation
Documentation lives in a separate repo: https://github.com/your-org/axi-docs
(Hosted site link coming soon.)

## AXI Cloud
Managed AXI with multi-tenant projects, environments (dev/staging/prod), scheduled refresh, snapshotting, semantic and warehouse lineage, query caching, semantic marts, and SSO/RBAC. Cloud runs AXI OSS under the hood.

## Contributing
We welcome contributions. See CONTRIBUTING.md.

## Licensing
- Backend (axi-semantic): Business Source License (BSL 1.1). Free/commercial use, modification, redistribution; prohibits offering AXI as a competing hosted service. Automatic Change Date: 2027-01-01 (becomes MIT afterward).
- CLI, UI, examples, docs: MIT. See respective LICENSE files for terms.
