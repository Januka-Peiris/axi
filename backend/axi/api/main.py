# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, List, Optional, Union
import os, glob, json
import logging
import sqlite3
import snowflake.connector
import yaml

from axi.config.loader import load_config
from axi.extractor.promotion import PromotionEngine
from axi.extractor.scanner import SqlScanner
from axi.extractor.core import extract_metadata
from axi.metadata.writer import MetadataWriter
from axi.metadata.indexer import MetadataIndexer
from axi.query.graph import SemanticGraph
from axi.query.engine import SemanticQueryEngine
from axi.execution.snowflake_runner import SnowflakeRunner
from axi.config.settings import get_settings
from axi.version import get_version as get_backend_version
from axi.utils.logging_config import setup_logging, get_logger
from axi.utils.sanitization import (
    validate_metric_name,
    validate_dimension_name,
    sanitize_string,
    sanitize_path
)
from axi.exceptions import (
    AXIBaseException,
    ValidationError,
    MetadataError,
    QueryError,
    DatabaseError,
    ConfigurationError
)

# Load .env files before initializing settings
from axi.config.env_loader import load_env_file
load_env_file()

settings = get_settings()

# Initialize logging on module import
setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file,
    json_format=settings.log_json
)
logger = get_logger(__name__)

app = FastAPI(title="AXI Semantic Layer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from axi.api.error_handlers import register_axi_exception_handlers
register_axi_exception_handlers(app)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "AXI Semantic Layer"}

@app.get("/version")
def version():
    return {"version": get_backend_version()}

# Plugin Init
from axi.plugins.loader import PluginLoader
from axi.plugins.registry import API_ROUTERS_REGISTRY
from axi.api.routers import glossary
from axi.api.routers import dimensions
from axi.api.routers import metrics
from axi.api.routers import query
from axi.api.routers import promotion
from axi.api.routers import saved_queries
from axi.api.routers import roi

plugin_loader = PluginLoader(["./plugins", os.path.expanduser("~/.axi/plugins")])
plugin_loader.load_plugins()

app.include_router(glossary.router)
app.include_router(dimensions.router)
app.include_router(metrics.router)
app.include_router(query.router)
app.include_router(promotion.router)
app.include_router(saved_queries.router)
app.include_router(roi.router)

for router in API_ROUTERS_REGISTRY:
    app.include_router(router)

class QueryRequest(BaseModel):
    metric: str = Field(..., min_length=1, description="Metric name")
    dimensions: List[str] = Field(default_factory=list, description="List of dimension names")
    filters: List[Union[str, Dict[str, Any]]] = Field(default_factory=list, description="List of filter strings or objects")
    
    @field_validator('metric')
    @classmethod
    def validate_metric(cls, v: str) -> str:
        return validate_metric_name(v)
    
    @field_validator('dimensions')
    @classmethod
    def validate_dimensions(cls, v: List[str]) -> List[str]:
        validated = []
        for dim in v:
            if not dim or not dim.strip():
                continue
            validated.append(validate_dimension_name(dim))
        return validated

class RunRequest(BaseModel):
    sql: str
    limit: int = 500

class ExtractRequest(BaseModel):
    path: str = Field(..., min_length=1, description="Path to directory containing SQL files")
    
    @field_validator('path')
    @classmethod
    def validate_path(cls, v: str) -> str:
        return sanitize_path(v)

@app.get("/health")
def health():
    snowflake_ok = None
    try:
        runner = SnowflakeRunner()
        snowflake_ok = runner.test_connection()
    except ValueError as ve:
        # Missing credentials - not an error, just unavailable
        logger.debug(f"Snowflake unavailable: {ve}")
        snowflake_ok = False
    except (snowflake.connector.errors.DatabaseError, snowflake.connector.errors.OperationalError) as e:
        # Connection/auth errors
        logger.debug(f"Snowflake connection error: {e}")
        snowflake_ok = False
    except Exception as e:
        # Unexpected errors
        logger.warning(f"Unexpected error checking Snowflake health: {e}")
        snowflake_ok = False
        # Don't raise - health check should be resilient
    return {"status": "ok", "snowflake": snowflake_ok}

