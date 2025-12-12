# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import yaml
import logging
from pathlib import Path
from typing import List, Optional, Tuple
from pydantic import ValidationError

from axi.metadata.indexer import MetadataIndexer
from axi.query.engine import SemanticQueryEngine
from axi.queries.models import SavedQuery, SavedQueryFilter

logger = logging.getLogger(__name__)


class SavedQueryStore:
    """
    YAML-backed persistence for saved semantic queries.
    Files live under axi/queries/<id>.yml
    """

    def __init__(self, project_root: Optional[str] = None, indexer: Optional[MetadataIndexer] = None, metadata_dir: Optional[str] = None):
        if project_root:
            self.project_root = os.path.abspath(project_root)
        else:
            self.project_root = self._find_project_root()
        metadata_path = metadata_dir or os.path.join(self.project_root, "axi", "metadata")
        self.indexer = indexer or MetadataIndexer(metadata_path)
        self.queries_dir = os.path.join(self.project_root, "axi", "queries")
        os.makedirs(self.queries_dir, exist_ok=True)
        self.engine = SemanticQueryEngine(self.indexer)

    def _find_project_root(self) -> str:
        current = os.getcwd()
        while current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, "axi.yml")):
                return current
            current = os.path.dirname(current)
        return os.getcwd()

    def _path_for(self, query_id: str) -> Path:
        safe_id = query_id.replace("/", "_").replace("\\", "_")
        return Path(self.queries_dir) / f"{safe_id}.yml"

    def _load_file(self, path: Path) -> SavedQuery:
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        query = SavedQuery(**data)
        if path.stem != query.id:
            raise ValueError(f"Saved query id '{query.id}' must match filename '{path.stem}'")
        return query

    def _validate_semantics(self, query: SavedQuery) -> Tuple[bool, Optional[str]]:
        if not self.indexer.get_entity(query.entity):
            return False, f"Entity '{query.entity}' not found"
        # Validate metrics exist
        for m in query.metrics:
            if not self.indexer.get_metric(m):
                return False, f"Metric '{m}' not found"
        # Validate dimensions using allowed list when present
        try:
            allowed_sets = []
            for m in query.metrics:
                allowed = set(self.engine.get_allowed_dimensions_for_metric(m))
                if allowed:
                    allowed_sets.append(allowed)
            if allowed_sets:
                common = set.intersection(*allowed_sets) if len(allowed_sets) > 1 else allowed_sets[0]
                for d in query.dimensions:
                    if common and d not in common:
                        return False, f"Dimension '{d}' not valid for all metrics"
        except Exception as exc:
            logger.debug("Dimension validation skipped: %s", exc)
        return True, None

    def list_queries(self) -> List[SavedQuery]:
        queries: List[SavedQuery] = []
        for path in sorted(Path(self.queries_dir).glob("*.yml")):
            try:
                q = self._load_file(path)
                queries.append(q)
            except Exception as exc:
                logger.warning("Skipping invalid saved query %s: %s", path, exc)
                continue
        return queries

    def get_query(self, query_id: str) -> Optional[SavedQuery]:
        path = self._path_for(query_id)
        if not path.exists():
            return None
        try:
            return self._load_file(path)
        except (ValidationError, ValueError) as exc:
            raise ValueError(f"Invalid saved query: {exc}") from exc

    def save_query(self, query: SavedQuery) -> SavedQuery:
        valid, err = self._validate_semantics(query)
        if not valid:
            raise ValueError(err or "Invalid saved query")
        path = self._path_for(query.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            yaml.safe_dump(query.model_dump(), f, sort_keys=False)
        return query

    def delete_query(self, query_id: str) -> bool:
        path = self._path_for(query_id)
        if not path.exists():
            return False
        path.unlink()
        return True
