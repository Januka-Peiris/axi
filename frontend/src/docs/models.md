# Semantic Models

Models represent the tables and views in your data warehouse that AXI has mapped to the semantic layer.

<br>

---

## What is a Model?

A model is a logical representation of a data source that contains:

<br>

- **Dimensions** - Columns you can group or filter by
<br>

- **Metrics** - Aggregate calculations
<br>

- **Relationships** - Connections to other models
<br>

- **Entity** - The primary key and grain

<br>

---

## Model Types

<br>

| Type | Description | Example |
|------|-------------|---------|
| `fact` | Transactional data with metrics | `fct_orders`, `fct_events` |
| `dimension` | Descriptive attributes | `dim_customers`, `dim_products` |
| `mart` | Pre-aggregated analytics | `mart_sales_summary` |
| `staging` | Raw data (typically not promoted) | `stg_raw_orders` |

<br>

---

## Model Definition

Models are automatically extracted from SQL or defined in YAML:

```yaml
models:
  - name: orders
    type: fact
    source: analytics.marts.fct_orders
    primary_key: order_id
    dimensions:
      - order_date
      - customer_id
      - status
      - region
    metrics:
      - total_amount
      - quantity
    relationships:
      - target: customers
        type: many_to_one
        join_key: customer_id
```

<br>

---

## Relationships

Relationships define how models connect, enabling automatic joins.

<br>

### Relationship Types

<br>

| Type | Description |
|------|-------------|
| `one_to_one` | Each record matches exactly one |
| `one_to_many` | One parent, many children |
| `many_to_one` | Many children, one parent |
| `many_to_many` | Complex relationship (via bridge) |

<br>

### Example

```yaml
relationships:
  - parent_model: customers
    child_model: orders
    join_key: customer_id
    type: one_to_many
```

<br>

When you query `revenue` by `customer_name`, AXI automatically:

<br>

1. Finds the path: `orders` → `customers`
<br>

2. Generates the JOIN: `orders JOIN customers ON customer_id`
<br>

3. Includes the dimension in GROUP BY

<br>

---

## Viewing Models

<br>

### In the UI

<br>

- Browse models at [/models](/models)
<br>

- Click a model to see its dimensions, metrics, and relationships
<br>

- View the entity graph at [/graph](/graph)

<br>

### Via CLI

```bash
# List all models
axi models list

# Describe a model
axi models describe orders
```

<br>

### Via API

```bash
# List models
GET /api/models

# Get specific model
GET /api/models/orders

# Get model with details
GET /api/entities/orders
```

<br>

---

## Best Practices

<br>

1. **Use clear naming** - `fct_orders` not `orders_table_v2`
<br>

2. **Define primary keys** - Essential for relationship building
<br>

3. **Document relationships** - Enable cross-model queries
<br>

4. **Set appropriate types** - Helps with semantic understanding
