# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
AI Explanation using approved glossary language only.

Given a subject (metric/entity name), return a structured explanation:
- explained: uses approved glossary text
- partial: linked term exists but gaps remain
- unexplained: no approved term
"""

from typing import Dict, Optional, List
from axi.glossary.term_store import GlossaryTermStore
from axi.metadata.indexer import MetadataIndexer
from axi.config.settings import get_settings


def explain_subject(subject: str, subject_type: str) -> Dict:
    """
    Explain a metric or entity using approved glossary language only.
    subject_type: "metric" | "entity"
    """
    settings = get_settings()
    indexer = MetadataIndexer(settings.metadata_dir)
    term_store = GlossaryTermStore()

    # Approved terms map
    terms = [t for t in term_store.list_terms() if t.status == "approved"]
    term_by_name = {t.term.lower(): t for t in terms}

    linked_terms: List[str] = []
    if subject_type == "metric":
        metric = indexer.get_metric(subject)
        if metric:
            linked_terms = [
                t.term for t in terms
                if metric.get("name") in (t.derived_from or [])
            ]
    elif subject_type == "entity":
        entity = indexer.get_entity(subject)
        if entity:
            linked_terms = [
                t.term for t in terms
                if entity.get("name") in (t.applies_to_entities or [])
            ]

    # Direct glossary term match
    direct = term_by_name.get(subject.lower())
    if direct:
        return {
            "type": "explained",
            "subject": subject,
            "explanation": direct.definition,
            "sources": [f"{direct.term} (glossary)"]
        }

    # Linked glossary term
    if linked_terms:
        term = term_by_name.get(linked_terms[0].lower())
        if term:
            return {
                "type": "partial",
                "subject": subject,
                "explanation": f"This is linked to the glossary term '{term.term}'. {term.definition}",
                "sources": [f"{term.term} (glossary)"],
                "missing": ["No direct glossary entry for this item; consider adding if business meaning differs."]
            }

    return {
        "type": "unexplained",
        "subject": subject,
        "reason": "No approved glossary definition exists for this concept."
    }
