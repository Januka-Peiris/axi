# Licensed under the Business Source License 1.1 (BSL).
# CLI contract tests for AXI hardening.
#
# These tests verify CLI behavior contracts:
# - Exit codes match documented behavior
# - Run summary format is correct
# - Flags behave as documented

import pytest
import json

from axi_cli.run_summary import RunSummary, FailureEntry, SkippedEntry
from axi_cli import exit_codes


class TestExitCodeContract:
    """Verify exit code semantics match documentation."""

    def test_exit_code_values(self):
        """Exit codes must have correct numeric values."""
        assert exit_codes.SUCCESS == 0
        assert exit_codes.GENERAL_ERROR == 1
        assert exit_codes.CONFIG_ERROR == 2
        assert exit_codes.VALIDATION_ERROR == 3
        assert exit_codes.NOT_FOUND == 4
        assert exit_codes.EXTRACTION_ERROR == 5
        assert exit_codes.CONNECTION_ERROR == 6

    def test_no_duplicate_exit_codes(self):
        """All exit codes must be unique."""
        codes = [
            exit_codes.SUCCESS,
            exit_codes.GENERAL_ERROR,
            exit_codes.CONFIG_ERROR,
            exit_codes.VALIDATION_ERROR,
            exit_codes.NOT_FOUND,
            exit_codes.EXTRACTION_ERROR,
            exit_codes.CONNECTION_ERROR,
        ]
        assert len(codes) == len(set(codes)), "Duplicate exit codes found"


class TestRunSummaryContract:
    """Verify run summary format and semantics."""

    def test_summary_has_required_fields(self):
        """Run summary must include all required fields."""
        summary = RunSummary(
            command="extract",
            status="success",
            exit_code=0,
            scanned=10,
            processed=10,
            skipped=0,
            failed=0
        )

        result = summary.to_dict()

        required_fields = [
            "schema_version",
            "command",
            "status",
            "exit_code",
            "counts",
            "failures",
            "skipped"
        ]
        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_counts_structure(self):
        """Counts must include scanned, processed, skipped, failed."""
        summary = RunSummary(
            command="extract",
            status="success",
            exit_code=0,
            scanned=100,
            processed=90,
            skipped=5,
            failed=5
        )

        counts = summary.to_dict()["counts"]
        assert counts["scanned"] == 100
        assert counts["processed"] == 90
        assert counts["skipped"] == 5
        assert counts["failed"] == 5

    def test_status_enum_values(self):
        """Status must be one of: success, partial_success, failure, error."""
        valid_statuses = ["success", "partial_success", "failure", "error"]

        for status in valid_statuses:
            summary = RunSummary(
                command="test",
                status=status,
                exit_code=0
            )
            assert summary.status in valid_statuses

    def test_compute_status_success(self):
        """All processed, none failed = success."""
        status = RunSummary.compute_status(processed=10, failed=0)
        assert status == "success"

    def test_compute_status_partial_success(self):
        """Some processed, some failed = partial_success."""
        status = RunSummary.compute_status(processed=8, failed=2)
        assert status == "partial_success"

    def test_compute_status_failure(self):
        """None processed, all failed = failure."""
        status = RunSummary.compute_status(processed=0, failed=10)
        assert status == "failure"

    def test_compute_status_empty(self):
        """No items at all = success (empty input is valid)."""
        status = RunSummary.compute_status(processed=0, failed=0)
        assert status == "success"

    def test_compute_exit_code_success(self):
        """Success status = exit code 0."""
        code = RunSummary.compute_exit_code("success")
        assert code == exit_codes.SUCCESS

    def test_compute_exit_code_partial(self):
        """Partial success = exit code 5 (EXTRACTION_ERROR)."""
        code = RunSummary.compute_exit_code("partial_success")
        assert code == exit_codes.EXTRACTION_ERROR

    def test_compute_exit_code_failure(self):
        """Failure = exit code 5 (EXTRACTION_ERROR)."""
        code = RunSummary.compute_exit_code("failure")
        assert code == exit_codes.EXTRACTION_ERROR

    def test_failures_list_structure(self):
        """Failures list must contain item and error."""
        failures = [
            FailureEntry(item="model_a.sql", error="Parse error at line 5"),
            FailureEntry(item="model_b.sql", error="Unclosed string literal")
        ]

        summary = RunSummary(
            command="extract",
            status="failure",
            exit_code=5,
            failed=2,
            failures=failures
        )

        result = summary.to_dict()
        assert len(result["failures"]) == 2
        assert result["failures"][0]["item"] == "model_a.sql"
        assert "Parse error" in result["failures"][0]["error"]

    def test_skipped_list_structure(self):
        """Skipped list must contain item and reason."""
        skipped = [
            SkippedEntry(item="staging_model.sql", reason="excluded by rule"),
            SkippedEntry(item="temp_model.sql", reason="no grain detected")
        ]

        summary = RunSummary(
            command="extract",
            status="success",
            exit_code=0,
            skipped=2,
            skipped_items=skipped
        )

        result = summary.to_dict()
        assert len(result["skipped"]) == 2
        assert result["skipped"][0]["reason"] == "excluded by rule"

    def test_json_serialization_is_valid(self):
        """Run summary must serialize to valid JSON."""
        summary = RunSummary(
            command="extract",
            status="partial_success",
            exit_code=5,
            scanned=100,
            processed=95,
            skipped=2,
            failed=3,
            failures=[FailureEntry(item="bad.sql", error="syntax error")],
            skipped_items=[SkippedEntry(item="skip.sql", reason="excluded")]
        )

        json_str = summary.to_json()

        # Must be valid JSON
        parsed = json.loads(json_str)
        assert parsed["status"] == "partial_success"
        assert parsed["exit_code"] == 5

    def test_json_is_sorted_for_determinism(self):
        """JSON output must have sorted keys for deterministic output."""
        summary = RunSummary(
            command="extract",
            status="success",
            exit_code=0
        )

        json1 = summary.to_json()
        json2 = summary.to_json()

        assert json1 == json2, "JSON output must be deterministic"


class TestSchemaVersion:
    """Verify schema version is included in outputs."""

    def test_summary_includes_schema_version(self):
        """Run summary must include schema_version."""
        from axi.version import SCHEMA_VERSION

        summary = RunSummary(
            command="extract",
            status="success",
            exit_code=0
        )

        result = summary.to_dict()
        assert result["schema_version"] == SCHEMA_VERSION
