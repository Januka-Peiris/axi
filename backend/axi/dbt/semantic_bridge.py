# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import json
import re
from typing import Dict, Any, List, Optional, Set
from axi.metadata.indexer import MetadataIndexer
from axi.utils.logging_config import get_logger

logger = get_logger(__name__)


class SemanticBridge:
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer

    def map_constraints(self):
        """
        Scans dbt tests and creates AXI constraints.
        - unique -> PRIMARY_KEY (also updates entity PK)
        - relationships -> FOREIGN_KEY (also creates relationship edge)
        - not_null -> NOT_NULL

        Also creates relationship edges in the relationships table.
        """
        tests = self.indexer.list_dbt_tests()

        pk_count = 0
        fk_count = 0
        rel_count = 0

        with self.indexer._get_conn() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM axi_constraints')

            for test in tests:
                test_type = test['test_type']
                model_node = test['model_name']  # e.g. model.my_project.users
                if not model_node:
                    continue

                # Convert model node id "model.proj.users" -> "users"
                model_name = model_node.split('.')[-1]
                column_name = test['column_name']

                if test_type == 'unique':
                    self._add_constraint(c, model_name, column_name, 'PRIMARY_KEY', {})
                    pk_count += 1

                    # Update entity's primary key
                    if column_name:
                        self.indexer.update_entity_pk(model_name, column_name)

                elif test_type == 'not_null':
                    self._add_constraint(c, model_name, column_name, 'NOT_NULL', {})

                elif test_type == 'relationships':
                    target_info = self._parse_relationship_test(test)
                    if target_info:
                        target_model, target_field = target_info
                        self._add_constraint(c, model_name, column_name, 'FOREIGN_KEY', {
                            'to_table': target_model,
                            'to_column': target_field
                        })
                        fk_count += 1

                        # Create relationship edge (parent -> child direction)
                        # In FK terms: child.column -> parent.pk
                        # So parent_model is target, child_model is source
                        rel_id = self.indexer.add_relationship({
                            'parent_model': target_model,
                            'child_model': model_name,
                            'fk_column': column_name,
                            'pk_column': target_field,
                            'join_type': 'DBT_RELATIONSHIP'
                        })
                        if rel_id > 0:
                            rel_count += 1

            conn.commit()

        logger.info(f"Mapped {pk_count} PKs, {fk_count} FKs, created {rel_count} relationships from dbt tests")

    def _parse_relationship_test(self, test: Dict[str, Any]) -> Optional[tuple]:
        """
        Parse a dbt relationships test to extract target model and field.

        Returns:
            Tuple of (target_model, target_field) or None if parsing fails
        """
        try:
            config_raw = test.get('config')
            if not config_raw:
                return None

            config = json.loads(config_raw) if isinstance(config_raw, str) else config_raw
            meta = config.get('axi_metadata', {})
            kwargs = meta.get('kwargs', {})

            # Target field in the other table (default 'id')
            target_field = kwargs.get('field', 'id')

            # Parse 'to' to extract target model
            to_ref = kwargs.get('to', '')
            target_model = None

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
                return (target_model, target_field)

        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.debug(f"Failed to parse relationship test: {e}")

        return None

    def _add_constraint(self, cursor, model, column, c_type, details):
        cursor.execute('''INSERT INTO axi_constraints
                          (model_name, column_name, constraint_type, details)
                          VALUES (?, ?, ?, ?)''',
                       (model, column, c_type, json.dumps(details)))

    def sync_model_columns_to_entities(self):
        """
        Extract primary key information from dbt model column metadata.
        Some dbt projects mark PKs in model config or column meta.
        """
        models = self.indexer.list_dbt_models()
        pk_found = 0

        for model in models:
            model_name = model.get('model_name')
            if not model_name:
                continue

            # Try to find entity and check columns for PK markers
            entity = self.indexer.get_entity(model_name)
            if not entity:
                continue

            columns = entity.get('columns', [])
            for col in columns:
                if isinstance(col, dict):
                    # Check for common PK markers in dbt column metadata
                    col_name = col.get('name', '')
                    meta = col.get('meta', {})
                    tests = col.get('tests', [])

                    # Check meta for PK indicator
                    is_pk = meta.get('is_primary_key', False) or meta.get('primary_key', False)

                    # Check if column has unique test
                    if not is_pk:
                        for t in tests:
                            if isinstance(t, str) and t == 'unique':
                                is_pk = True
                                break
                            elif isinstance(t, dict) and 'unique' in t:
                                is_pk = True
                                break

                    if is_pk and col_name:
                        self.indexer.update_entity_pk(model_name, col_name)
                        pk_found += 1

        if pk_found:
            logger.info(f"Found {pk_found} PKs from model column metadata")

    def create_relationships_from_dependencies(self):
        """
        Create DEPENDS_ON relationship edges from dbt model dependencies.
        These provide graph connectivity even without FK/PK info.

        Note: This is also done in indexer._merge_manifest_relationships(),
        but this method can be called explicitly after manifest load.
        """
        models = self.indexer.list_dbt_models()
        created = 0

        existing_rels = self.indexer.list_relationships()
        existing_pairs = set()
        for rel in existing_rels:
            existing_pairs.add((rel.get('parent_model'), rel.get('child_model')))

        for model in models:
            model_name = model.get('model_name')
            deps = model.get('depends_on', [])

            if not model_name or not deps:
                continue

            for dep in deps:
                if not dep or not isinstance(dep, str):
                    continue

                # dbt nodes are like model.project.name or source.project.table
                dep_name = dep.split('.')[-1]
                if not dep_name or dep_name == model_name:
                    continue

                # Skip if relationship already exists
                if (dep_name, model_name) in existing_pairs:
                    continue

                rel_id = self.indexer.add_relationship({
                    'parent_model': dep_name,
                    'child_model': model_name,
                    'fk_column': '',
                    'pk_column': '',
                    'join_type': 'DEPENDS_ON'
                })

                if rel_id > 0:
                    created += 1
                    existing_pairs.add((dep_name, model_name))

        if created:
            logger.info(f"Created {created} DEPENDS_ON relationships from dbt dependencies")

    def full_sync(self):
        """
        Run full semantic bridge synchronization:
        1. Map dbt test constraints to AXI constraints and relationships
        2. Sync model column metadata to entity PKs
        3. Create DEPENDS_ON edges from model dependencies
        """
        logger.info("Starting semantic bridge full sync...")

        # Map constraints from tests
        self.map_constraints()

        # Extract PKs from model column metadata
        self.sync_model_columns_to_entities()

        # Create dependency edges
        self.create_relationships_from_dependencies()

        logger.info("Semantic bridge sync complete")
