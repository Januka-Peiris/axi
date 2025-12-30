# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Semantic drift and conflict detection.

Compares approved glossary terms against current promoted semantics and flags:
- drift_warning: underlying metric/entity changed since term approval
- definition_conflict: linked metric/entity missing (meaning at risk)
- no_issue: nothing concerning detected

This module is advisory only. It never mutates glossary or semantics.
"""

from datetime import datetime
from typing import List, Optional, Dict

from axi.glossary.term_store import GlossaryTermStore
from axi.metadata.indexer import MetadataIndexer
from axi.config.settings import get_settings
from axi.utils.logging_config import get_logger

logger = get_logger(__name__)


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val)
    except Exception:
        return None


def detect_drift(term_name: Optional[str] = None) -> List[Dict]:
    """
    Detect potential semantic drift/conflicts for approved glossary terms.

    Returns list of findings with:
    - type: drift_warning | definition_conflict | no_issue
    - glossary_term
    - confidence (optional for no_issue)
    - reason
    """
    settings = get_settings()
    term_store = GlossaryTermStore()
    indexer = MetadataIndexer(settings.metadata_dir)

    terms = [
        t for t in term_store.list_terms()
        if t.status == "approved" and (not term_name or t.term == term_name)
    ]

    findings: List[Dict] = []

    for term in terms:
        has_issue = False
        term_updated = _parse_dt(term.updated_at.isoformat() if hasattr(term.updated_at, "isoformat") else term.updated_at)

        # Check linked metrics/entities existence
        for m in term.derived_from or []:
            if not indexer.get_metric(m):
                findings.append({
                    "type": "definition_conflict",
                    "glossary_term": term.term,
                    "reason": f"Linked metric '{m}' no longer exists or is not promoted."
                })
                has_issue = True

        for e in term.applies_to_entities or []:
            if not indexer.get_entity(e):
                findings.append({
                    "type": "definition_conflict",
                    "glossary_term": term.term,
                    "reason": f"Linked entity '{e}' no longer exists or is not promoted."
                })
                has_issue = True

        # Drift warning: linked metric updated after term approval
        drift_flagged = False
        for m in term.derived_from or []:
            metric = indexer.get_metric(m)
            if not metric:
                continue
            met_updated = _parse_dt(metric.get("updated_at"))
            if met_updated and term_updated and met_updated > term_updated:
                drift_flagged = True
                findings.append({
                    "type": "drift_warning",
                    "glossary_term": term.term,
                    "confidence": 0.68,
                    "reason": f"Metric '{m}' changed after this term was approved."
                })
        if not has_issue and not drift_flagged:
            findings.append({
                "type": "no_issue",
                "glossary_term": term.term,
                "confidence": 0.9
            })

    if term_name and not terms:
        findings.append({
            "type": "no_issue",
            "glossary_term": term_name,
            "confidence": 0.0,
            "reason": "Glossary term not found or not approved."
        })

    return findings
