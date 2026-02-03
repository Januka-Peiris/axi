# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""Tests for AXI exception hierarchy and error serialization."""

import unittest

from axi.exceptions import (
    AXIBaseException,
    ValidationError,
    IntentValidationError,
    ContractViolationError,
    DeploymentValidationError,
    MetadataError,
    QueryError,
    MetricDisabledError,
    ConfigurationError,
)


class TestValidationErrorHierarchy(unittest.TestCase):
    """ValidationError hierarchy and HTTP status codes."""

    def test_intent_validation_error_is_validation_error(self):
        self.assertTrue(issubclass(IntentValidationError, ValidationError))
        self.assertTrue(issubclass(IntentValidationError, AXIBaseException))

    def test_contract_violation_error_is_validation_error(self):
        self.assertTrue(issubclass(ContractViolationError, ValidationError))

    def test_validation_error_http_status_400(self):
        e = ValidationError("Bad input", code="BAD_INPUT")
        self.assertEqual(e.http_status, 400)

    def test_deployment_validation_error_http_status_422(self):
        e = DeploymentValidationError("Deploy failed", code="DEPLOYMENT_VALIDATION_FAILED")
        self.assertEqual(e.http_status, 422)

    def test_metadata_error_http_status_404(self):
        e = MetadataError("Not found", code="ENTITY_NOT_FOUND")
        self.assertEqual(e.http_status, 404)


class TestExceptionToDict(unittest.TestCase):
    """Structured to_dict() for API JSON."""

    def test_to_dict_has_code_and_message(self):
        e = ValidationError("Dimension not on path", code="DIMENSION_NOT_ON_PATH")
        d = e.to_dict()
        self.assertEqual(d["code"], "DIMENSION_NOT_ON_PATH")
        self.assertEqual(d["message"], "Dimension not on path")

    def test_to_dict_includes_hint_and_context_when_present(self):
        e = ValidationError(
            "Invalid grain",
            code="GRAIN_INCOMPATIBLE",
            hint="Grain must reference base entity or join path.",
            context={"metric_name": "mrr", "offending_entity_or_dimension": "x.y"},
        )
        d = e.to_dict()
        self.assertEqual(d["hint"], "Grain must reference base entity or join path.")
        self.assertEqual(d["context"]["metric_name"], "mrr")
        self.assertEqual(d["context"]["offending_entity_or_dimension"], "x.y")

    def test_deployment_validation_error_to_dict_includes_result_details(self):
        class FakeResult:
            errors = ["Metric disabled: x"]
            warnings = ["Deprecated: y"]
            disabled_metrics = ["x"]
            conflict_details = []

        e = DeploymentValidationError(
            "Deployment validation failed",
            code="DEPLOYMENT_VALIDATION_FAILED",
            result=FakeResult(),
        )
        d = e.to_dict()
        self.assertIn("context", d)
        self.assertEqual(d["context"]["errors"], ["Metric disabled: x"])
        self.assertEqual(d["context"]["warnings"], ["Deprecated: y"])
        self.assertEqual(d["context"]["disabled_metrics"], ["x"])
