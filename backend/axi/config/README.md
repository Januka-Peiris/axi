# AXI Configuration Guide

This document describes how to configure the AXI semantic layer.

## Configuration Overview

AXI uses a two-tier configuration system:

1. **Application Settings** (`AXISettings`): Application-level settings loaded from environment variables or `.env` files
2. **Project Config** (`Config`): Project-specific configuration loaded from `axi.yml` YAML files

## Application Settings

Application settings control how AXI runs (logging, API server, etc.) and are loaded from environment variables with the `AXI_` prefix or from `.env` files.

### Environment Variables

All application settings use the `AXI_` prefix:

| Variable | Default | Description |
|---------|---------|-------------|
| `AXI_METADATA_DIR` | Auto-detected | Directory for storing metadata |
| `AXI_ENV` | `local` | Environment name (dev, staging, prod, local) |
| `AXI_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `AXI_LOG_FILE` | None | Path to log file (optional) |
| `AXI_LOG_JSON` | `false` | Use JSON format for structured logging |
| `AXI_API_HOST` | `0.0.0.0` | API server host |
| `AXI_API_PORT` | `8000` | API server port |
| `AXI_DEMO_MODE` | `false` | Enable demo mode |
| `AXI_DEBUG` | `false` | Enable debug mode |

### .env Files

You can use `.env` files instead of environment variables. AXI loads `.env` files in this priority order:

1. `.env.local` (highest priority, for local overrides)
2. `.env.{AXI_ENV}` (environment-specific, e.g., `.env.dev`, `.env.prod`)
3. `.env` (default)

Example `.env` file:

```bash
AXI_ENV=dev
AXI_LOG_LEVEL=DEBUG
AXI_LOG_FILE=./logs/axi.log
AXI_METADATA_DIR=./metadata_store
```

**Note**: Environment variables already set take precedence over `.env` file values.

## Project Configuration (axi.yml)

Project configuration is stored in `axi.yml` files and controls project-specific settings like promotion rules, dbt integration, and Snowflake credentials.

### Environment-Specific Config Files

AXI supports environment-specific config files:

- `axi.dev.yml` (loaded when `AXI_ENV=dev`)
- `axi.staging.yml` (loaded when `AXI_ENV=staging`)
- `axi.prod.yml` (loaded when `AXI_ENV=prod`)
- `axi.yml` (default, used if no environment-specific file exists)

### Configuration Schema

```yaml
# Promotion rules
include:
  folders:
    - "models/marts/**"
  tags:
    - "axi"

exclude:
  folders:
    - "models/staging/**"
  tags: []

# Promotion configuration
promotion:
  mode: "auto"  # auto, strict, hybrid

# dbt integration
dbt:
  compiled_path: "./target/compiled"

# Dimension configuration
dimensions:
  keep:
    - "date"
    - "customer_id"
  drop:
    - "internal_id"

# Snowflake credentials
snowflake:
  account: "your_account"
  user: "your_user"
  password: "env:SNOWFLAKE_PASSWORD"  # Reference env var
  role: "your_role"
  warehouse: "your_warehouse"
  database: "your_database"
  schema: "your_schema"
```

### Environment Variable Substitution

You can reference environment variables in YAML config files using two syntaxes:

1. **`env:VAR_NAME`** syntax:
   ```yaml
   snowflake:
     password: "env:SNOWFLAKE_PASSWORD"
   ```

2. **`${VAR_NAME}`** syntax:
   ```yaml
   snowflake:
     database: "${SNOWFLAKE_DB}"
   ```

## Secrets Management

### Best Practices

1. **Never commit secrets to version control**
   - Use `.env` files for local development (add to `.gitignore`)
   - Use environment variables in production
   - Use secret management systems (AWS Secrets Manager, HashiCorp Vault) for production

2. **Use environment variable references in YAML**
   ```yaml
   snowflake:
     password: "env:SNOWFLAKE_PASSWORD"  # Recommended
   ```

3. **Separate secrets from config**
   - Store secrets in environment variables or `.env` files
   - Reference them in `axi.yml` using `env:` syntax

### Snowflake Credentials

Snowflake credentials can be provided via:

1. **Config file** (`axi.yml`):
   ```yaml
   snowflake:
     account: "your_account"
     user: "your_user"
     password: "env:SNOWFLAKE_PASSWORD"
     # ... other fields
   ```

2. **Environment variables** (with backward compatibility):
   - `AXI_SNOWFLAKE_ACCOUNT` or `SNOWFLAKE_ACCOUNT`
   - `AXI_SNOWFLAKE_USER` or `SNOWFLAKE_USER`
   - `AXI_SNOWFLAKE_PASSWORD` or `SNOWFLAKE_PASSWORD`
   - `AXI_SNOWFLAKE_ROLE` or `SNOWFLAKE_ROLE`
   - `AXI_SNOWFLAKE_WAREHOUSE` or `SNOWFLAKE_WAREHOUSE`
   - `AXI_SNOWFLAKE_DB` or `SNOWFLAKE_DB`
   - `AXI_SNOWFLAKE_SCHEMA` or `SNOWFLAKE_SCHEMA`

## Configuration Validation

All configuration is validated on load:

- **Settings**: Validated by Pydantic with type checking
- **Config**: Validated by Pydantic models with field validators
- **Secrets**: Validated when used (e.g., on Snowflake connection)

### Common Validation Errors

1. **Missing required fields**: Clear error messages indicate which fields are missing
2. **Invalid file paths**: Paths are validated to exist (for dbt.compiled_path)
3. **Invalid identifiers**: Snowflake identifiers are validated for format
4. **Placeholder values**: Detected and reported (e.g., "your_account", "TODO")

## Examples

### Development Setup

`.env.local`:
```bash
AXI_ENV=dev
AXI_LOG_LEVEL=DEBUG
AXI_DEBUG=true
```

`axi.dev.yml`:
```yaml
promotion:
  mode: "auto"
  include:
    folders: ["**"]
  
