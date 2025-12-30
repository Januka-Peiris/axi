# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class SemanticState:
    """
    Core semantic state record stored in the backing database.
    The payload remains JSON-first regardless of backend.
    """
    id: str
    project_id: str
    state_type: str  # extracted | inferred | approved
    version: int
    payload: Dict[str, Any]
    created_at: Optional[datetime] = None
