# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import os
import json
import sqlite3
from typing import List, Optional
from axi.config.settings import get_settings
from axi.glossary.glossary_models import Glossary, GlossaryEntity, GlossaryMetric, GlossaryDimension, GlossaryRelationship

settings = get_settings()

class GlossaryStore:
    def __init__(self, metadata_dir: str = None):
        self.metadata_dir = metadata_dir or settings.AXI_METADATA_DIR
        self.db_path = os.path.join(self.metadata_dir, "axi.db")
        self.json_path = os.path.join(self.metadata_dir, "glossary.json")
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_conn()
        c = conn.cursor()
        
        # Glossary Tables
        c.execute('''CREATE TABLE IF NOT EXISTS glossary_entities (
            name TEXT PRIMARY KEY,
            model_name TEXT,
            description TEXT,
            data JSON -- stores attributes, tags, etc.
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS glossary_metrics (
            name TEXT PRIMARY KEY,
            expression TEXT,
            type TEXT,
            description TEXT,
            data JSON -- stores dims, filters, grain, sources, tags
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS glossary_dimensions (
            name TEXT PRIMARY KEY,
            data_type TEXT,
            description TEXT,
            data JSON -- attributes, related_metrics, tags
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS glossary_relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_entity TEXT,
            target_entity TEXT,
            rel_type TEXT,
            description TEXT,
            data JSON -- keys
        )''')
        
        conn.commit()
        conn.close()

    def save(self, glossary: Glossary):
        """
        Persists full glossary to SQLite and JSON file.
        """
        # 1. Save to JSON
        with open(self.json_path, "w") as f:
            f.write(glossary.model_dump_json(indent=2))
            
        # 2. Save to SQLite
        conn = self._get_conn()
        c = conn.cursor()
        
        # Clear existing
        c.execute("DELETE FROM glossary_entities")
        c.execute("DELETE FROM glossary_metrics")
        c.execute("DELETE FROM glossary_dimensions")
        c.execute("DELETE FROM glossary_relationships")
        
        # Entities
        for e in glossary.entities:
            c.execute("INSERT INTO glossary_entities (name, model_name, description, data) VALUES (?, ?, ?, ?)",
                      (e.name, e.model, e.description, e.model_dump_json(include={"attributes", "metrics", "tags", "relationships"})))
                      
        # Metrics
        for m in glossary.metrics:
            c.execute("INSERT INTO glossary_metrics (name, expression, type, description, data) VALUES (?, ?, ?, ?, ?)",
                      (m.name, m.expression, m.metric_type, m.description, m.model_dump_json(include={"dimensions", "default_filters", "grain", "tags", "sources"})))
                      
        # Dimensions
        for d in glossary.dimensions:
             c.execute("INSERT INTO glossary_dimensions (name, data_type, description, data) VALUES (?, ?, ?, ?)",
                       (d.name, d.data_type, d.description, d.model_dump_json(include={"attributes", "related_metrics", "tags"})))
                       
        # Relationships
        for r in glossary.relationships:
            c.execute("INSERT INTO glossary_relationships (source_entity, target_entity, rel_type, description, data) VALUES (?, ?, ?, ?, ?)",
                      (r.source_entity, r.target_entity, r.type, r.description, r.model_dump_json(include={"source_key", "target_key"})))

        conn.commit()
        conn.close()

    def load_from_json(self) -> Optional[Glossary]:
        if not os.path.exists(self.json_path):
            return None
        with open(self.json_path, "r") as f:
            data = json.load(f)
            return Glossary(**data)
            
    # API Helpers
    
    def list_entities(self) -> List[GlossaryEntity]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT name, model_name, description, data FROM glossary_entities")
        rows = c.fetchall()
        conn.close()
        
        res = []
        for r in rows:
            base = {"name": r[0], "model": r[1], "description": r[2]}
            data = json.loads(r[3])
            res.append(GlossaryEntity(**base, **data))
        return res

    def get_entity(self, name: str) -> Optional[GlossaryEntity]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT name, model_name, description, data FROM glossary_entities WHERE name = ?", (name,))
        row = c.fetchone()
        conn.close()
        
        if row:
            base = {"name": row[0], "model": row[1], "description": row[2]}
            data = json.loads(row[3])
            return GlossaryEntity(**base, **data)
        return None

    def list_metrics(self) -> List[GlossaryMetric]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT name, expression, type, description, data FROM glossary_metrics")
        rows = c.fetchall()
        conn.close()
        
        res = []
        for r in rows:
            base = {"name": r[0], "expression": r[1], "metric_type": r[2], "description": r[3]}
            data = json.loads(r[4])
            res.append(GlossaryMetric(**base, **data))
        return res
        
    def get_metric(self, name: str) -> Optional[GlossaryMetric]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT name, expression, type, description, data FROM glossary_metrics WHERE name = ?", (name,))
        row = c.fetchone()
        conn.close()
        
        if row:
            base = {"name": row[0], "expression": row[1], "metric_type": row[2], "description": row[3]}
            data = json.loads(row[4])
            return GlossaryMetric(**base, **data)
        return None

    def list_dimensions(self) -> List[GlossaryDimension]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT name, data_type, description, data FROM glossary_dimensions")
        rows = c.fetchall()
        conn.close()
        
        res = []
        for r in rows:
            base = {"name": r[0], "data_type": r[1], "description": r[2]}
            data = json.loads(r[3])
            res.append(GlossaryDimension(**base, **data))
        return res

    def get_dimension(self, name: str) -> Optional[GlossaryDimension]:
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT name, data_type, description, data FROM glossary_dimensions WHERE name = ?", (name,))
        row = c.fetchone()
        conn.close()
        
        if row:
            base = {"name": row[0], "data_type": row[1], "description": row[2]}
            data = json.loads(row[3])
            return GlossaryDimension(**base, **data)
        return None

    def search(self, query: str) -> List[dict]:
        # Simple wildcard search across tables
        conn = self._get_conn()
        c = conn.cursor()
        q = f"%{query}%"
        
        results = []
        
        # Entities
        c.execute("SELECT name, description, 'entity' as type FROM glossary_entities WHERE name LIKE ? OR description LIKE ?", (q, q))
        for r in c.fetchall():
            results.append({"name": r[0], "description": r[1], "type": r[2]})
            
        # Metrics
        c.execute("SELECT name, description, 'metric' as type FROM glossary_metrics WHERE name LIKE ? OR description LIKE ?", (q, q))
        for r in c.fetchall():
            results.append({"name": r[0], "description": r[1], "type": r[2]})

        # Dimensions
        c.execute("SELECT name, description, 'dimension' as type FROM glossary_dimensions WHERE name LIKE ? OR description LIKE ?", (q, q))
        for r in c.fetchall():
            results.append({"name": r[0], "description": r[1], "type": r[2]})
            
        conn.close()
        return results
