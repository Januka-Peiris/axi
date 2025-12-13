# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Sample data generator for AXI demos.
Creates a realistic e-commerce semantic layer without requiring external data.
"""

import os
import json
from pathlib import Path
from typing import Optional

SAMPLE_MODELS = {
    "orders": {
        "sql": """
-- axi: true
-- grain: order_id
SELECT
    order_id,
    customer_id,
    order_date,
    status,
    channel,
    region,
    amount,
    discount,
    tax,
    (amount - discount + tax) as total_amount,
    COUNT(*) as order_count,
    SUM(amount) as gross_revenue,
    SUM(amount - discount) as net_revenue
FROM raw.orders
GROUP BY 1,2,3,4,5,6,7,8,9
""",
        "description": "Order transactions with revenue metrics"
    },
    "customers": {
        "sql": """
-- axi: true
-- grain: customer_id
SELECT
    customer_id,
    customer_name,
    email,
    signup_date,
    country,
    segment,
    lifetime_value,
    COUNT(DISTINCT order_id) as total_orders,
    SUM(total_amount) as total_spent
FROM raw.customers c
LEFT JOIN raw.orders o ON c.customer_id = o.customer_id
GROUP BY 1,2,3,4,5,6,7
""",
        "description": "Customer master with aggregated order metrics"
    },
    "products": {
        "sql": """
-- axi: true
-- grain: product_id
SELECT
    product_id,
    product_name,
    category,
    subcategory,
    brand,
    unit_price,
    cost,
    (unit_price - cost) as margin,
    SUM(quantity) as units_sold,
    SUM(quantity * unit_price) as product_revenue
FROM raw.products p
LEFT JOIN raw.order_items oi ON p.product_id = oi.product_id
GROUP BY 1,2,3,4,5,6,7
""",
        "description": "Product catalog with sales metrics"
    },
    "order_items": {
        "sql": """
-- axi: true
-- grain: order_item_id
SELECT
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price,
    discount,
    (quantity * unit_price) as line_total,
    (quantity * unit_price - discount) as line_net
FROM raw.order_items
""",
        "description": "Order line items linking orders to products"
    },
    "daily_metrics": {
        "sql": """
-- axi: true
-- grain: date
SELECT
    DATE(order_date) as date,
    COUNT(DISTINCT order_id) as orders,
    COUNT(DISTINCT customer_id) as active_customers,
    SUM(total_amount) as daily_revenue,
    AVG(total_amount) as avg_order_value,
    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as completion_rate
FROM orders
GROUP BY 1
""",
        "description": "Daily aggregated business metrics"
    }
}

SAMPLE_RELATIONSHIPS = [
    {"parent": "customers", "child": "orders", "fk": "customer_id", "pk": "customer_id"},
    {"parent": "orders", "child": "order_items", "fk": "order_id", "pk": "order_id"},
    {"parent": "products", "child": "order_items", "fk": "product_id", "pk": "product_id"},
]

SAMPLE_GLOSSARY = {
    "revenue": {
        "term": "Revenue",
        "definition": "Total monetary value of completed sales transactions",
        "related_metrics": ["gross_revenue", "net_revenue", "daily_revenue"],
        "related_entities": ["orders", "customers"]
    },
    "customer": {
        "term": "Customer",
        "definition": "An individual or business that has made at least one purchase",
        "related_metrics": ["total_orders", "total_spent", "lifetime_value"],
        "related_entities": ["customers", "orders"]
    },
    "aov": {
        "term": "Average Order Value (AOV)",
        "definition": "Mean transaction value calculated as total revenue divided by number of orders",
        "related_metrics": ["avg_order_value"],
        "related_entities": ["orders"]
    }
}


def generate_sample_project(output_dir: str, force: bool = False) -> dict:
    """
    Generate a complete sample AXI project with models, config, and glossary.

    Args:
        output_dir: Directory to create the sample project in
        force: Overwrite existing files if True

    Returns:
        dict with generation statistics
    """
    output_path = Path(output_dir)
    models_dir = output_path / "models"
    glossary_dir = output_path / "glossary"

    stats = {"models": 0, "glossary": 0, "config": 0}

    # Create directories
    models_dir.mkdir(parents=True, exist_ok=True)
    glossary_dir.mkdir(parents=True, exist_ok=True)

    # Generate model SQL files
    for model_name, model_data in SAMPLE_MODELS.items():
        model_file = models_dir / f"{model_name}.sql"
        if model_file.exists() and not force:
            continue
        model_file.write_text(model_data["sql"].strip())
        stats["models"] += 1

    # Generate glossary files
    for term_key, term_data in SAMPLE_GLOSSARY.items():
        import yaml
        glossary_file = glossary_dir / f"{term_key}.yml"
        if glossary_file.exists() and not force:
            continue
        glossary_file.write_text(yaml.dump(term_data, default_flow_style=False))
        stats["glossary"] += 1

    # Generate axi.yml config
    config_file = output_path / "axi.yml"
    if not config_file.exists() or force:
        config_content = """project: sample_ecommerce

promotion:
  mode: auto
  include:
    folders: ["models/*"]
    tags: ["axi"]

settings:
  warehouse: snowflake
  preview_limit: 100
"""
        config_file.write_text(config_content)
        stats["config"] = 1

    return stats


def get_sample_metrics() -> list:
    """Return sample metrics for demo mode."""
    return [
        {"name": "gross_revenue", "type": "sum", "entity": "orders", "expression": "SUM(amount)"},
        {"name": "net_revenue", "type": "sum", "entity": "orders", "expression": "SUM(amount - discount)"},
        {"name": "order_count", "type": "count", "entity": "orders", "expression": "COUNT(DISTINCT order_id)"},
        {"name": "avg_order_value", "type": "average", "entity": "orders", "expression": "AVG(total_amount)"},
        {"name": "total_customers", "type": "count_distinct", "entity": "customers", "expression": "COUNT(DISTINCT customer_id)"},
        {"name": "units_sold", "type": "sum", "entity": "products", "expression": "SUM(quantity)"},
    ]


def get_sample_dimensions() -> list:
    """Return sample dimensions for demo mode."""
    return [
        {"name": "order_date", "entity": "orders", "type": "date"},
        {"name": "status", "entity": "orders", "type": "string"},
        {"name": "channel", "entity": "orders", "type": "string"},
        {"name": "region", "entity": "orders", "type": "string"},
        {"name": "country", "entity": "customers", "type": "string"},
        {"name": "segment", "entity": "customers", "type": "string"},
        {"name": "category", "entity": "products", "type": "string"},
        {"name": "brand", "entity": "products", "type": "string"},
    ]