@app.post("/extract")
def extract_metadata_endpoint(req: ExtractRequest):
    base_path = os.path.abspath(req.path)
    if not os.path.exists(base_path):
        raise HTTPException(status_code=404, detail={"code": "PATH_NOT_FOUND", "message": f"Path not found: {base_path}"})
    if not os.path.isdir(base_path):
        raise HTTPException(status_code=400, detail={"code": "INVALID_PATH", "message": f"Path is not a directory: {base_path}"})
        
    # Load config (supports environment-specific files)
    config_path = os.path.join(base_path, "axi.yml")
    try:
        config = load_config(config_path=config_path, env=settings.env)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "CONFIG_NOT_FOUND", "message": f"axi.yml not found at {config_path}"})
    except (yaml.YAMLError, ValueError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_CONFIG", "message": f"Invalid config file: {str(e)}"})
    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error loading config: {e}")
        raise HTTPException(status_code=500, detail=ConfigurationError("Failed to load configuration", code="CONFIG_LOAD_ERROR").to_dict())
    
    promotion_engine = PromotionEngine(config)
    scanner = SqlScanner(base_path, promotion_engine)
    
    metadata_dir = settings.metadata_dir
    writer = MetadataWriter(metadata_dir)
    
    extracted_count = 0
    errors = []
    
    for model in scanner.scan():
        # model.path is relative path, use basename as model name for now
        model_name = os.path.splitext(os.path.basename(model.path))[0]
        try:
            meta = extract_metadata(model.content, model_name)
            if meta.get("grain_status") == "not_detected":
                logger.info(f"[SKIP] {model_name}: no grouping/aggregation detected (treated as staging/non-semantic).")
                continue
            writer.write(meta)
            extracted_count += 1
        except (ValueError, KeyError) as e:
            errors.append(f"Error extracting {model.path}: {str(e)}")
            logger.warning(f"Extraction error for {model.path}: {e}")
        except MetadataError as e:
            errors.append(f"Error extracting {model.path}: {str(e)}")
            logger.warning(f"Metadata error extracting {model.path}: {e}")
        except Exception as e:
            errors.append(f"Error extracting {model.path}: {str(e)}")
            logger.error(f"Unexpected extraction error for {model.path}: {e}")
            
    return {
        "status": "success", 
        "extracted_models": extracted_count, 
        "metadata_dir": os.path.abspath(metadata_dir),
        "errors": errors
    }

# Metrics endpoints are now handled by /api/metrics router

@app.get("/api/models")
def list_models():
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        models = indexer.list_models()
        return models if models else []
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error listing models: {e}")
        return []
    except DatabaseError as e:
        logger.warning(f"Database error listing models: {e}")
        return []
    except MetadataError as e:
        logger.warning(f"Metadata error listing models: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error listing models: {e}")
        return []

# Old /dimensions route removed - use /api/dimensions router instead
# If you need reachable dimensions for a metric, use /api/query/semantic/plan endpoint

@app.get("/relationships")
def list_relationships():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_relationships()

@app.get("/api/entities")
def list_entities():
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        entities = indexer.list_entities()
        return entities if entities else []
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error listing entities: {e}")
        return []
    except DatabaseError as e:
        logger.warning(f"Database error listing entities: {e}")
        return []
    except MetadataError as e:
        logger.warning(f"Metadata error listing entities: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error listing entities: {e}")
        return []

@app.get("/api/entities/{name}")
def get_entity_detail(name: str, include_pruned: bool = False):
    """
    Return entity with dimensions including pruning metadata, plus metrics referencing it and relationships.
    """
    # Sanitize entity name
    name = sanitize_string(name, max_length=255)
    
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    ent = indexer.get_entity(name)
    if not ent:
        raise HTTPException(status_code=404, detail=MetadataError("Entity not found", code="ENTITY_NOT_FOUND").to_dict())

    model_name = ent.get("model") or name
    dim_details = []
    try:
        model_path = os.path.join(indexer.metadata_dir, "models", f"{model_name}.json")
        if os.path.exists(model_path):
            with open(model_path, "r") as f:
                model_json = json.load(f)
                dim_details = model_json.get("dimension_details", [])
    except FileNotFoundError:
        dim_details = []
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in model file {model_path}: {e}")
        dim_details = []
    except (FileNotFoundError, json.JSONDecodeError):
        # Already handled above
        dim_details = []
    except MetadataError as e:
        logger.warning(f"Metadata error reading model file {model_path}: {e}")
        dim_details = []
    except Exception as e:
        logger.warning(f"Unexpected error reading model file {model_path}: {e}")
        dim_details = []

    if not include_pruned:
        dim_details = [d for d in dim_details if d.get("included")]

    # Metrics referencing this entity (by model/entity_name)
    metrics = []
    try:
        all_metrics = indexer.list_metrics()
        for m in all_metrics:
            if m.get("entity_name") == name or m.get("model") == name:
                metrics.append(m.get("name") or m.get("metric"))
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error listing metrics for entity: {e}")
        metrics = []
    except DatabaseError as e:
        logger.warning(f"Database error listing metrics for entity: {e}")
        metrics = []
    except MetadataError as e:
        logger.warning(f"Metadata error listing metrics for entity: {e}")
        metrics = []
    except Exception as e:
        logger.warning(f"Unexpected error listing metrics for entity: {e}")
        metrics = []

    # Relationships
    relationships = indexer.get_entity_relationships(name)

    # Join keys (collect pk/fk from relationships)
    join_keys = []
    for rel in relationships:
        if rel.get("pk_column"):
            join_keys.append(rel["pk_column"])
        if rel.get("fk_column"):
            join_keys.append(rel["fk_column"])
    join_keys = sorted(list({k for k in join_keys if k}))

    # Grain from primary_key
    grain = []
    pk = ent.get("primary_key")
    if pk:
        if isinstance(pk, str):
            grain = [pk]
        elif isinstance(pk, list):
            grain = [p for p in pk if p]

    # Dimensions (names only) as fallback if no dim_details
    dim_names = [d.get("name") or d.get("dimension") for d in dim_details if isinstance(d, dict)]
    dim_names = [d for d in dim_names if d] or [col.get("name") for col in ent.get("columns", []) if isinstance(col, dict)]

    return {
        "name": name,
        "model": model_name,
        "primary_key": ent.get("primary_key"),
        "columns": ent.get("columns", []),
        "dimensions": dim_details,
        "dimension_names": dim_names,
        "type": ent.get("type"),
        "is_read_only": bool(ent.get("is_read_only")),
        "is_staging": bool(ent.get("is_staging")),
        "physical_location": ent.get("physical_location"),
        "schema": ent.get("schema_name"),
        "database": ent.get("database_name"),
        "metrics": metrics,
        "relationships": relationships,
        "join_keys": join_keys,
        "grain": grain
    }

@app.get("/api/graph")
def graph():
    """
    Full global graph - DEBUG ONLY.
    Only accessible when AXI_DEBUG=1 environment variable is set.
    """
    debug_mode = os.getenv("AXI_DEBUG", "0") == "1"
    if not debug_mode:
        return {
            "nodes": [],
            "edges": [],
            "error": "Full graph disabled. Use /api/graph/local, /api/graph/filtered, or /api/graph/category instead."
        }
    
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        sg = SemanticGraph(indexer)
        graph_data = sg.get_graph_json()
        
        # Warn if graph is too large
        if len(graph_data.get("nodes", [])) > 500:
            return {
                "nodes": [],
                "edges": [],
                "error": "Full graph disabled due to size (>500 nodes). Use filtered or local graph modes.",
                "node_count": len(graph_data.get("nodes", []))
            }
        
        return graph_data
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error building graph: {e}")
        return {"nodes": [], "edges": [], "error": "Database error"}
    except DatabaseError as e:
        logger.warning(f"Database error building graph: {e}")
        return {"nodes": [], "edges": [], "error": "Database error"}
    except MetadataError as e:
        logger.warning(f"Metadata error building graph: {e}")
        return {"nodes": [], "edges": [], "error": "Metadata error"}
    except Exception as e:
        logger.error(f"Unexpected error building graph: {e}")
        return {"nodes": [], "edges": [], "error": "Failed to build graph"}

def _graph_nodes_edges(indexer, include_dimensions: bool = True):
    nodes = []
    edges = []
    entities = indexer.list_entities()
    metrics = indexer.list_metrics()
    entity_map = {e.get("name"): e for e in entities}
    promotion_map = {}
    try:
        for pr in indexer.list_promotion_results():
            name = pr.get("name")
            if name:
                promotion_map[name] = pr.get("status")
    except (sqlite3.OperationalError, AttributeError) as e:
        logger.debug(f"Error loading promotion results: {e}")
        promotion_map = {}
    except (DatabaseError, MetadataError) as e:
        logger.debug(f"Error loading promotion results: {e}")
        promotion_map = {}
    except Exception as e:
        logger.warning(f"Unexpected error loading promotion results: {e}")
        promotion_map = {}

    # Entity nodes
    for e in entities:
        nodes.append({
            "id": f"entity.{e.get('name')}",
            "label": e.get("name"),
            "type": "entity",
            "entity_type": e.get("type"),
            "promotion_status": promotion_map.get(e.get("name"))
        })
        if include_dimensions and e.get("columns"):
            for col in e["columns"]:
                if isinstance(col, dict):
                    dim_name = col.get("name")
                    if dim_name:
                        nodes.append({
                            "id": f"dimension.{e.get('name')}.{dim_name}",
                            "label": dim_name,
                            "type": "dimension"
                        })
                        edges.append({
                            "from": f"entity.{e.get('name')}",
                            "to": f"dimension.{e.get('name')}.{dim_name}",
                            "type": "dimension"
                        })

    # Metric nodes + edges to entity
    for m in metrics:
        mname = m.get("name") or m.get("metric")
        if not mname:
            continue
        nodes.append({
            "id": f"metric.{mname}",
            "label": mname,
            "type": "metric"
        })
        ent_name = m.get("entity_name") or m.get("model")
        if ent_name:
            edges.append({
                "from": f"entity.{ent_name}",
                "to": f"metric.{mname}",
                "type": "metric_dep"
            })

    # Entity relationships
    for rel in indexer.list_relationships():
        p = rel.get("parent_model")
        c = rel.get("child_model")
        if p and c:
            edges.append({
                "from": f"entity.{p}",
                "to": f"entity.{c}",
                "type": "join"
            })
    return nodes, edges

def _local_subgraph(node_id: str, depth: int, indexer):
    nodes, edges = _graph_nodes_edges(indexer)
    node_lookup = {n["id"]: n for n in nodes}
    adj = {}
    for e in edges:
        adj.setdefault(e["from"], []).append(e["to"])
        adj.setdefault(e["to"], []).append(e["from"])
    if node_id not in node_lookup:
        return {"nodes": [], "edges": [], "error": {"code": "NODE_NOT_FOUND", "message": f"Node {node_id} not found"}}
    visited = set([node_id])
    q = [(node_id, 0)]
    sub_nodes = {}
    sub_edges = []
    while q:
        nid, d = q.pop(0)
        sub_nodes[nid] = node_lookup.get(nid, {"id": nid, "label": nid, "type": "unknown"})
        if d >= depth:
            continue
        for nbr in adj.get(nid, []):
            edge_matches = [e for e in edges if (e["from"] == nid and e["to"] == nbr) or (e["to"] == nid and e["from"] == nbr)]
            sub_edges.extend(edge_matches)
            if nbr not in visited:
                visited.add(nbr)
                q.append((nbr, d + 1))
    # Sort nodes by id for deterministic ordering
    sorted_nodes = sorted(sub_nodes.values(), key=lambda n: n.get("id", ""))
    sorted_edges = sorted(sub_edges, key=lambda e: (e.get("from", ""), e.get("to", "")))
    return {"nodes": sorted_nodes, "edges": sorted_edges}

# Removed duplicate endpoints - using SemanticGraph-based implementations below

@app.get("/api/graph/categories")
def graph_categories():
    nodes = [
        {"id": "bucket.entities", "label": "Entities", "type": "bucket"},
        {"id": "bucket.metrics", "label": "Metrics", "type": "bucket"},
        {"id": "bucket.dimensions", "label": "Dimensions", "type": "bucket"},
    ]
    edges = [
        {"from": "bucket.entities", "to": "bucket.metrics", "type": "category_relation"},
        {"from": "bucket.entities", "to": "bucket.dimensions", "type": "category_relation"},
    ]
    return {"nodes": nodes, "edges": edges}

@app.get("/api/graph/category_nodes")
def graph_category_nodes(bucket: str, page: int = 1, page_size: int = 50):
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    nodes = []
    if bucket == "entities":
        ents = indexer.list_entities()
        slice_ = ents[(page-1)*page_size: page*page_size]
        for e in slice_:
            nodes.append({"id": f"entity.{e.get('name')}", "label": e.get("name"), "type": "entity"})
    elif bucket == "metrics":
        mets = indexer.list_metrics()
        slice_ = mets[(page-1)*page_size: page*page_size]
        for m in slice_:
            name = m.get("name") or m.get("metric")
            if name:
                nodes.append({"id": f"metric.{name}", "label": name, "type": "metric"})
    elif bucket == "dimensions":
        ents = indexer.list_entities()
        dims = []
        for e in ents:
            for col in e.get("columns") or []:
                if isinstance(col, dict):
                    dims.append({"id": f"dimension.{e.get('name')}.{col.get('name')}", "label": col.get("name"), "type": "dimension"})
        slice_ = dims[(page-1)*page_size: page*page_size]
        nodes.extend(slice_)
    return {"nodes": nodes, "edges": []}

@app.get("/api/graph/local")
def graph_local(node: str, depth: int = 1):
    """
    Get local subgraph around a specific node.
    Query params:
    - node: Node ID/name (required)
    - depth: 1 or 2 (default: 1)
    """
    if not node or not node.strip():
        raise HTTPException(status_code=400, detail={"code": "INVALID_NODE", "message": "Node parameter is required"})
    
    if depth < 1 or depth > 2:
        depth = 1
    
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        sg = SemanticGraph(indexer)
        return sg.get_local_subgraph(node, depth)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "INVALID_NODE", "message": str(ve)})
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error getting local graph: {e}")
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": "Database error"})
    except DatabaseError as e:
        logger.warning(f"Database error getting local graph: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error getting local graph: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to get local graph", code="GRAPH_ERROR").to_dict())

