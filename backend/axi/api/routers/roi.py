# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
ROI / usage summary API (read-only, config-driven).
No BI-tool-specific logic; simple summaries only.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from axi.config.settings import get_settings
from axi.metadata.indexer import MetadataIndexer
from axi.utils.logging_config import get_logger

router = APIRouter(prefix="/api/roi", tags=["roi"])
logger = get_logger(__name__)
settings = get_settings()


def _get_indexer() -> MetadataIndexer:
    return MetadataIndexer(settings.AXI_METADATA_DIR)


@router.get("/summary")
def get_roi_summary(
    top_n: int = 20,
    days_back: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Lightweight ROI summary: top used metrics, deprecated usage, estimated analyst hours saved.
    Config-driven (roi_hours_saved_per_query). No BI-tool logic.
    """
    indexer = _get_indexer()
    rows = indexer.list_usage()
    if not rows:
        return {
            "top_metrics": [],
            "total_matched_queries": 0,
            "total_deprecated_access": 0,
            "deprecated_last_7_days": 0,
            "deprecated_previous_7_days": 0,
            "estimated_analyst_hours_saved": 0.0,
            "hours_saved_per_query": getattr(settings, "roi_hours_saved_per_query", 0.1),
        }
    by_metric: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"usage_count": 0, "deprecated_access_count": 0, "by_date": defaultdict(lambda: {"usage": 0, "deprecated": 0})})
    for r in rows:
        name = r["metric_name"]
        by_metric[name]["usage_count"] += r["usage_count"]
        by_metric[name]["deprecated_access_count"] += r["deprecated_access_count"]
        d = r["usage_date"]
        by_metric[name]["by_date"][d]["usage"] += r["usage_count"]
        by_metric[name]["by_date"][d]["deprecated"] += r["deprecated_access_count"]
    top_metrics = sorted(
        [{"metric_name": k, "usage_count": v["usage_count"], "deprecated_access_count": v["deprecated_access_count"}] for k, v in by_metric.items()
    , key=lambda x: -x["usage_count"])[:top_n]
    total_matched = sum(r["usage_count"] for r in rows)
    total_deprecated = sum(r["deprecated_access_count"] for r in rows)
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc).date()
    last_7 = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    prev_7 = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7, 14)]
    deprecated_last_7 = sum(r["deprecated_access_count"] for r in rows if r["usage_date"] in last_7)
    deprecated_prev_7 = sum(r["deprecated_access_count"] for r in rows if r["usage_date"] in prev_7)
    hours_per = getattr(settings, "roi_hours_saved_per_query", 0.1)
    return {
        "top_metrics": top_metrics,
        "total_matched_queries": total_matched,
        "total_deprecated_access": total_deprecated,
        "deprecated_last_7_days": deprecated_last_7,
        "deprecated_previous_7_days": deprecated_prev_7,
        "estimated_analyst_hours_saved": round(total_matched * hours_per, 2),
        "hours_saved_per_query": hours_per,
    }
