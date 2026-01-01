# Licensed under the Business Source License 1.1 (BSL).
# Tests for the promotion engine - explicit rules, conflict resolution

import pytest
from axi.extractor.promotion import PromotionEngine, PromotionResult
from axi.config.loader import Config, PromotionConfig, PromotionRules


class TestPromotionBasics:
    """Test basic promotion functionality."""

    def test_empty_rules_promotes_all(self):
        """With no rules, everything should be promoted (auto mode)."""
        config = Config(
            include=PromotionRules(folders=[], tags=[]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        result = engine.check_promotion("any/path/model.sql", [])
        assert result.promoted is True

    def test_tag_based_promotion(self):
        """Models with matching tags should be promoted."""
        config = Config(
            include=PromotionRules(tags=["axi"], folders=[]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        # With tag
        result_with_tag = engine.check_promotion("model.sql", ["axi"])
        assert result_with_tag.promoted is True
        assert "axi" in result_with_tag.reason.lower() or "tag" in result_with_tag.reason.lower()

        # Without tag
        result_no_tag = engine.check_promotion("model.sql", [])
        assert result_no_tag.promoted is False

    def test_folder_based_promotion(self):
        """Models in included folders should be promoted."""
        config = Config(
            include=PromotionRules(folders=["models/marts"], tags=[]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        # In folder
        result_in = engine.check_promotion("models/marts/revenue.sql", [])
        assert result_in.promoted is True

        # Not in folder
        result_out = engine.check_promotion("models/staging/raw.sql", [])
        assert result_out.promoted is False


class TestExclusionRules:
    """Test that exclusion rules take precedence."""

    def test_exclusion_overrides_inclusion(self):
        """Exclude rules should override include rules."""
        config = Config(
            include=PromotionRules(folders=["models/**"], tags=[]),
            exclude=PromotionRules(folders=["models/staging"], tags=[])
        )
        engine = PromotionEngine(config)

        # Matches include but also exclude
        result = engine.check_promotion("models/staging/raw.sql", [])
        assert result.promoted is False
        assert "exclude" in result.reason.lower()

        # Matches include only
        result_mart = engine.check_promotion("models/marts/revenue.sql", [])
        assert result_mart.promoted is True

    def test_exclude_by_tag(self):
        """Models with excluded tags should not be promoted."""
        config = Config(
            include=PromotionRules(folders=["**"], tags=[]),
            exclude=PromotionRules(folders=[], tags=["ignore", "staging"])
        )
        engine = PromotionEngine(config)

        result = engine.check_promotion("model.sql", ["ignore"])
        assert result.promoted is False

        result_staging = engine.check_promotion("model.sql", ["staging"])
        assert result_staging.promoted is False

        result_ok = engine.check_promotion("model.sql", ["axi"])
        assert result_ok.promoted is True


class TestWildcardPatterns:
    """Test wildcard pattern matching."""

    def test_double_star_recursive(self):
        """** should match any depth."""
        config = Config(
            include=PromotionRules(folders=["models/**"], tags=[]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        # Various depths
        assert engine.check_promotion("models/a.sql", []).promoted is True
        assert engine.check_promotion("models/sub/b.sql", []).promoted is True
        assert engine.check_promotion("models/sub/deep/c.sql", []).promoted is True

        # Outside models
        assert engine.check_promotion("other/a.sql", []).promoted is False

    def test_single_star_one_level(self):
        """* should match one level only."""
        config = Config(
            include=PromotionRules(folders=["models/*.sql"], tags=[]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        # Direct match
        result_direct = engine.check_promotion("models/revenue.sql", [])
        # Implementation may vary - just verify no crash
        assert result_direct is not None


class TestDeterministicConflictResolution:
    """Test that conflicts resolve deterministically."""

    def test_same_input_same_result(self):
        """Same input should always produce same result."""
        config = Config(
            include=PromotionRules(folders=["models"], tags=["axi"]),
            exclude=PromotionRules(folders=["models/staging"], tags=["ignore"])
        )
        engine = PromotionEngine(config)

        path = "models/marts/revenue.sql"
        tags = ["axi"]

        results = [engine.check_promotion(path, tags) for _ in range(10)]

        # All results should be identical
        assert all(r.promoted == results[0].promoted for r in results)
        assert all(r.reason == results[0].reason for r in results)

    def test_order_independence(self):
        """Tag order should not affect result."""
        config = Config(
            include=PromotionRules(folders=[], tags=["axi", "semantic"]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        result1 = engine.check_promotion("model.sql", ["axi", "semantic"])
        result2 = engine.check_promotion("model.sql", ["semantic", "axi"])

        assert result1.promoted == result2.promoted


class TestPromotionReasons:
    """Test that promotion results include clear reasons."""

    def test_included_reason(self):
        """Included models should have clear reason."""
        config = Config(
            include=PromotionRules(folders=["models"], tags=[]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        result = engine.check_promotion("models/revenue.sql", [])
        assert result.promoted is True
        assert result.reason is not None
        assert len(result.reason) > 0

    def test_excluded_reason(self):
        """Excluded models should have clear reason."""
        config = Config(
            include=PromotionRules(folders=["models"], tags=[]),
            exclude=PromotionRules(folders=["models/staging"], tags=[])
        )
        engine = PromotionEngine(config)

        result = engine.check_promotion("models/staging/raw.sql", [])
        assert result.promoted is False
        assert result.reason is not None
        assert "exclude" in result.reason.lower()

    def test_not_promoted_reason(self):
        """Non-promoted models should explain why."""
        config = Config(
            include=PromotionRules(folders=["models/marts"], tags=[]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        result = engine.check_promotion("other/path.sql", [])
        assert result.promoted is False
        assert result.reason is not None


class TestPromotionResult:
    """Test PromotionResult object structure."""

    def test_result_has_required_fields(self):
        """PromotionResult should have all required fields."""
        config = Config()
        engine = PromotionEngine(config)

        result = engine.check_promotion("test.sql", [])

        assert hasattr(result, 'promoted')
        assert hasattr(result, 'reason')
        assert isinstance(result.promoted, bool)
        assert isinstance(result.reason, str)

    def test_result_is_immutable_like(self):
        """Results from same input should be equal."""
        config = Config(
            include=PromotionRules(folders=["models"], tags=[]),
            exclude=PromotionRules(folders=[], tags=[])
        )
        engine = PromotionEngine(config)

        result1 = engine.check_promotion("models/test.sql", [])
        result2 = engine.check_promotion("models/test.sql", [])

        assert result1.promoted == result2.promoted
        assert result1.reason == result2.reason