@app.get("/api/graph/filtered")
def graph_filtered(root: Optional[str] = None, depth: int = 2, types: Optional[str] = None):
    """
    Get filtered graph based on root node, depth, and type filters.
    Query params:
    - root: Root node ID (optional)
    - depth: 1, 2, or 3 (default: 2)
    - types: Comma-separated list of node types (optional)
    """
    # Validate depth
    if depth < 1 or depth > 3:
        depth = 2
    
    # Sanitize root and types
    if root:
        root = sanitize_string(root, max_length=255)
    
    node_types = None
    if types:
        node_types = [sanitize_string(t.strip(), max_length=50) for t in types.split(",") if t.strip()]
    
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        sg = SemanticGraph(indexer)
        return sg.get_filtered_graph(root_node=root, depth=depth, node_types=node_types)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "INVALID_FILTER", "message": str(ve)})
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error getting filtered graph: {e}")
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": "Database error"})
    except DatabaseError as e:
        logger.warning(f"Database error getting filtered graph: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error getting filtered graph: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to get filtered graph", code="GRAPH_ERROR").to_dict())

@app.get("/api/graph/category")
def graph_category(type: Optional[str] = None):
    """
    Get category-level graph showing collapsed buckets.
    Query params:
    - type: Category type to filter (optional: entities, metrics, dimensions, models)
    """
    # Sanitize type if provided
    if type:
        type = sanitize_string(type, max_length=50)
    
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        sg = SemanticGraph(indexer)
        return sg.get_category_graph(category_type=type)
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error getting category graph: {e}")
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": "Database error"})
    except DatabaseError as e:
        logger.warning(f"Database error getting category graph: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error getting category graph: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to get category graph", code="GRAPH_ERROR").to_dict())

