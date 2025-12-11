# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Dict, Any, Protocol, Type, Optional, Callable
from pydantic import BaseModel
from fastapi import APIRouter
from typer import Typer

# Protocols
class CustomMetric(Protocol):
    type_name: str
    def to_sql(self, context: Dict[str, Any]) -> str: ...

class OptimizationRule(Protocol):
    name: str
    def apply(self, expression: Any, context: Any) -> Any: ...

class MetadataExtractor(Protocol):
    warehouse: str
    def extract(self) -> List[Any]: ...

# Manifest
class AXIPluginManifest(BaseModel):
    name: str
    version: str
    description: str = ""
    author: str = ""
    
    # Entrypoints
    metrics: Optional[List[Type[CustomMetric]]] = None
    optimizer_rules: Optional[List[Type[OptimizationRule]]] = None
    # We can't type hint Typer/APIRouter easily in Pydantic without arbitrary types allowed
    # For now, we rely on the loader to pull these from the module or manual registration
    
    # Hooks
    hooks: Optional[Dict[str, Callable]] = None
    
    class Config:
        arbitrary_types_allowed = True
