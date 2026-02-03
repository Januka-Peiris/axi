# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
JSON Schema for Semantic Intent.

Warehouse-agnostic, deterministic, no raw SQL.
"""

from typing import Any, Dict

from axi.intent.models import SemanticIntent


def get_intent_json_schema() -> Dict[str, Any]:
    """
    Return JSON Schema for SemanticIntent (and nested types).

    Suitable for validation and documentation; keys are sorted for stable output.
    """
    schema = SemanticIntent.model_json_schema()
    return _sort_schema_keys(schema)


def _sort_schema_keys(obj: Any) -> Any:
    """Recursively sort dict keys for deterministic schema output."""
    if isinstance(obj, dict):
        return {k: _sort_schema_keys(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_sort_schema_keys(item) for item in obj]
    return obj
