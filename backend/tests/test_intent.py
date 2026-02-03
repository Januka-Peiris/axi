# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Tests for Semantic Intent (Pydantic models, schema, builder)."""

import json
import os
import tempfile
import unittest

from axi.intent.models import (
    SemanticIntent,
    Measure,
    TimeDimension,
    JoinStep,
    SimpleFilter,
    AndFilter,
    OrFilter,
)
from axi.intent.schema import get_intent_json_schema
from axi.intent.builder import build_intent_from_metric
from axi.metadata.indexer import MetadataIndexer


class TestSemanticIntentModels(unittest.TestCase):
    """Test Semantic Intent Pydantic models: serialization, validation, determinism."""

    def test_simple_intent_roundtrip(self):
        intent = SemanticIntent(
            metric_name="mrr",
            metric_version="1.0",
            base_entity="orders",
            grain=[],
            measures=[Measure(name="mrr", column_ref="orders.amount", aggregation="sum")],
            dimensions=["region"],
            filters=[SimpleFilter(type="simple", dimension="status", op="=", value="active")],
            join_path=[
                JoinStep(
                    from_entity="orders",
                    to_entity="customers",
                    from_column="customer_id",
                    to_column="id",
                    join_type="left",
                )
            ],
        )
        js = intent.model_dump_json()
        parsed = SemanticIntent.model_validate_json(js)
        self.assertEqual(parsed.metric_name, intent.metric_name)
        self.assertEqual(len(parsed.join_path), 1)
        self.assertEqual(parsed.join_path[0].to_entity, "customers")

    def test_intent_no_raw_sql(self):
        intent = SemanticIntent(
            metric_name="x",
            metric_version="1.0",
            base_entity="t",
            measures=[Measure(name="x", column_ref="t.col", aggregation="sum")],
        )
        d = intent.model_dump()
        js = json.dumps(d)
        self.assertNotIn("SELECT", js)
        self.assertNotIn("FROM", js)

    def test_filters_composable(self):
        f1 = SimpleFilter(type="simple", dimension="a", op="=", value=1)
        f2 = SimpleFilter(type="simple", dimension="b", op="!=", value=2)
        and_f = AndFilter(type="and", clauses=[f1, f2])
        intent = SemanticIntent(
            metric_name="m",
            metric_version="1.0",
            base_entity="e",
            measures=[Measure(name="m", column_ref="e.x", aggregation="sum")],
            filters=[and_f],
        )
        js = intent.model_dump_json()
        parsed = SemanticIntent.model_validate_json(js)
        self.assertEqual(parsed.filters[0].type, "and")
        self.assertEqual(len(parsed.filters[0].clauses), 2)

    def test_dimensions_sorted_deterministic(self):
        intent = SemanticIntent(
            metric_name="m",
            metric_version="1.0",
            base_entity="e",
            measures=[Measure(name="m", column_ref="e.x", aggregation="sum")],
            dimensions=["z", "a", "m"],
        )
        self.assertEqual(intent.dimensions, ["a", "m", "z"])

    def test_measures_sorted_deterministic(self):
        intent = SemanticIntent(
            metric_name="m",
            metric_version="1.0",
            base_entity="e",
            measures=[
                Measure(name="b", column_ref="e.y", aggregation="count"),
                Measure(name="a", column_ref="e.x", aggregation="sum"),
            ],
        )
        names = [m.name for m in intent.measures]
        self.assertEqual(names, ["a", "b"])


class TestIntentJsonSchema(unittest.TestCase):
    """Test JSON schema export."""

    def test_schema_has_semantic_intent(self):
        schema = get_intent_json_schema()
        self.assertIn("SemanticIntent", str(schema))
        self.assertIn("metric_name", str(schema))
        self.assertIn("join_path", str(schema))

    def test_schema_no_raw_sql(self):
        schema = get_intent_json_schema()
        js = json.dumps(schema)
        self.assertNotIn("SELECT", js)
        self.assertNotIn("FROM", js)


class TestIntentBuilder(unittest.TestCase):
    """Test building SemanticIntent from AXI metadata."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.models_dir = os.path.join(self.temp_dir, "models")
        os.makedirs(self.models_dir, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_model_json(self, name: str, data: dict):
        path = os.path.join(self.models_dir, f"{name}.json")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def test_build_from_single_table_model(self):
        self._write_model_json("orders", {
            "model": "orders",
            "metrics": [
                {
                    "name": "order_count",
                    "expression": "COUNT(*)",
                    "aggregation": "count",
                    "grain": [],
                    "metric_type": "aggregate",
                }
            ],
            "dimensions": ["id", "status"],
            "filters": [],
            "source_tables": ["raw_orders"],
            "entity": {"name": "orders", "pk": "id", "columns": ["id", "status"]},
            "relationships": [],
        })
        indexer = MetadataIndexer(self.temp_dir)
        indexer.build_index()
        intent = build_intent_from_metric(indexer, "order_count")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.metric_name, "order_count")
        self.assertEqual(intent.base_entity, "orders")
        self.assertEqual(len(intent.measures), 1)
        self.assertEqual(intent.measures[0].aggregation, "count")
        self.assertEqual(intent.join_path, [])

    def test_build_from_multi_table_model_resolves_join_path(self):
        self._write_model_json("revenue", {
            "model": "revenue",
            "metrics": [
                {
                    "name": "mrr",
                    "expression": "SUM(o.amount)",
                    "aggregation": "sum",
                    "grain": [],
                    "metric_type": "aggregate",
                }
            ],
            "dimensions": ["c.region"],
            "filters": ["o.status = 'active'"],
            "source_tables": ["orders", "customers"],
            "entity": {"name": "revenue", "pk": None, "columns": ["region", "mrr"]},
            "relationships": [
                {
                    "parent_model": "customers",
                    "child_model": "orders",
                    "fk_column": "customer_id",
                    "pk_column": "id",
                    "join_type": "inner",
                }
            ],
        })
        indexer = MetadataIndexer(self.temp_dir)
        indexer.build_index()
        intent = build_intent_from_metric(indexer, "mrr")
        self.assertIsNotNone(intent)
        self.assertEqual(intent.metric_name, "mrr")
        self.assertEqual(len(intent.join_path), 1)
        self.assertEqual(intent.join_path[0].from_entity, "orders")
        self.assertEqual(intent.join_path[0].to_entity, "customers")
        self.assertEqual(len(intent.filters), 1)
        self.assertEqual(intent.filters[0].dimension, "o.status")
        self.assertEqual(intent.filters[0].value, "active")


if __name__ == "__main__":
    unittest.main()
