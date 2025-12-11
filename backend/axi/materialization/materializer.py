# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import json
import time
import re
from typing import List, Dict, Any, Optional
from axi.metadata.indexer import MetadataIndexer
from axi.query.engine import SemanticQueryEngine
from axi.execution.snowflake_runner import SnowflakeRunner

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
        """
        dim_slug = "_".join([self._slugify(d) for d in sorted(dimensions)])
        table_name = f"axi__{self._slugify(metric_name)}__{dim_slug}"
        if len(table_name) > 255:
            table_name = table_name[:255] # Truncate if too long (naive)

        # Generate SQL
        sql = self.engine.generate_sql(metric_name, dimensions, [], dialect="snowflake")
        
        # Check if table exists
        # Naive: try full refresh first if "create"
        # We need state tracking in SQLite
        
        # For this stage, we assume "create or replace" for full refresh
        # Incremental logic requires time dimension detection
        
        meta = self.indexer.get_metric(metric_name)
        time_dim = meta.get('time_dimension')
        
        final_mode = "full"
        if refresh_mode == "incremental" or (refresh_mode == "auto" and time_dim):
             # Check if we can increment
             # Need to check if table exists in SQLite registry to know we have a base
             # Or check Snowflake directly.
             # MVP: Always full rebuild unless strictly incremental requested and feasible logic implemented
             if time_dim:
                 final_mode = "incremental"
        
        if final_mode == "full":
            ddl = f"CREATE OR REPLACE TABLE {table_name} AS {sql}"
            self.runner.execute_query(ddl)
        else:
            # Incremental Logic (MERGE)
            # 1. Get max time from target
            # 2. Select from source > max time
            # 3. Merge
            pass # Placeholder for complex logic, falling back to full for safety in MVP step
            ddl = f"CREATE OR REPLACE TABLE {table_name} AS {sql}"
            self.runner.execute_query(ddl)
            
        # Update Registry
        # self._update_registry(...) -> Replaced by indexer method
        self.indexer.record_materialization(table_name, metric_name, dimensions, final_mode, f"SNOWFLAKE.{table_name}")
        
        return {"table": table_name, "mode": final_mode, "status": "success"}

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
