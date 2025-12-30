# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Dict, Any, Optional, Set, Tuple
import json
import re
from axi.execution.snowflake_runner import SnowflakeRunner
from axi.metadata.indexer import MetadataIndexer
from axi.utils.logging_config import get_logger

logger = get_logger(__name__)


class SnowflakeMetadataExtractor:
    def __init__(self, indexer: MetadataIndexer):
        self.runner = SnowflakeRunner()
        self.indexer = indexer
        self._table_map: Dict[str, int] = {}  # table_name -> table_id
        self._schema_tables: Dict[str, List[str]] = {}  # schema -> [table_names]

    def sync(self,
             include_constraints: bool = True,
             infer_relationships: bool = True,
             extract_semantic: bool = True,
             schemas: Optional[List[str]] = None,
             view_patterns: Optional[List[str]] = None):
        """
        Main method to sync all metadata from Snowflake to SQLite.

        Args:
            include_constraints: Fetch PK/FK constraints via SHOW commands
            infer_relationships: Infer FK relationships from naming conventions
            extract_semantic: Parse VIEW definitions to extract metrics/dimensions
            schemas: List of schemas to sync (None = all non-system schemas)
            view_patterns: List of view name patterns to include for semantic extraction (e.g., ['mart_%', 'fact_%'])
        """
        logger.info("Starting Snowflake metadata sync...")

        print("Syncing Tables and Columns...")
        self.fetch_tables_and_columns(schemas=schemas)

        if include_constraints:
            print("Syncing Constraints (PK/FK)...")
            self.fetch_constraints()

        print("Syncing Policies...")
        self.fetch_policies()

        print("Syncing Lineage...")
        self.fetch_lineage()

        if infer_relationships:
            print("Inferring Relationships from Naming Conventions...")
            self.infer_relationships_from_naming()

        print("Syncing Tags...")
        self.fetch_tags()

        print("Creating Semantic Relationships from Snowflake Metadata...")
        self.create_relationships_from_constraints()

        if extract_semantic:
            print("Extracting Semantic Metadata from Views...")
            self.extract_semantic_metadata(view_patterns=view_patterns)

        logger.info("Snowflake metadata sync complete")

    def fetch_tables_and_columns(self, schemas: Optional[List[str]] = None):
        """
        Fetch all tables and columns from Snowflake INFORMATION_SCHEMA.

        Args:
            schemas: List of schemas to sync (None = all non-system schemas)
        """
        # Build schema filter
        schema_filter = "TABLE_SCHEMA != 'INFORMATION_SCHEMA'"
        if schemas:
            schema_list = "', '".join(schemas)
            schema_filter = f"TABLE_SCHEMA IN ('{schema_list}')"

        query = f"""
        SELECT
            TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE, COMMENT, CREATED, LAST_ALTERED
        FROM INFORMATION_SCHEMA.TABLES
        WHERE {schema_filter}
        ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        rows, cols = self.runner.execute_query(query)

        conn = self.indexer._get_conn()
        c = conn.cursor()

        # Clear existing
        c.execute('DELETE FROM sf_tables')
        c.execute('DELETE FROM sf_columns')
        c.execute('DELETE FROM sf_constraints')

        self._table_map = {}  # Reset table map
        self._schema_tables = {}  # Reset schema -> tables mapping
        column_names_by_table: Dict[str, List[str]] = {}  # table -> [column_names]

        for row in rows:
            database, schema, table_name, table_type, comment, created, last_altered = row

            # Insert Table
            c.execute('''
                INSERT INTO sf_tables (database, schema, name, type, comment, created_at, last_altered, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (database, schema, table_name, table_type, comment, str(created), str(last_altered)))
            table_id = c.lastrowid

            # Store mappings
            full_name = f"{schema}.{table_name}"
            self._table_map[table_name] = table_id
            self._table_map[full_name] = table_id
            self._table_map[f"{database}.{schema}.{table_name}"] = table_id

            if schema not in self._schema_tables:
                self._schema_tables[schema] = []
            self._schema_tables[schema].append(table_name)

            # Upsert as snowflake entity (read-only)
            physical = f"{database}.{schema}.{table_name}"

            # Fetch Columns for this table
            col_query = f"""
            SELECT
                COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COMMENT, ORDINAL_POSITION
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_NAME = '{table_name}' AND TABLE_SCHEMA = '{schema}'
            ORDER BY ORDINAL_POSITION
            """
            c_rows, _ = self.runner.execute_query(col_query)

            columns = []
            column_names_by_table[table_name] = []
            for cr in c_rows:
                col_name, data_type, is_nullable, default_val, col_comment, ordinal = cr
                c.execute('''
                    INSERT INTO sf_columns (table_id, name, type, nullable, default_val, comment, ordinal, tags)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (table_id, col_name, data_type, is_nullable == 'YES', default_val, col_comment, ordinal, '{}'))
                columns.append(col_name)
                column_names_by_table[table_name].append(col_name.lower())

            # Upsert entity with column info
            self.indexer.upsert_entity({
                "name": table_name,
                "model": table_name,
                "primary_key": None,
                "columns": columns,
                "type": "snowflake",
                "is_read_only": True,
                "is_staging": False,
                "physical_location": physical,
                "schema_name": schema,
                "database_name": database,
            })

        conn.commit()
        conn.close()

        # Store column names for FK inference
        self._column_names_by_table = column_names_by_table
        logger.info(f"Synced {len(self._table_map)} tables from Snowflake")

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
        # SHOW TAGS - placeholder for future implementation
        pass

    def fetch_constraints(self):
        """
        Fetch PRIMARY KEY and FOREIGN KEY constraints from Snowflake using SHOW commands.

        Snowflake doesn't expose constraints in INFORMATION_SCHEMA, but we can use:
        - SHOW PRIMARY KEYS IN SCHEMA <schema>
        - SHOW IMPORTED KEYS IN SCHEMA <schema> (foreign keys)
        """
        conn = self.indexer._get_conn()
        c = conn.cursor()

        pk_count = 0
        fk_count = 0

        for schema, tables in self._schema_tables.items():
            # Fetch Primary Keys for this schema
            try:
                pk_query = f"SHOW PRIMARY KEYS IN SCHEMA {schema}"
                rows, _ = self.runner.execute_query(pk_query)

                # SHOW PRIMARY KEYS returns:
                # created_on, database_name, schema_name, table_name, column_name,
                # key_sequence, constraint_name, ...
                for row in rows:
                    if len(row) >= 5:
                        db_name, schema_name, table_name, column_name = row[1], row[2], row[3], row[4]
                        table_id = self._table_map.get(table_name)
                        if table_id:
                            c.execute('''
                                INSERT INTO sf_constraints (table_id, type, columns, referenced_table, referenced_columns)
                                VALUES (?, 'PRIMARY_KEY', ?, NULL, NULL)
                            ''', (table_id, column_name))
                            pk_count += 1

                            # Update entity with primary key info
                            self.indexer.update_entity_pk(table_name, column_name)

            except Exception as e:
                logger.warning(f"Could not fetch primary keys for schema {schema}: {e}")

            # Fetch Foreign Keys (Imported Keys) for this schema
            try:
                fk_query = f"SHOW IMPORTED KEYS IN SCHEMA {schema}"
                rows, _ = self.runner.execute_query(fk_query)

                # SHOW IMPORTED KEYS returns:
                # pk_database_name, pk_schema_name, pk_table_name, pk_column_name,
                # fk_database_name, fk_schema_name, fk_table_name, fk_column_name,
                # key_sequence, update_rule, delete_rule, fk_name, pk_name, ...
                for row in rows:
                    if len(row) >= 8:
                        pk_table = row[2]  # Referenced (parent) table
                        pk_column = row[3]  # Referenced (parent) column
                        fk_table = row[6]  # This (child) table
                        fk_column = row[7]  # This (child) column

                        table_id = self._table_map.get(fk_table)
                        if table_id:
                            c.execute('''
                                INSERT INTO sf_constraints (table_id, type, columns, referenced_table, referenced_columns)
                                VALUES (?, 'FOREIGN_KEY', ?, ?, ?)
                            ''', (table_id, fk_column, pk_table, pk_column))
                            fk_count += 1

            except Exception as e:
                logger.warning(f"Could not fetch foreign keys for schema {schema}: {e}")

        conn.commit()
        conn.close()
        logger.info(f"Extracted {pk_count} primary keys and {fk_count} foreign keys from Snowflake")

    def infer_relationships_from_naming(self):
        """
        Infer FK relationships from common naming conventions.

        Patterns detected:
        - column_name ends with '_id' and matches table_name + '_id' (e.g., customer_id -> customers)
        - column_name ends with '_id' and matches singular table_name + '_id' (e.g., customer_id -> customer)
        - column_name ends with '_fk' patterns
        """
        conn = self.indexer._get_conn()
        c = conn.cursor()

        inferred_count = 0
        all_tables_lower = {t.lower(): t for t in self._table_map.keys() if '.' not in t}

        for table_name, columns in getattr(self, '_column_names_by_table', {}).items():
            table_id = self._table_map.get(table_name)
            if not table_id:
                continue

            for col in columns:
                col_lower = col.lower()

                # Skip if already a known constraint
                c.execute('''
                    SELECT 1 FROM sf_constraints
                    WHERE table_id = ? AND columns = ? AND type = 'FOREIGN_KEY'
                ''', (table_id, col))
                if c.fetchone():
                    continue

                # Pattern 1: ends with _id
                if col_lower.endswith('_id') and col_lower != 'id':
                    base_name = col_lower[:-3]  # Remove '_id'

                    # Try plural forms
                    candidates = [
                        base_name + 's',      # customer -> customers
                        base_name + 'es',     # box -> boxes
                        base_name,            # customer -> customer (singular)
                        base_name.rstrip('s') if base_name.endswith('s') else None,  # categories -> category
                    ]

                    for candidate in candidates:
                        if candidate and candidate in all_tables_lower:
                            ref_table = all_tables_lower[candidate]
                            # Check if target table has 'id' column
                            ref_columns = getattr(self, '_column_names_by_table', {}).get(ref_table, [])
                            if 'id' in ref_columns:
                                c.execute('''
                                    INSERT INTO sf_constraints (table_id, type, columns, referenced_table, referenced_columns)
                                    VALUES (?, 'INFERRED_FK', ?, ?, 'id')
                                ''', (table_id, col, ref_table))
                                inferred_count += 1
                                logger.debug(f"Inferred FK: {table_name}.{col} -> {ref_table}.id")
                                break

                # Pattern 2: ends with _fk
                elif col_lower.endswith('_fk'):
                    base_name = col_lower[:-3]  # Remove '_fk'
                    if base_name in all_tables_lower:
                        ref_table = all_tables_lower[base_name]
                        ref_columns = getattr(self, '_column_names_by_table', {}).get(ref_table, [])
                        if 'id' in ref_columns:
                            c.execute('''
                                INSERT INTO sf_constraints (table_id, type, columns, referenced_table, referenced_columns)
                                VALUES (?, 'INFERRED_FK', ?, ?, 'id')
                            ''', (table_id, col, ref_table))
                            inferred_count += 1

        conn.commit()
        conn.close()
        logger.info(f"Inferred {inferred_count} relationships from naming conventions")

    def create_relationships_from_constraints(self):
        """
        Convert sf_constraints (FK/PK) into the semantic relationships table.

        This bridges Snowflake metadata into the semantic layer's relationship graph.
        """
        conn = self.indexer._get_conn()
        c = conn.cursor()

        # Get all FK constraints (both explicit and inferred)
        c.execute('''
            SELECT t.name, sc.columns, sc.referenced_table, sc.referenced_columns, sc.type
            FROM sf_constraints sc
            JOIN sf_tables t ON sc.table_id = t.id
            WHERE sc.type IN ('FOREIGN_KEY', 'INFERRED_FK')
        ''')

        created_count = 0
        for row in c.fetchall():
            child_table, fk_column, parent_table, pk_column, constraint_type = row

            if not all([child_table, fk_column, parent_table, pk_column]):
                continue

            # Check if relationship already exists
            existing = self.indexer.list_relationships()
            already_exists = any(
                r.get("parent_model") == parent_table and
                r.get("child_model") == child_table and
                r.get("fk_column") == fk_column
                for r in existing
            )

            if not already_exists:
                # Determine join type based on constraint type
                join_type = "SNOWFLAKE_FK" if constraint_type == "FOREIGN_KEY" else "INFERRED_FK"

                self.indexer.add_relationship({
                    "parent_model": parent_table,
                    "child_model": child_table,
                    "fk_column": fk_column,
                    "pk_column": pk_column,
                    "join_type": join_type
                })
                created_count += 1
                logger.debug(f"Created relationship: {child_table}.{fk_column} -> {parent_table}.{pk_column}")

        conn.close()
        logger.info(f"Created {created_count} semantic relationships from Snowflake constraints")

    def list_constraints(self) -> List[Dict[str, Any]]:
        """List all detected constraints (for CLI/API)."""
        conn = self.indexer._get_conn()
        conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
        c = conn.cursor()

        c.execute('''
            SELECT t.name as table_name, t.schema, sc.type, sc.columns,
                   sc.referenced_table, sc.referenced_columns
            FROM sf_constraints sc
            JOIN sf_tables t ON sc.table_id = t.id
            ORDER BY t.name, sc.type
        ''')

        results = c.fetchall()
        conn.close()
        return results

    def extract_semantic_metadata(self, view_patterns: Optional[List[str]] = None):
        """
        Extract semantic metadata (metrics, dimensions, filters) from Snowflake VIEW definitions.

        This is the key method that provides parity with dbt by parsing SQL to extract:
        - Metrics (aggregates like SUM, COUNT, AVG)
        - Dimensions (GROUP BY columns)
        - Filters (WHERE clauses)
        - Grain (TIME grouping patterns)

        Args:
            view_patterns: List of LIKE patterns for view names to include (e.g., ['mart_%', 'fact_%'])
                          If None, extracts from all views
        """
        from axi.extractor.core import extract_metadata
        from axi.metadata.writer import MetadataWriter

        logger.info("Starting semantic metadata extraction from Snowflake views...")

        # Get list of views to process
        conn = self.indexer._get_conn()
        c = conn.cursor()

        # Build pattern filter
        pattern_filter = "table_type = 'VIEW'"
        if view_patterns:
            pattern_conditions = []
            for pattern in view_patterns:
                pattern_conditions.append(f"name LIKE '{pattern}'")
            pattern_filter += " AND (" + " OR ".join(pattern_conditions) + ")"

        c.execute(f'''
            SELECT database, schema, name, type
            FROM sf_tables
            WHERE {pattern_filter}
            ORDER BY schema, name
        ''')

        views = c.fetchall()
        conn.close()

        if not views:
            logger.info("No views found matching criteria")
            return

        logger.info(f"Found {len(views)} views to process")

        # Initialize metadata writer
        writer = MetadataWriter(self.indexer.metadata_dir)

        extracted_count = 0
        skipped_count = 0
        error_count = 0

        for database, schema, view_name, table_type in views:
            try:
                # Get view DDL using GET_DDL
                full_name = f"{database}.{schema}.{view_name}"
                logger.debug(f"Fetching DDL for {full_name}")

                ddl_query = f"SELECT GET_DDL('VIEW', '{full_name}')"
                ddl_rows, _ = self.runner.execute_query(ddl_query)

                if not ddl_rows or not ddl_rows[0]:
                    logger.warning(f"Could not fetch DDL for {full_name}")
                    skipped_count += 1
                    continue

                # Extract SQL from DDL (remove CREATE VIEW ... AS prefix)
                ddl = ddl_rows[0][0]
                sql = self._extract_sql_from_ddl(ddl)

                if not sql:
                    logger.warning(f"Could not extract SQL from DDL for {view_name}")
                    skipped_count += 1
                    continue

                # Parse SQL using core extractor
                logger.debug(f"Parsing SQL for {view_name}")
                metadata = extract_metadata(sql, view_name)

                # Check if semantic content was found
                if metadata.get("grain_status") == "not_detected":
                    logger.info(f"[SKIP] {view_name}: no grouping/aggregation detected (not semantic)")
                    skipped_count += 1
                    continue

                # Enhance metadata with Snowflake-specific info
                metadata['source'] = 'snowflake'
                metadata['schema_name'] = schema
                metadata['database_name'] = database
                metadata['physical_location'] = full_name
                metadata['table_type'] = table_type

                # Write metadata
                writer.write(metadata)
                extracted_count += 1
                logger.info(f"✓ Extracted semantic metadata from {view_name}")

            except Exception as e:
                logger.error(f"Error processing {view_name}: {e}")
                error_count += 1

        logger.info(f"""
