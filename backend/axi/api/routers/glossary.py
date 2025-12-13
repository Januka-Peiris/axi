# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import APIRouter, HTTPException
from typing import List
from axi.config.settings import get_settings
from axi.glossary.glossary_store import GlossaryStore
from axi.glossary.glossary_models import GlossaryEntity, GlossaryMetric, GlossaryDimension
from axi.utils.logging_config import get_logger
from axi.exceptions import MetadataError, ValidationError

router = APIRouter(prefix="/api/glossary", tags=["glossary"])
settings = get_settings()
logger = get_logger(__name__)

@router.get("/")
def glossary_status():
    logger.debug("Getting glossary status")
    store = GlossaryStore()
    gl = store.load_from_json()
    if not gl:
        return {"status": "not_generated"}
    return {
        "status": "available",
        "generated_at": gl.generated_at,
        "counts": {
            "entities": len(gl.entities),
            "metrics": len(gl.metrics),
            "dimensions": len(gl.dimensions),
            "relationships": len(gl.relationships)
        }
    }

@router.get("/entities", response_model=List[GlossaryEntity])
def list_entities():
    logger.debug("Listing glossary entities")
    store = GlossaryStore()
    return store.list_entities()

@router.get("/entities/{name}", response_model=GlossaryEntity)
def get_entity(name: str):
    logger.debug(f"Getting glossary entity: {name}")
    # Validate entity name
    from axi.utils.sanitization import sanitize_string
    name = sanitize_string(name, max_length=255)
    
    store = GlossaryStore()
    ent = store.get_entity(name)
    if not ent:
        raise HTTPException(status_code=404, detail=MetadataError(f"Entity '{name}' not found", code="ENTITY_NOT_FOUND").to_dict())
    return ent

@router.get("/metrics", response_model=List[GlossaryMetric])
def list_metrics():
    logger.debug("Listing glossary metrics")
    store = GlossaryStore()
    return store.list_metrics()

@router.get("/metrics/{name}", response_model=GlossaryMetric)
def get_metric(name: str):
    logger.debug(f"Getting glossary metric: {name}")
    # Validate metric name
    from axi.utils.sanitization import validate_metric_name
    try:
        validated_name = validate_metric_name(name)
    except ValueError as ve:
        raise ValidationError(str(ve), code="INVALID_METRIC_NAME")
    
    store = GlossaryStore()
    met = store.get_metric(validated_name)
    if not met:
        raise HTTPException(status_code=404, detail=MetadataError(f"Metric '{validated_name}' not found", code="METRIC_NOT_FOUND").to_dict())
    return met

@router.get("/dimensions", response_model=List[GlossaryDimension])
def list_dimensions():
    logger.debug("Listing glossary dimensions")
    store = GlossaryStore()
    return store.list_dimensions()

@router.get("/dimensions/{name}", response_model=GlossaryDimension)
def get_dimension(name: str):
    logger.debug(f"Getting glossary dimension: {name}")
    # Validate dimension name
    from axi.utils.sanitization import validate_dimension_name
    try:
        validated_name = validate_dimension_name(name)
    except ValueError as ve:
        raise ValidationError(str(ve), code="INVALID_DIMENSION_NAME")
    
    store = GlossaryStore()
    dim = store.get_dimension(validated_name)
    if not dim:
        raise HTTPException(status_code=404, detail=MetadataError(f"Dimension '{validated_name}' not found", code="DIMENSION_NOT_FOUND").to_dict())
    return dim

@router.get("/search")
def search_glossary(q: str):
    logger.debug(f"Searching glossary: {q}")
    # Sanitize search query
    from axi.utils.sanitization import sanitize_string
    q = sanitize_string(q, max_length=100)
    
    store = GlossaryStore()
    return store.search(q)

@router.post("/generate")
def generate_glossary():
    """
    Generate glossary from current metadata index.
    This populates the glossary with entities, metrics, dimensions, and relationships.
    """
    logger.info("Generating glossary")
    try:
        from axi.glossary.glossary_generator import GlossaryGenerator
        generator = GlossaryGenerator()
        glossary = generator.generate()
        
        store = GlossaryStore()
        store.save(glossary)
        
        logger.info(f"Successfully generated glossary: {len(glossary.entities)} entities, {len(glossary.metrics)} metrics, {len(glossary.dimensions)} dimensions")
        return {
            "status": "success",
            "generated_at": glossary.generated_at,
            "counts": {
                "entities": len(glossary.entities),
                "metrics": len(glossary.metrics),
                "dimensions": len(glossary.dimensions),
                "relationships": len(glossary.relationships)
            }
        }
    except MetadataError as e:
        logger.error(f"Metadata error generating glossary: {e}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error generating glossary: {e}")
        raise HTTPException(status_code=500, detail=MetadataError(f"Failed to generate glossary: {e}", code="GLOSSARY_GENERATION_ERROR").to_dict())
