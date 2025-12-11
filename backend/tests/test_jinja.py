import unittest
from axi.utils.jinja import strip_jinja

class TestJinjaStripper(unittest.TestCase):
    def test_variable_stripping(self):
        sql = "SELECT * FROM {{ ref('my_table') }}"
        expected = "SELECT * FROM /* jinja_expr */"
        self.assertEqual(strip_jinja(sql), expected)

    def test_block_stripping(self):
        sql = """
        {% set x = 1 %}
        SELECT 1
        """
        stripped = strip_jinja(sql)
        self.assertIn("SELECT 1", stripped)
        self.assertNotIn("{%", stripped)
        self.assertNotIn("%}", stripped)
        # Check explicit length preservation roughly (newlines should match)
        self.assertEqual(len(sql.splitlines()), len(stripped.splitlines()))

    def test_comment_stripping(self):
        sql = "SELECT 1 {# comment #}"
        stripped = strip_jinja(sql)
        self.assertIn("SELECT 1", stripped)
        self.assertNotIn("{#", stripped)

if __name__ == '__main__':
    unittest.main()