Semantic extraction complete:
  - Extracted: {extracted_count} views
  - Skipped: {skipped_count} views (no semantic content)
  - Errors: {error_count} views
        """)

    def _extract_sql_from_ddl(self, ddl: str) -> Optional[str]:
        """
        Extract the SELECT statement from a CREATE VIEW DDL.

        Args:
            ddl: Full DDL string from GET_DDL

        Returns:
            SELECT statement or None if extraction fails
        """
        if not ddl:
            return None

        # Remove leading/trailing whitespace
        ddl = ddl.strip()

        # Find "AS" keyword (case insensitive)
        # Pattern: CREATE [OR REPLACE] VIEW ... AS <select>
        as_pattern = re.compile(r'\bAS\b', re.IGNORECASE)
        match = as_pattern.search(ddl)

        if match:
            # Extract everything after AS
            sql = ddl[match.end():].strip()
            # Remove trailing semicolon if present
            if sql.endswith(';'):
                sql = sql[:-1].strip()
            return sql

        # Fallback: if no AS found, try to extract SELECT directly
        select_pattern = re.compile(r'\bSELECT\b', re.IGNORECASE)
        match = select_pattern.search(ddl)
        if match:
            sql = ddl[match.start():].strip()
            if sql.endswith(';'):
                sql = sql[:-1].strip()
            return sql

        return None
