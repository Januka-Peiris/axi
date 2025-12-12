# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import os, glob, json

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

settings = get_settings()

app = FastAPI(title="AXI Semantic Layer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "AXI Semantic Layer"}

# Plugin Init
from axi.plugins.loader import PluginLoader
from axi.plugins.registry import API_ROUTERS_REGISTRY
from axi.api.routers import glossary
from axi.api.routers import dimensions
from axi.api.routers import metrics
from axi.api.routers import query
from axi.api.routers import promotion
from axi.api.routers import saved_queries

plugin_loader = PluginLoader(["./plugins", os.path.expanduser("~/.axi/plugins")])
plugin_loader.load_plugins()

app.include_router(glossary.router)
app.include_router(dimensions.router)
app.include_router(metrics.router)
app.include_router(query.router)
app.include_router(promotion.router)
app.include_router(saved_queries.router)

for router in API_ROUTERS_REGISTRY:
    app.include_router(router)

class QueryRequest(BaseModel):
    metric: str
    dimensions: List[str]
    filters: List[str] = []

class RunRequest(BaseModel):
    sql: str
    limit: int = 500

class ExtractRequest(BaseModel):
    path: str

@app.get("/health")
def health():
    snowflake_ok = None
    try:
        runner = SnowflakeRunner()
        snowflake_ok = runner.test_connection()
    except Exception:
        snowflake_ok = False
    return {"status": "ok", "snowflake": snowflake_ok}

@app.post("/extract")
def extract_metadata_endpoint(req: ExtractRequest):
    base_path = os.path.abspath(req.path)
    if not os.path.exists(base_path):
        raise HTTPException(status_code=404, detail="Path not found")
        
    # Load config (assuming axi.yml in base_path or current dir?)
    # For now, let's look for axi.yml in base_path
    config_path = os.path.join(base_path, "axi.yml")
    config = load_config(config_path)
    
    promotion_engine = PromotionEngine(config)
    scanner = SqlScanner(base_path, promotion_engine)
    
    # Metadata output dir
    # Stored under axi/metadata/models/ ? 
    # Or relative to where app is running? 
    # "axi/metadata/models/<model_name>.json"
    # Let's use a fixed location for now or relative to project root
    # assuming we run from 'backend' or root.
    # Let's put it in /tmp/axi/metadata or similar for now if not specified?
    # Or strict path: /home/jay/msh/axi/backend/axi/metadata/models works if we are there.
    # But this is a library.
    # Let's save to `output_dir` in `req` or default to `./metadata_store`.
    
    metadata_dir = settings.AXI_METADATA_DIR
    writer = MetadataWriter(metadata_dir)
    
    extracted_count = 0
    errors = []
    
    for model in scanner.scan():
        # model.path is relative path, use basename as model name for now
        model_name = os.path.splitext(os.path.basename(model.path))[0]
        try:
            meta = extract_metadata(model.content, model_name)
            writer.write(meta)
            extracted_count += 1
        except Exception as e:
            errors.append(f"Error extracting {model.path}: {str(e)}")
            
    return {
        "status": "success", 
        "extracted_models": extracted_count, 
        "metadata_dir": os.path.abspath(metadata_dir),
        "errors": errors
    }

@app.get("/metrics")
def list_metrics():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_metrics()

@app.get("/metrics/{metric_name}")
def get_metric(metric_name: str):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    m = indexer.get_metric(metric_name)
    if not m:
         raise HTTPException(status_code=404, detail="Metric not found")
    return m

@app.get("/metrics/{metric_name}/sql")
def get_metric_sql(metric_name: str, dims: str = "", filters: str = "", compare: str = None, window: str = None):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    engine = SemanticQueryEngine(indexer)
    dim_list = [d.strip() for d in dims.split(",")] if dims else []
    filter_list = [f.strip() for f in filters.split(",")] if filters else []
    try:
        sql = engine.generate_sql(metric_name, dim_list, filter_list, dialect="ansi", compare=compare, window=window)
        return {"sql": sql}
    except Exception as e:
        return {"error": str(e)}

@app.get("/metrics/{metric_name}/dependencies")
def get_metric_deps(metric_name: str):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    m = indexer.get_metric(metric_name)
    if not m:
         raise HTTPException(status_code=404, detail="Metric not found")
    return {"dependencies": m.get('depends_on', [])}

@app.get("/metrics/search")
def search_metrics(tag: str = None):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    res = []
    for m in indexer.list_metrics():
        if tag:
            if tag in m.get('tags', []):
                res.append(m)
        else:
            res.append(m)
    return res

@app.get("/models")
@app.get("/api/models")  # Also support /api/models for consistency
def list_models():
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        models = indexer.list_models()
        return models if models else []
    except Exception as e:
        # Return empty list on error to prevent 500
        return []

# Old /dimensions route removed - use /api/dimensions router instead
# If you need reachable dimensions for a metric, use /api/query/semantic/plan endpoint

@app.get("/relationships")
def list_relationships():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_relationships()

@app.get("/entities")
@app.get("/api/entities")  # Also support /api/entities for consistency
def list_entities():
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        entities = indexer.list_entities()
        return entities if entities else []
    except Exception as e:
        # Return empty list on error to prevent 500
        return []

@app.get("/api/entities/{name}")
def get_entity_detail(name: str, include_pruned: bool = False):
    """
    Return entity with dimensions including pruning metadata, plus metrics referencing it and relationships.
    """
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    ent = indexer.get_entity(name)
    if not ent:
        raise HTTPException(status_code=404, detail="Entity not found")

    model_name = ent.get("model") or name
    dim_details = []
    try:
        model_path = os.path.join(indexer.metadata_dir, "models", f"{model_name}.json")
        if os.path.exists(model_path):
            with open(model_path, "r") as f:
                model_json = json.load(f)
                dim_details = model_json.get("dimension_details", [])
    except Exception:
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
    except Exception:
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

@app.get("/graph")
@app.get("/api/graph")  # Also support /api/graph for consistency
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
    except Exception as e:
        # Return empty graph on error
        return {"nodes": [], "edges": []}

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
    except Exception:
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
    return {"nodes": list(sub_nodes.values()), "edges": sub_edges}

@app.get("/api/graph/local")
def graph_local_param(node: str, depth: int = 1):
    """
    Local subgraph for a node (entity/metric/dimension). Depth 1 or 2.
    """
    depth = 1 if depth < 1 else 2 if depth > 2 else depth
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return _local_subgraph(node, depth, indexer)

@app.get("/api/graph/filtered")
def graph_filtered(root: str, depth: int = 2, types: str = "entity,metric,dimension", promoted_only: bool = False):
    """
    Filtered graph walk from root with depth 1..3 and type filter.
    Caps at 300 nodes.
    """
    depth = max(1, min(depth, 3))
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    base = _local_subgraph(root, depth, indexer)
    if base.get("error"):
        return base
    type_set = set([t.strip() for t in types.split(",") if t.strip()])
    filtered_nodes = [n for n in base["nodes"] if not type_set or n.get("type") in type_set]
    node_ids = set(n["id"] for n in filtered_nodes)
    filtered_edges = [e for e in base["edges"] if e["from"] in node_ids and e["to"] in node_ids]
    if len(filtered_nodes) > 300:
        return {"error": {"code": "GRAPH_TOO_LARGE", "message": "Filtered graph exceeds 300 nodes. Narrow your filters."}}
    return {"nodes": filtered_nodes, "edges": filtered_edges}

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
    try:
        if depth < 1 or depth > 2:
            depth = 1
        
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        sg = SemanticGraph(indexer)
        return sg.get_local_subgraph(node, depth)
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

@app.get("/api/graph/filtered")
def graph_filtered(root: Optional[str] = None, depth: int = 2, types: Optional[str] = None):
    """
    Get filtered graph based on root node, depth, and type filters.
    Query params:
    - root: Root node ID (optional)
    - depth: 1, 2, or 3 (default: 2)
    - types: Comma-separated list of node types (optional)
    """
    try:
        if depth < 1 or depth > 3:
            depth = 2
        
        node_types = None
        if types:
            node_types = [t.strip() for t in types.split(",")]
        
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        sg = SemanticGraph(indexer)
        return sg.get_filtered_graph(root_node=root, depth=depth, node_types=node_types)
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

@app.get("/api/graph/category")
def graph_category(type: Optional[str] = None):
    """
    Get category-level graph showing collapsed buckets.
    Query params:
    - type: Category type to filter (optional: entities, metrics, dimensions, models)
    """
    try:
        indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
        sg = SemanticGraph(indexer)
        return sg.get_category_graph(category_type=type)
    except Exception as e:
        return {"nodes": [], "edges": [], "error": str(e)}

@app.post("/semantic/sql")
def generate_sql(req: QueryRequest):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    engine = SemanticQueryEngine(indexer)
    try:
        # Pydantic model doesn't have optimize field yet, assuming default True
        sql = engine.generate_sql(req.metric, req.dimensions, req.filters, optimize=True)
        return {"sql": sql}
    except Exception as e:
        return {"error": str(e)}

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
    except Exception as e:
        return {"error": str(e)}

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
    except Exception as e:
        return {"error": str(e)}

@app.get("/snowflake/tables")
def sf_tables():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_sf_tables()

@app.get("/snowflake/columns")
def sf_columns(table: str):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_sf_columns(table)

@app.get("/snowflake/policies")
def sf_policies():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_sf_policies()

@app.get("/snowflake/lineage")
def sf_lineage(table: Optional[str] = None):
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
    except Exception as e:
        return {"error": str(e)}

@app.get("/dbt/models")
def dbt_models():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    return indexer.list_dbt_models()

@app.get("/dbt/models/{name}")
def dbt_model(name: str):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    m = indexer.get_dbt_model(name)
    if not m:
        raise HTTPException(status_code=404, detail="dbt model not found")
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
    except Exception as e:
        return {"error": str(e)}

class MaterializeRequest(BaseModel):
    metric: str
    dimensions: List[str]
    refresh: str = "auto"

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
    except Exception as e:
        return {"error": str(e)}

@app.post("/materialize/refresh")
def refresh_materialization(req: MaterializeRequest):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    from axi.materialization.materializer import Materializer
    mat = Materializer(indexer)
    try:
        return mat.materialize_metric(req.metric, req.dimensions, "auto")
    except Exception as e:
        return {"error": str(e)}

@app.post("/mart")
def create_mart(req: MartRequest):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    from axi.materialization.materializer import Materializer
    mat = Materializer(indexer)
    try:
        return mat.create_mart(req.name, req.metrics, req.dimensions)
    except Exception as e:
        return {"error": str(e)}

@app.get("/cache")
def get_cache_stats():
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    conn = indexer._get_conn()
    c = conn.cursor()
    c.execute("SELECT count(*) FROM cache_entries")
    count = c.fetchone()[0]
    conn.close()
    return {"entries": count}

@app.delete("/cache")
def clear_cache(metric: str = None):
    indexer = MetadataIndexer(settings.AXI_METADATA_DIR)
    from axi.cache.query_cache import QueryCache
    cache = QueryCache(indexer)
    cache.clear(metric)
    return {"status": "cleared"}

def run():
    import uvicorn
    uvicorn.run("axi.api.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    run()
