# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import sqlglot
from sqlglot import exp
from typing import Dict, Any, List, Optional, Tuple
from axi.metadata.indexer import MetadataIndexer

class MetricValidator:
    """
    Validates user-defined metrics according to semantic rules.
    """
    
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer
    
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
        
        return len(errors) == 0, errors
    
    def _validate_expression(self, expression: str) -> List[str]:
        """
        Validate that expression contains exactly one aggregation.
        
        Rules:
        - Must contain exactly one aggregation (SUM, COUNT, AVG, MIN, MAX)
        - Cannot be a window function
        - Cannot be multiple aggregations
        """
        errors = []
        
        try:
            # Parse expression
            parsed = sqlglot.parse_one(expression)
            
            # Find all aggregations
            aggregations = list(parsed.find_all((exp.Sum, exp.Count, exp.Avg, exp.Min, exp.Max)))
            
            if len(aggregations) == 0:
                errors.append("Expression must contain exactly one aggregation (SUM, COUNT, AVG, MIN, MAX)")
            elif len(aggregations) > 1:
                errors.append("Expression must contain exactly one aggregation, found multiple")
            
            # Check for window functions
            window_functions = list(parsed.find_all((exp.Window, exp.RowNumber, exp.Rank, exp.DenseRank)))
            if window_functions:
                errors.append("Window functions are not allowed in metric expressions")
            
        except Exception as e:
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

