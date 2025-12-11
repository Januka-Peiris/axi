# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import hashlib
import json
import sqlite3
import time
from typing import Dict, Any, List, Optional
from axi.metadata.indexer import MetadataIndexer

class QueryCache:
    def __init__(self, indexer: MetadataIndexer, ttl_seconds: int = 3600):
        self.indexer = indexer
        self.ttl_seconds = ttl_seconds

    def generate_key(self, metric: str, dimensions: List[str], filters: List[str], dialect: str, sql: str) -> str:
        """
        Generates a deterministic cache key.
        """
        key_parts = [
            metric,
            json.dumps(sorted(dimensions)),
            json.dumps(sorted(filters)),
            dialect,
            sql
        ]
        raw_key = "|".join(key_parts)
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        conn = self.indexer._get_conn()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM cache_entries WHERE cache_key = ?", (key,))
        row = c.fetchone()
        conn.close()
        
        if row:
            entry = dict(row)
            # Check expiration
            if time.time() > entry['expires_at']:
                self.delete(key)
                return None
            
            entry['dimensions'] = json.loads(entry['dimensions'])
            entry['filters'] = json.loads(entry['filters'])
            entry['storage_location'] = json.loads(entry['storage_location'])
            return entry
        return None

    def set(self, key: str, metric: str, dimensions: List[str], filters: List[str], sql: str, row_count: int, location: Dict[str, Any]):
        conn = self.indexer._get_conn()
        c = conn.cursor()
        
        created_at = time.time()
        expires_at = created_at + self.ttl_seconds
        
        c.execute("""
            INSERT OR REPLACE INTO cache_entries 
            (cache_key, metric, dimensions, filters, sql, created_at, expires_at, row_count, storage_location)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (key, metric, json.dumps(dimensions), json.dumps(filters), sql, created_at, expires_at, row_count, json.dumps(location)))
        
        conn.commit()
        conn.close()

    def delete(self, key: str):
        conn = self.indexer._get_conn()
        c = conn.cursor()
        c.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
        conn.commit()
        conn.close()

    def clear(self, metric: Optional[str] = None):
        conn = self.indexer._get_conn()
        c = conn.cursor()
        if metric:
            c.execute("DELETE FROM cache_entries WHERE metric = ?", (metric,))
        else:
            c.execute("DELETE FROM cache_entries")
        conn.commit()
        conn.close()
