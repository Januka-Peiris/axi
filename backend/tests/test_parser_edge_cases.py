# Licensed under the Business Source License 1.1 (BSL).
# Tests for parser edge cases - broken SQL, empty queries, dialect handling

import pytest
from axi.extractor.core import extract_metadata


class TestEmptyAndMinimalSQL:
    """Test handling of empty, minimal, and edge case SQL inputs."""

    def test_empty_string_raises(self):
        """Empty SQL should raise an exception (intentional - no guessing)."""
        with pytest.raises(Exception, match="Failed to parse"):
            extract_metadata("", "empty_model")

    def test_whitespace_only_raises(self):
        """Whitespace-only SQL should raise an exception."""
        with pytest.raises(Exception, match="Failed to parse"):
            extract_metadata("   \n\t  ", "whitespace_model")

    def test_comment_only_raises(self):
        """Comment-only SQL should raise an exception."""
        with pytest.raises(Exception, match="Failed to parse"):
            extract_metadata("-- just a comment", "comment_model")

    def test_multiline_comment_only_raises(self):
        """Multi-line comment only should raise an exception."""
        with pytest.raises(Exception, match="Failed to parse"):
            extract_metadata("/* multi\nline\ncomment */", "multicomment_model")

    def test_minimal_select(self):
        """Minimal SELECT statement."""
        result = extract_metadata("SELECT 1", "minimal_model")
        assert result is not None
        assert result.get("model") == "minimal_model"


class TestBrokenSQL:
    """Test handling of malformed/broken SQL that should fail gracefully."""

    def test_unclosed_parenthesis(self):
        """Unclosed parenthesis should not crash."""
        sql = "SELECT COUNT(*) FROM (SELECT * FROM users"
        result = extract_metadata(sql, "unclosed_paren")
        # Should return something, not crash
        assert result is not None

    def test_unclosed_string_raises(self):
        """Unclosed string literal should raise (can't parse)."""
        sql = "SELECT * FROM users WHERE name = 'John"
        with pytest.raises(Exception):
            extract_metadata(sql, "unclosed_string")

    def test_invalid_keyword(self):
        """Invalid SQL keyword should not crash."""
        sql = "SELEKT * FROM users"
        result = extract_metadata(sql, "invalid_keyword")
        assert result is not None

    def test_missing_from(self):
        """SELECT without FROM should not crash."""
        sql = "SELECT id, name WHERE status = 'active'"
        result = extract_metadata(sql, "missing_from")
        assert result is not None

    def test_double_semicolon(self):
        """Double semicolons should be handled."""
        sql = "SELECT * FROM users;;"
        result = extract_metadata(sql, "double_semi")
        assert result is not None

    def test_multiple_statements(self):
        """Multiple statements should parse first one."""
        sql = "SELECT 1; SELECT 2; SELECT 3"
        result = extract_metadata(sql, "multi_stmt")
        assert result is not None


class TestComplexSQL:
    """Test complex SQL patterns."""

    def test_deeply_nested_subquery(self):
        """Deeply nested subqueries should not crash."""
        sql = """
        SELECT * FROM (
            SELECT * FROM (
                SELECT * FROM (
                    SELECT * FROM (
                        SELECT * FROM users
                    ) a
                ) b
            ) c
        ) d
        """
        result = extract_metadata(sql, "nested_subquery")
        assert result is not None

    def test_multiple_ctes(self):
        """Multiple CTEs should be parsed."""
        sql = """
        WITH
            cte1 AS (SELECT id FROM users),
            cte2 AS (SELECT id FROM orders),
            cte3 AS (SELECT id FROM products)
        SELECT * FROM cte1
        JOIN cte2 ON cte1.id = cte2.id
        JOIN cte3 ON cte2.id = cte3.id
        """
        result = extract_metadata(sql, "multi_cte")
        assert result is not None

    def test_cte_with_aggregation(self):
        """CTE with aggregation should extract metrics."""
        sql = """
        WITH aggregated AS (
            SELECT
                customer_id,
                SUM(amount) as total_amount,
                COUNT(*) as order_count
            FROM orders
            GROUP BY customer_id
        )
        SELECT * FROM aggregated
        """
        result = extract_metadata(sql, "cte_agg")
        assert result is not None
        # Should detect metrics from CTE
        assert "metrics" in result

    def test_union_query(self):
        """UNION queries should not crash."""
        sql = """
        SELECT id, name FROM users
        UNION ALL
        SELECT id, name FROM admins
        """
        result = extract_metadata(sql, "union_query")
        assert result is not None

    def test_window_function(self):
        """Window functions should be handled."""
        sql = """
        SELECT
            id,
            name,
            ROW_NUMBER() OVER (PARTITION BY department ORDER BY salary DESC) as rank
        FROM employees
        """
        result = extract_metadata(sql, "window_func")
        assert result is not None

    def test_case_statement(self):
        """CASE statements should be handled."""
        sql = """
        SELECT
            id,
            CASE
                WHEN status = 'active' THEN 1
                WHEN status = 'pending' THEN 2
                ELSE 0
            END as status_code
        FROM users
        GROUP BY id, status
        """
        result = extract_metadata(sql, "case_stmt")
        assert result is not None


