# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from axi.metadata.indexer import MetadataIndexer
from axi.config.settings import get_settings
from axi.utils.logging_config import get_logger
from axi.exceptions import DatabaseError, MetadataError

router = APIRouter(prefix="/api/promotion", tags=["promotion"])
logger = get_logger(__name__)

def _get_indexer() -> MetadataIndexer:
    settings = get_settings()
    return MetadataIndexer(settings.AXI_METADATA_DIR)

@router.get("")
def get_promotion_dashboard():
    """
    Get promotion dashboard data including summary and all promotion results.
    """
    logger.debug("Getting promotion dashboard")
    indexer = _get_indexer()
    
    try:
        # Get summary
        summary = indexer.get_promotion_summary()
        
        # Get all results grouped by status
        all_results = indexer.list_promotion_results()
        
        promoted = [r for r in all_results if r.get('status') == 'promoted']
        ignored = [r for r in all_results if r.get('status') == 'ignored']
        errors = [r for r in all_results if r.get('status') == 'error']
        
        # Generate warnings
        warnings = []
        if summary['counts']['promoted'] == 0:
            warnings.append({
                "type": "no_promoted",
                "message": "No models promoted — check promotion rules.",
                "help": "Update your promotion rules in axi.yml and re-run: axi extract"
            })
        
        if summary.get('extraction_mode') == 'dbt' and summary['counts']['total_scanned'] == 0:
            warnings.append({
                "type": "no_models_scanned",
                "message": "No models were scanned. Make sure you've run 'dbt compile' first.",
                "help": "Run: dbt compile && axi extract"
            })
        
        logger.debug(f"Promotion dashboard: {len(promoted)} promoted, {len(ignored)} ignored, {len(errors)} errors")
        return {
            **summary,
            "promoted": promoted,
            "ignored": ignored,
            "errors": errors,
            "warnings": warnings
        }
    except DatabaseError as e:
        logger.warning(f"Database error loading promotion dashboard: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error loading promotion dashboard: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to load promotion data: {e}", code="PROMOTION_DASHBOARD_ERROR").to_dict())

@router.get("/summary")
def get_promotion_summary():
    """Get just the promotion summary statistics."""
    logger.debug("Getting promotion summary")
    indexer = _get_indexer()
    try:
        return indexer.get_promotion_summary()
    except DatabaseError as e:
        logger.warning(f"Database error loading promotion summary: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error loading promotion summary: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to load promotion summary: {e}", code="PROMOTION_SUMMARY_ERROR").to_dict())

