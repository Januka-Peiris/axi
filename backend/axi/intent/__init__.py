# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Semantic Intent: canonical, warehouse-agnostic representation of a metric query.

No raw SQL; serializable to JSON; deterministic and diffable.
"""

from axi.intent.models import (
    SemanticIntent,
    Measure,
    TimeDimension,
    JoinStep,
    IntentFilter,
    SimpleFilter,
    AndFilter,
    OrFilter,
)
from axi.intent.schema import get_intent_json_schema
from axi.intent.builder import build_intent_from_metric
from axi.intent.compiler import compile_metric, resolve_plan, emit_sql, QueryPlan
from axi.intent.validation import validate_intent_for_compilation

__all__ = [
    "SemanticIntent",
    "Measure",
    "TimeDimension",
    "JoinStep",
    "IntentFilter",
    "SimpleFilter",
    "AndFilter",
    "OrFilter",
    "get_intent_json_schema",
    "build_intent_from_metric",
    "compile_metric",
    "resolve_plan",
    "emit_sql",
    "QueryPlan",
    "validate_intent_for_compilation",
]