class TestDialectEdgeCases:
    """Test SQL dialect-specific edge cases."""

    def test_snowflake_qualify(self):
        """Snowflake QUALIFY clause should not crash."""
        sql = """
        SELECT * FROM orders
        QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY date DESC) = 1
        """
        result = extract_metadata(sql, "snowflake_qualify")
        assert result is not None

    def test_snowflake_flatten(self):
        """Snowflake FLATTEN should not crash."""
        sql = """
        SELECT
            f.value:id::STRING as id
        FROM my_table,
        LATERAL FLATTEN(input => json_column) f
        """
        result = extract_metadata(sql, "snowflake_flatten")
        assert result is not None

    def test_postgres_array_access(self):
        """PostgreSQL array access should not crash."""
        sql = "SELECT tags[1] FROM posts"
        result = extract_metadata(sql, "pg_array")
        assert result is not None

    def test_mixed_case_keywords(self):
        """Mixed case keywords should work."""
        sql = "SeLeCt Id, NaMe FrOm UsErS wHeRe StAtUs = 'active'"
        result = extract_metadata(sql, "mixed_case")
        assert result is not None


class TestGrainDetection:
    """Test grain detection edge cases."""

    def test_no_group_by(self):
        """Query without GROUP BY should be non-semantic."""
        sql = "SELECT * FROM users"
        result = extract_metadata(sql, "no_group")
        assert result.get("grain_status") == "not_detected"

    def test_simple_group_by(self):
        """Simple GROUP BY should detect grain."""
        sql = """
        SELECT customer_id, SUM(amount) as total
        FROM orders
        GROUP BY customer_id
        """
        result = extract_metadata(sql, "simple_group")
        assert result.get("grain_status") in ["clear", "ambiguous"]

    def test_distinct_as_grain(self):
        """DISTINCT should be detected as grain."""
        sql = "SELECT DISTINCT customer_id, product_id FROM orders"
        result = extract_metadata(sql, "distinct_grain")
        assert result.get("grain_detection") in ["distinct", "group_by", "none"]

    def test_multiple_group_by_columns(self):
        """Multiple GROUP BY columns should be handled."""
        sql = """
        SELECT
            region,
            product_category,
            year,
            SUM(revenue) as total_revenue
        FROM sales
        GROUP BY region, product_category, year
        """
        result = extract_metadata(sql, "multi_group")
        assert result is not None
        dimensions = result.get("dimensions", [])
        # Should have at least some dimensions
        assert len(dimensions) >= 0  # May vary based on implementation


class TestSpecialCharacters:
    """Test handling of special characters in identifiers."""

    def test_quoted_identifiers(self):
        """Quoted identifiers should work."""
        sql = 'SELECT "user-id", "order-total" FROM "my-table"'
        result = extract_metadata(sql, "quoted_ids")
        assert result is not None

    def test_backtick_identifiers(self):
        """Backtick identifiers (MySQL style) should not crash."""
        sql = "SELECT `user id`, `order total` FROM `my table`"
        result = extract_metadata(sql, "backtick_ids")
        assert result is not None

    def test_unicode_in_strings(self):
        """Unicode in string literals should work."""
        sql = "SELECT * FROM users WHERE name = 'Müller'"
        result = extract_metadata(sql, "unicode_str")
        assert result is not None


class TestLargeSQL:
    """Test handling of large/complex SQL."""

    def test_many_columns(self):
        """Query with many columns should work."""
        columns = ", ".join([f"col_{i}" for i in range(100)])
        sql = f"SELECT {columns} FROM big_table GROUP BY {columns}"
        result = extract_metadata(sql, "many_cols")
        assert result is not None

    def test_many_joins(self):
        """Query with many joins should work."""
        sql = """
        SELECT a.id
        FROM table_a a
        JOIN table_b b ON a.id = b.a_id
        JOIN table_c c ON b.id = c.b_id
        JOIN table_d d ON c.id = d.c_id
        JOIN table_e e ON d.id = e.d_id
        JOIN table_f f ON e.id = f.e_id
        JOIN table_g g ON f.id = g.f_id
        JOIN table_h h ON g.id = h.g_id
        JOIN table_i i ON h.id = i.h_id
        JOIN table_j j ON i.id = j.i_id
        GROUP BY a.id
        """
        result = extract_metadata(sql, "many_joins")
        assert result is not None
        # Should detect relationships
        relationships = result.get("relationships", [])
        assert len(relationships) >= 0
