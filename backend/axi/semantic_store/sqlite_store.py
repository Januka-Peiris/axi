# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from typing import Iterable, Optional

from .base import SemanticStore, Predicate
from .models import SemanticState


class SQLiteSemanticStore(SemanticStore):
    """
    SQLite-backed semantic store for local/offline workflows.
    JSON payloads are stored as TEXT but kept unmodified.
    """

    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS semantic_state (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              state_type TEXT NOT NULL,
              version INTEGER NOT NULL,
              payload TEXT NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_state_project_type_version "
            "ON semantic_state(project_id, state_type, version)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_semantic_state_payload_json ON semantic_state(id)"
        )
        self.conn.commit()

    def write(
        self,
        state_type: str,
        payload: dict,
        version: int,
        project_id: str,
        state_id: Optional[str] = None,
    ) -> SemanticState:
        # Generate deterministic ID from content if not provided
        if not state_id:
            content_hash = hashlib.sha256(
                f"{project_id}:{state_type}:{version}:{json.dumps(payload, sort_keys=True)}".encode()
            ).hexdigest()[:32]
            state_id = content_hash
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO semantic_state (id, project_id, state_type, version, payload)
            VALUES (?, ?, ?, ?, ?)
            """,
            (state_id, project_id, state_type, version, json.dumps(payload)),
        )
        self.conn.commit()
        return SemanticState(
            id=state_id,
            project_id=project_id,
            state_type=state_type,
            version=version,
            payload=payload,
            created_at=datetime.utcnow(),
        )

    def read_latest(self, state_type: str, project_id: str) -> Optional[SemanticState]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT id, project_id, state_type, version, payload, created_at
            FROM semantic_state
            WHERE project_id = ? AND state_type = ?
            ORDER BY version DESC, created_at DESC
            LIMIT 1
            """,
            (project_id, state_type),
        )
        row = cur.fetchone()
        if not row:
            return None
        return SemanticState(
            id=row[0],
            project_id=row[1],
            state_type=row[2],
            version=row[3],
            payload=json.loads(row[4]) if row[4] else {},
            created_at=datetime.fromisoformat(row[5]) if row[5] else None,
        )

    def query(
        self,
        state_type: Optional[str] = None,
        project_id: Optional[str] = None,
        predicate: Optional[Predicate] = None,
    ) -> Iterable[SemanticState]:
        cur = self.conn.cursor()
        sql = "SELECT id, project_id, state_type, version, payload, created_at FROM semantic_state WHERE 1=1"
        params = []
        if state_type:
            sql += " AND state_type = ?"
            params.append(state_type)
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        cur.execute(sql, tuple(params))
        for row in cur.fetchall():
            state = SemanticState(
                id=row[0],
                project_id=row[1],
                state_type=row[2],
                version=row[3],
                payload=json.loads(row[4]) if row[4] else {},
                created_at=datetime.fromisoformat(row[5]) if row[5] else None,
            )
            if predicate and not predicate(state):
                continue
            yield state

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
