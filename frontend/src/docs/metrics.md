# Metrics Framework

Metrics are the core of AXI's semantic layer. They represent business calculations that can be queried across different dimensions.

<br>

---

## Metric Types

<br>

| Type | Description | Example |
|------|-------------|---------|
| `sum` | Additive aggregation | `SUM(amount)` |
| `count` | Count of records | `COUNT(*)` |
| `count_distinct` | Unique count | `COUNT(DISTINCT customer_id)` |
| `avg` | Average value | `AVG(order_value)` |
| `min` / `max` | Extremes | `MAX(sale_date)` |
| `ratio` | Division of metrics | `revenue / orders` |

<br>

---

## Metric Definition

Metrics are extracted automatically from your SQL or defined in YAML:

```yaml
name: total_revenue
entity: orders
type: sum
expression: "SUM(amount)"
dimensions:
  - date
  - region
  - customer_segment
tags:
  - finance
  - executive
grain:
  - date
description: "Total revenue from completed orders"
```

<br>

### Key Properties

<br>

| Property | Description |
|----------|-------------|
| `entity` | Links the metric to a model for automatic joins |
| `expression` | The SQL aggregation formula |
| `dimensions` | Default dimensions for this metric |
| `grain` | Time grain for semi-additive handling |
| `tags` | Categories for search and filtering |

<br>

---

## Using Metrics

<br>

### In the UI

<br>

1. Browse metrics at [/metrics](/metrics)
<br>

2. Click a metric to see its definition and sample queries
<br>

3. Use the Query Explorer to combine metrics with dimensions

<br>

### Via CLI

```bash
# List all metrics
axi metrics list

# Get metric details
axi metrics describe revenue

# Generate SQL
axi metrics sql revenue --dims region,date

# With time intelligence
axi metrics sql revenue --dims date --compare previous_period
```

<br>

### Via API

```bash
# List metrics
GET /api/metrics

# Get specific metric
GET /api/metrics/revenue

# Generate SQL
GET /api/metrics/revenue/sql?dimensions=region,date
```

<br>

---

## Time Intelligence

AXI supports time-aware calculations:

<br>

| Option | Description |
|--------|-------------|
| `previous_period` | Compare to prior period |
| `year_over_year` | Compare to same period last year |
| `rolling_7d` | 7-day rolling average |
| `month_to_date` | Cumulative for current month |

<br>

Example:

```bash
axi metrics sql mrr --dims date --compare previous_period
```

<br>

---

## Best Practices

<br>

1. **Use clear names** - `total_revenue` not `rev1`
<br>

2. **Set default dimensions** - Common slices users will want
<br>

3. **Add tags** - Makes discovery easier
<br>

4. **Define grain** - Prevents incompatible metric combinations
<br>

5. **Write descriptions** - Help users understand what the metric measures
