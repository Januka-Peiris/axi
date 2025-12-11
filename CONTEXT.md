📄 AXI — AI CONTEXT FILE (v1.0)

The semantic layer product in the msh ecosystem

🔷 PRODUCT NAME

AXI — A semantic layer built from SQL.
Meaning inspired by “axiom” → a fundamental truth.

🔷 PRODUCT PURPOSE

AXI extracts meaning from SQL models to create:

a business-friendly semantic layer,

a metric glossary,

a dimension model,

and a no-SQL metric query engine,

powered entirely by existing SQL, without requiring:

YAML

LookML

Semantic DSLs

Proprietary modeling

AXI works independently OR inside the msh ecosystem, but is not part of msh itself.

🧩 HIGH-LEVEL DESCRIPTION

AXI:

Reads SQL from dbt Core, Snowflake, msh, or raw .sql files

Extracts metrics, dimensions, grains, filters, and source tables

Stores them in metadata JSON + SQLite index

Provides a FastAPI backend for semantic querying

Generates SQL dynamically and executes it in Snowflake

Supports a React UI for business-friendly exploration

Only extracts models that are promoted

🧩 PROMOTION MODEL (CRITICAL)

AXI must only extract metadata from promoted models/tables, using:

1. Tag-based promotion

Works in dbt, Snowflake, and msh:

dbt
tags: ["axi"]


or SQL comment:

-- axi: true

Snowflake

Using table tags:

alter table analytics.mrr set tag axi = 'true';

msh

Inside .msh file:

axi: true

2. Folder-based promotion (dbt only)

Any model inside included folders is promoted.

Example config:

include:
  folders:
    - models/axi
    - models/business

3. Include/Exclude Rules

Main config file: axi.yml

include:
  tags: ["axi"]
  folders: ["models/axi"]
exclude:
  folders: ["raw/", "staging/"]
  tags: ["ignore"]


Promotion logic:

PROMOTED IF:
  (dbt/msh/Snowflake tag == axi) 
  OR folder matches include rule
EXCEPT WHEN:
  file or folder matches exclusion rule


This ensures clean, intentional semantic modeling.

🧠 ARCHITECTURE OVERVIEW

Repo structure:

axi/
  backend/
    axi/
      config/
      extractor/
      metadata/
      api/
  frontend/
    src/
  axi-cli/

🧠 BACKEND COMPONENTS
1. Config Loader

Loads axi.yml and exposes:

include.tags

include.folders

exclude.tags

exclude.folders

2. Promotion Engine

Determines whether a model should be extracted:

checks tags

checks folder inclusion

checks exclude rules

3. SQL Scanner

Scans directories and finds .sql models.

Later:
Supports dbt compiled folder, msh assets, Snowflake extraction.

4. Metadata Extractor

Uses sqlglot to parse SQL and extract:

metrics (SUM, COUNT, AVG)

dimensions (GROUP BY)

filters (WHERE)

grain (DATE_TRUNC)

source tables (FROM/JOIN)

Output example:

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

5. Metadata Storage

Two layers:

A) JSON files

Stored under:

axi/metadata/models/<model_name>.json

B) SQLite index

For fast lookup and querying.

Tables:

metrics

models

dimensions

relationships (later)

6. Semantic Query Engine

Generates SQL dynamically from metadata:

Inputs:

{
  "metric": "mrr",
  "dimensions": ["month"],
  "filters": ["region = 'EU'"]
}


Outputs SQL:

SELECT
  month,
  SUM(amount) AS mrr
FROM subscription_charges
WHERE status = 'active'
  AND region = 'EU'
GROUP BY month;


Executes in Snowflake via connector.

🧠 FASTAPI BACKEND

Endpoints:

POST /extract      → run metadata extraction
GET  /metrics      → list metrics
GET  /metrics/:id  → metric detail
POST /query        → run semantic query
GET  /models       → list promoted models

🧠 CLI TOOL: axi

Commands:

axi extract

axi list metrics

axi run query --metric mrr --dims month

🎨 FRONTEND (REACT) — MVP PAGES

Metrics List

Metric Detail

Explore Metric

Query Result Table

🧱 STAGE 1 IMPLEMENTATION PLAN

Set up AXI repo (backend, frontend, CLI folders)

Implement config loader

Implement promotion engine

Implement SQL scanner

Implement metadata extractor skeleton

Implement FastAPI bootstrap

Implement CLI scaffold

This produces the backbone of AXI.

🚀 STAGE 2+ (For Future AI Use)

Full metadata extraction via sqlglot

SQLite index builder

Semantic SQL generator

Snowflake connector

UI query builder

dbt package for metadata extraction

integration with msh manifests (optional)

🎯 DESIGN PRINCIPLES

AXI does not require dbt Cloud

AXI works with dbt Core OR Snowflake OR msh OR raw SQL

AXI reads SQL as the source of truth

No YAML modeling

No new DSL

No manual dimension/metric definitions

Promotion controls what enters the semantic layer

Separation from msh but optional integration

🔐 NON-GOALS (MVP)

No lineage graphs yet

No natural language interface

No role-based access control

No joins across models

No materialization

No time-travel SQL

Those come later.

✔ This is your AI Context File

You can drop it into:

Cursor AI context

Bolt.new context

v1/dev context

GitHub Copilot workspace

Any agent environment

and the assistant will understand exactly what AXI is and how to develop it.