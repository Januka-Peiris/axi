# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import yaml
import typer
from typing import Optional
from pathlib import Path


def _get_dbt_project_name(root_dir: str) -> Optional[str]:
    """Detect dbt project name from dbt_project.yml if present."""
    dbt_project_path = os.path.join(root_dir, "dbt_project.yml")
    if os.path.exists(dbt_project_path):
        try:
            with open(dbt_project_path, "r") as f:
                data = yaml.safe_load(f)
                return data.get("name")
        except Exception:
            pass
    return None


def _create_directory(path: str) -> None:
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def _write_file(file_path: str, content: str, force: bool = False) -> bool:
    """Write file, return True if written, False if skipped."""
    if os.path.exists(file_path) and not force:
        typer.echo(f"  ⚠ Skipping {file_path} (already exists, use --force to overwrite)")
        return False
    
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)
        typer.echo(f"  ✓ Created {file_path}")
        return True
    except Exception as e:
        typer.echo(f"  ✗ Error creating {file_path}: {e}")
        return False


def scaffold_project(force: bool = False) -> None:
    """
    Create a new AXI project in the current directory.
    """
    current_dir = os.getcwd()
    dbt_project_name = _get_dbt_project_name(current_dir)
    project_name = dbt_project_name or "my_project"
    
    typer.echo(f"🚀 Scaffolding AXI project in {current_dir}")
    if dbt_project_name:
        typer.echo(f"  ✓ Detected dbt project: {dbt_project_name}")
    
    # Create directories
    dirs = [
        "metadata_store",
        "rules",
        "glossary",
        "overrides",
        "metrics",
        "dimensions",
    ]
    
    for dir_name in dirs:
        dir_path = os.path.join(current_dir, dir_name)
        _create_directory(dir_path)
        typer.echo(f"  ✓ Created directory: {dir_name}/")
    
    # Generate axi.yml
    axi_yml_content = f"""project: {project_name}
dbt:
  compiled_path: target/compiled/{project_name}/models

promotion:
  mode: strict        # strict, auto, hybrid
  include:
    folders: ["models/semantic/*"]
    tags: ["axi"]
  exclude:
    folders: []
    tags: []

settings:
  warehouse: snowflake
  preview_limit: 50
"""
    _write_file(os.path.join(current_dir, "axi.yml"), axi_yml_content, force)
    
    # Generate rules/promotion.yml
    promotion_yml_content = """rules:
  - include: ["models/semantic/*"]
  - tag: "axi"
"""
    _write_file(os.path.join(current_dir, "rules", "promotion.yml"), promotion_yml_content, force)
    
    # Generate glossary/sample_term.yml
    glossary_yml_content = """term: customer
definition: Example glossary entry.
related_entities: []
related_metrics: []
tags: []
"""
    _write_file(os.path.join(current_dir, "glossary", "sample_term.yml"), glossary_yml_content, force)
    
    # Generate overrides/sample_entity.yml
    override_yml_content = """entity: orders
friendly_name: Orders
description: Override example.
"""
    _write_file(os.path.join(current_dir, "overrides", "sample_entity.yml"), override_yml_content, force)
    
    # Generate .gitignore
    gitignore_content = """# AXI
metadata_store/*.db
metadata_store/*.json
metadata_store/glossary.json

# dbt
target/
dbt_packages/
logs/

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
"""
    _write_file(os.path.join(current_dir, ".gitignore"), gitignore_content, force)
    
    # Generate README.md
    readme_content = f"""# {project_name}

AXI Semantic Layer Project

## Getting Started

### 1. Extract Metadata

Run AXI extraction to scan your SQL models and build the semantic layer:

```bash
axi extract
```

### 2. Working with dbt

If you're using dbt:

```bash
# Compile dbt models
dbt compile

# Extract metadata from compiled models
axi extract

# Start the UI
axi ui
```

### 3. Semantic Query Console

Access the semantic query console at http://localhost:5173/query after starting the UI.

Build queries by:
- Selecting metrics from the left panel
- Adding dimensions
- Applying filters
- Generating and running SQL

## Project Structure

- `metadata_store/` - SQLite database and JSON metadata
- `rules/` - Promotion rules for model selection
- `glossary/` - Business glossary terms
- `overrides/` - Entity and metric overrides
- `metrics/` - Metric definitions (generated)
- `dimensions/` - Dimension definitions (generated)

## Generating Resources

### Generate a Metric

```bash
axi generate metric revenue --entity orders
```

### Generate a Dimension

```bash
axi generate dimension date --entity orders
```

### Generate a Glossary Term

```bash
axi generate glossary customer
```

## Next Steps

1. Add your SQL models to the project
2. Tag models with `axi` tag or place in `models/semantic/` folder
3. Run `axi extract` to build the semantic layer
4. Use `axi ui` to explore metrics and dimensions
"""
    _write_file(os.path.join(current_dir, "README.md"), readme_content, force)
    
    typer.echo("\n✅ AXI project scaffolded successfully!")
    typer.echo("\nNext steps:")
    typer.echo("  1. Add your SQL models")
    typer.echo("  2. Run: axi extract")
    typer.echo("  3. Run: axi ui")

