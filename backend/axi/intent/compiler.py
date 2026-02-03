# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
AXI Metric SQL Compiler.

Resolves a Semantic Intent into a query plan and compiles warehouse-native SQL.
Does NOT execute SQL; prefers clarity over cleverness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, TYPE_CHECKING

from axi.intent.models import (
    SemanticIntent,
    Measure,
    TimeDimension,
    JoinStep,
    SimpleFilter,
    AndFilter,
    OrFilter,
    IntentFilter,
)
from axi.utils.sanitization import sanitize_identifier

if TYPE_CHECKING:
    from axi.metadata.indexer import MetadataIndexer


# --- Query plan (resolved, no SQL) ---

@dataclass
class ResolvedSelect:
    """Single SELECT expression: alias.col AS output_name or AGG(alias.col) AS name."""
    expr: str  # e.g. "o.amount" or "SUM(o.amount)"
    output_name: str


@dataclass
class QueryPlan:
    """Resolved query plan: tables, joins, selects, filters, group_by. No raw SQL."""
    base_table: str
    base_alias: str
    joins: List[Tuple[str, str, str, str, str]]  # (table, alias, on_left, on_right, join_type)
    select_list: List[ResolvedSelect]
    where_clauses: List[str]
    group_by_list: List[str]  # alias.col expressions
    entity_to_alias: Dict[str, str]
    alias_to_entity: Dict[str, str]


# --- Warehouse type ---

WarehouseType = str  # "snowflake", "postgres", etc.


def _entity_to_alias_map(intent: SemanticIntent) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Build deterministic entity -> alias and alias -> entity maps.
    Base entity first, then join path order (from_entity, to_entity). Aliases: first letter, then first two, then entity name.
    """
    entities: List[str] = [intent.base_entity]
    for step in intent.join_path:
        if step.from_entity not in entities:
            entities.append(step.from_entity)
        if step.to_entity not in entities:
            entities.append(step.to_entity)
    entity_to_alias: Dict[str, str] = {}
    alias_to_entity: Dict[str, str] = {}
    for entity in entities:
        alias = entity[:1].lower()
        suffix = 0
        while alias in alias_to_entity and alias_to_entity.get(alias) != entity:
            suffix += 1
            alias = (entity[:2] if len(entity) >= 2 else entity) + str(suffix)
        entity_to_alias[entity] = alias
        alias_to_entity[alias] = entity
    return entity_to_alias, alias_to_entity


def _resolve_column_ref(
    ref: str,
    entity_to_alias: Dict[str, str],
    alias_to_entity: Dict[str, str],
) -> str:
    """
    Resolve column ref (entity.column or alias.column) to alias.column for SQL.
    """
    if "." not in ref:
        return ref
    left, col = ref.split(".", 1)
    left = left.strip()
    col = col.strip()
    if not col:
        return ref
    if left in entity_to_alias:
        return f"{entity_to_alias[left]}.{col}"
    if left in alias_to_entity:
        return f"{left}.{col}"
    return f"{left}.{col}"


def _aggregation_sql(agg: str, expr: str, warehouse: WarehouseType) -> str:
    """Map aggregation type to SQL expression. expr is already alias.col or *."""
    if agg == "count" and expr.strip() == "*":
        return "COUNT(*)"
    if agg == "count_distinct":
        return f"COUNT(DISTINCT {expr})"
    a = agg.upper()
    if a == "SUM":
        return f"SUM({expr})"
    if a == "COUNT":
        return f"COUNT({expr})"
    if a == "AVG":
        return f"AVG({expr})"
    if a == "MIN":
        return f"MIN({expr})"
    if a == "MAX":
        return f"MAX({expr})"
    return f"SUM({expr})"


def _escape_value(v: Any) -> str:
    """Escape value for SQL literal. Numbers unquoted, strings single-quoted, escape quotes."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def _filter_to_sql(
    f: IntentFilter,
    entity_to_alias: Dict[str, str],
    alias_to_entity: Dict[str, str],
    warehouse: WarehouseType,
) -> str:
    """Render a single filter to SQL predicate. Values are escaped for safety."""
    if isinstance(f, SimpleFilter):
        dim_sql = _resolve_column_ref(f.dimension, entity_to_alias, alias_to_entity)
        if f.op in ("IS NULL", "IS NOT NULL"):
            return f"{dim_sql} {f.op}"
        if f.op in ("IN", "NOT IN"):
            if isinstance(f.value, list):
                parts = [_escape_value(v) for v in f.value]
                return f"{dim_sql} {f.op} ({', '.join(parts)})"
            return f"{dim_sql} {f.op} ({_escape_value(f.value)})"
        if f.op == "BETWEEN" and isinstance(f.value, (list, tuple)) and len(f.value) == 2:
            return f"{dim_sql} BETWEEN {_escape_value(f.value[0])} AND {_escape_value(f.value[1])}"
        return f"{dim_sql} {f.op} {_escape_value(f.value)}"
    if isinstance(f, AndFilter):
        return "(" + " AND ".join(
            _filter_to_sql(c, entity_to_alias, alias_to_entity, warehouse) for c in f.clauses
        ) + ")"
    if isinstance(f, OrFilter):
        return "(" + " OR ".join(
            _filter_to_sql(c, entity_to_alias, alias_to_entity, warehouse) for c in f.clauses
        ) + ")"
    return ""


