# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from axi.metadata.indexer import MetadataIndexer
from axi.config.settings import get_settings

router = APIRouter(prefix="/api/promotion", tags=["promotion"])

def _get_indexer() -> MetadataIndexer:
    settings = get_settings()
    return MetadataIndexer(settings.AXI_METADATA_DIR)

@router.get("")
def get_promotion_dashboard():
    """
    Get promotion dashboard data including summary and all promotion results.
    """
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
        
        return {
            **summary,
            "promoted": promoted,
            "ignored": ignored,
            "errors": errors,
            "warnings": warnings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load promotion data: {str(e)}")

@router.get("/summary")
def get_promotion_summary():
    """Get just the promotion summary statistics."""
    indexer = _get_indexer()
    try:
        return indexer.get_promotion_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load promotion summary: {str(e)}")

