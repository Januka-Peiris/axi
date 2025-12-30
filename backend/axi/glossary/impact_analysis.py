# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Semantic impact awareness.

Advisory-only: surfaces downstream concepts that may be affected by glossary or semantic changes.
Never blocks or mutates; no SQL is inspected.
"""

from typing import Dict, List, Optional
from axi.config.settings import get_settings
from axi.glossary.term_store import GlossaryTermStore
from axi.metadata.indexer import MetadataIndexer
from axi.utils.logging_config import get_logger

logger = get_logger(__name__)


def _severity(count: int) -> str:
    if count >= 5:
        return "high"
    if count >= 2:
        return "medium"
    return "low"


def run_impact_analysis(
    change_type: str,
    subject: str,
    before: Optional[Dict] = None,
    after: Optional[Dict] = None,
) -> List[Dict]:
    """
    Compute advisory impact statements.

    change_type: glossary_edit | glossary_deprecate | semantic_change
    subject: term or metric/entity name
    before/after: optional snapshots (names/definitions only)
    """
    settings = get_settings()
    term_store = GlossaryTermStore()
    indexer = MetadataIndexer(settings.metadata_dir)

    findings: List[Dict] = []

    # Find linked semantics for glossary terms
    term = term_store.get_term(subject)
    linked_metrics = []
    linked_entities = []
    if term:
        linked_metrics = term.derived_from or []
        linked_entities = term.applies_to_entities or []

    # Gather references (basic: linked metrics/entities, plus any metrics depending on linked metrics)
    downstream: List[str] = []
    downstream.extend(linked_metrics)
    downstream.extend(linked_entities)

    # Include metrics depending on linked metrics
    try:
        metrics = indexer.list_metrics()
        for m in metrics:
            deps = m.get("depends_on") or []
            if isinstance(deps, list) and any(d in linked_metrics for d in deps):
                downstream.append(m.get("name"))
    except Exception as e:
        logger.debug(f"Unable to load downstream metrics: {e}")

    downstream = [d for d in downstream if d]
    downstream = list(dict.fromkeys(downstream))

    if term:
        change_label = f"Glossary {change_type.replace('_', ' ')}: {term.term}"
        if downstream:
            findings.append({
                "type": "impact_detected",
                "change": change_label,
                "affected": downstream,
                "severity": _severity(len(downstream)),
                "explanation": "These concepts are linked to this glossary term and may be interpreted differently after the change."
            })
        else:
            findings.append({
                "type": "minimal_impact",
                "change": change_label,
                "confidence": 0.9,
                "explanation": "No downstream metrics or entities are linked to this term."
            })
        return findings

    # For semantic changes (metric/entity) without a glossary term
    if change_type == "semantic_change":
        # Check if any approved term references this subject
        impacted_terms = []
        for t in term_store.list_terms():
            if t.status != "approved":
                continue
            if subject in (t.derived_from or []) or subject in (t.applies_to_entities or []):
                impacted_terms.append(t.term)

        change_label = f"Semantic change: {subject}"
        if impacted_terms:
            findings.append({
                "type": "impact_detected",
                "change": change_label,
                "affected": impacted_terms,
                "severity": _severity(len(impacted_terms)),
                "explanation": "These glossary terms reference this concept and may need review."
            })
        else:
            findings.append({
                "type": "uncertain",
                "change": change_label,
                "reason": "No linked glossary terms found; downstream impact unclear."
            })

    return findings
