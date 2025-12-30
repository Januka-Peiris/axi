# Saved Queries

Saved queries let you define reusable semantic queries that can be version-controlled and shared across your team.

<br>

---

## What is a Saved Query?

A saved query captures:

<br>

- Which metrics to calculate
<br>

- Which dimensions to group by
<br>

- What filters to apply
<br>

- Result limits

<br>

Once saved, anyone can run the same query with consistent results.

<br>

---

## Creating Saved Queries

<br>

### In the UI

<br>

1. Build your query in the [Query Explorer](/query)
<br>

2. Click "Save Query"
<br>

3. Give it a name and description
<br>

4. The query is saved and available in [/saved-queries](/saved-queries)

<br>

### Via YAML

Create files in `axi/queries/` directory:

```yaml
# axi/queries/monthly_revenue_uk.yml
id: monthly_revenue_uk
name: Monthly Revenue (UK)
description: Total revenue per month for UK customers
entity: orders
metrics:
  - total_revenue
dimensions:
  - month
filters:
  - dimension: country
    op: "="
    value: "UK"
limit: 500
tags:
  - finance
  - executive
```

<br>

---

## Query Structure

<br>

| Field | Description | Required |
|-------|-------------|----------|
| `id` | Unique identifier (matches filename) | Yes |
| `name` | Display name | Yes |
| `entity` | Base entity for the query | Yes |
| `metrics` | List of metric names | Yes |
| `dimensions` | List of dimension names | No |
| `filters` | Filter conditions | No |
| `limit` | Max rows to return | No |
| `tags` | Categories for filtering | No |
| `description` | What this query shows | No |

<br>

---

## Running Saved Queries

<br>

### In the UI

<br>

1. Go to [/saved-queries](/saved-queries)
<br>

2. Find your query
<br>

3. Click "Run" to execute
<br>

4. View results in the Query Explorer

<br>

### Via API

```bash
# Run a saved query
POST /api/saved_queries/monthly_revenue_uk/run

# Run with overrides
POST /api/saved_queries/monthly_revenue_uk/run
Content-Type: application/json

{
  "override_filters": [
    {"dimension": "country", "op": "=", "value": "US"}
  ],
  "override_limit": 100
}
```

<br>

### Via CLI

```bash
# List saved queries
axi queries list

# Run a saved query
axi queries run monthly_revenue_uk
```

<br>

---

## API Reference

<br>

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/saved_queries` | GET | List all saved queries |
| `/api/saved_queries` | POST | Create a new query |
| `/api/saved_queries/{id}` | GET | Get query details |
| `/api/saved_queries/{id}` | DELETE | Delete a query |
| `/api/saved_queries/{id}/run` | POST | Execute the query |

<br>

---

## Filter Operators

<br>

| Operator | Description | Example |
|----------|-------------|---------|
| `=` | Equals | `country = 'US'` |
| `!=` | Not equals | `status != 'cancelled'` |
| `>` | Greater than | `amount > 100` |
| `<` | Less than | `quantity < 10` |
| `>=` | Greater or equal | `date >= '2024-01-01'` |
| `<=` | Less or equal | `score <= 50` |
| `in` | In list | `region in ('US', 'UK')` |
| `like` | Pattern match | `name like '%corp%'` |

<br>

---

## Best Practices

<br>

1. **Use descriptive names** - `monthly_revenue_by_region` not `query1`
<br>

2. **Add descriptions** - Help others understand what the query shows
<br>

3. **Tag appropriately** - Enable filtering by domain
<br>

4. **Version control** - Keep YAML files in git
<br>

5. **Use overrides** - Don't duplicate queries for minor filter changes
