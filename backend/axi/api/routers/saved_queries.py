# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import snowflake.connector
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError, Field, field_validator

from axi.config.settings import get_settings
from axi.utils.logging_config import get_logger
from axi.queries.store import SavedQueryStore
from axi.queries.models import SavedQuery, SavedQueryFilter
from axi.api.routers.query import _validate_metrics, _validate_grain_compatibility, _generate_sql_for_metrics
from axi.query.engine import SemanticQueryEngine
from axi.exceptions import QueryError, ValidationError, MetadataError
from axi.execution.snowflake_runner import SnowflakeRunner

router = APIRouter(prefix="/api/saved_queries", tags=["saved_queries"])
settings = get_settings()
logger = get_logger(__name__)


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
    
    @field_validator('override_limit')
    @classmethod
    def validate_limit(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 1 or v > 10000):
            from axi.exceptions import ValidationError
            raise ValidationError("Limit must be between 1 and 10000", code="INVALID_LIMIT")
        return v


@router.get("")
def list_saved_queries():
    logger.debug("Listing saved queries")
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
    logger.debug(f"Getting saved query: {query_id}")
    # Sanitize query_id
    from axi.utils.sanitization import sanitize_string
    query_id = sanitize_string(query_id, max_length=255)
    
    store = _get_store()
    try:
        query = store.get_query(query_id)
    except ValueError as exc:
        logger.warning(f"Invalid saved query ID: {exc}")
        raise HTTPException(status_code=400, detail=ValidationError(str(exc), code="INVALID_SAVED_QUERY").to_dict())
    if not query:
        raise HTTPException(status_code=404, detail=MetadataError("Saved query not found", code="SAVED_QUERY_NOT_FOUND").to_dict())
    return query


@router.post("")
def create_or_update_saved_query(payload: SavedQuery):
    logger.info(f"Creating/updating saved query: {payload.id}")
    store = _get_store()
    try:
        saved = store.save_query(payload)
        logger.info(f"Successfully saved query: {payload.id}")
        return saved
    except ValidationError as exc:
        logger.warning(f"Validation error saving query: {exc}")
        raise HTTPException(status_code=400, detail=ValidationError(str(exc), code="INVALID_SAVED_QUERY").to_dict())
    except ValueError as exc:
        logger.warning(f"Value error saving query: {exc}")
        raise HTTPException(status_code=400, detail=ValidationError(str(exc), code="INVALID_SAVED_QUERY").to_dict())


@router.delete("/{query_id}")
def delete_saved_query(query_id: str):
    logger.info(f"Deleting saved query: {query_id}")
    # Sanitize query_id
    from axi.utils.sanitization import sanitize_string
    query_id = sanitize_string(query_id, max_length=255)
    
    store = _get_store()
    deleted = store.delete_query(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=MetadataError("Saved query not found", code="SAVED_QUERY_NOT_FOUND").to_dict())
    logger.info(f"Successfully deleted query: {query_id}")
    return {"status": "deleted"}


@router.post("/{query_id}/run")
def run_saved_query(query_id: str, req: RunSavedQueryRequest = RunSavedQueryRequest()):
    logger.info(f"Running saved query: {query_id}")
    # Sanitize query_id
    from axi.utils.sanitization import sanitize_string
    query_id = sanitize_string(query_id, max_length=255)
    
    store = _get_store()
    try:
        saved = store.get_query(query_id)
    except ValueError as exc:
        logger.warning(f"Invalid saved query ID: {exc}")
        raise HTTPException(status_code=400, detail=ValidationError(str(exc), code="INVALID_SAVED_QUERY").to_dict())
    if not saved:
        raise HTTPException(status_code=404, detail=MetadataError("Saved query not found", code="SAVED_QUERY_NOT_FOUND").to_dict())

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
            logger.error(f"Snowflake connection error: {e}")
            raise HTTPException(status_code=500, detail={"code": "SNOWFLAKE_CONNECTION_ERR", "message": str(e)})
    except QueryError as se:
        logger.warning(f"Query error running saved query: {se}")
        raise HTTPException(status_code=400, detail=se.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error running saved query: {e}")
        raise HTTPException(status_code=400, detail=QueryError(f"Failed to run saved query: {e}", code="SAVED_QUERY_RUN_ERROR").to_dict())
