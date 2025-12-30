# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class GlossaryTerm(BaseModel):
    term: str = Field(..., description="Unique business term")
    definition: str = Field(..., min_length=1, description="Human-written definition")
    status: str = Field("draft", description="draft | approved | deprecated")
    version: int = Field(1, ge=1)
    derived_from: List[str] = Field(default_factory=list, description="Metrics or dimensions this term is based on")
    applies_to_entities: List[str] = Field(default_factory=list)
    scope: Optional[str] = Field(default=None, description="Business scope (e.g., company-wide, region-specific)")
    notes: Optional[str] = Field(default=None, description="Optional context/usage notes")
    synonyms: List[str] = Field(default_factory=list)
    source: str = Field("axi", description="Origin of the term")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"draft", "approved", "deprecated"}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v

    @field_validator("definition")
    @classmethod
    def validate_definition(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Definition cannot be empty")
        text = v.strip()
        banned_tokens = ["select", "from", "join", ".", "_id"]
        lowered = text.lower()
        if any(tok in lowered for tok in banned_tokens):
            raise ValueError("Definition must be plain language (avoid SQL/column names)")
        return text
