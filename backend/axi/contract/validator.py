# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Validate SQL against the AXI SQL contract.

Checks: no session state, no temp tables, no stored procedures.
Contract is machine-readable (contract_schema.json).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from axi.contract.loader import get_contract


@dataclass
class ContractViolation:
    """A single contract violation."""
    rule_id: str
    message: str
    snippet: Optional[str] = None
    line: Optional[int] = None


def _strip_comments(sql: str) -> str:
    """Remove SQL comments to avoid false positives on contract text in comments."""
    lines = []
    for line in sql.split("\n"):
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        # Remove inline -- comment
        if " -- " in line:
            idx = line.find(" -- ")
            line = line[:idx].rstrip()
        lines.append(line)
    return "\n".join(lines)


def validate_sql_contract(
    sql: str,
    contract: Optional[Dict[str, Any]] = None,
    strip_axi_comments: bool = True,
) -> List[ContractViolation]:
    """
    Validate SQL against the AXI SQL contract.

    - sql: Full SQL string (may include AXI metadata comments).
    - contract: Optional pre-loaded contract; if None, loads from contract_schema.json.
    - strip_axi_comments: If True, strip lines starting with -- before checking (avoids flagging AXI comments).

    Returns list of ContractViolation; empty list if valid.
    """
    if contract is None:
        contract = get_contract()
    violations: List[ContractViolation] = []
    body = sql
    if strip_axi_comments:
        body = _strip_comments(sql)

    disallowed = contract.get("disallowed_patterns") or []
    for rule in disallowed:
        rule_id = rule.get("id") or "unknown"
        desc = rule.get("description") or rule_id

        # Check keywords (case-insensitive)
        for kw in rule.get("keywords") or []:
            if re.search(re.escape(kw), body, re.IGNORECASE):
                violations.append(ContractViolation(
                    rule_id=rule_id,
                    message=f"Contract violation ({rule_id}): {desc}. Found keyword: {kw}",
                    snippet=kw,
                ))
                break
        if any(v.rule_id == rule_id for v in violations):
            continue

        # Check regex
        pattern = rule.get("regex")
        if pattern:
            try:
                m = re.search(pattern, body, re.IGNORECASE)
                if m:
                    violations.append(ContractViolation(
                        rule_id=rule_id,
                        message=f"Contract violation ({rule_id}): {desc}",
                        snippet=m.group(0)[:80],
                    ))
            except re.error:
                pass

    return violations
