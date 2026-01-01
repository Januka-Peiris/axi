# AXI Snowflake Direct Integration Guide

## Overview

AXI now supports **direct Snowflake integration** without requiring dbt. This allows you to extract semantic metadata (metrics, dimensions, entities, relationships) directly from your Snowflake views and tables.

## Features

### What Gets Extracted

#### Schema Metadata
- **Tables and Views**: All table/view names, types, schemas, databases
- **Columns**: Column names, data types, nullability, ordinal positions
- **Constraints**: Primary keys, foreign keys (explicit and inferred)
- **Policies**: Masking policies and row access policies
- **Lineage**: Table dependencies from ACCOUNT_USAGE
- **Tags**: Snowflake tags (future enhancement)

#### Semantic Metadata (from VIEW definitions)
- **Metrics**: Aggregate functions (SUM, COUNT, AVG, MIN, MAX, etc.)
- **Dimensions**: GROUP BY columns
- **Filters**: WHERE clause conditions
- **Grain**: Time-based grouping (DATE_TRUNC patterns)
- **Relationships**: JOIN patterns between entities

### How It Works

1. **Schema Sync**: Fetches table/column metadata from `INFORMATION_SCHEMA`
2. **Constraint Detection**: Uses `SHOW PRIMARY KEYS` and `SHOW IMPORTED KEYS`
3. **Relationship Inference**: Detects FK relationships from naming conventions (`_id`, `_fk` suffixes)
4. **View Parsing**: Uses `GET_DDL('VIEW', ...)` to extract view definitions
5. **Semantic Extraction**: Parses SQL through the same engine as dbt models
6. **Metadata Writing**: Stores extracted metrics/dimensions in the metadata store

## Authentication

AXI supports **all modern Snowflake authentication methods**:

### 1. Password Authentication (Basic)

```bash
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export SNOWFLAKE_USER=myuser
export SNOWFLAKE_PASSWORD=mypassword
export SNOWFLAKE_WAREHOUSE=compute_wh
export SNOWFLAKE_DATABASE=analytics
export SNOWFLAKE_SCHEMA=marts
```

### 2. Key-Pair Authentication (Recommended for Production)

**Generate key pair:**
```bash
# Generate private key
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out snowflake_key.pem -nocrypt

# Generate public key
openssl rsa -in snowflake_key.pem -pubout -out snowflake_key.pub

# Assign public key to Snowflake user (run in Snowflake)
ALTER USER myuser SET RSA_PUBLIC_KEY='<public_key_contents>';
```

**Configure AXI:**
```bash
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export SNOWFLAKE_USER=myuser
export SNOWFLAKE_PRIVATE_KEY_PATH=~/.ssh/snowflake_key.pem
# Optional: if key is encrypted
export SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=my_passphrase
export SNOWFLAKE_WAREHOUSE=compute_wh
export SNOWFLAKE_DATABASE=analytics
export SNOWFLAKE_SCHEMA=marts
```

**Or in axi.yml:**
```yaml
snowflake:
  account: xy12345.us-east-1
  user: myuser
  private_key_path: ~/.ssh/snowflake_key.pem
  # private_key_passphrase: env:SNOWFLAKE_KEY_PASSPHRASE  # if encrypted
  warehouse: compute_wh
  database: analytics
  schema: marts
```

### 3. SSO Authentication (Browser-based)

**Configure:**
```bash
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export SNOWFLAKE_USER=myuser@company.com
export SNOWFLAKE_AUTHENTICATOR=externalbrowser
export SNOWFLAKE_WAREHOUSE=compute_wh
export SNOWFLAKE_DATABASE=analytics
```

**Or in axi.yml:**
```yaml
snowflake:
  account: xy12345.us-east-1
  user: myuser@company.com
  authenticator: externalbrowser
  warehouse: compute_wh
  database: analytics
```

When you run `axi snowflake sync`, a browser window will open for SSO authentication.

### 4. OAuth Authentication

**Configure:**
```bash
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export SNOWFLAKE_USER=myuser
export SNOWFLAKE_TOKEN=<your_oauth_token>
export SNOWFLAKE_WAREHOUSE=compute_wh
export SNOWFLAKE_DATABASE=analytics
```

### 5. Okta Authentication

**Configure:**
```bash
export SNOWFLAKE_ACCOUNT=xy12345.us-east-1
export SNOWFLAKE_USER=myuser@company.com
export SNOWFLAKE_AUTHENTICATOR=https://company.okta.com
export SNOWFLAKE_PASSWORD=mypassword
export SNOWFLAKE_WAREHOUSE=compute_wh
export SNOWFLAKE_DATABASE=analytics
```

