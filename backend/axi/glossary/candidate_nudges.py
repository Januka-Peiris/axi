# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Glossary candidate nudges (advisory only).

Given promoted items and existing glossary terms, suggest whether an item
might warrant a curated glossary entry. Never creates or edits glossary terms.
"""

from typing import List, Dict, Optional

from axi.glossary.term_store import GlossaryTermStore
from axi.metadata.indexer import MetadataIndexer
from axi.config.settings import get_settings
from axi.utils.logging_config import get_logger

logger = get_logger(__name__)


def _looks_business(name: str) -> bool:
    signals = ["revenue", "customer", "active", "cohort", "gross", "net", "margin", "churn", "retention", "ltv", "aov"]
    lname = name.lower()
    return any(sig in lname for sig in signals)


def _looks_technical(name: str) -> bool:
    tech_tokens = ["raw", "tmp", "test", "flag", "id", "hash", "event", "stg", "fct", "dim", "tmp_", "_tmp"]
    lname = name.lower()
    return any(tok in lname for tok in tech_tokens)


def suggest_candidates(item_name: Optional[str] = None) -> List[Dict]:
    """
    Suggest whether promoted items might merit a glossary term.

    Returns list of findings with:
    - type: candidate_suggestion | not_recommended | uncertain
    - item
    - confidence
    - reason
    """
    settings = get_settings()
    indexer = MetadataIndexer(settings.metadata_dir)
    term_store = GlossaryTermStore()

    approved_terms = {t.term.lower() for t in term_store.list_terms()}

    findings: List[Dict] = []

    def evaluate(name: str) -> Dict:
        lname = name.lower()
        if lname in approved_terms:
            return {
                "type": "not_recommended",
                "item": name,
                "confidence": 0.95,
                "reason": "Already covered by an approved glossary term."
            }

        if _looks_technical(name):
            return {
                "type": "not_recommended",
                "item": name,
                "confidence": 0.9,
                "reason": "Appears technical and unlikely to need a business glossary definition."
            }

        if _looks_business(name):
            return {
                "type": "candidate_suggestion",
                "item": name,
                "confidence": 0.78,
                "reason": "Name suggests business relevance; consider an agreed definition if used in reporting."
            }

        return {
            "type": "uncertain",
            "item": name,
            "confidence": 0.4,
            "reason": "Insufficient signal to recommend a glossary term."
        }

    try:
        items = []
        if item_name:
            items = [item_name]
        else:
            items.extend([m.get("name") for m in indexer.list_metrics()] or [])
            items.extend([e.get("name") for e in indexer.list_entities()] or [])
            # de-dup
            items = [i for i in items if i]
            items = list(dict.fromkeys(items))
    except Exception as e:
        logger.error(f"Failed to load promoted items for candidate nudges: {e}")
        return []

    for name in items:
        findings.append(evaluate(name))

    return findings
