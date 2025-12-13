# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import json
import time
import re
import logging
from typing import List, Dict, Any, Optional
from axi.metadata.indexer import MetadataIndexer
from axi.query.engine import SemanticQueryEngine
from axi.execution.snowflake_runner import SnowflakeRunner
from axi.utils.logging_config import get_logger
from axi.utils.sanitization import validate_metric_name, sanitize_identifier

logger = get_logger(__name__)

class Materializer:
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer
        self.engine = SemanticQueryEngine(indexer)
        self.runner = SnowflakeRunner()

    def _slugify(self, text: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_]', '_', text).lower()

    def materialize_metric(self, metric_name: str, dimensions: List[str], refresh_mode: str = "auto") -> Dict[str, Any]:
        """
        Creates or refreshes a materialized table for a metric.
        Naming: axi__<metric>__<dims>
        
        Note: Only full refresh is currently supported. Incremental materialization
        requires state tracking, time dimension handling, and MERGE logic which is
        not yet implemented.
        """
        # Validate and sanitize inputs
        metric_name = validate_metric_name(metric_name)
        dimensions = [validate_dimension_name(d) for d in dimensions if d]
        
        logger.info(f"Starting materialization for metric: {metric_name}, dimensions: {dimensions}, mode: {refresh_mode}")
        
        # Validate refresh mode
        if refresh_mode == "incremental":
            logger.warning(f"Incremental materialization requested but not implemented for {metric_name}")
            raise ValueError(
                "Incremental materialization is not yet implemented. "
                "Please use refresh_mode='full' or 'auto'."
            )
        
        # Sanitize table name components
        safe_metric = sanitize_identifier(self._slugify(metric_name), max_length=100)
        dim_slug = "_".join([sanitize_identifier(self._slugify(d), max_length=50) for d in sorted(dimensions)])
        table_name = f"axi__{safe_metric}__{dim_slug}"
        if len(table_name) > 255:
            table_name = table_name[:255]  # Truncate if too long
            logger.warning(f"Table name truncated to 255 characters: {table_name}")

        # Generate SQL
        logger.debug(f"Generating SQL for materialization")
        sql = self.engine.generate_sql(metric_name, dimensions, [], dialect="snowflake")
        
        # Strip semicolon if present
        sql = sql.strip().rstrip(';')
        
        # Full refresh: CREATE OR REPLACE TABLE
        logger.info(f"Executing DDL for table: {table_name}")
        ddl = f"CREATE OR REPLACE TABLE {table_name} AS {sql}"
        self.runner.execute_query(ddl)
        logger.info(f"Successfully created materialized table: {table_name}")
            
        # Update Registry
        self.indexer.record_materialization(
            table_name, 
            metric_name, 
            dimensions, 
            "full", 
            f"SNOWFLAKE.{table_name}"
        )
        
        return {
            "table": table_name, 
            "mode": "full", 
            "status": "success",
            "message": "Materialization completed with full refresh"
        }

    def create_mart(self, mart_name: str, metrics: List[str], dimensions: List[str]):
        """
        Creates a wide table with multiple metrics joined on dimensions.
        """
        table_name = f"axi__mart__{self._slugify(mart_name)}"
        
        # Generate SQL for each metric
        # Join them on dimensions
        # CTE approach
        
        ctes = []
        selects = list(dimensions)
        joins = []
        
        base_cte = f"base_{metrics[0]}"
        
        # We need to align them.
        # This is complex semantic layer logic ("Stitching").
        # Simplified: Assume all metrics share the exact same grain/dims and joins are trivial on those dims.
        
        # Construct a query that joins valid metric subqueries.
        # Or better: `SELECT dims, metric1, metric2...` from source if they are on same source?
        # Likely they are not.
        
        # MVP: Generate SQL for each, putting them in CTEs, then joining on dims.
        
        master_sql = "WITH "
        cte_defs = []
        for i, m in enumerate(metrics):
            m_sql = self.engine.generate_sql(m, dimensions, [], dialect="snowflake")
            # We need to strip the semicolon
            m_sql = m_sql.strip().rstrip(';')
            cte_name = f"m_{i}_{m}"
            cte_defs.append(f"{cte_name} AS ({m_sql})")
            
            if i == 0:
                pass # Base
            else:
                 # Join condition
                 on_clauses = [f"m_0_{metrics[0]}.{d} = {cte_name}.{d}" for d in dimensions]
                 joins.append(f"LEFT JOIN {cte_name} ON {' AND '.join(on_clauses)}")
            
            selects.append(f"{cte_name}.{m} as {m}")
            
        master_sql += ",\n".join(cte_defs)
        master_sql += f"\nSELECT {', '.join(dimensions)}, {', '.join([f'{m}' for m in metrics])} FROM m_0_{metrics[0]}" # Simplified projection
        # Actually need to project from respective CTEs in SELECT list
        
        # Re-do Selects properly
        # Dims from first CTE
        final_selects = [f"m_0_{metrics[0]}.{d}" for d in dimensions]
        # Metrics from their CTEs
        for i, m in enumerate(metrics):
            final_selects.append(f"m_{i}_{m}.{m}")
            
        master_sql += f"\nSELECT {', '.join(final_selects)} FROM m_0_{metrics[0]}"
        
        if joins:
            master_sql += "\n" + "\n".join(joins)
            
        ddl = f"CREATE OR REPLACE TABLE {table_name} AS {master_sql}"
        self.runner.execute_query(ddl)
        
        # Register Mart
        self.indexer.record_mart(mart_name, metrics, dimensions, table_name)
        return {"mart": mart_name, "table": table_name}
