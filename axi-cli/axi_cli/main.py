import typer
import os
import sys
import json
import subprocess
import atexit
from importlib import metadata
from typing import List, Optional

from . import exit_codes

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

app = typer.Typer(
    help="AXI Semantic Layer - Transform SQL into a semantic metrics layer",
    no_args_is_help=True
)

from axi.config.settings import get_settings
from axi.config.env_loader import load_env_file
from axi.exceptions import AXIBaseException, DeploymentValidationError
from .scaffold import scaffold_project
from .error_format import format_axi_error, format_deployment_validation_error
from .generate import generate_metric, generate_dimension, generate_glossary, generate_rule_promotion
from axi.semantic_store.factory import get_semantic_store
from axi.glossary.term_store import GlossaryTermStore
from axi.glossary.drift_detector import detect_drift
from axi.glossary.candidate_nudges import suggest_candidates
from axi.glossary.explanation import explain_subject
from axi.glossary.impact_analysis import run_impact_analysis
from axi.glossary.history_summary import summarize_changes

# Load .env files before initializing settings
load_env_file()

settings = get_settings()

# Define storage locations
METADATA_DIR = settings.metadata_dir

# Plugin Init
from axi.plugins.loader import PluginLoader
from axi.plugins.registry import CLI_EXTENSIONS_REGISTRY

plugin_loader = PluginLoader(["./plugins", os.path.expanduser("~/.axi/plugins")])
plugin_loader.load_plugins()

# Mount Plugin CLI Apps
for name, sub_app in CLI_EXTENSIONS_REGISTRY.items():
    app.add_typer(sub_app, name=name)

@app.command()
def migrate(
    from_backend: str = typer.Option("sqlite", "--from", help="Source backend (sqlite|postgres)"),
    to_backend: str = typer.Option("postgres", "--to", help="Target backend (sqlite|postgres)"),
    sqlite_path: str = typer.Option(None, "--sqlite-path", help="Path to source SQLite semantic_state.db"),
    postgres_url: str = typer.Option(None, "--postgres-url", help="Target Postgres URL (overrides env/DATABASE_URL)"),
    state_type: str = typer.Option(None, "--state-type", help="Optional state type filter (extracted|inferred|approved)"),
):
    """
    Migrate semantic state between backends (non-destructive).
    """
    typer.echo(f"Starting migration from {from_backend} to {to_backend}...")
    source = get_semantic_store(
        storage_backend=from_backend,
        sqlite_path=sqlite_path,
        postgres_url=postgres_url if from_backend == "postgres" else None,
    )
    target = get_semantic_store(
        storage_backend=to_backend,
        sqlite_path=sqlite_path,
        postgres_url=postgres_url,
    )

    migrated = 0
    skipped = 0
    try:
        for state in source.query(state_type=state_type):
            try:
                target.write(
                    state_type=state.state_type,
                    payload=state.payload,
                    version=state.version,
                    project_id=state.project_id,
                    state_id=state.id,
                )
                migrated += 1
            except Exception as e:
                skipped += 1
                typer.echo(f"[WARN] Skipping {state.id}: {e}")
    finally:
        if hasattr(source, "close"):
            source.close()
        if hasattr(target, "close"):
            target.close()

    typer.echo(f"Migration complete. Migrated {migrated} states, skipped {skipped}.")

@app.command()
def scaffold(
    force: bool = typer.Option(False, "--force", help="Overwrite existing files")
):
    """
    Create a new AXI project in the current directory.
    """
    scaffold_project(force=force)

