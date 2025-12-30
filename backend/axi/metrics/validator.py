# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import sqlglot
from sqlglot import exp
import re
from typing import Dict, Any, List, Optional, Tuple, Set
from axi.metadata.indexer import MetadataIndexer

class MetricValidator:
    """
    Validates user-defined metrics according to semantic rules.
    """
    
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer

    def _extract_metric_references(self, expr: str) -> List[str]:
        """Extract all {metric_name} patterns from expression."""
        if not expr:
            return []
        pattern = r'\{([a-z_][a-z0-9_]*)\}'
        return re.findall(pattern, expr, re.IGNORECASE)

    def validate(self, metric_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate a metric definition.
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []
        
        # Required fields
        if not metric_data.get("metric"):
            errors.append("Metric name is required")
        if not metric_data.get("entity"):
            errors.append("Entity is required")
        if not metric_data.get("expression"):
            errors.append("Expression is required")
        
        if errors:
            return False, errors
        
        metric_name = metric_data["metric"]
        entity_name = metric_data["entity"]
        expression = metric_data["expression"]
        
        # Validate expression
        expr_errors = self._validate_expression(expression)
        errors.extend(expr_errors)
        
        # Validate entity exists
        entity = self.indexer.get_entity(entity_name)
        if not entity:
            errors.append(f"Entity '{entity_name}' not found")
        else:
            # Validate columns referenced in expression exist in entity
            col_errors = self._validate_columns(expression, entity)
            errors.extend(col_errors)
            
            # Validate grain dimensions
            if metric_data.get("grain"):
                grain_errors = self._validate_grain(metric_data["grain"], entity)
                errors.extend(grain_errors)
            
            # Validate allowed dimensions
            if metric_data.get("dimensions"):
                dim_errors = self._validate_dimensions(metric_data["dimensions"], entity)
                errors.extend(dim_errors)

        # Validate metric references
        metric_refs = self._extract_metric_references(expression)
        if metric_refs:
            ref_errors = self._validate_metric_references(metric_name, metric_refs)
            errors.extend(ref_errors)

        return len(errors) == 0, errors
    
    def _validate_expression(self, expression: str) -> List[str]:
        """
        Validate that expression contains exactly one aggregation.

        Rules:
        - Must contain exactly one aggregation (SUM, COUNT, AVG, MIN, MAX) OR reference other metrics
        - Cannot be a window function
        - Cannot be multiple aggregations (excluding those in metric references)
        """
        errors = []

        # Check if expression contains metric references
        has_metric_refs = bool(self._extract_metric_references(expression))

        # Remove metric references temporarily for parsing
        # Replace {metric_name} with placeholder to avoid parse errors
        temp_expr = re.sub(r'\{[a-z_][a-z0-9_]*\}', '0', expression, flags=re.IGNORECASE)

        try:
            # Parse expression
            parsed = sqlglot.parse_one(temp_expr)

            # Find all aggregations
            aggregations = list(parsed.find_all((exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)))

            # If there are no metric references, must have exactly one aggregation
            if not has_metric_refs:
                if len(aggregations) == 0:
                    errors.append("Expression must contain exactly one aggregation (SUM, COUNT, AVG, MIN, MAX) or reference other metrics using {metric_name}")
                elif len(aggregations) > 1:
                    errors.append("Expression must contain exactly one aggregation, found multiple")
            # If there are metric references, aggregations are optional (might be in referenced metrics)
            # But if there are aggregations in the expression itself, limit to one
            elif len(aggregations) > 1:
                errors.append("Expression can contain at most one aggregation when referencing other metrics")

            # Check for window functions
            window_functions = list(parsed.find_all((exp.Window, exp.RowNumber, exp.Rank, exp.DenseRank)))
            if window_functions:
                errors.append("Window functions are not allowed in metric expressions")

        except Exception as e:
            # If we can't parse, it might be because of the metric references
            if not has_metric_refs:
                errors.append(f"Invalid SQL expression: {str(e)}")

        return errors
    
    def _validate_columns(self, expression: str, entity: Dict[str, Any]) -> List[str]:
        """
        Validate that all columns referenced in expression exist in entity.
        """
        errors = []
        
        try:
            parsed = sqlglot.parse_one(expression)
            columns = list(parsed.find_all(exp.Column))
            
            entity_columns = entity.get("columns", [])
            # Handle both list of strings and list of dicts
            entity_col_names = set()
            for col in entity_columns:
                if isinstance(col, dict):
                    entity_col_names.add(col.get("name", ""))
                elif isinstance(col, str):
                    entity_col_names.add(col)
            
            for col in columns:
                col_name = col.alias_or_name
                if col_name and col_name not in entity_col_names:
                    # Check if it's a table-qualified column (table.column)
                    if "." in col_name:
                        parts = col_name.split(".", 1)
                        if len(parts) == 2 and parts[1] not in entity_col_names:
                            errors.append(f"Column '{parts[1]}' not found in entity")
                    else:
                        errors.append(f"Column '{col_name}' not found in entity")
        
        except Exception as e:
            # If parsing fails, skip column validation (expression validation will catch it)
            pass
        
        return errors
    
    def _validate_grain(self, grain: List[str], entity: Dict[str, Any]) -> List[str]:
        """
        Validate that grain dimensions belong to entity.
        """
        errors = []
        
        if not isinstance(grain, list):
            errors.append("Grain must be a list of dimension names")
            return errors
        
        # Get entity dimensions
        entity_model = entity.get("model")
        if entity_model:
            model = self.indexer.get_model(entity_model)
            if model:
                entity_dims = model.get("dimensions", [])
                entity_dim_set = set(entity_dims) if isinstance(entity_dims, list) else set()
                
                for dim in grain:
                    if dim not in entity_dim_set:
                        errors.append(f"Grain dimension '{dim}' not found in entity")
        
        return errors
    
    def _validate_dimensions(self, dimensions: List[str], entity: Dict[str, Any]) -> List[str]:
        """
        Validate that all allowed dimensions exist in entity.
        """
        errors = []
        
        if not isinstance(dimensions, list):
            errors.append("Dimensions must be a list")
            return errors
        
        # Get entity dimensions
        entity_model = entity.get("model")
        if entity_model:
            model = self.indexer.get_model(entity_model)
            if model:
                entity_dims = model.get("dimensions", [])
                entity_dim_set = set(entity_dims) if isinstance(entity_dims, list) else set()
                
                for dim in dimensions:
                    if dim not in entity_dim_set:
                        errors.append(f"Dimension '{dim}' not found in entity")

        return errors

    def _validate_metric_references(self, metric_name: str, metric_refs: List[str]) -> List[str]:
        """
        Validate that referenced metrics exist and check for circular dependencies.

        Args:
            metric_name: Name of the metric being validated
            metric_refs: List of metric names referenced in the expression

        Returns:
            List of validation errors
        """
        errors = []

        for ref_name in metric_refs:
            # Check that referenced metric exists
            ref_metric = self.indexer.get_metric(ref_name)
            if not ref_metric:
                errors.append(f"Referenced metric '{ref_name}' not found")
                continue

            # Check for direct circular dependency
            if ref_name == metric_name:
                errors.append(f"Circular dependency: metric '{metric_name}' references itself")
                continue

            # Check for indirect circular dependencies
            try:
                if self._has_circular_dependency(metric_name, ref_name, visited=set()):
                    errors.append(f"Circular dependency detected: metric '{ref_name}' eventually references '{metric_name}'")
            except Exception as e:
                errors.append(f"Error checking circular dependencies for '{ref_name}': {str(e)}")

        return errors

    def _has_circular_dependency(self, original_metric: str, current_metric: str, visited: Set[str]) -> bool:
        """
        Check if current_metric has a circular dependency back to original_metric.

        Uses DFS to traverse the dependency graph.

        Args:
            original_metric: The metric we're checking for circular reference to
            current_metric: The current metric in the traversal
            visited: Set of metrics already visited in this path

        Returns:
            True if circular dependency detected, False otherwise
        """
        if current_metric in visited:
            return False

        visited.add(current_metric)

        # Get the current metric's definition
        metric = self.indexer.get_metric(current_metric)
        if not metric:
            return False

        # Extract references from current metric's expression
        expr = metric.get('expression', '')
        refs = self._extract_metric_references(expr)

        for ref in refs:
            # If any reference points back to the original metric, we have a cycle
            if ref == original_metric:
                return True

            # Recursively check transitive dependencies
            if self._has_circular_dependency(original_metric, ref, visited.copy()):
                return True

        return False

