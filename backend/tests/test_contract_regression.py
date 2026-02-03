# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Regression tests for AXI SQL contract.

These tests MUST fail if the contract is weakened (e.g. a rule is removed or
a disallowed pattern stops being detected). CI blocks merges on failure.
"""

import unittest

from axi.contract.loader import get_contract
from axi.contract.validator import validate_sql_contract

# Frozen set of rule IDs in contract_schema.json. Removing a rule = regression.
CONTRACT_RULE_IDS = frozenset({
    "no_session_state",
    "no_temp_tables",
    "no_stored_procedures",
    "no_procedure_udf_definitions",
    "no_nondeterministic_functions",
    "no_select_star",
    "no_transaction_control",
    "no_ddl",
})

# SQL that must remain VALID (no violations). If contract is over-tightened, these may fail.
VALID_SQL_SNIPPETS = [
    "SELECT a.x, SUM(b.y) AS total FROM t AS a LEFT JOIN s AS b ON a.id = b.id GROUP BY a.x;",
    "SELECT 1 AS x;",
    "SELECT o.amount, c.region FROM orders AS o JOIN customers AS c ON o.customer_id = c.id GROUP BY o.amount, c.region;",
    "SELECT COUNT(*) AS cnt, MIN(d.created_at) AS first FROM events AS d;",
    "-- axi.metric_name: m\n-- axi.metric_version: 1.0\n\nSELECT id, SUM(amount) AS total FROM orders GROUP BY id;",
    "SELECT DATE_TRUNC('month', d.created_at) AS month FROM events AS d GROUP BY 1;",
    "SELECT CURRENT_DATE AS d, col FROM t GROUP BY col;",
]

# For each rule_id, SQL that must be flagged with that rule. Weakening a rule = regression.
INVALID_SQL_BY_RULE = {
    "no_session_state": [
        "USE database_name; SELECT 1 AS x;",
        "SET session_var = 1; SELECT 1;",
        "ALTER SESSION SET QUOTED_IDENTIFIERS = ON; SELECT 1;",
    ],
    "no_temp_tables": [
        "CREATE TEMP TABLE x (id INT); SELECT id FROM x;",
        "CREATE TEMPORARY VIEW v AS SELECT 1 AS x;",
    ],
    "no_stored_procedures": [
        "CALL my_proc(); SELECT 1;",
        "EXEC my_proc; SELECT 1;",
    ],
    "no_procedure_udf_definitions": [
        "CREATE PROCEDURE my_proc() BEGIN SELECT 1; END;",
        "CREATE FUNCTION my_func() RETURNS INT RETURN 1;",
        "CREATE OR REPLACE PROCEDURE p() BEGIN END;",
    ],
    "no_nondeterministic_functions": [
        "SELECT RAND() AS r FROM t;",
        "SELECT NEWID() AS id FROM t;",
        "SELECT UUID() AS u FROM t;",
    ],
    "no_select_star": [
        "SELECT * FROM orders AS o;",
        "SELECT * FROM t WHERE x = 1;",
    ],
    "no_transaction_control": [
        "COMMIT; SELECT 1;",
        "ROLLBACK; SELECT 1;",
        "BEGIN TRANSACTION; SELECT 1;",
    ],
    "no_ddl": [
        "CREATE TABLE x (id INT); SELECT 1;",
        "DROP VIEW v; SELECT 1;",
        "ALTER TABLE t ADD COLUMN c INT; SELECT 1;",
    ],
}


class TestContractSchemaRegression(unittest.TestCase):
    """Contract schema must not lose rules (regression lock)."""

    def test_contract_rule_ids_unchanged(self):
        """Removing or renaming a disallowed rule is a regression."""
        contract = get_contract()
        rule_ids = {r.get("id") for r in (contract.get("disallowed_patterns") or []) if r.get("id")}
        self.assertEqual(
            rule_ids,
            set(CONTRACT_RULE_IDS),
            "Contract disallowed_patterns rule IDs must not change. "
            "Removing or renaming a rule weakens the contract. "
            "Update CONTRACT_RULE_IDS in test_contract_regression.py if intentional.",
        )


class TestValidSqlRemainsValid(unittest.TestCase):
    """Previously valid SQL must remain valid. Over-tightening the contract fails these."""

    def test_each_valid_snippet_has_no_violations(self):
        for i, sql in enumerate(VALID_SQL_SNIPPETS):
            with self.subTest(valid_sql_index=i, snippet=sql[:60]):
                violations = validate_sql_contract(sql, strip_axi_comments=True)
                self.assertEqual(
                    violations,
                    [],
                    f"Valid SQL must not be flagged. Snippet: {sql[:80]}... Violations: {violations}",
                )


class TestInvalidSqlRemainsInvalid(unittest.TestCase):
    """Previously invalid SQL must remain invalid. Weakening a rule fails these."""

    def test_each_invalid_snippet_flagged_with_expected_rule(self):
        for rule_id, snippets in INVALID_SQL_BY_RULE.items():
            for j, sql in enumerate(snippets):
                with self.subTest(rule_id=rule_id, snippet_index=j, snippet=sql[:60]):
                    violations = validate_sql_contract(sql, strip_axi_comments=True)
                    rule_violations = [v for v in violations if v.rule_id == rule_id]
                    self.assertGreater(
                        len(rule_violations),
                        0,
                        f"SQL that must violate {rule_id} was not flagged. "
                        f"Snippet: {sql[:80]}... All violations: {violations}. "
                        "Contract may have been weakened.",
                    )

    def test_all_contract_rules_have_invalid_examples(self):
        """Every rule in the schema must have at least one regression snippet."""
        for rule_id in CONTRACT_RULE_IDS:
            with self.subTest(rule_id=rule_id):
                self.assertIn(
                    rule_id,
                    INVALID_SQL_BY_RULE,
                    f"Regression suite must include invalid SQL for rule {rule_id}",
                )
                self.assertGreater(
                    len(INVALID_SQL_BY_RULE[rule_id]),
                    0,
                    f"At least one invalid snippet required for rule {rule_id}",
                )
