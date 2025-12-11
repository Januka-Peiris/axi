# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import json
from typing import Dict, Any, List
from axi.metadata.indexer import MetadataIndexer

class SemanticBridge:
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer

    def map_constraints(self):
        """
        Scans dbt tests and creates AXI constraints.
        - unique -> PRIMARY_KEY
        - relationships -> FOREIGN_KEY
        - not_null -> NOT_NULL
        """
        tests = self.indexer.list_dbt_tests()
        
        with self.indexer._get_conn() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM axi_constraints')
            
            for test in tests:
                test_type = test['test_type']
                model_node = test['model_name'] # e.g. model.my_project.users
                if not model_node:
                    continue
                
                # Convert model node id "model.proj.users" -> "users"
                # This is a simplification, ideally we map by exact node id.
                model_name = model_node.split('.')[-1]
                column_name = test['column_name']
                
                if test_type == 'unique':
                    self._add_constraint(c, model_name, column_name, 'PRIMARY_KEY', {})
                    
                elif test_type == 'not_null':
                     self._add_constraint(c, model_name, column_name, 'NOT_NULL', {})
                     
                elif test_type == 'relationships':
                    # Retrieve stored metadata from config
                    config = json.loads(test['config'])
                    if not config:
                        continue
                        
                    meta = config.get('axi_metadata', {})
                    kwargs = meta.get('kwargs', {})
                    
                    # Target field in the other table
                    target_field = kwargs.get('field', 'id')
                    
                    # Identify target model from dependencies
                    # relationships test depends on [current_model, target_model]
                    # We know current_model (model_name variable above)
                    # So we look for the other one in depends_on
                    depends_on = json.loads(test['config']).get('depends_on', [])
                    # Wait, manifest_loader stored depends_on in dbt_models/tests table?
                    # Let's check dbt_tests schema: test_name, test_type, model_name, column_name, severity, config
                    # manifest_loader._insert_test stores 'config' node['config'].
                    # It does not store 'depends_on' in the 'config' column, it stores it in 'dbt_models' table but test is a separate node?
                    # manifest_loader._insert_test DOES NOT store depends_on directly in the table columns except implicitly if we added it?
                    # Review manifest_loader:
                    # _insert_test inserts: (name, test_type, model_name, column_name, severity, json.dumps(config))
                    # It extracts `deps` to find `model_name`.
                    # But it doesn't store the full list of deps in the DB for the test.
                    
                    # FIX: We need depends_on to correctly identify the target model if we rely on it.
                    # OR we can parse 'to' from kwargs: "ref('customers')"
                    # Regex might be safer than relying on missing data.
                    
                    to_ref = kwargs.get('to', '')
                    target_model = None
                    import re
                    # Match ref('model') or ref("model")
                    m = re.search(r"ref\(['\"](.*?)['\"]\)", to_ref)
                    if m:
                        target_model = m.group(1)
                    
                    # Match source('source', 'table')
                    if not target_model:
                        m = re.search(r"source\(['\"](.*?)['\"],\s*['\"](.*?)['\"]\)", to_ref)
                        if m:
                            target_model = f"{m.group(1)}.{m.group(2)}"
                            
                    if target_model:
                         self._add_constraint(c, model_name, column_name, 'FOREIGN_KEY', {
                             'to_table': target_model,
                             'to_column': target_field
                         }) 
                    
            conn.commit()

    def _add_constraint(self, cursor, model, column, c_type, details):
        cursor.execute('''INSERT INTO axi_constraints 
                          (model_name, column_name, constraint_type, details)
                          VALUES (?, ?, ?, ?)''', 
                       (model, column, c_type, json.dumps(details)))
