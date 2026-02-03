# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Semantic Intent Pydantic models.

Warehouse-agnostic, JSON-serializable, deterministic and diffable.
No raw SQL.
"""

from __future__ import annotations

from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# --- Aggregation and join types (closed set for determinism) ---

AggregationType = Literal["sum", "count", "avg", "min", "max", "count_distinct"]
JoinType = Literal["left", "inner", "right", "full"]
FilterOperator = Literal[
    "=", "!=", ">", "<", ">=", "<=",
    "IN", "NOT IN", "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL",
]
TimeGranularity = Literal["day", "week", "month", "quarter", "year"]


# --- Typed, composable filters ---

class SimpleFilter(BaseModel):
    """Single predicate: dimension op value."""
    type: Literal["simple"] = "simple"
    dimension: str = Field(..., description="Column or entity.column reference")
    op: FilterOperator
    value: Optional[Any] = None  # None for IS NULL / IS NOT NULL

    @field_validator("dimension")
    @classmethod
    def dimension_stripped(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("op")
    @classmethod
    def op_upper(cls, v: str) -> str:
        return v.strip().upper() if v in ("IN", "NOT IN", "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL") else v.strip()


class AndFilter(BaseModel):
    """Conjunction of filter clauses."""
    type: Literal["and"] = "and"
    clauses: List["IntentFilter"]  # noqa: F821

    @field_validator("clauses")
    @classmethod
    def clauses_non_empty(cls, v: List[Any]) -> List[Any]:
        if not v or len(v) < 2:
            raise ValueError("AndFilter requires at least 2 clauses")
        return v


class OrFilter(BaseModel):
    """Disjunction of filter clauses."""
    type: Literal["or"] = "or"
    clauses: List["IntentFilter"]  # noqa: F821

    @field_validator("clauses")
    @classmethod
    def clauses_non_empty(cls, v: List[Any]) -> List[Any]:
        if not v or len(v) < 2:
            raise ValueError("OrFilter requires at least 2 clauses")
        return v


IntentFilter = Union[SimpleFilter, AndFilter, OrFilter]

# Resolve forward refs for nested filter types
AndFilter.model_rebuild()
OrFilter.model_rebuild()


# --- Measure (name + column ref + aggregation) ---

class Measure(BaseModel):
    """A single measure: output name, source column reference, aggregation."""
    name: str = Field(..., description="Output name of the measure")
    column_ref: str = Field(..., description="Entity.column or column (warehouse-agnostic)")
    aggregation: AggregationType

    @field_validator("name", "column_ref")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return (v or "").strip()


# --- Time dimension ---

class TimeDimension(BaseModel):
    """Optional time dimension with granularity."""
    name: str = Field(..., description="Output name (e.g. month, week)")
    column_ref: str = Field(..., description="Entity.column or column")
    granularity: Optional[TimeGranularity] = None

    @field_validator("name", "column_ref")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return (v or "").strip()


# --- Resolved join path (order matters) ---

class JoinStep(BaseModel):
    """Single step in a resolved join path: from_entity -> to_entity."""
    from_entity: str = Field(..., description="Entity on the left of the join")
    to_entity: str = Field(..., description="Entity on the right of the join")
    from_column: str = Field(..., description="Column on from_entity (usually FK)")
    to_column: str = Field(..., description="Column on to_entity (usually PK)")
    join_type: JoinType = "left"

    @field_validator("from_entity", "to_entity", "from_column", "to_column")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return (v or "").strip()


# --- Semantic Intent (root) ---

class SemanticIntent(BaseModel):
    """
    Canonical representation of a metric query: warehouse-agnostic, no SQL.

    - metric_name / metric_version: identity and versioning for diffing.
    - base_entity: entity the metric is anchored to.
    - grain: ordered list of columns defining the grain (determinism).
    - measures: one or more measures with aggregation type.
    - dimensions: column refs for GROUP BY (sorted for deterministic serialization).
    - time_dimension: optional time axis.
    - filters: typed, composable (AND/OR).
    - join_path: resolved path from base_entity to any other entities needed; not inferred at runtime.
    """

    metric_name: str = Field(..., description="Metric identifier")
    metric_version: str = Field(default="1.0", description="Version for deterministic diffing")
    base_entity: str = Field(..., description="Entity the metric is anchored to")
    grain: List[str] = Field(default_factory=list, description="Ordered grain columns")
    measures: List[Measure] = Field(..., min_length=1, description="Measures with aggregation type")
    dimensions: List[str] = Field(default_factory=list, description="Dimension column refs")
    time_dimension: Optional[TimeDimension] = None
    filters: List[IntentFilter] = Field(default_factory=list, description="Typed, composable filters")
    join_path: List[JoinStep] = Field(default_factory=list, description="Resolved join path; order matters")

    @field_validator("metric_name", "base_entity")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("dimensions")
    @classmethod
    def dimensions_sorted(cls, v: List[str]) -> List[str]:
        """Sort dimensions for deterministic JSON serialization."""
        return sorted((x or "").strip() for x in v if (x or "").strip())

    @field_validator("grain")
    @classmethod
    def grain_stripped(cls, v: List[str]) -> List[str]:
        return [(x or "").strip() for x in v if (x or "").strip()]

    @field_validator("measures")
    @classmethod
    def measures_sorted(cls, v: List[Measure]) -> List[Measure]:
        """Sort measures by (name, column_ref, aggregation) for deterministic serialization."""
        return sorted(v, key=lambda m: (m.name, m.column_ref, m.aggregation))

    def model_dump_json_sorted(self, **kwargs: Any) -> str:
        """Serialize to JSON with sorted keys for stable diffs."""
        return self.model_dump_json(**kwargs)
