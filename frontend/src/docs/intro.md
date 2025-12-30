# Introduction to AXI

**AXI** is a semantic layer for the modern data stack. It transforms your SQL models into business-friendly concepts that anyone can understand and query.

<br>

---

## Core Concepts

<br>

### Entities

The **nouns** of your business - the things you measure and analyze.

Examples: `Customer`, `Order`, `Product`, `Subscription`

<br>

### Metrics

The **calculations** that drive decisions - aggregations with business meaning.

Examples: `Revenue`, `Active Users`, `Conversion Rate`, `MRR`

<br>

### Dimensions

The **context** for analysis - how you slice and filter your metrics.

Examples: `Region`, `Date`, `Product Category`, `Customer Segment`

<br>

### Relationships

The **connections** between entities that enable automatic joins.

Examples: `Order` belongs to `Customer`, `Product` belongs to `Category`

<br>

---

## What You Can Do

<br>

- **Explore Metrics** - Browse all available metrics with their definitions
<br>

- **Query Data** - Build semantic queries without writing SQL
<br>

- **View Lineage** - See how metrics connect to source data
<br>

- **Search Glossary** - Find business terms and their definitions

<br>

---

## Quick Links

<br>

- [Business Glossary](/glossary) - Search and browse terms
<br>

- [Query Explorer](/query) - Build and run semantic queries
<br>

- [Saved Queries](/saved-queries) - Reuse common queries
<br>

- [Metrics](/metrics) - Browse all metrics

<br>

---

## How It Works

<br>

1. **Extract** - AXI parses your SQL models to find metrics and dimensions
<br>

2. **Index** - Metadata is stored for fast querying and exploration
<br>

3. **Query** - Request metrics by name; AXI generates optimized SQL
<br>

4. **Execute** - Run queries directly against Snowflake

<br>

---

> AXI handles all the SQL generation and joins automatically.
