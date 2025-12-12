# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Dict, Any
import json
from axi.execution.snowflake_runner import SnowflakeRunner
from axi.metadata.indexer import MetadataIndexer

class SnowflakeMetadataExtractor:
    def __init__(self, indexer: MetadataIndexer):
        self.runner = SnowflakeRunner()
        self.indexer = indexer

    def sync(self):
        """
        Main method to sync all metadata from Snowflake to SQLite.
        """
        print("Syncing Tables and Columns...")
        self.fetch_tables_and_columns()
        
        print("Syncing Policies...")
        self.fetch_policies()
        
        print("Syncing Lineage...")
        self.fetch_lineage()
        
        print("Syncing Tags...")
        self.fetch_tags()

    def fetch_tables_and_columns(self):
        # Fetch Tables
        query = """
        SELECT 
            TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, COMMENT, CREATED, LAST_ALTERED
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA != 'INFORMATION_SCHEMA'
        """
        rows, cols = self.runner.execute_query(query)
        
        conn = self.indexer._get_conn()
        c = conn.cursor()
        
        # Clear existing
        c.execute('DELETE FROM sf_tables')
        c.execute('DELETE FROM sf_columns')
        
        table_map = {} # name -> id
        
        for row in rows:
            # Insert Table
            c.execute('''
                INSERT INTO sf_tables (database, schema, name, type, comment, created_at, last_altered, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (row[0], row[1], row[2], row[3], row[4], str(row[5]), str(row[6])))
            table_id = c.lastrowid
            table_map[row[2]] = table_id # Store by name (simple assumption unique by name for demo)
            # Upsert as snowflake entity (read-only)
            physical = f"{row[0]}.{row[1]}.{row[2]}"
            self.indexer.upsert_entity({
                "name": row[2],
                "model": row[2],
                "primary_key": None,
                "columns": [],
                "type": "snowflake",
                "is_read_only": True,
                "is_staging": False,
                "physical_location": physical,
                "schema_name": row[1],
                "database_name": row[0],
            })
            
            # Fetch Columns for this table
            col_query = f"""
            SELECT 
                COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COMMENT, ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{row[2]}' AND TABLE_SCHEMA = '{row[1]}'
            ORDER BY ORDINAL_POSITION
            """
            c_rows, _ = self.runner.execute_query(col_query)
            
            for cr in c_rows:
                c.execute('''
                    INSERT INTO sf_columns (table_id, name, type, nullable, default_val, comment, ordinal, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (table_id, cr[0], cr[1], cr[2]=='YES', cr[3], cr[4], cr[5], '{}'))
        
        conn.commit()
        conn.close()

    def fetch_policies(self):
        conn = self.indexer._get_conn()
        c = conn.cursor()
        c.execute('DELETE FROM sf_masking_policies')
        c.execute('DELETE FROM sf_row_access_policies')
        
        # Masking Policies
        try:
            # We can't easily parse SHOW outputs in pure SQLRunner usually, 
            # but if SnowflakeRunner returns rows for SHOW commands, use that.
            # Assuming SnowflakeRunner handles cursor.fetchall() for SHOW commands.
            rows, _ = self.runner.execute_query("SHOW MASKING POLICIES")
            for r in rows:
                # Output: created_on, name, database_name, schema_name, kind, owner, comment, ...
                # We need to map columns carefully. 
                # Simplification: store name and schema.
                name = r[1]
                schema = r[3]
                c.execute('INSERT INTO sf_masking_policies (name, schema, table_name, column_name, body) VALUES (?, ?, ?, ?, ?)',
                          (name, schema, "", "", "Detected in Snowflake"))
        except Exception as e:
            print(f"Warning: Could not fetch masking policies: {e}")

        # Row Access Policies
        try:
            rows, _ = self.runner.execute_query("SHOW ROW ACCESS POLICIES")
            for r in rows:
                name = r[1]
                schema = r[3]
                c.execute('INSERT INTO sf_row_access_policies (name, schema, table_name, body) VALUES (?, ?, ?, ?)',
                          (name, schema, "", "Detected in Snowflake"))
        except Exception as e:
             print(f"Warning: Could not fetch row access policies: {e}")
             
        conn.commit()
        conn.close()

    def fetch_lineage(self):
        # Using Account Usage: Object Dependencies
        # This requires Account Admin or specific privileges usually.
        # Fallback gracefully.
        query = """
        SELECT 
          REFERENCED_OBJECT_NAME AS upstream,
          OBJECT_NAME AS downstream,
          DEPENDENCY_TYPE
        FROM SNOWFLAKE.ACCOUNT_USAGE.OBJECT_DEPENDENCIES
        WHERE REFERENCED_OBJECT_DOMAIN = 'TABLE' AND OBJECT_DOMAIN = 'TABLE'
        LIMIT 1000
        """
        try:
            rows, _ = self.runner.execute_query(query)
            
            conn = self.indexer._get_conn()
            c = conn.cursor()
            c.execute('DELETE FROM sf_lineage')
            
            for r in rows:
                c.execute('INSERT INTO sf_lineage (upstream_table, downstream_table, type) VALUES (?, ?, ?)',
                          (r[0], r[1], r[2]))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Warning: Could not fetch lineage (check privileges): {e}")

    def fetch_tags(self):
        # SHOW TAGS
        pass
