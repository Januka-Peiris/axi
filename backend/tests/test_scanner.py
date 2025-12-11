import os
import shutil
import unittest
from axi.extractor.scanner import SqlScanner
from axi.extractor.promotion import PromotionResult

class MockPromotionEngine:
    def check_promotion(self, path, tags):
        # Always promote in tests
        return PromotionResult(promoted=True, reason="test", matched_rule=None)

class TestScanner(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_dbt_project"
        os.makedirs(self.test_dir, exist_ok=True)
        # Mock dbt_project.yml
        with open(os.path.join(self.test_dir, "dbt_project.yml"), "w") as f:
            f.write("name: test_project\n")
        
        # Mock models
        os.makedirs(os.path.join(self.test_dir, "models"), exist_ok=True)
        with open(os.path.join(self.test_dir, "models/raw_model.sql"), "w") as f:
            f.write("SELECT * FROM {{ ref('other') }}")

        # Mock compiled
        compiled_dir = os.path.join(self.test_dir, "target/compiled/test_project/models")
        os.makedirs(compiled_dir, exist_ok=True)
        with open(os.path.join(compiled_dir, "raw_model.sql"), "w") as f:
            f.write("SELECT * FROM db.schema.other")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_compiled_priority(self):
        scanner = SqlScanner(self.test_dir, MockPromotionEngine())
        models = list(scanner.scan())
        self.assertEqual(len(models), 1)
        # Should use compiled content
        self.assertIn("db.schema.other", models[0].content)
        self.assertNotIn("{{", models[0].content)

if __name__ == '__main__':
    unittest.main()