generate_app = typer.Typer()
app.add_typer(generate_app, name="generate", help="Generate metric, dimension, and glossary definitions")

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
    no_dbt: bool = typer.Option(False, "--no-dbt", help="Disable dbt manifest loading entirely"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and show what would be extracted without writing"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-error output (for CI/CD)"),
    summary: str = typer.Option(None, "--summary", help="Write JSON run summary to file (for CI/CD)")
):
    """
    Run metadata extraction on the given path (CLI-mode).
    """
    from .run_summary import RunSummary, FailureEntry, SkippedEntry
    run_start = RunSummary.now_iso()
    # Helper for conditional output
    def echo(msg: str, err: bool = False):
        if not quiet or err:
            typer.echo(msg, err=err)

    # Silence noisy sqlglot warnings about ToChar format args during parsing
    import warnings
    warnings.filterwarnings(
        "ignore",
        message=r"Argument 'format' is not supported for expression 'ToChar' when targeting.*",
        category=Warning,
    )
    if debug or debug_models:
        os.environ["AXI_DEBUG"] = "true"
    else:
        if "AXI_DEBUG" in os.environ:
            del os.environ["AXI_DEBUG"]

    if dry_run:
        echo("[DRY-RUN] Validation mode - no files will be written")

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
    compiled_roots: List[str] = []
    user_passed_path = path is not None and path != "."
    
    # Decision tree implementation
    if user_passed_path:
        # (1) User passed a path → ALWAYS use it
        sql_root = os.path.abspath(path)
        if not os.path.exists(sql_root):
            typer.echo(f"✗ Error: Path does not exist: {sql_root}", err=True)
            raise typer.Exit(exit_codes.NOT_FOUND)
        if os.environ.get("AXI_DEBUG") == "true":
            print(f"[AXI-DEBUG] Using SQL root (user-provided): {sql_root}")
    elif not no_dbt and config.dbt and config.dbt.compiled_path:
        # (2) axi.yml has dbt.compiled_path → scan project root, prefer configured compiled path
        sql_root = project_root
        if os.path.isabs(config.dbt.compiled_path):
            compiled_path = config.dbt.compiled_path
        else:
            compiled_path = os.path.join(project_root, config.dbt.compiled_path)
        compiled_roots.append(compiled_path)
        if not os.path.exists(compiled_path):
            echo(f"[WARN] Compiled dbt models not found at: {compiled_path}")
            echo("       Falling back to raw SQL; run 'dbt compile' for best results.")
        if os.environ.get("AXI_DEBUG") == "true":
            print(f"[AXI-DEBUG] Using SQL root (project): {sql_root}")
            print(f"[AXI-DEBUG] Compiled SQL fallback: {compiled_path}")
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
                        compiled_roots.append(default_compiled_path)
                        sql_root = project_root
                        if not os.path.exists(default_compiled_path):
                            echo("[WARN] Compiled dbt models not found.")
                            echo(f"       Expected at: {default_compiled_path}")
                            echo("       Falling back to raw SQL; run 'dbt compile' for best results.")
                        if os.environ.get("AXI_DEBUG") == "true":
                            print(f"[AXI-DEBUG] Using SQL root (dbt project): {sql_root}")
                            print(f"[AXI-DEBUG] Compiled SQL fallback: {default_compiled_path}")
                    else:
                        typer.echo("✗ Error: Could not determine dbt project name.", err=True)
                        typer.echo("  Run: dbt compile", err=True)
                        raise typer.Exit(exit_codes.CONFIG_ERROR)
                except Exception as e:
                    typer.echo(f"✗ Error reading dbt manifest: {e}", err=True)
                    raise typer.Exit(exit_codes.CONFIG_ERROR)
            else:
                # dbt project but no manifest - only allow if --no-dbt
                typer.echo("✗ Error: dbt project detected but manifest.json not found.", err=True)
                typer.echo("  Run: dbt compile", err=True)
                typer.echo("  Or use: axi extract --no-dbt (for raw SQL mode)", err=True)
                raise typer.Exit(exit_codes.CONFIG_ERROR)
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
        typer.echo("✗ Error: Could not determine SQL root path.", err=True)
        raise typer.Exit(exit_codes.CONFIG_ERROR)

    # Create scanner with sql_root
    promotion_engine = PromotionEngine(config)
    scanner = SqlScanner(sql_root, promotion_engine, compiled_roots=compiled_roots)
    writer = MetadataWriter(METADATA_DIR)
    indexer = MetadataIndexer(METADATA_DIR)
    
    if debug_models:
        echo("=== MODEL DISCOVERY DEBUG ===")
        echo(f"SQL Root: {sql_root}")
        for model in scanner.scan():
             echo(f"FOUND: {model.path}")
        return

    echo(f"Scanning SQL from: {sql_root}")
    
    # Load dbt manifest ONLY for metadata (not file paths) unless --no-dbt is set
    if not no_dbt:
        dbt_project_file = os.path.join(project_root, "dbt_project.yml")
        manifest_path = os.path.join(project_root, "target", "manifest.json")
        
        if os.path.exists(dbt_project_file) and os.path.exists(manifest_path):
            echo("✔ Loading dbt manifest metadata...")
            from axi.dbt.manifest_loader import ManifestLoader
            from axi.dbt.semantic_bridge import SemanticBridge

            try:
                if not dry_run:
                    loader = ManifestLoader(indexer)
                    loader.load_manifest(manifest_path)

                    bridge = SemanticBridge(indexer)
                    bridge.map_constraints()
                echo("  ✔ Manifest metadata loaded & constraints mapped.")
            except Exception as e:
                echo(f"  [WARN] Failed to load manifest: {e}")

    # Clear previous promotion results
    if not dry_run:
        indexer.clear_promotion_results()

    stats = {
        "scanned": 0,
        "parsed": 0,
        "skipped": 0,
        "failed": 0
    }
    failures_list: List[FailureEntry] = []
    skipped_list: List[SkippedEntry] = []

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
                if meta.get("grain_status") == "not_detected":
                    echo(f"[SKIP] {model_name}: no grouping/aggregation detected (treated as staging/non-semantic).")
                    stats["skipped"] += 1
                    skipped_list.append(SkippedEntry(item=model_name, reason="no grouping/aggregation detected"))
                    continue
                if not dry_run:
                    writer.write(meta)
                stats["parsed"] += 1

                # Count extracted items
                entity_created = "entity" in meta and meta.get("entity", {}).get("name") == model_name
                dimensions_count = len(meta.get("dimensions", []))
                metrics_count = len(meta.get("metrics", []))

                if debug or dry_run:
                    prefix = "[DRY-RUN] " if dry_run else "[AXI-DEBUG] "
                    echo(f"{prefix}Would extract: {model_name} ({metrics_count} metrics, {dimensions_count} dimensions)")
            else:
                # Model was not promoted - this is a skip, not a failure
                stats["skipped"] += 1
                skip_reason = promotion_result.reason if promotion_result else "not promoted"
                skipped_list.append(SkippedEntry(item=model_name, reason=skip_reason))
        except Exception as e:
            stats["failed"] += 1
            status = "error"
            error_message = str(e)
            failures_list.append(FailureEntry(item=model_name, error=str(e)))
            # Always report failures to stderr
            typer.echo(f"[FAIL] {model_name}: {e}", err=True)

        # Record promotion result (skip in dry-run)
        if not dry_run:
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

    if not dry_run:
        echo("Rebuilding Index...")
        indexer.build_index()

    # Build run summary
    run_status = RunSummary.compute_status(stats["parsed"], stats["failed"])
    final_exit_code = RunSummary.compute_exit_code(run_status)
    run_summary = RunSummary(
        command="extract",
        status=run_status,
        exit_code=final_exit_code,
        scanned=stats["scanned"],
        processed=stats["parsed"],
        skipped=stats["skipped"],
        failed=stats["failed"],
        failures=failures_list,
        skipped_items=skipped_list,
        started_at=run_start,
        completed_at=RunSummary.now_iso()
    )

    # Write summary file if requested
    if summary:
        with open(summary, "w") as f:
            f.write(run_summary.to_json())
        echo(f"Run summary written to: {summary}")

    echo("\n======== AXI EXTRACTION SUMMARY ========")
    echo(f"Models scanned: {stats['scanned']}")
    echo(f"Models parsed successfully: {stats['parsed']}")
    echo(f"Models skipped: {stats['skipped']}")
    echo(f"Models failed: {stats['failed']}")
    echo(f"Status: {run_status}")
    if dry_run:
        echo("[DRY-RUN] No files were written")
    echo("========================================")

    # Exit with appropriate code - NEVER return success if any item failed
    if stats["failed"] > 0:
        # Partial or full failure - CI must be informed
        raise typer.Exit(exit_codes.EXTRACTION_ERROR)