## Quick Start

### Prerequisites

1. **Authentication**: Choose one of the methods above

2. **Required Privileges**:
   - `SELECT` on `INFORMATION_SCHEMA.TABLES`
   - `SELECT` on `INFORMATION_SCHEMA.COLUMNS`
   - `USAGE` on schemas you want to sync
   - `SELECT` on views you want to extract
   - `USAGE` on database
   - Optional: `IMPORTED PRIVILEGES` on `SNOWFLAKE` database (for ACCOUNT_USAGE lineage)

### Basic Usage

#### 1. Full Sync (All Schemas)

```bash
axi snowflake sync
```

This will:
- Extract all tables/views from all non-system schemas
- Detect primary/foreign key constraints
- Infer relationships from naming conventions
- Parse all VIEW definitions for semantic metadata
- Extract metrics, dimensions, and relationships

#### 2. Sync Specific Schemas

```bash
axi snowflake sync --schemas MARTS,ANALYTICS,FINANCE
```

Only syncs tables/views from the specified schemas.

#### 3. Filter Views for Semantic Extraction

```bash
axi snowflake sync --views "mart_%,fact_%,dim_%"
```

Only extracts semantic metadata from views matching these patterns (using SQL LIKE).

#### 4. Schema Metadata Only (No Semantic Extraction)

```bash
axi snowflake sync --skip-semantic
```

Extracts schema metadata (tables, columns, constraints) but skips parsing VIEW definitions.

#### 5. Skip Constraint Detection

```bash
axi snowflake sync --skip-constraints --skip-inferred
```

Faster sync if you don't need PK/FK information.

## Configuration

### axi.yml Configuration

You can configure Snowflake sync options in `axi.yml`:

```yaml
project: my_analytics

# Snowflake connection (can also use env vars)
snowflake:
  account: my_account
  warehouse: compute_wh
  database: analytics
  schema: marts  # default schema

# Snowflake promotion rules (optional)
snowflake_promotion:
  # Schemas to sync
  schemas:
    - MARTS
    - ANALYTICS
    - FINANCE

  # View patterns for semantic extraction (SQL LIKE patterns)
  view_patterns:
    - "mart_%"
    - "fact_%"
    - "dim_%"
    - "rpt_%"

  # Skip options (for faster sync)
  skip_constraints: false
  skip_inferred_relationships: false
  skip_semantic_extraction: false

# General settings (applies to both dbt and Snowflake)
metadata_dir: ./metadata_store
```

### Environment Variables

**Password Authentication:**
```bash
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=myuser
SNOWFLAKE_PASSWORD=mypassword
SNOWFLAKE_WAREHOUSE=compute_wh
SNOWFLAKE_DATABASE=analytics
SNOWFLAKE_SCHEMA=marts
SNOWFLAKE_ROLE=analyst_role  # optional
```

**Key-Pair Authentication:**
```bash
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=myuser
SNOWFLAKE_PRIVATE_KEY_PATH=~/.ssh/snowflake_key.pem
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=key_password  # if key is encrypted
SNOWFLAKE_WAREHOUSE=compute_wh
SNOWFLAKE_DATABASE=analytics
SNOWFLAKE_SCHEMA=marts
```

**SSO Authentication:**
```bash
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=myuser@company.com
SNOWFLAKE_AUTHENTICATOR=externalbrowser
SNOWFLAKE_WAREHOUSE=compute_wh
SNOWFLAKE_DATABASE=analytics
```

**Advanced Options:**
```bash
# Connection timeouts
SNOWFLAKE_LOGIN_TIMEOUT=60           # seconds
SNOWFLAKE_NETWORK_TIMEOUT=120        # seconds

# AXI settings
AXI_METADATA_DIR=./metadata_store
AXI_LOG_LEVEL=INFO
AXI_DEBUG=false
```

## CLI Reference

### `axi snowflake sync`

Main command to sync Snowflake metadata and extract semantic information.

**Options:**
- `--schemas <list>`: Comma-separated list of schemas (e.g., `MARTS,ANALYTICS`)
- `--views <patterns>`: Comma-separated view patterns (e.g., `mart_%,fact_%`)
- `--skip-constraints`: Skip PK/FK constraint detection (faster)
- `--skip-inferred`: Skip inferring relationships from naming conventions
- `--skip-semantic`: Skip semantic metadata extraction from views

