# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Metric versioning and deprecation: version comparison, breaking-change detection, diff.

Versioning is explicit, never inferred. Backwards compatibility is sacred.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


# --- Version comparison (explicit, never inferred) ---

def _parse_version_parts(v: str) -> List[int]:
    """Parse version string into comparable parts. Handles 1.0, 1.0.0, 2."""
    if not v or not isinstance(v, str):
        return [0]
    s = v.strip()
    # Allow digits and dots only; strip any suffix like -alpha
    s = re.sub(r"[^0-9.].*$", "", s)
    if not s:
        return [0]
    parts = []
    for p in s.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return parts if parts else [0]


def version_compare(a: str, b: str) -> int:
    """
    Compare two version strings. Explicit, deterministic.

    Returns:
        -1 if a < b, 0 if a == b, 1 if a > b
    """
    pa = _parse_version_parts(a)
    pb = _parse_version_parts(b)
    for i in range(max(len(pa), len(pb))):
        va = pa[i] if i < len(pa) else 0
        vb = pb[i] if i < len(pb) else 0
        if va < vb:
            return -1
        if va > vb:
            return 1
    return 0


def _normalize_list(x: Any) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return [str(i).strip() for i in x if i is not None and str(i).strip()]
    if isinstance(x, str):
        return [x.strip()] if x.strip() else []
    return []


def _normalize_str(x: Any) -> str:
    if x is None:
        return ""
    return str(x).strip()


# --- Breaking change detection ---

def is_breaking_change(old_metric: Dict[str, Any], new_metric: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Detect if new_metric introduces breaking changes vs old_metric.
    Returns (is_breaking, list of change descriptions).
    """
    reasons: List[str] = []
    old_expr = _normalize_str(old_metric.get("expression"))
    new_expr = _normalize_str(new_metric.get("expression"))
    if old_expr != new_expr:
        reasons.append("expression changed")
    old_grain = sorted(_normalize_list(old_metric.get("grain")))
    new_grain = sorted(_normalize_list(new_metric.get("grain")))
    if old_grain != new_grain:
        reasons.append("grain changed")
    old_dims = sorted(_normalize_list(old_metric.get("dimensions")))
    new_dims = sorted(_normalize_list(new_metric.get("dimensions")))
    if old_dims != new_dims:
        reasons.append("dimensions changed")
    old_agg = _normalize_str(old_metric.get("aggregation"))
    new_agg = _normalize_str(new_metric.get("aggregation"))
    if old_agg != new_agg:
        reasons.append("aggregation changed")
    old_model = _normalize_str(old_metric.get("model"))
    new_model = _normalize_str(new_metric.get("model"))
    if old_model != new_model:
        reasons.append("model changed")
    return (len(reasons) > 0, reasons)


# --- Human-readable diff ---

def diff_metrics(
    a: Dict[str, Any],
    b: Dict[str, Any],
    name_a: Optional[str] = None,
    name_b: Optional[str] = None,
) -> str:
    """
    Produce human-readable diff between two metrics.
    name_a / name_b are optional labels (e.g. metric name or "v1" / "v2").
    """
    label_a = name_a or a.get("name") or "A"
    label_b = name_b or b.get("name") or "B"
    lines: List[str] = []
    lines.append(f"--- {label_a}")
    lines.append(f"+++ {label_b}")
    lines.append("")

    def _diff_field(key: str, fmt: str = "{}") -> None:
        va = a.get(key)
        vb = b.get(key)
        if va == vb:
            return
        lines.append(f"  {key}:")
        lines.append(f"    - {fmt.format(va)}")
        lines.append(f"    + {fmt.format(vb)}")
        lines.append("")

    def _diff_list(key: str) -> None:
        la = _normalize_list(a.get(key))
        lb = _normalize_list(b.get(key))
        if la == lb:
            return
        lines.append(f"  {key}:")
        lines.append(f"    - {la}")
        lines.append(f"    + {lb}")
        lines.append("")

    _diff_field("expression")
    _diff_field("model")
    _diff_field("aggregation")
    _diff_field("version")
    _diff_field("status")
    _diff_field("deprecation_date")
    _diff_field("replacement_metric")
    _diff_list("grain")
    _diff_list("dimensions")
    _diff_list("filters")
    _diff_list("default_dimensions")

    if len(lines) <= 3:
        return f"--- {label_a}\n+++ {label_b}\n\n(no differences)"
    return "\n".join(lines).rstrip()