glossary_app = typer.Typer()
app.add_typer(glossary_app, name="glossary", help="Manage business glossary terms and definitions")

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

# Glossary term management
term_store = GlossaryTermStore()

@app.command()
def version():
    """
    Show CLI and backend package versions.
    """
    try:
        cli_version = metadata.version("axi-cli")
    except metadata.PackageNotFoundError:
        from axi_cli import __version__ as cli_version

    try:
        backend_version = metadata.version("axi-semantic")
    except metadata.PackageNotFoundError:
        try:
            from axi.version import get_version as get_backend_version
            backend_version = get_backend_version()
        except Exception:
            backend_version = "unknown"

    typer.echo(json.dumps({
        "cli": cli_version,
        "backend": backend_version
    }, indent=2))

# Deploy governed semantic views (SQL-first; no execution engine)
deploy_app = typer.Typer(help="Deploy governed semantic views (generate CREATE VIEW SQL; no execution)")

@deploy_app.command("views")
def deploy_views(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show plan and SQL only; do not record state"),
    record_state: bool = typer.Option(False, "--record-state", help="Record deployed view state in AXI metadata (use after applying SQL)"),
    schema: str = typer.Option("axi", "--schema", "-s", help="Schema name for views (e.g. axi)"),
    warehouse: str = typer.Option("snowflake", "--warehouse", "-w", help="Warehouse dialect (snowflake)"),
    version_coexistence: bool = typer.Option(False, "--version-coexistence", help="Name views with version suffix for coexistence"),
    contract_mode: Optional[str] = typer.Option(None, "--contract-mode", help="Contract enforcement: warn | strict (overrides axi.yml)"),
):
    """
    Plan deployment of metric views: generate CREATE VIEW SQL per metric.
    Use --dry-run to show plan and SQL without recording deployment state.
    Use --record-state after manually applying SQL to persist deployment state for conflict detection.
    No execution engine: SQL is copy-pasteable for manual or CI execution.
    """
    from axi.views.planner import DeploymentPlanner
    from axi.exceptions import DeploymentValidationError

    # Resolve contract mode: CLI flag > axi.yml > env/settings
    resolved_contract_mode: Optional[str] = None
    if contract_mode is not None:
        cm = (contract_mode or "").strip().lower()
        if cm not in ("warn", "strict"):
            typer.echo(f"Invalid --contract-mode '{contract_mode}'; use warn or strict.", err=True)
            raise typer.Exit(1)
        resolved_contract_mode = cm
    else:
        cwd = os.getcwd()
        project_root = cwd
        current = cwd
        while current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, "axi.yml")) or os.path.exists(os.path.join(current, "dbt_project.yml")):
                project_root = current
                break
            current = os.path.dirname(current)
        config_path = os.path.join(project_root, "axi.yml")
        if os.path.exists(config_path):
            config = load_config(config_path)
            resolved_contract_mode = getattr(config, "contract_enforcement", None) or "strict"
        if resolved_contract_mode is None:
            resolved_contract_mode = get_settings().contract_enforcement_mode

    indexer = MetadataIndexer(METADATA_DIR)
    planner = DeploymentPlanner(
        indexer,
        schema=schema,
        warehouse=warehouse,
        replace_existing=True,
        version_coexistence=version_coexistence,
        contract_mode=resolved_contract_mode,
    )
    try:
        plan = planner.plan()
    except DeploymentValidationError as e:
        typer.echo(format_deployment_validation_error(e), err=True)
        raise typer.Exit(1)

    for w in plan.warnings:
        typer.echo(f"WARNING: {w}", err=True)

    if dry_run:
        typer.echo("[DRY-RUN] Deployment plan (no state will be written):")
        typer.echo(f"  Create: {len(plan.create)} view(s)")
        typer.echo(f"  Replace: {len(plan.replace)} view(s)")
        typer.echo(f"  Drop (deprecated): {len(plan.drop)} view(s)")
        for a in plan.create:
            typer.echo(f"\n--- CREATE {a.view_name} ---")
            typer.echo(a.sql or "")
        for a in plan.replace:
            typer.echo(f"\n--- REPLACE {a.view_name} ---")
            typer.echo(a.sql or "")
        for a in plan.drop:
            typer.echo(f"\n--- DROP {a.view_name} ---")
            typer.echo(a.sql or "")
        return

    typer.echo(f"Plan: create={len(plan.create)}, replace={len(plan.replace)}, drop={len(plan.drop)}")
    for a in plan.create + plan.replace:
        typer.echo(f"\n--- {a.action.upper()} {a.view_name} ---")
        typer.echo(a.sql or "")
    for a in plan.drop:
        typer.echo(f"\n--- DROP {a.view_name} ---")
        typer.echo(a.sql or "")
    typer.echo("\n(No execution engine: run the SQL above in your warehouse to deploy.)")
    
    if record_state:
        from datetime import datetime, timezone
        from axi.views.deployment_validation import hash_view_definition, _extract_view_body_from_ddl
        
        typer.echo("\n[RECORDING STATE]")
        deployed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        for a in plan.create + plan.replace:
            body = _extract_view_body_from_ddl(a.sql or "")
            definition_hash = hash_view_definition(body)
            indexer.record_deployed_view(
                view_name=a.view_name,
                metric_name=a.metric_name,
                metric_version=a.metric_version,
                schema_name=schema,
                deployed_at_utc=deployed_at,
                deprecated=a.deprecated,
                definition_hash=definition_hash,
            )
            typer.echo(f"  ✓ Recorded deployment state for {a.view_name}")
        
        for a in plan.drop:
            indexer.remove_deployed_view(a.view_name)
            typer.echo(f"  ✓ Removed deployment state for {a.view_name}")
        
        typer.echo(f"\nDeployment state persisted. Conflict detection and drop_deprecated now available.")