@app.post("/semantic/sql")
def generate_sql(req: QueryRequest):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    engine = SemanticQueryEngine(indexer)
    try:
        # Pydantic model doesn't have optimize field yet, assuming default True
        sql = engine.generate_sql(req.metric, req.dimensions, req.filters, optimize=True)
        return {"sql": sql}
    except QueryError as se:
        raise HTTPException(
            status_code=400,
            detail={"code": se.code, "message": str(se), "hint": se.hint}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(ve)})
    except Exception as e:
        logger.error(f"Unexpected error generating SQL: {e}")
        raise HTTPException(status_code=500, detail={"code": "SQL_GENERATION_ERROR", "message": "Failed to generate SQL"})

@app.post("/semantic/explain")
def explain_sql(req: QueryRequest):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    engine = SemanticQueryEngine(indexer)
    try:
        # Get raw SQL
        raw_sql = engine.generate_sql(req.metric, req.dimensions, req.filters, optimize=False)
        
        from axi.optimizer.core import Optimizer, OptimizationContext
        from axi.optimizer.rules import get_default_rules
        
        ctx = OptimizationContext(config={"optimizer.rules.snowflake_hints": True}) # Default context
        opt = Optimizer(ctx)
        for rule in get_default_rules():
                opt.add_rule(rule)
        
        return opt.explain(raw_sql)
    except QueryError as se:
        raise HTTPException(
            status_code=400,
            detail={"code": se.code, "message": str(se), "hint": se.hint}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(ve)})
    except QueryError as e:
        logger.warning(f"Query error explaining SQL: {e}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error explaining SQL: {e}")
        raise HTTPException(status_code=500, detail=QueryError("Failed to explain SQL", code="EXPLAIN_ERROR").to_dict())

