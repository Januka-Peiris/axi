# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Optional, Any
from pydantic import BaseModel, Field, field_validator
import re


class SavedQueryFilter(BaseModel):
    dimension: str
    op: str
    value: Any

    @field_validator("dimension")
    @classmethod
    def validate_dimension(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Dimension cannot be empty")
        return v.strip()

    @field_validator("op")
    @classmethod
    def validate_op(cls, v: str) -> str:
        allowed = {"=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN", "BETWEEN", "LIKE"}
        if v not in allowed:
            raise ValueError(f"Operator {v} not allowed")
        return v


class SavedQuery(BaseModel):
    id: str = Field(..., description="Slug identifier used for filename and API")
    name: str
    description: Optional[str] = None
    entity: str
    metrics: List[str]
    dimensions: List[str] = []
    filters: List[SavedQueryFilter] = []
    limit: Optional[int] = None
    tags: List[str] = []

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]+$", v or ""):
            raise ValueError("id must be slug-like: [a-zA-Z0-9_-]+")
        return v

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, v: List[str]) -> List[str]:
        if not v or len(v) == 0:
            raise ValueError("At least one metric is required")
        return v

    @field_validator("entity")
    @classmethod
    def validate_entity(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Entity is required")
        return v.strip()