app.add_typer(deploy_app, name="deploy")

drop_app = typer.Typer(help="Drop views (plan only; no execution)")

@drop_app.command("deprecated")
def drop_deprecated(
    schema: str = typer.Option("axi", "--schema", "-s", help="Schema filter (optional)"),
):
    """
    Plan dropping deprecated views: generate DROP VIEW IF EXISTS SQL.
    No execution: SQL is copy-pasteable.
    """
    from axi.views.planner import DeploymentPlanner

    indexer = MetadataIndexer(METADATA_DIR)
    planner = DeploymentPlanner(indexer, schema=schema or "axi")
    plan = planner.plan_drop_deprecated()

    if not plan.drop:
        typer.echo("No deprecated views in deployment state.")
        return
    typer.echo(f"Deprecated views to drop: {len(plan.drop)}")
    for a in plan.drop:
        typer.echo(f"\n--- DROP {a.view_name} ---")
        typer.echo(a.sql or "")
    typer.echo("\n(No execution engine: run the SQL above to drop.)")

app.add_typer(drop_app, name="drop")

# Metric versioning and deprecation
promote_app = typer.Typer(help="Promote metrics (version bump)")
@promote_app.command("metric")
def promote_metric(
    name: str = typer.Argument(..., help="Metric name"),
    version: Optional[str] = typer.Option(None, "--version", "-v", help="New version (e.g. 1.1); required for breaking changes"),
):
    """
    Promote a metric: set status active and optionally bump version.
    Use --version when making breaking changes (expression, grain, dimensions, aggregation, model).
    """
    from axi.metrics.versioning import is_breaking_change, version_compare
    indexer = MetadataIndexer(METADATA_DIR)
    existing = indexer.get_metric(name)
    if not existing:
        typer.echo(f"Metric '{name}' not found.", err=True)
        raise typer.Exit(exit_codes.NOT_FOUND)
    indexer.update_metric_version_status(name, status="active")
    if version:
        indexer.update_metric_version_status(name, version=version)
        typer.echo(f"Promoted metric '{name}' to version {version}.")
    else:
        typer.echo(f"Promoted metric '{name}' (status active, version unchanged: {existing.get('version', '1.0')}).")