@app.post("/snowflake/sync")
def snowflake_sync():
    """
    Trigger sync of Snowflake metadata.
    """
    from axi.snowflake.extractor import SnowflakeMetadataExtractor
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    extractor = SnowflakeMetadataExtractor(indexer)
    try:
        extractor.sync()
        return {"status": "success"}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "MISSING_CREDENTIALS", "message": str(ve)})
    except (snowflake.connector.errors.DatabaseError, snowflake.connector.errors.OperationalError) as e:
        raise HTTPException(status_code=401, detail={"code": "SNOWFLAKE_CONNECTION_ERROR", "message": str(e)})
    except DatabaseError as e:
        logger.warning(f"Database error syncing Snowflake: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error syncing Snowflake: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to sync Snowflake metadata", code="SYNC_ERROR").to_dict())

@app.get("/snowflake/tables")
def sf_tables():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_sf_tables()

@app.get("/snowflake/columns")
def sf_columns(table: str):
    # Sanitize table name
    from axi.utils.sanitization import sanitize_identifier
    try:
        table = sanitize_identifier(table)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=ValidationError(str(ve), code="INVALID_TABLE_NAME").to_dict())
    
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_sf_columns(table)

@app.get("/snowflake/policies")
def sf_policies():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_sf_policies()

@app.get("/snowflake/lineage")
def sf_lineage(table: Optional[str] = None):
    # Sanitize table name if provided
    if table:
        from axi.utils.sanitization import sanitize_identifier
        try:
            table = sanitize_identifier(table)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=ValidationError(str(ve), code="INVALID_TABLE_NAME").to_dict())
    
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_sf_lineage(table)

