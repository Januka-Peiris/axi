# AXI Helm Charts

This directory contains Helm charts for deploying AXI applications to Kubernetes.

## Available Charts

### axi-oss

The open-source AXI semantic layer and metrics API.

**Features:**
- Single-tenant deployment
- SQLite or PostgreSQL storage
- Snowflake integration
- Frontend UI

**Quick Start:**

```bash
# Add Bitnami repo for dependencies
helm repo add bitnami https://charts.bitnami.com/bitnami

# Update dependencies
cd axi-oss
helm dependency update

# Install with default values (SQLite storage)
helm install axi ./axi-oss

# Install with PostgreSQL storage
helm install axi ./axi-oss \
  --set config.storage=postgres \
  --set postgresql.enabled=true

# Install with production values
helm install axi ./axi-oss -f axi-oss/values-production.yaml
```

### axi-cloud

The multi-tenant AXI Cloud platform.

**Features:**
- Multi-tenant architecture
- API token management
- Scheduled query execution (Celery)
- Rate limiting (Redis)
- Credential encryption

**Quick Start:**

```bash
# Add Bitnami repo for dependencies
helm repo add bitnami https://charts.bitnami.com/bitnami

# Update dependencies
cd axi-cloud
helm dependency update

# Create secrets first
kubectl create secret generic axi-cloud-secrets \
  --from-literal=secret-key=$(python -c "import secrets; print(secrets.token_urlsafe(32))") \
  --from-literal=encryption-key=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Install
helm install axi-cloud ./axi-cloud \
  --set secrets.existingSecret=axi-cloud-secrets

# Install with production values
helm install axi-cloud ./axi-cloud -f axi-cloud/values-production.yaml
```

## Configuration

### Common Configuration Options

| Parameter | Description | Default |
|-----------|-------------|---------|
| `api.replicaCount` | Number of API replicas | `1` (OSS) / `2` (Cloud) |
| `api.image.repository` | API image repository | varies |
| `api.image.tag` | API image tag | Chart appVersion |
| `frontend.enabled` | Enable frontend | `true` |
| `ingress.enabled` | Enable ingress | `false` |
| `persistence.enabled` | Enable persistent storage | `true` |

### Snowflake Configuration (OSS)

```yaml
config:
  snowflake:
    account: "your-account"
    user: "your-user"
    warehouse: "COMPUTE_WH"
    database: "YOUR_DB"
    schema: "PUBLIC"

secrets:
  snowflakePassword: "your-password"
  # Or use key-pair auth:
  # snowflakePrivateKey: |
  #   -----BEGIN PRIVATE KEY-----
  #   ...
  #   -----END PRIVATE KEY-----
```

### External Database (Cloud)

```yaml
postgresql:
  enabled: false

externalPostgresql:
  host: "your-db-host.rds.amazonaws.com"
  port: 5432
  username: axi_cloud
  database: axi_cloud
  existingSecret: my-db-secret
```

### External Redis (Cloud)

```yaml
redis:
  enabled: false

externalRedis:
  host: "your-redis.elasticache.amazonaws.com"
  port: 6379
  existingSecret: my-redis-secret
```

## Upgrading

```bash
# Upgrade with new values
helm upgrade axi-cloud ./axi-cloud -f values-production.yaml

# Rollback if needed
helm rollback axi-cloud 1
```

## Uninstalling

```bash
# Uninstall release
helm uninstall axi-cloud

# Delete PVCs if needed (WARNING: deletes data)
kubectl delete pvc -l app.kubernetes.io/instance=axi-cloud
```

## Troubleshooting

### Check pod status
```bash
kubectl get pods -l app.kubernetes.io/instance=axi-cloud
```

### View logs
```bash
kubectl logs -l app.kubernetes.io/component=api -f
```

### Check migrations
```bash
kubectl logs -l app.kubernetes.io/component=migrations
```

### Verify database connection
```bash
kubectl exec -it deploy/axi-cloud-api -- python -c "from axi_cloud.storage.database import engine; print(engine.execute('SELECT 1').fetchone())"
```
