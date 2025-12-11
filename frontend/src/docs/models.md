# Semantic Models

Models represent the physical tables or views in your data warehouse that have been mapped to AXI.

## Defining a Model

Models are defined in YAML files. AXI automatically scans your project and infers basic models, but you can enrich them.

```yaml
models:
  - name: orders
    type: table
    source: raw.prod.orders
    dimensions: 
      - created_at
      - status
    primary_key: id
```

## Relationships
Relationships define how models connect. AXI uses these to generate JOIN paths.