def resolve_plan(
    intent: SemanticIntent,
    warehouse: WarehouseType,
    indexer: Optional["MetadataIndexer"] = None,
) -> QueryPlan:
    """
    Resolve semantic intent into a query plan (enforce grain, joins, filters, time).
    Does not emit SQL.
    """
    entity_to_alias, alias_to_entity = _entity_to_alias_map(intent)

    # Base table: use first join path entity when base_entity is a mart (not in join path)
    join_entities = set()
    for step in intent.join_path:
        join_entities.add(step.from_entity)
        join_entities.add(step.to_entity)
    if intent.join_path and intent.base_entity not in join_entities:
        base_entity = intent.join_path[0].from_entity
    else:
        base_entity = intent.base_entity

    base_table = base_entity
    if indexer:
        ent = indexer.get_entity(base_entity)
        if ent and ent.get("physical_location"):
            base_table = ent["physical_location"]
        elif ent:
            db = ent.get("database_name")
            schema = ent.get("schema_name")
            table = ent.get("model") or ent.get("name")
            if db and schema and table:
                base_table = f"{db}.{schema}.{table}"
            elif table:
                base_table = table
    base_alias = entity_to_alias[base_entity]

    # Joins from intent.join_path (already resolved)
    joins: List[Tuple[str, str, str, str, str]] = []
    for step in intent.join_path:
        to_table = step.to_entity
        if indexer:
            ent = indexer.get_entity(step.to_entity)
            if ent and ent.get("physical_location"):
                to_table = ent["physical_location"]
            elif ent:
                db = ent.get("database_name")
                schema = ent.get("schema_name")
                t = ent.get("model") or ent.get("name")
                if db and schema and t:
                    to_table = f"{db}.{schema}.{t}"
                elif t:
                    to_table = t
        to_alias = entity_to_alias[step.to_entity]
        joins.append((
            to_table,
            to_alias,
            f"{entity_to_alias[step.from_entity]}.{step.from_column}",
            f"{to_alias}.{step.to_column}",
            step.join_type,
        ))

    # SELECT: dimensions + time_dimension + measures
    select_list: List[ResolvedSelect] = []
    group_by_list: List[str] = []

    for dim in intent.dimensions:
        resolved = _resolve_column_ref(dim, entity_to_alias, alias_to_entity)
        select_list.append(ResolvedSelect(expr=resolved, output_name=resolved.split(".")[-1]))
        group_by_list.append(resolved)

    if intent.time_dimension:
        td = intent.time_dimension
        ref = _resolve_column_ref(td.column_ref, entity_to_alias, alias_to_entity)
        if td.granularity and warehouse == "snowflake":
            unit = td.granularity.upper()
            select_list.append(ResolvedSelect(expr=f"DATE_TRUNC('{unit}', {ref})", output_name=td.name))
            group_by_list.append(f"DATE_TRUNC('{unit}', {ref})")
        else:
            select_list.append(ResolvedSelect(expr=ref, output_name=td.name))
            group_by_list.append(ref)

    # Grain: intent.grain columns (if any) added to GROUP BY and SELECT when not already present
    for g in intent.grain:
        resolved = _resolve_column_ref(g, entity_to_alias, alias_to_entity)
        if resolved not in group_by_list:
            group_by_list.append(resolved)
        if not any(s.expr == resolved for s in select_list):
            select_list.append(ResolvedSelect(expr=resolved, output_name=resolved.split(".")[-1]))

    for m in intent.measures:
        col_ref = _resolve_column_ref(m.column_ref, entity_to_alias, alias_to_entity)
        agg_expr = _aggregation_sql(m.aggregation, col_ref, warehouse)
        select_list.append(ResolvedSelect(expr=agg_expr, output_name=m.name))

    # WHERE from intent.filters
    where_clauses: List[str] = []
    for f in intent.filters:
        pred = _filter_to_sql(f, entity_to_alias, alias_to_entity, warehouse)
        if pred:
            where_clauses.append(pred)

    return QueryPlan(
        base_table=base_table,
        base_alias=base_alias,
        joins=joins,
        select_list=select_list,
        where_clauses=where_clauses,
        group_by_list=group_by_list,
        entity_to_alias=entity_to_alias,
        alias_to_entity=alias_to_entity,
    )


def _quote_identifier(name: str, warehouse: WarehouseType) -> str:
    """Quote identifier for warehouse. Snowflake: double quotes for case sensitivity."""
    try:
        sanitize_identifier(name)
    except ValueError:
        return name
    if warehouse == "snowflake":
        return f'"{name}"' if name else name
    return name


