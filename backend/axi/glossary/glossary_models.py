# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from pydantic import BaseModel
from typing import List, Optional

class GlossaryAttribute(BaseModel):
    name: str
    data_type: str
    description: Optional[str] = None
    is_pk: bool = False
    is_fk: bool = False
    source_column: str
    tags: List[str] = []

class GlossaryRelationship(BaseModel):
    source_entity: str
    target_entity: str
    type: str  # "one_to_many", "many_to_one", etc.
    source_key: str
    target_key: str
    description: Optional[str] = None

class GlossaryEntity(BaseModel):
    name: str
    model: str
    description: Optional[str] = None
    attributes: List[GlossaryAttribute]
    metrics: List[str]  # metric names
    relationships: List[GlossaryRelationship]
    tags: List[str] = []

class GlossaryMetric(BaseModel):
    name: str
    expression: str
    metric_type: str
    dimensions: List[str]
    description: Optional[str] = None
    default_filters: List[str] = []
    grain: Optional[str] = None
    tags: List[str] = []
    sources: List[str] = []  # underlying tables

class GlossaryDimension(BaseModel):
    name: str
    data_type: str
    attributes: List[str]
    related_metrics: List[str]
    description: Optional[str] = None
    tags: List[str] = []

class Glossary(BaseModel):
    generated_at: str
    entities: List[GlossaryEntity]
    metrics: List[GlossaryMetric]
    dimensions: List[GlossaryDimension]
    relationships: List[GlossaryRelationship]
