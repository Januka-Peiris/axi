# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import json
import os
import sqlite3
from typing import Dict, Any, List

from axi.metadata.indexer import MetadataIndexer

class ManifestLoader:
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer

    def load_manifest(self, manifest_path: str):
        if not os.path.exists(manifest_path):
            raise FileNotFoundError(f"Manifest not found at {manifest_path}")

        with open(manifest_path, 'r') as f:
            data = json.load(f)

        nodes = data.get('nodes', {})
        sources = data.get('sources', {})
        snapshots = data.get('snapshots', {})
        
        # We also need to look at 'child_map' or 'tests' usually found in nodes?
        # dbt tests are in 'nodes' with resource_type='test'

        conn = self.indexer._get_conn()
        c = conn.cursor()

        # Clear existing dbt data
        c.execute('DELETE FROM dbt_models')
        c.execute('DELETE FROM dbt_sources')
        c.execute('DELETE FROM dbt_tests')

        # Parse Nodes (Models + Tests)
        for key, node in nodes.items():
            resource_type = node.get('resource_type')
            
            if resource_type == 'model':
                self._insert_model(c, node)
                self._upsert_entity_from_model(node)
            elif resource_type == 'seed':
                self._insert_seed(c, node)
                self._upsert_entity_from_model(node, override_type="seed", read_only=True)
            elif resource_type == 'test':
                self._insert_test(c, node)
            elif resource_type == 'snapshot':
                self._insert_snapshot(c, node)
                self._upsert_entity_from_model(node, override_type="snapshot")

        # Parse Sources
        for key, source in sources.items():
            self._insert_source(c, source)
            self._upsert_entity_from_source(source)

        # Snapshots block if present
        for key, snap in snapshots.items():
            self._insert_snapshot(c, snap)
            self._upsert_entity_from_model(snap, override_type="snapshot")

        conn.commit()
        conn.close()

    def _insert_model(self, cursor, node: Dict[str, Any]):
        name = node.get('name')
        database = node.get('database')
        schema = node.get('schema')
        alias = node.get('alias')
        relation_name = node.get('relation_name') # might be None if not compiled? usually populated.
        # Fallback for relation name
        if not relation_name:
             relation_name = f"{database}.{schema}.{alias}"
        
        materialization = node.get('config', {}).get('materialized', 'table')
        path = node.get('original_file_path') or node.get('path')
        tags = node.get('tags', [])
        description = node.get('description', '')
        depends_on = node.get('depends_on', {}).get('nodes', [])

        cursor.execute('''INSERT INTO dbt_models 
                          (model_name, resource_type, database, schema, alias, relation_name, materialization, path, tags, description, depends_on)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (name, 'model', database, schema, alias, relation_name, materialization, path, json.dumps(tags), description, json.dumps(depends_on)))

    def _insert_source(self, cursor, node: Dict[str, Any]):
        unique_id = node.get('unique_id')
        source_name = node.get('source_name')
        table_name = node.get('name')
        database = node.get('database')
        schema = node.get('schema')
        relation_name = node.get('relation_name')
        if not relation_name:
             relation_name = f"{database}.{schema}.{table_name}"
        
        freshness = node.get('freshness', {})
        tags = node.get('tags', [])
        description = node.get('description', '')

        cursor.execute('''INSERT INTO dbt_sources
                          (unique_id, source_name, table_name, database, schema, relation_name, freshness, tags, description)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (unique_id, source_name, table_name, database, schema, relation_name, json.dumps(freshness), json.dumps(tags), description))

    def _insert_test(self, cursor, node: Dict[str, Any]):
        # Test parsing (generic tests like unique, not_null)
        # dbt generic tests usually have 'test_metadata' in node
        # e.g. node['test_metadata']['name'] = 'unique'
        # node['test_metadata']['kwargs']['column_name']
        # node['test_metadata']['kwargs']['model'] -> parsed ref
        
        name = node.get('name')
        test_meta = node.get('test_metadata', {})
        test_type = test_meta.get('name', 'custom')
        
        # dependent model
        # depends_on: { nodes: [ 'model.x' ] }
        deps = node.get('depends_on', {}).get('nodes', [])
        model_name = deps[0] if deps else None
        
        # Clean model name (remove 'model.project.')
        # Actually storing the unique_id is safer, but user asked for model_name
        # Keep unique_id ref if possible or strip
        
        column_name = test_meta.get('kwargs', {}).get('column_name')
        severity = node.get('config', {}).get('severity')
        config = node.get('config', {})
        
        # Store full test_metadata to allow bridge to parse relationships
        # We need to alter table or stuff it into config?
        # Let's verify dbt_tests schema in indexer.py. 
        # It has: test_name, test_type, model_name, column_name, severity, config
        # We can put test_metadata into 'config' or add a new column. 
        # Updating schema is hard mid-flight without migration.
        # Let's merge test_metadata into config for now as 'axi_metadata'
        
        config['axi_metadata'] = test_meta

        cursor.execute('''INSERT INTO dbt_tests
                          (test_name, test_type, model_name, column_name, severity, config)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (name, test_type, model_name, column_name, severity, json.dumps(config)))

    def _insert_snapshot(self, cursor, node: Dict[str, Any]):
        # For now just reuse models table for snapshots with resource_type snapshot
        name = node.get('name')
        database = node.get('database')
        schema = node.get('schema')
        alias = node.get('alias') or name
        relation_name = node.get('relation_name') or f"{database}.{schema}.{alias}"
        materialization = 'snapshot'
        path = node.get('original_file_path') or node.get('path')
        tags = node.get('tags', [])
        description = node.get('description', '')
        depends_on = node.get('depends_on', {}).get('nodes', [])

        cursor.execute('''INSERT INTO dbt_models 
                          (model_name, resource_type, database, schema, alias, relation_name, materialization, path, tags, description, depends_on)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (name, 'snapshot', database, schema, alias, relation_name, materialization, path, json.dumps(tags), description, json.dumps(depends_on)))

    def _insert_seed(self, cursor, node: Dict[str, Any]):
        name = node.get('name')
        database = node.get('database')
        schema = node.get('schema')
        alias = node.get('alias') or name
        relation_name = node.get('relation_name') or f"{database}.{schema}.{alias}"
        materialization = 'seed'
        path = node.get('original_file_path') or node.get('path')
        tags = node.get('tags', [])
        description = node.get('description', '')
        depends_on = node.get('depends_on', {}).get('nodes', [])

        cursor.execute('''INSERT INTO dbt_models 
                          (model_name, resource_type, database, schema, alias, relation_name, materialization, path, tags, description, depends_on)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                       (name, 'seed', database, schema, alias, relation_name, materialization, path, json.dumps(tags), description, json.dumps(depends_on)))

    def _upsert_entity_from_model(self, node: Dict[str, Any], override_type: str = None, read_only: bool = False):
        name = node.get('name')
        if not name:
            return
        path = node.get('original_file_path') or node.get('path') or ""
        entity_type = override_type or "model"
        lower_path = path.lower()
        if not override_type:
            if "staging" in lower_path:
                entity_type = "staging"
            elif "marts" in lower_path:
                entity_type = "mart"
            elif "models" in lower_path:
                entity_type = "model"
        physical = node.get('relation_name')
        database = node.get('database')
        schema = node.get('schema')
        alias = node.get('alias') or name
        if not physical and database and schema and alias:
            physical = f"{database}.{schema}.{alias}"
        self.indexer.upsert_entity({
            "name": name,
            "model": name,
            "primary_key": None,
            "columns": node.get('columns') or [],
            "type": entity_type,
            "is_read_only": read_only,
            "is_staging": entity_type == "staging",
            "physical_location": physical,
            "schema_name": schema,
            "database_name": database,
        })

    def _upsert_entity_from_source(self, source: Dict[str, Any]):
        table_name = source.get('name')
        source_name = source.get('source_name')
        if not table_name:
            return
        database = source.get('database')
        schema = source.get('schema')
        relation_name = source.get('relation_name')
        if not relation_name and database and schema:
            relation_name = f"{database}.{schema}.{table_name}"
        self.indexer.upsert_entity({
            "name": f"{source_name}.{table_name}" if source_name else table_name,
            "model": table_name,
            "primary_key": None,
            "columns": source.get('columns') or [],
            "type": "source",
            "is_read_only": True,
            "is_staging": False,
            "physical_location": relation_name,
            "schema_name": schema,
            "database_name": database,
            "source_name": source_name
        })
