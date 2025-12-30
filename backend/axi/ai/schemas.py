# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class AlignmentResult(BaseModel):
    type: Literal["match", "possible_duplicate", "no_match", "conflict"]
    confidence: float = Field(ge=0, le=1)
    explanation: str


class DriftFinding(BaseModel):
    type: Literal["drift_warning", "definition_conflict", "no_issue"]
    glossary_term: str
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    reason: Optional[str] = None


class NudgeResult(BaseModel):
    type: Literal["candidate_suggestion", "not_recommended", "uncertain"]
    item: str
    confidence: float = Field(ge=0, le=1)
    reason: str


class ExplanationResult(BaseModel):
    type: Literal["explained", "partial", "unexplained"]
    subject: str
    explanation: Optional[str] = None
    sources: Optional[List[str]] = None
    missing: Optional[List[str]] = None
    reason: Optional[str] = None


class ImpactResult(BaseModel):
    type: Literal["impact_detected", "minimal_impact", "uncertain"]
    change: str
    affected: Optional[List[str]] = None
    severity: Optional[Literal["low", "medium", "high"]] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    explanation: Optional[str] = None
    reason: Optional[str] = None


class HistorySummary(BaseModel):
    type: Literal["change_summary"]
    summary: str
    affected_terms: List[str]
    impact: Optional[str] = None
