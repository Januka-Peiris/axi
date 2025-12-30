# Business Glossary

The AXI glossary provides a searchable index of business terms, connecting them to the underlying semantic layer.

<br>

---

## What's in the Glossary

The glossary automatically includes:

<br>

- **Entities** - Business objects (Customer, Order, Product)
<br>

- **Metrics** - Calculations (Revenue, MRR, Conversion Rate)
<br>

- **Dimensions** - Slicing attributes (Region, Date, Category)
<br>

- **Relationships** - How entities connect

<br>

---

## Using the Glossary

<br>

### In the UI

<br>

1. Navigate to [/glossary](/glossary)
<br>

2. Search by term, tag, or description
<br>

3. Click a term to see its definition and relationships
<br>

4. View linked metrics and dimensions

<br>

### Via CLI

```bash
# Generate glossary from extracted metadata
axi glossary generate

# Search for terms
axi glossary search "revenue"
axi glossary search "customer"
```

<br>

### Via API

```bash
# Search glossary
GET /api/glossary?q=revenue

# Get specific term
GET /api/glossary/terms/revenue
```

<br>

---

## Adding Custom Terms

<br>

### Glossary YAML Files

Create terms in `glossary/` directory:

```yaml
# glossary/revenue.yml
term: revenue
definition: >
  Total money received from sales of goods and services,
  before any deductions for costs or expenses.
related_metrics:
  - total_revenue
  - monthly_revenue
related_entities:
  - orders
  - invoices
tags:
  - finance
  - executive
owner: finance-team
```

<br>

### Overrides

Customize extracted terms in `overrides/`:

```yaml
# overrides/entities.yml
orders:
  display_name: "Sales Orders"
  description: "Customer purchase transactions"
  owner: sales-ops
```

<br>

---

## Glossary Structure

<br>

| Field | Description |
|-------|-------------|
| `term` | The business term name |
| `definition` | Plain-language explanation |
| `related_metrics` | Linked metric names |
| `related_entities` | Linked entity names |
| `tags` | Categories for filtering |
| `owner` | Team or person responsible |

<br>

---

## Best Practices

<br>

1. **Write for humans** - Definitions should be understandable by non-technical users
<br>

2. **Link related terms** - Help users discover connected concepts
<br>

3. **Add owners** - Make it clear who to ask for questions
<br>

4. **Use tags consistently** - Enable filtering by domain (finance, marketing, ops)
<br>

5. **Keep it current** - Update when metrics or definitions change