**Examples:**
```bash
# Full sync
axi snowflake sync

# Specific schemas with view filtering
axi snowflake sync --schemas MARTS,ANALYTICS --views "mart_%,fact_%"

# Schema metadata only
axi snowflake sync --skip-semantic

# Fast sync (no constraints, no semantic)
axi snowflake sync --skip-constraints --skip-inferred --skip-semantic
```

### `axi snowflake tables`

List all synced tables and views.

```bash
axi snowflake tables
```

Output: JSON array of tables with schema, name, type, comment, created/modified dates.

### `axi snowflake columns <table>`

List columns for a specific table.

```bash
axi snowflake columns my_table_name
```

### `axi snowflake constraints`

List all detected constraints (PK/FK).

```bash
axi snowflake constraints
```

Shows:
- Primary keys
- Foreign keys (explicit from Snowflake)
- Inferred foreign keys (from naming conventions)

### `axi snowflake lineage [table]`

Show table lineage from Snowflake ACCOUNT_USAGE.

```bash
# All lineage
axi snowflake lineage

# Lineage for specific table
axi snowflake lineage my_table
```

### `axi snowflake policies`

List masking and row access policies.

```bash
axi snowflake policies
```

## How Semantic Extraction Works

### 1. View Detection

AXI queries `sf_tables` for all views (or views matching patterns):

```sql
SELECT database, schema, name, type
FROM sf_tables
WHERE type = 'VIEW'
  AND (name LIKE 'mart_%' OR name LIKE 'fact_%')
```

### 2. DDL Retrieval

For each view, AXI uses Snowflake's `GET_DDL` function:

```sql
SELECT GET_DDL('VIEW', 'DATABASE.SCHEMA.VIEW_NAME')
```

Returns:
```sql
CREATE OR REPLACE VIEW DATABASE.SCHEMA.REVENUE_METRICS AS
SELECT
  c.region,
  DATE_TRUNC('month', o.created_at) as month,
  SUM(o.amount) as total_revenue,
  COUNT(DISTINCT o.customer_id) as customer_count
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'paid'
GROUP BY c.region, DATE_TRUNC('month', o.created_at)
```

### 3. SQL Extraction

AXI extracts the SELECT statement from the DDL (removes `CREATE VIEW ... AS` prefix).

### 4. Semantic Parsing

The SELECT statement is parsed using AXI's core extractor (`axi.extractor.core.extract_metadata`), which:

- **Identifies Metrics**:
  - `total_revenue` → SUM(o.amount)
  - `customer_count` → COUNT(DISTINCT o.customer_id)

- **Identifies Dimensions**:
  - `region` (from c.region)
  - `month` (from DATE_TRUNC)

- **Detects Grain**:
  - `month` → Time grain detected

- **Identifies Filters**:
  - `status = 'paid'`

- **Detects Joins**:
  - `orders JOIN customers ON customer_id = id`

### 5. Metadata Writing

Extracted metadata is written to JSON files in `metadata_store/models/<view_name>.json`:

```json
{
  "model": "revenue_metrics",
  "source": "snowflake",
  "schema_name": "marts",
  "database_name": "analytics",
  "physical_location": "analytics.marts.revenue_metrics",
  "metrics": [
    {
      "name": "total_revenue",
      "expression": "SUM(o.amount)",
      "type": "simple",
      "grain": "month"
    },
    {
      "name": "customer_count",
      "expression": "COUNT(DISTINCT o.customer_id)",
      "type": "simple",
      "grain": "month"
    }
  ],
  "dimensions": ["region", "month"],
  "filters": ["status = 'paid'"],
  "grain": "month"
}
```

## Constraint Detection

### Explicit Constraints (from Snowflake)

AXI uses Snowflake's `SHOW` commands:

```sql
-- Primary Keys
SHOW PRIMARY KEYS IN SCHEMA MARTS;

-- Foreign Keys
SHOW IMPORTED KEYS IN SCHEMA MARTS;
```

These are stored as `PRIMARY_KEY` and `FOREIGN_KEY` constraint types.

### Inferred Constraints (from Naming Conventions)

AXI infers FK relationships from common patterns:

1. **`column_id` → `columns` table**
   - `customer_id` → `customers.id`
   - `order_id` → `orders.id`

2. **`column_fk` → `column` table**
   - `customer_fk` → `customer.id`

3. **Plural/Singular matching**
   - `category_id` → `categories.id` OR `category.id`

**Important**: Inferred constraints are stored with `join_type: "INFERRED_FK"`. They are:
- Explicitly marked (never silent)
- Not used in query generation by default
- Opt-in for join path resolution