snowflake:
  account: "dev_account"
  user: "dev_user"
  password: "env:SNOWFLAKE_PASSWORD"
  warehouse: "dev_warehouse"
  database: "dev_db"
  schema: "dev_schema"
```

### Production Setup

Environment variables (set in deployment):
```bash
export AXI_ENV=prod
export AXI_LOG_LEVEL=INFO
export AXI_LOG_FILE=/var/log/axi/axi.log
export AXI_METADATA_DIR=/app/metadata_store
```

`axi.prod.yml`:
```yaml
promotion:
  mode: "strict"
  include:
    folders: ["models/marts/**"]
    tags: ["promoted"]
  
snowflake:
  account: "prod_account"
  user: "prod_user"
  password: "env:SNOWFLAKE_PASSWORD"  # From secrets manager
  warehouse: "prod_warehouse"
  database: "prod_db"
  schema: "prod_schema"
```

## Migration from Old Configuration

If you're upgrading from an older version:

1. **Environment variables**: Old names still work but consider migrating to `AXI_` prefix
2. **Settings access**: `settings.AXI_METADATA_DIR` still works (backward compatible)
3. **Config loading**: `load_config()` now supports environment-specific files automatically

## Database Configuration

AXI supports two database backends for metadata storage:

### SQLite (Default - Embedded)

SQLite is the default database for local development and single-user deployments. It requires no setup and stores data in a single file.

**Configuration:**
- Default: No configuration needed
- Set `AXI_DB_TYPE=sqlite` (or leave unset)
- Database file: `{metadata_dir}/axi.db`

**Pros:**
- Zero configuration
- No separate service required
- Fast for single-user scenarios
- Perfect for local development

**Cons:**
- Limited concurrency
- Not suitable for production multi-user deployments

### PostgreSQL (Server - Production)

PostgreSQL is recommended for production deployments, multi-user scenarios, and when you need better performance and scalability.

**Configuration via Environment Variables:**
```bash
export AXI_DB_TYPE=postgres
export AXI_DB_HOST=localhost
export AXI_DB_PORT=5432
export AXI_DB_NAME=axi
export AXI_DB_USER=axi
export AXI_DB_PASSWORD=your_password
```

**Or via Connection URL:**
```bash
export AXI_DB_TYPE=postgres
export AXI_DB_URL=postgresql://user:password@host:port/database
```

**Configuration via YAML (axi.yml):**
```yaml
database:
  db_type: postgres
  db_host: localhost
  db_port: 5432
  db_name: axi
  db_user: axi
  db_password: "env:POSTGRES_PASSWORD"  # Use env: syntax for secrets
```

**Pros:**
- Better concurrency and performance
- Connection pooling
- Native JSONB support
- Suitable for production
- Multi-user support

**Cons:**
- Requires PostgreSQL server
- More setup complexity

### Docker Setup with PostgreSQL

The `docker/compose.yaml` includes a PostgreSQL service. To use it:

1. **Uncomment PostgreSQL environment variables in docker/compose.yaml:**
```yaml
environment:
  - AXI_DB_TYPE=postgres
  - AXI_DB_HOST=postgres
  - AXI_DB_PORT=5432
  - AXI_DB_NAME=axi
  - AXI_DB_USER=axi
  - AXI_DB_PASSWORD=axi_dev_password
```

2. **Start services:**
```bash
docker-compose up -d
```

The PostgreSQL database will be automatically initialized with the AXI schema.

### Migration from SQLite to PostgreSQL

1. Export data from SQLite (if needed)
2. Configure PostgreSQL connection
3. Re-run metadata extraction to populate PostgreSQL
4. Verify data integrity

**Note:** AXI will automatically create the schema in PostgreSQL on first use.

## Troubleshooting

### Configuration not loading

1. Check that `.env` files are in the project root
2. Verify environment variable names use `AXI_` prefix
3. Check logs for validation errors

### Secrets not working

1. Verify environment variables are set: `echo $SNOWFLAKE_PASSWORD`
2. Check `.env` file format (no spaces around `=`)
3. Ensure `env:VAR_NAME` syntax is correct in YAML

### Environment-specific config not loading

1. Verify `AXI_ENV` is set correctly
2. Check that `axi.{env}.yml` file exists
3. Check file naming (case-sensitive)
