# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import datetime
from typing import Dict, List, Optional

from axi.config.settings import get_settings
from axi.glossary.term_models import GlossaryTerm
from axi.metadata.indexer import MetadataIndexer
from axi.semantic_store.factory import get_semantic_store
from axi.semantic_store.models import SemanticState
from axi.utils.logging_config import get_logger

logger = get_logger(__name__)


class GlossaryTermStore:
    """
    Versioned glossary term store backed by the SemanticStore abstraction.
    """

    def __init__(self, project_id: Optional[str] = None):
        self.settings = get_settings()
        self.project_id = project_id or "default"
        self.store = get_semantic_store()
        self.indexer = MetadataIndexer(self.settings.metadata_dir)

    def _latest_by_term(self) -> Dict[str, SemanticState]:
        latest: Dict[str, SemanticState] = {}
        for state in self.store.query(state_type="glossary_term", project_id=self.project_id):
            term_name = state.payload.get("term")
            if not term_name:
                continue
            existing = latest.get(term_name)
            if not existing or state.version > existing.version:
                latest[term_name] = state
        return latest

    def list_terms(
        self,
        linked_entity: Optional[str] = None,
        linked_metric: Optional[str] = None,
    ) -> List[GlossaryTerm]:
        latest = self._latest_by_term()
        results: List[GlossaryTerm] = []
        for state in latest.values():
            payload = state.payload
            if linked_entity and linked_entity not in payload.get("linked_entities", []):
                continue
            if linked_metric and linked_metric not in payload.get("linked_metrics", []):
                continue
            results.append(GlossaryTerm(**payload))
        return sorted(results, key=lambda t: t.term.lower())

    def get_term(self, term: str) -> Optional[GlossaryTerm]:
        latest = self._latest_by_term()
        state = latest.get(term)
        if not state:
            return None
        return GlossaryTerm(**state.payload)

    def _validate_links(self, derived_from: List[str], applies_to_entities: List[str]) -> None:
        # Entities must exist and be promoted
        for ent in applies_to_entities:
            if not self.indexer.get_entity(ent):
                raise ValueError(f"Linked entity '{ent}' does not exist or is not promoted")
        # Derived items must be promoted metrics or dimensions
        for item in derived_from:
            if self.indexer.get_metric(item):
                continue
            dim = self.indexer.get_dimension(item) if hasattr(self.indexer, "get_dimension") else None
            if dim:
                continue
            raise ValueError(f"Derived item '{item}' is not a promoted metric or dimension")

    def create_term(
        self,
        term: str,
        definition: str,
        status: str = "draft",
        derived_from: Optional[List[str]] = None,
        applies_to_entities: Optional[List[str]] = None,
        synonyms: Optional[List[str]] = None,
        scope: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> GlossaryTerm:
        latest = self._latest_by_term()
        if term in latest:
            raise ValueError(f"Term '{term}' already exists. Use edit instead.")

        derived_from = derived_from or []
        applies_to_entities = applies_to_entities or []
        synonyms = synonyms or []
        self._validate_links(derived_from, applies_to_entities)

        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        new_term = GlossaryTerm(
            term=term,
            definition=definition,
            status=status,
            version=1,
            derived_from=derived_from,
            applies_to_entities=applies_to_entities,
            scope=scope,
            notes=notes,
            synonyms=synonyms,
            source="axi",
            created_at=now,
            updated_at=now,
        )
        self.store.write(
            state_type="glossary_term",
            payload=new_term.model_dump(mode="json"),
            version=new_term.version,
            project_id=self.project_id,
        )
        return new_term

    def edit_term(
        self,
        term: str,
        definition: Optional[str] = None,
        status: Optional[str] = None,
        derived_from: Optional[List[str]] = None,
        applies_to_entities: Optional[List[str]] = None,
        synonyms: Optional[List[str]] = None,
        scope: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> GlossaryTerm:
        current = self.get_term(term)
        if not current:
            raise ValueError(f"Term '{term}' not found.")
        if current.status == "deprecated":
            raise ValueError("Deprecated terms cannot be edited. Create a new term instead.")

        new_definition = definition or current.definition
        new_status = status or current.status
        new_derived = derived_from if derived_from is not None else current.derived_from
        new_entities = applies_to_entities if applies_to_entities is not None else current.applies_to_entities
        new_synonyms = synonyms if synonyms is not None else current.synonyms
        new_scope = scope if scope is not None else current.scope
        new_notes = notes if notes is not None else current.notes

        self._validate_links(new_derived, new_entities)

        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        updated = GlossaryTerm(
            term=current.term,
            definition=new_definition,
            status=new_status,
            version=current.version + 1,
            derived_from=new_derived,
            applies_to_entities=new_entities,
            synonyms=new_synonyms,
            scope=new_scope,
            notes=new_notes,
            source=current.source,
            created_at=current.created_at or now,
            updated_at=now,
        )
        self.store.write(
            state_type="glossary_term",
            payload=updated.model_dump(mode="json"),
            version=updated.version,
            project_id=self.project_id,
        )
        return updated

    def deprecate_term(self, term: str) -> GlossaryTerm:
        current = self.get_term(term)
        if not current:
            raise ValueError(f"Term '{term}' not found.")
        if current.status == "deprecated":
            return current
        return self.edit_term(term, status="deprecated")
