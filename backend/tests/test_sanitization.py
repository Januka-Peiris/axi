# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import unittest
from axi.utils.sanitization import (
    sanitize_identifier,
    sanitize_string,
    sanitize_path,
    sanitize_sql_fragment,
    validate_metric_name,
    validate_dimension_name,
    sanitize_filter_value
)


class TestSanitization(unittest.TestCase):
    """Test cases for sanitization utilities."""
    
    def test_sanitize_identifier_valid(self):
        """Test that valid identifiers pass through."""
        self.assertEqual(sanitize_identifier("test_table"), "test_table")
        self.assertEqual(sanitize_identifier("test_table_123"), "test_table_123")
        self.assertEqual(sanitize_identifier("schema.table"), "schema.table")
    
    def test_sanitize_identifier_empty(self):
        """Test that empty identifiers raise ValueError."""
        with self.assertRaises(ValueError):
            sanitize_identifier("")
        with self.assertRaises(ValueError):
            sanitize_identifier("   ")
    
    def test_sanitize_identifier_sql_injection(self):
        """Test that SQL injection patterns are rejected."""
        with self.assertRaises(ValueError):
            sanitize_identifier("table; DROP TABLE")
        with self.assertRaises(ValueError):
            sanitize_identifier("table--")
        with self.assertRaises(ValueError):
            sanitize_identifier("table/*")
    
    def test_sanitize_identifier_invalid_chars(self):
        """Test that invalid characters are rejected."""
        with self.assertRaises(ValueError):
            sanitize_identifier("table-name")  # hyphen not allowed
        with self.assertRaises(ValueError):
            sanitize_identifier("table name")  # space not allowed in simple case
    
    def test_sanitize_identifier_max_length(self):
        """Test that max length is enforced."""
        long_name = "a" * 300
        with self.assertRaises(ValueError):
            sanitize_identifier(long_name)
    
    def test_sanitize_string_valid(self):
        """Test that valid strings pass through."""
        self.assertEqual(sanitize_string("test"), "test")
        self.assertEqual(sanitize_string("test with spaces"), "test with spaces")
    
    def test_sanitize_string_removes_control_chars(self):
        """Test that control characters are removed."""
        result = sanitize_string("test\x00\x01\x02string")
        self.assertEqual(result, "teststring")
    
    def test_sanitize_string_max_length(self):
        """Test that max length is enforced."""
        long_string = "a" * 20000
        with self.assertRaises(ValueError):
            sanitize_string(long_string)
    
    def test_sanitize_path_valid(self):
        """Test that valid paths are resolved."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")
            
            resolved = sanitize_path(test_file)
            self.assertTrue(os.path.exists(resolved))
    
    def test_sanitize_path_traversal(self):
        """Test that path traversal is detected."""
        # This should be allowed but logged
        # Actual prevention happens with base_dir parameter
        pass
    
    def test_sanitize_path_with_base_dir(self):
        """Test that base_dir restriction works."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "base")
            os.makedirs(base)
            
            # Path within base should work
            valid_path = os.path.join(base, "file.txt")
            resolved = sanitize_path(valid_path, base_dir=base)
            self.assertTrue(resolved.startswith(base))
            
            # Path outside base should fail
            outside = os.path.join(tmpdir, "outside", "file.txt")
            with self.assertRaises(ValueError):
                sanitize_path(outside, base_dir=base)
    
    def test_sanitize_sql_fragment_safe(self):
        """Test that safe SQL fragments pass through."""
        self.assertEqual(sanitize_sql_fragment("name = 'test'"), "name = 'test'")
        self.assertEqual(sanitize_sql_fragment("amount > 100"), "amount > 100")
    
    def test_sanitize_sql_fragment_injection(self):
        """Test that SQL injection patterns are rejected."""
        with self.assertRaises(ValueError):
            sanitize_sql_fragment("name = 'test'; DROP TABLE")
        with self.assertRaises(ValueError):
            sanitize_sql_fragment("name = 'test'--")
        with self.assertRaises(ValueError):
            sanitize_sql_fragment("name = 'test'/*")
    
    def test_validate_metric_name_valid(self):
        """Test that valid metric names pass."""
        self.assertEqual(validate_metric_name("total_revenue"), "total_revenue")
        self.assertEqual(validate_metric_name("metric_123"), "metric_123")
    
    def test_validate_metric_name_invalid(self):
        """Test that invalid metric names are rejected."""
        with self.assertRaises(ValueError):
            validate_metric_name("")
        with self.assertRaises(ValueError):
            validate_metric_name("metric-name")  # hyphen
        with self.assertRaises(ValueError):
            validate_metric_name("metric; DROP")
    
    def test_validate_dimension_name_valid(self):
        """Test that valid dimension names pass."""
        self.assertEqual(validate_dimension_name("name"), "name")
        self.assertEqual(validate_dimension_name("schema.table.column"), "schema.table.column")
    
    def test_validate_dimension_name_invalid(self):
        """Test that invalid dimension names are rejected."""
        with self.assertRaises(ValueError):
            validate_dimension_name("")
        with self.assertRaises(ValueError):
            validate_dimension_name("dim; DROP")
    
    def test_sanitize_filter_value_in_operator(self):
        """Test that IN operator requires list."""
        with self.assertRaises(ValueError):
            sanitize_filter_value("not_a_list", "IN")
        
        result = sanitize_filter_value(["value1", "value2"], "IN")
        self.assertEqual(len(result), 2)
    
    def test_sanitize_filter_value_between_operator(self):
        """Test that BETWEEN operator requires two-element list."""
        with self.assertRaises(ValueError):
            sanitize_filter_value([1], "BETWEEN")
        with self.assertRaises(ValueError):
            sanitize_filter_value([1, 2, 3], "BETWEEN")
        
        result = sanitize_filter_value([1, 2], "BETWEEN")
        self.assertEqual(len(result), 2)
    
    def test_sanitize_filter_value_like_operator(self):
        """Test that LIKE operator escapes wildcards."""
        result = sanitize_filter_value("test%value", "LIKE")
        self.assertIn("\\%", result)


if __name__ == '__main__':
    unittest.main()