@app.post("/snowflake/explain")
def sf_explain(req: QueryRequest):
    """
    Generate Snowflake-optimized SQL.
    """
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    engine = SemanticQueryEngine(indexer)
    try:
        sql = engine.generate_sql(req.metric, req.dimensions, req.filters, dialect="snowflake")
        return {"sql": sql}
    except QueryError as se:
        raise HTTPException(
            status_code=400,
            detail={"code": se.code, "message": str(se), "hint": se.hint}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(ve)})
    except QueryError as e:
        logger.warning(f"Query error generating Snowflake SQL: {e}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error generating Snowflake SQL: {e}")
        raise HTTPException(status_code=500, detail=QueryError("Failed to generate SQL", code="SQL_GENERATION_ERROR").to_dict())

@app.get("/dbt/models")
def dbt_models():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_dbt_models()

@app.get("/dbt/models/{name}")
def dbt_model(name: str):
    # Sanitize model name
    name = sanitize_string(name, max_length=255)
    
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    m = indexer.get_dbt_model(name)
    if not m:
        raise HTTPException(status_code=404, detail=MetadataError("dbt model not found", code="DBT_MODEL_NOT_FOUND").to_dict())
    return m

@app.get("/dbt/sources")
def dbt_sources():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_dbt_sources()

@app.get("/dbt/tests")
def dbt_tests():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_dbt_tests()

