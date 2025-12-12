# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import snowflake.connector
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from axi.config.settings import get_settings
from axi.queries.store import SavedQueryStore
from axi.queries.models import SavedQuery, SavedQueryFilter
from axi.api.routers.query import _validate_metrics, _validate_grain_compatibility, _generate_sql_for_metrics
from axi.query.engine import SemanticQueryEngine
from axi.execution.snowflake_runner import SnowflakeRunner

router = APIRouter(prefix="/api/saved_queries", tags=["saved_queries"])
settings = get_settings()


def _find_project_root() -> str:
    current = os.getcwd()
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "axi.yml")):
            return current
        current = os.path.dirname(current)
    return os.getcwd()


def _get_store() -> SavedQueryStore:
    project_root = _find_project_root()
    return SavedQueryStore(project_root=project_root, metadata_dir=settings.AXI_METADATA_DIR)


class RunSavedQueryRequest(BaseModel):
    override_filters: Optional[List[SavedQueryFilter]] = None
    override_limit: Optional[int] = None


@router.get("")
def list_saved_queries():
    store = _get_store()
    queries = store.list_queries()
    # Return summary
    return [
        {
            "id": q.id,
            "name": q.name,
            "description": q.description,
            "entity": q.entity,
            "metrics": q.metrics,
            "dimensions": q.dimensions,
            "tags": q.tags,
        }
        for q in queries
    ]


@router.get("/{query_id}")
def get_saved_query(query_id: str):
    store = _get_store()
    try:
        query = store.get_query(query_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SAVED_QUERY", "message": str(exc)})
    if not query:
        raise HTTPException(status_code=404, detail={"code": "SAVED_QUERY_NOT_FOUND", "message": "Saved query not found"})
    return query


@router.post("")
def create_or_update_saved_query(payload: SavedQuery):
    store = _get_store()
    try:
        saved = store.save_query(payload)
        return saved
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SAVED_QUERY", "message": str(exc)})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SAVED_QUERY", "message": str(exc)})


@router.delete("/{query_id}")
def delete_saved_query(query_id: str):
    store = _get_store()
    deleted = store.delete_query(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"code": "SAVED_QUERY_NOT_FOUND", "message": "Saved query not found"})
    return {"status": "deleted"}


@router.post("/{query_id}/run")
def run_saved_query(query_id: str, req: RunSavedQueryRequest = RunSavedQueryRequest()):
    store = _get_store()
    try:
        saved = store.get_query(query_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "INVALID_SAVED_QUERY", "message": str(exc)})
    if not saved:
        raise HTTPException(status_code=404, detail={"code": "SAVED_QUERY_NOT_FOUND", "message": "Saved query not found"})

    filters = list(saved.filters or [])
    if req.override_filters:
        filters.extend(req.override_filters)
    limit = req.override_limit or saved.limit or 500

    engine = SemanticQueryEngine(store.indexer)

    try:
        validated_metrics = _validate_metrics(engine, saved.metrics)
        _validate_grain_compatibility(engine, validated_metrics)
        sql = _generate_sql_for_metrics(
            engine,
            saved.metrics,
            saved.dimensions,
            filters,
            dialect="snowflake"
        )

        final_sql = f"{sql.rstrip(';')}\nLIMIT {limit}"
        runner = SnowflakeRunner()
        try:
            rows, cols, elapsed = runner.execute_query(final_sql)
            rows_list = [[row.get(c) for c in cols] for row in rows]
            return {
                "sql": final_sql,
                "columns": cols,
                "rows": rows_list,
                "generated_at": saved.id,
                "execution_ms": elapsed,
                "entity": saved.entity,
                "metrics": saved.metrics,
                "dimensions": saved.dimensions,
            }
        except ValueError as ve:
            raise HTTPException(status_code=400, detail={"code": "NO_SNOWFLAKE_CREDENTIALS", "message": str(ve)})
        except snowflake.connector.errors.ProgrammingError as pe:  # type: ignore
            raise HTTPException(status_code=400, detail={"code": "SQL_SYNTAX_ERROR", "message": str(pe)})
        except snowflake.connector.errors.DatabaseError as de:  # type: ignore
            raise HTTPException(status_code=401, detail={"code": "SNOWFLAKE_AUTH_FAILED", "message": str(de)})
        except Exception as e:
            raise HTTPException(status_code=500, detail={"code": "SNOWFLAKE_CONNECTION_ERR", "message": str(e)})
    except SemanticQueryEngine.SemanticError as se:  # type: ignore
        raise HTTPException(status_code=400, detail={"code": se.code, "message": str(se), "hint": se.hint})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail={"code": "METRIC_INVALID", "message": str(e)})

