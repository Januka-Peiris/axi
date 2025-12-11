import typer
import os
import sys
import json
from typing import List, Optional

# Ensure backend is in pythonpath
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "backend")
if os.path.exists(backend_path):
    sys.path.insert(0, backend_path)

from axi.config.loader import load_config
from axi.extractor.promotion import PromotionEngine
from axi.extractor.scanner import SqlScanner
from axi.extractor.core import extract_metadata
from axi.metadata.writer import MetadataWriter
from axi.metadata.indexer import MetadataIndexer
from axi.query.engine import SemanticQueryEngine
from axi.execution.snowflake_runner import SnowflakeRunner

app = typer.Typer()

from axi.config.settings import get_settings
from .scaffold import scaffold_project
from .generate import generate_metric, generate_dimension, generate_glossary, generate_rule_promotion

settings = get_settings()

# Define storage locations
METADATA_DIR = settings.AXI_METADATA_DIR

# Plugin Init
from axi.plugins.loader import PluginLoader
from axi.plugins.registry import CLI_EXTENSIONS_REGISTRY

plugin_loader = PluginLoader(["./plugins", os.path.expanduser("~/.axi/plugins")])
plugin_loader.load_plugins()

# Mount Plugin CLI Apps
for name, sub_app in CLI_EXTENSIONS_REGISTRY.items():
    app.add_typer(sub_app, name=name)

@app.command()
def scaffold(
    force: bool = typer.Option(False, "--force", help="Overwrite existing files")
):
    """
    Create a new AXI project in the current directory.
    """
    scaffold_project(force=force)

generate_app = typer.Typer()
app.add_typer(generate_app, name="generate")

