#!/usr/bin/env python3
"""
Full End-to-End Test for AXI Pipeline

Tests:
1. Config loading
2. Promotion engine
3. SQL scanning
4. Metadata extraction
5. Index building
6. API endpoints
"""

import os
import sys
import tempfile
import shutil
import json
from pathlib import Path

# Add backend to path
BACKEND_DIR = Path(__file__).parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from axi.config.loader import load_config, Config, PromotionRules
from axi.extractor.promotion import PromotionEngine
from axi.extractor.scanner import SqlScanner
from axi.extractor.core import extract_metadata
from axi.metadata.writer import MetadataWriter
from axi.metadata.indexer import MetadataIndexer
from axi.config.settings import get_settings


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def test_pass(name):
    print(f"{Colors.GREEN}✓{Colors.END} {name}")


def test_fail(name, error):
    print(f"{Colors.RED}✗{Colors.END} {name}: {error}")
    return False


def test_info(name):
    print(f"{Colors.BLUE}→{Colors.END} {name}")


def test_config_loader():
    """Test config loading"""
    test_info("Testing config loader...")
    
    try:
        # Test default config
        config = Config()
        assert config.include is not None
        assert config.exclude is not None
        test_pass("Default config creation")
        
        # Test with promotion rules
        config = Config(
            include=PromotionRules(folders=["**"], tags=["axi"]),
            exclude=PromotionRules(folders=["test"], tags=[])
        )
        assert len(config.include.folders) == 1
        assert config.include.folders[0] == "**"
        test_pass("Config with promotion rules")
        
        return True
    except Exception as e:
        return test_fail("Config loader", str(e))


def test_promotion_engine():
    """Test promotion engine"""
    test_info("Testing promotion engine...")
    
    try:
        # Test with wildcard promotion
        config = Config(include=PromotionRules(folders=["**"], tags=[]))
        engine = PromotionEngine(config)
        
        # Should promote everything
        assert engine.is_promoted("any/path/file.sql", []) == True
        test_pass("Wildcard promotion")
        
        # Test with specific folder
        config = Config(include=PromotionRules(folders=["models/marts/**"], tags=[]))
        engine = PromotionEngine(config)
        assert engine.is_promoted("models/marts/revenue.sql", []) == True
        assert engine.is_promoted("models/staging/orders.sql", []) == False
        test_pass("Folder-based promotion")
        
        # Test exclusion
        config = Config(
            include=PromotionRules(folders=["**"], tags=[]),
            exclude=PromotionRules(folders=["models/test/**"], tags=[])
        )
        engine = PromotionEngine(config)
        assert engine.is_promoted("models/marts/revenue.sql", []) == True
        assert engine.is_promoted("models/test/temp.sql", []) == False
        test_pass("Exclusion rules")
        
        # Test tag-based promotion
        config = Config(include=PromotionRules(folders=[], tags=["axi"]))
        engine = PromotionEngine(config)
        assert engine.is_promoted("any/file.sql", ["axi"]) == True
        assert engine.is_promoted("any/file.sql", []) == False
        test_pass("Tag-based promotion")
        
        return True
    except Exception as e:
        return test_fail("Promotion engine", str(e))


def test_sql_scanner():
    """Test SQL scanner"""
    test_info("Testing SQL scanner...")
    
    try:
        # Create temp directory with SQL files
        with tempfile.TemporaryDirectory() as tmpdir:
            sql_dir = Path(tmpdir) / "models"
            sql_dir.mkdir()
            
            # Create test SQL files
            (sql_dir / "orders.sql").write_text("SELECT id, customer_id, amount FROM orders")
            (sql_dir / "revenue.sql").write_text("SELECT date, SUM(amount) as revenue FROM orders GROUP BY date")
            
            # Test scanner
            config = Config(include=PromotionRules(folders=["**"], tags=[]))
            engine = PromotionEngine(config)
            scanner = SqlScanner(str(sql_dir), engine)
            
            models = list(scanner.scan())
            assert len(models) == 2, f"Expected 2 models, got {len(models)}"
            test_pass(f"SQL scanner found {len(models)} models")
            
            # Check model paths
            paths = [m.path for m in models]
            assert "orders.sql" in paths or "models/orders.sql" in str(paths)
            test_pass("Model paths correct")
            
        return True
    except Exception as e:
        return test_fail("SQL scanner", str(e))


