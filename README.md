AXI: The Open Source Semantic Layer
SQL → Metrics · Dimensions · Entities · Relationships · Glossary · Semantic SQL

AXI is a headless, open-source semantic layer that turns your SQL models into business-ready concepts—metrics, dimensions, entities, relationships, and a complete business glossary—and then generates optimized, join-aware SQL for any downstream tool.

It is lightweight, warehouse-native, dbt-aware, and requires zero DSL.
Just SQL → semantics.

🚀 Why AXI?

Modern data teams face three persistent problems:

1. Rewriting the same SQL logic everywhere

JOINs, filters, CASE expressions, window logic, aggregations… repeated in BI tools, notebooks, and production apps.

2. Metric inconsistency

Every team calculates metrics slightly differently → misalignment and constant rework.

3. No central semantic truth

dbt models define tables, not meaning.
BI tools define metrics, not models.
No unified layer exists across the stack.

🧠 How AXI Solves This

AXI creates a semantic layer directly from your SQL:

Extracts metrics, dimensions, entities, relationships

Automatically infers join paths

Generates optimized SQL (Snowflake-aware)

Builds a business glossary for all concepts

Provides caching + materialized semantic marts

Integrates deeply with dbt Core

Includes a full Semantic Explorer UI

The result:
Define once. Query everywhere.

🏗️ Architecture
graph LR
    DW[(Warehouse\nSnowflake/PG)] --> AXI[AXI Core\nSemantic Engine]
    AXI --> API[FastAPI Server]
    AXI --> CLI[CLI Tool]
    API --> UI[Semantic Explorer]
    API --> BI[BI Tools]
    API --> NB[Notebooks]
    AXI --> Docs[Glossary & Semantic Output]

⚡ Quick Start
1. Install AXI CLI
pip install axi-cli

2. Run the Demo Project

AXI ships with a full demo you can run instantly:

# 1. Extract demo project
axi extract examples/demo

# 2. Inspect available metrics
axi metrics list

# 3. Run a semantic query (no SQL needed)
axi query --metric total_revenue --dims customer_id

# 4. Launch the Semantic Explorer UI
axi ui


Then open:

http://localhost:5173

✨ Features
🔍 Semantic Extraction (from SQL—no DSL)

AXI automatically extracts:

Metrics

Dimensions

Grain

Entities

Relationships

Filters

Tags

Descriptions

📊 Advanced Metrics Layer

Supports:

Simple metrics

Ratios (safe division with TRY_DIVIDE)

Semi-additive metrics

Derived metrics

Time intelligence:

Previous Period

Rolling windows

To-date measures

🧭 Semantic Query Engine

Join-aware SQL generation:

axi query --metric mrr --dims customers.region


AXI automatically finds the join graph and generates:

Optimized JOINs

Group-by logic

Snowflake-specific SQL (IFF, TRY_DIVIDE, QUALIFY)

🧱 dbt Integration

Loads manifest.json

Ingests models, sources, tests

Extracts constraints from unique/not_null tests

Enhances semantic graph with dbt lineage

❄️ Deep Snowflake Integration

Table + column metadata

Constraints (PK/FK)

Tags

Masking + row access policies

Lineage from ACCOUNT_USAGE

Snowflake-optimized SQL generation

📚 Business Glossary

Generates a complete glossary of:

Entities

Attributes

Metrics

Dimensions

Relationships

All derived from SQL + dbt metadata.

🚀 Caching & Materialized Semantic Marts

Query caching

Materialized metric tables

Multi-metric marts

Full + incremental refresh

🖥️ Semantic Explorer UI

Modern React UI for:

Metrics

Dimensions

Entities

Models

Semantic Graph

Glossary

SQL preview

Query runner

🆚 Comparison
Feature	AXI	dbt Metrics	LookML
Open Source	✅	⚠️ Deprecated	❌
Headless	✅	⚠️ Limited	❌
Auto-JOINs	✅	❌	✅
SQL-first	✅	❌	❌ DSL
Glossary	✅	❌	⚠️ Basic
Time Intelligence	✅	⚠️	⚠️
Caching + Marts	✅	❌	❌
Snowflake Integration	🔥	⚠️	⚠️
📁 Project Structure
backend/        Semantic Engine (BSL)
axi-cli/        CLI Tools (MIT)
frontend/       UI (MIT)
examples/       Demo Project
docker/         Docker Compose Support

🐳 Run with Docker
docker-compose up --build


Starts:

API (FastAPI)

UI (Vite/React)

Demo metadata

📘 Documentation

Documentation lives in a separate repo:
👉 https://github.com/your-org/axi-docs

(Hosted site link coming soon)

🌩️ AXI Cloud

A fully managed version of AXI offering:

Multi-tenant project management

Environments (dev/staging/prod)

Scheduled refresh

Snapshotting

Lineage (semantic + warehouse)

Query caching

Semantic marts

SSO + RBAC

Cloud runs AXI OSS under the hood—battle-tested, scalable, opinionated.

🤝 Contributing

We welcome contributions from the community.
See: CONTRIBUTING.md

📜 Licensing

AXI uses a dual-license structure:

Backend (axi-semantic)

Licensed under Business Source License (BSL 1.1).
This allows:

Free use

Commercial use

Modification

Redistribution

But prohibits offering AXI as a cloud-hosted service that competes with AXI Cloud.

Automatic Change Date: 2027-01-01
After that date, the backend becomes MIT.

CLI, UI, Examples, Docs

Licensed under MIT for maximum community adoption.

See the respective LICENSE files for exact terms.