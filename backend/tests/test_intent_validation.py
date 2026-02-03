# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Unit tests for compile-time intent validation (grain, joins, dimensions, filters, time)."""

import unittest

from axi.exceptions import ValidationError
from axi.intent.models import (
    SemanticIntent,
    Measure,
    TimeDimension,
    JoinStep,
    SimpleFilter,
)
from axi.intent.validation import validate_intent_for_compilation
from axi.intent.compiler import compile_metric


def _minimal_intent(**overrides) -> SemanticIntent:
    base = {
        "metric_name": "test_metric",
        "metric_version": "1.0",
        "base_entity": "orders",
        "grain": [],
        "measures": [Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        "dimensions": [],
        "filters": [],
        "join_path": [],
    }
    base.update(overrides)
    return SemanticIntent(**base)


class TestGrainIncompatibleWithJoinTarget(unittest.TestCase):
    """Fail when grain column does not belong to base entity or join path."""

    def test_grain_references_unknown_entity(self):
        intent = _minimal_intent(
            grain=["unknown_entity.id"],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "GRAIN_INCOMPATIBLE_WITH_JOIN_TARGET")
        self.assertIn("test_metric", ctx.exception.message)
        self.assertIn("1.0", ctx.exception.message)
        self.assertIn("unknown_entity.id", ctx.exception.message)
        self.assertIn("offending_entity_or_dimension", ctx.exception.context)

    def test_grain_on_path_passes(self):
        intent = _minimal_intent(
            grain=["orders.id"],
            join_path=[JoinStep(from_entity="orders", to_entity="customers", from_column="customer_id", to_column="id")],
        )
        validate_intent_for_compilation(intent)

    def test_compile_metric_raises_on_invalid_grain(self):
        intent = _minimal_intent(grain=["other_table.other_col"])
        with self.assertRaises(ValidationError):
            compile_metric(intent, warehouse="snowflake")


class TestJoinsIntroduceFanout(unittest.TestCase):
    """Fail when join path does not form a chain or duplicates join target."""

    def test_first_join_not_from_base_entity(self):
        intent = _minimal_intent(
            base_entity="orders",
            join_path=[
                JoinStep(from_entity="customers", to_entity="orders", from_column="id", to_column="customer_id"),
            ],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "GRAIN_INCOMPATIBLE_WITH_JOIN_TARGET")
        self.assertIn("first join", ctx.exception.message.lower())

    def test_second_join_from_entity_not_in_chain(self):
        intent = _minimal_intent(
            base_entity="orders",
            join_path=[
                JoinStep(from_entity="orders", to_entity="customers", from_column="customer_id", to_column="id"),
                JoinStep(from_entity="products", to_entity="line_items", from_column="id", to_column="product_id"),
            ],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "JOINS_INTRODUCE_FANOUT")
        self.assertIn("test_metric", ctx.exception.message)
        self.assertIn("offending_join", ctx.exception.context)

    def test_duplicate_join_target_raises(self):
        intent = _minimal_intent(
            base_entity="orders",
            join_path=[
                JoinStep(from_entity="orders", to_entity="customers", from_column="customer_id", to_column="id"),
                JoinStep(from_entity="customers", to_entity="customers", from_column="id", to_column="id"),
            ],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "JOINS_INTRODUCE_FANOUT")
        self.assertIn("duplicate", ctx.exception.message.lower())

    def test_chain_join_path_passes(self):
        intent = _minimal_intent(
            base_entity="orders",
            join_path=[
                JoinStep(from_entity="orders", to_entity="customers", from_column="customer_id", to_column="id"),
                JoinStep(from_entity="customers", to_entity="regions", from_column="region_id", to_column="id"),
            ],
        )
        validate_intent_for_compilation(intent)


class TestDimensionNotOnPath(unittest.TestCase):
    """Fail when dimension does not belong to base entity or resolved join path."""

    def test_dimension_unknown_entity(self):
        intent = _minimal_intent(
            dimensions=["other_entity.other_col"],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "DIMENSION_NOT_ON_PATH")
        self.assertIn("test_metric", ctx.exception.message)
        self.assertIn("offending_entity_or_dimension", ctx.exception.context)

    def test_dimension_on_base_entity_passes(self):
        intent = _minimal_intent(dimensions=["orders.status"])
        validate_intent_for_compilation(intent)

    def test_dimension_on_join_path_passes(self):
        intent = _minimal_intent(
            dimensions=["c.region"],
            join_path=[JoinStep(from_entity="orders", to_entity="customers", from_column="customer_id", to_column="id")],
        )
        validate_intent_for_compilation(intent)


class TestFilterFieldUnresolvable(unittest.TestCase):
    """Fail when filter references unknown or unresolvable field."""

    def test_filter_unknown_entity(self):
        intent = _minimal_intent(
            filters=[SimpleFilter(type="simple", dimension="other_entity.col", op="=", value="x")],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "FILTER_FIELD_UNRESOLVABLE")
        self.assertIn("test_metric", ctx.exception.message)
        self.assertIn("offending_entity_or_dimension", ctx.exception.context)

    def test_filter_on_path_passes(self):
        intent = _minimal_intent(
            filters=[SimpleFilter(type="simple", dimension="orders.status", op="=", value="active")],
        )
        validate_intent_for_compilation(intent)


class TestTimeDimensionIncompatibleWithGrain(unittest.TestCase):
    """Fail when time dimension column_ref does not belong to path."""

    def test_time_dimension_unknown_entity(self):
        intent = _minimal_intent(
            time_dimension=TimeDimension(name="month", column_ref="other_entity.created_at", granularity="month"),
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "TIME_DIMENSION_INCOMPATIBLE_WITH_GRAIN")
        self.assertIn("test_metric", ctx.exception.message)
        self.assertIn("offending_entity_or_dimension", ctx.exception.context)

    def test_time_dimension_on_path_passes(self):
        intent = _minimal_intent(
            time_dimension=TimeDimension(name="month", column_ref="orders.created_at", granularity="month"),
        )
        validate_intent_for_compilation(intent)


class TestMeasureColumnRefNotOnPath(unittest.TestCase):
    """Fail when measure column_ref does not belong to base or join path."""

    def test_measure_unknown_entity(self):
        intent = _minimal_intent(
            measures=[Measure(name="total", column_ref="other_entity.amount", aggregation="sum")],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "DIMENSION_NOT_ON_PATH")
        self.assertIn("test_metric", ctx.exception.message)

    def test_measure_star_skipped(self):
        intent = _minimal_intent(
            measures=[Measure(name="cnt", column_ref="*", aggregation="count")],
        )
        validate_intent_for_compilation(intent)


class TestValidationRunsBeforeSqlGeneration(unittest.TestCase):
    """Validation must occur before SQL generation; compile_metric fails on invalid intent."""

    def test_compile_metric_valid_intent_succeeds(self):
        intent = _minimal_intent()
        sql = compile_metric(intent, warehouse="snowflake")
        self.assertIn("axi.metric_name: test_metric", sql)
        self.assertIn("SELECT", sql)

    def test_compile_metric_invalid_dimension_fails_before_sql(self):
        intent = _minimal_intent(dimensions=["nonexistent.x"])
        with self.assertRaises(ValidationError) as ctx:
            compile_metric(intent, warehouse="snowflake")
        self.assertEqual(ctx.exception.code, "DIMENSION_NOT_ON_PATH")
        self.assertIn("test_metric", ctx.exception.message)
        self.assertIn("1.0", ctx.exception.message)


class TestExistingCompilationStillWorks(unittest.TestCase):
    """Ensure existing valid intents still compile (no weakening)."""

    def test_minimal_intent_compiles(self):
        intent = SemanticIntent(
            metric_name="test",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="total", column_ref="orders.amount", aggregation="sum")],
        )
        validate_intent_for_compilation(intent)
        sql = compile_metric(intent, warehouse="snowflake")
        self.assertIn("SUM(o.amount)", sql)

    def test_intent_with_dimensions_and_filters_compiles(self):
        intent = SemanticIntent(
            metric_name="mrr",
            metric_version="1.0",
            base_entity="orders",
            measures=[Measure(name="mrr", column_ref="o.amount", aggregation="sum")],
            dimensions=["c.region"],
            filters=[SimpleFilter(type="simple", dimension="o.status", op="=", value="active")],
            join_path=[
                JoinStep(from_entity="orders", to_entity="customers", from_column="customer_id", to_column="id"),
            ],
        )
        validate_intent_for_compilation(intent)
        sql = compile_metric(intent, warehouse="snowflake")
        self.assertIn("axi.metric_name: mrr", sql)
        self.assertIn("c.region", sql)
        self.assertIn("o.status", sql)


if __name__ == "__main__":
    unittest.main()
