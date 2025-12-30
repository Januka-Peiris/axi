# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import json
import uuid
from datetime import datetime
from typing import Iterable, Optional

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError as exc:
    raise ImportError(
        "psycopg2-binary is required for PostgresSemanticStore. "
        "Install with `pip install psycopg2-binary` or use AXI_STORAGE=sqlite."
    ) from exc

from .base import SemanticStore, Predicate
from .models import SemanticState


class PostgresSemanticStore(SemanticStore):
    """
    Postgres-backed semantic store using JSONB payloads.
    """

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.conn = psycopg2.connect(self.db_url)
        self.conn.autocommit = True
        self.ensure_schema()

    def ensure_schema(self) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_state (
                  id UUID PRIMARY KEY,
                  project_id TEXT NOT NULL,
                  state_type TEXT NOT NULL,
                  version INTEGER NOT NULL,
                  payload JSONB NOT NULL,
                  created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_state_project_type_version "
                "ON semantic_state(project_id, state_type, version)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_state_payload_gin "
                "ON semantic_state USING GIN (payload jsonb_path_ops)"
            )

    def write(
        self,
        state_type: str,
        payload: dict,
        version: int,
        project_id: str,
        state_id: Optional[str] = None,
    ) -> SemanticState:
        state_id = state_id or str(uuid.uuid4())
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO semantic_state (id, project_id, state_type, version, payload)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET project_id = EXCLUDED.project_id,
                    state_type = EXCLUDED.state_type,
                    version = EXCLUDED.version,
                    payload = EXCLUDED.payload
                """,
                (state_id, project_id, state_type, version, json.dumps(payload)),
            )
        return SemanticState(
            id=state_id,
            project_id=project_id,
            state_type=state_type,
            version=version,
            payload=payload,
            created_at=datetime.utcnow(),
        )

    def read_latest(self, state_type: str, project_id: str) -> Optional[SemanticState]:
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, project_id, state_type, version, payload, created_at
                FROM semantic_state
                WHERE project_id = %s AND state_type = %s
                ORDER BY version DESC, created_at DESC
                LIMIT 1
                """,
                (project_id, state_type),
            )
            row = cur.fetchone()
            if not row:
                return None
            return SemanticState(
                id=str(row["id"]),
                project_id=row["project_id"],
                state_type=row["state_type"],
                version=row["version"],
                payload=row["payload"] or {},
                created_at=row.get("created_at"),
            )

    def query(
        self,
        state_type: Optional[str] = None,
        project_id: Optional[str] = None,
        predicate: Optional[Predicate] = None,
    ) -> Iterable[SemanticState]:
        clauses = []
        params = []
        if state_type:
            clauses.append("state_type = %s")
            params.append(state_type)
        if project_id:
            clauses.append("project_id = %s")
            params.append(project_id)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        sql = f"""
        SELECT id, project_id, state_type, version, payload, created_at
        FROM semantic_state
        {where}
        ORDER BY created_at ASC
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            for row in cur.fetchall():
                state = SemanticState(
                    id=str(row["id"]),
                    project_id=row["project_id"],
                    state_type=row["state_type"],
                    version=row["version"],
                    payload=row["payload"] or {},
                    created_at=row.get("created_at"),
                )
                if predicate and not predicate(state):
                    continue
                yield state

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