app.add_typer(promote_app, name="promote")

deprecate_app = typer.Typer(help="Deprecate metrics")
@deprecate_app.command("metric")
def deprecate_metric(
    name: str = typer.Argument(..., help="Metric name"),
    replacement: Optional[str] = typer.Option(None, "--replacement", "-r", help="Replacement metric name"),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Deprecation date (YYYY-MM-DD)"),
):
    """
    Deprecate a metric: set status deprecated, optional replacement and date.
    """
    indexer = MetadataIndexer(METADATA_DIR)
    existing = indexer.get_metric(name)
    if not existing:
        typer.echo(f"Metric '{name}' not found.", err=True)
        raise typer.Exit(exit_codes.NOT_FOUND)
    indexer.update_metric_version_status(
        name,
        status="deprecated",
        deprecation_date=date,
        replacement_metric=replacement,
    )
    typer.echo(f"Deprecated metric '{name}'." + (f" Replacement: {replacement}." if replacement else ""))

app.add_typer(deprecate_app, name="deprecate")

diff_app = typer.Typer(help="Diff metrics")
@diff_app.command("metrics")
def diff_metrics_cmd(
    name1: str = typer.Argument(..., help="First metric name"),
    name2: str = typer.Argument(..., help="Second metric name (or same as name1 to diff versions)"),
    version1: Optional[str] = typer.Option(None, "--version1", "-v1", help="First metric version from history (e.g. 1.0)"),
    version2: Optional[str] = typer.Option(None, "--version2", "-v2", help="Second metric version from history (e.g. 1.1)"),
):
    """
    Show human-readable diff between two metrics. Uses persisted history when --version1/--version2 are given.
    """
    from axi.metrics.versioning import diff_metrics as do_diff
    indexer = MetadataIndexer(METADATA_DIR)
    if version1:
        rec1 = indexer.get_metric_version_record(name1, version1)
        if not rec1:
            typer.echo(f"Metric '{name1}' version '{version1}' not found in history.", err=True)
            raise typer.Exit(exit_codes.NOT_FOUND)
        m1 = rec1["definition_snapshot"]
        label1 = f"{name1}@{version1}"
    else:
        m1 = indexer.get_metric(name1)
        if not m1:
            typer.echo(f"Metric '{name1}' not found.", err=True)
            raise typer.Exit(exit_codes.NOT_FOUND)
        label1 = name1
    if version2:
        rec2 = indexer.get_metric_version_record(name2, version2)
        if not rec2:
            typer.echo(f"Metric '{name2}' version '{version2}' not found in history.", err=True)
            raise typer.Exit(exit_codes.NOT_FOUND)
        m2 = rec2["definition_snapshot"]
        label2 = f"{name2}@{version2}"
    else:
        m2 = indexer.get_metric(name2)
        if not m2:
            typer.echo(f"Metric '{name2}' not found.", err=True)
            raise typer.Exit(exit_codes.NOT_FOUND)
        label2 = name2
    typer.echo(do_diff(m1, m2, name_a=label1, name_b=label2))

app.add_typer(diff_app, name="diff")

# Usage tracking: Snowflake QUERY_HISTORY ingestion (read-only)
usage_app = typer.Typer(help="Usage tracking (read-only warehouse access)")
@usage_app.command("ingest-snowflake")
def usage_ingest_snowflake(
    days: int = typer.Option(7, "--days", "-d", help="Last N days of QUERY_HISTORY (max 7 for INFORMATION_SCHEMA)"),
    limit: int = typer.Option(10000, "--limit", "-l", help="Max rows to fetch and match"),
):
    """
    Ingest Snowflake QUERY_HISTORY, match to AXI fingerprints, update metric_usage.
    Read-only. Run on a schedule (e.g. cron) to keep usage up to date.
    """
    from axi.usage.snowflake_ingest import ingest_snowflake_usage
    indexer = MetadataIndexer(METADATA_DIR)
    try:
        runner = SnowflakeRunner()
    except ValueError as e:
        typer.echo(f"Snowflake credentials required: {e}", err=True)
        raise typer.Exit(exit_codes.CONNECTION_ERROR)
    typer.echo(f"Ingesting QUERY_HISTORY (last {days} days, limit {limit})...")
    matched = ingest_snowflake_usage(indexer, runner, days_back=days, result_limit=limit)
    typer.echo(f"Matched {matched} query log rows to AXI metrics.")

app.add_typer(usage_app, name="usage")

@glossary_app.command("list")
def glossary_list():
    """
    List glossary terms (latest version).
    """
    terms = term_store.list_terms()
    typer.echo(json.dumps([t.model_dump() for t in terms], indent=2, default=str))

@glossary_app.command("show")
def glossary_show(term: str):
    """
    Show a single glossary term.
    """
    t = term_store.get_term(term)
    if not t:
        typer.echo(f"Term '{term}' not found.")
        raise typer.Exit(1)
    typer.echo(json.dumps(t.model_dump(), indent=2, default=str))

