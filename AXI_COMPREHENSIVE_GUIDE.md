# AXI: Comprehensive Technical Guide for AI Agents and Developers

## 🎯 What is AXI?

**AXI (Axiom)** is an open-source semantic layer that transforms SQL models into business-ready semantic concepts. It extracts meaning from existing SQL code without requiring new DSLs, YAML configurations, or proprietary modeling languages.

### Core Mission
- **Zero DSL Required**: Works directly with your existing SQL
- **Warehouse-Native**: Designed for modern data warehouses (Snowflake, PostgreSQL)
- **dbt-Aware**: Deep integration with dbt Core projects
- **Headless Architecture**: API-first design supporting multiple frontends

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Data Sources  │    │   AXI Core       │    │   Consumers     │
│                 │    │                  │    │                 │
│ • dbt Models    │───▶│ • Semantic Engine│───▶│ • BI Tools      │
│ • Raw SQL Files │    │ • Metadata Store │    │ • Notebooks     │
│ • Snowflake     │    │ • Query Engine   │    │ • React UI      │
│ • PostgreSQL    │    │ • Cache Layer    │    │ • API Clients   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Components Breakdown

#### 1. **Backend (axi-semantic)**
- **Language**: Python
- **Framework**: FastAPI
- **License**: Business Source License (BSL 1.1)
- **Purpose**: Core semantic engine and API server

**Key Modules:**
- `extractor/`: SQL parsing and metadata extraction
- `metadata/`: Storage and indexing of semantic information
- `query/`: SQL generation and semantic query engine
- `api/`: REST API endpoints
- `dbt/`: dbt integration and manifest processing
- `snowflake/`: Snowflake-specific optimizations
- `cache/`: Query caching and performance
- `materialization/`: Metric materialization
- `glossary/`: Business glossary management

#### 2. **Frontend**
- **Technology**: React + TypeScript + Vite
- **License**: MIT
- **Purpose**: Semantic Explorer UI

**Key Features:**
- Metrics exploration and comparison
- Dimension analysis
- Entity relationship visualization
- Query builder and SQL preview
- Business glossary interface
- Graph-based semantic exploration

#### 3. **CLI (axi-cli)**
- **Technology**: Python + Typer
- **License**: MIT
- **Purpose**: Command-line interface for all AXI operations

## 🔄 How AXI Works

### 1. **Promotion System**
AXI uses a promotion system to determine which SQL models enter the semantic layer:

**Promotion Methods:**
- **Tag-based**: `-- axi: true` comment or `axi: true` tag
- **Folder-based**: Models in specific directories
- **Configuration-based**: Rules in `axi.yml`

**Example axi.yml:**
```yaml
include:
  tags: ["axi"]
  folders: ["models/marts", "models/analytics"]
exclude:
  tags: ["staging", "ignore"]
  folders: ["models/staging"]
```

### 2. **Metadata Extraction**
AXI parses SQL to extract:

- **Metrics**: Aggregate functions (SUM, COUNT, AVG, etc.)
- **Dimensions**: GROUP BY columns
- **Entities**: Primary keys and grain
- **Relationships**: JOIN patterns and foreign keys
- **Filters**: WHERE clauses
- **Grain**: Time-based grouping (DATE_TRUNC, etc.)

**Example SQL Input:**
```sql
-- axi: true
SELECT
  c.region,
  DATE_TRUNC('month', o.created_at) as month,
  SUM(o.amount) as mrr
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'active'
GROUP BY c.region, DATE_TRUNC('month', o.created_at)
```

**Extracted Metadata:**
```json
{
  "model": "revenue",
  "metrics": [
    {
      "name": "mrr",
      "expression": "SUM(o.amount)",
      "grain": "month"
    }
  ],
  "dimensions": ["region", "month"],
  "entities": ["orders", "customers"],
  "relationships": [
    {
      "from": "orders.customer_id",
      "to": "customers.id",
      "type": "foreign_key"
    }
  ],
  "filters": ["status = 'active'"]
}
```

### 3. **Semantic Query Engine**
Transforms business questions into optimized SQL:

**Input Request:**
```json
{
  "metric": "mrr",
  "dimensions": ["region"],
  "filters": ["region = 'EU'"]
}
```

