# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import APIRouter, HTTPException
from typing import List
from axi.config.settings import get_settings
from axi.glossary.glossary_store import GlossaryStore
from axi.glossary.glossary_models import GlossaryEntity, GlossaryMetric, GlossaryDimension

router = APIRouter(prefix="/api/glossary", tags=["glossary"])
settings = get_settings()

@router.get("/")
def glossary_status():
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
    store = GlossaryStore()
    return store.list_entities()

@router.get("/entities/{name}", response_model=GlossaryEntity)
def get_entity(name: str):
    store = GlossaryStore()
    ent = store.get_entity(name)
    if not ent:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ent

@router.get("/metrics", response_model=List[GlossaryMetric])
def list_metrics():
    store = GlossaryStore()
    return store.list_metrics()

@router.get("/metrics/{name}", response_model=GlossaryMetric)
def get_metric(name: str):
    store = GlossaryStore()
    met = store.get_metric(name)
    if not met:
        raise HTTPException(status_code=404, detail="Metric not found")
    return met

@router.get("/dimensions", response_model=List[GlossaryDimension])
def list_dimensions():
    store = GlossaryStore()
    return store.list_dimensions()

@router.get("/dimensions/{name}", response_model=GlossaryDimension)
def get_dimension(name: str):
    store = GlossaryStore()
    dim = store.get_dimension(name)
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    return dim

@router.get("/search")
def search_glossary(q: str):
    store = GlossaryStore()
    return store.search(q)

@router.post("/generate")
def generate_glossary():
    """
    Generate glossary from current metadata index.
    This populates the glossary with entities, metrics, dimensions, and relationships.
    """
    try:
        from axi.glossary.glossary_generator import GlossaryGenerator
        generator = GlossaryGenerator()
        glossary = generator.generate()
        
        store = GlossaryStore()
        store.save(glossary)
        
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
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"Failed to generate glossary: {str(e)}")
