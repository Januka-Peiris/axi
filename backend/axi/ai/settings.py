# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
AI settings loader.

AI is optional and disabled by default. Configuration is driven by environment variables only.
"""

import os
from pydantic import BaseModel, Field


class AISettings(BaseModel):
    enabled: bool = Field(default=False, description="Enable AI advisory features")
    provider: str = Field(default="openai", description="AI provider identifier")
    api_key: str = Field(default="", description="AI provider API key")
    model: str = Field(default="gpt-4o-mini", description="Model name")
    timeout_seconds: int = Field(default=15, description="Request timeout in seconds")

    @classmethod
    def from_env(cls) -> "AISettings":
        return cls(
            enabled=os.getenv("AXI_AI_ENABLED", "false").lower() == "true",
            provider=os.getenv("AXI_AI_PROVIDER", "openai"),
            api_key=os.getenv("AXI_AI_API_KEY", ""),
            model=os.getenv("AXI_AI_MODEL", "gpt-4o-mini"),
            timeout_seconds=int(os.getenv("AXI_AI_TIMEOUT_SECONDS", "15")),
        )