**Generated SQL:**
```sql
SELECT
  c.region,
  SUM(o.amount) AS mrr
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.status = 'active'
  AND c.region = 'EU'
GROUP BY c.region
```

## 🚀 Key Features

### 1. **Metrics Layer**
- **Simple Metrics**: Direct aggregates (SUM, COUNT, AVG)
- **Ratio Metrics**: Safe division with TRY_DIVIDE
- **Semi-Additive**: Last value, non-summable metrics
- **Derived Metrics**: Combinations of other metrics
- **Time Intelligence**: 
  - Previous period comparisons
  - Rolling windows (7d, 30d)
  - To-date calculations (YTD, QTD)

### 2. **Semantic SQL Generation**
- **Join-Aware**: Automatically handles complex JOINs
- **Optimized**: Warehouse-specific optimizations
- **Snowflake-Specific**: IFF, TRY_DIVIDE, QUALIFY functions
- **Parameterized**: Safe SQL generation with validation

### 3. **dbt Integration**
- **Manifest Loading**: Reads `manifest.json` for metadata
- **Constraint Inference**: Derives constraints from dbt tests
- **Lineage Tracking**: Understands dbt model dependencies
- **Test Integration**: Uses dbt test results for semantic enrichment

### 4. **Snowflake Direct Integration** 🆕
- **No dbt Required**: Extract semantic metadata directly from Snowflake views
- **Full Metadata Sync**: Tables, columns, constraints, policies, lineage
- **Semantic Extraction**: Parse VIEW definitions to extract metrics/dimensions
- **Constraint Detection**: PK/FK from Snowflake + inferred from naming conventions
- **Policy Awareness**: Masking and row access policies
- **ACCOUNT_USAGE**: Automatic lineage extraction
- **Feature Parity with dbt**: Same semantic extraction capabilities

See [SNOWFLAKE_INTEGRATION_GUIDE.md](./SNOWFLAKE_INTEGRATION_GUIDE.md) for details.

### 5. **Business Glossary**
- **Auto-Generated**: From SQL and dbt metadata
- **Entity-Centric**: Organized around business entities
- **Versioned**: Track changes over time
- **Searchable**: Full-text search capabilities

### 6. **Caching & Materialization**
- **Query Caching**: Avoid redundant executions
- **Metric Tables**: Materialized aggregated tables
- **Semantic Marts**: Multi-metric materializations
- **Incremental Refresh**: Smart refresh strategies

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.9+
- Node.js 16+ (for frontend)
- Data warehouse access (Snowflake/PostgreSQL)

### Quick Start

1. **Install CLI:**
```bash
pip install axi-cli
```

2. **Run Demo:**
```bash
axi extract examples/demo
axi metrics list
axi query --metric mrr --dims customer_id
axi ui
```

3. **Access UI:**
Navigate to http://localhost:5173

### Development Setup

```bash
# Clone repository
git clone https://github.com/mshdata/axi.git
cd axi

# Recommended: install backend + CLI + frontend deps in one go (bootstraps hatchling and disables build isolation)
make install

# Manual alternative (if you prefer step-by-step; use your package mirror or a pre-downloaded wheel if offline)
python -m pip install --upgrade pip hatchling
PIP_NO_BUILD_ISOLATION=1 python -m pip install -e .

# Setup frontend
cd frontend
npm install
npm run dev

# Start backend API
cd ../backend
axi ui
```

## 📋 CLI Commands Reference

### Core Commands

#### `axi extract`
Extract metadata from SQL models
```bash
axi extract [path] [options]
--debug              # Enable verbose logging
--debug-models       # List discovered models only
--no-dbt            # Disable dbt integration
```

#### `axi query`
Generate or execute semantic queries
```bash
axi query --metric <name> [options]
--dims "dim1,dim2"  # Dimensions
--filters "f1,f2"   # Filters
--run               # Execute on warehouse
```

#### `axi ui`
Start the API server
```bash
axi ui [options]
--host localhost    # API host
--port 8000        # API port
```

### Metrics Management

#### `axi metrics list`
List all available metrics

#### `axi metrics describe <metric>`
Show detailed metric metadata

