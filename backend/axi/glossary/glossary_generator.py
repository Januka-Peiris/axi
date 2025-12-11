# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import datetime
import yaml
from typing import List, Dict, Any
from axi.config.settings import get_settings
from axi.metadata.indexer import MetadataIndexer
from axi.glossary.glossary_models import (
    Glossary, GlossaryEntity, GlossaryAttribute, GlossaryMetric, 
    GlossaryDimension, GlossaryRelationship
)

settings = get_settings()

class GlossaryGenerator:
    def __init__(self, metadata_dir: str = None):
        self.metadata_dir = metadata_dir or settings.AXI_METADATA_DIR
        self.indexer = MetadataIndexer(self.metadata_dir)
        
    def generate(self) -> Glossary:
        # Load Raw Metadata
        models = self.indexer.list_models() # returns names
        raw_metrics = self.indexer.list_metrics() # returns dictionaries
        relationships = self.indexer.list_relationships() # returns list of dicts
        
        # 1. Build Entities
        entities = []
        model_entity_map = {} # model_name -> entity_name
        
        for model_config in models:
            m_name = model_config['name'] if isinstance(model_config, dict) else model_config
            m_def = self.indexer.get_model(m_name)
            if not m_def: continue
            
            # Heuristic: Entity name = Model name (capitalized/spaced?) for now keep as model name or prettify
            entity_name = m_name # can improve later
            model_entity_map[m_name] = entity_name
            
            # Attributes
            attributes = []
            # Where do we get columns? indexer.get_model returns {dimensions: ...}
            # We might need to look at source tables to get full column list if dimensions are just a subset.
            # But "Glossary" usually focuses on Semantic Dimensions.
            # Let's inspect "dimensions" from the model definition.
            
            # If dimensions is a list of strings (col names) or dicts?
            # get_model returns: "dimensions": [...]
            
            for dim in m_def.get('dimensions', []):
                # Dim might be string or dict? Assuming string for now based on previous indexing logic
                dim_name = dim if isinstance(dim, str) else dim.get('name')
                attributes.append(GlossaryAttribute(
                    name=dim_name,
                    data_type="unknown", # Metadata doesn't seem to store type in 'model' table yet?
                    source_column=dim_name,
                    is_pk=False # TODO: infer from constraints if available
                ))
                
            # Related Metrics
            # We have list of metrics, check which belong to this model
            related_metrics = [
                met['name'] for met in raw_metrics if met.get('model') == m_name
            ]
            
            ent = GlossaryEntity(
                name=entity_name,
                model=m_name,
                description=f"Entity derived from model {m_name}",
                attributes=attributes,
                metrics=related_metrics,
                relationships=[] 
            )
            entities.append(ent)
            
        # 2. Build Metrics
        metrics = []
        for rm in raw_metrics:
            import json
            def parse_list(v):
                if isinstance(v, str):
                    try: return json.loads(v)
                    except: return []
                return v or []

            metrics.append(GlossaryMetric(
                name=rm['name'],
                expression=rm['expression'],
                metric_type=rm['metric_type'],
                dimensions=parse_list(rm.get('dimensions')),
                description=rm.get('description'),
                default_filters=[rm.get('default_filter')] if rm.get('default_filter') else [],
                grain=rm.get('grain'),
                tags=parse_list(rm.get('tags')),
                sources=[rm.get('source_table')] if rm.get('source_table') else []
            ))
            
        # 3. Build Dimensions
        # Collect unique dimensions across all models
        dimension_map = {} # name -> GlossaryDimension
        
        for model_config in models:
            m_name = model_config['name'] if isinstance(model_config, dict) else model_config
            m_def = self.indexer.get_model(m_name)
            if not m_def: continue
            
            # Extract dimensions from model definition
            for dim in m_def.get('dimensions', []):
                d_name = dim if isinstance(dim, str) else dim.get('name')
                if not d_name: continue
                
                if d_name not in dimension_map:
                    dimension_map[d_name] = GlossaryDimension(
                        name=d_name,
                        data_type="unknown", # TODO: infer
                        attributes=[], # TODO: link to entity attributes?
                        related_metrics=[],
                        description=f"Dimension extracted from {m_name}",
                        tags=[]
                    )
                
                # Link related metrics
                # Find metrics that use this dimension
                for met in metrics:
                    if d_name in met.dimensions:
                        if met.name not in dimension_map[d_name].related_metrics:
                            dimension_map[d_name].related_metrics.append(met.name)

        glossary_dims = list(dimension_map.values())
        gloss_rels = []
        for rel in relationships:
            # rel: {parent_model, child_model, join_type, ...}
            source = model_entity_map.get(rel['parent_model'], rel['parent_model'])
            target = model_entity_map.get(rel['child_model'], rel['child_model'])
            
            gloss_rels.append(GlossaryRelationship(
                source_entity=source,
                target_entity=target,
                type=rel['join_type'],
                source_key=rel['pk_column'],
                target_key=rel['fk_column'],
                description=f"{rel['join_type']} relationship from {source} to {target}"
            ))
            
            # Also attach to entity objects? 
            # The GlossaryEntity model has 'relationships' list.
            # We should populate that.
            
        # Re-attach relationships to entities
        for ent in entities:
            # Outgoing
            ent_rels = [r for r in gloss_rels if r.source_entity == ent.name]
            ent.relationships = ent_rels

        # 5. Overrides
        self._apply_overrides(entities, metrics)
        
        return Glossary(
            generated_at=datetime.datetime.utcnow().isoformat() + "Z",
            entities=entities,
            metrics=metrics,
            dimensions=glossary_dims, # Empty for now unless we define shared dimensions
            relationships=gloss_rels
        )

    def _apply_overrides(self, entities: List[GlossaryEntity], metrics: List[GlossaryMetric]):
        # Load axi_glossary.yml
        config_path = os.path.join(self.metadata_dir, "..", "axi_glossary.yml") # Assuming root
        # Or check CWD?
        # Let's try explicit path or CWD
        if not os.path.exists(config_path):
            config_path = "axi_glossary.yml"
            
        if not os.path.exists(config_path):
            return
            
        try:
            with open(config_path, "r") as f:
                overrides = yaml.safe_load(f) or {}
                
            # Entities
            ent_map = {e.name: e for e in entities}
            for name, data in overrides.get("entities", {}).items():
                if name in ent_map:
                    if "description" in data:
                        ent_map[name].description = data["description"]
                    if "tags" in data:
                        ent_map[name].tags = data["tags"]
                        
            # Metrics
            met_map = {m.name: m for m in metrics}
            for name, data in overrides.get("metrics", {}).items():
                if name in met_map:
                    if "description" in data:
                        met_map[name].description = data["description"]
                    if "tags" in data:
                        met_map[name].tags = data["tags"]
                        
        except Exception as e:
            print(f"Warning: Failed to apply glossary overrides: {e}")
