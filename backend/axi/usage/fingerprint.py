# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Query fingerprinting for usage tracking.

Produces a deterministic hash from SQL so warehouse query logs can be matched
to AXI-generated metric SQL. Normalizes comments, whitespace, and literals
so BI-filled queries (e.g. different date values) still match. Read-only;
no PII; no query interception.
"""

from __future__ import annotations

import hashlib
import re
from typing import Optional


def _strip_comments(sql: str) -> str:
    """Remove SQL comments (-- and /* */). Preserves newlines for structure."""
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        # Block comment
        if i + 1 < n and sql[i : i + 2] == "/*":
            j = sql.find("*/", i + 2)
            if j == -1:
                i = n
                break
            i = j + 2
            continue
        # Line comment
        if i + 1 < n and sql[i : i + 2] == "--":
            j = sql.find("\n", i + 2)
            if j == -1:
                i = n
                break
            out.append("\n")
            i = j + 1
            continue
        out.append(sql[i])
        i += 1
    return "".join(out)


def _replace_literals(sql: str) -> str:
    """
    Replace string literals, numeric literals, and NULL/TRUE/FALSE with
    a placeholder so queries that differ only by literal values get the
    same fingerprint. No PII is retained.
    """
    placeholder = ":literal"
    out: list[str] = []
    i = 0
    n = len(sql)
    while i < n:
        # Single-quoted string (SQL: '' is escaped quote)
        if sql[i] == "'":
            out.append(placeholder)
            i += 1
            while i < n:
                if sql[i] == "'":
                    if i + 1 < n and sql[i + 1] == "'":
                        i += 2
                        continue
                    break
                i += 1
            i += 1
            continue
        # Double-quoted identifier (Snowflake) - do not replace; keep for structure
        if sql[i] == '"':
            out.append(sql[i])
            i += 1
            while i < n and sql[i] != '"':
                if sql[i] == "\\":
                    i += 1
                i += 1
            if i < n:
                out.append(sql[i])
                i += 1
            continue
        # Numeric literal (integer or decimal)
        if sql[i].isdigit() or (sql[i] == "." and i + 1 < n and sql[i + 1].isdigit()):
            out.append(placeholder)
            while i < n and (sql[i].isdigit() or sql[i] == "." or sql[i].lower() in "e+-"):
                i += 1
            continue
        # Word boundary for NULL, TRUE, FALSE (case-insensitive)
        if i < n and sql[i].isalpha():
            start = i
            while i < n and (sql[i].isalnum() or sql[i] == "_"):
                i += 1
            word = sql[start:i]
            if word.upper() in ("NULL", "TRUE", "FALSE"):
                out.append(placeholder)
            else:
                out.append(word)
            continue
        out.append(sql[i])
        i += 1
    return "".join(out)


def normalize_sql_for_fingerprint(sql: str) -> str:
    """
    Normalize SQL for deterministic fingerprinting.

    - Strips all comments (-- and /* */).
    - Replaces string, numeric, NULL/TRUE/FALSE literals with :literal.
    - Collapses whitespace to single spaces and trims.

    Same logical query (e.g. different date in WHERE) yields same normalized form.
    """
    if not sql or not sql.strip():
        return ""
    body = _strip_comments(sql)
    body = _replace_literals(body)
    # Collapse whitespace
    body = re.sub(r"\s+", " ", body)
    return body.strip()


def sql_fingerprint(sql: str) -> str:
    """
    Return a deterministic fingerprint (SHA-256 hex) for the given SQL.

    Use this to match warehouse query log text to AXI-generated metric SQL.
    """
    normalized = normalize_sql_for_fingerprint(sql)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