#### `axi metrics sql`
Generate SQL for a metric
```bash
axi metrics sql <metric> [options]
--dims "dim1,dim2"
--filters "f1,f2"
--dialect ansi|snowflake
--compare previous_period
--window rolling_7d
--explain
```

### dbt Integration

#### `axi dbt scan`
Auto-scan dbt project with smart defaults

#### `axi dbt manifest <path>`
Load dbt manifest for metadata enrichment

#### `axi dbt constraints`
List semantic constraints from dbt tests

### Glossary Management

#### `axi glossary generate`
Generate business glossary from metadata

#### `axi glossary create <term>`
Create new glossary term
```bash
axi glossary create revenue \
  --definition "Total income from sales" \
  --status approved \
  --entities orders,customers
```

#### `axi glossary search <query>`
Search glossary terms

### Advanced Features

#### `axi materialize create`
Create materialized metric tables
```bash
axi materialize create mrr \
  --dims "region,month" \
  --refresh auto
```

#### `axi snowflake sync`
Sync Snowflake metadata and extract semantic information from views (no dbt required)

```bash
# Full sync with semantic extraction
axi snowflake sync

# Sync specific schemas
axi snowflake sync --schemas MARTS,ANALYTICS

# Filter views for semantic extraction
axi snowflake sync --views "mart_%,fact_%"

# Schema metadata only (skip semantic extraction)
axi snowflake sync --skip-semantic
```

See [SNOWFLAKE_INTEGRATION_GUIDE.md](./SNOWFLAKE_INTEGRATION_GUIDE.md) for complete documentation.

#### `axi demo`
Generate sample project for testing

## 🔧 Configuration

### axi.yml Configuration File

```yaml
project: my_analytics

# dbt Integration
dbt:
  compiled_path: target/compiled/my_project/models

# Promotion Rules
promotion:
  include:
    tags: ["axi", "semantic"]
    folders: ["models/marts", "models/analytics"]
  exclude:
    tags: ["staging", "temp"]
    folders: ["models/staging", "models/raw"]

# Warehouse Settings
warehouse:
  type: snowflake
  account: my_account
  database: analytics
  schema: semantic

# Caching
cache:
  enabled: true
  ttl: 3600

# Materialization
materialization:
  enabled: true
  schema: semantic_marts
```

### Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///metadata/semantic_state.db
# or
DATABASE_URL=postgresql://user:pass@host/db

# Snowflake
SNOWFLAKE_ACCOUNT=my_account
SNOWFLAKE_USER=my_user
SNOWFLAKE_PASSWORD=my_pass
SNOWFLAKE_WAREHOUSE=my_wh
SNOWFLAKE_DATABASE=analytics
SNOWFLAKE_SCHEMA=semantic

# API
AXI_API_HOST=0.0.0.0
AXI_API_PORT=8000

# Debug
AXI_DEBUG=true
AXI_LOG_LEVEL=DEBUG
```

## 🎨 Frontend Features

### Pages and Components

#### 1. **Promotion Dashboard**
- Model promotion status
- Extraction results
- Configuration overview

#### 2. **Metrics Explorer**
- Metrics listing with search
- Metric detail views
- SQL preview and execution
- Metric comparison

#### 3. **Dimensions Browser**
- Dimension discovery
- Usage statistics
- Relationship mapping

#### 4. **Query Builder**
- Visual query construction
- SQL generation
- Result visualization
- Query saving

#### 5. **Semantic Graph**
- Entity relationship visualization
- Interactive exploration
- Lineage tracking

#### 6. **Business Glossary**
- Term definitions
- Entity mappings
- Version history
- Search interface

#### 7. **Settings**
- Configuration management
- Connection setup
- Cache management

### API Endpoints

#### Metrics
- `GET /metrics` - List metrics
- `GET /metrics/{id}` - Get metric details
- `GET /metrics/{id}/sql` - Generate SQL
- `POST /semantic/sql` - Generate semantic SQL

#### Entities
- `GET /entities` - List entities
- `GET /entities/{name}` - Get entity details

#### Graph
- `GET /api/graph/local` - Local subgraph
- `GET /api/graph/filtered` - Filtered graph
- `GET /api/graph/category` - Category view

#### Glossary
- `GET /api/glossary/terms` - List terms
- `GET /api/glossary/search` - Search glossary

## 🔍 Use Cases

### 1. **Business Intelligence**
- Consistent metrics across BI tools
- Self-service analytics
- Metric governance

### 2. **Data Science**
- Reproducible feature engineering
- Consistent training data
- Experiment tracking

### 3. **Product Analytics**
- Product metrics standardization
- A/B test metrics
- KPI tracking

### 4. **Financial Analytics**
- Revenue metrics
- Financial reporting
- Compliance metrics

### 5. **Operational Analytics**
- Dashboard metrics
- Alerting thresholds
- Performance KPIs

## 🏢 Enterprise Features

### Multi-Tenancy (AXI Cloud)
- Project isolation
- Environment management (dev/staging/prod)
- Scheduled refresh
- SSO/RBAC

### Performance
- Query caching
- Materialized views
- Connection pooling
- result streaming

### Governance
- Metric approval workflows
- Change tracking
- Audit logs
- Data lineage

### Monitoring
- Query performance metrics
- Cache hit rates
- Error tracking
- Usage analytics

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/
```

