# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import yaml
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os

class PromotionRules(BaseModel):
    tags: List[str] = Field(default_factory=list)
    folders: List[str] = Field(default_factory=list)

class DbtConfig(BaseModel):
    compiled_path: Optional[str] = None

class DimensionsConfig(BaseModel):
    keep: List[str] = Field(default_factory=list)
    drop: List[str] = Field(default_factory=list)

class Config(BaseModel):
    include: PromotionRules = Field(default_factory=PromotionRules)
    exclude: PromotionRules = Field(default_factory=PromotionRules)
    dbt: Optional[DbtConfig] = None
    dimensions: DimensionsConfig = Field(default_factory=DimensionsConfig)

def load_config(config_path: str) -> Config:
    if not os.path.exists(config_path):
        return Config()
        
    with open(config_path, "r") as f:
        data = yaml.safe_load(f)
        
    if not data:
        return Config()
    
    # Handle dbt config if present
    if "dbt" in data and isinstance(data["dbt"], dict):
        data["dbt"] = DbtConfig(**data["dbt"])
    
    # Handle dimensions config if present
    if "dimensions" in data and isinstance(data["dimensions"], dict):
        data["dimensions"] = DimensionsConfig(**data["dimensions"])
    
    return Config(**data)
