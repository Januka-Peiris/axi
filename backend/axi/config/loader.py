# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import yaml
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import os

class PromotionRules(BaseModel):
    tags: List[str] = Field(default_factory=list)
    folders: List[str] = Field(default_factory=list)

class PromotionConfig(BaseModel):
    mode: str = "auto"  # strict, auto, hybrid (future)
    include: PromotionRules = Field(default_factory=PromotionRules)
    exclude: PromotionRules = Field(default_factory=PromotionRules)

class DbtConfig(BaseModel):
    compiled_path: Optional[str] = None

class DimensionsConfig(BaseModel):
    keep: List[str] = Field(default_factory=list)
    drop: List[str] = Field(default_factory=list)

class SnowflakeConfig(BaseModel):
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)
    account: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    warehouse: Optional[str] = None
    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")

    @property
    def schema(self) -> Optional[str]:
        return self.schema_name

    @schema.setter
    def schema(self, value: Optional[str]):
        self.schema_name = value

class Config(BaseModel):
    include: PromotionRules = Field(default_factory=PromotionRules)
    exclude: PromotionRules = Field(default_factory=PromotionRules)
    promotion: PromotionConfig = Field(default_factory=PromotionConfig)
    dbt: Optional[DbtConfig] = None
    dimensions: DimensionsConfig = Field(default_factory=DimensionsConfig)
    snowflake: Optional[SnowflakeConfig] = None

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
    
    # Handle promotion config
    if "promotion" in data and isinstance(data["promotion"], dict):
        data["promotion"] = PromotionConfig(
            mode=data["promotion"].get("mode", "auto"),
            include=PromotionRules(**data["promotion"].get("include", {})),
            exclude=PromotionRules(**data["promotion"].get("exclude", {})),
        )
    else:
        # Default promotion mirrors include/exclude to avoid AttributeError downstream
        data["promotion"] = PromotionConfig(
            include=PromotionRules(**data.get("include", {})),
            exclude=PromotionRules(**data.get("exclude", {})),
            mode=data.get("promotion", {}).get("mode") if isinstance(data.get("promotion"), dict) else "auto",
        )

    # Snowflake credentials (optional)
    if "snowflake" in data and isinstance(data["snowflake"], dict):
        data["snowflake"] = SnowflakeConfig(**data["snowflake"])
    
    return Config(**data)
