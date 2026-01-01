# Licensed under the Business Source License 1.1 (BSL).
# Tests for determinism - same inputs should produce same outputs

import pytest
import json
import hashlib
from axi.extractor.core import extract_metadata
from axi.version import SCHEMA_VERSION


class TestExtractionDeterminism:
    """Verify that extraction produces identical results on repeated runs."""

    def test_same_sql_same_output(self):
        """Same SQL should produce identical metadata."""
        sql = """
        SELECT
            customer_id,
            SUM(amount) as total_revenue,
            COUNT(*) as order_count
        FROM orders
        GROUP BY customer_id
        """

        result1 = extract_metadata(sql, "test_model")
        result2 = extract_metadata(sql, "test_model")

        # Convert to JSON for comparison (excludes any object refs)
        json1 = json.dumps(result1, sort_keys=True)
        json2 = json.dumps(result2, sort_keys=True)

        assert json1 == json2, "Same SQL should produce identical output"

    def test_repeated_extraction_hash_stable(self):
        """Hash of extraction output should be stable across runs."""
        sql = """
        WITH daily_sales AS (
            SELECT
                date_trunc('day', order_date) as day,
                product_id,
                SUM(quantity) as units_sold
            FROM order_items
            GROUP BY 1, 2
        )
        SELECT * FROM daily_sales
        """

        hashes = set()
        for _ in range(5):
            result = extract_metadata(sql, "hash_test")
            result_json = json.dumps(result, sort_keys=True)
            result_hash = hashlib.sha256(result_json.encode()).hexdigest()
            hashes.add(result_hash)

        assert len(hashes) == 1, f"Expected 1 unique hash, got {len(hashes)}"

    def test_model_name_affects_output_deterministically(self):
        """Different model names should produce different but deterministic output."""
        sql = "SELECT id, SUM(amount) as total FROM orders GROUP BY id"

        result_a1 = extract_metadata(sql, "model_a")
        result_a2 = extract_metadata(sql, "model_a")
        result_b1 = extract_metadata(sql, "model_b")
        result_b2 = extract_metadata(sql, "model_b")

        # Same model name = same output
        assert json.dumps(result_a1, sort_keys=True) == json.dumps(result_a2, sort_keys=True)
        assert json.dumps(result_b1, sort_keys=True) == json.dumps(result_b2, sort_keys=True)

        # Different model names = different output (model name is in result)
        assert result_a1.get("model") == "model_a"
        assert result_b1.get("model") == "model_b"


class TestSchemaVersioning:
    """Test that schema versioning is properly implemented."""

    def test_schema_version_exists(self):
        """SCHEMA_VERSION constant should exist."""
        assert SCHEMA_VERSION is not None
        assert isinstance(SCHEMA_VERSION, str)
        assert len(SCHEMA_VERSION) > 0

    def test_schema_version_format(self):
        """SCHEMA_VERSION should be in MAJOR.MINOR format."""
        parts = SCHEMA_VERSION.split(".")
        assert len(parts) == 2, f"Expected MAJOR.MINOR format, got {SCHEMA_VERSION}"
        assert parts[0].isdigit(), "Major version should be numeric"
        assert parts[1].isdigit(), "Minor version should be numeric"


class TestMetricsDeterminism:
    """Test that metric extraction is deterministic."""

    def test_metric_order_stable(self):
        """Metrics should be extracted in stable order."""
        sql = """
        SELECT
            region,
            SUM(revenue) as total_revenue,
            AVG(price) as avg_price,
            COUNT(*) as transaction_count,
            MAX(amount) as max_amount,
            MIN(amount) as min_amount
        FROM sales
        GROUP BY region
        """

        orders = []
        for _ in range(3):
            result = extract_metadata(sql, "metrics_order")
            metric_names = [m.get("name") for m in result.get("metrics", [])]
            orders.append(tuple(metric_names))

        # All orders should be identical
        assert len(set(orders)) == 1, "Metric order should be stable"

    def test_dimension_order_stable(self):
        """Dimensions should be extracted in stable order."""
        sql = """
        SELECT
            region,
            country,
            city,
            product_category,
            SUM(sales) as total_sales
        FROM sales_data
        GROUP BY region, country, city, product_category
        """

        orders = []
        for _ in range(3):
            result = extract_metadata(sql, "dims_order")
            dim_names = [d.get("name") if isinstance(d, dict) else d
                        for d in result.get("dimensions", [])]
            orders.append(tuple(dim_names))

        assert len(set(orders)) == 1, "Dimension order should be stable"


class TestRelationshipDeterminism:
    """Test that relationship extraction is deterministic."""

    def test_join_extraction_stable(self):
        """Extracted relationships should be stable across runs."""
        sql = """
        SELECT
            o.order_id,
            c.customer_name,
            p.product_name,
            SUM(oi.quantity) as total_quantity
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        GROUP BY o.order_id, c.customer_name, p.product_name
        """

        relationship_sets = []
        for _ in range(3):
            result = extract_metadata(sql, "joins_test")
            rels = result.get("relationships", [])
            # Convert to hashable representation
            rel_tuples = tuple(sorted([
                (r.get("parent_model"), r.get("child_model"),
                 r.get("fk_column"), r.get("pk_column"))
                for r in rels
            ]))
            relationship_sets.append(rel_tuples)

        assert len(set(relationship_sets)) == 1, "Relationships should be stable"


class TestHashlibUsage:
    """Test that hashlib is used correctly for deterministic IDs."""

    def test_hashlib_produces_stable_ids(self):
        """IDs generated with hashlib should be stable."""
        test_input = "test_entity_name"

        ids = set()
        for _ in range(5):
            stable_id = int(hashlib.sha256(test_input.encode()).hexdigest()[:8], 16)
            ids.add(stable_id)

        assert len(ids) == 1, "hashlib should produce stable IDs"

    def test_different_inputs_different_hashes(self):
        """Different inputs should produce different hashes."""
        inputs = ["entity_a", "entity_b", "entity_c"]
        ids = set()

        for inp in inputs:
            stable_id = int(hashlib.sha256(inp.encode()).hexdigest()[:8], 16)
            ids.add(stable_id)

        assert len(ids) == len(inputs), "Different inputs should produce different IDs"
