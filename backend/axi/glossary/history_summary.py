# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Human-readable semantic change summaries (advisory only).

Reads glossary term history from the semantic store and produces plain-English
summaries of recent changes. Uses approved glossary language only.
"""

from collections import defaultdict
from typing import Dict, List, Optional

from axi.semantic_store.factory import get_semantic_store
from axi.glossary.impact_analysis import run_impact_analysis


def summarize_changes(term_name: Optional[str] = None) -> List[Dict]:
    """
    Summarize recent glossary term changes (latest vs previous version).

    Returns change_summary objects with:
    - type: change_summary
    - summary: plain language summary of what changed
    - affected_terms: [term]
    - impact: optional advisory text
    """
    store = get_semantic_store()
    states = [
        s for s in store.query(state_type="glossary_term", project_id="default")
        if not term_name or s.payload.get("term") == term_name
    ]
    grouped = defaultdict(list)
    for s in states:
        term = s.payload.get("term")
        if term:
            grouped[term].append(s)

    summaries: List[Dict] = []
    for term, items in grouped.items():
        items_sorted = sorted(items, key=lambda s: s.version)
        if len(items_sorted) < 2:
            continue  # no prior version to compare
        prev = items_sorted[-2].payload
        curr = items_sorted[-1].payload

        change_type = "glossary_edit"
        if prev.get("status") != curr.get("status") and curr.get("status") == "deprecated":
            change_type = "glossary_deprecate"

        summary_text = ""
        if prev.get("status") != curr.get("status"):
            summary_text = f"The status of {term} changed from {prev.get('status')} to {curr.get('status')}."
        elif prev.get("definition") != curr.get("definition"):
            summary_text = f"The definition of {term} was updated to clarify: {curr.get('definition')}."
        else:
            # No meaningful surface change detected
            continue

        impact_text = None
        impact_findings = run_impact_analysis(change_type=change_type, subject=term)
        if impact_findings:
            # Take first advisory explanation/affected list
            first = impact_findings[0]
            if "explanation" in first:
                impact_text = first["explanation"]
            elif "reason" in first:
                impact_text = first["reason"]

        summaries.append({
            "type": "change_summary",
            "summary": summary_text,
            "affected_terms": [term],
            "impact": impact_text or "Impact not assessed."
        })

    return summaries
