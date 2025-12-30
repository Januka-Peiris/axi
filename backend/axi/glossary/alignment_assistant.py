# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Deterministic glossary alignment assistant.

Given a candidate promoted name (metric/entity) and approved glossary terms,
suggest whether it matches, may duplicate, conflicts, or has no match.
No mutations are performed; outputs are advisory.
"""

import difflib
import re
from typing import List, Optional, Tuple, Dict

from axi.glossary.term_store import GlossaryTermStore
from axi.metadata.indexer import MetadataIndexer
from axi.config.settings import get_settings
from axi.utils.logging_config import get_logger

logger = get_logger(__name__)


def _normalize(text: str) -> str:
    text = text.lower().strip()
    # Replace separators with space and collapse
    text = re.sub(r"[_\-\.]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def _similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _best_term_match(candidate: str, terms: List[Dict]) -> Tuple[Optional[Dict], float, str]:
    best_term = None
    best_score = 0.0
    best_source = ""
    for term in terms:
        score_name = _similarity(candidate, term["term"])
        if score_name > best_score:
            best_term = term
            best_score = score_name
            best_source = term["term"]
        for syn in term.get("synonyms", []) or []:
            score_syn = _similarity(candidate, syn)
            if score_syn > best_score:
                best_term = term
                best_score = score_syn
                best_source = syn
    return best_term, best_score, best_source


def align_candidate(candidate_name: str, label: Optional[str] = None) -> Dict:
    """
    Return alignment suggestion for a candidate promoted item.

    Outputs:
    - result: match | possible_duplicate | no_match | conflict
    - confidence: 0-1 float
    - explanation: human-readable rationale
    """
    settings = get_settings()
    term_store = GlossaryTermStore()
    indexer = MetadataIndexer(settings.metadata_dir)

    approved_terms = [
        t.model_dump()
        for t in term_store.list_terms()
        if t.status == "approved"
    ]

    if not approved_terms:
        return {
            "result": "no_match",
            "confidence": 0.1,
            "explanation": "No approved glossary terms exist yet; nothing to align against."
        }

    candidate_basis = label or candidate_name
    best_term, best_score, best_source = _best_term_match(candidate_basis, approved_terms)

    if not best_term or best_score < 0.5:
        return {
            "result": "no_match",
            "confidence": round(best_score, 2),
            "explanation": f"No clear glossary alignment for '{candidate_basis}'."
        }

    # Conflict if the closest term is deprecated (should not happen with approved filter) or if candidate clashes with another promoted object name
    if best_term.get("status") == "deprecated":
        return {
            "result": "conflict",
            "confidence": round(best_score, 2),
            "explanation": f"Closest term '{best_term['term']}' is deprecated; avoid reusing this meaning."
        }

    # Check if candidate name already exists as a different promoted metric/entity for advisory conflict
    promoted_names = set()
    try:
        promoted_names.update([m.get("name") for m in indexer.list_metrics()] or [])
        promoted_names.update([e.get("name") for e in indexer.list_entities()] or [])
    except Exception as e:
        logger.debug(f"Unable to load promoted names for alignment: {e}")

    candidate_normalized = _normalize(candidate_name)
    existing_conflict = any(_normalize(name or "") == candidate_normalized for name in promoted_names)

    if best_score >= 0.9:
        result = "match"
        explanation = f"'{candidate_basis}' closely matches approved term '{best_term['term']}' (matched via '{best_source}')."
    else:
        result = "possible_duplicate"
        explanation = f"'{candidate_basis}' is similar to approved term '{best_term['term']}' (matched via '{best_source}')."

    if existing_conflict and best_term["term"].lower() != candidate_name.lower():
        result = "conflict"
        explanation = f"'{candidate_basis}' resembles '{best_term['term']}' and also matches an existing promoted name; clarify naming to avoid drift."

    return {
        "result": result,
        "confidence": round(best_score, 2),
        "explanation": explanation
    }
