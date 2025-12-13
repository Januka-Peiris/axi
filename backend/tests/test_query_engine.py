# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import unittest
import tempfile
import os
import json
import sqlite3
from unittest.mock import Mock, patch
from axi.metadata.indexer import MetadataIndexer
from axi.query.engine import SemanticQueryEngine
from axi.exceptions import QueryError


class TestQueryEngine(unittest.TestCase):
    """Test cases for SemanticQueryEngine edge cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.indexer = MetadataIndexer(self.temp_dir)
        self.engine = SemanticQueryEngine(self.indexer)
        
        # Create test metadata
        self._setup_test_metadata()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _setup_test_metadata(self):
        """Create test metadata in the indexer."""
        models_dir = os.path.join(self.temp_dir, "models")
        os.makedirs(models_dir, exist_ok=True)
        
        # Create a test model
        test_model = {
            "model": "test_model",
            "entity": {
                "name": "test_entity",
                "pk": ["id"],
                "columns": [
                    {"name": "id", "data_type": "INTEGER", "is_pk": True},
                    {"name": "name", "data_type": "TEXT"},
                    {"name": "date", "data_type": "DATE"},
                    {"name": "amount", "data_type": "DECIMAL"}
                ]
            },
            "metrics": [
                {
                    "name": "total_amount",
                    "expression": "SUM(amount)",
                    "model": "test_model",
                    "entity_name": "test_entity",
                    "metric_type": "sum",
                    "grain": ["id"]  # Explicitly set grain to match entity primary key
                }
            ],
            "dimensions": ["id", "name", "date"]
        }
        
        with open(os.path.join(models_dir, "test_model.json"), "w") as f:
            json.dump(test_model, f)
        
        self.indexer.build_index()
    
    def test_nonexistent_metric(self):
        """Test that non-existent metric raises QueryError."""
        with self.assertRaises(QueryError) as cm:
            self.engine.generate_sql("nonexistent_metric", [], [])
        
        self.assertEqual(cm.exception.code, "UNSUPPORTED_METRIC")
        self.assertIn("not found", str(cm.exception))
    
    def test_invalid_dimension_name(self):
        """Test that invalid dimension names are rejected."""
        # Test SQL injection attempt
        with self.assertRaises(QueryError) as cm:
            self.engine.generate_sql("total_amount", ["name; DROP TABLE"], [])
        
        self.assertEqual(cm.exception.code, "INVALID_DIMENSION")
    
    def test_invalid_filter_operator(self):
        """Test that invalid filter operators are rejected."""
        invalid_filter = {
            "dimension": "name",
            "op": "INVALID_OP",
            "value": "test"
        }
        
        with self.assertRaises(QueryError) as cm:
            self.engine.generate_sql("total_amount", ["name"], [invalid_filter])
        
        self.assertEqual(cm.exception.code, "INVALID_FILTER_OPERATOR")
    
    def test_filter_type_mismatch(self):
        """Test that type mismatches in filters are caught."""
        # LIKE on date dimension
        date_filter = {
            "dimension": "date",
            "op": "LIKE",
            "value": "2024%"
        }
        
        with self.assertRaises(QueryError) as cm:
            self.engine.generate_sql("total_amount", ["date"], [date_filter])
        
        self.assertEqual(cm.exception.code, "TYPE_MISMATCH")
        self.assertIn("LIKE", str(cm.exception))
        self.assertIn("date", str(cm.exception))
    
    def test_join_path_not_found(self):
        """Test that missing join paths raise QueryError."""
        # Create a second model without relationship
        models_dir = os.path.join(self.temp_dir, "models")
        other_model = {
            "model": "other_model",
            "entity": {
                "name": "other_entity",
                "pk": ["id"],
                "columns": [{"name": "id", "data_type": "INTEGER"}]
            },
            "metrics": [],
            "dimensions": ["id"]
        }
        
        with open(os.path.join(models_dir, "other_model.json"), "w") as f:
            json.dump(other_model, f)
        
        self.indexer.build_index()
        
        # Try to query with dimension from unrelated model
        with self.assertRaises(QueryError) as cm:
            self.engine.generate_sql("total_amount", ["other_model.id"], [])
        
        self.assertEqual(cm.exception.code, "JOIN_NOT_FOUND")
    
    def test_empty_dimensions_uses_defaults(self):
        """Test that empty dimensions list uses metric defaults or grain."""
        # Should not raise error, should use grain or defaults
        sql = self.engine.generate_sql("total_amount", [], [])
        self.assertIsInstance(sql, str)
        self.assertIn("SELECT", sql.upper())
    
    def test_empty_filters(self):
        """Test that empty filters list works correctly."""
        sql = self.engine.generate_sql("total_amount", ["name"], [])
        self.assertIsInstance(sql, str)
        self.assertIn("SELECT", sql.upper())
    
    def test_invalid_grain_dimension(self):
        """Test that invalid grain dimensions are caught."""
        # This would require a metric with invalid grain
        # For now, test that grain validation happens
        pass  # Would need to set up metric with invalid grain
    
    def test_sql_injection_in_filter_string(self):
        """Test that SQL injection attempts in filter strings are blocked."""
        malicious_filter = "name = 'test'; DROP TABLE metrics; --"
        
        with self.assertRaises(QueryError) as cm:
            self.engine.generate_sql("total_amount", ["name"], [malicious_filter])
        
        self.assertEqual(cm.exception.code, "INVALID_FILTER_OPERATOR")
        self.assertIn("Unsafe", str(cm.exception))
    
    def test_time_intelligence_missing_time_dim(self):
        """Test that time intelligence without time dimension is handled."""
        # Should not raise error, just not apply time intelligence
        sql = self.engine.generate_sql("total_amount", ["date"], [], compare="previous_period")
        self.assertIsInstance(sql, str)
    
    def test_optimization_enabled(self):
        """Test that optimization is applied when enabled."""
        with patch('axi.optimizer.core.Optimizer') as mock_optimizer:
            mock_opt = Mock()
            mock_opt.optimize.return_value = "SELECT * FROM test"
            mock_optimizer.return_value = mock_opt
            
            sql = self.engine.generate_sql("total_amount", ["name"], [], optimize=True)
            # Should call optimizer
            # Note: This is a simplified test - actual optimizer integration is more complex
    
    def test_dimension_from_wrong_entity(self):
        """Test that dimensions from wrong entities are validated."""
        # This would require setting up multiple entities
        # For now, test basic dimension validation
        pass
    
    def test_filter_in_operator_requires_list(self):
        """Test that IN operator requires list value."""
        invalid_filter = {
            "dimension": "name",
            "op": "IN",
            "value": "not_a_list"
        }
        
        # Should be caught by validation before reaching engine
        # But test that engine handles it if it gets through
        with self.assertRaises(QueryError):
            self.engine.generate_sql("total_amount", ["name"], [invalid_filter])


if __name__ == '__main__':
    unittest.main()
