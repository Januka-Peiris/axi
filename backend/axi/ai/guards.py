# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Guardrails to reject unsafe or untrusted AI outputs.
"""

import re
from typing import Any
from pydantic import BaseModel


FORBIDDEN_TOKENS = [
    "should",
    "must",
    "create",
    "add a new",
    "define",
    "please",
    "recommend",
]


def guard_output(model: BaseModel) -> bool:
    """
    Return True if output is acceptable, False otherwise.
    Heuristics only; errs on the side of rejection.
    """
    text_fields = []
    for _, value in model:
        if isinstance(value, str):
            text_fields.append(value.lower())
        elif isinstance(value, list):
            for v in value:
                if isinstance(v, str):
                    text_fields.append(v.lower())

    for text in text_fields:
        if any(tok in text for tok in FORBIDDEN_TOKENS):
            return False
        # No hallucinated imperative suggestions
        if re.search(r"\b(should|must|need to)\b", text):
            return False
    return True

