# Metrics Framework

Metrics are declared in YAML and indexed into the metadata store. AXI surfaces them through the UI, API, and CLI.

## Anatomy

```yaml
metric: revenue
entity: orders
type: sum            # e.g. sum, count, avg, ratio
expression: "SUM(amount)"
dimensions: [date, market]
tags: ["finance"]
grain: ["date"]      # optional effective grain
```

- **entity**: links the metric to an entity/model for joins.
- **dimensions**: optional defaults used in generated SQL.
- **tags**: used for search and filtering in the UI/CLI.
- **grain**: stored as JSON in the SQLite metadata; used to block incompatible metric mixes.

## Working with metrics (CLI)

- List indexed metrics: `axi metrics list`
- Describe a metric: `axi metrics describe <metric_name>`
- Generate SQL (with time intelligence options):  
  `axi metrics sql <metric> --dims region,date --compare previous_period --window rolling_7d`
- Dependency view: `axi metrics deps <metric>`

## CRUD via API/UI

- UI provides browsing, builder, and validation errors from the backend validator.
- API routes: `GET /api/metrics`, `GET /api/metrics/{id|name}`, `POST/PUT /api/metrics/{name}` (builder uses the same endpoints).

## Best practices

- Keep expressions warehouse-agnostic where possible.
- Set default dimensions for common slicing.
- Tag metrics by domain/owner for easier discovery.
- Define grains to avoid incompatible multi-metric queries.