@glossary_app.command("create")
def glossary_create(
    term: str,
    definition: str = typer.Option(..., "--definition", "-d"),
    status: str = typer.Option("draft", "--status", help="draft|approved|deprecated"),
    derived_from: str = typer.Option("", "--derived-from", help="Comma-separated metric/dimension names"),
    applies_to_entities: str = typer.Option("", "--entities", help="Comma-separated entity names"),
    synonyms: str = typer.Option("", "--synonyms", help="Comma-separated synonyms"),
    scope: str = typer.Option(None, "--scope", help="Business scope (optional)"),
    notes: str = typer.Option(None, "--notes", help="Optional notes"),
):
    """
    Create a glossary term.
    """
    try:
        t = term_store.create_term(
            term=term,
            definition=definition,
            status=status,
            derived_from=[i.strip() for i in derived_from.split(",") if i.strip()],
            applies_to_entities=[e.strip() for e in applies_to_entities.split(",") if e.strip()],
            synonyms=[s.strip() for s in synonyms.split(",") if s.strip()],
            scope=scope,
            notes=notes,
        )
        typer.echo(json.dumps(t.model_dump(), indent=2, default=str))
    except AXIBaseException as e:
        typer.echo(format_axi_error(e), err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

@glossary_app.command("edit")
def glossary_edit(
    term: str,
    definition: str = typer.Option(None, "--definition", "-d"),
    status: str = typer.Option(None, "--status", help="draft|approved|deprecated"),
    derived_from: str = typer.Option(None, "--derived-from", help="Comma-separated metric/dimension names"),
    applies_to_entities: str = typer.Option(None, "--entities", help="Comma-separated entity names"),
    synonyms: str = typer.Option(None, "--synonyms", help="Comma-separated synonyms"),
    scope: str = typer.Option(None, "--scope", help="Business scope (optional)"),
    notes: str = typer.Option(None, "--notes", help="Optional notes"),
):
    """
    Edit a glossary term (creates new version).
    """
    try:
        derived = [i.strip() for i in derived_from.split(",")] if derived_from else None
        ents = [e.strip() for e in applies_to_entities.split(",")] if applies_to_entities else None
        syns = [s.strip() for s in synonyms.split(",")] if synonyms else None
        t = term_store.edit_term(
            term=term,
            definition=definition,
            status=status,
            derived_from=derived if derived is not None else None,
            applies_to_entities=ents if ents is not None else None,
            synonyms=syns if syns is not None else None,
            scope=scope,
            notes=notes,
        )
        typer.echo(json.dumps(t.model_dump(), indent=2, default=str))
    except AXIBaseException as e:
        typer.echo(format_axi_error(e), err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

@glossary_app.command("deprecate")
def glossary_deprecate(term: str):
    """
    Deprecate a glossary term (creates new version).
    """
    try:
        t = term_store.deprecate_term(term)
        typer.echo(json.dumps(t.model_dump(), indent=2, default=str))
    except AXIBaseException as e:
        typer.echo(format_axi_error(e), err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

# Semantic drift check (advisory)
semantic_app = typer.Typer()
app.add_typer(semantic_app, name="semantic", help="Check semantic drift and alignment with glossary")

@semantic_app.command("check")
def semantic_check(term: str = typer.Option(None, "--term", help="Specific glossary term to check")):
    """
    Run semantic drift/conflict checks against approved glossary terms.
    """
    results = detect_drift(term_name=term)
    if not results:
        typer.echo("No findings.")
        return
    for r in results:
        typer.echo(json.dumps(r, indent=2, default=str))

@semantic_app.command("suggest")
def semantic_suggest(item: str = typer.Option(None, "--item", help="Optional specific item to evaluate")):
    """
    Suggest promoted items that might merit a glossary term (advisory only).
    """
    results = suggest_candidates(item_name=item)
    if not results:
        typer.echo("No suggestions.")
        return
    for r in results:
        typer.echo(json.dumps(r, indent=2, default=str))

@semantic_app.command("explain")
def semantic_explain(
    subject: str = typer.Argument(..., help="Metric or entity name"),
    subject_type: str = typer.Option("metric", "--type", "-t", help="metric|entity")
):
    """
    Explain a metric/entity using approved glossary language only.
    """
    res = explain_subject(subject, subject_type)
    typer.echo(json.dumps(res, indent=2, default=str))

@semantic_app.command("impact")
def semantic_impact(
    subject: str = typer.Option(None, "--subject", help="Glossary term or semantic item name"),
    change_type: str = typer.Option("glossary_edit", "--change-type", help="glossary_edit|glossary_deprecate|semantic_change")
):
    """
    Advisory impact awareness for glossary or semantic changes.
    """
    if not subject:
        typer.echo("Please provide --subject")
        raise typer.Exit(1)
    res = run_impact_analysis(change_type=change_type, subject=subject)
    if not res:
        typer.echo("No impact findings.")
        return
    for r in res:
        typer.echo(json.dumps(r, indent=2, default=str))

# History summaries
history_app = typer.Typer()
app.add_typer(history_app, name="history", help="View glossary change history and summaries")

@history_app.command("explain")
def history_explain(term: str = typer.Option(None, "--term", help="Specific glossary term to summarize")):
    """
    Plain-English summaries of glossary changes (latest vs previous).
    """
    summaries = summarize_changes(term_name=term)
    if not summaries:
        typer.echo("No change summaries available.")
        return
    for s in summaries:
        typer.echo(s["summary"])
        if s.get("impact"):
            typer.echo(f"Impact: {s['impact']}")
        typer.echo("")

# Diagnostics CLI (grain)
diagnostics_app = typer.Typer()
app.add_typer(diagnostics_app, name="diagnostics", help="Run diagnostic checks on semantic metadata")

@diagnostics_app.command("grain")
def diagnostics_grain(model: str = typer.Option(None, "--model", "-m", help="Optional model name to inspect")):
    """
    Generate semantic grain diagnostics (advisory, read-only).
    """
    from axi.diagnostics import grain_report
    report = grain_report.full_report(model_name=model)
    if model and not report.get("models"):
        typer.echo(f"No model named '{model}' found in metadata.")
        raise typer.Exit(1)
    typer.echo(json.dumps(report, indent=2, default=str))

metrics_app = typer.Typer()
app.add_typer(metrics_app, name="metrics", help="List, describe, and query metrics")

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
    except AXIBaseException as e:
        typer.echo(format_axi_error(e), err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

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
app.add_typer(cache_app, name="cache", help="Manage query result cache")

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
app.add_typer(mat_app, name="materialize", help="Create and refresh materialized metric tables")

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
app.add_typer(mart_app, name="mart", help="Create semantic marts (multi-metric tables)")

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

app.add_typer(dbt_app, name="dbt", help="Load and analyze dbt manifests and models")

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
            if meta.get("grain_status") == "not_detected":
                typer.echo(f"[SKIP] {model_name}: no grouping/aggregation detected (treated as staging/non-semantic).")
                continue
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
            rows, cols, _ = runner.execute_query(sql)
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
    except AXIBaseException as e:
        typer.echo(format_axi_error(e), err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

@app.command()
def ui(
    host: str = typer.Option("localhost", help="Host to bind to"),
    port: int = typer.Option(8000, help="Port to bind to"),
    frontend: bool = typer.Option(False, "--frontend", help="Also start the frontend dev server (npm required)"),
    frontend_port: int = typer.Option(5173, "--frontend-port", help="Port for the Vite dev server")
):
    """
    Start the Semantic Explorer UI (Backend API).
    """
    import uvicorn
    
    frontend_proc = None
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(current_dir)), "frontend"))

    if frontend:
        if not os.path.exists(os.path.join(frontend_dir, "package.json")):
            typer.echo(f"[WARN] Frontend not found at {frontend_dir}; skipping frontend start.")
        else:
            try:
                typer.echo(f"Starting frontend dev server (npm run dev -- --host --port {frontend_port}) in {frontend_dir}")
                frontend_proc = subprocess.Popen(
                    ["npm", "run", "dev", "--", "--host", "--port", str(frontend_port)],
                    cwd=frontend_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                atexit.register(lambda: frontend_proc and frontend_proc.terminate())
            except FileNotFoundError:
                typer.echo("[ERROR] npm not found. Install Node/npm to run the frontend or start it manually.")
                frontend_proc = None

    typer.echo(f"Starting AXI API at http://{host}:{port}")
    if not frontend:
        typer.echo("To view the UI, run in another terminal:")
        typer.echo("  cd frontend && npm run dev")
        typer.echo(f"Then open http://{host}:{frontend_port}")
    else:
        typer.echo(f"Frontend dev server will be available at http://{host}:{frontend_port}")
    
    # Run uvicorn programmatically
    # We need to target the app object.
    # Assuming axi is installed as package, or we use string reference.
    # To work in dev setup without package install, we might need sys path hacks handled above.
    
    try:
        # Change to backend directory for proper module loading
        original_dir = os.getcwd()
        os.chdir(backend_path)
        uvicorn.run("axi.api.main:app", host=host, port=port, reload=True)
    finally:
        if frontend_proc and frontend_proc.poll() is None:
            frontend_proc.terminate()
        # Restore original directory
        try:
            os.chdir(original_dir)
        except:
            pass

@app.command()
def snowflake(
    action: str = typer.Argument(..., help="sync, tables, columns, lineage, policies, constraints"),
    arg: str = typer.Argument(None, help="Table name for columns/lineage"),
    schemas: Optional[str] = typer.Option(None, "--schemas", help="Comma-separated list of schemas to sync (e.g., 'MARTS,ANALYTICS')"),
    views: Optional[str] = typer.Option(None, "--views", help="Comma-separated view patterns for semantic extraction (e.g., 'mart_%,fact_%')"),
    skip_constraints: bool = typer.Option(False, "--skip-constraints", help="Skip PK/FK constraint detection"),
    skip_inferred: bool = typer.Option(False, "--skip-inferred", help="Skip inferring relationships from naming conventions"),
    skip_semantic: bool = typer.Option(False, "--skip-semantic", help="Skip semantic metadata extraction from views"),
):
    """
    Manage Snowflake direct integration (no dbt required).

    Actions:
      - sync: Full sync of Snowflake metadata + semantic extraction from views
      - tables: List all synced tables
      - columns <table>: List columns for a table
      - lineage: Show table lineage from Snowflake
      - policies: List masking and row access policies
      - constraints: List detected PK/FK constraints

    Examples:
      # Full sync with semantic extraction
      axi snowflake sync

      # Sync specific schemas only
      axi snowflake sync --schemas MARTS,ANALYTICS

      # Sync with view pattern filtering for semantic extraction
      axi snowflake sync --views "mart_%,fact_%"

      # Sync without semantic extraction (schema metadata only)
      axi snowflake sync --skip-semantic
    """
    from axi.snowflake.extractor import SnowflakeMetadataExtractor

    indexer = MetadataIndexer(METADATA_DIR)

    if action == "sync":
        typer.echo("🔄 Starting Snowflake metadata sync...")
        typer.echo(f"   Metadata dir: {METADATA_DIR}")

        # Parse optional parameters
        schema_list = [s.strip() for s in schemas.split(",")] if schemas else None
        view_patterns = [v.strip() for v in views.split(",")] if views else None

        if schema_list:
            typer.echo(f"   Schemas: {', '.join(schema_list)}")
        if view_patterns:
            typer.echo(f"   View patterns: {', '.join(view_patterns)}")

        extractor = SnowflakeMetadataExtractor(indexer)
        extractor.sync(
            include_constraints=not skip_constraints,
            infer_relationships=not skip_inferred,
            extract_semantic=not skip_semantic,
            schemas=schema_list,
            view_patterns=view_patterns
        )

        typer.echo("✅ Snowflake sync complete!")
        typer.echo("\nNext steps:")
        typer.echo("  - View metrics: axi metrics list")
        typer.echo("  - View entities: axi entities list")
        typer.echo("  - Start UI: axi ui")

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

    elif action == "constraints":
        extractor = SnowflakeMetadataExtractor(indexer)
        constraints = extractor.list_constraints()
        if constraints:
            typer.echo(f"\nFound {len(constraints)} constraints:\n")
            for c in constraints:
                typer.echo(f"  {c['table_name']}.{c['columns']} ({c['type']})")
                if c['referenced_table']:
                    typer.echo(f"    → {c['referenced_table']}.{c['referenced_columns']}")
        else:
            typer.echo("No constraints found. Run 'axi snowflake sync' first.")

    else:
        typer.echo(f"Unknown action: {action}")

@app.command()
def demo(
    output: str = typer.Option("./demo_project", "--output", "-o", help="Output directory for demo project"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing files"),
    extract: bool = typer.Option(True, "--extract/--no-extract", help="Run extraction after generating"),
):
    """
    Generate a sample e-commerce project for demos and testing.

    Creates:
    - Sample SQL models (orders, customers, products)
    - axi.yml configuration
    - Glossary terms

    Example:
        axi demo --output ./my_demo
        axi demo --force --extract
    """
    from axi.demo import generate_sample_project

    typer.echo(f"Generating sample project in {output}...")

    stats = generate_sample_project(output, force=force)

    typer.echo(f"Created {stats['models']} models, {stats['glossary']} glossary terms, {stats['config']} config file")

    if extract:
        typer.echo("\nRunning extraction...")
        import os
        original_dir = os.getcwd()
        try:
            os.chdir(output)
            metadata_dir = os.path.join(output, "metadata_store")
            indexer = MetadataIndexer(metadata_dir)
            writer = MetadataWriter(metadata_dir)

            # Load config for promotion rules
            config_path = os.path.join(output, "axi.yml")
            if os.path.exists(config_path):
                config = load_config(config_path)
            else:
                from axi.config.loader import Config, PromotionRules
                config = Config(include=PromotionRules(folders=["models/*"], tags=["axi"]))

            promotion_engine = PromotionEngine(config)
            scanner = SqlScanner(os.path.join(output, "models"), promotion_engine)

            stats = {"scanned": 0, "parsed": 0, "metrics_extracted": 0, "failed": 0}
            for model in scanner.scan():
                stats["scanned"] += 1
                model_name = os.path.splitext(os.path.basename(model.path))[0]
                promotion_result = getattr(model, "promotion_result", None)
                if promotion_result and promotion_result.promoted and model.content:
                    try:
                        meta = extract_metadata(model.content, model_name, config=config)
                        writer.write(meta)
                        stats["parsed"] += 1
                        stats["metrics_extracted"] += len(meta.get("metrics", []))
                    except Exception:
                        stats["failed"] += 1
                else:
                    stats["failed"] += 1

            indexer.build_index()
            typer.echo(f"Extracted {stats['parsed']} models, {stats['metrics_extracted']} metrics")
        finally:
            os.chdir(original_dir)

    typer.echo(f"\n[green]Demo project ready![/green]")
    typer.echo(f"Next steps:")
    typer.echo(f"  cd {output}")
    typer.echo(f"  axi ui")

if __name__ == "__main__":
    app()
