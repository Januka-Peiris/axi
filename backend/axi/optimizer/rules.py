# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from sqlglot import exp, optimizer
from sqlglot.optimizer.pushdown_predicates import pushdown_predicates
from axi.optimizer.core import OptimizationRule, OptimizationContext

class PredicatePushdownRule(OptimizationRule):
    name = "predicate_pushdown"
    
    def apply(self, expression: exp.Expression, context: OptimizationContext) -> exp.Expression:
        # Use sqlglot's built-in optimizer for this
        return optimizer.optimize(expression, rules=[pushdown_predicates])

class SimplificationRule(OptimizationRule):
    name = "simplification"
    
    def apply(self, expression: exp.Expression, context: OptimizationContext) -> exp.Expression:
        # built-in simplify
        from sqlglot.optimizer.simplify import simplify
        return optimizer.optimize(expression, rules=[simplify])

class ColumnPruningRule(OptimizationRule):
    name = "column_pruning"

    def apply(self, expression: exp.Expression, context: OptimizationContext) -> exp.Expression:
        # built-in eliminate_subqueries (often does column pruning implicitly or partially)
        # sqlglot "prune_columns" is not fully semantic without schema, but "eliminate_subqueries" helps.
        # We can try "eliminate_ctes" or "eliminate_subqueries".
        # Let's use a safer set of simplifications.
        
        # NOTE: Aggressive column pruning without schema awareness is risky in sqlglot.
        # We'll stick to 'eliminate_subqueries' which merges derived tables if safe.
        from sqlglot.optimizer.eliminate_subqueries import eliminate_subqueries
        return optimizer.optimize(expression, rules=[eliminate_subqueries])

class SnowflakeHintRule(OptimizationRule):
    name = "snowflake_hints"
    
    def apply(self, expression: exp.Expression, context: OptimizationContext) -> exp.Expression:
        # Example: Add a comment hint if it's a big aggregation
        # Naive implementation
        if isinstance(expression, exp.Select):
             expression.add_comments(["AXI Optimized"])
        return expression

# Default set
def get_default_rules():
    return [
        PredicatePushdownRule(),
        SimplificationRule(),
        ColumnPruningRule(),
        SnowflakeHintRule()
    ]
