# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Load machine-readable AXI SQL contract."""

from __future__ import annotations

import json
import os
from typing import Any, Dict

_CONTRACT_CACHE: Dict[str, Any] | None = None


def get_contract() -> Dict[str, Any]:
    """Load and return the AXI SQL contract (cached)."""
    global _CONTRACT_CACHE
    if _CONTRACT_CACHE is not None:
        return _CONTRACT_CACHE
    path = os.path.join(os.path.dirname(__file__), "contract_schema.json")
    with open(path) as f:
        _CONTRACT_CACHE = json.load(f)
    return _CONTRACT_CACHE