def test_metadata_extraction():
    """Test metadata extraction"""
    test_info("Testing metadata extraction...")
    
    try:
        # Test simple SELECT
        sql = "SELECT id, customer_id, amount FROM orders"
        meta = extract_metadata(sql, "orders")
        
        assert meta["model"] == "orders"
        assert "source_tables" in meta
        assert "orders" in meta["source_tables"]
        test_pass("Basic SELECT extraction")
        
        # Test aggregation
        sql = "SELECT date, SUM(amount) as total_revenue FROM orders GROUP BY date"
        meta = extract_metadata(sql, "revenue")
        
        assert len(meta["metrics"]) > 0, "Should extract metrics"
        assert any("revenue" in m.get("name", "").lower() for m in meta["metrics"])
        test_pass("Aggregation extraction")
        
        # Test dimensions
        assert len(meta["dimensions"]) > 0, "Should extract dimensions"
        assert "date" in meta["dimensions"]
        test_pass("Dimension extraction")
        
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return test_fail("Metadata extraction", str(e))


def test_metadata_writer():
    """Test metadata writer"""
    test_info("Testing metadata writer...")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            writer = MetadataWriter(tmpdir)
            
            meta = {
                "model": "test_model",
                "metrics": [{"name": "test_metric", "expression": "SUM(amount)"}],
                "dimensions": ["date"],
                "source_tables": ["orders"]
            }
            
            writer.write(meta)
            
            # Check JSON file created
            json_file = Path(tmpdir) / "models" / "test_model.json"
            assert json_file.exists(), "JSON metadata file should be created"
            test_pass("Metadata JSON file created")
            
            # Check content
            with open(json_file) as f:
                data = json.load(f)
            assert data["model"] == "test_model"
            test_pass("Metadata JSON content correct")
            
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return test_fail("Metadata writer", str(e))


def test_metadata_indexer():
    """Test metadata indexer"""
    test_info("Testing metadata indexer...")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = MetadataIndexer(tmpdir)
            
            # Build index
            indexer.build_index()
            
            # Check database exists (it's created in __init__)
            db_file = Path(tmpdir) / "axi.db"
            assert db_file.exists(), "Index database should be created"
            test_pass("Index database created")
            
            # Test listing (should work even if empty)
            entities = indexer.list_entities()
            metrics = indexer.list_metrics()
            assert isinstance(entities, list)
            assert isinstance(metrics, list)
            test_pass("Indexer list methods work")
            
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return test_fail("Metadata indexer", str(e))


def test_full_pipeline():
    """Test full extraction pipeline"""
    test_info("Testing full extraction pipeline...")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            sql_dir = Path(tmpdir) / "models"
            sql_dir.mkdir()
            
            # Create test SQL
            (sql_dir / "orders.sql").write_text(
                "SELECT id, customer_id, amount, order_date FROM orders"
            )
            (sql_dir / "revenue.sql").write_text(
                "SELECT order_date, SUM(amount) as total_revenue FROM orders GROUP BY order_date"
            )
            
            # Setup
            config = Config(include=PromotionRules(folders=["**"], tags=[]))
            promotion_engine = PromotionEngine(config)
            scanner = SqlScanner(str(sql_dir), promotion_engine)
            writer = MetadataWriter(tmpdir)
            indexer = MetadataIndexer(tmpdir)
            
            # Extract
            count = 0
            for model in scanner.scan():
                count += 1
                meta = extract_metadata(model.content, model.path.replace(".sql", ""))
                writer.write(meta)
            
            assert count == 2, f"Expected 2 models, got {count}"
            test_pass(f"Extracted {count} models")
            
            # Build index
            indexer.build_index()
            test_pass("Index built")
            
            # Verify index
            entities = indexer.list_entities()
            metrics = indexer.list_metrics()
            
            assert len(entities) > 0, "Should have entities"
            assert len(metrics) > 0, "Should have metrics"
            test_pass(f"Index has {len(entities)} entities and {len(metrics)} metrics")
            
        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        return test_fail("Full pipeline", str(e))


def test_api_endpoints():
    """Test API endpoints (if server available)"""
    test_info("Testing API endpoints...")
    
    try:
        # Just test that we can import and create router instances
        from axi.api.routers import metrics, dimensions
        
        # Check routers exist
        assert metrics.router is not None
        assert dimensions.router is not None
        test_pass("API routers importable")
        
        return True
    except Exception as e:
        return test_fail("API endpoints", str(e))


def main():
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}AXI End-to-End Test Suite{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    tests = [
        ("Config Loader", test_config_loader),
        ("Promotion Engine", test_promotion_engine),
        ("SQL Scanner", test_sql_scanner),
        ("Metadata Extraction", test_metadata_extraction),
        ("Metadata Writer", test_metadata_writer),
        ("Metadata Indexer", test_metadata_indexer),
        ("Full Pipeline", test_full_pipeline),
        ("API Endpoints", test_api_endpoints),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            results.append((name, test_fail(name, str(e))))
        print()
    
    # Summary
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    if passed == total:
        print(f"{Colors.GREEN}✅ All {passed}/{total} tests passed!{Colors.END}")
        return 0
    else:
        print(f"{Colors.RED}❌ {passed}/{total} tests passed{Colors.END}")
        for name, result in results:
            if not result:
                print(f"   {Colors.RED}✗{Colors.END} {name}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