@generate_app.command("metric")
def generate_metric_cmd(
    name: str = typer.Argument(..., help="Metric name"),
    entity: str = typer.Option(..., "--entity", "-e", help="Entity name"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing file")
):
    """
    Generate a metric definition file.
    """
    generate_metric(name, entity, force=force)

@generate_app.command("dimension")
def generate_dimension_cmd(
    name: str = typer.Argument(..., help="Dimension name"),
    entity: str = typer.Option(..., "--entity", "-e", help="Entity name"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing file")
):
    """
    Generate a dimension definition file.
    """
    generate_dimension(name, entity, force=force)

@generate_app.command("glossary")
def generate_glossary_term(
    term: str = typer.Argument(..., help="Glossary term"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing file")
):
    """
    Generate a glossary term definition file.
    """
    generate_glossary(term, force=force)

@generate_app.command("rule")
def generate_rule_cmd(
    rule_type: str = typer.Argument(..., help="Rule type (e.g., 'promotion')"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing file")
):
    """
    Generate a rule definition file.
    """
    if rule_type == "promotion":
        generate_rule_promotion(force=force)
    else:
        typer.echo(f"Unknown rule type: {rule_type}")
        typer.echo("Available types: promotion")
        raise typer.Exit(1)

@app.command()
def extract(
    path: str = typer.Argument(None),
    debug: bool = typer.Option(False, "--debug", help="Enable verbose debug logging"),
    debug_models: bool = typer.Option(False, "--debug-models", help="List all discovered models without extracting"),
    no_dbt: bool = typer.Option(False, "--no-dbt", help="Disable dbt manifest loading entirely")
):
    """
    Run metadata extraction on the given path (CLI-mode).
    """
    if debug or debug_models:
        os.environ["AXI_DEBUG"] = "true"
    else:
        if "AXI_DEBUG" in os.environ:
            del os.environ["AXI_DEBUG"]

    # Find project root (where axi.yml or dbt_project.yml might be)
    cwd = os.getcwd()
    project_root = cwd
    current = cwd
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "axi.yml")) or os.path.exists(os.path.join(current, "dbt_project.yml")):
            project_root = current
            break
        current = os.path.dirname(current)
    
    # Load config
    config_path = os.path.join(project_root, "axi.yml")
    if os.path.exists(config_path):
        config = load_config(config_path)
    else:
        from axi.config.loader import Config, PromotionRules
        # Empty folders list = promote everything (default behavior)
        config = Config(include=PromotionRules(folders=[], tags=[]))
    
    # Determine SQL root using exact priority order
    sql_root = None
    user_passed_path = path is not None and path != "."
    
    # Decision tree implementation
    if user_passed_path:
        # (1) User passed a path → ALWAYS use it
        sql_root = os.path.abspath(path)
        if not os.path.exists(sql_root):
            typer.echo(f"✗ Error: Path does not exist: {sql_root}")
            raise typer.Exit(1)
        if os.environ.get("AXI_DEBUG") == "true":
            print(f"[AXI-DEBUG] Using SQL root (user-provided): {sql_root}")
    elif config.dbt and config.dbt.compiled_path:
        # (2) axi.yml has dbt.compiled_path → use it
        if os.path.isabs(config.dbt.compiled_path):
            sql_root = config.dbt.compiled_path
        else:
            sql_root = os.path.join(project_root, config.dbt.compiled_path)
        
        if not os.path.exists(sql_root):
            typer.echo(f"✗ Error: Compiled dbt models not found at: {sql_root}")
            typer.echo("  Run: dbt compile")
            raise typer.Exit(1)
        
        if os.environ.get("AXI_DEBUG") == "true":
            print(f"[AXI-DEBUG] Using SQL root (from config): {sql_root}")
    elif not no_dbt:
        # (3) Check for dbt manifest
        dbt_project_file = os.path.join(project_root, "dbt_project.yml")
        manifest_path = os.path.join(project_root, "target", "manifest.json")
        
        if os.path.exists(dbt_project_file):
            # dbt project detected
            if os.path.exists(manifest_path):
                # Try to determine compiled path from manifest
                try:
                    import json
                    with open(manifest_path, "r") as f:
                        manifest = json.load(f)
                    
                    # Get project name from dbt_project.yml
                    import yaml
                    with open(dbt_project_file, "r") as f:
                        dbt_config = yaml.safe_load(f)
                    project_name = dbt_config.get("name")
                    
                    if project_name:
                        default_compiled_path = os.path.join(project_root, "target", "compiled", project_name)
                        if os.path.exists(default_compiled_path):
                            sql_root = default_compiled_path
                            if os.environ.get("AXI_DEBUG") == "true":
                                print(f"[AXI-DEBUG] Using SQL root (from dbt manifest): {sql_root}")
                        else:
                            typer.echo("✗ Error: Compiled dbt models not found.")
                            typer.echo(f"  Expected at: {default_compiled_path}")
                            typer.echo("  Run: dbt compile")
                            raise typer.Exit(1)
                    else:
                        typer.echo("✗ Error: Could not determine dbt project name.")
                        typer.echo("  Run: dbt compile")
                        raise typer.Exit(1)
                except Exception as e:
                    typer.echo(f"✗ Error reading dbt manifest: {e}")
                    raise typer.Exit(1)
            else:
                # dbt project but no manifest - only allow if --no-dbt
                typer.echo("✗ Error: dbt project detected but manifest.json not found.")
                typer.echo("  Run: dbt compile")
                typer.echo("  Or use: axi extract --no-dbt (for raw SQL mode)")
                raise typer.Exit(1)
        else:
            # (4) No dbt project → raw SQL mode
            sql_root = cwd
            if os.environ.get("AXI_DEBUG") == "true":
                print(f"[AXI-DEBUG] Using SQL root (raw SQL mode): {sql_root}")
    else:
        # --no-dbt flag set → raw SQL mode
        sql_root = cwd
        if os.environ.get("AXI_DEBUG") == "true":
            print(f"[AXI-DEBUG] Using SQL root (--no-dbt, raw SQL mode): {sql_root}")
    
    if sql_root is None:
        typer.echo("✗ Error: Could not determine SQL root path.")
        raise typer.Exit(1)
    
    # Create scanner with sql_root
    promotion_engine = PromotionEngine(config)
    scanner = SqlScanner(sql_root, promotion_engine)
    writer = MetadataWriter(METADATA_DIR)
    indexer = MetadataIndexer(METADATA_DIR)
    
    if debug_models:
        typer.echo("=== MODEL DISCOVERY DEBUG ===")
        typer.echo(f"SQL Root: {sql_root}")
        for model in scanner.scan():
             typer.echo(f"FOUND: {model.path}")
        return

    typer.echo(f"Scanning SQL from: {sql_root}")
    
    # Load dbt manifest ONLY for metadata (not file paths) unless --no-dbt is set
    if not no_dbt:
        dbt_project_file = os.path.join(project_root, "dbt_project.yml")
        manifest_path = os.path.join(project_root, "target", "manifest.json")
        
        if os.path.exists(dbt_project_file) and os.path.exists(manifest_path):
            typer.echo("✔ Loading dbt manifest metadata...")
            from axi.dbt.manifest_loader import ManifestLoader
            from axi.dbt.semantic_bridge import SemanticBridge
             
            try:
                loader = ManifestLoader(indexer)
                loader.load_manifest(manifest_path)
                
                bridge = SemanticBridge(indexer)
                bridge.map_constraints()
                typer.echo("  ✔ Manifest metadata loaded & constraints mapped.")
            except Exception as e:
                typer.echo(f"  [WARN] Failed to load manifest: {e}")

    # Clear previous promotion results
    indexer.clear_promotion_results()
    
    stats = {
        "scanned": 0,
        "parsed": 0,
        "failed": 0
    }
    
    for model in scanner.scan():
        stats["scanned"] += 1
        model_name = os.path.splitext(os.path.basename(model.path))[0]
        
        # Record promotion result
        promotion_result = model.promotion_result if hasattr(model, 'promotion_result') else None
        if promotion_result:
            status = "promoted" if promotion_result.promoted else "ignored"
            reason = promotion_result.reason
            matched_rule = promotion_result.matched_rule
        else:
            status = "ignored"
            reason = "not_tracked"
            matched_rule = None
        
        entity_created = False
        dimensions_count = 0
        metrics_count = 0
        error_message = None
        
        try:
            if promotion_result and promotion_result.promoted and model.content:
                meta = extract_metadata(model.content, model_name, config=config)
                writer.write(meta)
                stats["parsed"] += 1
                
                # Count extracted items
                entity_created = "entity" in meta and meta.get("entity", {}).get("name") == model_name
                dimensions_count = len(meta.get("dimensions", []))
                metrics_count = len(meta.get("metrics", []))
                
                if debug:
                    typer.echo(f"[AXI-DEBUG] Extracted: {model_name}")
            else:
                # Model was not promoted, so don't extract
                stats["failed"] += 1
        except Exception as e:
            stats["failed"] += 1
            status = "error"
            error_message = str(e)
            # Error already logged by extract_metadata if debug is on
            if debug:
                typer.echo(f"  [FAIL] {model_name}")
        
        # Record promotion result
        indexer.record_promotion_result(
            name=model_name,
            path=model.path,
            status=status,
            reason=reason,
            source="dbt" if not no_dbt else "raw_sql",
            model_type="model",
            matched_rule=matched_rule,
            error_message=error_message,
            entity_created=entity_created,
            dimensions_count=dimensions_count,
            metrics_count=metrics_count
        )

    typer.echo("Rebuilding Index...")
    indexer.build_index()
    
    typer.echo("\n======== AXI EXTRACTION SUMMARY ========")
    typer.echo(f"Models scanned: {stats['scanned']}")
    typer.echo(f"Models parsed successfully: {stats['parsed']}")
    typer.echo(f"Models with parse errors: {stats['failed']}")
    typer.echo("========================================")

glossary_app = typer.Typer()
app.add_typer(glossary_app, name="glossary")

@glossary_app.command("generate")
def glossary_generate():
    """
    Generate business glossary from metadata and overrides.
    """
    from axi.glossary.glossary_generator import GlossaryGenerator
    from axi.glossary.glossary_store import GlossaryStore
    
    typer.echo("Generating glossary...")
    gen = GlossaryGenerator(METADATA_DIR)
    glossary = gen.generate()
    
    store = GlossaryStore(METADATA_DIR)
    store.save(glossary)
    typer.echo(f"Glossary saved to {store.json_path} and SQLite.")

@glossary_app.command("search")
def glossary_search(query: str):
    """
    Search glossary.
    """
    from axi.glossary.glossary_store import GlossaryStore
    store = GlossaryStore(METADATA_DIR)
    results = store.search(query)
    typer.echo(json.dumps(results, indent=2))

metrics_app = typer.Typer()
app.add_typer(metrics_app, name="metrics")

@metrics_app.command("list")
def metrics_list():
    """
    List indexed metrics.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    metrics = indexer.list_metrics()
    typer.echo(json.dumps(metrics, indent=2, default=str))

@metrics_app.command("describe")
def metrics_describe(metric_name: str):
    """
    Show full metadata for a metric.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    metric = indexer.get_metric(metric_name)
    if metric:
        typer.echo(json.dumps(metric, indent=2, default=str))
    else:
        typer.echo(f"Metric '{metric_name}' not found.")

@metrics_app.command("sql")
def metrics_sql(
    metric: str = typer.Argument(..., help="Metric name"),
    dims: str = typer.Option(None, help="Comma separated dimensions"),
    filters: str = typer.Option(None, help="Comma separated filters"),
    dialect: str = typer.Option("ansi", help="SQL Dialect (ansi, snowflake)"),
    compare: str = typer.Option(None, help="Time comparison (previous_period)"),
    window: str = typer.Option(None, help="Window function (rolling_7d)"),
    explain: bool = typer.Option(False, help="Explain optimization"),
    optimize: bool = typer.Option(True, help="Enable optimizer")
):
    """
    Generate SQL for a metric with expanded time intelligence options.
    """
    dim_list = [d.strip() for d in dims.split(",")] if dims else []
    filter_list = [f.strip() for f in filters.split(",")] if filters else []
    
    indexer = MetadataIndexer(METADATA_DIR)
    engine = SemanticQueryEngine(indexer)
    try:
        if explain:
            # We need to manually invoke optimizer explain for now, or add explain support to engine
            # Let's do it manually here to show diff
            raw_sql = engine.generate_sql(metric, dim_list, filter_list, dialect, compare, window, optimize=False)
            
            from axi.optimizer.core import Optimizer, OptimizationContext
            from axi.optimizer.rules import get_default_rules
            
            ctx = OptimizationContext(config={"optimizer.rules.snowflake_hints": dialect == "snowflake"})
            opt = Optimizer(ctx)
            for rule in get_default_rules():
                 opt.add_rule(rule)
            
            expl = opt.explain(raw_sql, dialect=dialect)
            typer.echo(json.dumps(expl, indent=2))
        else:
            sql = engine.generate_sql(metric, dim_list, filter_list, dialect, compare, window, optimize=optimize)
            typer.echo(sql)
    except Exception as e:
        typer.echo(f"Error: {e}")

@metrics_app.command("deps")
def metrics_deps(metric: str):
    """
    Show dependency graph for a metric.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    m = indexer.get_metric(metric)
    if m:
        deps = m.get('depends_on', [])
        typer.echo(f"Metric: {metric}")
        typer.echo(f"Type: {m.get('metric_type')}")
        typer.echo(f"Dependencies: {deps}")
        # Could traverse recursively in real impl
    else:
        typer.echo(f"Metric '{metric}' not found.")

@metrics_app.command("search")
def metrics_search(tag: str = typer.Option(None, help="Tag to filter by")):
    """
    Search metrics by tag.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    all_metrics = indexer.list_metrics()
    results = []
    for m in all_metrics:
        tags = m.get('tags', [])
        if tag:
            if tag in tags:
                results.append(m['name'])
        else:
            results.append(m['name'])
    
    typer.echo(json.dumps(results, indent=2))

# Cache CLI
cache_app = typer.Typer()
app.add_typer(cache_app, name="cache")

@cache_app.command("show")
def cache_show():
    """
    Show cache stats.
    """
    # Just list count for now or dump table
    indexer = MetadataIndexer(METADATA_DIR)
    conn = indexer._get_conn()
    c = conn.cursor()
    c.execute("SELECT count(*) FROM cache_entries")
    count = c.fetchone()[0]
    conn.close()
    typer.echo(f"Cache Entries: {count}")

@cache_app.command("clear")
def cache_clear(metric: str = typer.Option(None, help="Specific metric to clear")):
    """
    Clear query cache.
    """
    from axi.cache.query_cache import QueryCache
    indexer = MetadataIndexer(METADATA_DIR)
    cache = QueryCache(indexer)
    cache.clear(metric)
    typer.echo("Cache cleared.")

# Materialize CLI
mat_app = typer.Typer()
app.add_typer(mat_app, name="materialize")

@mat_app.command("create")
def mat_create(
    metric: str = typer.Argument(..., help="Metric name"),
    dims: str = typer.Option(..., help="Dimensions (comma sep)"),
    refresh: str = typer.Option("auto", help="Refresh mode: auto, full, incremental")
):
    """
    Create a materialized metric table.
    """
    from axi.materialization.materializer import Materializer
    indexer = MetadataIndexer(METADATA_DIR)
    mat = Materializer(indexer)
    
    dim_list = [d.strip() for d in dims.split(",")]
    stats = mat.materialize_metric(metric, dim_list, refresh)
    typer.echo(json.dumps(stats, indent=2))

@mat_app.command("refresh")
def mat_refresh(
    metric: str = typer.Argument(..., help="Metric name"),
     dims: str = typer.Option(..., help="Dimensions (comma sep)")
):
    """
    Refresh an existing materialization.
    """
    from axi.materialization.materializer import Materializer
    indexer = MetadataIndexer(METADATA_DIR)
    mat = Materializer(indexer)
    dim_list = [d.strip() for d in dims.split(",")]
    stats = mat.materialize_metric(metric, dim_list, "auto") # Auto refresh
    typer.echo(json.dumps(stats, indent=2))

# Mart CLI
mart_app = typer.Typer()
app.add_typer(mart_app, name="mart")

@mart_app.command("create")
def mart_create(
    name: str = typer.Argument(..., help="Mart Name"),
    metrics: str = typer.Option(..., help="Metrics (comma sep)"),
    dims: str = typer.Option(..., help="Dimensions (comma sep)")
):
    """
    Create a semantic mart (multi-metric table).
    """
    from axi.materialization.materializer import Materializer
    indexer = MetadataIndexer(METADATA_DIR)
    mat = Materializer(indexer)
    
    m_list = [m.strip() for m in metrics.split(",")]
    d_list = [d.strip() for d in dims.split(",")]
    
    stats = mat.create_mart(name, m_list, d_list)
    typer.echo(json.dumps(stats, indent=2))

dbt_app = typer.Typer()

app.add_typer(dbt_app, name="dbt")

@dbt_app.command("manifest")
def dbt_manifest(path: str = typer.Argument(..., help="Path to manifest.json")):
    """
    Load and parse a dbt manifest.json file.
    """
    from axi.dbt.manifest_loader import ManifestLoader
    from axi.dbt.semantic_bridge import SemanticBridge
    
    indexer = MetadataIndexer(METADATA_DIR)
    loader = ManifestLoader(indexer)
    bridge = SemanticBridge(indexer)
    
    try:
        typer.echo(f"Loading manifest from {path}...")
        loader.load_manifest(path)
        typer.echo("Manifest loaded.")
        
        typer.echo("Mapping constraints...")
        bridge.map_constraints()
        typer.echo("Done.")
        
    except Exception as e:
        typer.echo(f"Error: {e}")

@dbt_app.command("scan")
def dbt_scan():
    """
    Scan dbt models and auto-promote based on axi.yml config.
    This is a convenience command for dbt projects that runs extraction
    with dbt-aware defaults.
    """
    # Find project root (where axi.yml or dbt_project.yml might be)
    cwd = os.getcwd()
    project_root = cwd
    current = cwd
    while current != os.path.dirname(current):
        if os.path.exists(os.path.join(current, "axi.yml")) or os.path.exists(os.path.join(current, "dbt_project.yml")):
            project_root = current
            break
        current = os.path.dirname(current)
    
    # Check for dbt project
    dbt_project_file = os.path.join(project_root, "dbt_project.yml")
    if not os.path.exists(dbt_project_file):
        typer.echo("✗ Error: Not a dbt project (dbt_project.yml not found).")
        typer.echo("  Use 'axi extract' for non-dbt projects.")
        raise typer.Exit(1)
    
    # Load config
    config_path = os.path.join(project_root, "axi.yml")
    if os.path.exists(config_path):
        config = load_config(config_path)
    else:
        from axi.config.loader import Config, PromotionRules
        # Empty folders list = promote everything (default behavior)
        config = Config(include=PromotionRules(folders=[], tags=[]))
    
    # Determine SQL root - for dbt scan, prefer compiled path
    sql_root = None
    
    if config.dbt and config.dbt.compiled_path:
        # (1) Use configured compiled path
        if os.path.isabs(config.dbt.compiled_path):
            sql_root = config.dbt.compiled_path
        else:
            sql_root = os.path.join(project_root, config.dbt.compiled_path)
        
        if not os.path.exists(sql_root):
            typer.echo(f"✗ Error: Compiled dbt models not found at: {sql_root}")
            typer.echo("  Run: dbt compile")
            raise typer.Exit(1)
        
        typer.echo(f"[AXI] Using configured dbt compiled path: {sql_root}")
    else:
        # (2) Auto-detect from manifest
        manifest_path = os.path.join(project_root, "target", "manifest.json")
        
        if not os.path.exists(manifest_path):
            typer.echo("✗ Error: dbt manifest.json not found.")
            typer.echo("  Run: dbt compile")
            raise typer.Exit(1)
        
        try:
            import json
            import yaml
            
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
            
            with open(dbt_project_file, "r") as f:
                dbt_config = yaml.safe_load(f)
            
            project_name = dbt_config.get("name")
            
            if project_name:
                default_compiled_path = os.path.join(project_root, "target", "compiled", project_name)
                if os.path.exists(default_compiled_path):
                    sql_root = default_compiled_path
                    typer.echo(f"[AXI] Using auto-detected dbt compiled path: {sql_root}")
                else:
                    typer.echo("✗ Error: Compiled dbt models not found.")
                    typer.echo(f"  Expected at: {default_compiled_path}")
                    typer.echo("  Run: dbt compile")
                    raise typer.Exit(1)
            else:
                typer.echo("✗ Error: Could not determine dbt project name.")
                raise typer.Exit(1)
        except Exception as e:
            typer.echo(f"✗ Error reading dbt project: {e}")
            raise typer.Exit(1)
    
    if sql_root is None:
        typer.echo("✗ Error: Could not determine SQL root path.")
        raise typer.Exit(1)
    
    # Create scanner and extractor
    promotion_engine = PromotionEngine(config)
    scanner = SqlScanner(sql_root, promotion_engine)
    writer = MetadataWriter(METADATA_DIR)
    indexer = MetadataIndexer(METADATA_DIR)
    
    typer.echo(f"Scanning dbt models from: {sql_root}")
    
    # Load dbt manifest for metadata
    manifest_path = os.path.join(project_root, "target", "manifest.json")
    if os.path.exists(manifest_path):
        typer.echo("✔ Loading dbt manifest metadata...")
        from axi.dbt.manifest_loader import ManifestLoader
        from axi.dbt.semantic_bridge import SemanticBridge
        
        try:
            loader = ManifestLoader(indexer)
            loader.load_manifest(manifest_path)
            
            bridge = SemanticBridge(indexer)
            bridge.map_constraints()
            typer.echo("  ✔ Manifest metadata loaded & constraints mapped.")
        except Exception as e:
            typer.echo(f"  [WARN] Failed to load manifest: {e}")
    
    # Scan and extract models
    stats = {
        "scanned": 0,
        "parsed": 0,
        "failed": 0
    }
    
    for model in scanner.scan():
        stats["scanned"] += 1
        model_name = os.path.splitext(os.path.basename(model.path))[0]
        try:
            meta = extract_metadata(model.content, model_name, config=config)
            writer.write(meta)
            stats["parsed"] += 1
        except Exception as e:
            stats["failed"] += 1
    
    typer.echo("Rebuilding Index...")
    indexer.build_index()
    
    typer.echo("\n======== AXI DBT SCAN SUMMARY ========")
    typer.echo(f"Models scanned: {stats['scanned']}")
    typer.echo(f"Models promoted/extracted: {stats['parsed']}")
    typer.echo(f"Models with parse errors: {stats['failed']}")
    typer.echo("======================================")

@dbt_app.command("describe")
def dbt_describe(model: str):
    """
    Show metadata for a dbt model.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    m = indexer.get_dbt_model(model)
    if m:
        typer.echo(json.dumps(m, indent=2, default=str))
    else:
        typer.echo(f"dbt model '{model}' not found.")

@dbt_app.command("constraints")
def dbt_constraints(model: str = typer.Argument(None, help="Model name")):
    """
    List semantic constraints derived from dbt tests.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    constraints = indexer.list_constraints(model)
    typer.echo(json.dumps(constraints, indent=2, default=str))

@dbt_app.command("deps")
def dbt_deps(model: str):
    """
    Show dependencies for a dbt model.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    m = indexer.get_dbt_model(model)
    if m:
        deps = m.get('depends_on', [])
        typer.echo(f"Model: {model}")
        typer.echo(f"Dependencies: {deps}")
    else:
        typer.echo(f"dbt model '{model}' not found.")

@app.command()
def relationships():
    """
    List all detected relationships.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    rels = indexer.list_relationships()
    typer.echo(json.dumps(rels, indent=2, default=str))

@app.command()
def graph():
    """
    Print JSON graph of model relationships.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    # We need to import SemanticGraph here, ensure it's available
    from axi.query.graph import SemanticGraph
    sg = SemanticGraph(indexer)
    typer.echo(json.dumps(sg.get_graph_json(), indent=2, default=str))

@app.command()
def query(
    metric: str = typer.Option(..., help="Metric name to query"),
    dims: str = typer.Option(None, help="Comma separated dimensions"),
    filters: str = typer.Option(None, help="Comma separated filters"),
    run: bool = typer.Option(False, help="Execute on Snowflake")
):
    """
    Generate or Run a semantic query.
    """
    dim_list = [d.strip() for d in dims.split(",")] if dims else []
    filter_list = [f.strip() for f in filters.split(",")] if filters else []
    
    indexer = MetadataIndexer(METADATA_DIR)
    engine = SemanticQueryEngine(indexer)
    
    try:
        sql = engine.generate_sql(metric, dim_list, filter_list)
        
        if run:
            typer.echo("Thinking... (Executing on Snowflake)")
            runner = SnowflakeRunner()
            rows, cols = runner.execute_query(sql)
            # Basic table print
            typer.echo(f"Query Result ({len(rows)} rows):")
            typer.echo(f"{' | '.join(cols)}")
            typer.echo("-" * 40)
            for row in rows[:20]: # Show top 20
                 vals = [str(row[c]) for c in cols]
                 typer.echo(" | ".join(vals))
            if len(rows) > 20:
                typer.echo("... (truncated)")
        else:
            typer.echo(sql)
            
    except Exception as e:
        typer.echo(f"Error: {e}")

@app.command()
def ui(
    host: str = typer.Option("localhost", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to")
):
    """
    Start the Semantic Explorer UI (Backend API).
    """
    import uvicorn
    
    typer.echo(f"Starting AXI API at http://{host}:{port}")
    typer.echo("To view the UI, run the following in another terminal:")
    typer.echo("  cd frontend && npm run dev")
    typer.echo("Then open http://localhost:5173")
    
    # Run uvicorn programmatically
    # We need to target the app object.
    # Assuming axi is installed as package, or we use string reference.
    # To work in dev setup without package install, we might need sys path hacks handled above.
    
    uvicorn.run("axi.api.main:app", host=host, port=port, reload=True, app_dir=backend_path)

@app.command()
def snowflake(
    action: str = typer.Argument(..., help="sync, tables, columns, lineage, policies"),
    arg: str = typer.Argument(None, help="Table name for columns/lineage")
):
    """
    Manage Snowflake integration.
    Actions: sync, tables, columns <table>, lineage <table>, policies
    """
    from axi.snowflake.extractor import SnowflakeMetadataExtractor
    
    indexer = MetadataIndexer(METADATA_DIR)
    
    if action == "sync":
        extractor = SnowflakeMetadataExtractor(indexer)
        extractor.sync()
        typer.echo("Sync complete.")
        
    elif action == "tables":
        tables = indexer.list_sf_tables()
        typer.echo(json.dumps(tables, indent=2, default=str))

    elif action == "columns":
        if not arg:
            typer.echo("Error: Table name required for columns action")
            return
        cols = indexer.list_sf_columns(arg)
        typer.echo(json.dumps(cols, indent=2, default=str))

    elif action == "policies":
        pols = indexer.list_sf_policies()
        typer.echo(json.dumps(pols, indent=2, default=str))

    elif action == "lineage":
        lin = indexer.list_sf_lineage(arg)
        typer.echo(json.dumps(lin, indent=2, default=str))
        
    else:
        typer.echo(f"Unknown action: {action}")

if __name__ == "__main__":
    app()
