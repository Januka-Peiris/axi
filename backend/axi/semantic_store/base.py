# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from abc import ABC, abstractmethod
from typing import Callable, Iterable, Optional

from .models import SemanticState

Predicate = Callable[[SemanticState], bool]


class SemanticStore(ABC):
    """
    JSON-first semantic state store.
    Implementations must keep payload as JSON/JSONB and avoid over-normalization.
    """

    @abstractmethod
    def write(
        self,
        state_type: str,
        payload: dict,
        version: int,
        project_id: str,
        state_id: Optional[str] = None,
    ) -> SemanticState:
        ...

    @abstractmethod
    def read_latest(self, state_type: str, project_id: str) -> Optional[SemanticState]:
        ...

    @abstractmethod
    def query(
        self,
        state_type: Optional[str] = None,
        project_id: Optional[str] = None,
        predicate: Optional[Predicate] = None,
    ) -> Iterable[SemanticState]:
        ...

    @abstractmethod
    def ensure_schema(self) -> None:
        ...
