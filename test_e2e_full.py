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


def _pass(name):
    print(f"{Colors.GREEN}✓{Colors.END} {name}")


def _fail(name, error):
    print(f"{Colors.RED}✗{Colors.END} {name}: {error}")
    return False


def _info(name):
    print(f"{Colors.BLUE}→{Colors.END} {name}")


def test_config_loader():
    """Test config loading"""
    _info("Testing config loader...")
    
    try:
        # Test default config
        config = Config()
        assert config.include is not None
        assert config.exclude is not None
        _pass("Default config creation")
        
        # Test with promotion rules
        config = Config(
            include=PromotionRules(folders=["**"], tags=["axi"]),
            exclude=PromotionRules(folders=["test"], tags=[])
        )
        assert len(config.include.folders) == 1
        assert config.include.folders[0] == "**"
        _pass("Config with promotion rules")
    except Exception as e:
        _fail("Config loader", str(e))
        raise


def test_promotion_engine():
    """Test promotion engine"""
    _info("Testing promotion engine...")
    
    try:
        class PromoConfig:
            def __init__(self, include, exclude, mode="auto"):
                self.include = include
                self.exclude = exclude
                self.promotion = type("P", (), {"mode": mode})()

        # Test with wildcard promotion
        include_all = PromotionRules(folders=["**"], tags=[])
        exclude_none = PromotionRules(folders=[], tags=[])
        engine = PromotionEngine(PromoConfig(include_all, exclude_none))

        # Should promote everything
        assert engine.is_promoted("any/path/file.sql", []) == True
        _pass("Wildcard promotion")

        # Test with specific folder
        include_marts = PromotionRules(folders=["models/marts/**"], tags=[])
        exclude_staging = PromotionRules(folders=["models/staging/**"], tags=[])
        engine_specific = PromotionEngine(PromoConfig(include_marts, exclude_staging))
        assert engine_specific.is_promoted("models/marts/revenue.sql", []) == True
        assert engine_specific.is_promoted("models/staging/orders.sql", []) == False
        _pass("Folder-based promotion")
        
        # Test exclusion
        exclude_tests = PromotionRules(folders=["models/test/**"], tags=[])
        engine_exclude = PromotionEngine(PromoConfig(include_all, exclude_tests))
        assert engine_exclude.is_promoted("models/marts/revenue.sql", []) == True
        assert engine_exclude.is_promoted("models/test/temp.sql", []) == False
        _pass("Exclusion rules")
        
        # Test tag-based promotion
        include_tags = PromotionRules(folders=[], tags=["axi"])
        engine_tags = PromotionEngine(PromoConfig(include_tags, exclude_none))
        assert engine_tags.is_promoted("any/file.sql", ["axi"]) is True
        assert engine_tags.is_promoted("any/file.sql", []) is False
        _pass("Tag-based promotion")
    except Exception as e:
        _fail("Promotion engine", str(e))
        raise


def test_sql_scanner():
    """Test SQL scanner"""
    _info("Testing SQL scanner...")
    
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
            _pass(f"SQL scanner found {len(models)} models")
            
            # Check model paths
            paths = [m.path for m in models]
            assert "orders.sql" in paths or "models/orders.sql" in str(paths)
            _pass("Model paths correct")
    except Exception as e:
        _fail("SQL scanner", str(e))
        raise


def test_metadata_extraction():
    """Test metadata extraction"""
    _info("Testing metadata extraction...")
    
    try:
        # Test simple SELECT
        sql = "SELECT id, customer_id, amount FROM orders"
        meta = extract_metadata(sql, "orders")
        
        assert meta["model"] == "orders"
        assert "source_tables" in meta
        assert "orders" in meta["source_tables"]
        _pass("Basic SELECT extraction")
        
        # Test aggregation
        sql = "SELECT date, SUM(amount) as total_revenue FROM orders GROUP BY date"
        meta = extract_metadata(sql, "revenue")
        
        assert len(meta["metrics"]) > 0, "Should extract metrics"
        assert any("revenue" in m.get("name", "").lower() for m in meta["metrics"])
        _pass("Aggregation extraction")
        
        # Test dimensions
        assert len(meta["dimensions"]) > 0, "Should extract dimensions"
        assert "date" in meta["dimensions"]
        _pass("Dimension extraction")
    except Exception as e:
        import traceback
        traceback.print_exc()
        _fail("Metadata extraction", str(e))
        raise


def test_metadata_writer():
    """Test metadata writer"""
    _info("Testing metadata writer...")
    
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
            _pass("Metadata JSON file created")
            
            # Check content
            with open(json_file) as f:
                data = json.load(f)
            assert data["model"] == "test_model"
            _pass("Metadata JSON content correct")
    except Exception as e:
        import traceback
        traceback.print_exc()
        _fail("Metadata writer", str(e))
        raise


def test_metadata_indexer():
    """Test metadata indexer"""
    _info("Testing metadata indexer...")
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            indexer = MetadataIndexer(tmpdir)
            
            # Build index
            indexer.build_index()
            
            # Check database exists (it's created in __init__)
            db_file = Path(tmpdir) / "axi.db"
            assert db_file.exists(), "Index database should be created"
            _pass("Index database created")
            
            # Test listing (should work even if empty)
            entities = indexer.list_entities()
            metrics = indexer.list_metrics()
            assert isinstance(entities, list)
            assert isinstance(metrics, list)
            _pass("Indexer list methods work")
    except Exception as e:
        import traceback
        traceback.print_exc()
        _fail("Metadata indexer", str(e))
        raise


def test_full_pipeline():
    """Test full extraction pipeline"""
    _info("Testing full extraction pipeline...")
    
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
            _pass(f"Extracted {count} models")
            
            # Build index
            indexer.build_index()
            _pass("Index built")
            
            # Verify index
            entities = indexer.list_entities()
            metrics = indexer.list_metrics()
            
            assert len(entities) > 0, "Should have entities"
            assert len(metrics) > 0, "Should have metrics"
            _pass(f"Index has {len(entities)} entities and {len(metrics)} metrics")
    except Exception as e:
        import traceback
        traceback.print_exc()
        _fail("Full pipeline", str(e))
        raise


def test_api_endpoints():
    """Test API endpoints (if server available)"""
    _info("Testing API endpoints...")
    
    try:
        # Just test that we can import and create router instances
        from axi.api.routers import metrics, dimensions
        
        # Check routers exist
        assert metrics.router is not None
        assert dimensions.router is not None
        _pass("API routers importable")
    except Exception as e:
        _fail("API endpoints", str(e))
        raise


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
            test_func()
            results.append((name, True))
        except Exception as e:
            results.append((name, _fail(name, str(e))))
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
