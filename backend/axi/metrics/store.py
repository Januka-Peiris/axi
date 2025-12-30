# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import yaml
import os
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

class MetricStore:
    """
    Manages user-defined metrics stored in YAML files.
    Metrics are stored in: axi/metrics/<metric_name>.yml
    """
    
    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize metric store.
        
        Args:
            project_root: Root directory of AXI project. If None, searches for axi.yml.
        """
        if project_root:
            self.project_root = os.path.abspath(project_root)
        else:
            # Find project root by looking for axi.yml
            self.project_root = self._find_project_root()
        
        self.metrics_dir = os.path.join(self.project_root, "axi", "metrics")
        os.makedirs(self.metrics_dir, exist_ok=True)
    
    def _find_project_root(self) -> str:
        """Find project root by searching for axi.yml."""
        current = os.getcwd()
        while current != os.path.dirname(current):
            if os.path.exists(os.path.join(current, "axi.yml")):
                return current
            current = os.path.dirname(current)
        # Fallback to current directory
        return os.getcwd()
    
    def _get_metric_path(self, metric_name: str) -> str:
        """Get file path for a metric."""
        # Sanitize metric name for filename
        safe_name = metric_name.replace("/", "_").replace("\\", "_")
        return os.path.join(self.metrics_dir, f"{safe_name}.yml")

    def _extract_metric_references(self, expr: str) -> List[str]:
        """Extract all {metric_name} patterns from expression."""
        if not expr:
            return []
        pattern = r'\{([a-z_][a-z0-9_]*)\}'
        return re.findall(pattern, expr, re.IGNORECASE)

    def _populate_depends_on(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """Auto-populate depends_on field from expression."""
        expression = metric_data.get("expression", "")
        metric_refs = self._extract_metric_references(expression)

        if metric_refs:
            # Only set depends_on if there are references
            metric_data["depends_on"] = metric_refs
        elif "depends_on" not in metric_data:
            # If no references and field not set, set to empty list
            metric_data["depends_on"] = []

        return metric_data

    def create(self, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new metric.
        
        Args:
            metric_data: Metric definition dict with keys: metric, description, entity, expression, etc.
        
        Returns:
            Full metric definition
        """
        metric_name = metric_data.get("metric")
        if not metric_name:
            raise ValueError("Metric name is required")
        
        path = self._get_metric_path(metric_name)
        if os.path.exists(path):
            raise ValueError(f"Metric '{metric_name}' already exists")

        # Auto-populate depends_on field from expression
        metric_data = self._populate_depends_on(metric_data)

        # Add metadata
        metric_data["created_at"] = metric_data.get("created_at")
        metric_data["updated_at"] = metric_data.get("updated_at")

        # Write YAML file
        with open(path, "w") as f:
            yaml.dump(metric_data, f, default_flow_style=False, sort_keys=False)
        
        return metric_data
    
    def get(self, metric_name: str) -> Optional[Dict[str, Any]]:
        """Get a metric by name."""
        path = self._get_metric_path(metric_name)
        if not os.path.exists(path):
            return None
        
        with open(path, "r") as f:
            return yaml.safe_load(f)
    
    def update(self, metric_name: str, metric_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing metric.
        
        Args:
            metric_name: Name of metric to update
            metric_data: Updated metric definition (will be merged with existing)
        """
        path = self._get_metric_path(metric_name)
        if not os.path.exists(path):
            raise ValueError(f"Metric '{metric_name}' not found")
        
        # Load existing
        existing = self.get(metric_name)
        if not existing:
            raise ValueError(f"Metric '{metric_name}' not found")
        
        # Merge updates
        updated = {**existing, **metric_data}
        updated["metric"] = metric_name  # Ensure name matches
        updated["updated_at"] = metric_data.get("updated_at")

        # Auto-populate depends_on field if expression changed
        updated = self._populate_depends_on(updated)

        # Write back
        with open(path, "w") as f:
            yaml.dump(updated, f, default_flow_style=False, sort_keys=False)
        
        return updated
    
    def delete(self, metric_name: str) -> bool:
        """Delete a metric."""
        path = self._get_metric_path(metric_name)
        if not os.path.exists(path):
            return False
        
        os.remove(path)
        return True
    
    def list_all(self) -> List[Dict[str, Any]]:
        """List all user-defined metrics."""
        metrics = []
        if not os.path.exists(self.metrics_dir):
            return metrics
        
        for filename in os.listdir(self.metrics_dir):
            if filename.endswith(".yml") or filename.endswith(".yaml"):
                metric_name = os.path.splitext(filename)[0]
                metric = self.get(metric_name)
                if metric:
                    metrics.append(metric)
        
        return metrics