@app.get("/dbt/constraints")
def dbt_constraints(model: str = None):
    # Sanitize model name if provided
    if model:
        model = sanitize_string(model, max_length=255)
    
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_constraints(model)

class ManifestRequest(BaseModel):
    path: str

@app.post("/dbt/manifest")
def load_manifest(req: ManifestRequest):
    """
    Load dbt manifest and map metadata.
    """
    from axi.dbt.manifest_loader import ManifestLoader
    from axi.dbt.semantic_bridge import SemanticBridge
    
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    loader = ManifestLoader(indexer)
    bridge = SemanticBridge(indexer)
    
    try:
        loader.load_manifest(req.path)
        bridge.map_constraints()
        return {"status": "success", "message": "Manifest loaded and constraints mapped"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "MANIFEST_NOT_FOUND", "message": str(e)})
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail={"code": "INVALID_MANIFEST", "message": f"Invalid manifest file: {str(e)}"})
    except MetadataError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error loading manifest: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to load manifest", code="MANIFEST_LOAD_ERROR").to_dict())

class MaterializeRequest(BaseModel):
    metric: str = Field(..., min_length=1, description="Metric name to materialize")
    dimensions: List[str] = Field(default_factory=list, description="List of dimensions")
    refresh: str = Field(default="auto", description="Refresh mode: auto, full, or incremental")
    
    @field_validator('metric')
    @classmethod
    def validate_metric(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Metric name cannot be empty")
        return v.strip()
    
    @field_validator('refresh')
    @classmethod
    def validate_refresh(cls, v: str) -> str:
        allowed = {"auto", "full", "incremental"}
        if v not in allowed:
            raise ValueError(f"Refresh mode must be one of: {', '.join(allowed)}")
        return v

class MartRequest(BaseModel):
    name: str
    metrics: List[str]
    dimensions: List[str]

@app.post("/materialize")
def create_materialization(req: MaterializeRequest):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    from axi.materialization.materializer import Materializer
    mat = Materializer(indexer)
    try:
        return mat.materialize_metric(req.metric, req.dimensions, req.refresh)
    except QueryError as se:
        raise HTTPException(
            status_code=400,
            detail={"code": se.code, "message": str(se), "hint": se.hint}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(ve)})
    except (snowflake.connector.errors.DatabaseError, snowflake.connector.errors.ProgrammingError) as e:
        raise HTTPException(status_code=400, detail={"code": "SNOWFLAKE_ERROR", "message": str(e)})
    except QueryError as e:
        logger.warning(f"Query error materializing metric: {e}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error materializing metric: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to materialize metric", code="MATERIALIZATION_ERROR").to_dict())