Use `--skip-inferred` to disable inference entirely.

## Relationship Creation

All constraints (explicit and inferred) are converted to semantic relationships in the `relationships` table:

```python
{
  "parent_model": "customers",
  "child_model": "orders",
  "fk_column": "customer_id",
  "pk_column": "id",
  "join_type": "SNOWFLAKE_FK"  # or "INFERRED_FK"
}
```

These relationships enable:
- Automatic JOIN generation in queries
- Relationship graph visualization
- Dimension reachability analysis

## Feature Parity with dbt

| Feature | dbt Integration | Snowflake Direct |
|---------|----------------|------------------|
| **Metadata Extraction** | ✅ manifest.json | ✅ INFORMATION_SCHEMA |
| **Semantic Parsing** | ✅ Compiled SQL | ✅ VIEW DDL |
| **Metrics Detection** | ✅ Aggregates | ✅ Aggregates |
| **Dimensions** | ✅ GROUP BY | ✅ GROUP BY |
| **Grain Detection** | ✅ DATE_TRUNC | ✅ DATE_TRUNC |
| **Relationships** | ✅ dbt tests | ✅ PK/FK + inferred |
| **Primary Keys** | ✅ unique tests | ✅ SHOW PRIMARY KEYS |
| **Foreign Keys** | ✅ relationships tests | ✅ SHOW IMPORTED KEYS |
| **Lineage** | ✅ depends_on | ✅ ACCOUNT_USAGE |
| **Column Metadata** | ✅ manifest | ✅ INFORMATION_SCHEMA |
| **Policies** | ❌ | ✅ Masking/Row Access |
| **Tags** | ✅ dbt tags | 🔜 Snowflake tags |
| **Incremental Models** | ✅ | ⚠️ Views only |
| **Seeds** | ✅ | ⚠️ Tables as entities |

**Legend:**
- ✅ Fully supported
- 🔜 Planned
- ⚠️ Partial support
- ❌ Not applicable

## Best Practices

### 1. Naming Conventions

For best results with inferred relationships, use consistent naming:

```sql
-- Good: Clear FK pattern
CREATE VIEW orders AS
SELECT
  order_id,
  customer_id,      -- Will infer FK to customers.id
  product_id,       -- Will infer FK to products.id
  created_date
FROM raw.orders;

-- Also supported
CREATE VIEW orders AS
SELECT
  order_id,
  customer_fk,      -- Will infer FK to customer.id
  product_fk        -- Will infer FK to product.id
FROM raw.orders;
```

### 2. View Structure

Create semantic views with clear aggregations:

```sql
-- Good: Clear semantic structure
CREATE VIEW mart_revenue AS
SELECT
  DATE_TRUNC('month', order_date) as month,
  customer_segment,
  SUM(amount) as total_revenue,
  COUNT(DISTINCT customer_id) as customer_count,
  AVG(amount) as avg_order_value
FROM orders
WHERE status = 'completed'
GROUP BY 1, 2;

-- Avoid: No aggregations (will be skipped)
CREATE VIEW customer_list AS
SELECT customer_id, name, email
FROM customers;
```

### 3. Schema Organization

Organize schemas by purpose:

```
ANALYTICS
├── MARTS          ← Semantic views (extract these)
│   ├── mart_revenue
│   ├── mart_customers
│   └── mart_products
├── STAGING        ← Raw data (skip these)
└── INTERMEDIATE   ← Transformations (optional)
```

Sync only semantic schemas:
```bash
axi snowflake sync --schemas MARTS --views "mart_%"
```

### 4. Incremental Sync

For large Snowflake instances, start with specific schemas:

```bash
# Day 1: Sync marts only
axi snowflake sync --schemas MARTS

# Day 2: Add analytics
axi snowflake sync --schemas MARTS,ANALYTICS

# Production: Full sync
axi snowflake sync
```

### 5. Performance Optimization

**Fast Schema-Only Sync** (for development):
```bash
axi snowflake sync --skip-semantic
```

**Full Sync** (for production):
```bash
axi snowflake sync --schemas MARTS,ANALYTICS --views "mart_%,fact_%"
```

## Troubleshooting

### No Views Found

**Symptom**: "No views found matching criteria"

**Solution**:
1. Check schema names are uppercase: `--schemas MARTS` (not `marts`)
2. Verify views exist: `axi snowflake tables`
3. Check view patterns: Use SQL LIKE syntax (`mart_%` not `mart_*`)

### Permission Denied

**Symptom**: "SQL access control error"

