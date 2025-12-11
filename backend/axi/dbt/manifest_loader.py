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
            elif resource_type == 'test':
                self._insert_test(c, node)

        # Parse Sources
        for key, source in sources.items():
            self._insert_source(c, source)

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