def emit_sql(
    plan: QueryPlan,
    warehouse: WarehouseType,
    indent: str = "  ",
) -> str:
    """
    Emit warehouse-native SQL from a query plan.
    Readable, copy-pasteable, deterministic (order of SELECT/GROUP BY fixed).
    """
    lines: List[str] = []
    sel = indent + (",\n" + indent).join(
        f"{s.expr} AS {_quote_identifier(s.output_name, warehouse)}" for s in plan.select_list
    )
    from_clause = f"{plan.base_table} AS {plan.base_alias}"
    for table, alias, on_left, on_right, join_type in plan.joins:
        j = join_type.upper()
        if j not in ("LEFT", "INNER", "RIGHT", "FULL"):
            j = "LEFT"
        from_clause += f"\n{j} JOIN {table} AS {alias} ON {on_left} = {on_right}"
    lines.append("SELECT")
    lines.append(sel)
    lines.append("FROM " + from_clause)
    if plan.where_clauses:
        lines.append("WHERE " + " AND ".join(plan.where_clauses))
    if plan.group_by_list:
        lines.append("GROUP BY " + ", ".join(plan.group_by_list))
    return "\n".join(lines)


ContractMode = Literal["warn", "strict"]


def compile_metric(
    intent: SemanticIntent,
    warehouse: WarehouseType = "snowflake",
    indexer: Optional["MetadataIndexer"] = None,
    deprecated: bool = False,
    status: Optional[str] = None,
    replacement_metric: Optional[str] = None,
    generated_at: Optional[datetime] = None,
    validate_contract: bool = True,
    register_fingerprint: bool = False,
    contract_mode: Optional[ContractMode] = None,
) -> str:
    """
    Compile a Semantic Intent into warehouse-native SQL.

    - intent: Semantic Intent (metric_name, base_entity, measures, dimensions, filters, join_path, etc.)
    - warehouse: "snowflake" (initial), "postgres", etc.
    - indexer: optional MetadataIndexer to resolve entity -> physical_location
    - deprecated: if True, add deprecated flag in AXI comment (overridden by status)
    - status: "active" | "deprecated" | "disabled"; if "disabled", raises MetricDisabledError
    - replacement_metric: optional; emitted in comment when deprecated
    - generated_at: timestamp for comment (default: now UTC)
    - validate_contract: deprecated; validation against contract_schema.json is always performed (no bypass).
    - register_fingerprint: if True and indexer is set, register SQL fingerprint for usage tracking (read-only, no PII)
    - contract_mode: "strict" (default) = violations hard-fail; "warn" = violations emit warnings but allow compile.
      If None, uses get_settings().contract_enforcement_mode.

    Returns SQL string with AXI metadata comments. Does NOT execute.
    """
    from axi.exceptions import MetricDisabledError
    from axi.intent.validation import validate_intent_for_compilation

    validate_intent_for_compilation(intent)

    effective_status = (status or "active").strip().lower()
    if effective_status == "disabled":
        raise MetricDisabledError(
            f"Metric '{intent.metric_name}' is disabled and cannot be compiled.",
            code="METRIC_DISABLED",
            hint="Re-enable the metric or use a different metric.",
            context={"metric_name": intent.metric_name},
        )

    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    compiled_at_iso8601 = generated_at.strftime("%Y-%m-%dT%H:%M:%SZ")

    plan = resolve_plan(intent, warehouse, indexer)
    sql = emit_sql(plan, warehouse)

    effective_deprecated = deprecated or effective_status == "deprecated"
    lifecycle_status = "deprecated" if effective_deprecated else effective_status
    from axi.sql_metadata import format_axi_sql_header
    header = format_axi_sql_header(
        metric_name=intent.metric_name,
        metric_version=intent.metric_version,
        lifecycle_status=lifecycle_status,
        compiled_at_utc_iso8601=compiled_at_iso8601,
        replacement_metric=replacement_metric,
        include_deprecation_warning=effective_deprecated,
    )
    full_sql = header + sql + ";"

    # Validate against contract_schema.json; behavior by contract_mode (strict=raise, warn=log and allow).
    from axi.contract.validator import validate_sql_contract
    from axi.exceptions import ContractViolationError
    mode = contract_mode
    if mode is None:
        from axi.config.settings import get_settings
        mode = get_settings().contract_enforcement_mode
    violations = validate_sql_contract(full_sql, strip_axi_comments=True)
    if violations:
        if mode == "strict":
            v = violations[0]
            raise ContractViolationError(
                v.message,
                code=v.rule_id,
                hint="AXI-generated SQL must comply with the BI contract (no session state, temp tables, stored procedures, SELECT *, or non-deterministic functions).",
                context={"snippet": v.snippet},
            )
        import logging
        log = logging.getLogger("axi.intent.compiler")
        for v in violations:
            log.warning("Contract violation (warn mode): %s [%s] snippet=%s", v.message, v.rule_id, v.snippet or "")
    # Fingerprinting MUST occur after metadata insertion; SQL text equality implies fingerprint equality.
    if register_fingerprint and indexer is not None:
        from axi.usage.fingerprint import sql_fingerprint
        fp = sql_fingerprint(full_sql)
        indexer.record_fingerprint(
            fingerprint=fp,
            metric_name=intent.metric_name,
            metric_version=intent.metric_version,
            deprecated=effective_deprecated,
            first_seen_utc=compiled_at_iso8601,
        )
    return full_sql
