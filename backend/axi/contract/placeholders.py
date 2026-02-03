# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Parameter placeholder names for time and dimension filters (BI tool binding)."""

from typing import Any

# Standard time filter parameter names (contract-aligned)
TIME_FILTER_PARAMS = ("axi_start_date", "axi_end_date")
DIMENSION_FILTER_PREFIX = "axi_filter_"


def format_time_placeholder(kind: str) -> str:
    """Return placeholder for time filter. kind is 'start_date' or 'end_date'."""
    if kind == "start_date":
        return ":axi_start_date"
    if kind == "end_date":
        return ":axi_end_date"
    return f":axi_{kind}"


def format_dimension_placeholder(dimension_name: str) -> str:
    """Return placeholder for dimension filter (safe identifier)."""
    safe = (dimension_name or "").strip().replace(".", "_").replace(" ", "_")
    return f":{DIMENSION_FILTER_PREFIX}{safe}"
