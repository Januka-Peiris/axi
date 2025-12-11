# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

import sqlglot
from sqlglot import exp
from typing import List, Dict, Any, Protocol
from dataclasses import dataclass, field

@dataclass
class OptimizationContext:
    config: Dict[str, Any] = field(default_factory=dict)
    rules_applied: List[str] = field(default_factory=list)

class OptimizationRule(Protocol):
    name: str
    def apply(self, expression: exp.Expression, context: OptimizationContext) -> exp.Expression:
        ...

class Optimizer:
    def __init__(self, context: OptimizationContext = None):
        self.context = context or OptimizationContext()
        self.rules: List[OptimizationRule] = []

    def add_rule(self, rule: OptimizationRule):
        self.rules.append(rule)

    def optimize(self, sql: str, dialect: str = "snowflake") -> str:
        # Parse
        expression = sqlglot.parse_one(sql, read=dialect)
        
        # Apply Rules
        for rule in self.rules:
            # Check config if rule is enabled (default true)
            if self.context.config.get(f"optimizer.rules.{rule.name}", True):
                new_expression = rule.apply(expression, self.context)
                if new_expression != expression:
                     # Track if changed? naive check
                     # Ideally rule.apply returns info if it did something
                     # For now, we rely on the rule to mutate or return new
                     self.context.rules_applied.append(rule.name)
                expression = new_expression

        return expression.sql(dialect=dialect)

    def explain(self, sql: str, dialect: str = "snowflake") -> Dict[str, Any]:
        """
        Returns info about what would be optimized.
        """
        original_sql = sql
        
        # Reset context text for run
        self.context.rules_applied = []
        optimized_sql = self.optimize(sql, dialect)
        
        return {
            "original_sql": original_sql,
            "optimized_sql": optimized_sql,
            "rules_applied": self.context.rules_applied
        }
