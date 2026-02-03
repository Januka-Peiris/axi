# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
AXI SQL contract for BI tools.

Machine-readable contract and validation so AXI-generated SQL works
as custom SQL, derived table, or view definition across BI tools.
"""

from axi.contract.loader import get_contract
from axi.contract.validator import validate_sql_contract, ContractViolation
from axi.contract.placeholders import (
    TIME_FILTER_PARAMS,
    DIMENSION_FILTER_PREFIX,
    format_time_placeholder,
    format_dimension_placeholder,
)

__all__ = [
    "get_contract",
    "validate_sql_contract",
    "ContractViolation",
    "TIME_FILTER_PARAMS",
    "DIMENSION_FILTER_PREFIX",
    "format_time_placeholder",
    "format_dimension_placeholder",
]
