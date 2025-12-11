# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import yaml
import typer
from typing import Optional
from pathlib import Path


def _write_file(file_path: str, content: str, force: bool = False) -> bool:
    """Write file, return True if written, False if skipped."""
    if os.path.exists(file_path) and not force:
        typer.echo(f"⚠ File {file_path} already exists. Use --force to overwrite.")
        return False
    
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)
        typer.echo(f"✓ Created {file_path}")
        return True
    except Exception as e:
        typer.echo(f"✗ Error creating {file_path}: {e}")
        raise typer.Exit(1)


def generate_metric(name: str, entity: str, force: bool = False) -> None:
    """
    Generate a metric definition file.
    """
    current_dir = os.getcwd()
    metrics_dir = os.path.join(current_dir, "metrics")
    os.makedirs(metrics_dir, exist_ok=True)
    
    file_name = f"{entity}__{name}.yml"
    file_path = os.path.join(metrics_dir, file_name)
    
    content = f"""metric: {name}
entity: {entity}
type: sum
expression: "SUM(<field>)"
dimensions: []
description: ""
tags: []
"""
    
    _write_file(file_path, content, force)
    typer.echo(f"\n✓ Metric '{name}' generated for entity '{entity}'")
    typer.echo(f"  Edit {file_path} to customize the metric definition")


def generate_dimension(name: str, entity: str, force: bool = False) -> None:
    """
    Generate a dimension definition file.
    """
    current_dir = os.getcwd()
    dimensions_dir = os.path.join(current_dir, "dimensions")
    os.makedirs(dimensions_dir, exist_ok=True)
    
    file_name = f"{entity}__{name}.yml"
    file_path = os.path.join(dimensions_dir, file_name)
    
    content = f"""dimension: {name}
entity: {entity}
data_type: string
description: ""
cardinality: null
tags: []
"""
    
    _write_file(file_path, content, force)
    typer.echo(f"\n✓ Dimension '{name}' generated for entity '{entity}'")
    typer.echo(f"  Edit {file_path} to customize the dimension definition")


def generate_glossary(term: str, force: bool = False) -> None:
    """
    Generate a glossary term definition file.
    """
    current_dir = os.getcwd()
    glossary_dir = os.path.join(current_dir, "glossary")
    os.makedirs(glossary_dir, exist_ok=True)
    
    file_name = f"{term}.yml"
    file_path = os.path.join(glossary_dir, file_name)
    
    content = f"""term: {term}
definition: ""
related_entities: []
related_metrics: []
tags: []
"""
    
    _write_file(file_path, content, force)
    typer.echo(f"\n✓ Glossary term '{term}' generated")
    typer.echo(f"  Edit {file_path} to add definition and relationships")


def generate_rule_promotion(force: bool = False) -> None:
    """
    Generate or update promotion.yml rule file.
    """
    current_dir = os.getcwd()
    rules_dir = os.path.join(current_dir, "rules")
    os.makedirs(rules_dir, exist_ok=True)
    
    file_path = os.path.join(rules_dir, "promotion.yml")
    
    # If file exists and not forcing, try to merge
    if os.path.exists(file_path) and not force:
        try:
            with open(file_path, "r") as f:
                existing = yaml.safe_load(f) or {}
            
            # Check if rules already exist
            if "rules" in existing and existing["rules"]:
                typer.echo(f"⚠ File {file_path} already contains rules.")
                typer.echo("  Use --force to overwrite, or edit manually to add new rules.")
                return
        except Exception:
            pass
    
    content = """rules:
  - include: ["models/semantic/*"]
  - tag: "axi"
  - exclude: ["models/tmp/*"]
"""
    
    _write_file(file_path, content, force)
    typer.echo(f"\n✓ Promotion rule file generated/updated")
    typer.echo(f"  Edit {file_path} to customize promotion rules")

