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
from axi.utils.sanitization import validate_metric_name, validate_dimension_name, sanitize_identifier

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

    def create_mart(self, mart_name: str, metrics: List[str], dimensions: List[str]) -> Dict[str, Any]:
        """
        Creates a wide table with multiple metrics joined on dimensions.

        Uses a CTE approach where each metric query becomes a CTE, then all CTEs
        are joined on the shared dimensions to produce a single wide table.
        """
        # Validate inputs
        if not metrics:
            raise ValueError("At least one metric is required")
        if not dimensions:
            raise ValueError("At least one dimension is required")

        metrics = [validate_metric_name(m) for m in metrics]
        dimensions = [validate_dimension_name(d) for d in dimensions]

        table_name = f"axi__mart__{self._slugify(mart_name)}"
        base_cte = f"m_0_{self._slugify(metrics[0])}"

        # Build CTEs for each metric
        cte_defs = []
        joins = []

        for i, m in enumerate(metrics):
            m_sql = self.engine.generate_sql(m, dimensions, [], dialect="snowflake")
            m_sql = m_sql.strip().rstrip(';')
            cte_name = f"m_{i}_{self._slugify(m)}"
            cte_defs.append(f"{cte_name} AS (\n{m_sql}\n)")

            # Build join clauses for non-base CTEs
            if i > 0:
                on_clauses = [f"{base_cte}.{d} = {cte_name}.{d}" for d in dimensions]
                joins.append(f"LEFT JOIN {cte_name} ON {' AND '.join(on_clauses)}")

        # Build SELECT list: dimensions from base CTE, metrics from their respective CTEs
        select_cols = [f"{base_cte}.{d}" for d in dimensions]
        for i, m in enumerate(metrics):
            cte_name = f"m_{i}_{self._slugify(m)}"
            select_cols.append(f"{cte_name}.{m}")

        # Assemble final SQL
        master_sql = "WITH " + ",\n".join(cte_defs)
        master_sql += f"\nSELECT {', '.join(select_cols)}\nFROM {base_cte}"
        if joins:
            master_sql += "\n" + "\n".join(joins)

        ddl = f"CREATE OR REPLACE TABLE {table_name} AS {master_sql}"

        logger.info(f"Creating mart table: {table_name}")
        logger.debug(f"Mart DDL: {ddl}")

        self.runner.execute_query(ddl)

        # Register Mart
        self.indexer.record_mart(mart_name, metrics, dimensions, table_name)

        logger.info(f"Successfully created mart: {mart_name}")
        return {"mart": mart_name, "table": table_name, "metrics": metrics, "dimensions": dimensions}
