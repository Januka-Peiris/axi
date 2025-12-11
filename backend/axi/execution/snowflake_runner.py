# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import snowflake.connector
from typing import List, Any, Dict, Tuple

class SnowflakeRunner:
    def __init__(self):
        self.account = os.getenv("SNOWFLAKE_ACCOUNT")
        self.user = os.getenv("SNOWFLAKE_USER")
        self.password = os.getenv("SNOWFLAKE_PASSWORD")
        self.database = os.getenv("SNOWFLAKE_DB")
        self.schema = os.getenv("SNOWFLAKE_SCHEMA")
        self.warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
        
    def execute_query(self, sql: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Executes query and returns (rows as dicts, column_names)
        """
        if not all([self.account, self.user, self.password, self.database, self.schema, self.warehouse]):
           raise ValueError("Missing Snowflake environment variables")

        ctx = snowflake.connector.connect(
            user=self.user,
            password=self.password,
            account=self.account,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema
        )
        cs = ctx.cursor()
        try:
            cs.execute(sql)
            results = cs.fetchall()
            # generic fetch?
            # get column names
            col_names = [col[0].lower() for col in cs.description]
            
            rows = []
            for row in results:
                rows.append(dict(zip(col_names, row)))
                
            return rows, col_names
        finally:
            cs.close()
            ctx.close()