@app.post("/materialize/refresh")
def refresh_materialization(req: MaterializeRequest):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    from axi.materialization.materializer import Materializer
    mat = Materializer(indexer)
    try:
        return mat.materialize_metric(req.metric, req.dimensions, "auto")
    except QueryError as se:
        raise HTTPException(
            status_code=400,
            detail={"code": se.code, "message": str(se), "hint": se.hint}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(ve)})
    except (snowflake.connector.errors.DatabaseError, snowflake.connector.errors.ProgrammingError) as e:
        raise HTTPException(status_code=400, detail={"code": "SNOWFLAKE_ERROR", "message": str(e)})
    except QueryError as e:
        logger.warning(f"Query error refreshing materialization: {e}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error refreshing materialization: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to refresh materialization", code="MATERIALIZATION_ERROR").to_dict())

@app.post("/mart")
def create_mart(req: MartRequest):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    from axi.materialization.materializer import Materializer
    mat = Materializer(indexer)
    try:
        return mat.create_mart(req.name, req.metrics, req.dimensions)
    except QueryError as se:
        raise HTTPException(
            status_code=400,
            detail={"code": se.code, "message": str(se), "hint": se.hint}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": str(ve)})
    except (snowflake.connector.errors.DatabaseError, snowflake.connector.errors.ProgrammingError) as e:
        raise HTTPException(status_code=400, detail={"code": "SNOWFLAKE_ERROR", "message": str(e)})
    except QueryError as e:
        logger.warning(f"Query error creating mart: {e}")
        raise HTTPException(status_code=400, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error creating mart: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to create mart", code="MART_CREATION_ERROR").to_dict())

@app.get("/cache")
def get_cache_stats():
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        conn = indexer._get_conn()
        c = conn.cursor()
        c.execute("SELECT count(*) FROM cache_entries")
        count = c.fetchone()[0]
        conn.close()
        return {"entries": count}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error getting cache stats: {e}")
        return {"entries": 0}
    except DatabaseError as e:
        logger.warning(f"Database error getting cache stats: {e}")
        return {"entries": 0}
    except Exception as e:
        logger.error(f"Unexpected error getting cache stats: {e}")
        return {"entries": 0}

@app.delete("/cache")
def clear_cache(metric: str = None):
    # Sanitize metric name if provided
    if metric:
        try:
            metric = validate_metric_name(metric)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=ValidationError(str(ve), code="INVALID_METRIC_NAME").to_dict())
    
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        from axi.cache.query_cache import QueryCache
        cache = QueryCache(indexer)
        cache.clear(metric)
        return {"status": "cleared"}
    except DatabaseError as e:
        raise HTTPException(status_code=500, detail=e.to_dict())
    except sqlite3.OperationalError as e:
        logger.warning(f"Database error clearing cache: {e}")
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": "Failed to clear cache"})
    except DatabaseError as e:
        logger.warning(f"Database error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=e.to_dict())
    except Exception as e:
        logger.error(f"Unexpected error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=MetadataError("Failed to clear cache", code="CACHE_ERROR").to_dict())

def run():
    """Run the API server."""
    import uvicorn
    uvicorn.run(
        "axi.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )

if __name__ == "__main__":
    run()