### Frontend Tests
```bash
cd frontend
npm test
```

### Integration Tests
```bash
# End-to-end testing
python test_e2e_full.py
```

## 🤝 Contributing

### Development Workflow
1. Fork repository
2. Create feature branch
3. Make changes with tests
4. Run linting: `./scripts/lint.sh`
5. Submit pull request

### Code Standards
- **Python**: `ruff` for formatting/linting
- **TypeScript**: `prettier` + `eslint`
- **Testing**:pytest for backend, Jest for frontend

### Plugin Development
AXI supports plugins for:
- Custom extractors
- New warehouse connectors
- Custom metrics
- Authentication providers

## 📊 Architecture Deep Dive

### Metadata Storage
AXI uses dual storage:
1. **JSON Files**: Human-readable metadata
2. **SQLite Index**: Fast querying and relationships

### Query Optimization
- **Rule-based optimizer**
- **Warehouse-specific hints**
- **Join order optimization**
- **Predicate pushdown**

### Caching Strategy
- **Query result caching**
- **Metadata caching**
- **Compiled SQL caching**
- **Dependency-based invalidation**

## 🔮 Future Roadmap

### Near Term
- Natural language interface
- Advanced time intelligence
- More warehouse connectors
- Enhanced UI/UX

### Long Term
- Machine learning optimization
- Real-time streaming support
- Advanced governance features
- Multi-warehouse federation

## 📚 Additional Resources

### Documentation
- [Official Docs](https://github.com/mshdata/axi-docs)
- [API Reference](./api/)
- [Examples](./examples/)

### Community
- [GitHub Discussions](https://github.com/mshdata/axi/discussions)
- [Issues](https://github.com/mshdata/axi/issues)
- [Contributing Guide](./CONTRIBUTING.md)

### Commercial
- [AXI Cloud](https://axi.cloud)
- [Enterprise Support](mailto:enterprise@axi.cloud)

---

## 🎯 Quick Reference for AI Agents

### Core Concepts
1. **Semantic Layer**: Business meaning over technical data
2. **Promotion**: Intentional inclusion of models in semantic layer
3. **Extraction**: Automatic metadata discovery from SQL
4. **Query Engine**: Business questions → optimized SQL

### Key Files to Understand
- `backend/axi/extractor/core.py` - Core extraction logic
- `backend/axi/query/engine.py` - SQL generation
- `backend/axi/metadata/indexer.py` - Metadata storage
- `axi-cli/axi_cli/main.py` - CLI interface
- `frontend/src/App.tsx` - Frontend routing

### Common Patterns
- SQL parsing with sqlglot
- FastAPI for REST APIs
- React with TypeScript for UI
- SQLite for metadata indexing
- Plugin architecture for extensibility

### Testing Strategy
- Unit tests for core logic
- Integration tests for API endpoints
- End-to-end tests for full workflows
- Performance tests for query generation

This guide provides a comprehensive understanding of AXI for both human developers and AI agents working with the codebase.