**Solution**:
1. Grant required privileges:
   ```sql
   -- As ACCOUNTADMIN
   GRANT USAGE ON DATABASE analytics TO ROLE analyst_role;
   GRANT USAGE ON SCHEMA analytics.marts TO ROLE analyst_role;
   GRANT SELECT ON ALL VIEWS IN SCHEMA analytics.marts TO ROLE analyst_role;
   ```

2. For lineage, grant ACCOUNT_USAGE access:
   ```sql
   GRANT IMPORTED PRIVILEGES ON DATABASE snowflake TO ROLE analyst_role;
   ```

### Views Skipped During Extraction

**Symptom**: "Skipped: no grouping/aggregation detected"

**Cause**: View doesn't contain semantic content (no aggregations/GROUP BY).

**Solution**: This is expected behavior. AXI only extracts views with:
- Aggregate functions (SUM, COUNT, AVG, etc.)
- GROUP BY clauses
- Clear metrics/dimensions

Non-semantic views are still stored as entities but don't generate metrics.

### GET_DDL Fails

**Symptom**: "Could not fetch DDL for VIEW"

**Solutions**:
1. Verify view exists: Check `axi snowflake tables`
2. Check permissions: Ensure `SELECT` on view
3. Try manually: `SELECT GET_DDL('VIEW', 'DB.SCHEMA.VIEW')`

### Constraints Not Detected

**Symptom**: `axi snowflake constraints` shows empty

**Causes**:
1. Ran with `--skip-constraints` flag
2. Snowflake doesn't have explicit constraints defined
3. Table names don't follow naming conventions for inference

**Solutions**:
1. Run full sync: `axi snowflake sync`
2. Define constraints in Snowflake:
   ```sql
   ALTER TABLE customers ADD PRIMARY KEY (id);
   ALTER TABLE orders ADD FOREIGN KEY (customer_id) REFERENCES customers(id);
   ```
3. Use naming conventions: `customer_id`, `order_id`, etc.

## Advanced Usage

### Combining with dbt

You can use both dbt and Snowflake direct integration:

```bash
# Extract from dbt models
axi dbt scan

# Also extract from Snowflake views not in dbt
axi snowflake sync --schemas LEGACY_MARTS --views "v_%"
```

### Custom View Filtering

Use SQL LIKE patterns to target specific views:

```bash
# All fact and dimension tables
axi snowflake sync --views "fact_%,dim_%"

# Reports and dashboards
axi snowflake sync --views "rpt_%,dash_%"

# Version-specific
axi snowflake sync --views "%_v2,%_v3"
```

### Automation

Add to CI/CD pipeline:

```bash
#!/bin/bash
# sync_snowflake.sh

# Set credentials from secrets
export SNOWFLAKE_ACCOUNT=$SF_ACCOUNT
export SNOWFLAKE_USER=$SF_USER
export SNOWFLAKE_PASSWORD=$SF_PASSWORD

# Sync production schemas
axi snowflake sync --schemas MARTS,ANALYTICS

# Publish metrics
axi metrics list --format json > metrics.json
```

## Next Steps

After syncing Snowflake metadata:

1. **View Extracted Metrics**:
   ```bash
   axi metrics list
   ```

2. **View Entities**:
   ```bash
   axi entities list
   ```

3. **Generate Queries**:
   ```bash
   axi query --metric total_revenue --dims region,month
   ```

4. **Start UI**:
   ```bash
   axi ui
   # Visit http://localhost:5173
   ```

5. **Explore Relationships**:
   - Navigate to the Graph view in UI
   - See entity relationships
   - Explore join paths

## Comparison: dbt vs. Snowflake Direct

### When to Use dbt Integration

- You already have a dbt project
- You want Git-based version control for metrics
- You need dbt-specific features (incremental models, tests, docs)
- You want to define metrics in code (YAML/SQL)

### When to Use Snowflake Direct

- You don't use dbt
- You have legacy views in Snowflake
- You want to quickly explore existing Snowflake views
- You need real-time sync with Snowflake metadata
- Your team prefers defining logic in Snowflake views

### Use Both!

Many teams use both approaches:
- **dbt** for new metrics and transformations
- **Snowflake direct** for legacy views and ad-hoc exploration

```bash
# Daily: Sync dbt models
axi dbt scan

# Weekly: Sync legacy Snowflake views
axi snowflake sync --schemas LEGACY
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/mshdata/axi/issues
- Documentation: https://github.com/mshdata/axi/docs
- Examples: `./examples/snowflake/`

