# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from typing import List, Dict, Optional, Tuple, Set
from collections import deque
from axi.metadata.indexer import MetadataIndexer

class SemanticGraph:
    def __init__(self, indexer: MetadataIndexer):
        self.indexer = indexer
        # Filter out relationships with null/empty model names
        all_rels = indexer.list_relationships()
        self.relationships = [
            rel for rel in all_rels
            if rel.get('parent_model') and rel.get('child_model') and
               isinstance(rel.get('parent_model'), str) and isinstance(rel.get('child_model'), str) and
               rel.get('parent_model').strip() and rel.get('child_model').strip()
        ]
        self.adj = self._build_adjacency_list()

    def _build_adjacency_list(self) -> Dict[str, List[Dict]]:
        adj = {}
        for rel in self.relationships:
            parent = rel['parent_model']
            child = rel['child_model']
            
            # Add edge: child -> parent (Many to One usually)
            if child not in adj: adj[child] = []
            adj[child].append({
                "target": parent,
                "type": "child_to_parent",
                "rel": rel
            })
            
            # Add edge: parent -> child (One to Many)
            # We add this for traversal, though standard SQL joins usually start from Fact (Child) -> Dim (Parent)
            if parent not in adj: adj[parent] = []
            adj[parent].append({
                "target": child,
                "type": "parent_to_child",
                "rel": rel
            })
        return adj

    def find_path(self, start_node: str, end_node: str) -> Optional[List[Dict]]:
        """
        BFS to find path from start_node to end_node.
        """
        # Checks
        if start_node == end_node:
            return []
            
        queue = deque([(start_node, [])])
        visited = set([start_node])
        
        while queue:
            curr, path = queue.popleft()
            
            if curr == end_node:
                return path
            
            if curr in self.adj:
                for edge in self.adj[curr]:
                    neighbor = edge['target']
                    if neighbor not in visited:
                        visited.add(neighbor)
                        new_path = path + [edge]
                        queue.append((neighbor, new_path))
                        
        return None
    
    def get_graph_json(self):
        """Return graph data in format expected by frontend."""
        models = self.indexer.list_models()
        
        # Convert models to nodes format - ensure all have valid names
        nodes = []
        for model in models:
            if isinstance(model, dict):
                model_name = model.get('name')
            elif isinstance(model, str):
                model_name = model
            else:
                continue
            
            # Skip nodes with null/empty names
            if not model_name or not isinstance(model_name, str) or not model_name.strip():
                continue
            
            # Create node object
            node = {
                "name": model_name.strip(),
                "type": "model"
            }
            
            # Add optional properties if available
            if isinstance(model, dict):
                if model.get('path'):
                    node['path'] = model['path']
                if model.get('source_tables'):
                    node['source_tables'] = model['source_tables']
                if model.get('dimensions'):
                    node['dimensions'] = model['dimensions']
            
            nodes.append(node)
        
        # Build edges from relationships - ensure all references are valid
        edges = []
        node_names = {node['name'] for node in nodes}
        
        for rel in self.relationships:
            from_model = rel.get('child_model')
            to_model = rel.get('parent_model')
            
            # Only add edge if both nodes exist
            if from_model and to_model and from_model in node_names and to_model in node_names:
                edges.append({
                    "from": from_model,
                    "to": to_model,
                    "fk": rel.get('fk_column', ''),
                    "pk": rel.get('pk_column', '')
                })
        
        return {"nodes": nodes, "edges": edges}
    
    def get_local_subgraph(self, node_id: str, depth: int = 1) -> Dict:
        """
        Get local subgraph around a specific node.
        Returns the node, its direct neighbors (depth=1) or up to 2 hops (depth=2).
        Handles metrics, dimensions, entities, and models.
        """
        if depth < 1 or depth > 2:
            depth = 1
        
        # Get all models to build node lookup
        all_models = self.indexer.list_models()
        model_lookup = {}
        for model in all_models:
            if isinstance(model, dict):
                name = model.get('name')
            elif isinstance(model, str):
                name = model
            else:
                continue
            if name and isinstance(name, str) and name.strip():
                model_lookup[name.strip()] = model
        
        # Check if node_id is a metric, dimension, or entity and find its model/entity connections
        nodes_to_include = set([node_id])
        seed_nodes = [node_id]
        
        # Try to find connections through metrics/dimensions/entities
        try:
            with self.indexer._get_conn() as conn:
                conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
                c = conn.cursor()
                
                # Check if it's a metric - find its entity/model
                c.execute("SELECT entity_name, model FROM metrics WHERE name = ?", (node_id,))
                metric_row = c.fetchone()
                if metric_row:
                    if metric_row.get('entity_name'):
                        seed_nodes.append(metric_row['entity_name'])
                        nodes_to_include.add(metric_row['entity_name'])
                    if metric_row.get('model'):
                        seed_nodes.append(metric_row['model'])
                        nodes_to_include.add(metric_row['model'])
                
                # Check if it's a dimension - find linked entities/metrics
                c.execute("SELECT entity_name FROM entity_dimensions ed JOIN dimensions d ON ed.dimension_id = d.id WHERE d.name = ? LIMIT 5", (node_id,))
                for row in c.fetchall():
                    if row.get('entity_name'):
                        seed_nodes.append(row['entity_name'])
                        nodes_to_include.add(row['entity_name'])
                
                c.execute("SELECT metric_name FROM metric_dimensions md JOIN dimensions d ON md.dimension_id = d.id WHERE d.name = ? LIMIT 5", (node_id,))
                for row in c.fetchall():
                    if row.get('metric_name'):
                        seed_nodes.append(row['metric_name'])
                        nodes_to_include.add(row['metric_name'])
                
                # Check if it's an entity - find its model
                c.execute("SELECT model FROM entities WHERE name = ?", (node_id,))
                entity_row = c.fetchone()
                if entity_row and entity_row.get('model'):
                    seed_nodes.append(entity_row['model'])
                    nodes_to_include.add(entity_row['model'])
        except Exception:
            pass  # If DB queries fail, just use model relationships
        
        # BFS to collect nodes within depth, starting from all seed nodes
        visited = set()
        queue = deque([(n, 0) for n in seed_nodes])
        for n in seed_nodes:
            visited.add(n)
        
        while queue:
            curr, curr_depth = queue.popleft()
            if curr_depth >= depth:
                continue
            
            # Check model relationships
            if curr in self.adj:
                for edge in self.adj[curr]:
                    neighbor = edge['target']
                    if neighbor not in visited:
                        visited.add(neighbor)
                        nodes_to_include.add(neighbor)
                        queue.append((neighbor, curr_depth + 1))
        
        # Build nodes list - include metrics, dimensions, entities, and models
        result_nodes = []
        node_types_map = {}
        
        # Get metrics, dimensions, and entities from database
        try:
            with self.indexer._get_conn() as conn:
                c = conn.cursor()
                
                # Get metrics
                c.execute("SELECT name FROM metrics")
                for row in c.fetchall():
                    name = row[0] if isinstance(row, tuple) else row.get('name')
                    if name:
                        node_types_map[name] = "metric"
                
                # Get dimensions
                c.execute("SELECT name FROM dimensions")
                for row in c.fetchall():
                    name = row[0] if isinstance(row, tuple) else row.get('name')
                    if name:
                        node_types_map[name] = "dimension"
                
                # Get entities
                c.execute("SELECT name FROM entities")
                for row in c.fetchall():
                    name = row[0] if isinstance(row, tuple) else row.get('name')
                    if name:
                        node_types_map[name] = "entity"
        except Exception:
            pass
        
        for node_name in nodes_to_include:
            node_type = node_types_map.get(node_name, "model")
            
            if node_name in model_lookup:
                model = model_lookup[node_name]
                node = {
                    "name": node_name,
                    "type": node_type
                }
                if isinstance(model, dict):
                    if model.get('path'):
                        node['path'] = model['path']
                    if model.get('source_tables'):
                        node['source_tables'] = model['source_tables']
                    if model.get('dimensions'):
                        node['dimensions'] = model['dimensions']
                result_nodes.append(node)
            else:
                # Create node for metric/dimension/entity
                result_nodes.append({
                    "name": node_name,
                    "type": node_type
                })
        
        # Build edges only between included nodes
        result_edges = []
        node_names_set = {n['name'] for n in result_nodes}
        for rel in self.relationships:
            from_model = rel.get('child_model')
            to_model = rel.get('parent_model')
            if from_model and to_model and from_model in node_names_set and to_model in node_names_set:
                result_edges.append({
                    "from": from_model,
                    "to": to_model,
                    "fk": rel.get('fk_column', ''),
                    "pk": rel.get('pk_column', '')
                })
        
        return {"nodes": result_nodes, "edges": result_edges}
    
    def get_filtered_graph(self, root_node: Optional[str] = None, depth: int = 2, 
                          node_types: Optional[List[str]] = None) -> Dict:
        """
        Get filtered graph based on root node, depth, and node type filters.
        If root_node is None, returns all nodes matching types.
        """
        if depth < 1 or depth > 3:
            depth = 2
        
        all_models = self.indexer.list_models()
        model_lookup = {}
        for model in all_models:
            if isinstance(model, dict):
                name = model.get('name')
            elif isinstance(model, str):
                name = model
            else:
                continue
            if name and isinstance(name, str) and name.strip():
                model_lookup[name.strip()] = model
        
        nodes_to_include = set()
        
        if root_node:
            # BFS from root
            visited = set()
            queue = deque([(root_node, 0)])
            visited.add(root_node)
            nodes_to_include.add(root_node)
            
            while queue:
                curr, curr_depth = queue.popleft()
                if curr_depth >= depth:
                    continue
                
                if curr in self.adj:
                    for edge in self.adj[curr]:
                        neighbor = edge['target']
                        if neighbor not in visited:
                            visited.add(neighbor)
                            nodes_to_include.add(neighbor)
                            queue.append((neighbor, curr_depth + 1))
        else:
            # Include all nodes if no root specified
            nodes_to_include = set(model_lookup.keys())
        
        # Filter by type if specified
        if node_types:
            # For now, all nodes are "model" type, but we can extend this
            # This is a placeholder for future type filtering
            pass
        
        # Build result nodes
        result_nodes = []
        for node_name in nodes_to_include:
            if node_name in model_lookup:
                model = model_lookup[node_name]
                node = {
                    "name": node_name,
                    "type": "model"
                }
                if isinstance(model, dict):
                    if model.get('path'):
                        node['path'] = model['path']
                    if model.get('source_tables'):
                        node['source_tables'] = model['source_tables']
                    if model.get('dimensions'):
                        node['dimensions'] = model['dimensions']
                result_nodes.append(node)
        
        # Limit to 200 nodes max
        if len(result_nodes) > 200:
            return {
                "nodes": [],
                "edges": [],
                "error": "Graph too large. Please narrow your filters.",
                "node_count": len(result_nodes)
            }
        
        # Build edges
        result_edges = []
        node_names_set = {n['name'] for n in result_nodes}
        for rel in self.relationships:
            from_model = rel.get('child_model')
            to_model = rel.get('parent_model')
            if from_model and to_model and from_model in node_names_set and to_model in node_names_set:
                result_edges.append({
                    "from": from_model,
                    "to": to_model,
                    "fk": rel.get('fk_column', ''),
                    "pk": rel.get('pk_column', '')
                })
        
        return {"nodes": result_nodes, "edges": result_edges}
    
    def get_category_graph(self, category_type: Optional[str] = None) -> Dict:
        """
        Get category-level graph showing collapsed buckets.
        Returns category nodes and counts.
        """
        all_models = self.indexer.list_models()
        
        categories = {
            "entities": [],
            "metrics": [],
            "dimensions": [],
            "models": []
        }
        
        for model in all_models:
            if isinstance(model, dict):
                name = model.get('name')
                # Categorize based on model properties
                # This is simplified - you may need to adjust based on your metadata structure
                if model.get('type') == 'metric':
                    categories["metrics"].append(name)
                elif model.get('type') == 'dimension':
                    categories["dimensions"].append(name)
                elif model.get('type') == 'entity':
                    categories["entities"].append(name)
                else:
                    categories["models"].append(name)
            elif isinstance(model, str):
                categories["models"].append(model)
        
        # Build category nodes
        category_nodes = []
        for cat_type, items in categories.items():
            if category_type and cat_type != category_type:
                continue
            category_nodes.append({
                "name": f"{cat_type}_category",
                "type": "category",
                "category_type": cat_type,
                "count": len(items),
                "items": items[:50]  # Limit to 50 items per category
            })
        
        # Category graph has no edges (they're collapsed)
        return {
            "nodes": category_nodes,
            "edges": [],
            "categories": {k: len(v) for k, v in categories.items()}
        }