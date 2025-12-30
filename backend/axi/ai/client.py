# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Provider-agnostic AI client.

Reads prompts from backend/axi/ai/prompts/*.md, validates structured output
against Pydantic schemas, and enforces guardrails. AI is optional and disabled
by default. If disabled or unavailable, raises AIDisabledError or returns a
controlled AIUnavailableError.
"""

import json
import os
from pathlib import Path
from typing import Type

from pydantic import BaseModel, ValidationError

from axi.ai.settings import AISettings
from axi.ai.guards import guard_output


class AIDisabledError(Exception):
    pass


class AIUnavailableError(Exception):
    pass


class AIRejectedError(Exception):
    pass


def _load_prompt(prompt_name: str) -> str:
    prompt_path = Path(__file__).parent / "prompts" / f"{prompt_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def _call_provider(settings: AISettings, prompt: str, payload: dict) -> str:
    """
    Placeholder provider call. This is intentionally minimal and safe:
    - No retries
    - No prompt modifications
    - Returns AIUnavailableError if not configured
    """
    if not settings.api_key:
        raise AIUnavailableError("AI API key not configured")
    # Provider integration would go here; for now we fail safely.
    raise AIUnavailableError("AI provider call not implemented in OSS build")


def run(prompt_name: str, input_payload: dict, schema: Type[BaseModel]) -> BaseModel:
    settings = AISettings.from_env()
    if not settings.enabled:
        raise AIDisabledError("AI disabled")

    prompt_text = _load_prompt(prompt_name)

    try:
        raw = _call_provider(settings, prompt_text, input_payload)
    except AIUnavailableError as e:
        raise
    except Exception as e:
        raise AIUnavailableError(str(e))

    # Parse JSON
    try:
        data = json.loads(raw)
    except Exception:
        raise AIUnavailableError("AI returned invalid JSON")

    # Validate schema
    try:
        model = schema(**data)
    except ValidationError:
        raise AIRejectedError("AI output failed schema validation")

    if not guard_output(model):
        raise AIRejectedError("AI output rejected by guardrails")

    return model
