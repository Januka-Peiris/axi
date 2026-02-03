# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Negative test suite: AXI MUST refuse invalid semantic input.

Test cases:
  1. Metric joins to lower-grain entity → fail (GRAIN_INCOMPATIBLE_WITH_JOIN_TARGET)
  2. Dimension not reachable via join path → fail (DIMENSION_NOT_ON_PATH)
  3. Fan-out join without aggregation → fail (JOINS_INTRODUCE_FANOUT)
  4. Time filter incompatible with metric grain → fail (TIME_DIMENSION / FILTER_FIELD_UNRESOLVABLE)
  5. Deprecated metric used in compile → warning (compiles; output contains deprecation)
  6. Disabled metric used in compile → fail (MetricDisabledError)

Requirements:
  - Tests assert on error message content.
  - No mocks of validation logic (real validate_intent_for_compilation / compile_metric).
  - Use real extracted AXI metadata where possible (_load_intent from metadata_store).
Failing-first: each test was written to expect a specific failure or warning (red before green).
"""

import json
import os
import unittest

from axi.exceptions import ValidationError, MetricDisabledError
from axi.intent.models import (
    SemanticIntent,
    Measure,
    TimeDimension,
    JoinStep,
    SimpleFilter,
)
from axi.intent.validation import validate_intent_for_compilation
from axi.intent.compiler import compile_metric


def _metadata_store_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "metadata_store")


def _load_intent(name: str) -> SemanticIntent:
    """Load intent from metadata_store/intents (real extracted AXI metadata)."""
    path = os.path.join(_metadata_store_path(), "intents", f"{name}_intent.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path) as f:
        return SemanticIntent.model_validate(json.load(f))


def _minimal_intent(**overrides) -> SemanticIntent:
    """Minimal valid intent for building invalid variants."""
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


# ---------------------------------------------------------------------------
# 1. Metric joins to lower-grain entity → fail
# ---------------------------------------------------------------------------
class TestMetricJoinsToLowerGrainEntity(unittest.TestCase):
    """When the first join does not start from base_entity, grain is incompatible."""

    def test_first_join_not_from_base_fails_with_grain_error(self):
        # Base is orders (fact grain); join from customers to orders is wrong direction
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
        self.assertIn("base entity", ctx.exception.message.lower())
        self.assertIn("orders", ctx.exception.message)
        self.assertIn("customers", ctx.exception.message)

    def test_compile_metric_refuses_join_to_lower_grain_entity(self):
        intent = _minimal_intent(
            base_entity="orders",
            join_path=[
                JoinStep(from_entity="customers", to_entity="orders", from_column="id", to_column="customer_id"),
            ],
        )
        with self.assertRaises(ValidationError) as ctx:
            compile_metric(intent, warehouse="snowflake")
        self.assertEqual(ctx.exception.code, "GRAIN_INCOMPATIBLE_WITH_JOIN_TARGET")
        self.assertIn("test_metric", ctx.exception.message)


# ---------------------------------------------------------------------------
# 2. Dimension not reachable via join path → fail
# ---------------------------------------------------------------------------
class TestDimensionNotReachableViaJoinPath(unittest.TestCase):
    """Dimension must belong to base entity or resolved join path."""

    def test_dimension_from_unknown_entity_fails(self):
        intent = _minimal_intent(
            dimensions=["unreachable_entity.region"],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "DIMENSION_NOT_ON_PATH")
        self.assertIn("dimension", ctx.exception.message.lower())
        self.assertIn("unreachable_entity.region", ctx.exception.message)
        self.assertIn("base entity", ctx.exception.message.lower() or "join path" in ctx.exception.message.lower())
        self.assertIn("test_metric", ctx.exception.message)

    def test_compile_metric_refuses_unreachable_dimension(self):
        intent = _minimal_intent(dimensions=["other_schema.other_col"])
        with self.assertRaises(ValidationError) as ctx:
            compile_metric(intent, warehouse="snowflake")
        self.assertEqual(ctx.exception.code, "DIMENSION_NOT_ON_PATH")
        self.assertIn("other_schema.other_col", ctx.exception.message)


# ---------------------------------------------------------------------------
# 3. Fan-out join without aggregation → fail
# ---------------------------------------------------------------------------
class TestFanOutJoinWithoutAggregation(unittest.TestCase):
    """Join path must form a chain; duplicate join target or broken chain introduces fan-out."""

    def test_duplicate_join_target_fails_with_fanout_error(self):
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
        self.assertIn("customers", ctx.exception.message)

    def test_second_join_from_entity_not_in_chain_fails(self):
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
        self.assertIn("fan-out", ctx.exception.message.lower() or "chain" in ctx.exception.message.lower())
        self.assertIn("products", ctx.exception.message)


# ---------------------------------------------------------------------------
# 4. Time filter incompatible with metric grain → fail
# ---------------------------------------------------------------------------
class TestTimeFilterIncompatibleWithMetricGrain(unittest.TestCase):
    """Time dimension column_ref must be on path; filter fields must be resolvable."""

    def test_time_dimension_column_ref_not_on_path_fails(self):
        intent = _minimal_intent(
            time_dimension=TimeDimension(
                name="month",
                column_ref="unknown_entity.created_at",
                granularity="month",
            ),
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "TIME_DIMENSION_INCOMPATIBLE_WITH_GRAIN")
        self.assertIn("time dimension", ctx.exception.message.lower())
        self.assertIn("unknown_entity.created_at", ctx.exception.message)
        self.assertIn("test_metric", ctx.exception.message)

    def test_filter_on_time_field_not_on_path_fails(self):
        intent = _minimal_intent(
            filters=[SimpleFilter(type="simple", dimension="other_entity.event_date", op=">=", value="2026-01-01")],
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(intent)
        self.assertEqual(ctx.exception.code, "FILTER_FIELD_UNRESOLVABLE")
        self.assertIn("filter", ctx.exception.message.lower())
        self.assertIn("other_entity.event_date", ctx.exception.message)


# ---------------------------------------------------------------------------
# 5. Deprecated metric used in compile → warning
# ---------------------------------------------------------------------------
class TestDeprecatedMetricUsedInCompile(unittest.TestCase):
    """Deprecated metric MUST compile successfully and emit explicit warning (replacement_metric)."""

    def test_deprecated_metric_compiles_with_warning_in_output(self):
        intent = _minimal_intent()
        sql = compile_metric(
            intent,
            warehouse="snowflake",
            status="deprecated",
            replacement_metric="new_metric",
        )
        self.assertIn("axi.lifecycle_status: deprecated", sql)
        self.assertIn("axi.deprecated: true", sql)
        self.assertIn("axi.replacement_metric: new_metric", sql)
        self.assertIn("SELECT", sql)

    def test_deprecated_metric_no_exception(self):
        intent = _minimal_intent(metric_name="legacy_mrr", metric_version="1.0")
        sql = compile_metric(
            intent,
            warehouse="snowflake",
            status="deprecated",
            replacement_metric="mrr_v2",
        )
        self.assertIn("axi.metric_name: legacy_mrr", sql)
        self.assertIn("axi.replacement_metric: mrr_v2", sql)


# ---------------------------------------------------------------------------
# 6. Disabled metric used in compile → fail
# ---------------------------------------------------------------------------
class TestDisabledMetricUsedInCompile(unittest.TestCase):
    """Disabled metric MUST fail compilation with structured error."""

    def test_disabled_metric_compile_fails_with_structured_error(self):
        intent = _minimal_intent(metric_name="retired_metric", metric_version="1.0")
        with self.assertRaises(MetricDisabledError) as ctx:
            compile_metric(intent, warehouse="snowflake", status="disabled")
        self.assertEqual(ctx.exception.code, "METRIC_DISABLED")
        self.assertIn("disabled", ctx.exception.message.lower())
        self.assertIn("retired_metric", ctx.exception.message)
        self.assertIn("cannot be compiled", ctx.exception.message.lower())

    def test_disabled_metric_context_contains_metric_name(self):
        intent = _minimal_intent(metric_name="x")
        with self.assertRaises(MetricDisabledError) as ctx:
            compile_metric(intent, warehouse="snowflake", status="disabled")
        self.assertIn("metric_name", ctx.exception.context)
        self.assertEqual(ctx.exception.context["metric_name"], "x")


# ---------------------------------------------------------------------------
# Real extracted metadata: invalid variant
# ---------------------------------------------------------------------------
class TestNegativeWithRealExtractedMetadata(unittest.TestCase):
    """Use real metadata_store intent when available; mutate to invalid and assert."""

    @unittest.skipUnless(
        os.path.isfile(os.path.join(_metadata_store_path(), "intents", "mrr_intent.json")),
        "metadata_store/intents/mrr_intent.json not found",
    )
    def test_mrr_intent_valid_then_dimension_not_on_path_fails(self):
        intent = _load_intent("mrr")
        validate_intent_for_compilation(intent)
        # Mutate to add dimension not on path (mrr has orders, customers; add unreachable)
        invalid = SemanticIntent(
            metric_name=intent.metric_name,
            metric_version=intent.metric_version,
            base_entity=intent.base_entity,
            grain=intent.grain,
            measures=intent.measures,
            dimensions=list(intent.dimensions) + ["unreachable_entity.x"],
            time_dimension=intent.time_dimension,
            filters=intent.filters,
            join_path=intent.join_path,
        )
        with self.assertRaises(ValidationError) as ctx:
            validate_intent_for_compilation(invalid)
        self.assertEqual(ctx.exception.code, "DIMENSION_NOT_ON_PATH")
        self.assertIn("unreachable_entity.x", ctx.exception.message)
        self.assertIn("mrr", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
